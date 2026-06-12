from .base import MarketplaceConnector, _parse_reward


class OpentaskConnector(MarketplaceConnector):
    def __init__(self, api_key: str):
        super().__init__("opentask", api_key, "https://api.opentask.ai/api")

    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"}

    def list_tasks(self, **params) -> list[dict]:
        results = []
        try:
            resp = self.session.get(
                "%s/tasks" % self.base_url,
                params=params,
                timeout=30,
            )
            if resp.ok:
                data = resp.json()
                self.diagnostics["last_raw"] = str(data)[:500]
                tasks = data.get("tasks", data.get("data", data if isinstance(data, list) else []))
                if isinstance(tasks, list):
                    for t in tasks:
                        if isinstance(t, dict):
                            results.append({
                                "id": t.get("id"),
                                "title": t.get("title", "Untitled"),
                                "description": t.get("description", ""),
                                "reward": _parse_reward(t.get("budget", t.get("reward", 0))),
                                "currency": t.get("currency", "USDC"),
                                "url": t.get("url", ""),
                                "requirements": t.get("requirements", ""),
                                "source": "opentask",
                                "job_mode": t.get("job_mode", "bid"),
                                "fixed_price": t.get("fixed_price"),
                            })
            else:
                self.logger.warning("list_tasks HTTP %d: %s", resp.status_code, resp.text[:200])
        except Exception as e:
            self.logger.warning("Failed to list tasks: %s", e)
        return results
