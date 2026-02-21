"""
app/api/health.py
──────────────────
Health check endpoint.
"""

from fastapi import APIRouter

from app.services import state, serial_reader, device_registry
from app.services.device_registry import find_port_for_hardware

router = APIRouter(prefix="/api", tags=["Meta"])


@router.get("/health")
def health():
    """System health — DB connection, serial threads, desk counts."""
    reg     = device_registry.get_all()
    threads = serial_reader.get_thread_status()
    desks   = state.get_all_desks()

    return {
        "status":       "ok",
        "total_desks":  len(desks),
        "real_sensors": sum(1 for d in desks if not d["is_mock"]),
        "mock_desks":   sum(1 for d in desks if d["is_mock"]),
        "devices": {
            hw_id: {
                "desk_id":    info["desk_id"],
                "room_id":    info["room_id"],
                "plugged_in": find_port_for_hardware(hw_id) is not None,
                "thread_alive": threads.get(hw_id, False),
            }
            for hw_id, info in reg.items()
        },
    }
