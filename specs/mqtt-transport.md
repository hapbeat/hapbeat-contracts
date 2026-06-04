# MQTT transport 仕様書

## 1. 概要

`mqtt` transport は、**センサ起点の遠隔通知**ユースケース（例: 施設内のセンサ値をトリガに、離れた場所の装着者へ振動通知）のための通信モード。

```
[sensor node] --publish--> [broker node (組み込み MQTT)] --deliver--> [receiver node(s)]
   role=sensor                 role=broker                              role=receiver, transport=mqtt
```

- **broker は Hapbeat の組み込みノード**（M5 AtomS3 等、`role=broker`）で動作する。PC は不要（無人常設可。DEC-034）。
- 施設の既存 Wi-Fi（LAN）上で完結する。Studio / Helper は **セットアップ・管理専任**で、稼働中のデータ経路には介在しない。
- payload は既存 UDP `PLAY`（`message-format.md` 0x01）と意味的に等価。**触覚資産（Kit/event）は transport 非依存**で共通。

## 2. ブローカー

| 項目 | 値 |
|---|---|
| 実体 | Hapbeat broker ノード（`role=broker`）上の組み込み MQTT broker |
| ポート | 1883（plaintext、LAN 内前提） |
| mDNS | サービス `_mqtt._tcp`、ホスト名 `hapbeat-broker`（`.local`） |
| 認証 | LAN 内前提のため必須としない（将来 username/role 分類は任意拡張） |
| QoS | 1（at-least-once） |

> plaintext/no-auth は「施設の隔離 LAN 内」を前提とする割り切り。インターネット越え/TLS が要るユースケースは本仕様の対象外（別途検討）。

## 3. ブローカー発見（zero-config）

receiver / sensor は broker を以下の優先順で解決する。

1. `set_broker_host` で `"auto"`（既定）の場合: **mDNS `_mqtt._tcp` browse** で `hapbeat-broker` を発見。
2. 明示ホスト/IP が設定されている場合: それを使用。
3. （任意 fallback）ゲートウェイ subnet 上の固定オクテット（broker の `set_broker_config.static_octet`）から算出。

broker は起動時に mDNS 登録 + 固定 IP（`static_octet`）を自己設定する。これにより**同一 LAN なら設定不要で繋がる**。

## 4. トピックとペイロード

トピックは平坦な CSV を避け、**役割で分けた階層 + JSON payload** を用いる（参考実装の踏襲ではなく再設計）。

| トピック | publisher | subscriber | 用途 |
|---|---|---|---|
| `hapbeat/play` | sensor | receiver | event 再生コマンド |
| `hapbeat/stop` | sensor | receiver | event 停止コマンド |
| `hapbeat/status/<node>` | 各ノード | broker / 管理 | 死活・状態（任意） |

### 4.1 `hapbeat/play` payload（JSON）

| フィールド | 型 | 説明 |
|---|---|---|
| `event_id` | string | Kit manifest `events`（command-mode）キー。`message-format.md` PLAY と同義 |
| `target` | string | ターゲットアドレス（空 = 全台）。`device-addressing.md` 準拠 |
| `gain` | number | 0.0〜1.0 |
| `loop` | bool | optional。ループ再生（既定 false） |
| `ts` | number | optional。送信時刻（ms epoch、情報用） |

例:
```json
{"event_id": "alert-kit.urgent", "target": "player_1/chest", "gain": 1.0, "loop": false}
```

### 4.2 `hapbeat/stop` payload（JSON）

| フィールド | 型 | 説明 |
|---|---|---|
| `event_id` | string | 停止対象（空文字 = target の全 event 停止） |
| `target` | string | ターゲットアドレス |

### 4.3 retain / late-joiner

- `hapbeat/play` / `hapbeat/stop` は **retain=false**。触覚イベントは momentary であり「遅れて届くより消えた方がマシ」（UDP と同じ思想）。
- 再起動した receiver は過去のイベントを取りこぼすが、通知用途では許容。retain による誤再発火を避ける。
- 継続状態（例: 持続アラート）が要るユースケースが立ち上がった時点で、別途 retained な `hapbeat/state/<target>` トピックを追加検討する（現時点では未定義）。

## 5. センサ → event マッピング（sensor ノード）

sensor は「センサ読み取り値の分類」→「発火する `hapbeat/play` payload」の対応表を持つ。
表は Studio の mapping editor が編集し、`serial-config.md` の `set_sensor_mapping` でノードに書き込む。

mapping エントリ:

| フィールド | 型 | 説明 |
|---|---|---|
| `key` | string | 分類ラベル（例: 色名 `red`/`blue`） |
| `match` | object | センサ種別依存の一致条件（色センサ: RGB 閾値ボックス `r_min`/`r_max`/`g_min`/`g_max`/`b_min`/`b_max`） |
| `event_id` | string | 一致時に publish する event |
| `target` | string | ターゲットアドレス |
| `gain` | number | 0.0〜1.0 |
| `debounce_ms` | number | optional。同一 key 連続発火の最小間隔（既定はノード実装値） |

- sensor は周期的にセンサを読み、`match` に最初に一致した `key` の payload を `hapbeat/play` に publish する。
- 色センサの分類は chromaticity（clear 正規化 RGB）で行うことを推奨（明るさ変動に頑健）。実装詳細はファーム側。

## 6. receiver 側の扱い

- `transport=mqtt` の receiver は broker に接続し `hapbeat/play` / `hapbeat/stop` を subscribe する。
- 受信 payload の `target` を自アドレスと照合（`device-addressing.md`）し、一致時のみ `event_id` を再生。
- 再生経路・Kit・event table は `udp` と完全共通（transport だけが差し替わる）。

## 7. 関連文書

- `node-roles.md` — role/transport taxonomy と get_info 必須フィールド
- `serial-config.md` — `set_broker_host` / `set_broker_config` / `set_sensor_mapping`
- `message-format.md` — UDP PLAY（payload の意味的等価元）
- `device-addressing.md` — target 照合
- `../docs/decision-log.md` DEC-034
