#!/usr/bin/env python3
"""Anchor a COLMAP fragment to airborne lidar and building footprints, in metres.

Protocol (no image geotags, no hand-picked correspondences):

1. Gravity from the facades: wall normals are horizontal, so the world vertical
   is the direction most orthogonal to wall-like patch normals of the points.
   (Camera up vectors are biased by photographers pitching up at the tower;
   they only seed the estimate. The tower's long axis agrees within 2 degrees.)
2. The landmark, McGraw Tower, is found in the model as the tallest compact
   vertical cluster; its axis is placed on the centre of its OSM footprint.
3. Vertical scale: each photographer stands at eye height on the lidar ground
   and sees the tower top, whose height lidar measures. Every camera therefore
   gives one scale estimate, (tower top - camera height in metres) /
   (tower top - camera height in model units); the median is the scale.
4. Yaw: one angle, chosen so that points lie on building footprint walls (the
   tolerance is in model units, so it does not reward shrinking) and no camera
   stands inside a building.

Independent checks (never used by the fit): a purely horizontal scale from the
library's footprint walls, which must agree with the vertical scale; the
library points' wall distances; leave-one-out photographer heights (each
camera's height predicted by a fit that excluded it). The native model is never modified; a transformed copy
is written next to the report.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from ghostmap.paths import ROOT

LIDAR = ROOT / 'data/lidar/NY_FingerLakes_1_2020'
FOOTPRINTS = ROOT / 'data/footprints/buildings-utm18n.json'
WALL_CELL = 0.25
TRUNCATE_M = 6.0
# Gate for calling the fragment metrically anchored (see the extension plan).
GATE = {'held_out_wall_median_m': 1.5, 'held_out_top_below_roof_m': 1.0, 'held_out_top_gap_m': 3.0,
        'camera_height_band_m': (0.5, 3.0), 'camera_fraction_in_band': 0.8, 'scale_relative_2sigma': 0.02}


# --- geometry helpers -----------------------------------------------------------

def rotation_to_z(up):
    """Rotation taking unit vector `up` to +z (Rodrigues)."""
    up = up / np.linalg.norm(up); z = np.array([0., 0., 1.])
    v = np.cross(up, z); c = float(up @ z)
    if np.linalg.norm(v) < 1e-12: return np.eye(3) if c > 0 else np.diag([1., -1., -1.])
    k = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + k + k @ k * ((1 - c) / (np.linalg.norm(v) ** 2))


def rot_z(theta):
    c, s = np.cos(theta), np.sin(theta)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.]])


def camera_up(rotations_cam_from_world):
    """World direction of each image's up axis (camera -y)."""
    return np.array([-(R.T @ np.array([0., 1., 0.])) for R in rotations_cam_from_world])


def facade_up(points, camera_up_hint, k=20, planarity=0.15, wall_band_deg=30., iterations=4):
    """Vertical as the direction most orthogonal to wall-like patch normals.

    Starting from the camera up hint, only normals within `wall_band_deg` of
    horizontal are kept (ground and roof patches would otherwise pull the
    estimate sideways); the estimate is iterated.
    """
    from scipy.spatial import cKDTree
    tree = cKDTree(points); _, nbrs = tree.query(points, k=min(k, len(points)))
    normals = []
    for idx in nbrs:
        q = points[idx] - points[idx].mean(0)
        w, v = np.linalg.eigh(q.T @ q)
        if w[0] < planarity * w[1]: normals.append(v[:, 0])
    normals = np.asarray(normals)
    up = camera_up_hint / np.linalg.norm(camera_up_hint)
    for _ in range(iterations):
        walls = normals[np.abs(normals @ up) < np.sin(np.radians(wall_band_deg))]
        w, v = np.linalg.eigh(walls.T @ walls)
        candidate = v[:, 0] if v[:, 0] @ up > 0 else -v[:, 0]
        up = candidate
    tilt = np.degrees(np.arcsin(np.clip(np.abs(walls @ up), 0, 1)))
    return up, {'planar_patches': int(len(normals)), 'wall_patches': int(len(walls)),
                'wall_normal_tilt_from_horizontal_deg_median': float(np.median(tilt))}


