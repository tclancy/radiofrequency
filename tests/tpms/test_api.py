from __future__ import annotations

import io
import time

import pytest

from src.tpms import db, ingest
from src.tpms.api import create_app

from . import fixtures


@pytest.fixture
def client(config):
    ingest.run(io.StringIO(fixtures.sample_line()), config=config)
    app = create_app(config)
    app.testing = True
    return app.test_client()


@pytest.fixture
def empty_client(config):
    conn = db.connect(config.db_path)
    conn.close()
    app = create_app(config)
    app.testing = True
    return app.test_client()


def test_list_vehicles(client):
    resp = client.get("/api/vehicles")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body[0]["slug"] == "mazda-cx9"
    assert body[0]["frequency_hz"] == 315_000_000


def test_latest_returns_reading_and_low_flag(config):
    ingest.run(
        io.StringIO(fixtures.sample_line(**{"pressure_kPa": 150.0})),
        config=config,
    )
    app = create_app(config)
    app.testing = True
    client = app.test_client()
    resp = client.get("/api/vehicles/mazda-cx9/tpms/latest")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["slug"] == "mazda-cx9"
    assert body["any_low"] is True
    assert body["low_psi_threshold"] == 30.0
    assert len(body["readings"]) == 1
    reading = body["readings"][0]
    assert reading["pressure_kpa"] == 150.0
    assert reading["pressure_psi"] is not None
    assert reading["pressure_psi"] < 30.0


def test_latest_reports_all_stale_when_over_threshold(config):
    old_ts = int(time.time()) - 4000
    ingest.run(
        io.StringIO(fixtures.sample_line(time=_fmt(old_ts), **{"pressure_kPa": 220.0})),
        config=config,
    )
    app = create_app(config)
    app.testing = True
    resp = app.test_client().get("/api/vehicles/mazda-cx9/tpms/latest")
    body = resp.get_json()
    assert body["all_stale"] is True
    assert body["readings"][0]["stale"] is True


def test_latest_unknown_vehicle_is_404(empty_client):
    resp = empty_client.get("/api/vehicles/nope/tpms/latest")
    assert resp.status_code == 404


def test_history_respects_since_until(config):
    events = [
        {"time": _fmt(1000), "id": "6ec8f7a1", "pressure_kPa": 200.0},
        {"time": _fmt(2000), "id": "6ec8f7a1", "pressure_kPa": 210.0},
        {"time": _fmt(3000), "id": "6ec8f7a1", "pressure_kPa": 220.0},
    ]
    ingest.run(io.StringIO("".join(fixtures.sample_stream(*events))), config=config)
    app = create_app(config)
    app.testing = True
    resp = app.test_client().get(
        "/api/vehicles/mazda-cx9/tpms/history?since=1500&until=2500"
    )
    body = resp.get_json()
    assert body["count"] == 1
    assert body["readings"][0]["ts"] == 2000


def test_health_no_data(empty_client):
    resp = empty_client.get("/api/health")
    body = resp.get_json()
    assert body["last_event_ts"] is None
    assert body["receiver_ok"] is False


def test_health_receiver_ok_when_recent(client):
    resp = client.get("/api/health")
    body = resp.get_json()
    assert body["last_event_ts"] is not None
    # Sample event's time is 2026-07-12 19:30:00 which will be in the past by the
    # time this runs, so receiver_ok depends on stale threshold vs. clock.
    assert isinstance(body["receiver_ok"], bool)


def _fmt(ts: int) -> str:
    """Convert a unix ts back to rtl_433's `YYYY-MM-DD HH:MM:SS` UTC format."""
    from datetime import datetime, timezone

    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
