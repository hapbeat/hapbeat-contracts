---
title: Contracts 概要
description: Hapbeat エコシステム全体の仕様の起点となる contracts repo の役割と、各 spec の読みどころ。
---

`hapbeat-contracts` は Hapbeat エコシステム全体の **仕様の起点** です。Pack（Kit）形式、メッセージプロトコル、JSON Schema 等の規範的仕様をここに集約し、他のすべての repo（pack-tools / firmware / manager / studio / SDK）が参照します。

## 構成

| ディレクトリ | 内容 |
|------------|-----|
| `specs/` | 規範的な仕様文書（プロトコル定義・データ形式） |
| `schemas/` | 機械可読な JSON Schema |
| `fixtures/` | テスト・例示用のサンプルデータ |
| `docs/` | 概念解説・チュートリアル（このディレクトリ） |
| `dev-notes/` | （あれば）内部検討メモ |

## 主要 spec の読みどころ

| ファイル | 何が書いてある |
|---------|------------|
| **kit-format.md** | Kit（旧 Pack）の manifest.json + clips の構造 |
| **kit-install-protocol.md** | Manager → Device の Kit 転送 TCP シーケンス |
| **message-format.md** | UDP / TCP / Serial のメッセージフォーマット全体像 |
| **device-addressing.md** | device ID / group ID の割り当てルール |
| **display-layout.md** | OLED ブロック配置の JSON 仕様 |
| **event-id.md** | Event ID 命名規則 |
| **serial-config.md** | シリアル経由の設定プロトコル |
| **bridge-api.md** | Bridge 経由通信時の API |
| **internal-bridge-transmitter.md** | Bridge ↔ Transmitter の内部仕様 |
| **versioning.md** | 互換性ポリシー、バージョン番号付け方 |

## 用語

| 用語 | 意味 |
|-----|-----|
| **Kit** | 触覚コンテンツのパッケージ（manifest + WAV）。旧称 Pack |
| **Event ID** | Kit 内の触覚を識別する文字列 |
| **Group ID** | デバイスを論理グループに分けるための整数（デフォルト 0） |
| **Device ID** | 個体識別。MAC アドレスベース |
| **mode** | Event の再生方式: `command` (FIRE) / `stream_clip` (CLIP) / `stream_source` (LIVE) |
| **intensity** | 0-128 の触覚強度（Kit 内に保存、再生時は SDK gain と乗算） |
| **device_wiper** | 強度補正値（左右バランス等、デバイス側で適用） |

## なぜ contracts を中心に置くのか

各 SDK や firmware が独自仕様を持つと、エコシステム全体が壊れます。contracts を起点にすることで:

- 仕様変更がここから他 repo へ波及する一方向性が保たれる
- pack-tools / firmware / manager / SDK のすべてが同じ JSON Schema で検証可能
- 新しい SDK（例: Unreal）追加時も contracts を読めば仕様が揃う

## 関連

- [Pack / Kit フォーマット](/docs/pack/) — 集約版（spec を要約したもの）
- [Protocol リファレンス](/docs/protocol/) — メッセージ仕様の総覧
- [アーキテクチャと主要概念](/docs/concepts/) — 全体像
