# Fan Control Debugging Session — 2026-04-19

Checkpoint for next-session-Tom. Context: we built the generic `/transmit`
firmware + CLI today, tried to drive the fans, and discovered that while
transmission happens, the fans don't respond. Investigation narrowed the
problem to pulse-envelope shape, not bit values.

## What works now

- Branch `claude/generic-firmware` has 10 commits:
  - ArduinoJson dep + generic `POST /transmit` firmware endpoint
  - `build_transmit_payload` helper in `src/device.py`
  - CLI refactored into `click.group` with `send` and `raw` subcommands
  - Rename: units `bedroom`/`living_room` → `main`/`stairs` (both fans live
    in the living room; names distinguish which is nearer main room vs stairs)
  - Frequency docs corrected from stale 315.4 → 433.935 MHz across YAML,
    PROTOCOL.md, tests
  - README flash-reminders + Gqrx setup notes
- 22/22 tests green
- Firmware flashed, NodeMCU at `192.168.68.66`
- Both endpoints work at the HTTP layer: legacy `GET /fan/{N}/{cmd}` and
  generic `POST /transmit`
- Gqrx shows a clear RF burst at 433.935 MHz when curl fires — **TX is alive**

## What doesn't work

- Neither fan responds to commands from the NodeMCU. Close-range and
  `repeat_count=40` made no difference. Light on the "stairs" fan was never
  verified (no capture for remote 2 light in `captures/`).

## Key diagnostic finding

Captured the NodeMCU's own transmission with RTL-SDR
(`captures/nodemcu_main_light.wav`, using the same rtl_fm + sox pipeline
that produced `captures/sofucor_remote1_light.wav`) and compared.

- Both show valid OOK bursts at 433.935 MHz
- NodeMCU burst is ~1.3 s (20 reps via old `/fan/1/light` endpoint);
  remote burst is ~3.4 s (36–41 reps)
- **Critical difference:** in the overlaid envelope at 10 ms zoom
  (`/tmp/compare_overlay.png`), the remote's pulses drop almost to zero
  between each pulse with visibly bimodal gap widths (short `0`-gaps
  vs wide `1`-gaps). The NodeMCU's envelope stays in the middle of the
  range between pulses — never fully silencing the carrier — and gap
  widths look more uniform.

This means the fan's receiver can't discriminate `0` from `1` in our output.

## Hypotheses, ranked by likelihood

1. **TX module on 3.3V instead of 5V.** HiLetgo 433 MHz ASK modules have
   notoriously dirty on/off response, especially under-powered. Carrier
   decay can take hundreds of microseconds at 3.3V, which would exactly
   match the smeared envelope we see.
   - **First thing to check next session:** verify TX module `VCC` is
     wired to NodeMCU `VIN` (5V from USB), not `3V3`.
2. **Our Audacity-decoded pulse/gap timings are slightly off.** Hand
   measurement of WBFM-demod data has ±50–100 µs error. Recapture the
   real remote with `rtl_fm -M am` for cleaner envelopes, then re-measure.
3. **ESP8266 WiFi ISR jitter during packet transmission.** Less likely
   to cause systematic smearing, more likely occasional bad packets.
4. **Bit pattern errors (MSB/LSB order, missing parity).** Unlikely given
   the pulse *smearing* we see — wrong bits would give clean pulses at
   wrong positions, not smear.

## Concrete next-session plan

**Step 1 (30 s):** Inspect TX module wiring. If on 3V3, move to VIN, retry
`uv run python cli.py send sofa_king_fan main light --host 192.168.68.66`.
If the fan responds, we're done.

**Step 2 (10 min):** If wiring was already correct, recapture the real
remote with clean AM demod:

    timeout 8 rtl_fm -f 433935000 -M am -s 250000 -r 250000 -g 38 - | \
      sox -t raw -r 250000 -e signed -b 16 -c 1 -V1 - \
      captures/sofucor_remote1_light_am.wav

Press the real remote light button while it runs. Open the AM capture
and re-measure pulse/gap widths precisely. Update `devices/sofa_king_fan.yaml`
timing with corrected values.

**Step 3 (if still no response):** Script a sweep. Using the `raw`
subcommand, fire the same bit string with timing variations and note which
reach the fan. Candidates to try: pulse_us in {300,400,500,600};
zero_gap_us in {500,670,800}; one_gap_us in {1500,1800,2100}.

**Step 4 (wild card):** Try with an actual antenna. The HiLetgo module
has an `ANT` pad — soldering ~17 cm of solid wire as a quarter-wave
improves radiated power by 10× and sometimes fixes receivers that are
marginal on noise.

## Artifacts left on disk

- `/tmp/comparison.png` — overview of both captures
- `/tmp/comparison_zoom.png` — 100 ms windows aligned to burst starts
- `/tmp/compare_bits.png` — 20 ms after-sync detail with 200 µs smoothing
- `/tmp/compare_overlay.png` — **the money shot**, normalized envelopes overlaid
- `/tmp/compare_captures.py`, `compare_zoom.py`, `compare_bits.py`,
  `compare_overlay.py` — scripts to regenerate the above
- `/tmp/measure_pulses.py` — attempt at auto-measuring pulse widths; noisy
  because it runs on WBFM-demod data. Revisit once we have AM captures.

If these stay useful past one session, move them into `tools/` in the repo.

## Things to decide before merging branch to main

1. Do we drop the legacy `/fan/{N}/{cmd}` endpoints (plan Task 7)?
2. Rename `sofa_king_fan.yaml` → something less punny now that we're
   settling? (Tom's call.)
3. The `visualizations/ook-signal-explorer/sofucor_fan.yaml` is a stale
   copy — keep in sync with the real device profile or delete?
