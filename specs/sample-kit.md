# Sample Kit 仕様（動作確認用の標準 Kit）

バージョン: 1.0.0 — 制定 2026-06（DEC-040）

## 目的

`sample-kit` は、**任意の SDK / ツールから「Hapbeat が振動するか」を即確認するための公式 Kit**
である。ユーザーが自前のコンテンツを用意する前でも、この Kit をデバイスへ deploy するだけで、
各 SDK が `sample-kit.sine_100hz` を再生して疎通・動作を確認できる。

想定フロー:

1. **Studio** が Kit 作業フォルダ選択時に `sample-kit`（manifest + sine WAV）を自動 materialize
   （`hapbeat-studio` instructions 参照）。
2. ユーザーは `sample-kit` をデバイスへ **deploy** する。
3. 任意の SDK から `hb.play("sample-kit.sine_100hz")` を送ると振動する。

## Kit 構成

- Kit 名（= Kit ID）: **`sample-kit`**（`event-id.md` の予約 Kit 名）
- `schema_version`: `2.0.0`（`kit-format.md` 準拠）

### clips（install-clips, command モード）

純音 sine の校正トーン 3 本。低・中・高で機種ごとの周波数特性・体感差が分かる。

| clip ファイル | Event ID | 周波数 | 備考 |
|---|---|---|---|
| `sine_50hz.wav` | `sample-kit.sine_50hz` | 50 Hz | 低域 |
| `sine_100hz.wav` | `sample-kit.sine_100hz` | 100 Hz | **canonical（疎通確認の既定イベント）** |
| `sine_200hz.wav` | `sample-kit.sine_200hz` | 200 Hz | 高域 |

各 SDK の quickstart / 動作確認サンプルは **`sample-kit.sine_100hz`** を既定イベントとして使う。

## WAV 生成仕様（決定的に再現可能）

install-clips の各 WAV は以下で生成する。同じパラメータなら誰が生成しても同一バイト列になる。

| 項目 | 値 |
|---|---|
| サンプルレート | 16000 Hz（デバイス再生レートと一致） |
| チャンネル | **1（mono）** — install-clips はデバイス焼き込み・mono |
| ビット深度 | 16-bit PCM（`pcm_s16le`） |
| 長さ | 1.0 秒 |
| 振幅 | 0.45 × フルスケール（peak = `round(0.45 * 32767)` = 14745）、一様（フェードなし） |
| 波形 | `sample[i] = round(peak * sin(2π * f * i / 16000))`, i = 0..15999 |

> 既存の `hapbeat-studio/scripts/gen-sine-tones.py` は同等の sine を生成する（ただし
> stream-clips 用に stereo・別周波数セット）。本 Kit の install-clips は **mono** で生成すること。

## manifest

正準の manifest は `fixtures/sample-kit-manifest.json`（本 spec と同梱の fixture）を参照。
`name: "sample-kit"`、`events` に上記 3 イベント、`install_clips` に 3 WAV のメタを持つ。

## 注意

- `sample-kit` は **command モードのみ**（`stream_events` は持たない）。最も移植性が高い fire 経路で
  動作確認できることを優先する。
- 振幅 0.45 はミキサーのヘッドルームを残した安全値。デバイス側 volume と SDK gain でさらに調整可能。
