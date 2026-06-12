import json
import logging
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional

import config
from agent.brain import LLMBrain
from agent.skills.base import BaseSkill, Task, EarningRecord
from agent.skills.marketplaces import (
    YoyoConnector, DealworkConnector, OpentaskConnector, UgigConnector,
    AgentHansaConnector, AnyTasksConnector,
)
from agent.skills.specialized import (
    SkillRouter, ContentCreatorSkill, CodeWorkerSkill, ResearchAnalystSkill,
    DataEntrySkill, TranslationSkill, MarketingSkill,
)
from agent.skills.learning_engine import LearningEngine
from agent.trainer import ProfessionalTrainer

logger = logging.getLogger("agent.skills.bounty_hunter")

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
STRATEGY_FILE = DATA_DIR / "strategy.json"


class BountyHunterSkill(BaseSkill):
    def __init__(self, brain: LLMBrain):
        super().__init__("bounty_hunter")
        self.brain = brain
        self.learner = LearningEngine(DATA_DIR)
        self.trainer = ProfessionalTrainer(brain)
        self.marketplaces = self._init_marketplaces()
        self.router = SkillRouter(brain)
        self._register_specialized_skills()
        self.strategy = self._load_strategy()
        self.services_posted = set()

    def _register_specialized_skills(self):
        self.router.register(ContentCreatorSkill(self.brain))
        self.router.register(CodeWorkerSkill(self.brain))
        self.router.register(ResearchAnalystSkill(self.brain))
        self.router.register(DataEntrySkill(self.brain))
        self.router.register(TranslationSkill(self.brain))
        self.router.register(MarketingSkill(self.brain))

    def _init_marketplaces(self) -> list:
        mps = []
        cfg = config.MARKETPLACE_CONFIG
        registry = {
            "yoyo": (YoyoConnector, {}),
            "dealwork": (DealworkConnector, {"agent_id": cfg.get("dealwork", {}).get("extra", {}).get("agent_id", "")}),
            "opentask": (OpentaskConnector, {}),
            "ugig": (UgigConnector, {}),
            "agenthansa": (AgentHansaConnector, {}),
            "anytasks": (AnyTasksConnector, {}),
        }
        for name, (mp_cls, kwargs) in registry.items():
            mp_cfg = cfg.get(name, {})
            if mp_cfg.get("api_key"):
                try:
                    mps.append(mp_cls(mp_cfg["api_key"], **kwargs))
                    logger.info("Connected to %s", name)
                except Exception as e:
                    logger.warning("Failed to init %s: %s", name, e)
            else:
                logger.info("Skipping %s — no API key", name)
        return mps

    def _load_strategy(self) -> dict:
        DATA_DIR.mkdir(exist_ok=True)
        if STRATEGY_FILE.exists():
            try:
                return json.loads(STRATEGY_FILE.read_text())
            except Exception:
                pass
        return {
            "bids_placed": 0, "bids_won": 0, "bids_lost": 0,
            "total_earned": 0.0, "history": [], "platform_stats": {},
            "bidding_multiplier": 0.9, "win_rate": 0.0, "aggression": 0.5,
            "services_posted": 0,
        }

    def _save_strategy(self):
        DATA_DIR.mkdir(exist_ok=True)
        STRATEGY_FILE.write_text(json.dumps(self.strategy, indent=2))

    async def find_opportunities(self) -> list[Task]:
        tasks = []
        for mp in self.marketplaces:
            try:
                if mp.name == "dealwork" and hasattr(mp, "heartbeat"):
                    mp.heartbeat()
            except Exception:
                pass
            try:
                raw = mp.list_tasks()
                logger.info("%s: found %d raw tasks", mp.name, len(raw))
                for t in raw:
                    task_id = "%s-%s" % (mp.name, t.get("id", len(self.tasks_seen)))
                    if task_id in self.tasks_seen:
                        continue
                    reward = float(t.get("reward", 0))
                    if reward <= 0:
                        logger.debug("Skipping %s: reward=0", task_id)
                        continue
                    mode = t.get("job_mode", "bid")
                    task = Task(
                        id=task_id,
                        title=t.get("title", "Untitled"),
                        description=t.get("description", ""),
                        reward=reward,
                        reward_currency=t.get("currency", "USDC"),
                        source=mp.name,
                        url=t.get("url", ""),
                        requirements=t.get("requirements"),
                        metadata={
                            "raw": t,
                            "marketplace": mp.name,
                            "job_mode": mode,
                            "fixed_price": t.get("fixed_price"),
                        },
                    )
                    self.tasks_seen.add(task_id)
                    tasks.append(task)
            except Exception as e:
                logger.warning("Error polling %s: %s", mp.name, e)
        logger.info("find_opportunities: returning %d tasks with reward > 0", len(tasks))
        return tasks

    async def try_claim_open_tasks(self, tasks: list[Task]) -> list[Task]:
        claimed = []
        for task in tasks:
            if task.metadata.get("job_mode") != "open":
                continue
            if task.source != "dealwork":
                continue
            mp = next((m for m in self.marketplaces if m.name == task.source), None)
            if mp and hasattr(mp, "claim_task"):
                success = mp.claim_task(task.metadata["raw"].get("id", ""))
                if success:
                    self.logger.info("Claimed open task: %s", task.title)
                    claimed.append(task)
        return claimed

    def _compute_bid(self, task: Task) -> float:
        base_bid = task.reward * self.strategy["bidding_multiplier"]
        adjustment = 1.0
        ps = self.strategy["platform_stats"].get(task.source, {})
        win_rate = ps.get("win_rate", 0.5)
        if win_rate > 0.3:
            adjustment += 0.05
        if win_rate < 0.2:
            adjustment -= 0.1
        if len(task.description) > 200:
            adjustment += 0.05
        if task.reward < 10:
            adjustment += 0.1
        if task.reward > 50:
            adjustment -= 0.05
        base = round(base_bid * min(max(adjustment, 0.5), 1.0), 2)
        learned = self.learner.get_optimal_bid(task.source, base)
        return learned

    def _evaluate_task(self, task: Task) -> tuple[bool, str, float, Optional[str]]:
        if task.reward <= 0:
            return False, "No reward", 0, None
        bid = self._compute_bid(task)
        try:
            can_do, reason, final_bid, skill_name = self.router.evaluate(task, bid)
        except Exception as e:
            logger.warning("Evaluation error for %s: %s", task.title, e)
            return True, "Auto-accept (eval fallback)", bid, None
        if can_do and task.reward > 20 and self.strategy["bids_won"] == 0:
            pass
        return can_do, reason or "Auto-qualified", final_bid, skill_name

    def _generate_proposal(self, task: Task, use_llm: bool = False) -> str:
        """Generate proposal. Uses template by default (fast), optional LLM for better quality."""
        if use_llm:
            return self.router.generate_proposal(task)
        t = task.title[:60] if task.title else "this task"
        r = task.reward
        return (
            "I understand your need for %s. "
            "I will deliver accurate, high-quality work within 24 hours "
            "using my specialized AI capabilities. "
            "My rate is $%.2f — I'm ready to start immediately. "
            "Let me earn this opportunity for you." % (t, r)
        )

    def _complete_task(self, task: Task) -> str:
        content, skill_name = self.router.complete(task)
        return content

    async def execute(self, task: Task, skill_name: Optional[str] = None) -> Optional[str]:
        self.logger.info("Executing task: %s - %s", task.id, task.title)
        try:
            draft = self._complete_task(task)
            passed, fix, score = self.trainer.self_review(
                task.title, task.requirements or "", draft
            )
            if not passed and fix:
                self.logger.info("Self-review: %s/100 — improving...", score)
                draft = self.trainer.fix_deliverable(
                    {"title": task.title, "requirements": task.requirements},
                    draft, fix,
                )
                self.logger.info("Deliverable improved after self-review")
            else:
                self.logger.info("Self-review: %s/100 — passed", score)
            deliverables = draft
            raw_id = task.metadata["raw"].get("id", task.id.split("-", 1)[-1] if "-" in task.id else "")
            mp = next((m for m in self.marketplaces if m.name == task.source), None)
            if mp:
                success = mp.submit_deliverable(raw_id, deliverables)
                if success:
                    record = EarningRecord(
                        task_id=task.id, source=task.source,
                        amount=task.reward, currency=task.reward_currency,
                        timestamp=datetime.utcnow(),
                        description="Completed: %s" % task.title,
                    )
                    self.earnings.append(record)
                    self.strategy["bids_won"] += 1
                    self.strategy["total_earned"] += task.reward
                    self.strategy["history"].append({
                        "task_id": task.id, "title": task.title,
                        "reward": task.reward, "source": task.source,
                        "result": "won", "timestamp": datetime.utcnow().isoformat(),
                    })
                    self._update_platform_stats(task.source, "won")
                    self.learner.record_bid_result(
                        task.title, skill_name, task.source, task.reward, True, ""
                    )
                    self.trainer.train_from_outcome(task.title, True, task.reward)
                    self._save_strategy()
                    logger.info("Delivered +$%s from %s", task.reward, task.source)
                    return record
                else:
                    self.strategy["bids_lost"] += 1
                    self._update_platform_stats(task.source, "lost")
                    self.learner.record_bid_result(
                        task.title, skill_name, task.source, task.reward, False, ""
                    )
                    self.trainer.train_from_outcome(task.title, False, task.reward)
            return None
        except Exception as e:
            logger.error("Failed to execute %s: %s", task.id, e)
            return None

    def _update_platform_stats(self, platform: str, result: str):
        if platform not in self.strategy["platform_stats"]:
            self.strategy["platform_stats"][platform] = {"won": 0, "lost": 0, "total_bid": 0.0, "win_rate": 0.0}
        ps = self.strategy["platform_stats"][platform]
        ps["won" if result == "won" else "lost"] += 1
        total = ps["won"] + ps["lost"]
        ps["win_rate"] = ps["won"] / total if total > 0 else 0.0
        overall_total = self.strategy["bids_won"] + self.strategy["bids_lost"]
        if overall_total > 0:
            self.strategy["win_rate"] = self.strategy["bids_won"] / overall_total
            if self.strategy["win_rate"] > 0.4:
                self.strategy["aggression"] = min(1.0, self.strategy["aggression"] + 0.02)
            else:
                self.strategy["aggression"] = max(0.3, self.strategy["aggression"] - 0.05)
            self.strategy["bidding_multiplier"] = 0.7 + self.strategy["aggression"] * 0.3
        self._save_strategy()

    def post_seed_services(self):
        posted = 0
        services = [
            {"title": "AI Writing & Content Creation",
             "description": "Professional AI-powered writing: articles, blog posts, marketing copy, social media content, translations, and editing. Fast turnaround, any language.",
             "price": 15.0, "category": "writing"},
            {"title": "Data Analysis & Research",
             "description": "Deep research and data analysis: market research, competitor analysis, data cleaning, spreadsheet creation, report writing.",
             "price": 25.0, "category": "data"},
            {"title": "Code & Technical Writing",
             "description": "Clean code, documentation, API guides, README files, technical tutorials, code review, and debugging. Python, JavaScript, TypeScript.",
             "price": 30.0, "category": "development"},
            {"title": "Translation & Localization",
             "description": "Professional translation between any languages. Native-level quality for documents, websites, apps, and marketing materials.",
             "price": 20.0, "category": "translation"},
        ]
        for mp in self.marketplaces:
            if mp.name not in ("dealwork", "anytasks"):
                continue
            for svc in services:
                key = "%s-%s" % (mp.name, svc["title"])
                if key in self.services_posted:
                    continue
                try:
                    ok = False
                    if hasattr(mp, "post_service"):
                        ok = mp.post_service(**svc)
                    elif hasattr(mp, "place_service"):
                        ok = mp.place_service(**svc)
                    if ok:
                        self.services_posted.add(key)
                        posted += 1
                        self.strategy["services_posted"] = len(self.services_posted)
                        self._save_strategy()
                        logger.info("Posted service on %s: %s @ $%s", mp.name, svc["title"], svc["price"])
                except Exception as e:
                    logger.warning("Service post failed on %s: %s", mp.name, e)
        return posted

    def agenthansa_checkin(self) -> bool:
        for mp in self.marketplaces:
            if mp.name == "agenthansa" and hasattr(mp, "checkin"):
                return mp.checkin()
        return False

    def check_platform_balances(self) -> list:
        results = []
        for mp in self.marketplaces:
            try:
                bal = mp.get_balance()
                results.append({"platform": mp.name, "balance": bal})
            except Exception as e:
                logger.warning("Balance check failed for %s: %s", mp.name, e)
        return results

    def get_learning_summary(self) -> dict:
        return self.learner.get_summary()

    def generate_weekly_report(self) -> dict:
        return self.learner.generate_report()

    def get_available_platforms(self) -> list[str]:
        return [mp.name for mp in self.marketplaces if mp.is_enabled()]

    def get_status(self) -> dict:
        learning = self.get_learning_summary()
        return {
            "connected_marketplaces": self.get_available_platforms(),
            "tasks_scanned": len(self.tasks_seen),
            "bids_placed": self.strategy["bids_placed"],
            "bids_won": self.strategy["bids_won"],
            "win_rate": "%.0f%%" % (self.strategy["win_rate"] * 100),
            "aggression": "%.0f%%" % (self.strategy["aggression"] * 100),
            "services_posted": self.strategy.get("services_posted", 0),
            "specialized_skills": list(self.router.get_stats().keys()),
            "learning": {
                "best_skill": learning.get("best_skill"),
                "preferred_platforms": learning.get("preferred_platforms"),
                "skills": learning.get("skills", []),
                "platforms": learning.get("platforms", []),
            },
            **self.get_earnings_summary(),
        }
