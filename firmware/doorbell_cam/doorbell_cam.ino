/*
 * DoorbellCam — ESP32-CAM (AI-Thinker) firmware
 * ------------------------------------------------
 * Streams MJPEG over WiFi, exposes a CameraWebServer-compatible settings API
 * (/control, /status), an identity marker (/api/whoami) for auto-discovery,
 * and a doorbell button input (GPIO13, active-LOW, use internal pull-up).
 *
 * WiFi credentials come from include/secrets.h (generated from .env by
 * scripts/gen_secrets.py). If both secrets and stored credentials fail,
 * the module falls back to a setup Access Point "DoorbellCam-Setup"
 * where you can pick a network from a phone.
 *
 * mDNS: doorbellcam.local  +  _doorbellcam._tcp (service discovery)
 */

#include "secrets.h"

#include <WiFi.h>
#include <WebServer.h>
#include <ESPmDNS.h>
#include <Preferences.h>

#include "esp_camera.h"
#include "img_converters.h"
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"
#include "driver/ledc.h"

// ---------------- AI-Thinker pin map ----------------
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

#define FLASH_LED_PIN      4   // on-board flash LED
#define STATUS_LED_PIN    33   // on-board red LED (inverted)
#define DOORBELL_BTN_PIN  13   // external doorbell button (to GND)

#ifndef CAMERA_NAME
#define CAMERA_NAME "doorbellcam"
#endif

WebServer server(80);
Preferences prefs;

bool camOk = false;
volatile bool doorbellPressed = false;
unsigned long lastBtnMs = 0;
uint32_t frameCount = 0;
uint32_t streamClients = 0;   // diagnostic: total clients served by the task
unsigned long bootMs = 0;

// ------------------------------------------------------------------ helpers
static void blinkStatus(int times, int ms = 150) {
  for (int i = 0; i < times; i++) {
    digitalWrite(STATUS_LED_PIN, LOW);   // inverted LED
    delay(ms);
    digitalWrite(STATUS_LED_PIN, HIGH);
    delay(ms);
  }
}

static bool connectWiFi() {
  const char* ssid = WIFI_SSID;
  const char* pass = WIFI_PASSWORD;

#if defined(WIFI_SSID) && defined(WIFI_PASSWORD)
  if (ssid && strlen(ssid) > 0) {
    Serial.printf("[WiFi] Trying credentials from secrets.h: %s\n", ssid);
    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid, pass);
    unsigned long start = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - start < 20000) {
      delay(250);
      Serial.print(".");
    }
    Serial.println();
    if (WiFi.status() == WL_CONNECTED) return true;
  }
#endif

  // Fallback: credentials stored in NVS (set via /setup page or AP)
  String nvsSsid = prefs.getString("ssid", "");
  String nvsPass = prefs.getString("pass", "");
  if (nvsSsid.length()) {
    Serial.printf("[WiFi] Trying credentials from NVS: %s\n", nvsSsid.c_str());
    WiFi.mode(WIFI_STA);
    WiFi.begin(nvsSsid.c_str(), nvsPass.c_str());
    unsigned long start = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - start < 20000) {
      delay(250);
      Serial.print(".");
    }
    Serial.println();
    if (WiFi.status() == WL_CONNECTED) return true;
  }
  return false;
}

// Setup AP with captive-style page: choose network, enter password.
static String scanNetworksJson() {
  int n = WiFi.scanComplete();
  if (n < 0) WiFi.scanNetworks(true);
  String out = "[";
  if (n > 0) {
    for (int i = 0; i < n; i++) {
      if (i) out += ",";
      out += "{\"ssid\":\"" + WiFi.SSID(i) + "\",\"rssi\":" + String(WiFi.RSSI(i)) + "}";
    }
  }
  out += "]";
  return out;
}

