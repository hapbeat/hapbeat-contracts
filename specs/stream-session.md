# WifiUdp Stream Gen 2 (session stream)

Status: released in device firmware 0.5.0 (2026-10-17). Requirements marked
**[1.x]** are added for the 1.0 release of all products (DEC-096) and are not in
firmware 0.5.0 or the 0.x SDKs. Names follow `versioning.md` §4: this document
defines **Stream Gen 2 (session stream / セッション方式)**; the previous format,
**Stream Gen 1 (sessionless stream / セッションなし方式)**, is defined in
`message-format.md` ("Stream Gen 1"). FIRE/PLAY and other non-stream commands are
unchanged by this document.

Stream Gen 2 replaces the fixed 300 ms END-to-BEGIN cooldown of Stream Gen 1. SDKs
keep streaming to Stream Gen 1 receivers in the Stream Gen 1 format (Legacy
receiver fallback).

## Invariants

1. An old BEGIN, DATA or END must never reset, feed or stop a newer session.
2. A valid newer generation can begin immediately after END; no fixed cooldown.
3. Identity is transport state, not an Event ID. SDK sources still mix per endpoint.
4. Discovery reserves a lease; it must not interrupt playback. Activation/termination
   of a newer ordered session explicitly supersedes the older writer.
5. This is replay/lifecycle isolation on a trusted LAN, not authentication.

## Assumptions

- A receiver plays **at most one** Stream Gen 2 session at a time. The ordering
  below is one lexicographic order per device boot; concurrent sessions are out of
  scope and would need a new generation (`versioning.md` §4.3).
- A sender sends its extended PINGs and all packets of a session **from the same
  IPv4 address and UDP port** (one socket). Leases are bound to that pair. IPv6 and
  rebinding a session across network interfaces are out of scope.
- Senders and receivers are on one LAN; packets may be lost, delayed, duplicated
  and reordered.

## Wire format

All numbers are little-endian. The 8-byte common header remains unchanged.
Only commands 0x30/0x31/0x32 use header protocol_version=2. Stream Gen 2
receivers reject Stream Gen 1 stream commands (protocol_version=1) without
changing playback, so senders built before Stream Gen 2 cannot stream to them
(their FIRE/PLAY still work). Non-stream commands remain version 1.
Receivers have no Stream Gen 1 fallback; SDKs keep a per-device fallback for
receivers that predate Stream Gen 2 (Legacy receiver fallback below).

Every Stream Gen 2 payload begins with this 16-byte envelope:

| Offset | Field | Type |
|---|---|---|
| 0 | device_boot_id | uint64, nonzero, freshly random per device boot |
| 8 | lease_ticket | uint32, nonzero, issued monotonically by the device |
| 12 | generation | uint32, nonzero, increased per new session within a lease |

- BEGIN appends the mandatory 12-byte format/gain body and an optional
  null-terminated target, so a BEGIN is **at least 28 bytes**; the target is at most
  64 bytes including its NUL (`device-addressing.md`).
- DATA appends a uint32 byte offset and **at least one** audio byte. A session's
  first DATA has offset 0.
- END is exactly the envelope, with no body.
- The packet sizes of `message-format.md` §10 apply (senders ≤ 1472 bytes).
- The format is frozen (`versioning.md` §7.4): receivers check lengths exactly;
  extensions go to a new generation, never into these packets.
- All format/length/target validations precede mutation of the session state.

Counters never wrap or get reused. Generation exhaustion (2^32 − 1 sessions under
one ticket) is not reachable in practice; a sender that reaches it obtains a new
ticket (fresh client incarnation) before the next session. Device ticket
exhaustion fails closed until reboot.

## Discovery lease

SDKs request a stream lease through the existing PING/PONG exchange, not through
an extra round trip for each haptic event. PING remains version 1 and appends a
nonzero uint64 client_incarnation to its existing int64 timestamp (16-byte
payload, the *extended PING*). A fresh client incarnation is required on
reconnect/explicit writer takeover. An 8-byte PING remains discovery-only and must
not allocate a stream lease.

