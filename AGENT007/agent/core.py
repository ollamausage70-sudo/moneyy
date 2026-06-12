import asyncio
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import config
from agent.brain import LLMBrain
from agent.database import DatabaseManager
from agent.skills.bounty_hunter import BountyHunterSkill
from agent.skills.harness import HarnessEngine
from agent.wallet import Wallet
from agent.csuite import (
    MessageBus, CSuiteRegistry, CEOAgent, CFOAgent, COOAgent,
    BizDevAgent, DeliveryAgent, QAAgent, PaymentsAgent,
    MarketingAgent, LearningAgent, SecurityAgent,
)
from agent.business_model import BusinessModelManager

logger = logging.getLogger("agent.core")


class AgentCore:
    def __init__(self, db: DatabaseManager):
        self.name = config.AGENT_NAME
        self.brain = LLMBrain()
        self.wallet = Wallet()
        self.db = db
        self.skills: dict = {}
        self.harness: Optional[HarnessEngine] = None
        self.running = False
        self.cycle_count = int(db.get_state("cycle_count", "0"))
        self.last_decision = None
        self.last_scan_summary = {}

        self.bus = MessageBus()
        self.csuite = CSuiteRegistry(self.bus)
        self.business_model = BusinessModelManager(db)
        self._csuite_inited = False

        if self.cycle_count > 0:
            logger.info("Resumed from cycle %d", self.cycle_count)

    def set_harness(self, harness: HarnessEngine):
        self.harness = harness

    def init_csuite(self):
        if self._csuite_inited:
            return
        bounty = self.skills.get("bounty_hunter")
        self.csuite.register(CEOAgent(self.brain, self.bus, self.db))
        self.csuite.register(CFOAgent(self.brain, self.bus, self.db))
        self.csuite.register(COOAgent(self.brain, self.bus, self.db))
        self.csuite.register(BizDevAgent(self.brain, self.bus, self.db, bounty))
        self.csuite.register(DeliveryAgent(self.brain, self.bus, self.db, bounty))
        self.csuite.register(QAAgent(self.brain, self.bus, self.db))
        self.csuite.register(PaymentsAgent(self.brain, self.bus, self.db, self.wallet))
        self.csuite.register(MarketingAgent(self.brain, self.bus, self.db))
        self.csuite.register(LearningAgent(self.brain, self.bus, self.db))
        self.csuite.register(SecurityAgent(self.brain, self.bus, self.db))
        self._csuite_inited = True
        logger.info("C-Suite initialized: %d agents", len(self.csuite.agents))

    def register_skill(self, name: str, skill):
        self.skills[name] = skill
        logger.info("Registered skill: %s", name)

    async def decide_next_action(self) -> Optional[dict]:
        cycle_mod = self.cycle_count % 6
        bounty: BountyHunterSkill = self.skills.get("bounty_hunter")
        stats = bounty.strategy if bounty else {}

        if cycle_mod == 0:
            return {"action": "scan", "skill": "bounty_hunter", "reason": "Scan marketplaces for tasks"}
        elif cycle_mod == 1:
            return {"action": "post_services", "skill": "bounty_hunter", "reason": "Post service listings"}
        elif cycle_mod == 2:
            return {"action": "check", "skill": "bounty_hunter", "reason": "Check balances and generate weekly report"}
        elif cycle_mod == 3:
            return {"action": "train", "skill": "bounty_hunter", "reason": "Self-training: analyze outcomes, optimize strategy"}
        elif cycle_mod == 4:
            return {"action": "harness", "skill": "bounty_hunter", "reason": "Proactive earning: forum, red packets, quests, content"}
        else:
            research_needed = stats.get("bids_placed", 0) > 0 and stats.get("bids_won", 0) == 0 and self.cycle_count > 5
            if research_needed:
                return {"action": "research", "skill": "bounty_hunter", "reason": "Analyze learning data for better opportunities"}
            return {"action": "harness", "skill": "bounty_hunter", "reason": "Content creation & passive earning"}

    async def execute_action(self, decision: dict) -> None:
        action = decision.get("action", "scan")
        skill_name = decision.get("skill", "bounty_hunter")
        skill = self.skills.get(skill_name)

        if not skill:
            logger.warning("Skill %s not found", skill_name)
            return

        self.db.add_decision(action, skill_name, decision.get("reason", ""), self.cycle_count)

        if action == "scan":
            print("=== SCAN START ===", flush=True)
            tasks = await skill.find_opportunities()
            print(f"=== SCAN FOUND {len(tasks)} TASKS ===", flush=True)
            self.last_scan_summary = {"tasks_found": len(tasks), "timestamp": datetime.utcnow().isoformat()}

            bid_count = 0
            for task in tasks[:10]:
                print(f"TASK: {task.id} reward={task.reward} source={task.source}", flush=True)
                if task.reward <= 0 or bid_count >= 5:
                    print(f"  SKIP: reward={task.reward} or bid_count={bid_count}", flush=True)
                    continue
                bid = skill._compute_bid(task)
                print(f"  BID=${bid}", flush=True)
                proposal = skill._generate_proposal(task)
                print(f"  PROPOSAL={proposal[:50]}", flush=True)
                mp = next((m for m in skill.marketplaces if m.name == task.source), None)
                print(f"  MP={mp.name if mp else 'NONE'}", flush=True)
                if mp:
                    try:
                        bid_ok = mp.submit_bid(
                            task.metadata["raw"].get("id", ""),
                            proposal,
                            bid,
                        )
                        print(f"  BID_OK={bid_ok}", flush=True)
                        skill.strategy["bids_placed"] += 1
                        skill._save_strategy()
                        if bid_ok:
                            bid_count += 1
                            logger.info("Bid submitted on %s: $%.2f", task.id, bid)
                        else:
                            logger.info("Bid failed for %s", task.id)
                    except Exception as e:
                        print(f"  BID_ERROR={e}", flush=True)
                        logger.error("Bid error %s: %s", task.id, e)

        elif action == "post_services":
            posted = skill.post_seed_services()
            logger.info("Posted %d new services on dealwork", posted)
            self.db.log_event("services_posted", {"count": posted})

        elif action == "harness":
            if self.harness:
                logger.info("Starting proactive earning cycle...")
                results = self.harness.run_all()
                self.db.log_event("harness", results)
                logger.info("Harness: %s estimated earnings", results.get("estimated_earnings", 0))

        elif action == "check":
            balance = self.wallet.get_usdc_balance()
            txns = self.wallet.get_recent_transactions()
            platform_balances = skill.check_platform_balances()
            report = skill.generate_weekly_report()
            if report:
                logger.info("Weekly report: %s best, %s win rate, $%s earned",
                            report.get("best_skill"),
                            report.get("overall_win_rate"),
                            report.get("total_earned"))
                self.db.log_event("weekly_report", report)
            self.db.log_event("check", {
                "wallet_balance": str(balance),
                "new_transactions": len(txns),
                "platform_balances": platform_balances,
            })
            logger.info("Wallet: $%s, Platform balances: %s", balance, platform_balances)

        elif action == "train":
            bounty_skill = skill
            if bounty_skill:
                report = bounty_skill.trainer.get_training_report()
                logger.info("Training report: %s", report)
                self.db.log_event("training", {"report": report})

        elif action == "research":
            prompt = (
                "Research new ways an AI agent can earn cryptocurrency in 2026. "
                "Focus on platforms that are free to join and have tasks suitable "
                "for an AI (writing, coding, data entry, translation). "
                "List 3 specific platforms or methods. "
                "Respond JSON: {\"opportunities\": [{\"name\": \"...\", "
                "\"description\": \"...\", \"effort\": \"low/medium/high\", "
                "\"setup_instructions\": \"...\"}]}"
            )
            research = self.brain.decide(prompt)
            self.db.log_event("research", research)
            logger.info("Research found: %d opportunities", len(research.get("opportunities", [])))

    async def _deliver_for_task(self, skill, task):
        try:
            draft = skill._complete_task(task)
            passed, fix, score = skill.trainer.self_review(
                task.title, task.requirements or "", draft
            )
            if not passed and fix:
                logger.info("Self-review: %s/100 — improving...", score)
                draft = skill.trainer.fix_deliverable(
                    {"title": task.title, "requirements": task.requirements},
                    draft, fix,
                )
            raw_id = task.metadata["raw"].get("id", "")
            mp = next((m for m in skill.marketplaces if m.name == task.source), None)
            if mp and hasattr(mp, "submit_deliverable"):
                ok = mp.submit_deliverable(raw_id, draft)
                if ok:
                    logger.info("Submitted deliverable for %s", task.title)
                    skill.strategy["bids_won"] += 1
                    skill.strategy["total_earned"] += task.reward
                    skill._save_strategy()
                    self.db.add_earning(task.id, task.source, task.reward, "USDC", task.title)
        except Exception as e:
            logger.error("Deliver failed for %s: %s", task.title, e)

    async def _init_agenthansa_alliance(self):
        bounty: BountyHunterSkill = self.skills.get("bounty_hunter")
        if not bounty:
            return
        for mp in bounty.marketplaces:
            if mp.name == "agenthansa" and hasattr(mp, "set_alliance"):
                try:
                    profile = mp.get_profile()
                    current = profile.get("alliance", "")
                    if not current:
                        best = self.brain.decide(
                            "Which AgentHansa alliance should AGENT007 join? "
                            "Red alliance is competitive with harder quests but higher "
                            "rewards. Royal is balanced. Blue is beginner-friendly. "
                            "Respond JSON: {\"alliance\": \"red/royal/blue\", \"reason\": \"...\"}"
                        ).get("alliance", "royal")
                        mp.set_alliance(best)
                        logger.info("Joined AgentHansa %s alliance", best)
                    else:
                        logger.info("AgentHansa alliance: %s", current)
                except Exception as e:
                    logger.warning("Alliance init failed: %s", e)

    async def run_cycle(self) -> None:
        self.cycle_count += 1
        logger.info("--- Cycle %d ---", self.cycle_count)
        if self.cycle_count == 1:
            await self._init_agenthansa_alliance()
        try:
            decision = await self.decide_next_action()
            self.last_decision = decision
            if decision:
                await self.execute_action(decision)
            if self.cycle_count % 4 == 0:
                balance = self.wallet.get_usdc_balance()
                bounty: BountyHunterSkill = self.skills.get("bounty_hunter")
                if bounty:
                    logger.info("Stats | Bids: %d placed, %d won | Win rate: %.0f%% | Aggression: %.0f%%",
                                bounty.strategy["bids_placed"],
                                bounty.strategy["bids_won"],
                                bounty.strategy["win_rate"] * 100,
                                bounty.strategy["aggression"] * 100)
            self.db.set_state("cycle_count", str(self.cycle_count))
        except Exception as e:
            logger.error("Cycle failed: %s", e)
            self.db.log_event("cycle_error", {"cycle": self.cycle_count, "error": str(e)})

    async def run_forever(self):
        self.running = True
        logger.info("%s starting...", self.name)
        logger.info("Wallet: %s on %s", self.wallet.address, self.wallet.network)
        logger.info("Connected: %s", self.wallet.is_connected())

        while self.running:
            await self.run_cycle()
            await asyncio.sleep(config.POLL_INTERVAL_MINUTES * 60)

    def stop(self):
        self.running = False
        logger.info("Agent stopping...")

    def get_status(self) -> dict:
        total_earned = self.db.get_total_earned()
        all_earnings = []
        for name, skill in self.skills.items():
            summary = skill.get_earnings_summary()
            total_earned += summary["total_earned"]
            all_earnings.append(summary)

        bounty: BountyHunterSkill = self.skills.get("bounty_hunter")
        strategy_stats = bounty.strategy if bounty else {}

        specialized = []
        if bounty:
            specialized = list(bounty.router.get_stats().keys())
        all_skill_names = list(self.skills.keys())
        if specialized:
            all_skill_names.extend("(%s)" % s for s in specialized)

        return {
            "name": self.name,
            "running": self.running,
            "cycle": self.cycle_count,
            "skills": all_skill_names,
            "earnings": all_earnings,
            "specialized_skills": specialized,
            "total_earned_usdc": total_earned,
            "wallet": self.wallet.get_status(),
            "last_decision": self.last_decision,
            "strategy": {
                "bids_placed": strategy_stats.get("bids_placed", 0),
                "bids_won": strategy_stats.get("bids_won", 0),
                "win_rate": strategy_stats.get("win_rate", 0),
                "aggression": strategy_stats.get("aggression", 0.5),
                "services_posted": strategy_stats.get("services_posted", 0),
            },
            "last_scan": self.last_scan_summary,
            "harness": self.harness.get_status() if self.harness else {},
            "providers": [p.name for p in self.brain.providers],
            "training": bounty.trainer.get_status() if bounty else {},
            "database": self.db.get_status(),
            "csuite": self.csuite.get_status() if hasattr(self, "csuite") else {"note": "not initialized"},
            "tier": self.business_model.get_status() if hasattr(self, "business_model") else {"note": "not initialized"},
        }
