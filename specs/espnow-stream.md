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
| 1 | mode_id + RELAYED | uint8 | **bit[7]=RELAYED / bit[6:0]=mode_id**（下表）。DEC-043 |
| 2 | seq | uint8 | シーケンス番号 |
| 3 | pb_count | uint8 | piggyback 数 |

> **RELAYED フラグ（byte[1] bit7, DEC-043）**: origin 送信機（音声ソース機）は **RELAYED=0 で送信しなければならない (MUST)**（送信機コードは無変更 — mode_id は 0–127 なので bit7 は自然に 0）。リピータは中継時に bit7 を 1 にセットする（§7.2）。**受信機は mode_id を検証する前に bit7 をマスクしなければならない (MUST)**（`mode = byte[1] & 0x7F`）。マスクを怠ると中継パケット（bit7 セット）を未知 mode と誤認して全破棄し、リピータ経由のカバレッジが無言で消える。

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

### 3.5 fleet-tune ビーコン（type = 0xAC, DEC-043 P5）

会場 60 台規模の全受信機へ**電波経由でランタイム調整値**を配る 4 バイト固定ビーコン。**runtime のみ・NVS 非保存**（再起動で mode 既定へ復帰 = 置き忘れ防止。relay-test と同思想）。

| オフセット | フィールド | 型 | 説明 |
|---|---|---|---|
| 0 | type | uint8 | `0xAC` |
| 1 | flags | uint8 | `[7]=RELAYED / [6:0]=version`（=1） |
| 2 | param_id | uint8 | 下表 |
| 3 | value | uint8 | param 依存 |

| param_id | 意味 | value | 適用先 |
|---|---|---|---|
| 1 | buffer_ms override | 0=mode 既定 / 4..60 | ジッタバッファ深さ |
| 2 | selection enable | 0/1 | 配信レートベース選択（§7.1.2）の有効/無効 |
| 3 | lock_timeout | ×10ms（5..50） | LOCK_TIMEOUT（§7.1） |
| 4 | resync_gap | 4..64 | RESYNC_GAP（§7.1.1） |

- **未知の param_id / version は無視しなければならない (MUST)**（前方互換 — 新 param 追加時に旧受信機が誤動作しない）。
- 受信機は**ロック中ソースからの 0xAC のみ適用しなければならない (MUST)**。RELAYED=1（リピータ中継）でも、そのリピータがロック中ソースなら適用対象。
- **べき等 (MUST)**: 送信機は変更時 ×3 連送 + 5s 周期再送する（後から電源 ON した受信機も追従）。受信機は**値が現在値と異なる時のみ適用**しなければならない（5s 再送で reprime グリッチを出さないため）。
- リピータは 0xAA と同じ bit7 ルールで 0xAC も中継する（§7.2）。RELAYED=1 は中継しない。

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

#### 7.1.1 seq 再同期（必須, DEC-043）

- **ロック中ソースからの forward seq gap が `RESYNC_GAP`（=20）以上の場合、受信機はこれをロスとして計上してはならず・補間/無音挿入してはならず (MUST NOT)、seq を再同期して短フェードで再開しなければならない (MUST)**。
- 根拠: リピータが上流 origin を切り替える／origin 送信機が再起動すると、**送信元 MAC は同一のまま seq が不連続**になる。これをロスとして扱うと最大 127 パケットのロス誤計上 + PLC 連発が起きる。実測 RF バーストの最大 gap は 4–18・OPUS_RECOVER_CAP=12 なので、20 以上は「別ストリームの接合」とみなせる。

#### 7.1.2 配信レートベース切替（DEC-043・値は実装調整可）

RSSI が取れない実装向けに、§7.1 の「最先着ロック + 途絶切替」を **per-Source 受信カウント窓**で補強する（RSSI/promiscuous 不使用）。以下の値は目安で、実装で調整してよい:

