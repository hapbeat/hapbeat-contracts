# Audio DSP Config — DuoWL v4 receiver (EQ / HP volume / A-V delay)

DuoWL v4 の ESP-NOW 受信機（`ESPNOW_HP48` build, mode 9 SOLID48）向けの音声/触覚
DSP 設定プロトコル。設定は **Studio → 受信機を USB Web Serial → NVS 永続**（per-device
設定。EQ 係数は 0xAC fleet には大き過ぎるため fleet 配信しない）。

参照設計: hapbeat-bt-workspace の ADAU1701 パイプライン（source → split → 音声EQ+delay /
触覚EQ+comp → 各DAC）。本仕様は ESP32-S3 + 2×AIC3204 に落とし込んだもの。

---

## 1. ボリューム構造（分離）

DuoWL v4 は 2×AIC3204（U1 触覚 / U2 HP）+ TPA6130A2（HP アンプ）。**従来はホイール(ADC)が
両 codec の DAC デジタル音量を同時制御**していた。本仕様で分離する:

- **ホイール(ADC) → 触覚(U1) DAC デジタル音量のみ**。
- **HP(U2) DAC デジタル音量は 0dB 固定**（max にピン留め）。HP 音量は **TPA6130A2 アナログ音量**のみで制御。
- **ボタン**: 再生モードで **右上(SW4) = HP vol+ / 右下(SW5) = HP vol−**（タップ1step +
  長押し連続。触覚はホイール据置）。触覚 EQ プリセットトグルは**左上(SW1)** に割当（§2.1、
  v3/v4 共通で左上に統一 — 2026-07-21）。
  - CONFIG モード切替は **左中(SW2)の単独長押し ~300ms**（2026-07-21 改定: 旧・二点押し
    combo（SW1+SW3 長押し ~300ms）から単一ボタンに変更。単一ボタン化した当初は誤爆防止のため
    一旦 ~1000ms に引き上げたが、同日中にユーザーが応答性を優先して ~300ms に戻した — combo の
    300ms hold-to-fire を単一ボタンのまま維持する形。CONFIG モード中の volmax タップは 300ms
    未満で release すればそのままタップとして通り、モード反転が発火した hold の release のみ
    下記の 1 サイクル suppress で二重動作を防ぐため誤爆は生じない）。左中は CONFIG モード中の
    タップ = volume-max cycle（§3.5 param 5）と兼務し、モード反転が発火した hold の release のみ
    1サイクル suppress（誤爆防止 — 発火に至らない短いタップはそのまま volmax として通る）。
    左上(SW1)の EQ プリセットトグル・relock は combo から切り離されたため、suppress は不要
    になった。実装は device-firmware `espnow_ui.cpp` の `EBTN_CFG_TOGGLE`
    （`EBTN_VOLMAX` と同一インデックス）/ `s_cfg_toggle_swallow` を参照。
- HP 音量 API: `duoV4SetHeadphoneVolume(hp_db)`（−59..+4 dB、NVS `duo_audio`/`hp_db`）既存を流用。
- **本体ボタン/OLED は 16 段の STEP に量子化**（2026-07-21 追加）: raw dB は基準が無いと
  意味が伝わらないため、SW4/SW5 と OLED 表示は **0=mute, 1..15 = dB(s)=4s−56（−52..+4dB,
  4dB/step）**の 16 段スケールで操作・表示する。**serial/wire（`set_headphone_volume`,
  `get_info.audio.hp_db`）と Studio の UI は従来通り dB のまま**（本量子化はデバイス側の
  ボタン/OLED UX のみに閉じたレイヤーで、プロトコル変更ではない）。Studio がグリッド外の
  dB を設定した場合、デバイス側は**最も近い step** を表示し、次のボタン操作はその最近傍
  step を起点に ±1 step 動く。mute（step 0）は TPA6130A2 の Volume/Mute レジスタに
  MUTE_L/MUTE_R ビット（D7/D6, SLOS619 §8.4.9）が存在するが、device-firmware 側に
  既存のミュート専用ヘルパーが無い（未検証の新規レジスタ書き込みを避ける方針）ため、
  既存の −59dB フロア（`duoV4SetHeadphoneVolume()` のクランプ下限）を流用して近似する
  （真のデジタルミュートではない）。実装は device-firmware `duowl_v4_audio.h/.cpp` の
  `duoV4HpVolGetStep()` / `duoV4HpVolSetStep()`（`DUO_HP_VOL_STEPS`）、ボタンは
  `espnow_ui.cpp` の `hpVolButton()`、OLED は `display_manager.cpp` の
  `drawEspnowDefault()` DUOWL_V4 分岐を参照。

