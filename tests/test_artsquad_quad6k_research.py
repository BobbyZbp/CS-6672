import copy
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pipeline'))
from artsquad_provider_probe import SOURCES
from prepare_quad6k_research import (BBOX, capture_assertion, location_screen, parse_geotags,
                                     prepare, validate_recovered_member, working_exif)
from run_artsquad_sfm import select_training_images, sha256


class Quad6KResearchPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.data, self.work = self.root / 'data', self.root / 'work'
        self.data.mkdir()
        self.manifest = {'schema_version': 2, 'recovered_research_members': [], 'requests': []}
        self.manifest_path = self.data / 'manifest.json'

    def tearDown(self): self.temp.cleanup()

    def add_member(self, index, *, day=None, modification='2011:01:01 00:00:00', orientation=1, kind='image', text=None, payload_override=None):
        name = 'ArtsQuad_dataset/images/' + str(index) + '_photo.jpg' if kind == 'image' else 'ArtsQuad_dataset/geotags.txt'
        if kind == 'image':
            raw = Image.new('RGB', (320, 240), ((index * 47) % 255, 80, 150))
            exif = Image.Exif(); exif[271] = 'Canon'; exif[272] = 'Canon EOS DIGITAL REBEL XSi'
            exif[274] = orientation
            if modification is not None: exif[306] = modification
            sub = {37386: 18, 41989: 29}
            if day is not None: sub[36867] = day + ' 12:34:56'
            exif[34665] = sub
            buffer = io.BytesIO(); raw.save(buffer, format='JPEG', exif=exif)
            payload = buffer.getvalue()
            dimensions, format_name = [320, 240], 'JPEG'
        else: payload = text.encode()
        if payload_override is not None: payload = payload_override
        digest = hashlib.sha256(payload).hexdigest()
        path = self.data / (digest[:20] + '__' + Path(name).name); path.write_bytes(payload)
        offset, total = index * 102400, 90000000
        url = SOURCES['quad6k-2016-frame']
        def request(start, body):
            return {'url': url, 'final_url': url, 'range_requested': [start, start + len(body) - 1],
                    'http_status': 206, 'bytes_read': len(body), 'range_delivery_verified': True,
                    'content_range': {'start': start, 'end': start + len(body) - 1, 'total': total},
                    'headers': {'content-type': 'application/x-tar'}, 'prefix_sha256': hashlib.sha256(body).hexdigest()}
        header = request(offset, b'h' * 512)
        body_requests = [request(offset + 512 + a, payload[a:a + 1024]) for a in range(0, len(payload), 1024)]
        self.manifest['requests'] += [header] + body_requests
        complete = {'name': name, 'size': len(payload), 'sha256': digest, 'kind': kind}
        if kind == 'image': complete.update(dimensions=dimensions, format=format_name)
        row = {'source': 'quad6k-2016-frame', 'url': url, 'header_offset': offset, 'header_request': header,
               'header_sha256': header['prefix_sha256'], 'rights_status': 'unknown_local_research_inspection_only',
               'public_redistribution_permitted': False, 'reconstruction_input_admitted': False,
               'archive_completeness_verified': False, 'original_bytes_preserved': True,
               'status': 'complete_research_member_recovered', 'file': str(path),
               'member': {'name': name, 'size': len(payload), 'type': 'file',
                          'next_header_delta': 512 + ((len(payload) + 511) // 512) * 512},
               'complete_member': complete}
        self.manifest['recovered_research_members'].append(row)
        return row

    def run_prepare(self, role_reviews=()):
        self.manifest_path.write_text(json.dumps(self.manifest))
        path = prepare([self.manifest_path], self.work, self.data, role_reviews)
        return path, json.loads((path / 'snapshot.json').read_text())

    def test_actual_compatible_private_snapshot_never_grants_public_rights(self):
        for i in range(1, 7): self.add_member(i, day=f'2010:03:{i:02d}')
        path, report = self.run_prepare()
        self.assertFalse(report['public_redistribution_permitted'])
        self.assertEqual(report['scope'], 'private-research-only')
        self.assertEqual(len(select_training_images(report)), 5)
        for image in report['images']:
            self.assertEqual(image['license'], 'UNKNOWN')
            self.assertFalse(image['public_redistribution_permitted'])
            self.assertFalse(image['research_use_permission_certified'])
            self.assertEqual(image['discovery']['targets'], ['artsquad-context'])
            self.assertFalse(image['target_identity_verified'])
        self.assertTrue((path / 'input-contact-artsquad-context.jpg').exists())

    def test_nested_original_capture_date_wins_over_modification_time(self):
        self.add_member(1, day='2010:03:06')
        _, report = self.run_prepare()
        record = report['images'][0]
        self.assertEqual(record['capture_evidence']['origin'], 'exif:DateTimeOriginal')
        self.assertEqual(record['capture_evidence']['earliest'], '2010-03-06')
        self.assertEqual(record['exif']['date_time'], '2011:01:01 00:00:00')

    def test_weak_date_fallback_is_never_invented_original(self):
        evidence, reason, value = capture_assertion({'date_time': '2010:03:06 12:34:56'})
        self.assertEqual(evidence['origin'], 'exif:DateTime-weak-not-original')
        self.assertFalse(evidence['capture_epoch_certified'])
        evidence, reason, value = capture_assertion({})
        self.assertIsNone(evidence)
        self.assertTrue(reason)

    def test_missing_dates_remain_conservatively_one_family(self):
        self.add_member(1, modification=None); self.add_member(2, modification=None)
        _, report = self.run_prepare()
        self.assertEqual(report['counts']['metadata_source_families'], 1)
        self.assertEqual(report['counts']['test_files'], 0)
        self.assertTrue(all(i['capture_evidence'] is None for i in report['images']))
        self.assertTrue(any('only 1 metadata source family' in s for s in report['limitations']))

    def test_orientation_transposed_once_and_physical_optics_preserved(self):
        self.add_member(1, day='2010:03:06', orientation=6)
        _, report = self.run_prepare(); record = report['images'][0]
        self.assertEqual(record['oriented_original_size'], [240, 320])
        self.assertEqual(record['working_size'], [240, 320])
        with Image.open(record['working_path']) as image:
            self.assertEqual(image.getexif().get(274, 1), 1)
            self.assertEqual(image.getexif()[271], 'Canon')
            self.assertEqual(float(image.getexif().get_ifd(34665)[37386]), 18.)
            self.assertFalse(image.getexif().get_ifd(34853))

    def test_gps_is_stripped_but_original_date_and_focal_retained(self):
        photo = Image.new('RGB', (320, 240)); raw = Image.Exif()
        raw[271] = 'Canon'; raw[34665] = {36867: '2010:03:06 12:34:56', 37386: 18}
        raw[34853] = {1: 'N', 2: (42, 27, 0), 3: 'W', 4: (76, 29, 0)}
        buffer = io.BytesIO(); photo.save(buffer, format='JPEG', exif=raw); buffer.seek(0)
        with Image.open(buffer) as loaded:
            result = working_exif(loaded, (160, 120))
            self.assertNotIn(34853, result)
            self.assertEqual(result[34665][37386], 18)
            self.assertEqual(result[34665][40962], 160)

    def test_automatic_geotag_scope_filter_not_filename_denylist(self):
        self.add_member(1, day='2010:03:06'); self.add_member(2, day='2010:03:07')
        self.add_member(10, kind='reference_metadata', text='1_photo.jpg 42.471166 -76.463833\n2_photo.jpg 42.45053 -76.4855665\n')
        _, report = self.run_prepare()
        outside = next(i for i in report['images'] if '1_photo' in i['filename'])
        inside = next(i for i in report['images'] if '2_photo' in i['filename'])
        self.assertEqual(outside['role'], 'out-of-scope-location-review')
        self.assertEqual(outside['split'], 'excluded')
        self.assertEqual(inside['role'], 'scene-candidate')
        self.assertFalse(inside['location_scope_screen']['fitted_pose_prior'])
        self.assertFalse(inside['location_scope_screen']['inside_scope_proves_building_identity'])

    def test_conflicting_location_sources_excluded_not_selected_for_convenience(self):
        result = location_screen('a.jpg', {'latitude': 42.471, 'longitude': -76.463}, {'a.jpg': (42.45, -76.485)})
        self.assertEqual(result['status'], 'outside-or-conflicting-location-review')

    def test_unknown_location_is_explicit_not_made_up(self):
        result = location_screen('a.jpg', {}, {})
        self.assertEqual(result['status'], 'location-unknown')
        self.assertEqual(result['assertions'], [])

    def test_missing_body_range_cannot_be_admitted(self):
        row = self.add_member(1, day='2010:03:06')
        self.manifest['requests'].pop()
        with self.assertRaises(ValueError): validate_recovered_member(row, self.manifest, self.data)
        _, report = self.run_prepare()
        self.assertEqual(report['counts']['train_files'], 0)
        self.assertEqual(report['counts']['rejected_member_ledger_records'], 1)

    def test_body_chunk_hash_checked_not_just_member_hash(self):
        row = self.add_member(1, day='2010:03:06')
        self.manifest['requests'][-1]['prefix_sha256'] = '0' * 64
        with self.assertRaises(ValueError): validate_recovered_member(row, self.manifest, self.data)

    def test_wrong_http_status_partial_range_and_false_bool_fail_closed(self):
        for replacement in ({'http_status': 200}, {'range_delivery_verified': 1}, {'bytes_read': 1}):
            with self.subTest(replacement=replacement):
                manifest = copy.deepcopy(self.manifest); row = self.add_member(len(self.manifest['recovered_research_members']) + 1, day='2010:03:06')
                self.manifest['requests'][-1].update(replacement)
                with self.assertRaises(ValueError): validate_recovered_member(row, self.manifest, self.data)
                self.manifest = manifest

    def test_unsafe_member_paths_and_symlink_files_rejected(self):
        row = self.add_member(1, day='2010:03:06')
        unsafe = copy.deepcopy(row); unsafe['member']['name'] = '../outside.jpg'
        with self.assertRaises(ValueError): validate_recovered_member(unsafe, self.manifest, self.data)
        link = self.data / 'symlink.jpg'; link.symlink_to(row['file']); row['file'] = str(link)
        with self.assertRaises(ValueError): validate_recovered_member(row, self.manifest, self.data)

    def test_original_tampering_rejected(self):
        row = self.add_member(1, day='2010:03:06')
        path = Path(row['file']); data = path.read_bytes(); path.write_bytes(data[:-1] + bytes([data[-1] ^ 1]))
        with self.assertRaises(ValueError): validate_recovered_member(row, self.manifest, self.data)

    def test_undecodable_complete_member_with_valid_hash_rejected_from_sfm(self):
        self.add_member(1, day='2010:03:06', payload_override=b'not an actual photograph')
        _, report = self.run_prepare()
        self.assertEqual(report['counts']['rejected_files'], 1)
        self.assertEqual(report['counts']['train_files'], 0)
        self.assertFalse(report['images'][0]['validation']['passed'])

    def test_incomplete_or_publicly_relicensed_recovery_not_admitted(self):
        row = self.add_member(1, day='2010:03:06')
        for replacement in ({'status': 'probe_budget_exhausted'}, {'public_redistribution_permitted': True},
                            {'rights_status': 'CC BY 4.0'}, {'original_bytes_preserved': False}):
            with self.subTest(replacement=replacement):
                changed = dict(row); changed.update(replacement)
                with self.assertRaises(ValueError): validate_recovered_member(changed, self.manifest, self.data)

    def test_snapshot_immutable_new_members_new_id_and_source_unchanged(self):
        row = self.add_member(1, day='2010:03:06'); original_hash = sha256(row['file'])
        first, report = self.run_prepare(); frozen = (first / 'snapshot.json').read_bytes()
        second, report2 = self.run_prepare()
        self.assertEqual(first, second)
        self.assertEqual(frozen, (second / 'snapshot.json').read_bytes())
        self.assertEqual(sha256(row['file']), original_hash)
        self.add_member(2, day='2010:03:07'); third, _ = self.run_prepare()
        self.assertNotEqual(first, third)
        self.assertEqual(frozen, (first / 'snapshot.json').read_bytes())

    def test_existing_working_derivative_never_silently_replaced(self):
        self.add_member(1, day='2010:03:06'); _, report = self.run_prepare()
        target = Path(report['images'][0]['working_path']); target.write_bytes(b'user-owned-changed-file')
        _, changed = self.run_prepare()
        self.assertEqual(changed['counts']['rejected_files'], 1)
        self.assertEqual(target.read_bytes(), b'user-owned-changed-file')

    def test_same_day_conservative_families_never_leak_to_test(self):
        for i in range(1, 7): self.add_member(i, day='2010:03:06' if i < 4 else f'2010:03:{i:02d}')
        _, report = self.run_prepare()
        first = [i for i in report['images'] if i['capture_evidence']['earliest'] == '2010-03-06']
        self.assertEqual(len({i['source_family_id'] for i in first}), 1)
        self.assertEqual(len({i['split'] for i in first}), 1)

    def test_references_never_enter_image_training_or_focal_calibration(self):
        self.add_member(1, day='2010:03:06')
        row = self.add_member(10, kind='reference_metadata', text='1_photo.jpg 42.45053 -76.4855665\n')
        _, report = self.run_prepare()
        self.assertEqual(len(report['images']), 1)
        self.assertEqual(len(report['reference_members_provenance']), 1)
        self.assertNotIn('fit_pose', report['images'][0])

    def test_malformed_or_conflicting_geotag_metadata_rejected(self):
        for text in ('a.jpg nonsense -76.4', 'a.jpg 95 -76.4', 'a.jpg 42 -76\na.jpg 43 -76'):
            path = self.data / 'bad.txt'; path.write_text(text)
            with self.subTest(text=text):
                with self.assertRaises(ValueError): parse_geotags([path])

    def test_role_notes_hash_bound_and_cannot_certify_buildings(self):
        row = self.add_member(1, day='2010:03:06')
        path = self.data / 'role-review.json'
        payload = {'method': 'agent inspection, not groundtruth', 'records': [
            {'sha256_original': row['complete_member']['sha256'], 'role': 'non-scene-object-review',
             'reason': 'object close-up', 'building_identity_validated': False}]}
        path.write_text(json.dumps(payload))
        _, report = self.run_prepare([path])
        self.assertEqual(report['counts']['excluded_files'], 1)
        payload['records'][0]['building_identity_validated'] = True; path.write_text(json.dumps(payload))
        with self.assertRaises(ValueError): self.run_prepare([path])

    def test_public_dist_workspace_rejected_before_any_write(self):
        from run_artsquad_sfm import ROOT
        with self.assertRaises(ValueError): prepare([], ROOT / 'dist/quad6k-private-test', self.data)

    def test_duplicate_manifest_records_do_not_duplicate_training_images(self):
        row = self.add_member(1, day='2010:03:06')
        self.manifest['recovered_research_members'].append(copy.deepcopy(row))
        _, report = self.run_prepare()
        self.assertEqual(report['counts']['source_records'], 1)


if __name__ == '__main__': unittest.main()
