# Demo Switch control protocol

複数の独立 demo runtime を、同一 LAN 上の controller から logical demo ID で切り替えるための制御プロトコル。触覚 command plane（UDP 7700）とは独立した control plane であり、触覚・音声 payload を運ばない。

## Transport and lifecycle

- UDP 7710。payload は UTF-8 JSON object 1 個、最大 **1024 bytes**。断片化、連結、末尾の非 JSON byte は禁止。
- controller は切替先 IPv4 が未設定のとき、`DISCOVER` だけを LAN broadcast で 7710 へ送ってよい。前面 runtime は送信元 endpoint へ `HERE` を unicast で返す。controller は同じ nonce に対する有効な応答元が 1 IPv4 だけの場合に限り、その address を最大 30 秒 cache して以後の `SWITCH` を unicast する。0 台または複数台なら `SWITCH` を送ってはならない。
- 前面の demo runtime だけが 7710 を bind する。切替順序は `ACK` 送信、listener 停止、切替前通知、local allowlist に解決した runtime 起動の順。
- 次 runtime は controller endpoint と sequence を platform-specific launch context で引き継ぎ、初期化後にその endpoint へ `READY` を返す。起動できなければ現在 runtime が `FAILED` を返す。
- launch context の搬送方法、process/application 起動 API は platform adapter の責務であり、この規範プロトコルには含めない。

## Identifiers and sequence

`controller_id` と `demo_id` は ASCII の `[a-z0-9][a-z0-9._-]{0,63}`。network command は `demo_id` だけを指定し、package name、activity、executable、URI、arbitrary arguments を含めてはならない。receiver は local settings の allowlist で `demo_id` を launch target に解決する。

`seq` は controller ごとに単調増加する JSON integer（1..9007199254740991）。receiver は受理済み最大値を再起動後も永続化する。`seq` が保存値以下なら起動せず、同じ `controller_id` / `seq` / `demo_id` の再送には以前と同じ terminal result を返してよい。それ以外は `FAILED` / `replay` とする。

## Command

```json
{"version":1,"type":"SWITCH","controller_id":"m5-main","seq":42,"demo_id":"gloveball","auth":"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"}
```

必須 field は `version`, `type`, `controller_id`, `seq`, `demo_id`。`version` は `1`、`type` は `SWITCH` 固定。`auth` は HMAC authentication 使用時に必須で、小文字 hex 64 文字。未知 field は version 1 では拒否する。

## Status

### In-application CONTROL

