"""
app/services/mock_jitter.py
────────────────────────────
Background thread that nudges mock desk values every JITTER_INTERVAL seconds
so the heatmap looks alive during the demo.

Only desks where is_mock=True are touched.
Real Arduino desks are never modified here.
"""

import random
import threading
import time
from datetime import datetime

from app.core.config import settings
from app.core.logging import get_logger
from app.services import state

log = get_logger("spacesync.mock")

_thread: threading.Thread | None = None


def start() -> None:
    """Start the mock jitter background thread (call once at startup)."""
    global _thread
    if _thread and _thread.is_alive():
        return
    _thread = threading.Thread(target=_loop, daemon=True, name="mock-jitter")
    _thread.start()
    log.info("Mock jitter thread started (interval=%ds).", settings.jitter_interval)


def _loop() -> None:
    while True:
        time.sleep(settings.jitter_interval)
        _apply_jitter()


def _apply_jitter() -> None:
    """Apply a small random delta to every mock desk."""
    now = datetime.utcnow().isoformat()

    with state.store_lock:
        for data in state.desk_store.values():
            if not data["is_mock"]:
                continue

            new_noise = data["_base_noise"] + random.randint(-5, 5)
            new_noise = max(25, min(90, new_noise))

            new_temp = data["_base_temp"] + round(random.uniform(-0.5, 0.5), 1)
            new_temp = round(max(16.0, min(30.0, new_temp)), 1)

            # 5 % chance of occupancy flip per tick
            if random.random() < 0.05:
                data["occupied"] = 1 - data["occupied"]

            data["noise_db"]     = new_noise
            data["temp_c"]       = new_temp
            data["last_updated"] = now

    # Record jittered values to in-memory history
    all_desks = state.get_all_desks(strip_private=False)
    for desk in all_desks:
        if not desk.get("is_mock"):
            continue
        state.record_history(desk["desk_id"], {
            "ts":       now,
            "occupied": desk["occupied"],
            "noise_db": desk["noise_db"],
            "temp_c":   desk["temp_c"],
        })