**[1.x] How SDKs send extended PINGs.**

- Extended PINGs are sent by **unicast** only, to endpoints the SDK streams to or
  expects to stream to (for example endpoints matching the target of a Deferred or
  Active Playback, or the SDK's configured default target). Discovery broadcasts
  use the 8-byte PING. (0.x SDKs broadcast extended PINGs; that makes every device
  allocate a lease for every application on the LAN.)
- A held lease is refreshed by unicast extended PING at an interval of at most one
  third of the lease TTL (5 s for the 15 s TTL), as long as the SDK may stream to
  that endpoint, and for at least one TTL after its last session ended.

The extended PONG tail follows the existing volume_level and volume_wiper bytes:

| Tail offset | Field | Type/value |
|---|---|---|
| 0 | marker | 4 bytes ASCII `HBS2` (`48 42 53 32`) |
| 4 | extension_version | uint8 = 1 |
| 5 | flags | uint8: bit 0 lease_valid; bit 1 lease_superseded; bit 2 lease_reissued **[1.x]**; other bits zero |
| 6 | reserved | uint16 = 0 |
| 8 | echoed_client_incarnation | uint64 |
| 16 | device_boot_id | uint64 |
| 24 | lease_ticket | uint32 (0 only if no lease is allocated) |
| 28 | high_water_ticket | uint32, last accepted BEGIN/END ticket, 0 initially |

Receivers send exactly these 32 bytes, directly after volume_wiper, only in
direct replies to extended PINGs (the PONG format is frozen, `message-format.md`
§0x11). Unsolicited/broadcast identity PONGs omit it; absence must not erase an
established lease. How a reply classifies a device is defined in Receiver
classification.

- An extended PING whose client_incarnation is 0 gets a tail with flags 0 and
  lease_ticket 0. SDKs must not send incarnation 0.
- **[1.x]** Nodes that do not receive streams (broker, sensor) answer an extended
  PING with a tail whose flags are 0 and whose tickets are 0, so SDKs classify them
  as Stream Gen 2 and defer instead of sending Stream Gen 1 packets. Their CAPS
  report `stream_gens` = 0.

An SDK updates lease state only when header seq, echoed timestamp and incarnation
match its pending request, and that timestamp is newer than the last accepted
request for that endpoint. Keep a pending broadcast request long enough to
correlate replies from multiple devices (do not consume on first reply).

### Lease table (receiver)

The receiver has lease slots keyed by source IPv4, source UDP port and client
incarnation. 0.5.0 has 8 slots; **[1.x]** receivers have at least **32** and
report the number in CAPS `stream_limits`.

- Repeated PING of a live key returns its existing ticket, except for the
  re-issue rule below.
- Non-active slots expire after **15 seconds** without PING (the lease TTL,
  reported in CAPS `stream_limits`). When the table is full, the receiver evicts the
  unpinned slot whose last PING is oldest.
- The active session's lease is pinned until END/takeover/timeout, so discovery
  traffic cannot invalidate live DATA. Active lease pinning does not authorize an
  unrelated sender.
- Expired keys get a fresh ticket, never a reused one.
- After END/takeover, an expired or evicted entry cannot authorize a greater
  generation. Greater BEGIN/END requires a live lease entry; a sender whose entry
  expired must obtain a new ticket. Retained high-water/tombstone state only rejects
  old/equal tuples and never substitutes for lease authorization.

**[1.x] Re-issue rule.** When a live key whose ticket is below the high-water
ticket sends an extended PING, the receiver issues that key a fresh ticket
(greater than every ticket issued in this boot) and reports it not superseded, if
either:

1. the high-water ticket was issued to the **same client incarnation** (the same
   application whose address changed and came back, for example), or
2. no session is Active **and** no live lease exists for the client incarnation to
   which the high-water ticket was issued (that application stopped PINGing for one
   TTL under every address).

The receiver retains the client incarnation to which the high-water ticket was
issued, even after that entry expires, to evaluate both rules. Otherwise the key
keeps its ticket and the reply reports superseded. Rule 2 lets an unattended
sender (a Python or TouchDesigner process) recover after another application
played once and left, without fighting an application that is still present.

Every reply for a re-issued ticket sets flag bit 2 `lease_reissued`, for as long
as the key holds that ticket. A ticket a key gets because its previous entry
expired or was evicted is not re-issued and does not set the bit. 0.x SDKs treat a
tail with bit 2 as malformed and ignore that reply, so they keep their earlier
superseded deferral, as with firmware 0.5.0.

### Incarnation and takeover (sender)

Issue a fresh nonzero client incarnation on SDK Connect/reconnect, foreground
resume or explicit stream-ownership reacquisition. Periodic discovery keeps the
incarnation unchanged. A superseded flag (high_water_ticket > lease_ticket) does
not authorize automatic takeover: stop/defer that endpoint and require explicit
reconnect/resume/reacquisition, avoiding a fight between concurrent applications.

- **[1.x]** A matched reply with lease_valid=1, superseded=0 **and lease_reissued=1**
  clears an earlier superseded deferral of that endpoint (the receiver re-issued a
  ticket under the rules above). A new ticket without lease_reissued (for example
  after the SDK's own entry expired) does not clear it; the deferral still needs an
  explicit reacquisition, so a superseded application never takes a device back
  from an application that is still present.
- **[1.x]** A matched reply may carry a different ticket for the same incarnation
  and boot. The SDK adopts it, ends any session under the old ticket (END under the
  old identity) and starts the next session under the new ticket. A finite source
  continues from its current cursor (it does not restart from frame 0).
- **[1.x]** A relay that streams for other clients (hapbeat-helper) must not
  reacquire ownership on a client's behalf unless that client explicitly requests a
  takeover for that stream.

New discovery/lease state changes must propagate to active endpoint resolution;
device reboot or lease renewal must not keep emitting DATA under the retired
identity.

## Receiver classification (SDK)

An SDK classifies each device endpoint from **matched direct replies** to its own
extended PING only (the correlation above). Unsolicited PONGs, replies to other
requests and late replies never change the class. Before the first matched reply
an endpoint is unknown and its streams defer.

**[1.x]** rules (bytes after volume_wiper in a matched reply):

| Bytes after volume_wiper | Class |
|---|---|
| None (the PONG ends at or before volume_wiper) | Stream Gen 1 (legacy) |
| At least 32 bytes, starting with `HBS2`, extension_version = 1 | Stream Gen 2. Read the first 32 bytes; ignore any bytes after them, the reserved field and flag bits other than bits 0–2 |
| Anything else (fewer than 32 bytes, another extension_version, or bytes not starting with `HBS2`) | Ignored: no class or lease change (an unknown endpoint stays deferred). Warn once per endpoint |

Within a Stream Gen 2 class, lease_valid=0 or superseded means defer, never legacy.

0.x SDKs classify bytes that do not start with `HBS2` as legacy, and ignore an
`HBS2` tail unless it is exactly 32 bytes with extension_version 1, only flag bits
0–1 and reserved 0 (`../fixtures/stream-session-cases.json`, `expected_0x`).
Because the PONG is frozen for all 1.x firmware, 0.x and 1.x SDKs classify 1.x
firmware the same way, except for replies carrying lease_reissued, which 0.x SDKs
ignore (above). The relaxed rule only prepares 1.x SDKs for a later major.

## Receiver ordering

The device checks a stream packet in this order, and the first failing check
decides the rejection and its error: protocol_version, length and format, the
BEGIN target, the boot identity and the issued lease's source IPv4/UDP-port
binding, and then (lease_ticket, generation) compared lexicographically. A
boot-lifetime high-water mark and terminal tombstone are retained even when sender
entries expire.

- BEGIN greater than the high-water mark: accept, supersede the previous session,
  and mark Active. Equal BEGIN is idempotently ignored (no decoder/buffer reset);
  lower BEGIN is rejected. An equal ended generation never restarts.
- DATA: accept only the exact Active tuple. Stale, ended, unknown and wrong-boot
  tuples are rejected before the decoder. With expected byte offset initially 0,
  reject DATA where `int32(offset - expected) < 0`; otherwise accept and set
  expected to offset + audio byte length (uint32 wrap). This serial-number
  comparison supports long streams across wrap; it assumes reorder distance below
  2^31 bytes. Forward gaps may be dropped/concealed by codec policy, never replay
  old data.
- END equal to Active: stop accepting data and mark Ended. A valid greater END also
  advances to an Ended tombstone and supersedes the previous session, so reordered
  END-before-BEGIN cannot resurrect that generation. Lower END is ignored.
  A greater END from another live lease therefore stops the Active session even if
  that lease's BEGIN never arrived; this is intended (the later writer's END may
  overtake its BEGIN) and is the same supersession a greater BEGIN causes.
- STOP_ALL whose target matches the device ends the Active session as if its END
  had been accepted (`message-format.md` §0x03), whoever sent it.
- Invalid/malformed packets never advance the high-water mark or stop the owner.
- A BEGIN whose target does not match the device is rejected before any state
  changes; it does not advance the high-water mark.

The receiver remembers why the high-water session ended — an END (its own, or a
greater END from another lease), the inactivity timeout, or STOP_ALL — to choose
the error below.

Lost BEGIN can lose a cue, as with the previous unreliable stream transport; it
must not cause DATA to enter another session. Repeating the same BEGIN is safe.
Lost END cannot make old DATA acceptable after a newer generation begins.
A lost END with no newer generation is recovered by the inactivity timeout below.

## Errors

**[1.x]** Receivers report rejected stream packets with the ERROR command
(`message-format.md` §0xFF, including its rate limits), by unicast to the packet's
source. For codes 0x0011–0x0017, `detail` carries the rejected packet's 16-byte
envelope, so a sender can tell which of its sessions the error is about; for the
other codes `detail` is empty.

| Situation (first failing check, Receiver ordering) | Code |
|---|---|
| Stream Gen 1 packet (protocol_version=1 on 0x30–0x32) | STREAM_GEN_UNSUPPORTED |
| Other unknown protocol_version on 0x30–0x32 | UNSUPPORTED_VERSION |
| Wrong length or format | MALFORMED |
| BEGIN whose target does not match the device | STREAM_TARGET_MISMATCH |
| Wrong device_boot_id, no live lease for the ticket, or the lease is bound to another source | STREAM_LEASE_INVALID |
| BEGIN or DATA whose ticket is below the high-water ticket | STREAM_SUPERSEDED |
| DATA for a tuple above the high-water mark (its BEGIN was not received) | STREAM_NOT_STARTED |
| DATA for the high-water tuple ended by the inactivity timeout | STREAM_TIMED_OUT |
| DATA for the high-water tuple ended by STOP_ALL | STREAM_STOPPED |
| DATA for the high-water tuple ended by an END | STREAM_ENDED |

No error is sent for these normal events: an equal (repeated) BEGIN; any END that
is equal to or lower than the high-water tuple (including an END after the
inactivity timeout); a BEGIN or DATA of an older generation under the high-water
ticket (reordered packets of the sender's own previous session); and DATA of the
Active session whose offset is duplicated or behind the expected offset (Wi-Fi
retransmission or reordering).

## Inactivity timeout

END is sent once and unacknowledged, so a receiver must not depend on it to leave
stream playback. When the Active session has had neither its BEGIN nor any of its
DATA accepted for **5 seconds** (device monotonic clock; reported in CAPS
`stream_limits`), the receiver ends it on its own, with the effect of accepting
that session's END: it stops accepting data, marks the tuple Ended (it stays the
high-water mark, so later DATA, equal BEGIN or END of that generation are rejected
and only a greater generation plays again), unpins its lease, and leaves stream
playback state (e.g. the PWM playback bias, output-mode switch lock,
playback-active power monitoring). Already buffered audio drains as after END. The
receiver logs the timeout once with the ended ticket/generation. The check runs in
the receiver's main loop, not in the audio mix path. Rejected, malformed or
wrong-target packets do not extend the window, nor does an equal (repeated) BEGIN
of the Active session; only the first BEGIN and accepted DATA do.

Senders MUST keep sending DATA (silence included) for as long as they intend a
session to stay open, and send END when it ends. A sender that stops sending DATA
for longer than the timeout (for example a pause) must END the session and BEGIN a
new generation when it resumes; resumed DATA under the timed-out generation is
rejected. The timeout only recovers a lost END; it never replaces END.

The value is chosen above the longest DATA gap of current senders while a session
is open: the SDK empty-session linger before END (Unity, Unreal: 300 ms; Python,
JS: 310 ms, `sdk-multi-stream.md` §6), Studio Scene haptics, which keeps sending
DATA in ~10 ms ticks through its 3 s quiet period before END (a throttled
background tab stretches ticks to about 1 s), and the Studio editor, which
streams a clip continuously from BEGIN to END. It stays below the 15 s lease TTL.

Scope: only WifiUdp Stream Gen 2 sessions. Paths that fill the device playback
ring without a WifiUdp session are not timed out by this rule: the ESP-NOW stream
receiver (`espnow-stream.md`, its own receive/lock logic) and DuoWL line-in
capture.

## Sender requirements

1. **Keep DATA flowing.** While a session is open, send DATA continuously,
   including silence. A live source with no new input contributes silence; it must
   not stop the session's DATA (see Inactivity timeout).
2. **[1.x] Repeat BEGIN.** Send the session's BEGIN again with each of the first
   three DATA blocks, and resend it at least every 500 ms while the session is open
   (equal BEGIN is idempotent). On STREAM_NOT_STARTED, resend it at once. This
   recovers a lost BEGIN, which would otherwise silence the whole session.
3. **[1.x] Detect own gaps.** If the sender could not send DATA for 3 s or more
   (process suspended, debugger break, sleep), it ends the session and begins a
   new generation before sending more DATA, instead of resuming under a generation
   the receiver may have timed out.
4. **END.** Send END once when the session ends. Repeating the same END is safe;
   the receiver ignores equal or lower END.
5. **[1.x] Handle errors** (`message-format.md` §0xFF). Accept an ERROR only from
   the endpoint's address and UDP port 7700, and a stream error (0x0011–0x0017)
   only when its `detail` equals the envelope of a session the SDK still tracks for
   that endpoint (the current one, or the one it just ended); ignore the rest.
   - STREAM_LEASE_INVALID → renew the lease by unicast extended PING and begin a
     new generation.
   - STREAM_SUPERSEDED → defer the endpoint (no automatic takeover).
   - STREAM_TIMED_OUT → begin a new generation if the session should stay open.
   - STREAM_STOPPED → remove the sources from that endpoint; the same Playback does
     not rejoin it (`sdk-multi-stream.md` §6.13).
   - STREAM_TARGET_MISMATCH → re-resolve the endpoint.
   - STREAM_GEN_UNSUPPORTED → the endpoint's class is stale (the device was
     updated): send a unicast extended PING and classify it again.
   - STREAM_ENDED → log (a sender bug).
