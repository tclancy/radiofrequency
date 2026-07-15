# RF Protocol: Sofucor Ceiling Fan Remote

## Signal Parameters

| Parameter | Value |
|-----------|-------|
| Frequency | 433.935 MHz |
| Modulation | OOK (On-Off Keying), Pulse Distance |
| Packet length | 32 bits |
| Repetitions | 36–41 per button press (remote); 20 in firmware |
| Sync pulse (HIGH) | ~8200 µs (carrier on at start of each repetition) |
| Sync gap (LOW) | ~4500 µs (silence between sync and first data bit) |
| Bit pulse (HIGH) | ~560 µs (fixed for all bits) |
| Bit 0 gap (LOW) | ~570 µs |
| Bit 1 gap (LOW) | ~1700 µs |

Original WBFM-decoded values (pulse 400, sync_gap 670, bit gaps 670/1800)
were systematically off; the values above came from a clean AM-demod
RTL-SDR capture on 2026-05-09 and are what actually drives the fans.

## Encoding

Pulse-distance OOK: every bit begins with a fixed-length HIGH carrier pulse (~400 µs),
followed by a variable-length LOW gap. The gap duration encodes the bit value:

```
Bit 0: ▔▔▔|___|  (400 µs HIGH, 670 µs LOW)
Bit 1: ▔▔▔|________|  (400 µs HIGH, 1800 µs LOW)
Sync: ▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔|___|  (~8000 µs HIGH, ~670 µs LOW gap before first bit)
```

The sync pulse appears before each code repetition. After the last bit of a code (which
ends LOW), the next repetition starts with an 8 ms HIGH sync. The gap after the sync
before the first data bit uses the zero_gap duration as a default (may need tuning).

## Packet Structure

```
[bits 0–15: ADDRESS][bits 16–31: COMMAND]
```

- **ADDRESS** (16 bits): identifies the remote/fan pairing — unique per physical unit
- **COMMAND** (16 bits): identifies the button pressed — same across all units of this type

## Decoded Addresses

Both fans physically live in the living room; names distinguish which one
is nearer the main room vs the staircase landing.

| Fan | Name | Address (16 bits) |
|-----|------|-------------------|
| 1 | main | `1000110011110110` |
| 2 | stairs | `1111000100111011` |

## Decoded Commands

| Button | Command bits (16 bits) |
|--------|------------------------|
| light  | `1100000000111111` |
| off    | `0100000010111111` |
| speed1 | `0001000011101111` |
| speed2 | `1001000001101111` |
| speed3 | `0100100010110111` |

## Full 32-Bit Codes

### Remote 1 — Main Fan

| Button | Full code | Verified |
|--------|-----------|----------|
| light  | `10001100111101101100000000111111` | ✓ |
| off    | `10001100111101100100000010111111` | ✓ |
| speed1 | `10001100111101100001000011101111` | ✓ |
| speed2 | `10001100111101101001000001101111` | ✓ |
| speed3 | `10001100111101100100100010110111` | ✓ |

### Remote 2 — Stairs Fan

| Button | Full code | Verified |
|--------|-----------|----------|
| light  | `11110001001110111100000000111111` | derived |
| off    | `11110001001110110100000010111111` | ✓ |
| speed1 | `11110001001110110001000011101111` | ✓ |
| speed2 | `11110001001110111001000001101111` | derived |
| speed3 | `11110001001110110100100010110111` | derived |

"Derived" = remote 2 address + remote 1 command bits. **Verified working
against the stairs fan on 2026-05-09** — the address/command split was
correct.

## Notes on Timing Tolerances

The firmware reads timing from the JSON payload sent to `/transmit`, so all
tuning is in `devices/sofa_king_fan.yaml` — no reflash needed. The values
above (especially `sync_gap_us: 4500`) are what got the fans responding;
deviating much from them stops working.

## Etekcity ZAP 5LX (lighting outlets)

Captured 2026-07-15 from the living-room remote with:

```bash
rtl_433 -f 433.92M -A -S unknown    # one button per run, ~1 s press
```

Raw IQ recordings: `captures/zap_remote_pos{2-5}_{on,off}.cu8` (250 ksps).

### Encoding

PT2260-family tri-state OOK PWM (HS2260A-R4). Each 12-symbol code is sent
as 24 pulses plus a sync pair; symbols are `0` (2x short-high/long-low),
`1` (2x long-high/short-low), `F` (short-high/long-low then
long-high/short-low). rtl_433 saw ~47 frame repeats over a 1 s press.

### Measured timing (all 8 buttons identical)

| Parameter | Value | PT2260 ideal |
|-----------|-------|--------------|
| short pulse | 184 µs | 1α |
| long pulse | 548 µs | 3α (552) |
| sync gap | 5684 µs | 31α (5704) |
| SNR at couch distance | ~15 dB | — |

α ≈ 184 µs. rtl_433 reported high-pulse widths of 204/576 µs and low-gap
widths of 160/528 µs — the TX rise/fall skews highs long and lows short by
~20 µs; the symmetric 184/548 values are the underlying chip timing and are
what `devices/zap_lights.yaml` uses.

### Codes

| Position | Lamp | ON | OFF | raw (rtl_433 `{25}`) |
|----------|------|----|----|----------------------|
| 2 | window | `0FFFFFFF1001` | `0FFFFFFF1010` | `eaaa3c8` / `eaaa338` |
| 3 | couch | `0FFFFFF10001` | `0FFFFFF10010` | `eaa8fc8` / `eaa8f38` |
| 4 | speaker | `0FFFFF1F0001` | `0FFFFF1F0010` | `eaa2fc8` / `eaa2f38` |
| 5 | chairs | `0FFFF1FF0001` | `0FFFF1FF0010` | `ea8afc8` / `ea8af38` |

Raw-bit mapping: rtl_433 OOK_PWM emits `1` per short pulse, `0` per long;
symbol pairs decode as `11`→`0`, `00`→`1`, `10`→`F`; the 25th bit is the
sync pulse.

### Structure

Not a clean 8+4 address/command split. Symbol 1 is `0`, symbols 2–9 are `F`
except a one-hot `1` that walks left one symbol per outlet position
(pos 2 → symbol 9, pos 3 → 8, pos 4 → 7, pos 5 → 6), and the last two
symbols are `01` = ON, `10` = OFF. The YAML stores full 12-symbol codes per
button, so this structure is documentation only.
