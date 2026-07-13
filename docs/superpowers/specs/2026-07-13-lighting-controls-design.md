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
OOK, 12 symbols per frame — 8 tri-state (0/1/F) address symbols + 4 binary
data bits — followed by a sync symbol, repeated while the button is held. The
outlets are learning-code receivers paired to *our* remote.

Note: the 5LX has 10 buttons (5 on + 5 off) against a 4-bit data nibble, so
buttons may assert multiple data lines or borrow address-area symbols. The
capture is the source of truth — the implementation must not bake in a
nibble-only assumption for button/state.

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

- Record all 8 buttons (positions 2–5 × on/off) at 433.92 MHz:
  `rtl_433 -f 433.92M -A -S unknown` — the pulse analyzer prints decoded
  frames live and `-S unknown` writes native `.cu8` sample files (the fan-era
  WAVs needed format conversion before rtl_433 could read them; `.cu8` avoids
  that).
- Fallback ladder if `-A` doesn't decode cleanly (the fan project's WBFM
  mis-timing history says have one): URH → triq.org/pdv pulse visualizer →
  Audacity.
- Captures saved as `captures/zap_remote_pos{2-5}_{on,off}.cu8`.
- Comparing the 8 frames yields the address/data split and the measured
  `short_us` / `long_us` / sync timings. Decoded results documented in
  `PROTOCOL.md`.

### 2. Device profile — `devices/zap_lights.yaml`

```yaml
frequency_mhz: 433.92       # documentation-only: the MX-FS-03V TX is SAW-locked
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
  `[[high_us, low_us], ...]`. The sync pair is the **last** element of the
  train (PT2260 transmits sync after the 12 data symbols); since every pair
  ends LOW, repeats are contiguous valid codewords with the sync gap doubling
  as the inter-frame gap, and the pin is left LOW.
- New payload builder for the `pulses` body shape enforcing the **same
  numeric limits as the firmware** (µs values 1..100,000, ≤256 pairs,
  repeat_count 1..100, total-duration budget below) so bad payloads fail
  locally with a readable message instead of a NodeMCU 400.
- Small, composable, unit-tested (known tri-state code → known waveform).

### 4. Firmware — `firmware/src/main.cpp`

- `handleTransmit` accepts the new `pulses` body shape alongside the legacy
  one (presence of the `pulses` key selects the path).
- Validation: µs values clamped 1..100000, max 256 pulse pairs,
  `repeat_count` 1..100, **and a total-duration budget**:
  `repeat_count × Σ(high_us + low_us)` must be ≤ 5 s. Without the budget,
  worst-case limits allow a 51 s busy-wait inside a single repetition —
  `delayMicroseconds()` blocks and the ESP8266 soft watchdog fires at
  ~3.2 s, hard-resetting the chip mid-transmit. (A ZAP transmit is ~140 ms;
  a hypothetical fan migration at 20 repeats is ~1.3 s; 5 s is generous.)
- Watchdog fed **inside the pulse-pair loop**, not just between repetitions.
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
  chairs with on/off each, plus All On / All Off.
- **"All" must await the four POSTs serially, not `Promise.all`.** During a
  transmit the ESP8266 is busy-waiting — `server.handleClient()` isn't
  running — so concurrent requests stall or time out against the
  single-threaded server. On a mid-sequence failure: surface the error via
  the existing toast; each transmit is idempotent, so retry is safe.
- `app.js` loads the generated `devices.json` and POSTs to `/api/transmit`.
  New Caddy route follows the existing pattern **including the prefix
  strip** (`handle /api/transmit` + `uri strip_prefix /api`). Note the
  template now lives at
  `ansible/roles/products/templates/22-parsons-remote-Caddyfile.j2`
  (moved from `roles/docker-services/` since PR #92).
- Service worker: `sw.js` is already network-first with cache fallback and
  skips `/api/*`, so updated `app.js` reaches online clients without ceremony.
  Add `devices.json` to the precache `ASSETS` list and bump the `CACHE`
  version so first-load-offline behavior includes it.
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
  Cheap interim guard: CI in this repo regenerates and diffs against a
  committed copy, catching YAML/JSON drift without solving cross-repo
  automation.

## Deliverables

1. This spec, committed on `claude/12-lighting-controls`.
2. Implementation plan posted to issue #12 (radiofrequency work).
3. Companion issue in tclancy/homelab for the PWA/Caddy half, linked from #12.
