# cue 表（イベント → 効果音・触覚の割り当て表）仕様

バージョン: `schema_version` 1（2026-10-14、DEC-095）。Hapbeat Studio の Editor / Scene はベータで、この仕様も Unity / Unreal SDK が cue の実行を持つまでは変わりうる。

schema: [`schemas/cue-table.schema.json`](../schemas/cue-table.schema.json)（構造）、[`schemas/cue-inventory.schema.json`](../schemas/cue-inventory.schema.json)（§10 のイベントの一覧）。値の範囲と相互の規則は本書 §6 で定め、`hapbeat-helper cues validate` と Studio が同じ規則で検証する。

## 1. 位置づけ

- **cue** = ゲーム内の 1 つのイベント（足音、咆哮、ボタンを押した等）。cue ごとに、効果音（sfx）を 0〜1 つと、触覚の route（Kit の clip × 装着位置 × 倍率）を 0 個以上持つ。
- cue 表は、Hapbeat Studio（Editor のイベントパネル、Scene タブ）とゲームの間で、割り当てをやり取りする形式。表に書かれた内容が「決定済み」の正本で、ゲームはこの表どおりに鳴らす。
- 触覚の素材（clip）は Kit に入る（[`kit-format.md`](kit-format.md)）。Kit は clip しか持たない。cue → clip・装着位置・倍率・効果音の対応はこの表が持つ。
- 作業の流れ: Studio の Editor でイベントごとに音を決め、次に触覚を決める → Scene タブで録画の流れに合わせて確かめる → ゲームが表と WAV を取り込む。

## 2. ファイル

- 1 プロジェクトに 1 つの JSON ファイル（UTF-8、2 スペース字下げ、末尾改行。Studio は未知のフィールドを保ったまま書き戻す）。
- 触覚の WAV はゲームプロジェクト内の clip フォルダに `<clip>.wav`、効果音の WAV は sound フォルダに `<Sound>.wav` で置く。フォルダの場所は Scene の設定（[`scene-recording.md`](scene-recording.md) の `viewer-lib.json` `paths`）が示す。

## 3. 名前

| 対象 | 規則 | 例 |
|---|---|---|
| cue | `^[a-z][a-z0-9_]*$` | `footstep`、`feed_loop` |
| variant | `^[a-z][a-z0-9_]*$`。ゲームと記録では `<cue>:<variant>` | `footstep:approach` |
| clip | `^[a-z][a-z0-9_-]*$`（[`event-id.md`](event-id.md) の `<file-name>` と同じ） | `roar`、`grab_light` |
| sound | `^[A-Za-z][A-Za-z0-9_]*$`（エンジンの資産名に使える文字） | `Roar_A`、`impactPunch_heavy_000` |
| kit | [`kit-format.md`](kit-format.md) §4 の Kit 名 | `trex-kit` |

## 4. 構造

```jsonc
{
  "schema_version": 1,
  "kit": "trex-kit",
  // syncMs = その素材の同期点（ファイル先頭からの ms、省略 = 0）。§7
  // clip_gain = 素材の強さの補正（§9）。この欄だけ Kit の manifest と同じ snake_case
  "clips":  { "<clip>":  { "clip_gain": 0..1, "loop": bool, "description": "...", "syncMs": 0.. } },
  // 音ファイルごとの素材の強さの補正（省略 = 1）
  "sounds": { "<Sound>": { "clip_gain": 0..1, "syncMs": 0.. } },
  "cues": {
    "<cue>": {
      "description": "...",
      "loop": false,                     // true = 続いて鳴る cue（撫でる、送りの音など）。§5.6
      "sfx": { "sound": "<Sound>", "volume": 0..2 } | null,
      "haptics": [ { "clip": "<clip>", "at": "hand|both|pos_*", "gain": 0..2 } ],
      "variants": { "<variant>": { ... } },          // §5.3
      "variation": { ... },                          // §5.4
      "distanceFalloff": { ... } | null,             // §5.5
      "emit": { "during": "<loop cue>", "intervalSec": 0.05..30, "jitterPct": 0..100 },  // §5.7
      "review": { "sfx": "tentative|approved", "haptics": "tentative|approved" }          // §5.8
    }
  }
}
```

