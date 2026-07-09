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

既存の ADPCM 経路（`P-haptic`、type=0xAA）に加え、DEC-042（Opus 採用確定）により Opus profile（`P-audio-LD`、type=0xAB、§3.3）を追加する。両者は**別パケット type**で共存し、同一チャンネル上でも type バイトで区別できる。プロファイル定義の詳細は `docs/instructions-opus-streaming-plan-202607040323.md` §2 を正とする。

| 項目 | P-haptic（既存、type=0xAA） | P-audio-LD（新設、type=0xAB） |
|---|---|---|
| サンプルレート | 16000 Hz（送信機・受信機で一致必須） | 48000 Hz（Opus デコード後 PCM。receiver は 16kHz へ直接デコードしてもよい、§3.3 参照） |
| チャンネル | 2（stereo） | 2（stereo） |
| コーデック | IMA-ADPCM 4:1（L=low nibble, R=high nibble の 1 byte/frame） | **Opus restricted low-delay（CELT-only）** |
| フレーム長 | 16 frames/packet（≒ 1 ms/packet） | **5 ms/frame**（1 パケット = 1 フレームが基本、§3.3） |
| ビットレート目安 | — | **64–96 kbps** |
| ロス対策 | piggyback（単発ロス回復、§3.2） | piggyback（単発ロス回復、§3.3 で Opus フレーム全体を複製）。inband FEC は low-delay モードでは使用不可（CELT-only は LBRR 非対応のため） |
| 無線プロファイル | 11b/g/n、6 Mbps、broadcast | 11b/g/n、6 Mbps、broadcast（P-haptic と共通） |

> `P-audio-Q`（10–20ms フレーム・inband FEC・jitter buffer 60–120ms、遅延許容の音楽リスニング用）は **Wi-Fi UDP transport 側**（`message-format.md` §0x30 format=2）で提供する。ESP-NOW は 250B MTU 制約が厳しく、`P-audio-Q` のような長めフレーム + FEC 併用は本仕様の対象外とする（§3.3 の MTU 計算参照）。

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

### 3.3 OPUS STREAM パケット（type = 0xAB, P-audio-LD / DEC-042）

Opus restricted low-delay プロファイル用。**1 パケット = 1 Opus フレーム**（5 ms 基本）。ADPCM と違いデコーダ状態フィールドは持たない（Opus フレームはパケット単位で自己完結し、欠落は PLC / piggyback で吸収する）。

| オフセット | フィールド | 型 | 説明 |
|---|---|---|---|
| 0 | type | uint8 | `0xAB`（ESP-NOW Opus streaming） |
| 1 | seq | uint8 | シーケンス番号（ラップ） |
| 2 | flags | uint8 | bit0: piggyback あり / bit1: restricted low-delay（=1 固定）/ bit2-7: reserved(0) |
| 3 | frame_ms | uint8 | フレーム長 ms（5 基本。10 は piggyback なしのみ、下記 MTU 計算） |
| 4 | frame_len | uint16 LE | Opus フレームのバイト長（1 以上。DTX 不使用） |
| 6 | frame_data | uint8[frame_len] | 1 Opus フレーム（`opus_encode` 出力そのまま。48 kHz stereo CBR） |

**piggyback（flags bit0=1 のとき、frame_data 直後）** — §3.2 と同じ単発ロス回復戦略を Opus フレームに適用:

| オフセット | フィールド | 型 | 説明 |
|---|---|---|---|
| 6+N | prev_seq | uint8 | 前パケットの seq |
| 7+N | prev_len | uint16 LE | 前フレームのバイト長 |
| 9+N | prev_data | uint8[prev_len] | 前パケットの Opus フレーム複製 |

**250B MTU 計算（CBR）**: 5ms@64k → frame 40B、総長 6+40+3+40 = **89B** ✓ / 5ms@96k → 60B、総長 **129B** ✓ / 10ms@96k → 120B、piggyback 込み **249B**（ギリギリのため **10ms は piggyback なし運用を推奨**）。

