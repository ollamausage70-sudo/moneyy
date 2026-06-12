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
        self._ceo_strategy = {}

        self.bus = MessageBus()
        self.csuite = CSuiteRegistry(self.bus)
        self.business_model = BusinessModelManager(db)
        self._csuite_inited = False

        if self.cycle_count > 0:
            logger.info("Resumed from cycle %d", self.cycle_count)

    # ── helpers ──────────────────────────────────────────────

    def _get(self, name: str):
        return self.csuite.get(name) if self.csuite else None

    def _build_context(self) -> dict:
        bounty: BountyHunterSkill = self.skills.get("bounty_hunter")
        return {
            "cycle": self.cycle_count,
            "strategy": self._ceo_strategy,
            "financial": self._get("CFO").get_financial_summary() if self._get("CFO") else {},
            "operations": self._get("COO").get_ops_summary() if self._get("COO") else {},
            "learning": self._get("Learning").get_learning_summary() if self._get("Learning") else {},
            "strategy_stats": bounty.strategy if bounty else {},
            "last_scan": self.last_scan_summary,
            "business_tier": self.business_model.get_status() if hasattr(self, "business_model") else {},
        }

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

    # ── C-Suite driven cycle ─────────────────────────────────

    async def run_cycle(self) -> None:
        self.cycle_count += 1
        logger.info("═══ Cycle %d ═══", self.cycle_count)
        if self.cycle_count == 1:
            await self._init_agenthansa_alliance()

        try:
            context = self._build_context()
            cycle_mod = self.cycle_count % 6

            # 1. Security — scan context for threats
            sec = self._get("Security")
            if sec:
                safe, risk = sec.scan_input(json.dumps(context))
                if not safe:
                    logger.warning("Security blocked cycle: %s", risk)
                    self.db.log_event("security_block", {"cycle": self.cycle_count, "risk": risk})
                    self.db.set_state("cycle_count", str(self.cycle_count))
                    return

            # 2. COO — report ops status
            coo = self._get("COO")
            ops_decision = None
            if coo:
                ops_decision = await coo.think(context)
                self.db.add_decision("operations", "coo", (ops_decision or {}).get("actions", "Ops analysis"), self.cycle_count)

            # 3. CEO — set strategy
            ceo = self._get("CEO")
            if ceo:
                strategy = await ceo.think(context)
                self._ceo_strategy = ceo.get_strategy()
                notes = (strategy or {}).get("strategic_notes", "Strategy updated")
                aggression = (strategy or {}).get("aggression", "moderate")
                self.db.add_decision("strategy", "ceo", "aggression=%s, notes=%s" % (aggression, notes[:120]), self.cycle_count)

            # 4. BizDev — scan marketplaces every cycle
            bizdev = self._get("BizDev")
            if bizdev:
                top = await bizdev.scan_opportunities()
                if top:
                    self.last_scan_summary = {
                        "tasks_found": len(top),
                        "timestamp": datetime.utcnow().isoformat(),
                        "top_tasks": [{"title": t["title"][:30], "reward": t["reward"], "source": t["source"]} for t in top[:3]],
                    }
                    self.db.add_decision("scan", "bizdev", "Found %d tasks, top reward=$%.2f" % (len(top), top[0]["reward"] if top else 0), self.cycle_count)
                else:
                    self.last_scan_summary = {"tasks_found": 0, "timestamp": datetime.utcnow().isoformat()}

            # 5. Execute core action based on cycle
            await self._execute_csuite_action(cycle_mod, context)

            # 6. CFO — review finances
            cfo = self._get("CFO")
            if cfo:
                fin = await cfo.think(context)
                self.db.add_decision("finance", "cfo", (fin or {}).get("recommendations", "Financial review")[:120], self.cycle_count)

            # 7. Learning — analyze trends
            learn = self._get("Learning")
            if learn:
                insight = await learn.think(context)
                self.db.add_decision("analytics", "learning", (insight or {}).get("actionable_insights", str((insight or {}).get("recommended_focus", "")))[:120], self.cycle_count)

            # 8. Marketing — optimize proposals
            mkt = self._get("Marketing")
            if mkt:
                await mkt.think(context)
            bounty = self.skills.get("bounty_hunter")
            if bounty:
                posted = bounty.post_seed_services()
                self.db.log_event("services_posted", {"count": posted, "cycle": self.cycle_count})
                self.db.add_decision("marketing", "marketing", "Posted %d service listings" % posted, self.cycle_count)

            # 9. Payments — check for incoming
            payments = self._get("Payments")
            if payments:
                txns = payments.check_incoming_payments()
                if txns:
                    self.db.add_decision("payment_check", "payments", "Found %d incoming transactions" % len(txns), self.cycle_count)

            # 10. Business model auto-upgrade
            if hasattr(self, "business_model"):
                self.business_model.check_auto_upgrade()

            # Log summary every cycle
            self.db.log_event("cycle_complete", {
                "cycle": self.cycle_count,
                "strategy_aggression": self._ceo_strategy.get("aggression_level", "moderate"),
                "tasks_found": self.last_scan_summary.get("tasks_found", 0),
            })
            self.db.set_state("cycle_count", str(self.cycle_count))
            logger.info("Cycle %d complete", self.cycle_count)

        except Exception as e:
            logger.error("Cycle %d failed: %s", self.cycle_count, e)
            self.db.log_event("cycle_error", {"cycle": self.cycle_count, "error": str(e)})
            self.db.set_state("cycle_count", str(self.cycle_count))

    async def _execute_csuite_action(self, cycle_mod: int, context: dict) -> None:
        bounty: BountyHunterSkill = self.skills.get("bounty_hunter")
        if not bounty:
            logger.warning("No bounty_hunter skill — cannot execute")
            return

        if cycle_mod == 0:
            # Scan + bid on opportunities (BizDev already scanned above)
            tasks = await bounty.find_opportunities()
            bid_count = 0
            for task in tasks[:15]:
                if task.reward <= 0 or bid_count >= 5:
                    continue
                mp = next((m for m in bounty.marketplaces if m.name == task.source), None)
                if not mp:
                    continue
                try:
                    bid = bounty._compute_bid(task)
                    proposal = bounty._generate_proposal(task)
                    bid_ok = mp.submit_bid(
                        task.metadata["raw"].get("id", ""),
                        proposal,
                        bid,
                    )
                    bounty.strategy["bids_placed"] += 1
                    bounty._save_strategy()
                    if bid_ok:
                        bid_count += 1
                        logger.info("Bid submitted on %s: $%.2f", task.id, bid)
                    else:
                        logger.info("Bid failed for %s", task.id)
                except Exception as e:
                    logger.error("Bid error %s: %s", task.id, e)
            self.db.add_decision("bid", "bounty_hunter", "Submitted %d bids on %d tasks" % (bid_count, len(tasks)), self.cycle_count)
            self.db.log_event("evaluation", {"cycle": self.cycle_count, "bids_placed": bid_count, "tasks_scanned": len(tasks)})

        elif cycle_mod == 1:
            # Harness — passive earning
            if self.harness:
                results = self.harness.run_all()
                est = results.get("estimated_earnings", 0)
                self.db.log_event("harness", {**results, "cycle": self.cycle_count})
                self.db.add_decision("earn", "harness", "Passive earning: ~$%.2f estimated" % est, self.cycle_count)
                logger.info("Harness: ~$%s estimated earnings", est)

        elif cycle_mod == 2:
            # Check — balances + report
            balance = self.wallet.get_usdc_balance()
            platform_balances = bounty.check_platform_balances()
            report = bounty.generate_weekly_report()
            if report:
                self.db.log_event("weekly_report", {**report, "cycle": self.cycle_count})
            self.db.log_event("check", {
                "wallet_balance": str(balance),
                "platform_balances": platform_balances,
                "cycle": self.cycle_count,
            })
            self.db.add_decision("check", "bounty_hunter", "Wallet: $%s, platforms: %s" % (balance, platform_balances), self.cycle_count)

        elif cycle_mod == 3:
            # Research — find new opportunities
            research = self.brain.decide(
                "Research new ways an AI agent can earn cryptocurrency in 2026. "
                "Focus on platforms that are free to join with AI-suitable tasks "
                "(writing, coding, data entry, translation). "
                "List 3 specific platforms or methods. "
                "Respond JSON: {\"opportunities\": [{\"name\": \"...\", "
                "\"description\": \"...\", \"effort\": \"low/medium/high\", "
                "\"setup_instructions\": \"...\"}]}"
            )
            self.db.log_event("research", {**research, "cycle": self.cycle_count})
            count = len(research.get("opportunities", []))
            self.db.add_decision("research", "bounty_hunter", "Found %d new earning opportunities" % count, self.cycle_count)

        elif cycle_mod == 4:
            # Training — analyze + optimize
            if bounty.trainer:
                report = bounty.trainer.get_training_report()
                self.db.log_event("training", {"report": report, "cycle": self.cycle_count})
                self.db.add_decision("train", "bounty_hunter", "Quality score: %s" % (report.get("avg_quality_score", "N/A")), self.cycle_count)

        else:
            # Post services (cycle_mod == 5)
            posted = bounty.post_seed_services()
            self.db.log_event("services_posted", {"count": posted, "cycle": self.cycle_count})
            self.db.add_decision("services", "bounty_hunter", "Posted %d service listings" % posted, self.cycle_count)

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
