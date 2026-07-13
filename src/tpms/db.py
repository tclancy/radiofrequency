"""SQLite schema + connection helpers for TPMS readings.

Three tables:
- vehicles: one row per vehicle (slug, freq, decoder). Slice-1 seeds Mazda CX-9 only.
- sensors:  one row per known physical sensor. Position is nullable — slice-1 does not
            map sensor→corner (Tom's answer to Q4: any-tire-low is sufficient).
- readings: one row per rtl_433 event. Primary key (ts, sensor_id) drops perfect dupes
            without a UNIQUE index round-trip.

`connect` is idempotent: safe to re-call on every ingest event.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 1

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS vehicles (
    id           INTEGER PRIMARY KEY,
    slug         TEXT UNIQUE NOT NULL,
    make         TEXT NOT NULL,
    model        TEXT NOT NULL,
    year         INTEGER NOT NULL,
    vin          TEXT,
    frequency_hz INTEGER NOT NULL,
    decoder      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sensors (
    vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
    sensor_id  TEXT NOT NULL,
    position   TEXT,
    PRIMARY KEY (vehicle_id, sensor_id)
);

CREATE TABLE IF NOT EXISTS readings (
    ts             INTEGER NOT NULL,
    sensor_id      TEXT NOT NULL,
    pressure_kpa   REAL,
    temperature_c  REAL,
    battery_ok     INTEGER,
    raw_json       TEXT NOT NULL,
    PRIMARY KEY (ts, sensor_id)
);

CREATE INDEX IF NOT EXISTS readings_by_sensor_ts
    ON readings(sensor_id, ts DESC);

CREATE INDEX IF NOT EXISTS readings_by_ts
    ON readings(ts DESC);

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);
"""

# Slice-1 vehicle set. Slug "mazda-cx9" is stable and used by the API path.
# rtl_433 register 156 (Abarth-124Spider) is confirmed working at 315 MHz for the
# Mazda VDO sensors per issue #1 research.
_SEED_VEHICLES = [
    {
        "slug": "mazda-cx9",
        "make": "Mazda",
        "model": "CX-9",
        "year": 2013,
        "vin": "JM3TB3CV0D0420001",
        "frequency_hz": 315_000_000,
        "decoder": "r156",
    },
]


def connect(db_path: Path) -> sqlite3.Connection:
    """Open a connection, ensure schema, seed the vehicle table.

    Runs on every ingest event — SQLite's IF NOT EXISTS keeps this cheap. WAL mode
    lets the API reader concurrent-read while ingest writes.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(_SCHEMA_SQL)
    _seed_vehicles(conn)
    _record_version(conn)
    conn.commit()
    return conn


def _seed_vehicles(conn: sqlite3.Connection) -> None:
    for v in _SEED_VEHICLES:
        conn.execute(
            """
            INSERT INTO vehicles (slug, make, model, year, vin, frequency_hz, decoder)
            VALUES (:slug, :make, :model, :year, :vin, :frequency_hz, :decoder)
            ON CONFLICT(slug) DO UPDATE SET
                make         = excluded.make,
                model        = excluded.model,
                year         = excluded.year,
                vin          = excluded.vin,
                frequency_hz = excluded.frequency_hz,
                decoder      = excluded.decoder
            """,
            v,
        )


def _record_version(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO schema_version (version) VALUES (?) "
        "ON CONFLICT(version) DO NOTHING",
        (SCHEMA_VERSION,),
    )


def upsert_reading(
    conn: sqlite3.Connection,
    ts: int,
    sensor_id: str,
    pressure_kpa: float | None,
    temperature_c: float | None,
    battery_ok: int | None,
    raw_json: str,
) -> bool:
    """Insert a reading; return True if new, False if a duplicate was skipped."""
    cur = conn.execute(
        """
        INSERT INTO readings (ts, sensor_id, pressure_kpa, temperature_c, battery_ok, raw_json)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(ts, sensor_id) DO NOTHING
        """,
        (ts, sensor_id, pressure_kpa, temperature_c, battery_ok, raw_json),
    )
    conn.commit()
    return cur.rowcount > 0


def register_sensor(
    conn: sqlite3.Connection, vehicle_slug: str, sensor_id: str
) -> None:
    """Ensure a `sensors` row exists so the API can enumerate vehicle→sensors.

    Positions stay NULL — slice-1 does not map sensor→corner.
    """
    conn.execute(
        """
        INSERT INTO sensors (vehicle_id, sensor_id, position)
        SELECT id, ?, NULL FROM vehicles WHERE slug = ?
        ON CONFLICT(vehicle_id, sensor_id) DO NOTHING
        """,
        (sensor_id, vehicle_slug),
    )
    conn.commit()


def vehicle_sensor_ids(conn: sqlite3.Connection, slug: str) -> list[str]:
    rows = conn.execute(
        """
        SELECT s.sensor_id
        FROM sensors s
        JOIN vehicles v ON v.id = s.vehicle_id
        WHERE v.slug = ?
        ORDER BY s.sensor_id
        """,
        (slug,),
    ).fetchall()
    return [r["sensor_id"] for r in rows]


def latest_reading_for_sensor(
    conn: sqlite3.Connection, sensor_id: str
) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT ts, sensor_id, pressure_kpa, temperature_c, battery_ok
        FROM readings
        WHERE sensor_id = ?
        ORDER BY ts DESC
        LIMIT 1
        """,
        (sensor_id,),
    ).fetchone()


def history_for_vehicle(
    conn: sqlite3.Connection,
    slug: str,
    since: int,
    until: int,
    limit: int = 5000,
) -> list[sqlite3.Row]:
    # JOIN sensors on (vehicle_id, sensor_id) not sensor_id alone: TPMS sensor
    # IDs aren't globally unique, so if a second vehicle is ever seeded, an
    # overlapping ID would otherwise cross-contaminate the history results.
    return conn.execute(
        """
        SELECT r.ts, r.sensor_id, r.pressure_kpa, r.temperature_c, r.battery_ok
        FROM readings r
        JOIN vehicles v ON v.slug = ?
        JOIN sensors s
          ON s.vehicle_id = v.id
         AND s.sensor_id = r.sensor_id
        WHERE r.ts >= ?
          AND r.ts <= ?
        ORDER BY r.ts DESC
        LIMIT ?
        """,
        (slug, since, until, limit),
    ).fetchall()


def last_event_ts(conn: sqlite3.Connection) -> int | None:
    row = conn.execute("SELECT MAX(ts) AS ts FROM readings").fetchone()
    return row["ts"] if row and row["ts"] is not None else None
