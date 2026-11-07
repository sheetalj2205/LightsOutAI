// Settings for the Wokwi simulation. Edit SERVER_HOST before you press Play.
#pragma once

#define WIFI_SSID "Wokwi-GUEST"   // Wokwi's built-in open network
#define WIFI_PASS ""

// Free Wokwi can only reach the public internet, not "localhost". Use one of:
//   Vultr server by IP:      "45.x.x.x",       port 80,  USE_SSL false
//   Your domain with HTTPS:  "yourdomain.xyz", port 443, USE_SSL true
// (no http://, no slash at the end)
#define SERVER_HOST "YOUR_VULTR_IP"
#define SERVER_PORT 80
#define USE_SSL false

// LED grid = the model building: FLOORS rows x COLS windows. Keep in sync with diagram.json.
#define FLOORS 5
#define COLS 6
#define LED_PIN 5
#define SERPENTINE true      // matches "matrixLayout": "serpentine"
#define START_AT_TOP true    // Wokwi's matrix starts at the top-left pixel
