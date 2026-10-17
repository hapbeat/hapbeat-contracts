# WifiUdp/OSC メッセージフォーマット仕様書

## 1. 概要

本文書は、`NodeTransport.WifiUdp`（wire/config 値 `wifi_udp`）の SDK → デバイス UDP 通信と OSC 変換を定義する。Stream Gen 2（セッション方式）の識別・順序規則は [stream-session.md](stream-session.md) を正とする。版の付け方・拡張と互換の規則は [versioning.md](versioning.md) を正とする。

## 2. メッセージ層の整理

| 区間 | プロトコル | 公開範囲 |
|---|---|---|
| SDK → デバイス | Wi-Fi UDP 7700 | 公開仕様（本文書） |
| OSC ツール → デバイス | OSC UDP 7702 → Wi-Fi UDP 7700 | ツールの変換経路 |

SDK は既知デバイスへ unicast し、既知デバイスが 0 台のときだけ broadcast する。legacy `hapbeat-bridge` は現行非対応で再利用しない。

> エコシステム全体のポート一覧とホスト側 bind 方針は `ports.md`（ポート台帳）を正とする。

本文書は **`wifi_udp` transport** の wire format を定義する。他の transport は別文書で定義する（`node-roles.md` の taxonomy 参照）:

- **`mqtt` transport**（センサ起点の遠隔通知）→ `mqtt-transport.md`
- **`espnow_stream` transport**（会場同報のライブ音声）→ `espnow-stream.md`

触覚資産（Kit / event_id）と再生意味論は transport 非依存で共通。各 transport はその搬送方法だけが異なる。

## 3. 共通ヘッダ構造（WifiUdp パケット）

すべての UDP パケットは以下の共通ヘッダで始まる。

| オフセット | フィールド | 型 | サイズ | 説明 |
|---|---|---|---|---|
| 0 | magic | uint16 | 2 bytes | 固定値 `0x4842`（ASCII "HB"） |
| 2 | protocol_version | uint8 | 1 byte | コマンドの形式の版。非 stream は `0x01`、STREAM_BEGIN/DATA/END は `0x02`（Stream Gen 2）。下記参照 |
| 3 | command_type | uint8 | 1 byte | コマンド種別（後述） |
| 4 | seq | uint16 | 2 bytes | シーケンス番号（§7） |
| 6 | payload_length | uint16 | 2 bytes | payload のバイト長 |
| 8 | payload | variable | payload_length bytes | コマンド固有のデータ |

ヘッダサイズは固定 8 bytes である。

- **`protocol_version` はコマンドごとの形式の版であり、製品の版ではない。** 1.x の間、値は上表のまま変えない（`versioning.md` §7.4）。既存コマンドの拡張は §4.0 の規則で行い、版は上げない。STREAM_BEGIN/DATA/END の値 `0x02` は Stream Gen 2 を表し、`0x01` は Stream Gen 1（0.4.x 以前のファーム、本書「Stream Gen 1」節）を表す。
- 受信側は、知っている command_type で知らない `protocol_version` のパケットを、状態を変えずに捨て、送信元へ ERROR `UNSUPPORTED_VERSION` を返す（Stream Gen 2 専用の受信機が Stream Gen 1 を受けた場合は `STREAM_GEN_UNSUPPORTED`。§0xFF）。
- 受信側は `payload_length` で payload の範囲を決める。datagram のそれより後ろの byte は無視する。ただし Stream Gen 2 のパケットは、datagram の長さが `8 + payload_length` と一致しなければならない（一致しなければ MALFORMED。`stream-session.md`）。

## 4. コマンド定義（WifiUdp）

### 4.0 拡張の規則と command_type の割当

既存コマンドを拡張するときは、`protocol_version` を上げずに次のいずれかで行う（`versioning.md` §6・§7）。

