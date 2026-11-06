# Scene の記録形式（ゲームの録画と cue の発生）

バージョン: `schema_version` 1（2026-10-14、DEC-095）。Hapbeat Studio の Scene / Editor はベータで、この仕様も変わりうる。

schema: [`schemas/scene-session.schema.json`](../schemas/scene-session.schema.json)、[`schemas/scene-viewer-lib.schema.json`](../schemas/scene-viewer-lib.schema.json)、[`schemas/scene-viewer-data.schema.json`](../schemas/scene-viewer-data.schema.json)、[`schemas/scene-viewer-edits.schema.json`](../schemas/scene-viewer-edits.schema.json)（§3.5）、[`schemas/scene-log-record.schema.json`](../schemas/scene-log-record.schema.json)（§5）、[`schemas/scene-project.schema.json`](../schemas/scene-project.schema.json)（§6）。

## 1. 位置づけと流れ

ゲームのプレイを録画し、cue（[`cue-table.md`](cue-table.md)）が鳴った時刻と一緒に残す。Hapbeat Studio の Scene タブと Editor は、この映像に合わせて cue 表どおりに効果音と触覚を鳴らし、割り当てを確かめ・直す。

```
ゲーム（記録モード / 記録スクリプト）
  → 記録のログ ＋ 画面（PNG 連番か動画）                §5
  → hapbeat-helper scene session（hapbeat-scene.json）    §6、cue 表との突き合わせ §7
  → session.json                                         §2
  → hapbeat-helper scene build
  → <プロジェクト>/Saved/HapticViewer/                   §3
       viewer-lib.json / viewer-data.json / full_replay.mp4
  → Hapbeat Studio（Scene / Editor）
```

