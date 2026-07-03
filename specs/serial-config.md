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

**Response:** フィールドは**フラット**（`data{}` ラッパー無し）。バージョンは `fw`（`firmware` ではない）。
```json
{
  "status": "ok",
  "name": "Hapbeat-A",
  "group": 1,
  "address": "player_1/pos_r_wrist",
  "fw": "2.0.0",
  "build": "a1b2c3d",
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
```

> wire 上はフラット構造が source of truth（firmware `tcp_server.cpp cmdGetInfo` /
> `serial_config.cpp` と Studio の読み出しが一致。2026-06-13 監査で確認）。
> 旧版の `data{}` ラッパー・`firmware` キーは廃止。

`role` / `transport` / `board` は **全ノード必須**（`node-roles.md` §4）。
`transports` は複数 transport 対応時のみ。役割固有フィールド（`broker_host` / `gain` / `input_level` / `relay_source` / `static_octet` / `mqtt_port` / `mappings` 等）は当該役割でのみ含める。

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

### 4.8 set_broker_host — MQTT クライアント設定（receiver(mqtt) / sensor）

**Request:**
```json
{"cmd": "set_broker_host", "host": "auto", "port": 1883, "topic_root": "default-topic"}
```

| フィールド | 型 | 説明 |
|---|---|---|
| `host` | string | `"auto"`（mDNS `_mqtt._tcp` で自動発見）または明示ホスト/IP（例: `"192.168.1.10"` / `"hapbeat-broker.local"`） |
| `port` | number | optional（既定 1883）。明示 host 時の接続ポート。`auto` 時は mDNS が advertise したポートが優先 |
| `topic_root` | string | optional（既定 `"default-topic"`）。トピック第 1 階層（`mqtt-transport.md` §4） |

NVS: `hapbeat/broker_host` / `hapbeat/broker_port` (u16) / `hapbeat/mq_root`。詳細は `mqtt-transport.md` §7。