1. **末尾への省略可能な項目の追加**（前例: PLAY の `pan`、DEC-055）。
   - 受信側は、定義より後ろの余りの byte を無視する。存在しない末尾の項目は、その項目の既定値として扱う。
   - 送信側は、自分が知っている項目をすべて付けて送る。
   - 末尾に追加できるのは非 stream のコマンドだけである。PING・PONG と Stream Gen 2 のパケットは凍結している（§0x10・§0x11、`stream-session.md`）。
   - PLAY・STOP・STOP_ALL に項目を足すときは、MQTT の対応する payload（`mqtt-transport.md`）にも同じ項目を同時に足す。
2. **新しいコマンドの追加**。末尾への追加で表せない変更（項目の意味の変更・途中への挿入・応答の追加）は、新しい command_type にする。旧受信機は未知のコマンドを無視する。
3. **能力に依存する機能**。送信側は、機体が能力申告（§0x13 CAPS）で申告した機能だけを使う。申告を持たない機体（0.x のファーム）は、追加機能を持たないものとして扱う。

command_type の割当:

| 範囲 | 用途 | 定義済み |
|---|---|---|
| 0x01–0x0F | 再生の制御 | 0x01 PLAY、0x02 STOP、0x03 STOP_ALL |
| 0x10–0x1F | 探索・能力 | 0x10 PING、0x11 PONG、0x12 CAPS_REQ、0x13 CAPS |
| 0x20–0x2F | 状態の通知 | 0x20 CONNECT_STATUS |
| 0x30–0x3F | stream | 0x30 STREAM_BEGIN、0x31 STREAM_DATA、0x32 STREAM_END |
| 0x40–0xEF | 予約（contracts で割り当てる） | |
| 0xF0–0xFE | 実験用（製品に載せない。受信側は未知のコマンドとして扱う） | |
| 0xFF | ERROR | 0xFF ERROR |

### 0x01 PLAY

触覚イベントの再生を指示する。

| フィールド | 型 | 説明 |
|---|---|---|
| event_id | null-terminated string | 再生するイベントの識別子。Kit manifest の `events` (command-mode) のキーと一致する必要がある。`stream_events` のキーは SDK 内部ラベルでありここには乗らない |
| target | null-terminated string | ターゲットアドレス（空文字 = 全台）。詳細は `device-addressing.md` 参照 |
| target_time | int64 | 再生開始時刻（マイクロ秒）。`0` は即時再生 |
| gain | float32 | 再生ゲイン（0.0 〜 1.0） |
| pan | float32 | 左右バランス（-1.0 = 左のみ / 0.0 = 中央 / +1.0 = 右のみ）。**末尾の省略可能フィールド**: 受信側は存在しなければ 0.0（中央）として扱う。送信側は常に付与すること。適用則は下記 (DEC-055) |

#### PLAY の pan 適用則（DEC-055）

`pan` はデバイス側ミキサーで **voice 単位の L/R ゲイン**に展開する。法則は **linear balance**（中央 = 両チャンネルとも減衰なし）で、SDK 側が StreamClip のステレオ PCM に事前乗算する法則と同一である:

```
gain_l = gain × (pan <= 0 ? 1.0 : 1.0 - pan)
gain_r = gain × (pan >= 0 ? 1.0 : 1.0 + pan)
```

- 受信側は `pan` を `[-1.0, +1.0]` にクランプしてから適用する
- **mono クリップ**: 1 サンプルを L/R に複製したうえで上式を掛ける（mono 音源 + コマンドで左右差を付けるのが主用途）
- **stereo クリップ**: 既存の L/R にそれぞれ `gain_l` / `gain_r` を掛ける（バランス。真のパンニングではない）
- **出力が 1 系統の実装**（モーター 1 個、CAPS の `haptic_channels` = 1）は `pan` を無視し、中央（`gain` のみ）として再生する。回路の出力が stereo でもモーターが 1 個なら 1 系統として扱う
- equal-power を採らない理由: Hapbeat の左右アクチュエータは身体上で物理的に分離しており両耳加算のような合成は起きないため、equal-power の √½ 補正は中央定位のクリップを mono 相当より約 3 dB 弱めるだけで利点が無い（SDK の StreamClip と同じ判断）

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

