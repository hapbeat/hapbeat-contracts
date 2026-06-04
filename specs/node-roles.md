# ノード役割 / 通信モード仕様書（node roles / transports）

## 1. 概要

本文書は Hapbeat エコシステムの **ノード役割 (role)** と **通信モード (transport)** の taxonomy を定義する。
ツールチェーン（Studio / Helper）はこの 2 軸を「デバイス属性」として扱い、UI を出し分ける（DEC-034）。

> **設計原則:** 通信モードは *アプリのページ/タブ* ではなく *デバイス（ノード）の属性*。
> 型を名乗らないノードは従来どおりの UDP 受信機として扱われ、UDP 利用者の体験は変わらない。

すべてのノードは **同一の ESP32 系 SoC** で動作し、**共通の設定プロトコル**（`serial-config.md`）を喋る。
これにより Studio は「どの役割のノードでも、同じ作法でファーム書込 → 設定」ができる。

## 2. ノード役割 (role)

| role | 役割 | 代表ハードウェア | 主な transport | 設定経路 |
|---|---|---|---|---|
| `receiver` | 触覚を再生する装着デバイス（不変の中核） | Hapbeat band / necklace (ESP32-S3) | `udp` / `mqtt` / `espnow_stream` | Wi-Fi 系は Helper(TCP 7701)、それ以外は USB serial |
| `sensor` | センサ値をトリガに event を発火する送信元 | M5 ATOM 系 + センサ（例: 色センサ） | `mqtt` | Wi-Fi（Helper or USB serial） |
| `broker` | MQTT メッセージを中継する組み込みブローカー | M5 AtomS3（組み込み broker） | `mqtt`（インフラ） | Wi-Fi（Helper or USB serial） |
| `transmitter` | ライブ音声を ESP-NOW で同報する送信元 | M5 / XIAO + 音声 codec | `espnow_stream`（インフラ） | USB serial（Wi-Fi STA 非接続のため） |

`receiver` が常に存在する不変の中核で、`sensor` / `broker` / `transmitter` はシナリオ固有のサテライト・ノードである。

## 3. 通信モード (transport)

| transport | 用途 | 経路 | 関連仕様 |
|---|---|---|---|
| `udp` | リアルタイム（Unity 等 SDK 連携） | SDK → Wi-Fi UDP broadcast → receiver（group/address フィルタ） | `message-format.md` |
| `mqtt` | センサ起点の遠隔通知（施設 Wi-Fi 経由） | sensor → broker(MQTT) → receiver | `mqtt-transport.md` |
| `espnow_stream` | 会場同報（PA ライブ音声 → 全観客が同時に触覚） | transmitter → ESP-NOW broadcast → receiver | `espnow-stream.md` |

- `transport` は **ファームのビルドで確定**し、`get_info` で報告される（実行時スイッチではない）。
  「正しいファームを焼く」モデルに統一することで、Studio はノードを発見した時点で適切な設定面を出せる。
- `receiver` は将来的に複数 transport を同時サポートしうる（例: udp + mqtt）。その場合 `get_info.transports`（配列）で報告してよい（§4）。

## 4. get_info の必須報告フィールド

すべてのノードは `serial-config.md` の `get_info` で、既存フィールドに加えて以下を **必ず** 報告する。

| フィールド | 型 | 説明 |
|---|---|---|
| `role` | string | §2 の役割（`receiver` / `sensor` / `broker` / `transmitter`） |
| `transport` | string | §3 の主 transport。複数対応時は代表値（詳細は `transports`） |
| `transports` | string[] | optional。複数 transport 対応時の全リスト（例: `["udp","mqtt"]`） |
| `board` | string | 基板識別子（例: `band_wl_v3` / `duo_wl_v3` / `atom_lite` / `atom_s3` / `xiao_c6`）。ファーム書込の board mismatch 検証に使う |

`role` / `transport` / `board` の **3 つは全ノード必須**。これが Studio/Helper の mode-aware 化の唯一の前提となる。

## 5. 共通設定プロトコル（全ノード）

すべてのノードは `serial-config.md` の JSON 設定プロトコルを実装する。
コマンドは **役割に応じて部分集合**になる（未対応コマンドは `{"status":"error","message":"unsupported for role"}` を返す）。

| コマンド | receiver | sensor | broker | transmitter | 説明 |
|---|:--:|:--:|:--:|:--:|---|
| `get_info` | ✅ | ✅ | ✅ | ✅ | role/transport/board 含む |
| `set_name` / `set_address` | ✅ | ✅ | ✅ | ✅ | 識別 |
| `set_wifi` / `get_wifi_status` / `clear_wifi` | ✅ | ✅ | ✅ | ➖ | Wi-Fi（transmitter は不要） |
| `reboot` | ✅ | ✅ | ✅ | ✅ | 再起動 |
| `set_broker_host` | ✅(mqtt) | ✅ | ➖ | ➖ | MQTT broker アドレス（`"auto"` = mDNS 発見） |
| `set_espnow_channel` | ✅(espnow) | ➖ | ➖ | ✅ | ESP-NOW チャンネル（1/6/11） |
| `set_gain` | ✅(espnow) | ➖ | ➖ | ➖ | espnow_stream 受信の既定ゲイン |
| `set_input_level` | ➖ | ➖ | ➖ | ✅ | ライン入力レベル |
| `set_broker_config` | ➖ | ➖ | ✅ | ➖ | broker の static octet / port |
| `set_sensor_mapping` / `get_sensor_mapping` | ➖ | ✅ | ➖ | ➖ | センサ値 → event の対応表（`mqtt-transport.md` §5） |

各コマンドの詳細フォーマットは `serial-config.md` を参照。

## 6. ファーム配布との関係

役割・transport・board の組み合わせごとに別のファームビルド（PlatformIO env）が存在する。
配布 manifest はこの 3 軸でファームを分類し、Studio が「このノードに正しいファーム」を提示する。
詳細は `firmware-distribution.md`。

## 7. 関連文書

- `serial-config.md` — 共通設定プロトコル（本仕様のコマンド実体）
- `message-format.md` — UDP transport の wire format
- `mqtt-transport.md` — MQTT transport（topic / payload / broker 発見）
- `espnow-stream.md` — ESP-NOW streaming transport（packet 形式）
- `firmware-distribution.md` — ファーム配布 manifest（role/transport/board 分類）
- `../docs/decision-log.md` DEC-034 — 本 taxonomy の決定
