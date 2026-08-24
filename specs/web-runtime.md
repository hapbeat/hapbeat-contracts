# Web Runtime v1 仕様書

## 1. 範囲

本文書は、Web アプリから意味イベントを送る `hapbeat` client API と、Session Relay を介して Runtime Console がそのイベントを触覚再生へ解決する v1 契約を定義する。Web Runtime の message は**意味を持つ JSON のみ**とし、音声・触覚の bytes を API や relay に持ち込まない。

構成要素は次の 3 つである。

- Web app: `hapbeat.emit` で意味イベントを送る。
- Session Relay: Cloudflare Worker gateway と session 単位の Durable Object (DO) WebSocket が JSON と最新 snapshot を中継する。
- Runtime Console: runtime role でイベントを受け、Runtime config に従って helper/device へ解決する。

Session DO の有効期間は約 15 分（900 秒）である。接続・認証・再接続・snapshot の規則は [`session-relay.md`](session-relay.md) を参照する。

## 2. App API

アプリが利用する公開 API は次の 1 つである。

```js
hapbeat.emit(event, payload?, { targetTime? })
```

| 引数 | 型 | 必須 | 説明 |
|---|---|---:|---|
| `event` | string | yes | 空でないアプリ側の意味イベント名。最大 128 文字。Runtime config の `events` キーと完全一致させる |
| `payload` | JSON value | no | アプリ固有データ。省略できる。PCM、WAV、Kit、asset bytes は指定しない |
| `options` | object | no | v1 で指定できるのは `targetTime` だけ。省略できる |

`options.targetTime` は Runtime-PC scheduler の基準で解決する整数時刻で、`0..9007199254740991`（JavaScript `Number.MAX_SAFE_INTEGER`）の範囲である。過去または現在の targetTime は `0 ms`（即時）として扱い、未来の targetTime だけ現在時刻との差分を検査する。未来の差分が `2147483647` ms を超える targetTime は Runtime Console が拒否する。v1 は device まで同じ時刻で再生されることを保証しない。`target`、`gain`、`delayMs`、`eventId`、`clipAsset` は options や payload で上書きせず、Runtime config から解決する。

`emit` は一過性の通知である。Session Relay は emit を保存せず、再接続または late join 後に replay してはならない (MUST NOT)。

アプリは Hapbeat Event ID、Kit、gain、target、helper protocol を直接扱わない。アプリが指定するのは意味イベント名と任意の JSON payload だけである。

### 2.1 Client-side validation

client API は WebSocket へ送る前に、`event`、`options.targetTime`、payload/options 全体を検証する。検証する上限は event 名 128 文字、JSON nesting depth 16、JSON node 数 4096、JSON string（object key を含む）8192 文字である。`targetTime` は schema の safe-integer 範囲と未来差分の規則に従う。

PCM、WAV、Kit、raw asset bytes またはそれらを表す forbidden-byte field/value（base64・`data:` 等の埋込みを含む）は意味 JSON ではないため拒否する。`options` の未知フィールドも拒否し、`target`、`gain`、`eventId`、`clipAsset` を client API の options/payload から再生制御値として使ってはならない。

いずれかの検証に失敗した `emit` は `throw` し、WebSocket queue への enqueue と送信を行ってはならない (MUST NOT)。

## 3. Runtime config による解決

Runtime config の形式は [`schemas/runtime-config.schema.json`](../schemas/runtime-config.schema.json) である。root は `revision`、`master`、`events` を必須とし、`events` は最大 256 件である。`revision` は JSON safe integer（`0..9007199254740991`）である。

Runtime Console が config import を受けたとき、入力 config の `revision` を管理値として採用してはならない (MUST NOT)。Console は現在の管理 revision に `1` を加えた値を新しい revision として割り当てる。現在の管理 revision が `9007199254740991`（`Number.MAX_SAFE_INTEGER`）に到達している場合は import を拒否する。割り当てた revision を config snapshot の body と envelope の `configRevision` に使い、session 内の strictly increasing を維持する。

未登録の event 名は無効イベントとして扱い、触覚を送信してはならない (MUST NOT)。

`master` は enabled event に対する `{gain,target}` である。`gain` は `0..1`、`target` は次の構造化 object とする。

```json
{
  "player": -1,
  "position": "all",
  "group": -1
}
```

`player` と `group` は `-1`（All）または `1..99`、`position` は `all`、`pos_neck`、`pos_chest`、`pos_abd`、`pos_l_arm`、`pos_r_arm`、`pos_l_wrist`、`pos_r_wrist`、`pos_hip`、`pos_l_thigh`、`pos_r_thigh`、`pos_l_ankle`、`pos_r_ankle` のいずれかである。

