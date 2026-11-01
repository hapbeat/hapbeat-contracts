"""Run: python -m unittest discover -s tests -p test_cue_table_scene.py"""
import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8-sig'))


SCHEMAS = {name: load(f'schemas/{name}.schema.json')
           for name in ('cue-table', 'cue-inventory', 'scene-session', 'scene-viewer-lib', 'scene-viewer-data',
                        'scene-log-record', 'scene-project')}
REGISTRY = Registry().with_resources((s['$id'], Resource.from_contents(s)) for s in SCHEMAS.values())
VALIDATORS = {name: Draft202012Validator(s, registry=REGISTRY) for name, s in SCHEMAS.items()}
CUES = load('fixtures/sample-cue-table.json')
SCENE = load('fixtures/sample-scene-recording.json')
LOG = [json.loads(line) for line in (ROOT / 'fixtures/sample-scene-log.jsonl').read_text(encoding='utf-8-sig').splitlines()
       if line.strip()]
PROJECT = load('fixtures/sample-scene-project.json')
INVENTORY = load('fixtures/sample-cue-inventory.json')


def changed(base, path, value):
    """A deep copy of base with path (keys / indices) set to value, or deleted when value is DELETE."""
    doc = copy.deepcopy(base)
    target = doc
    for key in path[:-1]:
        target = target[key]
    if value is DELETE:
        del target[path[-1]]
    else:
        target[path[-1]] = value
    return doc


DELETE = object()


class SchemaTests(unittest.TestCase):
    def test_schemas_are_valid(self):
        for validator in VALIDATORS.values():
            Draft202012Validator.check_schema(validator.schema)


class CueTableTests(unittest.TestCase):
    V = VALIDATORS['cue-table']

    def test_valid(self):
        self.V.validate(CUES)

    def test_rejects(self):
        cases = [
            (['schema_version'], 2),
            (['kit'], 'Sample_Kit'),
            (['cues', 'foot-step'], {}),
            (['clips', 'Footstep'], {'clip_gain': 1, 'loop': False}),
            (['clips', 'grab', 'clip_gain'], 1.5),
            (['clips', 'grab'], {'intensity': 0.6, 'loop': False}),  # the old name (DEC-103)
            (['sounds', 'Roar_A'], {'intensity': 1}),
            (['clips', 'grab', 'loop'], DELETE),
            (['sounds', 'Roar-C'], {'clip_gain': 1}),
            (['cues', 'grab', 'haptics', 0, 'clips'], ['grab']),          # clip and clips
            (['cues', 'purr', 'haptics', 0, 'alternates'], []),           # nothing starred, no alternates
            (['cues', 'grab', 'haptics', 0, 'at'], 'pos_foot'),
            (['cues', 'grab', 'haptics', 0, 'gain'], 3),
            (['cues', 'roar', 'sfx', 'sound'], 'Roar_A'),                 # sound and sounds
            (['cues', 'roar', 'sfx', 'volume'], DELETE),
            (['cues', 'rub', 'haptics', 0, 'levelMap', 'points'], [[0, 1]]),
            (['cues', 'rub', 'haptics', 0, 'levelMap', 'points'], [[1, 5]]),
            (['cues', 'rub', 'haptics', 0, 'levelMap', 'curve'], 'smooth'),
            (['cues', 'purr', 'emit', 'extra'], 1),
            (['cues', 'purr', 'emit', 'intervalSec'], 0.01),
            (['cues', 'footstep', 'variants', 'leave', 'rampTo'], 1),     # rampSteps with rampTo
            (['cues', 'footstep', 'variants', 'Leave'], {}),
            (['cues', 'footstep', 'variation', 'pick'], 'shuffle'),
            (['cues', 'footstep', 'variation', 'rateJitterPct'], 60),
            (['cues', 'footstep', 'review', 'sfx'], 'done'),
            (['cues', 'footstep', 'preview'], {'count': 5}),
            (['cues', 'footstep', 'distanceFalloff', 'farGain'], 3),
            (['cues', 'footstep', 'variants', 'approach', 'loop'], True),   # variant cannot be a loop
            (['cues', 'footstep', 'variants', 'approach', 'emit'], {'during': 'rub', 'intervalSec': 1}),
            (['cues', 'footstep', 'variants', 'approach', 'variants'], {}),
        ]
        for path, value in cases:
            with self.subTest(path=path, value=value):
                self.assertFalse(self.V.is_valid(changed(CUES, path, value)))

    def test_undecided_and_none(self):
        self.assertNotIn('sfx', CUES['cues']['bite'])
        self.assertIsNone(CUES['cues']['grab']['sfx'])
        self.V.validate(changed(CUES, ['cues', 'grab', 'haptics'], []))


