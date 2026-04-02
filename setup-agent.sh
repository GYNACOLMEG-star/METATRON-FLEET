#!/usr/bin/env bash
# setup-agent.sh — Deploy OpenClaw Agent on this machine
#
# Usage:
#   ./setup-agent.sh <laptop-number> <server-url>
#
# Examples:
#   ./setup-agent.sh 1 http://10.0.0.5:8000   # sets up as laptop-1
#   ./setup-agent.sh 2 http://10.0.0.5:8000   # sets up as laptop-2
#   ./setup-agent.sh 3 http://10.0.0.5:8000   # sets up as laptop-3

set -euo pipefail

LAPTOP_NUM="${1:-}"
SERVER_URL="${2:-}"
INSTALL_DIR="/opt/openclaw"

# ── Validate args ──────────────────────────────────────────────────────────────
if [[ -z "$LAPTOP_NUM" || -z "$SERVER_URL" ]]; then
    echo "Usage: $0 <laptop-number> <server-url>"
    echo "  e.g. $0 1 http://10.0.0.5:8000"
    exit 1
fi

if [[ ! "$LAPTOP_NUM" =~ ^[1-3]$ ]]; then
    echo "Error: laptop-number must be 1, 2, or 3."
    exit 1
fi

MACHINE_NAME="laptop-${LAPTOP_NUM}"

echo "==> Setting up OpenClaw Agent: $MACHINE_NAME → $SERVER_URL"

# ── Install files ──────────────────────────────────────────────────────────────
echo "==> Copying agent to $INSTALL_DIR ..."
mkdir -p "$INSTALL_DIR"
cp -r "$(dirname "$0")/agent/"* "$INSTALL_DIR/"

# Write the config with the correct server_url
cat > "$INSTALL_DIR/agent_config.yaml" <<EOF
server_url: "$SERVER_URL"
machine_name: "$MACHINE_NAME"
machine_id: null
api_key: null
heartbeat_interval: 10
poll_interval: 5
EOF

# ── Install Python deps ────────────────────────────────────────────────────────
echo "==> Installing Python dependencies ..."
pip3 install --quiet httpx PyYAML psutil

# ── Optional: install systemd service ────────────────────────────────────────
if command -v systemctl &>/dev/null && [[ $EUID -eq 0 ]]; then
    echo "==> Installing systemd service (openclaw-agent) ..."
    cat > /etc/systemd/system/openclaw-agent.service <<EOF
[Unit]
Description=OpenClaw Agent - METATRON-FLEET ($MACHINE_NAME)
After=network.target

[Service]
ExecStart=/usr/bin/python3 $INSTALL_DIR/openclaw_agent.py
WorkingDirectory=$INSTALL_DIR
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable --now openclaw-agent
    echo "==> Service started. Check: systemctl status openclaw-agent"
else
    echo "==> Skipping systemd install (not root or systemd unavailable)."
    echo "    To run manually:  python3 $INSTALL_DIR/openclaw_agent.py"
fi

echo "==> Done. $MACHINE_NAME is ready to join METATRON-FLEET."
