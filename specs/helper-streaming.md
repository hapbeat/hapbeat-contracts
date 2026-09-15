# Helper WebSocket audio streaming

This document defines the transaction identity used by browser clients when
they send PCM audio through `hapbeat-helper` on WebSocket port 7703.

## Stream transaction

A client that can cancel one playback and begin another before the old async
operation has unwound MUST put the same non-empty string
`payload.stream_id` on every `stream_begin`, `stream_data`, and `stream_end`
message for one logical playback. A new logical playback MUST use a new
`stream_id`.

A strictly serial client MAY omit `stream_id`; Helper then treats its current
connection as one implicit transaction. Such a client cannot overlap stream
generations and does not receive stale-message protection within that one
connection.

`stream_begin` makes that transaction the active stream for every explicit
destination in `payload.targets`. For each destination, Helper MUST forward
`stream_data` and `stream_end` only while their client connection and
`stream_id` match the active transaction. A later `stream_begin` takes
ownership immediately; delayed data or end messages from the displaced
transaction MUST be ignored for that destination.

The `stream_id` is a Studio-to-Helper coordination field. Helper does not put
it into the device UDP packet. UDP stream sequence numbers start at zero for
each accepted transaction and advance only for its forwarded data/end packets.
