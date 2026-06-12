import json
import logging
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("ruflo.bridge")


class RufloMCPBridge:
    """Bridges AGENT007's C-Suite agents to Ruflo MCP server."""

    def __init__(self, swarm_config_path: Optional[str] = None):
        self.swarm_config_path = swarm_config_path or str(Path(__file__).resolve().parent / "swarm.yaml")
        self.process: Optional[subprocess.Popen] = None
        self.connected = False
        self.agent_status: dict[str, dict] = {}

    def start(self) -> bool:
        """Start the Ruflo MCP server as a subprocess."""
        try:
            self.process = subprocess.Popen(
                ["npx", "@ruvnet/ruflo", "server", "--config", self.swarm_config_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.connected = True
            logger.info("Ruflo MCP server started (PID: %d)", self.process.pid)

            threading.Thread(target=self._read_output, daemon=True).start()
            return True
        except FileNotFoundError:
            logger.error("Ruflo not found. Install with: npm install -g @ruvnet/ruflo")
            return False
        except Exception as e:
            logger.error("Failed to start Ruflo: %s", e)
            return False

    def _read_output(self):
        while self.process and self.process.poll() is None:
            try:
                line = self.process.stdout.readline()
                if line:
                    logger.info("[Ruflo] %s", line.strip())
            except Exception:
                break

    def stop(self):
        if self.process:
            self.process.terminate()
            self.process.wait(timeout=5)
            self.connected = False
            logger.info("Ruflo MCP server stopped")

    def send_command(self, agent_name: str, command: str, params: dict = None) -> dict:
        """Send a command to a specific agent via Ruflo."""
        if not self.connected:
            return {"error": "Ruflo not connected", "status": "error"}

        payload = {
            "jsonrpc": "2.0",
            "method": "agent.execute",
            "params": {
                "agent": agent_name,
                "command": command,
                "params": params or {},
            },
            "id": int(time.time() * 1000),
        }

        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect("/tmp/ruflo.sock")
            sock.sendall(json.dumps(payload).encode())
            response = sock.recv(65536).decode()
            sock.close()
            return json.loads(response)
        except Exception as e:
            logger.warning("Ruflo command failed: %s", e)
            return {"error": str(e), "status": "error"}

    def get_swarm_status(self) -> dict:
        return self.send_command("swarm", "status")

    def health_check(self) -> bool:
        try:
            result = self.send_command("swarm", "ping")
            return result.get("status") == "ok"
        except Exception:
            return False

    def get_status(self) -> dict:
        return {
            "connected": self.connected,
            "swarm_config": self.swarm_config_path,
            "agent_status": self.agent_status,
            "ruflo_pid": self.process.pid if self.process else None,
        }
