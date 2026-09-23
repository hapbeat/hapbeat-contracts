# WifiUdp stream session v2

Status: development, Unity-first validation (2026-09-23). Replaces the fixed
300 ms END-to-BEGIN cooldown for v2 receivers. SDKs keep streaming to pre-v2
receivers with the legacy format (see Legacy receiver fallback). FIRE/PLAY and
other non-stream commands are unchanged.

## Invariants

1. An old BEGIN, DATA or END must never reset, feed or stop a newer session.
2. A valid newer generation can begin immediately after END; no fixed cooldown.
3. Identity is transport state, not an Event ID. SDK sources still mix per endpoint.
4. Discovery reserves a lease; it must not interrupt playback. Activation/termination
   of a newer ordered session explicitly supersedes the older writer.
5. This is replay/lifecycle isolation on a trusted LAN, not authentication.

## Wire format

All numbers are little-endian. The 8-byte common header remains unchanged.
Only commands 0x30/0x31/0x32 use header protocol_version=2. v2 receivers reject
v1 stream commands without changing playback, so senders built before v2 cannot
stream to them (their FIRE/PLAY still work). Non-stream commands remain version 1.
Receivers have no v1 stream fallback; SDKs keep a per-device fallback for
receivers that predate v2 (Legacy receiver fallback below).

Every v2 stream payload begins with this 16-byte envelope:

| Offset | Field | Type |
|---|---|---|
| 0 | device_boot_id | uint64, nonzero, freshly random per device boot |
| 8 | lease_ticket | uint32, nonzero, issued monotonically by the device |
| 12 | generation | uint32, nonzero, increased per new session within a lease |

BEGIN appends the existing mandatory 12-byte format/gain body and optional
null-terminated target. DATA appends uint32 byte offset and audio bytes. END is
exactly the envelope, with no body. The total packet remains at most 1500 bytes.
All format/length/target validations precede mutation of the session state.
Counters never wrap/reuse: renew the lease before generation exhaustion; device
lease exhaustion fails closed until reboot.

## Discovery lease

SDKs request a stream lease through the existing PING/PONG exchange, not through
an extra round trip for each haptic event. PING remains version 1 and appends a
nonzero uint64 client_incarnation to its existing int64 timestamp (16-byte payload).
A fresh client incarnation is required on reconnect/explicit writer takeover.
Unextended PING remains discovery-only and must not allocate a stream lease.

The extended PONG tail follows the existing volume_level and volume_wiper bytes:

| Tail offset | Field | Type/value |
|---|---|---|
| 0 | marker | 4 bytes ASCII `HBS2` (`48 42 53 32`) |
| 4 | extension_version | uint8 = 1 |
| 5 | flags | uint8: bit 0 lease_valid; bit 1 lease_superseded; other bits zero |
| 6 | reserved | uint16 = 0 |
| 8 | echoed_client_incarnation | uint64 |
| 16 | device_boot_id | uint64 |
| 24 | lease_ticket | uint32 (0 only if allocation fails) |
| 28 | high_water_ticket | uint32, last accepted BEGIN/END ticket, 0 initially |

The tail is exactly 32 bytes. Only direct replies to extended PING carry it.
Unsolicited/broadcast identity PONGs omit it; absence must not erase an established
lease. How a missing tail classifies a device is defined in Legacy receiver
fallback. An SDK updates lease state only when header seq, echoed
timestamp and incarnation match its pending request, and that timestamp is newer
than the last accepted request for that endpoint. Keep a pending broadcast request
long enough to correlate replies from multiple devices (do not consume on first reply).

The receiver has 8 lease slots keyed by source IPv4, source UDP port and client
incarnation. Repeated PING of a live key returns its existing ticket. Non-active
slots expire after 15 seconds without PING; otherwise evict the oldest unpinned
slot if full. The active session's lease is pinned until END/takeover, so discovery
traffic cannot invalidate live DATA. Expired keys get a fresh ticket, never a reused
one. Active lease pinning does not authorize an unrelated sender.
After END/takeover, an expired or evicted entry cannot authorize a greater
generation. Greater BEGIN/END requires a live lease entry; a sender whose entry
expired must obtain a new ticket. Retained high-water/tombstone state only rejects
old/equal tuples and never substitutes for lease authorization.

Issue a fresh nonzero client incarnation on SDK Connect/reconnect, foreground
resume or explicit stream-ownership reacquisition. Periodic discovery keeps the
incarnation unchanged. A superseded flag (high_water_ticket > lease_ticket) does
not authorize automatic takeover: stop/defer that endpoint and require explicit
reconnect/resume/reacquisition, avoiding a fight between concurrent applications.
New discovery/lease state changes must propagate to active endpoint resolution;
device reboot or lease renewal must not keep emitting DATA under the retired identity.

