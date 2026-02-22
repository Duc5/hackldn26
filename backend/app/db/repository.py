"""
app/db/repository.py
─────────────────────
All MongoDB read / write operations.

This is the ONLY layer that talks to the database.
Services call these functions — routes never touch Motor directly.

Functions are grouped by collection:

  Snapshots
    insert_snapshot(doc)
    insert_many_snapshots(docs)
    get_desk_snapshots(assignment_id, limit, since)
    get_room_snapshots(assignment_ids, limit, since)
    get_latest_snapshot_per_desk()

  Device Registry
    upsert_device(info)
    get_all_devices()
    get_device(hardware_id)
    delete_device(hardware_id)

  Room Events
    insert_room_event(event)
    get_room_events(room_id, limit)
"""

from datetime import datetime, timezone
from typing import Optional

from pymongo import DESCENDING, ReplaceOne

from app.core.logging import get_logger
from app.db.mongo import Collections, get_db

log = get_logger("spacesync.repository")


# ─────────────────────────────────────────────────────────────
# Snapshots
# ─────────────────────────────────────────────────────────────

async def insert_snapshot(doc: dict) -> None:
    """
    Write a single desk snapshot to MongoDB.
    `doc` should match the SnapshotDoc shape (see models/schemas.py).
    """
    try:
        db = get_db()
        await db[Collections.SNAPSHOTS].insert_one(doc)
    except Exception as exc:
        log.error("insert_snapshot failed: %s", exc)


async def insert_many_snapshots(docs: list[dict]) -> int:
    """
    Bulk-insert a list of desk snapshots.
    Returns the number of documents inserted (0 on error).
    Used by the snapshot collector to write all desks in one round-trip.
    """
    if not docs:
        return 0
    try:
        db     = get_db()
        result = await db[Collections.SNAPSHOTS].insert_many(docs, ordered=False)
        return len(result.inserted_ids)
    except Exception as exc:
        log.error("insert_many_snapshots failed: %s", exc)
        return 0


async def get_desk_snapshots(
    assignment_id: str,
    limit:   int = 100,
    since:   Optional[datetime] = None,
) -> list[dict]:
    """
    Return up to `limit` snapshots for a desk assignment, newest first.
    Optionally filter to only readings after `since` (UTC datetime).
    """
    try:
        db    = get_db()
        query: dict = {"assignment_id": assignment_id}
        if since:
            query["recorded_at"] = {"$gte": since}
        cursor = (
            db[Collections.SNAPSHOTS]
            .find(query, {"_id": 0})
            .sort("recorded_at", DESCENDING)
            .limit(limit)
        )
        return await cursor.to_list(length=limit)
    except Exception as exc:
        log.error("get_desk_snapshots failed: %s", exc)
        return []


async def get_room_snapshots(
    assignment_ids: list[str],
    limit:   int = 500,
    since:   Optional[datetime] = None,
) -> list[dict]:
    """
    Return up to `limit` snapshots for a set of desk assignments, newest first.
    """
    try:
        db    = get_db()
        if not assignment_ids:
            return []
        query: dict = {"assignment_id": {"$in": assignment_ids}}
        if since:
            query["recorded_at"] = {"$gte": since}
        cursor = (
            db[Collections.SNAPSHOTS]
            .find(query, {"_id": 0})
            .sort("recorded_at", DESCENDING)
            .limit(limit)
        )
        return await cursor.to_list(length=limit)
    except Exception as exc:
        log.error("get_room_snapshots failed: %s", exc)
        return []


