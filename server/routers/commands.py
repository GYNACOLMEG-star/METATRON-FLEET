import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException

from server.auth import verify_api_key
from server.database import (
    connect_db,
    utcnow,
    fetch_command,
    fetch_commands,
    fetch_machine,
    fetch_pending_commands,
    insert_command,
    update_command_result,
    update_command_sent,
)
from server.models import CommandDispatchRequest, CommandResponse, CommandResultPayload
from server.services.openclaw import openclaw
from server.ws.hub import hub

MAX_OUTPUT = 65536  # match agent/executor.py truncation limit

router = APIRouter(prefix="/api/commands", tags=["commands"])


@router.post("/dispatch", response_model=CommandResponse)
async def dispatch_command(req: CommandDispatchRequest):
    db = await connect_db()
    try:
        machine = await fetch_machine(db, req.machine_id)
        if not machine:
            raise HTTPException(status_code=404, detail="Machine not found")

        command_id = str(uuid.uuid4())
        now = utcnow()
        cmd = {
            "id": command_id,
            "machine_id": req.machine_id,
            "command_text": req.command_text,
            "status": "pending",
            "created_at": now,
            "requested_by": req.requested_by,
            "timeout_seconds": req.timeout_seconds,
        }
        await insert_command(db, cmd)
        await openclaw.dispatch(req.machine_id, command_id)

        command = await fetch_command(db, command_id)
        await hub.broadcast("COMMAND_UPDATE", {"command": command})
        return CommandResponse(**command)
    finally:
        await db.close()


@router.get("", response_model=list[CommandResponse])
async def list_commands(machine_id: Optional[str] = None, status: Optional[str] = None, limit: int = 50):
    db = await connect_db()
    try:
        commands = await fetch_commands(db, machine_id=machine_id, status=status, limit=limit)
        return [CommandResponse(**c) for c in commands]
    finally:
        await db.close()


@router.get("/{command_id}", response_model=CommandResponse)
async def get_command(command_id: str):
    db = await connect_db()
    try:
        command = await fetch_command(db, command_id)
        if not command:
            raise HTTPException(status_code=404, detail="Command not found")
        return CommandResponse(**command)
    finally:
        await db.close()


@router.post("/{command_id}/result")
async def command_result(command_id: str, payload: CommandResultPayload):
    db = await connect_db()
    try:
        command = await fetch_command(db, command_id)
        if not command:
            raise HTTPException(status_code=404, detail="Command not found")

        machine = await fetch_machine(db, payload.machine_id)
        if not machine or machine["id"] != command["machine_id"]:
            raise HTTPException(status_code=403, detail="Forbidden")
        if not verify_api_key(payload.api_key, machine["api_key_hash"]):
            raise HTTPException(status_code=401, detail="Invalid API key")

        now = utcnow()
        status = "completed" if payload.exit_code == 0 else "failed"
        result = {
            "status": status,
            "completed_at": now,
            "exit_code": payload.exit_code,
            "stdout": payload.stdout[:MAX_OUTPUT],
            "stderr": payload.stderr[:MAX_OUTPUT],
        }
        await update_command_result(db, command_id, result)
        updated = await fetch_command(db, command_id)
        await hub.broadcast("COMMAND_RESULT", {"command": updated})
        return {"ok": True}
    finally:
        await db.close()


# Agent polls this endpoint for pending commands
@router.get("/pending/{machine_id}")
async def pending_commands(machine_id: str, api_key: str):
    db = await connect_db()
    try:
        machine = await fetch_machine(db, machine_id)
        if not machine:
            raise HTTPException(status_code=404, detail="Machine not found")
        if not verify_api_key(api_key, machine["api_key_hash"]):
            raise HTTPException(status_code=401, detail="Invalid API key")

        # Drain queue
        command_ids = await openclaw.poll(machine_id, limit=5)

        # Also check DB for any not in memory queue (e.g. added while server was down)
        db_pending = await fetch_pending_commands(db, machine_id, limit=5)
        db_ids = {c["id"] for c in db_pending}
        all_ids = list(dict.fromkeys(command_ids + [cid for cid in db_ids if cid not in command_ids]))

        now = utcnow()
        results = []
        for cid in all_ids[:5]:
            cmd = await fetch_command(db, cid)
            if cmd and cmd["status"] == "pending":
                await update_command_sent(db, cid, now)
                results.append(cmd)

        return {"commands": results}
    finally:
        await db.close()
