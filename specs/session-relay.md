# Session Relay v1 仕様書

## 1. 範囲と接続モデル

Session Relay は、同一 session に参加した app、runtime、console の WebSocket 接続を中継する。message の wire format は [`web-runtime.md`](web-runtime.md) と [`schemas/session-envelope.schema.json`](../schemas/session-envelope.schema.json) を正とする。

Relay は**意味を持つ JSON の text frame**の中継と、最新 snapshot の保持だけを担う。binary frame、PCM、WAV、Kit archive、その他の asset bytes を WebSocket で受理・中継・保存してはならない (MUST NOT)。asset は `https://` で事前配置し、Runtime config の `clipAsset` から参照する。

Session は Cloudflare Durable Object (DO) 1 個に対応し、有効期間は約 15 分（900 秒）である。WebSocket 接続の寿命は session の expiry までであり、接続に使った ticket の expiry では切断しない。

## 2. Session 作成と ticket exchange

### 2.1 Session

Session 作成は `POST /v1/sessions` で行う。外部 API の `sessionId` は UUID とし、作成された session は作成時刻から 900 秒で expiry となる。session 作成は Cloudflare の global rate-limit binding で制限し、**1 colo あたり 60 秒間に最大 20 件**とする。

### 2.2 Ticket

WebSocket 接続の前に、session の credential を ticket exchange に渡す。

```text
POST /v1/sessions/{sessionId}/tickets
```

ticket exchange は HTTP `POST` の request body（最大 64 KiB）で credential に束縛された `sessionId`、`role`、`clientId` を検査し、成功時に**60 秒だけ有効な one-time ticket**を発行する。credential/token は session、role（`app` / `runtime` / `console`）、clientId、有効期限に束縛される。token は最大 256 文字、clientId は最大 128 文字とし、別 session・別 role・別 client の交換に使ってはならない (MUST NOT)。ticket の発行数は session あたり最大 300 件である。

WebSocket route の `sessionId` は UUID でなければならず、ticket に束縛された sessionId と一致しなければならない。認証情報を渡す query は ticket だけを含む。

```text
wss://relay.example/v1/sessions/{sessionId}/ws?ticket=<one-time-ticket>
```

query string に `role`、`clientId`、credential などを併記してはならない (MUST NOT)。path の `{sessionId}` 以外に sessionId を query へ重複指定してはならない。ticket の有効期限は接続受付時に検査する。受付後は ticket を再利用できず、ticket が 60 秒を過ぎても、接続は session expiry まで維持する。

期限切れ、使用済み、別 session の ticket、ticket に記録された role/clientId と異なる接続は拒否する。接続後に role、sessionId、clientId を変更してはならない (MUST NOT)。

ticket 発行カウンタの増分と one-time ticket の保存は、session DO storage transaction で原子的に行う。上限到達時に ticket だけが保存されたり、カウンタだけが進んだりしてはならない。

ticket HTTP request body は `Content-Length` の有無や値を信頼して全量 buffer してはならない。Relay は body を streaming で読み、読み込み途中の累積 bytes が 65536 bytes を超えた時点で読み込みを中断し、HTTP `413 Payload Too Large` を返す。`Content-Length` が無い場合も同じ検査を行う。事前に超過が分かる `Content-Length` は読み込み開始前に 413 としてよい。

## 3. Role ACL

Relay は ticket の role に基づき、publish と subscribe の両方を検査する。ACL 外の message は中継してはならない (MUST NOT)。

| role | publish できる type | subscribe できる type | 用途 |
|---|---|---|---|
| `app` | `emit` | `state` / `catalog` / `config` | アプリの意味イベント送信と snapshot 参照 |
| `runtime` | `state` | `emit` / `catalog` / `config` | Runtime Console のイベント処理と状態報告 |
| `console` | `state` / `catalog` / `config` | `emit` / `state` / `catalog` / `config` | Runtime config、catalog、状態の管理 |

`join` handshake は session envelope の `type` ではなく、ticket を使う接続処理である。接続後の envelope の `sessionId` と `clientId` は ticket から導出した connection-bound 値と完全一致しなければならない。

## 4. Message 制限と中継

次の制限を session DO が検査する。

