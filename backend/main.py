"""
SpaceSync — Library Management System Backend v3
═════════════════════════════════════════════════
FastAPI + Python Threading

KEY DESIGN: Desks are identified by Arduino HARDWARE ID (serial number / VID:PID),
NOT by USB port. This means:
  • Plug the same Arduino into any port → automatically maps to the same desk
  • Move an Arduino to a new desk → re-register it to a new desk_id / room
  • The physical desk assignment is permanently stored in devices.json

Feature summary:
  • Hardware-ID-based device registry (survives port changes)
  • One serial thread per connected Arduino
  • Persistent devices.json — survives server restarts
  • Dynamic registration API (register, move, unregister)
  • Mock data + jitter fills rooms that have no physical sensors
  • Full analytics (averages, peaks, history per desk)
  • Filterable queries on every endpoint
  • CORS for React on port 3000

Install:
    pip install fastapi uvicorn pyserial

Run:
    uvicorn main:app --reload --port 8000

How to find your Arduino's hardware ID (run once):
    python -c "
    import serial.tools.list_ports
    for p in serial.tools.list_ports.comports():
        print(p.device, '|', p.serial_number, '|', p.vid, p.pid, '|', p.description)
    "
"""

import json
import logging
import os
import random
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

import serial
import serial.tools.list_ports
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ─────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("spacesync")


# ─────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────
SERIAL_BAUD     = 9600
SERIAL_TIMEOUT  = 2          # seconds per readline
JITTER_INTERVAL = 3          # seconds between mock data updates
HISTORY_MAXLEN  = 200        # readings kept per desk for analytics
DEVICES_FILE    = "devices.json"

# Room definitions — label + how many desks each room holds
ROOM_CONFIG: dict[str, dict] = {
    "room_a": {"label": "Floor 3 — Quiet Zone",    "capacity": 6},
    "room_b": {"label": "Ground Floor — Social",    "capacity": 6},
    "room_c": {"label": "Level 2 — Collaborative", "capacity": 6},
}

# Status thresholds
OCCUPANCY_BUSY_THRESHOLD = 0.70   # 70% occupied → "Busy"
NOISE_LOUD_THRESHOLD     = 65     # dB → "Loud"


# ─────────────────────────────────────────────────────────────
# In-memory stores
# ─────────────────────────────────────────────────────────────

# desk_id → current live snapshot
desk_store: dict[str, dict] = {}

# desk_id → deque of historical readings
desk_history: dict[str, deque] = defaultdict(lambda: deque(maxlen=HISTORY_MAXLEN))

# ── Device registry ──────────────────────────────────────────
# The registry is keyed by HARDWARE ID (not USB port).
# hardware_id → {
#     "desk_id":   "desk_1",
#     "room_id":   "room_a",
#     "last_port": "COM3",      # last known port (informational only)
#     "label":     "My Label",  # optional friendly name
# }
device_registry: dict[str, dict] = {}

store_lock    = threading.Lock()
registry_lock = threading.Lock()

# hardware_id → running Thread
active_serial_threads: dict[str, threading.Thread] = {}


# ─────────────────────────────────────────────────────────────
# Hardware ID helpers
# ─────────────────────────────────────────────────────────────

def _build_hardware_id(port_info) -> str:
    """
    Build a stable hardware ID from a ListPortInfo object.

    Priority:
      1. USB serial number  (most stable — unique per board)
      2. VID:PID            (stable per Arduino model, not per board)
      3. Port name fallback (least stable — changes on reconnect)
    """
    if port_info.serial_number:
        return f"SN:{port_info.serial_number}"
    if port_info.vid and port_info.pid:
        return f"VIDPID:{port_info.vid:04X}:{port_info.pid:04X}"
    return f"PORT:{port_info.device}"


def _get_all_arduino_ports() -> list:
    """
    Return all detected serial ports that look like Arduino / CH340 / FTDI devices.
    Falls back to returning all ports if none match the filter.
    """
    known_vids = {
        0x2341,  # Arduino LLC
        0x1A86,  # CH340 (clone boards)
        0x0403,  # FTDI
        0x10C4,  # Silicon Labs CP210x
        0x239A,  # Adafruit
    }
    all_ports  = list(serial.tools.list_ports.comports())
    arduino    = [p for p in all_ports if p.vid in known_vids]
    return arduino if arduino else all_ports