各 event entry は `enabled`、`mode`、`gain`、`delayMs` を必須とする。`gain` は `0..1`、`delayMs` は `0..2147483647` の整数である。`mode` は次のいずれかである。

| mode | 必須の解決先 | 動作 |
|---|---|---|
| `fire` | `eventId` | 既存 Kit の Event ID を Runtime Console から発火する |
| `clip` | `clipAsset` | `https://` URL の asset を Runtime Console で取得して再生する |

`enabled=false` の entry、events に存在しない event、または `enabled=true` で選択 mode の解決先が無い entry は無効である。無効な event から触覚を送信してはならない (MUST NOT)。既定動作は no target / no haptic であり、master target を推測したり別 event へフォールバックしたりしてはならない (MUST NOT)。

個別 target は `targetOverride:{enabled,target}` で指定する。`targetOverride` の省略は override off（`enabled=false`）である。`enabled=false` のときは master target を使い、`enabled=true` のときだけ個別 target を使う。

`clipAsset` は `https://` URL だけを受理する。PCM、WAV、Kit archive、その他の asset bytes を WebSocket frame や JSON payload に埋め込んではならない (MUST NOT)。

## 4. CLIP の Runtime Console 処理

CLIP の asset は Runtime Console が CORS を使って HTTPS fetch する。取得した asset は**音声出力へ接続せず**、`OfflineAudioContext` で無音のまま decode し、16 kHz・mono・PCM16 に resample/変換する。変換後の bytes は Session Relay を通さず、既存 helper の `stream_begin` → `stream_data` → `stream_end` へ渡す。

helper への送信先は、Runtime Console が選択した online device の IP を固定・明示して unicast する。helper の送信は初期状態 OFF とし、選択 online IP が 0 台なら**絶対に送信せず、broadcast に fallback しない**。CLIP の開始時に元の IP を保持し、event の変更・disable・cancel で `stream_end` を送る場合も同じ元 IP を使う。

Session または Runtime config を再 Create したときは、Runtime Console の状態を `sendEnabled=false` と選択 online IP 0 台へ戻す。明示的な再選択と送信有効化が行われるまで、再 Create 後も送信・broadcast を行わない。

## 5. Session envelope

JSON WebSocket の text message は [`schemas/session-envelope.schema.json`](../schemas/session-envelope.schema.json) の envelope を使う。binary frame は使用しない。

| フィールド | 型 | 説明 |
|---|---|---|
| `v` | integer | envelope version。v1 は `1` |
| `type` | string | `emit` / `state` / `catalog` / `config` |
| `sessionId` | UUID string | ticket に束縛された session 識別子。接続中に変更できない |
| `clientId` | UUID string | ticket に束縛された client 識別子。接続中に変更できない |
| `messageId` | string (1..128) | `clientId` と組み合わせた冪等性キー |
| `clientSeq` | integer | client ごとの単調増加シーケンス |
| `configRevision` | integer | この message が参照する runtime config revision |
| `body` | object | `type` ごとの JSON body |
| `serverSeq` | decimal string | Relay が fan-out 時に付与する値。client は送信しない |

`serverSeq` は relay 後の message にだけ現れる。Relay は client が持ち込んだ `serverSeq` を受理してはならない (MUST NOT)。`sessionId` と `clientId` は connection bound であり、envelope で別値へ変更してはならない (MUST NOT)。

`type=emit` の `body` は次の形である。

```json
{
  "event": "menu.open",
  "payload": { "source": "pause-menu" },
  "options": { "targetTime": 1710000000000 }
}
```

`payload` と `options` は省略できる。`options` の v1 フィールドは `targetTime` だけである。`type=state`、`catalog`、`config` の body はそれぞれの最新 snapshot JSON object とする。`type=config` の body は [`runtime-config.schema.json`](../schemas/runtime-config.schema.json) に適合し、その Console が割り当てた `revision` は envelope の `configRevision` と一致しなければならない (MUST)。config revision は session 内で strictly increasing でなければならない (MUST)。

## 6. Relay が保持・再生するデータ

`emit` は保存・replay しない。Session Relay が保持・再接続時に送るのは最新の `state`、`catalog`、`config` snapshot だけである。snapshot に PCM/Kit/asset bytes、binary frame、base64 化した bytes を含めてはならない (MUST NOT)。

## 7. 関連ファイル

- `specs/session-relay.md` — session lifetime、ticket、role、ACL、limits、replay、冪等性
- `schemas/runtime-config.schema.json` — config snapshot schema
- `schemas/session-envelope.schema.json` — WebSocket envelope schema
- `fixtures/sample-runtime-config.json` — fire / clip / disabled の例
- `fixtures/sample-session-envelope.json` — relay 後の emit envelope の例