### 4.1 `clips`

| フィールド | 型 | 必須 | 意味 |
|---|---|---|---|
| `clip_gain` | number 0..1 | ✓ | 素材の強さの補正。Kit の manifest の `clip_gain` と同じ意味（WAV はフルスケールで書き、強さはここで持つ）。Kit を持つプロジェクトでは Kit の値の写し（§9.1）。cue 表のほかの欄は camelCase だが、Kit の manifest と同じ値だと読めるよう、この欄は `clip_gain` |
| `loop` | boolean | ✓ | ループ再生する clip。ループの cue だけが使え、単発の cue は `loop: false` の clip だけを使う |
| `description` | string | | 説明 |
| `syncMs` | number 0..600000 | | 同期点（§7） |

### 4.2 `sounds`

| フィールド | 型 | 必須 | 意味 |
|---|---|---|---|
| `clip_gain` | number 0..1 | ✓ | 音の素材の強さの補正（§9）。エントリの無い音は 1 |
| `syncMs` | number 0..600000 | | 同期点（§7） |

### 4.3 sfx（効果音）

| フィールド | 型 | 意味 |
|---|---|---|
| `sound` / `sounds` | string / string[] | 鳴らす音（★を付けた素材）。複数のときは発火ごとに 1 つを選ぶ（§5.4）。両方は書かない |
| `alternates` | string[] | ★を付けていない控え。ゲームも Studio も鳴らさない |
| `volume` | number 0..2 | アプリの倍率（`app_gain` の部品。§9。必須。通常は 1） |
| `levelMap` | object | ループの cue だけ。§5.6 |

### 4.4 route（触覚）

| フィールド | 型 | 意味 |
|---|---|---|
| `clip` / `clips` | string / string[] | 鳴らす clip（★を付けた素材）。`clips` は発火ごとに 1 つを選ぶ。両方は書かない |
| `alternates` | string[] | ★を付けていない控え |
| `at` | string | 装着位置。§4.5 |
| `gain` | number 0..2 | アプリの倍率（`app_gain` の部品。§9。必須。通常は 1） |
| `levelMap` | object | ループの cue だけ。§5.6 |

### 4.5 `at`（装着位置）

| 値 | 鳴らす所 |
|---|---|
| `hand` | 発火のたびにゲームが渡す「動いた側」の手首。左なら `pos_l_wrist`、右なら `pos_r_wrist`、両手なら両方。ゲームが動いた側を渡さないときは両方 |
| `both` | 両手首（`pos_l_wrist` と `pos_r_wrist`）。動いた側によらない |
| `pos_*` | [`device-addressing.md`](device-addressing.md) §3 の部位（`pos_neck` など）。その部位の Hapbeat |

ゲームは `hand` / `both` / 部位を、実際の送信先（ターゲット文字列）に置き換えてよい（例: プレイヤーごとの `player_N`）。

## 5. 意味

### 5.1 未定と「なし」

- cue に `sfx` / `haptics` のキーが無い = **未定**（まだ決めていない）。
- `"sfx": null` = 音なし、`"haptics": []` = 触覚なし。どちらも決定済み。
- ゲームは、未定もなしも鳴らさない。

### 5.2 ★と控え

- `sound` / `sounds` と route の `clip` / `clips` は「★を付けた、鳴らす素材」で、先頭が代表。
- ★を全部外した sfx / route は、`sound(s)` / `clip(s)` を持たず `alternates` だけになる。ゲームも Studio もそれを鳴らさない。決定ではないので、Studio は一覧で印を付ける。
- `alternates` も空の sfx / route は不正。

### 5.3 variants（状況別）

- `variants.<variant>` は元の cue を引き継ぎ、書いたフィールドだけを丸ごと上書きする。書けるのは `description`、`sfx`、`haptics`、`variation`、`distanceFalloff`、`review` と、下の倍率。
  - キーが無い = 元の cue をそのまま使う。`null` / `[]` = この状況では鳴らさない。
