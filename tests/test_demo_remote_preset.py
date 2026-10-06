"""Run: python -m unittest discover -s tests -p test_demo_remote_preset.py"""
import base64
import json
import re
import unittest
from pathlib import Path
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 700
MAX_TOKEN = 937
TOKEN = re.compile(r'^v1\.[A-Za-z0-9_-]+$')


def load(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8-sig'))


SCHEMA = Draft202012Validator(load('schemas/demo-remote-preset.schema.json'))
FIXTURES = load('fixtures/sample-demo-remote-preset.json')


def encode(payload):
    raw = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return 'v1.' + base64.urlsafe_b64encode(raw).decode('ascii').rstrip('=')


def _no_duplicates(pairs):
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError('duplicate key')
    return dict(pairs)


def decode(token):
    """Receiver-side rules of demo-session.md: token check, strict base64url and UTF-8, no duplicate keys."""
    if len(token) > MAX_TOKEN or not TOKEN.match(token):
        raise ValueError('invalid token')
    body = token[3:]
    raw = base64.urlsafe_b64decode(body + '=' * (-len(body) % 4))
    if len(raw) > MAX_BYTES:
        raise ValueError('payload too large')
    return json.loads(raw.decode('utf-8'), object_pairs_hook=_no_duplicates)


class RemotePresetTests(unittest.TestCase):
    def test_schema_and_valid(self):
        Draft202012Validator.check_schema(SCHEMA.schema)
        SCHEMA.validate(FIXTURES['valid'])
        SCHEMA.validate(FIXTURES['valid_token_json'])

    def test_rejects(self):
        for i, payload in enumerate(FIXTURES['invalid']):
            with self.subTest(i=i):
                self.assertFalse(SCHEMA.is_valid(payload))

    def test_more_than_three_presets(self):
        one = FIXTURES['valid']['presets'][0]
        self.assertFalse(SCHEMA.is_valid({'version': 1, 'presets': [one] * 4}))

    def test_token_round_trip(self):
        self.assertEqual(decode(FIXTURES['valid_token']), FIXTURES['valid_token_json'])
        self.assertEqual(encode(FIXTURES['valid_token_json']), FIXTURES['valid_token'])
        self.assertEqual(decode(encode(FIXTURES['valid'])), FIXTURES['valid'])

    def test_token_has_no_padding_and_is_url_safe(self):
        token = encode(FIXTURES['valid'])
        self.assertNotIn('=', token)
        self.assertNotIn('+', token)
        self.assertNotIn('/', token)

    def test_invalid_tokens(self):
        for token in FIXTURES['invalid_tokens']:
            with self.subTest(token=token[:20]):
                with self.assertRaises((ValueError, UnicodeDecodeError)):
                    decode(token)

    def test_duplicate_keys(self):
        raw = b'{"version":1,"version":1,"presets":[]}'
        token = 'v1.' + base64.urlsafe_b64encode(raw).decode('ascii').rstrip('=')
        with self.assertRaises(ValueError):
            decode(token)

    def test_max_payload_fits_token_limit(self):
        token = 'v1.' + base64.urlsafe_b64encode(b'x' * MAX_BYTES).decode('ascii').rstrip('=')
        self.assertLessEqual(len(token), MAX_TOKEN)

    def test_size_limit(self):
        self.assertLessEqual(len(json.dumps(FIXTURES['valid'], ensure_ascii=False,
                                            separators=(',', ':')).encode('utf-8')), MAX_BYTES)
        big = {'version': 1, 'presets': [{'name': 'x' * 40, 'steps': [
            {'demo_id': 'trex-encounter', 'options': {'tutorial': 'off'}}] * 32}] * 3}
        with self.assertRaises(ValueError):
            decode(encode(big))


if __name__ == '__main__':
    unittest.main()
