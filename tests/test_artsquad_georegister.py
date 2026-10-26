"""The unified estimator on synthetic halls with a known similarity: it must recover a two-facade hall,
report a single facade as 'scale undetermined', and report scattered lawn points as 'no facade seen'.
Real-fragment regressions (the tower, the portico, Gates Hall) run only with GHOSTMAP_SLOW_TESTS=1."""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pipeline'))
from ghostmap.anchor.align import apply  # noqa: E402
from ghostmap.anchor.georegister import fit_arrays, fit_levelled  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


from ghostmap.evaluate.synthetic import hall  # noqa: E402


class SyntheticHallTest(unittest.TestCase):
    def test_two_facades_recovered(self):
        d = hall()
        report, sim = fit_arrays(d['points'], d['centres'], d['rotations'], 'Hall', d['buildings'], d['rasters'], d['observations'], yaw_step_deg=6.0, scale_steps=11)
        self.assertLess(abs(sim[0] / d['truth']['scale'] - 1), 0.03, report['certificate'])
        self.assertLess(np.linalg.norm(apply(sim, d['centres']) - d['truth']['cams'], axis=1).max(), 2.0)
        self.assertEqual(report['certificate']['verdict'], 'usable', report['certificate'])
        self.assertTrue(report['certificate']['scale_fixed_by'], report['certificate'])

    def test_single_facade_reports_scale_undetermined(self):
        d = hall(facades=('south',))
        report, sim = fit_arrays(d['points'], d['centres'], d['rotations'], 'Hall', d['buildings'], d['rasters'], d['observations'], yaw_step_deg=6.0, scale_steps=11)
        self.assertEqual(report['certificate']['verdict'], 'not usable', report['certificate'])
        self.assertIn(report['certificate']['failure_mode'], ('scale undetermined', 'yaw ambiguous', 'position undetermined'), report['certificate'])

    def test_tilted_vertical_is_levelled_by_camera_heights(self):
        # A vertical 4 degrees off (as facade normals can leave it): the photographers' heights over the ground then
        # rise across the fragment, and the levelling must bring the vertical back within a degree.
        from scipy.spatial.transform import Rotation
        d = hall(cameras=20)
        true_up = d['truth']['R'].T @ [0, 0, 1.0]
        wrong_up = Rotation.from_rotvec(np.radians(4.0) * np.array([0.6, 0.8, 0.0])).apply(true_up)
        report, sim = fit_levelled(d['points'], d['centres'], d['rotations'], 'Hall', d['buildings'], d['rasters'], d['observations'], up=wrong_up, yaw_step_deg=6.0, scale_steps=11)
        fitted_up = np.asarray(sim[1]).T @ [0, 0, 1.0]
        self.assertLess(np.degrees(np.arccos(np.clip(fitted_up @ true_up, -1, 1))), 1.0, report['levelling'])
        self.assertGreater(report['levelling']['correction_deg'], 2.5, report['levelling'])
        self.assertTrue(report['levelling']['decision'].startswith('levelled'), report['levelling'])

    def test_lawn_points_report_no_facade(self):
        d = hall(lawn_only=True)
        report, sim = fit_arrays(d['points'], d['centres'], d['rotations'], 'Hall', d['buildings'], d['rasters'], d['observations'], yaw_step_deg=6.0, scale_steps=11)
        self.assertEqual(report['certificate']['failure_mode'], 'no facade seen', report['certificate'])


@unittest.skipUnless(os.environ.get('GHOSTMAP_SLOW_TESTS'), 'set GHOSTMAP_SLOW_TESTS=1 to run the real-fragment regressions')
class RealFragmentRegressionTest(unittest.TestCase):
    RUN = ROOT / 'artifacts/artsquad_modern/runs/6406b8eaae260163b303'

    def test_tower_fragment_matches_landmark_anchor(self):
        import pycolmap
        from ghostmap.anchor.georegister import fit
        old = json.loads((self.RUN / 'anchor/0/report.json').read_text())
        model = pycolmap.Reconstruction(str(self.RUN / 'sfm/models/0'))
        report, sim, _ = fit(model, 'Uris Library')  # the building most of its photographs carry; the tower is found as the landmark
        s_old, R_old, t_old = old['similarity']['scale_m_per_model_unit'], np.array(old['similarity']['rotation']), np.array(old['similarity']['translation_utm18n'])
        self.assertLess(abs(sim[0] / s_old - 1), 0.03, report['certificate'])
        # The landmark anchor keeps the facade vertical; the levelling may turn it by a few degrees, which it reports.
        # So heading and tilt are compared separately: the heading must agree, the tilt must be the reported correction.
        rel = sim[1] @ R_old.T
        tilt = np.degrees(np.arccos(np.clip(rel[2, 2], -1, 1)))
        x = rel @ [1.0, 0, 0]; heading = abs(np.degrees(np.arctan2(x[1], x[0])))
        self.assertLess(heading, 2.0, report['levelling'])
        self.assertLess(abs(tilt - report['levelling']['correction_deg']), 1.5, (tilt, report['levelling']))
        self.assertLess(np.linalg.norm(sim[2] - t_old), 6.0)
        self.assertEqual(report['certificate']['verdict'], 'usable', report['certificate'])


if __name__ == '__main__': unittest.main()