## 2. EQ（AIC3204 in-codec biquad）

各 DAC 経路（U1 触覚 16k / U2 HP 48k）に **3 biquad/ch**（PRB_P1、既定 passthrough）。
係数は **coefficient RAM に書込み**、再生中の差替えは **Adaptive Filtering モード**
（Page44 Reg1 D2=1 で double-buffer → 非アクティブ側に書込み → D0=1 で sample 境界 flip）で
グリッチ無し。

### 係数変換（Studio が RBJ cookbook で計算 → 生 24-bit int を送信）

AIC3204 伝達関数（TI SLAA557 §2.4.2.2 / SLAA447）:
```
        N0 + 2·N1·z⁻¹ + N2·z⁻²
H(z) = ────────────────────────────
        1 − 2·D1·z⁻¹ − D2·z⁻²          （24-bit 2の補数 Q1.23、scale 2^23）
```
RBJ cookbook float `(b0,b1,b2,a0,a1,a2)`（分母 `a0 + a1z⁻¹ + a2z⁻²`）→ AIC3204:
```
N0 = b0/a0            N1 = b1/(2·a0)        N2 = b2/a0
D1 = −a1/(2·a0)       D2 = −a2/a0
各々 ×2^23 して round、[−8388608, 8388607] に clamp（clamp 発生=警告）
```
- **中間係数の ÷2** により安定 2 次セクションは常に [−1,1) に収まる。検証済み worked example =
  **100Hz 2次 Butterworth LPF @16kHz → `{N0,N1,N2,D1,D2} = {3146, 3146, 3146, 8155730, −7935438}`**
  （Python 計算・Studio `aic3204Eq.ts` と firmware 既定が bit-for-bit 一致）。LPF は b1=2·b0 なので
  **N0=N1=N2 になる**点に注意（この不変条件を満たさない係数は変換ミス）。
- **注意**: 分子 N0/N2 は ÷2 されないため **passband gain > 0dB（bass boost 等）で 1.0 超過**しうる。
  その場合は Studio 側で **セクション gain を下げて pre-scale**（不足分は DAC デジタル音量 or
  別バンドで makeup）、または clamp して警告。LPF/HPF/notch（≤0dB）は常に安全。
- フィルタ種別（RBJ）: `off | lpf | hpf | peaking | lowshelf | highshelf | notch`。

### 既定 EQ
- **触覚**: band0 = **100Hz 2次 Butterworth LPF** を boot 時に適用（BT 製品と同一。モーターを
  低域に制限し HF buzz を抑制）。band1/2 = off。
- **音声(HP)**: 全 band = off（flat）。

### serial コマンド
```
{"cmd":"set_eq_band","codec":"haptic"|"hp","band":0..2,
 "ftype":"off|lpf|hpf|peaking|lowshelf|highshelf|notch",
 "coeffs":[N0,N1,N2,D1,D2]}          // 生 24-bit 符号付き int（host 計算済み）
```
- firmware は coeffs を AIC3204 coefficient RAM に書込み（adaptive buffer swap）。ftype は表示/記録用。
- NVS 永続（codec×band×5係数 + ftype）。boot 時に復元。未設定の触覚 band0 は既定 LPF。
- `get_info.eq`: `{haptic:[{ftype,coeffs}×3], hp:[...]}` を報告。

### 2.1 v3 系列（codec 無し受信機）— ソフトウェア EQ

