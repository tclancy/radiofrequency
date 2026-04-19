#include <Arduino.h>
#include <ArduinoJson.h>
#include <ESP8266WebServer.h>
#include <ESP8266WiFi.h>

// ─── USER CONFIG ──────────────────────────────────────────────────────────────
const char *WIFI_SSID = "22 Parsons";
const char *WIFI_PASS = "password";
const int   TX_PIN    = D1;               // DATA pin → HiLetgo MX-FS-03V TX module
// ──────────────────────────────────────────────────────────────────────────────

// ─── PROTOCOL TIMING (µs) ─────────────────────────────────────────────────────
// Sofucor fan remote: OOK Pulse Distance
//   each bit = PULSE_US HIGH + gap LOW
//   gap LOW: ZERO_GAP (bit 0) or ONE_GAP (bit 1)
//   sync = SYNC_US HIGH burst before each code repetition
//
// If the fan doesn't respond, try increasing SYNC_GAP_US (e.g. 4000–10000 µs)
// or reducing REPEAT_N to see if timing is the issue.
//
const uint32_t SYNC_US    = 8000;  // sync HIGH pulse before each repetition
const uint32_t SYNC_GAP   =  670;  // LOW gap between sync and first data bit
const uint32_t PULSE_US   =  400;  // carrier-ON pulse (same for all bits)
const uint32_t ZERO_GAP   =  670;  // LOW gap = bit 0
const uint32_t ONE_GAP    = 1800;  // LOW gap = bit 1
const int      REPEAT_N   =   20;  // repetitions per button press (remote uses 36–41)
// ──────────────────────────────────────────────────────────────────────────────

// ─── FAN ADDRESSES (bits 0–15, unique per remote/fan pair) ───────────────────
const char *ADDR_FAN1 = "1000110011110110";  // bedroom
const char *ADDR_FAN2 = "1111000100111011";  // living room

// ─── COMMAND CODES (bits 16–31, shared across all fan units) ─────────────────
const char *CMD_LIGHT  = "1100000000111111";  // verified: fan 1
const char *CMD_OFF    = "0100000010111111";  // verified: fans 1 and 2
const char *CMD_SPEED1 = "0001000011101111";  // verified: fans 1 and 2
const char *CMD_SPEED2 = "1001000001101111";  // verified: fan 1 (derived for fan 2)
const char *CMD_SPEED3 = "0100100010110111";  // verified: fan 1 (derived for fan 2)

ESP8266WebServer server(80);

// ─── RF TRANSMISSION ─────────────────────────────────────────────────────────
// Builds a 32-bit packet from addr (16 chars) + cmd (16 chars), then sends it
// REPEAT_N times with a sync pulse before each repetition.
//
// Note: delayMicroseconds() on the ESP8266 is accurate to ±1–2 µs. WiFi ISRs
// can add brief jitter between repetitions, which is fine — the fan's receiver
// integrates across all repetitions and only needs a few clean ones to decode.
//
void transmit(const char *addr, const char *cmd) {
    char packet[33];
    memcpy(packet, addr, 16);
    memcpy(packet + 16, cmd, 16);
    packet[32] = '\0';

    for (int r = 0; r < REPEAT_N; r++) {
        // Sync: long carrier burst so receiver can (re)lock AGC
        digitalWrite(TX_PIN, HIGH);
        delayMicroseconds(SYNC_US);
        digitalWrite(TX_PIN, LOW);
        delayMicroseconds(SYNC_GAP);

        // 32 data bits, MSB first
        for (int i = 0; i < 32; i++) {
            digitalWrite(TX_PIN, HIGH);
            delayMicroseconds(PULSE_US);
            digitalWrite(TX_PIN, LOW);
            delayMicroseconds(packet[i] == '1' ? ONE_GAP : ZERO_GAP);
        }

        // Feed watchdog between repetitions (total tx time ≈ 1.2 s)
        ESP.wdtFeed();
    }
}

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

