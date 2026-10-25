import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pipeline'))
from prepare_artsquad import assign_groups, assign_split, capture_evidence, prepare


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.data = self.root / 'data'
        self.work = self.root / 'artifacts'
        (self.data / 'originals').mkdir(parents=True)
        (self.work / 'images').mkdir(parents=True)
        self.config = {'minimum_short_side': 10, 'capture_year_min': 2000,
                       'targets': [{'id': 'white', 'name': 'White Hall', 'role': 'quad-core'}]}
        self.manifest = {'status': 'running', 'images': []}
        self.inventory = {'config': self.config, 'pages': []}

    def tearDown(self): self.temp.cleanup()

    def add(self, index, artist=None, date=None, title='File:Cornell White Hall exterior.jpg', categories=''):
        date = date or f'2019-01-{index + 1:02d}'
        original = self.data / 'originals' / f'{index}.png'
        working = self.work / 'images' / f'modern__{index}.jpg'
        Image.new('RGB', (32, 24), (index * 11 % 255, 80, 120)).save(original)
        Image.open(original).save(working)
        sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
        row = {'pageid': index, 'filename': working.name, 'original_filename': original.name,
               'title': title, 'sha256_original': sha(original), 'sha256_working': sha(working),
               'original_size': [32, 24], 'working_size': [32, 24], 'capture_date_asserted': date,
               'artist': artist or f'Author {index}', 'license': 'CC BY 4.0', 'dhash64': f'{index * 178867:016x}',
               'discovery': {'targets': ['white'], 'sources': ['Category:White Hall (Cornell University)']}}
        page = {'pageid': index, 'title': title, 'discovery': row['discovery'],
                'imageinfo': [{'mime': 'image/jpeg', 'width': 32, 'height': 24,
                               'extmetadata': {'DateTimeOriginal': {'value': date},
                                               'Categories': {'value': categories},
                                               'LicenseShortName': {'value': 'CC BY 4.0'}}}]}
        self.manifest['images'].append(row)
        self.inventory['pages'].append(page)
        return row

    def run_prepare(self):
        self.manifest_path = self.data / 'manifest.json'
        inventory_path = self.data / 'inventory.json'
        self.manifest_path.write_text(json.dumps(self.manifest))
        inventory_path.write_text(json.dumps(self.inventory))
        path = prepare(self.manifest_path, inventory_path, self.work)
        return path, json.loads((path / 'snapshot.json').read_text())

    def test_running_snapshot_immutable_and_no_input_changes(self):
        for i in range(12): self.add(i)
        path, report = self.run_prepare()
        before = (path / 'snapshot.json').read_bytes()
        manifest_bytes = self.manifest_path.read_bytes()
        again, report2 = self.run_prepare()
        self.assertEqual(path, again)
        self.assertEqual(before, (again / 'snapshot.json').read_bytes())
        self.assertEqual(manifest_bytes, self.manifest_path.read_bytes())
        self.assertEqual(report['source_manifest_sha256'], hashlib.sha256(manifest_bytes).hexdigest())
        self.assertEqual(report['counts']['train_files'] + report['counts']['test_files'], 12)
        self.assertTrue(.15 <= report['counts']['test_files'] / 12 <= .20)
        self.assertFalse(report['claims']['geometric_coverage_verified'])
        self.assertTrue((path / 'input-contact-white.jpg').exists())
        self.assertTrue(any('partial acquisition' in item for item in report['limitations']))

    def test_groups_do_not_leak_author_day_or_exact_original(self):
        for i in range(12): self.add(i)
        self.manifest['images'][1]['artist'] = self.manifest['images'][0]['artist']
        self.manifest['images'][1]['capture_date_asserted'] = self.manifest['images'][0]['capture_date_asserted']
        # The same original may have two derived renditions/filenames.
        self.manifest['images'][2]['original_filename'] = self.manifest['images'][0]['original_filename']
        self.manifest['images'][2]['sha256_original'] = self.manifest['images'][0]['sha256_original']
        _, report = self.run_prepare()
        rows = {i['pageid']: i for i in report['images']}
        self.assertEqual(rows[0]['exposure_group_id'], rows[2]['exposure_group_id'])
        self.assertEqual(len({rows[i]['source_family_id'] for i in (0, 1, 2)}), 1)
        self.assertEqual(len({rows[i]['split'] for i in (0, 1, 2)}), 1)

    def test_role_exclusions_and_invalid_hash_are_explicit(self):
        self.add(0)
        self.add(1, title='File:Cornell White Hall plans.jpg')
        self.add(2, title='File:Cornell White Hall Interior.jpg')
        self.add(3)['projection_hint'] = 'equirectangular'
        self.add(4, title='File:Cornell White Hall construction.jpg')
        self.add(5)['sha256_working'] = '0' * 64
        path, report = self.run_prepare()
        rows = {i['pageid']: i for i in report['images']}
        self.assertEqual(rows[1]['role'], 'reference-document')
        self.assertEqual(rows[2]['role'], 'interior')
        self.assertEqual(rows[3]['role'], 'panorama-camera-review')
        self.assertEqual(rows[4]['role'], 'structural-epoch-review')
        self.assertEqual(rows[5]['split'], 'rejected')
        self.assertTrue(any('SHA256 mismatch' in e for e in rows[5]['validation']['errors']))
        listed = (path / 'train.txt').read_text() + (path / 'test.txt').read_text()
        for i in (1, 2, 3, 4, 5): self.assertNotIn(f'modern__{i}.jpg', listed)

    def test_missing_and_upload_only_capture_dates_rejected(self):
        self.add(0, date='unknown')
        self.add(1, date='28 March 2007 (original upload date)')
        _, report = self.run_prepare()
        self.assertEqual(report['counts']['rejected_files'], 2)
        self.assertEqual(report['counts']['test_files'], 0)
        self.assertTrue(any('No metadata-eligible' in s for s in report['limitations']))

    def test_bad_image_with_matching_digest_still_rejected(self):
        row = self.add(0)
        broken = self.work / 'images' / row['filename']
        broken.write_bytes(b'not an image')
        row['sha256_working'] = hashlib.sha256(broken.read_bytes()).hexdigest()
        _, report = self.run_prepare()
        self.assertEqual(report['images'][0]['split'], 'rejected')

    def test_new_record_changes_id_without_overwriting_old_snapshot(self):
        self.add(0)
        first, _ = self.run_prepare()
        self.add(1)
        second, _ = self.run_prepare()
        self.assertNotEqual(first, second)
        self.assertTrue((first / 'snapshot.json').exists())

    def test_tiny_stratum_limitation_and_no_forced_leakage(self):
        for i in range(4): self.add(i, artist='Single Author', date='2019-01-01')
        _, report = self.run_prepare()
        self.assertTrue(any('only 1 metadata source family' in item for item in report['limitations']))
        self.assertEqual(len({i['split'] for i in report['images']}), 1)
        self.assertEqual(report['images'][0]['split'], 'train')

    def test_single_family_target_kept_in_train_even_if_group_spans_other_targets(self):
        first = self.add(0, artist='One session', date='2019-01-01')
        first['discovery']['targets'].append('rare-target')
        self.add(1, artist='One session', date='2019-01-01')
        for i in range(2, 12): self.add(i)
        _, report = self.run_prepare()
        self.assertEqual(next(i for i in report['images'] if i['pageid'] == 0)['split'], 'train')

    def test_perceptual_copies_flagged_not_certified_same_exposure(self):
        self.add(0)['dhash64'] = '0' * 16
        self.add(1)['dhash64'] = '0' * 16
        _, report = self.run_prepare()
        a, b = report['images']
        self.assertNotEqual(a['exposure_group_id'], b['exposure_group_id'])
        self.assertEqual(report['perceptual_copy_candidates'][0]['status'], 'needs-geometric-exposure-audit')
        self.assertFalse(report['claims']['capture_independence_verified'])

    def test_partial_date_merges_overlapping_author_session(self):
        self.add(0, artist='Same Author', date='2019-01')
        self.add(1, artist='Same Author', date='2019-01-23')
        self.add(2, artist='Different Author', date='2019-01-23')
        _, report = self.run_prepare()
        a, b, c = report['images']
        self.assertEqual(a['source_family_id'], b['source_family_id'])
        self.assertNotEqual(a['source_family_id'], c['source_family_id'])

    def test_explicit_video_family_groups_distinct_days_and_authors(self):
        self.add(0)['video_id'] = 'clip-001'
        self.add(1)['video_id'] = 'clip-001'
        self.add(2)['video_id'] = 'clip-002'
        _, report = self.run_prepare()
        a, b, c = report['images']
        self.assertEqual(a['source_family_id'], b['source_family_id'])
        self.assertEqual(a['split'], b['split'])
        self.assertNotEqual(a['source_family_id'], c['source_family_id'])

    def test_input_path_cannot_escape_originals(self):
        row = self.add(0)
        row['original_filename'] = '../manifest.json'
        _, report = self.run_prepare()
        self.assertEqual(report['images'][0]['split'], 'rejected')
        self.assertTrue(any('escapes input directory' in s for s in report['images'][0]['validation']['errors']))

    def test_photostitch_not_assumed_pinhole_without_xmp(self):
        self.add(0, title='File:Cornell White Hall photostitch recti.jpg')
        self.add(1, title='File:Cornell Arts Quad Panorama.jpg')
        _, report = self.run_prepare()
        self.assertTrue(all(i['role'] == 'panorama-camera-review' for i in report['images']))
        self.assertEqual(report['counts']['train_files'], 0)

    def test_event_people_images_not_treated_as_building_exterior(self):
        self.add(0, title='File:Art + Feminism at White Hall Cornell University.jpg')
        self.add(1, title='File:Editors researching during the Cornell White Hall event.jpg')
        self.add(2, title='File:Cornell White Hall photo.jpg', categories='ArtAndFeminism 2018/Cornell')
        _, report = self.run_prepare()
        self.assertTrue(all(i['role'] == 'interior-event-review' for i in report['images']))
        self.assertEqual(report['counts']['excluded_files'], 3)

    def test_exif_capture_can_disambiguate_upload_only_assertion(self):
        evidence, error = capture_evidence({'capture_date_asserted': '28 March 2007 (original upload date)',
                                          'exif': {'date_time_original': '2006:07:01 12:30:00'}}, 2000)
        self.assertIsNone(error)
        self.assertEqual(evidence['earliest'], '2006-07-01')
        self.assertEqual(evidence['origin'], 'exif:DateTimeOriginal')


if __name__ == '__main__': unittest.main()
