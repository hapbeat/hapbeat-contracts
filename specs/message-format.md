# UDP/OSC メッセージフォーマット仕様書

## 1. 概要

本文書は、Hapbeat エコシステムで使用される全メッセージフォーマットを定義する。SDK から Bridge への通信（Layer 1）を公開仕様として詳細に規定し、内部層については概要のみ記載する。

## 2. メッセージ層の整理

Hapbeat システムの通信は以下の 3 層で構成される。

| 層 | 区間 | プロトコル | 公開範囲 |
|---|---|---|---|
| Layer 1 | SDK → Bridge | UDP / OSC（ポート 7700 / 7702） | 公開仕様（本文書） |
| Layer 2 | Bridge → Transmitter | USB シリアル（内部） | 内部仕様（`internal-bridge-transmitter.md` で定義） |
| Layer 3 | Transmitter → Device | ESP-NOW | 内部仕様（device-firmware 側で定義） |

SDK 開発者は Layer 1 のみを意識すればよい。Layer 2・Layer 3 は Bridge および Firmware が内部的に処理する。

## 3. 共通ヘッダ構造（Layer 1 UDP パケット）

すべての UDP パケットは以下の共通ヘッダで始まる。

| オフセット | フィールド | 型 | サイズ | 説明 |
|---|---|---|---|---|
| 0 | magic | uint16 | 2 bytes | 固定値 `0x4842`（ASCII "HB"） |
| 2 | protocol_version | uint8 | 1 byte | プロトコルバージョン。現行は `0x01` |
| 3 | command_type | uint8 | 1 byte | コマンド種別（後述） |
| 4 | seq | uint16 | 2 bytes | シーケンス番号（重複検出用） |
| 6 | payload_length | uint16 | 2 bytes | payload のバイト長 |
| 8 | payload | variable | payload_length bytes | コマンド固有のデータ |

ヘッダサイズは固定 8 bytes である。

## 4. コマンド定義（Layer 1）

### 0x01 PLAY

触覚イベントの再生を指示する。

| フィールド | 型 | 説明 |
|---|---|---|
| event_id | null-terminated string | 再生するイベントの識別子 |
| target | null-terminated string | ターゲットアドレス（空文字 = 全台）。詳細は `device-addressing.md` 参照 |
| target_time | int64 | 再生開始時刻（マイクロ秒、Bridge 基準時刻） |
| gain | float32 | 再生ゲイン（0.0 〜 1.0） |

### 0x02 STOP

指定イベントの再生を停止する。

| フィールド | 型 | 説明 |
|---|---|---|
| event_id | null-terminated string | 停止するイベントの識別子 |
| target | null-terminated string | ターゲットアドレス（空文字 = 全台） |

### 0x03 STOP_ALL

ターゲットに一致する全デバイスの全イベントを停止する。

| フィールド | 型 | 説明 |
|---|---|---|
| target | null-terminated string | ターゲットアドレス（空文字 = 全台） |

### 0x10 PING

Bridge との接続確認および時刻同期に使用する。

| フィールド | 型 | 説明 |
|---|---|---|
| timestamp | int64 | 送信時のタイムスタンプ（マイクロ秒） |

### 0x11 PONG

PING に対する応答。Bridge から SDK に返送される。

| フィールド | 型 | 説明 |
|---|---|---|
| timestamp | int64 | 元の PING のタイムスタンプ（マイクロ秒） |
| server_time | int64 | Bridge が PONG を送信した時刻（マイクロ秒） |

### 0x11 PONG（デバイス応答時の拡張）

デバイスが直接 PONG を返す場合（Wi-Fi UDP 直接通信時）、標準フィールドに加えて以下の拡張フィールドを含む。

| フィールド | 型 | 説明 |
|-----------|-----|------|
| timestamp | int64 | 元の PING のタイムスタンプ（マイクロ秒） |
| server_time | int64 | デバイスが PONG を送信した時刻（マイクロ秒） |
| device_name | null-terminated string | デバイス名 |
| address | null-terminated string | デバイスアドレス（例: `player_1/chest`）。詳細は `device-addressing.md` 参照 |
| firmware_version | null-terminated string | ファームウェアバージョン |

受信側は `payload_length` を確認することで、Bridge 標準 PONG（16 bytes）とデバイス拡張 PONG（16 bytes + 可変長）を区別できる。

### 0xFF ERROR

エラー通知。Bridge から SDK に送信される。

| フィールド | 型 | 説明 |
|---|---|---|
| error_code | uint16 | エラーコード |
| message | null-terminated string | 人間が読めるエラーメッセージ |

## 5. エンディアン

すべての多バイトフィールドは **リトルエンディアン** で格納する。

## 6. OSC マッピング

OSC プロトコル経由でアクセスする場合、以下のアドレスと UDP コマンドが対応する。

| OSC アドレス | UDP コマンド | command_type |
|---|---|---|
| `/hapbeat/play` | PLAY | 0x01 |
| `/hapbeat/stop` | STOP | 0x02 |
| `/hapbeat/stop-all` | STOP_ALL | 0x03 |
| `/hapbeat/ping` | PING | 0x10 |

OSC メッセージの引数は、対応する UDP コマンドの payload フィールドと同じ順序で指定する。

## 7. シーケンス番号

- 型: uint16（0 〜 65535）
- 65535 の次は 0 にラップアラウンドする
- Bridge は直近に受信した seq を追跡し、同一の seq を持つパケットを重複として無視する
- SDK はパケット送信ごとに seq をインクリメントする

## 8. targetTime の扱い

- 単位: マイクロ秒
- 基準: Bridge のローカル時刻
- `0` を指定した場合: 即時再生
- 過去の時刻を指定した場合: 即時再生にフォールバック
- SDK は PING/PONG を用いて Bridge との時刻差を推定し、targetTime を補正することが推奨される

## 9. デバイスアドレッシング

パケット内の `target` フィールドでデバイスのフィルタリングを行う。

| target 値 | 意味 |
|---|---|
| `""` (空文字) | 全デバイスに送信 |
| `"player_1"` | `player_1` で始まるアドレスのデバイス（前方一致） |
| `"player_1/chest"` | 完全一致 |
| `"*/chest"` | 全 player の chest（ワイルドカード） |

詳細は `device-addressing.md` を参照。

## 10. パケットサイズ制限

- 最大パケットサイズ: **512 bytes**（ヘッダ + payload の合計）
- UDP MTU を考慮した制限値であり、フラグメンテーションを防止する
- 512 bytes を超えるパケットを Bridge が受信した場合、そのパケットは破棄される
