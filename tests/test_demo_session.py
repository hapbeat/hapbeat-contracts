"""Run: python -m unittest discover -s tests -p test_demo_session.py"""
import copy
import json
import unittest
from pathlib import Path
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8-sig'))


DESCRIPTOR = Draft202012Validator(load('schemas/demo-session-descriptor.schema.json'))
TICKET = Draft202012Validator(load('schemas/demo-session-ticket.schema.json'))
DEVICE = Draft202012Validator(load('schemas/demo-device-address.schema.json'))
SHARE = Draft202012Validator(load('schemas/demo-remote-preset-share.schema.json'))
FIXTURES = load('fixtures/sample-demo-session.json')


class DescriptorTests(unittest.TestCase):
    def test_valid(self):
        Draft202012Validator.check_schema(DESCRIPTOR.schema)
        DESCRIPTOR.validate(FIXTURES['descriptor_volley'])
        DESCRIPTOR.validate(FIXTURES['descriptor_trex'])

    def test_defaults_and_when_reference_declared_values(self):
        for key in ('descriptor_volley', 'descriptor_trex'):
            options = {o['id']: o for o in FIXTURES[key]['options']}
            for option in options.values():
                self.assertIn(option['default'], [v['value'] for v in option['values']])
                for ref, values in option.get('when', {}).items():
                    declared = [v['value'] for v in options[ref]['values']]
                    self.assertTrue(set(values) <= set(declared))

    def test_rejects(self):
        base = FIXTURES['descriptor_volley']
        for changes in [dict(demo_id='Volley'), dict(version=2), dict(package='jp.x'), dict(supports={}),
                        dict(title={'en': 'x'})]:
            with self.subTest(changes=changes):
                self.assertFalse(DESCRIPTOR.is_valid(dict(base, **changes)))
        bad = copy.deepcopy(base)
        bad['options'][0]['values'][0]['value'] = '../x'
        self.assertFalse(DESCRIPTOR.is_valid(bad))


class TicketTests(unittest.TestCase):
    def test_valid(self):
        Draft202012Validator.check_schema(TICKET.schema)
        TICKET.validate(FIXTURES['ticket'])
        TICKET.validate(dict(FIXTURES['ticket'], hand_style='skin', recenter_ui=True))
        encoded = json.dumps(FIXTURES['ticket'], ensure_ascii=False).encode('utf-8')
        self.assertLessEqual(len(encoded), 16384)

    def test_rejects(self):
        base = FIXTURES['ticket']
        for changes in [dict(index=-1), dict(session_id='xyz'), dict(steps=[]), dict(extra=1),
                        dict(finish={'package': 'jp.hapbeat.demohub'}), dict(haptics_ui='false'), dict(hand_style='glove'), dict(recenter_ui='yes')]:
            with self.subTest(changes=changes):
                self.assertFalse(TICKET.is_valid(dict(base, **changes)))
        for field, value in [('package', 'not a package'), ('activity', '../evil'), ('options', {'scene': 'Block'}),
                             ('demo_id', 'Volley'), ('retry', 'yes')]:
            bad = copy.deepcopy(base)
            bad['steps'][0][field] = value
            with self.subTest(field=field):
                self.assertFalse(TICKET.is_valid(bad))
        for field in base:
            value = copy.copy(base)
            del value[field]
            self.assertFalse(TICKET.is_valid(value), field)



class DeviceAddressTests(unittest.TestCase):
    def test_valid(self):
        Draft202012Validator.check_schema(DEVICE.schema)
        DEVICE.validate(FIXTURES['device_address'])
        DEVICE.validate({'version': 1, 'player': 3, 'group': -1})

    def test_rejects(self):
        base = FIXTURES['device_address']
        for changes in [dict(group=0), dict(group=100), dict(player=-2), dict(group='2'), dict(version=2), dict(extra=1)]:
            with self.subTest(changes=changes):
                self.assertFalse(DEVICE.is_valid(dict(base, **changes)))
        for field in base:
            value = dict(base)
            del value[field]
            self.assertFalse(DEVICE.is_valid(value), field)



class RemotePresetShareTests(unittest.TestCase):
    def test_valid_and_fits_a_qr(self):
        Draft202012Validator.check_schema(SHARE.schema)
        SHARE.validate(FIXTURES['remote_preset_share'])
        encoded = json.dumps(FIXTURES['remote_preset_share'], ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        self.assertLessEqual(len(encoded), 1024)

    def test_rejects(self):
        base = FIXTURES['remote_preset_share']
        for changes in [dict(version=2), dict(presets=[]), dict(extra=1)]:
            with self.subTest(changes=changes):
                self.assertFalse(SHARE.is_valid(dict(base, **changes)))
        for preset in [{'name': '', 'steps': [{'demo_id': 'volley'}]}, {'name': 'a
b', 'steps': [{'demo_id': 'volley'}]},
                       {'name': 'x', 'steps': []}, {'name': 'x', 'steps': [{'demo_id': 'Volley'}]},
                       {'name': 'x', 'steps': [{'demo_id': 'volley', 'title': 't'}]},
                       {'name': 'x', 'steps': [{'demo_id': 'volley', 'retry': 'no'}]}]:
            with self.subTest(preset=preset):
                self.assertFalse(SHARE.is_valid({'version': 1, 'presets': [preset]}))


if __name__ == '__main__':
    unittest.main()
