"""
OpenClaw Dispatch Engine
Manages per-machine command queues, retry logic, and result correlation.
Pull-model: agents poll for work rather than server pushing.
"""
import asyncio
import logging
from typing import Dict, List

import aiosqlite

from server.config import settings
from server.database import utcnow

logger = logging.getLogger("openclaw")


class OpenClawEngine:
    """
    OpenClaw Dispatch Engine.
    Maintains per-machine asyncio queues backed by SQLite for durability.
    """

    def __init__(self):
        self._queues: Dict[str, asyncio.Queue] = {}
        self._timeout_task: asyncio.Task = None
        self.active = False

    def _get_queue(self, machine_id: str) -> asyncio.Queue:
        if machine_id not in self._queues:
            self._queues[machine_id] = asyncio.Queue(
                maxsize=settings.OPENCLAW_QUEUE_MAXSIZE
            )
        return self._queues[machine_id]

    async def startup(self, db_path: str):
        """Reload pending commands from DB into memory queues on server restart."""
        self.active = True
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT id, machine_id FROM commands WHERE status = 'pending' ORDER BY created_at"
            ) as cur:
                rows = await cur.fetchall()
                for row in rows:
                    q = self._get_queue(row["machine_id"])
                    if not q.full():
                        await q.put(row["id"])
        logger.info(f"OpenClaw Engine started. Reloaded {len(rows) if rows else 0} pending commands.")
        self._timeout_task = asyncio.create_task(self._timeout_watcher(db_path))

    async def shutdown(self):
        self.active = False
        if self._timeout_task:
            self._timeout_task.cancel()
            try:
                await self._timeout_task
            except asyncio.CancelledError:
                pass
        logger.info("OpenClaw Engine stopped.")

    async def dispatch(self, machine_id: str, command_id: str):
        """Enqueue a newly created command for delivery."""
        q = self._get_queue(machine_id)
        try:
            await asyncio.wait_for(q.put(command_id), timeout=1.0)
            logger.info(f"[OpenClaw] Dispatched command {command_id} -> machine {machine_id}")
        except (asyncio.TimeoutError, asyncio.QueueFull):
            logger.warning(f"[OpenClaw] Queue full for machine {machine_id}, command {command_id} held in DB only")

    async def poll(self, machine_id: str, limit: int = 5) -> List[str]:
        """Return up to `limit` pending command IDs for a machine."""
        q = self._get_queue(machine_id)
        command_ids = []
        for _ in range(limit):
            try:
                command_ids.append(q.get_nowait())
            except asyncio.QueueEmpty:
                break
        return command_ids

    async def _timeout_watcher(self, db_path: str):
        """Mark commands as timed-out if they stay in sent/running state too long."""
        while self.active:
            await asyncio.sleep(15)
            try:
                now = utcnow()
                async with aiosqlite.connect(db_path) as db:
                    # Mark commands timed out if sent more than timeout_seconds ago
                    await db.execute(
                        """UPDATE commands SET status = 'timeout', completed_at = ?
                           WHERE status IN ('sent', 'running')
                           AND datetime(sent_at, '+' || timeout_seconds || ' seconds') < datetime(?)""",
                        (now, now),
                    )
                    await db.commit()
            except Exception as e:
                logger.error(f"[OpenClaw] Timeout watcher error: {e}")


# Singleton engine instance
openclaw = OpenClawEngine()
