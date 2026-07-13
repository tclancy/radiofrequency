# ZAP Lighting Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Control the four Etekcity ZAP outlet lamps (window, couch, speaker, chairs) from the NodeMCU RF server via a generic pulse-train transmit path.

**Architecture:** All PT2260 protocol encoding lives in Python, derived from a YAML device profile; the firmware gains one universal capability — transmit an explicit `[[high_µs, low_µs], ...]` pulse train — and never learns another protocol. Legacy `{bits, timing}` transmit and `/fan/*` routes are untouched.

**Tech Stack:** Python 3.13 + uv + pytest (host side), Arduino/PlatformIO ESP8266 + ArduinoJson 7 (firmware), rtl_433 + RTL-SDR (capture/verification).

**Spec:** `docs/superpowers/specs/2026-07-13-lighting-controls-design.md` — read it before starting.

## Global Constraints

- Work on branch `claude/12-lighting-controls`. Commit after every task; pre-commit hooks must pass.
- Python: always `uv run pytest ...`, never bare pytest/pip.
- TDD: every Python task writes the failing test first and shows it failing.
- Firmware validation limits (spec §4, copy exactly): µs values 1..100000; 1..256 pulse pairs; `repeat_count` 1..100; total-duration budget `repeat_count × Σ(high_us + low_us) ≤ 5,000,000 µs`. Watchdog fed inside the pulse-pair loop.
- Python payload validation mirrors those numbers exactly (spec §3).
- PT2260 sync pair is the LAST element of the pulse train; every pair ends LOW.
- Tri-state code strings use only the characters `0`, `1`, `F`.
- Tasks 6–7 need Tom at the keyboard (button presses, flashing, lamp checks). Everything in Tasks 1–5 runs without hardware.

## Deviation from the spec's YAML sketch (intentional)

The spec sketches `units` + shared `commands` and hedges "the frames are the source of truth." This plan stores the **full 12-symbol code per unit per command** (`units.<name>.codes.on/off`) because the 5LX has 10 buttons against a 4-bit data nibble and the address/data split may not be clean. `resolve_code()` (Task 1) is the single place that knows this schema — if the capture shows a clean factoring we can refactor later without touching the encoder.

---

### Task 1: PT2260 waveform encoder + code resolution

**Files:**
- Modify: `src/device.py`
- Test: `tests/test_device.py`

**Interfaces:**
- Consumes: `DeviceProfile` (existing dataclass in `src/device.py`).
- Produces:
  - `pt2260_pulses(code: str, timing: dict) -> list[tuple[int, int]]` — timing needs keys `short_us`, `long_us`, `sync_gap_us`.
  - `resolve_code(profile: DeviceProfile, unit: str, command: str) -> str`
  - `DeviceProfile.load` tolerates a profile with no top-level `commands` key (PT2260 profiles keep codes under units).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_device.py`:

```python
# --- PT2260 pulse-train encoding ---

from src.device import pt2260_pulses, resolve_code

PT2260_TIMING = {"short_us": 180, "long_us": 540, "sync_gap_us": 5580, "repeat_count": 6}


def _pt2260_profile():
    return DeviceProfile(
        frequency_mhz=433.92,
        encoding="PT2260",
        timing=PT2260_TIMING,
        commands={},
        units={
            "window": {"position": 2, "codes": {"on": "0F1F0F0F1010", "off": "0F1F0F0F1001"}},
        },
    )


def test_pt2260_symbol_waveforms():
    # '0' = 2x (short-high, long-low); '1' = 2x (long-high, short-low);
    # 'F' = (short-high, long-low) then (long-high, short-low); sync pair last.
    assert pt2260_pulses("01F", PT2260_TIMING) == [
        (180, 540), (180, 540),   # 0
        (540, 180), (540, 180),   # 1
        (180, 540), (540, 180),   # F
        (180, 5580),              # sync
    ]


def test_pt2260_full_frame_is_25_pairs():
    # 12 symbols x 2 pulses + 1 sync pair
    assert len(pt2260_pulses("0F1F0F0F1010", PT2260_TIMING)) == 25


def test_pt2260_rejects_invalid_symbol():
    with pytest.raises(ValueError, match="symbol"):
        pt2260_pulses("01X", PT2260_TIMING)


def test_resolve_code_looks_up_unit_command():
    profile = _pt2260_profile()
    assert resolve_code(profile, "window", "on") == "0F1F0F0F1010"


