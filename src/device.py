from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class DeviceProfile:
    frequency_mhz: float
    encoding: str
    timing: dict
    commands: dict[str, str]
    units: dict[str, dict]

    @classmethod
    def load(cls, path: str) -> "DeviceProfile":
        data = yaml.safe_load(Path(path).read_text())
        return cls(
            frequency_mhz=data["frequency_mhz"],
            encoding=data["encoding"],
            timing=data["timing"],
            commands=data.get("commands", {}),
            units=data["units"],
        )


def build_packet(profile: DeviceProfile, unit: str, command: str) -> str:
    """Return the full 32-bit bit string for a given unit and command.

    Raises KeyError if unit or command is not in the profile.
    """
    address = profile.units[unit]["address"]  # KeyError on unknown unit
    command_bits = profile.commands[command]  # KeyError on unknown command
    return address + command_bits


_TIMING_KEYS = (
    "sync_us",
    "sync_gap_us",
    "pulse_us",
    "zero_gap_us",
    "one_gap_us",
    "repeat_count",
)


def build_transmit_payload(profile: DeviceProfile, bits: str) -> dict:
    """Return the JSON-ready payload for POST /transmit.

    Raises ValueError if bits is empty or contains non-binary characters.
    """
    if not bits:
        raise ValueError("bits must be non-empty")
    if not set(bits).issubset({"0", "1"}):
        raise ValueError("bits must contain only '0' and '1'")
    timing = {k: profile.timing[k] for k in _TIMING_KEYS}
    return {"bits": bits, "timing": timing}


# PT2260 tri-state symbols → two (level-duration) pulse halves each.
# Sync is a short HIGH followed by the long inter-frame gap; it is
# appended LAST so repeats are contiguous valid codewords and the
# TX pin is always left LOW.
_PT2260_SYMBOLS = {
    "0": (("short", "long"), ("short", "long")),
    "1": (("long", "short"), ("long", "short")),
    "F": (("short", "long"), ("long", "short")),
}


def pt2260_pulses(code: str, timing: dict) -> list[tuple[int, int]]:
    """Encode a PT2260 tri-state code string as [(high_us, low_us), ...]."""
    duration = {"short": timing["short_us"], "long": timing["long_us"]}
    pulses: list[tuple[int, int]] = []
    for symbol in code:
        if symbol not in _PT2260_SYMBOLS:
            raise ValueError(f"invalid PT2260 symbol {symbol!r} (want 0/1/F)")
        for high, low in _PT2260_SYMBOLS[symbol]:
            pulses.append((duration[high], duration[low]))
    pulses.append((timing["short_us"], timing["sync_gap_us"]))
    return pulses


def resolve_code(profile: DeviceProfile, unit: str, command: str) -> str:
    """Full tri-state code for a unit+command.

    PT2260 profiles keep whole codes per unit (no address/command split —
    see the design spec); this is the only function that knows that.
    """
    return profile.units[unit]["codes"][command]  # KeyError on unknown names


# Limits mirror firmware/src/main.cpp exactly so bad payloads fail here
# with a readable message instead of a NodeMCU 400 (or a watchdog reset).
MAX_PULSE_PAIRS = 256
MAX_PULSE_US = 100_000
MAX_TOTAL_US = 5_000_000  # repeat_count x sum(high+low) busy-waits the ESP8266


def build_pulses_payload(pulses: list[tuple[int, int]], repeat_count: int) -> dict:
    """JSON-ready body for POST /transmit (pulse-train shape)."""
    if not pulses:
        raise ValueError("pulses must contain at least one (high_us, low_us) pair")
    if len(pulses) > MAX_PULSE_PAIRS:
        raise ValueError(f"too many pulse pairs ({len(pulses)}), max {MAX_PULSE_PAIRS}")
    if not 1 <= repeat_count <= 100:
        raise ValueError(f"repeat_count must be 1..100, got {repeat_count}")
    total_us = 0
    for high_us, low_us in pulses:
        for value in (high_us, low_us):
            if not 1 <= value <= MAX_PULSE_US:
                raise ValueError(
                    f"pulse durations must be 1..{MAX_PULSE_US} µs, got {value}"
                )
        total_us += high_us + low_us
    if total_us * repeat_count > MAX_TOTAL_US:
        raise ValueError(
            f"transmission exceeds duration budget: {total_us * repeat_count} µs "
            f"> {MAX_TOTAL_US} µs (would busy-wait the ESP8266 into a watchdog reset)"
        )
    return {
        "pulses": [[high, low] for high, low in pulses],
        "repeat_count": repeat_count,
    }


def build_payload_for(profile: DeviceProfile, unit: str, command: str) -> dict:
    """Build the right POST /transmit body for this profile's encoding."""
    if profile.encoding == "PT2260":
        code = resolve_code(profile, unit, command)
        pulses = pt2260_pulses(code, profile.timing)
        return build_pulses_payload(pulses, profile.timing["repeat_count"])
    bits = build_packet(profile, unit=unit, command=command)
    return build_transmit_payload(profile, bits=bits)
