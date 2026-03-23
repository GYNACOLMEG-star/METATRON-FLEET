import aiosqlite
from server.database import upsert_metrics, fetch_recent_metrics


async def ingest(db, machine_id: str, metrics: dict, recorded_at: str):
    await upsert_metrics(db, machine_id, metrics, recorded_at)


async def get_recent(db, machine_id: str, n: int = 60):
    return await fetch_recent_metrics(db, machine_id, n)
