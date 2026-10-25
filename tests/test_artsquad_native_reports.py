import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pipeline'))
from run_artsquad_sfm import saved_component_reports
from run_cpu_mvs import reports_zero_fused_points


class NativeReportsTests(unittest.TestCase):
    def test_saved_ids_not_returned_manager_order_determine_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for cid in ('5', '1'):
                (root / cid).mkdir(); (root / cid / 'images.bin').write_bytes(b'fixture marker, not a native model')
            def loader(path):
                name = Path(path).name + '.jpg'
                return types.SimpleNamespace(images={1: types.SimpleNamespace(name=name, has_pose=True)}, export_PLY=lambda path: None)
            with patch('run_artsquad_sfm.component_report', side_effect=lambda model, cid, records: {'id': cid, 'name': model.images[1].name}):
                reports = saved_component_reports(root, [{'filename': '1.jpg'}, {'filename': '5.jpg'}], loader)
            self.assertEqual(reports, [{'id': '1', 'name': '1.jpg'}, {'id': '5', 'name': '5.jpg'}])

    def test_foreign_camera_is_not_silently_relabelled(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / '0').mkdir(); (root / '0/images.bin').write_bytes(b'fixture')
            model = types.SimpleNamespace(images={1: types.SimpleNamespace(name='heldout.jpg', has_pose=True)})
            with self.assertRaisesRegex(ValueError, 'undeclared'):
                saved_component_reports(root, [{'filename': 'train.jpg'}], lambda path: model)

    def test_zero_fusion_log_is_not_sparse_interface_point_count(self):
        self.assertTrue(reports_zero_fused_points('Densifying point-cloud completed: 0 points (9s)'))
        self.assertFalse(reports_zero_fused_points('275 points, 0 vertices, 0 faces'))
        self.assertFalse(reports_zero_fused_points('Densifying point-cloud completed: 1200 points'))


if __name__ == '__main__': unittest.main()
