# Hapbeat Bridge API 仕様書

## 1. 概要

Hapbeat Bridge は、ホスト PC 上で動作する中継サービスである。各種 SDK（Unity、Unreal、TouchDesigner、Max）から送られる軽量コマンドを受信し、送信機ファームウェアへ転送する役割を担う。

Bridge の責務範囲は以下のとおりである。

- SDK からの UDP/OSC コマンドの受信と解釈
- デバイスレジストリの管理（接続デバイスの検出・状態管理）
- 時刻同期の基準時刻提供
- 送信機ファームウェアへのコマンドディスパッチ

Bridge が担当 **しない** 処理は以下のとおりである。

- Kit のロードや wav 再生（デバイスファームウェアの責務）
- ESP-NOW の直接送信（送信機ファームウェアの責務）

通信フロー全体像:

```
SDK → (UDP/OSC) → Bridge → (内部通信) → 送信機ファームウェア → (ESP-NOW) → Hapbeat デバイス
```

---

## 2. 設計原則

| 原則 | 説明 |
|------|------|
| SDK に独自プロトコルを持たせない | SDK は標準的な UDP 送信のみを行い、プロトコルの複雑さは Bridge が吸収する |
| ローカルネットワーク完結 | すべての通信はローカルネットワーク内で完結する。インターネット接続は不要 |
| 低遅延 | 触覚フィードバックの即時性を確保するため、コマンド処理は最小遅延で行う |
| プラットフォーム中立 | UDP/HTTP/OSC という標準プロトコルを採用し、あらゆるプラットフォーム・言語から利用可能とする |

---

## 3. ネットワーク構成

### 3.1 SDK → Bridge: UDP（デフォルトポート 7700）

SDK からのリアルタイムコマンド（再生・停止・ping）を受け付けるメインチャネル。低遅延を優先するため UDP を使用する。

### 3.2 Bridge Management API: HTTP REST（デフォルトポート 7701）

デバイス管理・状態照会などの非リアルタイム操作を提供する REST API。

### 3.3 Bridge → 送信機: USB シリアル or 内部通信

Bridge から送信機ファームウェアへの通信インタフェース。詳細は別仕様（送信機ファームウェア仕様）で定義する。

---

## 4. UDP Control Plane（ポート 7700）

SDK から Bridge へのメインプロトコル。すべてのパケットはリトルエンディアンで格納する。

### 4.1 コマンドタイプ一覧

| コマンドタイプ | 値 | 方向 | 説明 |
|----------------|------|------|------|
| play | `0x01` | SDK → Bridge | 再生コマンド |
| stop | `0x02` | SDK → Bridge | 停止コマンド |
| ping | `0x10` | SDK → Bridge | 疎通確認 |
| pong | `0x11` | Bridge → SDK | ping 応答 |
| error | `0xFF` | Bridge → SDK | エラー応答 |

### 4.2 再生コマンド（play: 0x01）

Event ID を指定してデバイスに再生を指示する。

**パケットフォーマット:**

| フィールド | 型 | サイズ | 説明 |
|------------|------|--------|------|
| command_type | uint8 | 1 バイト | `0x01` 固定 |
| seq | uint16 | 2 バイト | シーケンス番号 |
| event_id | string (null-terminated) | 可変 | 再生する Event ID |
| target_time | int64 | 8 バイト | 再生目標時刻（マイクロ秒、Bridge 基準）。`0` は即時再生を意味する |
| target_group | uint8 | 1 バイト | 対象グループ。`0` はブロードキャスト（全デバイス） |
| gain | float32 | 4 バイト | 再生ゲイン。範囲: `0.0` - `1.0`、デフォルト: `1.0` |

### 4.3 停止コマンド（stop: 0x02）

再生中のイベントを停止する。

**パケットフォーマット:**

| フィールド | 型 | サイズ | 説明 |
|------------|------|--------|------|
| command_type | uint8 | 1 バイト | `0x02` 固定 |
| seq | uint16 | 2 バイト | シーケンス番号 |
| event_id | string (null-terminated) | 可変 | 停止する Event ID |
| target_group | uint8 | 1 バイト | 対象グループ。`0` は全グループ |

