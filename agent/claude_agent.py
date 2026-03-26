#!/usr/bin/env python3
"""
Claude Agent — METATRON-FLEET Inter-Claude Communication
Registers with the Command Center, polls for ICC messages from other Claude agents,
processes them through the Anthropic API, and posts replies back.

Usage:
    python agent/claude_agent.py
    python agent/claude_agent.py --config agent/claude_beta_config.yaml
    python agent/claude_agent.py --send <recipient_name> "Your message here"
    python agent/claude_agent.py --config agent/claude_beta_config.yaml --send claude-alpha "Hi!"
"""
import argparse
import logging
import os
import signal
import socket
import sys
import time
from pathlib import Path
from typing import Optional

import httpx
import yaml

try:
    import anthropic
except ImportError:
    print("ERROR: 'anthropic' package not found. Run: pip install anthropic>=0.25.0")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ClaudeAgent] %(levelname)s: %(message)s",
)
logger = logging.getLogger("claude-agent")

DEFAULT_CONFIG_PATH = Path(__file__).parent / "claude_agent_config.yaml"
RUNNING = True

# Set by main() after argument parsing
_config_path: Path = DEFAULT_CONFIG_PATH


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def load_config() -> dict:
    if not _config_path.exists():
        raise FileNotFoundError(
            f"Config not found at {_config_path}. "
            "Copy agent/claude_agent_config.yaml and edit it."
        )
    with open(_config_path) as f:
        return yaml.safe_load(f)


def save_config(cfg: dict):
    with open(_config_path, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False)


# ---------------------------------------------------------------------------
# Server registration (reuses the existing OpenClaw /api/machines/register)
# ---------------------------------------------------------------------------

