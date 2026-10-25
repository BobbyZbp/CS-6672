#!/usr/bin/env python3
"""Anchor a COLMAP fragment to lidar through one named building's footprint.

The landmark method in `anchor/align.py` needs McGraw Tower in the fragment.
Fragments that see only Goldwin Smith Hall, Uris Library or Gates Hall are
anchored here through the building's OpenStreetMap footprint and the lidar
around it, again without geotags or hand-picked correspondences:

1. Gravity from wall-like facade normals (shared with the landmark method).
2. A wide grid of scales around a rough prior (the fragment's core spans the
   facade from foot to top; the lidar roof edges give that height). At each
   scale, yaw every 3 degrees; for each yaw the horizontal position starts at
   the best cell of a grid over the footprint and descends along the wall
   distance field. The objective is the geometric mean of precision (points
   near the named building's walls) and recall (wall length the points cover),
   so a fragment cannot shrink onto one wall line; plus a roof-edge term (the
   model's facade top along each wall, taken where the point density ends,
   against the lidar surface just inside that wall, with the photographers at
   eye height); minus photographers inside any footprint and the spread of
   their heights above the lidar ground. The best few scales are refined
   jointly over yaw, log scale and position (Nelder-Mead from an explicit
   simplex, since UTM coordinates are hundreds of kilometres).
3. The vertical position is the photographers' median eye height.

Reported checks: the scale the walls alone prefer (biased towards stretching a
facade along its wall, so it only vetoes the fit when 25 % off); the other
three yaw quadrants, which a rectangular hall nearly satisfies and which must
score clearly worse; the per-wall roof-edge scale estimates and their spread
(the frame is usable only when at least two walls agree within 15 %); the
neighbouring buildings' walls; the photographers' heights. The report has the
same shape as the landmark method's, so the chronology and viewer stages read
either. The native model is never modified; a transformed copy is written next
to the report.

A single facade of unknown scale fits walls of different heights at different
scales; the Goldwin Smith portico fragment shows this and is reported as not
usable. The synthetic check in `tests/test_artsquad_footprint_anchor.py`
recovers a known similarity on a two-facade hall.

Usage: PYTHONPATH=pipeline python -m ghostmap.anchor.footprint --run <run> --component <id> --building "Goldwin Smith Hall"
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from ghostmap.anchor.align import (FOOTPRINTS, GATE, InsideMask, WallField, apply, camera_up, facade_up, raster_lookup,
                                   robust_mean_direction, rot_z, rotation_to_z)
from ghostmap.paths import ROOT

LIDAR_CROPS = {'quad': ROOT / 'data/lidar/NY_FingerLakes_1_2020', 'gates-site': ROOT / 'data/lidar/gates-site'}
EYE_M = 1.6
KERNEL_M = 0.75           # wall score: mean exp(-(distance / KERNEL_M)^2); WallField truncates the distance at 6 m
COARSE_POINTS = 1000      # points used by the yaw search; the refinement uses up to REFINE_POINTS
REFINE_POINTS = 4000
NEIGHBOUR_RADIUS_M = 150  # buildings whose centroid lies within this distance count as neighbours (a check)
WALL_BAND_M = 2.5         # points this close to a wall belong to it for the per-wall scale
MIN_WALL_POINTS = 30
MIN_WALL_LENGTH_M = 4.0


def lidar_for(ring, crops=LIDAR_CROPS):
    """The lidar crop whose box contains the footprint, with its rasters."""
    r = np.asarray(ring)
    for name, folder in crops.items():
        if not (folder / 'quad-rasters-utm18n.npz').exists(): continue
        rasters = np.load(folder / 'quad-rasters-utm18n.npz'); box = tuple(rasters['box'])
        if box[0] <= r[:, 0].min() and r[:, 0].max() <= box[2] and box[1] <= r[:, 1].min() and r[:, 1].max() <= box[3]:
            return name, folder, rasters
    raise ValueError('no lidar crop contains the footprint')


class Walls:
    """The named building's walls, one per footprint edge, with the lidar roof edge just inside each
    and the lidar ground just outside; assigns points to their nearest wall."""

    def __init__(self, ring, surface, ground, box, cell, inset_m=1.5):
        from shapely.geometry import Polygon
        ring = np.asarray(ring, float)
        if not np.allclose(ring[0], ring[-1]): ring = np.vstack([ring, ring[:1]])
        poly = Polygon(ring); ccw = poly.exterior.is_ccw
        self.a, self.b = ring[:-1], ring[1:]
        d = self.b - self.a; self.length = np.linalg.norm(d, axis=1)
        unit = d / np.maximum(self.length, 1e-9)[:, None]
        inward = np.column_stack([-unit[:, 1], unit[:, 0]]) * (1 if ccw else -1)
        self.eave, self.ground = np.full(len(d), np.nan), np.full(len(d), np.nan)
        for i in range(len(d)):
            if self.length[i] < MIN_WALL_LENGTH_M: continue
            t = np.arange(0.5, self.length[i] - 0.5, 0.5) / self.length[i]
            along = self.a[i] + t[:, None] * d[i]
            self.eave[i] = np.nanmedian(raster_lookup(surface, box, cell, along + inset_m * inward[i]))
            self.ground[i] = np.nanmedian(raster_lookup(ground, box, cell, along - inset_m * inward[i]))

    def nearest(self, xy):
        """Index of the nearest wall and the distance to it, for points (N, 2) in metres."""
        ab = self.b - self.a; l2 = np.maximum((ab ** 2).sum(1), 1e-9)
        t = np.clip(((xy[:, None, :] - self.a[None]) * ab[None]).sum(2) / l2[None], 0, 1)
        dist = np.linalg.norm(xy[:, None, :] - (self.a[None] + t[..., None] * ab[None]), axis=2)
        return dist.argmin(1), dist.min(1)


def fit_arrays(points, centres, rotations, building, buildings, rasters, seed=0, yaw_step_deg=3.0, scale_steps=21, debug_truth=None):
    """Fit from arrays: 3D points, camera centres and cam-from-world rotations in model units;
    the named building; all footprints; the lidar rasters (box, cell, surface, ground)."""
    from ghostmap.anchor.lidar import fill_nearest
    from scipy.optimize import minimize
    from shapely.geometry import Polygon

    ring = np.asarray(next(b for b in buildings if b['name'] == building)['ring']); poly = Polygon(ring)
    box, cell = tuple(rasters['box']), float(rasters['cell'])
    surface, ground = fill_nearest(rasters['surface']), fill_nearest(rasters['ground'])  # QL2 leaves empty cells
    centroid_lidar = np.asarray(poly.centroid.coords[0])
    all_rings = [b['ring'] for b in buildings]
    neighbour_rings = [b['ring'] for b in buildings
                       if b['name'] != building and np.linalg.norm(np.mean(b['ring'], 0) - centroid_lidar) < NEIGHBOUR_RADIUS_M]
    walls = Walls(ring, surface, ground, box, cell)

    hint, up_spread = robust_mean_direction(camera_up(rotations))
    up, gravity_quality = facade_up(points, hint)
    Rg = rotation_to_z(up)
    pg, cg = points @ Rg.T, centres @ Rg.T
    centroid_model = np.median(pg[:, :2], 0)
    cam_z_model = float(np.median(cg[:, 2]))
    rng = np.random.default_rng(seed)
    sub = rng.choice(len(pg), min(COARSE_POINTS, len(pg)), replace=False)
    sub_refine = rng.choice(len(pg), min(REFINE_POINTS, len(pg)), replace=False)

    own_walls, neighbour_walls = WallField([ring], box), WallField(neighbour_rings, box)
    every_wall, inside = WallField(all_rings, box), InsideMask(all_rings, box)

    def nelder_mead(fun, x0, steps, maxiter):
        """Nelder-Mead from an explicit simplex: UTM coordinates are hundreds of kilometres, so scipy's
        default 5 % initial steps would be kilometres; these steps are the expected corrections."""
        x0 = np.asarray(x0, float)
        simplex = np.vstack([x0] + [x0 + np.eye(len(x0))[i] * steps[i] for i in range(len(x0))])
        return minimize(fun, x0, method='Nelder-Mead', options={'initial_simplex': simplex, 'xatol': 1e-4, 'fatol': 1e-6, 'maxiter': maxiter})

    def place(theta, s, txy, idx):
        R2 = rot_z(theta)[:2, :2]
        return s * pg[idx, :2] @ R2.T + txy, s * cg[:, :2] @ R2.T + txy

    def height_spread(s, cams):
        """Median absolute deviation of the photographers' heights above the lidar ground, metres."""
        h = s * cg[:, 2] - raster_lookup(ground, box, cell, cams)
        return float(np.median(np.abs(h - np.median(h))))

    # Wall cells of the named building on a 1 m grid, for the recall half of the wall score.
    wall_cells = np.zeros((int(np.ceil((box[3] - box[1]))), int(np.ceil((box[2] - box[0])))), bool)
    for a_, b_ in zip(walls.a, walls.b):
        for t_ in np.linspace(0, 1, max(2, int(np.linalg.norm(b_ - a_) * 2))):
            e, n = a_ + t_ * (b_ - a_); r_, c_ = int(box[3] - n), int(e - box[0])
            if 0 <= r_ < wall_cells.shape[0] and 0 <= c_ < wall_cells.shape[1]: wall_cells[r_, c_] = True
    wall_cell_count = int(wall_cells.sum())

    def on_walls(pts):
        """Geometric mean of precision (points near the walls) and recall (wall length the points cover):
        a fragment shrunk onto one wall line keeps its precision but loses its recall."""
        precision = float(np.mean(np.exp(-(own_walls(pts) / KERNEL_M) ** 2)))
        r_ = (box[3] - pts[:, 1]).astype(int); c_ = (pts[:, 0] - box[0]).astype(int)
        ok = (r_ >= 0) & (r_ < wall_cells.shape[0]) & (c_ >= 0) & (c_ < wall_cells.shape[1])
        hit = np.zeros_like(wall_cells); hit[r_[ok], c_[ok]] = True
        for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):  # a point covers its cell and the four neighbours
            hit |= np.roll(np.roll(hit, dr, 0), dc, 1)
        recall = float((hit & wall_cells).sum() / max(wall_cell_count, 1))
        return float(np.sqrt(precision * recall))

    def facade_top(z, s):
        """Height (model units) where a facade's point density ends: the highest 0.5 m bin that still holds a
        quarter of the typical bin count between the 10th and 90th percentiles (a percentile would sit below
        the roof edge; the maximum would follow a tree or a chimney)."""
        lo, hi = np.percentile(z, [10, 90]); width = 0.5 / s
        edges = np.arange(z.min(), z.max() + 2 * width, width)
        counts, _ = np.histogram(z, edges)
        body = (edges[:-1] >= lo) & (edges[:-1] <= hi)
        typical = np.median(counts[body]) if body.any() else counts.max()
        full = np.flatnonzero(counts >= 0.25 * typical)
        return float(edges[full.max() + 1]) if len(full) else float(np.percentile(z, 95))

    def roof_edges(s, idx, pts, cams):
        """How well the model's facade top along each wall meets that wall's lidar roof edge, with the
        photographers at eye height: mean over walls with enough points of exp(-((top - roof edge) / 2 m)^2).
        A collapsed scale puts every facade top near the ground and scores zero here."""
        tz = float(np.median(raster_lookup(ground, box, cell, cams) + EYE_M - s * cg[:, 2]))
        wall, dist = walls.nearest(pts)
        close = dist <= WALL_BAND_M
        z = pg[idx, 2]
        terms = []
        for w in np.unique(wall[close]):
            sel = close & (wall == w)
            if sel.sum() < max(10, MIN_WALL_POINTS * len(idx) // len(pg)) or not np.isfinite(walls.eave[w]): continue
            top = s * facade_top(z[sel], s) + tz
            terms.append(np.exp(-((top - walls.eave[w]) / 2.0) ** 2))
        return float(np.mean(terms)) if terms else 0.0

    def score(theta, s, txy, idx=sub):
        pts, cams = place(theta, s, txy, idx)
        return on_walls(pts) + 0.5 * roof_edges(s, idx, pts, cams) - 0.5 * float(np.mean(inside(cams))) - 0.05 * height_spread(s, cams)

    # Candidate positions of the fragment's centre: a grid over the footprint and 25 m around it.
    grid_step = 4.0
    gx = np.arange(ring[:, 0].min() - 25, ring[:, 0].max() + 25, grid_step); gy = np.arange(ring[:, 1].min() - 25, ring[:, 1].max() + 25, grid_step)
    offsets = np.column_stack([np.repeat(gx, len(gy)), np.tile(gy, len(gx))])
    coarse = rng.choice(len(pg), min(400, len(pg)), replace=False)

    def best_position(theta, s):
        """The grid position where most of the fragment's points lie on the walls (precision alone; the scale is fixed here)."""
        R2 = rot_z(theta)[:2, :2]
        base = s * (pg[coarse, :2] - centroid_model) @ R2.T
        pts = (base[None] + offsets[:, None]).reshape(-1, 2)
        precision = np.exp(-(own_walls(pts) / KERNEL_M) ** 2).reshape(len(offsets), -1).mean(1)
        return offsets[int(np.argmax(precision))] - s * centroid_model @ R2.T

    def descend(theta, s, iterations=15):
        """Horizontal position for one yaw and scale: from the best grid position, move along the
        (untruncated) wall distance field, as point-to-wall ICP would."""
        R2 = rot_z(theta)[:2, :2]
        base = s * pg[sub, :2] @ R2.T
        txy = best_position(theta, s)
        field, fcell, h = own_walls.distance, own_walls.cell, 0.5
        for _ in range(iterations):
            p = base + txy
            d = np.minimum(raster_lookup(field, box, fcell, p), 10.0)
            gx = (raster_lookup(field, box, fcell, p + [h, 0]) - raster_lookup(field, box, fcell, p - [h, 0])) / (2 * h)
            gy = (raster_lookup(field, box, fcell, p + [0, h]) - raster_lookup(field, box, fcell, p - [0, h])) / (2 * h)
            step = np.array([np.mean(d * gx), np.mean(d * gy)])
            if np.linalg.norm(step) < 0.02: break
            txy = txy - step
        return txy

    yaws = np.radians(np.arange(0, 360, yaw_step_deg))

    def yaw_search(s):
        """Yaw and position at a given scale: every 3 degrees with position descent, then the best few
        distinct yaws refined over yaw and position together."""
        table, shifts = np.empty(len(yaws)), []
        for i, th in enumerate(yaws):
            txy = descend(th, s); shifts.append(txy); table[i] = score(th, s, txy)
        candidates = []
        for i in np.argsort(-table):
            if all(abs(((yaws[i] - yaws[k]) + np.pi) % (2 * np.pi) - np.pi) > np.radians(12) for k in candidates): candidates.append(i)
            if len(candidates) == 3: break
        best = None
        for i in candidates:
            res = nelder_mead(lambda x: -score(x[0], s, x[1:3], sub_refine), [yaws[i], *shifts[i]], [np.radians(2), 1.0, 1.0], 150)
            if best is None or -res.fun > best[0]: best = (-res.fun, float(res.x[0]), res.x[1:3])
        return best[1], best[2], table

    def vertical_scale(theta, s, txy):
        """Per wall: (lidar roof edge - photographers' eye height) / (model facade top - photographers' height),
        and the facade's own extent, (roof edge - ground) / (model facade top - model facade foot), as a second estimate."""
        pts, _ = place(theta, s, txy, slice(None))
        wall, dist = walls.nearest(pts)
        rows = []
        for w in np.unique(wall[dist <= WALL_BAND_M]):
            sel = (wall == w) & (dist <= WALL_BAND_M)
            if sel.sum() < MIN_WALL_POINTS or not np.isfinite(walls.eave[w]) or not np.isfinite(walls.ground[w]): continue
            top, foot = facade_top(pg[sel, 2], s), float(np.percentile(pg[sel, 2], 5))
            if top <= cam_z_model or top <= foot: continue
            rows.append({'wall': int(w), 'length_m': float(walls.length[w]), 'points': int(sel.sum()),
                         'lidar_roof_edge_m': float(walls.eave[w]), 'lidar_ground_m': float(walls.ground[w]),
                         'model_facade_top_units': top, 'model_facade_foot_units': foot,
                         'scale': float((walls.eave[w] - (walls.ground[w] + EYE_M)) / (top - cam_z_model)),
                         'scale_from_facade_extent': float((walls.eave[w] - walls.ground[w]) / (top - foot))})
        return rows

    def refine(theta0, txy0, s_prior, sigma_log):
        """Yaw, log scale and position together, with a Gaussian prior on the log scale."""
        def objective(x):
            return -score(x[0], np.exp(x[1]), x[2:4], sub_refine) + 0.5 * ((x[1] - np.log(s_prior)) / sigma_log) ** 2
        res = nelder_mead(objective, [theta0, np.log(s_prior), *txy0], [np.radians(2), 0.03, 1.0, 1.0], 800)
        return float(res.x[0]), float(np.exp(res.x[1])), res.x[2:4]

    # A wide scale grid around a rough prior (the fragment's core spans the facade from foot to top; the
    # lidar roof edges give that height), each scale with its own yaw and position; the best few refined jointly.
    radius = np.linalg.norm(pg[:, :2] - centroid_model, axis=1)
    core = radius <= np.percentile(radius, 60)
    model_height = float(np.percentile(pg[core, 2], 95) - np.percentile(pg[core, 2], 5))
    ok = np.isfinite(walls.eave) & np.isfinite(walls.ground)
    lidar_height = float(np.average(walls.eave[ok] - walls.ground[ok], weights=walls.length[ok]))
    s_prior = lidar_height / model_height
    grid0 = s_prior * np.exp(np.linspace(np.log(0.33), np.log(3.0), scale_steps))
    history = [{'step': 'scale grid around the facade-extent prior', 'lidar_facade_height_m': lidar_height,
                'model_facade_height_units': model_height, 'prior_scale': s_prior}]
    per_scale = []
    for g in grid0:
        th, sh, tbl = yaw_search(g)
        per_scale.append((score(th, g, sh, sub_refine), th, sh, tbl))
    scale_table = np.array([p[0] for p in per_scale])
    history.append({'step': 'objective by scale', 'values': {f'{g:.4f}': float(v) for g, v in zip(grid0, scale_table)}})
    best, tried = None, []
    for j in np.argsort(-scale_table):
        if any(abs(np.log(grid0[j] / grid0[k])) < 0.15 for k in tried): continue
        tried.append(j)
        th, s_j, sh = refine(per_scale[j][1], per_scale[j][2], float(grid0[j]), 1.0)
        v = score(th, s_j, sh, sub_refine)
        if best is None or v > best[0]: best = (v, th, s_j, sh, j)
        if len(tried) == 4: break
    _, theta, scale, txy, j_best = best
    table = per_scale[j_best][3]
    rows = vertical_scale(theta, scale, txy)
    history.append({'step': 'joint refinement', 'yaw_deg': float(np.degrees(theta)), 'scale': scale, 'objective': float(best[0]),
                    'walls_with_enough_points': len(rows)})
    if debug_truth is not None:  # tests only: the objective and its parts at a known placement (yaw, scale, position)
        th_t, s_t, txy_t = debug_truth
        pts_t, cams_t = place(th_t, s_t, txy_t, sub_refine)
        history.append({'step': 'objective at the given truth', 'objective': score(th_t, s_t, txy_t, sub_refine), 'on_walls': on_walls(pts_t),
                        'roof_edges': roof_edges(s_t, sub_refine, pts_t, cams_t), 'inside': float(np.mean(inside(cams_t))), 'height_spread': height_spread(s_t, cams_t),
                        'found': {'objective': float(best[0]), 'on_walls': on_walls(place(theta, scale, txy, sub_refine)[0]),
                                  'roof_edges': roof_edges(scale, sub_refine, *place(theta, scale, txy, sub_refine)),
                                  'inside': float(np.mean(inside(place(theta, scale, txy, sub_refine)[1]))), 'height_spread': height_spread(scale, place(theta, scale, txy, sub_refine)[1])}})
    R = rot_z(theta) @ Rg
    cams_xy = scale * cg[:, :2] @ rot_z(theta)[:2, :2].T + txy
    tz = float(np.median(raster_lookup(ground, box, cell, cams_xy) + EYE_M - scale * cg[:, 2]))
    sim = (scale, R, np.array([txy[0], txy[1], tz]))
    world_pts, world_cams = apply(sim, points), apply(sim, centres)

    # --- checks (none used by the fit) ---------------------------------------------------------
    # The scale the walls alone prefer: the wall score over a scale grid at the fitted yaw, position re-descended.
    grid = scale * np.exp(np.linspace(np.log(0.5), np.log(2.0), 29))
    wall_profile = np.array([on_walls(place(theta, g, descend(theta, g), sub_refine)[0]) for g in grid])
    within = wall_profile >= wall_profile.max() - 0.05 * abs(wall_profile.max())
    band = (float(grid[within].min() / scale), float(grid[within].max() / scale))
    walls_scale = float(grid[int(np.argmax(wall_profile))])
    walls_determined = band[1] / band[0] <= 1.25   # a peak narrower than +-10 % around its centre
    per_wall = np.array([r['scale'] for r in rows]) if rows else np.array([])
    extent_scale = float(np.median([r['scale_from_facade_extent'] for r in rows])) if rows else None
    wall_spread = float(np.median(np.abs(per_wall - scale)) / scale) if len(per_wall) else None

    d_own = own_walls(world_pts[:, :2]); d_neigh = neighbour_walls(world_pts[:, :2]); d_all = every_wall(world_pts[:, :2])
    off_own = d_own > 3.0; on_neighbour = off_own & (d_neigh <= 3.0)
    cam_height = world_cams[:, 2] - raster_lookup(ground, box, cell, world_cams[:, :2])
    lo, hi = GATE['camera_height_band_m']
    deg = np.degrees(yaws)
    quadrants = {}
    for q in (90, 180, 270):
        near = np.abs(((deg - (np.degrees(theta) + q) % 360) + 180) % 360 - 180) <= 15
        quadrants[f'+{q}'] = float(table[near].max())
    runner = float(table[np.abs(((deg - np.degrees(theta)) + 180) % 360 - 180) > 20].max())
    best_score = float(table.max())

    metrics = {
        'building': {'points_within_1m_of_own_walls': float(np.mean(d_own <= 1.0)), 'points_within_2m_of_own_walls': float(np.mean(d_own <= 2.0)),
                     'median_distance_to_own_walls_m': float(np.median(d_own)), 'points_near_own_walls': int((~off_own).sum()),
                     'walls_with_enough_points': len(rows), 'per_wall': rows},
        'neighbour_wall_distance_m': {'points_within_3m': int(on_neighbour.sum()),
                                      'median': float(np.median(d_neigh[on_neighbour])) if on_neighbour.any() else None,
                                      'p90': float(np.percentile(d_neigh[on_neighbour], 90)) if on_neighbour.any() else None,
                                      'points_off_the_named_building': int(off_own.sum())},
        'all_walls_distance_m': {'median': float(np.median(d_all)), 'within_1m': float(np.mean(d_all <= 1.0)), 'within_2m': float(np.mean(d_all <= 2.0))},
        'camera_height_above_ground_m': {'median': float(np.median(cam_height)), 'p10': float(np.percentile(cam_height, 10)), 'p90': float(np.percentile(cam_height, 90))},
        'cameras_in_height_band': int(((cam_height >= lo) & (cam_height <= hi)).sum()), 'cameras': int(len(cam_height)),
        'cameras_inside_buildings': int(inside(world_cams[:, :2]).sum()),
        'yaw': {'best_score': best_score, 'other_quadrants': quadrants, 'runner_up_outside_20deg': runner},
        'walls_only_scale': {'best_m_per_unit': walls_scale, 'band_within_5pct_of_best': {'low': band[0], 'high': band[1]},
                             'determined': bool(walls_determined), 'profile': {f'{g:.4f}': float(v) for g, v in zip(grid, wall_profile)}},
        'steps': history,
    }
    scale_checks = {'vertical_from_roof_edges_and_photographers': scale, 'horizontal_from_walls': walls_scale,
                    'vertical_from_facade_extent': extent_scale, 'prior_from_facade_extent': s_prior,
                    'walls_vs_vertical_ratio': walls_scale / scale, 'walls_scale_determined': bool(walls_determined),
                    'per_wall_relative_spread': wall_spread}
    disagreement = abs(scale_checks['walls_vs_vertical_ratio'] - 1)
    inside_fraction = metrics['cameras_inside_buildings'] / max(metrics['cameras'], 1)
    gate = {
        'independent_scales_agree': bool(walls_determined) and disagreement <= 0.05,
        'photographers_on_the_ground': metrics['cameras_in_height_band'] >= 0.6 * metrics['cameras'],
        'neighbours_on_their_walls': (metrics['neighbour_wall_distance_m']['median'] or 1e9) <= 1.0 and on_neighbour.sum() >= 100,
        'no_camera_inside_a_building': metrics['cameras_inside_buildings'] == 0,
        'scale_from_several_walls': len(rows) >= 2 and (wall_spread or 1) <= 0.15,
        'yaw_unique': all(v < 0.85 * best_score for v in quadrants.values()) if best_score > 0 else False,
        'yaw_runner_up_clear': runner < 0.85 * best_score if best_score > 0 else False,
    }
    gate = {k: bool(v) for k, v in gate.items()}
    # Usable for metric work when the roof-edge scale rests on at least two walls that agree within 15 %,
    # the one yaw is unique (no quadrant within 15 % of the best), at most 5 % of the photographers stand
    # inside a building, and the walls-only scale, where the walls determine one, is not wildly off (25 %):
    # that profile is biased towards stretching a facade along its wall, so it is reported, not trusted.
    usable = (gate['scale_from_several_walls'] and (not walls_determined or disagreement <= 0.25)
              and gate['yaw_unique'] and inside_fraction <= 0.05)
    s, R, t = sim
    return {
        'method': f'{building} footprint fixes yaw and position through its walls; scale from the lidar roof edge of each wall against the model facade top and the photographers at eye height; the walls-only scale is held out as the check',
        'scale_checks': scale_checks,
        'similarity': {'scale_m_per_model_unit': float(s), 'rotation': R.tolist(), 'translation_utm18n': t.tolist()},
        'gravity': {'model_up': up.tolist(), 'from': 'wall-like facade normals', **gravity_quality,
                    'camera_up_hint_angle_deg': float(np.degrees(np.arccos(np.clip(up @ hint, -1, 1)))),
                    'camera_up_spread_deg_median': float(np.median(up_spread))},
        'landmark_building': building, 'neighbour_building': None, 'neighbours_checked': len(neighbour_rings),
        'metrics': metrics,
        'uncertainty': {'independent_scale_disagreement': disagreement if walls_determined else None,
                        'per_wall_relative_spread': wall_spread, 'walls_only_scale_band': band},
        'gate': gate, 'passed': all(gate.values()), 'metric_frame_usable': bool(usable),
        'camera_heights_m': {str(i): float(h) for i, h in enumerate(cam_height)},
    }, sim


def fit(model, building, footprints=FOOTPRINTS, seed=0):
    buildings = json.loads(Path(footprints).read_text())['buildings']
    ring = next(b for b in buildings if b['name'] == building)['ring']
    crop_name, crop, rasters = lidar_for(ring)
    images = sorted(model.images.values(), key=lambda im: im.name)
    rotations = [im.cam_from_world().rotation.matrix() for im in images]
    centres = np.array([im.projection_center() for im in images])
    points = np.array([p.xyz for p in model.points3D.values()])
    result, sim = fit_arrays(points, centres, rotations, building, buildings, rasters, seed)
    result['camera_heights_m'] = {im.name: result['camera_heights_m'][str(i)] for i, im in enumerate(images)}
    result['lidar_crop'] = crop_name
    return result, sim, crop


def run(run_path, component, building):
    import pycolmap
    run_path = Path(run_path).resolve()
    report = json.loads((run_path / 'report.json').read_text())
    if report.get('status') != 'sfm_complete': raise ValueError('A completed sparse run is required')
    comp = next(c for c in report['components'] if str(c['id']) == str(component))
    model = pycolmap.Reconstruction(str(run_path / comp['model_path']))
    result, (s, R, t), crop = fit(model, building)
    out = run_path / 'anchor' / str(component); out.mkdir(parents=True, exist_ok=True)
    lidar_report = json.loads((crop / 'report.json').read_text())
    anchored = pycolmap.Reconstruction(str(run_path / comp['model_path']))
    origin = np.asarray(lidar_report['box_utm'][:2] + [0.0])
    # Local metric frame: UTM 18N minus the lidar crop's box origin (keeps float32 precision in the viewer).
    anchored.transform(pycolmap.Sim3d(s, pycolmap.Rotation3d(R), t - origin))
    (out / 'model-local-metres').mkdir(exist_ok=True)
    anchored.write(str(out / 'model-local-metres'))
    checks = result['scale_checks']
    if result['passed']: status = 'lidar-anchored through the footprint, all checks passed'
    elif result['metric_frame_usable'] and checks['walls_scale_determined']:
        status = f"lidar-anchored through the footprint; the walls-only scale differs by {100 * abs(checks['walls_vs_vertical_ratio'] - 1):.1f} %; some checks failed"
    elif result['metric_frame_usable']:
        status = f"lidar-anchored through the footprint; scale from the roof edges of {result['metrics']['building']['walls_with_enough_points']} walls (the walls alone do not determine it); some checks failed"
    else: status = 'anchoring attempted; frame not usable'
    result.update({'schema_version': 1, 'created_utc': datetime.now(timezone.utc).isoformat(), 'run_id': report['run_id'],
                   'component_id': str(component), 'model_path': comp['model_path'], 'pycolmap_version': pycolmap.__version__,
                   'lidar_report': str(crop / 'report.json'), 'footprints': str(FOOTPRINTS),
                   'local_frame': {'crs': 'EPSG:32618', 'origin_utm18n': origin.tolist(),
                                   'meaning': 'local = UTM 18N coordinates minus origin, metres, z up'},
                   'anchored_model': str(out / 'model-local-metres'),
                   'metric_units': bool(result['metric_frame_usable']), 'scale_status': status,
                   'inputs_used': f'model 3D points and camera orientations; the OSM footprint of {building} and its neighbours; lidar surface and ground; no geotags, no manual correspondences',
                   'checks_not_used_by_the_fit': 'walls-only scale profile; neighbour walls; other yaw quadrants; per-wall scale spread; photographer heights'})
    (out / 'report.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--component', required=True)
    parser.add_argument('--building', required=True, help='footprint name, e.g. "Goldwin Smith Hall"')
    args = parser.parse_args()
    result = run(args.run, args.component, args.building)
    shown = {k: result[k] for k in ('similarity', 'scale_checks', 'gate', 'passed', 'metric_frame_usable', 'scale_status')}
    shown['metrics'] = {k: v for k, v in result['metrics'].items() if k != 'walls_only_scale'}
    shown['metrics']['building'] = {k: v for k, v in result['metrics']['building'].items() if k != 'per_wall'}
    print(json.dumps(shown, indent=2))


if __name__ == '__main__': main()
