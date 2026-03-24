# METATRON-FLEET — BRAIN DUMP

> This file is the external memory for this project.
> Any Claude session, any device, any time — start here.
> Last updated: 2026-03-24

---

## WHAT IS THIS PROJECT?

You are building a **remote fleet management system** for a small group of laptops (3 machines).

- You control all the machines from **one central dashboard** in your web browser.
- Each laptop runs a small background program called the **OpenClaw Agent**.
- The agents check in with the server and wait for commands — like an old dial-up connection, but always on.
- You can send shell commands to any laptop from the dashboard, see if it's online, and check its stats.

---

## THE TWO PIECES

### 1. THE SERVER (runs on YOUR main machine)
```
Location: server/
Starts with: python -m server.main
Dashboard URL: http://localhost:8000/
```
This is the command center. Run it once on the machine you want to control things from.

### 2. THE AGENT (runs on each laptop you want to control)
```
Location: agent/
Config file: agent/agent_config.yaml
Starts with: python agent/openclaw_agent.py
```
Each laptop needs the agent installed and pointed at the server's IP address.

---

## HOW TO SET UP A LAPTOP (the simple version)

**On your main machine (the server), find your local IP address:**
```bash
# On Windows:
ipconfig
# Look for "IPv4 Address" — something like 192.168.1.50

# On Linux/Mac:
ip addr
```

**On each laptop, run:**
```bash
git clone https://github.com/GYNACOLMEG-star/METATRON-FLEET.git
cd METATRON-FLEET
bash setup-agent.sh 1 http://YOUR-SERVER-IP:8000
```
Change the `1` to `2` or `3` for the second and third laptops.

---

## CURRENT STATUS (as of 2026-03-24)

| Item | Status |
|------|--------|
| Server code | DONE — in `server/` folder |
| Agent code | DONE — in `agent/` folder |
| `setup-agent.sh` script | DONE — in repo root |
| Laptop 1 set up | NOT YET |
| Laptop 2 set up | NOT YET |
| Laptop 3 set up | NOT YET |
| Server actually running | NOT YET |

---

## THE PROBLEM YOU HIT (and the fix)

**Problem:** Running `bash setup-agent.sh` gave "No such file or directory"
**Why:** The file was on a different git branch, not on `master`
**Fix:** Already done — `setup-agent.sh` is now on `master`

So on each laptop, just do:
```bash
git pull
bash setup-agent.sh 1 http://YOUR-SERVER-IP:8000
```

---

## NEXT STEPS IN ORDER

1. **Find your server's local IP address** (run `ipconfig` on the machine that will be the server)
2. **Start the server:**
   ```bash
   pip install -r requirements.txt
   python -m server.main
   ```
3. **Open the dashboard** in your browser: `http://localhost:8000/`
4. **On each laptop**, run `setup-agent.sh` with the correct IP and laptop number
5. **Watch the dashboard** — each laptop should appear as online within seconds

---

## FOR ANY CLAUDE SESSION PICKING THIS UP

If you are a Claude session helping with this project, here is the full picture:

- **Repo:** `gynacolmeg-star/metatron-fleet` on GitHub
- **Working branch for changes:** `claude/organize-laptops-metatron-MGHNN`
- **User:** Gerard — has memory/visualization challenges, needs things stated simply and directly
- **Goal:** Get 3 laptops registered and visible in the fleet dashboard
- **The code is complete** — this is purely a deployment/setup task now
- **The server IP** needs to be the real local network IP of Gerard's main machine (not 192.0.2.2 which was just a placeholder example)

---

## FILE MAP

```
METATRON-FLEET/
├── BRAIN.md                  <-- YOU ARE HERE (start here always)
├── README.md                 <-- technical reference
├── setup-agent.sh            <-- run this on each laptop to set it up
├── requirements.txt          <-- server dependencies
├── requirements-agent.txt    <-- agent dependencies
├── server/                   <-- command center code
│   ├── main.py               <-- start here: python -m server.main
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── auth.py
│   ├── routers/              <-- API endpoints
│   ├── services/             <-- business logic
│   ├── static/               <-- web dashboard files
│   └── ws/                   <-- real-time websocket
└── agent/                    <-- laptop agent code
    ├── openclaw_agent.py     <-- the agent program
    ├── agent_config.yaml     <-- edit this: set server_url and machine_name
    ├── executor.py           <-- runs shell commands
    └── metrics.py            <-- collects CPU/RAM stats
```