- 倍率（引き継いだ素材だけに使う。自分の `sfx` / `haptics` を持つときは使えない）:
  - `sfxVolume` 0..2: 引き継いだ sfx の `volume` に掛ける。
  - `hapticsGain` 0..2: 引き継いだ各 route の `gain` に掛ける。
  - `rampTo` 0..2: 一続きの発生の間に、開始の倍率（`sfxVolume` / `hapticsGain`、省略 = 1）からこの値まで変える。`rampCurve`（§8 の形、既定 `linear`）で補間する。ゲームは場面の進み具合で、Studio は一続きの何回目かで補間する。
  - `rampSteps` 0..2 の配列（1〜64 個）: 1 発ずつの倍率（一続きの何回目か、足りなければ最後の値）。`rampTo` / `rampCurve` の代わりに使う。
- ゲームは `<cue>` か `<cue>:<variant>` で鳴らす。無い variant 名が来たら、元の cue で鳴らして警告を出す。
- 同じ出来事の程度違い（強弱など）は、cue を分けずに variant にする（例: `guard_glove:soft` / `guard_glove:hard`）。音と触覚は別々に「共有」（variant に `sfx` / `haptics` を書かず、差は `sfxVolume` / `hapticsGain` で付ける）か「分ける」（variant に自分の `sfx` / `haptics` を書く）かを選ぶ。程度違いの variant では、素材を持つのは親か各 variant かのどちらか一方にする（書き方の約束で、検証のエラーにはしない）。状況別の variant（親が既定として単独でも鳴り、variant がその場面だけ上書きする）は、親と variant の両方に書いてよい。
- ゲームの取り込みは、引き継ぎを展開して variant ごとの再生情報に書き出してよい。

### 5.4 variation（揺らぎ）

| フィールド | 範囲 | 意味 |
|---|---|---|
| `gainJitterDb` | 0..12 | 発火ごとに ±この dB の一様乱数を、触覚と音の両方に掛ける |
| `pitchJitterSt` | 0..12 | 音のピッチを ±半音 |
| `rateJitterPct` | 0..50 | 触覚 clip の再生速度を ±%（周波数と長さが一緒に変わる） |
| `pick` | `random` / `roundRobin` | 複数素材の選び方（既定 `random`。`random` は直前と同じものを避ける） |
| `paired` | boolean | true = 音と触覚を同じ番号どうしで組にして選ぶ（`sounds[i]` と各 route の `clips[i]`）。鳴らす sfx（引き継ぎを含む）が必要で、`null` や未定ではいけない。★のある音と、★のある各 route の素材の数が同じであること。音に★が無い（控えだけの）ときは、各 route が自分で選ぶ |

- variant にも書ける（丸ごと上書き）。
- ループの cue では `gainJitterDb` だけが効く。ループの途中で選び直さない。

### 5.5 distanceFalloff（距離）

- `{ "nearCm": n, "farCm": f, "farGain": g, "curve": "<§8>" }`。0 ≤ nearCm < farCm、farGain 0..2。
- 倍率 = `1 + (farGain − 1) × curve(t)`、`t = clamp((距離 − nearCm) / (farCm − nearCm), 0, 1)`。音と触覚の両方に掛ける。
- ゲームは発火時のプレイヤーとの距離（cm）を使う。Studio は記録の `dist` を使い、無ければ 1 として扱う。
- variant に書けば上書き、`null` で無効。

### 5.6 ループの cue

- `"loop": true` の cue は、ゲームが開始・停止し、その間ずっと鳴る。route には `loop: true` の clip だけを使う。sfx を持てば音もループする。
- ゲームはループに **入力値**（0 以上。撫でる速さ、送りの速さなど）を渡し続ける。入力 0 = 止まっている。
- `levelMap`（sfx と各 route、任意）: `{ "points": [[input, output], ...], "intercept": 0..4, "curve": "<§8>" }`。
  - 点は 1〜16 個。input > 0 で昇順・重複なし。output は 0..4。
  - (0, intercept) と各点を input の順に結び、区間ごとに `y = y0 + (y1 − y0) · c((x − x0) / (x1 − x0))` で補間する（c は §8）。最後の点より大きい input は、最後の区間の両端を結ぶ傾きで直線に延ばす。出力は 0..4 に収める。
  - input 0 は常に 0。intercept 省略 = 0、curve 省略 = linear、levelMap 省略 = 出力は input そのもの。

