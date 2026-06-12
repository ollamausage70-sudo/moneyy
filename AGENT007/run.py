#!/usr/bin/env python3
import asyncio
import logging
import os
import sys
import threading
import time
import json
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config
from agent.database import DatabaseManager
from agent.core import AgentCore
from agent.skills.bounty_hunter import BountyHunterSkill
from agent.skills.harness import HarnessEngine
from dashboard.app import create_app

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("run")

required_vars = {
    "WALLET_ADDRESS": config.WALLET_ADDRESS,
}

has_llm = config.OMNIROUTE_URL or config.GEMINI_API_KEY or config.GROQ_API_KEY or config.GITHUB_TOKEN
if not has_llm:
    logger.warning("No LLM provider configured (OMNIROUTE_URL, GEMINI_API_KEY, GROQ_API_KEY, or GITHUB_TOKEN)")
    logger.warning("Agent will use hardcoded decisions only.")

missing = [k for k, v in required_vars.items() if not v]
if missing:
    logger.warning("MISSING required env vars: %s", ", ".join(missing))

mp_count = sum(1 for mp in config.MARKETPLACE_CONFIG.values() if mp.get("enabled"))
logger.info("Marketplaces enabled: %d/6", mp_count)
if mp_count == 0:
    logger.warning("No marketplaces enabled — agent cannot earn.")

from flask import jsonify

agent = None
db = DatabaseManager()

try:
    agent = AgentCore(db)
    bounty = BountyHunterSkill(agent.brain)
    agent.register_skill("bounty_hunter", bounty)
    harness = HarnessEngine(agent.brain, bounty.marketplaces)
    agent.set_harness(harness)
    agent.init_csuite()
    logger.info("Agent + HarnessEngine + C-Suite initialized successfully")
    if not has_llm:
        logger.warning("Agent running in degraded mode — no LLM provider configured")
except Exception as e:
    logger.error("Agent init failed: %s", e)
    logger.info("App will serve /debug endpoint for troubleshooting")

app = create_app(agent)


def _dedicated_event_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop


SCHEDULER_BACKOFF_INITIAL = 30
SCHEDULER_BACKOFF_MAX = 1800
_scheduler_backoff = SCHEDULER_BACKOFF_INITIAL


def _scheduler():
    global _scheduler_backoff
    render_url = os.getenv("RENDER_EXTERNAL_URL", "")
    loop = _dedicated_event_loop()

    while True:
        try:
            if agent and has_llm:
                loop.run_until_complete(agent.run_cycle())
                logger.info("Scheduler cycle %d done", agent.cycle_count)
                _scheduler_backoff = SCHEDULER_BACKOFF_INITIAL
            elif not has_llm:
                logger.warning("Skipping cycle — no LLM provider configured")

            if render_url:
                try:
                    urllib.request.urlopen(f"{render_url}/health", timeout=10)
                except Exception:
                    pass

        except Exception as e:
            logger.error("Scheduler cycle failed: %s", e)
            logger.info("Backing off %ds...", _scheduler_backoff)
            time.sleep(_scheduler_backoff)
            _scheduler_backoff = min(_scheduler_backoff * 2, SCHEDULER_BACKOFF_MAX)
            continue

        interval = config.CYCLE_INTERVAL_SECONDS
        if agent and agent.cycle_count > 0:
            db.backup_to_json()
        time.sleep(interval)


scheduler_thread = threading.Thread(target=_scheduler, daemon=True)
scheduler_thread.start()
logger.info("Scheduler started (interval: %ds)", config.CYCLE_INTERVAL_SECONDS)


@app.route("/debug")
def debug():
    keys = {
        "OMNIROUTE_URL": bool(config.OMNIROUTE_URL),
        "GEMINI_API_KEY": bool(config.GEMINI_API_KEY),
        "GROQ_API_KEY": bool(config.GROQ_API_KEY),
        "GITHUB_TOKEN": bool(config.GITHUB_TOKEN),
        "WALLET_ADDRESS": config.WALLET_ADDRESS[:10] + "..." if config.WALLET_ADDRESS else "MISSING",
        "YOYO": bool(config.MARKETPLACE_CONFIG["yoyo"]["api_key"]),
        "DEALWORK": bool(config.MARKETPLACE_CONFIG["dealwork"]["api_key"]),
        "OPENTASK": bool(config.MARKETPLACE_CONFIG["opentask"]["api_key"]),
        "UGIG": bool(config.MARKETPLACE_CONFIG["ugig"]["api_key"]),
        "AGENTHANSA": bool(config.MARKETPLACE_CONFIG["agenthansa"]["api_key"]),
        "ANYTASKS": bool(config.MARKETPLACE_CONFIG["anytasks"]["api_key"]),
        "has_llm": has_llm,
        "mp_count": mp_count,
    }
    return keys


@app.route("/cycle")
def run_cycle():
    if agent is None:
        return jsonify({"status": "error", "error": "Agent not initialized — check /debug"}), 500
    if not has_llm:
        return jsonify({"status": "error", "error": "No LLM provider configured"}), 500
    def _run():
        loop = _dedicated_event_loop()
        try:
            loop.run_until_complete(agent.run_cycle())
        except Exception as e:
            logger.error("Manual cycle failed: %s", e)
    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return {"status": "ok", "message": "Cycle started in background thread"}


