# hapbeat-contracts

## この repo は何か

Hapbeat SDK エコシステム全体の**中核仕様リポジトリ**です。
すべての実装 repo が参照する「信頼できる唯一の情報源 (Single Source of Truth)」として機能します。

本リポジトリで定義・管理する仕様:

- **Event ID 命名規則** -- 触覚イベントを一意に識別するための ID 体系
- **Kit 形式仕様** -- 触覚パターンをまとめた Kit ファイルのマニフェスト・ディレクトリ構造
- **Bridge API 仕様** -- hapbeat-bridge が公開する API エンドポイントの定義
- **UDP/OSC メッセージ仕様** -- Bridge・Transmitter 間、SDK・Bridge 間で流れるメッセージのフォーマット
- **バージョニング方針** -- 仕様のバージョン管理と互換性の維持ルール
- **互換性ルール** -- 各コンポーネント間のバージョン互換性マトリクス

## 全体の中での位置づけ

hapbeat-contracts は**依存関係の起点**です。

```
hapbeat-contracts (ここ)
 ├── hapbeat-kit-tools
 ├── hapbeat-device-firmware
 ├── hapbeat-bridge
 ├── hapbeat-transmitter-firmware
 ├── hapbeat-unity-sdk
 ├── hapbeat-unreal-sdk
 └── hapbeat-creative-kit
```

他の全 repo はここで定義された仕様に従って実装されます。
hapbeat-contracts 自体は他のどの repo にも依存しません。

## 設計方針

**contracts 起点の開発フロー**を採用します。

1. まず hapbeat-contracts で仕様を策定・合意する
2. 合意された仕様を各実装 repo に反映する
3. 仕様変更が必要な場合は、まず hapbeat-contracts で議論・更新してから実装に着手する

これにより、複数 repo にまたがる仕様の不整合を防ぎ、各チーム・各 repo が同じ仕様に基づいて並行開発できる体制を実現します。

## 依存関係

| 方向 | 内容 |
|------|------|
| **この repo が依存するもの** | なし |
| **この repo に依存する repo** | hapbeat-kit-tools, hapbeat-device-firmware, hapbeat-bridge, hapbeat-transmitter-firmware, hapbeat-unity-sdk, hapbeat-unreal-sdk, hapbeat-creative-kit |

## 今後の最初のタスク

1. **Event ID 命名規則の策定** -- 触覚イベントを識別する ID の命名体系を決定する
2. **Kit manifest schema の定義** -- Kit ファイルのマニフェスト JSON Schema を策定する
3. **Bridge API の基本仕様策定** -- hapbeat-bridge が公開するエンドポイント・プロトコルを定義する

## 現在の状態

現時点では実装コードはありません。仕様書・schema 定義・テスト用 fixtures を順次追加していく予定です。
