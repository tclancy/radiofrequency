# RF Waveform Explorer — Streamlit Dashboard

A real-time visualization tool for Sofucor ceiling fan RF signals with live timing parameter adjustment.

## Features

- **Live Waveform Rendering:** Generates OOK-PDM waveforms on-the-fly as you adjust parameters
- **Timing Sliders:** Adjust pulse durations, gap widths, sync timing, and repetition count
- **Command Selection:** Pick any command from the YAML profile (light, off, speed1, speed2, speed3)
- **Unit Selection:** Choose which remote/fan unit to visualize (determines address bits)
- **Packet Details:** See address bits, command bits, and total transmission duration
- **Protocol Guide:** Expandable explanation of OOK-PDM modulation and packet structure

## How It Works

The app reads `/sessions/friendly-relaxed-goodall/mnt/radiofrequency/devices/sofucor_fan.yaml` and:

1. Extracts timing parameters (pulse_us, zero_gap_us, one_gap_us, sync_us, sync_gap_us)
2. Loads commands and unit addresses from the YAML
3. Generates OOK waveform samples based on selected command and current slider values
4. Renders the waveform as a matplotlib plot showing HIGH/LOW transitions
5. Updates reactively as you move any slider or change selections

## Protocol Overview

**OOK Pulse Distance Modulation (OOK_PDM)**
- Carrier pulse: constant duration (`pulse_us`)
- Information encoding: gap duration
  - Bit 0 → short gap (`zero_gap_us`)
  - Bit 1 → long gap (`one_gap_us`)

**Packet Structure**
```
[SYNC HIGH pulse] [SYNC LOW gap] [32 data bits: 16 address + 16 command] × repeat_count
```

Each data bit is: `[HIGH pulse] [LOW gap based on bit value]`

## Running the App

```bash
streamlit run waveform_explorer.py
```

Then open http://localhost:8501 in your browser.

## Parameters Explained

| Parameter | Purpose | Default |
|-----------|---------|---------|
| pulse_us | Duration of HIGH carrier for each bit | 400 µs |
| zero_gap_us | LOW gap duration when bit=0 | 670 µs |
| one_gap_us | LOW gap duration when bit=1 | 1800 µs |
| sync_us | Duration of initial SYNC HIGH pulse | 8000 µs |
| sync_gap_us | LOW gap after SYNC before data bits | 670 µs |
| repeat_count | How many times to repeat the full packet | 5 (max 50) |

## Files

- `waveform_explorer.py` — Main Streamlit application
- `README.md` — This file

## Dependencies

- streamlit
- numpy
- matplotlib
- pyyaml
- pathlib (stdlib)

All dependencies verified on smoke test.
