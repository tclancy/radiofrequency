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
            commands=data["commands"],
            units=data["units"],
        )


def build_packet(profile: DeviceProfile, unit: str, command: str) -> str:
    """Return the full 32-bit bit string for a given unit and command.

    Raises KeyError if unit or command is not in the profile.
    """
    address = profile.units[unit]["address"]        # KeyError on unknown unit
    command_bits = profile.commands[command]        # KeyError on unknown command
    return address + command_bits
