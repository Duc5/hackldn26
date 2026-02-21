import importlib
import os
import sys
from collections import defaultdict, deque

import pytest
from fastapi.testclient import TestClient

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
