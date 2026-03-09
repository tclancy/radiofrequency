# Project Scope: RF Automation Toolkit

## Problem

Two Sofucor ceiling fans have RF remotes but no smart home integration. Controlling them requires physical remotes.

## Goal

Replace the physical remotes with WiFi-controllable NodeMCU devices that replay the RF signals. Build this as a generic, repeatable toolkit so any RF-controlled device can be added by following the same workflow.

## In Scope (Phase 1 — Fans)

- Reverse-engineer the Sofucor fan remote RF protocol
- Build NodeMCU firmware that replays fan commands over HTTP
- Python CLI to send commands
- Controls: fan speed (off / speed 1 / speed 2 / speed 3) and light toggle

## In Scope (Stretch)

- Home Assistant integration (REST or MQTT)
- Generic toolkit: any RF device can be added by writing a YAML profile

## Out of Scope

- Rolling code remotes (ceiling fans use fixed codes — if these don't, we reassess)
- Building a custom PCB
- Mobile app (HTTP endpoint is sufficient for HA integration)

## Workflow for Adding Any New RF Device

1. Capture RF signal with RTL-SDR + `rtl_fm`
2. Analyze waveform in Audacity, measure pulse timings
3. Write `devices/<device_name>.yaml` with frequency, encoding, and bit patterns
4. No firmware or code changes needed

## Hardware Inventory

| Item | Status | Notes |
| --- | --- | --- |
| Nooelec NESDR Mini 2+ RTL-SDR | Working | SN: 00000001, confirmed with `rtl_test` |
| HiLetgo ESP8266 NodeMCU | Have it | Not yet tested |
| HiLetgo 315MHz TX/RX module | Ordered | MX-FS-03V transmitter, MX-05V receiver |
| ELEGOO dupont jumper wires | Ordered | F-to-F for NodeMCU↔TX module connection |
| Two Sofucor ceiling fans | Installed | Remote frequency not yet confirmed |

## Software Stack

| Tool | Purpose | Status |
| --- | --- | --- |
| Gqrx | Visual spectrum analysis / frequency finding | Installed, tested |
| rtl_fm | CLI signal capture to WAV | Installed |
| Audacity | Waveform analysis, pulse timing | Installed |
| PlatformIO | NodeMCU firmware deployment | Installed |
| Python 3.13 | Control CLI | Installed |

## Known Unknowns

1. **Exact fan remote frequency** — likely 315 MHz, promising signal spotted at 315.4 MHz, not yet confirmed
2. **Fixed vs rolling code** — almost certainly fixed (standard for ceiling fans)
3. **NodeMCU 3.3V GPIO vs TX module 3.5V minimum** — try at 3.3V first, add level shifter if needed

## Success Criteria

- Fan responds to HTTP command sent to NodeMCU (no physical remote needed)
- `python main.py sofucor_fan speed_1` controls the fan
- Adding a second RF device requires only a new YAML file
