from typing import Optional

from .base import MarketplaceConnector, _parse_reward


class AgentHansaConnector(MarketplaceConnector):
    def __init__(self, api_key: str):
        super().__init__("agenthansa", api_key, "https://www.agenthansa.com/api")

    def _auth_headers(self) -> dict:
        return {"Authorization": "Bearer %s" % self.api_key}

    def list_tasks(self, **params) -> list[dict]:
        tasks = []
        try:
            quests = self.session.get(
                "%s/alliance-war/quests" % self.base_url,
                params=params,
                timeout=30,
            )
            if quests.ok:
                data = quests.json()
                self.diagnostics["last_raw"] = str(data)[:500]
                quest_list = data.get("quests", data)
                if isinstance(quest_list, list):
                    for q in quest_list:
                        tasks.append({
                            "id": q.get("id"),
                            "title": q.get("title", "Untitled Quest"),
                            "description": q.get("description", ""),
                            "reward": _parse_reward(q.get("reward_amount")),
                            "currency": "USDC",
                            "url": "https://agenthansa.com/alliance-war/quests/%s" % q.get("id") if q.get("id") else "",
                            "requirements": q.get("goal", ""),
                            "source": "agenthansa",
                        })
            else:
                self.logger.warning("Quests HTTP %d: %s", quests.status_code, quests.text[:200])
        except Exception as e:
            self.logger.warning("Failed to list quests: %s", e)

        try:
            community = self.session.get(
                "%s/community/tasks" % self.base_url,
                timeout=30,
            )
            if community.ok:
                data = community.json()
                task_list = data.get("tasks", data)
                if isinstance(task_list, list):
                    for t in task_list:
                        tasks.append({
                            "id": "ct-%s" % t.get("id"),
                            "title": t.get("title", "Untitled Community Task"),
                            "description": t.get("description", ""),
                            "reward": _parse_reward(t.get("reward_amount")),
                            "currency": "USDC",
                            "url": "",
                            "requirements": t.get("goal", ""),
                            "source": "agenthansa",
                        })
        except Exception as e:
            self.logger.warning("Failed to list community tasks: %s", e)

        try:
            bounties = self.session.get(
                "%s/collective/bounties/public" % self.base_url,
                timeout=30,
            )
            if bounties.ok:
                data = bounties.json()
                bounty_list = data.get("bounties", data)
                if isinstance(bounty_list, list):
                    for b in bounty_list:
                        tasks.append({
                            "id": "cb-%s" % b.get("id"),
                            "title": b.get("title", "Untitled Bounty"),
                            "description": b.get("description", ""),
                            "reward": _parse_reward(b.get("reward_amount")),
                            "currency": "USDC",
                            "url": "",
                            "requirements": "",
                            "source": "agenthansa",
                        })
        except Exception as e:
            self.logger.warning("Failed to list bounties: %s", e)

        return tasks

    def submit_deliverable(self, task_id: str, content: str) -> bool:
        try:
            if task_id.startswith("ct-"):
                real_id = task_id[3:]
                resp = self.session.post(
                    "%s/community/tasks/%s/join" % (self.base_url, real_id),
                    json={"content": content},
                    timeout=30,
                )
            elif task_id.startswith("cb-"):
                real_id = task_id[3:]
                resp = self.session.post(
                    "%s/collective/bounties/%s/submit" % (self.base_url, real_id),
                    json={"description": content},
                    timeout=30,
                )
            else:
                resp = self.session.post(
                    "%s/alliance-war/quests/%s/submit" % (self.base_url, task_id),
                    json={"content": content},
                    timeout=30,
                )
            ok = resp.status_code in (200, 201)
            if not ok:
                self.logger.warning("Deliverable HTTP %d for %s: %s", resp.status_code, task_id, resp.text[:200])
            return ok
        except Exception as e:
            self.logger.warning("Deliverable failed for %s: %s", task_id, e)
            return False

    def checkin(self) -> bool:
        try:
            resp = self.session.post("%s/agents/checkin" % self.base_url, timeout=30)
            if not resp.ok:
                self.logger.warning("Checkin HTTP %d: %s", resp.status_code, resp.text[:200])
            return resp.ok
        except Exception as e:
            self.logger.warning("Checkin failed: %s", e)
            return False

    def get_balance(self) -> float:
        try:
            resp = self.session.get("%s/agents/earnings" % self.base_url, timeout=30)
            if resp.ok:
                data = resp.json()
                return float(data.get("total_earned", 0))
            else:
                self.logger.warning("Balance HTTP %d: %s", resp.status_code, resp.text[:200])
        except Exception as e:
            self.logger.warning("Balance check failed: %s", e)
        return 0.0

    def get_offers(self) -> list:
        try:
            resp = self.session.get("%s/offers" % self.base_url, timeout=30)
            if resp.ok:
                return resp.json().get("offers", resp.json())
            else:
                self.logger.warning("Offers HTTP %d: %s", resp.status_code, resp.text[:200])
        except Exception as e:
            self.logger.warning("Offers fetch failed: %s", e)
        return []

    def generate_referral(self, offer_id: str) -> Optional[str]:
        try:
            resp = self.session.post("%s/offers/%s/ref" % (self.base_url, offer_id), timeout=30)
            if resp.ok:
                data = resp.json()
                return data.get("ref_url") or data.get("url")
            else:
                self.logger.warning("Referral HTTP %d: %s", resp.status_code, resp.text[:200])
        except Exception as e:
            self.logger.warning("Referral gen failed: %s", e)
        return None

    def get_forum_posts(self) -> list:
        try:
            resp = self.session.get("%s/forum" % self.base_url, timeout=30)
            if resp.ok:
                return resp.json().get("posts", resp.json())
            else:
                self.logger.warning("Forum HTTP %d: %s", resp.status_code, resp.text[:200])
        except Exception as e:
            self.logger.warning("Forum fetch failed: %s", e)
        return []

    def post_forum(self, title: str, body: str, category: str = "review") -> bool:
        try:
            resp = self.session.post(
                "%s/forum" % self.base_url,
                json={"title": title, "body": body, "category": category},
                timeout=30,
            )
            if not resp.ok:
                self.logger.warning("Forum post HTTP %d: %s", resp.status_code, resp.text[:200])
            return resp.ok
        except Exception as e:
            self.logger.warning("Forum post failed: %s", e)
            return False

    def vote_forum(self, post_id: str, direction: str = "up") -> bool:
        try:
            resp = self.session.post(
                "%s/forum/%s/vote" % (self.base_url, post_id),
                json={"direction": direction},
                timeout=30,
            )
            return resp.ok
        except Exception as e:
            self.logger.warning("Forum vote failed: %s", e)
            return False

    def get_red_packets(self) -> list:
        try:
            resp = self.session.get("%s/red-packets" % self.base_url, timeout=30)
            if resp.ok:
                return resp.json().get("packets", resp.json())
        except Exception as e:
            self.logger.warning("Red packets fetch failed: %s", e)
        return []

    def get_red_packet_challenge(self, packet_id: str) -> Optional[dict]:
        try:
            resp = self.session.get(
                "%s/red-packets/%s/challenge" % (self.base_url, packet_id),
                timeout=30,
            )
            if resp.ok:
                return resp.json()
        except Exception as e:
            self.logger.warning("Challenge fetch failed: %s", e)
        return None

    def join_red_packet(self, packet_id: str, answer: str) -> bool:
        try:
            resp = self.session.post(
                "%s/red-packets/%s/join" % (self.base_url, packet_id),
                json={"answer": answer},
                timeout=30,
            )
            return resp.ok
        except Exception as e:
            self.logger.warning("Red packet join failed: %s", e)
            return False

    def get_daily_quests(self) -> dict:
        try:
            resp = self.session.get("%s/agents/daily-quests" % self.base_url, timeout=30)
            if resp.ok:
                return resp.json()
        except Exception as e:
            self.logger.warning("Daily quests fetch failed: %s", e)
        return {}

    def get_profile(self) -> dict:
        try:
            resp = self.session.get("%s/agents/me" % self.base_url, timeout=30)
            if resp.ok:
                return resp.json()
            else:
                self.logger.warning("Profile HTTP %d: %s", resp.status_code, resp.text[:200])
        except Exception as e:
            self.logger.warning("Profile fetch failed: %s", e)
        return {}

    def set_alliance(self, alliance: str) -> bool:
        try:
            resp = self.session.patch(
                "%s/agents/alliance" % self.base_url,
                json={"alliance": alliance},
                timeout=30,
            )
            return resp.ok
        except Exception as e:
            self.logger.warning("Alliance set failed: %s", e)
            return False

    def register_agent(self, name: str, description: str = "") -> Optional[str]:
        try:
            resp = self.session.post(
                "%s/agents/register" % self.base_url,
                json={"name": name, "description": description},
                timeout=30,
            )
            if resp.ok:
                return resp.json().get("api_key")
        except Exception as e:
            self.logger.warning("Registration failed: %s", e)
        return None

    def get_feed(self) -> list:
        try:
            resp = self.session.get("%s/agents/feed" % self.base_url, timeout=30)
            if resp.ok:
                return resp.json().get("items", [])
        except Exception as e:
            self.logger.warning("Feed fetch failed: %s", e)
        return []
