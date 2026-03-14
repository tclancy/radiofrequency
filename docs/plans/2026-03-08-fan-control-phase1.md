# Fan Control Phase 1 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reverse-engineer the Sofucor fan remote RF protocol and build a working HTTP-controlled NodeMCU transmitter.

**Architecture:** Capture raw RF with RTL-SDR, decode OOK pulse timing manually in Audacity, encode protocol as a YAML device profile, deploy generic firmware to NodeMCU that reads the profile, expose HTTP endpoints for fan control.

**Tech Stack:** Python 3.13, PlatformIO/Arduino (ESP8266), rtl_fm, Audacity, YAML

---

## Phase 1: Signal Capture (Hardware — Manual Steps)

These steps require physical presence with the hardware.

### Task 1: Confirm fan remote frequency

**What's happening:** The fan remote broadcasts a modulated RF burst. We need to see it visually to confirm it's at 315.4 MHz and not some nearby harmonic.

**Step 1: Open Gqrx**
- Select: `Realtek RTL2838UHIDIR SN: 00000001`
- Input rate: 2.048 MHz
- Gain: ~38 dB (AGC off)
- Tune to: `315.400 MHz`
- Mode: WFM (for visualisation only), FFT Size: 32768

**Step 2: Confirm signal burst**
- Press and hold any fan remote button for 1 second
- Watch waterfall for a bright vertical stripe around 315.4 MHz
- If signal appears offset from center, note the exact frequency shown in the peak marker
- **Expected:** Bright burst, ±50 kHz of 315.4 MHz
- **If nothing:** Try 433.92 MHz — some import fans use 433

**Step 3: Note exact frequency**
- Record confirmed frequency in `captures/README.md` (create if needed)

---

### Task 2: Capture WAV files for each button

**What's happening:** `rtl_fm` down-converts the RF signal to an audio-rate signal. The OOK modulation shows up as on/off pulses you can see and measure in Audacity.

**Step 1: Capture each button (run these commands one at a time)**

Replace `315400000` with the confirmed frequency if different:

```bash
# Fan Speed 1 — press and hold button while recording, then Ctrl+C
rtl_fm -f 315400000 -s 250000 -r 250000 -g 38 captures/sofucor_speed1.wav &
# Press and hold Speed 1 button for 2 seconds, then:
kill %1

# Repeat for each button:
rtl_fm -f 315400000 -s 250000 -r 250000 -g 38 captures/sofucor_speed2.wav &
rtl_fm -f 315400000 -s 250000 -r 250000 -g 38 captures/sofucor_speed3.wav &
rtl_fm -f 315400000 -s 250000 -r 250000 -g 38 captures/sofucor_off.wav &
rtl_fm -f 315400000 -s 250000 -r 250000 -g 38 captures/sofucor_light.wav &
```

Capture files: `captures/sofucor_speed1.wav`, `sofucor_speed2.wav`, `sofucor_speed3.wav`, `sofucor_off.wav`, `sofucor_light.wav`

Also capture **both remotes** for at least one button (e.g. `sofucor_bedroom_speed1.wav` and `sofucor_livingroom_speed1.wav`) — comparing them reveals which bits are the address.

**Step 2: Verify captures opened in Audacity**
- Open one WAV in Audacity
- You should see a noisy flat line with 1-3 distinct bursts of pulse activity
- If file is completely silent or pure noise: re-capture with higher gain

---

## Phase 2: Protocol Decoding (Manual — Audacity)

**What's happening:** OOK (On-Off Keying) encodes bits as the *ratio* of pulse widths. A short HIGH followed by a long LOW = bit 0; long HIGH, short LOW = bit 1 (or vice versa — we'll determine which from context).

### Task 3: Measure pulse timings

**Step 1: Open `sofucor_speed1.wav` in Audacity**

**Step 2: Zoom in to a single burst**
- Use View > Zoom In until you can see individual pulses (alternating high/low)

**Step 3: Measure sync pulse**
- The very first pulse (longest HIGH at start of burst) is the sync pulse
- Click at start of sync HIGH, shift-click at end
- Read duration in the Selection toolbar at bottom
- Expected: ~10,000–15,000 µs (10–15 ms)

**Step 4: Measure a short pulse and a long pulse**
- After the sync, pulses repeat in pairs (one HIGH, one LOW = one bit)
- Measure the SHORT high-period and LONG high-period
- Expected values:
  - Short: ~350 µs
  - Long: ~1050 µs (3× short)

