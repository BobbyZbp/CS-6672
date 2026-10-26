#!/usr/bin/env python3
"""Place a COLMAP fragment in metres from public data alone, and say how sure that is.

One estimator for every fragment, composed from the pieces that already work
(`anchor/align.py`: gravity, landmark, wall and inside rasters; `anchor/footprint.py`:
walls precision-and-recall, roof edges, position grid and descent, explicit-simplex
refinement). It owns three things:

1. **A registry of cues**, each a bounded score with a stated noise model, added with
   a weight: walls (points on OpenStreetMap footprint walls, precision over every wall
   in the box and recall over the named building's walls, so a fragment cannot shrink
   onto one wall line); roof edges (the model's facade top along each wall against the
   lidar surface just inside it, 2 m); camera height (photographers 1.6 +- 0.3 m above
   the lidar ground, robust to a few elevated viewpoints); the landmark (a tower's axis
   on its footprint centre and its top at the lidar top, when a tower is in the box);
   free space (the ray from each camera to each of its points must not pass through a
   building, after Kaminsky et al. 2009); cameras outside footprints.
2. **A search that keeps everything it looks at**: a grid over scale (0.33 to 3 times a
   prior from the facade's vertical extent) and yaw (every 3 degrees), the position
   found per cell from a grid over the named building and a descent along the wall
   distance field, then joint refinement of the best cells. Every cue's score is
   stored per cell, so the profile of any subset of cues over scale or yaw is read off
   afterwards without a second search.
3. **A certificate**: which degrees of freedom the fit determines (bands of scale, yaw
   and position inside which the objective stays within 5 % of its best; the other
   yaw quadrants and the runner-up), how far the optimum moves when each cue is
   removed (a local refinement per cue), the cues' own scale profiles, and a verdict
   with a named failure mode: `sees no walls` (the points are not on footprint walls
   at any placement, as for close-ups), `scale undetermined` (one facade fits walls of
   different heights at different scales), `yaw ambiguous`, `position undetermined`,
   `cameras inside buildings`, or usable, with the cue that fixed the scale named.

Geotags are never read here; they are the evaluation's held-out truth
(`evaluate/georegistration.py`). The report keeps the shape of the earlier anchors
(`similarity`, `metric_frame_usable`, `scale_status`, `local_frame`, `anchored_model`),
so the chronology and viewer stages read it unchanged.

Usage: PYTHONPATH=pipeline python -m ghostmap.anchor.georegister --run <run> --component <id> [--building "Goldwin Smith Hall"] [--without free_space,landmark]
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from ghostmap.anchor.align import (FOOTPRINTS, InsideMask, WallField, apply, camera_up, facade_up, raster_lookup,
                                   robust_mean_direction, rot_z, rotation_to_z, tallest_cluster)
from ghostmap.anchor.footprint import KERNEL_M, MIN_WALL_POINTS, WALL_BAND_M, Walls
from ghostmap.paths import ROOT

CONFIG = ROOT / 'config/artsquad-modern.json'
LIDAR_CROPS = {'quad': ROOT / 'data/lidar/NY_FingerLakes_1_2020', 'gates-site': ROOT / 'data/lidar/gates-site', 'campus': ROOT / 'data/lidar/campus'}
EYE_M, EYE_SD_M = 1.6, 0.3          # photographer height above the lidar ground
ROOF_EDGE_SD_M = 2.0                # facade top versus the lidar roof edge
LANDMARK_SD_M = (3.0, 2.0)          # tower axis to footprint centre; tower top to lidar top
TOWER_MIN_HEIGHT_M = 25.0           # a footprint this much above its ground counts as a landmark
FREE_SPACE_SAMPLES, FREE_SPACE_MAX_RAY_M = 32, 400.0   # samples along each camera-to-point ray; longer rays are outliers
WEIGHTS = {'walls': 1.0, 'roof_edges': 0.5, 'camera_height': 0.3, 'landmark': 1.0, 'free_space': 0.5, 'outside': 0.5}
COARSE_POINTS, REFINE_POINTS, FREE_SPACE_RAYS = 1000, 4000, 600
BAND_DROP = 0.10                    # a degree of freedom is "inside the band" while the objective loses less than a tenth of its dynamic range
LIMITS = {'walls_fraction_1m': 0.2, 'roof_edge_min': 0.25, 'scale_band': 0.15, 'yaw_contrast': 0.7, 'yaw_band_deg': 10.0, 'position_band_m': 5.0, 'cameras_inside': 0.05,
          'scale_disagreement': 0.25, 'per_wall_spread': 0.15}


def crop_for(ring, crops=LIDAR_CROPS, margin=60.0):
    """The smallest lidar crop that contains the footprint with a margin, with its rasters."""
    r = np.asarray(ring); best = None
    for name, folder in crops.items():
        if not (folder / 'quad-rasters-utm18n.npz').exists(): continue
        rasters = np.load(folder / 'quad-rasters-utm18n.npz'); box = tuple(rasters['box'])
        if box[0] + margin <= r[:, 0].min() and r[:, 0].max() <= box[2] - margin and box[1] + margin <= r[:, 1].min() and r[:, 1].max() <= box[3] - margin:
            area = (box[2] - box[0]) * (box[3] - box[1])
            if best is None or area < best[0]: best = (area, name, folder, rasters)
    if best is None: raise ValueError('no lidar crop contains the footprint with a %.0f m margin' % margin)
    return best[1:]


def nelder_mead(fun, x0, steps, maxiter):
    """Nelder-Mead from an explicit simplex (UTM coordinates are hundreds of kilometres; scipy's 5 % steps would be kilometres)."""
    from scipy.optimize import minimize
    x0 = np.asarray(x0, float)
    simplex = np.vstack([x0] + [x0 + np.eye(len(x0))[i] * steps[i] for i in range(len(x0))])
    return minimize(fun, x0, method='Nelder-Mead', options={'initial_simplex': simplex, 'xatol': 1e-4, 'fatol': 1e-6, 'maxiter': maxiter})


class Fragment:
    """A fragment in its gravity frame with the public data around its named building, and the cue scores."""

    def __init__(self, points, centres, rotations, building, buildings, rasters, observations=None, landmark=None, cues=None, seed=0):
        from ghostmap.anchor.lidar import fill_nearest
        from shapely.geometry import Polygon
        self.building = building
        self.ring = np.asarray(next(b for b in buildings if b['name'] == building)['ring'], float); self.poly = Polygon(self.ring)
        self.box, self.cell = tuple(rasters['box']), float(rasters['cell'])
        self.surface, self.ground = fill_nearest(rasters['surface']), fill_nearest(rasters['ground'])
        self.rings = [np.asarray(b['ring'], float) for b in buildings if _touches(b['ring'], self.box)]
        self.names = [b['name'] for b in buildings if _touches(b['ring'], self.box)]
        self.walls_all, self.inside = WallField(self.rings, self.box), InsideMask(self.rings, self.box)
        self.walls_named = WallField([self.ring], self.box)
        self.edges = Walls(self.ring, self.surface, self.ground, self.box, self.cell)
        # Lidar building heights where footprints are, ground elsewhere: the occluder for free space.
        self.building_raster = np.where(self.inside.mask, self.surface, self.ground) if self.inside.mask.shape == self.surface.shape else None
        # Gravity: from wall-like facade normals when the fragment holds facades in at least two directions; a single
        # facade leaves the vertical free to rotate within its plane, and a fragment without walls (a lawn) has no
        # facade normals at all, so those fall back to the photographers' camera-up direction (projected to be
        # orthogonal to the one facade, where there is one).
        hint, up_spread = robust_mean_direction(camera_up(rotations))
        self.up, self.gravity_quality = gravity(points, hint)
        self.gravity_quality.update({'camera_up_hint_angle_deg': float(np.degrees(np.arccos(np.clip(self.up @ hint, -1, 1)))),
                                     'camera_up_spread_deg_median': float(np.median(up_spread))})
        self.Rg = rotation_to_z(self.up)
        self.pg, self.cg = points @ self.Rg.T, centres @ self.Rg.T
        self.centroid_model = np.median(self.pg[:, :2], 0)
        self.cam_z_model = float(np.median(self.cg[:, 2]))
        rng = np.random.default_rng(seed)
        self.sub = rng.choice(len(self.pg), min(COARSE_POINTS, len(self.pg)), replace=False)
        self.sub_refine = rng.choice(len(self.pg), min(REFINE_POINTS, len(self.pg)), replace=False)
        # Camera-point observations for free space: (camera index, point index) pairs, a fixed subsample.
        self.rays = None
        if observations is not None and len(observations):
            obs = np.asarray(observations); self.rays = obs[rng.choice(len(obs), min(FREE_SPACE_RAYS, len(obs)), replace=False)]
        # Wall cells of the named building and of footprints within 40 m of it on a 1 m grid (recall: the wall length
        # the points cover; a tower's library and a hall's wings count, the far side of the campus does not).
        self.wall_cells = np.zeros((int(np.ceil(self.box[3] - self.box[1])), int(np.ceil(self.box[2] - self.box[0]))), bool)
        from shapely.geometry import Polygon as _Polygon
        near_rings = [r for r in self.rings if _Polygon(r).distance(self.poly) <= 40.0]
        self.recall_buildings = [n for n, r in zip(self.names, self.rings) if _Polygon(r).distance(self.poly) <= 40.0]
        for ring in near_rings:
            ring = np.asarray(ring)
            for a, b in zip(ring[:-1], ring[1:]):
                for t in np.linspace(0, 1, max(2, int(np.linalg.norm(b - a) * 2))):
                    e, n = a + t * (b - a); r, c = int(self.box[3] - n), int(e - self.box[0])
                    if 0 <= r < self.wall_cells.shape[0] and 0 <= c < self.wall_cells.shape[1]: self.wall_cells[r, c] = True
        # Landmark: a tower in the box (named, or the tallest footprint well above its ground) and the fragment's tallest cluster.
        self.landmark = None
        lm = landmark or self._tallest_footprint()
        if lm is not None and lm in self.names:
            ring = self.rings[self.names.index(lm)]; poly = Polygon(ring)
            inner = poly.buffer(-0.5) if not poly.buffer(-0.5).is_empty else poly
            e0, n0, e1, n1 = inner.bounds
            gx, gy = np.meshgrid(np.arange(e0, e1, self.cell), np.arange(n0, n1, self.cell))
            from shapely.geometry import Point
            grid = np.column_stack([gx.ravel(), gy.ravel()]); grid = grid[[inner.contains(Point(*g)) for g in grid]]
            top = float(np.nanmax(raster_lookup(self.surface, self.box, self.cell, grid))) if len(grid) else None
            outer = poly.buffer(3.0).exterior
            ring_pts = np.array([outer.interpolate(d).coords[0] for d in np.arange(0, outer.length, 0.5)])
            ground = float(np.nanmedian(raster_lookup(self.ground, self.box, self.cell, ring_pts)))
            mask, axis_xy, radius = tallest_cluster(self.pg)
            if top is not None and top - ground >= TOWER_MIN_HEIGHT_M and mask.sum() >= 50:
                self.landmark = {'name': lm, 'centre': np.asarray(poly.centroid.coords[0]), 'lidar_top': top, 'lidar_ground': ground,
                                 'mask': mask, 'axis_xy': axis_xy, 'model_top': float(np.percentile(self.pg[mask, 2], 99.5))}
        self.cues = {c: WEIGHTS[c] for c in (cues or WEIGHTS) if c in WEIGHTS}
        if 'landmark' in self.cues and self.landmark is None: self.cues.pop('landmark')
        if 'free_space' in self.cues and (self.rays is None or self.building_raster is None): self.cues.pop('free_space')

    def _tallest_footprint(self):
        """A landmark is a slender footprint (height at least twice the square root of its area) at least 25 m above its
        ground within 200 m of the named building; the tallest such, so a tower, not a tall laboratory block."""
        from shapely.geometry import Polygon
        best = None
        for name, ring in zip(self.names, self.rings):
            r = np.asarray(ring); poly = Polygon(r)
            if poly.distance(self.poly) > 200.0 or poly.area <= 0: continue
            top = float(np.nanmax(raster_lookup(self.surface, self.box, self.cell, r)))
            ground = float(np.nanmedian(raster_lookup(self.ground, self.box, self.cell, r)))
            height = top - ground
            if height >= TOWER_MIN_HEIGHT_M and height / np.sqrt(poly.area) >= 2.0 and (best is None or height > best[0]): best = (height, name)
        return best[1] if best else None

    # --- placement -----------------------------------------------------------------------------
    def place(self, theta, s, txy, idx):
        R2 = rot_z(theta)[:2, :2]
        return s * self.pg[idx, :2] @ R2.T + txy, s * self.cg[:, :2] @ R2.T + txy

    def tz(self, s, cams):
        """Vertical offset from all photographers standing at eye height (`cams`: every camera's placed xy)."""
        return float(np.median(raster_lookup(self.ground, self.box, self.cell, cams) + EYE_M - s * self.cg[:, 2]))

    def tz_at(self, theta, s, txy):
        return self.tz(s, s * self.cg[:, :2] @ rot_z(theta)[:2, :2].T + txy)

    # --- cues: each returns a score in [0, 1] (1 = perfectly consistent) ------------------------
    def cue_walls(self, theta, s, txy, idx):
        pts, _ = self.place(theta, s, txy, idx)
        precision = float(np.mean(np.exp(-(self.walls_all(pts) / KERNEL_M) ** 2)))
        r = (self.box[3] - pts[:, 1]).astype(int); c = (pts[:, 0] - self.box[0]).astype(int)
        ok = (r >= 0) & (r < self.wall_cells.shape[0]) & (c >= 0) & (c < self.wall_cells.shape[1])
        hit = np.zeros_like(self.wall_cells); hit[r[ok], c[ok]] = True
        for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)): hit |= np.roll(np.roll(hit, dr, 0), dc, 1)
        recall = float((hit & self.wall_cells).sum() / max(int(self.wall_cells.sum()), 1))
        return float(np.sqrt(precision * recall))

    def facade_top(self, z, s):
        """Height (model units) where a facade's point density ends (the highest 0.5 m bin still holding a quarter of the typical count)."""
        lo, hi = np.percentile(z, [10, 90]); width = 0.5 / s
        edges = np.arange(z.min(), z.max() + 2 * width, width); counts, _ = np.histogram(z, edges)
        body = (edges[:-1] >= lo) & (edges[:-1] <= hi)
        typical = np.median(counts[body]) if body.any() else counts.max()
        full = np.flatnonzero(counts >= 0.25 * typical)
        return float(edges[full.max() + 1]) if len(full) else float(np.percentile(z, 95))

    def per_wall(self, theta, s, txy, idx):
        pts, cams = self.place(theta, s, txy, idx)
        tz = self.tz(s, cams)
        wall, dist = self.edges.nearest(pts); close = dist <= WALL_BAND_M; z = self.pg[idx, 2]
        rows = []
        for w in np.unique(wall[close]):
            sel = close & (wall == w)
            if sel.sum() < max(10, MIN_WALL_POINTS * len(idx) // len(self.pg)) or not np.isfinite(self.edges.eave[w]): continue
            top = self.facade_top(z[sel], s)
            rows.append({'wall': int(w), 'length_m': float(self.edges.length[w]), 'points': int(sel.sum()),
                         'model_facade_top_m': float(s * top + tz), 'lidar_roof_edge_m': float(self.edges.eave[w]),
                         'scale_from_this_wall': float((self.edges.eave[w] - self.tz_ground(cams) - EYE_M) / (top - self.cam_z_model)) if top > self.cam_z_model else None})
        return rows

    def tz_ground(self, cams):
        return float(np.median(raster_lookup(self.ground, self.box, self.cell, cams)))

    def cue_roof_edges(self, theta, s, txy, idx):
        rows = self.per_wall(theta, s, txy, idx)
        if not rows: return 0.0
        return float(np.mean([np.exp(-((r['model_facade_top_m'] - r['lidar_roof_edge_m']) / ROOF_EDGE_SD_M) ** 2) for r in rows]))

    def cue_camera_height(self, theta, s, txy, idx):
        _, cams = self.place(theta, s, txy, idx)
        h = s * self.cg[:, 2] + self.tz(s, cams) - raster_lookup(self.ground, self.box, self.cell, cams)
        return float(np.mean(np.exp(-((h - EYE_M) / (2 * EYE_SD_M)) ** 2)))

    def cue_landmark(self, theta, s, txy, idx):
        lm = self.landmark
        axis = s * lm['axis_xy'] @ rot_z(theta)[:2, :2].T + txy
        _, cams = self.place(theta, s, txy, idx)
        top = s * lm['model_top'] + self.tz(s, cams)
        return float(np.exp(-(np.linalg.norm(axis - lm['centre']) / LANDMARK_SD_M[0]) ** 2) * np.exp(-((top - lm['lidar_top']) / LANDMARK_SD_M[1]) ** 2))

    def cue_free_space(self, theta, s, txy, idx):
        cam_i, pt_i = self.rays[:, 0], self.rays[:, 1]
        R2 = rot_z(theta)[:2, :2]
        pts = s * self.pg[pt_i, :2] @ R2.T + txy; cams = s * self.cg[cam_i, :2] @ R2.T + txy
        tz = self.tz_at(theta, s, txy); pz = s * self.pg[pt_i, 2] + tz; cz = s * self.cg[cam_i, 2] + tz
        d = pts - cams; L = np.linalg.norm(d, axis=1)
        keep = L <= FREE_SPACE_MAX_RAY_M   # a far outlier point would otherwise dictate the sampling of every ray
        if keep.sum() < 20: return 1.0
        d, cams, L, pz, cz = d[keep], cams[keep], L[keep], pz[keep], cz[keep]
        n = FREE_SPACE_SAMPLES
        t = np.linspace(0.05, 0.95, n)[None, :, None]
        samples = cams[:, None, :] + t * d[:, None, :]; heights = cz[:, None] + t[..., 0] * (pz - cz)[:, None]
        roof = raster_lookup(self.building_raster, self.box, self.cell, samples.reshape(-1, 2)).reshape(len(L), n)
        blocked = np.any((self.inside(samples.reshape(-1, 2)).reshape(len(L), n)) & (roof > heights + 1.0), axis=1)
        return float(1.0 - np.mean(blocked))

    def cue_outside(self, theta, s, txy, idx):
        _, cams = self.place(theta, s, txy, idx)
        return float(1.0 - np.mean(self.inside(cams)))

    def scores(self, theta, s, txy, idx):
        return {c: getattr(self, 'cue_' + c)(theta, s, txy, idx) for c in self.cues}

    def objective(self, theta, s, txy, idx, without=()):
        sc = self.scores(theta, s, txy, idx)
        return sum(self.cues[c] * v for c, v in sc.items() if c not in without), sc

    # --- position per yaw and scale ----------------------------------------------------------
    def position_grid(self, margin=50.0, step=4.0):
        gx = np.arange(self.ring[:, 0].min() - margin, self.ring[:, 0].max() + margin, step)
        gy = np.arange(self.ring[:, 1].min() - margin, self.ring[:, 1].max() + margin, step)
        return np.column_stack([np.repeat(gx, len(gy)), np.tile(gy, len(gx))])

    def descend(self, theta, s, offsets, coarse, iterations=15):
        """Position for one yaw and scale. With a landmark, the tower's axis goes onto its footprint centre and that is
        the position (the landmark pins it; the walls then decide the yaw and the tower top the scale). Otherwise the
        best grid cell for the fragment's centre (precision on all walls), then descent along the named building's
        wall field."""
        R2 = rot_z(theta)[:2, :2]
        if self.landmark is not None:
            return self.landmark['centre'] - s * (R2 @ self.landmark['axis_xy'])
        base = s * (self.pg[coarse, :2] - self.centroid_model) @ R2.T
        pts = (base[None] + offsets[:, None]).reshape(-1, 2)
        precision = np.exp(-(self.walls_all(pts) / KERNEL_M) ** 2).reshape(len(offsets), -1).mean(1)
        txy = offsets[int(np.argmax(precision))] - s * self.centroid_model @ R2.T
        base = s * self.pg[self.sub, :2] @ R2.T
        field, fcell, h = self.walls_named.distance, self.walls_named.cell, 0.5
        for _ in range(iterations):
            p = base + txy
            d = np.minimum(raster_lookup(field, self.box, fcell, p), 10.0)
            gx = (raster_lookup(field, self.box, fcell, p + [h, 0]) - raster_lookup(field, self.box, fcell, p - [h, 0])) / (2 * h)
            gy = (raster_lookup(field, self.box, fcell, p + [0, h]) - raster_lookup(field, self.box, fcell, p - [0, h])) / (2 * h)
            step = np.array([np.mean(d * gx), np.mean(d * gy)])
            if np.linalg.norm(step) < 0.02: break
            txy = txy - step
        return txy


def gravity(points, hint, k=20, planarity=0.15, wall_band_deg=30.0, min_wall_patches=60, span_ratio=0.15):
    """Vertical direction and how it was found. Facade normals are horizontal, so the vertical is the direction most
    orthogonal to them (`align.facade_up`), but only when those normals span two directions; otherwise the camera-up
    hint (made orthogonal to the single facade normal) is used."""
    from scipy.spatial import cKDTree
    hint = hint / np.linalg.norm(hint)
    tree = cKDTree(points); _, nbrs = tree.query(points, k=min(k, len(points)))
    normals = []
    for idx in nbrs:
        q = points[idx] - points[idx].mean(0); w, v = np.linalg.eigh(q.T @ q)
        if w[0] < planarity * w[1]: normals.append(v[:, 0])
    normals = np.asarray(normals) if normals else np.zeros((0, 3))
    walls = normals[np.abs(normals @ hint) < np.sin(np.radians(wall_band_deg))] if len(normals) else normals
    if len(walls) < min_wall_patches:
        return hint, {'from': 'camera up (too few wall-like patches)', 'planar_patches': int(len(normals)), 'wall_patches': int(len(walls))}
    w, v = np.linalg.eigh(walls.T @ walls)   # ascending eigenvalues; v[:, 2] is the dominant facade normal
    if w[1] < span_ratio * w[2]:              # one facade direction only: the vertical is free within its plane
        n = v[:, 2]; up = hint - (hint @ n) * n; up /= np.linalg.norm(up)
        return up, {'from': 'camera up projected orthogonal to the single facade', 'planar_patches': int(len(normals)), 'wall_patches': int(len(walls)),
                    'facade_direction_eigenvalues': w.tolist()}
    up, quality = facade_up(points, hint, k=k, planarity=planarity, wall_band_deg=wall_band_deg)
    quality['from'] = 'wall-like facade normals'; quality['facade_direction_eigenvalues'] = w.tolist()
    return up, quality


def _touches(ring, box, margin=10.0):
    r = np.asarray(ring)
    return r[:, 0].max() >= box[0] - margin and r[:, 0].min() <= box[2] + margin and r[:, 1].max() >= box[1] - margin and r[:, 1].min() <= box[3] + margin


def fit_arrays(points, centres, rotations, building, buildings, rasters, observations=None, landmark=None, cues=None, seed=0,
               yaw_step_deg=3.0, scale_steps=21):
    """Fit from arrays (model units): points, camera centres, cam-from-world rotations, optional (camera, point) observation
    pairs; the named building; all footprints; the lidar rasters. Returns (report, (scale, R, t))."""
    f = Fragment(points, centres, rotations, building, buildings, rasters, observations, landmark, cues, seed)
    yaws = np.radians(np.arange(0, 360, yaw_step_deg))
    offsets = f.position_grid(); coarse = f.sub[:400]

    # Scale prior: the fragment's core spans the facade from foot to top; the named building's roof edges give that height.
    radius = np.linalg.norm(f.pg[:, :2] - f.centroid_model, axis=1); core = radius <= np.percentile(radius, 60)
    model_height = float(np.percentile(f.pg[core, 2], 95) - np.percentile(f.pg[core, 2], 5))
    ok = np.isfinite(f.edges.eave) & np.isfinite(f.edges.ground)
    lidar_height = float(np.average(f.edges.eave[ok] - f.edges.ground[ok], weights=f.edges.length[ok])) if ok.any() else 10.0
    s_prior = lidar_height / max(model_height, 1e-6)
    if f.landmark is not None:  # a tower gives a better prior: its lidar height over the model's cluster height
        s_prior = (f.landmark['lidar_top'] - f.landmark['lidar_ground'] - EYE_M) / max(f.landmark['model_top'] - f.cam_z_model, 1e-6)
    grid = s_prior * np.exp(np.linspace(np.log(0.33), np.log(3.0), scale_steps))

    # Coarse table: every cue's score per (scale, yaw) cell, with the position found per cell.
    tables = {c: np.zeros((len(grid), len(yaws))) for c in f.cues}
    shifts = np.zeros((len(grid), len(yaws), 2))
    for i, s in enumerate(grid):
        for j, th in enumerate(yaws):
            txy = f.descend(th, s, offsets, coarse); shifts[i, j] = txy
            for c, v in f.scores(th, s, txy, f.sub).items(): tables[c][i, j] = v
    total = sum(f.cues[c] * tables[c] for c in f.cues)

    # Joint refinement from the best few cells (distinct scales).
    best, tried = None, []
    for i, j in zip(*np.unravel_index(np.argsort(-total, axis=None), total.shape)):
        if any(abs(np.log(grid[i] / grid[k])) < 0.15 and abs(((yaws[j] - yaws[l]) + np.pi) % (2 * np.pi) - np.pi) < np.radians(15) for k, l in tried): continue
        tried.append((i, j))
        res = nelder_mead(lambda x: -f.objective(x[0], np.exp(x[1]), x[2:4], f.sub_refine)[0], [yaws[j], np.log(grid[i]), *shifts[i, j]],
                          [np.radians(2), 0.03, 1.0, 1.0], 800)
        if best is None or -res.fun > best[0]: best = (-res.fun, res.x)
        if len(tried) == 4: break
    theta, scale, txy = float(best[1][0]), float(np.exp(best[1][1])), best[1][2:4]
    value, at_optimum = f.objective(theta, scale, txy, f.sub_refine)
    R = rot_z(theta) @ f.Rg
    _, cams_xy = f.place(theta, scale, txy, f.sub)
    tz = f.tz(scale, cams_xy)
    sim = (scale, R, np.array([txy[0], txy[1], tz]))
    world_pts, world_cams = apply(sim, points), apply(sim, centres)

    # --- certificate -------------------------------------------------------------------------
    i_best, j_best = int(np.argmin(np.abs(np.log(grid / scale)))), int(np.argmin(np.abs(((yaws - theta) + np.pi) % (2 * np.pi) - np.pi)))
    def profiles(without=()):
        t = sum(f.cues[c] * tables[c] for c in f.cues if c not in without)
        return {'scale': t.max(1), 'yaw': t[i_best]} if t is not None and not np.isscalar(t) else None
    prof_all = profiles()
    scale_prof, yaw_prof = prof_all['scale'], prof_all['yaw']
    # Cues that score the same everywhere (every photographer outside buildings, say) add a constant to every cell, so
    # bands are measured against the profile's dynamic range: inside the band while the objective loses less than a
    # tenth of (best - floor), the floor being the coarse profile's 10th percentile.
    floor_scale, floor_yaw = float(np.percentile(scale_prof, 10)), float(np.percentile(yaw_prof, 10))
    def refined(axis, factors):
        """The objective at fixed scale ratios (or yaw offsets) around the optimum, yaw/position (or scale/position) re-refined."""
        out = []
        for fct in factors:
            if axis == 'scale':
                fun = lambda x, s_=scale * fct: -f.objective(x[0], s_, x[1:3], f.sub_refine)[0]
                res = nelder_mead(fun, [theta, *txy], [np.radians(1.5), 0.7, 0.7], 200)
            else:
                fun = lambda x, th_=theta + np.radians(fct): -f.objective(th_, np.exp(x[0]), x[1:3], f.sub_refine)[0]
                res = nelder_mead(fun, [np.log(scale), *txy], [0.02, 0.7, 0.7], 200)
            out.append(float(-res.fun))
        return np.array(out)
    scale_factors = np.exp(np.linspace(np.log(0.7), np.log(1.4), 13)); scale_curve = refined('scale', scale_factors)
    scale_curve[np.argmin(np.abs(np.log(scale_factors)))] = max(scale_curve[np.argmin(np.abs(np.log(scale_factors)))], value)
    ok = scale_curve >= value - BAND_DROP * (value - floor_scale)
    # the band is the contiguous run of factors around 1 that stay inside
    centre = int(np.argmin(np.abs(np.log(scale_factors)))); lo = hi = centre
    while lo > 0 and ok[lo - 1]: lo -= 1
    while hi < len(ok) - 1 and ok[hi + 1]: hi += 1
    scale_band = (float(scale_factors[lo]), float(scale_factors[hi]))
    yaw_offsets = np.arange(-30, 31, 5.0); yaw_curve = refined('yaw', yaw_offsets)
    okY = yaw_curve >= value - BAND_DROP * (value - floor_yaw); c0 = int(np.argmin(np.abs(yaw_offsets))); lo = hi = c0
    while lo > 0 and okY[lo - 1]: lo -= 1
    while hi < len(okY) - 1 and okY[hi + 1]: hi += 1
    yaw_band_deg = (float(yaw_offsets[lo]), float(yaw_offsets[hi]))
    deg = np.degrees(yaws); dyaw = np.abs(((deg - np.degrees(theta)) + 180) % 360 - 180)
    quadrants = {f'+{q}': float(yaw_prof[np.abs(((deg - (np.degrees(theta) + q) % 360) + 180) % 360 - 180) <= 15].max()) for q in (90, 180, 270)}
    runner = float(yaw_prof[dyaw > 20].max()) if (dyaw > 20).any() else float('nan'); yaw_best = float(max(yaw_prof.max(), value))
    contrast = lambda v: (v - floor_yaw) / max(yaw_best - floor_yaw, 1e-9)   # 1 at the best, 0 at the floor
    yaw_contrasts = {'runner_up_outside_20deg': contrast(runner) if np.isfinite(runner) else None, **{k: contrast(v) for k, v in quadrants.items()}}
    # Position band: how far the fragment slides along x and y before the objective loses a tenth of its range.
    def position_band(axis):
        out = []
        for sign in (-1, 1):
            d = 0.0
            while d < 12.0:
                d += 0.5; shift = txy + sign * d * np.eye(2)[axis]
                if f.objective(theta, scale, shift, f.sub_refine)[0] < value - BAND_DROP * (value - floor_scale): break
            out.append(d)
        return out
    pos_band = {'x_m': position_band(0), 'y_m': position_band(1)}
    # Cue ablation: refine from the optimum without each cue; how far does each degree of freedom move?
    ablation = {}
    for c in f.cues:
        res = nelder_mead(lambda x: -f.objective(x[0], np.exp(x[1]), x[2:4], f.sub_refine, without=(c,))[0], [theta, np.log(scale), *txy], [np.radians(2), 0.03, 1.0, 1.0], 400)
        ablation[c] = {'yaw_shift_deg': float(np.degrees(((res.x[0] - theta) + np.pi) % (2 * np.pi) - np.pi)), 'scale_ratio': float(np.exp(res.x[1]) / scale),
                       'position_shift_m': float(np.linalg.norm(res.x[2:4] - txy))}
    cue_profiles = {'scale_grid_m_per_unit': grid.tolist(), 'all': scale_prof.tolist()}
    for c in f.cues:
        p = profiles(without=(c,)); cue_profiles['without_' + c] = p['scale'].tolist()
    for c in f.cues: cue_profiles['only_' + c] = tables[c].max(1).tolist()
    # Independent-ish diagnostics.
    rows = f.per_wall(theta, scale, txy, np.arange(len(f.pg)))
    per_wall_scales = np.array([r['scale_from_this_wall'] for r in rows if r['scale_from_this_wall']])
    per_wall_spread = float(np.median(np.abs(per_wall_scales - scale)) / scale) if len(per_wall_scales) else None
    walls_only = tables['walls'].max(1) if 'walls' in tables else None
    walls_only_scale = float(grid[int(np.argmax(walls_only))]) if walls_only is not None else None
    walls_only_band = None
    if walls_only is not None:
        w = walls_only >= walls_only.max() - BAND_DROP * abs(walls_only.max()); walls_only_band = (float(grid[w].min() / scale), float(grid[w].max() / scale))
    d_all = f.walls_all(world_pts[:, :2])
    cam_height = world_cams[:, 2] - raster_lookup(f.ground, f.box, f.cell, world_cams[:, :2])
    inside_fraction = float(np.mean(f.inside(world_cams[:, :2])))
    metrics = {
        'points_within_1m_of_walls': float(np.mean(d_all <= 1.0)), 'points_within_2m_of_walls': float(np.mean(d_all <= 2.0)),
        'median_distance_to_walls_m': float(np.median(d_all)),
        'camera_height_above_ground_m': {'median': float(np.median(cam_height)), 'p10': float(np.percentile(cam_height, 10)), 'p90': float(np.percentile(cam_height, 90))},
        'cameras_in_height_band': int(((cam_height >= 0.5) & (cam_height <= 3.0)).sum()), 'cameras': int(len(cam_height)),
        'cameras_inside_buildings': int(round(inside_fraction * len(cam_height))),
        'walls_with_enough_points': len(rows), 'per_wall': rows,
        'yaw': {'best_score': yaw_best, 'floor': floor_yaw, 'other_quadrants': quadrants, 'runner_up_outside_20deg': runner, 'contrast': yaw_contrasts, 'band_deg': yaw_band_deg},
        'scale_band': {'low': scale_band[0], 'high': scale_band[1], 'curve': {f'{fct:.3f}': float(v) for fct, v in zip(scale_factors, scale_curve)}}, 'position_band_m': pos_band,
        'walls_only_scale': {'best_m_per_unit': walls_only_scale, 'band': walls_only_band},
        'cue_scores_at_optimum': at_optimum, 'objective': float(value), 'scale_prior': float(s_prior),
    }
    # --- verdict with a named failure mode -------------------------------------------------------
    reasons = []; failure = None
    # A facade is a wall seen from the ground to its roof edge. A fragment whose points reach no roof edge and hold no
    # landmark (close-ups of an entrance, a lawn) has seen no facade, whatever the walls score says.
    if (at_optimum.get('roof_edges', 0.0) < LIMITS['roof_edge_min'] and f.landmark is None) or metrics['points_within_1m_of_walls'] < LIMITS['walls_fraction_1m']:
        failure = 'no facade seen'; reasons.append(f"the points reach no wall's roof edge (roof-edge score {at_optimum.get('roof_edges', 0.0):.2f}) and {100 * metrics['points_within_1m_of_walls']:.0f} % lie within 1 m of a wall at the best placement; the photographs do not show a facade from the ground to its roof edge")
    elif inside_fraction > LIMITS['cameras_inside']:
        failure = 'cameras inside buildings'; reasons.append(f"{100 * inside_fraction:.0f} % of the photographers would stand inside a building")
    elif not (scale_band[0] >= 1 - LIMITS['scale_band'] and scale_band[1] <= 1 + LIMITS['scale_band']):
        failure = 'scale undetermined'; reasons.append(f"the objective keeps nine tenths of its range for scales between {scale_band[0]:.2f} and {scale_band[1]:.2f} of the fitted one")
    elif walls_only_band and walls_only_band[1] / walls_only_band[0] <= 1.3 and abs(walls_only_scale / scale - 1) > LIMITS['scale_disagreement']:
        failure = 'scale undetermined'; reasons.append(f"the walls alone prefer a scale {walls_only_scale / scale:.2f} times the fitted one")
    elif len(rows) < 2 and f.landmark is None and (per_wall_spread is None or True):
        failure = 'scale undetermined'; reasons.append('the scale rests on the roof edge of a single wall and no landmark')
    elif per_wall_spread is not None and per_wall_spread > LIMITS['per_wall_spread'] and f.landmark is None:
        failure = 'scale undetermined'; reasons.append(f'the roof-edge scales of the walls disagree by {100 * per_wall_spread:.0f} %')
    elif any(v is not None and v >= LIMITS['yaw_contrast'] for v in yaw_contrasts.values()):
        failure = 'yaw ambiguous'; reasons.append('another yaw reaches %.0f %% of the best score above the floor' % (100 * max(v for v in yaw_contrasts.values() if v is not None)))
    elif yaw_band_deg[1] - yaw_band_deg[0] > 2 * LIMITS['yaw_band_deg']:
        failure = 'yaw ambiguous'; reasons.append('the yaw band spans %.0f degrees' % (yaw_band_deg[1] - yaw_band_deg[0]))
    elif max(max(pos_band['x_m']), max(pos_band['y_m'])) > LIMITS['position_band_m']:
        failure = 'position undetermined'; reasons.append(f"the fragment slides {max(max(pos_band['x_m']), max(pos_band['y_m'])):.1f} m before the objective drops 5 %")
    usable = failure is None
    fixed_by = []
    if usable:
        if f.landmark is not None and at_optimum.get('landmark', 0) > 0.5: fixed_by.append(f"the {f.landmark['name']} landmark top")
        if len(rows) >= 2: fixed_by.append(f'the roof edges of {len(rows)} walls')
        if walls_only_band and walls_only_band[1] / walls_only_band[0] <= 1.3: fixed_by.append('the walls alone (parallel walls in view)')
    s_, R_, t_ = sim
    report = {
        'method': 'cue-based similarity from public lidar and OpenStreetMap footprints: walls (precision and recall), roof edges, camera height, '
                  + ('a landmark, ' if f.landmark else '') + ('free space, ' if 'free_space' in f.cues else '') + 'cameras outside buildings; coarse scale-yaw table with per-cell positions, joint refinement, certificate from the stored table',
        'building': building, 'landmark_building': f.landmark['name'] if f.landmark else building, 'neighbour_building': None,
        'cues': {c: {'weight': f.cues[c], 'score_at_optimum': at_optimum[c]} for c in f.cues},
        'similarity': {'scale_m_per_model_unit': float(s_), 'rotation': R_.tolist(), 'translation_utm18n': t_.tolist()},
        'gravity': {'model_up': f.up.tolist(), **f.gravity_quality},
        'metrics': metrics,
        'certificate': {'verdict': 'usable' if usable else 'not usable', 'failure_mode': failure, 'reasons': reasons, 'scale_fixed_by': fixed_by,
                        'scale_band': scale_band, 'yaw': metrics['yaw'], 'position_band_m': pos_band, 'cue_ablation': ablation,
                        'profiles': cue_profiles, 'per_wall_relative_spread': per_wall_spread, 'walls_only_scale': metrics['walls_only_scale'], 'limits': LIMITS},
        'uncertainty': {'scale_band': scale_band, 'per_wall_relative_spread': per_wall_spread,
                        'independent_scale_disagreement': abs(walls_only_scale / scale - 1) if walls_only_scale else None},
        'gate': {'usable': usable}, 'passed': usable, 'metric_frame_usable': usable,
        'camera_heights_m': {str(i): float(h) for i, h in enumerate(cam_height)},
    }
    return report, sim


def building_for(model, run_path):
    """The fragment's named building: the footprint of the acquisition target most of its photographs carry."""
    from collections import Counter
    report = json.loads((Path(run_path) / 'report.json').read_text())
    snapshot = json.loads(Path(report['snapshot_path']).read_text())
    targets = {r['filename']: (r.get('discovery') or {}).get('targets', []) for r in snapshot['images']}
    config = json.loads(CONFIG.read_text()); footprint = {t['id']: t.get('footprint') for t in config['targets']}
    votes = Counter(footprint[t] for im in model.images.values() for t in targets.get(im.name, []) if footprint.get(t))
    return votes.most_common(1)[0][0] if votes else None


def observations_of(model):
    """(camera index, point index) pairs in the order of sorted image names and point ids."""
    images = sorted(model.images.values(), key=lambda im: im.name); cam_index = {im.image_id: i for i, im in enumerate(images)}
    pids = list(model.points3D.keys()); pt_index = {pid: i for i, pid in enumerate(pids)}
    pairs = [(cam_index[el.image_id], pt_index[pid]) for pid in pids for el in model.points3D[pid].track.elements if el.image_id in cam_index]
    return np.array(pairs, dtype=np.int64) if pairs else None


def fit(model, building, landmark=None, cues=None, footprints=FOOTPRINTS, seed=0):
    buildings = json.loads(Path(footprints).read_text())['buildings']
    ring = next(b for b in buildings if b['name'] == building)['ring']
    crop_name, crop, rasters = crop_for(ring)
    images = sorted(model.images.values(), key=lambda im: im.name)
    rotations = [im.cam_from_world().rotation.matrix() for im in images]
    centres = np.array([im.projection_center() for im in images])
    points = np.array([p.xyz for p in model.points3D.values()])
    report, sim = fit_arrays(points, centres, rotations, building, buildings, rasters, observations_of(model), landmark, cues, seed)
    report['camera_heights_m'] = {im.name: report['camera_heights_m'][str(i)] for i, im in enumerate(images)}
    report['lidar_crop'] = crop_name
    return report, sim, crop


def run(run_path, component, building=None, landmark=None, cues=None, output=None):
    import pycolmap
    run_path = Path(run_path).resolve()
    report = json.loads((run_path / 'report.json').read_text())
    if report.get('status') != 'sfm_complete': raise ValueError('A completed sparse run is required')
    comp = next(c for c in report['components'] if str(c['id']) == str(component))
    model = pycolmap.Reconstruction(str(run_path / comp['model_path']))
    building = building or building_for(model, run_path)
    if building is None: raise ValueError('no building named for this fragment (no target photographs); pass --building')
    result, (s, R, t), crop = fit(model, building, landmark, cues)
    out = Path(output) if output else run_path / 'anchor' / str(component); out.mkdir(parents=True, exist_ok=True)
    lidar_report = json.loads((crop / 'report.json').read_text())
    anchored = pycolmap.Reconstruction(str(run_path / comp['model_path']))
    origin = np.asarray(lidar_report['box_utm'][:2] + [0.0])
    anchored.transform(pycolmap.Sim3d(s, pycolmap.Rotation3d(R), t - origin))
    (out / 'model-local-metres').mkdir(exist_ok=True); anchored.write(str(out / 'model-local-metres'))
    cert = result['certificate']
    status = (f"lidar-anchored; scale fixed by {', '.join(cert['scale_fixed_by']) or 'the cues jointly'}" if result['metric_frame_usable']
              else f"anchoring attempted; frame not usable ({cert['failure_mode']}: {cert['reasons'][0] if cert['reasons'] else ''})")
    result.update({'schema_version': 2, 'created_utc': datetime.now(timezone.utc).isoformat(), 'run_id': report['run_id'],
                   'component_id': str(component), 'model_path': comp['model_path'], 'pycolmap_version': pycolmap.__version__,
                   'lidar_report': str(crop / 'report.json'), 'footprints': str(FOOTPRINTS),
                   'local_frame': {'crs': 'EPSG:32618', 'origin_utm18n': origin.tolist(), 'meaning': 'local = UTM 18N coordinates minus origin, metres, z up'},
                   'anchored_model': str(out / 'model-local-metres'), 'metric_units': bool(result['metric_frame_usable']), 'scale_status': status,
                   'inputs_used': 'model 3D points, camera centres and orientations, camera-point observations; OpenStreetMap footprints; lidar surface and ground; no geotags, no manual correspondences',
                   'checks_not_used_by_the_fit': 'held-out geotags and cross-fragment agreement (evaluate/georegistration.py); the walls-only scale and the per-wall spread are read from the stored cue tables'})
    (out / 'report.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def run_all(run_path, min_cameras=8, landmark=None, cues=None):
    """Anchor every fragment of a run that has enough cameras and a named building; failures of a fragment are recorded, not fatal."""
    import pycolmap
    run_path = Path(run_path).resolve(); report = json.loads((run_path / 'report.json').read_text()); done = {}
    for comp in report['components']:
        if comp['registered_cameras'] < min_cameras: continue
        model = pycolmap.Reconstruction(str(run_path / comp['model_path'])); building = building_for(model, run_path)
        if building is None: done[str(comp['id'])] = {'skipped': 'no building named by its photographs'}; continue
        try:
            result = run(run_path, comp['id'], building, landmark, cues)
            done[str(comp['id'])] = {'building': building, 'cameras': comp['registered_cameras'], 'verdict': result['certificate']['verdict'],
                                     'failure_mode': result['certificate']['failure_mode'], 'scale_status': result['scale_status']}
        except Exception as error:  # a fragment that breaks the estimator is a finding, kept with the others
            done[str(comp['id'])] = {'building': building, 'cameras': comp['registered_cameras'], 'error': f'{type(error).__name__}: {error}'}
        print(json.dumps({comp['id']: done[str(comp['id'])]}), flush=True)
    (run_path / 'anchor' / 'summary.json').write_text(json.dumps({'created_utc': datetime.now(timezone.utc).isoformat(), 'min_cameras': min_cameras, 'fragments': done}, indent=2) + '\n')
    return done


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--component', help='fragment id; or --all')
    parser.add_argument('--all', action='store_true', help='every fragment with at least --min-cameras cameras and a named building')
    parser.add_argument('--min-cameras', type=int, default=8)
    parser.add_argument('--building', help='footprint name; default: the target most of the fragment\'s photographs carry')
    parser.add_argument('--landmark', help='footprint name of a tower to use as the landmark; default: the tallest one in the box')
    parser.add_argument('--without', default='', help='comma-separated cues to leave out, e.g. free_space,landmark')
    parser.add_argument('--output', type=Path, help='report directory (default: <run>/anchor/<component>)')
    args = parser.parse_args()
    cues = [c for c in WEIGHTS if c not in set(filter(None, args.without.split(',')))]
    if args.all:
        run_all(args.run, args.min_cameras, args.landmark, cues); return
    if not args.component: parser.error('--component or --all')
    result = run(args.run, args.component, args.building, args.landmark, cues, args.output)
    shown = {k: result[k] for k in ('building', 'similarity', 'scale_status', 'metric_frame_usable')}
    shown['certificate'] = {k: v for k, v in result['certificate'].items() if k not in ('profiles', 'limits')}
    shown['metrics'] = {k: v for k, v in result['metrics'].items() if k != 'per_wall'}
    print(json.dumps(shown, indent=2))


if __name__ == '__main__': main()