def test_resolve_code_unknown_unit_raises_keyerror():
    with pytest.raises(KeyError):
        resolve_code(_pt2260_profile(), "basement", "on")


def test_profile_load_tolerates_missing_commands(tmp_path):
    yaml_text = (
        "frequency_mhz: 433.92\n"
        "encoding: PT2260\n"
        "timing: {short_us: 180, long_us: 540, sync_gap_us: 5580, repeat_count: 6}\n"
        "units:\n"
        "  window: {position: 2, codes: {'on': '0F1F0F0F1010', 'off': '0F1F0F0F1001'}}\n"
    )
    p = tmp_path / "zap.yaml"
    p.write_text(yaml_text)
    profile = DeviceProfile.load(str(p))
    assert profile.commands == {}
    assert profile.units["window"]["codes"]["off"] == "0F1F0F0F1001"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_device.py -v -k "pt2260 or resolve_code or missing_commands"`
Expected: FAIL — `ImportError: cannot import name 'pt2260_pulses'`

- [ ] **Step 3: Implement in `src/device.py`**

Change one line in `DeviceProfile.load`:

```python
            commands=data.get("commands", {}),
```

Append:

```python
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
```

- [ ] **Step 4: Run the full suite**

Run: `uv run pytest tests/ -v`
Expected: all PASS (new tests plus every pre-existing fan test).

- [ ] **Step 5: Commit**

```bash
git add src/device.py tests/test_device.py
git commit -m "feat(device): PT2260 tri-state pulse-train encoder"
```

---

### Task 2: Pulse payload builder with firmware-mirrored validation

**Files:**
- Modify: `src/device.py`
- Test: `tests/test_device.py`

**Interfaces:**
- Consumes: pulse lists from `pt2260_pulses` (Task 1).
- Produces: `build_pulses_payload(pulses: list[tuple[int, int]], repeat_count: int) -> dict` returning `{"pulses": [[h, l], ...], "repeat_count": n}`; module constants `MAX_PULSE_PAIRS = 256`, `MAX_PULSE_US = 100_000`, `MAX_TOTAL_US = 5_000_000`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_device.py`:

```python
# --- pulses payload validation (mirrors firmware limits exactly) ---

from src.device import build_pulses_payload


def test_pulses_payload_shape():
    payload = build_pulses_payload([(180, 540), (180, 5580)], repeat_count=6)
    assert payload == {"pulses": [[180, 540], [180, 5580]], "repeat_count": 6}


def test_pulses_payload_rejects_empty():
    with pytest.raises(ValueError, match="at least one"):
        build_pulses_payload([], repeat_count=6)


def test_pulses_payload_rejects_too_many_pairs():
    with pytest.raises(ValueError, match="256"):
        build_pulses_payload([(10, 10)] * 257, repeat_count=1)


def test_pulses_payload_rejects_out_of_range_us():
    with pytest.raises(ValueError, match="1..100000"):
        build_pulses_payload([(0, 540)], repeat_count=6)
    with pytest.raises(ValueError, match="1..100000"):
        build_pulses_payload([(180, 100_001)], repeat_count=6)


def test_pulses_payload_rejects_bad_repeat_count():
    for bad in (0, 101):
        with pytest.raises(ValueError, match="repeat_count"):
            build_pulses_payload([(180, 540)], repeat_count=bad)


def test_pulses_payload_rejects_over_duration_budget():
    # 256 pairs x 200ms x 100 reps = 5120s >> 5s budget. The firmware
    # hard-resets on payloads like this (soft WDT ~3.2s); fail locally.
    with pytest.raises(ValueError, match="budget"):
        build_pulses_payload([(100_000, 100_000)] * 256, repeat_count=100)


def test_zap_frame_fits_budget_comfortably():
    pulses = pt2260_pulses("0F1F0F0F1010", PT2260_TIMING)
    payload = build_pulses_payload(pulses, repeat_count=6)
    total_us = sum(h + l for h, l in pulses) * payload["repeat_count"]
    assert total_us < 5_000_000
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_device.py -v -k pulses_payload`
Expected: FAIL — `ImportError: cannot import name 'build_pulses_payload'`

- [ ] **Step 3: Implement in `src/device.py`**

