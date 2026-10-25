import copy
import math
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pipeline'))
from analyze_artsquad_bridges import PAIR_BASE, angle_degrees, camera_warnings, database_edges, percentiles, summarize_component


def camera(identifier, center, labels=('morrill',), family=None, exposure=None):
    return {'id': identifier, 'name': str(identifier) + '.jpg', 'center': center,
            'width': 1000, 'height': 800, 'focal_px': 1000.,
            'simple_radial_k': .01, 'exif': {},
            'metadata_targets': list(labels), 'source_family_id': family or 'family-' + str(identifier),
            'exposure_group_id': exposure or 'exposure-' + str(identifier),
            'camera_model': 'SIMPLE_RADIAL', 'camera_parameters': [1000., 500., 400., .01]}


def point(identifier=1, ids=(1, 2), xyz=(0, 0, 10)):
    return {'id': identifier, 'image_ids': ids, 'xyz': xyz}


class BridgeDiagnosticsTests(unittest.TestCase):
    def test_known_triangulation_angle(self):
        angle = angle_degrees((-1, 0, 0), (1, 0, 0), (0, 0, 10))
        self.assertAlmostEqual(angle, math.degrees(2 * math.atan(.1)))

    def test_unknown_frame_scale_never_enters_normalized_baseline(self):
        cameras = [camera(1, (-1, 0, 0)), camera(2, (1, 0, 0))]
        first = summarize_component(cameras, [point()])['shared_track_pairs'][0]
        scaled = copy.deepcopy(cameras)
        for c in scaled: c['center'] = np.asarray(c['center']) * 17
        second = summarize_component(scaled, [point(xyz=(0, 0, 170))])['shared_track_pairs'][0]
        self.assertAlmostEqual(first['baseline_to_mean_point_distance_percentiles']['50'],
                               second['baseline_to_mean_point_distance_percentiles']['50'])
        self.assertAlmostEqual(first['triangulation_angle_degrees_percentiles']['50'],
                               second['triangulation_angle_degrees_percentiles']['50'])

    def test_low_parallax_is_warning_not_pure_rotation_diagnosis(self):
        c = [camera(1, (0, 0, 0)), camera(2, (.001, 0, 0))]
        result = summarize_component(c, [point()])['shared_track_pairs'][0]
        self.assertIn('low-triangulation-angle', result['warnings'])
        self.assertIn('very-low-parallax-not-proof-of-pure-rotation', result['warnings'])

    def test_one_multilabel_photo_cannot_prove_two_buildings(self):
        c = [camera(1, (-1, 0, 0), ('morrill', 'white')), camera(2, (1, 0, 0), ('morrill',))]
        result = summarize_component(c, [point()])
        self.assertEqual(result['label_disjoint_native_pair_count'], 0)

    def test_disjoint_labels_are_only_candidates_not_acceptance(self):
        c = [camera(1, (-1, 0, 0), ('morrill',)), camera(2, (1, 0, 0), ('white',))]
        result = summarize_component(c, [point()])
        self.assertEqual(result['label_disjoint_native_pair_count'], 1)
        self.assertNotIn('milestone_passed', result)

    def test_tower_cannot_count_as_core_label(self):
        c = [camera(1, (-1, 0, 0), ('mcgraw-tower', 'uris')), camera(2, (1, 0, 0), ('white',))]
        result = summarize_component(c, [point()])
        self.assertEqual(result['label_disjoint_native_pair_count'], 0)

    def test_same_hash_and_source_family_warnings_remain_distinct(self):
        c = [camera(1, (-1, 0, 0), family='same', exposure='same'),
             camera(2, (1, 0, 0), family='same', exposure='same')]
        pair = summarize_component(c, [point()])['shared_track_pairs'][0]
        self.assertIn('same-exact-original-group', pair['warnings'])
        self.assertIn('same-recorded-source-family', pair['warnings'])
        self.assertFalse(pair['different_exact_original_groups'])

    def test_duplicate_track_observation_does_not_inflate_support(self):
        c = [camera(1, (-1, 0, 0)), camera(2, (1, 0, 0))]
        result = summarize_component(c, [point(ids=(1, 1, 2, 2))])
        self.assertEqual(result['duplicate_track_observations_ignored'], 2)
        self.assertEqual(result['shared_track_pairs'][0]['shared_native_track_count'], 1)

    def test_duplicate_point_or_camera_rejected(self):
        c = [camera(1, (-1, 0, 0)), camera(2, (1, 0, 0))]
        with self.assertRaises(ValueError): summarize_component(c, [point(), point()])
        with self.assertRaises(ValueError): summarize_component([c[0], c[0]], [])
        c[1]['name'] = c[0]['name']
        with self.assertRaises(ValueError): summarize_component(c, [])

    def test_unregistered_foreign_track_camera_rejected(self):
        with self.assertRaises(ValueError): summarize_component([camera(1, (0, 0, 0))], [point()])

    def test_nonintegral_or_boolean_native_ids_rejected(self):
        c = [camera(1, (-1, 0, 0)), camera(2, (1, 0, 0))]
        for identifier in (True, 1.5, '1'):
            with self.subTest(identifier=identifier):
                with self.assertRaises(ValueError): summarize_component(c, [point(ids=(identifier, 2))])

    def test_invalid_geometry_rejected_not_silently_dropped(self):
        for c, p in [((0, 0, 10), (0, 0, 10)), ((float('nan'), 0, 0), (0, 0, 10)),
                     ((0, 0, 0), (0, float('inf'), 10))]:
            with self.subTest(c=c, p=p):
                with self.assertRaises(ValueError): angle_degrees(c, (1, 0, 0), p)

    def test_empty_component_is_negative_diagnostic(self):
        result = summarize_component([], [])
        self.assertEqual(result['registered_cameras'], 0)
        self.assertEqual(result['label_disjoint_native_pair_count'], 0)

    def test_camera_extreme_focal_and_distortion_are_separate_flags(self):
        c = camera(1, (0, 0, 0)); c.update(focal_px=140., simple_radial_k=1.4)
        flags = camera_warnings(c)['warnings']
        self.assertIn('extreme-focal-ratio', flags)
        self.assertIn('large-fitted-radial-distortion', flags)

    def test_large_negative_radial_also_flagged(self):
        c = camera(1, (0, 0, 0)); c['simple_radial_k'] = -14.8
        self.assertIn('large-fitted-radial-distortion', camera_warnings(c)['warnings'])

    def test_exif35_prior_is_weak_and_not_raw_sensor_focal(self):
        c = camera(1, (0, 0, 0)); c['exif'] = {'focal_length_mm': '4', 'focal_length_35mm': '28/1'}
        result = camera_warnings(c)
        self.assertAlmostEqual(result['weak_exif35_focal_px'], 28 * math.hypot(1000, 800) / math.hypot(36, 24))
        self.assertNotIn('focal-disagrees-with-weak-exif35-prior', result['warnings'])
        c['exif'] = {'focal_length_mm': '4'}
        self.assertIsNone(camera_warnings(c)['weak_exif35_focal_px'])

    def test_invalid_exif_does_not_produce_fake_prior(self):
        for value in ('None', '0', '1/0', '-12', None):
            c = camera(1, (0, 0, 0)); c['exif'] = {'focal_length_35mm': value}
            with self.subTest(value=value): self.assertIsNone(camera_warnings(c)['weak_exif35_focal_px'])

    def test_finite_threshold_distributions(self):
        self.assertEqual(percentiles([]), {})
        with self.assertRaises(ValueError): percentiles([float('nan')])

    def test_failed_grid_unprojection_is_not_hidden(self):
        c = camera(1, (0, 0, 0)); c['roundtrip'] = {'samples': 25, 'valid_samples': 20, 'maximum_error_px': .1}
        result = summarize_component([c], [])
        self.assertIn('camera-image-grid-unprojection-failed', result['camera_calibration'][0]['warnings'])
        self.assertEqual(result['camera_calibration'][0]['image_grid_roundtrip']['valid_samples'], 20)

    def test_helpers_do_not_mutate_source_records(self):
        c, p = [camera(1, (-1, 0, 0)), camera(2, (1, 0, 0))], [point()]
        before = copy.deepcopy((c, p)); summarize_component(c, p)
        self.assertEqual(before, (c, p))

    def test_database_epipolar_edge_is_not_a_shared_native_track(self):
        records = [{'filename': 'a.jpg', 'source_family_id': 'fa', 'exposure_group_id': 'ea',
                    'discovery': {'targets': ['morrill']}},
                   {'filename': 'b.jpg', 'source_family_id': 'fb', 'exposure_group_id': 'eb',
                    'discovery': {'targets': ['white']}}]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'database.db'
            with sqlite3.connect(path) as connection:
                connection.executescript('CREATE TABLE images(image_id INTEGER,name TEXT);'
                                         'CREATE TABLE two_view_geometries(pair_id INTEGER,rows INTEGER,config INTEGER);')
                connection.executemany('INSERT INTO images VALUES(?,?)', [(1, 'a.jpg'), (2, 'b.jpg')])
                connection.execute('INSERT INTO two_view_geometries VALUES(?,?,?)', (PAIR_BASE + 2, 145, 3))
            first = database_edges(path, records, {'a.jpg': ['0'], 'b.jpg': ['1']})[0]
            self.assertEqual(first['shared_native_components'], [])
            self.assertTrue(first['disjoint_nonempty_metadata_core_labels'])
            self.assertEqual(first['inliers'], 145)
            records[-1]['filename'] = 'foreign.jpg'
            with self.assertRaises(ValueError): database_edges(path, records, {})


if __name__ == '__main__': unittest.main()
