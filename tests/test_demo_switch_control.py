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
                       'haptics_on', 'haptics_off', 'haptics_ui_show', 'haptics_ui_hide']:
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

if __name__ == '__main__':
    unittest.main()