```python
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
                raise ValueError(f"pulse durations must be 1..{MAX_PULSE_US} µs, got {value}")
        total_us += high_us + low_us
    if total_us * repeat_count > MAX_TOTAL_US:
        raise ValueError(
            f"transmission exceeds duration budget: {total_us * repeat_count} µs "
            f"> {MAX_TOTAL_US} µs (would busy-wait the ESP8266 into a watchdog reset)"
        )
    return {"pulses": [[h, l] for h, l in pulses], "repeat_count": repeat_count}
```

- [ ] **Step 4: Run the full suite**

Run: `uv run pytest tests/ -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/device.py tests/test_device.py
git commit -m "feat(device): pulses payload builder with firmware-mirrored limits"
```

---

### Task 3: Firmware — pulse-train body shape on POST /transmit

**Files:**
- Modify: `firmware/src/main.cpp` (handler starts at `handleTransmit()`, ~line 107)

**Interfaces:**
- Consumes: JSON body `{"pulses": [[high_us, low_us], ...], "repeat_count": N}` (exactly what Task 2 emits).
- Produces: HTTP 200 `OK <pairs> pairs x <reps> reps`; legacy `{bits, timing}` shape and all `/fan/*` routes unchanged.

No host-side unit test exists for firmware; the "test" is a clean compile (Step 3) and the Task 7 bench capture. Do not refactor the legacy paths.

- [ ] **Step 1: Add the pulse-train transmitter after `transmitGeneric` (~line 101)**

```cpp
// Fully generic transmit: an explicit train of (high_us, low_us) pairs.
// This is the last protocol-shaped capability the firmware should ever
// need — PDM, PWM, tri-state etc. are all just pulse trains to the pin.
// Every pair ends LOW, so the pin is always left LOW.
void transmitPulses(JsonArrayConst pairs, int repeat_count) {
    for (int r = 0; r < repeat_count; r++) {
        for (JsonArrayConst pair : pairs) {
            digitalWrite(TX_PIN, HIGH);
            delayMicroseconds(pair[0].as<uint32_t>());
            digitalWrite(TX_PIN, LOW);
            delayMicroseconds(pair[1].as<uint32_t>());
            // Fed per pair, not per repetition: delayMicroseconds() is a
            // busy-wait and the soft WDT fires at ~3.2 s.
            ESP.wdtFeed();
        }
    }
}
```

- [ ] **Step 2: Route and validate the new body shape in `handleTransmit()`**

Insert immediately after the `deserializeJson` error check (after the `if (err) {...}` block), before the `const char *bits = ...` line:

```cpp
    // New body shape: {"pulses": [[high_us, low_us], ...], "repeat_count": N}
    if (doc["pulses"].is<JsonArray>()) {
        JsonArrayConst pairs = doc["pulses"].as<JsonArrayConst>();
        size_t n = pairs.size();
        if (n == 0 || n > 256) {
            server.send(400, "text/plain", "pulses must be 1..256 pairs\n");
            return;
        }
        int repeat_count = doc["repeat_count"] | 0;
        if (repeat_count < 1 || repeat_count > 100) {
            server.send(400, "text/plain", "repeat_count must be 1..100\n");
            return;
        }
        uint64_t total_us = 0;
        for (JsonArrayConst pair : pairs) {
            if (pair.size() != 2) {
                server.send(400, "text/plain", "each pulse must be [high_us, low_us]\n");
                return;
            }
            uint32_t high_us = pair[0] | 0u;
            uint32_t low_us  = pair[1] | 0u;
            if (high_us == 0 || high_us > 100000 || low_us == 0 || low_us > 100000) {
                server.send(400, "text/plain", "pulse durations must be 1..100000 us\n");
                return;
            }
            total_us += high_us + low_us;
        }
        // Budget: worst-case limits would otherwise allow a 51 s busy-wait
        // in a single repetition — far past the ~3.2 s soft watchdog.
        if (total_us * (uint64_t)repeat_count > 5000000ULL) {
            server.send(400, "text/plain", "transmission exceeds 5 s duration budget\n");
            return;
        }
        transmitPulses(pairs, repeat_count);
        String reply = String("OK ") + n + " pairs x " + repeat_count + " reps\n";
        server.send(200, "text/plain", reply);
        return;
    }
```

- [ ] **Step 3: Compile**

Run: `cd firmware && pio run`
Expected: `SUCCESS` (no upload yet — flashing happens in Task 7 with Tom present).
If `pio` is not on PATH: `export PATH="$HOME/.local/bin:/opt/homebrew/bin:$PATH"` first; it may also live at `~/.platformio/penv/bin/pio`.

