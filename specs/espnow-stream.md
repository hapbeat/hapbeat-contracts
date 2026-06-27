# [INTERNAL] ESP-NOW streaming transport 仕様書

> **[INTERNAL] 本文書は ESP-NOW transport 上のパケット形式・受信戦略を定義する内部仕様（Layer 3 相当）。SDK からは直接参照されない。**

## 1. 概要

`espnow_stream` transport は、**会場同報**ユースケース（PA のライブ音声を ESP-NOW で同報し、会場の全観客が装着する Hapbeat が同時に音声ベースの触覚を体験する。LE Audio Auracast 的）のための通信モード。

```
[PA / mixer] --analog line-in--> [transmitter] --ESP-NOW broadcast--> [receiver ×N (観客)]
                                   role=transmitter                      role=receiver, transport=espnow_stream
```

- **broadcast（peer `FF:FF:FF:FF:FF:FF`）**による真の one-to-many。ペアリング不要、ACK なし、台数は RF のみが上限。
- **「グループ」= Wi-Fi チャンネル**（1/6/11）。送信機と受信機を同一チャンネルに合わせる。別チャンネルなら混信しない。
- 低遅延優先（LR モードは使わず 11b/g/n）。詳細な無線方式選定・多重化戦略は **DEC-033** を参照。
- **送信元多重化**: カバレッジ確保のため複数 transmitter（音声ソース機 + リピータ機）を分散配置できる。受信機は送信元 MAC で 1 台を選択する（§7）。

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
- 複数 transmitter（ソース機 / リピータ機）を同時受信しうる場合、**送信元 MAC で 1 台にロックして再生**する（§7）。**複数ソースをミキシングしない**。

## 6. UDP STREAM（0x30 系）との関係

`message-format.md` の UDP STREAM_BEGIN/DATA/END（0x30/0x31/0x32）は **Wi-Fi UDP transport** 上の音声ストリーミング。
本仕様は **ESP-NOW transport** 上の音声ストリーミングで、別経路・別パケット形式である。
音声フォーマット（16kHz / ADPCM）の意味は共通だが、フレーミング（ESP-NOW 250B + piggyback）は ESP-NOW 固有。

## 7. 送信元多重化（マルチソース選択 + リピータ）

DEC-033 の「送信元多重化 + 独立ソース選択」を本仕様の確定挙動とする。複数 transmitter（音声ソース機 + リピータ機）を分散配置してカバレッジを確保し、受信機は **送信元 MAC で 1 台を選んで**再生する。**パケット形式（§3）は変更しない** — 送信元の識別は ESP-NOW 受信コールバックが渡す送信元 MAC で行う（source-id フィールドは持たない）。

### 7.1 受信側ソース選択

- 受信機は同時に複数 MAC の `0xAA` を受信しうるが、**常に 1 つの MAC にロック**してそのストリームのみ再生する。非ロック MAC は RSSI / 生存のみ追跡し、**デコード・再生しない（ミキシング禁止 = 二重再生を防ぐ）**。
- **選択ロジック**:
  - 初期ロック: 最初に受信した、または最強 RSSI の MAC。
  - **ヒステリシス**: 別 MAC が現ロックより RSSI が一定閾値以上強い状態が最小保持時間継続したときのみ切替（頻繁な往復を防ぐ。初期値の目安は実装で調整、例: 6–10 dB / 300–500 ms）。
  - **ロック喪失**: ロック MAC のパケットが一定時間（例 100–200 ms）途絶したら、次に強い生存 MAC へ切替。
  - **ハンドオフ**: 切替時に数 ms の短クロスフェードでプチノイズを隠す。
- **発振防止（規範）**: ロック喪失タイムアウトは通常のパケット間隔 + ジッタより十分大きく取り（瞬間的な欠落で切り替えない）、RSSI 切替の最小保持時間は複数パケット分を確保する（瞬間的な RSSI 逆転で切り替えない）。両条件を欠くと、弱い/途絶気味の MAC 間で往復切替（発振）が起きうる。
- RSSI が取れない実装（IDF バージョン依存）は「最先着ロック + 途絶切替」で代替してよい。
- 「transmitter」は**音声ソース機とリピータ機の両方**を指す。受信機は両者を区別しない（どちらも送信元 MAC でロック対象）。

### 7.2 リピータ

アナログ分配を増やさずにカバレッジを広げるため、**リピータ機**（音声取込を持たない中継専用 transmitter）を配置できる。

- リピータは**設定された 1 つの source MAC** の `0xAA` パケットを受信し、**verbatim 再ブロードキャスト**する（再送時の ESP-NOW 送信元 MAC は**リピータ自身の MAC**になる → 受信機からは別の送信元として見える）。
- **ループ防止**: リピータは設定 source MAC のパケットのみ中継し、**他のリピータ・他のソースは中継しない**。これにより中継は **最大 1 ホップ**（source → repeater → receiver）に有界化される。
- リピータは音声取込を行わない（I2S 不要、RX→TX 中継のみ）。
- 各リピータは **1 ソースに割り当てる**（ソース 2 機なら各ソースにリピータを割り当てる構成）。
- 中継元 source MAC の設定は `serial-config.md` `set_relay_source`（NVS `espnow/relay_src`）。一発勝負イベントでは flash-time 定数でも可。**設定漏れ（`relay_src` 空）だとリピータにならず独立した通常 transmitter として振る舞う**（受信機から見て余分なソースが増える）ので注意。
- **source 途絶時**: リピータは verbatim 中継なので、中継元 source が無音/途絶すると**リピータも無音になる**（中継するものが無い）。そのリピータにロックしていた受信機は §7.1 のロック喪失タイムアウトで他の生存 transmitter へ切替する。
- **配置の注記（重要・レイテンシ）**: 受信機はソースとリピータを区別せず最強 RSSI を選ぶため、**直波（source）とリピータ波の両方が届く重複域では、リピータ波が強いと中継 1 ホップぶん遅い音声にロックし続けうる**。リピータは原則 **直波が届かない死角のカバー**に充て、重複域では中継ホップぶんのレイテンシ増を許容する前提で配置する（直波の厳密優先には packet に hop/鮮度フィールドが要るが、本仕様は wire 無変更を優先し配置運用で対処する）。

> 想定構成（DEC-033）: 音声ソース機 1〜2 + リピータ機 2 前後を同一固定チャンネルで運用。

## 8. 関連文書

- `node-roles.md` — role/transport taxonomy
- `serial-config.md` — `set_espnow_channel` / `set_gain` / `set_input_level` / `set_relay_source`
- `message-format.md` §0x30 — UDP 経路の streaming（別経路）
- `../docs/decision-log.md` DEC-033（無線方式選定 + 送信元多重化 + 独立ソース選択）/ DEC-034（ツールチェーン）