class SceneTests(unittest.TestCase):
    def test_valid(self):
        VALIDATORS['scene-session'].validate(SCENE['session'])
        for key in ('viewer_lib_minimal', 'viewer_lib_layers'):
            VALIDATORS['scene-viewer-lib'].validate(SCENE[key])
        VALIDATORS['scene-viewer-data'].validate(SCENE['viewer_data'])

    def test_session_rejects(self):
        v, base = VALIDATORS['scene-session'], SCENE['session']
        cases = [
            (['video'], 'replay.mp4'),                                    # frames and video
            (['frames'], DELETE),                                         # neither
            (['events', 0, 'cue'], 'Footstep'),
            (['events', 0, 'cue'], 'footstep:approach:near'),
            (['events', 0, 'frame'], -1),
            (['events', 0, 'hand'], 'up'),
            (['levels', 'columns'], ['rub:gain:left', 'rub:level:right']),
            (['levels', 'rows', 0], [-1, 0]),
            (['lib', 'paths'], DELETE),
            (['lib', 'schema_version'], 2),
            (['project'], 'Sample Scene'),
            (['takes'], [{'start': 0, 'label': 'take 1'}]),               # takes item without end
            (['takes'], [{'start': 0, 'end': 0, 'label': 'take 1'}]),
            (['takes'], [{'start': 0, 'end': 90, 'label': 'take 1', 'expect': ['Grab']}]),
        ]
        for path, value in cases:
            with self.subTest(path=path, value=value):
                self.assertFalse(v.is_valid(changed(base, path, value)))

    def test_session_takes(self):
        takes = [{'start': 0, 'end': 150, 'label': 'take 1', 'expect': ['footstep', 'roar'], 'allow': ['footstep:approach']},
                 {'start': 150, 'end': 240, 'label': 'take 2'}]
        VALIDATORS['scene-session'].validate(changed(SCENE['session'], ['takes'], takes))

    def test_variant_references(self):
        lib = changed(SCENE['viewer_lib_minimal'], ['ticks'], ['footstep', 'footstep:approach'])
        lib['moment_rules'] = {'max': {'footstep:approach': 2}, 'min_gap_s': {'roar': 1.5}}
        VALIDATORS['scene-viewer-lib'].validate(lib)
        self.assertFalse(VALIDATORS['scene-viewer-lib'].is_valid(changed(lib, ['ticks'], ['footstep:Approach'])))

    def test_viewer_rejects(self):
        lib, data = VALIDATORS['scene-viewer-lib'], VALIDATORS['scene-viewer-data']
        for path, value in [(['at'], ['hand', 'wrist']), (['families'], [{'label': 'x', 'color': 'red', 'cues': []}]),
                            (['layers', 0, 'level'], [0])]:
            with self.subTest(path=path):
                self.assertFalse(lib.is_valid(changed(SCENE['viewer_lib_layers'], path, value)))
        for path, value in [(['video'], DELETE), (['events', 0, 't'], -0.5), (['frames'], 0)]:
            with self.subTest(path=path):
                self.assertFalse(data.is_valid(changed(SCENE['viewer_data'], path, value)))

    def test_viewer_chapters(self):
        v = VALIDATORS['scene-viewer-data']
        chapters = [{'start': 0, 'end': 4.5, 'label': 'approach'}, {'start': 4, 'end': 8, 'label': 'grab'}]
        v.validate(changed(SCENE['viewer_data'], ['chapters'], chapters))       # overlap and gaps are allowed
        for item in [{'start': 0, 'end': 4.5}, {'start': -1, 'end': 4.5, 'label': 'x'},
                     {'start': 0, 'end': 0, 'label': 'x'}, {'start': 0, 'end': 4.5, 'label': ''}]:
            with self.subTest(item=item):
                self.assertFalse(v.is_valid(changed(SCENE['viewer_data'], ['chapters'], [item])))


