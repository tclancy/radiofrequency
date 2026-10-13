# RF Automation Toolkit — Claude Context

## What This Project Is

A generic RF signal reverse-engineering and replay toolkit. The Sofucor ceiling fans are device #1. The goal is a repeatable workflow for making any RF-controlled device "smart":

1. Capture RF signal with RTL-SDR
2. Decode the protocol in Audacity
3. Write a YAML device profile
4. NodeMCU replays the signal over WiFi HTTP

## Hardware

| Device | Details |
| --- | --- |
| RTL-SDR | Nooelec NESDR Mini 2+ (RTL2838UHIDIR, SN: 00000001) |
| Microcontroller | HiLetgo ESP8266 NodeMCU |
| RF transmitter | HiLetgo 433MHz TX/RX module (MX-FS-03V / MX-05V) |
| Jumper wires | ELEGOO 120pc dupont kit — use female-to-female for NodeMCU↔TX module |
| Target device | Two Sofucor ceiling fans (confirmed 433.935 MHz remote) |

## Software

- Gqrx — visual spectrum analyzer (use to find the frequency)
- rtl_fm — CLI capture tool (use to record WAV files)
- Audacity — waveform analysis and pulse timing measurement
- PlatformIO (VSCode extension) — NodeMCU firmware deployment
- Python (this repo) — generic control CLI

## Project Status (as of 2026-07-15)

- **Fans: fully working.** Both Sofucor fans controllable via NodeMCU HTTP (`/fan/*` routes); protocol in `PROTOCOL.md`, profile in `devices/sofa_king_fan.yaml`
- **Lights: fully working.** Etekcity ZAP 5LX outlets (window, couch, speaker, chairs) decoded and controllable via `cli.py send zap_lights <unit> <on|off>` — PT2260 tri-state codes captured 2026-07-15, all 4 lamps verified end-to-end
- Firmware has a generic pulse-train endpoint (`POST /transmit` with `pulses` + `repeat_count`) — new protocols need zero firmware changes
- `scripts/export_web_devices.py` derives the PWA `devices.json` bundle from the YAML profiles; homelab 22-parsons-remote PWA consumes it (tracked in the companion issue)
- Interactive signal explorer built (`signal_explorer.py`) — Streamlit app for understanding OOK waveforms

## Next Session Starting Point

1. Homelab PWA integration — regenerate `devices.json` via `scripts/export_web_devices.py` and wire it into the 22-parsons-remote PWA (companion issue)
2. TPMS monitoring for the three vehicles (see memory notes) is still an open idea
3. Debugging tip: transient RF interference can make a far outlet miss a command — verify with the SDR-witness technique in `PROTOCOL.md` before suspecting code

## Onboarding a New Device

Use the `rf-device-onboarding` skill (`skills/rf-device-onboarding/`, symlinked into
`~/.claude/skills/`). It has the phase checklist, capture/decode commands,
profile shapes and the "transmits but device ignores it" troubleshooting ladder.

## Useful Tools for Signal Analysis

- **Universal Radio Hacker (URH)** — `brew install urh` — purpose-built for OOK signal analysis, auto-detects pulse widths and bit patterns. Try this before squinting at Audacity.
- **rtl_433** — `brew install rtl_433` — auto-decodes hundreds of OOK protocols. `-A` analyzes pulses, `-S unknown` saves raw `.cu8` captures you can re-decode offline with `-r`.
- **Audacity** — manual fallback for measuring pulse timings by hand. Only measure from `rtl_fm -M am` captures — WBFM smears edges by ±50–100 µs.

## rtl_433 Auto-Decode Notes

GitHub issue merbanan/rtl_433#3345 describes the Sofucor FT0317R as OOK_PWM
(~302/906 µs). **That does not match our remotes** — ours are OOK_PDM
(fixed ~560 µs pulse, gap encodes the bit: 570 µs = 0, 1700 µs = 1), and the
OOK_PWM flex decoder produced 1–9 garbage bits per frame. Treat published
decoder specs as hints; measured values live in `PROTOCOL.md`.