| 項目 | 上限 / 条件 |
|---|---|
| WebSocket text frame | 64 KiB（65536 bytes）以下。binary frame は拒否 |
| JSON nesting depth | 16 以下 |
| JSON nodes | 1 message あたり 4096 以下 |
| JSON string | 8192 文字以下 |
| `event` 名 | 128 文字以下 |
| `messageId` | 1..128 文字。`(clientId,messageId)` を storage key にする |
| ticket HTTP body | 64 KiB（65536 bytes）以下 |
| ticket token | 256 文字以下 |
| ticket clientId | 128 文字以下。接続 envelope の clientId は UUID |
| config `events` | 1 snapshot あたり最大 256 件 |
| unique message | session あたり `(clientId,messageId)` の unique 組を最大 10000 件 |
| ticket 発行 | session あたり最大 300 件 |
| session 作成 | global rate-limit binding により colo あたり 60 秒で最大 20 件 |

Relay は受理した client envelope を検証し、fan-out 前に `serverSeq` を付与する。`serverSeq` は session 内で単調増加する 10 進文字列 (`^[0-9]+$`) とし、JSON number に変換してはならない。client から受信した `serverSeq` は無効として扱い、受理してはならない (MUST NOT)。

fan-out は peer ごとに独立して実行する。ある peer への send が失敗しても、その peer の失敗を記録・切断処理した上で後続 peer への send を継続し、1 peer の失敗で fan-out 全体を中断してはならない (MUST NOT)。

`clientSeq` は client ごとの単調増加値である。Relay は transport の順序だけで処理結果を決めず、`clientId` と `messageId` の組を冪等性キーとして扱う。同じ組を再受信した場合、最初の message だけを処理し、同じ emit を再配信・再スケジュールしてはならない (MUST NOT)。unique message 上限を超えた message は拒否する。

dedup key の登録、unique message 上限の検査、config revision の strictly-increasing 検査、`serverSeq` の割当、snapshot の更新は、1 回の session DO storage transaction で原子的に行う。いずれかの検査に失敗した場合は fan-out と storage 更新を行わず、部分的な dedup 登録・sequence 消費・snapshot 更新を残してはならない。

## 5. Replay と snapshot

`type=emit` は transient message であり、保存してはならず、再接続または late join 後に replay してはならない (MUST NOT)。Relay が一時的に fan-out 用に保持していても、replay の根拠にはならない。

Relay が保持・再接続時に送るのは、各 type の最新 snapshot だけである。

- `type=state`
- `type=catalog`
- `type=config`

過去の transient emit を snapshot として再構成してはならない (MUST NOT)。snapshot は JSON object とし、PCM/Kit/asset bytes、WebSocket binary frame、base64 化した PCM/Kit bytes を含めてはならない (MUST NOT)。

`type=config` の body は [`schemas/runtime-config.schema.json`](../schemas/runtime-config.schema.json) に適合し、Runtime Console が現在 revision+1 として割り当てた body の `revision` と envelope の `configRevision` が一致しなければならない (MUST)。config snapshot の revision は session 内で strictly increasing でなければならず、同値・減少する更新は拒否する。`9007199254740991` 到達後の import は拒否する。

## 6. Runtime-PC との境界

Relay は触覚再生を実行せず、`targetTime` の device end-to-end 到達も保証しない。`targetTime` と config の `delayMs` は Runtime-PC scheduler の基準で解決され、過去または現在の targetTime は `0 ms`（即時）、未来の差分が `2147483647` ms を超える targetTime は拒否される。Runtime Console が送信を行わない場合、既定結果は target なし・触覚なしである。

CLIP の asset fetch、`OfflineAudioContext` による無音 decode/resample、PCM16 化、helper の `stream_begin` / `stream_data` / `stream_end` への固定明示 online IP unicast は Runtime Console の責務であり、Relay の責務ではない。helper の初期送信は OFF、選択 online IP が 0 台のときは送信も broadcast fallback も行わない。変更・disable・cancel の `stream_end` は開始時と同じ元 IP へ送る。

## 7. 関連ファイル

- `specs/web-runtime.md` — `hapbeat.emit`、config 解決、CLIP、envelope の利用方法
- `schemas/session-envelope.schema.json` — envelope の構造
- `schemas/runtime-config.schema.json` — config snapshot の構造
- `fixtures/sample-session-envelope.json` — `serverSeq` を含む relay 後の例
