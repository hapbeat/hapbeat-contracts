# Event ID 仕様

バージョン: 1.0.0

> **2026-06 改定 (DEC-040)**: 正準フォーマットを `<category>.<name>`（旧）から
> **`<kit-name>.<file-name>`** に改めた。実装（Studio の event_id 自動合成・各 SDK）は
> 早期にこの形へ移行済みで、本改定は spec を実態に合わせるもの。旧 `<category>.<name>`
> 形式（`impact.hit` 等）と standard categories 表は **deprecated**。リリース前のため
> 後方互換エイリアスは設けない。

## 概要

Event ID は、Hapbeat エコシステム全体で触覚イベントを一意に識別する文字列識別子である。
SDK からデバイスへ再生指示（PLAY）を送る際、また Kit 内で clip と触覚パターンを紐づける際の
共通キーとして機能する。

## 正準フォーマット

```
<kit-name>.<file-name>
```

- **`<kit-name>`** — その clip が属する Kit の `name`（= Kit ID, `kit-format.md` §4）。
  on-disk のフォルダ名・`manifest.json` の `name`・wire の `kit_id` と同一値。
- **`<file-name>`** — Kit 内の clip ファイル名から拡張子（`.wav`）を除いた basename。
- 区切りは **`.`（ドット）1 個**。

### 例

| Event ID | Kit | clip ファイル |
|---|---|---|
| `sample-kit.sine_100hz` | `sample-kit` | `sine_100hz.wav` |
| `showcase-kit.z1_pin_hit` | `showcase-kit` | `z1_pin_hit.wav` |
| `my-game.sword_slash` | `my-game` | `sword_slash.wav` |

Event ID は **Studio が clip から自動合成**する（ユーザーが手で組み立てない）。`<kit-name>` が
名前空間を兼ねるため、異なる Kit 間で ID が衝突しない。

### 構文規則

| 要素 | 規則 |
|------|------|
| `<kit-name>` | `kit-format.md` §4 の Kit 命名規則と同一: `^[a-z][a-z0-9-]*$`（英小文字始まり、英数字・ハイフン。アンダースコア不可） |
| `<file-name>` | 英小文字始まり、英数字・アンダースコア `_`・ハイフン `-`: `^[a-z][a-z0-9_-]*$` |
| 区切り文字 | `.`（ドット）1 個のみ |
| 大文字 | 使用不可（正規化のため小文字のみ） |
| `<file-name>` 先頭 | **英字始まり**（数字始まり不可）。例: `100hz` ではなく `sine_100hz` のように letter 始まりにする |
| ID 全体最大長 | 255 文字 |

### 正規表現

```
^[a-z][a-z0-9-]*\.[a-z][a-z0-9_-]*$
```

## 予約 Kit 名

以下の Kit 名は Hapbeat 公式用途に予約されている。コンテンツ開発者は使用しない。

| 予約 Kit 名 / プレフィックス | 用途 |
|---|---|
| `sample-kit` | 公式の **動作確認用 Kit**（`specs/sample-kit.md`）。`sample-kit.sine_100hz` が正準の疎通確認イベント |
| `showcase-kit` | 公式の showcase Kit（SDK サンプル用） |
| `hapbeat-*` | Hapbeat 公式 Kit の名前空間（予約） |

## Event ID の使用例

### SDK からの再生指示

```
HapbeatManager.Play("sample-kit.sine_100hz");   // Unity
hb.play("showcase-kit.z2_door_slam")            // Python / JS
Hapbeat.play("my-game.sword_slash", 0.6f);      // Arduino / Godot
```

### Kit manifest 内での参照（schema 2.0.0）

```json
{
  "name": "sample-kit",
  "events": {
    "sample-kit.sine_100hz": {
      "clip": "sine_100hz.wav",
      "parameters": { "intensity": 1.0 }
    }
  }
}
```

### OSC メッセージでの使用

```
/hapbeat/play sample-kit.sine_100hz
```

## Event ID のライフサイクル

### 定義

- Event ID は Kit の manifest 内で定義され、`<kit-name>.<file-name>` 規約に従う
- 1 つの Kit 内で同一 Event ID の重複定義は禁止
- `<kit-name>` が一意であることで、異なる Kit 間の ID 衝突を回避する

### 解決

- デバイス側で Event ID → clip ファイルへの解決を行う
- 解決は Kit install 時にインデックスを構築し、再生時はインデックス参照で行う
- 未解決の Event ID を受信した場合、デバイスはエラーログを記録し、無視する

### 変更

- **既存 Event ID の中身（紐づく clip）変更** — Kit 差し替えのみで可能。アプリ再ビルド不要
- **Event ID の新規追加** — Kit manifest への追記（= clip 追加）で可能
- **Event ID の名前変更 / 削除** — clip ファイル名 or Kit 名の変更を伴う。公開インターフェースの破壊的変更となる

## 命名のベストプラクティス

1. **clip ファイル名を意味のある名前に** — event id がそのまま `<kit-name>.<file-name>` になるので、`a1.wav` ではなく `sword_slash.wav`
2. **英小文字 + `_` / `-`** — `sword_slash` / `door-slam`
3. **数字始まりを避ける** — `100hz.wav` ではなく `sine_100hz.wav`（event id セグメントは英字始まり）
4. **Kit 名は短く一意に** — `<kit-name>` が名前空間なので、プロジェクトを表す短い名前にする
