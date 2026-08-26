# バージョニング・互換性ルール仕様書

## 1. 概要

本ドキュメントは、Hapbeat エコシステム全体におけるバージョニング方針と互換性ルールを定義する。
SDK、EspNowStream transmitter、デバイスファームウェア、Kit など複数のコンポーネントが連携するため、
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
| WifiUdp プロトコルバージョン | ヘッダの `protocol_version` | パケットヘッダに含まれる整数値。wire/config 値は `wifi_udp` |
| EspNowStream プロトコルバージョン | `0xAA` / `0xAC` の packet format | **[INTERNAL]**。現行 wire bytes は変更しない |
| デバイスファームウェアバージョン | semver | デバイス本体に書き込まれる |
| Kit バージョン | semver | 各 Kit の `version` フィールド |

## 4. 互換性マトリクス

### 4.1 Kit と Device Firmware

Kit の `target_device` セクションで互換性を管理する。

- `target_device.firmware_version_min`: この Kit が動作する最低ファームウェアバージョン
- `target_device.firmware_version_max`（省略可能）: この Kit が動作する最大ファームウェアバージョン

Kit を配布するツールはデバイスのファームウェアバージョンと Kit の要件を照合し、
互換性がない場合はエラーを返す。

### 4.2 SDK と WifiUdp

`protocol_version` で管理する。

- SDK はデバイスへ UDP 7700 を直接送信する。
- wire bytes を変更する場合は `protocol_version` を上げる。

### 4.3 EspNowStream transmitter と receiver

`0xAA` / `0xAC` の packet format と mode_id の対応で管理する。送信機と受信機は対応する mode の codec / sample rate / channel を一致させる。

## 5. 破壊的変更の扱い

各変更の種類に応じたバージョンアップの基準を以下に定める。

### MAJOR バージョンアップが必要な変更

| 変更内容 | 理由 |
|---------|------|
| Event ID 命名規則の変更 | 既存の Event ID が無効になる可能性がある |
| Kit manifest schema の必須フィールド追加 | 既存の manifest が不正になる |
| WifiUdp コマンドの既存フォーマット変更 | 既存のパケット解析が失敗する |
| NodeTransport の enum 値変更 | metadata/config を読む実装が解釈できなくなる |

### MINOR バージョンアップで行える変更

| 変更内容 | 理由 |
|---------|------|
| Kit manifest schema のオプショナルフィールド追加 | 既存の manifest は引き続き有効 |
| WifiUdp コマンドの追加 | 既存コマンドには影響しない |

## 6. 破壊的変更

Hapbeat はリリース前であり、旧名 alias・互換 fallback・移行ガイドを作らない。破壊的変更は旧仕様を削除し、全実装を同じ contracts に追従させる。

## 7. 初期バージョン (0.x.y)

バージョン `0.x.y` は開発段階を示す。

- 安定版リリース（`1.0.0`）までは、破壊的変更を **MINOR** バージョンアップで行うことを許容する。
- `0.x.y` の間は破壊的変更を旧仕様の保持なしで適用する。
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
