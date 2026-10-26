#!/usr/bin/env python3
"""A synthetic hall with a known similarity, for identifiability studies and the estimator's fixtures.

A 60 x 30 m hall on a sloping lawn, an annex 20 m north (where the photographers of a 180-degree-flipped
placement would have to stand), points on the chosen facades from the foot to the roof edge (or only on
the lawn), fourteen photographers at eye height on the lawn looking at the hall, and each camera
observing the points it can actually see. Everything is then expressed in model units through a known
similarity (world = s R model + t), so a fit's scale, yaw and positions can be scored exactly. Knobs:
which facades carry points, lidar roof-edge error, camera-height noise, point noise, the number of points.
"""
from __future__ import annotations

import numpy as np

from ghostmap.anchor.align import rot_z

TRUE_SCALE, TRUE_YAW_DEG, TRUE_TILT_DEG = 23.0, 37.0, 2.5


def rot_x(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], float)


def hall(seed=0, facades=('south', 'east'), lawn_only=False, roof_edge_error_m=0.0, camera_height_noise_m=0.0,
         point_noise_m=0.15, facade_points=1600, cameras=14):
    rng = np.random.default_rng(seed)
    box, cell = (1000., 2000., 1300., 2300.), 0.5
    e = box[0] + (np.arange(600) + .5) * cell; n = box[3] - (np.arange(600) + .5) * cell
    E, N = np.meshgrid(e, n)
    def g(x): return 100 + 0.01 * (x - box[0])
    ground = g(E)
    ring = np.array([[1100, 2100], [1160, 2100], [1160, 2130], [1100, 2130], [1100, 2100]], float)
    annex = np.array([[1095, 2150], [1165, 2150], [1165, 2178], [1095, 2178], [1095, 2150]], float)
    # The lidar surface: a 15 m hall, a 10 m annex; the roof-edge error shifts what the lidar says about the hall's roof.
    surface = ground + np.where((E >= 1100) & (E <= 1160) & (N >= 2100) & (N <= 2130), 15.0 + roof_edge_error_m, 0.0)
    surface += np.where((E >= 1095) & (E <= 1165) & (N >= 2150) & (N <= 2178), 10.0, 0.0)
    buildings = [{'name': 'Hall', 'ring': ring.tolist()}, {'name': 'Annex', 'ring': annex.tolist()}]
    rasters = {'box': np.array(box), 'cell': np.array(cell), 'surface': surface, 'ground': ground}
    parts = []
    if not lawn_only:
        n_e = max(1, int(facade_points * 0.56))
        if 'south' in facades: parts.append(np.column_stack([rng.uniform(1100, 1160, facade_points), 2100 + rng.normal(0, point_noise_m, facade_points), rng.uniform(0.5, 14.8, facade_points)]))
        if 'east' in facades: parts.append(np.column_stack([1160 + rng.normal(0, point_noise_m, n_e), rng.uniform(2100, 2130, n_e), rng.uniform(0.5, 14.8, n_e)]))
        if 'north' in facades: parts.append(np.column_stack([rng.uniform(1100, 1160, facade_points), 2130 + rng.normal(0, point_noise_m, facade_points), rng.uniform(0.5, 14.8, facade_points)]))
        if 'west' in facades: parts.append(np.column_stack([1100 + rng.normal(0, point_noise_m, n_e), rng.uniform(2100, 2130, n_e), rng.uniform(0.5, 14.8, n_e)]))
    n_c = 300 if not lawn_only else 2000
    parts.append(np.column_stack([rng.uniform(1120, 1200, n_c), rng.uniform(2060, 2098, n_c), rng.uniform(0, 3.0, n_c)]))
    world = np.vstack(parts); world[:, 2] += g(world[:, 0])
    cams = np.column_stack([rng.uniform(1110, 1200, cameras), rng.uniform(2050, 2090, cameras), np.zeros(cameras)])
    cams[:, 2] = g(cams[:, 0]) + 1.6 + rng.normal(0, camera_height_noise_m, cameras)
    rotations_world = []
    for c in cams:
        f = np.array([1130, 2115, c[2] + 5]) - c; f /= np.linalg.norm(f)
        r = np.cross(f, [0, 0, 1.]); r /= np.linalg.norm(r)
        rotations_world.append(np.vstack([r, np.cross(f, r), f]))
    from shapely.geometry import LineString, Polygon
    hall_poly = Polygon(ring).buffer(-0.3)
    obs = []
    for i, c in enumerate(cams):
        for j in rng.choice(len(world), len(world) // 3, replace=False):
            if not LineString([c[:2], world[j, :2]]).intersects(hall_poly): obs.append((i, j))
    s, R, t = TRUE_SCALE, rot_z(np.radians(TRUE_YAW_DEG)) @ rot_x(np.radians(TRUE_TILT_DEG)), np.array([1130., 2110., 90.])
    to_model = lambda x: ((np.asarray(x) - t) / s) @ R
    return dict(points=to_model(world), centres=to_model(cams), rotations=[Rcw @ R for Rcw in rotations_world], observations=np.array(obs),
                buildings=buildings, rasters=rasters, truth=dict(scale=s, R=R, t=t, cams=cams, world=world))


def score(report, sim, truth):
    """Scale ratio, yaw error in degrees and the photographers' position error of a fit against the known similarity."""
    from ghostmap.anchor.align import apply
    s, R, t = sim
    yaw_err = float(np.degrees(np.arccos(np.clip((np.trace(R @ truth['R'].T) - 1) / 2, -1, 1))))
    cam_err = np.linalg.norm(apply(sim, ((truth['cams'] - truth['t']) / truth['scale']) @ truth['R']) - truth['cams'], axis=1)
    return {'scale_ratio': float(s / truth['scale']), 'yaw_error_deg': yaw_err, 'camera_error_m': {'median': float(np.median(cam_err)), 'max': float(cam_err.max())},
            'verdict': report['certificate']['verdict'], 'failure_mode': report['certificate']['failure_mode'], 'scale_band': report['certificate']['scale_band']}
