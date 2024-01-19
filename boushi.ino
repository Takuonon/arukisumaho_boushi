#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <FS.h>
#include <SPIFFS.h>
#include "AudioFileSourceSPIFFS.h"
#include "AudioGeneratorWAV.h"
#include "AudioOutputI2S.h"

const int motorPinRight = 17; // モータドライバのIN1ピン
const int motorPinLeft = 27; // モータドライバのIN2ピン

const char* ssid = "your-wifi-ssid";     // WiFiのSSID
const char* password = "your-wifi-pass"; // WiFiのパスワード

bool pinTriggered = false; // 18番ピンがHIGHになったかどうかを示すフラグ

WebServer server(80);

AudioGeneratorWAV *wav;
AudioFileSourceSPIFFS *file;
AudioOutputI2S *out;
int DirectionReceived;

File uploadedFile;

// テキストとWAVファイルを受け取るためのハンドラ
void handleWavUpload() {
    HTTPUpload& upload = server.upload();
    if (upload.status == UPLOAD_FILE_START) {
        String filename = "/audio/uploaded.wav";
        SPIFFS.remove(filename);
        uploadedFile = SPIFFS.open(filename, FILE_WRITE);
    } else if (upload.status == UPLOAD_FILE_WRITE) {
        if (uploadedFile) {
            uploadedFile.write(upload.buf, upload.currentSize);
        }
    } else if (upload.status == UPLOAD_FILE_END) {
        if (uploadedFile) {
            uploadedFile.close();
            server.send(200, "text/plain", "WAV upload complited");
        }
    }
}

// 単純なテキストデータを処理するハンドラ
void handleSimpleTextUpload() {
    if (server.hasArg("plain")) {
        String text = server.arg("plain");
        Serial.println(text); // 受信したテキストをシリアルモニタに表示

        // 1で右折、2で左折などの指示を処理
        if (text == "1") {
            DirectionReceived = 1;
            server.send(200, "text/plain", "Direction received");
        } else if (text == "2") {
            DirectionReceived = 2;
            server.send(200, "text/plain", "Direction received");
        } else if (text == "0") {
            DirectionReceived = 0;
            server.send(200, "text/plain", "Direction received");
        } else {
            server.send(200, "text/plain", "Unknown direction");
        }
    } else {
        server.send(500, "text/plain", "No text received");
    }
}


void playWavFile() {
file = new AudioFileSourceSPIFFS("/audio/uploaded.wav");
wav = new AudioGeneratorWAV();
if (wav->begin(file, out)) {
Serial.println("再生を始めます");
server.send(200, "text/plain", "WAV file received");

} else {
Serial.println("再生開始に失敗しました");
server.send(500, "text/plain", "WAV file failed");
}
}

void handlePinState() {
    if (pinTriggered) {
        // ピンが一度HIGHになった後の最初のリクエストに対して「1」を返す
        server.send(200, "text/plain", "1");
        pinTriggered = false; // フラグをリセット
    } else {
        server.send(200, "text/plain", "0");
    }
}

void setup() {
Serial.begin(115200);
DirectionReceived = 0;
if (!SPIFFS.begin(true)) {
Serial.println("SPIFFSの初期化に失敗しました");
return;
}
// WiFi接続の初期化
WiFi.begin(ssid, password);
while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.println("WiFiに接続中...");
}
Serial.println("WiFiに接続されました");

// ESP32のIPアドレスをシリアルモニタに表示
Serial.print("ESP32のIPアドレス: ");
Serial.println(WiFi.localIP());

pinMode(22, INPUT);
pinMode(motorPinRight, OUTPUT);
pinMode(motorPinLeft, OUTPUT);

digitalWrite(motorPinRight, LOW); // モータ停止
digitalWrite(motorPinLeft, LOW);

// Audio出力の初期化
out = new AudioOutputI2S(0, 1, 25);
out->begin();

server.on("/upload", HTTP_POST, []() {
    playWavFile();
}, handleWavUpload);

server.on("/direction", HTTP_POST, handleSimpleTextUpload);

server.on("/pinstate", HTTP_GET, handlePinState);

server.begin();
}

void loop() {
server.handleClient();
if (wav && wav->isRunning()) {
  // Serial.print("DirectionReceived: ");
  // Serial.println(DirectionReceived);
        if (DirectionReceived == 1){
          digitalWrite(motorPinRight, HIGH); // モータを正転させる  
          digitalWrite(motorPinLeft, LOW);
        } else if (DirectionReceived == 2){
          digitalWrite(motorPinRight, LOW); 
          digitalWrite(motorPinLeft, HIGH);
        }
        if (!wav->loop()) {
            wav->stop();
            digitalWrite(motorPinRight, LOW); // モータ停止
            digitalWrite(motorPinLeft, LOW);
        }
    } else {
        digitalWrite(motorPinRight, LOW); // モータ停止
        digitalWrite(motorPinLeft, LOW);
    }

    // 18番ピンの状態をチェックし、HIGHになった場合はフラグをセット
    if (digitalRead(22) == HIGH) {
        pinTriggered = true;
    }
  
  //Serial.print("pinTriggered: ");
  //Serial.println(pinTriggered);

}