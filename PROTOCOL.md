# RF Protocol: Sofucor Ceiling Fan Remote

## Signal Parameters

| Parameter | Value |
|-----------|-------|
| Frequency | 315.4 MHz |
| Modulation | OOK (On-Off Keying), Pulse Distance |
| Packet length | 32 bits |
| Repetitions | 36–41 per button press (remote); 20 in firmware |
| Sync pulse | ~8 ms HIGH (between/before each repetition) |
| Bit pulse (HIGH) | ~400 µs (fixed for all bits) |
| Bit 0 gap (LOW) | ~670 µs |
| Bit 1 gap (LOW) | ~1800 µs |

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

| Fan | Location | Address (16 bits) |
|-----|----------|-------------------|
| 1 | Bedroom | `1000110011110110` |
| 2 | Living room | `1111000100111011` |

## Decoded Commands

| Button | Command bits (16 bits) |
|--------|------------------------|
| light  | `1100000000111111` |
| off    | `0100000010111111` |
| speed1 | `0001000011101111` |
| speed2 | `1001000001101111` |
| speed3 | `0100100010110111` |

## Full 32-Bit Codes

### Remote 1 — Bedroom Fan

| Button | Full code | Verified |
|--------|-----------|----------|
| light  | `10001100111101101100000000111111` | ✓ |
| off    | `10001100111101100100000010111111` | ✓ |
| speed1 | `10001100111101100001000011101111` | ✓ |
| speed2 | `10001100111101101001000001101111` | ✓ |
| speed3 | `10001100111101100100100010110111` | ✓ |

### Remote 2 — Living Room Fan

| Button | Full code | Verified |
|--------|-----------|----------|
| light  | `11110001001110111100000000111111` | derived |
| off    | `11110001001110110100000010111111` | ✓ |
| speed1 | `11110001001110110001000011101111` | ✓ |
| speed2 | `11110001001110111001000001101111` | derived |
| speed3 | `11110001001110110100100010110111` | derived |

"Derived" = remote 2 address + remote 1 command bits. Should work; not yet verified
against physical hardware.

## Notes on Timing Tolerances

The firmware uses the measured values. If the fan doesn't respond, the most likely
cause is the sync gap. Try adjusting `SYNC_GAP_US` in firmware/src/main.cpp:
- Increase to 4000–10000 µs if the fan ignores all commands
- Reduce to 0 if the fan responds erratically
