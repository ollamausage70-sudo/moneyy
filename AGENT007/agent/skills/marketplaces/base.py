import logging
import re
from abc import ABC, abstractmethod
from typing import Optional

import requests


def _parse_reward(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = re.sub(r"[^0-9.]", "", value.replace(",", ""))
        try:
            return float(cleaned) if cleaned else 0.0
        except ValueError:
            return 0.0
    return 0.0


class MarketplaceConnector(ABC):
    def __init__(self, name: str, api_key: str, base_url: str):
        self.name = name
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.logger = logging.getLogger("marketplace.%s" % name)
        self.session = requests.Session()
        if api_key:
            self.session.headers.update(self._auth_headers())
        self.diagnostics = {"errors": [], "last_raw": None}

    @abstractmethod
    def _auth_headers(self) -> dict:
        return {}

    def list_tasks(self, **params) -> list[dict]:
        try:
            resp = self.session.get(
                "%s/tasks" % self.base_url,
                params=params,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            self.diagnostics["last_raw"] = str(data)[:500]
            tasks = data.get("tasks", data)
            if isinstance(tasks, dict):
                tasks = [tasks]
            return tasks if isinstance(tasks, list) else []
        except Exception as e:
            self.logger.warning("Failed to list tasks: %s", e)
            self.diagnostics["errors"].append(str(e)[:200])
            return []

    def submit_bid(self, task_id: str, proposal: str, bid_amount: float) -> bool:
        try:
            resp = self.session.post(
                "%s/tasks/%s/bids" % (self.base_url, task_id),
                json={"proposal": proposal, "amount": bid_amount},
                timeout=30,
            )
            ok = resp.status_code in (200, 201)
            if not ok:
                self.logger.warning("Bid failed HTTP %d for %s: %s", resp.status_code, task_id, resp.text[:200])
            return ok
        except Exception as e:
            self.logger.warning("Bid failed for %s: %s", task_id, e)
            return False

    def submit_deliverable(self, task_id: str, content: str) -> bool:
        try:
            resp = self.session.post(
                "%s/tasks/%s/deliverables" % (self.base_url, task_id),
                json={"content": content},
                timeout=30,
            )
            return resp.status_code in (200, 201)
        except Exception as e:
            self.logger.warning("Deliverable submission failed for %s: %s", task_id, e)
            return False

    def post_service(self, title: str, description: str, price: float, category: str = "") -> bool:
        try:
            resp = self.session.post(
                "%s/services" % self.base_url,
                json={"title": title, "description": description, "price": price, "category": category},
                timeout=30,
            )
            ok = resp.status_code in (200, 201)
            if not ok:
                self.logger.warning("Service post HTTP %d: %s", resp.status_code, resp.text[:200])
            return ok
        except Exception as e:
            self.logger.warning("Service posting failed: %s", e)
            return False

    def get_balance(self, currency: str = "USDC") -> float:
        try:
            resp = self.session.get("%s/wallet/balance" % self.base_url, timeout=30)
            data = resp.json()
            bal = data.get("balance", data.get("available", 0))
            return float(bal) if bal else 0.0
        except Exception as e:
            self.logger.warning("Balance check failed: %s", e)
            return 0.0

    def withdraw(self, amount: float, address: str) -> bool:
        try:
            resp = self.session.post(
                "%s/wallet/withdraw" % self.base_url,
                json={"amount": amount, "address": address, "currency": "USDC"},
                timeout=30,
            )
            return resp.status_code in (200, 201)
        except Exception as e:
            self.logger.warning("Withdraw failed: %s", e)
            return False

    def is_enabled(self) -> bool:
        return bool(self.api_key)

    def get_diagnostics(self) -> dict:
        return {
            "name": self.name,
            "enabled": self.is_enabled(),
            "base_url": self.base_url,
            "errors": self.diagnostics["errors"][-5:],
            "last_raw": self.diagnostics["last_raw"][:300] if self.diagnostics["last_raw"] else None,
        }
