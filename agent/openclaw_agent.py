#!/usr/bin/env python3
"""
OpenClaw Agent — METATRON-FLEET
Runs on each managed machine. Registers with the Command Center,
sends heartbeats, polls for commands, and posts results.
"""
import logging
import os
import signal
import socket
import sys
import time
from pathlib import Path

import httpx
import yaml

# Allow running as: python agent/openclaw_agent.py
sys.path.insert(0, str(Path(__file__).parent))
from executor import execute
from metrics import collect

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [OpenClaw] %(levelname)s: %(message)s",
)
logger = logging.getLogger("openclaw-agent")

CONFIG_PATH = Path(__file__).parent / "agent_config.yaml"
RUNNING = True


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def save_config(cfg: dict):
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False)


def register(cfg: dict, client: httpx.Client) -> dict:
    logger.info(f"Registering with Command Center at {cfg['server_url']}...")
    resp = client.post(
        f"{cfg['server_url']}/api/machines/register",
        json={
            "name": cfg["machine_name"],
            "hostname": socket.gethostname(),
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    cfg["machine_id"] = data["machine_id"]
    cfg["api_key"] = data["api_key"]
    save_config(cfg)
    logger.info(f"Registered. Machine ID: {cfg['machine_id']}")
    return cfg


def send_heartbeat(cfg: dict, client: httpx.Client):
    metrics = collect()
    client.post(
        f"{cfg['server_url']}/api/machines/{cfg['machine_id']}/heartbeat",
        json={
            "machine_id": cfg["machine_id"],
            "api_key": cfg["api_key"],
            "metrics": metrics,
        },
        timeout=5,
    )


def poll_and_execute(cfg: dict, client: httpx.Client):
    resp = client.get(
        f"{cfg['server_url']}/api/commands/pending/{cfg['machine_id']}",
        params={"api_key": cfg["api_key"]},
        timeout=5,
    )
    if resp.status_code != 200:
        return

    commands = resp.json().get("commands", [])
    for cmd in commands:
        command_id = cmd["id"]
        command_text = cmd["command_text"]
        timeout_secs = cmd.get("timeout_seconds", 60)

        logger.info(f"Executing [{command_id[:8]}]: {command_text!r}")
        result = execute(command_text, timeout=timeout_secs)
        logger.info(f"Done [{command_id[:8]}] exit={result['exit_code']}")

        try:
            client.post(
                f"{cfg['server_url']}/api/commands/{command_id}/result",
                json={
                    "machine_id": cfg["machine_id"],
                    "api_key": cfg["api_key"],
                    **result,
                },
                timeout=10,
            )
        except Exception as e:
            logger.error(f"Failed to post result for {command_id}: {e}")


def shutdown_handler(sig, frame):
    global RUNNING
    logger.info("Shutdown signal received. Stopping OpenClaw agent...")
    RUNNING = False


signal.signal(signal.SIGTERM, shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)


def main():
    global RUNNING
    cfg = load_config()

    client = httpx.Client(
        headers={"User-Agent": f"OpenClaw-Agent/1.0 ({cfg['machine_name']})"},
    )

    # Register if not yet done
    if not cfg.get("machine_id") or not cfg.get("api_key"):
        retries = 0
        while RUNNING:
            try:
                cfg = register(cfg, client)
                break
            except Exception as e:
                retries += 1
                wait = min(2 ** retries, 60)
                logger.warning(f"Registration failed ({e}). Retrying in {wait}s...")
                time.sleep(wait)

    heartbeat_interval = cfg.get("heartbeat_interval", 10)
    poll_interval = cfg.get("poll_interval", 5)
    last_heartbeat = 0
    last_poll = 0

    logger.info(f"OpenClaw Agent running. Server: {cfg['server_url']}")
    logger.info(f"Machine: {cfg['machine_name']} ({cfg['machine_id']})")

    while RUNNING:
        now = time.time()

        if now - last_heartbeat >= heartbeat_interval:
            try:
                send_heartbeat(cfg, client)
                last_heartbeat = now
            except Exception as e:
                logger.warning(f"Heartbeat failed: {e}")

        if now - last_poll >= poll_interval:
            try:
                poll_and_execute(cfg, client)
                last_poll = now
            except Exception as e:
                logger.warning(f"Poll failed: {e}")

        time.sleep(1)

    client.close()
    logger.info("OpenClaw Agent stopped.")


if __name__ == "__main__":
    main()
