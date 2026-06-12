from .base import MarketplaceConnector


class OpentaskConnector(MarketplaceConnector):
    def __init__(self, api_key: str):
        super().__init__("opentask", api_key, "https://api.opentask.ai/api")

    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"}
