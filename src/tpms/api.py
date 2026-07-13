"""Flask JSON API for the home dashboard to read TPMS state.

Endpoints:
    GET /api/vehicles
        List known vehicles (slice-1: mazda-cx9 only).
    GET /api/vehicles/<slug>/tpms/latest
        Latest reading per sensor, one entry per sensor_id. Empty list is
        legitimate (no readings yet); the client uses `/api/health` to tell
        empty-because-parked from empty-because-broken.
    GET /api/vehicles/<slug>/tpms/history?since=<unix>&until=<unix>&limit=<n>
        Raw readings within the window. Defaults: last 7 days, limit 5000.
    GET /api/health
        Overall health — last event timestamp, receiver_ok flag.

Design notes:
- No auth. LAN-only service, mounted behind whatever the plexpi already fronts.
- One SQLite connection per request keeps thread-safety trivial and lets us
  swap `TPMS_DB` in tests without touching Flask internals.
- Pressure is stored in kPa; response payloads carry both kPa and PSI so the
  dashboard doesn't have to know the conversion.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from flask import Flask, jsonify, request

from . import db
from .config import Config

_KPA_TO_PSI = 0.14503773773


def kpa_to_psi(kpa: float | None) -> float | None:
    return None if kpa is None else round(kpa * _KPA_TO_PSI, 1)


def _serialize_reading(row) -> dict:
    kpa = row["pressure_kpa"]
    return {
        "ts": row["ts"],
        "sensor_id": row["sensor_id"],
        "pressure_kpa": kpa,
        "pressure_psi": kpa_to_psi(kpa),
        "temperature_c": row["temperature_c"],
        "battery_ok": row["battery_ok"],
    }


def create_app(config: Config | None = None) -> Flask:
    cfg = config or Config.from_env()
    app = Flask(__name__)
    app.config["TPMS_CONFIG"] = cfg

    # Init schema once at app startup so per-request connects can skip the
    # `CREATE TABLE IF NOT EXISTS` script and vehicle upsert. The API is a
    # concurrent reader alongside the ingest daemon — extra write-lock traffic
    # per request would contend needlessly on the plexpi SQLite file.
    db.connect(cfg.db_path).close()

    @app.get("/api/vehicles")
    def list_vehicles():
        with _connect(cfg.db_path) as conn:
            rows = conn.execute(
                "SELECT slug, make, model, year, vin, frequency_hz, decoder "
                "FROM vehicles ORDER BY slug"
            ).fetchall()
        return jsonify([dict(r) for r in rows])

    @app.get("/api/vehicles/<slug>/tpms/latest")
    def latest(slug: str):
        with _connect(cfg.db_path) as conn:
            if not _vehicle_exists(conn, slug):
                return jsonify({"error": "unknown vehicle"}), 404
            now = int(time.time())
            sensor_ids = db.vehicle_sensor_ids(conn, slug)
            readings = []
            any_low = False
            all_stale = bool(sensor_ids)
            for sid in sensor_ids:
                row = db.latest_reading_for_sensor(conn, sid)
                if row is None:
                    continue
                item = _serialize_reading(row)
                item["stale"] = (now - row["ts"]) > cfg.stale_seconds
                if not item["stale"]:
                    all_stale = False
                if (
                    item["pressure_psi"] is not None
                    and item["pressure_psi"] < cfg.low_psi
                ):
                    any_low = True
                readings.append(item)
        return jsonify(
            {
                "slug": slug,
                "readings": readings,
                "any_low": any_low,
                "all_stale": all_stale,
                "low_psi_threshold": cfg.low_psi,
            }
        )

    @app.get("/api/vehicles/<slug>/tpms/history")
    def history(slug: str):
        now = int(time.time())
        since = int(request.args.get("since", now - 7 * 86400))
        until = int(request.args.get("until", now))
        limit = min(int(request.args.get("limit", 5000)), 20000)
        with _connect(cfg.db_path) as conn:
            if not _vehicle_exists(conn, slug):
                return jsonify({"error": "unknown vehicle"}), 404
            rows = db.history_for_vehicle(conn, slug, since, until, limit)
        return jsonify(
            {
                "slug": slug,
                "since": since,
                "until": until,
                "count": len(rows),
                "readings": [_serialize_reading(r) for r in rows],
            }
        )

    @app.get("/api/health")
    def health():
        with _connect(cfg.db_path) as conn:
            last = db.last_event_ts(conn)
        now = int(time.time())
        receiver_ok = last is not None and (now - last) <= cfg.stale_seconds
        return jsonify(
            {
                "last_event_ts": last,
                "receiver_ok": receiver_ok,
                "stale_seconds": cfg.stale_seconds,
                "now": now,
            }
        )

    return app


def _connect(db_path: Path) -> sqlite3.Connection:
    """Lightweight read-side connection. Assumes create_app() already ran
    `db.connect` once to init the schema.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _vehicle_exists(conn, slug: str) -> bool:
    row = conn.execute("SELECT 1 FROM vehicles WHERE slug = ?", (slug,)).fetchone()
    return row is not None


def main() -> int:  # pragma: no cover
    app = create_app()
    app.run(host="0.0.0.0", port=8090)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
