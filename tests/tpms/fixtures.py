"""rtl_433 JSON fixtures for TPMS tests.

Shape modeled on real Abarth-124Spider decoder output. Field names track what
rtl_433 emits at CLI (`-F json`) — case matters (`pressure_kPa`, `temperature_C`).
"""

from __future__ import annotations

import json

SAMPLE_EVENT = {
    "time": "2026-07-12 19:30:00",
    "model": "Abarth-124Spider",
    "type": "TPMS",
    "id": "6ec8f7a1",
    "flags": "00",
    "pressure_kPa": 220.0,
    "temperature_C": 28.5,
    "battery_ok": 1,
    "mic": "CRC",
}


def sample_line(**overrides) -> str:
    """Return a single-line JSON event string with optional overrides."""
    event = dict(SAMPLE_EVENT)
    event.update(overrides)
    return json.dumps(event) + "\n"


def sample_stream(*event_overrides: dict) -> list[str]:
    if not event_overrides:
        return [sample_line()]
    return [sample_line(**o) for o in event_overrides]


NON_TARGET_LINE = (
    json.dumps(
        {
            "time": "2026-07-12 19:30:05",
            "model": "Somfy-RTS",
            "id": "12345",
            "code": "0x1234",
        }
    )
    + "\n"
)

MALFORMED_LINE = "this is not JSON\n"
