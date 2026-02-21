"""
app/core/rooms.py
Static room configuration. Add / remove rooms here.
"""

ROOM_CONFIG: dict[str, dict] = {
    "room_a": {"label": "Floor 3 - Quiet Zone", "capacity": 6},
    "room_b": {"label": "Ground Floor - Social", "capacity": 6},
    "room_c": {"label": "Level 2 - Collaborative", "capacity": 7},
}

ROOM_ZONE_TYPES: dict[str, str] = {
    "room_a": "quiet",
    "room_b": "mixed",
    "room_c": "group",
}

# Status thresholds
OCCUPANCY_BUSY_THRESHOLD: float = 0.70
NOISE_LOUD_THRESHOLD: int = 65
