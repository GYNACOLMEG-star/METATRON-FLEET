import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

import aiosqlite

from server.auth import generate_api_key, hash_api_key, verify_api_key
from server.config import settings
from server.database import (
    delete_machine,
    fetch_all_machines,
    fetch_machine,
    fetch_recent_metrics,
    insert_machine,
    update_machine_heartbeat,
    upsert_metrics,
)
from server.models import (
    HeartbeatPayload,
    MachineRegisterRequest,
    MachineRegisterResponse,
    MachineResponse,
)
from server.services import metrics_store
from server.ws.hub import hub

router = APIRouter(prefix="/api/machines", tags=["machines"])


def get_db_path():
    return settings.DB_PATH


async def _get_db(db_path: str):
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    return db


@router.post("/register", response_model=MachineRegisterResponse)
async def register_machine(req: MachineRegisterRequest, request: Request):
    db = await _get_db(settings.DB_PATH)
    try:
        api_key = generate_api_key()
        machine_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        client_ip = request.client.host if request.client else None

        machine_record = {
            "id": machine_id,
            "name": req.name,
            "hostname": req.hostname,
            "ip_address": client_ip,
            "api_key_hash": hash_api_key(api_key),
            "status": "offline",
            "registered_at": now,
            "last_seen": now,
            "tags": "[]",
        }
        await insert_machine(db, machine_record)
        machine = await fetch_machine(db, machine_id)
        return MachineRegisterResponse(
            machine_id=machine_id,
            api_key=api_key,
            machine=MachineResponse(**machine),
        )
    finally:
        await db.close()


@router.get("", response_model=list[MachineResponse])
async def list_machines():
    db = await _get_db(settings.DB_PATH)
    try:
        machines = await fetch_all_machines(db)
        return [MachineResponse(**m) for m in machines]
    finally:
        await db.close()


@router.get("/{machine_id}")
async def get_machine(machine_id: str):
    db = await _get_db(settings.DB_PATH)
    try:
        machine = await fetch_machine(db, machine_id)
        if not machine:
            raise HTTPException(status_code=404, detail="Machine not found")
        recent_metrics = await fetch_recent_metrics(db, machine_id, n=60)
        return {"machine": MachineResponse(**machine), "metrics": recent_metrics}
    finally:
        await db.close()


@router.delete("/{machine_id}")
async def deregister_machine(machine_id: str):
    db = await _get_db(settings.DB_PATH)
    try:
        machine = await fetch_machine(db, machine_id)
        if not machine:
            raise HTTPException(status_code=404, detail="Machine not found")
        await delete_machine(db, machine_id)
        return {"ok": True, "machine_id": machine_id}
    finally:
        await db.close()


@router.post("/{machine_id}/heartbeat")
async def heartbeat(machine_id: str, payload: HeartbeatPayload, request: Request):
    db = await _get_db(settings.DB_PATH)
    try:
        machine = await fetch_machine(db, machine_id)
        if not machine:
            raise HTTPException(status_code=404, detail="Machine not found")
        if not verify_api_key(payload.api_key, machine["api_key_hash"]):
            raise HTTPException(status_code=401, detail="Invalid API key")

        now = datetime.now(timezone.utc).isoformat()
        await update_machine_heartbeat(db, machine_id, now, "online")

        if payload.metrics:
            await upsert_metrics(db, machine_id, payload.metrics.model_dump(), now)

        # Broadcast update
        machines = await fetch_all_machines(db)
        await hub.broadcast("FLEET_UPDATE", {"machines": machines})
        return {"ok": True, "server_time": now}
    finally:
        await db.close()