NECKLACE_V3 / BAND_V2 / BAND_V3 / BAND_V4（`_mqtt` / `_stream_espnow` 派生含む）は
DSP 内蔵 codec を持たない裸の I2S DAC（PCM5100 相当）を駆動するため、DuoWL v4 と
同一の EQ を **ESP32-S3 側ソフトウェア**（`sw_eq.h/.cpp`）で実装する。

- **wire は DuoWL v4 と完全に同一**: `{"cmd":"set_eq_band","codec":"haptic","band":0..2,
  "ftype":"off|lpf|hpf|peaking|lowshelf|highshelf|notch","coeffs":[N0,N1,N2,D1,D2],
  "persist":true}`。係数の意味・Q1.23 scale・RBJ→AIC3204 変換式（本節冒頭）も同一 —
  Studio の EQ デザイナー/グラフ/プリセットはそのまま動作する（DSP バックエンドが
  in-codec biquad RAM ↔ ソフトウェア biquad に変わるだけ）。`codec:"hp"` はこれらの
  機種に HP codec が無いため `{"status":"error","message":"unsupported on this board"}`。
- **適用段**: 触覚ミキサーの最終加算段（`audio_player.cpp` の `audioPlayerUpdate()`、
  マスターゲイン適用の直前・16 kHz）で、既存の int32 mix accumulator に対して
  in-place で direct-form-II-transposed biquad を最大3バンド縦続適用。**追加バッファ
  遅延ゼロ**（既存のミックスブロックをそのまま処理するだけ、リングやレイテンシは
  増えない — group delay はフィルタ自体の特性のみ、DuoWL v4 の in-codec EQ と同じ）。
  全 transport（ESP-NOW ストリーム / Wi-Fi UDP ストリーム / ローカル clip 再生）が
  同じ `audioPlayerUpdate()` を通るため、等しく適用される。
- 未設定バンドは **全バンド off**（unity passthrough）— v3 系列の既存フリート挙動を
  変えないため、DuoWL v4 のような band0=100Hz LPF 既定は**適用しない**。unity
  passthrough のバンドは biquad 演算自体をスキップする（未設定時のコストはゼロ）。
- NVS 永続（band×5係数 + ftype、namespace `sw_eq`）。boot 時に復元。
- `get_info.eq`: `{haptic:[{ftype,coeffs}×3]}` に加え `"eq_engine":"sw"` を報告する
  （DuoWL v4 は引き続き 6-band in-codec EQ を `eq_engine` フィールド無しで報告 — 変更なし）。
- **本体ボタンプリセット（espnow 受信機 v3/v4 共通）**: 再生モードで**左上ボタン（タップ）**
  により触覚 EQ band0 を **NONE ↔ LPF 200 Hz (Q=0.7071)** でトグルする（判定は係数の厳密一致。
  カスタム設計や v4 の boot 既定 100Hz LPF が入っている場合、初回押下で LPF200 に置換）。
  NVS 永続・`get_info.eq` に反映（Studio の実機読み出しが追従）。LPF200 の係数（Q1.23,
  AIC3204 規約）= `{12250, 12250, 12250, 7923179, −7506750}`（N0=N1=N2・DC gain=1 検証済み）。
  **2026-07-21: 右上/右下は元々 v4 の HP 音量専用（§1）のため、EQ トグルは左上に統一**
  （右上に一時的にタップ機能を割り込ませていたのは設計ミスで撤回・右上/右下は §1 の HP vol+/−
  のみに戻した）。
  - **v3（左上 = SW2/btn_1）**: タップでトグル（バックエンド = ソフト EQ。boot 既定 NONE）。
    CONFIG モード切替は別ボタン（左中/btn_2、§1）に分離済みのため、この左上ボタンは combo
    ではなくなっており release 誤爆の suppress は不要（2026-07-21 改定）。
  - **v4（左上 = SW1、CONFIG 時は force-relock も兼務）**: PLAY 中のタップで
    EQ トグル、CONFIG 中は既存の relock（従来どおり）。バックエンド = in-codec AIC3204 EQ。
    こちらも CONFIG モード切替は別ボタン（左中/SW2、§1）に分離済みのため combo ではなく、
    suppress は不要（2026-07-21 改定）。
  Studio 側の v3 SW EQ の**書込み時ドラフト既定**も band0 = LPF 200 Hz/Q0.707 とする
  （firmware の boot 既定は NONE のまま — 適用ボタンを押すまでデバイスは変わらない）。
  - **Wi-Fi（非 ESP-NOW）ビルド**: 同機能を ui-config ボタンアクション
    `eq_preset_toggle`（v3/v4 共通）として任意の物理ボタンに割当可能（2026-07-22）。
    espnow 受信機の固定ジェスチャ（左上/SW1）とは独立した経路で、実装は
    device-firmware `button_handler.cpp` の `actionEqPresetToggle`（backend は
    espnow 側と同じ `duoV4HapticEqToggleLpf200` / `swEqTogglePresetLpf200`）。
    同様に §1 の HP vol+/− も `hp_vol_up` / `hp_vol_down`（v4 のみ、16 段 step ±1）
    として任意ボタンに割当可能。

