import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import config
from agent.database import DatabaseManager

logger = logging.getLogger("agent.business_model")


class BusinessModelManager:
    """Manages AGENT007's business model tiers."""

    def __init__(self, db: DatabaseManager):
        self.db = db
        self.current_tier = 1
        self.tier_config = self._load_tier_config()

    def _load_tier_config(self) -> dict:
        raw = self.db.get_state("tier_config")
        if raw:
            try:
                return json.loads(raw)
            except Exception:
                pass
        return {
            "tier": 1,
            "max_agents": 1,
            "max_concurrent_tasks": 3,
            "external_clients": [],
            "white_label": None,
        }

    def _save_tier_config(self):
        self.db.set_state("tier_config", json.dumps(self.tier_config))

    def get_current_tier(self) -> int:
        return self.tier_config.get("tier", 1)

    def get_tier_info(self) -> dict:
        return {
            1: {
                "name": "Automated Freelancer",
                "description": "Single agent earning USDC from marketplaces autonomously",
                "max_agents": 1,
                "max_concurrent_tasks": 3,
                "features": ["marketplace_scanner", "bidding", "auto_delivery", "harness_earning"],
                "status": "active" if self.current_tier >= 1 else "locked",
            },
            2: {
                "name": "Agent Fleet",
                "description": "Multiple agents operating in parallel, scaled by CFO profitability reports",
                "max_agents": 5,
                "max_concurrent_tasks": 15,
                "features": ["parallel_execution", "load_balancing", "auto_scaling", "cost_optimization"],
                "status": "active" if self.current_tier >= 2 else "locked",
            },
            3: {
                "name": "Agent-as-a-Service",
                "description": "External clients can hire the agent fleet via API",
                "max_agents": 20,
                "max_concurrent_tasks": 50,
                "features": ["client_api", "multi_tenant", "usage_tracking", "client_dashboard"],
                "status": "active" if self.current_tier >= 3 else "locked",
            },
            4: {
                "name": "White-Label Platform",
                "description": "Self-hosted branded platform for clients",
                "max_agents": 100,
                "max_concurrent_tasks": 200,
                "features": ["custom_branding", "client_portal", "revenue_sharing", "marketplace"],
                "status": "active" if self.current_tier >= 4 else "locked",
            },
        }

    def upgrade_tier(self, target_tier: int) -> bool:
        if target_tier < 1 or target_tier > 4:
            logger.warning("Invalid tier: %d", target_tier)
            return False
        if target_tier <= self.current_tier:
            logger.info("Already at or above tier %d", target_tier)
            return True

        self.current_tier = target_tier
        self.tier_config["tier"] = target_tier
        info = self.get_tier_info().get(target_tier, {})
        self.tier_config["max_agents"] = info.get("max_agents", 1)
        self.tier_config["max_concurrent_tasks"] = info.get("max_concurrent_tasks", 3)
        self._save_tier_config()
        self.db.log_event("tier_upgrade", {"from": target_tier - 1, "to": target_tier})
        logger.info("Upgraded to Tier %d: %s", target_tier, info.get("name"))
        return True

    def should_scale(self, cfo_report: dict) -> Optional[int]:
        if self.current_tier < 2:
            return None

        total_earned = cfo_report.get("total_earned", 0)
        total_costs = cfo_report.get("total_costs", 0)
        profit = total_earned - total_costs

        if profit > 50 and self.current_tier < 2:
            return 2
        if profit > 200 and self.current_tier < 3:
            return 3
        if profit > 1000 and self.current_tier < 4:
            return 4

        if profit < -10 and self.current_tier > 1:
            return self.current_tier - 1

        return None

    def register_external_client(self, client_name: str, api_key: str) -> dict:
        if self.current_tier < 3:
            return {"error": "Tier 3 required for external clients"}
        client = {
            "name": client_name,
            "api_key": api_key,
            "registered_at": datetime.utcnow().isoformat(),
            "tasks_completed": 0,
            "total_spent": 0.0,
        }
        self.tier_config["external_clients"].append(client)
        self._save_tier_config()
        self.db.log_event("client_registered", client)
        return client

    def set_white_label(self, brand_name: str, domain: str) -> bool:
        if self.current_tier < 4:
            logger.warning("Tier 4 required for white-label")
            return False
        self.tier_config["white_label"] = {
            "brand": brand_name,
            "domain": domain,
            "created_at": datetime.utcnow().isoformat(),
        }
        self._save_tier_config()
        return True

    def get_status(self) -> dict:
        tiers = self.get_tier_info()
        return {
            "current_tier": self.current_tier,
            "current_tier_name": tiers.get(self.current_tier, {}).get("name", "Unknown"),
            "max_agents": self.tier_config.get("max_agents", 1),
            "max_concurrent_tasks": self.tier_config.get("max_concurrent_tasks", 3),
            "external_clients": len(self.tier_config.get("external_clients", [])),
            "white_label": self.tier_config.get("white_label"),
            "all_tiers": tiers,
        }