**Response:** `{"status": "ok", "cmd": "set_broker_host", "host": "auto", "port": 1883, "topic_root": "default-topic"}`

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
    {"key": "red",  "match": {"r_min": 140, "g_max": 70, "b_max": 70},  "event_id": "alert-kit.urgent",  "target": "player_1/chest", "gain": 1.0, "oled": "Red alert occured"},
    {"key": "blue", "match": {"r_max": 70, "g_max": 90, "b_min": 120},  "event_id": "alert-kit.calm",    "target": "", "gain": 0.7}
  ]
}
```

`match` の意味はセンサ種別に依存する（色センサは RGB 閾値ボックス）。`event_id` は Kit manifest の `events`（command-mode）キー。`target` は `device-addressing.md` 準拠。各行は任意で `oled`（受信機に表示する文言、§4.1）・`debounce_ms`・`topic`（送り先 root）を持てる。
詳細は `mqtt-transport.md` §5。

**Response（set）:** `{"status": "ok", "cmd": "set_sensor_mapping", "count": 2}`

**Request（get）:** `{"cmd": "get_sensor_mapping"}`
**Response（get）:** `{"status": "ok", "cmd": "get_sensor_mapping", "data": {"mappings": [ ... ]}}`

### 4.14 get_sensor_reading — センサ現在値の取得（sensor）

Studio の「ライブ値を見ながら閾値を設定する」チューニング UI 用。ポーリング前提（推奨 1 Hz 程度）。

**Request:**
```json
{"cmd": "get_sensor_reading"}
```

**Response:**
```json
{
  "status": "ok",
  "cmd": "get_sensor_reading",
  "data": {
    "sensor": "tcs34725",
    "r": 162, "g": 54, "b": 39,
    "clear": 1240,
    "key": "red",
    "age_ms": 35
  }
}
```

- `r`/`g`/`b`: clear 正規化（chromaticity）した 0〜255 値 — mapping の `match` 閾値と同じスケール
- `clear`: 生の明るさ（参考値）
- `key`: 現在の読み値に一致している mapping キー（debounce 無視の表示用。一致なしは `""`）
- `age_ms`: 最終サンプルからの経過 ms
- センサ未接続・有効サンプル無しの場合は `{"status":"error","message":"sensor not ready"}`
- get_info の `sensor_types` フィールド（**配列**、sensor 役割のみ）でセンサ種別を報告する（例: `["tcs34725"]`）。1 つの送信機が複数センサを持つ将来拡張のため配列とする。単一センサのビルドは要素 1 つを返し、単一しか扱わない consumer は `[0]` を読む

### 4.15 set_alert_mode — alert-loop / ack 長押し時間（receiver(mqtt)）

MQTT 受信機の alert-loop（`mqtt-transport.md` §6.1）と、停止に要する**意図的長押し時間**を設定する。

**Request:**
```json
{"cmd": "set_alert_mode", "loop": true, "ack_hold_ms": 1000}
```

- `loop` (bool, optional): `true` = アラートを**意図的なボタン長押しで acknowledge されるまで**ループ（一度離して〜`ack_hold_ms` 長押し。瞬間タップや押しっぱなしでは止まらない。詳細は `mqtt-transport.md` §6.1） / `false` = 単発。
- `ack_hold_ms` (number, optional): 停止に要する長押し時間（ms、200〜10000 にクランプ、既定 1000）。
- `loop` / `ack_hold_ms` は**いずれか一方だけでも可**（両方省略はエラー）。
- NVS: `hapbeat/alert_loop` (u8, 既定 1) / `hapbeat/ack_hold_ms` (u32, 既定 1000)。ファームは都度参照するため、変更は**即時反映**（再起動不要）。
- get_info の `alert_loop`（bool）・`ack_hold_ms`（number）（receiver(mqtt) のみ）で現在値を読む。

**Response:** `{"status": "ok", "cmd": "set_alert_mode", "loop": true, "ack_hold_ms": 1000}`

### 4.16 set_recv_topics — 受信 topic（receiver(mqtt)）

MQTT 受信機が購読する topic root のリストを設定する（`mqtt-transport.md` §6）。各 root の
`<root>/play` + `<root>/stop` を購読する。

**Request:**
```json
{"cmd": "set_recv_topics", "topics": ["default-topic", "ward-a"]}
```

- `topics` (array of string): 購読する topic root。各 root はスラッシュ無し ≤32 文字。空配列 =
  既定チャンネル（`default-topic`）のみ購読。
- NVS: `hapbeat/recv_topics`（JSON 配列）。変更は受信機の再接続/再起動で反映。
- get_info の `recv_topics`（array, receiver(mqtt) のみ）で現在値を読む。

**Response:** `{"status": "ok", "cmd": "set_recv_topics", "count": 2}`

### 4.17 制限モード（receiver(mqtt) の重要色フィルタ）

MQTT 受信機の **制限モード**（`mqtt-transport.md` §6.3）。ON のとき `critical:true` の `play` のみ
再生し、それ以外は無視する。OFF（既定）は全色再生。

- **切り替えは本体ボタンの `limit_toggle` アクション**で行う（シリアル set コマンドは持たない）。
  ボタンに `limit_toggle` を割り当てると、押下のたびに ON/OFF をトグルし、OLED に現在モード
  （`制限モード` / `全て再生`）を短時間表示する。`limit_toggle` は `transport=mqtt` かつ
  非 sensor 役割でのみ有効。
- NVS: `hapbeat/alert_limit` (u8, 既定 0=全て再生)。ファームは受信のたびに RAM キャッシュを
  参照するため、トグルは**次の受信から即時反映**（再起動不要）。
- get_info の `alert_limit`（bool, receiver(mqtt) のみ）で現在値を読む。

### 4.18 set_relay_source — リピータの中継元 source MAC（transmitter / repeater）

ESP-NOW stream のリピータ機が中継する **1 つの source MAC** を設定する（`espnow-stream.md` §7.2）。
設定するとそのデバイスはリピータとして動作し、当該 source の `0xAA` パケットのみを verbatim
再ブロードキャストする（ループ防止のため他ソース・他リピータは中継しない = 最大 1 ホップ）。

**Request:**
```json
{"cmd": "set_relay_source", "mac": "AA:BB:CC:DD:EE:FF"}
```

- `mac` (string): 中継する source 機の MAC（`""` でリピータ動作を無効化 = 通常の transmitter）。
- NVS: `espnow/relay_src`（string）。一発勝負イベントでは flash-time 定数でも可。
- get_info の `relay_source`（string, transmitter のみ）で現在値を読む。

**Response:** `{"status": "ok", "cmd": "set_relay_source", "mac": "AA:BB:CC:DD:EE:FF"}`

### 4.19 set_espnow_ui — 受信機の省電力 UI ポリシー（receiver(espnow_stream)）

espnow_stream 受信機は Wi-Fi/UDP 機と挙動が大きく異なる（メニュー・Wi-Fi 設定なし、ただ受信して触覚を鳴らすだけ）。60 台 2 時間のウェアラブル運用に向け、OLED は**常時消灯**・LED は**常時 off**にし、**ボタン押下またはボリューム変更**で低輝度の音量オーバーレイを数秒だけ表示する。本コマンドはその挙動ポリシーを設定する（**全フィールド任意・部分更新**）。表示レイアウト自体はファーム固定（Studio の grid 編集対象外）。輝度は既存の `set_oled_brightness` を使う（本コマンドでは扱わない）。

- **既定画面**: 1 行目 = 全幅セグメント音量バー、2 行目 = `VOL n   BAT xxx%`（FW 版は既定画面には出さない）。
- **デバッグ画面**: いずれかのボタンを**長押ししている間だけ**、FW 版（dev suffix 込み）+ ESP-NOW リンク統計（`ch / loss% / sources / delay`）を表示。離すと既定画面に戻り自動消灯タイマー再開。

設定はすべて USB serial 経由（Wi-Fi 非接続のため）。受信機は純 ESP-NOW 運用で TCP 7701 を持たないので、Helper 経由 TCP では設定できない（Studio の Web Serial 経路を使う）。

**Request:**
```json
{"cmd": "set_espnow_ui",
 "auto_off_ms": 8000, "wake_on_button": true, "wake_on_volume": true,
 "led_enabled": false, "low_batt_pct": 15, "vol_wake_step": 1, "volume_steps": 16}
