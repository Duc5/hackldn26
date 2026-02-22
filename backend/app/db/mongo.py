"""
app/db/mongo.py
────────────────
Async MongoDB connection via Motor.

Collections
───────────
  snapshots        — time-series desk readings (written every SNAPSHOT_INTERVAL)
  device_registry  — persistent hardware_id → desk mapping
  room_events      — room-level status change log (Busy/Loud transitions)

Usage
─────
    from app.db.mongo import get_db, Collections

    db = get_db()
    await db[Collections.SNAPSHOTS].insert_one(doc)
"""

import motor.motor_asyncio
from pymongo import ASCENDING, DESCENDING, IndexModel
from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("spacesync.db")

# Module-level client — created once at startup
_client: motor.motor_asyncio.AsyncIOMotorClient | None = None
_db:     motor.motor_asyncio.AsyncIOMotorDatabase | None = None


class Collections:
    SNAPSHOTS        = "snapshots"
    ROOM_SNAPSHOTS   = "room_snapshots"
    DEVICE_REGISTRY  = "device_registry"
    ROOM_EVENTS      = "room_events"


async def connect_db() -> None:
    """
    Open the MongoDB connection and ensure all indexes exist.
    Call once from FastAPI lifespan startup.
    """
    global _client, _db

    log.info("Connecting to MongoDB…")
    _client = motor.motor_asyncio.AsyncIOMotorClient(
        settings.mongodb_uri,
        serverSelectionTimeoutMS=5_000,
    )

    # Verify the connection is reachable
    await _client.admin.command("ping")
    log.info("MongoDB connected ✓")

    _db = _client[settings.mongodb_db_name]
    await _ensure_indexes()


async def close_db() -> None:
    """Close the MongoDB connection. Call from FastAPI lifespan shutdown."""
    global _client
    if _client:
        _client.close()
        log.info("MongoDB connection closed.")


def get_db() -> motor.motor_asyncio.AsyncIOMotorDatabase:
    """Return the active database handle. Raises if not yet connected."""
    if _db is None:
        raise RuntimeError("MongoDB not connected — call connect_db() first.")
    return _db


async def _ensure_indexes() -> None:
    """
    Create indexes if they don't already exist.
    Motor's create_indexes is idempotent — safe to call on every startup.
    """
    db = get_db()

    # snapshots — query by desk/room + time range
    await db[Collections.SNAPSHOTS].create_indexes([
        IndexModel([("assignment_id", ASCENDING), ("recorded_at", DESCENDING)]),
        IndexModel([("desk_id",    ASCENDING), ("recorded_at", DESCENDING)]),
        IndexModel([("room_id",    ASCENDING), ("recorded_at", DESCENDING)]),
        IndexModel([("recorded_at", DESCENDING)]),
        # TTL index — auto-delete snapshots older than 30 days (2_592_000 seconds)
        # Remove or increase this if you want longer retention.
        IndexModel([("recorded_at", ASCENDING)], expireAfterSeconds=2_592_000, name="ttl_30d"),
    ])


    # room_snapshots � time-series room aggregates
    await db[Collections.ROOM_SNAPSHOTS].create_indexes([
        IndexModel([('room_id', ASCENDING), ('recorded_at', DESCENDING)]),
        IndexModel([('recorded_at', DESCENDING)]),
        IndexModel([('recorded_at', ASCENDING)], expireAfterSeconds=2_592_000, name='room_ttl_30d'),
    ])
    # device_registry — hardware_id is unique
    await db[Collections.DEVICE_REGISTRY].create_indexes([
        IndexModel([("hardware_id", ASCENDING)], unique=True),
    ])

    # room_events — query by room + time
    await db[Collections.ROOM_EVENTS].create_indexes([
        IndexModel([("room_id",    ASCENDING), ("recorded_at", DESCENDING)]),
        IndexModel([("recorded_at", DESCENDING)]),
    ])

    log.info("MongoDB indexes verified ✓")
