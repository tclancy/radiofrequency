# Generic-Bits Firmware + Fan-2 Verification Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the per-button hardcoded HTTP endpoints on the NodeMCU with a single generic `POST /transmit` endpoint that accepts raw bits + timing, update the CLI to drive it, then empirically map which of the five Sofucor commands actually work on each of the two fans.

**Architecture:** The Mac becomes the brain — Python builds the 32-bit packet from the YAML profile (or from a user-supplied literal via `raw` subcommand) and POSTs `{bits, timing}` JSON to the NodeMCU. The firmware becomes dumb — it validates the payload, toggles `TX_PIN` per the timing dict, returns `200 OK`. Existing hardcoded `/fan/{1,2}/{cmd}` endpoints stay in place during cutover so we can A/B if generic behaviour looks wrong, then get removed once verified.

**Tech Stack:** Python 3.13 (click, httpx, pytest, pyyaml), PlatformIO/Arduino (ESP8266, ArduinoJson)

---

## File Structure

**Modify:**
- [firmware/platformio.ini](firmware/platformio.ini) — add `ArduinoJson` to `lib_deps`
- [firmware/src/main.cpp](firmware/src/main.cpp) — add `handleTransmit()` + `/transmit` route; keep existing routes
- [cli.py](cli.py) — restructure as `click.group` with `send` and `raw` subcommands; POST to `/transmit`
- [src/device.py](src/device.py) — add `build_transmit_payload()` helper

**Create:**
- [tests/test_cli.py](tests/test_cli.py) — click `CliRunner` tests with mocked `httpx`
- [docs/fan-test-matrix.md](docs/fan-test-matrix.md) — empirical results table

**Leave alone:** `devices/sofa_king_fan.yaml` (timing already matches), `PROTOCOL.md`, `signal_explorer.py`.

---

## Task 0: Branch setup

**Files:** none yet

- [ ] **Step 1: Create and check out working branch**

```bash
git checkout -b claude/generic-firmware
git status  # should show clean tree on new branch
```

---

## Task 1: Add ArduinoJson dependency to PlatformIO

**Files:**
- Modify: `firmware/platformio.ini`

- [ ] **Step 1: Add ArduinoJson to lib_deps**

Replace the `lib_deps` block so the file reads:

```ini
[env:nodemcuv2]
platform = espressif8266
board = nodemcuv2
framework = arduino
lib_deps =
    ESP8266WiFi
    ESP8266WebServer
    bblanchon/ArduinoJson@^7.0.0
monitor_speed = 115200
upload_speed = 115200
build_flags = -DPIO_FRAMEWORK_ARDUINO_ENABLE_EXCEPTIONS
```

- [ ] **Step 2: Verify PlatformIO picks up the dependency (compile only, no upload)**

```bash
cd firmware && pio run
```

Expected: `SUCCESS`. The first run will download ArduinoJson — that's normal. If compile fails mentioning `ArduinoJson.h`, confirm internet access and re-run.

- [ ] **Step 3: Commit**

```bash
cd ..
git add firmware/platformio.ini
git commit -m "chore: add ArduinoJson dependency for generic /transmit endpoint"
```

---

## Task 2: Firmware — add generic /transmit endpoint

**Files:**
- Modify: `firmware/src/main.cpp`

**Why this shape:** The endpoint accepts a bit string up to 128 chars (well over 32 for our current protocol, but leaves headroom for other devices later) and a timing object with exactly the six keys the old hardcoded constants represented. Anything missing or out of range returns `400` with a plain-text error so `curl` output is readable. The existing hardcoded endpoints stay in place — do NOT touch lines 79-91 or the route registrations at 124-135. We delete those in a later task only after the generic path is proven.

- [ ] **Step 1: Add the ArduinoJson include at the top**

At line 3 (after the existing `ESP8266WiFi.h` include), add:

```cpp
#include <ArduinoJson.h>
```

- [ ] **Step 2: Add a generic transmit function**

Insert this function immediately after the existing `transmit()` function (after its closing brace around line 73), before the `// ─── HTTP HANDLERS ───` block:

```cpp
// Generic transmit: toggle TX_PIN per an explicit timing spec.
// Used by POST /transmit so the Mac can drive arbitrary bit patterns
// without the firmware knowing anything about the device protocol.
void transmitGeneric(const char *bits,
                     uint32_t sync_us, uint32_t sync_gap_us,
                     uint32_t pulse_us, uint32_t zero_gap_us,
                     uint32_t one_gap_us, int repeat_count) {
    for (int r = 0; r < repeat_count; r++) {
        digitalWrite(TX_PIN, HIGH);
        delayMicroseconds(sync_us);
        digitalWrite(TX_PIN, LOW);
        delayMicroseconds(sync_gap_us);

        for (const char *p = bits; *p; p++) {
            digitalWrite(TX_PIN, HIGH);
            delayMicroseconds(pulse_us);
            digitalWrite(TX_PIN, LOW);
            delayMicroseconds(*p == '1' ? one_gap_us : zero_gap_us);
        }

        ESP.wdtFeed();
    }
}
```

- [ ] **Step 3: Add the HTTP handler**

Immediately after the new `transmitGeneric` function, before `void sendOK()`:

```cpp
// POST /transmit — body is JSON:
//   {"bits": "010...", "timing": {"sync_us":N, "sync_gap_us":N,
//    "pulse_us":N, "zero_gap_us":N, "one_gap_us":N, "repeat_count":N}}
void handleTransmit() {
    if (server.method() != HTTP_POST) {
        server.send(405, "text/plain", "method not allowed\n");
        return;
    }
    if (!server.hasArg("plain")) {
        server.send(400, "text/plain", "missing body\n");
        return;
    }

    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, server.arg("plain"));
    if (err) {
        server.send(400, "text/plain", String("bad json: ") + err.c_str() + "\n");
        return;
    }

    const char *bits = doc["bits"] | (const char *)nullptr;
    if (!bits) {
        server.send(400, "text/plain", "missing 'bits'\n");
        return;
    }
    size_t bitlen = strlen(bits);
    if (bitlen == 0 || bitlen > 128) {
        server.send(400, "text/plain", "bits must be 1..128 chars\n");
        return;
    }
    for (size_t i = 0; i < bitlen; i++) {
        if (bits[i] != '0' && bits[i] != '1') {
            server.send(400, "text/plain", "bits must contain only 0 and 1\n");
            return;
        }
    }

    JsonObject t = doc["timing"].as<JsonObject>();
    if (t.isNull()) {
        server.send(400, "text/plain", "missing 'timing' object\n");
        return;
    }

    const char *required[] = {"sync_us", "sync_gap_us", "pulse_us",
                              "zero_gap_us", "one_gap_us", "repeat_count"};
    for (const char *k : required) {
        if (!t.containsKey(k)) {
            String msg = String("missing timing.") + k + "\n";
            server.send(400, "text/plain", msg);
            return;
        }
    }

    uint32_t sync_us      = t["sync_us"];
    uint32_t sync_gap_us  = t["sync_gap_us"];
    uint32_t pulse_us     = t["pulse_us"];
    uint32_t zero_gap_us  = t["zero_gap_us"];
    uint32_t one_gap_us   = t["one_gap_us"];
    int      repeat_count = t["repeat_count"];

    // Sanity clamps. Anything outside these is almost certainly a typo/bug
    // and we'd rather fail loudly than sit in delayMicroseconds() forever.
    auto badUs = [](uint32_t v) { return v == 0 || v > 100000; };
    if (badUs(sync_us) || badUs(sync_gap_us) || badUs(pulse_us) ||
        badUs(zero_gap_us) || badUs(one_gap_us)) {
        server.send(400, "text/plain", "timing microsecond values must be 1..100000\n");
        return;
    }
    if (repeat_count < 1 || repeat_count > 100) {
        server.send(400, "text/plain", "repeat_count must be 1..100\n");
        return;
    }

    transmitGeneric(bits, sync_us, sync_gap_us,
                    pulse_us, zero_gap_us, one_gap_us, repeat_count);

    String reply = String("OK ") + bitlen + " bits x " + repeat_count + " reps\n";
    server.send(200, "text/plain", reply);
}
```

- [ ] **Step 4: Register the route**

Inside `setup()`, after the existing `server.on("/fan/2/speed3"...)` line (around line 135), before `server.onNotFound(send404)`, add:

```cpp
    // Generic endpoint — preferred path, used by cli.py send & raw
    server.on("/transmit", HTTP_POST, handleTransmit);
```

Also update the `Serial.println` at the bottom of `setup()` so the bootup banner reflects the new route. Replace:

```cpp
    Serial.println("Endpoints: /fan/{1,2}/{light,off,speed1,speed2,speed3}");
```

with:

```cpp
    Serial.println("Endpoints:");
    Serial.println("  POST /transmit                (generic bits + timing)");
    Serial.println("  GET  /fan/{1,2}/{light,off,speed1,speed2,speed3}  (legacy hardcoded)");
```

