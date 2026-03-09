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
| RF transmitter | HiLetgo 315MHz TX/RX module (MX-FS-03V / MX-05V) |
| Jumper wires | ELEGOO 120pc dupont kit — use female-to-female for NodeMCU↔TX module |
| Target device | Two Sofucor ceiling fans (model unknown, likely 315MHz remote) |

## Software

- Gqrx — visual spectrum analyzer (use to find the frequency)
- rtl_fm — CLI capture tool (use to record WAV files)
- Audacity — waveform analysis and pulse timing measurement
- PlatformIO (VSCode extension) — NodeMCU firmware deployment
- Python (this repo) — generic control CLI

## Project Status (as of 2026-02-17)

- RTL-SDR confirmed working (`rtl_test` shows device, tuner recognized)
- Gqrx installed and device recognized
- Promising activity spotted around 315.4 MHz — not yet confirmed
- Gain was too low during first scan (~-6 dB); needs to be 35-40 dB to see signals clearly
- TX module and dupont wires on order, not yet arrived

## Next Session Starting Point

1. Open Gqrx, select Realtek RTL2838UHIDIR SN: 00000001
2. Set gain to ~35-40 dB
3. Tune to 315.400 MHz
4. Press and hold a fan remote button for 1 second — watch for a bright burst in the waterfall
5. Once frequency confirmed, use `rtl_fm` to capture WAV files for each button

## Key Architecture Decisions

- Device profiles are YAML files in `devices/` — one file per RF device
- YAML is the single source of truth (firmware + Python CLI both read from it)
- NodeMCU firmware is generic — no device-specific logic, reads profiles from flash
- Python CLI is generic: `python main.py <device> <command>`
- No breadboard needed — 3 female-to-female dupont wires connect TX module to NodeMCU

## Multiple Units of the Same Device Type

There are two Sofucor fans, each with its own remote. RF remotes almost always encode signals as:

`[sync] [address bits — unique per remote unit] [command bits — same for all units of that type]`

The YAML schema must account for this. Proposed approach: a device *type* file defines the protocol and commands; each physical unit adds only its unique address. Example:

```yaml
# devices/sofucor_fan.yaml
frequency_mhz: 315
encoding: OOK
timing:
  short_pulse_us: 350
  long_pulse_us: 1050
  sync_us: 10500
commands:          # command bits only — address prepended at send time
  speed_1: "0001"
  speed_2: "0010"
  speed_3: "0100"
  off:     "1000"
  light:   "0110"

units:
  bedroom:     { address: "10101010" }
  living_room: { address: "11001100" }
```

CLI usage: `python main.py sofucor_fan bedroom speed_1`

This means capturing both remotes during Phase 1 — press each button on remote 1, then repeat for remote 2. Comparing the two captures will reveal exactly which bits are the address and which are the command.

## Wiring (when TX module arrives)

- TX VCC → NodeMCU VIN (5V preferred, 3.3V may work)
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
