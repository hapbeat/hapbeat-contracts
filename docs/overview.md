---
title: Contracts 概要
description: Event ID・Kit・Group ID など、Hapbeat SDK を使う上で知っておくべき基本概念のリファレンス。
---

Hapbeat SDK を使ううえで登場する主要な概念を説明します。

## Event ID

触覚コンテンツを識別する文字列です。SDK はこの ID を送信するだけで Hapbeat が対応する触覚を再生します。

**形式**: `<kit-name>.<clip-name>`

```
basic-exam-kit.sine_100hz_1s
my-game.sword-hit
my-game.footstep-grass
```

- `kit-name` は Kit のフォルダ名（スペースなし、ハイフン区切り推奨）
- `clip-name` は Kit 内の WAV ファイル名（拡張子なし）
- Unity SDK では EventMap ウィンドウで管理し、自動で合成されます

## Kit

触覚コンテンツのパッケージです。**WAV ファイル群 + manifest.json** で構成されます。

```
my-game/               ← Kit フォルダ（= kit-name）
  manifest.json        ← メタデータ・Event 一覧
  install-clips/
    sword-hit.wav      ← FIRE モード用クリップ
    footstep-grass.wav
  stream-clips/        ← CLIP モード用（Studio が自動配置）
```

### manifest.json の主なフィールド

```json
{
  "name": "my-game",
  "version": "1.0.0",
  "events": [
    {
      "id": "my-game.sword-hit",
      "clip": "sword-hit.wav",
      "mode": "command",
      "intensity": 0.8
    }
  ]
}
```

| フィールド | 意味 |
|-----------|------|
| `name` | Kit 名（Event ID のプレフィックスになる） |
| `id` | Event ID（`<kit-name>.<clip-name>` 形式） |
| `mode` | `command`（FIRE）または `stream_clip`（CLIP） |
| `intensity` | 基本強度 0.0〜1.0（SDK の gain と乗算される） |

Kit は **Studio で作成・編集** し、Helper 経由で Hapbeat にデプロイします。

## 再生モード

| モード | SDK 表記 | 動作 |
|--------|---------|------|
| FIRE | `command` | Kit をデバイスに事前デプロイ → 短いコマンドを送るだけで再生。低遅延・安定 |
| CLIP | `stream_clip` | WAV を PC からリアルタイムストリーミング。デプロイ不要、長尺対応 |

詳細: [Fire と Clip の比較](/docs/unity-sdk/fire-vs-clip/)

## Group ID と Player 番号

同じ空間に複数のプレイヤーや展示ブースを混在させる場合に使います。

| 概念 | 用途 | 範囲 |
|------|------|------|
| **Group ID** | デバイスを論理グループに分類。同じ Group のデバイスだけがコマンドを受け取る | 1〜99 |
| **Player 番号** | 同一グループ内での個体識別 | 1〜99 |

**例**: プレイヤー A の Group=1、プレイヤー B の Group=2 に設定すると、A の SDK からの送信は A の Hapbeat だけに届きます。

設定は Studio の Devices タブで行います。デバイスのボタン操作でも ±1 できます。

## 通信プロトコル

標準の通信経路は **Wi-Fi UDP broadcast** です。SDK がブロードキャストを送信し、Hapbeat が自身の Group ID に一致するパケットだけを処理します。

```
SDK（PC / Quest / スマートフォン）
  └─ Wi-Fi UDP broadcast ─→ Hapbeat デバイス（Group ID でフィルタ）
```

Bridge や USB 接続は不要です。同じ Wi-Fi ネットワークに繋がっていれば動作します。