- [ ] **Step 5: Compile-check**

```bash
cd firmware && pio run
```

Expected: `SUCCESS`. If the linker complains about `transmitGeneric` mismatch, check that the function prototype matches the call.

- [ ] **Step 6: Commit**

```bash
cd ..
git add firmware/src/main.cpp
git commit -m "feat(firmware): add generic POST /transmit endpoint"
```

---

## Task 3: Flash and smoke-test firmware

**Files:** none (manual hardware test)

**Why:** Before writing any CLI code, confirm the firmware works end-to-end with `curl`. If we can drive fan 1's light with a hand-rolled JSON payload, the transport layer is proved and every subsequent failure is a Python bug.

- [ ] **Step 1: Confirm WIFI_PASS is set to the real password**

Check `firmware/src/main.cpp:8`. The literal `"password"` is a placeholder — if it's still there, replace it with the real value before flashing. Do **not** commit the real password.

- [ ] **Step 2: Flash and watch serial**

```bash
cd firmware
pio run --target upload
pio device monitor
```

Wait for the serial output to show `Connected! IP: 192.168.x.x` and `HTTP server ready`. Note the IP. If it times out, check SSID/password.

- [ ] **Step 3: Smoke test — hit the OLD endpoint as a baseline**

In another terminal, replace `<IP>` with the NodeMCU IP:

```bash
curl -v "http://<IP>/fan/1/light"
```

Expected: `HTTP/1.1 200 OK`, body `OK`. Bedroom fan's light should toggle. If this fails, the regression is our firmware change — stop and debug before going further.

- [ ] **Step 4: Smoke test the NEW endpoint with the same bits**

The fan-1 light packet is `10001100111101101100000000111111`:

```bash
curl -v -X POST "http://<IP>/transmit" \
  -H 'Content-Type: application/json' \
  -d '{
    "bits":"10001100111101101100000000111111",
    "timing":{"sync_us":8000,"sync_gap_us":670,"pulse_us":400,
              "zero_gap_us":670,"one_gap_us":1800,"repeat_count":20}
  }'
```

Expected: `HTTP/1.1 200 OK`, body `OK 32 bits x 20 reps`. Bedroom light should toggle.

- [ ] **Step 5: Smoke test validation**

```bash
curl -v -X POST "http://<IP>/transmit" -H 'Content-Type: application/json' -d '{"bits":""}'
curl -v -X POST "http://<IP>/transmit" -H 'Content-Type: application/json' -d '{"bits":"01x0","timing":{}}'
```

Expected: both return `400 Bad Request` with a plain-text error message. Confirms validation fires.

- [ ] **Step 6: Record the IP for the CLI tests**

Note the IP in your scratch notes (or set an env var):

```bash
export FAN_HOST=<IP>
```

No commit in this task — it's verification, not code.

---

## Task 4: CLI — refactor to click group with `send` and `raw`

**Files:**
- Modify: `cli.py`
- Create: `tests/test_cli.py`
- Modify: `src/device.py` (add helper)

**Why this shape:** Single-command CLI doesn't fit once we need two usage modes. `click.group` with subcommands is idiomatic. A `build_transmit_payload` helper in `src/device.py` keeps payload shape in one place so `send` and `raw` can't drift from each other.

### Task 4a: Add the payload helper

- [ ] **Step 1: Write the failing test**

Create or append to `tests/test_device.py` (add to the end):

```python
from src.device import build_transmit_payload


def test_build_transmit_payload_shape(profile):
    payload = build_transmit_payload(profile, bits="01" * 16)
    assert payload["bits"] == "01" * 16
    assert set(payload["timing"].keys()) == {
        "sync_us", "sync_gap_us", "pulse_us",
        "zero_gap_us", "one_gap_us", "repeat_count",
    }
    assert payload["timing"]["pulse_us"] == 400
    assert payload["timing"]["repeat_count"] == 20


def test_build_transmit_payload_rejects_bad_bits(profile):
    with pytest.raises(ValueError):
        build_transmit_payload(profile, bits="")
    with pytest.raises(ValueError):
        build_transmit_payload(profile, bits="0102")
```

- [ ] **Step 2: Run the tests to confirm failure**

```bash
uv run pytest tests/test_device.py::test_build_transmit_payload_shape -v
```

Expected: `ImportError: cannot import name 'build_transmit_payload'`.

- [ ] **Step 3: Implement the helper**

Append to `src/device.py`:

