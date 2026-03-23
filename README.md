# METATRON-FLEET Command Center

Fleet machine management powered by the **OpenClaw Engine**.

## Architecture

```
Command Center Server  ←→  Web Dashboard (browser)
        ↑
   OpenClaw Engine (command dispatch, pull-model)
        ↑
   OpenClaw Agents (running on each managed machine)
```

Agents **pull** commands from the server — they work behind NAT/firewalls with no inbound ports required.

## Quick Start

### 1. Start the Command Center Server

```bash
pip install -r requirements.txt
python -m server.main
```

Dashboard opens at: **http://localhost:8000/**

### 2. Deploy an Agent on Each Machine

Copy the `agent/` directory to the target machine, then:

```bash
pip install -r requirements-agent.txt

# Edit agent_config.yaml — set server_url and machine_name
nano agent/agent_config.yaml

python agent/openclaw_agent.py
```

The agent auto-registers on first run and writes its credentials back to `agent_config.yaml`.

### 3. Run as a systemd Service (optional)

```ini
[Unit]
Description=OpenClaw Agent - METATRON-FLEET
After=network.target

[Service]
ExecStart=/usr/bin/python3 /opt/openclaw/agent/openclaw_agent.py
WorkingDirectory=/opt/openclaw
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## Configuration

### Server (`environment variables`)

| Variable | Default | Description |
|---|---|---|
| `DB_PATH` | `metatron.db` | SQLite database path |
| `SECRET_KEY` | random | HMAC key for API key hashing |
| `SERVER_HOST` | `0.0.0.0` | Bind address |
| `SERVER_PORT` | `8000` | Listen port |
| `MACHINE_TIMEOUT_SECONDS` | `30` | Seconds before machine marked offline |

### Agent (`agent/agent_config.yaml`)

| Key | Description |
|---|---|
| `server_url` | Command Center URL (e.g. `http://10.0.0.1:8000`) |
| `machine_name` | Human-readable name for this machine |
| `heartbeat_interval` | Seconds between heartbeats (default 10) |
| `poll_interval` | Seconds between command polls (default 5) |

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/machines/register` | Register a new machine |
| `GET` | `/api/machines` | List all machines |
| `GET` | `/api/machines/{id}` | Machine detail + metrics |
| `DELETE` | `/api/machines/{id}` | Deregister machine |
| `POST` | `/api/machines/{id}/heartbeat` | Agent heartbeat |
| `POST` | `/api/commands/dispatch` | Dispatch command to machine |
| `GET` | `/api/commands` | List commands |
| `GET` | `/api/commands/{id}` | Command detail |
| `GET` | `/api/commands/pending/{machine_id}` | Agent polls for work |
| `POST` | `/api/commands/{id}/result` | Agent posts result |
| `WS` | `/ws/fleet` | Real-time fleet updates |

## Security Notes

- API keys are HMAC-SHA256 hashed — never stored in plain text.
- The dashboard has no authentication in the base build. For production, add HTTP Basic Auth or a reverse proxy with auth.
- Agents run commands as the user that started the agent process. Treat command dispatch as full shell access.
