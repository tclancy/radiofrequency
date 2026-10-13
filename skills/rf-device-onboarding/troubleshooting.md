# Troubleshooting: "it transmits but the device ignores it"

Work top-down. Each step rules out one layer. Don't jump to "the code is wrong".

## 1. Is the carrier clean?

Look at Gqrx or an AM capture of *your* TX next to the remote's. If the carrier never
drops to near zero between pulses, the receiver can't tell 0 from 1.
**Fix:** TX VCC → NodeMCU **VIN** (5 V), not 3V3. Use short wires and attach an antenna
(a 17.3 cm wire is a ¼-wave at 433 MHz).

## 2. Is the code byte-identical? (SDR witness)

Capture your own transmission with rtl_433 and compare the decode to the factory remote's.
- **Different** → it's a decode or encoder bug. Re-check the modulation family
  (PWM vs PDM) and the symbol mapping, re-decode the saved `.cu8` offline, and
  machine-verify.
- **Identical** → the code is right. Go to step 3 and stop editing encoders.

## 3. Is the timing close enough?

Receivers vary in strictness. Re-measure from an **AM** capture (never WBFM). The
sync gap matters most: the receiver's AGC needs it to settle after the sync burst.
Use `cli.py raw` to sweep one parameter at a time (e.g. sync_gap
{670, 2000, 4500}) and record which values make the device react.

## 4. Enough frames?

Compare frames per press: the factory remote vs your `repeat_count`. The ZAP chairs
outlet latched ON only at 15 frames (remote sends ~47). Keep total airtime under 5 s.

**Logical squeeze**: if OFF works for a unit (so the prefix is fine) and ON works for
other units (so the ON tail is fine), no deterministic code bug can single out
one unit's ON. The cause is the receiver (sensitivity or frame count).

## 5. Interference or range?

A/B against a known-good unit at the same moment. If the SDR shows a raised
noise floor during a miss, it's transient interference. Retry before changing anything.

## Field notes

| Device | Symptom | Real cause |
|---|---|---|
| Sofucor fans | TX visible, fans never react, for 3 weeks | WBFM-measured timing. Sync gap 670 vs real 4500 µs |
| Sofucor fans | rtl_433 flex gives 1–9 bits/frame | Configured OOK_PWM, actually OOK_PDM |
| ZAP chairs outlet | ON intermittent, OFF fine, other lamps fine | repeat_count 6 too low, needed 15 |
| ZAP far outlet | Occasional miss | Transient RF noise burst |
| Lutron Caséta | n/a: shelved | GFSK + sequence counter; an OOK TX can't do it |
