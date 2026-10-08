"""Run: python -m unittest discover -s tests -p test_demo_switch_control.py"""
import copy
import hashlib
import hmac
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

def canonical_demos(demos):
    """`demos` HMAC value of HUB_SETTINGS (demo-switch-control.md, Authentication of the Hub settings and Hub start)."""
    return '|'.join(f"{demo['demo_id']};{1 if demo['visible'] else 0};{len(demo['title'].encode('utf-8'))}:{demo['title']}"
                    for demo in demos)

STATE_FIELDS = ['version', 'type', 'controller_id', 'nonce', 'current_demo_id', 'foreground', 'haptics_on', 'haptics_ui',
                'recenter_ui', 'paused', 'step_index', 'step_count']
STATE_OPTIONAL_FIELDS = ['device_model', 'editor', 'screen', 'hand_style']
# type -> (header, signed fields in order); STATE appends each optional field that is present.
CANONICAL = {
    'STATE': ('STATE', STATE_FIELDS),
    'CONTROL': ('COMMAND', ['version', 'type', 'controller_id', 'seq', 'demo_id', 'action', 'scene_id']),
    'HUB_SETTINGS_GET': ('HUB_SETTINGS_GET', ['version', 'type', 'controller_id', 'nonce', 'from']),
    'HUB_SETTINGS': ('HUB_SETTINGS', ['version', 'type', 'controller_id', 'nonce', 'revision', 'haptics_ui', 'recenter_ui',
                                      'hand_style', 'staff_waiting', 'player', 'group', 'demo_count', 'from', 'demos']),
    'HUB_SETTINGS_SET': ('COMMAND', ['version', 'type', 'controller_id', 'seq', 'demo_id', 'haptics_ui', 'recenter_ui',
                                     'hand_style', 'staff_waiting', 'visible_demos']),
    'HUB_START': ('COMMAND', ['version', 'type', 'controller_id', 'seq', 'demo_id', 'steps']),
}

def canonical_value(name, value):
    if name == 'steps':
        return canonical_steps(value)
    if name == 'demos':
        return canonical_demos(value)
    if name == 'visible_demos':
        return '|'.join(value)
    if isinstance(value, bool):
        return 'true' if value else 'false'
    return str(value)

def canonical_bytes(message):
    header, fields = CANONICAL[message['type']]
    if message['type'] == 'STATE':
        fields = fields + [name for name in STATE_OPTIONAL_FIELDS if name in message]
    text = f'HAPBEAT-DEMO-SWITCH/1\n{header}\n'
    for name in fields:
        value = canonical_value(name, message[name])
        text += f"{name}={len(value.encode('utf-8'))}:{value}\n"
    return text.encode('utf-8')

def sign(message, secret='test-secret'):
    return hmac.new(secret.encode('utf-8'), canonical_bytes(message), hashlib.sha256).hexdigest()

