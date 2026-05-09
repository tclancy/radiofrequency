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

## Tom's setup checklist — run through this every cold start

Future-you forgets. This is the path from "open laptop" to "send a command at a fan" without re-deriving anything.

1. **Plug in the NodeMCU** with a *data-capable* USB cable (not a charge-only one). `ls /dev/cu.usbserial-*` should list a new device.
2. **Plug in the RTL-SDR** with the antenna attached, *only if you intend to capture or run Gqrx this session*. The two USB devices don't conflict — but Gqrx and `rtl_fm` both grab the RTL-SDR exclusively, so quit one before starting the other.
3. **Activate the project venv** (otherwise `pio`, `pytest`, etc. aren't on PATH):
   ```bash
   cd ~/Documents/work/radiofrequency
   source .venv/bin/activate
   ```
   Or use `uv run <command>` from the repo root for one-shots.
4. **Find the NodeMCU's IP** by booting and watching serial:
   ```bash
   cd firmware
   pio device monitor -b 115200
   ```
   Press the board's RST button if needed. Look for `Connected! IP: 192.168.68.XX`. Note the IP, then Ctrl+C — the chip keeps running. The first second of garbage is the ESP8266 ROM bootloader; ignore it.
5. **Smoke test:**
   ```bash
   curl -s -o /dev/null -w "%{http_code}\n" "http://<IP>/fan/1/light"
   ```
   `200` means HTTP server is up.
6. **Send a command via the CLI:**
   ```bash
   uv run python cli.py send sofa_king_fan main light --host <IP>
   ```

Useful gotchas worth remembering:

- The DHCP lease usually gives the NodeMCU the same IP across reboots, but not always. If a curl times out, monitor again to find the new IP.
- For RTL-SDR captures, the bulletproof one-liner pattern is `(sleep 3; curl ...) & timeout 8 rtl_fm ... | sox ...` — fire-and-forget, no zombies. See `docs/fan-debugging-2026-04-19.md` for the exact recipe.
- The current bottleneck is documented in `docs/fan-debugging-2026-04-19.md`. The 9 AM ntfy nudge points there too.

## Flashing the NodeMCU — future-you checklist

Ghost-of-past-sessions present: this burned half an hour the last time. Two things to verify before `pio run --target upload`:

1. **Plug the NodeMCU in first.** PlatformIO's upload step can't autodiscover a board that isn't on USB yet. If `pio device list` returns nothing, the board isn't connected (or isn't seen — see #2).
2. **Use a data-capable USB cable.** Most short/thin USB cables in the drawer are charge-only and will power the board without exposing the serial port. If macOS shows no new `/dev/cu.usbserial-*` after plugging in, swap cables.

## Verifying transmission with Gqrx

Use this to see whether the NodeMCU is actually putting RF into the air when you hit `/transmit`. If these settings give you a clear burst on the waterfall, the transmitter is alive — any remaining issue is bits/timing/range, not hardware.

**Tune and demodulate:**

- Frequency: `433.935 MHz`
- Input: `Realtek RTL2838UHIDIR SN: 00000001` (auto-selected)
- Input rate: `2.4 Msps` (default is fine)
- Mode: **AM** — OOK rides amplitude; AM makes bursts audible and visible
- Filter width: `Normal` (~10 kHz)
- Squelch: `-150 dB` (i.e. off — you want to see everything)

**Gain and AGC (right-hand panel):**

- AGC: **Off** (AGC will chase noise and mask the bursts)
- LNA gain: `~38 dB` (headroom without overload; nudge down if the waterfall looks saturated)

**FFT / waterfall readability:**

- FFT size: `32768` — finer frequency resolution separates the fan signal from nearby WiFi/noise
- FFT rate: `30 fps`
- Waterfall speed: leave at default (20–30 fps)
- dB range: drag the range slider so the noise floor is dark and bursts pop bright. If everything is one color, you're clipped — adjust.

**What a good burst looks like:** when you fire the curl, you should see a vertical bright stripe centered on 433.935 MHz lasting ~1 second (20 packet repeats × ~55 ms each). The signal meter jumps; in AM mode you'll hear a rapid chatter through speakers.