```python
_TIMING_KEYS = (
    "sync_us", "sync_gap_us", "pulse_us",
    "zero_gap_us", "one_gap_us", "repeat_count",
)


def build_transmit_payload(profile: DeviceProfile, bits: str) -> dict:
    """Return the JSON-ready payload for POST /transmit.

    Raises ValueError if bits is empty or contains non-binary characters.
    """
    if not bits:
        raise ValueError("bits must be non-empty")
    if not set(bits).issubset({"0", "1"}):
        raise ValueError("bits must contain only '0' and '1'")
    timing = {k: profile.timing[k] for k in _TIMING_KEYS}
    return {"bits": bits, "timing": timing}
```

- [ ] **Step 4: Run the tests to confirm pass**

```bash
uv run pytest tests/test_device.py -v
```

Expected: all green, including the two new ones.

- [ ] **Step 5: Commit**

```bash
git add src/device.py tests/test_device.py
git commit -m "feat: add build_transmit_payload helper"
```

### Task 4b: Refactor CLI into click group

- [ ] **Step 1: Write the failing test**

Create `tests/test_cli.py`:

```python
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from cli import cli


@pytest.fixture
def runner():
    return CliRunner()


def test_help_lists_subcommands(runner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "send" in result.output
    assert "raw" in result.output


def test_send_posts_to_transmit_endpoint(runner):
    with patch("cli.httpx.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200, text="OK")
        mock_post.return_value.raise_for_status = MagicMock()

        result = runner.invoke(
            cli,
            ["send", "sofa_king_fan", "bedroom", "light", "--host", "1.2.3.4"],
        )

    assert result.exit_code == 0, result.output
    assert mock_post.call_count == 1
    url, = mock_post.call_args.args
    assert url == "http://1.2.3.4:80/transmit"
    payload = mock_post.call_args.kwargs["json"]
    assert payload["bits"] == "10001100111101101100000000111111"
    assert payload["timing"]["pulse_us"] == 400


def test_send_rejects_unknown_unit(runner):
    with patch("cli.httpx.post") as mock_post:
        result = runner.invoke(
            cli,
            ["send", "sofa_king_fan", "garage", "light", "--host", "1.2.3.4"],
        )
    assert result.exit_code != 0
    assert "unknown unit" in result.output.lower()
    assert mock_post.call_count == 0


def test_raw_posts_arbitrary_bits(runner):
    with patch("cli.httpx.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200, text="OK")
        mock_post.return_value.raise_for_status = MagicMock()

        result = runner.invoke(
            cli,
            [
                "raw", "01" * 16,
                "--device", "sofa_king_fan",
                "--host", "1.2.3.4",
            ],
        )

    assert result.exit_code == 0, result.output
    assert mock_post.call_count == 1
    payload = mock_post.call_args.kwargs["json"]
    assert payload["bits"] == "01" * 16
    assert payload["timing"]["pulse_us"] == 400


def test_raw_rejects_non_binary(runner):
    with patch("cli.httpx.post") as mock_post:
        result = runner.invoke(
            cli,
            ["raw", "01x0", "--device", "sofa_king_fan", "--host", "1.2.3.4"],
        )
    assert result.exit_code != 0
    assert mock_post.call_count == 0
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_cli.py -v
```

Expected: all fail. The current `cli.py` is a single command, not a group — `send` and `raw` don't exist.

- [ ] **Step 3: Rewrite `cli.py` as a group**

Replace the entire contents of `cli.py` with:

