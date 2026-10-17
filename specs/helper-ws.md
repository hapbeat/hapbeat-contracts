# Helper WebSocket: handshake and capabilities

`hapbeat-helper` serves Hapbeat Studio and browser SDK clients on WebSocket port
7703 (`ports.md`). Messages are JSON objects `{"type": ..., "payload": {...}}`.
This document defines the first message Helper sends and how clients decide which
Helper features they may use (DEC-096, `versioning.md` §5.4). Audio streaming
messages are in `helper-streaming.md`.

## helper_hello

Helper sends `helper_hello` as the first message on every connection, before
`device_list`.

| Field | Type | Since | Meaning |
|---|---|---|---|
| `version` | string | 0.x | Helper's version (display only; clients do not compare it to enable features) |
| `generation` | integer | **1.x** | Helper's major (`versioning.md` §3.2) |
| `types` | string array | **1.x** | Every request `type` Helper handles (for example `get_info`, `stream_begin`, `reset_storage`) |
| `features` | string array | **1.x** | Behaviors that a request type alone does not show (below) |

`features` values:

| Value | Meaning |
|---|---|
| `stream_gen2` | Helper streams to Stream Gen 2 receivers (`stream-session.md`) and keeps the Stream Gen 1 fallback |
| `stream_lost` | Helper sends `stream_lost` and recovers device-side errors itself (`helper-streaming.md`) |
| `stream_takeover` | Helper honors `stream_begin.payload.takeover` and otherwise defers superseded destinations |
| `device_caps` | `get_info` replies pass through the device's `caps`, `stream_protocol` and `storage_incompatible` (`serial-config.md` §4.1) |

## Client rules

- Enable a feature only when Helper lists the request type and, where one applies,
  the feature value. Clients do not compare Helper's `version` to enable features.
- Ignore unknown `types`, `features` and payload fields (`versioning.md` §7.1).
- A Helper without `types` (0.x) offers only what Helper 0.5.0 offered. A client
  keeps its minimum connectable Helper version for that case only, and shows
  "update Helper" per feature, not as a global block, when a needed type or feature
  is missing.
- If `generation` is greater than the client's own major, the client shows once
  that it should be updated (`versioning.md` §3.3).
- Helper answers an unknown request `type` with
  `{"type": "error", "payload": {"message": "unknown type: <type>"}}`, as today.
