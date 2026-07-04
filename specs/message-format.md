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

UDP オーディオストリーミングの開始を通知する。**ADPCM デコーダー状態は必ずリセットする**。リングバッファの扱いは残差量で分岐する（実装: `audio_stream.cpp` `audioStreamBegin`、しきい値 `BEGIN_FLUSH_THRESHOLD` = 512 frames ≈ 32 ms）:

- **残差 ≤ 32 ms（短い末尾）**: クリアせず**自然ドレイン**。直前の one-shot を最後まで鳴らし、rapid STREAM_END→STREAM_BEGIN による切り詰めを防ぐ。
- **残差 > 32 ms（前ストリームがまだ再生中＝Live Audio のソース切替等）**: リングバッファを**フラッシュ**して再開し、古いコンテンツの長い尾を断つ。

したがって**連続変調**を続ける場合は、STREAM_END を挟まず STREAM_DATA を流し続ければ STREAM_BEGIN は最初の 1 回のみとなり、リングが枯渇しない限り 1 本のストリームとして途切れず再生される。ストリーミングは voice ミキサーと並行して動作し、ローカルクリップの再生を停止しない。

STREAM_BEGIN/DATA/END には **event_id フィールドを含まない**。stream イベントは session レベル（送信元 SDK が 1 session = 1 stream を管理）で識別され、device は eventId を認識しない。Kit manifest の `stream_events` のキーは SDK 内部で AudioClip / binding を紐付けるラベルとしてのみ使用される。

| フィールド | 型 | 説明 |
|---|---|---|
| sample_rate | uint16 | サンプルレート（Hz、例: 16000 / 48000） |
| channels | uint8 | チャンネル数（1=mono, 2=stereo） |
| format | uint8 | オーディオフォーマット（0=PCM16, 1=IMA_ADPCM, **2=OPUS**） |
| total_samples | uint32 | 総サンプル数（0=不明。情報用、省略可） |
| gain | float32 | 再生ゲイン（0.0 〜 1.0）。intensity × SDK_gain × binding を SDK 側で計算した値 |
| target | null-terminated string | optional。ターゲットアドレス（省略時は全台）。詳細は `device-addressing.md` 参照 |

固定部分のサイズは 12 bytes (既存 8 + gain 4)。`target` は可変長（省略時は 0 bytes、存在する場合は null 終端文字列）。

#### format=2 (OPUS) の注記（DEC-042）

**固定部分の追加フィールドは無い** — format=2 も PCM16/ADPCM と同じ **12 bytes 固定 + optional target** で、フレーム長・モード等の Opus パラメータは wire に載せない。理由:

- **frame duration / mode は wire 不要**: 各 Opus フレームはパケット単位で自己完結し、`opus_decode` はフレームから長さ・チャンネル・モードを自己判定する。受信側は decode の戻り値（サンプル数）から 1 フレーム長を知れるため、`frame_duration_ms` を事前に持つ必要がない（← 追加フィールドを固定部に挟むと既存の `target` 解析位置がずれるため、載せない設計を優先）。
- **pre-skip も wire で扱わない**: 生ライブストリーム（Ogg コンテナなし）であり、エンコーダ立ち上がりのプライミングは**送信側で吸収**する（受信側は先頭フレームからそのまま再生）。
- `sample_rate`/`channels`: **送信側は 48000 / 2 固定を推奨**。receiver が別レートでデコードする場合（duo_v3 が 48kHz ストリームを 16kHz で直接デコード）は receiver 実装事項で、wire 値は変えない。Opus は mono/stereo をフレーム内で自己記述するため、receiver は `channels`（=2）でデコーダを生成すればよい。
- 残差フラッシュ閾値（`BEGIN_FLUSH_THRESHOLD` ≈ 32ms）は**デコード後 PCM 領域**の値で format に依らず共通。
- profile（P-audio-LD 5ms / P-audio-Q 10–20ms）の差は「送信側のフレーム長・ビットレート・エンコーダ設定」だけで、**UDP wire format は同一**（`docs/instructions-opus-streaming-plan-202607040323.md` §2）。

