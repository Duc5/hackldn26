from app.services import device_registry, serial_reader, state


def test_simulation_clamps_occupied_to_binary(client):
    payload = {"line": "desk_1,4,41,21.3"}
    resp = client.post("/api/sim/serial-line", json=payload)
    assert resp.status_code == 200

    desk = state.get_desk("desk_1")
    assert desk is not None
    assert desk["occupied"] == 1


def test_serial_parse_uses_hardware_id_for_registry_lookup(monkeypatch):
    captured = {"hardware_id": None}

    def fake_get(hw_id: str):
        captured["hardware_id"] = hw_id
        return {"room_id": "room_b"}

    monkeypatch.setattr(device_registry, "get", fake_get)

    serial_reader._parse_and_store("2,44,22.0", "desk_999", "HW:ABC123")

    desk = state.get_desk("desk_999")
    assert desk is not None
    assert captured["hardware_id"] == "HW:ABC123"
    assert desk["room_id"] == "room_b"
    assert desk["occupied"] == 1
