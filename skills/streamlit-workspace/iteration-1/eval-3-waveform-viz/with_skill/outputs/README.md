# RF Waveform Explorer — Streamlit App

## What it does

Interactive dashboard for visualizing OOK (On-Off Keying) RF waveforms from the Sofucor ceiling fan device profile. Load the YAML, pick a command and unit, adjust timing parameters with sliders, and see the resulting waveform update in real time.

## Features

- **Load device YAML** — reads `sofucor_fan.yaml` with all timing and command definitions
- **Command selector** — dropdown to pick any command (light, off, speed1, speed2, speed3)
- **Unit selector** — choose which fan unit (bedroom, living_room) for address bits
- **Adjustable timing sliders** — tweak sync, pulse, and gap durations in microseconds
- **Live waveform plot** — matplotlib plot styled to match Streamlit's dark theme
- **Info panels** — shows address+command bits, timing summary, total duration

## How to run

```bash
streamlit run waveform_explorer.py
```

The app will open in your browser at `http://localhost:8501/`.

## File structure

- `waveform_explorer.py` — single-file Streamlit app
  - Uses `@st.cache_data` to load YAML once
  - Waveform generation: builds (duration, level) tuples for OOK modulation
  - Time-series conversion: samples at 1 MHz for plotting
  - Matplotlib styling: dark theme with Streamlit accent colors

## Requirements

All standard and tested:
- `streamlit` — app framework
- `numpy` — array math for time series
- `matplotlib` — plotting with full control
- `pyyaml` — load device YAML
- `pathlib` — locate sofucor_fan.yaml (stdlib)

## How it encodes waveforms

Each packet: `[address 16 bits][command 16 bits]` = 32 bits total

For each repetition:
1. **Sync HIGH** → `sync_us` microseconds
2. **Sync gap LOW** → `sync_gap_us` microseconds
3. For each bit:
   - **Pulse HIGH** → `pulse_us` microseconds
   - **Gap LOW** → `zero_gap_us` (if bit=0) or `one_gap_us` (if bit=1)

This is Pulse Distance Modulation (PDM): fixed-width pulses with variable gaps.

## Example output

Total duration for 20 repeats of a 32-bit packet (~8000 µs sync + payload):
- Single repeat ≈ ~62 ms
- 20 repeats ≈ ~1.24 seconds

The waveform plot shows the full sequence with address + command bits, making it easy to verify protocol details or debug timing issues.
