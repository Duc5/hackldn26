import importlib
import os
import sys
from collections import defaultdict, deque
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure backend root is importable even when pytest is started from repo root.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ["MONGODB_REQUIRED"] = "0"
os.environ["SIMULATION_ENABLED"] = "1"

from app.core.config import settings
from app.services import state


@pytest.fixture(autouse=True)
def reset_state():
    state.desk_store.clear()
    state.desk_history = defaultdict(lambda: deque(maxlen=settings.history_maxlen))
    yield
    state.desk_store.clear()
    state.desk_history.clear()


@pytest.fixture
def client():
    if "main" in sys.modules:
        importlib.reload(sys.modules["main"])
        app = sys.modules["main"].app
    else:
        from main import app

    with TestClient(app) as test_client:
        yield test_client
