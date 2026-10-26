#!/usr/bin/env python3
"""A clean city model from public lidar and OpenStreetMap footprints, for the GhostMap page.

The page used to draw the lidar's first-return surface as one sheet, so every building wall became a smeared
slope. Here each footprint becomes a building, still from measurement only:

- walls: vertical, along the footprint outline, from the lidar bare ground just outside up to the lidar roof
  just inside, sampled every metre (gables and parapets follow the lidar);
- roof: the lidar surface inside the footprint (0.5 m cells, 1 m for large buildings; a 3 x 3 median against
  single stray returns), extended half a metre past the walls like eaves, and draped with the year's aerial
  image by the page; within 1.5 m of the outline the highest surface within a metre is used, so the eaves
  do not sag where the footprint and the lidar disagree;
- trees: one per maximum of the lidar canopy height (surface minus bare ground, 2.5 to 40 m) outside every
  footprint, at least 4 m apart; its crown is the canopy that drains to that maximum (a watershed), drawn
  by the page as a crown of the same area on a trunk;
- ground: the bare-earth raster (the terrain the page drapes with the aerial images).

Buildings whose visibility changes on the page (those the documented dates add or remove, and those a
reconstruction covers) are kept as separate index ranges; everything else is merged.

Outputs per site under `<scene>/city/`: `<site>-xyz.f32` (vertex positions, scene local metres),
`<site>-shade.u8` (one shade per vertex: walls darker towards the ground), `<site>-roof.u32` and
`<site>-wall.u32` (triangle indices), `<site>-trees.f32` (x, y, ground, top, crown radius per tree) and
`<site>-trees.u8` (a colour per tree); and a dictionary for scene.json
with the index ranges.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ghostmap.paths import ROOT

ROOF_CELL_SMALL, ROOF_CELL_LARGE, LARGE_AREA_M2 = 0.5, 1.0, 1500.0
EAVE_M = 0.5
EDGE_REACH_M, EDGE_BAND_M = 1.0, 1.5   # roof vertices this close to the outline take the edge surface
WALL_STEP_M = 1.0
TREE_MIN_M, TREE_MAX_M, TREE_SPACING_M = 2.5, 40.0, 4.0


def _site_rasters(lidar_dir):
    from ghostmap.anchor.lidar import fill_nearest
    from scipy.ndimage import maximum_filter, median_filter
    r = np.load(Path(lidar_dir) / 'quad-rasters-utm18n.npz')
    dsm = median_filter(fill_nearest(r['surface']), size=3)
    # Near the outline the footprint and the lidar disagree by up to a metre, so the plain surface would sag to
    # the ground at the eaves; the edge uses the highest surface within EDGE_REACH_M instead.
    reach = max(1, int(round(EDGE_REACH_M / float(r['cell']))))
    return {'box': tuple(float(v) for v in r['box']), 'cell': float(r['cell']), 'dsm': dsm, 'dsm_edge': maximum_filter(dsm, size=2 * reach + 1),
            'dsm_raw': fill_nearest(r['surface']), 'dtm': fill_nearest(r['ground'])}


def _lookup(raster, box, cell, e, n):
    rows, cols = raster.shape
    r = np.clip(((box[3] - n) / cell).astype(int), 0, rows - 1); c = np.clip(((e - box[0]) / cell).astype(int), 0, cols - 1)
    return raster[r, c]


def building_mesh(ring, R, origin):
    """Vertices (n, 3) in scene local metres, a shade per vertex, roof and wall triangles, for one footprint."""
    from matplotlib.path import Path as MPath
    from shapely.geometry import Polygon
    ring = np.asarray(ring, float)
    if not np.allclose(ring[0], ring[-1]): ring = np.vstack([ring, ring[:1]])
    poly = Polygon(ring)
    if not poly.is_valid: poly = poly.buffer(0)
    if poly.is_empty or poly.area < 4: return None
    box, cell = R['box'], R['cell']
    step = ROOF_CELL_SMALL if poly.area < LARGE_AREA_M2 else ROOF_CELL_LARGE
    ground = float(np.median(_lookup(R['dtm'], box, cell, ring[:, 0], ring[:, 1])))
    # roof grid: cell centres inside the footprint grown by the eave
    grown = poly.buffer(EAVE_M)
    gx = np.arange(grown.bounds[0], grown.bounds[2] + step, step); gy = np.arange(grown.bounds[1], grown.bounds[3] + step, step)
    E, N = np.meshgrid(gx, gy)
    outline = grown.exterior if grown.geom_type == 'Polygon' else max(grown.geoms, key=lambda g: g.area).exterior
    inside = MPath(np.asarray(outline.coords)).contains_points(np.column_stack([E.ravel(), N.ravel()])).reshape(E.shape)
    Z = _lookup(R['dsm'], box, cell, E.ravel(), N.ravel()).reshape(E.shape)
    from shapely import distance, points
    near_edge = (distance(poly.exterior, points(E.ravel(), N.ravel())) < EDGE_BAND_M).reshape(E.shape) | ~MPath(ring).contains_points(np.column_stack([E.ravel(), N.ravel()])).reshape(E.shape)
    Z = np.where(near_edge, _lookup(R['dsm_edge'], box, cell, E.ravel(), N.ravel()).reshape(E.shape), Z)
    Z = np.maximum(Z, ground + 2.0)   # a roof never drops to the ground inside a footprint
    verts, shade, roof, wall = [], [], [], []
    index = -np.ones(E.shape, int)
    for (i, j) in zip(*np.nonzero(inside)):
        index[i, j] = len(verts); verts.append((E[i, j], N[i, j], Z[i, j])); shade.append(255)
    for i in range(E.shape[0] - 1):
        for j in range(E.shape[1] - 1):
            a, b, c, d = index[i, j], index[i, j + 1], index[i + 1, j], index[i + 1, j + 1]
            if min(a, b, c, d) < 0: continue
            roof += [a, b, d, a, d, c]   # y grows with i: counter-clockwise seen from above
    # walls: outward normal from the footprint's orientation; top from the roof grid just inside, bottom from the ground outside
    ccw = Polygon(ring).exterior.is_ccw
    for p, q in zip(ring[:-1], ring[1:]):
        L = float(np.linalg.norm(q - p))
        if L < 0.2: continue
        u = (q - p) / L; inward = np.array([-u[1], u[0]]) * (1 if ccw else -1)
        ts = np.linspace(0, L, max(2, int(np.ceil(L / WALL_STEP_M)) + 1))
        P = p + ts[:, None] * u
        top = np.maximum(_lookup(R['dsm_edge'], box, cell, *(P + 0.7 * inward).T), ground + 2.0)   # the same edge surface as the eaves
        bottom = np.minimum(_lookup(R['dtm'], box, cell, *(P - 0.7 * inward).T), top - 0.5)
        base = len(verts)
        for k in range(len(P)):
            verts.append((P[k, 0], P[k, 1], bottom[k])); shade.append(150)
            verts.append((P[k, 0], P[k, 1], top[k])); shade.append(235)
        for k in range(len(P) - 1):
            b0, t0, b1, t1 = base + 2 * k, base + 2 * k + 1, base + 2 * k + 2, base + 2 * k + 3
            wall += [b0, b1, t1, b0, t1, t0] if ccw else [b0, t1, b1, b0, t0, t1]
    if not verts: return None
    V = np.asarray(verts, np.float64); V[:, 0] -= origin[0]; V[:, 1] -= origin[1]; V[:, 2] -= origin[2]
    return {'xyz': V.astype(np.float32), 'shade': np.asarray(shade, np.uint8), 'roof': np.asarray(roof, np.uint32),
            'wall': np.asarray(wall, np.uint32), 'ground': ground - origin[2], 'top': float(Z[inside].max() - origin[2]) if inside.any() else ground + 3}


def trees(R, rings, origin, seed=0):
    """Tree crowns from the lidar canopy outside every footprint: one tree per canopy-height maximum.

    Canopy height = first-return surface minus bare ground, 2.5 to 40 m, outside every footprint grown by
    1.5 m (walls and eaves are not trees). Tree tops are local maxima at least TREE_SPACING_M apart; each
    canopy cell joins the top it drains to (watershed), and the crown's radius is that of a disc of the same
    area. Returns per tree (x, y, ground, top, crown radius) in scene local metres and a colour.
    """
    from ghostmap.anchor.align import InsideMask
    from scipy.ndimage import binary_dilation, gaussian_filter, label, maximum_filter, sum_labels, watershed_ift
    cell = R['cell']
    chm = gaussian_filter(R['dsm_raw'] - R['dtm'], 0.8)
    built = binary_dilation(InsideMask(rings, R['box'], cell).mask, iterations=int(round(1.5 / cell)))
    canopy = (chm > TREE_MIN_M) & (chm < TREE_MAX_M) & ~built
    window = int(round(TREE_SPACING_M / cell)) | 1
    tops = canopy & (chm == maximum_filter(np.where(canopy, chm, 0), size=window)) & (chm > TREE_MIN_M + 1.0)
    markers, n = label(tops)
    if n == 0: return np.zeros((0, 5), np.float32), np.zeros((0, 3), np.uint8)
    markers = markers.astype(np.int32); markers[~canopy & (markers == 0)] = n + 1   # everything that is not canopy drains to one background basin
    levels = np.clip((TREE_MAX_M - np.clip(chm, 0, TREE_MAX_M)) / TREE_MAX_M * 65000, 0, 65000).astype(np.uint16)
    crowns = watershed_ift(levels, markers)
    crowns[~canopy] = 0
    ids = np.arange(1, n + 1)
    area = sum_labels(np.ones_like(chm), crowns, ids) * cell * cell
    rows, cols = np.nonzero(tops); top_id = markers[rows, cols]
    first = np.unique(top_id, return_index=True)[1]; rows, cols = rows[first], cols[first]   # one cell per marker
    x = R['box'][0] + (cols + 0.5) * cell; y = R['box'][3] - (rows + 0.5) * cell
    ground, height = R['dtm'][rows, cols], chm[rows, cols]
    radius = np.clip(np.sqrt(area / np.pi), 1.2, 0.45 * height + 2.0)
    keep = area >= 3.0
    out = np.column_stack([x - origin[0], y - origin[1], ground - origin[2], ground + height - origin[2], radius])[keep]
    rng = np.random.default_rng(seed)
    t = np.clip(height[keep] / 25.0, 0, 1)[:, None]
    rgb = (1 - t) * np.array([92, 124, 58]) + t * np.array([58, 92, 44]) + rng.normal(0, 10, (len(out), 3))
    return out.astype(np.float32), np.clip(rgb, 0, 255).astype(np.uint8)


def build_site(site, lidar_dir, buildings, origin, out, special=()):
    """Write one site's city model; `buildings` are (name, ring) pairs already assigned to this site."""
    R = _site_rasters(lidar_dir)
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    xyz, shade, roof_all, wall_all, groups = [], [], [], [], {}
    base = 0
    static_roof, static_wall = [], []
    for name, ring in buildings:
        m = building_mesh(ring, R, origin)
        if m is None: continue
        xyz.append(m['xyz']); shade.append(m['shade'])
        roof, wall = m['roof'] + base, m['wall'] + base
        if name in special:
            groups[name] = {'roof': [len(roof_all), len(roof)], 'wall': [len(wall_all), len(wall)], 'ground': m['ground'], 'top': m['top']}
            roof_all += roof.tolist(); wall_all += wall.tolist()
        else:
            static_roof.append(roof); static_wall.append(wall)
        base += len(m['xyz'])
    # static buildings first in each index buffer, then the special ones (their ranges shifted accordingly)
    sr = np.concatenate(static_roof) if static_roof else np.zeros(0, np.uint32); sw = np.concatenate(static_wall) if static_wall else np.zeros(0, np.uint32)
    for g in groups.values(): g['roof'][0] += len(sr); g['wall'][0] += len(sw)
    roof_idx = np.concatenate([sr, np.asarray(roof_all, np.uint32)]); wall_idx = np.concatenate([sw, np.asarray(wall_all, np.uint32)])
    V = np.concatenate(xyz) if xyz else np.zeros((0, 3), np.float32); S = np.concatenate(shade) if shade else np.zeros(0, np.uint8)
    V.astype(np.float32).tofile(out / f'{site}-xyz.f32'); S.tofile(out / f'{site}-shade.u8')
    roof_idx.astype(np.uint32).tofile(out / f'{site}-roof.u32'); wall_idx.astype(np.uint32).tofile(out / f'{site}-wall.u32')
    T, C = trees(R, [r for _, r in buildings], origin)
    T.tofile(out / f'{site}-trees.f32'); C.tofile(out / f'{site}-trees.u8')
    return {'xyz_url': f'city/{site}-xyz.f32', 'shade_url': f'city/{site}-shade.u8', 'roof_url': f'city/{site}-roof.u32', 'wall_url': f'city/{site}-wall.u32',
            'trees_url': f'city/{site}-trees.f32', 'trees_rgb_url': f'city/{site}-trees.u8',
            'static': {'roof': [0, int(len(sr))], 'wall': [0, int(len(sw))]}, 'special': groups,
            'vertices': int(len(V)), 'triangles': int((len(roof_idx) + len(wall_idx)) // 3), 'trees': int(len(T)),
            'rule': 'walls from the lidar bare ground to the lidar roof along OpenStreetMap footprints; roofs the lidar surface inside them; one tree per lidar canopy-height maximum outside them, its crown the canopy that drains to it'}
