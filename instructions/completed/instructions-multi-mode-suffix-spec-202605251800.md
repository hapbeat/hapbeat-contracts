# Kit manifest を `command_events` / `stream_events` の 2 bucket に再構成 (schema 2.0.0)

**起点セッション:** workspace `hapbeat-studio` (2026-05-25)
**起点 commit:** `hapbeat-studio` 4dd0362 "feat(kit): KitEvent を library から独立化 + multi-mode + Deploy/Save 分離"
**関連:** [[multi-mode-manifest-read]] (unity-sdk 側), DEC-023 (mode field 導入), DEC-028 (kit name = id)
**優先度:** 高 — Studio が現在出力する `.fire` / `.clip` suffix 付き manifest を unity-sdk / device-firmware が正しく読めない。本指示書で根本的に schema を再設計する。

> **背景**: 当初は「`events: {}` 内の key に `.fire` / `.clip` suffix を付けて multi-mode を表現する」案で進めようとしたが、これは性質の違う 2 種類のイベント (device がコマンドを受け取る command と、SDK が UDP stream を送るだけの stream_clip) を 1 つの dict に押し込めるための **serialization hack** だった。bucket を上位で分離することで suffix・mode フィールド・firmware の mode filter がすべて不要になることが判明したため、こちらに方針変更。

---

## 課題の本質

現状の `events: {...}` には device の挙動が違う 2 種類が混在している:

| 種別 | device 視点 | wire 上の eventId |
|---|---|---|
| `command` | flash 焼き込み → kit_loader が event_id_hash でテーブル lookup → 再生 | **必要**: PLAY/STOP packet に乗る (`message-format.md:42,53`) |
| `stream_clip` | device は eventId を受け取らない (STREAM_BEGIN/DATA で PCM のみ受信) | **不要**: STREAM_BEGIN に eventId フィールド無し (`message-format.md:105-118`) |

→ 2 種類を 1 つの dict に混ぜているせいで:
- BOTH モード (1 つの authored event を両方で出す) の表現に suffix hack が必要になる
- 各 entry に `mode` フィールドを足す必要がある
- firmware kit_loader が `mode != "command"` を skip する filter を持つ必要がある (`kit_loader.cpp:324-341`)
- schema regex も `.fire` `.clip` suffix で 4 segments まで許す必要が出てくる

## 新 schema (2.0.0)

`events` を廃止し、上位で 2 bucket に分離する。

```jsonc
{
  "schema_version": "2.0.0",
  "version": "1.0.0",
  "name": "mykit",
  "target_device": { "firmware_version_min": "0.1.0" },

  "command_events": {                                  // ← device の event table。wire eventId はこれのキー
    "mykit.hit": {
      "clip": "hit.wav",                               // bare filename → install-clips/hit.wav
      "description": "中強度の打撃",
      "tags": ["impact"],
      "parameters": { "intensity": 0.8, "loop": false, "device_wiper": 64 }
    }
  },

  "stream_events": {                                   // ← SDK のみ参照。device は無関係
    "mykit.hit": {                                     // command_events と同じ eventId OK = BOTH モード
      "clip": "hit.wav",                               // bare filename → stream-clips/hit.wav
      "description": "...",
      "parameters": { "intensity": 0.8, "loop": false }
    },
    "mykit.rain": {
      "clip": "rain_loop.wav",
      "parameters": { "intensity": 0.3, "loop": true }
    }
  },

  "install_clips": {                                   // command_events の参照 WAV metadata (現状維持)
    "hit.wav": { "duration_ms": 150, "sample_rate": 16000, "channels": 1, "format": "pcm_s16le" }
  }
}
```

### 確定済み設計事項

1. **bucket 名**: `command_events` / `stream_events`
2. **clip フィールド表記**: bare filename。bucket から subdir を自動解決
   - `command_events.<id>.clip` → `install-clips/<clip>`
   - `stream_events.<id>.clip` → `stream-clips/<clip>`
   - サブディレクトリ表記 (`subdir/foo.wav`) は引き続き許可
3. **stream_source は廃止**。`stream_events.<id>.clip` は必須
4. **`mode` フィールド廃止**。bucket で意味が決まる
5. **`events` フィールド廃止**。schema 2.0.0 で破壊的変更
6. **wire spec への波及**: 既存 `message-format.md` のままで整合済み (PLAY/STOP は eventId 持つ / STREAM_BEGIN は持たない)。本指示書では「`command_events` のキーが PLAY/STOP の wire eventId」「`stream_events` のキーは SDK 内部ラベル (wire には乗らない)」を `kit-format.md` に明記する
7. **後方互換は作らない** (contracts CLAUDE.md 方針: pre-release のため旧 alias 無し)