- WAV files may need conversion to `.cu8` format before rtl_433 can read them
- Also try the triq.org/pdv/ browser visualizer for .ook pulse files

## Reading / Learning Resources

- *Make: Electronics* (3rd ed) — Ch 1-2 for signal/oscillation fundamentals
- rtl_433 wiki — OOK signal analysis examples with visuals
- Instructables guide linked in README
- GitHub issue merbanan/rtl_433#3345 — Sofucor discussion (timings there are wrong for our remotes, see above)

## Key Architecture Decisions

- Device profiles are YAML files in `devices/` — one file per RF device type
- YAML is the single source of truth: `src/device.py` turns a profile into a `/transmit` JSON payload; `scripts/export_web_devices.py` derives the PWA bundle from it
- NodeMCU firmware is generic — no device-specific logic; timings and pulses arrive in each `POST /transmit` body, so tuning never needs a reflash
- Python CLI is generic: `uv run python cli.py send <device> <unit> <command>` (and `raw <bits> --device <device>` for A/B experiments)
- No breadboard needed — 3 female-to-female dupont wires connect TX module to NodeMCU

## Multiple Units of the Same Device Type

There are two Sofucor fans, each with its own remote. Many RF remotes encode signals as:

`[sync] [address bits — unique per remote unit] [command bits — same for all units of that type]`

A device *type* file defines the protocol and commands; each physical unit adds only its unique address. Excerpt of the real profile:

```yaml
# devices/sofa_king_fan.yaml
frequency_mhz: 433.935
encoding: OOK_PDM
timing: {sync_us: 8200, sync_gap_us: 4500, pulse_us: 560,
         zero_gap_us: 570, one_gap_us: 1700, repeat_count: 20}
units:
  main:   { address: "1000110011110110" }
  stairs: { address: "1111000100111011" }
commands:          # 16-bit command field, appended to the address at send time
  light: "1100000000111111"
  "off": "0100000010111111"
```

CLI usage: `uv run python cli.py send sofa_king_fan main light`

Not every device splits cleanly: the ZAP outlets (`devices/zap_lights.yaml`,
`encoding: PT2260`) store a full tri-state code per unit instead. Capturing the
same button on two remotes is what reveals which shape you have.

## Wiring

- TX VCC → NodeMCU VIN (5V — 3.3V leaves the carrier half-on between pulses)
- TX GND → NodeMCU GND
- TX DATA → NodeMCU D1 (or any GPIO)

## Collaboration Style

The user wants to be an active partner, not just an executor. When doing anything non-trivial:

- **Explain the physics/electronics briefly before doing it.** Why does this step work? What is actually happening in the hardware?
- **Flag decision points.** When there's a choice (e.g., which GPIO pin, which encoding approach), explain the tradeoff rather than just picking one.
- **Use analogies** where they help. RF concepts like OOK modulation, carrier frequency, and pulse timing are learnable with the right framing.
- **Don't just report success/failure** — explain what it means. "The PLL locked" should come with a one-line explanation of what a PLL is doing.

The goal is that the user understands enough to debug problems independently and could explain this project to someone else.

The user (whatever happened to calling me Big Lad?) also has a library full of electronics books he has bought optimistically in
the past and then not been able to make headway, so ask him to tell you which ones he has access to in order to assign follow up
reading or assignments.

### Books Mentioned So Far

- [Make: Electronics: Learning by Discovery: A hands-on primer for the new electronics enthusiast 3rd Edition](https://www.amazon.com/dp/B0B3LS5K2Z)
- [Electronics Demystified: A Guide to Understanding Electronic Circuits and Components](https://www.amazon.com/dp/B0CLVMQPX4)
- [Getting Started with Sensors: Measure the World with Electronics, Arduino, and Raspberry Pi](https://www.amazon.com/dp/1449367089)

## Conventions

- All work in `claude/` prefixed git branches
- Raw captures go in `captures/` with descriptive filenames
- Decoded protocols documented in `PROTOCOL.md`
- Device YAML profiles go in `devices/`
