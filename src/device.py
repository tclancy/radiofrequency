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
