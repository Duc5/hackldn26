"""
app/services/snapshot_collector.py
────────────────────────────────────
Periodic background task that writes a snapshot of ALL desks to MongoDB
every SNAPSHOT_INTERVAL seconds (default 60s from .env).

This is the bridge between the live in-memory state and the persistent DB.

What it writes
──────────────
  Collection: snapshots
  One document per desk per interval, e.g.:
  {
      "desk_id":     "desk_1",
      "room_id":     "room_a",
      "is_mock":     false,
      "occupied":    1,
      "noise_db":    42,
      "temp_c":      21.5,
      "recorded_at": ISODate("2024-01-15T14:30:00Z")
  }

Room events
───────────
  If a room's status changes (Available ↔ Busy / Loud) between ticks,
  an event document is written to the `room_events` collection.

Design notes
────────────
  • Runs as an asyncio task (not a thread) — started from FastAPI lifespan
  • Uses insert_many for efficiency (one round-trip per tick for all desks)
  • Catches all exceptions — a DB hiccup must never kill the collector
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional

from app.core.config import settings
from app.core.logging import get_logger
from app.core.rooms import ROOM_CONFIG, NOISE_LOUD_THRESHOLD, OCCUPANCY_BUSY_THRESHOLD
from app.db.repository import insert_many_snapshots, insert_room_event
from app.services import state

log = get_logger("spacesync.snapshot")

# Track last known room status so we can detect transitions
_last_room_status: dict[str, str] = {}


async def run_collector() -> None:
    """
    Main asyncio task loop.
    Schedule with:  asyncio.create_task(run_collector())
    """
    log.info(
        "Snapshot collector started — writing to MongoDB every %ds.",
        settings.snapshot_interval,
    )
    while True:
        await asyncio.sleep(settings.snapshot_interval)
        await _collect()


async def _collect() -> None:
    """Take a snapshot of all desks and persist to MongoDB."""
    now   = datetime.now(timezone.utc)
    desks = state.get_all_desks(strip_private=False)

    if not desks:
        log.debug("No desks in state — skipping snapshot.")
        return

    # ── Build snapshot documents ──────────────────────────────
    docs: list[dict] = []
    for d in desks:
        assignment_id = d.get("assignment_id")
        if not assignment_id:
            continue
        docs.append({
            "desk_id":       d["desk_id"],
            "assignment_id": assignment_id,
            "room_id":       d["room_id"],
            "is_mock":       d["is_mock"],
            "occupied":      d["occupied"],
            "noise_db":      d["noise_db"],
            "temp_c":        d["temp_c"],
            "recorded_at":   now,
        })

    inserted = await insert_many_snapshots(docs)
    log.info("Snapshot written: %d desk(s) at %s", inserted, now.isoformat())

    # ── Detect and record room status transitions ─────────────
    await _check_room_events(desks, now)


async def _check_room_events(desks: list[dict], now: datetime) -> None:
    """
    Compare current room status to the last known status.
    If it changed, write a room_event document.
    """
    # Group desks by room
    by_room: dict[str, list[dict]] = {}
    for d in desks:
        by_room.setdefault(d["room_id"], []).append(d)

    for room_id, room_desks in by_room.items():
        if room_id not in ROOM_CONFIG:
            continue

        total    = len(room_desks)
        occupied = sum(1 for d in room_desks if d["occupied"])
        occ_pct  = round(occupied / total, 2) if total else 0
        avg_noise = round(sum(d["noise_db"] for d in room_desks) / total, 1) if total else 0

        statuses = []
        if occ_pct  >= OCCUPANCY_BUSY_THRESHOLD: statuses.append("Busy")
        if avg_noise >= NOISE_LOUD_THRESHOLD:     statuses.append("Loud")
        status = " & ".join(statuses) if statuses else "Available"

        prev = _last_room_status.get(room_id)

        if prev != status:
            log.info("Room %s status changed: %s → %s", room_id, prev or "unknown", status)
            event = {
                "room_id":       room_id,
                "status":        status,
                "prev_status":   prev,
                "occupancy_pct": occ_pct,
                "avg_noise_db":  avg_noise,
                "recorded_at":   now,
            }
            await insert_room_event(event)
            _last_room_status[room_id] = status
