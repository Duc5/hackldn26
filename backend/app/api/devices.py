"""
app/api/devices.py
───────────────────
Device registry endpoints.

  GET    /api/devices/scan                  — scan USB ports
  GET    /api/devices                       — list registered devices
  POST   /api/devices/register             — register a new Arduino
  PATCH  /api/devices/{hardware_id}/move   — move to a new desk/room
  DELETE /api/devices/{hardware_id}        — unregister

Typical first-time workflow:
  1. Plug in Arduino
  2. GET  /api/devices/scan          →  find hardware_id
  3. POST /api/devices/register      →  { hardware_id, room_id }
  4. Done — desk is live immediately
"""

from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    DeviceListResponse,
    MoveDeviceRequest,
    RegisterDeviceRequest,
    RegisterDeviceResponse,
)
from app.services import device_registry, serial_reader

router = APIRouter(prefix="/api/devices", tags=["Devices"])


@router.get("/scan")
def scan_ports():
    """
    List every detected serial port with its hardware_id and registration status.
    Plug in one Arduino at a time and call this to identify it.
    """
    return {"ports": device_registry.scan_all_ports()}


@router.get("", response_model=DeviceListResponse)
def list_devices():
    """All registered hardware IDs with live connection status."""
    import serial.tools.list_ports
    from app.services.device_registry import build_hardware_id, find_port_for_hardware
    from app.services.serial_reader import get_thread_status

    reg     = device_registry.get_all()
    threads = get_thread_status()

    registered = [
        {
            "hardware_id":  hw_id,
            "desk_id":      info["desk_id"],
            "room_id":      info["room_id"],
            "label":        info.get("label", info["desk_id"]),
            "last_port":    info.get("last_port"),
            "current_port": find_port_for_hardware(hw_id),
            "plugged_in":   find_port_for_hardware(hw_id) is not None,
            "thread_alive": threads.get(hw_id, False),
        }
        for hw_id, info in reg.items()
    ]

    detected = [
        {
            "port":        p.device,
            "hardware_id": build_hardware_id(p),
            "description": p.description,
        }
        for p in serial.tools.list_ports.comports()
    ]

    return {"registered_devices": registered, "detected_ports": detected}


@router.post("/register", response_model=RegisterDeviceResponse)
async def register_device(req: RegisterDeviceRequest):
    """
    Register an Arduino to a desk.

    Body:
        { "hardware_id": "SN:ABC123", "room_id": "room_a" }
        { "hardware_id": "SN:ABC123", "room_id": "room_a", "desk_id": "desk_2", "label": "Window seat" }
    """
    try:
        entry = await device_registry.register(
            hardware_id=req.hardware_id,
            room_id=req.room_id,
            desk_id=req.desk_id,
            label=req.label,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Ensure a serial thread is running for this device
    serial_reader.ensure_thread(req.hardware_id)

    port = entry.get("last_port")
    return RegisterDeviceResponse(
        hardware_id=req.hardware_id,
        desk_id=entry["desk_id"],
        room_id=entry["room_id"],
        last_port=port,
        message=(
            f"Registered {req.hardware_id} → {entry['desk_id']} in {entry['room_id']}. "
            + (f"Found on port {port}." if port else "Not currently plugged in — will connect when detected.")
        ),
    )


@router.patch("/{hardware_id}/move", response_model=RegisterDeviceResponse)
async def move_device(hardware_id: str, req: MoveDeviceRequest):
    """
    Move a registered Arduino to a new desk / room.
    The old desk keeps its last reading and reverts to mock jitter.
    """
    try:
        entry = await device_registry.move(
            hardware_id=hardware_id,
            new_room_id=req.new_room_id,
            new_desk_id=req.new_desk_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    port = entry.get("last_port")
    return RegisterDeviceResponse(
        hardware_id=hardware_id,
        desk_id=entry["desk_id"],
        room_id=entry["room_id"],
        last_port=port,
        message=f"Moved to {entry['desk_id']} in {entry['room_id']}. Old desk reverted to mock.",
    )


@router.delete("/{hardware_id}")
async def unregister_device(hardware_id: str):
    """
    Remove a device from the registry.
    The desk stays in the heatmap with its last reading, handed to mock jitter.
    """
    try:
        removed = await device_registry.unregister(hardware_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return {
        "message": (
            f"Unregistered {hardware_id} "
            f"(was {removed['desk_id']} in {removed['room_id']}). "
            f"Desk kept with last reading."
        )
    }