STOP_ALL は stream を含む全ての再生を止める。target が一致した受信機は、Stream Gen 2 の Active な session を、送信元に関係なく END と同じ扱いで終える（`stream-session.md` の Receiver ordering）。その session の送信側には、以後の DATA に対して ERROR `STREAM_STOPPED` を返す（§0xFF）。

### 0x10 PING

デバイスの接続確認に使用する。

| フィールド | 型 | 説明 |
|---|---|---|
| timestamp | int64 | 送信時のタイムスタンプ（マイクロ秒） |

Stream Gen 2 に対応した SDK は、続けて非ゼロの `client_incarnation`（uint64）を付加し、
payload を 16 bytes にする（拡張 PING）。通常の 8 byte の PING は探索だけで、lease を発行しない。
詳細は [stream-session.md](stream-session.md)。

**PING の形式は凍結している**（`versioning.md` §7.4）。payload は 8 bytes（探索）か 16 bytes（lease の要求）だけとし、送信側は他の長さを送ってはならない。受信側は 16 bytes 以外の PING を探索だけの PING として扱う。能力の問い合わせは §0x12 CAPS_REQ で行う。

### 0x11 PONG

PING に対するデバイスの応答。

| フィールド | 型 | 説明 |
|---|---|---|
| timestamp | int64 | 元の PING のタイムスタンプ（マイクロ秒） |
| server_time | int64 | デバイスが PONG を送信した時刻（マイクロ秒） |

### 0x11 PONG 拡張

デバイスは標準フィールドに加えて以下の拡張フィールドを含む。

| フィールド | 型 | 説明 |
|-----------|-----|------|
| timestamp | int64 | 元の PING のタイムスタンプ（マイクロ秒） |
| server_time | int64 | デバイスが PONG を送信した時刻（マイクロ秒） |
| device_name | null-terminated string | デバイス名 |
| address | null-terminated string | デバイスの完全な正準 address（例: `player_1/pos_chest/group_1`）。詳細は `device-addressing.md` 参照 |
| firmware_version | null-terminated string | ファームウェアバージョン |
| volume_level | uint8 | 現在の音量レベル |
| volume_wiper | uint8 | 現在のwiper値 |

16 byte の PING への直接応答だけ、この直後に 32 byte の stream lease tail（印 `HBS2`）を付ける。
形式・照合条件・再起動時の扱いは [stream-session.md](stream-session.md) に従う。
unsolicited PONG は tail を持たず、確立済みの lease を消去しない。

受信側は `payload_length` を確認して、基本 PONG（16 bytes）と拡張 PONG（16 bytes + 可変長）を区別する。

**PONG の形式は凍結している**（`versioning.md` §7.4）。1.x のファームは、直接応答にも unsolicited PONG にも、上表と tail 以外の byte を付けてはならない。新しい情報は §0x13 CAPS で申告する。1.x の SDK の tail の読み方（将来の major で tail の後ろに byte が増えても読めること）は `stream-session.md` の Receiver classification に従う。

デバイスは `set_address`、address を変えるボタン操作、`set_name` など、PONG に含む識別情報の
変更を成功させた後、浅い main loop から unsolicited PONG を送る。SDK はこの PONG を endpoint
registry の更新として扱い、active source を新しい正準 address で直ちに再解決する。既存 PING
への PONG 応答と PLAY / STOP の target filter はこの通知で変わらない。

#### 識別情報更新時の PONG 配送

識別情報更新の unsolicited PONG は `seq=0`、`timestamp=0` とし、次の両方へ送る。

1. subnet broadcast の UDP 7700 — Manager / helper の常駐 listener 向け。
2. 有効な PING を直近 15 秒以内に送った各 sender の送信元 `(IPv4, UDP port)` への exact unicast —
   SDK の local port 0（ephemeral）socket 向け。

