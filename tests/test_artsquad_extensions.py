import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pipeline'))
from ghostmap.acquire.artsquad import assess
from ghostmap.anchor import align, lidar
from ghostmap.archival import resect


def look_at(C, target):
    z = np.asarray(target, float) - C; z /= np.linalg.norm(z)
    x = np.cross(z, [0, 0, 1.]); x /= np.linalg.norm(x); y = np.cross(z, x)
    R = np.vstack([x, y, z]); return R, -R @ C


class LidarTests(unittest.TestCase):
    def test_node_bounds_subdivide_the_root_cube(self):
        lo, hi = lidar.node_bounds('1-1-0-1', [0, 0, 0, 8, 8, 8])
        self.assertEqual(lo.tolist(), [4, 0, 4]); self.assertEqual(hi.tolist(), [8, 4, 8])

    def test_selection_keeps_every_depth_that_meets_the_box_and_follows_subtree_files(self):
        root = {'0-0-0-0': 10, '1-0-0-0': 5, '1-1-0-0': 5, '2-0-0-0': -1}
        subtree = {'2-0-0-0': 3, '3-0-0-0': 2}
        loader = lambda key: root if key == '0-0-0-0' else subtree
        nodes = lidar.select_nodes(loader, [0, 0, 0, 8, 8, 8], (0.5, 0.5, 1.5, 1.5))
        self.assertEqual(nodes, ['0-0-0-0', '1-0-0-0', '2-0-0-0', '3-0-0-0'])

    def test_rasterize_keeps_highest_and_lowest_and_fills_gaps(self):
        e, n, z = np.array([0.2, 0.3, 1.2]), np.array([1.8, 1.7, 1.8]), np.array([5., 9., 2.])
        top = lidar.rasterize(e, n, z, (0, 0, 2, 2), 1.0, 'max')
        low = lidar.rasterize(e, n, z, (0, 0, 2, 2), 1.0, 'min')
        self.assertEqual(top[0, 0], 9.); self.assertEqual(low[0, 0], 5.); self.assertTrue(np.isnan(top[1, 1]))
        self.assertFalse(np.isnan(lidar.fill_nearest(low)).any())


class AlignTests(unittest.TestCase):
    def test_rotation_to_z_maps_the_given_vertical_to_z(self):
        up = np.array([0.1, -0.8, 0.5]); up /= np.linalg.norm(up)
        np.testing.assert_allclose(align.rotation_to_z(up) @ up, [0, 0, 1], atol=1e-12)

    def test_facade_normals_recover_the_vertical_of_a_tilted_box(self):
        rng = np.random.default_rng(0)
        walls = [np.column_stack([rng.uniform(0, 20, 400), np.zeros(400), rng.uniform(0, 10, 400)]),
                 np.column_stack([np.zeros(400), rng.uniform(0, 15, 400), rng.uniform(0, 10, 400)])]
        points = np.vstack(walls) + rng.normal(0, 0.02, (800, 3))
        tilt = align.rotation_to_z(np.array([0.2, 0.1, 1.0]) / np.linalg.norm([0.2, 0.1, 1.0])).T  # world z -> tilted
        up, quality = align.facade_up(points @ tilt.T, tilt @ [0.05, 0, 1])
        self.assertLess(np.degrees(np.arccos(abs(up @ (tilt @ [0, 0, 1.])))), 1.0)

    def test_tallest_cluster_finds_the_tower_not_the_wall(self):
        rng = np.random.default_rng(1)
        wall = np.column_stack([rng.uniform(0, 30, 500), np.zeros(500), rng.uniform(0, 8, 500)])
        tower = np.column_stack([rng.uniform(40, 41, 200), rng.uniform(0, 1, 200), rng.uniform(0, 40, 200)])
        mask, centre, _ = align.tallest_cluster(np.vstack([wall, tower]))
        self.assertGreater(mask[500:].mean(), 0.8); self.assertEqual(mask[:500].sum(), 0)

    def test_wall_field_measures_distance_to_footprint_edges(self):
        field = align.WallField([[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]], (-5, -5, 15, 15))
        d = field(np.array([[5., 0.], [5., 3.], [5., 5.]]))
        self.assertLess(d[0], 0.3); self.assertAlmostEqual(d[1], 3.0, delta=0.3); self.assertAlmostEqual(d[2], 5.0, delta=0.3)


