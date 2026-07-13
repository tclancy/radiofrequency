from __future__ import annotations

from src.tpms import db


def test_connect_creates_schema_and_seeds_vehicle(config):
    conn = db.connect(config.db_path)
    try:
        row = conn.execute(
            "SELECT slug, make, model, year, frequency_hz, decoder FROM vehicles"
        ).fetchone()
        assert row["slug"] == "mazda-cx9"
        assert row["make"] == "Mazda"
        assert row["frequency_hz"] == 315_000_000
        assert row["decoder"] == "r156"
    finally:
        conn.close()


def test_connect_is_idempotent(config):
    for _ in range(3):
        conn = db.connect(config.db_path)
        conn.close()
    conn = db.connect(config.db_path)
    try:
        count = conn.execute("SELECT COUNT(*) AS n FROM vehicles").fetchone()["n"]
        assert count == 1
    finally:
        conn.close()


def test_upsert_reading_returns_false_on_duplicate(config):
    conn = db.connect(config.db_path)
    try:
        assert db.upsert_reading(conn, 100, "abc", 220.0, 25.0, 1, "{}") is True
        assert db.upsert_reading(conn, 100, "abc", 220.0, 25.0, 1, "{}") is False
    finally:
        conn.close()


def test_register_sensor_is_idempotent(config):
    conn = db.connect(config.db_path)
    try:
        db.register_sensor(conn, "mazda-cx9", "sensor-A")
        db.register_sensor(conn, "mazda-cx9", "sensor-A")
        ids = db.vehicle_sensor_ids(conn, "mazda-cx9")
        assert ids == ["sensor-A"]
    finally:
        conn.close()


def test_history_bounded_by_since_until(config):
    conn = db.connect(config.db_path)
    try:
        db.register_sensor(conn, "mazda-cx9", "s1")
        db.upsert_reading(conn, 1000, "s1", 200.0, 20.0, 1, "{}")
        db.upsert_reading(conn, 2000, "s1", 210.0, 22.0, 1, "{}")
        db.upsert_reading(conn, 3000, "s1", 220.0, 24.0, 1, "{}")
        rows = db.history_for_vehicle(conn, "mazda-cx9", since=1500, until=2500)
        assert [r["ts"] for r in rows] == [2000]
    finally:
        conn.close()


def test_last_event_ts_empty_returns_none(config):
    conn = db.connect(config.db_path)
    try:
        assert db.last_event_ts(conn) is None
    finally:
        conn.close()
