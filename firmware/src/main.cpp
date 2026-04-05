#include <Arduino.h>
#include <ESP8266WebServer.h>
#include <ESP8266WiFi.h>

// ─── USER CONFIG ──────────────────────────────────────────────────────────────
const char *WIFI_SSID = "your_ssid";      // <── change before flashing
const char *WIFI_PASS = "your_password";  // <── change before flashing
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

// ─── HTTP HANDLERS ───────────────────────────────────────────────────────────
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

    WiFi.begin(WIFI_SSID, WIFI_PASS);
    Serial.print("\nConnecting to WiFi");
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.printf("\nIP: %s\n", WiFi.localIP().toString().c_str());

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

    server.onNotFound(send404);
    server.begin();
    Serial.println("HTTP server ready");
    Serial.println("Endpoints: /fan/{1,2}/{light,off,speed1,speed2,speed3}");
}

// ─── LOOP ────────────────────────────────────────────────────────────────────
void loop() {
    server.handleClient();
}
