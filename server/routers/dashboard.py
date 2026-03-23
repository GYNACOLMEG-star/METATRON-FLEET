import asyncio
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from server.ws.hub import hub

router = APIRouter(tags=["dashboard"])

STATIC_DIR = Path(__file__).parent.parent / "static"


@router.get("/")
async def dashboard():
    return FileResponse(STATIC_DIR / "index.html")


@router.websocket("/ws/fleet")
async def fleet_websocket(ws: WebSocket):
    await hub.connect(ws)
    try:
        while True:
            # Keep connection alive; clients send pings
            await asyncio.wait_for(ws.receive_text(), timeout=30)
    except (WebSocketDisconnect, asyncio.TimeoutError, Exception):
        hub.disconnect(ws)
