import logging
from typing import Optional

from .base import MarketplaceConnector, _parse_reward


class DealworkConnector(MarketplaceConnector):
    def __init__(self, api_key: str, agent_id: str = ""):
        super().__init__("dealwork", api_key, "https://dealwork.ai/api/v1")
        self.agent_id = agent_id
        self.logger = logging.getLogger("marketplace.dealwork")

    def _auth_headers(self) -> dict:
        return {"Authorization": "Bearer %s" % self.api_key}

    def list_tasks(self, **params) -> list[dict]:
        results = []
        try:
            resp = self.session.get(
                "%s/jobs" % self.base_url,
                params={"per_page": 30, "sort": "newest", **params},
                timeout=30,
            )
            if resp.ok:
                data = resp.json()
                self.diagnostics["last_raw"] = str(data)[:500]
                jobs = data.get("data", [])
                for j in jobs:
                    mode = j.get("job_mode", j.get("jobMode", "bid"))
                    results.append({
                        "id": j.get("id"),
                        "title": j.get("title", "Untitled"),
                        "description": j.get("description", ""),
                        "reward": _parse_reward(j.get("budget_max", j.get("budgetMin", j.get("budget", 0)))),
                        "currency": "USDC",
                        "url": "https://dealwork.ai/jobs/%s" % j.get("id") if j.get("id") else "",
                        "requirements": "",
                        "source": "dealwork",
                        "job_mode": mode,
                        "fixed_price": j.get("fixed_price", j.get("fixedPrice")),
                    })
            else:
                self.logger.warning("list_tasks HTTP %d: %s", resp.status_code, resp.text[:200])
        except Exception as e:
            self.logger.warning("Failed to list tasks: %s", e)
        return results

    def claim_task(self, task_id: str) -> bool:
        try:
            resp = self.session.post(
                "%s/jobs/%s/claim" % (self.base_url, task_id),
                json={"acceptedCriteriaIds": []},
                timeout=30,
            )
            ok = resp.status_code in (200, 201)
            if ok:
                self.logger.info("Claimed task %s", task_id)
            else:
                self.logger.warning("Claim HTTP %d: %s", resp.status_code, resp.text[:200])
            return ok
        except Exception as e:
            self.logger.warning("Claim failed for %s: %s", task_id, e)
            return False

    def submit_bid(self, task_id: str, proposal: str, bid_amount: float) -> bool:
        try:
            resp = self.session.post(
                "%s/jobs/%s/bids" % (self.base_url, task_id),
                json={
                    "proposedAmount": "%.2f" % bid_amount,
                    "estimatedHours": 2.0,
                    "proposalText": proposal,
                },
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
            dl = self.session.post(
                "%s/contracts/%s/deliverables" % (self.base_url, task_id),
                json={"description": "Completed task", "outputData": {"content": content}},
                timeout=30,
            )
            if dl.ok:
                dl_id = dl.json().get("id")
                if dl_id:
                    ev = self.session.post(
                        "%s/contracts/%s/events" % (self.base_url, task_id),
                        json={"type": "SUBMIT_WORK", "deliverableId": dl_id},
                        timeout=30,
                    )
                    ok = ev.status_code in (200, 201)
                    if not ok:
                        self.logger.warning("Submit event HTTP %d: %s", ev.status_code, ev.text[:200])
                    return ok
            else:
                self.logger.warning("Deliverable HTTP %d: %s", dl.status_code, dl.text[:200])
            return False
        except Exception as e:
            self.logger.warning("Deliverable failed for %s: %s", task_id, e)
            return False

    def get_balance(self) -> float:
        try:
            resp = self.session.get("%s/wallet/balance" % self.base_url, timeout=30)
            if resp.ok:
                data = resp.json().get("data", {})
                return float(data.get("available", 0))
            else:
                self.logger.warning("Balance HTTP %d: %s", resp.status_code, resp.text[:200])
        except Exception as e:
            self.logger.warning("Balance check failed: %s", e)
        return 0.0

    def post_service(self, title: str, description: str, price: float, category: str = "") -> bool:
        try:
            resp = self.session.post(
                "%s/listings" % self.base_url,
                json={
                    "title": title, "description": description,
                    "category": category or "general",
                    "pricingMode": "fixed", "fixedPrice": "%.2f" % price,
                    "estimatedDeliveryHours": 24,
                },
                timeout=30,
            )
            if not resp.ok:
                self.logger.warning("Service post HTTP %d: %s", resp.status_code, resp.text[:200])
            return resp.ok
        except Exception as e:
            self.logger.warning("Service posting failed: %s", e)
            return False

    def heartbeat(self) -> Optional[dict]:
        if not self.agent_id:
            return None
        try:
            resp = self.session.post(
                "%s/agents/%s/heartbeat" % (self.base_url, self.agent_id),
                json={"skillVersion": "1.0.0"},
                timeout=30,
            )
            if resp.ok:
                return resp.json().get("data")
            else:
                self.logger.warning("Heartbeat HTTP %d: %s", resp.status_code, resp.text[:200])
        except Exception as e:
            self.logger.warning("Heartbeat failed: %s", e)
        return None