// ─── HTTP HANDLERS ───────────────────────────────────────────────────────────
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

void sendOK()  { server.send(200, "text/plain", "OK\n"); }
void send404() { server.send(404, "text/plain", "Not Found\n"); }

// Fan 1 — bedroom
void h1Light()  { transmit(ADDR_FAN1, CMD_LIGHT);  sendOK(); }
void h1Off()    { transmit(ADDR_FAN1, CMD_OFF);    sendOK(); }
void h1Speed1() { transmit(ADDR_FAN1, CMD_SPEED1); sendOK(); }
void h1Speed2() { transmit(ADDR_FAN1, CMD_SPEED2); sendOK(); }
void h1Speed3() { transmit(ADDR_FAN1, CMD_SPEED3); sendOK(); }

// Fan 2 — living room
void h2Light()  { transmit(ADDR_FAN2, CMD_LIGHT);  sendOK(); }
void h2Off()    { transmit(ADDR_FAN2, CMD_OFF);    sendOK(); }
void h2Speed1() { transmit(ADDR_FAN2, CMD_SPEED1); sendOK(); }
void h2Speed2() { transmit(ADDR_FAN2, CMD_SPEED2); sendOK(); }
void h2Speed3() { transmit(ADDR_FAN2, CMD_SPEED3); sendOK(); }

// ─── SETUP ───────────────────────────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    pinMode(TX_PIN, OUTPUT);
    digitalWrite(TX_PIN, LOW);

    WiFi.mode(WIFI_STA);              // station mode only (no AP)
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    Serial.printf("\nConnecting to WiFi SSID: [%s]\n", WIFI_SSID);

    const unsigned long WIFI_TIMEOUT_MS = 30000;  // 30 s then give up
    unsigned long start = millis();
    while (WiFi.status() != WL_CONNECTED) {
        ESP.wdtFeed();                 // pet the watchdog so it doesn't bite
        delay(500);
        Serial.print(".");
        if (millis() - start > WIFI_TIMEOUT_MS) {
            Serial.println("\n*** WiFi connection timed out after 30 s ***");
            Serial.printf("WiFi.status() = %d\n", WiFi.status());
            Serial.println("Check SSID/password. Retrying in 5 s...");
            delay(5000);
            ESP.wdtFeed();
            WiFi.disconnect();
            delay(100);
            WiFi.begin(WIFI_SSID, WIFI_PASS);
            start = millis();          // reset the timer for another attempt
        }
    }
    Serial.printf("\nConnected! IP: %s\n", WiFi.localIP().toString().c_str());

    // Fan 1 (bedroom)
    server.on("/fan/1/light",  HTTP_GET, h1Light);
    server.on("/fan/1/off",    HTTP_GET, h1Off);
    server.on("/fan/1/speed1", HTTP_GET, h1Speed1);
    server.on("/fan/1/speed2", HTTP_GET, h1Speed2);
    server.on("/fan/1/speed3", HTTP_GET, h1Speed3);

    // Fan 2 (living room)
    server.on("/fan/2/light",  HTTP_GET, h2Light);
    server.on("/fan/2/off",    HTTP_GET, h2Off);
    server.on("/fan/2/speed1", HTTP_GET, h2Speed1);
    server.on("/fan/2/speed2", HTTP_GET, h2Speed2);
    server.on("/fan/2/speed3", HTTP_GET, h2Speed3);

    // Generic endpoint — preferred path, used by cli.py send & raw
    server.on("/transmit", HTTP_POST, handleTransmit);

    server.onNotFound(send404);
    server.begin();
    Serial.println("HTTP server ready");
    Serial.println("Endpoints:");
    Serial.println("  POST /transmit                (generic bits + timing)");
    Serial.println("  GET  /fan/{1,2}/{light,off,speed1,speed2,speed3}  (legacy hardcoded)");
}

// ─── LOOP ────────────────────────────────────────────────────────────────────
void loop() {
    server.handleClient();
}