6. **[1.x] Expose state.** SDKs expose, per endpoint, the stream class (Gen 1,
   Gen 2, unknown) and why a Playback is deferred (no resolved endpoint, unknown
   class, lease unavailable, superseded) through their public API, not only logs.
7. **Same socket** for extended PINGs and every packet of a session (Assumptions).

## Legacy receiver fallback (SDK)

Updating only the SDK must not silence devices on firmware that predates Stream
Gen 2 (DEC-075). Such firmware ignores the extra 8 PING bytes and replies with an
ordinary PONG, which Receiver classification maps to Stream Gen 1.

Stream Gen 1 endpoints use the Stream Gen 1 format (`message-format.md`):
header protocol_version=1, BEGIN/DATA payloads without the 16-byte envelope, END
with an empty payload, exact unicast to that endpoint. That firmware cannot reject
an old END, so the SDK keeps the legacy guard **for that endpoint only**: after
sending END there, the next BEGIN there waits at least 300 ms (sources for it stay
deferred meanwhile; other endpoints are unaffected). Stream Gen 2 endpoints keep
no cooldown. Mixed Stream Gen 2 and Stream Gen 1 devices under one target are
allowed.

When a matched reply changes an endpoint's class (firmware update or rollback),
end its current session in the old format first; the next session starts in the
new format. The 300 ms guard applies only after a Stream Gen 1 END.