class SceneLogTests(unittest.TestCase):
    V = VALIDATORS['scene-log-record']

    def test_valid(self):
        for line, record in enumerate(LOG, 1):
            with self.subTest(line=line):
                self.V.validate(record)
        self.assertEqual({r['t'] for r in LOG}, {'start', 'take', 'take_end', 'cue', 'level', 'fail', 'end'})
        cues = [r for r in LOG if r['t'] == 'cue']
        self.assertTrue(any('cue' in r for r in cues) and any('source' in r for r in cues))
        self.assertGreaterEqual(sum(1 for r in LOG if r['t'] == 'take'), 2)

    def test_rejects(self):
        cue = next(r for r in LOG if r['t'] == 'cue' and 'cue' in r)
        take = next(r for r in LOG if r['t'] == 'take')
        start = next(r for r in LOG if r['t'] == 'start')
        level = next(r for r in LOG if r['t'] == 'level')
        end = next(r for r in LOG if r['t'] == 'end')
        fail = next(r for r in LOG if r['t'] == 'fail')
        cases = [
            (cue, ['source'], 'unity:ce65e997e9d54d2eabde0d646dea67c7'),   # cue and source
            (cue, ['cue'], DELETE),                                       # neither
            (cue, ['cue'], 'Roar'),
            (cue, ['frame'], -1),
            (cue, ['hand'], 'up'),
            (cue, ['t'], 'sound'),                                        # unknown t
            (level, ['values'], {'rub:gain:left': 0.4}),
            (level, ['values'], {'rub:level:left': -0.1}),
            (take, ['label'], DELETE),
            (take, ['expect'], ['Footstep']),
            (end, ['frames'], DELETE),
            (end, ['frames'], 0),
            (start, ['schema_version'], 2),
            (start, ['fps'], 0),
            (start, ['fps'], 241),
            (fail, ['reason'], DELETE),
        ]
        for base, path, value in cases:
            with self.subTest(t=base['t'], path=path, value=value):
                self.assertFalse(self.V.is_valid(changed(base, path, value)))
        self.V.validate(changed(cue, ['extra'], 1))                         # unknown fields are ignored

    def test_level_by_source(self):
        level = next(r for r in LOG if r['t'] == 'level')
        by_source = {'t': 'level', 'frame': level['frame'], 'source': 'unity:d7dd66801f2a4c0e9b3a5c6d7e8f9012/1f2e3d4c5b6a47980a1b2c3d4e5f6a7b',
                     'value': 0.4, 'hand': 'right'}
        self.V.validate(by_source)
        for path, value in [(['values'], {'rub:level:right': 0.4}),   # values and source
                            (['value'], DELETE), (['value'], -1), (['hand'], 'up')]:
            with self.subTest(path=path):
                self.assertFalse(self.V.is_valid(changed(by_source, path, value)))
        self.assertFalse(self.V.is_valid({'t': 'level', 'frame': 1}))   # neither values nor source
        self.assertFalse(self.V.is_valid(changed(level, ['value'], 0.4)))  # values with value


class SceneProjectTests(unittest.TestCase):
    V = VALIDATORS['scene-project']

    def test_valid(self):
        self.V.validate(PROJECT)
        sources = {r['source'] for r in LOG if r['t'] == 'cue' and 'source' in r}
        self.assertLessEqual(sources, {b['source'] for b in PROJECT['bindings']})

    def test_rejects(self):
        cases = [
            (['video'], 'replay.mp4'),                                    # frames and video
            (['frames'], DELETE),                                         # neither
            (['capture'], 'x'),
            (['bindings', 0, 'cue'], DELETE),
            (['bindings', 0, 'source'], 'ce65e997'),
            (['bindings', 0, 'hand'], 'up'),
            (['log'], ''),
            (['columns'], ['rub:gain:left']),
            (['columns'], ['rub:level:left', 'rub:level:left']),
            (['lib', 'paths'], DELETE),
            (['schema_version'], 2),
        ]
        for path, value in cases:
            with self.subTest(path=path, value=value):
                self.assertFalse(self.V.is_valid(changed(PROJECT, path, value)))
        self.V.validate(changed(PROJECT, ['columns'], ['rub:level:left', 'rub:level:right']))


class CueInventoryTests(unittest.TestCase):
    V = VALIDATORS['cue-inventory']

    def test_valid(self):
        self.V.validate(INVENTORY)

    def test_rejects(self):
        cases = [
            (['engine'], 'cry'),
            (['events', 0, 'source'], DELETE),
            (['events', 0, 'source'], 'ce65e997'),
            (['events', 0, 'loop'], DELETE),
            (['events', 0, 'target'], DELETE),
            (['events', 0, 'gain'], -1),
            (['events', 0, 'cue'], 'GrabLight'),
            (['events', 0, 'clip_gain'], 1.5),
            (['events', 3, 'levelMap', 'points'], [[0, 1]]),
            (['maps', 0, 'referenced'], DELETE),
            (['schema_version'], 2),
        ]
        for path, value in cases:
            with self.subTest(path=path, value=value):
                self.assertFalse(self.V.is_valid(changed(INVENTORY, path, value)))


class KitManifestTests(unittest.TestCase):
    """The material strength is `parameters.clip_gain` (DEC-103); the old `intensity` is not accepted."""
    V = Draft202012Validator(load('schemas/kit-manifest.schema.json'))
    KIT = load('fixtures/sample-kit-manifest.json')

    def test_valid(self):
        self.V.validate(self.KIT)

    def test_rejects_old_name(self):
        event = next(iter(self.KIT['events']))
        for value in ({'intensity': 0.5}, {'clip_gain': 1.5}):
            with self.subTest(value=value):
                self.assertFalse(self.V.is_valid(changed(self.KIT, ['events', event, 'parameters'], value)))


if __name__ == '__main__':
    unittest.main()