### 4.4 ping（0x10）

Bridge への疎通確認。

**パケットフォーマット:**

| フィールド | 型 | サイズ | 説明 |
|------------|------|--------|------|
| command_type | uint8 | 1 バイト | `0x10` 固定 |
| seq | uint16 | 2 バイト | シーケンス番号 |
| timestamp | int64 | 8 バイト | 送信時のタイムスタンプ（マイクロ秒） |

### 4.5 pong（0x11）

Bridge からの ping 応答。

**パケットフォーマット:**

| フィールド | 型 | サイズ | 説明 |
|------------|------|--------|------|
| command_type | uint8 | 1 バイト | `0x11` 固定 |
| seq | uint16 | 2 バイト | 対応する ping のシーケンス番号 |
| timestamp | int64 | 8 バイト | 元の ping のタイムスタンプ（エコーバック） |
| bridge_time | int64 | 8 バイト | Bridge が応答した時点の時刻（マイクロ秒） |

---

## 5. Management API（ポート 7701）

HTTP REST API によるデバイス管理・状態照会インタフェース。すべてのレスポンスは `application/json` で返却する。

### 5.1 `GET /api/v1/status`

Bridge のステータスを取得する。

**レスポンス例:**

```json
{
  "version": "1.0.0",
  "uptime_seconds": 3600,
  "connected_devices": 4,
  "connected_transmitters": 1
}
```

### 5.2 `GET /api/v1/devices`

接続中のデバイス一覧を取得する。

**レスポンス例:**

```json
{
  "devices": [
    {
      "device_id": "hapbeat-A1B2C3",
      "name": "Hapbeat Neck 1",
      "group": 1,
      "firmware_version": "2.1.0",
      "battery_level": 0.85,
      "last_seen": "2026-03-22T10:30:00Z",
      "installed_kits": ["com.example.game.explosion", "com.example.game.footstep"]
    }
  ]
}
```

### 5.3 `PUT /api/v1/devices/{id}/group`

デバイスのグループを設定する。

**リクエストボディ:**

```json
{
  "group": 2
}
```

**レスポンス例:**

```json
{
  "device_id": "hapbeat-A1B2C3",
  "group": 2
}
```

### 5.4 `GET /api/v1/devices/{id}/kits`

デバイスにインストール済みの Kit 一覧を取得する。

**レスポンス例:**

```json
{
  "device_id": "hapbeat-A1B2C3",
  "kits": [
    {
      "kit_id": "com.example.game.explosion",
      "version": "1.0.0"
    },
    {
      "kit_id": "com.example.game.footstep",
      "version": "1.2.0"
    }
  ]
}
```

### 5.5 `POST /api/v1/devices/{id}/kits/install`

デバイスに Kit のインストールを指示する。

**リクエストボディ:**

```json
{
  "kit_id": "com.example.game.explosion",
  "version": "1.0.0"
}
```

**レスポンス例:**

```json
{
  "device_id": "hapbeat-A1B2C3",
  "kit_id": "com.example.game.explosion",
  "status": "installing"
}
```

### 5.6 `GET /api/v1/time`

Bridge の現在時刻を取得する。時刻同期の基準として使用する。

**レスポンス例:**

```json
{
  "bridge_time_us": 1711100000000000,
  "iso8601": "2026-03-22T10:30:00.000000Z"
}
```

### 5.7 `GET /api/v1/transmitters`

接続中の送信機一覧を取得する。

**レスポンス例:**

```json
{
  "transmitters": [
    {
      "transmitter_id": "tx-001",
      "port": "COM3",
      "firmware_version": "1.5.0",
      "status": "connected"
    }
  ]
}
```

---

## 6. Device Registry

### 6.1 デバイス検出