Under `versioning.md` §3.3, 1.x SDKs keep this fallback (firmware 0.4.x is the
previous line); the major that follows 1.x may drop it.

## Diagnostics

Receivers expose counters and the active identity without per-packet serial
logging, through the TCP command `get_stream_debug`, in its `session_v2` object
(the JSON key keeps its name; `versioning.md` §4.2):

| Field | Meaning |
|---|---|
| `boot_id` | device_boot_id, 16 hex digits |
| `ticket`, `generation`, `active` | high-water tuple and whether it is Active |
| `begin_accepted`, `data_accepted`, `end_accepted` | accepted packet counts |
| `rejected` and `begin_rejected`, `data_rejected`, `end_rejected` | rejected counts, total and per command |
| `legacy_rejected` | Stream Gen 1 packets rejected |
| `stale_rejected`, `malformed_rejected`, `target_rejected` | rejected by reason |
| `last_begin_us`, `last_data_us` | device time of the last accepted BEGIN / DATA |
| `begin_duplicate` **[1.x]** | equal BEGINs ignored (not counted as rejected) |
| `unknown_version_rejected` **[1.x]** | stream packets with a protocol_version other than 1 or 2 (not counted in `legacy_rejected`) |
| `end_reason` **[1.x]** | `active` while the high-water session is Active; otherwise why it ended: `end`, `timeout` or `stop_all` |

