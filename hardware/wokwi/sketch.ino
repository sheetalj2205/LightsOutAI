/*
  Lights Out AI — simulated ESP32 + NeoPixel "mini building" (runs in Wokwi)

  One LED per window. The ESP32 joins the backend's WebSocket as an LED board:
      ws://<server>/ws?device=led&floors=5&cols=6
  and gets:
      {"type":"frame","states":"OODF...","colors":["ffe6b4",...]}   full building
      {"led":7,"state":"off"}                                       one LED changed
  It replies {"led":7,"state":"off","ok":true}.

  LED index 0 = bottom-left window, counting left->right then up a floor.
  Blue "Demo" button = offline demo (works without the server).

  Settings: config.h (server address, grid size).
  Libraries (libraries.txt): WebSockets, ArduinoJson, Adafruit NeoPixel.
*/
#include <WiFi.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>
#include <Adafruit_NeoPixel.h>
#include "config.h"

// ---- Defaults (override any of these in config.h) ----
#ifndef LED_PIN
#define LED_PIN 5
#endif
#ifndef FLOORS
#define FLOORS 5
#endif
#ifndef COLS
#define COLS 6
#endif
#ifndef SERPENTINE
#define SERPENTINE true      // strip snakes back and forth, row by row
#endif
#ifndef START_AT_TOP
#define START_AT_TOP false   // true if the strip's first LED is in the top row
#endif
#ifndef MAX_BRIGHTNESS
#define MAX_BRIGHTNESS 255
#endif
#ifndef DIM_LEVEL
#define DIM_LEVEL 0.22
#endif
#ifndef BUTTON_PIN
#define BUTTON_PIN 0         // the "Demo" push button in diagram.json
#endif
#ifndef USE_SSL
#define USE_SSL false
#endif
#ifndef WIFI_CHANNEL
#define WIFI_CHANNEL 6       // Wokwi-GUEST is on channel 6; skips the Wi-Fi scan
#endif

constexpr int N = FLOORS * COLS;
constexpr uint32_t WARM_WHITE = 0xFFE6B4;

Adafruit_NeoPixel strip(N, LED_PIN, NEO_GRB + NEO_KHZ800);
WebSocketsClient ws;

float cur[N][3];        // what each LED shows now (for fading)
float tgt[N][3];        // where it is fading to
uint32_t color[N];      // window light color
char ledState[N];       // 'O' on, 'D' dim, 'F' off
bool gotFrame = false;  // false until the server sends the building
bool serverUp = false;

// Offline demo: windows switch one by one, top floor first.
int demoQueue[N];
int demoLen = 0, demoPos = 0;
bool demoActive = false;
unsigned long demoLast = 0;

// ---------------------------------------------------------------------------

int physicalIndex(int i) {
  int row = i / COLS, col = i % COLS;  // row 0 = bottom floor
  if (START_AT_TOP) row = FLOORS - 1 - row;
  if (SERPENTINE && (row % 2 == 1)) col = COLS - 1 - col;
  return row * COLS + col;
}

void setLed(int i, char st) {
  if (i < 0 || i >= N) return;
  ledState[i] = st;
  float level = st == 'O' ? 1.0f : (st == 'D' ? DIM_LEVEL : 0.0f);
  tgt[i][0] = ((color[i] >> 16) & 0xFF) * level;
  tgt[i][1] = ((color[i] >> 8) & 0xFF) * level;
  tgt[i][2] = (color[i] & 0xFF) * level;
}

char codeOf(const char* state) {
  if (!state) return 'O';
  if (strcmp(state, "off") == 0) return 'F';
  if (strcmp(state, "dim") == 0) return 'D';
  return 'O';
}

void allOn() {
  for (int i = 0; i < N; i++) setLed(i, 'O');
}

// ---------------------------------------------------------------------------

void handleMessage(uint8_t* payload, size_t len) {
  JsonDocument doc;
  if (deserializeJson(doc, payload, len)) return;

  if (doc["type"] == "frame") {
    const char* states = doc["states"] | "";
    JsonArray colors = doc["colors"];
    for (int i = 0; i < N; i++) {
      const char* hex = colors[i] | "ffe6b4";
      color[i] = strtoul(hex, nullptr, 16);
      setLed(i, i < (int)strlen(states) ? states[i] : 'F');
    }
    if ((doc["floors"] | FLOORS) != FLOORS || (doc["cols"] | COLS) != COLS)
      Serial.println("Warning: server grid size differs from FLOORS/COLS");
    gotFrame = true;
    demoActive = false;
    Serial.printf("Building received: %s\n", states);
  } else if (doc["led"].is<int>()) {
    int i = doc["led"];
    const char* st = doc["state"] | "on";
    setLed(i, codeOf(st));
    char reply[64];
    snprintf(reply, sizeof(reply), "{\"led\":%d,\"state\":\"%s\",\"ok\":true}", i, st);
    ws.sendTXT(reply);
  }
}

