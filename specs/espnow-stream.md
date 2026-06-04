# ESP-NOW streaming transport 仕様書

## 1. 概要

`espnow_stream` transport は、**会場同報**ユースケース（PA のライブ音声を ESP-NOW で同報し、会場の全観客が装着する Hapbeat が同時に音声ベースの触覚を体験する。LE Audio Auracast 的）のための通信モード。

```
[PA / mixer] --analog line-in--> [transmitter] --ESP-NOW broadcast--> [receiver ×N (観客)]
                                   role=transmitter                      role=receiver, transport=espnow_stream
```

- **broadcast（peer `FF:FF:FF:FF:FF:FF`）**による真の one-to-many。ペアリング不要、ACK なし、台数は RF のみが上限。
- **「グループ」= Wi-Fi チャンネル**（1/6/11）。送信機と受信機を同一チャンネルに合わせる。別チャンネルなら混信しない。
- 低遅延優先（LR モードは使わず 11b/g/n）。詳細な無線方式選定・多重化戦略は **DEC-033** を参照。

> 本仕様は ESP-NOW 上の **パケット形式**を定義する（Layer 3 相当の internal spec）。
> 移植元の実装は `hapbeat-wireless-firmware` / `wireless-sender-firmware`（`lib/ima_adpcm`）。

## 2. 音声パラメータ

| 項目 | 値 |
|---|---|
| サンプルレート | 16000 Hz（送信機・受信機で一致必須） |
| チャンネル | 2（stereo） |
| コーデック | IMA-ADPCM 4:1（L=low nibble, R=high nibble の 1 byte/frame） |
| frames/packet | 16（≒ 1 ms/packet） |
| 無線プロファイル | 11b/g/n、6 Mbps、broadcast |

## 3. パケット形式

ESP-NOW payload（最大 250 bytes）に以下を載せる。先頭バイト `type` で識別する。

### 3.1 STREAM パケット（type = 0xAA）

| オフセット | フィールド | 型 | 説明 |
|---|---|---|---|
| 0 | type | uint8 | `0xAA`（ESP-NOW streaming） |
| 1 | seq | uint8 | シーケンス番号（ラップ） |
| 2 | num_frames | uint16 LE | フレーム数（=16） |
| 4 | predictor_L | int16 LE | ADPCM デコーダ状態 L |
| 6 | step_index_L | uint8 | ADPCM step index L |
| 7 | predictor_R | int16 LE | ADPCM デコーダ状態 R |
| 9 | step_index_R | uint8 | ADPCM step index R |
| 10 | data | uint8[num_frames] | ADPCM データ（1 byte = L nibble \| R nibble<<4） |
| 10+N | piggyback | optional | 前パケットの複製（§3.2） |

ヘッダサイズ = 10 bytes。piggyback なしの総長 = 10 + N（N=16 → 26 bytes）。

### 3.2 piggyback（単発ロス回復）

各パケットは**直前パケットの複製**を任意で末尾に持つ。受信側で seq 欠番が 1 個だけ かつ piggyback の `prev_seq` が一致する場合、欠落パケットを継ぎ目なく再構成する。

| オフセット | フィールド | 型 | 説明 |
|---|---|---|---|
| 10+N | prev_seq | uint8 | 前パケットの seq |
| 10+N+1 | prev_state | uint8[6] | 前パケットの L/R predictor+step_index |
| 10+N+7 | prev_data | uint8[N] | 前パケットの ADPCM データ |

piggyback ありの総長 = 17 + 2N（N=16 → 49 bytes）。欠番が 2 個以上の場合は有界の無音で埋める。

## 4. チャンネル（グループ）

| 項目 | 値 |
|---|---|
| 有効チャンネル | 1 / 6 / 11 |
| 設定 | `serial-config.md` `set_espnow_channel`（NVS `espnow/channel`）／本体ボタンでの巡回も可 |
| 既定 | 1 |

会場/イベントごとにチャンネルを割り当てて隔離する。送信機と全受信機が一致している必要がある。

## 5. 受信機の扱い

- `transport=espnow_stream` の receiver は ESP-NOW broadcast を受信し、ADPCM デコード → リングバッファ → I2S DAC → 触覚出力。
- レイテンシはリングバッファ上限超過分を破棄して累積させない（実装詳細はファーム側、移植元の低遅延化に準拠）。
- 既定ゲインは `set_gain`、物理ボリュームノブと併用。
- Wi-Fi STA には接続しない（純 ESP-NOW 運用、固定チャンネル）。設定は USB serial 経由。

## 6. UDP STREAM（0x30 系）との関係

`message-format.md` の UDP STREAM_BEGIN/DATA/END（0x30/0x31/0x32）は **Wi-Fi UDP transport** 上の音声ストリーミング。
本仕様は **ESP-NOW transport** 上の音声ストリーミングで、別経路・別パケット形式である。
音声フォーマット（16kHz / ADPCM）の意味は共通だが、フレーミング（ESP-NOW 250B + piggyback）は ESP-NOW 固有。

## 7. マルチソース（将来）

DEC-033 の「送信元多重化 + 独立ソース選択」（RSSI/最先着ロック + ヒステリシス + クロスフェード）は、複数 transmitter を分散配置するときの受信戦略。送信元識別（source-id / MAC）を packet に足す拡張は **DEC-033 実装フェーズ**で定義する（本仕様の単一ソース形式が基底）。

## 8. 関連文書

- `node-roles.md` — role/transport taxonomy
- `serial-config.md` — `set_espnow_channel` / `set_gain` / `set_input_level`
- `message-format.md` §0x30 — UDP 経路の streaming（別経路）
- `../docs/decision-log.md` DEC-033（無線方式選定）/ DEC-034（ツールチェーン）
