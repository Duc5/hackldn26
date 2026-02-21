"""
app/services/room_logic.py
───────────────────────────
Business logic for rooms — computes live summaries, status, and suggestions.
All calculations use the in-memory state store (fast, no DB hit).

Exports
───────
  compute_room_summary(room_id, include_desks) → dict
  filter_desks(desks, **kwargs)                → list[dict]
  desk_averages(desk_id)                       → dict  (from in-memory history)
  room_analytics(room_id)                      → dict  (from in-memory history)
"""

from typing import Optional

from app.core.logging import get_logger
from app.core.rooms import ROOM_CONFIG, NOISE_LOUD_THRESHOLD, OCCUPANCY_BUSY_THRESHOLD
from app.services import state

log = get_logger("spacesync.room_logic")


def compute_room_summary(room_id: str, include_desks: bool = True) -> dict:
    """
    Compute a full room summary from the live state.
    Returns an empty dict if the room has no desks yet.
    """
    desks = state.get_desks_for_room(room_id)
    if not desks:
        return {}

    total     = len(desks)
    occ_count = sum(1 for d in desks if d["occupied"])
    avg_noise = round(sum(d["noise_db"] for d in desks) / total, 1)
    avg_temp  = round(sum(d["temp_c"]   for d in desks) / total, 1)
    occ_pct   = round(occ_count / total, 2)

    # Status
    statuses: list[str] = []
    if occ_pct   >= OCCUPANCY_BUSY_THRESHOLD: statuses.append("Busy")
    if avg_noise >= NOISE_LOUD_THRESHOLD:     statuses.append("Loud")
    status = " & ".join(statuses) if statuses else "Available"

    # Suggestion
    suggestion: Optional[str] = None
    if statuses:
        best, best_score = None, float("inf")
        for rid in ROOM_CONFIG:
            if rid == room_id:
                continue
            peers = state.get_desks_for_room(rid)
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
        "occupancy_pct":  occ_pct,
        "total_desks":    total,
        "occupied_desks": occ_count,
        "suggestion":     suggestion,
    }

    if include_desks:
        result["desks"] = desks

    return result


def filter_desks(
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


def desk_averages(desk_id: str) -> dict:
    """Compute averages from in-memory history for a desk."""
    history = state.get_history(desk_id)
    d       = state.get_desk(desk_id) or {}

    if not history:
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


def room_analytics(room_id: str) -> dict:
    """Aggregate in-memory analytics for all desks in a room."""
    desks = state.get_desks_for_room(room_id)
    if not desks:
        return {}
    avgs = [desk_averages(d["desk_id"]) for d in desks]
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