static void startSetupAP() {
  const char* apName = "DoorbellCam-Setup";
  WiFi.mode(WIFI_AP);
  WiFi.softAP(apName);
  Serial.printf("[WiFi] Setup AP started: %s  IP: %s\n", apName, WiFi.softAPIP().toString().c_str());

  server.on("/scan", HTTP_GET, []() { server.send(200, "application/json", scanNetworksJson()); });
  server.on("/save", HTTP_GET, []() {
    if (server.hasArg("ssid") && server.arg("ssid").length()) {
      prefs.putString("ssid", server.arg("ssid"));
      prefs.putString("pass", server.arg("pass"));
      server.send(200, "text/html", "<h3>Saved. Rebooting…</h3>");
      delay(800);
      ESP.restart();
    } else {
      server.send(400, "text/html", "missing ssid");
    }
  });
  server.onNotFound([]() {
    server.send(200, "text/html",
      "<html><head><meta name=viewport content='width=device-width,initial-scale=1'>"
      "<title>DoorbellCam setup</title></head><body style='font-family:sans-serif;max-width:420px;margin:2em auto'>"
      "<h2>&#128274; DoorbellCam setup</h2>"
      "<div id='nets'>Scanning…</div>"
      "<script>fetch('/scan').then(r=>r.json()).then(l=>{document.getElementById('nets').innerHTML="
      "l.map(n=>`<a href='#' onclick=\"document.getElementById('s').value='${n.ssid}';return false\">${n.ssid} (${n.rssi})</a><br>`).join('')});</script>"
      "<form action='/save'><input id='s' name='ssid' placeholder='WiFi name' style='width:100%;padding:8px;margin:8px 0'>"
      "<input name='pass' type='password' placeholder='WiFi password' style='width:100%;padding:8px;margin:8px 0'>"
      "<button style='width:100%;padding:10px'>Save &amp; reboot</button></form>"
      "</body></html>");
  });
  server.begin();
}

// ------------------------------------------------------------------ camera
static bool initCamera() {
  // Power-cycle the sensor first — fixes detection on many clone boards
  pinMode(PWDN_GPIO_NUM, OUTPUT);
  digitalWrite(PWDN_GPIO_NUM, HIGH);   // sensor off
  delay(300);
  digitalWrite(PWDN_GPIO_NUM, LOW);    // sensor on
  delay(300);

  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 10000000;   // 10 MHz: clones often fail SCCB probe at 20 MHz
  config.pixel_format = PIXFORMAT_JPEG;
  // LATEST: keep capturing continuously so fb_get returns instantly (~4 fps
  // stream). WHEN_EMPTY saves idle power but fb_get then blocks ~2.4 s per
  // frame waiting for a fresh capture — far too slow for motion detection.
  config.grab_mode = CAMERA_GRAB_LATEST;
  config.fb_location = CAMERA_FB_IN_PSRAM;

  if (psramFound()) {
    config.frame_size = FRAMESIZE_SVGA;   // 800x600 default; changeable via /control
    config.jpeg_quality = 12;
    config.fb_count = 2;
  } else {
    // No PSRAM (common on clones): VGA JPEG still fits in DRAM with 1 buffer
    config.frame_size = FRAMESIZE_VGA;
    config.jpeg_quality = 14;
    config.fb_count = 1;
    config.fb_location = CAMERA_FB_IN_DRAM;
  }

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("[Cam] init FAILED 0x%x\n", err);
    return false;
  }
  sensor_t* s = esp_camera_sensor_get();
  s->set_vflip(s, 0);
  s->set_hmirror(s, 0);
  Serial.println("[Cam] init OK");
  return true;
}

// ------------------------------------------------------------------ handlers
static void handleWhoami() {
  String json = "{\"product\":\"doorbellcam\",\"name\":\"" CAMERA_NAME "\","
                "\"model\":\"ai_thinker\",\"fw\":\"1.0.0\","
                "\"ip\":\"" + WiFi.localIP().toString() + "\","
                "\"uptime_s\":" + String((millis() - bootMs) / 1000) + "}";
  server.send(200, "application/json", json);
}

