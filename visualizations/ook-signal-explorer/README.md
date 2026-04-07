# OOK Signal Explorer

Interactive Streamlit app for understanding On-Off Keying (OOK) RF signals, built during the [Sofucor ceiling fan reverse-engineering project](https://github.com/tclancy/radiofrequency).

## What it teaches

- How OOK pulse-distance modulation encodes bits (short gap = 0, long gap = 1)
- Why `rtl_fm` output looks "inverted" in Audacity (carrier ON = quiet, carrier OFF = noisy)
- How to read individual bits from a waveform
- How address and command bits combine in a 32-bit RF packet

## Run locally

```bash
pip install -r requirements.txt
streamlit run signal_explorer.py
```

## Data

`sofucor_fan.yaml` contains the decoded protocol for two Sofucor ceiling fans — timing values, addresses, and commands all verified against real captures.