**Step 5: Document in `PROTOCOL.md`**

```markdown
## Sofucor Fan Remote

- Frequency: 315.4 MHz
- Encoding: OOK (On-Off Keying), PWM variant
- Sync pulse: Xµs HIGH, Xµs LOW
- Bit 0: Xµs HIGH, Xµs LOW
- Bit 1: Xµs HIGH, Xµs LOW
- Packet length: X bits
- Repeat count: X (how many times burst repeats per button press)
```

**Step 6: Extract bit patterns**
- Decode each capture to binary string by hand (short pulse = 0, long = 1 or vice versa)
- Compare bedroom vs living room captures to identify which bits change (= address)
- Compare speed1 vs speed2 vs off to identify command bits

---

## Phase 3: YAML Device Profile

### Task 4: Write `devices/sofucor_fan.yaml`

**Files:**
- Create: `devices/sofucor_fan.yaml`

**Step 1: Create the devices directory**
```bash
mkdir -p devices
```

**Step 2: Write the YAML profile**

Fill in timing values from your Audacity measurements:

```yaml
# devices/sofucor_fan.yaml
frequency_mhz: 315.4
encoding: OOK_PWM
timing:
  sync_high_us: 10500   # replace with measured value
  sync_low_us: 10500    # replace with measured value
  short_pulse_us: 350   # replace with measured value
  long_pulse_us: 1050   # replace with measured value
  bit_low_us: 350       # LOW period between bits
  repeat_count: 5       # how many times to repeat packet

# bit encoding: 0 = short HIGH + bit_low_us LOW
#               1 = long HIGH + bit_low_us LOW

commands:
  speed_1: "0001"   # command bits only — fill in from Audacity
  speed_2: "0010"
  speed_3: "0100"
  off:     "1000"
  light:   "0110"

units:
  bedroom:
    address: "10101010"   # fill in from Audacity comparison
  living_room:
    address: "11001100"   # fill in from Audacity comparison
```

**Step 3: Commit**
```bash
git checkout -b claude/phase1-protocol
git add PROTOCOL.md devices/sofucor_fan.yaml captures/README.md
git commit -m "feat: document Sofucor fan RF protocol and device profile"
```

---

## Phase 4: Python CLI

**What's happening:** The CLI reads the YAML profile and constructs the raw bit sequence to send. For now it sends over HTTP to the NodeMCU (which does the actual RF transmission).

### Task 5: Add YAML parsing + bit-sequence builder

**Files:**
- Modify: `main.py`
- Create: `src/device.py`
- Create: `tests/test_device.py`

**Step 1: Install dependencies**
```bash
uv add pyyaml httpx pytest
```

**Step 2: Write the failing test**

```python
# tests/test_device.py
import pytest
from src.device import DeviceProfile, build_packet

def test_build_packet_for_bedroom_speed1():
    profile = DeviceProfile.load("devices/sofucor_fan.yaml")
    bits = build_packet(profile, unit="bedroom", command="speed_1")
    # address + command concatenated
    assert bits == "10101010" + profile.commands["speed_1"]

def test_unknown_command_raises():
    profile = DeviceProfile.load("devices/sofucor_fan.yaml")
    with pytest.raises(KeyError):
        build_packet(profile, unit="bedroom", command="nonexistent")

def test_unknown_unit_raises():
    profile = DeviceProfile.load("devices/sofucor_fan.yaml")
    with pytest.raises(KeyError):
        build_packet(profile, unit="garage", command="speed_1")
```

**Step 3: Run test to verify it fails**
```bash
pytest tests/test_device.py -v
```
Expected: `ModuleNotFoundError: No module named 'src'`

**Step 4: Implement `src/device.py`**

```python
# src/device.py
from dataclasses import dataclass
from pathlib import Path
import yaml


@dataclass
class DeviceProfile:
    frequency_mhz: float
    encoding: str
    timing: dict
    commands: dict[str, str]
    units: dict[str, dict]

    @classmethod
    def load(cls, path: str) -> "DeviceProfile":
        data = yaml.safe_load(Path(path).read_text())
        return cls(
            frequency_mhz=data["frequency_mhz"],
            encoding=data["encoding"],
            timing=data["timing"],
            commands=data["commands"],
            units=data["units"],
        )


def build_packet(profile: DeviceProfile, unit: str, command: str) -> str:
    address = profile.units[unit]["address"]  # KeyError if unknown unit
    command_bits = profile.commands[command]  # KeyError if unknown command
    return address + command_bits
```

