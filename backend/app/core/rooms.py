"""
app/core/rooms.py
──────────────────
Static room configuration. Add / remove rooms here.
Each room has a label and a desk capacity (total desks shown in the heatmap).
Real Arduino desks fill slots first; mock desks fill the remainder.
"""

ROOM_CONFIG: dict[str, dict] = {
    "room_a": {"label": "Floor 3 — Quiet Zone",    "capacity": 6},
    "room_b": {"label": "Ground Floor — Social",    "capacity": 6},
    "room_c": {"label": "Level 2 — Collaborative", "capacity": 6},
}

# Status thresholds
OCCUPANCY_BUSY_THRESHOLD: float = 0.70   # ≥ 70 % occupied  → "Busy"
NOISE_LOUD_THRESHOLD:     int   = 65     # ≥ 65 dB           → "Loud"