def tallest_cluster(points_g, quantile=0.9, margin=0.25):
    """Points of the tallest compact vertical structure, from the model alone.

    The highest decile of points defines a horizontal core; every point whose
    horizontal position lies within that core (dilated by `margin` of its
    size) belongs to the structure.
    """
    from scipy.spatial import cKDTree
    high = points_g[points_g[:, 2] >= np.quantile(points_g[:, 2], quantile)]
    centre = np.median(high[:, :2], 0)
    radius = np.percentile(np.linalg.norm(high[:, :2] - centre, axis=1), 80)
    dist = np.linalg.norm(points_g[:, :2] - centre, axis=1)
    return dist <= radius * (1 + margin), centre, float(radius)


def robust_mean_direction(vectors, iterations=5, cutoff_deg=20.):
    v = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
    mean = v.mean(0); mean /= np.linalg.norm(mean)
    for _ in range(iterations):
        keep = np.degrees(np.arccos(np.clip(v @ mean, -1, 1))) < cutoff_deg
        if keep.sum() < 3: break
        mean = v[keep].mean(0); mean /= np.linalg.norm(mean)
    spread = np.degrees(np.arccos(np.clip(v @ mean, -1, 1)))
    return mean, spread


class WallField:
    """Truncated distance (metres) to footprint wall lines on a raster."""

    def __init__(self, rings, box, cell=WALL_CELL):
        from scipy.ndimage import distance_transform_edt
        self.box, self.cell = box, cell
        cols = int(np.ceil((box[2] - box[0]) / cell)); rows = int(np.ceil((box[3] - box[1]) / cell))
        walls = np.zeros((rows, cols), bool)
        for ring in rings:
            ring = np.asarray(ring)
            for a, b in zip(ring[:-1], ring[1:]):
                n = max(2, int(np.ceil(np.linalg.norm(b - a) / (cell / 2))))
                for t in np.linspace(0, 1, n):
                    r, c = self.index(*(a + t * (b - a)))
                    if 0 <= r < rows and 0 <= c < cols: walls[r, c] = True
        self.distance = distance_transform_edt(~walls) * cell

    def index(self, e, n):
        return int((self.box[3] - n) / self.cell), int((e - self.box[0]) / self.cell)

    def __call__(self, en):
        rows, cols = self.distance.shape
        r = ((self.box[3] - en[:, 1]) / self.cell).astype(int); c = ((en[:, 0] - self.box[0]) / self.cell).astype(int)
        inside = (r >= 0) & (r < rows) & (c >= 0) & (c < cols)
        out = np.full(len(en), TRUNCATE_M)
        out[inside] = np.minimum(self.distance[r[inside], c[inside]], TRUNCATE_M)
        return out


def inside_any(en, rings):
    from shapely.geometry import Point, Polygon
    polys = [Polygon(r) for r in rings]
    return np.array([any(p.contains(Point(*x)) for p in polys) for x in en])


def raster_lookup(raster, box, cell, en):
    rows, cols = raster.shape
    r = np.clip(((box[3] - en[:, 1]) / cell).astype(int), 0, rows - 1)
    c = np.clip(((en[:, 0] - box[0]) / cell).astype(int), 0, cols - 1)
    return raster[r, c]


def apply(sim, x):
    s, R, t = sim
    return s * (np.asarray(x) @ R.T) + t


# --- fitting --------------------------------------------------------------------

