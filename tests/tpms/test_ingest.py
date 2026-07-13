from __future__ import annotations

import io

from src.tpms import db, ingest

from . import fixtures


def test_parse_event_survives_non_json():
    assert ingest.parse_event(fixtures.MALFORMED_LINE) is None
    assert ingest.parse_event("") is None
    assert ingest.parse_event("   \n") is None


def test_is_target_vehicle_matches_variants():
    for model in ("Abarth-124Spider", "Abarth 124Spider", "abarth_124spider"):
        assert ingest.is_target_vehicle({"model": model})
    assert not ingest.is_target_vehicle({"model": "Somfy-RTS"})
    assert not ingest.is_target_vehicle({})


def test_normalize_extracts_pressure_and_temperature():
    event = fixtures.SAMPLE_EVENT.copy()
    normalized = ingest.normalize(event)
    assert normalized is not None
    assert normalized["sensor_id"] == "6ec8f7a1"
    assert normalized["pressure_kpa"] == 220.0
    assert normalized["temperature_c"] == 28.5
    assert normalized["battery_ok"] == 1
    assert normalized["ts"] > 0


def test_normalize_converts_psi_to_kpa():
    event = {
        "time": "2026-07-12 19:30:00",
        "model": "Abarth-124Spider",
        "id": "abc",
        "pressure_PSI": 32.0,
    }
    normalized = ingest.normalize(event)
    assert normalized is not None
    assert normalized["pressure_kpa"] == 32.0 * 6.8947572932


def test_normalize_missing_id_returns_none():
    assert ingest.normalize({"model": "Abarth-124Spider"}) is None


def test_normalize_handles_old_battery_field():
    event = fixtures.SAMPLE_EVENT.copy()
    del event["battery_ok"]
    event["battery"] = "OK"
    normalized = ingest.normalize(event)
    assert normalized is not None
    assert normalized["battery_ok"] == 1

    event["battery"] = "LOW"
    normalized = ingest.normalize(event)
    assert normalized is not None
    assert normalized["battery_ok"] == 0


def test_run_writes_matching_events(config):
    stream = io.StringIO(
        "".join(
            [
                fixtures.sample_line(),
                fixtures.NON_TARGET_LINE,
                fixtures.MALFORMED_LINE,
                fixtures.sample_line(id="7fa22b03", **{"pressure_kPa": 210.0}),
            ]
        )
    )
    written = ingest.run(stream, config=config)
    assert written == 2

    conn = db.connect(config.db_path)
    try:
        rows = conn.execute(
            "SELECT sensor_id, pressure_kpa FROM readings ORDER BY sensor_id"
        ).fetchall()
        assert [r["sensor_id"] for r in rows] == ["6ec8f7a1", "7fa22b03"]
        ids = db.vehicle_sensor_ids(conn, "mazda-cx9")
        assert ids == ["6ec8f7a1", "7fa22b03"]
    finally:
        conn.close()


def test_duplicate_events_are_deduped(config):
    line = fixtures.sample_line()
    stream = io.StringIO(line + line + line)
    assert ingest.run(stream, config=config) == 1
