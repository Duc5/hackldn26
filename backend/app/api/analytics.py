"""
app/api/analytics.py
─────────────────────
Analytics endpoints — two data sources:

  LIVE (in-memory history, fast):
    GET /api/analytics/summary
    GET /api/analytics/rooms/{room_id}
    GET /api/analytics/desks/{desk_id}

  HISTORICAL (MongoDB, richer):
    GET /api/analytics/db/desks/{desk_id}          — DB snapshots for a desk
    GET /api/analytics/db/desks/{desk_id}/stats    — DB-computed aggregates
    GET /api/analytics/db/rooms/{room_id}          — DB snapshots for a room
    GET /api/analytics/db/rooms/{room_id}/stats    — DB-computed aggregates
    GET /api/analytics/db/rooms/{room_id}/events   — status change log
"""

from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.core.rooms import ROOM_CONFIG
from app.models.schemas import DeskAnalytics, GlobalSummary, RoomAnalytics
from app.services import room_logic, state
from app.db import repository

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


# ─────────────────────────────────────────────────────────────
# Live analytics (in-memory)
# ─────────────────────────────────────────────────────────────

@router.get("/summary", response_model=GlobalSummary)
def global_summary():
    """Bird's-eye stats across all rooms — great for a dashboard header."""
    desks    = state.get_all_desks()
    total    = len(desks)
    occupied = sum(1 for d in desks if d["occupied"])
    real     = sum(1 for d in desks if not d["is_mock"])
    return {
        "total_desks":       total,
        "occupied_desks":    occupied,
        "available_desks":   total - occupied,
        "occupancy_pct":     round(occupied / total, 2) if total else 0,
        "avg_noise_db":      round(sum(d["noise_db"] for d in desks) / total, 1) if total else 0,
        "avg_temp_c":        round(sum(d["temp_c"]   for d in desks) / total, 1) if total else 0,
        "real_sensor_count": real,
        "mock_desk_count":   total - real,
        "room_count":        len(ROOM_CONFIG),
    }


@router.get("/rooms/{room_id}", response_model=RoomAnalytics)
def live_room_analytics(room_id: str):
    """In-memory history averages and peaks for a room."""
    if room_id not in ROOM_CONFIG:
        raise HTTPException(status_code=404, detail=f"Room '{room_id}' not found.")
    result = room_logic.room_analytics(room_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"No data for room '{room_id}'.")
    return result


@router.get("/desks/{desk_id}", response_model=DeskAnalytics)
def live_desk_analytics(desk_id: str):
    """In-memory history averages for a single desk."""
    if not state.get_desk(desk_id):
        raise HTTPException(status_code=404, detail=f"Desk '{desk_id}' not found.")
    return room_logic.desk_averages(desk_id)


# ─────────────────────────────────────────────────────────────
# Historical analytics (MongoDB)
# ─────────────────────────────────────────────────────────────

def _parse_since(hours: Optional[int], days: Optional[int]) -> Optional[datetime]:
    """Build a `since` datetime from hours or days query params."""
    if hours:
        return datetime.now(timezone.utc) - timedelta(hours=hours)
    if days:
        return datetime.now(timezone.utc) - timedelta(days=days)
    return None


@router.get("/db/desks/{desk_id}")
async def db_desk_snapshots(
    desk_id: str,
    limit:   int            = Query(100, le=1000),
    hours:   Optional[int]  = Query(None, description="Only readings from last N hours"),
    days:    Optional[int]  = Query(None, description="Only readings from last N days"),
):
    """
    Raw snapshot documents for a desk from MongoDB.
    Use for detailed charts or exports.

        /api/analytics/db/desks/desk_1?hours=24
        /api/analytics/db/desks/desk_1?days=7&limit=500
    """
    since = _parse_since(hours, days)
    docs  = await repository.get_desk_snapshots(desk_id, limit=limit, since=since)
    return {"desk_id": desk_id, "count": len(docs), "snapshots": docs}


@router.get("/db/desks/{desk_id}/stats")
async def db_desk_stats(
    desk_id: str,
    hours:   Optional[int] = Query(None),
    days:    Optional[int] = Query(None),
):
    """
    MongoDB-computed avg/min/max for a desk.
    Much faster than fetching all documents for long time windows.

        /api/analytics/db/desks/desk_1/stats?days=30
    """
    since = _parse_since(hours, days)
    stats = await repository.get_desk_aggregates(desk_id, since=since)
    if not stats:
        raise HTTPException(status_code=404, detail=f"No DB data found for desk '{desk_id}'.")
    return {"desk_id": desk_id, "stats": stats}


@router.get("/db/rooms/{room_id}")
async def db_room_snapshots(
    room_id: str,
    limit:   int            = Query(500, le=5000),
    hours:   Optional[int]  = Query(None),
    days:    Optional[int]  = Query(None),
):
    """
    Raw snapshot documents for all desks in a room from MongoDB.

        /api/analytics/db/rooms/room_a?hours=6
    """
    if room_id not in ROOM_CONFIG:
        raise HTTPException(status_code=404, detail=f"Room '{room_id}' not found.")
    since = _parse_since(hours, days)
    docs  = await repository.get_room_snapshots(room_id, limit=limit, since=since)
    return {"room_id": room_id, "count": len(docs), "snapshots": docs}


@router.get("/db/rooms/{room_id}/stats")
async def db_room_stats(
    room_id: str,
    hours:   Optional[int] = Query(None),
    days:    Optional[int] = Query(None),
):
    """
    MongoDB-computed aggregates for an entire room.

        /api/analytics/db/rooms/room_a/stats?days=7
    """
    if room_id not in ROOM_CONFIG:
        raise HTTPException(status_code=404, detail=f"Room '{room_id}' not found.")
    since = _parse_since(hours, days)
    stats = await repository.get_room_aggregates(room_id, since=since)
    if not stats:
        raise HTTPException(status_code=404, detail=f"No DB data found for room '{room_id}'.")
    return {"room_id": room_id, "stats": stats}


@router.get("/db/rooms/{room_id}/events")
async def db_room_events(
    room_id: str,
    limit:   int = Query(50, le=200),
):
    """
    Status change event log for a room (Available ↔ Busy / Loud transitions).
    """
    if room_id not in ROOM_CONFIG:
        raise HTTPException(status_code=404, detail=f"Room '{room_id}' not found.")
    events = await repository.get_room_events(room_id, limit=limit)
    return {"room_id": room_id, "events": events}