class InsideMask:
    """Raster lookup: is a horizontal position inside any building footprint?"""

    def __init__(self, rings, box, cell=0.5):
        from matplotlib.path import Path as MPath
        self.box, self.cell = box, cell
        cols = int(np.ceil((box[2] - box[0]) / cell)); rows = int(np.ceil((box[3] - box[1]) / cell))
        e = box[0] + (np.arange(cols) + .5) * cell; n = box[3] - (np.arange(rows) + .5) * cell
        grid = np.column_stack([np.repeat(e[None], rows, 0).ravel(), np.repeat(n[:, None], cols, 1).ravel()])
        mask = np.zeros(rows * cols, bool)
        for ring in rings: mask |= MPath(np.asarray(ring)).contains_points(grid)
        self.mask = mask.reshape(rows, cols)

    def __call__(self, en):
        rows, cols = self.mask.shape
        r = ((self.box[3] - en[:, 1]) / self.cell).astype(int); c = ((en[:, 0] - self.box[0]) / self.cell).astype(int)
        ok = (r >= 0) & (r < rows) & (c >= 0) & (c < cols)
        out = np.zeros(len(en), bool); out[ok] = self.mask[r[ok], c[ok]]
        return out


def fit(model, landmark='McGraw Tower', neighbour='Uris Library', lidar=LIDAR, footprints=FOOTPRINTS,
        bootstrap=200, seed=0):
    from ghostmap.anchor.footprints import named
    from ghostmap.anchor.lidar import fill_nearest
    from shapely.geometry import Point, Polygon
    rasters = np.load(lidar / 'quad-rasters-utm18n.npz')
    box, cell, ground = tuple(rasters['box']), float(rasters['cell']), rasters['ground']
    surface = fill_nearest(rasters['surface'])  # QL2 leaves many empty 0.5 m cells
    buildings = json.loads(Path(footprints).read_text())['buildings']
    tower_ring = np.asarray(named(buildings, landmark)['ring']); tower_poly = Polygon(tower_ring)
    neighbour_ring = np.asarray(named(buildings, neighbour)['ring'])
    all_rings = [b['ring'] for b in buildings]

    images = sorted(model.images.values(), key=lambda im: im.name)
    rotations = [im.cam_from_world().rotation.matrix() for im in images]
    centres = np.array([im.projection_center() for im in images])
    points = np.array([p.xyz for p in model.points3D.values()])
    point_ids = np.array(list(model.points3D.keys()))

    hint, up_spread = robust_mean_direction(camera_up(rotations))
    up, gravity_quality = facade_up(points, hint)
    Rg = rotation_to_z(up)
    pg, cg = points @ Rg.T, centres @ Rg.T

    # Landmark measurements in the model.
    tower_mask, axis_xy, radius = tallest_cluster(pg)
    # Landmark measurements in lidar.
    e0, n0, e1, n1 = tower_poly.bounds
    gx, gy = np.meshgrid(np.arange(e0, e1, cell / 2), np.arange(n0, n1, cell / 2))
    grid = np.column_stack([gx.ravel(), gy.ravel()]); grid = grid[[tower_poly.contains(Point(*g)) for g in grid]]
    lidar_top = float(np.nanmax(raster_lookup(surface, box, cell, grid)))
    ring_pts = np.array([tower_poly.buffer(3.0).exterior.interpolate(d).coords[0] for d in np.arange(0, tower_poly.buffer(3.0).exterior.length, 0.5)])
    lidar_ground = float(np.nanmedian(raster_lookup(ground, box, cell, ring_pts)))
    tower_centre = np.asarray(tower_poly.centroid.coords[0])

    eye = 1.6
    every_wall, inside = WallField(all_rings, box), InsideMask(all_rings, box)
    others = ~tower_mask
    model_top = float(np.percentile(pg[tower_mask, 2], 99.5))
    cam_z = cg[:, 2]

    def similarity(theta, s):
        R = rot_z(theta) @ Rg
        xy = tower_centre - s * (rot_z(theta)[:2, :2] @ axis_xy)
        cams = s * cg @ rot_z(theta).T; cams[:, :2] += xy
        tz = float(np.median(raster_lookup(ground, box, cell, cams[:, :2]) + eye - cams[:, 2]))
        return s, R, np.array([xy[0], xy[1], tz])

    def camera_xy(theta, s):
        return tower_centre + s * (cg[:, :2] - axis_xy) @ rot_z(theta)[:2, :2].T

    def vertical_scales(theta, s):
        """One scale estimate per photographer standing at eye height."""
        g = raster_lookup(ground, box, cell, camera_xy(theta, s))
        return (lidar_top - (g + eye)) / (model_top - cam_z)

    def walls_explained(theta, s, pts, walls=every_wall, tol=0.025):
        d = walls(apply(similarity(theta, s), pts)[:, :2]); d[d >= TRUNCATE_M] = np.inf
        return float(np.mean(np.exp(-(d / (tol * s)) ** 2)))

    def yaw_score(theta, s):
        return walls_explained(theta, s, points[others]) - 0.5 * float(np.mean(inside(apply(similarity(theta, s), centres)[:, :2])))

    # Alternate: scale from photographers given yaw; yaw from walls given scale.
    usable = (model_top - cam_z) > 0
    scale = float(np.median((lidar_top - (lidar_ground + eye)) / (model_top - cam_z[usable])))
    yaws = np.radians(np.arange(0, 360, 1.0))
    for _ in range(4):
        profile = np.array([yaw_score(th, scale) for th in yaws])
        theta = float(yaws[int(np.argmax(profile))])
        from scipy.optimize import minimize_scalar
        theta = float(minimize_scalar(lambda th: -yaw_score(th, scale), bounds=(theta - .03, theta + .03), method='bounded').x)
        estimates = vertical_scales(theta, scale)[usable]
        scale = float(np.median(estimates))
    sim = similarity(theta, scale)
    # Leave-one-out photographer heights: the scale refit without each camera.
    loo = []
    for i in np.flatnonzero(usable):
        keep = usable.copy(); keep[i] = False
        s_i = float(np.median(vertical_scales(theta, scale)[keep]))
        cams = apply(similarity(theta, s_i), centres)
        loo.append(float(cams[i, 2] - raster_lookup(ground, box, cell, cams[i:i + 1, :2])[0]))
    loo = np.asarray(loo)
    deg = np.degrees(yaws); order = np.argsort(-profile)
    runner = next((i for i in order[1:] if abs(((deg[i] - np.degrees(theta)) + 180) % 360 - 180) > 10), order[1])
    yaw_uniqueness = {'best_walls_explained': float(profile.max()), 'runner_up_walls_explained': float(profile[runner]),
                      'runner_up_yaw_deg': float(deg[runner])}
    mad = float(np.median(np.abs(estimates - scale)))
    vertical = {'per_camera_scales': estimates.tolist(), 'median_m_per_unit': scale,
                'relative_sd_robust': float(1.4826 * mad / scale / np.sqrt(len(estimates)))}

    # Independent horizontal scale: library walls only (library points), yaw held.
    neighbour_field = WallField([neighbour_ring], box)
    log_grid = np.log(scale) + np.linspace(-.6, .6, 241)
    lib_profile = np.array([walls_explained(theta, np.exp(ls), points[others], neighbour_field) for ls in log_grid])
    horizontal_scale = float(np.exp(log_grid[int(np.argmax(lib_profile))]))
    scale_checks = {'vertical_from_photographers_and_tower_top': scale,
                    'horizontal_from_library_walls': horizontal_scale,
                    'library_vs_vertical_ratio': horizontal_scale / scale,
                    'leave_one_out_photographer_heights_m': {'median': float(np.median(loo)), 'p10': float(np.percentile(loo, 10)),
                                                            'p90': float(np.percentile(loo, 90)),
                                                            'within_band': int(((loo >= GATE['camera_height_band_m'][0]) & (loo <= GATE['camera_height_band_m'][1])).sum()),
                                                            'cameras': int(len(loo))}}

    world_pts, world_cams = apply(sim, points), apply(sim, centres)
    neighbour_walls = WallField([neighbour_ring], box)
    d_all = every_wall(world_pts[others][:, :2])
    d_neigh = neighbour_walls(world_pts[others][:, :2])
    on_neighbour = d_neigh <= 3.0
    tower_walls = WallField([tower_ring], box)
    d_tower = tower_walls(world_pts[tower_mask][:, :2])
    cam_height = world_cams[:, 2] - raster_lookup(ground, box, cell, world_cams[:, :2])
    lo, hi = GATE['camera_height_band_m']

    uncertainty = {'scale_relative_sd': vertical['relative_sd_robust'],
                   'meaning': 'robust standard error of the median per-photographer scale'}

    metrics = {
        'tower': {'top_m': float(np.percentile(world_pts[tower_mask][:, 2], 99.5)),
                  'lidar_top_m': lidar_top, 'lidar_ground_m': lidar_ground, 'lidar_height_m': lidar_top - lidar_ground,
                  'tower_points': int(tower_mask.sum()),
                           'points_to_own_walls_m': {'median': float(np.median(d_tower)), 'p90': float(np.percentile(d_tower, 90))}},
        'neighbour_wall_distance_m': {'points_within_3m': int(on_neighbour.sum()),
                                      'median': float(np.median(d_neigh[on_neighbour])) if on_neighbour.any() else None,
                                      'p90': float(np.percentile(d_neigh[on_neighbour], 90)) if on_neighbour.any() else None},
        'all_walls_distance_m': {'median': float(np.median(d_all)), 'within_1m': float(np.mean(d_all <= 1.0)),
                                 'within_2m': float(np.mean(d_all <= 2.0))},
        'camera_height_above_ground_m': {'median': float(np.median(cam_height)), 'p10': float(np.percentile(cam_height, 10)),
                                         'p90': float(np.percentile(cam_height, 90))},
        'cameras_in_height_band': int(((cam_height >= lo) & (cam_height <= hi)).sum()),
        'cameras': int(len(cam_height)),
        'cameras_inside_buildings': int(inside(world_cams[:, :2]).sum()),
        'yaw': yaw_uniqueness,
    }
    gate = {
        'independent_scales_agree': abs(scale_checks['library_vs_vertical_ratio'] - 1) <= 0.05,
        'photographers_on_the_ground_leave_one_out': scale_checks['leave_one_out_photographer_heights_m']['within_band'] >= 0.6 * scale_checks['leave_one_out_photographer_heights_m']['cameras'],
        'neighbour_on_its_walls': (metrics['neighbour_wall_distance_m']['median'] or 1e9) <= 1.0 and on_neighbour.sum() >= 200,
        'no_camera_inside_a_building': metrics['cameras_inside_buildings'] == 0,
        'scale_determined': 2 * uncertainty['scale_relative_sd'] <= GATE['scale_relative_2sigma'],
        'yaw_unique': yaw_uniqueness['runner_up_walls_explained'] < 0.85 * yaw_uniqueness['best_walls_explained'],
    }
    gate = {k: bool(v) for k, v in gate.items()}
    # The frame is usable for metric work when two independent scale estimates
    # agree within 10 %, the neighbouring building sits on its walls and the
    # one fitted angle is unique; photographer heights are reported, not gated,
    # because distant photographers are poorly placed along their viewing rays
    # (the same ambiguity the archival resection studies).
    usable = (abs(scale_checks['library_vs_vertical_ratio'] - 1) <= 0.10 and gate['neighbour_on_its_walls']
              and gate['yaw_unique'] and gate['no_camera_inside_a_building'])
    scale_spread = abs(scale_checks['library_vs_vertical_ratio'] - 1)
    s, R, t = sim
    return {
        'method': 'tower axis fixes position; scale from standing photographers and the measured tower top; one yaw from walls; horizontal scales held out',
        'scale_checks': scale_checks, 'vertical_scale': {k: v for k, v in vertical.items() if k != 'per_camera_scales'},
        'similarity': {'scale_m_per_model_unit': float(s), 'rotation': R.tolist(), 'translation_utm18n': t.tolist()},
        'gravity': {'model_up': up.tolist(), 'from': 'wall-like facade normals', **gravity_quality,
                    'camera_up_hint_angle_deg': float(np.degrees(np.arccos(np.clip(up @ hint, -1, 1)))),
                    'camera_up_spread_deg_median': float(np.median(up_spread))},
        'landmark_building': landmark, 'neighbour_building': neighbour,
        'tower_point_ids': point_ids[tower_mask].tolist(),
        'metrics': metrics, 'uncertainty': {**uncertainty, 'independent_scale_disagreement': scale_spread},
        'gate': gate, 'passed': all(gate.values()), 'metric_frame_usable': bool(usable),
        'camera_heights_m': {im.name: float(h) for im, h in zip(images, cam_height)},
    }, sim


