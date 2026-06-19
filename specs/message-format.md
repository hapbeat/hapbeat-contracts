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

> エコシステム全体のポート一覧とホスト側 bind 方針は `ports.md`（ポート台帳）を正とする。

本文書は **`udp` transport** の wire format を定義する。他の transport は別文書で定義する（`node-roles.md` の taxonomy 参照）:

- **`mqtt` transport**（センサ起点の遠隔通知）→ `mqtt-transport.md`
- **`espnow_stream` transport**（会場同報のライブ音声）→ `espnow-stream.md`

触覚資産（Kit / event_id）と再生意味論は transport 非依存で共通。各 transport はその搬送方法だけが異なる。

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
| event_id | null-terminated string | 再生するイベントの識別子。Kit manifest の `events` (command-mode) のキーと一致する必要がある。`stream_events` のキーは SDK 内部ラベルでありここには乗らない |
| target | null-terminated string | ターゲットアドレス（空文字 = 全台）。詳細は `device-addressing.md` 参照 |
| target_time | int64 | 再生開始時刻（マイクロ秒、Bridge 基準時刻） |
| gain | float32 | 再生ゲイン（0.0 〜 1.0） |

### 0x02 STOP

指定イベントの再生を停止する。

| フィールド | 型 | 説明 |
|---|---|---|
| event_id | null-terminated string | 停止するイベントの識別子。PLAY と同じく `events` (command-mode) のキー（device 側 event table 参照用） |
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

### 0x20 CONNECT_STATUS

SDK/アプリからデバイスへの接続状態通知。定期的に送信し、デバイスが接続中であることを示す。

| フィールド | 型 | 説明 |
|---|---|---|
| connected | uint8 | 1=接続中 / 0=切断（アプリ終了時など） |
| group | uint8 | グループ ID（表示用。ルーティングには使わない） |
| app_name | null-terminated string | 接続元アプリ名 |
| device_name | null-terminated string | 対象デバイス名 |

> 実装上の wire format はこの順序（`connected, group, app_name, device_name`）が
> source of truth。Unity `HapbeatProtocol.cs` / web-sdk `protocol.ts` / python-sdk と
> firmware `connect_status.cpp` がこれで一致している（DEC-032, 2026-06-13 監査で確認）。
> `group` はレガシーで現在ルーティングには未使用（device-addressing.md のアドレス文字列が正）。

### 0x30 STREAM_BEGIN

UDP オーディオストリーミングの開始を通知する。ADPCM デコーダー状態のリセットとリングバッファのクリアを行う。ストリーミングは voice ミキサーと並行して動作し、ローカルクリップの再生を停止しない。

STREAM_BEGIN/DATA/END には **event_id フィールドを含まない**。stream イベントは session レベル（送信元 SDK が 1 session = 1 stream を管理）で識別され、device は eventId を認識しない。Kit manifest の `stream_events` のキーは SDK 内部で AudioClip / binding を紐付けるラベルとしてのみ使用される。

| フィールド | 型 | 説明 |
|---|---|---|
| sample_rate | uint16 | サンプルレート（Hz、例: 16000） |
| channels | uint8 | チャンネル数（1=mono, 2=stereo） |
| format | uint8 | オーディオフォーマット（0=PCM16, 1=IMA_ADPCM） |
| total_samples | uint32 | 総サンプル数（0=不明。情報用、省略可） |
| gain | float32 | 再生ゲイン（0.0 〜 1.0）。intensity × SDK_gain × binding を SDK 側で計算した値 |
| target | null-terminated string | optional。ターゲットアドレス（省略時は全台）。詳細は `device-addressing.md` 参照 |

固定部分のサイズは 12 bytes (既存 8 + gain 4)。`target` は可変長（省略時は 0 bytes、存在する場合は null 終端文字列）。

### 0x31 STREAM_DATA

オーディオデータチャンク。リングバッファに書き込まれ、voice ミキサーのアキュムレータに加算される。

| フィールド | 型 | 説明 |
|---|---|---|
| offset | uint32 | バイトオフセット（順序確認用、デバイス側では未使用） |
| data | variable | オーディオデータ（PCM16 raw bytes または ADPCM encoded bytes） |

- PCM16: raw interleaved 16-bit LE samples
- ADPCM mono: 2 samples per byte (low nibble first)
- ADPCM stereo: 1 frame per byte (L=low nibble, R=high nibble)

### 0x32 STREAM_END

ストリーミング終了のヒント。ペイロードなし。リングバッファは自然にドレインされる。ACK は返さない。

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

- コマンドパケット（PLAY, STOP, PING 等）: 最大 **512 bytes**（ヘッダ + payload の合計）
- ストリーミングパケット（STREAM_DATA）: 最大 **1500 bytes**（Ethernet MTU）
- UDP MTU を考慮した制限値であり、IP フラグメンテーションを防止する
