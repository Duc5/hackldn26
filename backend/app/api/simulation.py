from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.models.schemas import SimSerialLineIn, SimSerialLineOut
from app.services import state

router = APIRouter(prefix="/api", tags=["Simulation"])


@router.post("/sim/serial-line", response_model=SimSerialLineOut)
def inject_sim_serial_line(payload: SimSerialLineIn) -> SimSerialLineOut:
    if not settings.simulation_enabled:
        raise HTTPException(status_code=403, detail="Simulation is disabled. Set SIMULATION_ENABLED=1.")

    parts = [p.strip() for p in payload.line.split(",")]
    if len(parts) != 4:
        raise HTTPException(status_code=400, detail="Malformed serial line. Expected: desk_id,occupied,noise,temp")

    desk_id, occ_raw, noise_raw, temp_raw = parts
    desk = state.get_desk(desk_id)
    if desk is None:
        raise HTTPException(status_code=400, detail=f"Unknown desk_id '{desk_id}'")

    try:
        occupied = int(occ_raw)
        noise_db = int(noise_raw)
        temp_c = float(temp_raw)
    except ValueError:
        raise HTTPException(status_code=400, detail="Could not parse occupied/noise/temp values")

    occupied = 1 if occupied > 0 else 0
    state.update_desk(desk_id, occupied=occupied, noise_db=noise_db, temp_c=temp_c)
    state.record_history(
        desk_id,
        {"ts": datetime.utcnow().isoformat(), "occupied": occupied, "noise_db": noise_db, "temp_c": temp_c},
    )
    return SimSerialLineOut(ok=True, message="Applied simulation line")
