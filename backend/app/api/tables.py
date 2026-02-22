from datetime import datetime, timezone

from fastapi import APIRouter

from app.core.rooms import ROOM_CONFIG, ROOM_ZONE_TYPES
from app.models.schemas import TableRow
from app.services import state

router = APIRouter(prefix="/api", tags=["Tables"])

TABLE_VIEW_BY_DESK_ID: dict[str, dict[str, object]] = {
    "desk_1": {"table_id": "Q1", "zone_name": "Quiet Zone", "zone_type": "quiet", "total_seats": 1},
    "desk_2": {"table_id": "Q2", "zone_name": "Quiet Zone", "zone_type": "quiet", "total_seats": 4},
    "desk_3": {"table_id": "Q3", "zone_name": "Quiet Zone", "zone_type": "quiet", "total_seats": 2},
    "desk_4": {"table_id": "R1", "zone_name": "Reading Room", "zone_type": "mixed", "total_seats": 6},
    "desk_5": {"table_id": "R2", "zone_name": "Reading Room", "zone_type": "mixed", "total_seats": 6},
    "desk_6": {"table_id": "R3", "zone_name": "Reading Room", "zone_type": "mixed", "total_seats": 6},
    "desk_7": {"table_id": "G1", "zone_name": "Group Area", "zone_type": "group", "total_seats": 6},
    "desk_8": {"table_id": "G2", "zone_name": "Group Area", "zone_type": "group", "total_seats": 6},
    "desk_9": {"table_id": "G3", "zone_name": "Group Area", "zone_type": "group", "total_seats": 8},
    "desk_10": {"table_id": "G4", "zone_name": "Group Area", "zone_type": "group", "total_seats": 8},
    "desk_11": {"table_id": "O1", "zone_name": "Open Study", "zone_type": "mixed", "total_seats": 4},
    "desk_12": {"table_id": "O2", "zone_name": "Open Study", "zone_type": "mixed", "total_seats": 4},
    "desk_13": {"table_id": "O3", "zone_name": "Open Study", "zone_type": "mixed", "total_seats": 4},
    "desk_14": {"table_id": "O4", "zone_name": "Open Study", "zone_type": "mixed", "total_seats": 6},
    "desk_15": {"table_id": "O5", "zone_name": "Open Study", "zone_type": "mixed", "total_seats": 4},
    "desk_16": {"table_id": "O6", "zone_name": "Open Study", "zone_type": "mixed", "total_seats": 4},
    "desk_17": {"table_id": "O7", "zone_name": "Open Study", "zone_type": "mixed", "total_seats": 4},
    "desk_18": {"table_id": "O8", "zone_name": "Open Study", "zone_type": "mixed", "total_seats": 6},
    "desk_19": {"table_id": "O9", "zone_name": "Open Study", "zone_type": "mixed", "total_seats": 6},
}


@router.get("/tables", response_model=list[TableRow])
def list_tables() -> list[TableRow]:
    rows: list[TableRow] = []
    now = datetime.now(timezone.utc).isoformat()
    desks = state.get_all_desks(strip_private=False)

    desks_by_room: dict[str, list[dict]] = {}
    for desk in desks:
        room_id = str(desk.get("room_id", ""))
        desks_by_room.setdefault(room_id, []).append(desk)

    room_avg_temp_by_room: dict[str, float] = {}
    for room_id, room_desks in desks_by_room.items():
        temps = [float(d.get("temp_c", 0.0)) for d in room_desks]
        room_avg_temp_by_room[room_id] = round(sum(temps) / len(temps), 1) if temps else 0.0

    for desk in desks:
        desk_id = str(desk.get("desk_id", ""))
        room_id = str(desk.get("room_id", ""))
        view_meta = TABLE_VIEW_BY_DESK_ID.get(desk_id, {})
        table_id = str(view_meta.get("table_id", desk_id))
        zone_name = str(view_meta.get("zone_name", ROOM_CONFIG.get(room_id, {}).get("label", room_id)))
        zone_type = str(view_meta.get("zone_type", desk.get("zone_type") or ROOM_ZONE_TYPES.get(room_id, "mixed")))

        total = int(view_meta.get("total_seats", desk.get("total_seats", 1)))
        total = max(1, total)

        occupied_raw = int(desk.get("occupied", 0))
        occupied = 1 if occupied_raw > 0 else 0
        available = max(0, total - occupied)
        status = "full" if available <= 0 else ("available" if available >= total else "partial")

        table_temp = float(desk.get("temp_c", room_avg_temp_by_room.get(room_id, 0.0)))
        room_avg_temp = room_avg_temp_by_room.get(room_id, table_temp)
        noise_db = int(desk.get("noise_db", 0))

        rows.append(
            TableRow(
                table_id=table_id,
                zone_name=zone_name,
                zone_type=zone_type,
                total_seats=total,
                occupied_seats=occupied,
                available_seats=available,
                status=status,
                noise_db=noise_db,
                temp_c=round(table_temp, 1),
                room_avg_temp_c=round(room_avg_temp, 1),
                last_updated=str(desk.get("last_updated") or now),
            )
        )

    return rows
