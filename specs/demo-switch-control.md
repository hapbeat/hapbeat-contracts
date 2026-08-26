# Demo Switch control protocol

複数の独立 demo runtime を、同一 LAN 上の controller から logical demo ID で切り替えるための制御プロトコル。触覚 command plane（UDP 7700）とは独立した control plane であり、触覚・音声 payload を運ばない。

## Transport and lifecycle

- UDP 7710。payload は UTF-8 JSON object 1 個、最大 **1024 bytes**。断片化、連結、末尾の非 JSON byte は禁止。
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
