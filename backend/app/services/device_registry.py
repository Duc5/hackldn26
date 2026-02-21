"""
app/services/device_registry.py
─────────────────────────────────
Manages the hardware_id → desk assignment registry.

Storage
───────
  Primary:   MongoDB `device_registry` collection  (async, persistent)
  Fallback:  devices.json                           (sync, local backup)

The JSON file is written on every change so the app can still start
without a DB connection (useful for local dev / hackathon demo).

On startup, load order:
  1. Try MongoDB — load all devices
  2. If MongoDB unavailable, fall back to devices.json
  3. Seed in-memory state store with loaded devices

Key functions
─────────────
  load_registry()                   → load from DB/JSON into memory
  register(hardware_id, ...)        → add/update mapping
  move(hardware_id, new_room, ...)  → reassign to a new desk
  unregister(hardware_id)           → remove mapping
  get(hardware_id)                  → single entry
  get_all()                         → full registry dict
  save_to_json()                    → write devices.json (backup)
"""

import json
import os
import threading
from datetime import datetime, timezone
from typing import Optional

import serial.tools.list_ports

from app.core.logging import get_logger
from app.core.rooms import ROOM_CONFIG
from app.services import state

log = get_logger("spacesync.registry")

DEVICES_FILE = "devices.json"

# hardware_id → info dict  (in-memory, protected by lock)
_registry: dict[str, dict] = {}
_lock = threading.Lock()


# ─────────────────────────────────────────────────────────────
# Hardware ID helpers
# ─────────────────────────────────────────────────────────────

def build_hardware_id(port_info) -> str:
    """
    Build a stable hardware ID from a ListPortInfo object.
    Priority: serial number → VID:PID → port name fallback.
    """
    if port_info.serial_number:
        return f"SN:{port_info.serial_number}"
    if port_info.vid and port_info.pid:
        return f"VIDPID:{port_info.vid:04X}:{port_info.pid:04X}"
    return f"PORT:{port_info.device}"


def find_port_for_hardware(hardware_id: str) -> Optional[str]:
    """Scan USB ports and return the OS port name for the given hardware_id."""
    for p in serial.tools.list_ports.comports():
        if build_hardware_id(p) == hardware_id:
            return p.device
    return None


def scan_all_ports() -> list[dict]:
    """Return info about every detected serial port."""
    results = []
    for p in serial.tools.list_ports.comports():
        hw_id = build_hardware_id(p)
        with _lock:
            registered = dict(_registry[hw_id]) if hw_id in _registry else None
        results.append({
            "port":          p.device,
            "hardware_id":   hw_id,
            "description":   p.description,
            "serial_number": p.serial_number,
            "vid_pid":       f"{p.vid:04X}:{p.pid:04X}" if p.vid else None,
            "registered_as": registered,
        })
    return results


# ─────────────────────────────────────────────────────────────
# Load / Save
# ─────────────────────────────────────────────────────────────

async def load_registry() -> None:
    """
    Load registry from MongoDB (preferred) or devices.json (fallback).
    Populates both _registry and the state store.
    """
    docs: list[dict] = []

    # Try MongoDB first
    try:
        from app.db.repository import get_all_devices
        docs = await get_all_devices()
        if docs:
            log.info("Loaded %d device(s) from MongoDB.", len(docs))
    except Exception as exc:
        log.warning("Could not load registry from MongoDB: %s. Trying devices.json…", exc)

    # Fallback to local JSON
    if not docs:
        docs = _load_json()

    with _lock:
        for doc in docs:
            hw_id = doc.get("hardware_id")
            if not hw_id:
                continue
            _registry[hw_id] = {
                "hardware_id": hw_id,
                "desk_id":     doc["desk_id"],
                "room_id":     doc["room_id"],
                "label":       doc.get("label", doc["desk_id"]),
                "last_port":   doc.get("last_port"),
            }
            # Ensure the desk exists in the live state store
            state.ensure_desk(doc["desk_id"], doc["room_id"], is_mock=False)

    log.info("Registry loaded: %d device(s).", len(_registry))


def _load_json() -> list[dict]:
    if not os.path.exists(DEVICES_FILE):
        return []
    try:
        with open(DEVICES_FILE) as f:
            data = json.load(f)
        log.info("Loaded %d device(s) from %s.", len(data), DEVICES_FILE)
        return list(data.values()) if isinstance(data, dict) else data
    except Exception as exc:
        log.error("Failed to read %s: %s", DEVICES_FILE, exc)
        return []