static void handleStatus() {
  if (!camOk) { server.send(503, "application/json", "{\"error\":\"camera unavailable\"}"); return; }
  sensor_t* s = esp_camera_sensor_get();
  int fs = s->status.framesize;
  int fw = 0, fh = 0;
  switch (fs) {
    case FRAMESIZE_QQVGA: fw = 160;  fh = 120;  break;
    case FRAMESIZE_QVGA:  fw = 320;  fh = 240;  break;
    case FRAMESIZE_VGA:   fw = 640;  fh = 480;  break;
    case FRAMESIZE_SVGA:  fw = 800;  fh = 600;  break;
    case FRAMESIZE_XGA:   fw = 1024; fh = 768;  break;
    case FRAMESIZE_HD:    fw = 1280; fh = 720;  break;
    case FRAMESIZE_SXGA:  fw = 1280; fh = 1024; break;
    case FRAMESIZE_UXGA:  fw = 1600; fh = 1200; break;
    default: break;
  }
  String json = "{"
    "\"framesize\":" + String(fs) + ","
    "\"quality\":" + String(s->status.quality) + ","
    "\"brightness\":" + String(s->status.brightness) + ","
    "\"contrast\":" + String(s->status.contrast) + ","
    "\"saturation\":" + String(s->status.saturation) + ","
    "\"special_effect\":" + String(s->status.special_effect) + ","
    "\"vflip\":" + String(s->status.vflip) + ","
    "\"hmirror\":" + String(s->status.hmirror) + ","
    "\"awb\":" + String(s->status.awb) + ","
    "\"agc\":" + String(s->status.agc) + ","
    "\"aec\":" + String(s->status.aec) + ","
    "\"aec2\":" + String(s->status.aec2) + ","
    "\"agc_gain\":" + String(s->status.agc_gain) + ","
    "\"aec_value\":" + String(s->status.aec_value) + ","
    "\"bpc\":" + String(s->status.bpc) + ","
    "\"wpc\":" + String(s->status.wpc) + ","
    "\"raw_gma\":" + String(s->status.raw_gma) + ","
    "\"lenc\":" + String(s->status.lenc) + ","
    "\"dcw\":" + String(s->status.dcw) + ","
    "\"xclk\":" + String(s->xclk_freq_hz / 1000000) + ","
    "\"doorbell\":" + String(doorbellPressed ? 1 : 0) + ","
    "\"frames\":" + String(frameCount) + ","
    "\"stream_clients\":" + String(streamClients) + ","
    "\"rssi\":" + String(WiFi.RSSI()) + ","
    "\"width\":" + String(fw) + ","
    "\"height\":" + String(fh) +
    "}";
  server.send(200, "application/json", json);
}

static void handleControl() {
  if (!camOk) { server.send(503, "application/json", "{\"error\":\"camera unavailable\"}"); return; }
  if (!server.hasArg("var") || !server.hasArg("val")) {
    server.send(400, "application/json", "{\"error\":\"var & val required\"}");
    return;
  }
  String var = server.arg("var");
  int val = server.arg("val").toInt();
  sensor_t* s = esp_camera_sensor_get();
  int r = 0;
  if      (var == "framesize")      r = s->set_framesize(s, (framesize_t)val);
  else if (var == "quality")        r = s->set_quality(s, val);
  else if (var == "brightness")     r = s->set_brightness(s, val);
  else if (var == "contrast")       r = s->set_contrast(s, val);
  else if (var == "saturation")     r = s->set_saturation(s, val);
  else if (var == "special_effect") r = s->set_special_effect(s, val);
  else if (var == "vflip")          r = s->set_vflip(s, val);
  else if (var == "hmirror")        r = s->set_hmirror(s, val);
  else if (var == "awb")            r = s->set_whitebal(s, val);
  else if (var == "agc")            r = s->set_gain_ctrl(s, val);
  else if (var == "aec")            r = s->set_exposure_ctrl(s, val);
  else if (var == "hmirror")        r = s->set_hmirror(s, val);
  else if (var == "dcw")            r = s->set_dcw(s, val);
  else if (var == "raw_gma")        r = s->set_raw_gma(s, val);
  else if (var == "lenc")           r = s->set_lenc(s, val);
  else if (var == "flash") { digitalWrite(FLASH_LED_PIN, val ? HIGH : LOW); r = 1; }
  else { server.send(400, "application/json", "{\"error\":\"unknown var\"}"); return; }
  server.send(200, "application/json", "{\"ok\":" + String(r == 0 ? "true" : "false") + ",\"var\":\"" + var + "\",\"val\":" + String(val) + "}");
}