### 5.7 emit（自動発生）

- 単発の cue に書ける。`during` のループの cue が鳴っている（入力 > 0）間、ゲームがこの cue を `intervalSec × (1 ± jitterPct %)` 秒ごとに自分で鳴らす。
- Studio は記録のループのレベルから、同じ規則で発生を作って鳴らす。

### 5.8 review

- 割り当ての確認状態。`tentative`（仮、既定）/ `approved`（ユーザーが確認した）。ゲームの再生には影響しない。variant にも書ける。

## 6. 検証の規則（schema の外）

1. `kit` は Kit 名の規則に合う。
2. `clips` の名前・`clip_gain`・`loop`・`syncMs` が §3 / §4.1 に合い、`<clip>.wav` が clip フォルダにある。
3. `sounds` の名前・`clip_gain`・`syncMs` が §3 / §4.2 に合い、`<Sound>.wav` が sound フォルダにある。
4. cue と variant の名前が §3 に合う。
5. sfx: `sound` と `sounds` は片方だけ。★が無いなら `alternates` が 1 つ以上。`sounds` は空でない。参照する音が `sounds` の名前の規則に合い、WAV がある。`volume` 0..2。`alternates` に同じ名前が 2 回出ない、★の音と重ならない。
6. route: `clip` と `clips` は片方だけ。★が無いなら `alternates` が 1 つ以上。参照する clip が `clips` にあり、その `loop` が cue の `loop` と一致する。`at` が §4.5 の値。`gain` 0..2。`alternates` は `clips` の名前で、重複・★との重なりが無い。
7. `levelMap` はループの cue の sfx / route にだけ書け、§5.6 の形に合う。
8. `variation` の値が §5.4 の範囲。`paired: true` なら、引き継ぎを含めて実際に鳴らす sfx がある（`null`・未定でない。★の音か控えがある）。★の音があるなら、★の素材を持つ各 route の数がその数とそろう。
9. variant の `sfxVolume` / `hapticsGain` / `rampTo` は 0..2 で、引き継ぐ素材にだけ使う（自分の `sfx` を持つ variant に `sfxVolume` は書けない、自分の `haptics` を持つ variant に `hapticsGain` は書けない）。`rampTo` と `rampSteps` は、`sfx` か `haptics` の少なくとも一方を引き継ぐ variant にだけ書ける。`rampCurve` は `rampTo` と一緒に。`rampSteps` は 1〜64 個の 0..2 で、`rampTo` / `rampCurve` と同時に書かない。variant は `loop`・`emit`・`variants` を持てない。
10. `distanceFalloff` は 0 ≤ nearCm < farCm、farGain 0..2、curve は §8。
11. `emit` は単発の cue にだけ書け、`during` はループの cue、`intervalSec` 0.05..30、`jitterPct` 0..100、ほかのキーを持たない。
12. `review` のキーは `sfx` / `haptics`、値は `tentative` / `approved`。

## 7. 同期点（syncMs）

- `clips.<clip>.syncMs` / `sounds.<Sound>.syncMs` は、その素材の中で「ここで音と触覚を合わせる」位置（ファイル先頭からの ms、0 以上・ファイル長以下、省略 = 0）。既定は Studio が検出した鳴り始め。
- 1 回の発生で鳴らす音 s と各 route の clip c_r について `d_r = syncMs(s) − syncMs(c_r)` を求め、`base = min(0, min_r d_r)` とする。音を `−base` ms、route r を `d_r − base` ms 遅らせて鳴らす（頭は削らない）。音が無い・★が無いときは遅らせない。素材を選んだ後（random / roundRobin / paired の後）に計算する。
- 再生環境の補正（音と触覚の出力遅延の差）は cue 表に入れない。各アプリが機器ごとの値を持ち、上の遅れに足す。

## 8. 補間の形（rampCurve・distanceFalloff.curve・levelMap.curve）

t ∈ [0, 1] → [0, 1]:

