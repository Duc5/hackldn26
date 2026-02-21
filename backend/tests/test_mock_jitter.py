from app.services import mock_jitter, state


def test_jitter_updates_only_mock_desks(monkeypatch):
    state.ensure_desk("desk_mock", "room_a", is_mock=True)
    state.ensure_desk("desk_real", "room_a", is_mock=False)

    state.update_desk("desk_mock", occupied=0, noise_db=30, temp_c=20.0)
    state.update_desk("desk_real", occupied=1, noise_db=50, temp_c=23.0)

    with state.store_lock:
        state.desk_store["desk_mock"]["_base_noise"] = 60
        state.desk_store["desk_mock"]["_base_temp"] = 22.0

    monkeypatch.setattr(mock_jitter.random, "randint", lambda _a, _b: 0)
    monkeypatch.setattr(mock_jitter.random, "uniform", lambda _a, _b: 0.0)
    monkeypatch.setattr(mock_jitter.random, "random", lambda: 0.0)  # force occupancy flip

    mock_jitter._apply_jitter()

    mock_desk = state.get_desk("desk_mock")
    real_desk = state.get_desk("desk_real")

    assert mock_desk is not None and real_desk is not None
    assert mock_desk["occupied"] == 1
    assert mock_desk["noise_db"] == 60
    assert mock_desk["temp_c"] == 22.0

    assert real_desk["occupied"] == 1
    assert real_desk["noise_db"] == 50
    assert real_desk["temp_c"] == 23.0
