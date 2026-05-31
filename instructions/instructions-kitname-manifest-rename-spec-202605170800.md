# Kit packaging spec: manifest filename を `<kit-name>-manifest.json` に変更

**作成日:** 2026-05-17
**起票元:** hapbeat-studio セッション (workspace worktree `recursing-curie-cd0c3f`)
**優先度:** 低 — 実装は SDK / Studio / Helper で先行決定済。spec を実装に合わせる normative documentation 更新
**関連:**
- `hapbeat-studio/instructions/completed/instructions-kitname-manifest-rename-202605161800.md` (元指示書)
- `hapbeat-helper/instructions/applied/applied-get-info-build-passthrough-202605170740.md` (helper 側追従)
- `hapbeat-pack-tools/instructions/instructions-kitname-manifest-rename-202605170800.md` (pack-tools 追従)

## 背景

複数 Kit が並ぶ環境で `manifest.json` の識別性が悪かったため、各実装が **`<kit-name>-manifest.json`** に統一した:

- ✅ hapbeat-unity-sdk: `HapbeatManifestIntensity.FindKitManifest` / `HapbeatEventMapWindow.DrawManifestPickerField`
- ✅ hapbeat-studio: `kitExporter.manifestFileName` / `localDirectory.findKitManifestHandle`
- ✅ hapbeat-helper: `_find_kit_manifest` / `_looks_like_manifest` + wire 上で `manifest.json` rewrite

contracts 側の spec 文書を実装に追従させる。

## 更新対象

### 1. `kit-format.md` (もしくは pack-format spec)

Kit ZIP の構造を以下に書き換える:

```
<kit_id>/
  <kit_id>-manifest.json      ← (旧: manifest.json)
  install-clips/
    <clip-file>.wav
  stream-clips/
    <clip-file>.wav
```

- 「discovery: preferred `<kit_id>-manifest.json` → fallback `*manifest*.json`」のルールを記述
- 「wire-level (firmware への TCP 転送) では `manifest.json` に rewrite される」点も明記 (firmware は LittleFS に literal `manifest.json` で書き、読み出す)

### 2. `decision-log.md`

新 DEC (例: DEC-031) を追加:

```
## DEC-031 Kit manifest filename を `<kit-id>-manifest.json` に統一 (2026-05-17)

### 判断
Kit フォルダの manifest は host 側 (Unity SDK / Studio / Helper) で
`<kit-id>-manifest.json` を正とする。firmware の LittleFS では
従来通り `manifest.json` を読む (host-side rewrite で吸収)。

### 理由
複数 Kit を 1 プロジェクトで扱う際、すべて `manifest.json` だと OS Explorer や
SDK の picker で識別性が悪い。`<kit-id>-manifest.json` で kit 名前置すると識別性 ↑。

### 影響
- hapbeat-unity-sdk: 実装済
- hapbeat-studio: 実装済
- hapbeat-helper: 実装済 (wire rename)
- hapbeat-pack-tools: 追従指示書起票済
- hapbeat-device-firmware: 影響なし
```

## 完了条件

- [ ] `kit-format.md` (or 相当する spec) を新規約に更新
- [ ] `decision-log.md` に新 DEC を追加
- [ ] 本ファイルを `instructions/completed/` に移動
