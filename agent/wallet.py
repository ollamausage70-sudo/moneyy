import logging
import time
from typing import Optional
from decimal import Decimal

from web3 import Web3
from web3.exceptions import ContractLogicError

import config

logger = logging.getLogger("agent.wallet")

USDC_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [
            {"name": "_owner", "type": "address"},
            {"name": "_spender", "type": "address"},
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "from", "type": "address"},
            {"indexed": True, "name": "to", "type": "address"},
            {"indexed": False, "name": "value", "type": "uint256"},
        ],
        "name": "Transfer",
        "type": "event",
    },
]


class Wallet:
    def __init__(self):
        self.address = Web3.to_checksum_address(config.WALLET_ADDRESS)
        self.network = config.WALLET_NETWORK
        self.rpc_url = config.RPC_URL
        self.usdc_address = Web3.to_checksum_address(config.USDC_CONTRACT_ADDRESS)
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        self.usdc_contract = self.w3.eth.contract(
            address=self.usdc_address, abi=USDC_ABI
        )
        self.known_balance = Decimal("0")
        self.transactions = []

    def is_connected(self) -> bool:
        return self.w3.is_connected()

    def get_usdc_balance(self) -> Decimal:
        try:
            raw = self.usdc_contract.functions.balanceOf(self.address).call()
            decimals = self.usdc_contract.functions.decimals().call()
            balance = Decimal(raw) / Decimal(10 ** decimals)
            self.known_balance = balance
            return balance
        except Exception as e:
            logger.error(f"Balance check failed: {e}")
            return self.known_balance

    def get_recent_transactions(self, from_block: Optional[int] = None) -> list:
        try:
            latest = self.w3.eth.block_number
            start = from_block or (latest - 10000)
            transfer_filter = self.usdc_contract.events.Transfer.create_filter(
                from_block=start,
                to_block=latest,
                argument_filters={"to": self.address},
            )
            events = transfer_filter.get_all_entries()
            txns = []
            for ev in events:
                args = ev["args"]
                txns.append({
                    "tx_hash": ev["transactionHash"].hex(),
                    "from": args["from"],
                    "value": Decimal(args["value"]) / Decimal(10 ** 6),
                    "block": ev["blockNumber"],
                    "timestamp": time.time(),
                })
            self.transactions = txns
            return txns
        except Exception as e:
            logger.error(f"Transaction fetch failed: {e}")
            return self.transactions

    def generate_payment_address(self, platform: str) -> str:
        return self.address

    def get_network_explorer(self) -> str:
        explorers = {
            "base": "https://basescan.org",
            "ethereum": "https://etherscan.io",
            "polygon": "https://polygonscan.com",
        }
        return explorers.get(self.network, explorers["base"])

    def get_status(self) -> dict:
        return {
            "address": self.address,
            "network": self.network,
            "connected": self.is_connected(),
            "usdc_balance": str(self.get_usdc_balance()),
            "recent_transactions": len(self.transactions),
            "explorer": self.get_network_explorer(),
        }
