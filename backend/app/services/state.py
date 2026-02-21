"""
app/services/state.py
──────────────────────
The single source of truth for LIVE desk data.

Everything that reads or writes current desk values goes through here.
MongoDB is written to separately (snapshot collector) — this module is
purely in-memory and thread-safe.

Exports
───────
  DeskState             — the dict shape held per desk
  desk_store            — dict[desk_id, DeskState]
  desk_history          — dict[desk_id, deque[reading]]
  store_lock            — threading.Lock covering desk_store
  get_desk(id)          → dict | None
  get_desks_for_room(id) → list[dict]
  get_all_desks()       → list[dict]
  update_desk(id, **kw) → None
  ensure_desk(id, room_id, is_mock) → None
  next_auto_desk_id()   → str
  next_available_room() → str | None
  seed_mock_desks()     → None
  record_history(id, reading) → None
"""

import random
import threading
from collections import defaultdict, deque
from datetime import datetime
from typing import Optional

from app.core.config import settings
from app.core.logging import get_logger
from app.core.rooms import ROOM_CONFIG

log = get_logger("spacesync.state")

# ─── Core stores ─────────────────────────────────────────────
desk_store:   dict[str, dict]   = {}
desk_history: dict[str, deque]  = defaultdict(
    lambda: deque(maxlen=settings.history_maxlen)
)
store_lock = threading.Lock()


# ─── Desk CRUD ────────────────────────────────────────────────

def get_desk(desk_id: str) -> Optional[dict]:
    with store_lock:
        d = desk_store.get(desk_id)
        return dict(d) if d else None


def get_desks_for_room(room_id: str) -> list[dict]:
    with store_lock:
        return [
            {k: v for k, v in d.items() if not k.startswith("_")}
            for d in desk_store.values()
            if d["room_id"] == room_id
        ]


def get_all_desks(strip_private: bool = True) -> list[dict]:
    with store_lock:
        if strip_private:
            return [
                {k: v for k, v in d.items() if not k.startswith("_")}
                for d in desk_store.values()
            ]
        return [dict(d) for d in desk_store.values()]


def ensure_desk(desk_id: str, room_id: str, is_mock: bool) -> None:
    """
    Create a desk entry if it doesn't exist.
    If it already exists, update room_id and is_mock (handles re-registration).
    """
    with store_lock:
        if desk_id in desk_store:
            desk_store[desk_id]["room_id"] = room_id
            desk_store[desk_id]["is_mock"] = is_mock
            return
        desk_store[desk_id] = {
            "desk_id":      desk_id,
            "room_id":      room_id,
            "is_mock":      is_mock,
            "occupied":     0,
            "noise_db":     30,
            "temp_c":       21.0,
            "last_updated": None,
            # Private mock personality baselines (stripped before API responses)
            "_base_noise":  random.randint(35, 75),
            "_base_temp":   round(random.uniform(19.0, 24.0), 1),
        }
    log.info("Desk created: %s  room=%s  mock=%s", desk_id, room_id, is_mock)


def update_desk(desk_id: str, **kwargs) -> None:
    """
    Update one or more fields on a desk.
    Automatically stamps last_updated.
    Raises KeyError if desk_id is not in the store.
    """
    now = datetime.utcnow().isoformat()
    with store_lock:
        if desk_id not in desk_store:
            raise KeyError(f"Desk '{desk_id}' not found in state store.")
        desk_store[desk_id].update(kwargs)
        desk_store[desk_id]["last_updated"] = now


def mark_desk_mock(desk_id: str, is_mock: bool = True) -> None:
    """Toggle the mock flag — used when an Arduino is unregistered."""
    with store_lock:
        if desk_id in desk_store:
            desk_store[desk_id]["is_mock"] = is_mock


# ─── History ─────────────────────────────────────────────────

def record_history(desk_id: str, reading: dict) -> None:
    """Append a reading to the in-memory history deque for a desk."""
    desk_history[desk_id].append(reading)


def get_history(desk_id: str, limit: int = 50) -> list[dict]:
    return list(desk_history.get(desk_id, []))[-limit:]


# ─── Auto-ID / room slot helpers ─────────────────────────────

def next_auto_desk_id() -> str:
    """Return the next unused desk_N id."""
    with store_lock:
        existing = set(desk_store.keys())
    n = 1
    while f"desk_{n}" in existing:
        n += 1
    return f"desk_{n}"


def next_available_room() -> Optional[str]:
    """Return a room that still has capacity, or None if all rooms are full."""
    with store_lock:
        counts: dict[str, int] = defaultdict(int)
        for d in desk_store.values():
            counts[d["room_id"]] += 1
    for room_id, cfg in ROOM_CONFIG.items():
        if counts[room_id] < cfg["capacity"]:
            return room_id
    return None


def seed_mock_desks() -> None:
    """
    Fill every room to its configured capacity with mock desks.
    Real desks that were already created take their slots first.
    """
    with store_lock:
        counts: dict[str, int] = defaultdict(int)
        for d in desk_store.values():
            counts[d["room_id"]] += 1

    for room_id, cfg in ROOM_CONFIG.items():
        for _ in range(cfg["capacity"] - counts[room_id]):
            desk_id = next_auto_desk_id()
            ensure_desk(desk_id, room_id, is_mock=True)
            log.debug("Mock desk seeded: %s in %s", desk_id, room_id)
