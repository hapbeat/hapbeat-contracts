"""Run: python -m unittest discover -s tests -p test_wire_compat.py

Reference checks for the 1.x wire rules (DEC-096): Stream Gen 2 classification
(stream-session.md), receiver errors, CAPS, ERROR and trailing-field tolerance
(message-format.md). The small parsers below are reference behavior for SDK and
firmware tests, not product code.
"""
import json
import re
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAGIC = 0x4842
STREAM_COMMANDS = (0x30, 0x31, 0x32)


def load(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8-sig'))


STREAM = load('fixtures/stream-session-cases.json')
EXT = load('fixtures/wire-extension-cases.json')
MESSAGE_FORMAT = (ROOT / 'specs/message-format.md').read_text(encoding='utf-8')
ERROR_CODES = {name: int(code, 16) for code, name in
               re.findall(r'^\| (0x[0-9A-F]{4}) \| ([A-Z_]+) \|', MESSAGE_FORMAT, re.M)}


def parse_packet(hex_string):
    data = bytes.fromhex(hex_string)
    magic, version, command, seq, length = struct.unpack_from('<HBBHH', data)
    payload = data[8:8 + length]
    return {'magic': magic, 'version': version, 'command': command, 'seq': seq,
            'length': length, 'payload': payload, 'datagram': data}


def read_cstring(data, offset):
    end = data.index(b'\0', offset)
    return data[offset:end].decode('utf-8'), end + 1


def pong_rest(payload):
    offset = 16
    for _ in range(3):
        _, offset = read_cstring(payload, offset)
    return payload[offset + 2:]


def lease_fields(rest):
    flags = rest[5]
    _, _, ticket, high = struct.unpack_from('<QQII', rest, 8)
    return {'lease_valid': bool(flags & 0x01) and ticket != 0,
            'superseded': bool(flags & 0x02), 'ticket': ticket, 'high_water_ticket': high,
            'lease_reissued': bool(flags & 0x04)}


def classify_1x(payload):
    rest = pong_rest(payload)
    if not rest:
        return {'class': 'gen1'}
    if len(rest) >= 32 and rest[:4] == b'HBS2' and rest[4] == 1:
        return {'class': 'gen2', **lease_fields(rest)}
    return {'class': 'ignored'}


def classify_0x(payload):
    rest = pong_rest(payload)
    if len(rest) < 4 or rest[:4] != b'HBS2':
        return 'gen1'
    reserved = struct.unpack_from('<H', rest, 6)[0] if len(rest) >= 8 else None
    if len(rest) != 32 or rest[4] != 1 or rest[5] & ~0x03 or reserved != 0:
        return 'ignored'
    return 'gen2'


CAPS_FORMATS = ['pcm16', 'adpcm', 'opus']
CAPS_FEATURES = ['play_pan', 'error_reply']


def bits(value, names):
    return [name for index, name in enumerate(names) if value & (1 << index)]


def parse_caps(payload):
    caps = {'caps_version': payload[0]}
    offset, seen = 2, set()
    while offset + 2 <= len(payload):
        kind, size = payload[offset], payload[offset + 1]
        value = payload[offset + 2:offset + 2 + size]
        offset += 2 + size
        if len(value) < size or kind in seen:
            continue
        defined = {0x01: 1, 0x03: 1, 0x04: 1, 0x05: 4, 0x06: 1, 0x07: 1, 0x08: 4}.get(kind)
        if kind == 0x02:
            seen.add(kind)
            caps['firmware_version'] = value.decode('utf-8')
        elif defined is not None and len(value) >= defined:
            seen.add(kind)
            if kind == 0x01:
                caps['generation'] = value[0]
            elif kind == 0x03:
                caps['stream_gens'] = [gen for gen in (1, 2) if value[0] & (1 << (gen - 1))]
            elif kind == 0x04:
                caps['stream_formats'] = bits(value[0], CAPS_FORMATS)
            elif kind == 0x05:
                caps['lease_ttl_s'], caps['lease_slots'], caps['inactivity_timeout_s'] = value[:3]
            elif kind == 0x06:
                caps['haptic_channels'] = value[0]
            elif kind == 0x07:
                caps['address_max_len'] = value[0]
            elif kind == 0x08:
                caps['features'] = bits(struct.unpack_from('<I', value)[0], CAPS_FEATURES)
    return caps


def parse_error(payload):
    code = struct.unpack_from('<H', payload)[0]
    message, offset = read_cstring(payload, 2)
    result = {'error_code': code, 'message': message}
    if len(payload) >= offset + 4:
        ref_command, ref_seq, detail_length = struct.unpack_from('<BHB', payload, offset)
        detail = payload[offset + 4:offset + 4 + detail_length]
        result.update({'ref_command': ref_command, 'ref_seq': ref_seq, 'detail_hex': detail.hex()})
    return result


def parse_play(payload):
    event_id, offset = read_cstring(payload, 0)
    target, offset = read_cstring(payload, offset)
    target_time, gain = struct.unpack_from('<qf', payload, offset)
    offset += 12
    pan = struct.unpack_from('<f', payload, offset)[0] if len(payload) >= offset + 4 else 0.0
    return {'event_id': event_id, 'target': target, 'target_time': target_time,
            'gain': gain, 'pan': round(pan, 6)}


def target_matches(target, address):
    return target == '' or address == target or address.startswith(target + '/')


class ReferenceReceiver:
    """Minimal Stream Gen 2 receiver for the fixture context (stream-session.md).

    Check order (Receiver ordering): protocol_version, length/format, BEGIN target,
    boot and lease binding, then the (ticket, generation) order.
    """

    def __init__(self, context):
        self.boot = int(context['device_boot_id'], 16)
        self.address = context['device_address']
        self.leases = context['leases']
        self.high_water = tuple(context['high_water'])
        self.end_reason = context['high_water_end_reason']
        self.active = context['active']
        self.expected_offset = context.get('expected_offset', 0)

    def handle(self, sender, packet):
        version, command, payload = packet['version'], packet['command'], packet['payload']
        if version == 1:
            return False, 'STREAM_GEN_UNSUPPORTED'
        if version != 2:
            return False, 'UNSUPPORTED_VERSION'
        if len(packet['datagram']) != 8 + len(payload):
            return False, 'MALFORMED'
        target = None
        if command == 0x30:
            if len(payload) < 28:
                return False, 'MALFORMED'
            if len(payload) > 28:
                raw = payload[28:]
                if raw[-1:] != b'\0' or len(raw) > 64 or b'\0' in raw[:-1]:
                    return False, 'MALFORMED'
                target = raw[:-1].decode('utf-8')
        elif command == 0x31 and len(payload) <= 20:
            return False, 'MALFORMED'
        elif command == 0x32 and len(payload) != 16:
            return False, 'MALFORMED'
        if target is not None and not target_matches(target, self.address):
            return False, 'STREAM_TARGET_MISMATCH'
        boot, ticket, generation = struct.unpack_from('<QII', payload)
        if boot != self.boot or self.leases.get(sender) != ticket:
            return False, 'STREAM_LEASE_INVALID'
        tup, high = (ticket, generation), self.high_water
        if command == 0x30:
            if tup > high:
                return True, None
            if tup < high and ticket < high[0]:
                return False, 'STREAM_SUPERSEDED'
            return False, None
        if command == 0x31:
            if tup == high and self.active:
                offset = struct.unpack_from('<I', payload, 16)[0]
                behind = ((offset - self.expected_offset) & 0xFFFFFFFF) >= 0x80000000
                return (False, None) if behind else (True, None)
            if tup > high:
                return False, 'STREAM_NOT_STARTED'
            if tup == high:
                return False, {'end': 'STREAM_ENDED', 'timeout': 'STREAM_TIMED_OUT',
                               'stop_all': 'STREAM_STOPPED'}.get(self.end_reason)
            return False, 'STREAM_SUPERSEDED' if ticket < high[0] else None
        return (True, None) if tup > high else (False, None)


def all_packet_hex():
    yield STREAM['pong_classification']['ping_hex']
    for case in STREAM['pong_classification']['cases']:
        yield case['hex']
    for case in STREAM['receiver_cases']['cases']:
        yield case['hex']
    yield EXT['caps_req']['hex']
    for group in ('caps', 'error', 'ping_lengths'):
        for case in EXT[group]:
            yield case['hex']
    yield EXT['play_trailing']['hex']


class HeaderTests(unittest.TestCase):
    def test_every_packet_has_a_consistent_header(self):
        for hex_string in all_packet_hex():
            packet = parse_packet(hex_string)
            self.assertEqual(packet['magic'], MAGIC, hex_string)
            self.assertEqual(len(packet['datagram']), 8 + packet['length'], hex_string)
            self.assertLessEqual(len(packet['datagram']), 512, hex_string)
            expected_version = 2 if packet['command'] in STREAM_COMMANDS else 1
            if packet['command'] not in STREAM_COMMANDS:
                self.assertEqual(packet['version'], expected_version, hex_string)


class PongClassificationTests(unittest.TestCase):
    def test_cases_follow_the_1x_and_0x_rules(self):
        ping = parse_packet(STREAM['pong_classification']['ping_hex'])
        _, incarnation = struct.unpack('<qQ', ping['payload'])
        for case in STREAM['pong_classification']['cases']:
            packet = parse_packet(case['hex'])
            self.assertEqual(packet['command'], 0x11)
            self.assertEqual(packet['seq'], ping['seq'], case['name'])
            self.assertEqual(packet['payload'][:8], ping['payload'][:8], case['name'])
            self.assertEqual(classify_1x(packet['payload']), case['expected_1x'], case['name'])
            if case['expected_0x'] != 'varies':
                self.assertEqual(classify_0x(packet['payload']), case['expected_0x'], case['name'])
            rest = pong_rest(packet['payload'])
            if case['expected_1x']['class'] == 'gen2':
                self.assertEqual(struct.unpack_from('<Q', rest, 8)[0], incarnation, case['name'])


class ReceiverTests(unittest.TestCase):
    def test_error_names_are_defined_in_message_format(self):
        for case in STREAM['receiver_cases']['cases']:
            error = case['expected']['error']
            if error is not None:
                self.assertIn(error, ERROR_CODES, case['name'])

    def test_reference_receiver_matches_every_case(self):
        context = STREAM['receiver_cases']['context']
        for case in STREAM['receiver_cases']['cases']:
            receiver = ReferenceReceiver({**context, **case.get('context_override', {})})
            accept, error = receiver.handle(case['from'], parse_packet(case['hex']))
            self.assertEqual({'accept': accept, 'error': error}, case['expected'], case['name'])


class ExtensionTests(unittest.TestCase):
    def test_caps_request(self):
        packet = parse_packet(EXT['caps_req']['hex'])
        self.assertEqual((packet['command'], packet['payload'][0]), (0x12, EXT['caps_req']['caps_version']))

    def test_caps_parse_ignores_unknown_and_reads_known_prefix(self):
        for case in EXT['caps']:
            packet = parse_packet(case['hex'])
            self.assertEqual(packet['command'], 0x13)
            self.assertEqual(parse_caps(packet['payload']), case['expected'], case['name'])

    def test_error_parse_and_codes(self):
        for case in EXT['error']:
            packet = parse_packet(case['hex'])
            self.assertEqual(packet['command'], 0xFF)
            expected = dict(case['expected'])
            name = expected.pop('name')
            self.assertEqual(ERROR_CODES[name], expected['error_code'], case['name'])
            self.assertEqual(parse_error(packet['payload']), expected, case['name'])

    def test_play_trailing_bytes_are_ignored(self):
        packet = parse_packet(EXT['play_trailing']['hex'])
        self.assertEqual(parse_play(packet['payload']), EXT['play_trailing']['expected'])

    def test_only_16_byte_ping_requests_a_lease(self):
        for case in EXT['ping_lengths']:
            packet = parse_packet(case['hex'])
            self.assertEqual(packet['length'] == 16, case['lease_request'], case['name'])


class ErrorTableTests(unittest.TestCase):
    def test_codes_are_unique(self):
        self.assertEqual(len(set(ERROR_CODES.values())), len(ERROR_CODES))
        self.assertGreaterEqual(len(ERROR_CODES), 11)


if __name__ == '__main__':
    unittest.main()
