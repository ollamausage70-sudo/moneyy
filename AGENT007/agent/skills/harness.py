import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from agent.brain import LLMBrain
from agent.skills.base import Task
from agent.skills.specialized import (
    SkillRouter, ContentCreatorSkill, CodeWorkerSkill, ResearchAnalystSkill,
    DataEntrySkill, TranslationSkill, MarketingSkill,
)
from agent.skills.learning_engine import LearningEngine

logger = logging.getLogger("agent.skills.harness")

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


class HarnessEngine:
    def __init__(self, brain: LLMBrain, marketplaces: list):
        self.brain = brain
        self.marketplaces = {mp.name: mp for mp in marketplaces}
        self.router = SkillRouter(brain)
        self.router.register(ContentCreatorSkill(brain))
        self.router.register(CodeWorkerSkill(brain))
        self.router.register(ResearchAnalystSkill(brain))
        self.router.register(DataEntrySkill(brain))
        self.router.register(TranslationSkill(brain))
        self.router.register(MarketingSkill(brain))
        self.learner = LearningEngine(DATA_DIR)
        self.stats = {
            "checkins": 0, "forum_posts": 0, "votes": 0,
            "red_packets_claimed": 0, "referrals_generated": 0,
            "quests_completed": 0, "content_published": 0,
        }

    def get_mp(self, name: str):
        return self.marketplaces.get(name)

    def run_agenthansa_daily(self) -> dict:
        result = {"checkin": False, "forum_post": False, "votes": 0,
                  "referral": False, "daily_quests": {}, "xp_earned": 0}
        mp = self.get_mp("agenthansa")
        if not mp:
            logger.info("AgentHansa not connected — skipping daily routine")
            return result

        try:
            ok = mp.checkin()
            if ok:
                self.stats["checkins"] += 1
                result["checkin"] = True
                logger.info("AgentHansa daily check-in done")
            else:
                logger.warning("AgentHansa check-in returned False")
        except Exception as e:
            logger.warning("Check-in failed: %s", e)
            result["checkin_error"] = str(e)[:100]

        try:
            profile = mp.get_profile()
            if profile.get("alliance") in (None, ""):
                mp.set_alliance("blue")
                logger.info("Joined Heavenly (blue) alliance")
        except Exception as e:
            logger.warning("Alliance check failed: %s", e)

        forum_posts = []
        try:
            forum_posts = mp.get_forum_posts()
            logger.info("Read %d forum posts", len(forum_posts))
        except Exception as e:
            logger.warning("Forum read failed: %s", e)

        votes_cast = 0
        for post in forum_posts[:10]:
            try:
                mp.vote_forum(post.get("id"), "up")
                votes_cast += 1
                self.stats["votes"] += 1
            except Exception as e:
                logger.warning("Vote failed for post %s: %s", post.get("id"), e)
        result["votes"] = votes_cast
        if votes_cast > 0:
            logger.info("Voted on %d forum posts", votes_cast)

        try:
            offers = mp.get_offers()
            ref_link = None
            if offers:
                offer = offers[0]
                ref_link = mp.generate_referral(offer.get("id"))
            category = "review"
            task = Task(
                id="harness-forum",
                title="AI Agent Marketplace Review — %s" % datetime.utcnow().strftime("%B %Y"),
                description="Write a review of AI agent marketplaces with referral link",
                reward=0, reward_currency="USDC",
                source="agenthansa", requirements="",
            )
            proposal = self.router.generate_proposal(task)
            ref_suffix = "\n\nSponsored disclosure: I may earn a commission if you purchase through my links.\nTry it yourself: %s" % ref_link if ref_link else ""
            body = proposal + ref_suffix
            ok = mp.post_forum(task.title, body, category)
            if ok:
                self.stats["forum_posts"] += 1
                result["forum_post"] = True
                logger.info("Forum post published: %s", task.title)
            else:
                logger.warning("Forum post returned False")
        except Exception as e:
            logger.warning("Forum post failed: %s", e)
            result["forum_post_error"] = str(e)[:100]

        try:
            if offers and not ref_link:
                ref_link = mp.generate_referral(offers[0].get("id"))
            if ref_link:
                self.stats["referrals_generated"] += 1
                result["referral"] = True
                logger.info("Referral link generated")
        except Exception as e:
            logger.warning("Referral gen failed: %s", e)

        try:
            dq = mp.get_daily_quests()
            result["daily_quests"] = dq
            if dq.get("bonus_claimed"):
                self.stats["quests_completed"] += 1
                logger.info("Daily quest bonus claimed!")
        except Exception as e:
            logger.warning("Daily quests check failed: %s", e)

        return result

    def claim_red_packets(self) -> list:
        result = []
        mp = self.get_mp("agenthansa")
        if not mp:
            return result

        try:
            packets = mp.get_red_packets()
            logger.info("Found %d red packets", len(packets))
            for packet in packets:
                pid = packet.get("id")
                challenge = mp.get_red_packet_challenge(pid)
                if challenge and challenge.get("question"):
                    prompt = (
                        "Answer this question correctly:\n\n"
                        "%s\n\n"
                        "Respond with just the answer, nothing else." % challenge["question"]
                    )
                    answer = self.brain.think(prompt).strip()
                    ok = mp.join_red_packet(pid, answer)
                    if ok:
                        self.stats["red_packets_claimed"] += 1
                        result.append({"packet_id": pid, "claimed": True})
                        logger.info("Red packet claimed: %s", pid)
                    else:
                        result.append({"packet_id": pid, "claimed": False})
                        logger.warning("Red packet claim failed for %s", pid)
                else:
                    logger.info("No challenge for red packet %s", pid)
        except Exception as e:
            logger.warning("Red packet routine failed: %s", e)
        return result

    def publish_content(self) -> dict:
        result = {"published": 0, "items": []}
        mp = self.get_mp("agenthansa")
        if not mp:
            return result

        topics = [
            "How AI Agents Are Changing the Gig Economy in 2026",
            "Top 5 Ways to Earn Crypto as an AI Agent",
            "A Complete Guide to AI Agent Marketplaces",
            "Why Every Business Needs an AI Agent in 2026",
            "The Rise of Autonomous Earning Agents",
        ]

        for topic in topics:
            try:
                check_task = Task(
                    id="pub-%d" % (hash(topic) % 10000),
                    title=topic, description=topic,
                    reward=0, reward_currency="USDC",
                    source="agenthansa", requirements="",
                )
                content, skill_name = self.router.complete(check_task)
                ref_link = None
                try:
                    offers = mp.get_offers()
                    if offers:
                        ref_link = mp.generate_referral(offers[0].get("id"))
                except Exception as e:
                    logger.warning("Ref link gen failed for content: %s", e)
                disclosure = (
                    "\n\n---\n*Sponsored: I may earn a commission if you "
                    "purchase through links on this page.*"
                )
                ref_suffix = "\n%s" % ref_link if ref_link else ""
                body = content[:1500] + disclosure + ref_suffix
                ok = mp.post_forum(topic[:80], body, "review")
                if ok:
                    self.stats["content_published"] += 1
                    result["published"] += 1
                    result["items"].append(topic[:40])
                    logger.info("Content published: %s", topic[:40])
                else:
                    logger.warning("Content publish returned False for: %s", topic[:30])
            except Exception as e:
                logger.warning("Content publish failed for '%s': %s", topic[:30], e)

        return result

    def run_competitive_quests(self) -> list:
        results = []
        mp = self.get_mp("agenthansa")
        if not mp:
            return results

        try:
            quests_raw = mp.list_tasks()
            quests = [q for q in quests_raw if "cb-" not in str(q.get("id")) and "ct-" not in str(q.get("id"))]
            logger.info("Found %d competitive quests", len(quests))
            for q in quests[:3]:
                qid = q.get("id")
                title = q.get("title", "Quest")
                task = Task(
                    id="ah-quest-%s" % qid,
                    title=title,
                    description=q.get("description", ""),
                    reward=float(q.get("reward_amount", 0)),
                    reward_currency="USDC",
                    source="agenthansa",
                    requirements=q.get("goal", ""),
                )
                content, skill_name = self.router.complete(task)
                ok = mp.submit_deliverable(str(qid), content[:2000])
                results.append({"quest_id": qid, "title": str(title)[:30], "submitted": ok})
                if ok:
                    self.stats["quests_completed"] += 1
                    logger.info("Quest submitted: %s", str(title)[:30])
                else:
                    logger.warning("Quest submission failed: %s", str(title)[:30])
        except Exception as e:
            logger.warning("Quest routine failed: %s", e)

        return results

    def run_all(self) -> dict:
        logger.info("=== Harness: proactive earning cycle ===")
        results = {
            "daily": self.run_agenthansa_daily(),
            "red_packets": self.claim_red_packets(),
            "quests": self.run_competitive_quests(),
            "content": self.publish_content(),
        }
        total_earned = self.stats["content_published"] * 0.05
        results["estimated_earnings"] = round(total_earned, 2)
        results["stats"] = dict(self.stats)
        logger.info("Harness done — %d pieces published, %d red packets, %d forum posts, %d quests",
                     self.stats["content_published"],
                     self.stats["red_packets_claimed"],
                     self.stats["forum_posts"],
                     self.stats["quests_completed"])
        return results

    def get_status(self) -> dict:
        return dict(self.stats)
