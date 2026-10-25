"""Footprint anchoring on a synthetic hall with a known similarity: two facades, clutter, a neighbour,
photographers at eye height on a sloping lawn. The fit must recover the scale, yaw and positions."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pipeline'))
from ghostmap.anchor.align import apply, rot_z  # noqa: E402
from ghostmap.anchor.footprint import fit_arrays  # noqa: E402


def rot_x(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c.item() if hasattr(c, 'item') else c]], float)


def synthetic(seed=0):
    rng = np.random.default_rng(seed)
    box, cell = (1000., 2000., 1300., 2300.), 0.5
    rows = cols = 600
    e = box[0] + (np.arange(cols) + .5) * cell; n = box[3] - (np.arange(rows) + .5) * cell
    E, N = np.meshgrid(e, n)
    def g(x): return 100 + 0.01 * (x - box[0])  # a gentle slope
    ground = g(E)
    ring = np.array([[1100, 2100], [1160, 2100], [1160, 2130], [1100, 2130], [1100, 2100]], float)
    # The annex stands where photographers of a 180-degree-flipped placement would have to stand.
    annex = np.array([[1095, 2150], [1165, 2150], [1165, 2178], [1095, 2178], [1095, 2150]], float)
    surface = ground + np.where((E >= 1100) & (E <= 1160) & (N >= 2100) & (N <= 2130), 15.0, 0.0)
    surface += np.where((E >= 1095) & (E <= 1165) & (N >= 2150) & (N <= 2178), 10.0, 0.0)
    buildings = [{'name': 'Hall', 'ring': ring.tolist()}, {'name': 'Annex', 'ring': annex.tolist()}]
    rasters = {'box': np.array(box), 'cell': np.array(cell), 'surface': surface, 'ground': ground}
    # Points on the south and east facades from the foot to the roof edge, plus clutter on the lawn.
    south = np.column_stack([rng.uniform(1100, 1160, 1600), 2100 + rng.normal(0, .15, 1600), np.zeros(1600)])
    east = np.column_stack([1160 + rng.normal(0, .15, 900), rng.uniform(2100, 2130, 900), np.zeros(900)])
    clutter = np.column_stack([rng.uniform(1120, 1200, 200), rng.uniform(2060, 2098, 200), np.zeros(200)])
    for arr, top in ((south, 14.5), (east, 14.5), (clutter, 6.0)): arr[:, 2] = g(arr[:, 0]) + rng.uniform(0.5, top, len(arr))
    world = np.vstack([south, east, clutter])
    cams = np.column_stack([rng.uniform(1110, 1200, 14), rng.uniform(2050, 2090, 14), np.zeros(14)]); cams[:, 2] = g(cams[:, 0]) + 1.6
    rotations_world = []
    for c in cams:
        f = np.array([1130, 2115, c[2] + 5]) - c; f /= np.linalg.norm(f)
        r = np.cross(f, [0, 0, 1.]); r /= np.linalg.norm(r)
        rotations_world.append(np.vstack([r, np.cross(f, r), f]))  # cam_from_world rows: right, down, forward
    # Model units through a known similarity: world = s * R @ model + t.
    s, R, t = 23.0, rot_z(np.radians(37.)) @ rot_x(np.radians(2.5)), np.array([1130., 2110., 90.])
    to_model = lambda x: ((np.asarray(x) - t) / s) @ R  # R.T applied on the right
    rotations_model = [Rcw @ R for Rcw in rotations_world]
    return dict(points=to_model(world), centres=to_model(cams), rotations=rotations_model, buildings=buildings, rasters=rasters,
                truth=dict(scale=s, R=R, t=t, cams=cams, world=world))


class FootprintAnchorTest(unittest.TestCase):
    def test_recovers_scale_yaw_and_positions(self):
        d = synthetic()
        result, sim = fit_arrays(d['points'], d['centres'], d['rotations'], 'Hall', d['buildings'], d['rasters'], yaw_step_deg=6.0, scale_steps=11)
        scale = result['similarity']['scale_m_per_model_unit']
        self.assertLess(abs(scale / d['truth']['scale'] - 1), 0.03, result['scale_checks'])
        cams = apply(sim, d['centres'])
        self.assertLess(np.linalg.norm(cams - d["truth"]["cams"], axis=1).max(), 2.0)
        pts = apply(sim, d['points'])
        self.assertLess(np.median(np.linalg.norm(pts - d['truth']['world'], axis=1)), 0.7)
        self.assertTrue(result['metric_frame_usable'], result['gate'])
        self.assertTrue(result['gate']['yaw_unique'])


if __name__ == '__main__': unittest.main()
