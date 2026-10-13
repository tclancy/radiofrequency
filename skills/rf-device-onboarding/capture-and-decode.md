# Capture and Decode (phases 2–5)

Tools: `brew install gqrx rtl_433 urh librtlsdr sox`. Gqrx, `rtl_fm` and `rtl_433`
each take the RTL-SDR **exclusively**. Quit one before starting another or you'll
get "usb_claim_interface error".

## Phase 2: find the carrier (Gqrx)

- Start at **433.92 MHz** (most imported gear). Sofucor fans sit at 433.935. Try
  315 MHz only if 433 shows nothing (US garage doors, car fobs, TPMS).
- Gain ~38 dB, AGC **off**, mode AM.
- Press a button. You want a vertical stripe in the waterfall. Note its center
  frequency to ~5 kHz.

## Phase 3: let rtl_433 try first

```bash
# Background task, 90 s window, analyze pulses, save unrecognized signals as .cu8
rtl_433 -f 433.92M -A -S unknown -T 90
```

- `-A` prints a pulse analysis per burst: pulse/gap width histograms and a guessed
  modulation with a ready-made `-X` flex spec. **This usually does most of the decode for you.**
- `-S unknown` writes `g###_433.92M_250k.cu8` raw IQ files. Rename them right away to
  `captures/<device>_<remote>_<button>.cu8`. They let you redo the decode
  offline later without the human or the remote.
- Replay offline: `rtl_433 -r captures/foo.cu8 -A` or with a flex decoder:
  `rtl_433 -r captures/foo.cu8 -X 'n=test,m=OOK_PWM,s=184,l=548,g=1000,r=6000'`.
- Before going further, search rtl_433's device list and GitHub issues for the remote's brand
  and FCC ID. Treat what you find as a **hint to verify**, never as truth.

## Phase 4: clean envelope capture (when you need to measure by eye)

AM demod, never WBFM:

```bash
timeout 8 rtl_fm -f 433935000 -M am -s 250000 -r 250000 -g 38 - | \
  sox -t raw -r 250000 -e signed -b 16 -c 1 -V1 - \
  captures/<device>_<remote>_<button>_am.wav
```

To get a capture timed alongside a transmit without zombie processes:
`(sleep 3; <transmit command>) & timeout 8 rtl_fm ... | sox ...`

Capture **every button on every remote** of the device type.

## Phase 5: decode

1. **Identify the modulation family** from rtl_433 `-A` or URH:

   | Family | What varies | Example |
   |---|---|---|
   | OOK_PWM | High-pulse width (short=1/long=0 or reverse). Period is roughly constant | PT2260/PT2262/EV1527 outlets |
   | OOK_PDM / PPM | Low-gap width. High pulse is fixed | Sofucor fans |
   | Tri-state (PT2260) | Pairs of PWM pulses → `0`, `1`, `F` symbols | Etekcity ZAP 5LX |
   | Manchester | Transition direction mid-bit | Some weather sensors |

2. **Measure the timing** from the histograms. Remember the TX's rise/fall
   skew: highs read ~20 µs long and lows ~20 µs short. Use the symmetric underlying
   value (e.g. 184/548, not 204/528). For PT2260-family chips everything is a
   multiple of α: short=1α, long=3α, sync=31α.
3. **Find the frame boundary**: the long sync pulse or gap that repeats once per frame.
   Count the frames in one press (this guides `repeat_count`).
4. **Split address from command**: line up the same button from two remotes (the bits
   that differ are the address) and different buttons from one remote (the bits that
   differ are the command). If there's no clean split (ZAP outlets have a
   one-hot walking bit), store full codes per unit and say so in the YAML.
5. **Machine-verify** the hand decode. Write a throwaway script that converts your
   symbol string back to the raw hex rtl_433 printed and asserts equality. It's cheap
   and catches transposed symbols.

URH (`urh`) is the graphical fallback. Open the `.cu8`, let it auto-detect
pulse widths, and read the bits off the Analysis tab. Audacity on the AM `.wav` is the
last resort for measuring by hand.
