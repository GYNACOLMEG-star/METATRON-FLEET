import aiosqlite
from server.config import settings

DB_PATH = settings.DB_PATH

CREATE_MACHINES = """
CREATE TABLE IF NOT EXISTS machines (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    hostname TEXT,
    ip_address TEXT,
    api_key_hash TEXT NOT NULL,
    status TEXT DEFAULT 'offline',
    registered_at TEXT,
    last_seen TEXT,
    tags TEXT DEFAULT '[]'
)
"""

CREATE_COMMANDS = """
CREATE TABLE IF NOT EXISTS commands (
    id TEXT PRIMARY KEY,
    machine_id TEXT REFERENCES machines(id),
    command_text TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at TEXT,
    sent_at TEXT,
    completed_at TEXT,
    exit_code INTEGER,
    stdout TEXT,
    stderr TEXT,
    requested_by TEXT,
    timeout_seconds INTEGER DEFAULT 60
)
"""

CREATE_METRICS = """
CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id TEXT REFERENCES machines(id),
    recorded_at TEXT,
    cpu_percent REAL,
    memory_percent REAL,
    disk_percent REAL,
    load_avg_1m REAL,
    uptime_seconds INTEGER
)
"""


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_MACHINES)
        await db.execute(CREATE_COMMANDS)
        await db.execute(CREATE_METRICS)
        await db.commit()


async def connect_db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def get_db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()


async def fetch_machine(db, machine_id: str):
    async with db.execute("SELECT * FROM machines WHERE id = ?", (machine_id,)) as cur:
        row = await cur.fetchone()
        return dict(row) if row else None


async def fetch_all_machines(db):
    async with db.execute("SELECT * FROM machines ORDER BY name") as cur:
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def insert_machine(db, machine: dict):
    await db.execute(
        """INSERT INTO machines (id, name, hostname, ip_address, api_key_hash,
           status, registered_at, last_seen, tags)
           VALUES (:id, :name, :hostname, :ip_address, :api_key_hash,
           :status, :registered_at, :last_seen, :tags)""",
        machine,
    )
    await db.commit()


async def update_machine_heartbeat(db, machine_id: str, last_seen: str, status: str):
    await db.execute(
        "UPDATE machines SET last_seen = ?, status = ? WHERE id = ?",
        (last_seen, status, machine_id),
    )
    await db.commit()


async def update_machines_offline(db, cutoff: str):
    await db.execute(
        "UPDATE machines SET status = 'offline' WHERE last_seen < ? AND status != 'offline'",
        (cutoff,),
    )
    await db.commit()


async def delete_machine(db, machine_id: str):
    await db.execute("DELETE FROM machines WHERE id = ?", (machine_id,))
    await db.commit()


async def insert_command(db, cmd: dict):
    await db.execute(
        """INSERT INTO commands (id, machine_id, command_text, status, created_at,
           requested_by, timeout_seconds)
           VALUES (:id, :machine_id, :command_text, :status, :created_at,
           :requested_by, :timeout_seconds)""",
        cmd,
    )
    await db.commit()


async def fetch_command(db, command_id: str):
    async with db.execute("SELECT * FROM commands WHERE id = ?", (command_id,)) as cur:
        row = await cur.fetchone()
        return dict(row) if row else None


async def fetch_pending_commands(db, machine_id: str, limit: int = 5):
    async with db.execute(
        "SELECT * FROM commands WHERE machine_id = ? AND status = 'pending' ORDER BY created_at LIMIT ?",
        (machine_id, limit),
    ) as cur:
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def fetch_commands(db, machine_id: str = None, status: str = None, limit: int = 50):
    query = "SELECT * FROM commands WHERE 1=1"
    params = []
    if machine_id:
        query += " AND machine_id = ?"
        params.append(machine_id)
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    async with db.execute(query, params) as cur:
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def update_command_sent(db, command_id: str, sent_at: str):
    await db.execute(
        "UPDATE commands SET status = 'sent', sent_at = ? WHERE id = ?",
        (sent_at, command_id),
    )
    await db.commit()


async def update_command_result(db, command_id: str, result: dict):
    await db.execute(
        """UPDATE commands SET status = ?, completed_at = ?, exit_code = ?,
           stdout = ?, stderr = ? WHERE id = ?""",
        (
            result["status"],
            result["completed_at"],
            result["exit_code"],
            result["stdout"],
            result["stderr"],
            command_id,
        ),
    )
    await db.commit()


async def upsert_metrics(db, machine_id: str, metrics: dict, recorded_at: str):
    await db.execute(
        """INSERT INTO metrics (machine_id, recorded_at, cpu_percent, memory_percent,
           disk_percent, load_avg_1m, uptime_seconds)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            machine_id,
            recorded_at,
            metrics.get("cpu_percent"),
            metrics.get("memory_percent"),
            metrics.get("disk_percent"),
            metrics.get("load_avg_1m"),
            metrics.get("uptime_seconds"),
        ),
    )
    # Keep only last 1000 rows per machine
    await db.execute(
        """DELETE FROM metrics WHERE machine_id = ? AND id NOT IN (
           SELECT id FROM metrics WHERE machine_id = ?
           ORDER BY recorded_at DESC LIMIT 1000)""",
        (machine_id, machine_id),
    )
    await db.commit()


async def fetch_recent_metrics(db, machine_id: str, n: int = 60):
    async with db.execute(
        """SELECT * FROM metrics WHERE machine_id = ?
           ORDER BY recorded_at DESC LIMIT ?""",
        (machine_id, n),
    ) as cur:
        rows = await cur.fetchall()
        return [dict(r) for r in reversed(rows)]