def _find_port_by_hardware_id(hardware_id: str) -> Optional[str]:
    """
    Scan currently connected ports and return the OS port name
    (e.g. "COM3") for the given hardware_id.
    Returns None if the device isn't currently plugged in.
    """
    for port_info in serial.tools.list_ports.comports():
        if _build_hardware_id(port_info) == hardware_id:
            return port_info.device
    return None


# ─────────────────────────────────────────────────────────────
# Device registry — persistence
# ─────────────────────────────────────────────────────────────

def _load_registry() -> None:
    if not os.path.exists(DEVICES_FILE):
        log.info("No devices.json found — starting with empty registry.")
        return
    try:
        with open(DEVICES_FILE, "r") as f:
            data = json.load(f)
        with registry_lock:
            device_registry.update(data)
        log.info("Loaded %d device(s) from %s", len(data), DEVICES_FILE)
        for hw_id, info in data.items():
            log.info("  %s → %s (%s)", hw_id, info["desk_id"], info["room_id"])
    except Exception as exc:
        log.error("Failed to load devices.json: %s", exc)


def _save_registry() -> None:
    with registry_lock:
        snapshot = dict(device_registry)
    try:
        with open(DEVICES_FILE, "w") as f:
            json.dump(snapshot, f, indent=2)
        log.info("Registry saved (%d device(s))", len(snapshot))
    except Exception as exc:
        log.error("Failed to save devices.json: %s", exc)


# ─────────────────────────────────────────────────────────────
# Desk store helpers
# ─────────────────────────────────────────────────────────────

def _next_auto_desk_id() -> str:
    with store_lock:
        existing = set(desk_store.keys())
    with registry_lock:
        registered = {v["desk_id"] for v in device_registry.values()}
    taken = existing | registered
    n = 1
    while f"desk_{n}" in taken:
        n += 1
    return f"desk_{n}"


def _next_available_room_slot() -> Optional[str]:
    with store_lock:
        counts: dict[str, int] = defaultdict(int)
        for d in desk_store.values():
            counts[d["room_id"]] += 1
    for room_id, cfg in ROOM_CONFIG.items():
        if counts[room_id] < cfg["capacity"]:
            return room_id
    return None


def _ensure_desk_exists(desk_id: str, room_id: str, is_mock: bool) -> None:
    with store_lock:
        if desk_id in desk_store:
            # Update room / mock flag if re-registered
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
            "_base_noise":  random.randint(35, 75),
            "_base_temp":   round(random.uniform(19.0, 24.0), 1),
        }
    log.info("Desk created: %s  room=%s  mock=%s", desk_id, room_id, is_mock)


def _seed_mock_desks() -> None:
    """Fill every room to capacity with mock desks."""
    with store_lock:
        counts: dict[str, int] = defaultdict(int)
        for d in desk_store.values():
            counts[d["room_id"]] += 1

    for room_id, cfg in ROOM_CONFIG.items():
        for _ in range(cfg["capacity"] - counts[room_id]):
            _ensure_desk_exists(_next_auto_desk_id(), room_id, is_mock=True)


# ─────────────────────────────────────────────────────────────
# Mock jitter thread
# ─────────────────────────────────────────────────────────────

def _apply_mock_jitter() -> None:
    """Nudge every mock desk slightly so the heatmap looks alive."""
    now = datetime.utcnow().isoformat()
    with store_lock:
        for data in desk_store.values():
            if not data["is_mock"]:
                continue
            new_noise = data["_base_noise"] + random.randint(-5, 5)
            new_noise = max(25, min(90, new_noise))
            new_temp  = data["_base_temp"] + round(random.uniform(-0.5, 0.5), 1)
            new_temp  = round(max(16.0, min(30.0, new_temp)), 1)
            if random.random() < 0.05:
                data["occupied"] = 1 - data["occupied"]
            data["noise_db"]     = new_noise
            data["temp_c"]       = new_temp
            data["last_updated"] = now

    # Record history outside the write lock
    with store_lock:
        snapshot = {k: dict(v) for k, v in desk_store.items()}
    for desk_id, data in snapshot.items():
        desk_history[desk_id].append({
            "ts":       data.get("last_updated") or now,
            "occupied": data["occupied"],
            "noise_db": data["noise_db"],
            "temp_c":   data["temp_c"],
        })


