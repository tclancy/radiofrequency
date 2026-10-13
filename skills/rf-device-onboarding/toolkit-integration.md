# Toolkit Integration (phases 6–8)

Verify these names still exist before relying on them (`src/device.py`,
`firmware/src/main.cpp`, `cli.py`). This file describes the repo as of 2026-10.

## Architecture in one line

`devices/<device>.yaml` → `src/device.py` builds a JSON payload → `cli.py` POSTs it
to the NodeMCU `/transmit` → the firmware toggles `TX_PIN` (D1). The firmware is
generic, so **new devices never need a reflash**.

## Pick a profile shape

**Address + command bit packet** (e.g. `devices/sofa_king_fan.yaml`, `encoding: OOK_PDM`):

```yaml
frequency_mhz: 433.935      # documentation; the TX module is SAW-locked
encoding: OOK_PDM
timing: {sync_us: 8200, sync_gap_us: 4500, pulse_us: 560,
         zero_gap_us: 570, one_gap_us: 1700, repeat_count: 20}
units:
  main:   {address: "1000110011110110"}
commands:
  light: "1100000000111111"
  "off": "0100000010111111"   # quote it: bare off is a YAML boolean
```

**Full code per unit** (e.g. `devices/zap_lights.yaml`, `encoding: PT2260`):

```yaml
encoding: PT2260
timing: {short_us: 184, long_us: 548, sync_gap_us: 5684, repeat_count: 15}
units:
  window: {position: 2, codes: {"on": "0FFFFFFF1001", "off": "0FFFFFFF1010"}}
```

Comment each timing value with where it came from (capture file and date). Future
you will want to know which numbers were measured and which were guessed.

## Adding a new encoding

If the device fits neither shape, add an encoder in `src/device.py` that returns
`list[tuple[high_us, low_us]]` (see `pt2260_pulses`), then dispatch on
`profile.encoding` in `build_payload_for` and `available_commands`. Feed the result
through `build_pulses_payload(pulses, repeat_count)`, which enforces the firmware
limits client-side. Write the failing test first in `tests/test_device.py`, using
the codes you captured as fixtures.

## Firmware limits (mirrored in `src/device.py`)

| Limit | Value | Why |
|---|---|---|
| Pulse pairs per frame | 256 | JSON doc size |
| Single duration | 1–100 000 µs | sanity |
| `repeat_count` | 1–100 | sanity |
| Total airtime | ≤ 5 s | the transmit loop busy-waits, and longer trips the ESP8266 watchdog |

## Transmit and verify (phase 7)

```bash
uv run python cli.py send <device> <unit> <command> --host ceilingfans.local
uv run python cli.py raw <bits> --device <device>     # A/B timing hypotheses
```

**SDR witness**: start `rtl_433 -f 433.92M -A -S unknown -T 30` in the background,
send the command, stop the capture, and compare the decoded code to the factory remote's.
Byte-identical means the transmission is proven. After that, any failure is on the receiver
side (repeat count, range, interference), not a code bug.

## Downstream (phase 8)

- Document the protocol in `PROTOCOL.md`: signal table, encoding diagram,
  codes table with a Verified/derived column, capture filenames.
- If the device belongs in the PWA, regenerate the bundle:
  `uv run python scripts/export_web_devices.py > devices.json`. Note that it currently
  exports PT2260 profiles only, so a new encoding needs a branch there plus a test.
- Update the CLAUDE.md "Project Status" section.