| 値 | 式 |
|---|---|
| `linear` | t |
| `easeIn` | t²（後半で急に変わる） |
| `easeOut` | 1 − (1 − t)²（早めに変わる） |
| `easeInOut` | smoothstep: t²(3 − 2t) |
| `sigmoid` | 0.5 + 0.5 · tanh(6(t − 0.5)) / tanh(3)（より急な S 字） |

## 9. 出力の強さ

- 式は [`kit-format.md`](kit-format.md)「強さの式（正本）」: `output = clip × app_gain × device_volume`、`clip = WAV × clip_gain`。
- WAV = 形（常にピーク約 −0.5 dBFS に正規化）、`clip_gain` = 素材の強さの補正（WAV と 2 つで 1 組）。
- `app_gain` = 再生するアプリが掛ける倍率の積。cue 表では route の `gain`・sfx の `volume`、variant の `hapticsGain`・`sfxVolume`・ramp（`rampTo`・`rampSteps`）、`distanceFalloff`、`levelMap` の出力、`gainJitterDb` の乱数がその部品で、ゲームが発生ごとに掛ける倍率（SDK の API の `gain` 引数、Scene の記録の `events[].gain`）も掛ける。どれも名前は変えない。
- 触覚の送る値は `clamp(clip_gain × app_gain, 0, 1)`（掛けるのは送る側だけ。本体は `clip_gain` を知らない）。音（sfx）も同じ式で、音の `clip_gain` に `app_gain` を掛ける。
- Studio の画面では、3 つの枠を「クリップ（素材）」「アプリ」「本体」と呼ぶ。素材の強さ（`clip_gain`）を変えるのは Studio のエディタ（Kit）で、Scene は `app_gain` の部品だけを変える。

### 9.1 素材の強さの元

- **Kit を持つプロジェクト**（`kit` の Kit がプロジェクトにある）: 触覚の素材の強さの元は、Kit の manifest の Event ID `<kit>.<clip>` のイベントの `parameters.clip_gain`（`events` にあればその値、無ければ `stream_events` の値。省略 = 1）。Studio のエディタで決める。
  - cue 表の `clips.<clip>.clip_gain` は、その**写し**。再生する側（Studio の Scene など）は Kit の値を使う。
  - Studio は写しを Kit の値にそろえる（cue 表を書く時に写す）。写しが Kit と違っていれば、Kit の状態として出す。
  - Kit に無い clip は、cue 表の値を使う。
- **Kit の無いプロジェクト**（ゲームの記録を PC から流すだけなど）: cue 表の `clips.<clip>.clip_gain` が元。
- 音（`sounds`）の素材の強さの元は、常に cue 表の `sounds.<Sound>.clip_gain`（Kit は音を持たない）。

## 10. イベントの一覧と、Event Map からの初版

SDK の Event Map（Unity・Unreal の項目）から cue 表の初版を作る規則（DEC-101）。`hapbeat-helper cues scan`（Unity）がイベントの一覧（inventory）を書き、`hapbeat-helper cues init` がこの規則で表と記録の `bindings`（[`scene-recording.md`](scene-recording.md) §6）を作る。一覧は、エージェントや人が手で書いてもよい（Unreal、独自の cue の層を持つゲームなど）。

schema: [`schemas/cue-inventory.schema.json`](../schemas/cue-inventory.schema.json)。

```jsonc
{
  "schema_version": 1,
  "engine": "unity",
  "project": "handdemo",
  "maps": [
    { "path": "Assets/Samples/HandsDemoLeftEventMap.asset", "id": "d7dd6680a2c34f1e9b0c5d4e3f2a1b0c", "referenced": true },
    { "path": "Assets/Samples/HandsDemoEventMap.asset", "id": "35f4a02a9e8d4c7b6a5f4e3d2c1b0a99", "referenced": false }
  ],
  "events": [
    {
      "source": "unity:d7dd6680a2c34f1e9b0c5d4e3f2a1b0c/6a24573fe8fc487a88a93a3871cc25e7",
      "map": "d7dd6680a2c34f1e9b0c5d4e3f2a1b0c",
      "name": "GrabLight",
      "loop": false,
      "target": "player_1/pos_l_wrist",
      "gain": 1.0,
      "wav": "Assets/Samples/Clips/grab-right.wav",
      "clip_gain": 0.08,
      "where": ["HandsDemoScene.unity: Left Hand/Grab (HapbeatUnityEventTrigger)"],
      "note": ""
    }
  ],
  "warnings": []
}
```

