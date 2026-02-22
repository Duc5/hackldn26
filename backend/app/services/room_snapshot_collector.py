"""
app/services/room_snapshot_collector.py
---------------------------------------
Periodic background task that writes room-level summary snapshots to MongoDB.
Runs every ROOM_SNAPSHOT_INTERVAL seconds (default 4 hours).
"""

import asyncio
from datetime import datetime, timezone

from app.core.config import settings
from app.core.logging import get_logger
from app.core.rooms import ROOM_CONFIG
from app.db.repository import insert_many_room_snapshots
from app.services import room_logic

log = get_logger("spacesync.room_snapshot")


async def run_room_collector() -> None:
    log.info(
        "Room snapshot collector started — writing to MongoDB every %ds.",
        settings.room_snapshot_interval,
    )
    while True:
        await asyncio.sleep(settings.room_snapshot_interval)
        await _collect()


async def _collect() -> None:
    now = datetime.now(timezone.utc)
    docs: list[dict] = []

    for room_id in ROOM_CONFIG:
        summary = room_logic.compute_room_summary(room_id, include_desks=False)
        if not summary:
            continue
        docs.append({
            "room_id":        room_id,
            "status":         summary["status"],
            "avg_noise_db":   summary["avg_noise_db"],
            "avg_temp_c":     summary["avg_temp_c"],
            "occupancy_pct":  summary["occupancy_pct"],
            "total_desks":    summary["total_desks"],
            "occupied_desks": summary["occupied_desks"],
            "recorded_at":    now,
        })

    if not docs:
        log.debug("No rooms available — skipping room snapshot.")
        return

    inserted = await insert_many_room_snapshots(docs)
    log.info("Room snapshots written: %d room(s) at %s", inserted, now.isoformat())