static void handleCapture() {
  if (!camOk) { server.send(503, "text/plain", "camera unavailable"); return; }
  camera_fb_t* fb = fbTake();
  if (!fb) { server.send(500, "text/plain", "capture failed"); return; }
  server.sendHeader("Content-Disposition", "inline; filename=capture.jpg");
  server.send_P(200, "image/jpeg", (const char*)fb->buf, fb->len);
  esp_camera_fb_return(fb);
}

static void handleDoorbell() {
  String json = "{\"doorbell\":" + String(doorbellPressed ? 1 : 0) + ",\"ms\":" + String(millis() - lastBtnMs) + "}";
  server.send(200, "application/json", json);
}

// ------------------------------------------------------------------ stream task
// The MJPEG stream runs in its own FreeRTOS task pinned to core 0 so that a
// long-lived stream client (the hub holds one permanently) never starves the
// control HTTP server running in loop() on core 1.
static SemaphoreHandle_t camMutex;
static TaskHandle_t streamTaskHandle;

static camera_fb_t* fbTake() {
  xSemaphoreTake(camMutex, portMAX_DELAY);
  camera_fb_t* fb = esp_camera_fb_get();
  xSemaphoreGive(camMutex);
  return fb;
}

static void streamGreet(WiFiClient& c) {
  c.print("HTTP/1.1 200 OK\r\n"
          "Content-Type: multipart/x-mixed-replace; boundary=doorbellframe\r\n"
          "Access-Control-Allow-Origin: *\r\n"
          "Cache-Control: no-store\r\n\r\n");
}

static void streamTaskFn(void*) {
  WiFiServer streamSrv(81);
  streamSrv.setNoDelay(true);
  streamSrv.begin();
  Serial.println("[Stream] task on core 0, port 81");

  for (;;) {
    // accept() returns a pending connection regardless of data; available()
    // would require the client to have sent bytes first.
    WiFiClient client = streamSrv.accept();
    if (!client) {
      vTaskDelay(pdMS_TO_TICKS(20));
      continue;
    }
    if (!camOk) { client.stop(); continue; }

    client.setNoDelay(true);
    client.setConnectionTimeout(2000);  // SO_SNDTIMEO: writes fail fast on zombies
    streamClients++;
    streamGreet(client);

    unsigned long started = millis();
    while (client.connected()) {
      // Rotate the single stream slot: a stalled/zombie client (hub restart,
      // lost TCP teardown) must never wedge the stream forever. The hub
      // reconnects immediately on this polite close.
      // NOTE: do NOT call accept() here to "preempt" for a newer client —
      // calling accept() while a connection is being served wedged lwIP on
      // this core version (whole device went TCP-dead within minutes).
      if (millis() - started > 90000) break;

      camera_fb_t* fb = fbTake();
      if (!fb) break;
      frameCount++;
      client.printf("--doorbellframe\r\nContent-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n", fb->len);
      size_t written = client.write(fb->buf, fb->len);
      esp_camera_fb_return(fb);
      if (written == 0) break;
      vTaskDelay(pdMS_TO_TICKS(250));  // ~4 fps at SVGA: plenty for a doorbell,
                                       // leaves the single core free for control
    }
    client.stop();
    vTaskDelay(pdMS_TO_TICKS(100));    // let the next queued client connect
  }
}

