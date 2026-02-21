"""
SpaceSync — main.py
────────────────────
FastAPI application entry point.

Run:
    uvicorn main:app --reload --port 8000

Startup sequence
────────────────
  1. Connect to MongoDB (with fallback — app still runs without DB)
  2. Load device registry from DB / devices.json
  3. Seed mock desks to fill room capacity
  4. Start serial listener threads for all registered Arduinos
  5. Start mock jitter thread
  6. Start MongoDB snapshot collector (asyncio task, runs every 60s)
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.logging import setup_logging, get_logger
from app.db.mongo import connect_db, close_db
from app.services import device_registry, mock_jitter, serial_reader, state
from app.services.snapshot_collector import run_collector
from app.api import rooms, desks, devices, analytics, health

setup_logging()
log = get_logger("spacesync.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────
    log.info("SpaceSync starting up…")

    # 1. MongoDB
    try:
        await connect_db()
    except Exception as exc:
        log.warning(
            "MongoDB connection failed: %s\n"
            "App will run with mock data only — no historical persistence.",
            exc,
        )

    # 2. Load device registry (DB → JSON fallback)
    await device_registry.load_registry()

    # 3. Seed mock desks
    state.seed_mock_desks()

    # 4. Serial threads
    serial_reader.start_all()

    # 5. Mock jitter
    mock_jitter.start()

    # 6. Snapshot collector (asyncio task)
    collector_task = asyncio.create_task(run_collector())
    log.info("All services started. API ready at http://localhost:8000")
    log.info("Interactive docs: http://localhost:8000/docs")

    yield   # ← app runs here

    # ── Shutdown ─────────────────────────────────────────────
    log.info("SpaceSync shutting down…")
    collector_task.cancel()
    try:
        await collector_task
    except asyncio.CancelledError:
        pass
    await close_db()
    log.info("Shutdown complete.")


# ─────────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="SpaceSync API",
    description=(
        "Real-time library desk occupancy, noise & temperature.\n\n"
        "Live data is served from in-memory state (updated by Arduino serial or mock jitter).\n"
        "Historical data is persisted to MongoDB every 60 seconds."
    ),
    version="3.0.0",
    lifespan=lifespan,
)

# CORS — allow React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(rooms.router)
app.include_router(desks.router)
app.include_router(devices.router)
app.include_router(analytics.router)
app.include_router(health.router)
