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
from ghostmap.anchor.align import apply, rot_z  # noqa: E402
from ghostmap.anchor.georegister import fit_arrays  # noqa: E402
from test_artsquad_footprint_anchor import rot_x  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def hall(seed=0, facades=('south', 'east'), lawn_only=False):
    """A 60 x 30 m hall on a sloping lawn, an annex where flipped photographers would stand, points on the
    chosen facades (or only on the lawn), fourteen photographers at eye height looking at the hall."""
    rng = np.random.default_rng(seed)
    box, cell = (1000., 2000., 1300., 2300.), 0.5
    e = box[0] + (np.arange(600) + .5) * cell; n = box[3] - (np.arange(600) + .5) * cell
    E, N = np.meshgrid(e, n)
    def g(x): return 100 + 0.01 * (x - box[0])
    ground = g(E)
    ring = np.array([[1100, 2100], [1160, 2100], [1160, 2130], [1100, 2130], [1100, 2100]], float)
    annex = np.array([[1095, 2150], [1165, 2150], [1165, 2178], [1095, 2178], [1095, 2150]], float)
    surface = ground + np.where((E >= 1100) & (E <= 1160) & (N >= 2100) & (N <= 2130), 15.0, 0.0)
    surface += np.where((E >= 1095) & (E <= 1165) & (N >= 2150) & (N <= 2178), 10.0, 0.0)
    buildings = [{'name': 'Hall', 'ring': ring.tolist()}, {'name': 'Annex', 'ring': annex.tolist()}]
    rasters = {'box': np.array(box), 'cell': np.array(cell), 'surface': surface, 'ground': ground}
    parts = []
    if not lawn_only:
        if 'south' in facades: parts.append(np.column_stack([rng.uniform(1100, 1160, 1600), 2100 + rng.normal(0, .15, 1600), rng.uniform(0.5, 14.8, 1600)]))
        if 'east' in facades: parts.append(np.column_stack([1160 + rng.normal(0, .15, 900), rng.uniform(2100, 2130, 900), rng.uniform(0.5, 14.8, 900)]))
    clutter = np.column_stack([rng.uniform(1120, 1200, 300 if not lawn_only else 2000), rng.uniform(2060, 2098, 300 if not lawn_only else 2000), rng.uniform(0, 3.0, 300 if not lawn_only else 2000)])
    parts.append(clutter)
    world = np.vstack(parts); world[:, 2] += g(world[:, 0])
    cams = np.column_stack([rng.uniform(1110, 1200, 14), rng.uniform(2050, 2090, 14), np.zeros(14)]); cams[:, 2] = g(cams[:, 0]) + 1.6
    rotations_world = []
    for c in cams:
        f = np.array([1130, 2115, c[2] + 5]) - c; f /= np.linalg.norm(f)
        r = np.cross(f, [0, 0, 1.]); r /= np.linalg.norm(r)
        rotations_world.append(np.vstack([r, np.cross(f, r), f]))
    # Each camera observes the points it can actually see: the segment to the point must not cross the hall's interior.
    from shapely.geometry import LineString, Polygon
    hall_poly = Polygon(ring).buffer(-0.3)
    obs = []
    for i, c in enumerate(cams):
        for j in rng.choice(len(world), len(world) // 3, replace=False):
            if not LineString([c[:2], world[j, :2]]).intersects(hall_poly): obs.append((i, j))
    obs = np.array(obs)
    s, R, t = 23.0, rot_z(np.radians(37.)) @ rot_x(np.radians(2.5)), np.array([1130., 2110., 90.])
    to_model = lambda x: ((np.asarray(x) - t) / s) @ R
    return dict(points=to_model(world), centres=to_model(cams), rotations=[Rcw @ R for Rcw in rotations_world], observations=obs,
                buildings=buildings, rasters=rasters, truth=dict(scale=s, R=R, t=t, cams=cams, world=world))


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