デバイスは sender table を最大 8 endpoint に制限し、同じ `(IPv4, UDP port)` の PING は既存 entry
を更新する。満杯時は最も古い live entry を置換し、TTL 超過 entry は送信せず再利用する。SDK は
PING を送った receive socket を維持して unicast PONG を受信し、periodic PING を待たず identity
update を反映する。broadcast 7700 を受信できない ephemeral port の SDK でも、この unicast が
endpoint 再解決を成立させる。

`timestamp=0` は PING への応答ではないことを示す sentinel である。SDK / Manager はこの PONG を
endpoint registry・liveness・表示用 identity の更新には使用するが、RTT（Round-Trip Time）や
device time offset の計算には使用してはならない。通常の PING 応答（元の PING timestamp が非 0）
だけが RTT / time-sync sample になる。

### 0x12 CAPS_REQ

SDK → デバイス。デバイスの能力申告を求める（`versioning.md` §5.2）。

| フィールド | 型 | 説明 |
|---|---|---|
| caps_version | uint8 | 要求側が読める CAPS の形式の版。現在 `1` |

- exact unicast で送る（broadcast で送らない。多数の機体が同時に応答するのを避けるため）。
- 送る時機: その endpoint の最初の照合済み PONG の後と、PONG の `firmware_version` または lease tail の `device_boot_id` が変わった後。
- 応答が無ければ 500 ms 間隔で計 3 回まで送る。3 回とも応答が無ければ、その機体を「能力申告なし」（0.x のファーム。`generation` 0、追加機能なし）として扱い、その boot の間は再要求しない。
- 0.x のファームは未知のコマンドとして無視する（応答しない）。

### 0x13 CAPS

デバイス → SDK。CAPS_REQ の送信元 (IPv4, UDP port) へ unicast で返す。header の `seq` は CAPS_REQ の `seq` をそのまま写す。

| オフセット | フィールド | 型 | 説明 |
|---|---|---|---|
| 0 | caps_version | uint8 | 形式の版。現在 `1`。要求の caps_version より大きい値は返さない |
| 1 | reserved | uint8 | `0` |
| 2 | entries | TLV の並び | payload の末尾まで |

各 entry は `type`（uint8）・`length`（uint8）・`value`（`length` bytes）の並びである。

- 読み手は未知の `type` を `length` で読み飛ばす。既知の `type` の `length` が定義より長ければ定義された先頭部分だけを読み、短ければその entry を無視する。同じ `type` が複数あれば、長さが足りている最初のものを使う。payload の末尾で途切れた entry は無視する。
- `type` の 0x01–0x7F は contracts が定義する。0x80–0xFF は実験用で、製品に載せない。
- payload は 504 bytes 以内とする（コマンドパケットの上限 512 bytes、§10）。

caps_version 1 の `type`:

| type | 名前 | 値 | 説明 |
|---|---|---|---|
| 0x01 | generation | uint8 | ファームの major（`versioning.md` §3.2）。1.x なら `1` |
| 0x02 | firmware_version | UTF-8（NUL なし、31 bytes 以内） | PONG の `firmware_version` と同じ値 |
| 0x03 | stream_gens | uint8 bitmap | 受け付ける Stream の世代。bit0 = Gen 1、bit1 = Gen 2。stream を受けないノード（broker・sensor）は `0` |
| 0x04 | stream_formats | uint8 bitmap | デコードできる形式。bit0 = PCM16、bit1 = IMA ADPCM、bit2 = Opus（STREAM_BEGIN の `format` の値 0 / 1 / 2 の順） |
| 0x05 | stream_limits | 4 bytes | `lease_ttl_s`（uint8）、`lease_slots`（uint8）、`inactivity_timeout_s`（uint8）、reserved（uint8 = 0）。値の意味は `stream-session.md` |
| 0x06 | haptic_channels | uint8 | 機体が駆動するモーター（触覚出力）の数。1 = モーター 1 個（mono。PLAY の pan を無視し、stereo の stream を (L+R)/2 で鳴らす）、2 = 左右（stereo）。ファームは board ごとのビルド設定として持つ（例: DuoWL v4 は 2、Band v2〜v4 は 1） |
| 0x07 | address_max_len | uint8 | 受け付ける address・target の最大 byte 数（NUL を除く） |
| 0x08 | features | uint32 bitmap | 追加機能。bit0 = `play_pan`（PLAY の `pan` を左右へ適用する）、bit1 = `error_reply`（§0xFF の ERROR を返す）。他の bit は予約（`0`） |