- [ ] **Step 4: Update the endpoint banner in `setup()`**

Change the existing line:

```cpp
    Serial.println("  POST http://ceilingfans.local/transmit                (generic bits + timing)");
```

to:

```cpp
    Serial.println("  POST http://ceilingfans.local/transmit                (bits+timing, or pulses+repeat_count)");
```

- [ ] **Step 5: Re-compile, then commit**

Run: `cd firmware && pio run` — Expected: `SUCCESS`.

```bash
git add firmware/src/main.cpp
git commit -m "feat(firmware): generic pulse-train shape on POST /transmit"
```

---

### Task 4: Route profiles through one payload chooser; wire the CLI

**Files:**
- Modify: `src/device.py`, `cli.py` (in `send`, the `build_packet`/`build_transmit_payload` pair, ~lines 60-69)
- Test: `tests/test_device.py`

**Interfaces:**
- Consumes: everything from Tasks 1–2.
- Produces: `build_payload_for(profile: DeviceProfile, unit: str, command: str) -> dict` — returns the pulses payload for `encoding == "PT2260"`, the legacy bits payload otherwise. `cli.py send` calls only this.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_device.py`:

```python
# --- payload routing by encoding ---

from src.device import build_payload_for


def test_payload_for_pt2260_profile_is_pulse_shaped():
    payload = build_payload_for(_pt2260_profile(), "window", "on")
    assert set(payload) == {"pulses", "repeat_count"}
    assert payload["repeat_count"] == 6
    assert len(payload["pulses"]) == 25
    assert payload["pulses"][-1] == [180, 5580]  # sync pair last


