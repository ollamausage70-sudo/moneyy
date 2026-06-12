import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger("agent.learning")


class LearningEngine:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.file = data_dir / "learning.json"
        self.data = self._load()

    def _load(self) -> dict:
        self.data_dir.mkdir(exist_ok=True)
        if self.file.exists():
            try:
                return json.loads(self.file.read_text())
            except Exception:
                pass
        return {
            "task_type_stats": {},
            "price_optimization": {},
            "proposal_style": {
                "total": 0, "won": 0, "avg_length": 0,
                "lengths_won": [], "lengths_lost": [],
            },
            "platform_preference": {},
            "weekly_reports": [],
            "last_report_week": None,
        }

    def _save(self):
        self.file.write_text(json.dumps(self.data, indent=2))

    def record_bid_result(
        self, task_title: str, skill_name: Optional[str],
        platform: str, bid_amount: float, won: bool,
        proposal_text: str = "",
    ):
        now = datetime.utcnow()

        # Task-type stats
        skill_key = skill_name or "generic"
        if skill_key not in self.data["task_type_stats"]:
            self.data["task_type_stats"][skill_key] = {
                "attempted": 0, "won": 0, "lost": 0,
                "total_earned": 0.0, "avg_bid": 0.0,
                "recent_titles": [],
            }
        ts = self.data["task_type_stats"][skill_key]
        ts["attempted"] += 1
        ts["won" if won else "lost"] += 1
        if won:
            ts["total_earned"] += bid_amount
        ts["avg_bid"] = (
            (ts["avg_bid"] * (ts["attempted"] - 1)) + bid_amount
        ) / ts["attempted"]
        ts["recent_titles"].insert(0, task_title[:60])
        ts["recent_titles"] = ts["recent_titles"][:10]

        # Price optimization per platform
        if platform not in self.data["price_optimization"]:
            self.data["price_optimization"][platform] = {
                "bids": [], "results": [], "optimal_min": 0,
                "optimal_max": 0, "avg_win_bid": 0, "avg_lose_bid": 0,
            }
        po = self.data["price_optimization"][platform]
        po["bids"].append(bid_amount)
        po["results"].append("won" if won else "lost")
        po["bids"] = po["bids"][-50:]
        po["results"] = po["results"][-50:]

        win_bids = [b for b, r in zip(po["bids"], po["results"]) if r == "won"]
        lose_bids = [b for b, r in zip(po["bids"], po["results"]) if r == "won" and r == "lost"]
        lose_bids = [b for b, r in zip(po["bids"], po["results"]) if r == "lost"]
        if win_bids:
            po["avg_win_bid"] = sum(win_bids) / len(win_bids)
            po["optimal_min"] = max(0, min(win_bids))
            po["optimal_max"] = max(win_bids)
        if lose_bids:
            po["avg_lose_bid"] = sum(lose_bids) / len(lose_bids)

        # Platform preference scoring
        if platform not in self.data["platform_preference"]:
            self.data["platform_preference"][platform] = {
                "score": 0, "attempts": 0, "wins": 0,
            }
        pp = self.data["platform_preference"][platform]
        pp["attempts"] += 1
        if won:
            pp["wins"] += 1
            pp["score"] = min(100, pp["score"] + 10)
        else:
            pp["score"] = max(-50, pp["score"] - 5)

        # Proposal style tracking
        ps = self.data["proposal_style"]
        ps["total"] += 1
        if won:
            ps["won"] += 1
        length = len(proposal_text)
        ps["avg_length"] = (
            (ps["avg_length"] * (ps["total"] - 1)) + length
        ) / ps["total"]
        (ps["lengths_won"] if won else ps["lengths_lost"]).append(length)
        ps["lengths_won"] = ps["lengths_won"][-20:]
        ps["lengths_lost"] = ps["lengths_lost"][-20:]

        self._save()

    def get_best_skill(self) -> Optional[str]:
        stats = self.data["task_type_stats"]
        if not stats:
            return None
        best = None
        best_rate = 0
        for skill, s in stats.items():
            if s["attempted"] >= 2:
                rate = s["won"] / s["attempted"]
                if rate > best_rate:
                    best_rate = rate
                    best = skill
        return best

    def get_optimal_bid(self, platform: str, default_bid: float) -> float:
        po = self.data["price_optimization"].get(platform)
        if not po or not po["bids"]:
            return default_bid
        if po["avg_win_bid"] > 0 and po["avg_lose_bid"] > 0:
            sweet_spot = (po["avg_win_bid"] + po["avg_lose_bid"]) / 2
            return round(sweet_spot, 2)
        return default_bid

    def get_preferred_platforms(self) -> list[str]:
        prefs = self.data["platform_preference"]
        sorted_p = sorted(prefs.items(), key=lambda x: -x[1]["score"])
        return [p for p, _ in sorted_p if _["score"] > 0]

    def generate_report(self) -> dict:
        now = datetime.utcnow()
        week = now.isocalendar()[1]
        if self.data["last_report_week"] == week:
            return {}
        self.data["last_report_week"] = week

        stats = self.data["task_type_stats"]
        prefs = self.data["platform_preference"]
        best_skill = self.get_best_skill()
        preferred = self.get_preferred_platforms()

        total_bids = sum(s["attempted"] for s in stats.values())
        total_wins = sum(s["won"] for s in stats.values())
        total_earned = sum(s["total_earned"] for s in stats.values())
        overall_rate = (total_wins / total_bids * 100) if total_bids > 0 else 0

        report = {
            "week": week,
            "timestamp": now.isoformat(),
            "total_bids": total_bids,
            "total_wins": total_wins,
            "overall_win_rate": f"{overall_rate:.1f}%",
            "total_earned": round(total_earned, 2),
            "best_skill": best_skill,
            "preferred_platforms": preferred[:3],
            "recommendations": [],
        }

        if best_skill:
            best_s = stats[best_skill]
            report["recommendations"].append(
                f"Focus on {best_skill} tasks ({best_s['won']}/{best_s['attempted']} won, "
                f"${best_s['total_earned']:.2f} earned)"
            )

        for p in preferred[:2]:
            pp = prefs[p]
            report["recommendations"].append(
                f"Prioritize {p} ({pp['wins']}/{pp['attempts']} wins, "
                f"score: {pp['score']})"
            )

        self.data["weekly_reports"].insert(0, report)
        self.data["weekly_reports"] = self.data["weekly_reports"][:10]
        self._save()
        return report

    def get_summary(self) -> dict:
        skills = []
        for name, s in self.data["task_type_stats"].items():
            rate = (s["won"] / s["attempted"] * 100) if s["attempted"] > 0 else 0
            skills.append({
                "name": name,
                "attempted": s["attempted"],
                "won": s["won"],
                "win_rate": f"{rate:.0f}%",
                "earned": round(s["total_earned"], 2),
            })

        platforms = []
        for name, p in self.data["platform_preference"].items():
            platforms.append({
                "name": name,
                "score": p["score"],
                "wins": p["wins"],
                "attempts": p["attempts"],
            })

        best_skill = self.get_best_skill()
        prefs = self.get_preferred_platforms()

        return {
            "skills": sorted(skills, key=lambda x: -float(x["win_rate"].rstrip("%"))),
            "platforms": sorted(platforms, key=lambda x: -x["score"]),
            "best_skill": best_skill,
            "preferred_platforms": prefs[:3],
            "proposals_tracked": self.data["proposal_style"]["total"],
            "proposal_win_rate": (
                f"{self.data['proposal_style']['won'] / self.data['proposal_style']['total'] * 100:.0f}%"
                if self.data["proposal_style"]["total"] > 0 else "0%"
            ),
        }