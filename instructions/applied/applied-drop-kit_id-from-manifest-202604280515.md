# Applied: kit-manifest から `kit_id` を削除して `name` に一本化

**日付:** 2026-04-28
**起点セッション:** workspace (helper + studio セッション)
**対象 repo:** hapbeat-contracts
**ステータス:** ✅ 適用済み — レビューしてください

## この repo に入った変更

- `schemas/kit-manifest.schema.json`
  - `required` から `"kit_id"` を削除
  - `properties.kit_id` を削除
  - `properties.name` を `^[a-z][a-z0-9-]*$` パターン制約付きに変更（旧 kit_id の制約を継承）。description を「Kit name (= ID = ディレクトリ名 = wire-protocol 上の kit_id)」に
- `specs/kit-format.md`
  - フィールド表から `kit_id` 行を削除
  - 「Kit ID」セクションを「Kit name (= Kit ID)」に改題、3 箇所同じ値（フォルダ・manifest.name・wire payload kit_id）であることを明記
  - manifest 例 から `kit_id` 行を削除、`name` の値を `basic-impacts` に変更（表示名でなく ID として使用される）
- `fixtures/sample-kit-manifest.json`
  - `kit_id` 行を削除、`name` を `basic-impacts` に変更

`kit-install-protocol.md` / `bridge-api.md` の wire payload `kit_id` フィールドはそのまま残置（API レベルでは引き続き必要、manifest と独立）。

## 変更の背景

`manifest.kit_id` と `manifest.name` が実用上常に同じ値（=ディレクトリ名）を保持しており、別フィールドにする実利が無かった。リリース前なので互換性は不要。1 フィールドに統合し、文字列の制約は contracts kit_id pattern (`^[a-z][a-z0-9-]*$`) に揃えた。

## 横断的に同セッションで入った関連変更

- **hapbeat-studio**:
  - `kitExporter.ts` の manifest 出力から `kit_id` 削除
  - `libraryStore.ts` の import 経路で `manifest.kit_id` を読まない（既に folderName 由来）
  - `validateKitName` を `^[a-z][a-z0-9-]*$` に揃え、UI sanitize / メッセージ更新

## 検証状況

- contracts は schema / spec / fixture すべて整合済み
- Studio 側 typecheck pass、新 manifest 出力サンプルで `kit_id` キーが存在しないことを確認

## この repo のエージェントへのアクション

1. schema / spec / fixture diff をレビュー
2. 必要なら `decision-log.md` に DEC を採番して追記（kit_id 削除は仕様変更なので採番推奨）
3. 問題なければ本ファイルを `instructions/completed/` に移動

## 影響を受ける他 repo (要追従、別セッションで対応)

各 repo で manifest から `kit_id` を読んでいる箇所を `name` または「ディレクトリ名」に切り替える必要がある:

- **hapbeat-kit-tools**: kit-validator / kit-builder の manifest 出力・検証
- **hapbeat-device-firmware**: `kit_loader.cpp` の manifest 読み取り（`manifest["kit_id"]` を参照しているなら削除し、`manifest["name"]` 1 本に）
- **hapbeat-helper**: deploy 時の payload 構築で manifest から kit_id を読まずディレクトリ名 / WS 入力 payload を使う
- **hapbeat-unity-sdk**: SDK 側で manifest を parse する箇所があれば追従

各 repo 宛の指示書として `hapbeat-contracts/instructions/instructions-drop-kit_id-from-manifest-202604280515.md` を残してあるので、そちらを参照して各 repo セッションで対応してください。