## 3. A-V（音声-触覚間）delay

codec に delay ブロック無し → **firmware のリング target オフセット**で実現
（`audio_stream.cpp` の per-ring `*_ll_target`）。**双方向**: 正で音声(HP)を触覚に対して遅延
（遅い触覚モーターに音声を合わせる = ADAU の設計意図）、負で触覚を音声に対して遅延（逆方向の
補正が要る場合向け）。

- 範囲 **符号付き -100..+100 ms**。
  - `ms > 0`: **HP ring** に delay 分を加算（frames = ms×48、48kHz）。HP ring headroom 内の
    ~138ms 相当（HP_CAP_FRAMES）でクランプ。48kHz HP ring の無い build（DUOWL_V4_DUAL_CODEC +
    HAPBEAT_OPUS_DECODE 以外）では no-op（値は保存/報告されるが効果無し）。
  - `ms < 0`: **触覚 ring**（`s_ring`、全 build 共通）に `-ms` 分を加算（frames = -ms×16、
    16kHz）。触覚 ring headroom 内の ~208ms 相当（RING_CAP_FRAMES、HP 側と同じ ring 容量比率）
    でクランプ。全 build で有効（触覚 ring は DUOWL_V4_DUAL_CODEC 限定ではないため）。
  - どちらの方向も `set_stream_buffer`（§4.20-pre）が設定した base 深度に加算される
    （base + delay を都度再計算、設定順序に依存しない）。
- serial: `{"cmd":"set_av_delay","ms":-100..100,"persist":true}`。`persist`（bool, 既定
  true）: NVS 保存 + 起動時再適用。`false` = 一時適用のみ（Studio ライブドラッグ用）——
  firmware 側のデバウンス watchdog が ~1.5s 後に `persist:true` 相当を自動発火するため、
  ドラッグ後に明示コミットが届かなくても最終的に NVS へ反映される。
- `get_info` の **`audio` object**（DuoWL v4 のみ）: `av_delay_ms`（符号付き）と
  `stream_buffer_ms`（`set_stream_buffer` の現在値）を報告。

## 3.5 codec DSP フル機能（AIC3204 の全処理ブロック, 2026-07）

AIC3204 は「固定 Processing Block(PRB) を選び、その係数を書く」方式。**生の PRB 番号は出さず、
検証済みの DSP プロファイル**として公開する（Filter-A stereo 固定＝DOSR/AOSR 変更不要、
Resource Class 予算も十分。レジスタ詳細は workspace `dev-notes/device-firmware/aic3204-full-dsp-registers.md`）。

| profile | PRB | biquad | 1次IIR | DRC | 3D | Beep |
|---|---|---|---|---|---|---|
| `standard`（既定） | P1 | 3 | – | – | – | – |
| `eq6` | P3 | 6 | ○ | – | – | – |
| `eq6_drc` | P2 | 6 | ○ | ○ | – | – |
| `full` | P25 | 5 | ○ | ○ | ○ | ○ |