## 必要な変更

### 1. `specs/kit-format.md` (大幅改訂)

#### 削除
- `## events オブジェクト` セクション全体
- 「### mode (string, optional, default: "command")」セクション
- `stream_source` への言及全般

#### 追加 / 改訂

**新セクション**: `## command_events / stream_events`

```markdown
## command_events / stream_events

Kit のイベント定義は **device が ID を直接扱うか否か** で 2 bucket に分離する。

### command_events (object, required)

Device が baked clip を再生するイベントの辞書。**device は manifest 読み込み時に
このキー (eventId) をハッシュ化して event table を構築する**。SDK は PLAY/STOP
packet の `event_id` フィールドにこれらのキーを乗せて送信する。

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `clip` | string | はい | install-clips/ 配下の WAV ファイル名 (bare filename。サブディレクトリ可) |
| `description` | string | いいえ | このイベントの説明 |
| `tags` | string[] | いいえ | 分類用タグ |
| `parameters.intensity` | number | いいえ | 0.0〜1.0、default 1.0 |
| `parameters.loop` | boolean | いいえ | default false |
| `parameters.device_wiper` | integer | いいえ | 0–127 |

`clip` の値は install-clips/ 直下の bare filename (例: `"hit.wav"`)。サブディレクトリを
使う場合は `"impacts/hit.wav"` のような相対パスを許す。

### stream_events (object, optional)

SDK がホストから UDP audio stream で送信するイベントの辞書。**device はこれらの
キーを認識しない**。STREAM_BEGIN/DATA packet には eventId は含まれず、SDK 側の
binding label としてのみ使用される。

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `clip` | string | はい | stream-clips/ 配下の WAV ファイル名 (bare filename。サブディレクトリ可) |
| `description` | string | いいえ | このイベントの説明 |
| `tags` | string[] | いいえ | 分類用タグ |
| `parameters.intensity` | number | いいえ | 0.0〜1.0、default 1.0 |
| `parameters.loop` | boolean | いいえ | default false |

`clip` は **必須**。`stream-clips/` 配下の bare filename (例: `"rain_loop.wav"`)。
SDK は実行時にこの WAV を読み出してチャンク分割し UDP で device に送信する。

### 同一 eventId が両 bucket に存在する場合

`command_events.<id>` と `stream_events.<id>` が同じキーを持つことを **許可** する。
これは「同じ意味的イベント (`mykit.hit`) を device baked 再生でも SDK stream 再生でも
扱える」ことを意味する (Studio の BOTH モードに相当)。

SDK は EventEntry の mode 設定に応じてどちらの bucket を参照するかを選択する。
`command_events` の参照は wire 上で PLAY packet として、`stream_events` の参照は
SDK 内部の AudioClip → UDP stream として実行される。

### intensity / parameters の重複

両 bucket に同じ eventId が存在する場合、parameters は **bucket ごとに独立** に
読まれる。Studio の現実装では同じ値を両方に書き出すが、規定としては「読む側は
自分が使う bucket の値のみ参照する」とする。
```

**サンプル更新**: `## manifest.json の例` を新スキーマで書き直す（command-only / stream-only / BOTH のサンプルを各 1 件含む）。

### 2. `schemas/kit-manifest.schema.json` (構造変更)

- top-level `required` に `command_events` を追加 (`stream_events` は optional)
- `events` プロパティを削除
- `command_events` と `stream_events` を patternProperties で定義。値の `clip` は両者で required
- `mode` プロパティを削除
- `additionalProperties: false` で旧 `events` の混入を防ぐ

eventId パターン (`patternProperties` のキー regex) は **現行のまま** で良い:
```
^([a-z][a-z0-9_-]{0,63}/)?[a-z][a-z0-9_-]{0,63}(\.[a-z][a-z0-9_-]{0,63}){1,3}$
```
suffix 廃止で 3 segments 制限内に収まる。

### 3. `fixtures/sample-kit-manifest.json`

- 新スキーマで書き直し
- command-only event 1 つ、stream-only event 1 つ、BOTH event 1 つを含むサンプル