### 10.1 一覧の項目

| フィールド | 必須 | 意味 |
|---|---|---|
| `schema_version` | ✓ | `1` |
| `engine` | ✓ | `unity` / `unreal` / `godot` / `js` / `python` / `other` |
| `project` | | プロジェクト名（[`scene-recording.md`](scene-recording.md) §2 の `project`） |
| `maps` | | 読んだ Event Map `[{ "path", "id", "referenced" }]`。`id` は map の識別子（Unity は asset の guid）。`referenced: false` = シーン・prefab などのどこからも参照されていない map で、その項目は `events` に入れない |
| `events` | ✓ | 項目ごとに 1 件（下の表） |
| `warnings` | | 読み取りで気づいたこと（文字列） |

`events[]`:

| フィールド | 必須 | 意味 |
|---|---|---|
| `source` | ✓ | 項目の識別子（scene-recording §5.2。Unity は `unity:<map の guid>/<項目の id>`）。一覧の中で重ならない。識別子が無い項目は `events` に入れず、`warnings` に書く |
| `map` | | この項目の map（`maps[].id`） |
| `name` | ✓ | SDK の項目の表示名 |
| `cue` | | 付ける cue の名前（`<cue>` か `<cue>:<variant>`）。人やエージェントが名前を決めた項目にだけ書く（`cues scan` は書かない）。省略 = §10.2 |
| `loop` | ✓ | ループの項目 |
| `target` | ✓ | SDK の項目の宛先の文字列（[`device-addressing.md`](device-addressing.md)）。空 = 全員（broadcast） |
| `gain` | ✓ | SDK の項目の倍率（0 以上） |
| `wav` | | 触覚の WAV（プロジェクトのルートからの相対パス）。無い = 手元に素材が無い |
| `clip_gain` | | 素材の強さの補正 0..1（Kit の manifest の `clip_gain`）。SDK の項目の `gain` には焼き込まず、別に書く。省略 = 1 |
| `levelMap` | | ループの項目の入力 → 出力（§5.6 の形）。SDK の binding から直せたとき（§10.4 の 2） |
| `where` | | この項目を鳴らす所（シーン・prefab の中の GameObject と trigger など）。空 = 見つからない（コードから鳴らしている場合がある） |
| `note` | | 自由記述 |

### 10.2 名前

項目の cue の名前は、次の順で決める。

1. 一覧の `cue`。
2. 記録の設定（scene-recording §6）の `bindings` に、その項目の `source` があれば、その binding の `cue`（人が直した名前を守る）。
3. `name` から作る: camelCase の境目（小文字か数字の後の大文字の前と、大文字の連続の後の「大文字＋小文字」の前）に `_` を入れる → 小文字にする → `a-z`・`0-9` 以外を `_` にする → 続く `_` を 1 つにし、両端の `_` を除く → 先頭が数字なら `c_` を付ける。空になったら `cue_` と、`source` の項目の識別子の英数字の先頭 8 文字。
   - 例: `GrabLight` → `grab_light`、`UI-Click-Light` → `ui_click_light`、`HTTPRequest` → `http_request`、`2ndHit` → `c_2nd_hit`。

### 10.3 項目をまとめる

同じ cue と variant になった項目を、1 つの cue（か variant）にまとめる。宛先は `target` を `/` で分け、[`device-addressing.md`](device-addressing.md) §3 の部位の名前と同じセグメントがちょうど 1 つあれば、それを部位とする（`*` や `pos_*` は部位ではない）。部位より前と後のセグメント（`player_N`・`group_M` など）を「部位のほかの宛先」とする。

まとめてよいのは、鳴り方が変わらないときだけ:

1. 部位・部位のほかの宛先・`loop`・`gain`・WAV の中身・`clip_gain`・`levelMap` が全部同じ → route 1 つ。
2. 左右の手首の組: 部位が `pos_l_wrist` の項目と `pos_r_wrist` の項目がどちらもあり、部位のほかは 1 と同じ → `at: "hand"` の route 1 つ。

