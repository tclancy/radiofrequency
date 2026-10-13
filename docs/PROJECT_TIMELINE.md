# Sofucor Ceiling Fan Smart Control — Project Timeline

Reconstructed from git history, GitHub PRs/issues, and session checkpoint docs.

## Timeline

| Date | Event |
|---|---|
| 2026-03-08 | Initial repo setup. SCOPE.md written. RTL-SDR confirmed working with `rtl_test`. Gqrx installed. Hypothesis: 315 MHz, "promising signal" spotted at 315.4 MHz. |
| 2026-03-08 | Phase 1 plan written (`docs/plans/2026-03-08-fan-control-phase1.md`) — capture → Audacity decode → YAML profile → NodeMCU firmware. |
| 2026-03-09 | Issue #1 filed: TPMS research (parallel curiosity, deferred). |
| 2026-03-14 | "Plan for fan controls" committed (b2cc75d). |
| ~late March | Frequency reality check: 315 MHz was wrong. Real frequency confirmed as **433.935 MHz** for both remotes/all buttons. CLAUDE.md updated. |
| ~late March | Protocol decoded by hand in Audacity from WBFM-demod captures. PROTOCOL.md written with initial timing (pulse 400, sync_gap 670, gaps 670/1800). |
| 2026-04-05 | `feat: Recover decoded protocol, device profile, CLI, and firmware from orphaned worktree` (2407375) — first real code lands: `devices/sofa_king_fan.yaml`, `src/device.py`, `cli.py`, `firmware/`. |
| 2026-04-05 | Streamlit `signal_explorer.py` added (47483c0) for visualizing OOK waveforms. |
| 2026-04-06 | Initial firmware iteration committed (993d3de). Per-button hardcoded endpoints: `GET /fan/{1,2}/{cmd}`. |
| 2026-04-07 | Issue #2 filed: package signal explorer as standalone Streamlit app (closed 2026-04-10, deferred). |
| 2026-04-19 | Generic-firmware plan written (`docs/plans/2026-04-19-generic-firmware.md`). Branch `claude/generic-firmware`: ArduinoJson dep, generic `POST /transmit`, CLI split into `send`/`raw` subcommands, unit names renamed `bedroom`/`living_room` → `main`/`stairs`, frequency docs corrected across YAML/PROTOCOL.md/tests. 22/22 tests green. |
| 2026-04-19 | **First on-air test fails.** NodeMCU at 192.168.68.66 transmits at 433.935 MHz (visible in Gqrx) but neither fan responds. RTL-SDR capture of NodeMCU's own output reveals smeared envelope vs. the real remote's clean bimodal gaps. Checkpoint written: `docs/fan-debugging-2026-04-19.md`. Four hypotheses ranked: (1) TX on 3.3 V not 5 V, (2) timings off, (3) ESP8266 ISR jitter, (4) bit pattern errors. |
| 2026-04-19 | LaunchAgent + ntfy daily 9 am nudge added (40b8cf5) to keep the project alive across calendar gaps. |
| 2026-05-09 | **Fans work.** Recaptured remote with `rtl_fm -M am` (AM demod instead of WBFM) gave clean envelopes. Hand-measured timing was systematically wrong — `sync_gap_us` was 670, real value ~4500 µs; sync HIGH ~8200 µs; one-gap ~1700 µs. YAML updated, fans respond on all 5 commands × both units. "Derived" stairs commands turned out to be correct. (1e002a0) |
| 2026-05-09 | Branch `claude/generic-firmware` merged to main. Home Assistant captured as next phase (3ed64e4). |
| 2026-05-09 | mDNS hostname `ceilingfans.local` added to firmware (92e9328). |
| 2026-05-09 | Issue #3: HA Docker bridge networking can't see mDNS — use `network_mode: host` or DHCP reservation. Closed next day. |
| 2026-05-09 | Issue #4: HA `rest_command` integration — closed 2026-05-10. |
| 2026-05-14 | Pre-commit hooks + GH Actions CI added (PR #6, issue #5). Project hits maintenance mode. |

---

## What Worked (the "no mistakes" path)

If we knew then what we know now, this is the entire workflow. ~1 weekend if hardware is in hand.

1. **Check rtl_433's flex-decoder DB first.** GitHub issue merbanan/rtl_433#3345 documents the Sofucor FT0317R protocol explicitly: OOK_PWM, ~302/906 µs, 32-bit (16 addr + 16 cmd), 5 repeats. Try `rtl_433 -X "n=Sofucor,m=OOK_PWM,..."` against a fresh capture before reaching for Audacity. Even if it doesn't auto-decode, the timing hints are gold.
2. **Buy the hardware once:** RTL-SDR (confirmed Nooelec NESDR Mini 2+), HiLetgo ESP8266 NodeMCU, HiLetgo 433 MHz TX module, F-to-F dupont wires. 3 wires total: VCC→VIN (5 V), GND→GND, DATA→D1.
3. **Find the carrier with Gqrx.** Try 433.92 MHz first for import gear (Sofucor lives at 433.935). Gain ~38 dB, AGC off. Confirm a vertical stripe in the waterfall when you press any button. Skip 315 MHz unless 433 shows nothing.
4. **Capture with AM demodulation, not WBFM.** This is the one big lesson: `rtl_fm -M am -f 433935000 -s 250000 -r 250000 -g 38 ...` produces a clean envelope where pulse widths are unambiguous by eye. WBFM smears the edges by ±50–100 µs, enough to break a strict receiver.
5. **Capture every button on both remotes.** Same-button comparison across two remotes reveals the address/command split immediately.
6. **Decode in Universal Radio Hacker.** `brew install urh`. Purpose-built for OOK; auto-detects pulse widths. Manual Audacity work is a fallback, not the default.
7. **Write the YAML profile** with the AM-demod timings (sync 8200 µs / sync_gap 4500 / pulse 560 / zero_gap 570 / one_gap 1700) and a single 32-bit code split into 16-bit address + 16-bit command. One YAML per device *type*; per-unit addresses are just a `units:` block.
8. **Flash a generic firmware from day one.** `POST /transmit` with `{bits, timing}` JSON. The ESP8266 has no per-device logic — it toggles `TX_PIN` per the payload. ArduinoJson on PlatformIO. Add mDNS (`ceilingfans.local`) up front so HA doesn't need a static IP.
9. **Build the Python CLI as a click group** with `send <device> <unit> <command>` and `raw <bits> --device <name>`. The `raw` subcommand pays for itself the first time you need to A/B a hypothesis.
10. **End-to-end test** by `curl`-ing `/transmit` with the correct bits + timings. Then drive via CLI. Both fans should respond first try.
11. **Home Assistant**: drop the `rest_command` block from the README into `configuration.yaml`. If HA is in Docker, use `network_mode: host` (for mDNS) or a DHCP reservation.

---

## What We Tried (full history, including blind alleys)

### Frequency hunt (March)
- Started on 315 MHz because the original BOM listed a 315 MHz TX module. A "promising signal" was visible at 315.4 MHz in Gqrx — but it wasn't the fan, and the actual TX module that arrived was 433. Real frequency turned out to be 433.935 MHz. Several docs and the YAML continued to say "315.4 MHz" through early April until a docs-correction commit (a01c5e1) caught up.

### First protocol decode (March → April)
- Captures done with `rtl_fm` default mode (WBFM demod).
- Hand-measured pulse/gap widths in Audacity. Wrote initial timing: pulse 400 µs, sync_gap 670 µs, zero_gap 670 µs, one_gap 1800 µs, repeat_count 5 (later 20).
- Decoded 32 bits: split as 16-bit address + 16-bit command. Recorded 5 commands × 2 remotes. Two of remote-2's commands were "derived" (remote-1 command bits + remote-2 address) rather than captured fresh.
- These timings *looked* right but were systematically wrong. WBFM demodulation smears the AM envelope, so eyeball measurements were off by several hundred µs in places.

### Firmware v1 — hardcoded endpoints
- Firmware had per-button handlers: `GET /fan/1/light`, `/fan/2/speed3`, etc., each with a hardcoded bit string + the (wrong) timing constants. No way to A/B without reflashing.

### Streamlit signal explorer
- Built `signal_explorer.py` (Streamlit) to visualize OOK captures — useful for teaching/understanding but didn't catch the timing error because it was reading the same WBFM-demod WAVs.
- Issue #2 floated packaging it as a standalone shareable app on Streamlit Cloud. Deferred.

### Firmware v2 — generic `/transmit` (April 19 session)
- 10-commit branch `claude/generic-firmware`: added `POST /transmit` with JSON payload, split CLI into `send`/`raw`, ArduinoJson dep, unit renames, frequency doc corrections, README flashing notes, Gqrx-verification notes.
- All 22 tests passed. Firmware flashed, NodeMCU live at 192.168.68.66.
- Curl against both `/fan/1/light` and `/transmit` returned 200 OK. Gqrx confirmed an RF burst at 433.935 MHz the moment curl fired.
- **Fans ignored every command.** Including at point-blank range. Including with `repeat_count=40`.

### Debugging session (April 19, checkpoint doc)
- Captured the NodeMCU's own transmission and compared it to the real remote.
- Diagnostic plots in `/tmp/`: `comparison.png`, `compare_bits.png`, `compare_overlay.png` (the "money shot" — normalized envelopes overlaid).
- Finding: NodeMCU envelope never fully silenced the carrier between pulses; gap widths looked uniform instead of bimodal. Real remote had crisp drops to zero.
- Four hypotheses ranked:
  1. TX on 3.3 V instead of 5 V (slow carrier decay).
  2. Timing values off (esp. since WBFM is imprecise).
  3. ESP8266 WiFi ISR jitter.
  4. Bit pattern errors (MSB/LSB, parity).
- Tried bumping `repeat_count`, point-blank range — no change.

### The fix (May 9)
- Recaptured remote with `rtl_fm -M am`. AM demod gave a clean envelope with unambiguous pulse widths.
- Real values: sync HIGH ~8200 µs (we had 8000, close enough), **sync_gap ~4500 µs (we had 670 — off by ~7×)**, pulse ~560 µs (we had 400), zero_gap ~570 µs, one_gap ~1700 µs.
- YAML updated. Fans responded immediately on all 5 commands × both units. The "derived" stairs commands turned out to be correct — the address/command split was right all along.
- Of the four ranked hypotheses, **#2 (timing) was the winner**. #1 (TX wiring) was probably fine all along. #3 and #4 were never relevant.
- Lesson: AM demodulation, not WBFM, is the right tool for measuring OOK pulse widths. The smeared envelope we thought was a TX problem was just what WBFM looked like when re-captured.

### Home Assistant integration (May 9–10)
- Branch merged to main.
- mDNS `ceilingfans.local` added so HA doesn't need a static IP.
- Issue #3: HA in Docker with bridge networking can't see mDNS — `network_mode: host` or DHCP reservation. Closed.
- Issue #4: `rest_command` block from README → `configuration.yaml`. Done.

### Infrastructure (May 14)
- Issue #5 / PR #6: pre-commit hooks (ruff, trailing whitespace, yaml/toml check), pre-push pytest gate, GitHub Actions CI. Merged.

### Parallel curiosities (still open or deferred)
- Issue #1 (closed) → Issue #7 (open 2026-05-15): TPMS reading for the three vehicles via rtl_433.
- Issue #2 (closed, deferred): standalone Streamlit deployment of the signal explorer.
