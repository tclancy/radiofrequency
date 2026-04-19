# Radio Frequency Hacking Project

This is a repository for attempting to make my home ceiling fans [smart like this](https://www.instructables.com/Reverse-Engineer-RF-Remote-Controller-for-IoT/). I have two of [these Sofucor fans](https://images.thdstatic.com/catalog/pdfImages/61/61a5284c-e813-411d-8c5d-9bcf81a198fa.pdf).

There is a [plan for dealing with the fans](docs/plans/2026-03-08-fan-control-phase1.md).

## What We Are Working With

### Software

- Gqrx - `brew install gqrx`
- rtl_fm - `brew install librtlsdr`
- sox - `brew install sox`
- Audacity (already installed)
- PlatformIO - extension to VSCode

### Hardware

- [Nooelec NESDR Mini 2+ 0.5PPM TCXO RTL-SDR & ADS-B USB Receiver Set](https://www.nooelec.com/store/sdr/sdr-receivers/nesdr-mini-2-plus.html)
- [HiLetgo 1PC ESP8266 NodeMCU CP2102 ESP-12E Development Board](http://www.hiletgo.com/ProductDetail/1906570.html)
- [HiLetgo 315Mhz RF Transmitter and Receiver Module](http://hiletgo.com/ProductDetail/2157209.html)

## Flashing the NodeMCU — future-you checklist

Ghost-of-past-sessions present: this burned half an hour the last time. Two things to verify before `pio run --target upload`:

1. **Plug the NodeMCU in first.** PlatformIO's upload step can't autodiscover a board that isn't on USB yet. If `pio device list` returns nothing, the board isn't connected (or isn't seen — see #2).
2. **Use a data-capable USB cable.** Most short/thin USB cables in the drawer are charge-only and will power the board without exposing the serial port. If macOS shows no new `/dev/cu.usbserial-*` after plugging in, swap cables.