- 1.x のファームは 0x01–0x08 をすべて返す。ただし stream を受けないノードは 0x05 を省略する。
- `get_info` の `caps` object（`serial-config.md` §4.1）は、共通の項目を同じ値で JSON に持つ。`firmware_version` は UDP の CAPS だけにあり（get_info では top-level の `fw`）、`kit_schema`・`kit_clip_formats`・`ui_elements` は get_info だけにある（SDK は使わない）。
- SDK は、`generation` が自分の major より大きい機体を見つけたら、SDK の更新を促す警告を 1 回出す（`versioning.md` §3.3）。
- Stream の世代の判定には CAPS を使わない（`stream-session.md` の Receiver classification、`versioning.md` §5.3）。

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

この閾値（32 ms）は受信機の内部の値だが、SDK の差し替え（`sdk-multi-stream.md` §6.14）がこの挙動に依存するため契約として扱う。値を変えるときは先に contracts を変える。同じ tuple の BEGIN の再送（`stream-session.md`）はこの処理を行わない（冪等）。

したがって**連続変調**を続ける場合は、STREAM_END を挟まず STREAM_DATA を流し続ければ STREAM_BEGIN は最初の 1 回のみとなり、リングが枯渇しない限り 1 本のストリームとして途切れず再生される。ストリーミングは voice ミキサーと並行して動作し、ローカルクリップの再生を停止しない。

STREAM_BEGIN/DATA/END には **event_id フィールドを含まない**。device が管理するのは送信側の論理 source ではなく、device endpoint ごとの wire session である。複数 source の分離・mixing・endpoint への割当は SDK の責務とし、共通契約は `sdk-multi-stream.md` に定める。Kit manifest の `stream_events` のキーは SDK 内部で AudioClip / binding を紐付けるラベルとしてのみ使用される。

#### Stream Gen 2（セッション方式）の順序制約

- 全 stream は exact unicast。全 payload の先頭に 16 byte の `device_boot_id / lease_ticket / generation` envelope を付ける。
- 古い BEGIN / DATA / END はデバイスの世代判定で拒否する。END 後の固定 300 ms 待ちは無い。詳細と PING / PONG の lease 拡張は `stream-session.md`。
- 経路の変更だけなら、同じ device boot・lease であることを確認して session と cursor を維持してよい。デバイスの再起動・lease の更新では、新しい識別で BEGIN し直す。
- 以下の BEGIN / DATA の表は envelope の**後ろの body** を示す。BEGIN は envelope を含めて 28 bytes 以上（target を付けるとその分長い）。Stream Gen 2 の受信機は Stream Gen 1 を受理しない。
- SDK は Stream Gen 2 に対応しない（0.4.x 以前の）ファームの機器にだけ、下記「Stream Gen 1」で送る。判定は `stream-session.md` の Legacy receiver fallback。

#### Stream Gen 1（セッションなし方式、0.4.x 以前のファーム向け）

- header protocol_version=`0x01`。BEGIN / DATA の payload は下表の body そのもの（envelope なし）、END は payload なし。
- このファームは古い END を判別できない。STREAM_END と STREAM_BEGIN を broadcast / unicast または異なる宛先集合をまたいで連続送信しない（DTIM で遅延した broadcast の END が新しい session を止める）。
- 経路だけを変える場合、END / BEGIN の再送は不要。このファームは STREAM_DATA の送信元経路を session の識別に使わない。
- END の後に BEGIN が不可避な場合は、同じ経路・同じ宛先へ送り、300 ms 以上空ける（その機器だけに適用し、Stream Gen 2 の機器は待たない）。

