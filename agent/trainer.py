import json
import logging
from pathlib import Path
from typing import Optional

from agent.brain import LLMBrain

logger = logging.getLogger("agent.trainer")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PROFILE_FILE = DATA_DIR / "professional_profile.json"

PROFESSIONAL_SYSTEM_PROMPT = (
    "You are AGENT007, a top-tier professional AI freelancer. You deliver "
    "exceptional quality work that exceeds client expectations. You are: "
    "Precise — you read requirements carefully and follow them exactly. "
    "Thorough — you deliver complete, polished work. "
    "Professional — your communication is clear, confident, and courteous. "
    "Reliable — you deliver on time, every time. "
    "Your goal is to earn maximum USDC by delivering outstanding work "
    "that gets 5-star reviews and repeat clients."
)

EVALUATION_SYSTEM_PROMPT = (
    "You are AGENT007's strategic advisor. Analyze tasks and opportunities "
    "objectively. Only recommend pursuing tasks where the AI can deliver "
    "independently with high quality. Be honest about limitations. "
    "Respond ONLY in the requested JSON format. No extra text."
)


class ProfessionalTrainer:
    def __init__(self, brain: LLMBrain):
        self.brain = brain
        self.profile = self._load_profile()

    def _load_profile(self) -> dict:
        DATA_DIR.mkdir(exist_ok=True)
        if PROFILE_FILE.exists():
            try:
                return json.loads(PROFILE_FILE.read_text())
            except Exception:
                pass
        return {
            "total_deliverables": 0,
            "self_review_score_avg": 0.0,
            "quality_standards": [
                "all requirements met",
                "no errors or typos",
                "well-formatted and organized",
                "professional language",
                "complete solution, no placeholders",
            ],
            "winning_patterns": [],
            "improvement_areas": [],
            "bid_strategy": {
                "min_acceptable": 5.0,
                "quality_premium": 1.0,
                "competitive_edge": 0.0,
            },
        }

    def _save_profile(self):
        DATA_DIR.mkdir(exist_ok=True)
        PROFILE_FILE.write_text(json.dumps(self.profile, indent=2))

    def get_system_prompt(self, context: str = "think") -> str:
        if context == "evaluate":
            return EVALUATION_SYSTEM_PROMPT
        return PROFESSIONAL_SYSTEM_PROMPT

    def self_review(self, task_title: str, task_requirements: str, draft: str) -> tuple[bool, str, float]:
        prompt = (
            f"Review this deliverable before submission.\n\n"
            f"Task: {task_title}\n"
            f"Requirements: {task_requirements or 'None'}\n\n"
            f"Deliverable:\n{draft[:2000]}\n\n"
            f"Check against these quality standards:\n"
            + "\n".join(f"- {s}" for s in self.profile["quality_standards"])
            + "\n\nScore 0-100. If below 70, explain what to fix. "
            f"Respond JSON: {{\"score\": int, \"pass\": bool, "
            f"\"issues\": [\"...\"], \"fix_instructions\": \"...\"}}"
        )
        decision = self.brain.decide(prompt)
        score = decision.get("score", 50)
        passed = decision.get("pass", False)
        issues = decision.get("issues", [])
        fix = decision.get("fix_instructions", "")

        self.profile["total_deliverables"] += 1
        old_avg = self.profile["self_review_score_avg"]
        n = self.profile["total_deliverables"]
        self.profile["self_review_score_avg"] = ((old_avg * (n - 1)) + score) / n

        if not passed and issues:
            self.profile["improvement_areas"] = list(set(
                self.profile["improvement_areas"] + issues
            ))[:10]
            self._save_profile()
            return False, fix, score

        return True, "", score

    def fix_deliverable(self, task: dict, draft: str, fix_instructions: str) -> str:
        prompt = (
            f"Fix this deliverable based on quality review.\n\n"
            f"Task: {task.get('title', '')}\n"
            f"Requirements: {task.get('requirements', '')}\n\n"
            f"Issues to fix:\n{fix_instructions}\n\n"
            f"Original draft:\n{draft}\n\n"
            f"Rewrite the deliverable fixing all issues. "
            f"Maintain or improve the quality."
        )
        return self.brain.think(prompt, self.get_system_prompt())

    def analyze_competition(self, task_title: str, task_reward: float, bid_count_estimate: int = 5) -> dict:
        prompt = (
            f"Analyze this task's competitive landscape:\n\n"
            f"Title: {task_title}\n"
            f"Reward: ${task_reward}\n"
            f"Estimated competitors: ~{bid_count_estimate}\n\n"
            f"Recommend a winning strategy. Consider:\n"
            f"- What bid price wins vs loses\n"
            f"- What proposal angle stands out\n"
            f"- Whether this task is worth competing for\n\n"
            f"Respond JSON: {{\"recommended_bid\": float, "
            f"\"angle\": \"...\", \"worth_it\": bool, "
            f"\"risk\": \"low/medium/high\"}}"
        )
        result = self.brain.decide(prompt)
        return result

    def train_from_outcome(self, task_title: str, won: bool, bid_amount: float, proposal_style: str = ""):
        if won:
            self.profile["winning_patterns"].insert(0, {
                "title": task_title[:50],
                "bid": bid_amount,
                "style": proposal_style[:50],
            })
            self.profile["winning_patterns"] = self.profile["winning_patterns"][:20]
        self._save_profile()

    def get_training_report(self) -> str:
        prompt = (
            f"Generate a professional development report for AGENT007.\n\n"
            f"Current stats:\n"
            f"Deliverables reviewed: {self.profile['total_deliverables']}\n"
            f"Average quality score: {self.profile['self_review_score_avg']:.1f}/100\n"
            f"Recent wins: {len(self.profile['winning_patterns'])}\n"
            f"Improvement areas: {self.profile['improvement_areas'][:3]}\n\n"
            f"Write 3 specific, actionable recommendations to improve "
            f"professional quality and win rate. Be concise."
        )
        return self.brain.think(prompt, self.get_system_prompt("think"))

    def get_status(self) -> dict:
        return {
            "deliverables_reviewed": self.profile["total_deliverables"],
            "avg_quality_score": round(self.profile["self_review_score_avg"], 1),
            "winning_patterns": len(self.profile["winning_patterns"]),
            "improvement_areas": self.profile["improvement_areas"][:3],
            "quality_standards": self.profile["quality_standards"],
        }