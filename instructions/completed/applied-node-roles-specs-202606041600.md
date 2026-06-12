# 事後承認 note: ノード役割 / 通信モード仕様の追加 (DEC-034)

- **編集元セッション**: hapbeat-sdk-workspace (起点 repo)、2026-06-04
- **関連 DEC**: DEC-034（ツールチェーン mode-aware 化） / DEC-033（ESP-NOW 60 台 streaming）

## 背景

Studio に MQTT / ESP-NOW streaming を「デバイス属性（role/transport）」として載せる方針（DEC-034）。
contracts 起点ルールに従い、まず本 repo に仕様を追加してから Studio / Helper / firmware に展開した。
「センサ通知(MQTT)」「会場同報(ESP-NOW stream)」「リアルタイム(UDP)」の 3 通信モードを taxonomy 化。

## 入った変更（このセッションで本 repo に追加）

新規 spec:
- `specs/node-roles.md` — role(receiver/sensor/broker/transmitter) × transport(udp/mqtt/espnow_stream) の taxonomy、get_info 必須フィールド（role/transport/board）、役割別 config コマンド表
- `specs/mqtt-transport.md` — MQTT topic(`hapbeat/play`等)/JSON payload/broker 発見(mDNS `_mqtt._tcp`)/retain 方針/sensor mapping
- `specs/espnow-stream.md` — ESP-NOW stream packet（type 0xAA, 16kHz stereo IMA-ADPCM, piggyback, channel グループ）
- `specs/firmware-distribution.md` — 配布 manifest v2（複数 repo × role/transport/board の集約、variant.json / fragment）
- `schemas/firmware-manifest.schema.json` — 上記 manifest の JSON Schema (schema_version 2)

既存 spec への追記:
- `specs/serial-config.md` — get_info に role/transport/transports/board + 役割固有フィールド、§4b に役割固有コマンド（set_broker_host / set_espnow_channel / set_gain / set_input_level / set_broker_config / set_sensor_mapping / get_sensor_mapping）、NVS キー追加
- `specs/message-format.md` — 冒頭に transport 別文書への相互参照（udp=本書 / mqtt / espnow_stream）
- `README.md` — specs 一覧に新規 5 spec を追加

## 横断背景（なぜこの変更か）

- MQTT は「センサ値トリガで遠隔の人物へ振動通知」、ESP-NOW stream は「PA 音声を会場全員へ同報」。いずれも既存 UDP とは別 transport だが、**触覚資産(Kit/event)と再生意味論は transport 非依存で共通**。
- payload は既存 UDP `PLAY`(0x01) と意味的に等価に揃えた（event_id/target/gain）。
- broker は M5 組み込み（PC 不要・無人常設）、MQTT 受信機は mainline device-firmware 統合（fork しない）に確定（DEC-034 の 2 分岐）。

## 検証状況

- JSON Schema (`firmware-manifest.schema.json`) は手書きの valid JSON。Studio 側の集約 script で生成した manifest が本 schema の必須フィールド構成に適合することを確認済（`board` は v1 推論で決まらない場合があるため optional に確定）。
- spec の整合は machine validation していない（規範文書）。下記アクション参照。

## この repo セッションへのアクション

1. 5 spec + schema をレビューし、矛盾なければ本 note を `instructions/completed/` へ移動。
2. 既存 spec（message-format / serial-config / device-addressing / kit-format）との整合を点検（特に target 照合・event_id 規約が transport 間で一貫しているか）。
3. 必要なら fixtures（sample MQTT play payload / ESP-NOW packet / firmware manifest v2）を追加して contract test 可能にする。
4. 問題があれば fix instruction を新規作成。

## 連動して変更された他 repo（参考）

- **hapbeat-studio**（セッション対象）: DeviceDetail role 別 subtab + 役割別設定パネル + firmware library role 分類 + manifest v2 reader + 集約 script + dev plugin 多 repo 対応。build/typecheck 通過済。
- **hapbeat-helper**: get_info の role/transport/board/役割固有フィールド passthrough + 役割別 config コマンドのリレー追加。py_compile 通過済。applied note 別途。
- **hapbeat-device-firmware / hapbeat-transmitter-firmware**: 実装の forward instruction を各 `instructions/` に起票（未実装・実機検証は各 repo セッション）。
