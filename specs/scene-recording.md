# Scene の記録形式（ゲームの録画と cue の発生）

バージョン: `schema_version` 1（2026-10-14、DEC-095）。Hapbeat Studio の Scene / Editor はベータで、この仕様も変わりうる。

schema: [`schemas/scene-session.schema.json`](../schemas/scene-session.schema.json)、[`schemas/scene-viewer-lib.schema.json`](../schemas/scene-viewer-lib.schema.json)、[`schemas/scene-viewer-data.schema.json`](../schemas/scene-viewer-data.schema.json)。

## 1. 位置づけと流れ

ゲームのプレイを録画し、cue（[`cue-table.md`](cue-table.md)）が鳴った時刻と一緒に残す。Hapbeat Studio の Scene タブと Editor は、この映像に合わせて cue 表どおりに効果音と触覚を鳴らし、割り当てを確かめ・直す。

```
ゲーム（記録モード / 記録スクリプト）
  → session.json ＋ 画面（PNG 連番か動画）              §2
  → hapbeat-helper scene build
  → <プロジェクト>/Saved/HapticViewer/                   §3
       viewer-lib.json / viewer-data.json / full_replay.mp4
  → Hapbeat Studio（Scene / Editor）
```

- `<プロジェクト>` はゲームのプロジェクトのルート（Unreal は `.uproject` のあるフォルダ、Unity は `Assets` の親）。`Saved/` はバージョン管理と、エンジンの資産取り込みの対象外にする。
- Studio は `Saved/HapticViewer/` だけを読み、cue 表と WAV は `viewer-lib.json` の `paths` から読み書きする。

## 2. 記録（`session.json`）

記録する側（SDK の記録モード、またはプロジェクトの記録スクリプト）が書く。

```jsonc
{
  "schema_version": 1,
  "project": "trex-encounter",
  "fps": 30,
  "frames": "Saved/HapticRecord/frames",     // f<frame>.png の連番（frame は 0 から）。video と片方だけ
  // "video": "Saved/HapticRecord/replay.mp4", // fps 一定の動画。先頭のフレームが frame 0
  "events": [
    { "frame": 120, "cue": "footstep:approach", "hand": "left", "gain": 1.0, "dist": 830, "note": "" }
  ],
  "levels": {                                 // ループの cue があるときだけ
    "columns": ["hold:level:left", "hold:level:right"],
    "rows": [[0, 0], [0.4, 0], ...]           // 1 フレーム 1 行（rows[i] = frame i）
  },
  "lib": { ... }                              // viewer-lib.json の中身（§3.1）
}
```

| フィールド | 必須 | 意味 |
|---|---|---|
| `schema_version` | ✓ | `1` |
| `project` | ✓ | プロジェクト名（`^[a-z][a-z0-9-]*$`） |
| `fps` | ✓ | 録画のフレームレート（固定タイムステップ。§4） |
| `frames` / `video` | どちらか 1 つ | 画面。パスはプロジェクトのルートから。`frames` は記録専用のフォルダで、`f<frame>.png` 以外を置かない（ビルド後にその PNG を消す。§4） |
| `events` | ✓ | cue の発生（時刻順） |
| `events[].frame` | ✓ | 発生したフレーム（0 以上の整数） |
| `events[].cue` | ✓ | `<cue>` か `<cue>:<variant>` |
| `events[].hand` | | 動いた側: `left` / `right` / `both`。`at: "hand"` の route の行き先（cue-table §4.5）。省略 = 動いた側の指定なし（`at: "hand"` は両手首） |
| `events[].gain` | | その発生にゲームが掛けた倍率（省略 = 1） |
| `events[].dist` | | 発生時のプレイヤーとの距離（cm）。`distanceFalloff` に使う |
| `events[].note` | | 自由記述（Studio が表示する） |
| `levels.columns` | | 列名。§2.1 |
| `levels.rows` | | 1 フレーム 1 行。各行は列と同じ数の 0 以上の数 |
| `lib` | ✓ | §3.1 |

### 2.1 ループの cue のレベル

ループの cue（`loop: true`）は、鳴り始めた（入力が 0 から上がった）フレームに `events` を 1 件書き（場面の目印になる。`note` は任意）、ゲームが渡す入力値（cue-table §5.6）を毎フレーム記録する。止まったときの発生は書かない（入力が 0 に戻る）。列名は次の形:

| 列名 | 意味 |
|---|---|
| `<cue>:level` | 入力値（左右の区別なし） |
| `<cue>:level:left` / `<cue>:level:right` | 左手・右手それぞれの入力値 |
| `<cue>:rate` / `<cue>:rate:left` / `<cue>:rate:right` | 任意。clip の再生速度（1 = 等速） |