**受信側の欠落処理**: seq 欠番 1 個 かつ piggyback の `prev_seq` 一致 → 前フレームを復元してデコード順を維持。それ以外の欠番 → 欠けたフレーム数ぶん `opus_decode(NULL, 0, …)`（PLC）で埋める（上限 2 フレーム ≈ 10ms、それ以上の連続欠落はデコーダを `OPUS_RESET_STATE` して再同期）。

**16 kHz デコード**: 触覚のみの receiver（duo_v3 等）は同じ 0xAB ストリームを **fs=16000 のデコーダで直接デコード**してよい（libopus 標準機能。リサンプラ不要）。wire は常に 48 kHz stereo エンコード。

### 3.4 mode_id とモード別 body（AS-BUILT, 2026-07-08／mode 6・mode 7・mode 8 は 2026-07-09 追加）

`0xAA` パケットの内訳を **mode-aware ヘッダ**として一般化する（送信機 `MODE_DEFS`（`audio_source.cpp`）と受信機 `RX_MODE`（`espnow_stream.cpp`）が **codec/fs/ch まで一致**必須）。

共通ヘッダ（全 mode 共通）:

| オフセット | フィールド | 型 | 説明 |
|---|---|---|---|
| 0 | type | uint8 | `0xAA` |
| 1 | mode_id | uint8 | ストリームモード（下表） |
| 2 | seq | uint8 | シーケンス番号 |
| 3 | pb_count | uint8 | piggyback 数 |

mode_id テーブル:

| id | 名前 | codec / fs / ch | frame | pb | RX buffer | 実測 E2E 遅延 |
|---|---|---|---|---|---|---|
| 0 | **SOLID** | IMA-ADPCM 16k **stereo**（高信頼モード） | 4ms | ×1 | 480f=30ms | 36ms |
| 1 | **FAST** | Opus 8k mono (cplx2) | 5ms | ×3 | 192f=12ms | 38ms |
| 2 | **BALANCED** | Opus 8k mono (cplx5) | 5ms | ×3 | 288f=18ms | 38ms |
| 3 | **SMOOTH** | Opus 8k mono (cplx5) | 10ms | ×2 | 448f=28ms | 54ms |
| 4 | **STEREO** | Opus 8k **stereo** (cplx5) | 10ms | ×2 | 288f=18ms | 未実測 |
| 5 | **HIFI** | Opus 16k **stereo** (cplx5) | 10ms | ×2 | 448f=28ms | 未実測 |
| 6 | **LITE** | IMA-ADPCM 8k **mono** | 5ms(40f) | ×3 | 256f=16ms | 25ms |
| 7 | **TURBO** | IMA-ADPCM 8k **mono** | 5ms(40f) | ×3 | 64f=4ms | ~13ms(推定) |
| 8 | **FINE** | Opus 16k **mono** (cplx5) | 10ms | ×2 | 448f=28ms | 未実測 |

> **AS-BUILT (2026-07-09)**: pb は per-mode の piggyback 深さ（送受一致必須。受信は wire `pb_count` を最大 3 までパース）。RX buffer は `RX_MODE[mode].buf_frames`（モード切替で適用）。FAST/LITE は当初 128f=8ms だったが RF バースト(maxgap≈4)で under-run したため 256f=16ms に深化。**FAST はその後 192f=12ms に再調整**し、BALANCED（288f=18ms）より確実に低遅延な Opus モードとして差別化した。実測 E2E 遅延は tx アナログ入力→rx アナログ出力の包絡クロス相関（≈ frame蓄積 + RX buffer + codec分。codec分は ADPCM ~2-4ms / Opus ~15-17ms、差 ~13ms が LITE/TURBO の低遅延要因）。**mode 8（FINE）は Opus 16kHz mono**（16k stereo の HIFI と 8k mono の SMOOTH の中間 — フルバンドだがモノラル）。wire body は他の Opus mode（1-5）と同一構造（§3.3-style: opus_len + frame + piggyback）で、送受とも既存の Opus コードパスをそのまま再利用する（新規 codec パス追加なし）。

