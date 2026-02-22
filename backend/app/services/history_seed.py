"""
app/services/history_seed.py
----------------------------
Seed MongoDB with lightweight historical data for demo charts.
Runs once on startup if collections are empty.
"""

import math
import random
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.core.logging import get_logger
from app.core.rooms import ROOM_CONFIG, NOISE_LOUD_THRESHOLD, OCCUPANCY_BUSY_THRESHOLD
from app.db import repository
from app.services import state

log = get_logger("spacesync.history_seed")


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


async def seed_history_if_empty() -> None:
    if not settings.history_seed_enabled:
        return

    try:
        snap_count = await repository.count_snapshots()
        room_count = await repository.count_room_snapshots()
    except Exception as exc:
        log.warning("History seed skipped — DB not ready: %s", exc)
        return

    if snap_count == 0:
        await _seed_desk_snapshots()
    else:
        log.info("Desk snapshots already present (%d) — skipping seed.", snap_count)

    if room_count == 0:
        await _seed_room_snapshots()
    else:
        log.info("Room snapshots already present (%d) — skipping seed.", room_count)


async def _seed_desk_snapshots() -> None:
    desks = state.get_all_desks(strip_private=False)
    if not desks:
        log.info("No desks found — skipping desk snapshot seed.")
        return

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=settings.history_seed_days)
    step = timedelta(minutes=settings.history_seed_desk_interval_minutes)
    total_steps = int((now - start) / step)

    rngs: dict[str, random.Random] = {
        d["desk_id"]: random.Random(hash(d["desk_id"]) & 0xFFFFFFFF)
        for d in desks
    }

    baselines: dict[str, dict] = {}
    for d in desks:
        base_noise = float(d.get("_base_noise", d.get("noise_db", 40)))
        base_temp = float(d.get("_base_temp", d.get("temp_c", 21.0)))
        base_occ = 0.6 if d.get("occupied") else 0.35
        baselines[d["desk_id"]] = {
            "noise": base_noise,
            "temp": base_temp,
            "occ": base_occ,
        }

    batch: list[dict] = []
    batch_size = 1000

    for i in range(total_steps + 1):
        ts = start + i * step
        day_phase = math.sin((ts.timestamp() / 86_400) * 2 * math.pi)

        for d in desks:
            assignment_id = d.get("assignment_id")
            if not assignment_id:
                continue
            rng = rngs[d["desk_id"]]
            base = baselines[d["desk_id"]]

            noise = base["noise"] + day_phase * 4 + rng.randint(-6, 6)
            temp = base["temp"] + day_phase * 0.6 + rng.uniform(-0.6, 0.6)
            occ_prob = _clamp(base["occ"] + rng.uniform(-0.2, 0.2), 0.05, 0.95)
            occupied = 1 if rng.random() < occ_prob else 0

            batch.append({
                "desk_id":      d["desk_id"],
                "assignment_id": assignment_id,
                "room_id":      d["room_id"],
                "is_mock":      d["is_mock"],
                "occupied":     occupied,
                "noise_db":     int(_clamp(noise, 25, 90)),
                "temp_c":       round(_clamp(temp, 16.0, 30.0), 1),
                "recorded_at":  ts,
            })

        if len(batch) >= batch_size:
            await repository.insert_many_snapshots(batch)
            batch.clear()

    if batch:
        await repository.insert_many_snapshots(batch)

    log.info(
        "Seeded desk snapshots — %d steps over %d day(s).",
        total_steps + 1,
        settings.history_seed_days,
    )


async def _seed_room_snapshots() -> None:
    desks = state.get_all_desks(strip_private=False)
    if not desks:
        log.info("No desks found — skipping room snapshot seed.")
        return

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=settings.history_seed_days)
    step = timedelta(hours=settings.history_seed_room_interval_hours)
    total_steps = int((now - start) / step)

    desks_by_room: dict[str, list[dict]] = {}
    for d in desks:
        desks_by_room.setdefault(d["room_id"], []).append(d)

    rngs = {room_id: random.Random(hash(room_id) & 0xFFFFFFFF) for room_id in ROOM_CONFIG}

    batch: list[dict] = []
    batch_size = 500

    for i in range(total_steps + 1):
        ts = start + i * step
        day_phase = math.sin((ts.timestamp() / 86_400) * 2 * math.pi)

        for room_id in ROOM_CONFIG:
            room_desks = desks_by_room.get(room_id, [])
            if not room_desks:
                continue

            base_noise = sum(d.get("noise_db", 40) for d in room_desks) / len(room_desks)
            base_temp = sum(d.get("temp_c", 21.0) for d in room_desks) / len(room_desks)
            base_occ = sum(1 for d in room_desks if d.get("occupied")) / len(room_desks)

            rng = rngs[room_id]
            avg_noise = base_noise + day_phase * 4 + rng.uniform(-4, 4)
            avg_temp = base_temp + day_phase * 0.5 + rng.uniform(-0.8, 0.8)
            occ_pct = _clamp(base_occ + rng.uniform(-0.2, 0.2), 0.02, 0.98)

            total_desks = len(room_desks)
            occupied_desks = int(round(occ_pct * total_desks))

            statuses = []
            if occ_pct >= OCCUPANCY_BUSY_THRESHOLD:
                statuses.append("Busy")
            if avg_noise >= NOISE_LOUD_THRESHOLD:
                statuses.append("Loud")
            status = " & ".join(statuses) if statuses else "Available"

            batch.append({
                "room_id":        room_id,
                "status":         status,
                "avg_noise_db":   round(_clamp(avg_noise, 25, 90), 1),
                "avg_temp_c":     round(_clamp(avg_temp, 16.0, 30.0), 1),
                "occupancy_pct":  round(occ_pct, 2),
                "total_desks":    total_desks,
                "occupied_desks": occupied_desks,
                "recorded_at":    ts,
            })

        if len(batch) >= batch_size:
            await repository.insert_many_room_snapshots(batch)
            batch.clear()

    if batch:
        await repository.insert_many_room_snapshots(batch)

    log.info(
        "Seeded room snapshots — %d steps over %d day(s).",
        total_steps + 1,
        settings.history_seed_days,
    )