Live probes are explicit opt-in; default tests use mocks.

## Required conformance

Receiver: immediate END-to-BEGIN, old END after new BEGIN, old/duplicate BEGIN,
END before BEGIN, old/duplicate/backward DATA, wrong source/boot/lease, reboot,
reconnect, table exhaustion/eviction, counter exhaustion, malformed bodies, the
inactivity timeout (BEGIN without DATA and DATA followed by silence end after the
timeout, each accepted DATA restarts it, it fires once, the timed-out generation's
DATA/BEGIN stay rejected, a greater BEGIN plays again), STOP_ALL ending the Active
session. After a lease ends and expires, a greater generation under its old ticket
must be rejected. **[1.x]** The re-issue rule (both conditions, lease_reissued
on every reply for the re-issued ticket and not after a plain expiry, and no
re-issue while the other application's incarnation has a live lease or a session
is Active), at least 32 lease slots, the tail of non-streaming nodes, the check
order, each error code and the rate limits, and no error for the normal events
listed under Errors.

SDK: after accepting a new-boot PONG for a newer pending request, a late old-boot
PONG must not revert the lease. An unsolicited PONG without a lease tail must not
clear or replace an established lease. Verify existing source mixing, independent
stop, target isolation and PCM remain. Legacy fallback: a matched reply without a
tail selects Stream Gen 1 packets and the 300 ms guard for that endpoint only;
unsolicited/unmatched PONGs never select legacy; Stream Gen 2 and Stream Gen 1
endpoints stream concurrently; a class change ends the old-format session before
the next BEGIN. **[1.x]** Classification of the future-form fixtures (a 40-byte
tail is Stream Gen 2, extension_version 2 and bytes not starting with `HBS2` are
ignored, unknown flag bits and reserved are ignored), extended PINGs only by
unicast at no more than TTL/3, BEGIN repetition, the 3 s own-gap rule, silence for
idle live sources, error handling and the acceptance check of ERROR, clearing a
superseded deferral only with lease_reissued, and continuing a finite source from
its cursor after a ticket change.

Fixtures: `../fixtures/stream-session-v2.json` (packet bytes) and
`../fixtures/stream-session-cases.json` (classification and error cases).

## Versions

Which firmware and SDK versions speak Stream Gen 2 is in `versioning.md` §9 (the
0.x to 1.x migration table). Tools that warn before a firmware update use the
major version and capabilities (`versioning.md` §5), not a copy of that table.
