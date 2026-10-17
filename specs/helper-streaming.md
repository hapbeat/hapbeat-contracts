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

## Replies to the client

Helper answers each `stream_begin` with one `stream_ack`, and tells clients when
they lose destinations. Clients that send `stream_id` MUST handle both messages;
a client that ignores them cannot tell that its stream went silent.

| Message | Payload | Meaning |
|---|---|---|
| `stream_ack` | `stream_id` (when the begin carried one), `status`, `targets` (IPs started), optional `deferred` (IPs not started) | `status` `ok`: started on `targets`; the destinations in `deferred` were not ready in time (unknown class, no lease, superseded). `no_target`: started on none. `error`: rejected (`message` says why). `no_session`: sent once when data/end arrive for a transaction that holds no destination (displaced or never begun), so the client can begin again |
| `stream_displaced` | `stream_id`, `targets` (IPs), `by` (the newer `stream_id`), `same_client` (bool) | A newer `stream_begin` took these destinations. `same_client` true means the client replaced its own stream |
| `stream_lost` **[1.x]** | `stream_id`, `targets` (IPs), `reason` | Helper ended the transaction on these destinations because of the device side. `reason`: `device_rebooted`, `lease_changed`, `superseded`, `timed_out`, `stopped` (STOP_ALL), `unreachable` |

A client whose every destination is displaced, lost or deferred treats its
playback as lost (Studio's `LiveStreamLoss`), and may start a new transaction.

## Device-side changes [1.x]

Helper is the Stream Gen 2 sender for its clients (`stream-session.md`). For each
destination of an active transaction:

- When a matched PONG shows a new `device_boot_id` or a different lease ticket,
  Helper ends the session under the old identity (END) and sends `stream_lost`
  (`device_rebooted` or `lease_changed`). It does not keep sending DATA under the
  retired identity.
- When the device reports a stream error (`message-format.md` §0xFF) for the
  session, Helper acts as an SDK would (`stream-session.md` Sender requirements 5)
  and sends `stream_lost` with the matching `reason`.

## Takeover [1.x]

A superseded destination (another application started a newer session on it) is
reacquired only when the client asks for it: `stream_begin` carries
`payload.takeover = true` for a playback the user started explicitly (for example
pressing play in Studio). Without `takeover`, Helper does not renew its client
incarnation for that destination; it reports the destination in `deferred` of the
`stream_ack`. An SDK that plays cues automatically through Helper (the JS SDK's
browser transport) does not set `takeover`.
