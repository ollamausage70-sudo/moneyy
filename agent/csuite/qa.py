import logging
from typing import Optional

from agent.brain import LLMBrain
from agent.database import DatabaseManager
from .base import CLevelAgent, Authority
from .message_bus import MessageBus, Message

logger = logging.getLogger("csuite.qa")


class QAAgent(CLevelAgent):
    def __init__(self, brain: LLMBrain, bus: MessageBus, db: DatabaseManager):
        super().__init__("QA", "Quality Assurance", Authority.OPERATIONS, brain, bus, db)
        self.reviews: list[dict] = []
        self.quality_scores: list[float] = []
        self.set_goal("Maintain average quality score >85/100", 9)
        self.set_goal("Zero defects in submitted deliverables", 10)

        self.bus.subscribe("task:for_review", self._on_review_request)

    def _on_review_request(self, message):
        body = message.body
        task_id = body.get("task_id")
        title = body.get("title", "?")
        deliverable = body.get("deliverable", "")

        score, passed, issues = self._review_deliverable(title, deliverable)
        self.reviews.append({
            "task_id": task_id,
            "title": title,
            "score": score,
            "passed": passed,
            "issues": issues,
        })
        self.quality_scores.append(score)

        if passed:
            self.logger.info("APPROVED %s (score: %d/100)", title, score)
            self.bus.reply(message, {
                "approved": True,
                "score": score,
                "task_id": task_id,
            })
            self.bus.publish(Message(
                sender=self.name, recipient="Delivery",
                subject="qa:approved",
                body={"task_id": task_id, "title": title, "score": score},
            ))
        else:
            self.logger.warning("REJECTED %s (score: %d/100) — %s", title, score, issues[:2])
            self.bus.reply(message, {
                "approved": False,
                "score": score,
                "issues": issues,
                "feedback": "Issues: %s. Please fix and resubmit." % "; ".join(issues[:3]),
                "task_id": task_id,
            })
            self.bus.publish(Message(
                sender=self.name, recipient="Delivery",
                subject="qa:rejected",
                body={"task_id": task_id, "title": title, "score": score, "feedback": issues},
            ))

    def _review_deliverable(self, title: str, content: str) -> tuple[float, bool, list]:
        prompt = (
            "Review this deliverable on a scale of 0-100:\n\n"
            "Task: %s\n"
            "Content: %s\n\n"
            "Check: completeness, correctness, formatting, professionalism, "
            "no placeholders, meets requirements.\n\n"
            "Respond JSON: {\"score\": int, \"pass\": bool (pass if >=70), "
            "\"issues\": [\"...\"]}" % (title, content[:2000])
        )
        decision = self._llm_decide(prompt)
        score = decision.get("score", 50)
        passed = decision.get("pass", False)
        issues = decision.get("issues", ["No specific issues found"])
        return score, passed, issues

    async def think(self, context: dict) -> dict:
        avg_score = sum(self.quality_scores) / len(self.quality_scores) if self.quality_scores else 0
        prompt = (
            "As QA for AGENT007, analyze quality metrics:\n\n"
            "Total reviews: %d\n"
            "Average quality score: %.1f/100\n"
            "Recent issues: %s\n\n"
            "What quality trends do you see? Any systemic issues to address? "
            "Respond JSON with: quality_trend (improving/stable/declining), "
            "systemic_issues (list), recommendations (str)." % (
                len(self.reviews),
                avg_score,
                [i["issues"][:2] for i in self.reviews[-3:] if i.get("issues")],
            )
        )
        result = self._llm_decide(prompt)
        self.save_decision("quality_analysis", context, result)
        return result

    def get_qa_summary(self) -> dict:
        avg = sum(self.quality_scores) / len(self.quality_scores) if self.quality_scores else 0
        return {
            "total_reviews": len(self.reviews),
            "avg_score": round(avg, 1),
            "recent_reviews": self.reviews[-5:],
        }
