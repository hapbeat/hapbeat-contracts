# Applied: clips/ → install-clips/ rename (DEC-027)

**日付:** 2026-04-26
**起点セッション:** workspace (hapbeat-studio セッション内で issue 単位の横断編集)
**対象 repo:** hapbeat-contracts
**関連 DEC:** [DEC-027](../../../docs/decision-log.md) (workspace `docs/decision-log.md` 参照)
**ステータス:** ✅ 適用済み — レビューしてください

## この repo に入った変更

- `schemas/kit-manifest.schema.json`
  - `events.<id>.clip` の description / examples を更新（command mode は install-clips/ 配下の bare filename、stream_* はキットルート相対）
  - top-level dict key を `clips` → `install_clips` に rename し、description を更新
- `specs/kit-format.md`
  - §3 Kit ディレクトリ構造: `clips/` を `install-clips/` に rename。stream-clips/ も明示。「過去の名称」セクションを追加
  - §5 events.clip の説明を「mode 別パス規則」に書き換え
  - §5 dict 名 `clips` → `install_clips`
  - §5 manifest.json 例の clip パスと dict 名を新規仕様に揃える + stream_clip の例を追加
  - §8 デバイス上のディレクトリ配置・§10 制約事項 を install-clips/ 表記に更新
- `specs/kit-install-protocol.md`
  - file_path 例の `clips/damage.wav` → `install-clips/damage.wav`
  - サブディレクトリ作成例 `clips/` → `install-clips/`
- `specs/event-id.md`
  - manifest 例の clip 値を bare filename に修正（`clips/<file>` の prefix 除去）
- `fixtures/sample-kit-manifest.json`
  - 全 clip 値を bare filename に
  - dict key `clips` → `install_clips`、内部キーも bare filename

## 変更の背景

Kit ディレクトリの `clips/` という名称はデバイスに焼き込んで保存される WAV であることを伝えにくく、`stream-clips/` との対比も弱かった。`install-clips/` に rename することで「install されてデバイスに残る」という時間軸ニュアンスを名前で表現する。manifest dict 名も `clips` → `install_clips` に揃えてフォルダ名と整合。

`event.clip` (command) と `install_clips` 内のキーは引き続き **bare filename** (install-clips/ 配下相対) を使う表記。これは現行の Studio / firmware / kit-tools が共通で前提としている規則を維持するため（過去の fixture には `clips/<file>` prefix が混入していたが、実装側の慣行に合わせて剥がした）。

## 横断的に同セッションで入った関連変更

- **kit-tools (hapbeat-pack-tools)**: `CLIPS_DIR = "install-clips"`, manifest dict key `install_clips`, builder/cli/validator のメッセージ更新, build_src/output 配下のサンプル kit を rename
- **device-firmware**: `kit_installer.cpp` / `kit_loader.cpp` / `tcp_server.cpp` の `"clips/"` プレフィックス判定を `"install-clips/"` に
- **manager**: `pack_normalize.py` が読む dict key と探索パスを `install-clips/` / `install_clips` に
- **studio**: `kitExporter.ts` の ZIP 配置と manifest 出力, `localDirectory.ts` の scan path, `libraryStore.ts` の import lookup
- **unity-sdk**: `HapbeatEventMapWindow.cs` UI hints、`HapbeatKitsReadme.cs`、`docs/kit-integration.md` の cosmetic 更新。templateVersion を `"2"` に bump（manifest 解析は path-agnostic なので機能影響なし）

## 検証状況

- 起点 repo (hapbeat-studio) で `npx tsc --noEmit` 通過
- kit-tools で `pytest` 全 58 test 通過
- firmware は ESP-IDF/PIO build 未実施（テキスト変更のみ、シンボル変化なし）
- contracts repo 自体は schema-validation スクリプトを持たないが、fixture と schema の整合は手動確認

## この repo のエージェントへのアクション

1. `schemas/kit-manifest.schema.json` の変更を確認 — manifest pattern (`^[^/\\\\].*\\.wav$`) は `install-clips/foo.wav` 形式も許容するため stream 系互換 OK
2. fixture が contract test で参照されている場合、テスト側を更新する必要があるか確認（現状この repo にテスト無し）
3. 問題なければ本ファイルを `instructions/completed/` に移動
4. 追加の追従が必要な箇所が見つかった場合は `instructions/` に新規 instruction を作成
