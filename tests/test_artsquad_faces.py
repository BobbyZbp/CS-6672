import copy
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pipeline'))
from index_artsquad_faces import build_face_index, parse_faces


def row(name, exposure, family, split='train'):
    return {'filename': name, 'exposure_group_id': exposure, 'source_family_id': family,
            'role': 'scene-candidate', 'validation': {'passed': True}, 'split': split}


class FaceIndexTests(unittest.TestCase):
    def setUp(self):
        self.xyz = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, .123456789]])
        self.obj = '\n'.join(['mtllib family-supported.mtl', 'v 0 0 0', 'v 1 0 0', 'v 0 1 0',
                              'v 1 1 .12345679', 'usemtl camera_7', 'f 1/1 2/2 3/3',
                              'usemtl camera_12', 'f 2/4 4/5 3/6'])
        self.records = [row('a.jpg', 'exposure-a', 'family-a'), row('b.jpg', 'exposure-b', 'family-b'),
                        row('c.jpg', 'exposure-c', 'family-a')]
        self.visibility = [[0, 1], [0, 1, 2], [0, 1, 2], [1, 2]]
        self.names = ['/export/a.jpg', '/export/b.jpg', '/export/c.jpg']

    def build(self, **changes):
        args = {'obj_text': self.obj, 'dense_xyz': self.xyz, 'visibility': self.visibility,
                'records': self.records, 'camera_names': self.names,
                'material_sources': {'camera_7': 'a.jpg', 'camera_12': 'b.jpg'}}
        args.update(changes)
        return build_face_index(**args)

    def test_faces_preserve_actual_order_across_materials(self):
        result = self.build()
        a, b = result['faces']
        self.assertEqual(a['face_index'], 0); self.assertEqual(b['face_index'], 1)
        self.assertEqual(a['vertex_indices'], [0, 1, 2])
        self.assertEqual(b['vertex_indices'], [1, 3, 2])
        self.assertEqual(a['texture_material'], 'camera_7')
        self.assertEqual(b['texture_material'], 'camera_12')
        self.assertEqual(a['common_images'], ['a.jpg', 'b.jpg'])
        self.assertEqual(b['common_images'], ['b.jpg', 'c.jpg'])
        self.assertFalse(result['claims']['milestone_passed'])

    def test_real_group_ids_not_raw_camera_count(self):
        records = copy.deepcopy(self.records); records[1]['exposure_group_id'] = 'exposure-a'
        result = self.build(records=records)
        self.assertEqual(result['faces'][0]['common_recorded_exposure_groups'], ['exposure-a'])
        self.assertEqual(result['faces'][0]['common_recorded_source_families'], ['family-a', 'family-b'])
        self.assertEqual(result['faces'][0]['vertex_min_recorded_source_families'], 2)

    def test_original_dense_vertices_retained_with_text_rounding_only(self):
        result = self.build()
        self.assertEqual(result['vertex_count'], 4)
        self.assertTrue(result['dense_vertices_preserved_within_text_precision'])
        changed = self.xyz.copy(); changed[0, 0] = .01
        with self.assertRaises(ValueError): self.build(dense_xyz=changed)
        with self.assertRaises(ValueError): self.build(dense_xyz=self.xyz[[1, 0, 2, 3]])
        with self.assertRaises(ValueError): self.build(dense_xyz=self.xyz[:-1])

    def test_nonfinite_xyz_rejected(self):
        changed = self.xyz.copy(); changed[0, 0] = np.nan
        with self.assertRaises(ValueError): self.build(dense_xyz=changed)

    def test_multimesh_declarations_rejected(self):
        for text in ('o first\ng second\n' + self.obj, self.obj + '\no second\nf 1 2 3',
                     'g first\n' + self.obj + '\ng second'):
            with self.subTest(text=text):
                with self.assertRaises(ValueError): self.build(obj_text=text)
        self.assertEqual(self.build(obj_text='o single\n' + self.obj)['face_count'], 2)

    def test_polygons_lines_points_and_invalid_indices_rejected(self):
        for line in ('f 1 2 3 4', 'f 0 2 3', 'f -1 2 3', 'f 1 2 99', 'f 1 1 3', 'l 1 2', 'p 1'):
            with self.subTest(line=line):
                with self.assertRaises(ValueError): self.build(obj_text=self.obj.replace('f 1/1 2/2 3/3', line))

    def test_missing_texture_material_rejected(self):
        with self.assertRaises(ValueError): self.build(obj_text=self.obj.replace('usemtl camera_7', ''))
        with self.assertRaises(ValueError): self.build(material_sources={'camera_7': 'a.jpg'})

    def test_texture_view_must_share_all_vertex_visibility(self):
        with self.assertRaises(ValueError): self.build(material_sources={'camera_7': 'c.jpg', 'camera_12': 'b.jpg'})

    def test_intersection_is_not_union(self):
        visibility = [[0], [1], [2], [1, 2]]
        result = self.build(visibility=visibility, material_sources=None)
        self.assertEqual(result['faces'][0]['common_images'], [])
        self.assertEqual(result['faces'][0]['common_recorded_source_families'], [])

    def test_malformed_visibility_rejected(self):
        for visibility in (self.visibility[:-1], [[0], [1], [2], [99]], [[0], [1], [2], [.0]],
                           [[0], [1], [2], [True]], [[0], [1], [2], None]):
            with self.subTest(visibility=visibility):
                with self.assertRaises(ValueError): self.build(visibility=visibility)

    def test_foreign_and_heldout_cameras_rejected(self):
        with self.assertRaises(ValueError): self.build(camera_names=['a.jpg', 'b.jpg', 'foreign.jpg'])
        records = copy.deepcopy(self.records); records[1]['split'] = 'test'
        with self.assertRaises(ValueError): self.build(records=records)

    def test_global_exposure_and_family_leakage_rejected(self):
        for exposure, family in (('exposure-a', 'unused-family'), ('unused-exposure', 'family-a')):
            records = self.records + [row('test.jpg', exposure, family, split='test')]
            with self.assertRaises(ValueError): self.build(records=records)

    def test_pure_helper_preserves_inputs(self):
        before = copy.deepcopy((self.records, self.visibility)); xyz = self.xyz.copy()
        self.build()
        self.assertEqual((self.records, self.visibility), before)
        np.testing.assert_array_equal(self.xyz, xyz)


if __name__ == '__main__': unittest.main()