def save_to_json() -> None:
    """Write current registry to devices.json (sync, called after every change)."""
    with _lock:
        snapshot = dict(_registry)
    try:
        with open(DEVICES_FILE, "w") as f:
            json.dump(snapshot, f, indent=2)
    except Exception as exc:
        log.error("Failed to write %s: %s", DEVICES_FILE, exc)


# ─────────────────────────────────────────────────────────────
# CRUD
# ─────────────────────────────────────────────────────────────

async def register(
    hardware_id: str,
    room_id:     str,
    desk_id:     Optional[str] = None,
    label:       Optional[str] = None,
) -> dict:
    """
    Register or re-register a hardware_id.
    Returns the registry entry dict.
    """
    if room_id not in ROOM_CONFIG:
        raise ValueError(f"Invalid room_id '{room_id}'.")

    desk_id = desk_id or state.next_auto_desk_id()
    port    = find_port_for_hardware(hardware_id)

    entry = {
        "hardware_id": hardware_id,
        "desk_id":     desk_id,
        "room_id":     room_id,
        "label":       label or desk_id,
        "last_port":   port,
    }

    with _lock:
        _registry[hardware_id] = entry

    # Persist
    save_to_json()
    try:
        from app.db.repository import upsert_device
        await upsert_device(entry)
    except Exception as exc:
        log.warning("Could not persist device to MongoDB: %s", exc)

    # Ensure desk in live store
    state.ensure_desk(desk_id, room_id, is_mock=False)

    log.info("Registered %s → %s in %s", hardware_id, desk_id, room_id)
    return entry


async def move(
    hardware_id: str,
    new_room_id: str,
    new_desk_id: Optional[str] = None,
) -> dict:
    """
    Move a registered device to a new desk / room.
    The old desk stays in the state store and reverts to mock.
    Returns the updated registry entry.
    """
    with _lock:
        if hardware_id not in _registry:
            raise KeyError(f"Hardware ID '{hardware_id}' not registered.")
        old = dict(_registry[hardware_id])

    if new_room_id not in ROOM_CONFIG:
        raise ValueError(f"Invalid room_id '{new_room_id}'.")

    new_desk_id = new_desk_id or state.next_auto_desk_id()
    port        = find_port_for_hardware(hardware_id)

    # Revert old desk to mock
    state.mark_desk_mock(old["desk_id"], is_mock=True)

    updated = {
        **old,
        "desk_id":   new_desk_id,
        "room_id":   new_room_id,
        "last_port": port,
    }

    with _lock:
        _registry[hardware_id] = updated

    save_to_json()
    try:
        from app.db.repository import upsert_device
        await upsert_device(updated)
    except Exception as exc:
        log.warning("Could not persist device move to MongoDB: %s", exc)

    state.ensure_desk(new_desk_id, new_room_id, is_mock=False)

    log.info(
        "Moved %s: %s/%s → %s/%s",
        hardware_id, old["room_id"], old["desk_id"], new_room_id, new_desk_id,
    )
    return updated


async def unregister(hardware_id: str) -> dict:
    """
    Remove a device from the registry.
    The desk stays in the live store (reverts to mock jitter).
    Returns the removed entry.
    """
    with _lock:
        if hardware_id not in _registry:
            raise KeyError(f"Hardware ID '{hardware_id}' not registered.")
        removed = _registry.pop(hardware_id)

    state.mark_desk_mock(removed["desk_id"], is_mock=True)

    save_to_json()
    try:
        from app.db.repository import delete_device
        await delete_device(hardware_id)
    except Exception as exc:
        log.warning("Could not delete device from MongoDB: %s", exc)

    log.info("Unregistered %s (was %s in %s)", hardware_id, removed["desk_id"], removed["room_id"])
    return removed


def get(hardware_id: str) -> Optional[dict]:
    with _lock:
        entry = _registry.get(hardware_id)
        return dict(entry) if entry else None


def get_all() -> dict[str, dict]:
    with _lock:
        return dict(_registry)


def update_last_port(hardware_id: str, port: str) -> None:
    """Update the cached last_port without a full upsert."""
    with _lock:
        if hardware_id in _registry:
            _registry[hardware_id]["last_port"] = port
