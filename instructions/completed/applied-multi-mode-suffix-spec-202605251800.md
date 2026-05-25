# 事後承認 note: Kit manifest 2 bucket 化 (schema 2.0.0, Option C) を contracts に適用

**起点 repo:** `hapbeat-studio` (workspace session 2026-05-25)
**関連 DEC:** DEC-031
**原 instructions:** `hapbeat-contracts/instructions/instructions-multi-mode-suffix-spec-202605251800.md`

## 何を変更したか

workspace `hapbeat-studio` セッションから横断的に contracts repo へ schema 2.0.0 を適用。

bucket 命名は **Option C** (`events` を command 専用に narrow + `stream_events` 新設) を採択。
当初検討した Option A (`command_events` / `stream_events` symmetric naming) は **device firmware
の kit_loader が `doc["events"]` を参照しているため、rename すると firmware の major bump + OTA
配布が必須** になることが判明し、避けた。

### 変更ファイル

| ファイル | 変更内容 |
|---|---|
| `specs/kit-format.md` | `events` セクションを command-mode 専用に narrow 化、`stream_events` 新セクション追加。`mode` フィールド説明を削除。サンプル manifest を schema 2.0.0 で書き直し (BOTH モードの例を含む)。"clip ファイルの配置" 節を bucket ベースに改訂。`stream_source` への言及を全削除。"命名注" として `events` を維持した理由 (firmware 無変更) を明記 |
| `schemas/kit-manifest.schema.json` | `events` を command 専用 patternProperties に narrow 化 (key regex は現行のまま)、`stream_events` (optional) を新規追加。`mode` プロパティと `stream_source` enum 値を削除。`clip` を両 bucket で `required` に変更。`schema_version` の examples を `"2.0.0"` に更新 |
| `fixtures/sample-kit-manifest.json` | 新スキーマで書き直し。command-only / stream-only / BOTH (同一 eventId が両 bucket に存在) の 3 ケースをサンプル化 |
| `specs/message-format.md` | PLAY (0x01) / STOP (0x02) の `event_id` 説明に「`events` (command-mode) のキーと一致、`stream_events` のキーはここに乗らない」を追記。STREAM_BEGIN (0x30) に「event_id フィールドを含まない、`stream_events` のキーは SDK 内部ラベル」を追記 |
| `../docs/decision-log.md` | DEC-031 追加 (workspace 側 decision-log) |

## 横断的背景

- 起点 commit: hapbeat-studio @ `4dd0362` (KitEvent multi-mode 追加時に `.fire` / `.clip` suffix で BOTH を表現していた)
- suffix 案の構造的問題を洗い出し、bucket 分離設計に方針変更 (本セッションでユーザーと議論して確定)
- 当初 Option A (`command_events`) で contracts spec / Studio 実装を進めたが、firmware への影響を再評価した結果、ユーザーと再相談して Option C (`events` 名維持) に切り替えた
- contracts spec / Studio 実装 (kitExporter / migration) を同セッションで cut-over
- device-firmware / unity-sdk への追従は別 instructions で対応 (本指示書末尾「副次影響」参照)

## 検証状況

- ajv で `fixtures/sample-kit-manifest.json` を `schemas/kit-manifest.schema.json` に対して validate → **pass**
- Studio 側で typecheck + build → 別タスクで実施 (pass 済)
- device-firmware / unity-sdk の追従は **未実施** (本 repo の責務外)

## 当該 repo (contracts) エージェントへのアクション

1. 上記変更を review
2. 問題なければ `instructions/instructions-multi-mode-suffix-spec-202605251800.md` を `instructions/completed/` へ移動
3. 本 applied note も同じく確認後 `completed/` へ移動 (or 残置)
4. 副次追従の instructions が起票済か確認:
   - `hapbeat-unity-sdk/instructions/instructions-multi-mode-manifest-read-202605251800.md` (起票済 — Option C 反映済)
   - `hapbeat-device-firmware/instructions/instructions-events-rename-on-next-update-202605251800.md` (起票済 — **低優先 / defer**。次回 firmware 更新時にバンドル推奨。Option C のおかげで現バイナリは無変更で動作する)

## 補足

- `stream_source` mode は spec / schema / fixture から完全に削除した。Studio 側のコードに残る `stream_source` 関連残骸は本セッション内で同時に削除済
- Studio v1 → v2 manifest migration は Studio repo 側で実装済 (`libraryStore.ts` の `importKitsFromOutputDir` が schema_version / stream_events 有無 / 各 entry の mode field & suffix 有無で自動判定)
- `events` という bucket 名は schema 1.x からの命名を継承。命名 symmetry より firmware 無変更を優先した妥協 (DEC-031 Option C)
