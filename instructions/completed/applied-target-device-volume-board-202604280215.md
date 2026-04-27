# Applied: target_device に board / volume_* を追加

**日付:** 2026-04-28 02:15
**起点セッション:** hapbeat-studio (Kit UX セッション、workspace 横断編集)
**対象 repo:** hapbeat-contracts
**ステータス:** ✅ 適用済み — レビューしてください

## この repo に入った変更

- `specs/kit-format.md`
  - `target_device` の表に 4 行追加:
    - `board` (string, optional) — 想定基板識別子
    - `volume_level` (integer, optional) — Kit 作者 device の volume level
    - `volume_wiper` (integer, optional) — MCP4018 wiper (0–127)
    - `volume_steps` (integer, optional) — Kit 作者 device の volume step 総数
- `schemas/kit-manifest.schema.json`
  - `target_device.properties` に同じ 4 フィールドを追加
  - `volume_wiper` は `minimum: 0, maximum: 127`
  - `volume_steps` は `minimum: 1`
  - `board` は `pattern: ^[a-z][a-z0-9_]*$`
  - `additionalProperties: false` のままなので互換性に注意 (新フィールドは
    すでにスキーマに追加済 → 旧 manifest は問題なく通る、新 manifest を
    旧 schema validator にかけると reject される — kit-tools 等の側で
    schema 同期が必要)

## 変更の背景

ユーザーから「kit が "どの基板で" "どのボリュームで" 調整されたか
記録できると便利」という要望。
Studio で kit を作るときに作者の環境を manifest に保存し、デバイス側で
受信時に board mismatch を warning で出す、という運用を可能にする。

manifest を見直して見つけた既存の不備:
- volume が manifest に一切載っていなかった (deviceWiper は per-event の
  KitEvent.deviceWiper だけだった)
- ハードウェア型番が manifest に載っておらず、再現性確認が手作業

## 横断的に同セッションで入った関連変更

- **studio**:
  - `src/types/library.ts`: `KitTargetDevice` interface 新設 + `KitDefinition.targetDevice` field
  - `src/utils/kitExporter.ts`: manifest.target_device に追加フィールドを undefined-safe に出力
  - `src/stores/libraryStore.ts`: kit import 時に target_device を読み戻す
  - `src/components/kit/KitManager.tsx`: kit details に折り畳み "Target Device"
    入力欄を追加 (board / FW min/max / volume_level / wiper / steps + デバイス
    から取り込みボタン)
- **device-firmware**:
  - `instructions/instructions-fire-mode-and-target-device-202604280210.md` 新設
    (タスク 2 として manifest target_device 検証を依頼)

## 検証状況

- contracts 単体での schema validation は行っていない (この repo に test 機構が
  まだない)。Studio export を新スキーマで通すことは
  Studio 側の `npm run build` (型チェック) で確認済。
- 後方互換: 旧 manifest (`target_device: {firmware_version_min: ...}` だけ) は
  `additionalProperties: false` 配下で問題なく通る。新フィールドはすべて optional。

## この repo のエージェントへのアクション

1. 上記 2 ファイルの diff を確認
2. fixtures/sample-kit-manifest.json にも例として board / volume_* を入れるかは
   author judgement (今回は触っていない — fixture にはユーザー側の最小限を残す方が
   schema validation の sanity check になる)
3. `kit-tools` repo (もし schema を同期している場合) も新フィールドに対応するか
   確認 (kit-tools 側は今回のセッションでは触っていない — 必要なら別指示書)
4. 問題なければ本ファイルを `instructions/completed/` に移動