async def get_latest_snapshot_per_desk() -> list[dict]:
    """
    Return the most recent snapshot document for every desk.
    Uses an aggregation pipeline — one DB round-trip for all desks.
    """
    try:
        db = get_db()
        pipeline = [
            {"$sort":  {"recorded_at": DESCENDING}},
            {"$group": {
                "_id":        "$assignment_id",
                "desk_id":    {"$first": "$desk_id"},
                "assignment_id": {"$first": "$assignment_id"},
                "room_id":    {"$first": "$room_id"},
                "is_mock":    {"$first": "$is_mock"},
                "occupied":   {"$first": "$occupied"},
                "noise_db":   {"$first": "$noise_db"},
                "temp_c":     {"$first": "$temp_c"},
                "recorded_at":{"$first": "$recorded_at"},
            }},
            {"$project": {"_id": 0}},
        ]
        cursor = db[Collections.SNAPSHOTS].aggregate(pipeline)
        return await cursor.to_list(length=None)
    except Exception as exc:
        log.error("get_latest_snapshot_per_desk failed: %s", exc)
        return []


async def get_desk_aggregates(
    assignment_id: str,
    since:   Optional[datetime] = None,
) -> dict:
    """
    Return avg/min/max for noise_db, temp_c and occupancy for a desk.
    Computed entirely in MongoDB — no Python-side number crunching.
    """
    try:
        db    = get_db()
        match: dict = {"assignment_id": assignment_id}
        if since:
            match["recorded_at"] = {"$gte": since}
        pipeline = [
            {"$match": match},
            {"$group": {
                "_id":          "$desk_id",
                "avg_noise":    {"$avg": "$noise_db"},
                "max_noise":    {"$max": "$noise_db"},
                "min_noise":    {"$min": "$noise_db"},
                "avg_temp":     {"$avg": "$temp_c"},
                "max_temp":     {"$max": "$temp_c"},
                "min_temp":     {"$min": "$temp_c"},
                "avg_occupied": {"$avg": "$occupied"},
                "count":        {"$sum": 1},
            }},
            {"$project": {"_id": 0}},
        ]
        results = await db[Collections.SNAPSHOTS].aggregate(pipeline).to_list(length=1)
        return results[0] if results else {}
    except Exception as exc:
        log.error("get_desk_aggregates failed: %s", exc)
        return {}


async def get_room_aggregates(
    assignment_ids: list[str],
    since:   Optional[datetime] = None,
) -> dict:
    """
    Return avg noise, temp and occupancy for a set of desk assignments.
    """
    try:
        db    = get_db()
        if not assignment_ids:
            return {}
        match: dict = {"assignment_id": {"$in": assignment_ids}}
        if since:
            match["recorded_at"] = {"$gte": since}
        pipeline = [
            {"$match": match},
            {"$group": {
                "_id":          "room",
                "avg_noise":    {"$avg": "$noise_db"},
                "max_noise":    {"$max": "$noise_db"},
                "avg_temp":     {"$avg": "$temp_c"},
                "avg_occupied": {"$avg": "$occupied"},
                "count":        {"$sum": 1},
            }},
            {"$project": {"_id": 0}},
        ]
        results = await db[Collections.SNAPSHOTS].aggregate(pipeline).to_list(length=1)
        return results[0] if results else {}
    except Exception as exc:
        log.error("get_room_aggregates failed: %s", exc)
        return {}


# ─────────────────────────────────────────────────────────────

async def insert_many_room_snapshots(docs: list[dict]) -> int:
    """Bulk-insert room summary snapshots."""
    if not docs:
        return 0
    try:
        db     = get_db()
        result = await db[Collections.ROOM_SNAPSHOTS].insert_many(docs, ordered=False)
        return len(result.inserted_ids)
    except Exception as exc:
        log.error("insert_many_room_snapshots failed: %s", exc)
        return 0


async def get_room_snapshot_series(
    room_id: str,
    limit:   int = 500,
    since:   Optional[datetime] = None,
) -> list[dict]:
    """Return time-series room snapshots, newest first."""
    try:
        db    = get_db()
        query: dict = {"room_id": room_id}
        if since:
            query["recorded_at"] = {"$gte": since}
        cursor = (
            db[Collections.ROOM_SNAPSHOTS]
            .find(query, {"_id": 0})
            .sort("recorded_at", DESCENDING)
            .limit(limit)
        )
        return await cursor.to_list(length=limit)
    except Exception as exc:
        log.error("get_room_snapshot_series failed: %s", exc)
        return []


