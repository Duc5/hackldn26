"""
app/api/rooms.py
─────────────────
Room endpoints.

  GET /api/rooms                  — list all rooms (summary cards)
  GET /api/rooms/{room_id}        — full desk grid for heatmap (with filters)
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.core.rooms import ROOM_CONFIG
from app.models.schemas import RoomDetail, RoomSummary
from app.services import room_logic

router = APIRouter(prefix="/api/rooms", tags=["Rooms"])


@router.get("", response_model=list[RoomSummary])
def list_rooms():
    """High-level summary card for every room. Use for the landing page."""
    return [
        s for rid in ROOM_CONFIG
        if (s := room_logic.compute_room_summary(rid, include_desks=False))
    ]


@router.get("/{room_id}", response_model=RoomDetail)
def get_room(
    room_id:   str,
    occupied:  Optional[int]   = Query(None, description="0=vacant, 1=occupied"),
    min_noise: Optional[int]   = Query(None, description="Min noise (dB)"),
    max_noise: Optional[int]   = Query(None, description="Max noise (dB)"),
    min_temp:  Optional[float] = Query(None, description="Min temperature (°C)"),
    max_temp:  Optional[float] = Query(None, description="Max temperature (°C)"),
    is_mock:   Optional[bool]  = Query(None, description="true=mock only, false=real sensors only"),
):
    """
    Full desk grid for the heatmap view.
    All query params are optional filters.

    Examples:
        /api/rooms/room_a?occupied=0
        /api/rooms/room_a?max_noise=55&is_mock=false
        /api/rooms/room_a?min_temp=20&max_temp=23
    """
    if room_id not in ROOM_CONFIG:
        raise HTTPException(
            status_code=404,
            detail=f"Room '{room_id}' not found. Valid: {list(ROOM_CONFIG.keys())}",
        )

    detail = room_logic.compute_room_summary(room_id, include_desks=True)
    detail["desks"] = room_logic.filter_desks(
        detail.get("desks", []),
        occupied=occupied, min_noise=min_noise, max_noise=max_noise,
        min_temp=min_temp, max_temp=max_temp, is_mock=is_mock,
    )
    return detail
