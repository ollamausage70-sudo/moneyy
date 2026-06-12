import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

WALLET_ADDRESS = os.getenv("WALLET_ADDRESS", "0x1f966CAAAF378E0d9caE669bD37431c00Ad9c15D")
WALLET_NETWORK = os.getenv("WALLET_NETWORK", "base")

RPC_URLS = {
    "base": "https://mainnet.base.org",
    "ethereum": "https://cloudflare-eth.com",
    "polygon": "https://polygon-rpc.com",
}

USDC_CONTRACTS = {
    "base": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    "ethereum": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    "polygon": "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359",
}

USDC_CONTRACT_ADDRESS = os.getenv("USDC_CONTRACT_ADDRESS", USDC_CONTRACTS.get(WALLET_NETWORK, ""))
RPC_URL = os.getenv("RPC_URL", RPC_URLS.get(WALLET_NETWORK, RPC_URLS["base"]))

AGENT_NAME = os.getenv("AGENT_NAME", "AGENT007")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
POLL_INTERVAL_MINUTES = int(os.getenv("POLL_INTERVAL_MINUTES", "15"))
CYCLE_INTERVAL_SECONDS = int(os.getenv("CYCLE_INTERVAL_SECONDS", "300"))

MARKETPLACE_CONFIG = {
    "yoyo": {
        "api_key": os.getenv("YOYO_API_KEY", ""),
        "base_url": "https://api.yoyo.bot/v1",
        "enabled": bool(os.getenv("YOYO_API_KEY")),
    },
    "dealwork": {
        "api_key": os.getenv("DEALWORK_API_KEY", ""),
        "base_url": "https://dealwork.ai/api/v1",
        "enabled": bool(os.getenv("DEALWORK_API_KEY")),
        "extra": {"agent_id": os.getenv("DEALWORK_AGENT_ID", "")},
    },
    "opentask": {
        "api_key": os.getenv("OPENTASK_API_KEY", ""),
        "base_url": "https://api.opentask.ai/api",
        "enabled": bool(os.getenv("OPENTASK_API_KEY")),
    },
    "ugig": {
        "api_key": os.getenv("UGIG_API_KEY", ""),
        "base_url": "https://api.ugig.net/v1",
        "enabled": bool(os.getenv("UGIG_API_KEY")),
    },
    "agenthansa": {
        "api_key": os.getenv("AGENTHANSA_API_KEY", ""),
        "base_url": "https://www.agenthansa.com/api",
        "enabled": bool(os.getenv("AGENTHANSA_API_KEY")),
    },
    "anytasks": {
        "api_key": os.getenv("ANYTASKS_API_KEY", ""),
        "base_url": "https://anytasks.io/api/v1",
        "enabled": bool(os.getenv("ANYTASKS_API_KEY")),
    },
}
