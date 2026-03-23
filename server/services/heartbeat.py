import asyncio
import logging
from datetime import datetime, timezone, timedelta

import aiosqlite

from server.config import settings
from server.database import fetch_all_machines, update_machines_offline
from server.ws.hub import hub

logger = logging.getLogger("heartbeat")


async def heartbeat_loop(db_path: str):
    """Background task: marks machines offline after timeout and broadcasts fleet state."""
    while True:
        await asyncio.sleep(settings.HEARTBEAT_CHECK_INTERVAL)
        try:
            cutoff = (
                datetime.now(timezone.utc)
                - timedelta(seconds=settings.MACHINE_TIMEOUT_SECONDS)
            ).isoformat()

            async with aiosqlite.connect(db_path) as db:
                db.row_factory = aiosqlite.Row
                await update_machines_offline(db, cutoff)
                machines = await fetch_all_machines(db)

            await hub.broadcast("FLEET_UPDATE", {"machines": machines})
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Heartbeat loop error: {e}")