- `<プロジェクト>` はゲームのプロジェクトのルート（Unreal は `.uproject` のあるフォルダ、Unity は `Assets` の親）。`Saved/` はバージョン管理と、エンジンの資産取り込みの対象外にする。
- Studio は `Saved/HapticViewer/` だけを読み、cue 表と WAV は `viewer-lib.json` の `paths` から読み書きする。
- Studio は記録（`viewer-lib.json`・`viewer-data.json`・映像）を書き換えない。人が発生ひとつずつに付けた強さと時刻は `viewer-edits.json`（§3.5）に書き、再生する側が記録に重ねる。撮り直し（`hapbeat-helper scene build`）は記録だけを作り直し、`viewer-edits.json` には触れない。
- 記録する側が `session.json` を直接書いてもよい（§5 のログを使わない）。その場合も `hapbeat-helper scene check` で §7 の突き合わせができる。
- **動画のプロジェクト**: ゲームの記録を使わず、ある映像（スポーツの中継、VR デモの画面収録など）に触覚を付けるときも、同じ配置（`<プロジェクト>/Saved/HapticViewer/` と §3 の形式）を使う。`viewer-data.json` は記録の出力ではなく、人や AI が書く原本になる。そのプロジェクトでは `Saved/HapticViewer/` の JSON をバージョン管理に入れ、映像は権利と大きさに応じて入れない。

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
  "takes": [                                  // 任意。台本の区切り（§7.1）
    { "start": 0, "end": 90, "label": "take 1: grab the bone", "expect": ["grab"], "allow": [] }
  ],
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
| `takes` | | 台本の区切り。§7.1 |
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
  "levels": { "columns": [...], "rows": [[...], ...] },  // §2 と同じ。ループの cue が無ければ省略
  "chapters": [ { "start": 0, "end": 25, "label": "テニス" } ]   // 任意。§3.2.1
}
```

- `events[].t` = `frame / fps`（秒）。`name` は §2 の `cue`。`hand` / `gain` / `dist` / `note` は §2 と同じ。
- 再生する側は、`viewer-edits.json`（§3.5）があれば、その上書きを重ねてから使う。
- cue ごとに事前に切り出した動画は持たない。場面の一覧は Studio が発生時刻から作る（§3.4）。

#### 3.2.1 `chapters`（任意）

映像の中の区切り（スポーツの種目、デモの段など）。再生する側が、区切りを選んで再生する・その範囲で繰り返すための目印で、触覚の鳴り方は変えない。

| フィールド | 必須 | 意味 |
|---|---|---|
| `start` | ✓ | 始まり（秒、0 以上） |
| `end` | ✓ | 終わり（秒、`start` より大きく、`frames / fps` 以下） |
| `label` | ✓ | 表示名（1 文字以上） |

- 配列の順が表示の順。区切りどうしは重なってよく、隙間があってよい。
- 範囲で繰り返すときは、`end` に達したら `start` へ戻る。区切りの外の発生も、映像の時刻がそこを通れば鳴る。
- §3.4 の場面の一覧（発生時刻から Studio が作る）とは別のもの。

### 3.3 `full_replay.mp4`

- H.264（yuv420p）、フレームレート一定 = `fps`。frame i が時刻 i / fps。
- 音声トラックは任意。ゲームの記録には入れない（効果音は Studio が cue 表から鳴らす）。映像そのものに音がある動画のプロジェクト（§1）では入れてよく、再生する側はそれを番組の音として流してよい。その場合、cue 表の `sfx` は `null` にする（効果音を二重に鳴らさない）。

### 3.4 場面の一覧（Studio の動作、参考）

- 0.2 秒以内に続く cue を 1 つの場面にまとめ、最初の cue の 2.0 秒前から 3.0 秒後までを区間にする。`ticks` の cue は単独で場面にする。
- `moment_rules` があれば、cue ごとの場面の数と間隔を絞る。

### 3.5 `viewer-edits.json`（発生ごとの上書き）

人が Studio の Scene で、発生ひとつずつに付けた強さと時刻。記録とは別に持ち、記録の値の代わりに使う。

```jsonc
{
  "schema_version": 1,
  "firings": [
    { "of": { "name": "roar", "t": 4.0 }, "gain": 0.6 },
    { "of": { "name": "grab", "t": 6.0, "hand": "right" }, "gain": 1.2, "t": 6.05 }
  ]
}
```

| フィールド | 必須 | 意味 |
|---|---|---|
| `schema_version` | ✓ | `1` |
| `firings` | ✓ | 上書きの一覧（順は問わない） |
| `firings[].of` | ✓ | 上書きする発生。記録（§3.2）の `name`・`t`・`hand` をそのまま書く |
| `firings[].gain` | | その発生の `events[].gain` の代わりに使う値（0 以上） |
| `firings[].t` | | その発生の `events[].t` の代わりに使う時刻（秒。0 以上、`frames / fps` 以下） |

- `gain` と `t` の少なくとも 1 つを書く。書かない方は記録の値を使う。
- 発生の見つけ方: `of.name` と記録の `name` が同じ、`of.hand` と記録の `hand` が同じ（どちらも無いのも同じとみなす）、`of.t` と記録の `t` の差が半フレーム（`0.5 / fps`）以内。当てはまる発生が複数あれば、`t` が近いもの（同じなら記録の先のもの）。1 つの発生に当てる上書きは 1 つまでで、`of.t` の早い上書きから順に決める。
- 当てはまる発生が無い上書き（撮り直しで発生が無くなった・時刻が変わったもの）は使わない。消さずに残し、Studio が数を見せて、人が消す。
- 記録の発生（`events`）だけに当てる。ループの cue の入力値（`levels`）と、cue 表の `emit`（[`cue-table.md`](cue-table.md) §5.7）が作る発生には当てない。
- `t` を変えた発生は、新しい時刻で鳴り、場面の一覧（§3.4）にも新しい時刻で入る。
- 書くのは Studio だけで、ファイルを丸ごと書き直す。記録する側と `hapbeat-helper` は書かず、消さない（`scene check` は読まない）。動画のプロジェクト（§1）では、ほかの JSON と一緒にバージョン管理に入れる。
- 再生する側（Studio の Scene・プレイヤー・映像を書き出す道具）は、このファイルを重ねる。重ねないと、Studio で聞いた強さと違って鳴る。

### 3.6 その他のファイル

- `studio-scene-ui.json` は Studio のパネル配置などの保存先で、本仕様の対象外。再録画でも消さない。
- `versions/` は Studio が保存する版（`viewer-edits.json` と cue 表の写し）の置き場で、本仕様の対象外。再生する側は読まない。再録画でも消さない。

## 4. 記録する側の約束

1. **固定タイムステップ**: frame i のゲーム時刻は i / fps。発生の `frame` は、その cue が鳴ったフレーム。
2. **全発生を記録する**: ゲームが cue を鳴らすたびに 1 件。variant 名、動いた側、倍率、距離を、ゲームが鳴らすときと同じ値で残す。ループの cue は鳴り始めに 1 件と、§2.1 の列を毎フレーム。
3. **鳴らさない**: 記録中は Hapbeat への送信と効果音を止める。ゲームの処理（cue の判定・揺らぎの乱数など）は止めない。
4. **全 cue を起こす**: 人がプレイするか、台本のリプレイを流す。台本は cue ごとに確実に起こる操作を並べ、意図しない cue が鳴ったら失敗にするのがよい。台本の区切りと、そこで鳴るべき cue は `takes`（§7.1）に書けば、`hapbeat-helper` が確かめる。
5. **画面の一時ファイル**: `frames` のフォルダは記録ごとの専用にし、記録を始める前にそのフォルダの `f<frame>.png` を消す。`hapbeat-helper scene build` は通し映像を作った後、そのフォルダの `f<frame>.png` だけを消し、空になったフォルダを消す（`--keep-frames` で残す）。ほかのファイルには触れない。

## 5. 記録のログ

記録する側（ゲームのコード、または SDK の発生の通知）は、記録中に起きたことを 1 行に 1 つの JSON（JSON Lines）で書く。`hapbeat-helper scene session` が、このログと §6 の設定から `session.json`（§2）を作る。記録する側は `events`・`levels.rows`・`takes` を組み立てなくてよい。

schema（1 行分）: [`schemas/scene-log-record.schema.json`](../schemas/scene-log-record.schema.json)。

```jsonc
{"t":"start","schema_version":1,"project":"boxing-vr","fps":30}
{"t":"take","frame":0,"label":"take 1: left punch to the glove","expect":["punch_glove:soft"]}
{"t":"cue","frame":45,"cue":"punch_glove:soft","hand":"left","gain":0.82,"note":"1.02 m/s"}
{"t":"cue","frame":60,"source":"unity:d7dd6680a2c34f1e9b0c5d4e3f2a1b0c/6a24573fe8fc487a88a93a3871cc25e7"}
{"t":"level","frame":46,"values":{"push:level:left":0.4}}
{"t":"take_end","frame":90}
{"t":"end","frames":5400}
```

### 5.1 書く場所と読み方

- 専用のファイル（既定 `Saved/HapticRecord/events.jsonl`）か、エンジンのログ（Unity の `Editor.log`・`Player.log`、Unreal の `Saved/Logs/*.log` など）に書く。毎フレーム `level` を書くときは専用のファイルを勧める（Unity の `Debug.Log` は 1 行ごとにスタックトレースを取る）。ブラウザのように書けない環境では、印を付けてコンソールに出し、自動化の道具が行を集める。
- エンジンのログに書くときは、行に印 `HAPBEAT_SCENE `（末尾に空白 1 つ）を付け、その直後に JSON を書く。印より前の文字（エンジンが付ける時刻・カテゴリ）と、JSON の後ろの文字は読まない。
  - Unreal: `UE_LOG(LogTemp, Display, TEXT("HAPBEAT_SCENE %s"), *Json)`
  - Unity: `Debug.Log("HAPBEAT_SCENE " + json)`（`Editor.log` で後ろに続くスタックトレースの行は、印が無いので読まない）
- 読み方:
  - ファイルは UTF-8（先頭の BOM は読み飛ばす）。
  - 印を含む行が 1 行でもあれば、印を含む行だけを読む。無ければ、空でない各行を 1 件とする。そのとき最初の空でない行が JSON として読めなければ、ログではない（`start` が無い誤り）。
  - 読む行の印の後（専用のファイルなら行全体）が JSON として読めなければ誤り（行番号を出す）。
  - 1 つのファイルに何回分かの記録がたまってよい（Unity のエディターで Play を繰り返したときなど）。読むのは最後の `start` から、その後の最初の `end` までで、`end` より後の行は読まない（警告）。

### 5.2 記録の種類

| `t` | 項目 | 意味 |
|---|---|---|
| `start` | `schema_version`（`1`）・`fps`・`project`（任意） | 記録の始まり。§6 の `fps`・`project` と違えば誤り |
| `take` | `frame`・`label`・`expect`（任意）・`allow`（任意） | 台本の 1 区切りの始まり（§7.1） |
| `take_end` | `frame` | 今の区切りの終わり。このフレームは含まない |
| `cue` | `frame`、`cue` か `source` の片方、`hand`・`gain`・`dist`・`note`（任意） | cue の発生。項目の意味は §2 の `events[]` と同じ |
| `level` | `frame`、`values`（`{ "<列名>": 0 以上の数 }`）か、`source`・`value`（0 以上の数）・`hand`（任意）の組 | ループの入力値。書いた列だけ、このフレームから値が変わる |
| `fail` | `reason`・`frame`（任意） | 台本が失敗した（意図しない cue が鳴った、待っても操作が起きないなど） |
| `end` | `frames` | 記録の終わり。全フレーム数（frame は 0 〜 `frames` − 1） |

- `frame` は `start` からのフレーム番号で、`frames` のフォルダの `f<frame>.png` と同じ番号（固定タイムステップ、§4）。
- `cue` は `<cue>` か `<cue>:<variant>`。`source` は SDK の項目の識別子 `<エンジン>:<map の識別子>/<項目の識別子>` で、§6 の `bindings` で cue に直す。
  - Unity: `unity:<Event Map の asset の guid>/<項目の id>`。Event Map を複製すると項目の id もそのまま写るため、map の guid で区別する。
  - ほかのエンジンは、その SDK が決める（同じ発生には、記録のたびに同じ識別子を書く）。
- `source` で書く発生の `gain` は、SDK の項目の倍率（と Kit の強さ）を除いた、ゲームがその発生に掛けた倍率（1 = 項目のとおり）。項目の倍率は cue 表の route の `gain` に入る（[`cue-table.md`](cue-table.md) §10.4）。
- `level`:
  - `values` の列名は §2.1 の形。`source` で書くときは、`bindings` でその cue に直し、`hand`（無ければ binding の `hand`）が `left` / `right` なら `<cue>:level:<hand>`、無ければ `<cue>:level` の列にする。
  - 入力値は、ゲームがループに渡す値（cue 表の `levelMap` の入力と同じ物差し）。
  - 各列は、次にその列が書かれるまで値を保つ。書かれる前の値は、`<cue>:level*` の列は 0、`<cue>:rate*` の列は 1。同じフレームに同じ列が 2 回書かれたら、後の値。
  - 列の順は、§6 の `columns` があればその順（`columns` に無い列は、その後ろに足す）、無ければログに初めて出てきた順。行の数は `end` の `frames`。
- 知らない `t` と項目は無視する（`hapbeat-helper` は警告を出す）。
- 次のどれかなら、`session.json` を作らない: `start` が無い、`end` が無い（記録が最後まで進まなかった）、`fail` がある、§7.2 の誤りがある。

## 6. プロジェクトの設定（`hapbeat-scene.json`）

プロジェクトのルート（§1）に置き、バージョン管理に入れる。§5 のログから `session.json` を作るのに要る、記録ごとに変わらない値を持つ。パスは、このファイルのあるフォルダ（＝プロジェクトのルート）からの相対パス。

schema: [`schemas/scene-project.schema.json`](../schemas/scene-project.schema.json)。

```jsonc
{
  "schema_version": 1,
  "project": "handdemo",
  "fps": 30,
  "frames": "Saved/HapticRecord/frames",
  "log": "Saved/HapticRecord/events.jsonl",
  "capture": "both",
  "columns": ["hold_light:level:left", "hold_light:level:right"],
  "lib": {
    "schema_version": 1, "title": "XRI Hand Demo", "project_name": "handdemo",
    "paths": { "cues": "Assets/HandDemo/Haptics/handdemo-cues.json",
               "clips": "Assets/HandDemo/Haptics/stream-clips", "sounds": "Assets/HandDemo/Haptics/sounds" }
  },
  "bindings": [
    { "source": "unity:d7dd6680a2c34f1e9b0c5d4e3f2a1b0c/6a24573fe8fc487a88a93a3871cc25e7", "cue": "grab_light", "hand": "left" },
    { "source": "unity:5e1c0b9a8f7d4c3b2a1908f7e6d5c4b3/6a24573fe8fc487a88a93a3871cc25e7", "cue": "grab_light", "hand": "right" }
  ]
}
```

| フィールド | 必須 | 意味 |
|---|---|---|
| `schema_version` | ✓ | `1` |
| `project` | ✓ | §2 と同じ |
| `fps` | ✓ | §2 と同じ |
| `frames` / `video` | どちらか 1 つ | §2 と同じ |
| `log` | | §5 のログのファイル（既定 `Saved/HapticRecord/events.jsonl`）。プロジェクトの外にあるエンジンのログは `hapbeat-helper scene session --log` で渡す |
| `capture` | | 記録する側が読む。`game`（既定。ゲームのコードが発生を書く）/ `sdk`（SDK の発生の通知を `source` で書く）/ `both`。`hapbeat-helper` は読まない。`both` は、同じ発生をゲームのコードと SDK の両方が書かないときだけ使う。SDK の通知は鳴り始めしか知らせないので、ループの cue の入力値（`level`）は、どの場合もゲームのコードか台本が書く |
| `columns` | | `levels` の列の順（§5.2）。`lib.layers` を列番号で書くときに使う |
| `lib` | ✓ | §3.1。`project_name` は `project` と同じ |
| `bindings` | | `[{ "source", "cue", "hand" }]`。ログの `source` → cue（`<cue>` か `<cue>:<variant>`）。`hand`（任意）は、ログの記録に `hand` が無いときに使う。同じ `source` を 2 回書かない |

- `session.json` = この設定の `schema_version`・`project`・`fps`・`frames` か `video`・`lib` と、ログから作った `events`・`levels`・`takes`。
- Studio は `hapbeat-scene.json` を読まない（Studio が読むのは §3）。
- `bindings` は `hapbeat-helper cues init` が cue 表の初版と一緒に書く（[`cue-table.md`](cue-table.md) §10.5）。

## 7. 記録と cue 表の突き合わせ

`hapbeat-helper scene check`（と `scene session`）は、記録を cue 表（[`cue-table.md`](cue-table.md)）と比べ、§7.2 の誤りがあれば不合格にする。

- `lib.paths.cues` の cue 表がまだ無いとき（Studio の「cue 表を作る」の前）は、§7.2 の 2・3・6 と §7.3 の 1・2・5 を当てず、警告を出して `session.json` を作る。

### 7.1 台本の区切り（`takes`）

- `session.json` の `takes`（任意）: `[{ "start", "end", "label", "expect", "allow" }]`。§5 のログの `take` / `take_end` から作る。
  - `start` 〜 `end` − 1 のフレームの発生が、その区切りのもの。`take_end` が無い区切りは、次の `take` か `end` で終わる。
  - `expect`（既定 `[]`）: この区切りで必ず鳴る cue。`allow`（既定 `[]`）: 鳴ってもよい cue。
  - 書き方は `<cue>`（その cue と全 variant に当たる）か `<cue>:<variant>`（その variant だけに当たる）。
- 形: `start` < `end`。`start` の昇順に並び、前の区切りの `end` ≤ 次の区切りの `start`（重ならない）。ログで、区切りが開いていないときの `take_end` と、区切りの `take` と同じか前のフレームの `take_end` は誤り。
- 区切りの中の発生は、どれも `expect` か `allow` のどれかに当たること。`expect` の各項目は、区切りの中で 1 回以上鳴ること。
- 区切りの外の発生にも §7.2 の 1〜4 を当てる。区切りの規則は当てない。

### 7.2 誤り

1. §2 の形に合わない（`hapbeat-helper scene build` と同じ検証。`takes` の形を含む）。
2. 発生の cue が cue 表に無い。`<cue>:<variant>` の variant が、その cue の `variants` に無い。
3. ループでない cue（表に無い cue を含む）の level の列がある。鳴ったループの cue に、`<cue>:level`・`<cue>:level:left`・`<cue>:level:right` のどの列も無い。
4. ログから作るとき: `source` が `bindings` に無い（unmapped）。`start` か `end` が無い。`fail` がある。`start` の `fps`・`project` が §6 と違う。読めない行がある（§5.1）。`frames` のフォルダに、番号が `end` の `frames` 以上の `f<frame>.png` がある（前の記録の残り。記録する側は `start` の前にそのフォルダの `f<frame>.png` を消す）。
5. 区切りの規則（§7.1）に反する。
6. 全 cue を求めたとき（`hapbeat-helper` の `--require-all`）: cue 表の cue に、1 回も鳴らなかったものがある（その cue の variant が鳴れば、その cue は鳴ったとみなす）。variant に、1 回も鳴らなかったものがある。`emit`（cue-table §5.7）を持つ cue とその variant は数えない（Studio がループのレベルから作る）。

### 7.3 警告

発生ごとに、その発生で鳴らす route（variant は §5.3 の引き継ぎを展開した後の route）で判断する。`haptics` が未定なら 1・2 は当てない。

1. 鳴らす route に `at: "hand"` があるのに、発生に `hand` が無い（両手首で鳴る）。
2. 鳴らす route に `at: "hand"` が無いのに、発生の `hand` が `left` か `right`（使われない。`both` は警告しない）。
3. `end` より後の行、最後のフレーム（`end` の `frames` − 1）より後の発生。`session.json` に入れない。
4. フレームの順が前後した発生。フレームの順に並べ替える。
5. 鳴らなかった cue と variant（`--require-all` でないとき。数え方は §7.2 の 6 と同じ）。
6. `takes` があるとき、どの区切りにも入らない発生。
