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
- **ボタン**: 再生モードで **Btn4 = HP vol+ / Btn5 = HP vol−**（触覚はホイール据置）。
  - 既存の config トグル combo（Btn1+Btn5 長押し）と Btn5 が競合するため、combo 発火後は
    Btn5 の release-edge を1サイクル suppress（誤爆防止）。
- HP 音量 API: `duoV4SetHeadphoneVolume(hp_db)`（−59..+4 dB、NVS `duo_audio`/`hp_db`）既存を流用。

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

## 3. A-V（音声-触覚間）delay

codec に delay ブロック無し → **firmware のリング target オフセット**で実現
（`audio_stream.cpp` の per-ring `*_ll_target`）。**音声(HP)を触覚に対して遅延**（遅い触覚
モーターに音声を合わせる = ADAU の設計意図）。

- 範囲 **0..30 ms**（HP ring headroom ~138ms 内に十分収まる。>180ms は prebuf 未達 bug のため不可）。
- HP ring は 48k（frames = ms×48）、触覚 ring は 16k。音声を遅らせる = HP target に delay 分を加算。
- serial: `{"cmd":"set_av_delay","ms":0..30}`。NVS 永続。`get_info.av_delay_ms` を報告。

## 4. 設定経路まとめ

Studio（EQ デザイナー UI + HP音量 + delay スライダー）が RBJ cookbook で係数計算 →
上記 serial コマンドを **USB Web Serial** で受信機に送信 → firmware が codec/ring/NVS に適用。
本体側での変更（ボタン等）は HP 音量のみ（EQ/delay は当面 Studio 専用、将来本体 UI 追加余地）。
