from typing import Optional

from .base import MarketplaceConnector, _parse_reward


class AnyTasksConnector(MarketplaceConnector):
    def __init__(self, api_key: str):
        super().__init__("anytasks", api_key, "https://anytasks.io/api/v1")

    def _auth_headers(self) -> dict:
        return {"X-API-Key": self.api_key}

    def list_tasks(self, **params) -> list[dict]:
        try:
            resp = self.session.get(
                "%s/tasks" % self.base_url,
                params={"limit": 20, **params},
                timeout=30,
            )
            if resp.ok:
                data = resp.json()
                tasks = data if isinstance(data, list) else data.get("tasks", [])
                self.diagnostics["last_raw"] = str(tasks[:2])[:500]
                return [
                    {
                        "id": t.get("id"),
                        "title": t.get("title", "Untitled"),
                        "description": t.get("description", ""),
                        "reward": _parse_reward(t.get("budget", t.get("max_budget", t.get("reward", 0)))),
                        "currency": "USDC",
                        "url": "https://anytasks.io/task/%s" % t.get("id") if t.get("id") else "",
                        "requirements": t.get("requirements", ""),
                        "source": "anytasks",
                    }
                    for t in tasks
                ]
            else:
                self.logger.warning("list_tasks HTTP %d: %s", resp.status_code, resp.text[:200])
        except Exception as e:
            self.logger.warning("Failed to list tasks: %s", e)
        return []

    def submit_bid(self, task_id: str, proposal: str, bid_amount: float) -> bool:
        try:
            resp = self.session.post(
                "%s/tasks/%s/bid" % (self.base_url, task_id),
                json={"proposal": proposal, "amount": bid_amount},
                timeout=30,
            )
            ok = resp.status_code in (200, 201)
            if not ok:
                self.logger.warning("Bid HTTP %d: %s", resp.status_code, resp.text[:200])
            return ok
        except Exception as e:
            self.logger.warning("Bid failed for %s: %s", task_id, e)
            return False

    def submit_deliverable(self, task_id: str, content: str) -> bool:
        try:
            resp = self.session.post(
                "%s/tasks/%s/deliver" % (self.base_url, task_id),
                json={"content": content},
                timeout=30,
            )
            return resp.status_code in (200, 201)
        except Exception as e:
            self.logger.warning("Deliverable failed for %s: %s", task_id, e)
            return False

    def get_balance(self) -> float:
        try:
            resp = self.session.get("%s/me" % self.base_url, timeout=30)
            if resp.ok:
                data = resp.json()
                return float(data.get("balance", 0))
        except Exception as e:
            self.logger.warning("Balance check failed: %s", e)
        return 0.0

    def register_agent(self, name: str = "") -> Optional[str]:
        try:
            resp = self.session.post(
                "%s/agent/register" % self.base_url,
                json={"name": name or "AGENT007"},
                timeout=30,
            )
            if resp.ok:
                return resp.json().get("api_key")
        except Exception as e:
            self.logger.warning("Registration failed: %s", e)
        return None

    def place_service(self, title: str, description: str, price: float) -> bool:
        try:
            resp = self.session.post(
                "%s/services" % self.base_url,
                json={"title": title, "description": description, "price": price},
                timeout=30,
            )
            return resp.ok
        except Exception as e:
            self.logger.warning("Service placement failed: %s", e)
            return False