def run(run_path, component, landmark='McGraw Tower', neighbour='Uris Library'):
    import pycolmap
    run_path = Path(run_path).resolve()
    report = json.loads((run_path / 'report.json').read_text())
    if report.get('status') != 'sfm_complete': raise ValueError('A completed sparse run is required')
    comp = next(c for c in report['components'] if str(c['id']) == str(component))
    model = pycolmap.Reconstruction(str(run_path / comp['model_path']))
    result, (s, R, t) = fit(model, landmark, neighbour)
    out = run_path / 'anchor' / str(component); out.mkdir(parents=True, exist_ok=True)
    lidar_report = json.loads((LIDAR / 'report.json').read_text())
    anchored = pycolmap.Reconstruction(str(run_path / comp['model_path']))
    origin = np.asarray(lidar_report['box_utm'][:2] + [0.0])
    # Local metric frame: UTM 18N minus the lidar box origin (keeps float32 precision in the viewer).
    sim = pycolmap.Sim3d(s, pycolmap.Rotation3d(R), t - origin)
    anchored.transform(sim)
    (out / 'model-local-metres').mkdir(exist_ok=True)
    anchored.write(str(out / 'model-local-metres'))
    result.update({'schema_version': 1, 'created_utc': datetime.now(timezone.utc).isoformat(), 'run_id': report['run_id'],
                   'component_id': str(component), 'model_path': comp['model_path'], 'pycolmap_version': pycolmap.__version__,
                   'lidar_report': str(LIDAR / 'report.json'), 'footprints': str(FOOTPRINTS),
                   'local_frame': {'crs': 'EPSG:32618', 'origin_utm18n': origin.tolist(),
                                   'meaning': 'local = UTM 18N coordinates minus origin, metres, z up'},
                   'anchored_model': str(out / 'model-local-metres'),
                   'metric_units': bool(result['metric_frame_usable']),
                   'scale_status': ('lidar-anchored, all checks passed' if result['passed'] else
                                    f"lidar-anchored; independent scales differ by {100 * result['uncertainty']['independent_scale_disagreement']:.1f} %; some checks failed"
                                    if result['metric_frame_usable'] else 'anchoring attempted; frame not usable'),
                   'inputs_used': 'model 3D points and camera orientations; OSM footprints; lidar surface and ground; no geotags, no manual correspondences',
                   'checks_not_used_by_the_fit': 'neighbour and other building points vs their walls; photographer heights vs lidar ground'})
    (out / 'report.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--component', required=True)
    parser.add_argument('--landmark', default='McGraw Tower')
    parser.add_argument('--neighbour', default='Uris Library')
    args = parser.parse_args()
    result = run(args.run, args.component, args.landmark, args.neighbour)
    print(json.dumps({k: result[k] for k in ('similarity', 'metrics', 'uncertainty', 'gate', 'passed')}, indent=2))


if __name__ == '__main__': main()
