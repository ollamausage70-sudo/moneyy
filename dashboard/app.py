import json
import logging
from pathlib import Path

from flask import Flask, jsonify, render_template

from agent.core import AgentCore

logger = logging.getLogger("dashboard")
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LOG_FILE = DATA_DIR / "agent_log.jsonl"


def create_app(agent: AgentCore = None):
    app = Flask(__name__)
    app.agent = agent

    @app.route("/")
    def index():
        return render_template("dashboard.html", agent_name="AGENT007")

    @app.route("/api/status")
    def api_status():
        if app.agent:
            return jsonify(app.agent.get_status())
        return jsonify({"error": "Agent not initialized"}), 503

    @app.route("/api/wallet")
    def api_wallet():
        if app.agent:
            return jsonify(app.agent.wallet.get_status())
        return jsonify({"error": "Agent not initialized"}), 503

    @app.route("/api/earnings")
    def api_earnings():
        if app.agent and app.agent.db:
            return jsonify(app.agent.db.get_earnings(100))
        records = []
        if app.agent:
            for skill in app.agent.skills.values():
                for rec in skill.earnings:
                    records.append({
                        "task_id": rec.task_id,
                        "source": rec.source,
                        "amount": rec.amount,
                        "currency": rec.currency,
                        "timestamp": rec.timestamp.isoformat(),
                        "description": rec.description,
                    })
        return jsonify(records)

    @app.route("/api/logs")
    def api_logs():
        if app.agent and app.agent.db:
            return jsonify(app.agent.db.get_logs(100))
        entries = []
        if LOG_FILE.exists():
            with open(LOG_FILE) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
        return jsonify(entries[-100:])

    @app.route("/api/training")
    def api_training():
        if app.agent:
            bounty = app.agent.skills.get("bounty_hunter")
            if bounty:
                return jsonify(bounty.trainer.get_status())
        return jsonify({})

    @app.route("/api/decisions")
    def api_decisions():
        if app.agent and app.agent.db:
            decisions = app.agent.db.get_decisions(50)
            logs = app.agent.db.get_logs(100)
            displayable = [l for l in logs if l.get("type") in (
                "decision", "evaluation", "check", "services_posted",
                "harness", "research", "training", "tier_upgrade",
                "weekly_report", "cycle_error", "client_registered",
            )]
            merged = sorted(decisions + displayable, key=lambda x: x.get("timestamp", ""), reverse=True)
            return jsonify(merged[:50])
        entries = []
        if LOG_FILE.exists():
            with open(LOG_FILE) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            obj = json.loads(line)
                            t = obj.get("type", "")
                            if t in ("decision", "cycle_decision", "evaluation", "check", "services_posted"):
                                entries.append(obj)
                        except json.JSONDecodeError:
                            pass
        return jsonify(entries[-50:])

    @app.route("/api/logs")
    def api_logs():
        if app.agent and app.agent.db:
            return jsonify(app.agent.db.get_logs(100))
        return jsonify([])

    @app.route("/api/database")
    def api_database():
        if app.agent and app.agent.db:
            return jsonify(app.agent.db.get_status())
        return jsonify({"error": "Database not available"}), 503

    @app.route("/api/diagnostics")
    def api_diagnostics():
        if not app.agent:
            return jsonify({"error": "No agent"}), 500
        results = {}
        bounty = app.agent.skills.get("bounty_hunter")
        if bounty:
            for mp in bounty.marketplaces:
                results[mp.name] = mp.get_diagnostics()
        return jsonify({"marketplaces": results})

    # C-Suite routes (stubs — populated in Phase 2)
    @app.route("/api/csuite/status")
    def api_csuite_status():
        if app.agent and hasattr(app.agent, "csuite"):
            return jsonify(app.agent.csuite.get_status())
        return jsonify({"note": "C-Suite not initialized yet", "agents": []})

    @app.route("/api/csuite/decisions")
    def api_csuite_decisions():
        if app.agent and app.agent.db:
            return jsonify(app.agent.db.get_csuite_decisions(limit=50))
        return jsonify([])

    return app