### 0x31 STREAM_DATA

オーディオデータチャンク。リングバッファに書き込まれ、voice ミキサーのアキュムレータに加算される。

| フィールド | 型 | 説明 |
|---|---|---|
| offset | uint32 | バイトオフセット（順序確認用、デバイス側では未使用） |
| data | variable | オーディオデータ（PCM16 raw bytes、ADPCM encoded bytes、または Opus フレーム列） |

- PCM16: raw interleaved 16-bit LE samples
- ADPCM mono: 2 samples per byte (low nibble first)
- ADPCM stereo: 1 frame per byte (L=low nibble, R=high nibble)
- **Opus (format=2)**: `data` は **1 個以上の Opus フレームの連結**。UDP は MTU 制約が緩い（本文書 §10 のパケット上限 1500 bytes）ため、1 STREAM_DATA パケットに複数フレームをまとめてよい（ESP-NOW 経路の 250B 制約下での 1 パケット=1 フレーム運用とは独立、`espnow-stream.md` §3.3 参照）。各フレームには以下の **2 byte length-prefix（uint16 LE）** を前置する:

  | フィールド | 型 | 説明 |
  |---|---|---|
  | frame_length | uint16 | 直後に続く Opus フレームのバイト長（**1 以上。0 は不正**） |
  | frame_data | uint8[frame_length] | 1 Opus フレーム（libopus の `opus_encode` 出力そのまま） |

  `data` の末尾まで `frame_length + frame_data` の組を繰り返す。offset は依然としてバイトオフセット（先頭からの累積、length-prefix を含む）を示し、順序確認用に使える。
  **DTX は使用しない**（送信側はエンコーダの DTX を無効化する。CBR 運用のため無音でも通常フレームを送る — 受信側の framing / アンダーラン判定を単純に保つ）。

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

## 11. ストリーミングプロファイルの対応広告（get_info）

複数のストリーミングプロファイル（`P-haptic` / `P-audio-LD` / `P-audio-Q`、定義は `docs/instructions-opus-streaming-plan-202607040323.md` §2）が併存するため、送信側（SDK/Studio/Helper）は receiver がどの `format` をデコード可能かを事前に知る必要がある。

- receiver は `get_info`（serial + TCP）で **`stream_formats`（string 配列）** を広告する:
  ```json
  "stream_formats": ["pcm16", "adpcm", "opus"]
  ```
- 値は format 単位（`"pcm16"` / `"adpcm"` / `"opus"`）。profile（LD/Q）の区別は wire format が同一（format=2）のため広告しない — フレーム長/ビットレートは STREAM_BEGIN が自己記述する。
- Opus 未対応の firmware（旧 build）は `stream_formats` を返さない。送信側は**フィールド不在 = pcm16/adpcm のみ対応**とみなす。
- Helper は本フィールドを get_info passthrough で Studio/SDK に透過する。

## 12. 関連文書

- `espnow-stream.md` — ESP-NOW transport 上の Opus profile（`P-audio-LD` 相当）のパケット形式
- `../docs/decision-log.md` DEC-042 — Opus 採用確定の判断
- `../docs/instructions-opus-streaming-plan-202607040323.md` — プロファイル設計・遅延バジェット・実装フェーズの計画書（本文書の §0x30/§0x31 拡張の元仕様）

> ドラフト時の open issues は 2026-07-04 レビューで裁定済み: get_info 広告=`stream_formats` 配列（§11）/ DTX=禁止（§0x31）/ pre_skip=wire から削除・送信側吸収（§0x30）/ フラッシュ閾値=デコード後 PCM 領域で共通（§0x30）/ channels=48000/2 固定推奨 + libopus 自己記述に委譲（§0x30）。
