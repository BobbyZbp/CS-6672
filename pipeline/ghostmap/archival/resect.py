"""Resection of a photograph through surviving structure, with an identifiability certificate.

A photograph registered only through a few distant, nearly planar surviving
anchors is ambiguous along one direction: the camera can slide along its
viewing ray toward the anchors while the focal length changes, and the anchors
reproject almost unchanged (the dolly-zoom ambiguity). This module measures
that ambiguity instead of hiding it.

For each focal length on a log grid, COLMAP's absolute pose solver
(LO-RANSAC plus refinement, focal fixed) places the camera; a robust
reprojection cost over every anchor correspondence gives a profile likelihood
over focal length, and each grid point carries its camera centre. Optional
cues reweight the same grid:

- standpoint: the photographer stood on the measured (lidar) ground, a few
  metres above it at most;
- people: pedestrians in the photograph stand on that ground and are about
  1.70 m tall, so their pixel height must match the camera's distance to them.

The certificate reports intervals for focal length, camera centre along the
ambiguity ray and camera height, for each cue combination, so the contribution
of every cue is an ablation, not a claim.
"""
from __future__ import annotations

import numpy as np

CAUCHY_PX = 4.0
STANDPOINT_BAND_M = (0.5, 4.0)   # eye height on the ground, or a few steps up
STANDPOINT_SOFTNESS_M = 1.0
PERSON_HEIGHT_M = (1.70, 0.08)


def focal_grid(width, height, lo=0.3, hi=5.0, n=72):
    return np.geomspace(lo, hi, n) * max(width, height)


def camera_centre(cam_from_world):
    R = cam_from_world.rotation.matrix(); t = np.asarray(cam_from_world.translation)
    return -R.T @ t


def project(points3D, R, t, f, cx, cy):
    X = points3D @ R.T + t
    z = X[:, 2]
    uv = np.column_stack([f * X[:, 0] / z + cx, f * X[:, 1] / z + cy])
    return uv, z


def profile(points2D, points3D, width, height, focals=None, ransac_px=12.0):
    """Pose and robust cost for each focal length (principal point at the centre)."""
    import pycolmap
    points2D = np.asarray(points2D, float); points3D = np.asarray(points3D, float)
    focals = focal_grid(width, height) if focals is None else np.asarray(focals, float)
    cx, cy = width / 2, height / 2
    rows = []
    for f in focals:
        camera = pycolmap.Camera(model='SIMPLE_RADIAL', width=int(width), height=int(height), params=[f, cx, cy, 0.])
        est = pycolmap.AbsolutePoseEstimationOptions(); est.estimate_focal_length = False
        est.ransac.max_error = ransac_px
        ref = pycolmap.AbsolutePoseRefinementOptions(); ref.refine_focal_length = False; ref.refine_extra_params = False
        result = pycolmap.estimate_and_refine_absolute_pose(points2D, points3D, camera, est, ref)
        if result is None:
            rows.append({'focal_px': float(f), 'ok': False}); continue
        pose = result['cam_from_world']
        R = pose.rotation.matrix(); t = np.asarray(pose.translation)
        uv, z = project(points3D, R, t, f, cx, cy)
        r = np.where(z > 0, np.linalg.norm(uv - points2D, axis=1), 1e3)
        cost = float(np.sum(np.log1p((r / CAUCHY_PX) ** 2)))
        rows.append({'focal_px': float(f), 'ok': True, 'cost': cost, 'inliers': int(result['num_inliers']),
                     'median_residual_px': float(np.median(r[r < 1e3])) if np.any(r < 1e3) else None,
                     'R': R, 't': t, 'centre': -R.T @ t})
    return rows


def standpoint_log_prior(centres, ground_height):
    """Soft band: the camera stood 0.5-4 m above the measured ground."""
    h = centres[:, 2] - ground_height(centres[:, :2])
    lo, hi = STANDPOINT_BAND_M
    outside = np.maximum(0, np.maximum(lo - h, h - hi))
    return -0.5 * (outside / STANDPOINT_SOFTNESS_M) ** 2, h


def ground_ray_intersection(C, direction, ground_height, max_range=2000., step=0.5):
    """First point where a ray from C meets the ground raster (None if never)."""
    ts = np.arange(step, max_range, step)
    P = C + ts[:, None] * direction
    below = P[:, 2] <= ground_height(P[:, :2])
    if not below.any(): return None
    i = int(np.argmax(below))
    return P[i]


def people_log_likelihood(row, people, width, height, ground_height):
    """Pedestrians stand on the ground and are about 1.70 m tall.

    people: list of (foot_uv, head_uv) pixel pairs. For the pose in `row`, the
    foot ray meets the ground at F; the head pixel predicted for a person of
    height h at F is compared with the observed head pixel, marginalising h
    over its prior. Returns (log-likelihood, per-person implied heights).
    """
    f, R, t = row['focal_px'], row['R'], row['t']
    C = row['centre']; cx, cy = width / 2, height / 2
    total, implied = 0.0, []
    mean_h, sd_h = PERSON_HEIGHT_M
    for foot, head in people:
        d = R.T @ np.array([(foot[0] - cx) / f, (foot[1] - cy) / f, 1.0]); d /= np.linalg.norm(d)
        F = ground_ray_intersection(C, d, ground_height)
        if F is None:
            total += -8.0; implied.append(None); continue
        # Height implied by the head pixel: intersect the head ray with the vertical line through F.
        dh = R.T @ np.array([(head[0] - cx) / f, (head[1] - cy) / f, 1.0]); dh /= np.linalg.norm(dh)
        horiz = np.linalg.norm((F - C)[:2]); dir_h = np.linalg.norm(dh[:2])
        if dir_h < 1e-9:
            total += -8.0; implied.append(None); continue
        z_head = C[2] + dh[2] * horiz / dir_h
        h = float(z_head - F[2]); implied.append(h)
        total += -0.5 * ((h - mean_h) / sd_h) ** 2
    return total, implied


