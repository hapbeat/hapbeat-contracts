# 指示書: pack → kit 命名統一（contracts 編）

_作成: 2026-04-25_
_関連メモリ: `../docs/agent-memory/project_pack_to_kit_migration.md`_

## 背景

ワークスペース全体で「pack」を「kit」に寄せる命名統一の **Phase 1**。本 repo は全体仕様の起点なので、他 repo に先行してこの移行を完了させる。完了後、pack-tools / firmware / manager / studio / SDK が順次追従する。

Manager UI は既に Kit 表記に移行済み（2026-04-21）。今回は **仕様側の内部名・スキーマ名・ドキュメント用語を Kit 統一**する。

## スコープ

### 1. スキーマファイル

- `schemas/pack-manifest.schema.json` → **`schemas/kit-manifest.schema.json`**
  - `$id` を `.../kit-manifest.schema.json` に更新
  - `title` / `description` 内の "pack" を "kit" に
  - **旧ファイルは削除**（alias 残置しない、workspace CLAUDE.md 方針）

### 2. specs ドキュメント

以下のファイルをリネームし、内容内の用語も置換:

- `docs/pack-format.md` → `docs/kit-format.md`
- `docs/pack-install-protocol.md` → `docs/kit-install-protocol.md`

他の specs (`message-format.md`, `device-addressing.md`, `event-id.md`, `bridge-api.md`, `internal-bridge-transmitter.md`, `versioning.md`, `display-layout.md`, `serial-config.md`) 内の "pack" 文字列も、文脈が現行の Kit を指している箇所はすべて "kit" に置換する。以下のパターンで grep して 1 件ずつ判断:

```bash
grep -rn -iE '\bpack(s|-|_|\.)|pack manager|pack id|pack file' docs/ schemas/ specs/
```

### 3. 内部プロトコル用語

- `pack_install` / `pack_list` / `pack_delete` / `pack_transfer` → `kit_install` / `kit_list` / `kit_delete` / `kit_transfer` に spec 上で変更
- payload field: `pack_id` → `kit_id`, `pack_dir` → `kit_dir`
- これは **spec の変更のみ**。実装 (firmware / manager) の変更は別セッションで atomic に行う

### 4. fixtures / tests

- `fixtures/` 内の sample pack は `fixtures/kit-*` 系にリネーム
- テストコードがあれば合わせて更新

### 5. versioning.md

末尾に decision log エントリを追記:

```md
## 2026-04-25 — pack → kit 命名統一

- `pack-manifest.schema.json` → `kit-manifest.schema.json`
- 仕様文書内の「pack」を「kit」に統一
- 旧名の alias は残さない
- 関連 repo（pack-tools / firmware / manager / studio / SDK）は順次追従予定
```

## やってはいけないこと

- alias や互換 schema を残す（workspace CLAUDE.md: "後方互換コードを作らない"）
- 他 repo のファイルを編集する（閲覧のみ可）
- Manager / firmware の TCP コマンド実装を変更する（別セッション）

## 完了条件

- [ ] `schemas/kit-manifest.schema.json` 存在、`schemas/pack-manifest.schema.json` 不在
- [ ] `docs/kit-format.md`, `docs/kit-install-protocol.md` 存在、旧名不在
- [ ] `grep -rin 'pack' docs/ schemas/ specs/` の結果がゼロ（あるいは履歴注記のみ）
- [ ] `versioning.md` にエントリ追加
- [ ] commit + push
- [ ] この指示書を `instructions/completed/` に移動

## 検証

```bash
# schema が JSON として valid
cat schemas/kit-manifest.schema.json | python -m json.tool > /dev/null

# specs 側の参照切れがないか
grep -rn 'pack-manifest\|pack-format\|pack-install-protocol' docs/ schemas/
# → ヒット 0 件になっているはず
```

## 次の指示書

この作業完了後、以下を順次実施（各 repo の `instructions/` に配置済み）:

1. `hapbeat-pack-tools/instructions/instructions-rename-kit-tools-202604251200.md` — repo リネーム
2. `hapbeat-device-firmware/` + `hapbeat-manager/` 連携 TCP コマンド rename
3. `hapbeat-manager/` + `hapbeat-studio/` 連携 WS プロトコル rename
4. SDK 各種の用語掃除
