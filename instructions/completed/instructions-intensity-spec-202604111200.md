# Instructions: Pack Manifest に intensity / device_wiper を追加

**対象リポジトリ**: hapbeat-contracts
**作成日**: 2026-04-11
**作成元**: hapbeat-studio セッション

## 背景

触覚コンテンツのゲイン設計を整理し、以下の方針を決定した:

### ゲイン3層の整理

```
最終出力 = WAV振幅 × intensity × SDK_gain × デバイス音量
```

| 層 | 責任者 | タイミング |
|---|---|---|
| WAV 振幅 | コンテンツ制作者 | ビルド時（固定） |
| intensity | コンテンツ制作者（Kit内） | ビルド時（固定） |
| SDK gain | アプリ開発者 | 実行時（動的） |
| デバイス音量 | エンドユーザー | 設定時（固定） |

- **intensity**: 制作者が意図した「基準強度」。WAV フルスケールに対する倍率 (0.0–1.0)
- **SDK gain=1.0**: intensity の値で再生 = 制作者の意図通り
- **SDK gain>1.0**: より強く（クリッピングはデバイスの物理限界で自然に制限）

### device_wiper

Kit 内の各イベントに、制作時の Hapbeat デバイスのボリューム（MCP4018 ワイパー値 0–127）を記録。
これにより制作者の体験を完全に再現可能にする。

## pack-manifest.schema.json の変更

`events[].parameters` に以下を追加:

```json
{
  "intensity": {
    "type": "number",
    "minimum": 0.0,
    "maximum": 1.0,
    "default": 1.0,
    "description": "Author's intended base strength. SDK gain=1.0 plays at this intensity."
  },
  "device_wiper": {
    "type": "integer",
    "minimum": 0,
    "maximum": 127,
    "description": "MCP4018 wiper value of the device when this event was tuned. For reproduction reference."
  }
}
```

**注意**: `gain` フィールドは `intensity` に置き換え。後方互換のため `gain` も読み取り可能だが、新規作成時は `intensity` を使用。

## specs/pack-format.md の変更

Parameters セクションに以下を追記:

```
### intensity (number, 0.0–1.0, default: 1.0)

制作者が意図した基準強度。WAV のフル振幅に対する倍率。

- `1.0`: WAV をそのまま再生（デフォルト）
- `0.7`: WAV の 70% の強さ（制作者が「これが中」と判断した値）
- SDK の gain パラメータは intensity に対する追加倍率として適用される

### device_wiper (integer, 0–127, optional)

イベント調整時の Hapbeat デバイスの MCP4018 ワイパー値。
再現性のための参照情報。デバイスが異なるモデルの場合は無視される。
```

## ファイル変更一覧

| ファイル | 変更内容 |
|---------|---------|
| `schemas/pack-manifest.schema.json` | parameters に `intensity`, `device_wiper` 追加 |
| `specs/pack-format.md` | intensity / device_wiper の仕様説明追加 |
