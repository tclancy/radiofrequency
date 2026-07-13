"""Ingest daemon — reads rtl_433 JSON events from stdin, writes to SQLite.

rtl_433 emits one JSON object per line when invoked with `-F json`. This module
parses each line, filters to the configured vehicle's decoder, normalizes the
fields we care about, and upserts a reading.

Non-matching lines (other decoders, malformed JSON, log messages) are logged and
skipped — the daemon must not exit on a bad line or the whole capture pipeline
stops.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import sys
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import IO

from . import db
from .config import Config

log = logging.getLogger(__name__)

_VEHICLE_SLUG = "mazda-cx9"


def parse_event(line: str) -> dict | None:
    """Return the parsed dict for a rtl_433 JSON line, or None if unusable.

    Returning None (not raising) is intentional — the daemon must survive bad
    lines without dropping the pipe.
    """
    line = line.strip()
    if not line:
        return None
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        log.warning("skipping non-JSON line: %.120s", line)
        return None


def is_target_vehicle(event: dict) -> bool:
    """Match rtl_433 model to the Mazda VDO decoder.

    The comparison is case-insensitive because the model string varies across
    rtl_433 versions (e.g. `Abarth-124Spider`, `Abarth 124Spider`).
    """
    model = (
        str(event.get("model", ""))
        .lower()
        .replace("-", "")
        .replace(" ", "")
        .replace("_", "")
    )
    return model == "abarth124spider"


def _psi_to_kpa(psi: float) -> float:
    return psi * 6.8947572932


def normalize(event: dict, now: datetime | None = None) -> dict | None:
    """Extract the fields we store from an rtl_433 event.

    Returns a dict of {ts, sensor_id, pressure_kpa, temperature_c, battery_ok, raw_json}
    or None if the event lacks the identifying fields we need.
    """
    sensor_id = event.get("id")
    if sensor_id is None:
        return None
    sensor_id = str(sensor_id)

    ts = _parse_time(event, now)

    pressure_kpa: float | None
    if "pressure_kPa" in event:
        pressure_kpa = float(event["pressure_kPa"])
    elif "pressure_kpa" in event:
        pressure_kpa = float(event["pressure_kpa"])
    elif "pressure_PSI" in event:
        pressure_kpa = _psi_to_kpa(float(event["pressure_PSI"]))
    else:
        pressure_kpa = None

    temperature_c: float | None
    if "temperature_C" in event:
        temperature_c = float(event["temperature_C"])
    elif "temperature_c" in event:
        temperature_c = float(event["temperature_c"])
    else:
        temperature_c = None

    battery_ok = _parse_battery(event)

    return {
        "ts": ts,
        "sensor_id": sensor_id,
        "pressure_kpa": pressure_kpa,
        "temperature_c": temperature_c,
        "battery_ok": battery_ok,
        "raw_json": json.dumps(event, sort_keys=True),
    }


def _parse_time(event: dict, now: datetime | None) -> int:
    """Parse rtl_433's `time` string into unix seconds UTC.

    rtl_433 emits `time` as `YYYY-MM-DD HH:MM:SS` — **assumed to be UTC** because
    the capture unit invokes rtl_433 with `-M utc` (see deploy/plexpi/tpms-
    capture.service). Without `-M utc`, rtl_433 emits system-local time with no
    tz suffix, which would silently skew every reading by the local UTC offset.
    If the field is missing or unparseable, fall back to injected `now` (or the
    current wall clock).
    """
    raw = event.get("time")
    if isinstance(raw, str):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                dt = datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
                return int(dt.timestamp())
            except ValueError:
                continue
    if now is None:
        now = datetime.now(tz=timezone.utc)
    return int(now.timestamp())


def _parse_battery(event: dict) -> int | None:
    """Battery arrives as `battery_ok: 1` in newer rtl_433, `battery: "OK"` in older."""
    if "battery_ok" in event:
        return 1 if event["battery_ok"] else 0
    if "battery" in event:
        return 1 if str(event["battery"]).lower() == "ok" else 0
    return None


def process_line(conn: sqlite3.Connection, line: str) -> bool:
    """Parse + persist one line. Return True if a new reading was written."""
    event = parse_event(line)
    if event is None:
        return False
    if not is_target_vehicle(event):
        return False
    normalized = normalize(event)
    if normalized is None:
        return False
    db.register_sensor(conn, _VEHICLE_SLUG, normalized["sensor_id"])
    written = db.upsert_reading(
        conn,
        ts=normalized["ts"],
        sensor_id=normalized["sensor_id"],
        pressure_kpa=normalized["pressure_kpa"],
        temperature_c=normalized["temperature_c"],
        battery_ok=normalized["battery_ok"],
        raw_json=normalized["raw_json"],
    )
    if written:
        log.info(
            "tpms reading id=%s kpa=%s c=%s",
            normalized["sensor_id"],
            normalized["pressure_kpa"],
            normalized["temperature_c"],
        )
    return written


def run(
    stream: IO[str] | Iterable[str] = sys.stdin,
    config: Config | None = None,
) -> int:
    """Consume the stream to EOF. Returns the number of new readings written."""
    cfg = config or Config.from_env()
    conn = db.connect(cfg.db_path)
    try:
        written = 0
        for line in stream:
            try:
                if process_line(conn, line):
                    written += 1
            except Exception:  # pragma: no cover - defensive
                log.exception("failed to process line: %.120s", line.strip())
        return written
    finally:
        conn.close()


def main() -> int:  # pragma: no cover - thin CLI wrapper
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    run()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
