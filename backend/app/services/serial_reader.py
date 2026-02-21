"""
app/services/serial_reader.py
──────────────────────────────
Serial port listener service.

One background thread per registered Arduino.
Each thread:
  1. Looks up its desk assignment from device_registry
  2. Scans USB ports to find the current port for its hardware_id
  3. Opens the port and streams readings into the live state store
  4. On disconnect — waits and retries (port may change on reconnect)

Exports
───────
  ensure_thread(hardware_id)   — start a thread if not already running
  start_all()                  — start threads for every registered device
  get_thread_status()          → dict[hardware_id, bool]  (alive?)
"""

import threading
from datetime import datetime
from typing import Optional

import serial

from app.core.config import settings
from app.core.logging import get_logger
from app.services import device_registry, state

log = get_logger("spacesync.serial")

# hardware_id → Thread
_threads: dict[str, threading.Thread] = {}
_threads_lock = threading.Lock()


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────

def ensure_thread(hardware_id: str) -> None:
    """Start a serial listener thread for hardware_id if not already running."""
    with _threads_lock:
        existing = _threads.get(hardware_id)
        if existing and existing.is_alive():
            return
        t = threading.Thread(
            target=_listener_loop,
            args=(hardware_id,),
            daemon=True,
            name=f"serial-{hardware_id[:16]}",
        )
        t.start()
        _threads[hardware_id] = t
    log.info("Serial thread started for %s", hardware_id)


def start_all() -> None:
    """Start a thread for every device in the registry."""
    for hw_id in device_registry.get_all():
        ensure_thread(hw_id)


def get_thread_status() -> dict[str, bool]:
    """Return alive status for every known serial thread."""
    with _threads_lock:
        return {hw_id: t.is_alive() for hw_id, t in _threads.items()}


# ─────────────────────────────────────────────────────────────
# Listener loop (runs in a daemon thread)
# ─────────────────────────────────────────────────────────────

def _listener_loop(hardware_id: str) -> None:
    ser: Optional[serial.Serial] = None
    last_port: Optional[str]     = None

    while True:
        # ── 1. Check registration ─────────────────────────────
        entry = device_registry.get(hardware_id)
        if entry is None:
            # Device was unregistered — thread should stop
            log.info("Device %s unregistered — serial thread exiting.", hardware_id)
            return

        desk_id = entry["desk_id"]

        # ── 2. Find current port ──────────────────────────────
        current_port = device_registry.find_port_for_hardware(hardware_id)

        if current_port is None:
            _close_serial(ser)
            ser = None
            log.warning("Device %s (%s) not detected on any port. Waiting…", hardware_id, desk_id)
            import time; time.sleep(5)
            continue

        # Track port changes
        if current_port != last_port:
            device_registry.update_last_port(hardware_id, current_port)
            last_port = current_port
            log.info("Device %s (%s) found on port %s", hardware_id, desk_id, current_port)

        # ── 3. (Re)connect ────────────────────────────────────
        if ser is None or not ser.is_open or ser.port != current_port:
            _close_serial(ser)
            ser = _open_serial(current_port)
            if ser is None:
                import time; time.sleep(3)
                continue

        # ── 4. Read one line ──────────────────────────────────
        try:
            raw = ser.readline()
            if raw:
                line = raw.decode("utf-8", errors="ignore").strip()
                if line:
                    _parse_and_store(line, desk_id, hardware_id)

        except serial.SerialException as exc:
            log.error("Serial read error on %s: %s. Reconnecting…", current_port, exc)
            _close_serial(ser)
            ser = None
            import time; time.sleep(2)

        except Exception as exc:
            log.error("Unexpected error reading %s: %s", current_port, exc)
            import time; time.sleep(1)


def _open_serial(port: str) -> Optional[serial.Serial]:
    try:
        ser = serial.Serial(port, settings.serial_baud, timeout=settings.serial_timeout)
        log.info("Serial port %s opened.", port)
        return ser
    except serial.SerialException as exc:
        log.warning("Cannot open serial port %s: %s", port, exc)
        return None


def _close_serial(ser: Optional[serial.Serial]) -> None:
    if ser:
        try:
            ser.close()
        except Exception:
            pass


def _parse_and_store(line: str, desk_id: str, hardware_id: str) -> None:
    """
    Parse a serial line and update the live state store.

    Accepted formats:
        1,40,21            →  occupied, noise_db, temp_c
        desk_1,1,40,21     →  desk name ignored — assignment comes from registry
    """
    parts = line.split(",")
    if len(parts) == 4:
        _, occ_raw, noise_raw, temp_raw = parts
    elif len(parts) == 3:
        occ_raw, noise_raw, temp_raw = parts
    else:
        log.debug("Malformed serial line: %r", line)
        return

    try:
        occupied = int(occ_raw.strip())
        noise_db = int(noise_raw.strip())
        temp_c   = float(temp_raw.strip())
    except ValueError:
        log.debug("Could not parse values from: %r", line)
        return
    occupied = 1 if occupied > 0 else 0

    # Write to live state
    try:
        state.update_desk(desk_id, occupied=occupied, noise_db=noise_db, temp_c=temp_c, is_mock=False)
    except KeyError:
        log.warning("Desk %s not in state store — creating it.", desk_id)
        entry = device_registry.get(hardware_id)
        room_id = entry["room_id"] if entry else "room_a"
        state.ensure_desk(desk_id, room_id, is_mock=False)
        state.update_desk(desk_id, occupied=occupied, noise_db=noise_db, temp_c=temp_c)

    # Record to in-memory history
    state.record_history(desk_id, {
        "ts":       datetime.utcnow().isoformat(),
        "occupied": occupied,
        "noise_db": noise_db,
        "temp_c":   temp_c,
    })

    log.debug("Live update %s → occ=%d noise=%d temp=%.1f", desk_id, occupied, noise_db, temp_c)
