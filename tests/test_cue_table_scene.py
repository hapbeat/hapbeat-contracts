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
           for name in ('cue-table', 'scene-session', 'scene-viewer-lib', 'scene-viewer-data')}
REGISTRY = Registry().with_resources((s['$id'], Resource.from_contents(s)) for s in SCHEMAS.values())
VALIDATORS = {name: Draft202012Validator(s, registry=REGISTRY) for name, s in SCHEMAS.items()}
CUES = load('fixtures/sample-cue-table.json')
SCENE = load('fixtures/sample-scene-recording.json')


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
            (['clips', 'Footstep'], {'intensity': 1, 'loop': False}),
            (['clips', 'grab', 'intensity'], 1.5),
            (['clips', 'grab', 'loop'], DELETE),
            (['sounds', 'Roar-C'], {'intensity': 1}),
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
        ]
        for path, value in cases:
            with self.subTest(path=path, value=value):
                self.assertFalse(v.is_valid(changed(base, path, value)))

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


if __name__ == '__main__':
    unittest.main()
