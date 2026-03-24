"""
Inter-Claude Communication (ICC) Router
Allows Claude agents to send, poll, and reply to messages via the METATRON-FLEET server.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

import aiosqlite
from fastapi import APIRouter, HTTPException

from server.auth import verify_api_key
from server.config import settings
from server.database import (
    fetch_machine,
    fetch_icc_message,
    fetch_pending_icc_messages,
    fetch_icc_thread,
    fetch_icc_threads_for_agent,
    insert_icc_message,
    update_icc_message_delivered,
)
from server.models import (
    ICCSendRequest,
    ICCMessageResponse,
    ICCReplyPayload,
    ICCPollResponse,
)
from server.ws.hub import hub

router = APIRouter(prefix="/api/icc", tags=["icc"])


async def _get_db():
    db = await aiosqlite.connect(settings.DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


def _thread_id(a: str, b: str) -> str:
    """Deterministic thread ID from two agent IDs."""
    return "::".join(sorted([a, b]))


@router.post("/send", response_model=ICCMessageResponse)
async def send_message(req: ICCSendRequest):
    """Send a message from one Claude agent to another."""
    db = await _get_db()
    try:
        sender = await fetch_machine(db, req.sender_id)
        if not sender:
            raise HTTPException(status_code=404, detail="Sender not found")
        if not verify_api_key(req.api_key, sender["api_key_hash"]):
            raise HTTPException(status_code=401, detail="Invalid API key")

        recipient = await fetch_machine(db, req.recipient_id)
        if not recipient:
            raise HTTPException(status_code=404, detail="Recipient not found")

        thread_id = req.thread_id or _thread_id(req.sender_id, req.recipient_id)
        now = datetime.now(timezone.utc).isoformat()
        msg = {
            "id": str(uuid.uuid4()),
            "thread_id": thread_id,
            "sender_id": req.sender_id,
            "recipient_id": req.recipient_id,
            "role": "user",
            "content": req.content,
            "status": "pending",
            "created_at": now,
        }
        await insert_icc_message(db, msg)

        row = await fetch_icc_message(db, msg["id"])
        await hub.broadcast("ICC_MESSAGE", {"message": row})
        return ICCMessageResponse(**row)
    finally:
        await db.close()


@router.get("/pending/{agent_id}", response_model=ICCPollResponse)
async def poll_messages(agent_id: str, api_key: str):
    """Agent polls for messages addressed to it."""
    db = await _get_db()
    try:
        machine = await fetch_machine(db, agent_id)
        if not machine:
            raise HTTPException(status_code=404, detail="Agent not found")
        if not verify_api_key(api_key, machine["api_key_hash"]):
            raise HTTPException(status_code=401, detail="Invalid API key")

        messages = await fetch_pending_icc_messages(db, agent_id, limit=10)
        now = datetime.now(timezone.utc).isoformat()
        for msg in messages:
            await update_icc_message_delivered(db, msg["id"], now)

        return ICCPollResponse(messages=[ICCMessageResponse(**m) for m in messages])
    finally:
        await db.close()


@router.post("/messages/{message_id}/reply", response_model=ICCMessageResponse)
async def reply_to_message(message_id: str, payload: ICCReplyPayload):
    """Post a reply to a specific ICC message. Reply is routed back to the original sender."""
    db = await _get_db()
    try:
        original = await fetch_icc_message(db, message_id)
        if not original:
            raise HTTPException(status_code=404, detail="Message not found")

        machine = await fetch_machine(db, payload.agent_id)
        if not machine:
            raise HTTPException(status_code=404, detail="Agent not found")
        if not verify_api_key(payload.api_key, machine["api_key_hash"]):
            raise HTTPException(status_code=401, detail="Invalid API key")
        if original["recipient_id"] != payload.agent_id:
            raise HTTPException(status_code=403, detail="Not the intended recipient")

        now = datetime.now(timezone.utc).isoformat()
        reply = {
            "id": str(uuid.uuid4()),
            "thread_id": original["thread_id"],
            "sender_id": payload.agent_id,
            "recipient_id": original["sender_id"],
            "role": "assistant",
            "content": payload.content,
            "status": "pending",
            "created_at": now,
        }
        await insert_icc_message(db, reply)

        row = await fetch_icc_message(db, reply["id"])
        await hub.broadcast("ICC_REPLY", {"message": row})
        return ICCMessageResponse(**row)
    finally:
        await db.close()


@router.get("/thread/{thread_id}", response_model=list[ICCMessageResponse])
async def get_thread(thread_id: str, agent_id: str, api_key: str, limit: int = 50):
    """Fetch full conversation history for a thread."""
    db = await _get_db()
    try:
        machine = await fetch_machine(db, agent_id)
        if not machine:
            raise HTTPException(status_code=404, detail="Agent not found")
        if not verify_api_key(api_key, machine["api_key_hash"]):
            raise HTTPException(status_code=401, detail="Invalid API key")

        messages = await fetch_icc_thread(db, thread_id, limit=limit)
        return [ICCMessageResponse(**m) for m in messages]
    finally:
        await db.close()


@router.get("/threads/{agent_id}")
async def list_threads(agent_id: str, api_key: str):
    """List all thread IDs involving this agent."""
    db = await _get_db()
    try:
        machine = await fetch_machine(db, agent_id)
        if not machine:
            raise HTTPException(status_code=404, detail="Agent not found")
        if not verify_api_key(api_key, machine["api_key_hash"]):
            raise HTTPException(status_code=401, detail="Invalid API key")

        threads = await fetch_icc_threads_for_agent(db, agent_id)
        return {"threads": threads}
    finally:
        await db.close()
