---
name: rf-device-onboarding
description: Use when adding a new 433/315 MHz remote-controlled device (fan, outlet, light, doorbell) to the RF toolkit, capturing a remote with an RTL-SDR, decoding OOK pulses with rtl_433/URH/Audacity, writing a devices/*.yaml profile, or when a replayed signal transmits but the device ignores it or only works intermittently.
---

# RF Device Onboarding

## Overview

Make an RF remote-controlled device "smart" by recording its remote, decoding the
pulse train, saving it as a YAML profile, and replaying it from an ESP8266 + cheap
OOK transmitter (MX-FS-03V) via `POST /transmit`.

**Core principle: the factory remote is ground truth.** Every decision (timing,
code, repeat count) is checked against a capture of the real remote. That includes
recording *your own* transmission and comparing it byte-for-byte (the SDR witness).

A quick physics refresher: OOK (on-off keying) is Morse code with a radio
carrier. The transmitter is either fully on or fully off. Information lives
**only** in how long each on-burst and off-gap lasts, so timing precision is
everything.

## When to use

- Onboarding a new remote-controlled device into this toolkit
- A replayed code shows up on the SDR but the device doesn't react
- A device reacts sometimes (one unit or one command is flaky)
- Deciding whether a device can be done at all with an OOK transmitter

**When NOT to use / stop early:**
- **FSK/GFSK devices** (Lutron Caséta, Z-Wave, most "pro" gear). The MX-FS-03V is
  SAW-locked OOK and *physically cannot* produce FSK. You'd need a CC1101, or wire
  an ESP to a spare remote's button pads, or use the vendor's bridge.
- **Rolling codes** (KeeLoq garage doors, cars). Replay doesn't work by design,
  and attempting it can desync the real remote.
- Passive monitoring only (TPMS, weather stations). Just run `rtl_433` and
  skip the transmit side.

## The workflow

Make a todo per phase. Don't skip the gates.

| # | Phase | Gate before moving on |
|---|-------|-----------------------|
| 1 | **Feasibility**: identify the remote's chip/FCC ID, look up its modulation | OOK/ASK, fixed code. Otherwise stop (see above) |
| 2 | **Find the carrier** in Gqrx (try 433.92 MHz first, then 315) | Visible burst in the waterfall when you press a button |
| 3 | **Try rtl_433 auto-decode** (`-A` analyze + `-S unknown` to save `.cu8`) | You have a decode, or saved raw captures to measure |
| 4 | **Capture every button on every remote** of this type | One saved file per button per remote, named descriptively in `captures/` |
| 5 | **Decode**: modulation family, timing, codes, address/command split | Hand decode cross-checked by a throwaway script |
| 6 | **Write the profile** `devices/<device>.yaml` + tests | `uv run pytest` green |
| 7 | **Transmit + SDR witness**: capture your own TX, compare to the remote | Byte-identical decode **and** the device reacts |
| 8 | **Document** in `PROTOCOL.md`, update CLAUDE.md status | Another person could reproduce it from the doc |

Commands and recipes for phases 2–5 are in [capture-and-decode.md](capture-and-decode.md).
Profile schemas, adding a new encoding, and firmware limits for phases 6–7 are in
[toolkit-integration.md](toolkit-integration.md). If the device ignores you or works
intermittently, use [troubleshooting.md](troubleshooting.md).

## Running a live capture session with a human

The human presses the buttons. You run the radio. Races and missed windows are
the main failure here:

- Start captures as a **background** task with a timeout
  (`rtl_433 ... -T 90`). Never use a foreground window the person has to race.
- Signal "window open, press now" with `osascript -e 'beep 2'`. Reserve `beep 3`
  for "task complete".
- They press at leisure and say "done". You end the capture with `pkill -INT rtl_433`,
  which flushes cleanly just like Ctrl-C.
- One button per capture file. Name it `<device>_<remote>_<button>.<ext>`.

## Common mistakes

| Mistake | Reality |
|---------|---------|
| Measuring pulse widths from a WBFM (`rtl_fm` default) recording | WBFM smears edges by ±50–100 µs. **Always use `-M am`** or rtl_433's `.cu8`. This one mistake cost the fans project three weeks |
| Trusting a published decoder spec (forum post, GitHub issue) | Sofucor issue said OOK_PWM 302/906 µs. Ours were PDM 560/570/1700. Use published specs as hints and measure your own remote |
| Confusing PWM with PDM | PWM: the **pulse width** carries the bit. PDM (pulse distance): pulse width is fixed and the **gap** carries the bit. Wrong family = 1–9 garbage bits per frame instead of 32 |
| Skipping the long sync gap | Receivers need it for AGC to settle. Sofucor sync gap 670 → 4500 µs was *the* fix |
| Low `repeat_count` | Factory remotes send 20–50 frames per press. Some receivers need ~15 consecutive clean frames to latch. Try 15 before suspecting the code |
| Capturing one remote of a multi-unit device | Comparing the same button across two remotes is what reveals the address vs command bits |
| Debugging code when it's RF interference | A far unit missing one command during a noise burst is not a bug. A/B against a known-good unit first |
| TX module on 3.3 V | Wire VCC to NodeMCU **VIN** (5 V). Under-powered modules leave the carrier half-on between pulses |
| Re-flashing firmware to tune timing | Timings live in the YAML and go over HTTP. No reflash is ever needed to tune |