### 4. `docs/decision-log.md`

新 DEC エントリ (e.g. DEC-031): "Kit manifest を `command_events` / `stream_events` 2 bucket に再構成 (schema 2.0.0)"

記録内容:
- 旧 `events` + `mode` field 構造の問題点 (suffix hack、firmware の mode filter、wire eventId の意味混線)
- 採択した bucket 分離設計
- 影響範囲と移行戦略 (後方互換無し、各 repo で同時 cut over)

### 5. `specs/message-format.md` (小規模追記)

PLAY (0x01) / STOP (0x02) の `event_id` フィールド説明に追記:
> このフィールドの値は kit manifest の `command_events` キーと一致する必要がある。
> `stream_events` のキーは SDK 内部のラベルであり wire には乗らない。

STREAM_BEGIN (0x30) の説明に追記:
> stream イベントの識別は session レベル (送信元の SDK が 1 session = 1 stream を管理) で
> 行われ、packet に eventId フィールドは含まれない。

### 6. `specs/kit-install-protocol.md` (確認のみ)

OTA 転送経路で `events` 名を decoding していないか確認。していなければ変更不要。
していれば schema 2.0.0 に対応。

## 副次影響 (各 repo の追従指示書)

### hapbeat-unity-sdk
- 起票済: `instructions-multi-mode-manifest-read-202605251800.md`
- `HapbeatManifestIntensity.ParseEvents` を 2 bucket reader に書き換え
- `KitManifestEvent.mode` は bucket 由来 (`"command"` / `"stream_clip"`) で確定設定
- (eventId × mode) tuple で match
- 詳細は当該指示書を参照

### hapbeat-device-firmware
- `src/kit_loader.cpp:313-341` を `command_events` 専用 reader に変更
  - `doc["events"]` → `doc["command_events"]`
  - mode filter (line 324-341) を **削除** (この bucket には command しか来ない)
  - `stream_events` は完全に無視 (firmware は触らない)
- ファーム version は major bump 候補 (kit format 破壊変更)
- 別途 instructions を起こす (本指示書 merge 後)

### hapbeat-studio
- `kitExporter.ts` を 2 bucket emit に書き換え
  - `composeSuffixedEventId` / `KIT_EVENT_MODE_SUFFIX` を **削除**
  - `KitEventMode` 型を `'command' | 'stream_clip'` に縮退、`stream_source` 関連を削除
  - emit 時、KitEvent.modes に基づいて `command_events` と `stream_events` に振り分け
- 既存 kits の migration: `migrateKit` を v2 化 (legacy `events` を新 bucket に振り分ける一発変換)
- 別途 instructions を起こす

### hapbeat-helper
- 転送のみで manifest 解釈無し。**変更不要** (確認のみ)

### hapbeat-bridge
- 同上。**変更不要** (確認のみ)

## Acceptance

- [ ] `kit-format.md` を 2 bucket 構造で全面改訂、`mode` field 記述削除
- [ ] `kit-manifest.schema.json` を 2 bucket 構造に変更、`additionalProperties: false` で旧 `events` を弾く
- [ ] `fixtures/sample-kit-manifest.json` を新スキーマで作り直し、ajv validation 通過
- [ ] `message-format.md` に wire scope の明記を追記
- [ ] `docs/decision-log.md` に DEC-031 (or similar) 追加
- [ ] hapbeat-unity-sdk / hapbeat-device-firmware / hapbeat-studio それぞれに追従 instructions が起票済
- [ ] schema_version は 2.0.0 (破壊的変更)

## 関連参照

- 起点 commit: hapbeat-studio @ 4dd0362
- 旧 spec の該当箇所:
  - `hapbeat-contracts/specs/kit-format.md:81-247` (events / mode セクション)
  - `hapbeat-contracts/schemas/kit-manifest.schema.json:81-160` (events patternProperties)
  - `hapbeat-contracts/specs/message-format.md:42,53,105-118` (PLAY/STOP/STREAM の event_id 扱い)
- 旧 firmware の mode filter (削除予定): `hapbeat-device-firmware/src/kit_loader.cpp:324-341`
- 旧 Studio emit (rewrite 予定): `hapbeat-studio/src/utils/kitExporter.ts:101-145`
- 旧 unity-sdk parser (rewrite 予定): `hapbeat-unity-sdk/Editor/HapbeatManifestIntensity.cs:363-435`
