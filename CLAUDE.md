# CLAUDE.md - hapbeat-contracts

## repo の目的

Hapbeat SDK エコシステム全体の**中核仕様リポジトリ**。
以下の仕様をすべてここで定義・管理する。

- Event ID 命名規則
- Kit 形式仕様（マニフェスト、ディレクトリ構造）
- Bridge API 仕様（エンドポイント、リクエスト/レスポンス）
- UDP/OSC メッセージ仕様（Bridge-Transmitter 間、SDK-Bridge 間）
- バージョニング方針
- 互換性ルール
- schema 定義ファイル
- テスト用 fixtures
- contract test の方針

## 全体アーキテクチャ上の役割

**依存関係の起点**。
ここで仕様を決めてから各実装 repo に反映する。
仕様変更はまず hapbeat-contracts で議論・合意し、その後に実装 repo へ展開する。

## この repo の責務

- Event ID 命名規則の定義と管理
- Kit manifest schema の定義
- Bridge API 仕様の定義（UDP/OSC プロトコル含む）
- メッセージフォーマットの定義
- バージョニング方針の策定と管理
- コンポーネント間の互換性ルールの定義
- schema 定義ファイルの管理（JSON Schema 等）
- テスト用 fixtures の管理
- contract test 方針の策定

## 管理対象

- 仕様書（Event ID、Kit、Bridge API、メッセージフォーマット等）
- schema 定義ファイル（JSON Schema 等）
- テスト用 fixtures（各 repo が contract test で使うサンプルデータ）
- バージョン互換性マトリクス

## 管理対象外

以下はこの repo では扱わない。

- 実装コード
- ビルドスクリプト
- UI
- デバイスファームウェア
- SDK コード

## 依存関係

### 依存してよい repo

**なし**。この repo は依存関係の起点であり、他の repo には一切依存しない。

### 依存される repo

- hapbeat-kit-tools
- hapbeat-device-firmware
- hapbeat-bridge
- hapbeat-transmitter-firmware
- hapbeat-unity-sdk
- hapbeat-unreal-sdk
- hapbeat-creative-kit

## 壊してはいけない公開インターフェース

- **Event ID 命名規則** -- 一度公開した命名規則を破壊的に変更すると、全 repo の互換性が崩壊する
- **Kit manifest schema** -- Kit ファイルの構造を変えると kit-tools および全 SDK に影響する
- **Bridge API の公開エンドポイント** -- Bridge と通信する全コンポーネントが影響を受ける
- **メッセージフォーマット** -- UDP/OSC メッセージの構造を変えると Bridge・Transmitter・SDK 全てに波及する

## 他 repo に影響する変更の例

- Event ID の命名規則変更（例: 区切り文字の変更、階層構造の変更）
- Kit manifest へのフィールド追加・削除・型変更
- Bridge API エンドポイントのパス変更、リクエスト/レスポンス形式の変更
- UDP/OSC メッセージのアドレスパターン変更、ペイロード構造の変更

これらの変更を行う際は、バージョニング方針に従い、後方互換性を慎重に検討すること。

## やってはいけないこと

- **Unity 固有の仕様を混ぜる** -- Unity SDK に都合の良い型やフォーマットをここに持ち込まない。プラットフォーム中立な仕様のみ定義する
- **特定 SDK の都合で公開仕様を歪める** -- 特定のゲームエンジンや言語の制約に引きずられた仕様にしない
- **internal spec と public spec を混同する** -- 内部実装の詳細と公開仕様を明確に区別する。internal spec には明示的にそのラベルを付ける

## まだ作らないもの

- CI/CD パイプライン
- パッケージ配布の仕組み
- 実装コード

## 今後の最初の着手タスク

1. **Event ID 命名規則策定** -- 触覚イベントの ID 体系を定義する
2. **Kit manifest schema 定義** -- Kit ファイルのマニフェスト JSON Schema を策定する
3. **Bridge API 基本仕様策定** -- hapbeat-bridge の公開エンドポイント・プロトコルを定義する
4. **UDP/OSC メッセージフォーマット定義** -- Bridge-Transmitter 間、SDK-Bridge 間のメッセージ構造を定義する

## 実装の優先順位

```
Event ID → Kit → Bridge API → Message format → Versioning
```

Event ID が最も基盤的な概念であり、他の全仕様が Event ID に依存する。
この順序で策定を進めること。

## テストや確認の考え方

- **schema validation** -- JSON Schema 等を使い、仕様書自体の整合性を機械的に検証する
- **contract test** -- 各実装 repo がここで定義された fixtures を使って互換性をテストする
- **fixtures による互換性確認** -- サンプルデータ（fixtures）を提供し、各 repo がそのデータを正しく処理できることを確認する

## オフライン動作をどう意識するか

**クラウド必須の仕様を作らない。**

- ローカルに配置された Kit ファイルと Event ID による触覚再生が、ネットワーク接続なしで完結する設計にする
- Bridge とデバイス間の通信はローカルネットワーク（UDP/OSC）で完結する
- クラウド連携はオプション機能として設計し、コア体験のオフライン動作を保証する

## Kit / Event ID / targetTime / Bridge のうち重要な概念

**全て。** この repo が全概念の定義元である。

- **Event ID** -- 触覚イベントを一意に識別する ID。全 repo で共通の命名規則に従う
- **Kit** -- 触覚パターンをまとめたファイル群。manifest schema はここで定義する
- **targetTime** -- 触覚イベントの再生タイミングを指定するパラメータ
- **Bridge** -- PC 上で動作する中継サービス。API 仕様はここで定義する

## 追記

- 必要に応じて **Bridge と transmitter-firmware 間の内部インターフェース仕様**もここで扱う。ただし internal spec であることを明示し、public spec と混同しないこと
- internal spec には `[INTERNAL]` ラベルを付け、ファイルやセクションを明確に分離する

## 指示書

- `instructions/` — 他セッションからの未実行の指示書
- `instructions/completed/` — 完了済みの指示書
- セッション開始時に `instructions/` を確認し、該当する指示書があれば適用する

## エージェント共通メモリ（Claude / OpenAI 系共通）

- セッション間で引き継ぐ知見・ログ・ルールはワークスペースルートの `docs/agent-memory/` に保存する
- インデックスは `docs/agent-memory/INDEX.md`
- この repo から参照する場合の相対パスは `../docs/agent-memory/`
- メモリを新規作成・更新した場合は、必ず `INDEX.md` も更新する
