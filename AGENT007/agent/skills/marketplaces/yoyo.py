from .base import MarketplaceConnector


class YoyoConnector(MarketplaceConnector):
    def __init__(self, api_key: str):
        super().__init__("yoyo", api_key, "https://api.yoyo.bot/v1")

    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"}
