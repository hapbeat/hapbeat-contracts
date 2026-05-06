# Instructions: kit-manifest から `kit_id` を削除して `name` に一本化

**発行日:** 2026-04-28
**起点セッション:** workspace (helper + studio セッション)
**優先度:** 即着手（Studio 側は既に追従済み — schema との不整合がある状態）
**関連 DEC:** （新規 DEC を採番予定）

## 背景

Studio セッションで kit-manifest の項目数を整理した。`kit_id` と `name` は常に同じ値（=ディレクトリ名）を持っていて、別フィールドにする実用上のメリットが無かった。リリース前なので互換性は不要、思い切って 1 フィールドに統合する。

新方針:
- on-disk フォルダ名 = `manifest.name` = wire 上の `kit_id` payload
- フォルダ名は `^[a-z][a-z0-9-]*$`（contracts kit_id pattern）に制限
- `manifest.kit_id` フィールドは削除

`kit_id` は wire / API レベル（kit-install-protocol、bridge-api 等）では引き続き使用される。「manifest 内に冗長に書かない」だけ。送信側（Studio / SDK）はフォルダ名を payload の `kit_id` に乗せて送る。

## Studio 側の現状（参考）

Studio は既に以下を実施済み:
- `kitExporter.ts` の manifest から `kit_id` を削除（`name` 一本）
- `libraryStore.importKitsFromOutputDir` で `manifest.kit_id` を参照しない（フォルダ名のみ使用）
- `validateKitName` を `^[a-z][a-z0-9-]*$` に揃え（contracts kit_id pattern と完全一致）

## このリポジトリで必要な変更

### 1. `schemas/kit-manifest.schema.json`
- `required` から `"kit_id"` を削除
- `properties.kit_id` を削除
- `additionalProperties: false` のままなので、`kit_id` を含む古い manifest は **invalid** になる（リリース前なので OK）

### 2. `specs/kit-format.md`
- フィールド定義表から `kit_id` 行を削除
- 「Kit ID の命名規則」セクションを「Kit name (= フォルダ名) の命名規則」に変更
- サンプル manifest から `kit_id` 行を削除
- 命名規則は `^[a-z][a-z0-9-]*$`（変更なし、ただし「kit_id」→「name」に呼び方を統一）

### 3. `specs/kit-install-protocol.md`
- wire 上の `kit_id` フィールド（CMD_INSTALL_KIT、CMD_DELETE_KIT、event_id 等）は **そのまま残す**。
- ただし「manifest.kit_id を読む」と書いてある箇所があれば「manifest.name」or「ディレクトリ名」に修正

### 4. `specs/bridge-api.md`
- API payload の `kit_id` フィールドは **そのまま残す**（変更なし）

### 5. `fixtures/sample-kit-manifest.json`
- `"kit_id": "basic-impacts",` 行を削除

## 完了条件

- [ ] schema / spec / fixture すべてが `kit_id` フィールドを持たない
- [ ] schema validate で新 manifest が pass する
- [ ] CHANGELOG または decision-log に DEC を追記
- [ ] 本ファイルを `instructions/completed/` へ移動

## 影響を受ける他 repo（要追従）

各 repo に同名の applied note を配置する。本指示書を完了したら、各 repo セッションで以下に対応:

- **hapbeat-kit-tools**: `kit-validator` / `kit-builder` の manifest 出力・検証から `kit_id` を削除
- **hapbeat-device-firmware**: `kit_loader.cpp` の `manifest["kit_id"]` 読み取り箇所を削除（`manifest["name"]` のみ参照）。kit ディレクトリ名と manifest.name が一致する前提でロード。
- **hapbeat-helper**: deploy 時の payload 構築コードで manifest から `kit_id` を読まずに、ディレクトリ名 / WS payload で渡された値を使用
- **hapbeat-unity-sdk**: SDK 側で manifest を parse する箇所があれば `kit_id` 参照を削除

## 参考 (Studio 側の commit)

近日中に Studio 側でこの変更がコミットされる予定 (workspace セッション)。