**Step 5: Run test to verify it passes**
```bash
pytest tests/test_device.py -v
```
Expected: 3 PASSED

**Step 6: Commit**
```bash
git add src/device.py tests/test_device.py
git commit -m "feat: device profile loader and packet builder"
```

---

### Task 6: Wire up the CLI entry point

**Files:**
- Modify: `main.py`
- Create: `tests/test_cli.py`

**Step 1: Write the failing test**

```python
# tests/test_cli.py
from click.testing import CliRunner
from main import cli

def test_cli_requires_device_unit_command():
    runner = CliRunner()
    result = runner.invoke(cli, [])
    assert result.exit_code != 0

def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "device" in result.output.lower()
```

**Step 2: Run to confirm failure**
```bash
pytest tests/test_cli.py -v
```

**Step 3: Implement CLI in `main.py`**

```python
# main.py
import click
import httpx
from src.device import DeviceProfile, build_packet


@click.command()
@click.argument("device")
@click.argument("unit")
@click.argument("command")
@click.option("--host", default="nodemcu.local", help="NodeMCU hostname or IP")
@click.option("--port", default=80, help="NodeMCU HTTP port")
def cli(device: str, unit: str, command: str, host: str, port: int):
    """Send an RF command to a device via NodeMCU.

    DEVICE: profile name (e.g. sofucor_fan)\n
    UNIT:   unit name from profile (e.g. bedroom)\n
    COMMAND: command name from profile (e.g. speed_1)
    """
    profile = DeviceProfile.load(f"devices/{device}.yaml")
    packet = build_packet(profile, unit=unit, command=command)

    url = f"http://{host}:{port}/transmit"
    payload = {
        "bits": packet,
        "frequency_mhz": profile.frequency_mhz,
        "timing": profile.timing,
    }
    resp = httpx.post(url, json=payload, timeout=5.0)
    resp.raise_for_status()
    click.echo(f"Sent {command} to {device}/{unit}: {packet}")


if __name__ == "__main__":
    cli()
```

**Step 4: Install click and run tests**
```bash
uv add click
pytest tests/ -v
```
Expected: all pass

**Step 5: Commit**
```bash
git add main.py tests/test_cli.py pyproject.toml uv.lock
git commit -m "feat: CLI entry point with device/unit/command arguments"
```

---

## Phase 5: NodeMCU Firmware

**What's happening:** The ESP8266 runs an HTTP server. When it receives a POST to `/transmit`, it reads the bit string and timing parameters, then toggles the DATA pin HIGH/LOW at the specified intervals. The 315 MHz TX module is always-on carrier — the DATA pin switches the carrier on and off (OOK).

### Task 7: Create PlatformIO project

**Step 1: Create firmware directory structure**
```bash
mkdir -p firmware/src firmware/include
```

**Step 2: Create `firmware/platformio.ini`**
```ini
[env:nodemcuv2]
platform = espressif8266
board = nodemcuv2
framework = arduino
lib_deps =
    ESP8266WiFi
    ESP8266WebServer
    ArduinoJson
monitor_speed = 115200
```

**Step 3: Create `firmware/src/main.cpp`**

