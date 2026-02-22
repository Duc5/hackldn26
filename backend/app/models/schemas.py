"""
app/models/schemas.py
──────────────────────
Pydantic models used across the app:
  • API request / response bodies
  • Internal typed dicts for the in-memory store
  • MongoDB document shapes (as TypedDicts — Motor returns plain dicts)
"""

from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


# ─────────────────────────────────────────────────────────────
# Desk
# ─────────────────────────────────────────────────────────────

class DeskData(BaseModel):
    """Public desk snapshot returned by the API."""
    desk_id:      str
    assignment_id: str
    room_id:      str
    is_mock:      bool
    occupied:     int            # 0 | 1
    noise_db:     int            # dB
    temp_c:       float          # °C
    last_updated: Optional[str] = None   # ISO timestamp
    sensor_distance_cm: Optional[float] = None
    sensor_motion: Optional[int] = None
    sensor_sound_flag: Optional[int] = None
    sensor_sound_p2p: Optional[int] = None


class DeskHistoryReading(BaseModel):
    ts:       str
    occupied: int
    noise_db: int
    temp_c:   float


class DeskHistoryResponse(BaseModel):
    desk_id:  str
    readings: list[DeskHistoryReading]


class TableRow(BaseModel):
    table_id: str
    zone_name: str
    zone_type: str
    total_seats: int
    occupied_seats: int
    available_seats: int
    status: str
    noise_db: Optional[int] = None
    temp_c: float
    room_avg_temp_c: float
    last_updated: str


class SimSerialLineIn(BaseModel):
    line: str


class SimSerialLineOut(BaseModel):
    ok: bool
    message: str


# ─────────────────────────────────────────────────────────────
# Room
# ─────────────────────────────────────────────────────────────

class RoomSummary(BaseModel):
    room_id:        str
    label:          str
    status:         str          # "Available" | "Busy" | "Loud" | "Busy & Loud"
    avg_noise_db:   float
    avg_temp_c:     float
    occupancy_pct:  float        # 0.0 – 1.0
    total_desks:    int
    occupied_desks: int
    suggestion:     Optional[str] = None


class RoomDetail(RoomSummary):
    desks: list[DeskData]


# ─────────────────────────────────────────────────────────────
# Device registry
# ─────────────────────────────────────────────────────────────

class RegisterDeviceRequest(BaseModel):
    hardware_id: str
    room_id:     str
    desk_id:     Optional[str] = None
    label:       Optional[str] = None


class MoveDeviceRequest(BaseModel):
    new_room_id: str
    new_desk_id: Optional[str] = None


class RegisterDeviceResponse(BaseModel):
    hardware_id: str
    desk_id:     str
    room_id:     str
    last_port:   Optional[str] = None
    message:     str


class RegisteredDeviceInfo(BaseModel):
    hardware_id:  str
    desk_id:      str
    room_id:      str
    label:        str
    last_port:    Optional[str] = None
    current_port: Optional[str] = None
    plugged_in:   bool
    thread_alive: bool


class DeviceListResponse(BaseModel):
    registered_devices: list[RegisteredDeviceInfo]
    detected_ports:     list[dict]


# ─────────────────────────────────────────────────────────────
# Analytics
# ─────────────────────────────────────────────────────────────

class DeskAnalytics(BaseModel):
    avg_occupied: float
    avg_noise_db: float
    avg_temp_c:   float
    sample_count: int


class RoomAnalytics(BaseModel):
    room_id:           str
    avg_noise_db:      float
    avg_temp_c:        float
    avg_occupancy_pct: float
    peak_noise_db:     float
    peak_occupancy:    float
    total_samples:     int


class GlobalSummary(BaseModel):
    total_desks:       int
    occupied_desks:    int
    available_desks:   int
    occupancy_pct:     float
    avg_noise_db:      float
    avg_temp_c:        float
    real_sensor_count: int
    mock_desk_count:   int
    room_count:        int


# ─────────────────────────────────────────────────────────────
# MongoDB document shapes (TypedDicts)
# ─────────────────────────────────────────────────────────────

from typing import TypedDict


class SnapshotDoc(TypedDict):
    """
    One document written to the `snapshots` collection every SNAPSHOT_INTERVAL.
    Represents the state of a single desk at a point in time.
    """
    desk_id:      str
    room_id:      str
    is_mock:      bool
    occupied:     int
    noise_db:     int
    temp_c:       float
    recorded_at:  datetime   # UTC — set by the snapshot service


class DeviceRegistryDoc(TypedDict):
    """
    One document in the `device_registry` collection.
    Mirrors devices.json but lives in MongoDB for multi-instance support.
    """
    hardware_id: str          # primary key (_id equivalent, stored as a field too)
    desk_id:     str
    assignment_id: str
    room_id:     str
    label:       str
    last_port:   Optional[str]
    updated_at:  datetime