## Receiver ordering

The device validates the boot identity and the issued lease's source IPv4/UDP-port
binding before comparing (lease_ticket, generation) lexicographically. A boot-lifetime
high-water mark and terminal tombstone are retained even when sender entries expire.

- BEGIN greater than the high-water mark: accept, supersede the previous session,
  and mark Active. Equal BEGIN is idempotently ignored (no decoder/buffer reset);
  lower BEGIN is rejected. An equal ended generation never restarts.
- DATA: accept only the exact Active tuple. Stale, ended, unknown and wrong-boot
  tuples are rejected before the decoder. With expected byte offset initially 0,
  reject DATA where `int32(offset - expected) < 0`; otherwise accept and set
  expected to offset + audio byte length (uint32 wrap). This serial-number comparison
  supports long streams across wrap; it assumes reorder distance below 2^31 bytes.
  Forward gaps may be dropped/concealed by codec policy, never replay old data.
- END equal to Active: stop accepting data and mark Ended. A valid greater END
  also advances to an Ended tombstone and supersedes the previous session, so
  reordered END-before-BEGIN cannot resurrect that generation. Lower END is ignored.
- Invalid/malformed packets never advance the high-water mark or stop the owner.

Lost BEGIN can lose a cue, as with the previous unreliable stream transport; it
must not cause DATA to enter another session. Repeating the same BEGIN is safe.
Lost END cannot make old DATA acceptable after a newer generation begins.

## Legacy receiver fallback (SDK)

Updating only the SDK must not silence devices on older firmware (DEC-075).
Pre-v2 firmware ignores the extra 8 PING bytes and replies with an ordinary PONG.
An SDK classifies each device endpoint from **matched direct replies** to its own
extended PING only (same correlation as leases: header seq, echoed timestamp and
incarnation match, and the timestamp is newer than the last accepted request):

| Matched reply | Class | Streaming |
|---|---|---|
| Valid 32-byte `HBS2` tail | v2 | Lease rules above. `lease_valid`=0 or superseded means defer, never legacy |
| No `HBS2` marker after the ordinary fields (the PONG ends at or before volume_wiper, or other bytes follow) | legacy | v1 format below |
| `HBS2` marker with wrong length, version, reserved or flags | ignored | No class or lease change; an unknown endpoint stays deferred |

Unsolicited PONGs, replies to other requests and late replies never change the
class. Before the first matched reply an endpoint is unknown and its streams defer.

Legacy endpoints use the pre-v2 stream format (`message-format.md` v1 stream):
header protocol_version=1, BEGIN/DATA payloads without the 16-byte envelope, END
with an empty payload, exact unicast to that endpoint. Pre-v2 firmware cannot
reject an old END, so the SDK keeps the legacy guard **for that endpoint only**:
after sending END there, the next BEGIN there waits at least 300 ms (sources for
it stay deferred meanwhile; other endpoints are unaffected). v2 endpoints keep no
cooldown. Mixed v2/legacy devices under one target are allowed.

When a matched reply changes an endpoint's class (firmware update or rollback),
end its current session in the old format first; the next session starts in the
new format. The 300 ms guard applies only after a legacy END.

## Required conformance and rollout

Test immediate END-to-BEGIN, old END after new BEGIN, old/duplicate BEGIN, END
before BEGIN, old/duplicate/backward DATA, wrong source/boot/lease, reboot,
reconnect, table exhaustion/eviction, counter exhaustion, and malformed bodies.
After a lease ends and expires, a greater generation under its old ticket must be
rejected. After accepting a new-boot PONG for a newer pending request, a late
old-boot PONG must not revert the lease. An unsolicited PONG without a lease tail
must not clear or replace an established lease.
Verify existing source mixing, independent stop, target isolation and PCM remain.
SDK legacy fallback: a matched reply without a tail selects v1 packets and the
300 ms guard for that endpoint only; unsolicited/unmatched PONGs and a malformed
`HBS2` tail never select legacy; v2 and legacy endpoints stream concurrently; a
class change ends the old-format session before the next BEGIN.
Device diagnostics expose accepted/rejected counters and active identity without
per-packet serial logging. Live probes are explicit opt-in; default tests use mocks.

Firmware and Unity are validated first by user request. Other SDK stream senders
must adopt this protocol, including the legacy fallback, before use with updated
firmware; v1 FIRE remains usable.
No release or public push is implied. Linger (keeping an idle session open briefly)
is distinct from the removed cooldown and may remain.
