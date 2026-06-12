from .base import MarketplaceConnector


class UgigConnector(MarketplaceConnector):
    def __init__(self, api_key: str):
        super().__init__("ugig", api_key, "https://api.ugig.net/v1")

    def _auth_headers(self) -> dict:
        return {"X-API-Key": self.api_key}