def _jitter_loop() -> None:
    while True:
        time.sleep(JITTER_INTERVAL)
        _apply_mock_jitter()


# ─────────────────────────────────────────────────────────────
# Serial listener (one thread per hardware_id)
# ─────────────────────────────────────────────────────────────

def _serial_listener(hardware_id: str) -> None:
    """
    Background thread for one Arduino (identified by hardware_id).

    Each loop:
      1. Look up desk_id from registry
      2. Scan USB ports to find which port this hardware_id is on right now
      3. Open that port and stream readings into desk_store
      4. On disconnect — wait and retry (the port may change on reconnect)
    """
    ser: Optional[serial.Serial] = None
    last_port: Optional[str]     = None

    while True:
        # ── 1. Resolve desk assignment ────────────────────────
        with registry_lock:
            info = device_registry.get(hardware_id)
        if info is None:
            # Device was unregistered — thread should stop
            log.info("Hardware %s unregistered — serial thread exiting.", hardware_id)
            return

        desk_id = info["desk_id"]

        # ── 2. Find current port ──────────────────────────────
        current_port = _find_port_by_hardware_id(hardware_id)

        if current_port is None:
            if ser and ser.is_open:
                try:
                    ser.close()
                except Exception:
                    pass
                ser = None
            log.warning("Arduino %s (%s) not found on any port. Waiting…", hardware_id, desk_id)
            time.sleep(5)
            continue

        # Update last_port in registry (informational)
        if current_port != last_port:
            with registry_lock:
                if hardware_id in device_registry:
                    device_registry[hardware_id]["last_port"] = current_port
            _save_registry()
            last_port = current_port
            log.info("Arduino %s (%s) detected on port %s", hardware_id, desk_id, current_port)

        # ── 3. (Re)connect if needed ──────────────────────────
        if ser is None or not ser.is_open or ser.port != current_port:
            try:
                if ser and ser.is_open:
                    ser.close()
                ser = serial.Serial(current_port, SERIAL_BAUD, timeout=SERIAL_TIMEOUT)
                log.info("Serial connected: %s → %s on %s", hardware_id, desk_id, current_port)
            except serial.SerialException as exc:
                log.warning("Cannot open %s: %s. Retry in 3 s.", current_port, exc)
                ser = None
                time.sleep(3)
                continue

        # ── 4. Read one line ──────────────────────────────────
        try:
            raw = ser.readline()
            if raw:
                line = raw.decode("utf-8", errors="ignore").strip()
                if line:
                    _parse_and_store(line, desk_id)
        except serial.SerialException as exc:
            log.error("Serial read error on %s: %s. Reconnecting…", current_port, exc)
            try:
                ser.close()
            except Exception:
                pass
            ser = None
            time.sleep(2)
        except Exception as exc:
            log.error("Unexpected serial error: %s", exc)
            time.sleep(1)