def register(cfg: dict, client: httpx.Client) -> dict:
    logger.info(f"Registering with Command Center at {cfg['server_url']}...")
    resp = client.post(
        f"{cfg['server_url']}/api/machines/register",
        json={
            "name": cfg["agent_name"],
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


# ---------------------------------------------------------------------------
# ICC helpers
# ---------------------------------------------------------------------------

def send_icc_message(
    cfg: dict,
    client: httpx.Client,
    recipient_id: str,
    content: str,
    thread_id: Optional[str] = None,
) -> dict:
    payload: dict = {
        "sender_id": cfg["machine_id"],
        "api_key": cfg["api_key"],
        "recipient_id": recipient_id,
        "content": content,
    }
    if thread_id:
        payload["thread_id"] = thread_id
    resp = client.post(
        f"{cfg['server_url']}/api/icc/send",
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def poll_icc_messages(cfg: dict, client: httpx.Client) -> list[dict]:
    resp = client.get(
        f"{cfg['server_url']}/api/icc/pending/{cfg['machine_id']}",
        params={"api_key": cfg["api_key"]},
        timeout=10,
    )
    if resp.status_code != 200:
        return []
    return resp.json().get("messages", [])


def reply_to_icc(
    cfg: dict,
    client: httpx.Client,
    message_id: str,
    content: str,
) -> dict:
    resp = client.post(
        f"{cfg['server_url']}/api/icc/messages/{message_id}/reply",
        json={
            "agent_id": cfg["machine_id"],
            "api_key": cfg["api_key"],
            "content": content,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_thread(
    cfg: dict,
    client: httpx.Client,
    thread_id: str,
) -> list[dict]:
    resp = client.get(
        f"{cfg['server_url']}/api/icc/thread/{thread_id}",
        params={"agent_id": cfg["machine_id"], "api_key": cfg["api_key"]},
        timeout=10,
    )
    if resp.status_code != 200:
        return []
    return resp.json()


def lookup_machine_by_name(
    cfg: dict,
    client: httpx.Client,
    name: str,
) -> Optional[str]:
    """Return machine_id for the first machine whose name matches (case-insensitive)."""
    resp = client.get(
        f"{cfg['server_url']}/api/machines",
        timeout=10,
    )
    if resp.status_code != 200:
        return None
    machines = resp.json()
    for m in machines:
        if m.get("name", "").lower() == name.lower():
            return m["id"]
    return None


# ---------------------------------------------------------------------------
# Anthropic processing
# ---------------------------------------------------------------------------

def build_anthropic_messages(thread_messages: list[dict], new_content: str) -> list[dict]:
    """
    Convert thread history into Anthropic-compatible messages format.
    role 'user' → 'user', role 'assistant' → 'assistant'.
    Append the new incoming message as a user turn.
    """
    result = []
    for msg in thread_messages:
        role = "user" if msg["role"] == "user" else "assistant"
        result.append({"role": role, "content": msg["content"]})

    # Only append if not already in thread
    if not thread_messages or thread_messages[-1]["content"] != new_content:
        result.append({"role": "user", "content": new_content})

    return result


def call_claude(
    anthropic_client: anthropic.Anthropic,
    cfg: dict,
    thread_messages: list[dict],
    new_content: str,
) -> str:
    """Call the Anthropic API and return the reply text."""
    messages = build_anthropic_messages(thread_messages, new_content)
    system_prompt = cfg.get(
        "system_prompt",
        (
            f"You are {cfg['agent_name']}, a Claude AI agent participating in an "
            "inter-agent conversation over the METATRON-FLEET communication network. "
            "You are talking to another Claude agent. Be direct and collaborative."
        ),
    )
    model = cfg.get("model", "claude-opus-4-6")

    with anthropic_client.messages.stream(
        model=model,
        max_tokens=cfg.get("max_tokens", 4096),
        thinking={"type": "adaptive"},
        system=system_prompt,
        messages=messages,
    ) as stream:
        reply = stream.get_final_message()

    text_blocks = [b.text for b in reply.content if b.type == "text"]
    return "\n".join(text_blocks).strip()


# ---------------------------------------------------------------------------
# Heartbeat (keep machine online so it shows up in the dashboard)
# ---------------------------------------------------------------------------

def send_heartbeat(cfg: dict, client: httpx.Client):
    try:
        client.post(
            f"{cfg['server_url']}/api/machines/{cfg['machine_id']}/heartbeat",
            json={"machine_id": cfg["machine_id"], "api_key": cfg["api_key"]},
            timeout=5,
        )
    except Exception as e:
        logger.warning(f"Heartbeat failed: {e}")


# ---------------------------------------------------------------------------
# Signal handling
# ---------------------------------------------------------------------------

def shutdown_handler(sig, frame):
    global RUNNING
    logger.info("Shutdown signal received. Stopping Claude agent...")
    RUNNING = False


signal.signal(signal.SIGTERM, shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run_agent(cfg: dict):
    global RUNNING

    api_key = cfg.get("anthropic_api_key") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error(
            "No Anthropic API key found. Set 'anthropic_api_key' in config "
            "or export ANTHROPIC_API_KEY."
        )
        sys.exit(1)

    anthropic_client = anthropic.Anthropic(api_key=api_key)
    http_client = httpx.Client(
        headers={"User-Agent": f"ClaudeAgent/1.0 ({cfg['agent_name']})"},
    )

    # Register if not yet done
    if not cfg.get("machine_id") or not cfg.get("api_key"):
        retries = 0
        while RUNNING:
            try:
                cfg = register(cfg, http_client)
                break
            except Exception as e:
                retries += 1
                wait = min(2 ** retries, 60)
                logger.warning(f"Registration failed ({e}). Retrying in {wait}s...")
                time.sleep(wait)

    poll_interval = cfg.get("poll_interval", 5)
    heartbeat_interval = cfg.get("heartbeat_interval", 15)
    last_poll = 0
    last_heartbeat = 0

    logger.info(f"Claude Agent running: {cfg['agent_name']} ({cfg['machine_id']})")
    logger.info(f"Server: {cfg['server_url']}")
    logger.info("Waiting for inter-Claude messages...")

    while RUNNING:
        now = time.time()

        if now - last_heartbeat >= heartbeat_interval:
            send_heartbeat(cfg, http_client)
            last_heartbeat = now

        if now - last_poll >= poll_interval:
            last_poll = now
            try:
                messages = poll_icc_messages(cfg, http_client)
            except Exception as e:
                logger.warning(f"Poll failed: {e}")
                time.sleep(1)
                continue

            for msg in messages:
                msg_id = msg["id"]
                thread_id = msg["thread_id"]
                sender_id = msg["sender_id"]
                content = msg["content"]

                logger.info(
                    f"[{msg_id[:8]}] Received from {sender_id[:8]}: {content[:80]!r}"
                )

                # Fetch existing thread history for context
                try:
                    history = fetch_thread(cfg, http_client, thread_id)
                except Exception as e:
                    logger.warning(f"Could not fetch thread history: {e}")
                    history = []

                # Call Claude API
                try:
                    reply_text = call_claude(anthropic_client, cfg, history, content)
                    logger.info(f"[{msg_id[:8]}] Replying: {reply_text[:80]!r}")
                except Exception as e:
                    logger.error(f"Anthropic API error: {e}")
                    reply_text = f"[Error generating response: {e}]"

                # Post reply back
                try:
                    reply_to_icc(cfg, http_client, msg_id, reply_text)
                except Exception as e:
                    logger.error(f"Failed to post reply: {e}")

        time.sleep(1)

    http_client.close()
    logger.info("Claude Agent stopped.")


# ---------------------------------------------------------------------------
# CLI: --send mode (initiate a message to another agent)
# ---------------------------------------------------------------------------

def cli_send(cfg: dict, recipient_name: str, message: str):
    http_client = httpx.Client(
        headers={"User-Agent": f"ClaudeAgent/1.0 ({cfg['agent_name']})"},
    )

    if not cfg.get("machine_id") or not cfg.get("api_key"):
        logger.error("Agent not registered yet. Run the agent in normal mode first.")
        sys.exit(1)

    recipient_id = lookup_machine_by_name(cfg, http_client, recipient_name)
    if not recipient_id:
        logger.error(f"No registered agent named '{recipient_name}' found.")
        sys.exit(1)

    result = send_icc_message(cfg, http_client, recipient_id, message)
    logger.info(
        f"Message sent to {recipient_name} ({recipient_id[:8]}). "
        f"Thread: {result['thread_id']}"
    )
    http_client.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    global _config_path

    parser = argparse.ArgumentParser(description="METATRON-FLEET Claude Agent")
    parser.add_argument(
        "--config",
        metavar="PATH",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to agent config YAML (default: agent/claude_agent_config.yaml)",
    )
    parser.add_argument(
        "--send",
        metavar="RECIPIENT_NAME",
        help="Send a one-shot ICC message to another Claude agent by name",
    )
    parser.add_argument(
        "message",
        nargs="?",
        help="Message text when using --send",
    )
    args = parser.parse_args()

    _config_path = Path(args.config)
    cfg = load_config()

    if args.send:
        if not args.message:
            parser.error("Provide a message after the recipient name.")
        cli_send(cfg, args.send, args.message)
    else:
        run_agent(cfg)


if __name__ == "__main__":
    main()