@app.route("/api/scan")
def api_scan():
    if agent is None:
        return jsonify({"error": "No agent"}), 500
    bounty = agent.skills.get("bounty_hunter")
    if not bounty:
        return jsonify({"error": "No bounty_hunter"}), 500

    mp_counts = {}
    for mp in bounty.marketplaces:
        try:
            raw = mp.list_tasks()
            mp_counts[mp.name] = {"count": len(raw), "sample": str(raw[:1])[:200] if raw else None}
        except Exception as e:
            mp_counts[mp.name] = {"error": str(e)[:200]}

    try:
        loop = _dedicated_event_loop()
        tasks = loop.run_until_complete(bounty.find_opportunities())
        fo_count = len(tasks)
        fo_samples = [{"id": t.id, "title": t.title[:30], "reward": t.reward, "source": t.source} for t in tasks[:3]]
    except Exception as e:
        fo_count = f"ERROR: {e}"
        fo_samples = []

    return jsonify({
        "direct_list_tasks": mp_counts,
        "find_opportunities_result": fo_count,
        "find_opportunities_samples": fo_samples,
    })


@app.route("/api/test/marketplaces")
def test_marketplaces():
    if agent is None:
        return jsonify({"error": "No agent"}), 500
    bounty = agent.skills.get("bounty_hunter")
    if not bounty:
        return jsonify({"error": "No bounty_hunter"}), 500
    results = {}
    for mp in bounty.marketplaces:
        try:
            tasks = mp.list_tasks()
            first3 = [{"id": t.get("id", "?"), "title": t.get("title", "?")[:30], "reward": t.get("reward", 0), "raw_reward": str(t.get("reward"))} for t in tasks[:3]]
            results[mp.name] = {"status": "ok", "count": len(tasks), "samples": first3}
        except Exception as e:
            results[mp.name] = {"status": "error", "error": str(e)[:200]}
    return jsonify(results)


@app.route("/api/pipeline")
def api_pipeline():
    if agent is None:
        return jsonify({"error": "No agent"}), 500
    try:
        bizdev = agent.csuite.get("BizDev") if hasattr(agent, "csuite") else None
        if not bizdev:
            return jsonify({"error": "No BizDev"}), 500
        pipe = getattr(bizdev, "opportunity_pipeline", [])
        return jsonify({
            "pipeline_size": len(pipe),
            "top_entries": [{
                "task_id": e.get("task_id", "?"),
                "title": e.get("title", "?")[:40],
                "source": e.get("source", "?"),
                "reward": e.get("reward", 0),
                "score": e.get("score", 0),
                "bid": e.get("recommended_bid", 0),
            } for e in pipe[:5]],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/test/scan_debug")
def scan_debug():
    if agent is None:
        return jsonify({"error": "No agent"}), 500
    bounty = agent.skills.get("bounty_hunter")
    if not bounty:
        return jsonify({"error": "No bounty_hunter"}), 500
    results = {}
    for mp in bounty.marketplaces:
        try:
            raw = mp.list_tasks()
            results[mp.name] = {
                "count": len(raw),
                "first_id": raw[0].get("id", "?") if raw else None,
                "first_reward": str(raw[0].get("reward", 0)) if raw else None,
                "raw_sample": str(raw[0])[:300] if raw else None,
            }
        except Exception as e:
            results[mp.name] = {"error": str(e)[:100]}
    return jsonify({"marketplaces": results, "total_mps": len(bounty.marketplaces)})


@app.route("/train")
def manual_train():
    if agent is None:
        return jsonify({"status": "error", "error": "Agent not initialized"}), 500
    try:
        bounty = agent.skills.get("bounty_hunter")
        if not bounty:
            return jsonify({"status": "error", "error": "BountyHunter not registered"}), 500
        report = bounty.trainer.get_training_report()
        return {"status": "ok", "report": report, "stats": bounty.trainer.get_status()}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.route("/health")
def health():
    if agent is None:
        return {"status": "degraded", "agent": "uninitialized", "missing": missing}
    return {
        "status": "alive",
        "agent": agent.name,
        "wallet": agent.wallet.is_connected(),
        "cycle": agent.cycle_count,
        "missing": missing,
    }


@app.route("/api/backup")
def trigger_backup():
    try:
        path = db.backup_to_json()
        return {"status": "ok", "backup_path": str(path)}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.route("/api/tiers")
def api_tiers():
    if agent is None:
        return jsonify({"error": "No agent"}), 500
    return jsonify(agent.business_model.get_status())


@app.route("/api/tiers/upgrade/<int:tier>")
def api_upgrade_tier(tier):
    if agent is None:
        return jsonify({"error": "No agent"}), 500
    ok = agent.business_model.upgrade_tier(tier)
    return jsonify({"upgraded": ok, "current": agent.business_model.get_current_tier()})


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    name = agent.name if agent else "AGENT007 (degraded)"
    logger.info("%s starting on port %d", name, port)
    logger.info("Visit /debug to check environment variables")
    logger.info("Run with gunicorn in production: gunicorn run:app --bind 0.0.0.0:$PORT --workers 1 --threads 2")
    app.run(host="0.0.0.0", port=port, debug=False)