def _parse_and_store(line: str, assigned_desk_id: str) -> None:
    """
    Parse a serial line and write to desk_store.

    Accepted Arduino output formats:
        1,40,21            →  occupied, noise_db, temp_c
        desk_1,1,40,21     →  (desk name ignored — we use registry assignment)
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

    now = datetime.utcnow().isoformat()
    with store_lock:
        if assigned_desk_id not in desk_store:
            log.warning("Desk %s not in store — dropping reading.", assigned_desk_id)
            return
        d = desk_store[assigned_desk_id]
        d["occupied"]     = occupied
        d["noise_db"]     = noise_db
        d["temp_c"]       = temp_c
        d["last_updated"] = now
        d["is_mock"]      = False

    desk_history[assigned_desk_id].append({
        "ts": now, "occupied": occupied, "noise_db": noise_db, "temp_c": temp_c,
    })
    log.debug("Updated %s → occ=%d noise=%d temp=%.1f", assigned_desk_id, occupied, noise_db, temp_c)


# ─────────────────────────────────────────────────────────────
# Serial thread manager
# ─────────────────────────────────────────────────────────────

def _ensure_serial_thread(hardware_id: str) -> None:
    existing = active_serial_threads.get(hardware_id)
    if existing and existing.is_alive():
        return
    t = threading.Thread(
        target=_serial_listener,
        args=(hardware_id,),
        daemon=True,
        name=f"serial-{hardware_id}",
    )
    t.start()
    active_serial_threads[hardware_id] = t
    log.info("Serial thread started for hardware_id=%s", hardware_id)


def _start_all_registered_threads() -> None:
    with registry_lock:
        hw_ids = list(device_registry.keys())
    for hw_id in hw_ids:
        _ensure_serial_thread(hw_id)


# ─────────────────────────────────────────────────────────────
# Analytics functions
# ─────────────────────────────────────────────────────────────

def _desk_averages(desk_id: str) -> dict:
    history = list(desk_history.get(desk_id, []))
    if not history:
        with store_lock:
            d = desk_store.get(desk_id, {})
        return {
            "avg_occupied": float(d.get("occupied", 0)),
            "avg_noise_db": float(d.get("noise_db", 0)),
            "avg_temp_c":   float(d.get("temp_c", 0)),
            "sample_count": 0,
        }
    n = len(history)
    return {
        "avg_occupied": round(sum(r["occupied"] for r in history) / n, 2),
        "avg_noise_db": round(sum(r["noise_db"] for r in history) / n, 1),
        "avg_temp_c":   round(sum(r["temp_c"]   for r in history) / n, 1),
        "sample_count": n,
    }


def _room_analytics(room_id: str) -> dict:
    with store_lock:
        desks = [d for d in desk_store.values() if d["room_id"] == room_id]
    if not desks:
        return {}
    avgs = [_desk_averages(d["desk_id"]) for d in desks]
    n    = len(avgs)
    return {
        "room_id":           room_id,
        "avg_noise_db":      round(sum(a["avg_noise_db"] for a in avgs) / n, 1),
        "avg_temp_c":        round(sum(a["avg_temp_c"]   for a in avgs) / n, 1),
        "avg_occupancy_pct": round(sum(a["avg_occupied"] for a in avgs) / n, 2),
        "peak_noise_db":     max(a["avg_noise_db"] for a in avgs),
        "peak_occupancy":    max(a["avg_occupied"] for a in avgs),
        "total_samples":     sum(a["sample_count"] for a in avgs),
    }


def _compute_room_summary(room_id: str, include_desks: bool = True) -> dict:
    with store_lock:
        desks = [dict(d) for d in desk_store.values() if d["room_id"] == room_id]
    if not desks:
        return {}

    total         = len(desks)
    occ_count     = sum(1 for d in desks if d["occupied"])
    avg_noise     = round(sum(d["noise_db"] for d in desks) / total, 1)
    avg_temp      = round(sum(d["temp_c"]   for d in desks) / total, 1)
    occupancy_pct = round(occ_count / total, 2)

    statuses: list[str] = []
    if occupancy_pct >= OCCUPANCY_BUSY_THRESHOLD:
        statuses.append("Busy")
    if avg_noise >= NOISE_LOUD_THRESHOLD:
        statuses.append("Loud")
    status = " & ".join(statuses) if statuses else "Available"

    suggestion: Optional[str] = None
    if statuses:
        best, best_score = None, float("inf")
        for rid in ROOM_CONFIG:
            if rid == room_id:
                continue
            with store_lock:
                peers = [d for d in desk_store.values() if d["room_id"] == rid]
            if not peers:
                continue
            score = (
                sum(d["noise_db"] for d in peers) / len(peers)
                + sum(d["occupied"] for d in peers) / len(peers) * 30
            )
            if score < best_score:
                best_score, best = score, rid
        if best:
            suggestion = (
                f"Try {ROOM_CONFIG[best]['label']} ({best}) — "
                f"quieter & more available."
            )

    result: dict = {
        "room_id":        room_id,
        "label":          ROOM_CONFIG[room_id]["label"],
        "status":         status,
        "avg_noise_db":   avg_noise,
        "avg_temp_c":     avg_temp,
        "occupancy_pct":  occupancy_pct,
        "total_desks":    total,
        "occupied_desks": occ_count,
        "suggestion":     suggestion,
    }

    if include_desks:
        result["desks"] = [
            {k: v for k, v in d.items() if not k.startswith("_")}
            for d in desks
        ]

    return result


# ─────────────────────────────────────────────────────────────
# Filtering helper
# ─────────────────────────────────────────────────────────────

def _filter_desks(
    desks:     list[dict],
    occupied:  Optional[int]   = None,
    min_noise: Optional[int]   = None,
    max_noise: Optional[int]   = None,
    min_temp:  Optional[float] = None,
    max_temp:  Optional[float] = None,
    is_mock:   Optional[bool]  = None,
) -> list[dict]:
    r = desks
    if occupied  is not None: r = [d for d in r if d["occupied"] == occupied]
    if min_noise is not None: r = [d for d in r if d["noise_db"] >= min_noise]
    if max_noise is not None: r = [d for d in r if d["noise_db"] <= max_noise]
    if min_temp  is not None: r = [d for d in r if d["temp_c"]   >= min_temp]
    if max_temp  is not None: r = [d for d in r if d["temp_c"]   <= max_temp]
    if is_mock   is not None: r = [d for d in r if d["is_mock"]  == is_mock]
    return r


# ─────────────────────────────────────────────────────────────
# Lifespan
# ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("SpaceSync v3 starting up…")

    _load_registry()

    # Ensure every registered device has a desk entry
    with registry_lock:
        reg = dict(device_registry)
    for hw_id, info in reg.items():
        _ensure_desk_exists(info["desk_id"], info["room_id"], is_mock=False)

    # Fill remaining room capacity with mock desks
    _seed_mock_desks()

    # Start serial thread per registered Arduino
    _start_all_registered_threads()

    # Start mock jitter
    threading.Thread(target=_jitter_loop, daemon=True, name="mock-jitter").start()
    log.info("All threads started. API ready.")

    yield

    log.info("SpaceSync shutting down.")


# ─────────────────────────────────────────────────────────────
# FastAPI app
# ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="SpaceSync API",
    description="Real-time library desk occupancy, noise & temperature.",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────
# Pydantic models
# ─────────────────────────────────────────────────────────────

class DeskData(BaseModel):
    desk_id:      str
    room_id:      str
    is_mock:      bool
    occupied:     int
    noise_db:     int
    temp_c:       float
    last_updated: Optional[str] = None


class RoomSummary(BaseModel):
    room_id:        str
    label:          str
    status:         str
    avg_noise_db:   float
    avg_temp_c:     float
    occupancy_pct:  float
    total_desks:    int
    occupied_desks: int
    suggestion:     Optional[str] = None


class RoomDetail(RoomSummary):
    desks: list[DeskData]


class RegisterDeviceRequest(BaseModel):
    hardware_id: str            # from _build_hardware_id() or the /api/devices/scan endpoint
    desk_id:     Optional[str] = None   # auto-generated if omitted
    room_id:     str
    label:       Optional[str] = None   # friendly name e.g. "Front door sensor"


class MoveDeviceRequest(BaseModel):
    new_desk_id: Optional[str] = None   # auto-generated if omitted
    new_room_id: str


class RegisterDeviceResponse(BaseModel):
    hardware_id: str
    desk_id:     str
    room_id:     str
    last_port:   Optional[str] = None
    message:     str


# ─────────────────────────────────────────────────────────────
# Routes — Rooms
# ─────────────────────────────────────────────────────────────

@app.get("/api/rooms", response_model=list[RoomSummary], tags=["Rooms"])
def list_rooms():
    """High-level summary for every room. Use for the landing page cards."""
    return [
        s for rid in ROOM_CONFIG
        if (s := _compute_room_summary(rid, include_desks=False))
    ]


@app.get("/api/rooms/{room_id}", response_model=RoomDetail, tags=["Rooms"])
def get_room(
    room_id:   str,
    occupied:  Optional[int]   = Query(None, description="0=vacant, 1=occupied"),
    min_noise: Optional[int]   = Query(None, description="Min noise (dB)"),
    max_noise: Optional[int]   = Query(None, description="Max noise (dB)"),
    min_temp:  Optional[float] = Query(None, description="Min temp (°C)"),
    max_temp:  Optional[float] = Query(None, description="Max temp (°C)"),
    is_mock:   Optional[bool]  = Query(None, description="true=mock, false=real sensors only"),
):
    """
    Full desk grid for the heatmap view with optional filters.

    Examples:
        /api/rooms/room_a?occupied=0
        /api/rooms/room_a?max_noise=55&is_mock=false
    """
    if room_id not in ROOM_CONFIG:
        raise HTTPException(
            status_code=404,
            detail=f"Room '{room_id}' not found. Valid: {list(ROOM_CONFIG.keys())}",
        )
    detail = _compute_room_summary(room_id, include_desks=True)
    detail["desks"] = _filter_desks(
        detail["desks"],
        occupied=occupied, min_noise=min_noise, max_noise=max_noise,
        min_temp=min_temp, max_temp=max_temp, is_mock=is_mock,
    )
    return detail


# ─────────────────────────────────────────────────────────────
# Routes — Desks
# ─────────────────────────────────────────────────────────────

@app.get("/api/desks", response_model=list[DeskData], tags=["Desks"])
def list_all_desks(
    room_id:   Optional[str]   = Query(None),
    occupied:  Optional[int]   = Query(None),
    min_noise: Optional[int]   = Query(None),
    max_noise: Optional[int]   = Query(None),
    min_temp:  Optional[float] = Query(None),
    max_temp:  Optional[float] = Query(None),
    is_mock:   Optional[bool]  = Query(None),
):
    """
    All desks across all rooms with optional filters.

    Examples:
        /api/desks?is_mock=false             → real sensors only
        /api/desks?occupied=1&max_noise=60   → occupied but quiet desks
        /api/desks?room_id=room_b            → all desks in Room B
    """
    with store_lock:
        desks = [
            {k: v for k, v in d.items() if not k.startswith("_")}
            for d in desk_store.values()
        ]
    if room_id:
        desks = [d for d in desks if d["room_id"] == room_id]
    return _filter_desks(
        desks,
        occupied=occupied, min_noise=min_noise, max_noise=max_noise,
        min_temp=min_temp, max_temp=max_temp, is_mock=is_mock,
    )


@app.get("/api/desks/{desk_id}", response_model=DeskData, tags=["Desks"])
def get_desk(desk_id: str):
    """Current reading for a single desk."""
    with store_lock:
        desk = desk_store.get(desk_id)
    if not desk:
        raise HTTPException(status_code=404, detail=f"Desk '{desk_id}' not found.")
    return {k: v for k, v in desk.items() if not k.startswith("_")}


@app.get("/api/desks/{desk_id}/history", tags=["Desks"])
def get_desk_history(
    desk_id: str,
    limit:   int = Query(50, le=HISTORY_MAXLEN),
):
    """Last N readings for a desk — use for sparklines / trend charts."""
    with store_lock:
        if desk_id not in desk_store:
            raise HTTPException(status_code=404, detail=f"Desk '{desk_id}' not found.")
    return {
        "desk_id":  desk_id,
        "readings": list(desk_history.get(desk_id, []))[-limit:],
    }


# ─────────────────────────────────────────────────────────────
# Routes — Device Registry
# ─────────────────────────────────────────────────────────────

@app.get("/api/devices/scan", tags=["Devices"])
def scan_ports():
    """
    Scan all USB ports and return hardware IDs for every detected device.
    Use this to find the hardware_id to pass to /api/devices/register.

    Tip: plug in one Arduino at a time and call this endpoint — the new
    entry that appears is your Arduino's hardware_id.
    """
    results = []
    for p in serial.tools.list_ports.comports():
        hw_id = _build_hardware_id(p)
        with registry_lock:
            registered = device_registry.get(hw_id)
        results.append({
            "port":         p.device,
            "hardware_id":  hw_id,
            "description":  p.description,
            "serial_number":p.serial_number,
            "vid_pid":      f"{p.vid:04X}:{p.pid:04X}" if p.vid else None,
            "registered_as":registered,   # None if not yet registered
        })
    return {"ports": results}


@app.post("/api/devices/register", response_model=RegisterDeviceResponse, tags=["Devices"])
def register_device(req: RegisterDeviceRequest):
    """
    Register an Arduino (by hardware_id) to a desk and room.

    The hardware_id is STABLE — it doesn't change when you plug into a
    different USB port. Get it from GET /api/devices/scan.

    • desk_id is optional — omit to auto-generate (desk_1, desk_2, …)
    • Registering an already-registered hardware_id updates its desk/room
    • Persisted to devices.json — survives server restarts

    Workflow for a new Arduino:
      1. Plug it in
      2. GET /api/devices/scan  → find hardware_id
      3. POST /api/devices/register  { hardware_id, room_id }
      4. Done — desk is live immediately
    """
    if req.room_id not in ROOM_CONFIG:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid room_id '{req.room_id}'. Valid: {list(ROOM_CONFIG.keys())}",
        )

    desk_id     = req.desk_id or _next_auto_desk_id()
    current_port = _find_port_by_hardware_id(req.hardware_id)

    with registry_lock:
        device_registry[req.hardware_id] = {
            "desk_id":   desk_id,
            "room_id":   req.room_id,
            "label":     req.label or desk_id,
            "last_port": current_port,
        }

    _save_registry()
    _ensure_desk_exists(desk_id, req.room_id, is_mock=False)
    _ensure_serial_thread(req.hardware_id)

    return RegisterDeviceResponse(
        hardware_id=req.hardware_id,
        desk_id=desk_id,
        room_id=req.room_id,
        last_port=current_port,
        message=(
            f"Registered hardware {req.hardware_id} → {desk_id} in {req.room_id}. "
            + (f"Found on port {current_port}." if current_port else "Not currently plugged in — will connect when detected.")
        ),
    )


@app.patch("/api/devices/{hardware_id}/move", response_model=RegisterDeviceResponse, tags=["Devices"])
def move_device(hardware_id: str, req: MoveDeviceRequest):
    """
    Move a registered Arduino to a new desk / room without losing its
    hardware identity or historical data.

    The old desk entry stays in the store with its last reading.
    A new desk entry is created (or updated) for the new location.

    Use this when you physically move a sensor node to a different desk.
    """
    with registry_lock:
        if hardware_id not in device_registry:
            raise HTTPException(
                status_code=404,
                detail=f"Hardware ID '{hardware_id}' not registered. Use /api/devices/register first.",
            )
        old_info = dict(device_registry[hardware_id])

    if req.new_room_id not in ROOM_CONFIG:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid room_id '{req.new_room_id}'. Valid: {list(ROOM_CONFIG.keys())}",
        )

    new_desk_id = req.new_desk_id or _next_auto_desk_id()

    # Mark old desk as mock so jitter keeps it animated
    with store_lock:
        if old_info["desk_id"] in desk_store:
            desk_store[old_info["desk_id"]]["is_mock"] = True

    # Update registry
    with registry_lock:
        device_registry[hardware_id]["desk_id"] = new_desk_id
        device_registry[hardware_id]["room_id"] = req.new_room_id

    _save_registry()
    _ensure_desk_exists(new_desk_id, req.new_room_id, is_mock=False)

    current_port = _find_port_by_hardware_id(hardware_id)

    log.info(
        "Moved %s: %s/%s → %s/%s",
        hardware_id, old_info["room_id"], old_info["desk_id"],
        req.new_room_id, new_desk_id,
    )

    return RegisterDeviceResponse(
        hardware_id=hardware_id,
        desk_id=new_desk_id,
        room_id=req.new_room_id,
        last_port=current_port,
        message=(
            f"Moved {hardware_id} from {old_info['desk_id']} ({old_info['room_id']}) "
            f"to {new_desk_id} ({req.new_room_id}). Old desk reverted to mock."
        ),
    )


@app.get("/api/devices", tags=["Devices"])
def list_devices():
    """
    All registered hardware IDs, their desk assignments, connection status,
    and currently detected USB ports.
    """
    with registry_lock:
        reg = dict(device_registry)

    registered = []
    for hw_id, info in reg.items():
        thread      = active_serial_threads.get(hw_id)
        current_port = _find_port_by_hardware_id(hw_id)
        registered.append({
            "hardware_id":   hw_id,
            "desk_id":       info["desk_id"],
            "room_id":       info["room_id"],
            "label":         info.get("label", info["desk_id"]),
            "last_port":     info.get("last_port"),
            "current_port":  current_port,
            "plugged_in":    current_port is not None,
            "thread_alive":  thread.is_alive() if thread else False,
        })

    return {
        "registered_devices": registered,
        "detected_ports": [
            {"port": p.device, "hardware_id": _build_hardware_id(p), "description": p.description}
            for p in serial.tools.list_ports.comports()
        ],
    }


@app.delete("/api/devices/{hardware_id}", tags=["Devices"])
def unregister_device(hardware_id: str):
    """
    Remove a hardware ID from the registry.

    The desk stays in the store with its last known reading and reverts
    to mock jitter. The serial thread for this device exits cleanly.
    """
    with registry_lock:
        if hardware_id not in device_registry:
            raise HTTPException(
                status_code=404,
                detail=f"Hardware ID '{hardware_id}' not registered.",
            )
        info = device_registry.pop(hardware_id)

    # Revert desk to mock
    with store_lock:
        if info["desk_id"] in desk_store:
            desk_store[info["desk_id"]]["is_mock"] = True

    _save_registry()
    # Thread will exit on its next loop when it finds hardware_id missing from registry
    return {
        "message": (
            f"Unregistered {hardware_id} (was {info['desk_id']} in {info['room_id']}). "
            f"Desk kept with last reading and handed to mock jitter."
        )
    }


# ─────────────────────────────────────────────────────────────
# Routes — Analytics
# ─────────────────────────────────────────────────────────────

@app.get("/api/analytics/summary", tags=["Analytics"])
def global_summary():
    """Bird's-eye stats across every room — great for a dashboard header."""
    with store_lock:
        all_desks = list(desk_store.values())
    total    = len(all_desks)
    occupied = sum(1 for d in all_desks if d["occupied"])
    real     = sum(1 for d in all_desks if not d["is_mock"])
    return {
        "total_desks":       total,
        "occupied_desks":    occupied,
        "available_desks":   total - occupied,
        "occupancy_pct":     round(occupied / total, 2) if total else 0,
        "avg_noise_db":      round(sum(d["noise_db"] for d in all_desks) / total, 1) if total else 0,
        "avg_temp_c":        round(sum(d["temp_c"]   for d in all_desks) / total, 1) if total else 0,
        "real_sensor_count": real,
        "mock_desk_count":   total - real,
        "room_count":        len(ROOM_CONFIG),
    }