Studio はこの列名からループの cue とレイヤーを組み立てる（`viewer-lib.json` の `layers` は省略してよい）。

## 3. Studio が読むもの（`Saved/HapticViewer/`）

`hapbeat-helper scene build` が §2 から作る。

### 3.1 `viewer-lib.json`

プロジェクトの設定。必須は 4 つで、ほかは省略すると既定値になる。

| フィールド | 必須 | 既定 | 意味 |
|---|---|---|---|
| `schema_version` | ✓ | | `1` |
| `title` | ✓ | | 表示名 |
| `project_name` | ✓ | | `session.json` の `project` |
| `paths` | ✓ | | `{ "cues": <cue 表の JSON>, "clips": <触覚 WAV のフォルダ>, "sounds": <効果音 WAV のフォルダ> }`。プロジェクトのルートからの相対パス |
| `at` | | cue-table §4.5 の全値 | 画面で選べる装着位置（絞り込み） |
| `loop_at` | | `at` | ループの cue で選べる装着位置 |
| `families` | | `[]` | cue の系統 `[{ "label", "color": "#rrggbb", "cues": [...] }]`。タイムラインの色分け。cue の指定は下の注を参照 |
| `ticks` | | `[]` | 細かく何度も鳴る cue（場面の一覧で単独に扱う） |
| `layers` | | 列名から作る | `[{ "cue", "level": [左, 右の列番号], "rate": [左, 右の列番号] or null, "colors": [...] }]`。左右の区別が無い cue は同じ列番号を 2 つ並べる。§2.1 の列名に従わない記録のときだけ書く |
| `moment_rules` | | 制限なし | 場面の一覧の数の制限 `{ "max": { "<cue>": n }, "min_gap_s": { "<cue>": s }, "default_max": n or null }`。cue の指定は下の注を参照 |
| `import_command` | | なし | 「ゲームへ取り込み」に表示するコマンド |
| `record_command` | | なし | 「録画」に表示するコマンド |

- `families[].cues`・`ticks`・`moment_rules` のキーには `<cue>` か `<cue>:<variant>` を書く。`<cue>` はその cue と全 variant に当たり、`<cue>:<variant>` はその variant だけに当たる。両方に当たるときは `<cue>:<variant>` を使う。

### 3.2 `viewer-data.json`

```jsonc
{
  "schema_version": 1,
  "fps": 30,
  "frames": 5400,                    // 通し映像のフレーム数
  "video": "full_replay.mp4",
  "events": [ { "t": 4.0, "name": "footstep:approach", "hand": "left", "gain": 1.0, "dist": 830 } ],
  "levels": { "columns": [...], "rows": [[...], ...] }   // §2 と同じ。ループの cue が無ければ省略
}
```

- `events[].t` = `frame / fps`（秒）。`name` は §2 の `cue`。`hand` / `gain` / `dist` / `note` は §2 と同じ。
- cue ごとに事前に切り出した動画は持たない。場面の一覧は Studio が発生時刻から作る（§3.4）。

### 3.3 `full_replay.mp4`

- H.264（yuv420p）、フレームレート一定 = `fps`。frame i が時刻 i / fps。音声トラックは不要（Studio が cue 表から鳴らす）。

### 3.4 場面の一覧（Studio の動作、参考）

- 0.2 秒以内に続く cue を 1 つの場面にまとめ、最初の cue の 2.0 秒前から 3.0 秒後までを区間にする。`ticks` の cue は単独で場面にする。
- `moment_rules` があれば、cue ごとの場面の数と間隔を絞る。

### 3.5 その他のファイル

- `studio-scene-ui.json` は Studio のパネル配置などの保存先で、本仕様の対象外。再録画でも消さない。

## 4. 記録する側の約束

1. **固定タイムステップ**: frame i のゲーム時刻は i / fps。発生の `frame` は、その cue が鳴ったフレーム。
2. **全発生を記録する**: ゲームが cue を鳴らすたびに 1 件。variant 名、動いた側、倍率、距離を、ゲームが鳴らすときと同じ値で残す。ループの cue は鳴り始めに 1 件と、§2.1 の列を毎フレーム。
3. **鳴らさない**: 記録中は Hapbeat への送信と効果音を止める。ゲームの処理（cue の判定・揺らぎの乱数など）は止めない。
4. **全 cue を起こす**: 人がプレイするか、台本のリプレイを流す。台本は cue ごとに確実に起こる操作を並べ、意図しない cue が鳴ったら失敗にするのがよい。
5. **画面の一時ファイル**: `frames` のフォルダは記録ごとの専用にする。`hapbeat-helper scene build` は通し映像を作った後、そのフォルダの `f<frame>.png` だけを消し、空になったフォルダを消す（`--keep-frames` で残す）。ほかのファイルには触れない。