まとめられないとき:

- 同じ cue の項目（variant を含む）の `loop` が違うなら、名前の決め方によらず誤り。
- それ以外で、名前を §10.2 の 1・2 で決めた項目を含むなら、誤り。
- 名前を §10.2 の 3 で作った項目だけなら、一覧の順に、まとめられる項目どうしを組にし、2 つ目以降の組の cue の名前に `_2`、`_3` … を付けて別の cue にする（警告）。付けた名前がほかの cue と重なるなら、重ならない番号まで進める。

### 10.4 中身

1. **cue**: ループの項目なら `"loop": true`。`description` は項目の `name`。効果音（`sfx`）は書かない（未定）。
2. **route**:
   - `at`: §10.3 の部位。§10.3 の 2 なら `hand`。部位のほかの宛先は cue 表に入らない（ゲームが送り先に置き換える。§4.5）。その値は初版の報告に書く。
   - 宛先が全員（`target` が空）か、部位が決まらないとき、`wav` が無いとき: route を作らない。cue は `haptics` を未定（§5.1）にする。variant は `"haptics": []`（キーを書かないと元の cue の route を引き継いで、別の所で鳴るため）にし、`review.haptics` を `tentative` にする。どちらも初版の報告に書き、人が決める。
   - `gain` = 項目の `gain`。2 を超えたら 2 にする（警告）。
   - `levelMap` = 項目の `levelMap`（ループの cue のときだけ）。入力は、SDK の binding が曲線に渡す値（Unity は binding の `inputMin` を 0、`inputMax` を 1 に直し、0..1 に収めた値）。記録の `level`（scene-recording §5.2）も同じ物差しで書く。入力をそのまま出す形も `"points": [[1, 1]]` と書く。同じ項目に形の違う binding が複数あるときは書かず、警告する。
3. **clip**: 名前は cue の名前（variant は `<cue>_<variant>`）。clip のフォルダ（`hapbeat-scene.json` の `lib.paths.clips`）にその名前の WAV が中身の違うもので既にあるか、表にその名前の clip が既にあるときは、`_2`、`_3` … を付ける（名前は一覧の順に決める）。`clip_gain` = 項目の `clip_gain`（省略 = 1）、`loop` = cue の `loop`、`description` = `from <wav>`。WAV を clip のフォルダに `<clip>.wav` として写す（元が写す先と同じファイルなら写さない）。
4. **variant**: `<cue>:<variant>` の項目は、その variant に自分の `haptics` を書く。元の cue の名前だけの項目が無ければ、元の cue の `haptics` は未定のまま。
5. **review**: `haptics` を書いた cue と variant に `{ "haptics": "tentative" }`。
6. **新しい表**: `kit` は `<project>-kit`（`project` が無ければ道具に渡した名前）、`sounds` は `{}`。

### 10.5 記録の `bindings`

各項目の `source` → その cue（variant を含む）。§10.3 の 2 でまとめた項目には、部位に合わせて `hand: "left"` / `"right"` を付ける。既にある binding は、一覧の `cue` で名前を決めた項目のときだけ書き換える（§10.2 の 2 で名前を決めた項目の binding は、そのまま残る）。

### 10.6 既にある表に足すとき

- 既にある cue・variant・clip・sound の、キーのある値は変えない（Studio や人が決めた内容を守る）。
- `haptics` が未定の cue・variant には、§10.4 の route と clip を書いてよい（Studio の「cue 表を作る」が作った空の cue を埋める）。
- 既にある cue の `variants` に、無い variant を足してよい。
- 足す clip は、足した route が使うものだけ。
- 既にある cue と `loop` が違う項目は、その variant を含めて足さず、警告する。

### 10.7 初版の報告

道具は、人が決める項目を一覧にして出す: 宛先が全員か部位の決まらない項目、WAV の無い項目、部位のほかの宛先の値、名前を変えた項目（§10.3）、`gain` を収めた項目、書かなかった `levelMap`、参照されていない map、`where` が空の項目。