class HubParityTests(unittest.TestCase):
    NAMES = ['unsigned_state_extended', 'unsigned_state_partial', 'unsigned_control_hand_style', 'unsigned_hub_settings_get',
             'unsigned_hub_settings', 'unsigned_hub_settings_set', 'unsigned_hub_start']

    def test_fixtures_valid_and_within_datagram(self):
        validator = Draft202012Validator(SCHEMA)
        for name in self.NAMES:
            with self.subTest(name=name):
                validator.validate(FIXTURES[name])
                self.assertLessEqual(len(json.dumps(FIXTURES[name], ensure_ascii=False, separators=(',', ':')).encode('utf-8')), 1024)

    def test_new_actions_and_boundaries(self):
        validator = Draft202012Validator(SCHEMA)
        for action in ['hand_style_ghost', 'hand_style_skin', 'session_next', 'session_retry', 'hub_top', 'hub_replay']:
            validator.validate(dict(FIXTURES['unsigned_control_hand_style'], action=action))
        state = FIXTURES['unsigned_state_extended']
        for changes in [dict(device_model='x' * 64), dict(device_model='Quest 🙂'), dict(screen='manage'), dict(hand_style='skin')]:
            validator.validate(dict(state, **changes))
        settings = FIXTURES['unsigned_hub_settings']
        demo = {'demo_id': 'volley', 'title': 'x' * 40, 'visible': True}
        for changes in [dict(player=99, group=1), dict(player=-1), dict(demo_count=64, **{'from': 63}), dict(demo_count=0, demos=[]),
                        dict(demos=[demo] * 64), dict(demos=[dict(demo, title='バレー🙂')])]:
            validator.validate(dict(settings, **changes))
        ids = [f'demo{i}' for i in range(64)]
        validator.validate(dict(FIXTURES['unsigned_hub_settings_set'], visible_demos=[]))
        validator.validate(dict(FIXTURES['unsigned_hub_settings_set'], visible_demos=ids))
        validator.validate(dict(FIXTURES['unsigned_hub_settings_get'], **{'from': 63}))
        validator.validate(dict(FIXTURES['unsigned_hub_start'], steps=[{'demo_id': 'volley'}] * 32))

    def test_rejects_invalid(self):
        validator = Draft202012Validator(SCHEMA)
        demo = {'demo_id': 'volley', 'title': 'Volley', 'visible': True}
        cases = {
            'unsigned_state_extended': [dict(device_model=''), dict(device_model='x' * 65), dict(device_model='Quest\n3'),
                                        dict(device_model='Quest' + chr(0x85)), dict(device_model=3), dict(editor='no'),
                                        dict(screen='pause'), dict(hand_style='glove'), dict(hand_style=None)],
            'unsigned_control_hand_style': [dict(action='hand_style'), dict(action='hand_style_toggle'),
                                            dict(action='session_next', scene_id='block')],
            'unsigned_hub_settings_get': [dict(from_=-1), dict(from_=64), dict(seq=1), dict(nonce='xyz'), dict(extra=1)],
            'unsigned_hub_settings': [dict(revision=-1), dict(hand_style='glove'), dict(staff_waiting='no'), dict(player=0),
                                      dict(player=100), dict(group=-2), dict(group=1.5), dict(demo_count=65), dict(from_=64),
                                      dict(demos=[demo] * 65), dict(demos=[dict(demo, title='')]),
                                      dict(demos=[dict(demo, title='x' * 41)]), dict(demos=[dict(demo, title='a' + chr(9))]),
                                      dict(demos=[dict(demo, demo_id='Volley')]), dict(demos=[dict(demo, extra=1)]),
                                      dict(demos=[{'demo_id': 'volley', 'title': 'Volley'}]), dict(extra=1)],
            'unsigned_hub_settings_set': [dict(demo_id='volley'), dict(seq=0), dict(hand_style='glove'),
                                          dict(visible_demos=['volley', 'volley']), dict(visible_demos=['Volley']),
                                          dict(visible_demos=[f'demo{i}' for i in range(65)]), dict(nonce='0123456789abcdef')],
            'unsigned_hub_start': [dict(demo_id='volley'), dict(seq=0), dict(steps=[]), dict(steps=[{'demo_id': 'volley'}] * 33),
                                   dict(steps=[{'demo_id': 'volley', 'path': 'x'}]), dict(preset=1)],
        }
        for name, changes_list in cases.items():
            for changes in changes_list:
                changes = {('from' if key == 'from_' else key): value for key, value in changes.items()}
                with self.subTest(name=name, changes=changes):
                    self.assertFalse(validator.is_valid(dict(FIXTURES[name], **changes)))
        for name in self.NAMES:
            required = CANONICAL[FIXTURES[name]['type']][1]
            for field in required:
                value = copy.copy(FIXTURES[name])
                del value[field]
                self.assertFalse(validator.is_valid(value), (name, field))

    def test_hmac_reference_values(self):
        expected = {
            'unsigned_state_extended': '4722f50769469f635991a711f24fe04dd847136b02d1e6a2e241840d48b85cf1',
            'unsigned_state_partial': 'c1529021a52273598596f8cefde5c5da6d58ee912bee05219f29c4e1569b1a74',
            'unsigned_control_hand_style': '19428bbb3df765bcb2606f517c3a41328574b5acd23537c306768ea4478eee80',
            'unsigned_hub_settings_get': 'de07246f7208dac8a116de59f8b2bf5f5e82135e5e276084a4b99664dc3d197a',
            'unsigned_hub_settings': '33d8ca3fbb0e14efae9e8e505992d3f97446bcdcfed7774953b367485a4d1a49',
            'unsigned_hub_settings_set': 'dd5dc8984242f56413c51d6b17ddfee52dd40e3dc663bfbfbd13533f8155039b',
            'unsigned_hub_start': '8cc476ef9a64e5b376aad77225b57429736f116063bdf4149601e111bec1e7a2',
        }
        for name, digest in expected.items():
            with self.subTest(name=name):
                self.assertEqual(sign(FIXTURES[name]), digest)
                validator = Draft202012Validator(SCHEMA)
                validator.validate(dict(FIXTURES[name], auth=digest))

    def test_canonical_list_values(self):
        demos = canonical_demos(FIXTURES['unsigned_hub_settings']['demos'])
        self.assertEqual(demos, 'volley;1;6:Volley|fps;0;3:FPS')
        self.assertEqual(len(demos.encode('utf-8')), 29)
        self.assertIn(b'demos=29:volley;1;6:Volley|fps;0;3:FPS\n', canonical_bytes(FIXTURES['unsigned_hub_settings']))
        self.assertIn(b'visible_demos=6:volley\n', canonical_bytes(FIXTURES['unsigned_hub_settings_set']))
        self.assertIn(b'visible_demos=0:\n', canonical_bytes(dict(FIXTURES['unsigned_hub_settings_set'], visible_demos=[])))
        self.assertIn(b'steps=20:volley;scene=match;1\n', canonical_bytes(FIXTURES['unsigned_hub_start']))
        partial = canonical_bytes(FIXTURES['unsigned_state_partial'])
        self.assertTrue(partial.endswith(b'step_count=1:3\nscreen=10:completion\n'))
        self.assertNotIn(b'device_model=', partial)

if __name__ == '__main__':
    unittest.main()
