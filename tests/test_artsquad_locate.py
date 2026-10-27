"""Placing a new photograph (anchor/locate.py): the certificate's verdicts, the segment a long lens leaves open,
and what the page receives (web/timemachine_scene.py, located_entry). The GPU pipeline itself is exercised by
`python -m ghostmap.anchor.locate --leave-one-out 88`, not here."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pipeline'))
from ghostmap.anchor.locate import MIN_INLIERS, certify, segment_distance  # noqa: E402
from ghostmap.web.timemachine_scene import located_entry  # noqa: E402


class FakeRef:
    """Flat lidar ground at z = 0, no buildings, the local frame at the UTM origin."""
    origin = np.zeros(3)
    def height_over_ground(self, c): return float(c[2])
    def inside_building(self, c): return False


class FakePose:
    def __init__(self, centre):
        self.rotation = type('R', (), {'matrix': staticmethod(lambda: np.eye(3))})()
        self.translation = -np.asarray(centre, float)


def result(centre, inliers, focal=1000.0, size=(1000, 800)):
    camera = type('Camera', (), {'params': [focal, size[0] / 2, size[1] / 2, 0.0]})()
    ret = {'cam_from_world': FakePose(centre), 'camera': camera, 'num_inliers': inliers, 'inlier_mask': [True] * inliers}
    log = {'points3D_ids': list(range(inliers + 10)), 'db': list(range(10))}
    return ret, log, size


class LocateCertificateTest(unittest.TestCase):
    def test_a_well_determined_pose_at_eye_height_is_placed(self):
        ret, log, size = result([10, 20, 1.6], 300)
        verdict, pose = certify(FakeRef(), ret, log, size, {'valley_m': 2.0, 'segment': []})
        self.assertEqual(verdict['verdict'], 'placed', verdict)
        self.assertAlmostEqual(pose['height_over_lidar_ground_m'], 1.6)

    def test_too_few_inliers_is_refused_with_the_reason(self):
        ret, log, size = result([0, 0, 1.6], MIN_INLIERS - 5)
        verdict, _ = certify(FakeRef(), ret, log, size, {'valley_m': 0.0})
        self.assertEqual(verdict['verdict'], 'refused'); self.assertIn('correspondences', verdict['reasons'][0])

    def test_a_long_valley_places_the_direction_only(self):
        ret, log, size = result([0, 0, 12.0], 200)
        segment = [{'centre_local_m': [0, -40, 2.0], 'height_m': 2.0}, {'centre_local_m': [0, 40, 22.0], 'height_m': 22.0}]
        verdict, pose = certify(FakeRef(), ret, log, size, {'valley_m': 80.0, 'segment': segment})
        self.assertEqual(verdict['verdict'], 'placed, distance uncertain', verdict)
        self.assertEqual(pose['segment'], segment)

    def test_deep_under_the_ground_everywhere_is_refused(self):
        ret, log, size = result([0, 0, -30.0], 200)
        segment = [{'centre_local_m': [0, -40, -40.0], 'height_m': -40.0}, {'centre_local_m': [0, 40, -20.0], 'height_m': -20.0}]
        verdict, _ = certify(FakeRef(), ret, log, size, {'valley_m': 80.0, 'segment': segment})
        self.assertEqual(verdict['verdict'], 'refused', verdict)

    def test_segment_distance(self):
        seg = [{'centre_local_m': [0, 0, 0]}, {'centre_local_m': [10, 0, 0]}]
        self.assertAlmostEqual(segment_distance(np.array([5.0, 3.0, 0.0]), seg), 3.0)
        self.assertAlmostEqual(segment_distance(np.array([14.0, 3.0, 0.0]), seg), 5.0)

    def test_the_page_gets_the_pose_in_its_frame_and_the_focal_at_its_size(self):
        report = {'photo': '/x/query__p.jpg', 'certificate': {'verdict': 'placed', 'reasons': [], 'notes': []}, 'seconds': {'a': 1.0, 'b': 0.5},
                  'pose': {'centre_local_m': [1, 2, 3], 'cam_from_world_rotation': np.eye(3).tolist(), 'focal_px': 2000.0, 'height_over_lidar_ground_m': 1.6,
                           'heading_deg': 90.0, 'inliers': 100, 'valley_m': 3.0, 'segment': [{'centre_local_m': [1, 2, 3]}]}}
        e = located_entry(report, np.array([10.0, 20.0, 0.0]), 'located/p.jpg', (4000, 3000), (1600, 1200))
        self.assertEqual(e['centre'], [11.0, 22.0, 3.0]); self.assertAlmostEqual(e['focal_px'], 800.0); self.assertEqual(e['segment'], [[11.0, 22.0, 3.0]])
        self.assertEqual(e['seconds'], 1.5)


if __name__ == '__main__': unittest.main()