| フィールド | 型 | 説明 |
|---|---|---|
| sample_rate | uint16 | サンプルレート（Hz、例: 16000 / 48000） |
| channels | uint8 | チャンネル数（1=mono, 2=stereo） |
| format | uint8 | オーディオフォーマット（0=PCM16, 1=IMA_ADPCM, **2=OPUS**） |
| total_samples | uint32 | 総サンプル数（0=不明。情報用、省略可） |
| gain | float32 | 再生ゲイン（0.0 〜 1.0）。intensity × SDK_gain × binding を SDK 側で計算した値 |
| target | null-terminated string | optional。ターゲットアドレス（省略時は全台）。NUL を含め 64 bytes 以内。詳細は `device-addressing.md` 参照 |

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
| offset | uint32 | バイトオフセット。Stream Gen 2 では重複・逆順の DATA を拒否する（uint32 の wrap の規則は `stream-session.md`） |
| data | variable | オーディオデータ（PCM16 raw bytes、ADPCM encoded bytes、または Opus フレーム列） |

- **触覚出力が 1 系統の受信機**（モーターが 1 個。CAPS の `haptic_channels` = 1）は、stereo の stream を (L+R)/2 で mono にして鳴らす（片方の channel だけを鳴らさない）。1.x の SDK はそうした endpoint へ pan を適用しない混合を送る（`sdk-multi-stream.md` §6.15）。
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

ストリーミング終了のヒント。Stream Gen 2 では 16 byte の session envelope だけを持つ（Stream Gen 1 では payload なし）。リングバッファは自然にドレインされる。ACK は返さない。END が失われても、Stream Gen 2 の受信機は、受理した DATA が 5 秒途絶えた session を END と同じ扱いで終了する（`stream-session.md` Inactivity timeout）。送信側は session を開いている間、無音を含め DATA を送り続ける。

受信側は有効なsession世代を検証してからENDを適用する。遅れた旧世代のENDで新世代を停止してはならない。

### 0xFF ERROR

デバイス → 送信元。受け付けなかったパケットの理由を知らせる。header の `protocol_version` は `0x01`、`seq` はデバイス自身の送信番号とする。

| フィールド | 型 | 説明 |
|---|---|---|
| error_code | uint16 | 下表 |
| message | null-terminated string | 人が読む説明（ASCII、NUL を含め 64 bytes 以内）。判定には使わない |
| ref_command | uint8 | 原因のパケットの command_type（以下 3 項目は §4.0 の末尾の追加） |
| ref_seq | uint16 | 原因のパケットの seq |
| detail_length | uint8 | `detail` の byte 数 |
| detail | bytes | code ごとの詳細。0x0011–0x0017 は原因のパケットの 16 byte の envelope。他の code は空（`detail_length` = 0） |

0.x の SDK は `error_code` と `message` だけを読む。

送る規則:

- 原因のパケットの送信元 (IPv4, UDP port) へ unicast で送る。以下「送信元」はこの (IPv4, UDP port) の組を指す。
- 同じ送信元・同じ `error_code` には、1 秒に 1 回までとする（毎 10 ms の DATA が拒否され続けても、1 秒に 1 通）。
- 機体全体でも 1 秒に 10 通までとする。頻度を数える表が満杯のときは、新しい送信元へは送らない。
- 送信元の UDP port が 0 のとき、送信元の address が broadcast・multicast のときは送らない。（hapbeat-helper は UDP 7700 から送るので、port 7700 は除外しない。機体どうしの往復は、機体が ERROR・PONG・CAPS に ERROR を返さないことで起きない）
- ERROR・PONG・CAPS に対して ERROR を送らない。`stream-session.md` の Errors に挙げた正常な事象（古い END、同じ BEGIN の再送など）には送らない。
- 定義済みのコマンドのうち、そのノードが役割上扱わないもの（例: broker・sensor が受けた PLAY・STREAM・CONNECT_STATUS）は、黙って無視する（UNKNOWN_COMMAND を返さない）。
- 1.x のファームは送る（CAPS の `features` bit1）。0.x のファームは送らない。

受ける規則（SDK）:

