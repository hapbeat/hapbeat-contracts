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

if __name__ == '__main__':
    unittest.main()