> ⚠ `full`（P25）の 5 band は **物理 biquad B..F**（A は 3D 差分パス専用、メイン音声経路には無い —
> SLAA557 Figure 2-36 で確認済み）。firmware は論理 band0..4 を物理 biquad B..F へ内部リマップして
> コミットする（物理 biquad A には常時 unity passthrough を書く）。`band` の wire 番号・NVS・
> `get_info` は常に論理 band のままで、このリマップはファームウェア内部にのみ存在する
> （`standard`/`eq6`/`eq6_drc` は元々 biquad A..F がメイン経路にあるため対象外）。

serial コマンド（全て DuoWL v4 receiver のみ・`persist` は §4c 共通仕様）:

- `{"cmd":"set_dsp_profile","codec":"haptic"|"hp","profile":"standard"|"eq6"|"eq6_drc"|"full","persist":true}`
  → 応答に `bands` / `has_iir` / `has_drc` / `has_3d` / `has_beep`。切替時は DAC を mute→power-down
  →PRB 書込み→power-up（power-status ポーリング）→**全 EQ/IIR/3D を再コミット**する。
- `{"cmd":"set_eq_band","codec":…,"band":0..5,…}` — **band が 0..2 から 0..5（A..F）に拡張**。
  プロファイルの band 数を超えるバンドも保存・コミットされる（上位プロファイルに切替えると有効化）。
- `{"cmd":"set_eq_iir","codec":…,"coeffs":[N0,N1,D1],"persist":true}` — 1次IIR（3係数、N2/D2 無し）。
- `{"cmd":"set_drc","codec":…,"enable"|"enable_l"|"enable_r":bool,"threshold_db":-3..-24(3dB刻み),
  "hysteresis_db":0..3,"hold":0..15,"attack":0..15,"decay":0..15,"persist":true}` → `{"applied":bool}`
  - **`hold`/`attack`/`decay` は生のハードウェアコード（dB/ms ではない）**。
    attack dB/sample = `4.0/2^code`、decay = `1.5625e-2/2^code`、hold = code0 で無効・以降 `32·2^(code-1)` DAC word clock。
    ※ SLAA557 の散文の推奨 dB/sample 値は同文書の bit-field 表と 10× 食い違うため、**表側を正**とする。
  - `get_info.drc.{haptic,hp}` に現在値 + `compressing_l`/`compressing_r`（閾値超過ライブフラグ）。
    連続的なゲインリダクション量の読み出しはハードに存在しない。
- `{"cmd":"set_beep","codec":…,"freq_hz":…,"volume_db":0..-63,"length_ms":…,"enable":true}`
  — ワンショットのテストトーン（profile `full` のみ）。`enable:false` で途中停止。永続化しない。
- `{"cmd":"set_3d","codec":…,"depth":0.0..1.0,"persist":true}` → `{"applied":bool}`（profile `full` のみ）。
  ※ datasheet に「エフェクト無し」を表す値の定義が無いため、**使わない時は `full` を選ばない**運用。
- `{"cmd":"set_agc","enable":bool,"target_level_db":…,"max_gain_db":…,"attack":0..255,"decay":0..255,
  "noise_threshold_db":…,"hysteresis_db":…,"persist":true}` — **ライン入力（HP codec ADC）専用のため `codec` フィールドは無い**。
  `get_info.agc` に現在値 + `applied_gain_l_db`/`applied_gain_r_db`（適用ゲイン読み出し）。
  ※ noise threshold −70/−80/−90dB は max PGA ≥ 11.5/21.5/31.5dB が必要（firmware が強制）。

**未実装（意図的）**: ADC FIR — 既定係数が存在せず、FIR 対応 PRB を選んで全 tap を書かないと未定義状態になるため。

## 4. 設定経路まとめ

Studio（EQ デザイナー UI + HP音量 + delay スライダー）が RBJ cookbook で係数計算 →
上記 serial コマンドを **USB Web Serial** で受信機に送信 → firmware が codec/ring/NVS に適用。
本体側での変更（ボタン等）は HP 音量のみ（EQ/delay は当面 Studio 専用、将来本体 UI 追加余地）。