```python
#!/usr/bin/env python3
"""Control RF devices via NodeMCU HTTP API.

    python cli.py send sofa_king_fan bedroom light --host 192.168.1.42
    python cli.py raw 10001100111101101100000000111111 \\
        --device sofa_king_fan --host 192.168.1.42
"""
import sys

import click
import httpx

from src.device import DeviceProfile, build_packet, build_transmit_payload

DEVICES_DIR = "devices"


def _load_profile(device: str) -> DeviceProfile:
    return DeviceProfile.load(f"{DEVICES_DIR}/{device}.yaml")


def _post_transmit(host: str, port: int, payload: dict) -> None:
    url = f"http://{host}:{port}/transmit"
    try:
        resp = httpx.post(url, json=payload, timeout=10.0)
        resp.raise_for_status()
    except httpx.ConnectError:
        click.echo(f"Error: could not connect to {host}:{port}", err=True)
        sys.exit(1)
    except httpx.HTTPStatusError as exc:
        body = exc.response.text.strip()
        click.echo(
            f"Error: NodeMCU returned {exc.response.status_code} — {body}",
            err=True,
        )
        sys.exit(1)


@click.group()
def cli() -> None:
    """Control RF devices via NodeMCU HTTP API."""


@cli.command()
@click.argument("device")
@click.argument("unit")
@click.argument("command")
@click.option("--host", default="nodemcu.local", show_default=True)
@click.option("--port", default=80, show_default=True)
def send(device: str, unit: str, command: str, host: str, port: int) -> None:
    """Send a named command from a device profile (e.g. bedroom light)."""
    profile = _load_profile(device)

    if unit not in profile.units:
        available = ", ".join(sorted(profile.units))
        click.echo(f"Error: unknown unit '{unit}'. Available: {available}", err=True)
        sys.exit(1)

    if command not in profile.commands:
        available = ", ".join(sorted(profile.commands))
        click.echo(f"Error: unknown command '{command}'. Available: {available}", err=True)
        sys.exit(1)

    bits = build_packet(profile, unit=unit, command=command)
    payload = build_transmit_payload(profile, bits=bits)
    _post_transmit(host, port, payload)
    click.echo(f"OK  {command} → {device}/{unit}  [{bits}]")


@cli.command()
@click.argument("bits")
@click.option("--device", required=True, help="Device profile whose timing to use.")
@click.option("--host", default="nodemcu.local", show_default=True)
@click.option("--port", default=80, show_default=True)
def raw(bits: str, device: str, host: str, port: int) -> None:
    """Transmit an arbitrary bit string using a device profile's timing."""
    profile = _load_profile(device)
    try:
        payload = build_transmit_payload(profile, bits=bits)
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    _post_transmit(host, port, payload)
    click.echo(f"OK  raw [{bits}]  ({len(bits)} bits) via {device}")


if __name__ == "__main__":
    cli()
```

- [ ] **Step 4: Run tests to confirm pass**

```bash
uv run pytest tests/test_cli.py tests/test_device.py -v
```

Expected: all green.

- [ ] **Step 5: Hit the live NodeMCU as a sanity check**

```bash
uv run python cli.py send sofa_king_fan bedroom light --host $FAN_HOST
uv run python cli.py raw 10001100111101101100000000111111 --device sofa_king_fan --host $FAN_HOST
```

Both should return `OK ...` and the bedroom light should toggle twice.

- [ ] **Step 6: Commit**

```bash
git add cli.py tests/test_cli.py
git commit -m "feat(cli): split into 'send' and 'raw' subcommands over /transmit"
```

---

## Task 5: Empirical fan test matrix

**Files:**
- Create: `docs/fan-test-matrix.md`

**Why:** Before we reason about what's broken, get the raw data. Tom's recollection is that the only confirmed-working combination was "light on fan 2." Verify all ten cells against physical hardware, one at a time, using the new CLI.

- [ ] **Step 1: Scaffold the results doc**

Create `docs/fan-test-matrix.md` with:

```markdown
# Sofucor Fan Test Matrix

Date: 2026-04-19
Firmware: claude/generic-firmware branch
CLI: `uv run python cli.py send ...`

Legend: ✓ = fan responded as expected. ✗ = no response. ? = partial / intermittent.
Leave a cell blank until tested.

## Results

| Unit         | light | off | speed1 | speed2 | speed3 |
|--------------|-------|-----|--------|--------|--------|
| bedroom      |       |     |        |        |        |
| living_room  |       |     |        |        |        |

## Notes

- Test each cell by running: `uv run python cli.py send sofa_king_fan <unit> <cmd> --host $FAN_HOST`
- Wait ~2 seconds between commands so the fan's receiver re-arms.
- For light, confirm it toggles (state-change), not absolute on/off.
- Record the distance from TX antenna to fan if coverage seems position-dependent.
```

- [ ] **Step 2: Run the matrix**

Walk every cell. For each command:

```bash
uv run python cli.py send sofa_king_fan bedroom light --host $FAN_HOST
# wait ~2s, observe fan, mark cell
```

- [ ] **Step 3: Fill in the results doc**

Edit `docs/fan-test-matrix.md` with observations. Add prose notes for anything surprising (intermittent responses, position-sensitive, speeds that work from one remote but not the other, etc.).

- [ ] **Step 4: Commit**

```bash
git add docs/fan-test-matrix.md
git commit -m "docs: record empirical fan-command test matrix"
```

---

## Task 6: (Conditional) Fan-2 failure investigation