デバイスの検出は送信機ファームウェア経由で行われる。送信機が ESP-NOW で周辺のデバイスを探索し、応答から Device Registry を構築する。Bridge はこのレジストリを管理・公開する。

### 6.2 デバイス属性

各デバイスは以下の属性を保持する。

| 属性 | 型 | 説明 |
|------|------|------|
| device_id | string | デバイスの一意識別子（例: `"hapbeat-A1B2C3"`） |
| name | string | デバイスの表示名（例: `"Hapbeat Neck 1"`） |
| group | uint8 | 所属グループ ID |
| firmware_version | string | デバイスファームウェアのバージョン |
| battery_level | float | バッテリー残量（`0.0` - `1.0`） |
| last_seen | string (ISO 8601) | 最終通信時刻 |
| installed_kits | string[] | インストール済み Kit ID の一覧 |

### 6.3 グループ管理

グループ ID はデバイスの論理的なグルーピングに使用する。

| グループ ID | 意味 |
|-------------|------|
| `0` | ブロードキャスト（全デバイス対象） |
| `1` - `254` | ユーザー定義グループ |
| `255` | 予約済み（将来の拡張用） |

再生コマンド・停止コマンドの `target_group` に指定することで、特定グループのデバイスのみを対象にできる。

---

## 7. Time Sync

### 7.1 基本方針

Bridge がシステム全体の基準時刻を提供する。すべてのタイムスタンプは Bridge 基準のマイクロ秒単位で表現する。

### 7.2 target_time の仕様

- `target_time` は Bridge 基準のマイクロ秒単位の絶対時刻である
- `target_time = 0` は「即時再生」を意味する特別な値である
- 将来の時刻を指定することで、複数デバイスの同期再生を実現できる

### 7.3 デバイスの時刻補正

デバイスは Bridge から定期的に送信される時刻同期情報を元に、ローカルクロックを補正する。これにより、target_time で指定された絶対時刻を各デバイスが正確に解釈できる。

### 7.4 同期精度目標

デバイス間の時刻同期精度は **1ms 以内** を目標とする。

---

## 8. OSC アダプタ

### 8.1 概要

Bridge は OSC（Open Sound Control）メッセージも受け付ける。これは TouchDesigner や Max などの音響・映像ツールからの利用を想定したインタフェースである。

### 8.2 OSC ポート

デフォルトポート: **7702**

### 8.3 OSC アドレス体系

#### `/hapbeat/play`

再生コマンドを送信する。

```
/hapbeat/play <event_id:string> [target_time:int] [group:int] [gain:float]
```

| 引数 | 型 | 必須 | デフォルト | 説明 |
|------|------|------|------------|------|
| event_id | string | 必須 | - | 再生する Event ID |
| target_time | int | 任意 | `0`（即時再生） | 再生目標時刻（マイクロ秒、Bridge 基準） |
| group | int | 任意 | `0`（ブロードキャスト） | 対象グループ ID |
| gain | float | 任意 | `1.0` | 再生ゲイン（`0.0` - `1.0`） |

#### `/hapbeat/stop`

停止コマンドを送信する。

```
/hapbeat/stop <event_id:string> [group:int]
```

| 引数 | 型 | 必須 | デフォルト | 説明 |
|------|------|------|------------|------|
| event_id | string | 必須 | - | 停止する Event ID |
| group | int | 任意 | `0`（全グループ） | 対象グループ ID |

#### `/hapbeat/ping`

疎通確認を送信する。引数なし。

```
/hapbeat/ping
```

### 8.4 内部変換

受信した OSC メッセージは Bridge 内部で対応する UDP コマンド（セクション 4 のフォーマット）に変換されて処理される。OSC 固有の追加処理は行わない。

---

## 9. エラー応答

### 9.1 UDP エラーパケット

UDP 通信でエラーが発生した場合、以下のフォーマットでエラーパケットを返却する。

**パケットフォーマット:**