def visible_fraction(C, points3D, surface_height, step=0.5, start_margin=30.0, end_margin=5.0, tolerance=2.0):
    """Fraction of anchor points with an unobstructed line of sight from C.

    The line of sight to each point is sampled against the measured lidar
    surface; it is blocked if the surface rises above it anywhere before the
    last `end_margin` metres (where the point's own building is). A pose that
    sees anchors through a building, for example the far face of a symmetric
    tower, is physically impossible however small its reprojection error.
    """
    C = np.asarray(C, float); visible = 0
    for X in np.asarray(points3D, float):
        d = X - C; L = np.linalg.norm(d)
        if L <= end_margin: visible += 1; continue
        ts = np.arange(start_margin, L - end_margin, step)
        if len(ts) == 0: visible += 1; continue
        P = C + ts[:, None] * (d / L)
        if not np.any(surface_height(P[:, :2]) > P[:, 2] + tolerance): visible += 1
    return visible / max(len(points3D), 1)


def posterior(rows, log_prior=None):
    ok = [r for r in rows if r['ok']]
    cost = np.array([r['cost'] for r in ok])
    logp = -cost + (0 if log_prior is None else log_prior)
    w = np.exp(logp - logp.max()); w /= w.sum()
    return ok, w


def interval(values, weights, mass=0.95):
    order = np.argsort(values); v, w = np.asarray(values)[order], np.asarray(weights)[order]
    c = np.cumsum(w); lo = v[np.searchsorted(c, (1 - mass) / 2)]; hi = v[min(len(v) - 1, np.searchsorted(c, 1 - (1 - mass) / 2))]
    return float(lo), float(hi)


def certificate(rows, anchor_centroid, ground_height, people=None, width=None, height=None,
                surface_height=None, anchors=None, min_visible=0.5):
    """Intervals under each cue combination, plus the per-grid data the viewer draws.

    With `surface_height` and `anchors`, each cue's most probable pose is also
    tested for line of sight to its anchors (see visible_fraction); a pose that
    could not have seen them is marked physically inconsistent.
    """
    ok = [r for r in rows if r['ok']]
    if len(ok) < 3: return {'status': 'not_registered', 'reason': 'absolute pose failed for almost every focal length'}
    centres = np.array([r['centre'] for r in ok]); focals = np.array([r['focal_px'] for r in ok])
    along = np.linalg.norm(centres - anchor_centroid, axis=1)
    stand, heights = standpoint_log_prior(centres, ground_height)
    combos = {'surviving anchors only': np.zeros(len(ok)), 'anchors + measured ground': stand}
    implied = None
    if people:
        ped = []; implied = []
        for r in ok:
            ll, imp = people_log_likelihood(r, people, width, height, ground_height)
            ped.append(ll); implied.append(imp)
        ped = np.asarray(ped)
        combos['anchors + people'] = ped
        combos['anchors + measured ground + people'] = stand + ped
    out = {'status': 'registered', 'grid': [], 'cues': {}}
    base_cost = np.array([r['cost'] for r in ok])
    for name, lp in combos.items():
        logp = -base_cost + lp; w = np.exp(logp - logp.max()); w /= w.sum()
        f_lo, f_hi = interval(np.log(focals), w)
        a_lo, a_hi = interval(along, w); h_lo, h_hi = interval(heights, w)
        best = int(np.argmax(w))
        out['cues'][name] = {
            'focal_px_95': [float(np.exp(f_lo)), float(np.exp(f_hi))],
            'focal_interval_ratio': float(np.exp(f_hi - f_lo)),
            'distance_to_anchors_m_95': [a_lo, a_hi], 'distance_interval_m': a_hi - a_lo,
            'camera_height_above_ground_m_95': [h_lo, h_hi],
            'map_focal_px': float(focals[best]), 'map_centre': centres[best].tolist(),
            'weights': w.tolist(),
        }
    for r, c, a, h in zip(ok, centres, along, heights):
        out['grid'].append({'focal_px': r['focal_px'], 'centre': c.tolist(), 'rotation': r['R'].tolist(),
                            'translation': r['t'].tolist(), 'distance_to_anchors_m': float(a), 'height_above_ground_m': float(h),
                            'cost': r['cost'], 'inliers': r['inliers'], 'median_residual_px': r['median_residual_px']})
    if surface_height is not None and anchors is not None:
        for name, c in out['cues'].items():
            frac = visible_fraction(c['map_centre'], anchors, surface_height)
            c['anchors_visible_fraction'] = float(frac)
            c['physically_consistent'] = bool(frac >= min_visible)
    base = out['cues']['surviving anchors only']
    for name, c in out['cues'].items():
        c['distance_interval_shrink_vs_anchors_only'] = 1 - c['distance_interval_m'] / max(base['distance_interval_m'], 1e-9)
        c['focal_interval_shrink_vs_anchors_only'] = 1 - np.log(c['focal_interval_ratio']) / max(np.log(base['focal_interval_ratio']), 1e-9)
    if implied is not None:
        out['people_implied_heights_at_map'] = implied[int(np.argmax(out['cues']['anchors + measured ground + people']['weights']))]
    return out