`CONTROL` operates only on the foreground runtime whose `current_demo_id` equals
`demo_id`; it never launches another application. Required fields are `version`,
`type`, `controller_id`, `seq`, `demo_id`, `action`, `scene_id`; optional `auth`.
The same identifier, payload, authentication and persistent sequence rules apply.
Unknown fields are rejected. Actions are `menu_open`, `menu_close`, `recenter`,
`restart`, `scene`, `haptics_on`, `haptics_off`, `haptics_ui_show`, `haptics_ui_hide`,
`recenter_ui_show`, `recenter_ui_hide`, `tutorial_start`.
`scene_id` is a logical identifier for `scene`, and MUST be
the empty string for every other action. The four `haptics_*` actions set Hapbeat
output and the visibility of the in-view haptics button as defined in
[Demo Session](demo-session.md#触覚-onoff); a runtime that does not declare
`supports.haptics_toggle` rejects them with `FAILED/not_allowed`. Like menus they are
explicit set operations, never toggles. `recenter_ui_show` / `recenter_ui_hide` set the visibility of
the in-view 視線をリセット button ([Demo Session](demo-session.md#視線をリセット)); `recenter` performs the same
reset as that button. `tutorial_start` starts the runtime's tutorial from its beginning (runtimes without a
tutorial reject it with `FAILED/not_allowed`).

Runtimes that host the shared pause panel handle `menu_open` / `menu_close` with it when the scene has no
app-specific menu adapter, and `restart` with the shared restart (the same as the panel's 最初からやり直す) when
the app registers none. A runtime rejects an action only when neither an adapter nor a shared handler exists. Scene IDs resolve through an application
allowlist, never to supplied paths or executable names. `restart` reloads the
current experience, not the OS process. `recenter` uses the application's authored
start/reposition policy, not a privileged OS recenter command.

```json
{"version":1,"type":"CONTROL","controller_id":"m5-main","seq":43,"demo_id":"volley","action":"scene","scene_id":"block"}
```

CONTROL uses the COMMAND HMAC header and fields in this order: `version`, `type`,
`controller_id`, `seq`, `demo_id`, `action`, `scene_id`. Both added fields are signed,
including an empty `scene_id`. SWITCH's fields and canonical bytes are unchanged.
An unsupported action/scene, mismatched current demo, or busy receiver returns
`FAILED/not_allowed` without executing. On acceptance send ACK, retain the
listener, perform the operation on the application thread, then send READY only
after completion (for scenes, after the new scene initializes). Execution failure
returns `FAILED/launch_failed`. Status uses the existing schema and is correlated
by controller ID, sequence and demo ID. A receiver accepts at most one operation
at a time; duplicate sequences never execute twice. Menus use explicit open/close,
not toggle, so repeated user actions do not invert state accidentally. Pending
operations are not replayed when an application regains foreground.

Controllers discover the foreground demo before CONTROL, including when an HMD
address is manually configured (unicast DISCOVER/HERE is permitted there).
Do not replay queued controls on a different demo after a transition. An operator
must request the action again after a mismatch or failure.

```json
{"version":1,"type":"READY","controller_id":"m5-main","seq":42,"demo_id":"gloveball","current_demo_id":"gloveball","code":"ok","message":"","auth":"..."}
```

`type` は次のいずれか。

- `ACK`: command の認証、allowlist、sequence 検査が完了し、切替を開始する。起動成功を意味しない。
- `READY`: 切替先 runtime が前面初期化を完了し、7710 を bind した。
- `FAILED`: command を実行しない、または切替先の起動に失敗した。`code` は `invalid_payload`, `unsupported_version`, `invalid_auth`, `unsigned_disabled`, `not_allowed`, `replay`, `launch_failed`, `listener_failed` のいずれか。

全 status の必須 field は `version`, `type`, `controller_id`, `seq`, `demo_id`, `current_demo_id`, `code`, `message`。`message` は診断用で 256 UTF-8 bytes 以下。shared secret 設定時は status にも `auth` が必須。

## HMAC-SHA256 authentication

shared secret が設定されている receiver は有効な `auth` のない command を拒否する。secret が空の場合、receiver は設定により (A) isolated demo LAN 用 unsigned mode を警告付きで許可、または (B) receiver を無効化する。secret を source、fixture、serialized distributable asset に格納してはならない。

HMAC input は次の canonical bytes とする。

1. 各値を JSON decode 後の値として扱う。integer は leading zero のない base-10 ASCII にする。
2. 各 field を `name=<N>:<value>\n` とする。`N` は `<value>` の UTF-8 byte 数を base-10 ASCII で表す。改行は LF (`0x0A`)。`name`, `=`, `:`, `N` は ASCII。
3. command は header `HAPBEAT-DEMO-SWITCH/1\nCOMMAND\n` に `version`, `type`, `controller_id`, `seq`, `demo_id` の順で field を連結する。
4. status は header `HAPBEAT-DEMO-SWITCH/1\nSTATUS\n` に `version`, `type`, `controller_id`, `seq`, `demo_id`, `current_demo_id`, `code`, `message` の順で field を連結する。
5. HMAC-SHA256 key は shared secret の UTF-8 bytes。`auth` は digest の小文字 hex。比較は timing-safe に行う。

上記 command 例で `auth` を除く canonical string は次の通り（末尾にも LF がある）。

```text
HAPBEAT-DEMO-SWITCH/1
COMMAND
version=1:1
type=6:SWITCH
controller_id=7:m5-main
seq=2:42
demo_id=9:gloveball
```

JSON Schema は [`demo-switch-message.schema.json`](../schemas/demo-switch-message.schema.json)、例は [`sample-demo-switch-messages.json`](../fixtures/sample-demo-switch-messages.json) を正とする。

## Discovery

Quest の IPv4 手入力は必須ではない。controller は切替先が明示設定されていない場合、次の request を LAN broadcast で UDP 7710 へ送る。`nonce` は discovery round ごとに新しく生成する 16 文字の lowercase hex とし、再利用しない。

```json
{"version":1,"type":"DISCOVER","controller_id":"m5-main","nonce":"0123456789abcdef","auth":"..."}
```

前面 runtime は authentication と設定を検証した後、受信元 endpoint へ次を unicast する。

```json
{"version":1,"type":"HERE","controller_id":"m5-main","nonce":"0123456789abcdef","current_demo_id":"gloveball","auth":"..."}
```

`DISCOVER` の必須 field は `version`, `type`, `controller_id`, `nonce`、`HERE` はそれらに `current_demo_id` を加える。未知 field は拒否する。shared secret 設定時は `auth` が必須で、未設定時は receiver と controller の双方が isolated-LAN unsigned mode を明示している場合だけ受理する。

HMAC canonical bytes は command/status と同じ field encoding を使う。request は header `HAPBEAT-DEMO-SWITCH/1\nDISCOVER\n` に `version`, `type`, `controller_id`, `nonce`、response は header `HAPBEAT-DEMO-SWITCH/1\nHERE\n` に `version`, `type`, `controller_id`, `nonce`, `current_demo_id` の順で連結する。controller は nonce、controller ID、HMAC、送信元 IPv4 を検証し、600 ms 以上の収集 window 内で応答元が 1 IPv4 の場合だけ採用する。複数の Quest が応答した場合、最初の応答を勝手に選んではならない。

## State query

A controller may ask the foreground runtime for its current state. The request is sent like `DISCOVER`
(unicast to a known HMD, or broadcast), and the runtime answers by unicast to the source endpoint. Neither
message changes state, so no sequence number is used; a fresh 16-hex `nonce` per request correlates the reply.

```json
{"version":1,"type":"QUERY","controller_id":"remote-pixel","nonce":"0123456789abcdef"}
```

```json
{"version":1,"type":"STATE","controller_id":"remote-pixel","nonce":"0123456789abcdef","current_demo_id":"handdemo","haptics_on":true,"haptics_ui":false,"recenter_ui":false,"paused":false,"step_index":1,"step_count":3}
```

`haptics_on` is the current Hapbeat output state, `haptics_ui` / `recenter_ui` the visibility of the in-view
buttons, `paused` whether the shared pause (or the app's own menu pause) is active, and `step_index` /
`step_count` the Demo Session position (-1 / 0 outside a session). Unknown fields are rejected. With a shared
secret both carry `auth`: HMAC canonical bytes use the header `HAPBEAT-DEMO-SWITCH/1
QUERY
` with `version`,
`type`, `controller_id`, `nonce`, and `HAPBEAT-DEMO-SWITCH/1
STATE
` with `version`, `type`, `controller_id`,
`nonce`, `current_demo_id`, `haptics_on`, `haptics_ui`, `recenter_ui`, `paused`, `step_index`, `step_count`
(booleans as `true` / `false`). Existing controllers that do not send `QUERY` are unaffected; `HERE` is unchanged.