async def count_snapshots() -> int:
    """Return total snapshot document count."""
    try:
        db = get_db()
        return await db[Collections.SNAPSHOTS].count_documents({})
    except Exception as exc:
        log.error("count_snapshots failed: %s", exc)
        return 0


async def count_room_snapshots() -> int:
    """Return total room snapshot document count."""
    try:
        db = get_db()
        return await db[Collections.ROOM_SNAPSHOTS].count_documents({})
    except Exception as exc:
        log.error("count_room_snapshots failed: %s", exc)
        return 0

# Device Registry
# ─────────────────────────────────────────────────────────────

async def upsert_device(info: dict) -> None:
    """
    Insert or update a device registry document.
    `info` must contain at minimum: hardware_id, desk_id, room_id.
    Uses replace-with-upsert so the full document is always fresh.
    """
    try:
        db = get_db()
        info["updated_at"] = datetime.now(timezone.utc)
        await db[Collections.DEVICE_REGISTRY].replace_one(
            {"hardware_id": info["hardware_id"]},
            info,
            upsert=True,
        )
    except Exception as exc:
        log.error("upsert_device failed: %s", exc)


async def upsert_many_devices(infos: list[dict]) -> None:
    """Bulk upsert multiple device documents."""
    if not infos:
        return
    try:
        db  = get_db()
        now = datetime.now(timezone.utc)
        ops = [
            ReplaceOne(
                {"hardware_id": info["hardware_id"]},
                {**info, "updated_at": now},
                upsert=True,
            )
            for info in infos
        ]
        await db[Collections.DEVICE_REGISTRY].bulk_write(ops, ordered=False)
    except Exception as exc:
        log.error("upsert_many_devices failed: %s", exc)


async def get_all_devices() -> list[dict]:
    """Return all documents from the device_registry collection."""
    try:
        db     = get_db()
        cursor = db[Collections.DEVICE_REGISTRY].find({}, {"_id": 0})
        return await cursor.to_list(length=None)
    except Exception as exc:
        log.error("get_all_devices failed: %s", exc)
        return []


async def get_device(hardware_id: str) -> Optional[dict]:
    """Return a single device document, or None if not found."""
    try:
        db  = get_db()
        doc = await db[Collections.DEVICE_REGISTRY].find_one(
            {"hardware_id": hardware_id}, {"_id": 0}
        )
        return doc
    except Exception as exc:
        log.error("get_device failed: %s", exc)
        return None


async def delete_device(hardware_id: str) -> bool:
    """
    Delete a device from the registry.
    Returns True if a document was deleted, False if not found.
    """
    try:
        db     = get_db()
        result = await db[Collections.DEVICE_REGISTRY].delete_one(
            {"hardware_id": hardware_id}
        )
        return result.deleted_count > 0
    except Exception as exc:
        log.error("delete_device failed: %s", exc)
        return False


# ─────────────────────────────────────────────────────────────
# Room Events
# ─────────────────────────────────────────────────────────────

async def insert_room_event(event: dict) -> None:
    """
    Record a room status transition event.

    Expected shape:
        {
            "room_id":     "room_a",
            "status":      "Busy",
            "prev_status": "Available",
            "occupancy_pct": 0.83,
            "avg_noise_db":  58.2,
            "recorded_at": datetime (UTC),
        }
    """
    try:
        db = get_db()
        await db[Collections.ROOM_EVENTS].insert_one(event)
    except Exception as exc:
        log.error("insert_room_event failed: %s", exc)


async def get_room_events(room_id: str, limit: int = 50) -> list[dict]:
    """Return the most recent status-change events for a room."""
    try:
        db     = get_db()
        cursor = (
            db[Collections.ROOM_EVENTS]
            .find({"room_id": room_id}, {"_id": 0})
            .sort("recorded_at", DESCENDING)
            .limit(limit)
        )
        return await cursor.to_list(length=limit)
    except Exception as exc:
        log.error("get_room_events failed: %s", exc)
        return []