- 自分が送った先の機体の address と UDP port 7700 から届いた ERROR だけを扱う。stream の code（0x0011–0x0017）は、`detail` が自分の追跡している session（現在のもの、または直前に終えたもの）の envelope と一致するときだけ扱う。それ以外は無視する（他の送信者の偽装による停止を防ぐ。信頼された LAN の前提の範囲での対策であり、認証ではない）。
- 扱いは endpoint ごとに決める（ある機体の ERROR で、他の機体への送信を変えない）。

| code | 名前 | 原因 | 送信側の扱い |
|---|---|---|---|
| 0x0001 | UNSUPPORTED_VERSION | 知っている command_type で、知らない `protocol_version` | ログに出す |
| 0x0002 | UNKNOWN_COMMAND | 知らない command_type | その endpoint でその機能を使わない |
| 0x0003 | MALFORMED | 長さの不足・不一致、必須項目の欠落、範囲外の値、長すぎる target | ログに出す |
| 0x0010 | STREAM_GEN_UNSUPPORTED | Stream Gen 2 専用の受信機が Stream Gen 1 を受けた | 1.x の SDK: その endpoint の分類が古い（機体が更新された）ので、拡張 PING を unicast で送って分類し直す。`message` は Stream Gen 1 しか送れない旧い SDK の利用者向けに、SDK の更新を促す文にする |
| 0x0011 | STREAM_LEASE_INVALID | lease が無い・期限切れ・送信元の束縛が違う・`device_boot_id` が違う | 拡張 PING で lease を取り直し、新しい世代で始め直す |
| 0x0012 | STREAM_SUPERSEDED | BEGIN・DATA の ticket が high-water の ticket より小さい（別の lease の session が後から始まった） | その機体を保留し、自動で奪い返さない |
| 0x0013 | STREAM_NOT_STARTED | high-water より新しい tuple の DATA で、その BEGIN を受けていない | 同じ BEGIN を再送する |
| 0x0014 | STREAM_TIMED_OUT | inactivity timeout で終えた session への DATA | session を続けるなら、新しい世代で BEGIN する |
| 0x0015 | STREAM_STOPPED | STOP_ALL で終えた session への DATA | その機体から source を外し、同じ Playback ではその機体に再参加しない（`sdk-multi-stream.md` §6.13） |
| 0x0016 | STREAM_ENDED | END で終えた session への DATA | ログに出す（送信側の不具合） |
| 0x0017 | STREAM_TARGET_MISMATCH | BEGIN の target がこの機体に一致しない | endpoint を再解決する |

stream の code の詳細な条件は `stream-session.md` の Receiver ordering と Errors に従う。

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
`/hapbeat/play` の第 5 引数 `pan`（float）は省略可で、省略時は 0.0（中央）として扱う。

## 7. シーケンス番号

- 型: uint16（0 〜 65535）
- 65535 の次は 0 にラップアラウンドする
- **SDK はパケット送信ごとに seq をインクリメントする（必須）**。下記の重複排除が
  これを前提にしているため、同一 seq を別コマンドで使い回してはならない
- 受信側は直近に受信した seq を追跡し、同一の seq を持つパケットを重複として無視する

### 7.1 PLAY / STOP / STOP_ALL の重複排除（同一コマンドの複数経路送信）

受信デバイスは **PLAY / STOP / STOP_ALL** について、**(送信元 IP, seq)** の組を短時間
（実装値 500 ms）記憶し、同じ組を再受信した場合 2 回目以降を無視する。

これにより送信側は、**同一コマンドを意図的に複数経路へ送ってよい**:

- 既知デバイス（PONG で IP を学習済み）へ **unicast** — DTIM 遅延なしで即時到達
- 未知デバイス（起動直後・電源入れ直し直後）のために **broadcast** を 1 発 — 保険

デバイス側が二重発火を吸収するため、送信側は「どちらが先に届いたか」を意識しなくてよい。

制約と根拠:

- キーは **seq 単独ではなく (送信元 IP, seq)**。複数の送信アプリがそれぞれ独立した
  seq カウンタを持つ構成で、互いを誤って抑制しないため
