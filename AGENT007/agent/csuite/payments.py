import logging
from datetime import datetime
from typing import Optional

from agent.brain import LLMBrain
from agent.database import DatabaseManager
from agent.wallet import Wallet
from .base import CLevelAgent, Authority
from .message_bus import MessageBus, Message

logger = logging.getLogger("csuite.payments")


class PaymentsAgent(CLevelAgent):
    def __init__(self, brain: LLMBrain, bus: MessageBus, db: DatabaseManager, wallet: Wallet = None):
        super().__init__("Payments", "Payments Manager", Authority.SUPPORT, brain, bus, db)
        self.wallet = wallet
        self.pending_confirmations: list[dict] = []
        self.confirmed_payments: list[dict] = []
        self.set_goal("Confirm all incoming USDC within 1 hour", 8)
        self.set_goal("Maintain accurate payment ledger", 9)

        self.bus.subscribe("payment:expected", self._on_expected_payment)
        self.bus.subscribe("request:balance_check", self._on_balance_request)

    def _on_expected_payment(self, message):
        amount = message.body.get("amount", 0)
        source = message.body.get("source", "unknown")
        self.pending_confirmations.append({
            "amount": amount,
            "source": source,
            "expected_at": datetime.utcnow().isoformat(),
            "confirmed": False,
        })
        self.logger.info("Expected payment: +$%s from %s", amount, source)

    def _on_balance_request(self, message):
        balance = self._check_balance()
        self.bus.reply(message, {"balance": balance})

    def _check_balance(self) -> float:
        if self.wallet:
            try:
                return float(self.wallet.get_usdc_balance())
            except Exception as e:
                self.logger.warning("Balance check failed: %s", e)
        return 0.0

    def check_incoming_payments(self):
        if not self.wallet:
            return []
        try:
            txns = self.wallet.get_recent_transactions()
            for txn in txns:
                self.confirmed_payments.append({
                    "tx_hash": txn.get("tx_hash", ""),
                    "from": txn.get("from", ""),
                    "amount": float(txn.get("value", 0)),
                    "confirmed_at": datetime.utcnow().isoformat(),
                })
                self.db.add_earning(
                    task_id="txn-%s" % txn.get("tx_hash", "")[:16],
                    source="blockchain",
                    amount=float(txn.get("value", 0)),
                    currency="USDC",
                    description="Incoming USDC from %s" % str(txn.get("from", ""))[:12],
                )
                self.bus.publish(Message(
                    sender=self.name,
                    recipient="CFO",
                    subject="payment:confirmed",
                    body={"amount": float(txn.get("value", 0)), "source": "blockchain", "tx": txn.get("tx_hash")},
                ))
            return txns
        except Exception as e:
            self.logger.error("Payment check failed: %s", e)
            return []

    async def think(self, context: dict) -> dict:
        prompt = (
            "As Payments Manager for AGENT007:\n\n"
            "Pending confirmations: %d\n"
            "Confirmed payments: %d\n"
            "Current balance: $%s\n\n"
            "Any issues with payment flow? Need to flag anything to CFO? "
            "Respond JSON with: payment_flow_status (normal/delayed/blocked), "
            "alerts (list), recommendations (str)." % (
                len(self.pending_confirmations),
                len(self.confirmed_payments),
                self._check_balance(),
            )
        )
        result = self._llm_decide(prompt)
        self.save_decision("payment_check", context, result)
        return result

    def get_payments_summary(self) -> dict:
        return {
            "pending": len(self.pending_confirmations),
            "confirmed": len(self.confirmed_payments),
            "pending_list": self.pending_confirmations[-5:],
            "recent_payments": self.confirmed_payments[-5:],
        }