| フィールド | 型 | サイズ | 説明 |
|------------|------|--------|------|
| command_type | uint8 | 1 バイト | `0xFF` 固定 |
| seq | uint16 | 2 バイト | 対応するコマンドのシーケンス番号 |
| error_code | uint16 | 2 バイト | エラーコード |
| message | string (null-terminated) | 可変 | エラーメッセージ |

**主なエラーコード:**

| エラーコード | 説明 |
|-------------|------|
| `0x0001` | 不明なコマンドタイプ |
| `0x0002` | 不正なパケットフォーマット |
| `0x0003` | 指定された Event ID が見つからない |
| `0x0004` | 指定されたグループにデバイスが存在しない |
| `0x0005` | 送信機が接続されていない |
| `0x0006` | 内部エラー |

### 9.2 HTTP エラーレスポンス

HTTP API でエラーが発生した場合、標準の HTTP ステータスコードと JSON ボディで応答する。

**レスポンスフォーマット:**

```json
{
  "error": "エラーメッセージ",
  "code": 1001
}
```

**主な HTTP ステータスコードとエラーコードの対応:**

| HTTP ステータス | エラーコード | 説明 |
|----------------|-------------|------|
| 400 Bad Request | `1001` | リクエストパラメータが不正 |
| 404 Not Found | `1002` | 指定されたリソースが見つからない |
| 409 Conflict | `1003` | 操作が競合している（例: Kit インストール中） |
| 500 Internal Server Error | `1004` | 内部エラー |
| 503 Service Unavailable | `1005` | 送信機が接続されていない |

---

## デバイス検出（自動検出）

### mDNS サービス公開

Hapbeat デバイスは Wi-Fi STA モード接続後、mDNS でサービスを公開する。

| 項目 | 値 |
|------|-----|
| サービスタイプ | `_hapbeat._udp` |
| ポート | 7700 |
| ホスト名 | デバイス名（NVS の dev_name、デフォルト: `hapbeat-XXXX`、XXXX は MAC 末尾4桁） |

TXT レコード:

| キー | 値 | 例 |
|------|-----|-----|
| `name` | デバイス名 | `Hapbeat-LeftArm` |
| `group` | グループ ID | `1` |
| `fw` | ファームウェアバージョン | `2.0.0` |
| `mac` | MAC アドレス | `AA:BB:CC:DD:EE:FF` |
| `role` | ノード役割 (specs/node-roles.md, DEC-034) | `receiver` / `sensor` / `broker` / `transmitter` |
| `transport` | 通信モード (specs/node-roles.md) | `udp` / `mqtt` / `espnow_stream` |

`role` / `transport` は省略可（旧ファームウェアは送らない）。受信側は欠落時に
`receiver` / `udp` として扱う。これによりツール (Helper / Studio) は get_info の
TCP 往復を待たずに discovery 時点でノード役割に応じた UI を出せる。

### UDP ブロードキャスト PING による検出

mDNS が使用できない環境（Unity の制約等）向けの補助検出手段。

1. SDK/アプリからブロードキャストアドレス（255.255.255.255:7700）に PING パケットを送信
2. LAN 上の Hapbeat デバイスが PONG で応答

PONG 応答の拡張フィールド（標準の timestamp, server_time に加えて）:

| フィールド | 型 | 説明 |
|-----------|-----|------|
| device_name | null-terminated string | デバイス名 |
| group | uint8 | グループ ID |
| firmware_version | null-terminated string | ファームウェアバージョン |

Note: デバイスからの PONG 応答は Bridge からの PONG 応答とは payload が異なる。受信側は payload_length で区別できる（デバイス PONG は拡張フィールド分だけ長い）。

---

## 10. ポート一覧まとめ

| ポート | プロトコル | 用途 | 方向 |
|--------|-----------|------|------|
| **7700** | UDP | Control Plane（再生・停止・ping） | SDK → Bridge |
| **7701** | HTTP | Management API（デバイス管理・状態照会） | クライアント ↔ Bridge |
| **7702** | OSC (UDP) | OSC アダプタ（TouchDesigner / Max 向け） | ツール → Bridge |