```cpp
#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <ArduinoJson.h>

// -- CONFIGURE THESE --
const char* WIFI_SSID = "your_ssid";
const char* WIFI_PASS = "your_password";
const int TX_PIN = D1;  // DATA pin to HiLetgo TX module
// ---------------------

ESP8266WebServer server(80);

void transmitOOK(const String& bits, int syncHighUs, int syncLowUs,
                 int shortUs, int longUs, int bitLowUs, int repeatCount) {
    for (int r = 0; r < repeatCount; r++) {
        // Sync pulse
        digitalWrite(TX_PIN, HIGH); delayMicroseconds(syncHighUs);
        digitalWrite(TX_PIN, LOW);  delayMicroseconds(syncLowUs);
        // Data bits
        for (char bit : bits) {
            int highUs = (bit == '1') ? longUs : shortUs;
            digitalWrite(TX_PIN, HIGH); delayMicroseconds(highUs);
            digitalWrite(TX_PIN, LOW);  delayMicroseconds(bitLowUs);
        }
    }
}

void handleTransmit() {
    if (!server.hasArg("plain")) {
        server.send(400, "text/plain", "No body");
        return;
    }
    StaticJsonDocument<512> doc;
    DeserializationError err = deserializeJson(doc, server.arg("plain"));
    if (err) {
        server.send(400, "text/plain", "Bad JSON");
        return;
    }

    String bits = doc["bits"].as<String>();
    JsonObject t = doc["timing"];

    transmitOOK(
        bits,
        t["sync_high_us"] | 10500,
        t["sync_low_us"]  | 10500,
        t["short_pulse_us"] | 350,
        t["long_pulse_us"]  | 1050,
        t["bit_low_us"]     | 350,
        t["repeat_count"]   | 5
    );

    server.send(200, "text/plain", "OK");
}

void setup() {
    Serial.begin(115200);
    pinMode(TX_PIN, OUTPUT);
    digitalWrite(TX_PIN, LOW);

    WiFi.begin(WIFI_SSID, WIFI_PASS);
    Serial.print("Connecting to WiFi");
    while (WiFi.status() != WL_CONNECTED) {
        delay(500); Serial.print(".");
    }
    Serial.printf("\nIP: %s\n", WiFi.localIP().toString().c_str());

    server.on("/transmit", HTTP_POST, handleTransmit);
    server.begin();
    Serial.println("HTTP server started");
}

void loop() {
    server.handleClient();
}
```

**Step 4: Edit WiFi credentials in main.cpp**
- Replace `your_ssid` and `your_password` with real values

**Step 5: Connect NodeMCU via USB and flash**
```bash
cd firmware
pio run --target upload
pio device monitor  # watch Serial output for IP address
```
Expected output: `IP: 192.168.x.x`

**Step 6: Note the IP address** — use `--host <IP>` in CLI until mDNS is confirmed working

**Step 7: Commit**
```bash
cd ..
git add firmware/
git commit -m "feat: NodeMCU HTTP server firmware for OOK transmission"
```

---

## Phase 6: End-to-End Integration Test

### Task 8: Manual integration test

**Step 1: Run the Python CLI pointing at your NodeMCU IP**
```bash
python main.py sofucor_fan bedroom speed_1 --host 192.168.x.x
```
Expected: fan responds; CLI prints `Sent speed_1 to sofucor_fan/bedroom: <bits>`

**Step 2: Test each command**
```bash
python main.py sofucor_fan bedroom speed_2 --host 192.168.x.x
python main.py sofucor_fan bedroom speed_3 --host 192.168.x.x
python main.py sofucor_fan bedroom off --host 192.168.x.x
python main.py sofucor_fan bedroom light --host 192.168.x.x
```

**Step 3: Test living room fan**
```bash
python main.py sofucor_fan living_room speed_1 --host 192.168.x.x
```

**Step 4: If fan doesn't respond — debug checklist**
- Check Serial monitor: did NodeMCU receive the POST? Did it parse JSON?
- Are bit timings correct? Re-measure in Audacity with more precision
- Is TX module powered from VIN (5V), not 3.3V?
- Check DATA pin wiring: TX module DATA → NodeMCU D1

**Step 5: Final commit**
```bash
git add .
git commit -m "feat: complete phase 1 fan control"
git checkout main
git merge --no-ff claude/phase1-protocol
```

---

## Wiring Reference

```
NodeMCU        HiLetgo MX-FS-03V TX module
--------       -------------------------
VIN (5V)  -->  VCC
GND       -->  GND
D1        -->  DATA (ATAD pin)
```

No breadboard needed — 3 female-to-female dupont wires.

---

## What to Do If You're Stuck

| Symptom | Likely cause | Fix |
|---|---|---|
| No signal in Gqrx | Gain too low | Set to 38 dB, AGC off |
| WAV is pure noise | Wrong frequency | Try 433.92 MHz |
| Can't distinguish pulses in Audacity | Zoom in more | View > Zoom In ×10 |
| NodeMCU won't flash | Wrong COM port | Check `pio device list` |
| Fan doesn't respond to NodeMCU | Wrong bit timing | Re-measure sync/short/long µs |
| Fan responds to one unit but not other | Wrong address bits | Re-compare captures |
