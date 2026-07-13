# Design: ZAP Lighting Controls for the RF Server and Remote PWA

**Issue:** [#12](https://github.com/tclancy/radiofrequency/issues/12) (research: [#10](https://github.com/tclancy/radiofrequency/issues/10))
**Date:** 2026-07-13
**Status:** Approved by Tom (conversation, 2026-07-13)

## Goal

Control the four Etekcity ZAP outlet-switched lamps in the living room (remote
positions 2–5) from the existing NodeMCU RF server and the 22-parsons-remote
PWA, the same way the ceiling fans work today.

| Position | Lamp    |
|----------|---------|
| 2        | window  |
| 3        | couch   |
| 4        | speaker |
| 5        | chairs  |

UI gets individual on/off per lamp plus **All On / All Off**.

## Background and key decisions

### The protocol (from issue #10)

The ZAP 5LX remote uses an HS2260A-R4 encoder (PT2260 family) at 433.92 MHz:
OOK with 12 tri-state symbols (0/1/F) per frame — 8 address + 4 data — sync
gap after each frame, repeated while the button is held. The outlets are
learning-code receivers paired to *our* remote.

### Decision: take the knowledge, not the library

We will **not** vendor [cpetrescu/ZAP-remote](https://github.com/cpetrescu/ZAP-remote).
Its hardcoded codes belong to the author's remote — PT2260 addresses are baked
into each remote's encoder, and our outlets learned ours. The library and the
[vmallet ZAP 3L teardown](https://vmallet.com/2020/07/etekcity-zap-3l-remote-power-outlet-teardown-and-analysis/)
serve as protocol references only. Codes come from an RTL-SDR capture of our
actual remote.

### Decision: generic pulse-train transmit (Option A)

The firmware's current `POST /transmit` assumes pulse-*distance* modulation
(fixed HIGH burst, data in the LOW gap). PT2260 is pulse-*width* modulation
(data in the HIGH burst length; two pulses per symbol) — inexpressible in the
current schema.

Rather than add a per-protocol mode flag (rejected: firmware update per future
protocol family) or hardcode ZAP routes like the legacy `/fan` endpoints
(rejected: violates the generic-firmware architecture rule), the firmware
gains one universal capability: transmit an explicit pulse train.

```
POST /transmit   (second accepted body shape)
{"pulses": [[high_us, low_us], ...], "repeat_count": N}
```

All encoding intelligence stays in Python, derived from the YAML profile.
This shape can express any OOK protocol, so the firmware never needs another
protocol update. The legacy `{bits, timing}` shape and `/fan/*` GET routes
remain untouched — fans keep working throughout.

## Components

### 1. Capture & decode (Tom-in-the-loop, ~15 min)

- Record all 8 buttons (positions 2–5 × on/off) at 433.92 MHz with
  `rtl_433 -A` (pulse analyzer); PT2260 is among the best-supported OOK
  protocols, so no manual Audacity work is expected.
- Captures saved as `captures/zap_remote_pos{2-5}_{on,off}.*`.
- Comparing the 8 frames yields the address/data split and the measured
  `short_us` / `long_us` / sync timings. Decoded results documented in
  `PROTOCOL.md`.

### 2. Device profile — `devices/zap_lights.yaml`

```yaml
frequency_mhz: 433.92
encoding: PT2260            # tri-state OOK PWM
timing:
  short_us: <measured>      # α-derived short segment
  long_us:  <measured>      # 3α long segment
  sync_gap_us: <measured>   # long quiet gap ending each frame
  repeat_count: 6           # remote repeats while held; 5–6 is plenty
units:
  window:  { position: 2, ... }   # exact code fields finalized after capture
  couch:   { position: 3, ... }
  speaker: { position: 4, ... }
  chairs:  { position: 5, ... }
commands:
  "on":  ...
  "off": ...
```

The exact split between per-unit and per-command tri-state fields is
finalized from the capture (expected: shared remote address + button/state in
the data nibble, but the frames are the source of truth).

### 3. Python encoder — `src/device.py`

- New pure function: profile + unit + command → pulse train
  `[[high_us, low_us], ...]` including the sync symbol.
- New payload builder for the `pulses` body shape with the same validation
  spirit as `build_transmit_payload`.
- Small, composable, unit-tested (known tri-state code → known waveform).

### 4. Firmware — `firmware/src/main.cpp`

- `handleTransmit` accepts the new `pulses` body shape alongside the legacy
  one (presence of the `pulses` key selects the path).
- Validation: µs values clamped 1..100000, max 256 pulse pairs,
  `repeat_count` 1..100. Watchdog fed between repetitions, as today.
- No device knowledge added; `/fan/*` and legacy `/transmit` untouched.

### 5. CLI

`python cli.py send zap_lights window on` — profile loading detects the
PT2260 encoding and routes through the pulse-train encoder/payload.

### 6. Derived web bundle — `scripts/export_web_devices.py`

Generates `devices.json` (button → ready-to-POST payload) from
`devices/*.yaml`, so the PWA never duplicates codes or timings. One documented
regen command for now; automation hook later if the manual step annoys us
(**open item**, see below).

### 7. homelab repo (separate PR, companion issue)

- 22-parsons-remote PWA adds a **Lights card**: window / couch / speaker /
  chairs with on/off each, plus All On / All Off. "All" fires the four codes
  sequentially from the client — each transmit is sub-second, no firmware
  queueing.
- `app.js` loads the generated `devices.json` and POSTs to `/api/transmit`;
  one new Caddy `reverse_proxy` route for the POST path.
- Fans stay on their existing GET pattern for now.

## Testing

1. **Unit tests first** (failing-test-as-spec): tri-state encoder waveform,
   payload validation edge cases.
2. **Bench proof**: capture the NodeMCU's own transmission with the RTL-SDR
   and diff against the remote's capture — the same technique that validated
   the fans (`captures/nodemcu_main_light.wav`).
3. **End-to-end**: lamps switch from the CLI first, then from the PWA on a
   phone.

## Out of scope / future

- Extracting the remote PWA into its own app (Tom's instinct, 2026-07-13 —
  "a problem for another day").
- Migrating the fan buttons off the legacy GET endpoints onto `/transmit`.
- Home Assistant exposure of the lights.
- Cross-repo automation for regenerating `devices.json` (manual documented
  command in v1).

## Open items

- Regen ergonomics for `devices.json` across two repos — revisit after v1.

## Deliverables

1. This spec, committed on `claude/12-lighting-controls`.
2. Implementation plan posted to issue #12 (radiofrequency work).
3. Companion issue in tclancy/homelab for the PWA/Caddy half, linked from #12.
