"""
app/api/desks.py
─────────────────
Desk endpoints.

  GET /api/desks                      — all desks (filterable)
  GET /api/desks/{desk_id}            — single desk current reading
  GET /api/desks/{desk_id}/history    — in-memory reading history
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import DeskData, DeskHistoryResponse
from app.services import state
from app.services.room_logic import filter_desks

router = APIRouter(prefix="/api/desks", tags=["Desks"])


@router.get("", response_model=list[DeskData])
def list_desks(
    room_id:   Optional[str]   = Query(None, description="Filter by room_id"),
    occupied:  Optional[int]   = Query(None, description="0=vacant, 1=occupied"),
    min_noise: Optional[int]   = Query(None),
    max_noise: Optional[int]   = Query(None),
    min_temp:  Optional[float] = Query(None),
    max_temp:  Optional[float] = Query(None),
    is_mock:   Optional[bool]  = Query(None),
):
    """
    All desks with optional filters.

    Examples:
        /api/desks?is_mock=false            → real Arduino desks only
        /api/desks?occupied=1&max_noise=60  → occupied but quiet
        /api/desks?room_id=room_b           → all desks in Room B
    """
    desks = state.get_all_desks()
    if room_id:
        desks = [d for d in desks if d["room_id"] == room_id]
    return filter_desks(
        desks,
        occupied=occupied, min_noise=min_noise, max_noise=max_noise,
        min_temp=min_temp, max_temp=max_temp, is_mock=is_mock,
    )


@router.get("/{desk_id}", response_model=DeskData)
def get_desk(desk_id: str):
    """Current live reading for a single desk."""
    desk = state.get_desk(desk_id)
    if not desk:
        raise HTTPException(status_code=404, detail=f"Desk '{desk_id}' not found.")
    return desk


@router.get("/{desk_id}/history", response_model=DeskHistoryResponse)
def get_desk_history(
    desk_id: str,
    limit:   int = Query(50, ge=1, le=200, description="Number of recent readings"),
):
    """
    In-memory reading history for a desk.
    Use for sparklines or trend micro-charts in the heatmap.
    """
    if not state.get_desk(desk_id):
        raise HTTPException(status_code=404, detail=f"Desk '{desk_id}' not found.")
    return {
        "desk_id":  desk_id,
        "readings": state.get_history(desk_id, limit=limit),
    }
