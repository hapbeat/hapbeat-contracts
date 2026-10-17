# Changelog

本 repo の版は [specs/versioning.md](specs/versioning.md) §3.7 に従う。major は全製品の major、minor は追加だけの仕様変更、patch は文言の修正である。1.0.0 までは tag を打たず、変更を「Unreleased」に積む。各項目には `versioning.md` §6 の分類（追加・破壊・修正）を付ける。

## Unreleased（1.0.0 に含める）

### 追加

- `versioning.md` を全面改訂（DEC-096）: 全製品の major を揃える規則、「SDK・helper の major ≥ ファームの major なら動く」、同じ major の中は追加だけ、製品単独で major を上げない、方式の世代（Stream Gen 1 / Gen 2）の呼び方、変更の分類表、無視する規則と拒否する規則、凍結している形式、永続データの版、0.x → 1.x の移行表、1.0 の条件。
- `message-format.md`: §4.0 拡張の規則と command_type の割当、0x12 CAPS_REQ / 0x13 CAPS（能力申告）、0xFF ERROR のコード表と返す規則、`protocol_version` の意味、STOP_ALL が stream session を終えること、PING・PONG の凍結。
- `serial-config.md`: `get_info` の `caps`・`stream_protocol`・`storage_incompatible`、§4.23 `reset_storage`。
- `stream-session.md`: 1.x の要件（拡張 PING は unicast で TTL/3 以下、lease slot は 32 以上、再発行の規則と tail の flag bit 2 `lease_reissued`、stream を受けないノードの tail、受信側の判定順と ERROR、送信側の要件、診断の項目）と、1.x の SDK の PONG の分類規則（32 byte 以上の tail を読み、予約と未知の flag を無視する）。superseded の保留を解くのは `lease_reissued` の応答だけ。
- `sdk-multi-stream.md`: `deferredReason` の値の追加、BEGIN の再送、live source の無入力時の無音、STOP_ALL で止まった endpoint の扱い（§6.13）。
- `helper-streaming.md`: 既存の `stream_ack`・`stream_displaced` の定義、`stream_lost` と `stream_begin.takeover`（1.x）。
- `kit-format.md`: `caps.kit_schema` と `caps.kit_clip_formats` による照合。
- fixture `stream-session-cases.json`（PONG の分類と受信側の判定）、`wire-extension-cases.json`（CAPS・ERROR・PLAY の末尾・PING の長さ）と、その参照テスト `tests/test_wire_compat.py`。

### 破壊

- なし。0.x のうち Stream Gen 2 に対応した SDK（`versioning.md` §9）は、1.x のファームとつながる（PING・PONG と Stream Gen 2 のパケットの形は変えていない）。0.x の SDK は、1.x のファームが送る ERROR を無視するかログに出すだけで、`lease_reissued` の付いた応答は不正な tail として無視する（0.5.0 と同じく保留のまま）。実機で確認する。
- Kit の `firmware_version_min` は major だけを比べ、`firmware_version_max` は照合しない（`versioning.md` §11）。0.x のファームは semver 全体で比べるため、1.x の書き手が `1.0.0` と書いた Kit を 0.x の機体は拒否する（意図どおり）。

### 修正

- `stream-session-v2.md` を `stream-session.md` に改名し、「v1 / v2」を Stream Gen 1（セッションなし方式）/ Stream Gen 2（セッション方式）に改めた。fixture `stream-session-v2.json` は各 SDK のテストが参照しているため名前を変えていない。
- `message-format.md`: パケットの上限（送信側 1472 bytes 以下、受信側 1500 bytes まで）、BEGIN は 28 bytes 以上で target は NUL を含め 64 bytes 以内、STREAM 系の seq の扱い。
- `stream-session.md`: lease の追い出しは最後の PING が最も古いもの、greater END の意図、DATA は 1 byte 以上の音声を持つ、前提（同時に 1 session、PING と stream は同じ socket）。
