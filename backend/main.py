"""
SpaceSync — Library Management System Backend
FastAPI + Python Threading
Real Arduino data (desk_1, desk_2) + realistic mock data for the demo.

Install dependencies:
    pip install fastapi uvicorn pyserial

Run:
    uvicorn main:app --reload --port 8000
"""

import random
import threading
import time
import logging
from contextlib import asynccontextmanager
from typing import Optional
import serial
import serial.tools.list_ports
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("spacesync")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SERIAL_PORT   = "/dev/ttyUSB0"   # Change to "COM3" on Windows
SERIAL_BAUD   = 9600
SERIAL_TIMEOUT = 2               # seconds

# Room membership — which desk IDs belong to which room
ROOM_CONFIG: dict[str, list[str]] = {
    "room_a": ["desk_1", "desk_2", "desk_3", "desk_4", "desk_5", "desk_6"],
    "room_b": ["desk_7", "desk_8", "desk_9", "desk_10", "desk_11", "desk_12"],
    "room_c": ["desk_13", "desk_14", "desk_15", "desk_16", "desk_17", "desk_18"],
}

ROOM_LABELS: dict[str, str] = {
    "room_a": "Floor 3 — Quiet Zone",
    "room_b": "Ground Floor — Social",
    "room_c": "Level 2 — Collaborative",
}

# Physical desks updated by the serial thread (room_a only)
PHYSICAL_DESKS = {"desk_1", "desk_2"}

# Thresholds for status logic
OCCUPANCY_BUSY_THRESHOLD = 0.70   # 70 %
NOISE_LOUD_THRESHOLD     = 65     # dB

# ---------------------------------------------------------------------------
# In-memory data store
# dict[desk_id] -> DeskData
# ---------------------------------------------------------------------------
desk_store: dict[str, dict] = {}
store_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Mock data seed — baseline values per desk
# ---------------------------------------------------------------------------
def _seed_mock_baselines() -> None:
    """Populate every non-physical desk with a stable baseline."""
    for room_id, desks in ROOM_CONFIG.items():
        for desk_id in desks:
            if desk_id in PHYSICAL_DESKS:
                # Physical desks start with a sane default; serial will overwrite
                desk_store[desk_id] = {
                    "desk_id":  desk_id,
                    "room_id":  room_id,
                    "is_mock":  False,
                    "occupied": 0,
                    "noise_db": 30,
                    "temp_c":   21.0,
                }
            else:
                desk_store[desk_id] = {
                    "desk_id":  desk_id,
                    "room_id":  room_id,
                    "is_mock":  True,
                    # Each mock desk gets a unique random baseline so the grid
                    # looks varied rather than uniform.
                    "_base_noise": random.randint(35, 75),
                    "_base_temp":  round(random.uniform(19.0, 24.0), 1),
                    "_base_occ":   random.random(),  # probability of being occupied
                    "occupied": random.choice([0, 1]),
                    "noise_db": random.randint(35, 75),
                    "temp_c":   round(random.uniform(19.0, 24.0), 1),
                }


# ---------------------------------------------------------------------------
# Mock jitter — called periodically so the frontend looks "live"
# ---------------------------------------------------------------------------
def _apply_mock_jitter() -> None:
    """
    Nudge each mock desk by a small random delta so the heatmap
    visibly updates without changing the overall feel of the room.
    """
    with store_lock:
        for desk_id, data in desk_store.items():
            if not data["is_mock"]:
                continue

            base_noise = data["_base_noise"]
            base_temp  = data["_base_temp"]
            base_occ   = data["_base_occ"]

            # Noise drifts ±5 dB around its baseline
            new_noise = base_noise + random.randint(-5, 5)
            new_noise = max(25, min(90, new_noise))

            # Temperature drifts ±0.5 °C around its baseline
            new_temp = base_temp + round(random.uniform(-0.5, 0.5), 1)
            new_temp = round(max(16.0, min(30.0, new_temp)), 1)

            # Occupancy flips occasionally (weighted toward the baseline prob)
            flip_roll = random.random()
            if flip_roll < 0.05:          # 5 % chance to flip each tick
                new_occ = 1 - data["occupied"]
            else:
                new_occ = data["occupied"]

            data["noise_db"] = new_noise
            data["temp_c"]   = new_temp
            data["occupied"] = new_occ