// ------------------------------------------------------------------ setup
void setup() {
  // NOTE: the brownout detector stays ENABLED — a 3V3 sag then produces a
  // clean ~10 s reboot (which the hub re-discovers) instead of risking a
  // silent latch. (The silent hangs observed earlier were caused by calling
  // accept() mid-serve in the stream task, not by brownout.)

  Serial.begin(115200);
  Serial.setDebugOutput(true);
  Serial.println("\n[Boot] DoorbellCam starting…");

  pinMode(STATUS_LED_PIN, OUTPUT);
  digitalWrite(STATUS_LED_PIN, HIGH);
  pinMode(FLASH_LED_PIN, OUTPUT);
  digitalWrite(FLASH_LED_PIN, LOW);
  pinMode(DOORBELL_BTN_PIN, INPUT_PULLUP);

  prefs.begin("doorbellcam", false);

  camOk = initCamera();
  camMutex = xSemaphoreCreateMutex();

  if (!connectWiFi()) {
    Serial.println("[WiFi] Could not connect — starting setup AP mode");
    blinkStatus(5);
    startSetupAP();
    bootMs = millis();
    return;                       // stay in AP mode; user configures from a phone
  }

  Serial.printf("[WiFi] Connected: %s  RSSI %d dBm\n", WiFi.localIP().toString().c_str(), WiFi.RSSI());
  blinkStatus(2);

  // Stream task only after the WiFi stack is up — starting it earlier asserts
  // inside lwIP (xQueueSemaphoreTake) because the TCP/IP queue isn't ready.
  if (camOk) {
    xTaskCreatePinnedToCore(streamTaskFn, "stream", 8192, NULL, 1,
                            &streamTaskHandle, 0);   // core 0; loop runs on core 1
  }

  // mDNS + service advertisement for auto-discovery
  if (MDNS.begin(CAMERA_NAME)) {
    MDNS.addService("_doorbellcam", "_tcp", 81);
    MDNS.addServiceTxt("_doorbellcam", "_tcp", "product", "doorbellcam");
    MDNS.addServiceTxt("_doorbellcam", "_tcp", "model", "ai_thinker");
    MDNS.addServiceTxt("_doorbellcam", "_tcp", "path", "/api/whoami");
    Serial.println("[mDNS] doorbellcam.local advertised");
  } else {
    Serial.println("[mDNS] failed to start");
  }

  server.on("/api/whoami", HTTP_GET, handleWhoami);
  server.on("/status", HTTP_GET, handleStatus);
  server.on("/control", HTTP_GET, handleControl);
  server.on("/capture", HTTP_GET, handleCapture);
  server.on("/api/doorbell", HTTP_GET, handleDoorbell);
  server.on("/", HTTP_GET, []() {
    server.send(200, "application/json",
      "{\"product\":\"doorbellcam\",\"name\":\"" CAMERA_NAME "\",\"stream\":\"/api/stream\",\"port\":81}");
  });
  server.begin();

  bootMs = millis();
  Serial.println("[HTTP] Ready: /api/whoami  /status  /control  /capture  :81/api/stream (task)");
}

void loop() {
  // doorbell button debounce (GPIO13, active LOW)
  if (digitalRead(DOORBELL_BTN_PIN) == LOW && millis() - lastBtnMs > 1000) {
    doorbellPressed = true;
    lastBtnMs = millis();
    Serial.println("[Doorbell] button pressed!");
    digitalWrite(FLASH_LED_PIN, HIGH);
    delay(60);
    digitalWrite(FLASH_LED_PIN, LOW);
  }

  if (WiFi.getMode() & WIFI_AP) {           // AP setup mode: only web config
    server.handleClient();
    blinkStatus(1, 400);
    delay(100);
    return;
  }

  server.handleClient();

  // self-heal WiFi
  static unsigned long lastCheck = 0;
  if (millis() - lastCheck > 10000) {
    lastCheck = millis();
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("[WiFi] reconnecting…");
      WiFi.reconnect();
    }
  }

  // heartbeat: proves the app is alive and shows WiFi/stream state on the
  // serial console — a stopped heartbeat means the chip itself died.
  static unsigned long lastBeat = 0;
  if (millis() - lastBeat > 30000) {
    lastBeat = millis();
    Serial.printf("[Beat] up=%lus rssi=%d frames=%u served=%u wifi=%d\n",
                  millis() / 1000, WiFi.RSSI(), frameCount, streamClients,
                  (int)WiFi.status());
  }

  // auto-clear doorbell flag after hub had a chance to poll it (2 s)
  static unsigned long dbMs = 0;
  if (doorbellPressed && millis() - lastBtnMs > 2000) {
    doorbellPressed = false;
    (void)dbMs;
  }
}
