import logging
import re
from typing import Optional

from agent.brain import LLMBrain
from agent.database import DatabaseManager
from .base import CLevelAgent, Authority
from .message_bus import MessageBus

logger = logging.getLogger("csuite.security")


SUSPICIOUS_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|above|prior)",
    r"forget\s+(all\s+)?(instructions|rules)",
    r"you\s+are\s+(not\s+)?(an?\s+)?AI",
    r"pretend\s+you\s+are",
    r"jailbreak",
    r"system\s+prompt",
    r"override\s+(instructions|protocol)",
    r"dad\s+said|mom\s+said|emergency\s+override",
    r"!important|!!urgent",
    r"bypass\s+(restrictions|safety|filter)",
    r"reveal\s+(your|the)\s+(prompt|instructions|system)",
]


class SecurityAgent(CLevelAgent):
    def __init__(self, brain: LLMBrain, bus: MessageBus, db: DatabaseManager):
        super().__init__("Security", "Security & Safety", Authority.STRATEGY, brain, bus, db)
        self.scanned_inputs = 0
        self.blocked_inputs = 0
        self.scanned_outputs = 0
        self.blocked_outputs = 0
        self.set_goal("Block 100% of prompt injection attempts", 10)
        self.set_goal("Zero security incidents", 10)

        self.bus.subscribe("security:scan_input", self._on_scan_input)
        self.bus.subscribe("security:scan_output", self._on_scan_output)

    def _on_scan_input(self, message):
        content = message.body.get("content", "")
        task_id = message.body.get("task_id", "?")
        safe, risk = self.scan_input(content)
        if not safe:
            self.logger.warning("BLOCKED input for task %s: %s", task_id, risk)
            self.bus.reply(message, {"safe": False, "risk": risk, "action": "blocked"})
        else:
            self.bus.reply(message, {"safe": True, "risk": None, "action": "allowed"})

    def _on_scan_output(self, message):
        content = message.body.get("content", "")
        task_id = message.body.get("task_id", "?")
        safe, risk = self.scan_output(content)
        if not safe:
            self.logger.warning("BLOCKED output for task %s: %s", task_id, risk)
            self.bus.reply(message, {"safe": False, "risk": risk, "action": "blocked"})
        else:
            self.bus.reply(message, {"safe": True, "risk": None, "action": "allowed"})

    def scan_input(self, content: str) -> tuple[bool, Optional[str]]:
        self.scanned_inputs += 1
        if not content:
            return True, None

        text = content.lower()
        for pattern in SUSPICIOUS_PATTERNS:
            if re.search(pattern, text):
                self.blocked_inputs += 1
                return False, "Suspicious pattern detected: %s" % pattern

        if len(content) > 10000:
            self.blocked_inputs += 1
            return False, "Content exceeds maximum length (10000 chars)"

        return True, None

    def scan_output(self, content: str) -> tuple[bool, Optional[str]]:
        self.scanned_outputs += 1
        if not content:
            return True, None

        sensitive = [
            r"sk-[a-zA-Z0-9]{20,}", r"pk-[a-zA-Z0-9]{20,}",
            r"ghp_[a-zA-Z0-9]{36}", r"AKIA[0-9A-Z]{16}",
            r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----",
        ]
        for pattern in sensitive:
            if re.search(pattern, content):
                self.blocked_outputs += 1
                return False, "Output contains sensitive credentials"

        if len(content) > 20000:
            return False, "Output exceeds maximum length"

        return True, None

    def sanitize(self, content: str) -> str:
        safe, risk = self.scan_input(content)
        if safe:
            return content
        for pattern in SUSPICIOUS_PATTERNS:
            content = re.sub(pattern, "[REDACTED]", content, flags=re.IGNORECASE)
        self.logger.info("Sanitized content: %s", risk)
        return content

    async def think(self, context: dict) -> dict:
        prompt = (
            "As Security Agent for AGENT007:\n\n"
            "Inputs scanned: %d\n"
            "Inputs blocked: %d\n"
            "Outputs scanned: %d\n"
            "Outputs blocked: %d\n\n"
            "Any new threat patterns to watch for? "
            "Should we tighten or loosen any security rules? "
            "Respond JSON with: threat_level (low/medium/high), "
            "new_patterns_to_watch (list), security_notes (str)." % (
                self.scanned_inputs, self.blocked_inputs,
                self.scanned_outputs, self.blocked_outputs,
            )
        )
        result = self._llm_decide(prompt)
        self.save_decision("security_analysis", context, result)
        return result

    def get_security_summary(self) -> dict:
        return {
            "inputs_scanned": self.scanned_inputs,
            "inputs_blocked": self.blocked_inputs,
            "outputs_scanned": self.scanned_outputs,
            "outputs_blocked": self.blocked_outputs,
            "block_rate_input": "%.1f%%" % (self.blocked_inputs / self.scanned_inputs * 100) if self.scanned_inputs > 0 else "0%",
        }
