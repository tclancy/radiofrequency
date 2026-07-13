"""Derive the PWA's devices.json from the YAML device profiles.

The homelab 22-parsons-remote PWA ships this file so it never duplicates
codes or timings — devices/*.yaml stays the single source of truth.

Usage:
    uv run python scripts/export_web_devices.py > devices.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure the project root is in sys.path so we can import src
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.device import DeviceProfile, build_payload_for


def build_bundle(device_dir: Path) -> dict:
    """Bundle every PT2260 profile's units into PWA-ready payloads."""
    lights = []
    for path in sorted(device_dir.glob("*.yaml")):
        profile = DeviceProfile.load(str(path))
        if profile.encoding != "PT2260":
            continue  # fans et al. stay on their existing endpoints
        for unit_name, unit in profile.units.items():
            lights.append(
                {
                    "unit": unit_name,
                    "label": unit_name.capitalize(),
                    "position": unit["position"],
                    "commands": {
                        command: build_payload_for(profile, unit_name, command)
                        for command in unit["codes"]
                    },
                }
            )
    lights.sort(key=lambda entry: entry["position"])
    return {"lights": lights}


if __name__ == "__main__":
    json.dump(build_bundle(Path("devices")), sys.stdout, indent=2)
    sys.stdout.write("\n")