- 評価窓 `SEL_WINDOW_MS`=4000 / 未回復ロスゲート ≥5%（ロック中の窓内 未回復ロス = Δpackets_lost − Δpiggyback_recovered）
- 挑戦者優位: 挑戦者の受信カウント×8 ≥ ロックの受信カウント×9（≥12.5%）かつ 挑戦者カウント ≥ 定格の 1/2（定格 = mode の pkt/s × 窓）
- 挑戦者は **同一 mode_id** のソースに限る / 切替時に旧ソースを blacklist 10s / 最小切替間隔 10s
- この規範は §7.1「発振防止」に紐付く（瞬間的なロス/カウント逆転で切り替えない）。

#### 7.1.3 リピータテストモード（設営確認用・MAY）

- 受信機は「**RELAYED=1 のパケットのみをソース候補とする**」揮発的なテストモードを持ってよい (MAY)。設営時に「リピータ経由でロックできるか」を受信機 1 台で確認するための機能。
- トグルは設定チャネル（serial `set_espnow_relay_test`）経由。**再起動で必ず解除される (MUST)**（NVS 保存しない → テスト置き忘れの構造的防止）。

### 7.2 リピータ

アナログ分配を増やさずにカバレッジを広げるため、**リピータ機**（音声取込を持たない中継専用 transmitter）を配置できる。

- **中継 = byte[1] bit7 を 1 にセットする点を除き verbatim** (MUST)。それ以外のバイト（type / mode_id 下位 7bit / seq / pb_count / body / piggyback）は**一切書き換えてはならない (MUST NOT)** — 受信機の piggyback は `prev_seq` の絶対値マッチで復元するため、seq を触ると回復が壊れる。再送時の ESP-NOW 送信元 MAC は**リピータ自身の MAC**になる → 受信機からは別の送信元として見える。
- **ループ防止（構造的）**: **RELAYED=1（bit7 セット）のパケットは中継してはならない (MUST NOT)**。「中継されたパケットは二度と中継されない」＝任意台数のリピータを並べても中継は**最大 1 ホップ**（origin → repeater → receiver）に構造的に有界化される。台数無制限・現地設定ゼロでループ不可能。
- **origin 自動追従（SHOULD, DEC-043）**: リピータは **RELAYED=0 の先着 MAC にロック**し、その MAC のパケットのみ中継する。ロック origin が `R_TIMEOUT`（=250ms）沈黙したらロックを解放し、次に届いた RELAYED=0 の origin に再ロックする。これによりソース 2 機のうち 1 機が死んでも、リピータは自動で生存 origin に追従する（TX2 が真のホットスタンバイになる）。
- **`R_TIMEOUT` は受信機のロック喪失タイムアウト（`LOCK_TIMEOUT`, §7.1）より長くなければならない (MUST)**。重複圏の受信機がリピータの再ロックより先に直波 origin へ移り、seq 不連続（§7.1.1 resync）を確実に発火させるため（現行 LOCK_TIMEOUT=150ms < R_TIMEOUT=250ms）。
- **手動ピン（NVS `relay_src`）**: `set_relay_source`（`serial-config.md`）で source MAC を設定した場合は**厳格な手動ピン**として振る舞い、auto 追従は無効になる。**ピン先の origin が死ねば中継は停止する**（他 origin に移らない）。空 MAC を設定すると auto 追従に戻る。
- **混在艦隊ルール (MUST NOT)**: bit7 導入前の旧リピータファームと auto-relay 世代（本 DEC-043 世代）を**併用してはならない**。旧機は中継時に bit7 を立てないため、その出力が新リピータからは「偽 origin（RELAYED=0）」に見え、2 ホップ連鎖して 1 ホップ保証が破れる。
- **展開順序 (MUST)**: **受信機（bit7 マスク対応, §3.4）を先に全台 flash してから、リピータを配備する**。旧受信機は bit7 セットのパケットを mode 範囲チェックで黙って捨てるため、逆順だとリピータ経由のカバレッジが無言で消える。
- リピータは音声取込を行わない（I2S 不要、RX→TX 中継のみ）。
- **配置の注記（レイテンシ）**: 受信機はソースとリピータを区別せず選ぶため、**直波（origin）とリピータ波の両方が届く重複域では、リピータ波を選ぶと中継 1 ホップぶん遅い音声にロックしうる**。リピータは原則 **直波が届かない死角のカバー**に充て、重複域では中継ホップぶん（~1–2ms）のレイテンシ増を許容する前提で配置する。