def test_payload_for_fan_profile_unchanged(profile):
    payload = build_payload_for(profile, "main", "light")
    assert set(payload) == {"bits", "timing"}
    assert payload == build_transmit_payload(
        profile, bits=build_packet(profile, unit="main", command="light")
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_device.py -v -k payload_for`
Expected: FAIL — `ImportError: cannot import name 'build_payload_for'`

- [ ] **Step 3: Implement in `src/device.py`**

```python
def build_payload_for(profile: DeviceProfile, unit: str, command: str) -> dict:
    """Build the right POST /transmit body for this profile's encoding."""
    if profile.encoding == "PT2260":
        code = resolve_code(profile, unit, command)
        pulses = pt2260_pulses(code, profile.timing)
        return build_pulses_payload(pulses, profile.timing["repeat_count"])
    bits = build_packet(profile, unit=unit, command=command)
    return build_transmit_payload(profile, bits=bits)
```

- [ ] **Step 4: Use it in `cli.py`**

In `send`, replace the two-step `bits = build_packet(...)` / `payload = build_transmit_payload(profile, bits=bits)` sequence with:

```python
    payload = build_payload_for(profile, unit=unit, command=command)
```

and update the import line to pull `build_payload_for` from `src.device` (keep existing imports that `raw` still uses; drop any that become unused — ruff will flag them).

- [ ] **Step 5: Run the full suite (covers tests/test_cli.py regressions)**

Run: `uv run pytest tests/ -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add src/device.py cli.py tests/test_device.py
git commit -m "feat(cli): route PT2260 profiles through pulse-train payloads"
```

---

### Task 5: Derived web bundle — scripts/export_web_devices.py

**Files:**
- Create: `scripts/export_web_devices.py`
- Test: `tests/test_export_web_devices.py`

**Interfaces:**
- Consumes: `DeviceProfile.load`, `build_payload_for` (Task 4).
- Produces: `build_bundle(device_dir: Path) -> dict` and a `__main__` that prints JSON to stdout. Bundle shape (what the homelab PWA will consume — keep stable):

```json
{
  "lights": [
    {
      "unit": "window",
      "label": "Window",
      "position": 2,
      "commands": {
        "on":  {"pulses": [[180, 540], "..."], "repeat_count": 6},
        "off": {"pulses": [[180, 540], "..."], "repeat_count": 6}
      }
    }
  ]
}
```

- [ ] **Step 1: Write the failing test**

Create `tests/test_export_web_devices.py`:

```python
import json
from pathlib import Path

from scripts.export_web_devices import build_bundle

ZAP_YAML = """\
frequency_mhz: 433.92
encoding: PT2260
timing: {short_us: 180, long_us: 540, sync_gap_us: 5580, repeat_count: 6}
units:
  couch:  {position: 3, codes: {'on': '0F1F0F0F1100', 'off': '0F1F0F0F0011'}}
  window: {position: 2, codes: {'on': '0F1F0F0F1010', 'off': '0F1F0F0F1001'}}
"""

FAN_YAML_PATH = Path("devices/sofa_king_fan.yaml")


def test_bundle_exports_pt2260_units_sorted_by_position(tmp_path):
    (tmp_path / "zap_lights.yaml").write_text(ZAP_YAML)
    # Non-PT2260 profiles are skipped (fans stay on their GET endpoints).
    (tmp_path / "fan.yaml").write_text(FAN_YAML_PATH.read_text())

    bundle = build_bundle(tmp_path)

    assert [u["unit"] for u in bundle["lights"]] == ["window", "couch"]
    window = bundle["lights"][0]
    assert window["label"] == "Window"
    assert window["position"] == 2
    assert window["commands"]["on"]["repeat_count"] == 6
    assert len(window["commands"]["on"]["pulses"]) == 25
    json.dumps(bundle)  # must be JSON-serializable as-is
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_export_web_devices.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.export_web_devices'`
(If `scripts/` lacks an `__init__.py` and the import fails for that reason instead, create an empty `scripts/__init__.py` — same as `tests/`.)

- [ ] **Step 3: Implement `scripts/export_web_devices.py`**

```python
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
```

- [ ] **Step 4: Run the full suite**

Run: `uv run pytest tests/ -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/export_web_devices.py tests/test_export_web_devices.py
git commit -m "feat(scripts): derive PWA devices.json from YAML profiles"
```

---

### Task 6: Capture the remote and write the real device profile — TOM REQUIRED

**Files:**
- Create: `devices/zap_lights.yaml`, `captures/zap_remote_pos{2-5}_{on,off}.cu8`
- Modify: `PROTOCOL.md` (append a ZAP section)
- Test: `tests/test_device.py`

This is the physical gate. Tom presses buttons; the agent runs commands and records results.

- [ ] **Step 1: Capture all 8 buttons**

For each of positions 2–5, ON then OFF (8 recordings):

```bash
export PATH="$HOME/.local/bin:/opt/homebrew/bin:$PATH"
rtl_433 -f 433.92M -A -S unknown
# Tom presses ONE button for ~1 second, then Ctrl-C.
# -A prints the pulse analysis live; -S unknown writes g###_433.92M_250k.cu8
# into the current directory. Rename each to captures/zap_remote_pos<N>_<on|off>.cu8
```

Record for each button: the tri-state code (rtl_433 -A prints PWM pulse widths and often the decoded row), measured short pulse µs, long pulse µs, and sync gap µs.
Fallback ladder if `-A` output is ambiguous: URH (`brew install urh`) → upload the .cu8 to triq.org/pdv → Audacity on an AM-demod recording (the fan workflow).

- [ ] **Step 2: Sanity-check the 8 codes against each other**

Expected pattern per issue #10 research: a shared 8-symbol prefix (remote address) with per-button variation in the tail. If the split is NOT clean, nothing changes — the YAML stores full codes anyway. Note whatever structure appears in PROTOCOL.md.

- [ ] **Step 3: Write `devices/zap_lights.yaml` with the measured values**

Template — replace every `MEASURED` with numbers from Step 1 and every `CODE` with the captured 12-symbol strings:

```yaml
# Etekcity ZAP 5LX outlet remote — RF Device Profile
# Encoding: PT2260-family tri-state OOK PWM (HS2260A-R4 encoder)
# Codes captured from OUR living-room remote on 2026-XX-XX — see PROTOCOL.md.
# Positions 2-5 drive the living room lamps; outlets are learning-code
# receivers paired to this remote.

frequency_mhz: 433.92   # documentation-only: the MX-FS-03V TX is SAW-locked here
encoding: PT2260

timing:
  short_us: MEASURED    # 1-alpha segment
  long_us: MEASURED     # 3-alpha segment (~3x short_us)
  sync_gap_us: MEASURED # long LOW after the sync pulse (~31x short_us)
  repeat_count: 6       # remote repeats while held; receiver needs a few clean ones

# Full 12-symbol tri-state code per button (no address/command factoring —
# the capture is the source of truth; see the design spec deviation note).
units:
  window:
    position: 2
    codes: {"on": "CODE", "off": "CODE"}
  couch:
    position: 3
    codes: {"on": "CODE", "off": "CODE"}
  speaker:
    position: 4
    codes: {"on": "CODE", "off": "CODE"}
  chairs:
    position: 5
    codes: {"on": "CODE", "off": "CODE"}
```

- [ ] **Step 4: Write the failing test, then make it pass with the real file**

Append to `tests/test_device.py`:

```python
# --- real ZAP profile ---

ZAP_PROFILE_PATH = "devices/zap_lights.yaml"


@pytest.fixture
def zap_profile():
    return DeviceProfile.load(ZAP_PROFILE_PATH)


def test_zap_profile_has_all_four_lamps(zap_profile):
    assert set(zap_profile.units) == {"window", "couch", "speaker", "chairs"}


def test_zap_all_eight_buttons_encode(zap_profile):
    for unit, spec in zap_profile.units.items():
        for command in ("on", "off"):
            payload = build_payload_for(zap_profile, unit, command)
            assert len(payload["pulses"]) == 25, f"{unit}/{command}"
            assert payload["repeat_count"] == zap_profile.timing["repeat_count"]


def test_zap_codes_are_twelve_tristate_symbols(zap_profile):
    for unit, spec in zap_profile.units.items():
        for command, code in spec["codes"].items():
            assert len(code) == 12, f"{unit}/{command}"
            assert set(code).issubset({"0", "1", "F"}), f"{unit}/{command}"
```

Run: `uv run pytest tests/test_device.py -v -k zap` — Expected: PASS (fails only if the YAML is malformed, which is the point).

- [ ] **Step 5: Document in PROTOCOL.md**

Append a `## Etekcity ZAP 5LX (lighting outlets)` section: measured timings, the 8 codes in a table (position / on / off), observed address/data structure, capture filenames, and the rtl_433 command used.

- [ ] **Step 6: Commit**

```bash
git add devices/zap_lights.yaml captures/zap_remote_*.cu8 PROTOCOL.md tests/test_device.py
git commit -m "feat(devices): ZAP 5LX lighting profile from live capture"
```

(If the .cu8 files are large, check `git ls-files captures/` first — the fan-era WAVs are committed, so captures belong in git per repo convention.)

---

### Task 7: Flash, bench-verify, and switch real lamps — TOM REQUIRED

**Files:** none created (verification task; findings go in PROTOCOL.md if timings need adjustment).

- [ ] **Step 1: Flash the firmware**

```bash
cd firmware && pio run -t upload
# NodeMCU on USB; if the port isn't auto-found: pio device list
```

- [ ] **Step 2: Bench proof — capture the NodeMCU's own transmission**

Terminal A: `rtl_433 -f 433.92M -A -S unknown`
Terminal B: `uv run python cli.py send zap_lights window on`
Compare the analyzer output against the remote's Step-1 capture for the same button: same code, pulse widths within ~10%. This is the same technique that validated the fans (`captures/nodemcu_main_light.wav`). If widths drift, adjust `timing:` in the YAML (never the firmware) and re-send.

- [ ] **Step 3: End-to-end — all 8 buttons against real lamps**

```bash
for unit in window couch speaker chairs; do
  uv run python cli.py send zap_lights $unit on;  sleep 2
  uv run python cli.py send zap_lights $unit off; sleep 2
done
```

Tom confirms each lamp switches. Any failures: check the outlet is paired (side button re-learns), then re-check Step 2's timing diff.

- [ ] **Step 4: Regenerate and eyeball the web bundle**

```bash
uv run python scripts/export_web_devices.py | head -30
```

Expected: all four lamps present, sorted by position 2→5.

- [ ] **Step 5: Update project docs and commit**

Update `CLAUDE.md` "Project Status": lights decoded + controllable via CLI; homelab PWA work tracked in the companion issue.

```bash
git add CLAUDE.md PROTOCOL.md devices/zap_lights.yaml
git commit -m "docs: ZAP lighting verified end-to-end"
```

---

## Done means

- `uv run pytest tests/` green.
- `pio run` compiles clean.
- All four lamps switch from `cli.py` (Task 7 Step 3 witnessed by Tom).
- `export_web_devices.py` emits the bundle the homelab companion issue consumes.
- Fans still work (spot-check one `/fan/1/light` GET after flashing).
