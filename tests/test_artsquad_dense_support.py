import copy
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pipeline'))
from audit_artsquad_dense_support import summarize_visibility


def record(name, exposure=None, family=None, split='train', day='2020-01-01'):
    return {'filename': name, 'exposure_group_id': exposure or 'exposure-' + name,
            'source_family_id': family or 'family-' + name, 'split': split,
            'role': 'scene-candidate', 'validation': {'passed': True},
            'capture_evidence': {'earliest': day, 'latest': day, 'precision': 'day'}}


class DenseSupportTests(unittest.TestCase):
    def test_camera_exposure_and_family_counts_are_distinct(self):
        records = [record('a.jpg', 'same-exposure', 'same-family'),
                   record('b.jpg', 'same-exposure', 'same-family'),
                   record('c.jpg', 'another-exposure', 'same-family')]
        result = summarize_visibility(records, ['a.jpg', 'b.jpg', 'c.jpg'], [[0, 1, 2]])
        self.assertEqual(result['histograms']['raw_camera_count'], {'3': 1})
        self.assertEqual(result['histograms']['exact_original_exposure_group_count'], {'2': 1})
        self.assertEqual(result['histograms']['metadata_source_family_count'], {'1': 1})
        self.assertIsNone(result['source_grouping']['independent_capture_count'])
        self.assertFalse(result['claims']['independent_captures_certified'])
        self.assertFalse(result['claims']['milestone_passed'])

    def test_noncontiguous_camera_ids_are_not_used_as_visibility_indices(self):
        records = [record('a.jpg'), record('b.jpg')]
        # Names are passed in compact order; original COLMAP IDs do not enter.
        result = summarize_visibility(records, ['/export/a.jpg', '/export/b.jpg'], [[1]])
        self.assertEqual(result['camera_names'], ['a.jpg', 'b.jpg'])
        self.assertEqual(result['histograms']['raw_camera_count'], {'1': 1})
        with self.assertRaises(ValueError): summarize_visibility(records, ['a.jpg', 'b.jpg'], [[7]])

    def test_numpy_integer_visibility_supported(self):
        result = summarize_visibility([record('a.jpg')], ['a.jpg'], [np.array([0], dtype=np.uint32)])
        self.assertEqual(result['point_count'], 1)

    def test_malformed_indices_are_rejected(self):
        for visibility in ([[1]], [[-1]], [[.0]], [[True]], [[None]], ['0'], [None], None):
            with self.subTest(visibility=visibility):
                with self.assertRaises(ValueError): summarize_visibility([record('a.jpg')], ['a.jpg'], visibility)

    def test_duplicate_camera_entries_never_inflate_support(self):
        result = summarize_visibility([record('a.jpg')], ['a.jpg'], [[0, 0, 0]])
        self.assertEqual(result['histograms']['raw_camera_count'], {'1': 1})
        self.assertEqual(result['duplicate_visibility_entries_ignored'], 2)

    def test_foreign_camera_rejected(self):
        with self.assertRaises(ValueError): summarize_visibility([record('a.jpg')], ['foreign.jpg'], [[0]])

    def test_held_out_camera_rejected(self):
        with self.assertRaises(ValueError): summarize_visibility([record('a.jpg', split='test')], ['a.jpg'], [[0]])

    def test_excluded_or_not_literally_admitted_camera_rejected(self):
        for replacement in ({'role': 'interior'}, {'validation': {'passed': 1}}, {'validation': {}}, {'validation': None}, {'split': 'excluded'}):
            value = record('a.jpg'); value.update(replacement)
            with self.subTest(replacement=replacement):
                with self.assertRaises(ValueError): summarize_visibility([value], ['a.jpg'], [[0]])

    def test_global_leakage_rejected_even_for_unused_camera(self):
        for field in ('exposure_group_id', 'source_family_id'):
            records = [record('a.jpg'), record('b.jpg'), record('test.jpg', split='test')]
            records[-1][field] = records[1][field]
            with self.subTest(field=field):
                with self.assertRaises(ValueError): summarize_visibility(records, ['a.jpg'], [[0]])

    def test_missing_global_group_identity_rejected(self):
        records = [record('a.jpg'), record('test.jpg', split='test')]
        records[-1]['source_family_id'] = ''
        with self.assertRaises(ValueError): summarize_visibility(records, ['a.jpg'], [[0]])

    def test_normalized_basename_collision_rejected(self):
        with self.assertRaises(ValueError):
            summarize_visibility([record('a.jpg'), record('nested/a.jpg')], ['a.jpg'], [[0]])
        with self.assertRaises(ValueError):
            summarize_visibility([record('a.jpg')], ['a.jpg', 'C:\\export\\a.jpg'], [[0]])

    def test_temporal_ranges_unknowns_and_mixed_years_reported(self):
        records = [record('a.jpg', day='2005-01-01'), record('b.jpg', day='2020-01-01'), record('c.jpg')]
        records[2]['capture_evidence'] = None
        result = summarize_visibility(records, ['a.jpg', 'b.jpg', 'c.jpg'], [[0, 1], [0, 2], [2], []])
        self.assertEqual(result['temporal_ranges']['earliest_asserted_capture'], '2005-01-01')
        self.assertEqual(result['temporal_ranges']['latest_asserted_capture'], '2020-01-01')
        self.assertEqual(result['temporal_ranges']['unknown_camera_ranges'], 1)
        self.assertEqual(result['histograms']['unknown_capture_camera_count'], {'0': 2, '1': 2})
        self.assertEqual(result['histograms']['capture_span_days_bucket'], {'0': 1, '1827+': 1, 'unknown': 2})
        self.assertEqual(result['point_counts']['points_with_unknown_or_incomplete_capture_range'], 3)

    def test_bad_or_reversed_date_range_is_unknown_not_invented(self):
        for evidence in ({'earliest': 'unknown', 'latest': '2020-01-01'},
                         {'earliest': '2021-01-01', 'latest': '2020-01-01'}, {}):
            value = record('a.jpg'); value['capture_evidence'] = evidence
            result = summarize_visibility([value], ['a.jpg'], [[0]])
            self.assertEqual(result['temporal_ranges']['unknown_camera_ranges'], 1)
            self.assertIsNone(result['temporal_ranges']['earliest_asserted_capture'])

    def test_empty_cloud_is_valid_diagnostic_not_successful_geometry(self):
        result = summarize_visibility([record('a.jpg')], ['a.jpg'], [])
        self.assertEqual(result['point_count'], 0)
        self.assertEqual(result['status'], 'diagnostic')
        self.assertFalse(result['claims']['geometry_accuracy_validated'])

    def test_helper_is_pure(self):
        records = [record('a.jpg')]; visibility = [[0], []]
        before = copy.deepcopy((records, visibility))
        summarize_visibility(records, ['a.jpg'], visibility)
        self.assertEqual((records, visibility), before)


if __name__ == '__main__': unittest.main()
