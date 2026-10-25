import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pipeline'))
from run_artsquad import densify, require_disk


class EntryPointTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def report(self, cameras=3, status='sfm_complete'):
        (self.root / 'report.json').write_text(json.dumps({'status': status, 'components': [
            {'id': '0', 'registered_cameras': cameras, 'model_path': 'sfm/models/0'}]}))

    def test_disk_guard_does_not_delete_anything(self):
        marker = self.root / 'user-data'; marker.write_text('preserve')
        with patch('run_artsquad.shutil.disk_usage') as usage:
            usage.return_value.free = 2 * 2**30
            with self.assertRaises(RuntimeError): require_disk(self.root, 5)
        self.assertEqual(marker.read_text(), 'preserve')

    def test_dense_requires_completed_native_run(self):
        self.report(status='running')
        with patch('run_artsquad.call') as call:
            with self.assertRaises(ValueError): densify(self.root, ['0'], 1280, 0)
            call.assert_not_called()

    def test_three_view_requirement(self):
        self.report(cameras=2)
        with patch('run_artsquad.call') as call:
            with self.assertRaises(ValueError): densify(self.root, ['0'], 1280, 0)
            call.assert_not_called()

    def test_all_component_ids_preflight_before_execution(self):
        self.report()
        with patch('run_artsquad.call') as call:
            with self.assertRaises(ValueError): densify(self.root, ['0', '../unknown'], 1280, 0)
            call.assert_not_called()

    def test_dense_orders_geometry_texture_and_provenance_without_release(self):
        self.report()
        workspace = self.root / 'mvs/0'; workspace.mkdir(parents=True)
        (workspace / 'report.json').write_text('{"status":"surface_candidate"}')
        with patch('run_artsquad.call') as call, patch('run_artsquad.require_disk'), patch('run_artsquad.surface_fragments') as fragments:
            densify(self.root, ['0'], 1280, 0)
        fragments.assert_called_once_with(self.root, '0')
        stages = [c.args[0] for c in call.call_args_list]
        self.assertEqual(stages, ['run_cpu_mvs.py', 'texture_from_cameras.py', 'audit_artsquad_dense_support.py'])
        args = call.call_args_list[0].args
        self.assertIn('all', args)
        self.assertIn(self.root / 'sfm/models/0', args)
        self.assertNotIn('artsquad_status.py', stages)

    def test_zero_depth_never_meshed_or_textured(self):
        self.report()
        workspace = self.root / 'mvs/0'; workspace.mkdir(parents=True)
        (workspace / 'report.json').write_text('{"status":"insufficient_depth_support"}')
        with patch('run_artsquad.call') as call, patch('run_artsquad.require_disk'), patch('run_artsquad.surface_fragments') as fragments:
            densify(self.root, ['0'], 1280, 0)
        self.assertEqual([c.args[0] for c in call.call_args_list], ['run_cpu_mvs.py'])
        fragments.assert_not_called()


if __name__ == '__main__': unittest.main()