# ---------------------------------------------------------------------------
# Serial listener thread
# ---------------------------------------------------------------------------
def _serial_listener() -> None:
    """
    Background thread that opens the serial port and continuously reads
    lines from the Arduino nodes.

    Expected format:  desk_id,occupied,noise,temp
    Example:          desk_1,1,40,21
    """
    ser: Optional[serial.Serial] = None

    while True:
        # --- (re)connect ---
        if ser is None or not ser.is_open:
            try:
                ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=SERIAL_TIMEOUT)
                log.info("Serial port %s opened at %d baud.", SERIAL_PORT, SERIAL_BAUD)
            except serial.SerialException as exc:
                log.warning("Could not open serial port %s: %s. Retrying in 5 s.", SERIAL_PORT, exc)
                time.sleep(5)
                continue

        # --- read one line ---
        try:
            raw = ser.readline()
            if not raw:
                continue

            line = raw.decode("utf-8", errors="ignore").strip()
            if not line:
                continue

            _parse_and_store(line)

        except serial.SerialException as exc:
            log.error("Serial read error: %s. Reconnecting…", exc)
            try:
                ser.close()
            except Exception:
                pass
            ser = None
            time.sleep(2)
        except Exception as exc:
            log.error("Unexpected error in serial listener: %s", exc)
            time.sleep(1)


def _parse_and_store(line: str) -> None:
    """Parse a raw serial line and update the desk store."""
    parts = line.split(",")
    if len(parts) != 4:
        log.debug("Malformed serial line (expected 4 fields): %r", line)
        return

    desk_id, occ_raw, noise_raw, temp_raw = (p.strip() for p in parts)

    if desk_id not in PHYSICAL_DESKS:
        log.debug("Unknown desk_id from serial: %r — ignoring.", desk_id)
        return

    try:
        occupied = int(occ_raw)
        noise_db = int(noise_raw)
        temp_c   = float(temp_raw)
    except ValueError:
        log.debug("Could not parse values from serial line: %r", line)
        return

    with store_lock:
        if desk_id in desk_store:
            desk_store[desk_id]["occupied"] = occupied
            desk_store[desk_id]["noise_db"] = noise_db
            desk_store[desk_id]["temp_c"]   = temp_c
            log.debug("Updated %s → occupied=%d noise=%d temp=%.1f", desk_id, occupied, noise_db, temp_c)


# ---------------------------------------------------------------------------
# Mock jitter background thread
# ---------------------------------------------------------------------------
def _jitter_loop() -> None:
    """Apply mock jitter every 3 seconds."""
    while True:
        time.sleep(3)
        _apply_mock_jitter()


# ---------------------------------------------------------------------------
# Room business logic
# ---------------------------------------------------------------------------
def _compute_room_summary(room_id: str) -> dict:
    """
    Compute averages and derive a status + suggestion for a room.
    Returns a dict ready for JSON serialisation.
    """
    desk_ids = ROOM_CONFIG.get(room_id, [])
    desks    = []

    with store_lock:
        for did in desk_ids:
            if did in desk_store:
                desks.append(dict(desk_store[did]))  # shallow copy is fine

    if not desks:
        return {}

    total          = len(desks)
    occupied_count = sum(1 for d in desks if d["occupied"])
    avg_noise      = round(sum(d["noise_db"] for d in desks) / total, 1)
    avg_temp       = round(sum(d["temp_c"]   for d in desks) / total, 1)
    occupancy_pct  = round(occupied_count / total, 2)

    # --- Status tagging ---
    statuses: list[str] = []
    if occupancy_pct >= OCCUPANCY_BUSY_THRESHOLD:
        statuses.append("Busy")
    if avg_noise >= NOISE_LOUD_THRESHOLD:
        statuses.append("Loud")
    status = " & ".join(statuses) if statuses else "Available"

    # --- Alternative suggestion ---
    suggestion: Optional[str] = None
    if statuses:
        other_rooms = [rid for rid in ROOM_CONFIG if rid != room_id]
        # Pick the quietest alternative
        best     = None
        best_noise = float("inf")
        for rid in other_rooms:
            peer_desks = []
            with store_lock:
                for did in ROOM_CONFIG[rid]:
                    if did in desk_store:
                        peer_desks.append(desk_store[did])
            if not peer_desks:
                continue
            peer_noise = sum(d["noise_db"] for d in peer_desks) / len(peer_desks)
            peer_occ   = sum(d["occupied"] for d in peer_desks) / len(peer_desks)
            # Score: lower is better (noise-weighted occupancy)
            score = peer_noise + peer_occ * 30
            if score < best_noise:
                best_noise = score
                best       = rid
        if best:
            suggestion = f"Try {ROOM_LABELS[best]} ({best}) — quieter & more available."

    return {
        "room_id":         room_id,
        "label":           ROOM_LABELS.get(room_id, room_id),
        "status":          status,
        "avg_noise_db":    avg_noise,
        "avg_temp_c":      avg_temp,
        "occupancy_pct":   occupancy_pct,
        "total_desks":     total,
        "occupied_desks":  occupied_count,
        "suggestion":      suggestion,
        "desks":           desks,
    }


# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("SpaceSync starting up…")
    _seed_mock_baselines()

    # Serial listener
    serial_thread = threading.Thread(target=_serial_listener, daemon=True, name="serial-listener")
    serial_thread.start()
    log.info("Serial listener thread started.")

    # Mock jitter
    jitter_thread = threading.Thread(target=_jitter_loop, daemon=True, name="mock-jitter")
    jitter_thread.start()
    log.info("Mock jitter thread started.")

    yield  # application runs here

    log.info("SpaceSync shutting down.")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="SpaceSync API",
    description="Real-time library desk occupancy, noise, and temperature.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow the React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pydantic response models (documentation + validation)
# ---------------------------------------------------------------------------
class DeskData(BaseModel):
    desk_id:  str
    room_id:  str
    is_mock:  bool
    occupied: int   # 0 | 1
    noise_db: int   # dB
    temp_c:   float # °C


class RoomSummary(BaseModel):
    room_id:        str
    label:          str
    status:         str           # "Available" | "Busy" | "Loud" | "Busy & Loud"
    avg_noise_db:   float
    avg_temp_c:     float
    occupancy_pct:  float         # 0.0 – 1.0
    total_desks:    int
    occupied_desks: int
    suggestion:     Optional[str]


class RoomDetail(RoomSummary):
    desks: list[DeskData]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/api/rooms", response_model=list[RoomSummary], tags=["Rooms"])
def list_rooms():
    """
    Return a high-level summary for every room.
    Used by the landing page to render the multi-room overview.
    """
    summaries = []
    for room_id in ROOM_CONFIG:
        summary = _compute_room_summary(room_id)
        if summary:
            # Drop 'desks' key — not included in the list view
            summary.pop("desks", None)
            summaries.append(summary)
    return summaries


@app.get("/api/rooms/{room_id}", response_model=RoomDetail, tags=["Rooms"])
def get_room(room_id: str):
    """
    Return the full desk-by-desk grid for a specific room.
    Used by the heatmap view when a user clicks into a room.
    """
    if room_id not in ROOM_CONFIG:
        raise HTTPException(
            status_code=404,
            detail=f"Room '{room_id}' not found. Valid rooms: {list(ROOM_CONFIG.keys())}",
        )
    detail = _compute_room_summary(room_id)
    return detail


@app.get("/api/health", tags=["Meta"])
def health():
    """Simple health-check for the demo."""
    physical_status = {}
    with store_lock:
        for did in PHYSICAL_DESKS:
            d = desk_store.get(did)
            physical_status[did] = {
                "occupied": d["occupied"] if d else None,
                "noise_db": d["noise_db"] if d else None,
                "temp_c":   d["temp_c"]   if d else None,
            }
    return {
        "status":            "ok",
        "physical_desks":    physical_status,
        "mock_desk_count":   sum(len(v) for v in ROOM_CONFIG.values()) - len(PHYSICAL_DESKS),
        "serial_port":       SERIAL_PORT,
    }