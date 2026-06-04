# Serial 設定プロトコル仕様書

## 1. 概要

Desktop アプリ（hapbeat-desktop）から Hapbeat デバイスに USB serial 経由で設定を行うためのプロトコル。Kit install プロトコル（バイナリフレーム）と同一の serial ポート上で共存する。

## 2. 通信仕様

| 項目 | 値 |
|------|-----|
| インターフェース | USB CDC Serial |
| ボーレート | 921600 |
| フォーマット | JSON（1行1コマンド、`\n` 終端） |
| エンコーディング | UTF-8 |
| 最大コマンド長 | 512 bytes |

## 3. Kit install プロトコルとの共存

同一 serial ポート上で Kit install プロトコル（バイナリフレーム、先頭バイト `0xAA`）と共存する。

| 先頭バイト | ルーティング先 |
|-----------|---------------|
| `{` (0x7B) | Serial 設定プロトコル（本仕様） |
| `0xAA` | Kit install プロトコル |
| その他 | 無視 |

デバイスは受信バイトの先頭を確認し、適切なハンドラにルーティングする。

## 4. コマンド一覧

### 4.1 get_info — デバイス情報取得

**Request:**
```json
{"cmd": "get_info"}
```

**Response:**
```json
{
  "status": "ok",
  "cmd": "get_info",
  "data": {
    "name": "Hapbeat-A",
    "address": "player_1/chest",
    "firmware": "2.0.0",
    "mac": "AA:BB:CC:DD:EE:FF",
    "role": "receiver",
    "transport": "udp",
    "transports": ["udp"],
    "board": "band_wl_v3",
    "wifi_connected": false,
    "wifi_ssid": "",
    "wifi_ip": "",
    "espnow_channel": 1,
    "broker_host": "auto"
  }
}
```

`role` / `transport` / `board` は **全ノード必須**（`node-roles.md` §4）。
`transports` は複数 transport 対応時のみ。役割固有フィールド（`broker_host` / `gain` / `input_level` / `static_octet` / `mqtt_port` / `mappings` 等）は当該役割でのみ含める。

### 4.2 set_wifi — Wi-Fi 認証情報設定

**Request:**
```json
{"cmd": "set_wifi", "ssid": "MyNetwork", "password": "mypass123"}
```

**Response（成功）:**
```json
{"status": "ok", "cmd": "set_wifi"}
```

**Response（エラー）:**
```json
{"status": "error", "cmd": "set_wifi", "message": "SSID is required"}
```

設定は NVS に保存される。反映には再起動が必要。

### 4.3 set_name — デバイス名設定

**Request:**
```json
{"cmd": "set_name", "name": "Hapbeat-LeftArm"}
```

デバイス名は最大 32 文字（UTF-8）。mDNS ホスト名にも使用される。

**Response:**
```json
{"status": "ok", "cmd": "set_name"}
```

### 4.4 set_address — デバイスアドレス設定

**Request:**
```json
{"cmd": "set_address", "address": "red/player_1/chest"}
```

アドレスはスラッシュ区切りの文字列（最大 64 bytes）。末尾2セグメントは `player_{N}/{position}` 形式。詳細は `device-addressing.md` を参照。

**Response:**
```json
{"status": "ok", "address": "red/player_1/chest"}
```

### 4.5 get_wifi_status — Wi-Fi 接続状態取得

**Request:**
```json
{"cmd": "get_wifi_status"}
```

**Response:**
```json
{
  "status": "ok",
  "cmd": "get_wifi_status",
  "data": {
    "connected": true,
    "ssid": "MyNetwork",
    "ip": "192.168.1.50",
    "rssi": -45,
    "channel": 6
  }
}
```

### 4.6 clear_wifi — Wi-Fi 認証情報削除

**Request:**
```json
{"cmd": "clear_wifi"}
```

**Response:**
```json
{"status": "ok", "cmd": "clear_wifi"}
```

### 4.7 reboot — デバイス再起動

**Request:**
```json
{"cmd": "reboot"}
```

**Response:**
```json
{"status": "ok", "cmd": "reboot"}
```

レスポンス送信後、500ms 後に再起動する。

## 4b. 役割固有コマンド（node-roles）

以下は `node-roles.md` で定義する役割（receiver/sensor/broker/transmitter）固有のコマンド。
当該役割を持たないノードは `{"status":"error","cmd":"<cmd>","message":"unsupported for role"}` を返す。

### 4.8 set_broker_host — MQTT broker アドレス設定（receiver(mqtt) / sensor）

**Request:**
```json
{"cmd": "set_broker_host", "host": "auto"}
```