```

- `auto_off_ms` (uint32): wake 後に OLED を表示し続ける時間（ms、既定 8000、500〜60000）。
- `wake_on_button` (bool): ボタン押下で表示を起こす（既定 true）。
- `wake_on_volume` (bool): ボリューム変更で表示を起こす（既定 true）。
- `vol_wake_step` (uint8): ボリュームが**この段数以上**動いたら表示を起こす（既定 1 = 1 段変化で起こす、≥1）。微小なノブ揺れを無視したい場合に上げる。
- `led_enabled` (bool): ステータス LED を使うか（既定 false = 省電力で常時消灯）。
- `low_batt_pct` (uint8): この SOC 以下に落ちた瞬間に表示を起こして % を見せる（既定 15、0〜100）。
- `volume_steps` (uint8): ボリュームの段数（1〜64）。NVS 永続（`volume_control` 自体は永続しないため espnow_ui が保持・起動時に適用）。
- get_info の `espnow_ui`（object, receiver(espnow_stream) のみ）で現在値を読む（上記 7 フィールド）。

**Response:** 適用後の全 7 フィールドをエコーする（`{"status": "ok", "auto_off_ms": …, …}`）。コマンド適用時に受信機は確認のため表示を一度起こす。

**デバッグ readout（get_info の `stream` object, receiver(espnow_stream) のみ）:** 受信ストリームのライブ統計を返す（DEC-033 検証 / 現場での「強度」確認用）。`received`・`lost`・`recovered`（piggyback 復元）・`dropped`・`max_gap`（最大連続欠落）・`handoffs`・`sources`（生存 source 数）・`locked`（bool）・`locked_mac`（locked 時）・`delay_ms`（推定再生遅延）。RSSI は arduino-esp32 2.0.x の legacy callback では取得不可のため、損失率を強度の代理指標として使う。

### 4.20-pre set_stream_buffer — UDP ストリーム ジッタバッファ（全受信機共通）

UDP 音声ストリーム（§0x30）受信のジッタバッファ深さを設定する。既定（`buffer_ms=0`）は**低遅延**（pre-buffer ~4ms・アンダーラン時に再prime）で触覚向き。Wi-Fi のゆらぎで頻繁に途切れる用途（**ヘッドホンで音楽等・遅延許容**）では大きくすると途切れが大幅に減る（遅延と引き換え）。ボード非依存（UDP 受信を持つ全機）。

**Request:**
```json
{"cmd": "set_stream_buffer", "buffer_ms": 0}
```

- `buffer_ms` (uint16, **0〜500**): ジッタバッファ深さ（ms）。**0 = 低遅延（既定・触覚向き）**。>0 = その ms 分を貯めてから再生開始し、以後アンダーランでも再prime せず連続再生（音楽向き）。目安: HP 音楽 = 100〜150ms。リングは 256ms 上限。
- NVS 永続（`hapbeat/strm_buf_ms`）。起動時に適用。

**Response:** `{"status": "ok", "buffer_ms": …}`。

## 4c. DuoWL v4 オーディオ段設定（DEC-041）

DuoWL v4 は v3 と音声/触覚経路の構成が大きく変わった（2× AIC3204 codec・PAM8404 4 段可変アンプ・TPA6130A2 ヘッドホンアンプ・左右 2 モータ）。以下は **`board = "duo_wl_v4"` の receiver のみ**の per-device 設定で、個体差キャリブレーション用。全て NVS 永続 + 起動時再適用で、`set_oled_brightness` と同じ「set で即適用 + NVS 保存、`get_info` で読み出し」パターンに従う。他ボードは `{"status": "error", "cmd": "…", "message": "unsupported board"}` を返す。

読み出しは `get_info` の **`audio` object**（DuoWL v4 のみ）: `{"pam_db": 24, "lineout_db": 6, "boost_db": 0, "hp_db": -10}`。

### 4.20 set_haptic_gain — 触覚ドライブ段ゲイン（DuoWL v4 receiver）

触覚出力段の 2 アナログ段（**AIC3204 haptic codec の LOL/LOR ライン出力ドライバ** と **PAM8404 パワーアンプ**）を設定する。**全フィールド任意・部分更新**。

**Request:**
```json
{"cmd": "set_haptic_gain", "pam_db": 24, "lineout_db": 6, "persist": true}
```

- `pam_db` (uint8): PAM8404 粗ゲイン。**{6, 12, 18, 24} dB のいずれかにスナップ**（PAM8404 datasheet Table 1、G1/G0 ピン）。中間値は最寄りに丸める。
- `lineout_db` (int8): AIC3204 haptic codec の LOL/LOR ドライバゲイン（**−6〜+29 dB**、1 dB step、AIC3204 datasheet §5.3.16/17）。PAM の前段アナログ微調整。
- `persist` (bool, 既定 true): NVS 保存 + 起動時再適用。`false` = 一時適用のみ（ベンチ調整用、再起動で NVS 値に戻る）。
- PAM ゲインピンは GPIO のみ（I2C 不要）。再生中の切替はポップ音を避けるため firmware は再生停止中のみ適用する。

**Response:** 適用後（スナップ後）の値をエコー（`{"status": "ok", "pam_db": 24, "lineout_db": 6}`）。

### 4.21 set_dac_boost — DAC デジタルメイクアップゲイン（DuoWL v4 receiver）

AIC3204 の DAC digital volume は IC 仕様で **−63.5〜+24 dB**。firmware は既定でユーザー音量（wiper）を **0 dB 上限**にクランプする（0dBFS 素材のクリップ回避）。本コマンドは静かな素材の底上げ用に **一律メイクアップゲイン**を加える。

**Request:**
```json
{"cmd": "set_dac_boost", "boost_db": 0}
```

- `boost_db` (uint8, **0〜24 dB**): DAC digital volume に一律加算するメイクアップ。**0 = 既定（従来通り、上限 0 dB）**。最大ノブ位置（wiper 127）で `+boost_db` dB になる。IC 上限 +24 dB でクランプ。**注意**: 0dBFS 素材は `boost_db>0` でクリップする（アナログの `lineout_db` の方が歪みは少ない）。
- NVS 永続。ファームは音量適用のたびに参照。

**Response:** `{"status": "ok", "boost_db": …}`。

### 4.22 set_headphone_volume — ヘッドホン音量（DuoWL v4 receiver）

DuoWL v4 は **TPA6130A2 capless ヘッドホンアンプ**（v3 に無い）を持つ。触覚音量（DAC）とは独立の HP 出力レベルを設定する。

**Request:**
```json
{"cmd": "set_headphone_volume", "hp_db": -10}
```

- `hp_db` (int8, **−59〜+4 dB**（送信可能な整数値。HW 下限は 0x00=**−59.5 dB**）): TPA6130A2 音量（Reg 0x02、6 bit オーディオテーパ、−59.5 dB=0x00 〜 +4.0 dB=0x3F）。ファームが dB→6bit レジスタコードにマップする（テーパは非線形、TPA6130A2 datasheet §8.4.9 Table 2 準拠）。
- NVS 永続。

**Response:** `{"status": "ok", "hp_db": …}`。

## 5. NVS キー一覧

| namespace | key | 型 | 説明 |
|-----------|-----|-----|------|
| hapbeat | address | string (max 64) | デバイスアドレス（例: `player_1/chest`） |
| hapbeat | dev_name | string | デバイス名（最大 32 文字） |
| hapbeat | wifi_ssid | string | Wi-Fi SSID |
| hapbeat | wifi_pass | string | Wi-Fi パスワード |
| hapbeat | broker_host | string | MQTT broker アドレス（`auto` or host/IP）。receiver(mqtt)/sensor |
| hapbeat | broker_port | uint16 | 明示 host 時の MQTT 接続ポート（既定 1883）。receiver(mqtt)/sensor |
| hapbeat | mq_root | string | MQTT topic root（既定 `default-topic`）。sender の既定送信 root / receiver の購読 fallback |
| hapbeat | recv_topics | blob/json | receiver(mqtt) の購読 topic root リスト（JSON 配列）。空 = `default-topic` |
| hapbeat | mq_qos | uint8 | MQTT publish/subscribe QoS（0/1、既定 1）。receiver(mqtt)/sensor |
| hapbeat | alert_loop | uint8 | alert-loop モード（1=ループ/0=単発、既定 1）。receiver(mqtt) |
| hapbeat | alert_limit | uint8 | 制限モード（1=重要色のみ/0=全て再生、既定 0）。本体ボタン `limit_toggle` で切替。receiver(mqtt) |
| hapbeat | ack_hold_ms | uint32 | アラート停止の意図的長押し時間（ms、既定 1000、200〜10000）。`set_alert_mode` で設定。receiver(mqtt) |
| hapbeat | sens_map | blob/json | センサ → event 対応表（sensor）。各行は `oled`（受信機表示文言）・`topic`（送り先 root）を任意で含む |
| hapbeat | strm_buf_ms | uint16 | UDP ストリーム ジッタバッファ深さ（ms、0=低遅延既定、0〜500）。全 UDP 受信機。`set_stream_buffer` |
| espnow | channel | uint8 | ESP-NOW チャンネル（既存） |
| espnow | gain | float | espnow_stream 受信の既定ゲイン（receiver(espnow_stream)） |
| espnow | relay_src | string | リピータが中継する source MAC（transmitter/repeater）。空 = 中継無効 |
| espnow_ui | auto_off_ms | uint32 | wake 後の OLED 表示時間（ms、既定 4000）。receiver(espnow_stream) |
| espnow_ui | wake_btn | uint8 | ボタン押下で表示を起こす（1/0、既定 1）。receiver(espnow_stream) |
| espnow_ui | wake_vol | uint8 | ボリューム変更で表示を起こす（1/0、既定 1）。receiver(espnow_stream) |
| espnow_ui | led_en | uint8 | ステータス LED を使う（1/0、既定 0=常時消灯）。receiver(espnow_stream) |
| espnow_ui | low_batt_pct | uint8 | この SOC 以下で表示を起こす（既定 15）。receiver(espnow_stream) |
| espnow_ui | vol_wake_step | uint8 | ボリュームがこの段数以上動いたら表示（既定 1）。receiver(espnow_stream) |
| espnow_ui | volume_steps | uint8 | ボリューム段数（1〜64、espnow_ui が永続）。receiver(espnow_stream) |
| broker | octet | uint8 | broker static host octet（broker） |
| broker | port | uint16 | broker MQTT ポート（broker、既定 1883） |
| duo_audio | pam_db | uint8 | PAM8404 粗ゲイン（6/12/18/24 dB、既定 24）。DuoWL v4（DEC-041） |
| duo_audio | lineout_db | int8 | AIC3204 haptic LOL/LOR ドライバゲイン（−6〜+29 dB、既定 6）。DuoWL v4（DEC-041） |
| duo_audio | dac_boost | uint8 | DAC デジタルメイクアップ（0〜24 dB、既定 0=無効）。DuoWL v4（DEC-041） |
| duo_audio | hp_db | int8 | TPA6130A2 ヘッドホン音量（−59〜+4 dB、既定 −10）。DuoWL v4（DEC-041） |

> NVS キー名は ESP32 の 15 文字制限内（namespace `duo_audio` = 9 文字）。get_info の `audio` object フィールド名は上記キーと一致させる（`pam_db`/`lineout_db`/`boost_db`/`hp_db`。ただし `dac_boost` キー ↔ `boost_db` フィールドの差異に注意）。

## 6. エラーハンドリング

- 不正な JSON → 無視（レスポンスなし）
- 未知のコマンド → `{"status": "error", "cmd": "unknown", "message": "Unknown command"}`
- 必須フィールド欠落 → `{"status": "error", "cmd": "...", "message": "..."}`
