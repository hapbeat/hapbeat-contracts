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
    "wifi_connected": false,
    "wifi_ssid": "",
    "wifi_ip": "",
    "espnow_channel": 1
  }
}
```

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

## 5. NVS キー一覧

| namespace | key | 型 | 説明 |
|-----------|-----|-----|------|
| hapbeat | address | string (max 64) | デバイスアドレス（例: `player_1/chest`） |
| hapbeat | dev_name | string | デバイス名（最大 32 文字） |
| hapbeat | wifi_ssid | string | Wi-Fi SSID |
| hapbeat | wifi_pass | string | Wi-Fi パスワード |
| espnow | channel | uint8 | ESP-NOW チャンネル（既存） |

## 6. エラーハンドリング

- 不正な JSON → 無視（レスポンスなし）
- 未知のコマンド → `{"status": "error", "cmd": "unknown", "message": "Unknown command"}`
- 必須フィールド欠落 → `{"status": "error", "cmd": "...", "message": "..."}`