- mode 0（SOLID、旧称 RAW）の body は §3.1（ただし mode-aware ヘッダでは offset 1=mode_id, offset 2=seq, offset 3=pb_count に読み替え。§3.1 の offset 1=seq/offset 2=num_frames は mode-id 導入前の記述）。
- mode 1-5, 8（Opus）の body は §3.3 参照。
- mode 6（LITE）の body は下記。
- **mode 7（TURBO）は mode 6（LITE）と wire が完全に同一**（同じ codec/fs/ch/frame/pb、同じ §3.4 mode 6 body 定義をそのまま使う）。**唯一の違いは受信機のジッタバッファ深さ**（LITE ≒16ms 相当 vs TURBO=64f=4ms）— 最小レイテンシ優先・途切れ増を許容する設定。送信側の encode/pack ロジックは mode 6 と共有し、パケットの `mode_id` のみ 7 を積む。

#### mode 6（LITE = ADPCM 8k mono）body（mode 7 TURBO も同一 body を使用）

`RAW`（mode 0, ADPCM 16k stereo）の**サンプルレートを 8k・チャンネルをモノラルに落とした版**。encode CPU コストはゼロ（Opus 不使用）。FAST/BALANCED（Opus 8k mono, pb=1）と**同じ pb=1 保護**のもとで比較することで、Opus encode 負荷が FAST/BALANCED の濁り（振幅ワブル）の原因かどうかを切り分けるための実験モード（デバッグ専用ではなく正式な追加モード）。

| オフセット | フィールド | 型 | 説明 |
|---|---|---|---|
| 4 | num_frames | uint8 | `40`（8kHz で 5ms 分のモノラルサンプル数） |
| 5 | predictor_lo | uint8 | ADPCM デコーダ状態（int16 LE 下位バイト、本ブロック処理前の値） |
| 6 | predictor_hi | uint8 | ADPCM デコーダ状態（int16 LE 上位バイト） |
| 7 | step_index | uint8 | ADPCM step index |
| 8 | data | uint8[ceil(num_frames/2)] | ADPCM データ（1 byte = 2 サンプル。low nibble=サンプル N、high nibble=サンプル N+1）。40 フレームで 20 bytes |

ヘッダサイズ = 8 bytes（共通4 + num_frames1 + state3）。mono state は 3 bytes（int16 predictor + uint8 step）— stereo（mode 0）の 6 bytes の半分。

**piggyback（pb_count=1 のとき、data 直後）** — §3.2 と同じ単発ロス回復戦略をモノラル状態に適用。ここで **D = ceil(num_frames/2)**（= data フィールドのパック後バイト長。num_frames=40 なら D=20）。data は 2 サンプル/byte のニブルパックなので piggyback は num_frames ではなく **byte 長 D** ぶん進んで offset `8+D` = **28** から始まる（mode 0 は 1 byte/frame なので N と byte 長が一致していたが、mode 6 では別物）:

| オフセット | フィールド | 型 | 説明 |
|---|---|---|---|
| 8+D (=28) | prev_seq | uint8 | 前パケットの seq |
| 9+D (=29) | prev_predictor_lo | uint8 | 前パケットの predictor（int16 LE 下位） |
| 10+D (=30) | prev_predictor_hi | uint8 | 前パケットの predictor（int16 LE 上位） |
| 11+D (=31) | prev_step_index | uint8 | 前パケットの step index |
| 12+D (=32) | prev_data | uint8[D] | 前パケットの ADPCM データ |

N=40（D=20 bytes）のとき、piggyback ブロック = 1+1+1+1+20 = 24 bytes。総長（pb=1）= 4（共通ヘッダ）+ 1（num_frames）+ 3（state）+ 20（data）+ 24（piggyback）= **52 bytes**（`ESP_NOW_MAX_DATA_LEN`=250 に十分収まる）。

**送信経路**: 48kHz stereo capture → FIR → 16kHz stereo → モノラルへダウンミックス → 2:1 間引きで 8kHz mono（既存の 8k mono Opus 経路と同じ間引きを、Opus encoder でなく ADPCM mono encoder に供給する）。

**受信経路**: 3-byte mono state を parse → `adpcmDecodeBlockMono` で 40 mono サンプル @8kHz を復元 → 線形補間で 2 倍して 80 サンプル @16kHz → ステレオへ複製（L=R interleave、160 int16）→ `feedFramesWithFade` へ投入。

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