`host` は `"auto"`（mDNS `_mqtt._tcp` で自動発見）または明示的なホスト/IP（例: `"192.168.1.10"` / `"hapbeat-broker.local"`）。
`port` は省略可（既定 1883）。詳細は `mqtt-transport.md`。

**Response:** `{"status": "ok", "cmd": "set_broker_host", "host": "auto"}`

### 4.9 set_espnow_channel — ESP-NOW チャンネル設定（receiver(espnow_stream) / transmitter）

**Request:**
```json
{"cmd": "set_espnow_channel", "channel": 6}
```

`channel` ∈ {1, 6, 11}（`espnow-stream.md`）。送信機と全受信機で一致させる必要がある。NVS `espnow/channel` に保存。

**Response:** `{"status": "ok", "cmd": "set_espnow_channel", "channel": 6}`

### 4.10 set_gain — espnow_stream 受信の既定ゲイン（receiver(espnow_stream)）

**Request:**
```json
{"cmd": "set_gain", "gain": 0.8}
```

`gain` ∈ [0.0, 1.0]。本体のアナログボリュームとは独立した、ストリーミング再生のソフトウェア既定ゲイン。

**Response:** `{"status": "ok", "cmd": "set_gain", "gain": 0.8}`

### 4.11 set_input_level — ライン入力レベル（transmitter）

**Request:**
```json
{"cmd": "set_input_level", "level": 50}
```

`level` ∈ [0, 100]（codec の ADC/ライン入力ゲインを正規化した値）。

**Response:** `{"status": "ok", "cmd": "set_input_level", "level": 50}`

### 4.12 set_broker_config — 組み込み broker 設定（broker）

**Request:**
```json
{"cmd": "set_broker_config", "static_octet": 10, "port": 1883}
```

`static_octet` ∈ [2, 254]：ゲートウェイ subnet 上で broker が名乗る固定ホストオクテット。`port` 省略時 1883。詳細は `mqtt-transport.md` §3。

**Response:** `{"status": "ok", "cmd": "set_broker_config", "static_octet": 10, "port": 1883}`

### 4.13 set_sensor_mapping / get_sensor_mapping — センサ → event 対応表（sensor）

センサ読み取り値の分類結果（例: 検出色）を、発火する **event_id / target / gain** に対応づける表。
Studio の mapping editor（Unity EventMap 相当）が編集し、ノードに書き込む。

**Request（set）:**
```json
{
  "cmd": "set_sensor_mapping",
  "mappings": [
    {"key": "red",  "match": {"r_min": 140, "g_max": 70, "b_max": 70},  "event_id": "alert-kit.urgent",  "target": "player_1/chest", "gain": 1.0},
    {"key": "blue", "match": {"r_max": 70, "g_max": 90, "b_min": 120},  "event_id": "alert-kit.calm",    "target": "", "gain": 0.7}
  ]
}
```

`match` の意味はセンサ種別に依存する（色センサは RGB 閾値ボックス）。`event_id` は Kit manifest の `events`（command-mode）キー。`target` は `device-addressing.md` 準拠。
詳細は `mqtt-transport.md` §5。

**Response（set）:** `{"status": "ok", "cmd": "set_sensor_mapping", "count": 2}`

**Request（get）:** `{"cmd": "get_sensor_mapping"}`
**Response（get）:** `{"status": "ok", "cmd": "get_sensor_mapping", "data": {"mappings": [ ... ]}}`

## 5. NVS キー一覧

| namespace | key | 型 | 説明 |
|-----------|-----|-----|------|
| hapbeat | address | string (max 64) | デバイスアドレス（例: `player_1/chest`） |
| hapbeat | dev_name | string | デバイス名（最大 32 文字） |
| hapbeat | wifi_ssid | string | Wi-Fi SSID |
| hapbeat | wifi_pass | string | Wi-Fi パスワード |
| hapbeat | broker_host | string | MQTT broker アドレス（`auto` or host/IP）。receiver(mqtt)/sensor |
| hapbeat | sens_map | blob/json | センサ → event 対応表（sensor） |
| espnow | channel | uint8 | ESP-NOW チャンネル（既存） |
| espnow | gain | float | espnow_stream 受信の既定ゲイン（receiver(espnow_stream)） |
| broker | octet | uint8 | broker static host octet（broker） |
| broker | port | uint16 | broker MQTT ポート（broker、既定 1883） |

## 6. エラーハンドリング

- 不正な JSON → 無視（レスポンスなし）
- 未知のコマンド → `{"status": "error", "cmd": "unknown", "message": "Unknown command"}`
- 必須フィールド欠落 → `{"status": "error", "cmd": "...", "message": "..."}`