- 送信側が 1 コマンドごとに seq をインクリメントする限り、連打や高速な再発火では
  seq が異なるので誤抑制は起きない。同一 seq が短時間に複数届くのは
  「同じコマンドが複数経路で来た」場合に限られる
- **STREAM 系（0x30 / 0x31 / 0x32）は対象外**。送信側は STREAM 系にも送信ごとに増やした seq を
  付けるが、受信側は STREAM 系の seq を重複排除にも順序の判定にも使わない。Stream Gen 2 の
  順序は envelope と DATA の offset で判定する（`stream-session.md`）
- 記憶期間を過ぎた同一 seq は通常どおり発火する（送信アプリ再起動で seq が
  巻き戻った場合に恒久的に無視されることを避けるため）

## 8. targetTime の扱い

- 単位: マイクロ秒
- 基準: 送信側とデバイスで合意した時刻
- `0` を指定した場合: 即時再生
- 過去の時刻を指定した場合: 即時再生にフォールバック
- SDK は PING/PONG を用いてデバイスとの時刻差を推定し、targetTime を補正することが推奨される

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
- ストリーミングパケット（STREAM_DATA）: 送信側は **1472 bytes 以下**（ヘッダ + payload の合計。推奨は 1400 bytes 以下）、受信側は **1500 bytes まで**受理する
- 1472 bytes は、Ethernet MTU 1500 から IPv4 ヘッダ 20 bytes と UDP ヘッダ 8 bytes を引いた、IP フラグメンテーションを起こさない UDP payload の上限である。VPN やトンネルを経由する経路では MTU が小さくなるため、1400 bytes 以下を推奨する

## 11. ストリーミングプロファイルの対応広告（get_info）

複数のストリーミングプロファイル（`P-haptic` / `P-audio-LD` / `P-audio-Q`、定義は `docs/instructions-opus-streaming-plan-202607040323.md` §2）が併存するため、送信側（SDK/Studio/Helper）は receiver がどの `format` をデコード可能かを事前に知る必要がある。

- receiver は `get_info`（serial + TCP）で **`stream_formats`（string 配列）** を広告する:
  ```json
  "stream_formats": ["pcm16", "adpcm", "opus"]
  ```
- 値は format 単位（`"pcm16"` / `"adpcm"` / `"opus"`）。profile（LD/Q）の区別は wire format が同一（format=2）のため広告しない — フレーム長/ビットレートは STREAM_BEGIN が自己記述する。
- Opus 未対応の firmware（旧 build）は `stream_formats` を返さない。送信側は**フィールド不在 = pcm16/adpcm のみ対応**とみなす。
- Helper は本フィールドを get_info passthrough で Studio/SDK に透過する。
- 1.x のファームは同じ内容を、UDP の CAPS（§0x13 の `stream_formats`）と get_info の `caps.stream_formats`（`serial-config.md` §4.1）でも申告する。UDP だけを使う SDK は CAPS を読む。

## 12. 関連文書

- `versioning.md` — 版の付け方、変更の分類、無視・拒否の規則、凍結している形式（DEC-096）
- `stream-session.md` — Stream Gen 2（セッション方式）の識別・順序・lease・timeout
- `espnow-stream.md` — ESP-NOW transport 上の Opus profile（`P-audio-LD` 相当）のパケット形式
- `../docs/decision-log.md` DEC-042 — Opus 採用確定の判断
- `../docs/instructions-opus-streaming-plan-202607040323.md` — プロファイル設計・遅延バジェット・実装フェーズの計画書（本文書の §0x30/§0x31 拡張の元仕様）

> ドラフト時の open issues は 2026-07-04 レビューで裁定済み: get_info 広告=`stream_formats` 配列（§11）/ DTX=禁止（§0x31）/ pre_skip=wire から削除・送信側吸収（§0x30）/ フラッシュ閾値=デコード後 PCM 領域で共通（§0x30）/ channels=48000/2 固定推奨 + libopus 自己記述に委譲（§0x30）。