> 想定構成（DEC-033 / DEC-043）: 音声ソース機 ×2（同じ aux を分配・全アクティブ）+ リピータ機（XIAO ESP32-C6 等）×2 前後を同一固定チャンネルで運用。ソース 2 機のうち 1 機は auto origin-follow によりホットスタンバイとして機能する。

### 7.3 LONGRANGE モード（送信機トグルで完結, DEC-043 P5）

不感地帯がリピータ配置でも埋まらない遠距離向けに、**送信機側トグルだけ**で LR（802.11 Long Range）へ切り替える。

- 送信機は RANGE=LONG 時、protocol mask に `WIFI_PROTOCOL_LR` を追加し espnow rate を `WIFI_PHY_RATE_LORA_500K` にする。**パケット諸元は SMOOTH（mode_id 3）の wire を借りた「LR プロファイル」に内部固定**する: **Opus 8k mono 10ms・bitrate 24k 初期値（現地で 24/32/48k を送信機 TUNE から可変）・pb1**（Opus は self-describing・pb は wire の `pb_count` で伝わる → **受信機・リピータの mode 対応変更ゼロ**。bitrate 変更も受信機影響なし）。実体は「BALANCED 相当の Opus 8k mono を 10ms フレーム化」で、**送信機 UI は「LR」と表示**する（id3 を借りるだけで音質設定は別物のため SMOOTH と混同させない）。
- **受信機・リピータは protocol mask を常時 `bgn+LR` にする (SHOULD)**（LR フレームも復調可能に。bgn 受信は不変）。→ LONGRANGE 追加は**送信機の変更だけ**で受け止まる（受信機の事前 1 回 flash に mask を同梱する）。
- **合計 airtime duty で運用上限を決める（台数でない）**: 6M=1 ソース ~3.9% → 4 ソース可 / LR500K LR プロファイル=1 ソース ~17%（24k 既定）〜~20%（32k, 67B/87B payload）→ **2 ソース（~34-41%）が実用上限**。LR が要る遠距離ほど隠れ端末で CCA が効かず衝突が duty 以上に増える。**LR で 2 ソース冗長が成立する唯一の構成**である理由は 4 点セット: ①10ms フレーム化でヘッダ税（~40B/pkt）を半減（100pkt/s 化が最大のレバー）②Opus は送信側だけで bitrate を絞れる（ADPCM は固定で不可）③pb1 で冗長 airtime を削る（PLC が下支え）④深い RX バッファ（id3=28ms）が LR の長 airtime + CCA ジッタに耐える。RANGE=LONG は LR プロファイルに内部固定し、LONG 中は他モードを選ばせない。
- **RANGE 判断フロー**: ① 6M 1 台で全域カバー → 非 LR・冗長 ≤4 ソース → ② 不感地帯 → まず 6M のままリピータを不感地帯側へ → ③ それでも届かない → LR×2 ソース。**多段直列中継（R→R）は bit7 ループ防止により構造的に不可（1 hop まで）**。距離延伸は「LR 化 + 1 hop リピータ」が上限。

### 7.4 fleet-tune（§3.5 の運用）

- 受信機は §3.5 の 0xAC を**ロック中ソースからのみ**適用（runtime・NVS 非保存）。リピータは 0xAA と同じ bit7 ルールで 0xAC を中継（RELAYED=1 は中継しない）。
- **新 param_id の追加のみ受信機 reflash が要る**。既存 param の新値・LONGRANGE 追加・諸元調整はすべて**送信機側の変更だけ**で受け止まる（受信機の「事前 1 回 flash」の設計目標）。

## 8. 関連文書

- `node-roles.md` — role/transport taxonomy
- `serial-config.md` — `set_espnow_channel` / `set_gain` / `set_input_level` / `set_relay_source`
- `message-format.md` §0x30 — UDP 経路の streaming（別経路）
- `../docs/decision-log.md` DEC-033（無線方式選定 + 送信元多重化 + 独立ソース選択）/ DEC-034（ツールチェーン）/ DEC-043（RELAYED bit7 + auto-relay + seq-resync + 配信レートベース選択）
