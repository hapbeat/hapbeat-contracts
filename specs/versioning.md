# バージョニング・互換性ルール仕様書

## 1. 概要

本ドキュメントは、Hapbeat エコシステム全体におけるバージョニング方針と互換性ルールを定義する。
SDK、Bridge、Transmitter、デバイスファームウェア、Kit など複数のコンポーネントが連携するため、
各コンポーネント間の互換性を明確に管理することが不可欠である。

## 2. バージョニング体系

[Semantic Versioning (semver)](https://semver.org/) を採用する。

形式: **MAJOR.MINOR.PATCH**

| 区分 | 説明 |
|------|------|
| **MAJOR** | 後方互換性を破壊する変更 |
| **MINOR** | 後方互換な機能追加 |
| **PATCH** | バグ修正 |

## 3. バージョン管理対象

以下のコンポーネントそれぞれが独立したバージョンを持つ。

| 対象 | バージョン形式 | 備考 |
|------|---------------|------|
| contracts 仕様バージョン | semver | この repo 全体を対象とする |
| Kit manifest schema バージョン | `schema_version` フィールド | manifest.json 内で宣言 |
| Bridge API バージョン | API パスに含む (`/api/v1/`) | URL パスのメジャーバージョンで管理 |
| UDP プロトコルバージョン | ヘッダの `protocol_version` | パケットヘッダに含まれる整数値 |
| Bridge-Transmitter プロトコルバージョン | 内部バージョン番号 | **[INTERNAL]** 外部公開しない |
| デバイスファームウェアバージョン | semver | デバイス本体に書き込まれる |
| Kit バージョン | semver | 各 Kit の `version` フィールド |

## 4. 互換性マトリクス

### 4.1 Kit と Device Firmware

Kit の `target_device` セクションで互換性を管理する。

- `target_device.firmware_version_min`: この Kit が動作する最低ファームウェアバージョン
- `target_device.firmware_version_max`（省略可能）: この Kit が動作する最大ファームウェアバージョン

Bridge はデバイスのファームウェアバージョンと Kit の要件を照合し、
互換性がない場合はエラーを返す。

### 4.2 SDK と Bridge API

API バージョン（v1, v2, ...）で管理する。

- 同一メジャーバージョン内では後方互換性を保証する。
- SDK は接続時に Bridge の API バージョンを確認し、互換性を検証する。

### 4.3 Bridge と Transmitter

内部プロトコルバージョンで管理する。

- Bridge と Transmitter は同時更新を前提とするが、互換性チェックは行う。
- 接続確立時にプロトコルバージョンのネゴシエーションを実施する。

## 5. 破壊的変更の扱い

各変更の種類に応じたバージョンアップの基準を以下に定める。

### MAJOR バージョンアップが必要な変更

| 変更内容 | 理由 |
|---------|------|
| Event ID 命名規則の変更 | 既存の Event ID が無効になる可能性がある |
| Kit manifest schema の必須フィールド追加 | 既存の manifest が不正になる |
| Bridge API の既存エンドポイント削除・変更 | 既存の SDK 連携が動作しなくなる |
| UDP コマンドの既存フォーマット変更 | 既存のパケット解析が失敗する |

### MINOR バージョンアップで行える変更

| 変更内容 | 理由 |
|---------|------|
| Kit manifest schema のオプショナルフィールド追加 | 既存の manifest は引き続き有効 |
| Bridge API の新エンドポイント追加 | 既存のエンドポイントには影響しない |
| UDP コマンドの追加 | 既存コマンドには影響しない |

## 6. 非推奨 (deprecation) ポリシー

破壊的変更を行う際は、以下の手順に従う。

1. **deprecation 警告の発行**: 破壊的変更の前に、最低 **1 マイナーバージョン** で deprecation 警告を出す。
   - ドキュメント、ログ出力、API レスポンスヘッダなどで明示する。
2. **維持期間**: deprecated な機能は、最低 **2 マイナーバージョン** 維持してから削除する。
   - 例: v1.3 で deprecation 警告 → v1.5 以降で削除可能
3. **移行ガイド**: deprecated な機能を削除する MAJOR バージョンアップ時には、移行ガイドを提供する。

## 7. 初期バージョン (0.x.y)

バージョン `0.x.y` は開発段階を示す。

- 安定版リリース（`1.0.0`）までは、破壊的変更を **MINOR** バージョンアップで行うことを許容する。
- `0.x.y` の間は deprecation ポリシーの適用を必須としない（推奨はする）。
- `1.0.0` のリリースをもって、本仕様書の全ルールが完全に適用される。

## 8. 変更履歴

### 2026-04-25 — pack → kit 命名統一

- `pack-manifest.schema.json` → `kit-manifest.schema.json`
- `specs/pack-format.md` → `specs/kit-format.md`
- `specs/pack-install-protocol.md` → `specs/kit-install-protocol.md`
- payload field: `pack_id` → `kit_id`
- TCP/プロトコルコマンド名: `pack_list` / `pack_delete` / `pack_transfer` → `kit_*`
- 関連 repo（pack-tools / firmware / manager / studio / SDK）は順次追従
- 旧名の alias は残さない（破壊的変更）