void onEvent(WStype_t type, uint8_t* payload, size_t len) {
  switch (type) {
    case WStype_CONNECTED:
      serverUp = true;
      Serial.println("Connected to Lights Out AI");
      break;
    case WStype_DISCONNECTED:
      serverUp = false;
      Serial.println("Disconnected, retrying...");
      break;
    case WStype_TEXT:
      handleMessage(payload, len);
      break;
    default:
      break;
  }
}

// ---------------------------------------------------------------------------

void startOfflineDemo() {
  // If the upper floors are all lit: lights out, top floor first (lobby stays on).
  // Otherwise (fresh board, or after a lights-out): light the whole building.
  bool anyOff = false;
  for (int i = COLS; i < N; i++) if (ledState[i] != 'O') anyOff = true;
  if (anyOff) {
    allOn();
    demoActive = false;
    Serial.println("Demo: all lights back on");
    return;
  }
  demoLen = 0;
  for (int i = N - 1; i >= COLS; i--) demoQueue[demoLen++] = i;
  demoPos = 0;
  demoActive = true;
  Serial.println("Demo: lights out");
}

void stepDemo() {
  if (!demoActive || millis() - demoLast < 90) return;
  demoLast = millis();
  int i = demoQueue[demoPos];
  setLed(i, (i % 4 == 0) ? 'D' : 'F');  // a few stay dimmed, like the AI does
  if (++demoPos >= demoLen) demoActive = false;
}

void checkButton() {
  static bool last = HIGH;
  static unsigned long changed = 0;
  bool now = digitalRead(BUTTON_PIN);
  if (now != last && millis() - changed > 40) {
    changed = millis();
    last = now;
    if (now == LOW) startOfflineDemo();
  }
}

void render() {
  static unsigned long lastFrame = 0;
  if (millis() - lastFrame < 15) return;
  lastFrame = millis();
  for (int i = 0; i < N; i++) {
    for (int c = 0; c < 3; c++) cur[i][c] += (tgt[i][c] - cur[i][c]) * 0.12f;  // smooth fade
    strip.setPixelColor(physicalIndex(i), strip.Color((uint8_t)cur[i][0], (uint8_t)cur[i][1], (uint8_t)cur[i][2]));
  }
  // Before the building arrives, pulse the bottom-left LED: blue = joining Wi-Fi, amber = finding server.
  if (ledState[0] == 'S') {  // cleared as soon as a frame or the demo sets LED 0
    float p = (sin(millis() / 300.0) + 1) / 2;
    uint32_t c = WiFi.status() != WL_CONNECTED ? strip.Color(0, 0, 40 + 120 * p) : strip.Color(120 * p + 40, 60 * p + 20, 0);
    strip.setPixelColor(physicalIndex(0), c);
  }
  strip.show();
}

// ---------------------------------------------------------------------------

void setup() {
  Serial.begin(115200);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  strip.begin();
  strip.setBrightness(MAX_BRIGHTNESS);
  for (int i = 0; i < N; i++) {
    color[i] = WARM_WHITE;
    ledState[i] = 'F';
    for (int c = 0; c < 3; c++) cur[i][c] = tgt[i][c] = 0;
  }
  ledState[0] = 'S';  // status pulse until connected
  strip.show();

  Serial.printf("Joining Wi-Fi %s ...\n", WIFI_SSID);
  Serial.printf("Server: %s://%s:%d\n", USE_SSL ? "wss" : "ws", SERVER_HOST, SERVER_PORT);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS, WIFI_CHANNEL);
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 20000) {
    render();
    checkButton();
    delay(10);
  }
  if (WiFi.status() == WL_CONNECTED)
    Serial.printf("Wi-Fi OK, IP %s\n", WiFi.localIP().toString().c_str());
  else
    Serial.println("No Wi-Fi yet (still retrying). Press the Demo button for the offline demo.");

  String path = String("/ws?device=led&floors=") + FLOORS + "&cols=" + COLS;
  if (USE_SSL) ws.beginSSL(SERVER_HOST, SERVER_PORT, path.c_str());
  else ws.begin(SERVER_HOST, SERVER_PORT, path.c_str());
  ws.onEvent(onEvent);
  ws.setReconnectInterval(2000);
  ws.enableHeartbeat(15000, 3000, 2);
}

void loop() {
  ws.loop();
  checkButton();
  stepDemo();
  render();
}
