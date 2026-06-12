import json
import logging
import os
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("agent.database")

DATA_DIR = Path(os.getenv("AGENT007_DATA_DIR", "/tmp/agent007_data"))
DB_PATH = DATA_DIR / "agent007.db"
BACKUP_DIR = DATA_DIR / "backups"


class DatabaseManager:
    def __init__(self):
        self.local = threading.local()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self.local, "conn") or self.local.conn is None:
            self.local.conn = sqlite3.connect(str(DB_PATH))
            self.local.conn.row_factory = sqlite3.Row
            self.local.conn.execute("PRAGMA journal_mode=WAL")
            self.local.conn.execute("PRAGMA busy_timeout=5000")
        return self.local.conn

    def _init_db(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        BACKUP_DIR.mkdir(exist_ok=True)
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS agent_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS tasks_seen (
                task_id TEXT PRIMARY KEY,
                title TEXT,
                source TEXT,
                reward REAL,
                seen_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS earnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT,
                source TEXT,
                amount REAL,
                currency TEXT DEFAULT 'USDC',
                description TEXT,
                tx_hash TEXT,
                timestamp TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT,
                skill TEXT,
                reason TEXT,
                cycle INTEGER,
                timestamp TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS harness_stats (
                key TEXT PRIMARY KEY,
                value INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS learning_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                data_json TEXT NOT NULL,
                timestamp TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS agent_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                data_json TEXT,
                timestamp TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS csuite_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT NOT NULL,
                decision_type TEXT NOT NULL,
                context_json TEXT,
                result_json TEXT,
                cycle INTEGER,
                timestamp TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_earnings_source ON earnings(source);
            CREATE INDEX IF NOT EXISTS idx_agent_log_type ON agent_log(type);
            CREATE INDEX IF NOT EXISTS idx_csuite_agent ON csuite_decisions(agent_name);
        """)
        conn.commit()

    def get_state(self, key: str, default=None) -> Optional[str]:
        try:
            row = self._get_conn().execute(
                "SELECT value FROM agent_state WHERE key = ?", (key,)
            ).fetchone()
            return row["value"] if row else default
        except Exception as e:
            logger.warning("get_state failed: %s", e)
            return default

    def set_state(self, key: str, value: str):
        try:
            self._get_conn().execute(
                "INSERT OR REPLACE INTO agent_state (key, value, updated_at) VALUES (?, ?, datetime('now'))",
                (key, value),
            )
            self._get_conn().commit()
        except Exception as e:
            logger.warning("set_state failed: %s", e)

    def add_earning(self, task_id: str, source: str, amount: float, currency: str, description: str, tx_hash: str = ""):
        try:
            self._get_conn().execute(
                "INSERT INTO earnings (task_id, source, amount, currency, description, tx_hash, timestamp) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
                (task_id, source, amount, currency, description, tx_hash),
            )
            self._get_conn().commit()
        except Exception as e:
            logger.warning("add_earning failed: %s", e)

    def get_earnings(self, limit: int = 100) -> list:
        try:
            rows = self._get_conn().execute(
                "SELECT * FROM earnings ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.warning("get_earnings failed: %s", e)
            return []

    def add_decision(self, action: str, skill: str, reason: str, cycle: int):
        try:
            self._get_conn().execute(
                "INSERT INTO decisions (action, skill, reason, cycle, timestamp) VALUES (?, ?, ?, ?, datetime('now'))",
                (action, skill, reason, cycle),
            )
            self._get_conn().commit()
        except Exception as e:
            logger.warning("add_decision failed: %s", e)

    def get_decisions(self, limit: int = 50) -> list:
        try:
            rows = self._get_conn().execute(
                "SELECT * FROM decisions ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
            return [{
                "type": "decision",
                "data": {"action": r["action"], "skill": r["skill"], "reason": r["reason"]},
                "timestamp": r["timestamp"],
            } for r in rows]
        except Exception as e:
            logger.warning("get_decisions failed: %s", e)
            return []

    def log_event(self, event_type: str, data: dict):
        try:
            self._get_conn().execute(
                "INSERT INTO agent_log (type, data_json, timestamp) VALUES (?, ?, datetime('now'))",
                (event_type, json.dumps(data)),
            )
            self._get_conn().commit()
        except Exception as e:
            logger.warning("log_event failed: %s", e)

    def get_logs(self, limit: int = 100) -> list:
        try:
            rows = self._get_conn().execute(
                "SELECT * FROM agent_log ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
            return [{"id": r["id"], "type": r["type"], "data": json.loads(r["data_json"] or "{}"), "timestamp": r["timestamp"]} for r in rows]
        except Exception as e:
            logger.warning("get_logs failed: %s", e)
            return []

    def increment_harness_stat(self, key: str, amount: int = 1):
        try:
            self._get_conn().execute("""
                INSERT INTO harness_stats (key, value, updated_at) VALUES (?, ?, datetime('now'))
                ON CONFLICT(key) DO UPDATE SET value = value + ?, updated_at = datetime('now')
            """, (key, amount, amount))
            self._get_conn().commit()
        except Exception as e:
            logger.warning("increment_harness_stat failed: %s", e)

    def get_harness_stats(self) -> dict:
        try:
            rows = self._get_conn().execute("SELECT key, value FROM harness_stats").fetchall()
            return {r["key"]: r["value"] for r in rows}
        except Exception as e:
            logger.warning("get_harness_stats failed: %s", e)
            return {}

    def add_task_seen(self, task_id: str, title: str, source: str, reward: float):
        try:
            self._get_conn().execute(
                "INSERT OR IGNORE INTO tasks_seen (task_id, title, source, reward) VALUES (?, ?, ?, ?)",
                (task_id, title, source, reward),
            )
            self._get_conn().commit()
        except Exception as e:
            logger.warning("add_task_seen failed: %s", e)

    def get_tasks_seen_count(self) -> int:
        try:
            row = self._get_conn().execute("SELECT COUNT(*) as cnt FROM tasks_seen").fetchone()
            return row["cnt"] if row else 0
        except Exception as e:
            logger.warning("get_tasks_seen_count failed: %s", e)
            return 0

    def save_csuite_decision(self, agent_name: str, decision_type: str, context: dict, result: dict, cycle: int):
        try:
            self._get_conn().execute(
                "INSERT INTO csuite_decisions (agent_name, decision_type, context_json, result_json, cycle, timestamp) VALUES (?, ?, ?, ?, ?, datetime('now'))",
                (agent_name, decision_type, json.dumps(context), json.dumps(result), cycle),
            )
            self._get_conn().commit()
        except Exception as e:
            logger.warning("save_csuite_decision failed: %s", e)

    def get_csuite_decisions(self, agent_name: Optional[str] = None, limit: int = 50) -> list:
        try:
            if agent_name:
                rows = self._get_conn().execute(
                    "SELECT * FROM csuite_decisions WHERE agent_name = ? ORDER BY timestamp DESC LIMIT ?",
                    (agent_name, limit),
                ).fetchall()
            else:
                rows = self._get_conn().execute(
                    "SELECT * FROM csuite_decisions ORDER BY timestamp DESC LIMIT ?", (limit,)
                ).fetchall()
            return [
                {
                    "id": r["id"],
                    "agent_name": r["agent_name"],
                    "decision_type": r["decision_type"],
                    "context": json.loads(r["context_json"] or "{}"),
                    "result": json.loads(r["result_json"] or "{}"),
                    "cycle": r["cycle"],
                    "timestamp": r["timestamp"],
                }
                for r in rows
            ]
        except Exception as e:
            logger.warning("get_csuite_decisions failed: %s", e)
            return []

    def save_learning_data(self, category: str, data: dict):
        try:
            self._get_conn().execute(
                "INSERT INTO learning_data (category, data_json) VALUES (?, ?)",
                (category, json.dumps(data)),
            )
            self._get_conn().commit()
        except Exception as e:
            logger.warning("save_learning_data failed: %s", e)

    def get_learning_data(self, category: Optional[str] = None, limit: int = 100) -> list:
        try:
            if category:
                rows = self._get_conn().execute(
                    "SELECT * FROM learning_data WHERE category = ? ORDER BY timestamp DESC LIMIT ?",
                    (category, limit),
                ).fetchall()
            else:
                rows = self._get_conn().execute(
                    "SELECT * FROM learning_data ORDER BY timestamp DESC LIMIT ?", (limit,)
                ).fetchall()
            return [{"id": r["id"], "category": r["category"], "data": json.loads(r["data_json"]), "timestamp": r["timestamp"]} for r in rows]
        except Exception as e:
            logger.warning("get_learning_data failed: %s", e)
            return []

    def backup_to_json(self) -> Path:
        try:
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup = BACKUP_DIR / f"backup_{ts}.json"
            data = {
                "state": {r["key"]: r["value"] for r in self._get_conn().execute("SELECT * FROM agent_state").fetchall()},
                "harness": self.get_harness_stats(),
                "tasks_seen_count": self.get_tasks_seen_count(),
                "earnings_count": len(self.get_earnings(10000)),
                "backup_time": datetime.utcnow().isoformat(),
            }
            backup.write_text(json.dumps(data, indent=2, default=str))
            old_backups = sorted(BACKUP_DIR.glob("backup_*.json"))
            for old in old_backups[:-10]:
                old.unlink()
            logger.info("Database backed up to %s", backup)
            return backup
        except Exception as e:
            logger.warning("Backup failed: %s", e)
            return Path("")

    def get_total_earned(self) -> float:
        try:
            row = self._get_conn().execute("SELECT COALESCE(SUM(amount), 0) as total FROM earnings").fetchone()
            return row["total"] if row else 0.0
        except Exception as e:
            logger.warning("get_total_earned failed: %s", e)
            return 0.0

    def get_status(self) -> dict:
        return {
            "db_path": str(DB_PATH),
            "earnings_count": len(self.get_earnings(10000)),
            "total_earned": self.get_total_earned(),
            "tasks_seen": self.get_tasks_seen_count(),
            "harness_stats": self.get_harness_stats(),
            "backup_dir": str(BACKUP_DIR),
        }
