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
from ghostmap.anchor.georegister import fit_arrays  # noqa: E402

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
        report, sim, _ = fit(model, 'McGraw Tower')
        s_old, R_old, t_old = old['similarity']['scale_m_per_model_unit'], np.array(old['similarity']['rotation']), np.array(old['similarity']['translation_utm18n'])
        self.assertLess(abs(sim[0] / s_old - 1), 0.03, report['certificate'])
        yaw_diff = np.degrees(np.arccos(np.clip((np.trace(sim[1] @ R_old.T) - 1) / 2, -1, 1)))
        self.assertLess(yaw_diff, 1.0)
        self.assertLess(np.linalg.norm(sim[2] - t_old), 2.0)
        self.assertEqual(report['certificate']['verdict'], 'usable', report['certificate'])


if __name__ == '__main__': unittest.main()
