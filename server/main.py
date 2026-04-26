import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from server.config import settings
from server.database import init_db
from server.services.openclaw import openclaw
from server.services.heartbeat import heartbeat_loop
from server.routers import machines, commands, dashboard, icc

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("metatron")

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("METATRON-FLEET Command Center starting...")
    await init_db()
    logger.info(f"Database initialized at {settings.DB_PATH}")
    await openclaw.startup(settings.DB_PATH)

    heartbeat_task = asyncio.create_task(heartbeat_loop(settings.DB_PATH))
    logger.info("Heartbeat monitor active.")
    logger.info("OpenClaw Engine: ACTIVE")
    logger.info(f"Dashboard: http://{settings.SERVER_HOST}:{settings.SERVER_PORT}/")

    yield

    # Shutdown
    logger.info("Shutting down METATRON-FLEET...")
    heartbeat_task.cancel()
    try:
        await heartbeat_task
    except asyncio.CancelledError:
        pass
    await openclaw.shutdown()
    logger.info("Shutdown complete.")


app = FastAPI(
    title="METATRON-FLEET Command Center",
    description="Fleet management powered by the OpenClaw Engine",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(dashboard.router)
app.include_router(machines.router)
app.include_router(commands.router)
app.include_router(icc.router)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


if __name__ == "__main__":
    uvicorn.run(
        "server.main:app",
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        reload=False,
    )