class ResectionTests(unittest.TestCase):
    W, H, F = 1600, 1000, 1800

    def observe(self, points, C, target, noise=1.0, seed=0):
        R, t = look_at(np.asarray(C, float), target)
        uv, _ = resect.project(points, R, t, self.F, self.W / 2, self.H / 2)
        return uv + np.random.default_rng(seed).normal(0, noise, uv.shape)

    def test_distant_planar_anchors_leave_a_long_ambiguity_that_the_ground_cuts(self):
        rng = np.random.default_rng(2)
        facade = np.column_stack([rng.uniform(-10, 10, 80), rng.uniform(-1, 1, 80), rng.uniform(0, 45, 80)])
        C = [0., -150., 1.6]
        rows = resect.profile(self.observe(facade, C, [0, 0, 18]), facade, self.W, self.H)
        cert = resect.certificate(rows, facade.mean(0), lambda xy: np.zeros(len(xy)))
        anchors, ground = cert['cues']['surviving anchors only'], cert['cues']['anchors + measured ground']
        self.assertGreater(anchors['distance_interval_m'], 50)
        self.assertLess(ground['distance_interval_m'], 0.5 * anchors['distance_interval_m'])

    def test_depth_diverse_anchors_determine_the_camera(self):
        rng = np.random.default_rng(3)
        near = np.column_stack([rng.uniform(-6, 6, 40), rng.uniform(-110, -90, 40), rng.uniform(0, 3, 40)])
        far = np.column_stack([rng.uniform(-10, 10, 80), rng.uniform(-1, 1, 80), rng.uniform(0, 45, 80)])
        points = np.vstack([far, near]); C = [0., -150., 1.6]
        rows = resect.profile(self.observe(points, C, [0, 0, 18]), points, self.W, self.H)
        cert = resect.certificate(rows, points.mean(0), lambda xy: np.zeros(len(xy)))
        self.assertLess(cert['cues']['surviving anchors only']['distance_interval_m'], 10)

    def test_a_person_of_known_height_implies_that_height_at_the_true_pose(self):
        C = np.array([0., -60., 1.6]); R, t = look_at(C, [0, 0, 1.0])
        foot, head = np.array([[2., -20., 0.]]), np.array([[2., -20., 1.7]])
        uv_f, _ = resect.project(foot, R, t, self.F, self.W / 2, self.H / 2)
        uv_h, _ = resect.project(head, R, t, self.F, self.W / 2, self.H / 2)
        row = {'focal_px': self.F, 'R': R, 't': t, 'centre': C}
        ll, implied = resect.people_log_likelihood(row, [(uv_f[0], uv_h[0])], self.W, self.H, lambda xy: np.zeros(len(xy)))
        self.assertAlmostEqual(implied[0], 1.7, delta=0.1)

    def test_line_of_sight_is_blocked_by_a_building_between(self):
        surface = lambda xy: np.where((xy[:, 1] > -60) & (xy[:, 1] < -40), 30.0, 0.0)
        anchors = np.array([[0., 0., 10.]])
        self.assertEqual(resect.visible_fraction([0, -150, 1.6], anchors, surface), 0.0)
        self.assertEqual(resect.visible_fraction([0, -30, 1.6], anchors, surface, start_margin=1.0), 1.0)


class GeosearchAdmissionTests(unittest.TestCase):
    config = {'minimum_short_side': 800, 'capture_year_min': 2000, 'targets': [{'name': 'Uris Library'}]}

    def page(self, title):
        meta = {'LicenseShortName': {'value': 'CC BY-SA 4.0'}, 'DateTimeOriginal': {'value': '2015-05-01'}}
        return {'title': title, 'imageinfo': [{'mime': 'image/jpeg', 'width': 3000, 'height': 2000, 'extmetadata': meta}],
                'discovery': {'sources': ['geosearch:south end'], 'targets': []}}

    def test_located_scene_photo_is_admitted_and_inscription_is_not(self):
        self.assertTrue(assess(self.page('File:Cornell Day Hall 1.jpg'), self.config)[0])
        self.assertFalse(assess(self.page('File:Close-up of the inscription (OpenBenches 7129).jpg'), self.config)[0])


if __name__ == '__main__': unittest.main()


class CarvingTests(unittest.TestCase):
    def test_sky_rays_cap_columns_without_ever_cutting_into_the_true_building(self):
        from ghostmap.archival import carve
        W, H, F = 240, 150, 220
        box = (np.array([-5., -5., 0.]), np.array([5., 5., 12.]))

        def render_sky(R, t):
            C = -R.T @ t; sky = np.zeros((H, W), bool)
            for v in range(H):
                for u in range(W):
                    d = R.T @ np.array([(u - W / 2) / F, (v - H / 2) / F, 1.]); d /= np.linalg.norm(d)
                    if d[2] <= 0: continue  # looking down hits the ground
                    with np.errstate(divide='ignore', invalid='ignore'):
                        t0, t1 = (box[0] - C) / d, (box[1] - C) / d
                    tn, tf = np.nanmax(np.minimum(t0, t1)), np.nanmin(np.maximum(t0, t1))
                    sky[v, u] = not (tf >= max(tn, 0))
            return sky
        poses = []
        for C in (np.array([0., -60., 1.6]), np.array([-60., 0., 1.6])):
            R, t = look_at(C, [0, 0, 8.])
            poses.append((R, t, F, 0.5, render_sky(R, t)))
        xs = np.arange(-14, 15, 2.0); grid = np.array([(x, y) for x in xs for y in xs])
        truth = np.where((np.abs(grid[:, 0]) < 5) & (np.abs(grid[:, 1]) < 5), 12.0, 0.0)
        heights = np.arange(0.5, 40, 0.5)
        caps = []
        for R, t, f, w, sky in poses:
            cap, _ = carve.column_caps(grid, np.zeros(len(grid)), [(R, t, f, 1.0)], sky, heights, W, H)
            caps.append(cap)
        cap = np.minimum(*caps)
        self.assertEqual(carve.containment(cap, truth), 1.0)
        self.assertTrue(np.isfinite(cap[truth > 0]).any())
