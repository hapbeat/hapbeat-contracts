# cue 表（イベント → 効果音・触覚の割り当て表）仕様

バージョン: `schema_version` 1（2026-10-14、DEC-095）。Hapbeat Studio の Editor / Scene はベータで、この仕様も Unity / Unreal SDK が cue の実行を持つまでは変わりうる。

schema: [`schemas/cue-table.schema.json`](../schemas/cue-table.schema.json)（構造）。値の範囲と相互の規則は本書 §6 で定め、`hapbeat-helper cues validate` と Studio が同じ規則で検証する。

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
  "clips":  { "<clip>":  { "intensity": 0..1, "loop": bool, "description": "...", "syncMs": 0.. } },
  // 音ファイルごとの基準の強さ（省略 = 1）
  "sounds": { "<Sound>": { "intensity": 0..1, "syncMs": 0.. } },
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
| `intensity` | number 0..1 | ✓ | 基準の強さ。Kit の `intensity` と同じ意味（WAV はフルスケールで書き、強さはここで持つ） |
| `loop` | boolean | ✓ | ループ再生する clip。ループの cue だけが使え、単発の cue は `loop: false` の clip だけを使う |
| `description` | string | | 説明 |
| `syncMs` | number 0..600000 | | 同期点（§7） |

### 4.2 `sounds`

| フィールド | 型 | 必須 | 意味 |
|---|---|---|---|
| `intensity` | number 0..1 | ✓ | 基準の強さ。エントリの無い音の強さは 1 |
| `syncMs` | number 0..600000 | | 同期点（§7） |

### 4.3 sfx（効果音）

| フィールド | 型 | 意味 |
|---|---|---|
| `sound` / `sounds` | string / string[] | 鳴らす音（★を付けた素材）。複数のときは発火ごとに 1 つを選ぶ（§5.4）。両方は書かない |
| `alternates` | string[] | ★を付けていない控え。ゲームも Studio も鳴らさない |
| `volume` | number 0..2 | 場面の倍率（既定 1） |
| `levelMap` | object | ループの cue だけ。§5.6 |

### 4.4 route（触覚）

| フィールド | 型 | 意味 |
|---|---|---|
| `clip` / `clips` | string / string[] | 鳴らす clip（★を付けた素材）。`clips` は発火ごとに 1 つを選ぶ。両方は書かない |
| `alternates` | string[] | ★を付けていない控え |
| `at` | string | 装着位置。§4.5 |
| `gain` | number 0..2 | 場面の倍率（既定 1） |
| `levelMap` | object | ループの cue だけ。§5.6 |

### 4.5 `at`（装着位置）

| 値 | 鳴らす所 |
|---|---|
| `hand` | 発火のたびにゲームが渡す「動いた側」の手首。左なら `pos_l_wrist`、右なら `pos_r_wrist`、両手なら両方 |
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
- 同じ出来事の程度違い（強弱など）は、cue を分けずに variant にする（例: `guard_glove:soft` / `guard_glove:hard`）。

### 5.4 variation（揺らぎ）

| フィールド | 範囲 | 意味 |
|---|---|---|
| `gainJitterDb` | 0..12 | 発火ごとに ±この dB の一様乱数を、触覚と音の両方に掛ける |
| `pitchJitterSt` | 0..12 | 音のピッチを ±半音 |
| `rateJitterPct` | 0..50 | 触覚 clip の再生速度を ±%（周波数と長さが一緒に変わる） |
| `pick` | `random` / `roundRobin` | 複数素材の選び方（既定 `random`。`random` は直前と同じものを避ける） |
| `paired` | boolean | true = 音と触覚を同じ番号どうしで組にして選ぶ（`sounds[i]` と各 route の `clips[i]`）。★のある音と、★のある各 route の素材の数が同じであること。音に★が無いときは、各 route が自分で選ぶ |

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
2. `clips` の名前・`intensity`・`loop`・`syncMs` が §3 / §4.1 に合い、`<clip>.wav` が clip フォルダにある。
3. `sounds` の名前・`intensity`・`syncMs` が §3 / §4.2 に合い、`<Sound>.wav` が sound フォルダにある。
4. cue と variant の名前が §3 に合う。
5. sfx: `sound` と `sounds` は片方だけ。★が無いなら `alternates` が 1 つ以上。`sounds` は空でない。参照する音が `sounds` の名前の規則に合い、WAV がある。`volume` 0..2。`alternates` に同じ名前が 2 回出ない、★の音と重ならない。
6. route: `clip` と `clips` は片方だけ。★が無いなら `alternates` が 1 つ以上。参照する clip が `clips` にあり、その `loop` が cue の `loop` と一致する。`at` が §4.5 の値。`gain` 0..2。`alternates` は `clips` の名前で、重複・★との重なりが無い。
7. `levelMap` はループの cue の sfx / route にだけ書け、§5.6 の形に合う。
8. `variation` の値が §5.4 の範囲。`paired: true` なら、引き継ぎを含めて実際に鳴らす sfx と route で数がそろう。
9. variant の `sfxVolume` / `hapticsGain` / `rampTo` は 0..2 で、引き継ぐ素材にだけ使う。`rampCurve` は `rampTo` と一緒に。`rampSteps` は 1〜64 個の 0..2 で、`rampTo` / `rampCurve` と同時に書かない。
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

- WAV = 形（常にピーク約 −0.5 dBFS に正規化）、`intensity` = 素材の基準の強さ、`gain` / `volume`（と variant・距離・ramp・levelMap の倍率）= 場面の倍率。
- 最終出力 = WAV × intensity × 場面の倍率 × デバイス音量（[`kit-format.md`](kit-format.md) の WAV × intensity × SDK gain × 音量 に対応）。