@app.get("/api/analytics/rooms/{room_id}", tags=["Analytics"])
def room_analytics(room_id: str):
    """Historical averages and peaks for a room."""
    if room_id not in ROOM_CONFIG:
        raise HTTPException(status_code=404, detail=f"Room '{room_id}' not found.")
    return _room_analytics(room_id)


@app.get("/api/analytics/desks/{desk_id}", tags=["Analytics"])
def desk_analytics(desk_id: str):
    """Historical averages for a single desk."""
    with store_lock:
        if desk_id not in desk_store:
            raise HTTPException(status_code=404, detail=f"Desk '{desk_id}' not found.")
    return _desk_averages(desk_id)


# ─────────────────────────────────────────────────────────────
# Routes — Health
# ─────────────────────────────────────────────────────────────

@app.get("/api/health", tags=["Meta"])
def health():
    with registry_lock:
        reg = dict(device_registry)
    return {
        "status":       "ok",
        "total_desks":  len(desk_store),
        "real_sensors": sum(1 for d in desk_store.values() if not d["is_mock"]),
        "devices":      {
            hw_id: {
                "desk_id":    info["desk_id"],
                "plugged_in": _find_port_by_hardware_id(hw_id) is not None,
                "thread_alive": (
                    active_serial_threads[hw_id].is_alive()
                    if hw_id in active_serial_threads else False
                ),
            }
            for hw_id, info in reg.items()
        },
    }