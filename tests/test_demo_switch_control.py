"""Run: python -m unittest discover -s tests -p test_demo_switch_control.py"""
import copy
import json
import unittest
from pathlib import Path
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / 'schemas/demo-switch-message.schema.json').read_text(encoding='utf-8-sig'))
FIXTURES = json.loads((ROOT / 'fixtures/sample-demo-switch-messages.json').read_text(encoding='utf-8-sig'))

class ControlTests(unittest.TestCase):
    def test_schema_and_control(self):
        Draft202012Validator.check_schema(SCHEMA)
        validator = Draft202012Validator(SCHEMA)
        value = FIXTURES['unsigned_control']
        validator.validate(value)
        for action in ['menu_open', 'menu_close', 'recenter', 'restart',
                       'haptics_on', 'haptics_off', 'haptics_ui_show', 'haptics_ui_hide',
                       'recenter_ui_show', 'recenter_ui_hide', 'tutorial_start']:
            validator.validate(dict(value, action=action, scene_id=''))

    def test_rejects_invalid_controls(self):
        validator = Draft202012Validator(SCHEMA)
        base = FIXTURES['unsigned_control']
        for changes in [dict(action='toggle'), dict(action='haptics_toggle'),
                        dict(action='haptics_on', scene_id='block'), dict(scene_id='../evil'), dict(scene_id=''),
                        dict(action='menu_open'), dict(seq=0), dict(auth='bad'), dict(path='arbitrary')]:
            with self.subTest(changes=changes):
                self.assertFalse(validator.is_valid(dict(base, **changes)))
        for field in base:
            value = copy.copy(base)
            del value[field]
            self.assertFalse(validator.is_valid(value), field)

class QueryStateTests(unittest.TestCase):
    def test_query_and_state(self):
        validator = Draft202012Validator(SCHEMA)
        validator.validate(FIXTURES['unsigned_query'])
        validator.validate(FIXTURES['unsigned_state'])
        for changes in [dict(paused='no'), dict(foreground='yes'), dict(step_index=-2), dict(extra=1), dict(nonce='xyz')]:
            with self.subTest(changes=changes):
                self.assertFalse(validator.is_valid(dict(FIXTURES['unsigned_state'], **changes)))
        state = dict(FIXTURES['unsigned_state'])
        del state['haptics_on']
        self.assertFalse(validator.is_valid(state))
        state = dict(FIXTURES['unsigned_state'])
        del state['foreground']
        self.assertFalse(validator.is_valid(state))

def canonical_steps(steps):
    """`steps` HMAC value of PRESET / PRESET_SET (demo-switch-control.md, Hub presets)."""
    encoded = []
    for step in steps:
        options = ','.join(f'{key}={value}' for key, value in sorted(step.get('options', {}).items()))
        encoded.append(f"{step['demo_id']};{options};{1 if step.get('retry', True) else 0}")
    return '|'.join(encoded)

class PresetTests(unittest.TestCase):
    NAMES = ['unsigned_preset_get', 'unsigned_preset', 'unsigned_preset_set', 'unsigned_preset_start']

    def test_fixtures_valid_and_within_datagram(self):
        validator = Draft202012Validator(SCHEMA)
        for name in self.NAMES:
            with self.subTest(name=name):
                validator.validate(FIXTURES[name])
                self.assertLessEqual(len(json.dumps(FIXTURES[name], ensure_ascii=False, separators=(',', ':')).encode('utf-8')), 1024)

    def test_empty_name_and_cleared_steps(self):
        validator = Draft202012Validator(SCHEMA)
        validator.validate(dict(FIXTURES['unsigned_preset_set'], name='', steps=[]))
        validator.validate(dict(FIXTURES['unsigned_preset'], name='', step_count=0, steps=[]))

    def test_rejects_invalid_presets(self):
        validator = Draft202012Validator(SCHEMA)
        cases = {
            'unsigned_preset_get': [dict(preset=0), dict(preset=4), dict(from_=-1), dict(seq=1), dict(nonce='xyz')],
            'unsigned_preset': [dict(revision=-1), dict(step_count=33), dict(visible='yes'), dict(name=' '),
                                dict(name='a' + chr(10)), dict(name='x' * 41), dict(extra=1)],
            'unsigned_preset_set': [dict(demo_id='volley'), dict(seq=0), dict(preset=4), dict(name='a' + chr(0x2028)),
                                    dict(steps=[{'demo_id': 'volley'}] * 33), dict(steps=[{'demo_id': 'Volley'}]),
                                    dict(steps=[{'demo_id': 'volley', 'path': 'x'}]),
                                    dict(steps=[{'demo_id': 'volley', 'options': {'scene': 'a;b'}}]), dict(nonce='0123456789abcdef')],
            'unsigned_preset_start': [dict(demo_id='volley'), dict(preset=0), dict(steps=[]), dict(seq=0)],
        }
        for name, changes_list in cases.items():
            for changes in changes_list:
                changes = {('from' if key == 'from_' else key): value for key, value in changes.items()}
                with self.subTest(name=name, changes=changes):
                    self.assertFalse(validator.is_valid(dict(FIXTURES[name], **changes)))
            for field in ['version', 'type', 'controller_id', 'preset']:
                value = copy.copy(FIXTURES[name])
                del value[field]
                self.assertFalse(validator.is_valid(value), (name, field))

    def test_canonical_steps_example(self):
        value = canonical_steps(FIXTURES['unsigned_preset_set']['steps'])
        self.assertEqual(value, 'energy-duel;tutorial=on;1|volley;scene=match;0')
        self.assertEqual(len(value.encode('utf-8')), 46)
        self.assertEqual(canonical_steps([]), '')
        self.assertEqual(canonical_steps([{'demo_id': 'boxing', 'options': {'b': '2', 'a': '1'}}]), 'boxing;a=1,b=2;1')

if __name__ == '__main__':
    unittest.main()