**Run this task only if Task 5 shows failures on fan 2 that aren't explainable by signal strength.**

**Files:** append findings to `docs/fan-test-matrix.md`.

**Hypotheses to test with `cli.py raw`:**

- [ ] **H1: address decoded wrong.** Swap remote-1 and remote-2 addresses in front of a known-working command (e.g. speed1). If fan 2 responds to `remote1_address + speed1_command`, our fan-2 address decoding is wrong.

```bash
# remote 1 addr + speed1 cmd — should drive fan 1 (baseline)
uv run python cli.py raw 10001100111101100001000011101111 --device sofa_king_fan --host $FAN_HOST
# remote 2 addr + speed1 cmd — should drive fan 2
uv run python cli.py raw 11110001001110110001000011101111 --device sofa_king_fan --host $FAN_HOST
```

- [ ] **H2: command bits leak into address.** Compare fan-2 captures across two known-working commands. Identify bits that differ between `off` and `speed1` in remote 2 and check whether any of those bits are in the "address" range.

Capture two fresh WAVs for remote 2 with `rtl_fm` and re-decode in `signal_explorer.py`. Diff the decoded 32-bit strings.

- [ ] **H3: signal strength.** Repeat the failing command(s) at short range (TX 30 cm from fan) vs. install location. If short range succeeds and install range fails, it's an antenna/power issue, not a bits issue.

- [ ] **H4: repeat_count too low.** Real remote sends 36–41 reps; firmware sends 20. Retry failing commands with:

```bash
# Temporarily bump repeats by editing devices/sofa_king_fan.yaml repeat_count: 40
# (or pass via a future --repeat flag if we add one — not in scope for now).
```

- [ ] **Step: Write findings back into `docs/fan-test-matrix.md`**

Append a `## Investigation` section with one subsection per hypothesis, noting which were ruled in / out.

- [ ] **Step: Commit**

```bash
git add docs/fan-test-matrix.md devices/sofa_king_fan.yaml
git commit -m "docs: fan-2 failure investigation"
```

---

## Task 7: (Optional) Retire legacy hardcoded endpoints

**Only do this after Tom confirms the generic path has been reliable for at least one full session.**

**Files:**
- Modify: `firmware/src/main.cpp`

- [ ] **Step 1: Delete the hardcoded handlers and route registrations**

Remove lines 79-91 (the `h1*` / `h2*` handler functions) and lines 124-135 (their `server.on(...)` registrations). Also remove the constants `ADDR_FAN1`, `ADDR_FAN2`, `CMD_LIGHT`, `CMD_OFF`, `CMD_SPEED1`, `CMD_SPEED2`, `CMD_SPEED3` if nothing else references them.

Update the boot banner at the bottom of `setup()`:

```cpp
    Serial.println("Endpoint: POST /transmit  (generic bits + timing)");
```

- [ ] **Step 2: Flash and confirm only the generic endpoint remains**

```bash
cd firmware && pio run --target upload
curl -v "http://$FAN_HOST/fan/1/light"      # expect 404
curl -v -X POST "http://$FAN_HOST/transmit" \
     -H 'Content-Type: application/json' \
     -d '{"bits":"10001100111101101100000000111111",
          "timing":{"sync_us":8000,"sync_gap_us":670,"pulse_us":400,
                    "zero_gap_us":670,"one_gap_us":1800,"repeat_count":20}}'
# expect 200 + bedroom light toggle
```

- [ ] **Step 3: Commit and merge**

```bash
cd ..
git add firmware/src/main.cpp
git commit -m "refactor(firmware): remove legacy hardcoded endpoints"
git checkout main
git merge --no-ff claude/generic-firmware
```

---

## Out of Scope (explicitly)

- Multiple firmware folders with a `/firmware` symlink (rejected in planning discussion — use branches).
- A `test-matrix` CLI subcommand that prompts for Y/N (manual is fine at 10 cells).
- `--repeat` / `--timing-override` CLI flags (add later if H4 looks promising).
- Non-Sofucor device profiles (TPMS, other remotes) — handled in a separate project phase.
- mDNS / `nodemcu.local` debugging — if DNS fails during Task 3, fall back to the IP.

---

## What "done" looks like

- Firmware exposes `POST /transmit` and the legacy routes (legacy stays until Task 7 if ever).
- `cli.py send` and `cli.py raw` both hit `/transmit`, both pass their tests.
- `docs/fan-test-matrix.md` has a filled-in results table and (if needed) an investigation section.
- Tom has physical evidence of which fan-2 commands actually work.
