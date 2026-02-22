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
  6. Seed MongoDB history (one-time, if empty)
  7. Start MongoDB snapshot collectors (desks every 10 min, rooms every 4 hours)
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.db.mongo import connect_db, close_db
from app.services import device_registry, mock_jitter, serial_reader, state
from app.services.snapshot_collector import run_collector
from app.services.room_snapshot_collector import run_room_collector
from app.services.history_seed import seed_history_if_empty
from app.api import rooms, desks, devices, analytics, health, tables, simulation

setup_logging()
log = get_logger("spacesync.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────
    log.info("SpaceSync starting up…")

    # 1. MongoDB
    db_ready = False
    try:
        await connect_db()
        db_ready = True
    except Exception as exc:
        if settings.mongodb_required:
            log.error("MongoDB connection failed and is required: %s", exc)
            raise
        log.warning(
            "MongoDB connection failed: %s\n"
            "App will run with mock data only — no historical persistence.",
            exc,
        )

    # 2. Load device registry (DB → JSON fallback)
    await device_registry.load_registry()

    # 3. Seed mock desks
    state.seed_mock_desks()
    state.ensure_desk("desk_19", "room_c", is_mock=False)
    state.update_desk("desk_19", occupied=1, noise_db=38, temp_c=21.5, total_seats=6, is_mock=False)

    # 4. Serial threads
    serial_reader.start_all()

    # 5. Mock jitter
    mock_jitter.start()

    # 6. Seed historical data (one-time, if empty)
    if db_ready:
        await seed_history_if_empty()

    # 7. Snapshot collectors (asyncio tasks)
    collector_task = asyncio.create_task(run_collector()) if db_ready else None
    room_collector_task = asyncio.create_task(run_room_collector()) if db_ready else None
    log.info("All services started. API ready at http://localhost:8000")
    log.info("Interactive docs: http://localhost:8000/docs")

    yield   # ← app runs here

    # ── Shutdown ─────────────────────────────────────────────
    log.info("SpaceSync shutting down…")
    if collector_task:
        collector_task.cancel()
        try:
            await collector_task
        except asyncio.CancelledError:
            pass
    if room_collector_task:
        room_collector_task.cancel()
        try:
            await room_collector_task
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
        "Historical data is persisted to MongoDB every 10 minutes "
        "(room summaries every 4 hours)."
    ),
    version="3.0.0",
    lifespan=lifespan,
)

# CORS — allow React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
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
app.include_router(tables.router)
app.include_router(simulation.router)
