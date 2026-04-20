# Instructions: Kit manifest に mode フィールド追加 + STREAM_BEGIN spec 同期

**発行日:** 2026-04-18
**起票:** hapbeat-unity-sdk セッション
**根拠:** workspace `docs/decision-log.md` DEC-023 / DEC-024

## 背景

Kit (内部名 Pack) の manifest.json は現在 Command mode の event のみを前提にしている。SDK 側 (Unity 等) で StreamClip / StreamSource mode の event も authoring したいため、全モードを Kit に含める設計に変更する。さらに STREAM_BEGIN の実装（Unity SDK `HapbeatProtocol.cs:231`）が contract spec より先行しているため同期する。

## タスク

### 1. `specs/pack-format.md` の events フィールド拡張

`parameters` オブジェクトの既存表はそのまま残しつつ、event の値オブジェクトに `mode` フィールドを追加する。

追加仕様:

```markdown
### mode (string, optional, default: "command")

event の再生モード。SDK が Kit を読み込む際、どのような方法で触覚再生を行うかを決定する。

- `"command"` (default): device 側に焼き込んだ clip を eventId で再生する従来モード。`clip` フィールド必須。pack-tools が device binary を生成する際はこの mode の event のみ含める。
- `"stream_clip"`: SDK (Unity 等) が AudioClip を PCM データとして UDP STREAM_BEGIN/DATA/END で送信するモード。`clip` フィールドは optional（Kit に音源を同梱して SDK が Asset として import する場合に指定）。device 側には焼き込まれない。
- `"stream_source"`: SDK が live AudioSource をキャプチャして UDP ストリーミングするモード。`clip` フィールドは不要。device 側には何も焼き込まれない。

device firmware は mode != "command" の event を load 時にスキップする (後方互換のため、mode が無い既存 manifest は command として扱う)。
```

events オブジェクトの表にも `mode` 行を追加:

```markdown
| `mode` | string | いいえ | 再生モード (`"command"` / `"stream_clip"` / `"stream_source"`)。既定 `"command"` |
| `clip` | string | 条件付き | mode=command では必須。stream_* では optional（Kit 同梱の wav を指すパス） |
```

clip 必須性を `mode` に依存させる注記を追加。

### 2. `schemas/pack-manifest.schema.json` の更新

events 内の event オブジェクトに `mode` プロパティを追加。

```json
{
  "properties": {
    "mode": {
      "type": "string",
      "enum": ["command", "stream_clip", "stream_source"],
      "default": "command",
      "description": "Playback mode. 'command' = device plays baked clip, 'stream_clip' = SDK streams clip over UDP, 'stream_source' = SDK streams live AudioSource capture."
    },
    "clip": { /* 既存 */ }
  },
  "allOf": [
    {
      "if": { "properties": { "mode": { "const": "command" } } },
      "then": { "required": ["clip"] }
    }
  ]
}
```

mode = command 時のみ clip を required に。

### 3. intensity 仕様の補足（pack-format.md §5 intensity 節）

既存記述 `最終出力 = WAV振幅 × intensity × SDK_gain × デバイス音量` はそのまま維持。以下を追記:

- **SDK_gain の範囲**: 1.0 を基準として 0.0 ～ 約 2.0。1.0 で intensity そのままの強さ、2.0 で intensity の倍（ただし最終値は SDK 側で clip される）
- **stream_clip / stream_source mode での intensity**: `device 側で stored clip の振幅に乗算される` のではなく、`SDK 側が STREAM_BEGIN.gain または PLAY.gain の float32 値に intensity を乗算して送信する`
- **デバイス音量**: SDK は感知しない。Studio で kit authoring 時点のデバイス wiper 値を `parameters.device_wiper` に記録しており、再現するユーザーは当該 wiper 値にデバイスを合わせることで制作者の意図した強度を得られる

### 4. `specs/message-format.md` §4 STREAM_BEGIN の修正

実装（`hapbeat-unity-sdk/Runtime/HapbeatProtocol.cs:231` の `BuildStreamBeginPayload`）に合わせて、**STREAM_BEGIN payload に `gain` フィールドと optional `target` フィールドを明記**する。

現行表:

```
| sample_rate | uint16 | サンプルレート（Hz、例: 16000） |
| channels | uint8 | チャンネル数（1=mono, 2=stereo） |
| format | uint8 | オーディオフォーマット（0=PCM16, 1=IMA_ADPCM） |
| total_samples | uint32 | 総サンプル数（0=不明。情報用、省略可） |
```

↓ 以下のように修正:

```
| sample_rate | uint16 | サンプルレート（Hz、例: 16000） |
| channels | uint8 | チャンネル数（1=mono, 2=stereo） |
| format | uint8 | オーディオフォーマット（0=PCM16, 1=IMA_ADPCM） |
| total_samples | uint32 | 総サンプル数（0=不明。情報用、省略可） |
| gain | float32 | 再生ゲイン（0.0 〜 1.0）。intensity × SDK_gain × binding を SDK 側で計算した値 |
| target | null-terminated string | optional。ターゲットアドレス（省略時は全台）。詳細は device-addressing.md 参照 |
```

固定部分のサイズは 12 bytes (既存 8 + gain 4)。target は可変長。

### 5. Kit/Pack 用語統一の decision 追記

`specs/pack-format.md` の冒頭か末尾に以下の注釈を追加:

```markdown
## 用語注記

- **Pack**: 本文書で定義する内部仕様の正式名称
- **Kit**: UI / designer 向け表記。Studio や各 SDK の UI では Kit と呼称する
- 両者は同じ概念を指す。将来のリファクタリングで名称を `Kit` に統一する予定（decision-log DEC-023 参照）
```

### 6. Working directory convention の追記（任意）

pack-format.md §3 に以下の「運用上の推奨」節を追加（normative ではなく informative）:

```markdown
### 3.1 運用上の推奨

各 SDK は Kit を ホストプロジェクトの asset 配下 に配置することを推奨する。例:

- Unity: `Assets/HapbeatKits/<pack-id>/`
- Unreal: `Content/HapbeatKits/<pack-id>/`

これにより Studio の working directory と SDK の asset 読み込みパスが一致し、二重管理が発生しない。詳細は decision-log DEC-024 参照。
```

## 完了条件

- [ ] pack-format.md §5 events に `mode` 追記、clip の必須条件を mode 依存に
- [ ] pack-manifest.schema.json に mode enum + conditional required 追加
- [ ] pack-format.md §5 intensity 節に SDK_gain range + device_wiper 記述補足
- [ ] message-format.md §4 STREAM_BEGIN に gain + optional target 追記
- [ ] Kit/Pack 用語注記追加
- [ ] (optional) working directory 推奨追記
- [ ] 本 instructions ファイルを `instructions/completed/` に移動

## 検証

- `schemas/pack-manifest.schema.json` の validation が既存 fixtures (`hand-demo-kit/manifest.json` 等) で通ること
- message-format.md の STREAM_BEGIN 仕様が `hapbeat-unity-sdk/Runtime/HapbeatProtocol.cs:BuildStreamBeginPayload` の payload 構造と一致すること (sample_rate uint16 → channels uint8 → format uint8 → total_samples uint32 → gain float32 → optional target null-terminated)

## 後続タスク

- hapbeat-studio: mode 選択 UI、stream event の clip optional 対応（別指示書）
- hapbeat-pack-tools: device binary build 時に mode=command のみフィルタ（別指示書）
- hapbeat-device-firmware: manifest loader で mode スキップロジック追加（別指示書）
- hapbeat-unity-sdk: HapbeatKitAsset / HapbeatEventMap.linkedKit 実装（contracts 確定後）
