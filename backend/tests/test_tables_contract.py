EXPECTED_TABLE_IDS = {
    "Q1", "Q2", "Q3",
    "R1", "R2", "R3",
    "G1", "G2", "G3", "G4",
    "O1", "O2", "O3", "O4", "O5", "O6", "O7", "O8", "O9",
}


def test_tables_contract_shape_and_ids(client):
    resp = client.get("/api/tables")
    assert resp.status_code == 200
    rows = resp.json()

    assert len(rows) == 19
    assert {row["table_id"] for row in rows} == EXPECTED_TABLE_IDS

    required = {
        "table_id",
        "zone_name",
        "zone_type",
        "total_seats",
        "occupied_seats",
        "available_seats",
        "status",
        "temp_c",
        "room_avg_temp_c",
        "last_updated",
    }

    for row in rows:
        assert set(row.keys()) == required
        assert row["occupied_seats"] in (0, 1)
        assert row["available_seats"] == row["total_seats"] - row["occupied_seats"]

    assert sum(row["total_seats"] for row in rows) == 98
