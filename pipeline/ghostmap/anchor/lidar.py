#!/usr/bin/env python3
"""Public-domain USGS 3DEP airborne lidar around the Arts Quad, in metres.

Reads the Entwine Point Tile (EPT) octree of the NY_FingerLakes_1_2020
collection, downloads only the nodes that intersect a box around the Quad,
reprojects from Web Mercator (EPSG:3857, which stretches horizontal distances
by about 1.35x at this latitude) to UTM zone 18N (EPSG:32618), and rasterizes a
surface model (highest return) and a ground model (ground-class returns).
Every downloaded node is recorded with its byte count and SHA-256.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from ghostmap.paths import ROOT

EPT = 'https://s3-us-west-2.amazonaws.com/usgs-lidar-public/NY_FingerLakes_1_2020'
AGENT = 'GhostMap-Research/0.3 (Cornell Arts Quad; public academic lidar use)'
UTM = 'EPSG:32618'
# The south end of the Quad (Uris Library, McGraw Tower, Olin Library) and
# the lawn to the north, with margin for the surrounding halls.
QUAD_CENTRE_LATLON = (42.4483, -76.4842)
HALF_SIZE_M = 320.0
GROUND_CLASS = 2
NOISE_CLASSES = (7, 18)


def fetch(url, path, attempts=5):
    """Download once; return (bytes, sha256) of the cached file."""
    path = Path(path)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        part = path.with_suffix(path.suffix + '.part')
        for attempt in range(attempts):
            try:
                request = urllib.request.Request(url, headers={'User-Agent': AGENT})
                with urllib.request.urlopen(request, timeout=60) as response, part.open('wb') as out:
                    for chunk in iter(lambda: response.read(1 << 20), b''): out.write(chunk)
                part.replace(path)
                break
            except OSError:
                if attempt == attempts - 1: raise
                time.sleep(2 ** attempt)
    data = path.read_bytes()
    return len(data), hashlib.sha256(data).hexdigest()


def node_bounds(key, root_bounds):
    """Axis-aligned bounds of octree node 'D-X-Y-Z' inside the root cube."""
    depth, x, y, z = map(int, key.split('-'))
    lo, hi = np.asarray(root_bounds[:3], float), np.asarray(root_bounds[3:], float)
    size = (hi - lo) / 2 ** depth
    start = lo + size * np.array([x, y, z])
    return start, start + size


def intersects_xy(bounds, box):
    (lo, hi), (bx0, by0, bx1, by1) = bounds, box
    return lo[0] < bx1 and hi[0] > bx0 and lo[1] < by1 and hi[1] > by0


def select_nodes(hierarchy_loader, root_bounds, box):
    """Every non-empty node whose XY footprint meets the box, at all depths.

    EPT stores a level-of-detail subsample at each depth, so the full-density
    point set over a region is the union of the intersecting nodes of every depth.
    """
    selected, pending, known = [], ['0-0-0-0'], dict(hierarchy_loader('0-0-0-0'))
    while pending:
        key = pending.pop()
        count = known.get(key)
        if count is None: continue
        if count == -1:
            known.update(hierarchy_loader(key)); count = known[key]
        if count <= 0 or not intersects_xy(node_bounds(key, root_bounds), box): continue
        selected.append(key)
        d, x, y, z = map(int, key.split('-'))
        pending.extend(f'{d + 1}-{2 * x + i}-{2 * y + j}-{2 * z + k}' for i in (0, 1) for j in (0, 1) for k in (0, 1))
    return sorted(selected, key=lambda k: tuple(map(int, k.split('-'))))


def utm_box(centre_latlon=QUAD_CENTRE_LATLON, half=HALF_SIZE_M):
    from pyproj import Transformer
    to_utm = Transformer.from_crs('EPSG:4326', UTM, always_xy=True)
    e, n = to_utm.transform(centre_latlon[1], centre_latlon[0])
    return (e - half, n - half, e + half, n + half)


def mercator_box(box_utm):
    """Web Mercator bounding box of a UTM box (all four corners)."""
    from pyproj import Transformer
    to_merc = Transformer.from_crs(UTM, 'EPSG:3857', always_xy=True)
    xs, ys = to_merc.transform([box_utm[0], box_utm[2], box_utm[0], box_utm[2]], [box_utm[1], box_utm[1], box_utm[3], box_utm[3]])
    return (min(xs), min(ys), max(xs), max(ys))


def rasterize(e, n, z, box, cell, reducer):
    cols = int(np.ceil((box[2] - box[0]) / cell)); rows = int(np.ceil((box[3] - box[1]) / cell))
    c = np.clip(((e - box[0]) / cell).astype(int), 0, cols - 1)
    r = np.clip(((box[3] - n) / cell).astype(int), 0, rows - 1)
    flat = r * cols + c
    grid = np.full(rows * cols, np.nan)
    order = np.argsort(z) if reducer == 'max' else np.argsort(-z)
    grid[flat[order]] = z[order]  # later writes win: max (or min) per cell
    return grid.reshape(rows, cols)


def fill_nearest(grid, max_passes=64):
    """Fill empty ground cells from their neighbours (iterative mean)."""
    out = grid.copy()
    for _ in range(max_passes):
        missing = np.isnan(out)
        if not missing.any(): break
        padded = np.pad(out, 1, constant_values=np.nan)
        stack = np.stack([padded[1 + di:1 + di + out.shape[0], 1 + dj:1 + dj + out.shape[1]]
                          for di in (-1, 0, 1) for dj in (-1, 0, 1) if di or dj])
        with np.errstate(all='ignore'): means = np.nanmean(stack, axis=0)
        out[missing] = means[missing]
    return out


def build(output=ROOT / 'data/lidar/NY_FingerLakes_1_2020', cell=0.5):
    import laspy
    from pyproj import Transformer

    output = Path(output)
    ept_size, ept_sha = fetch(EPT + '/ept.json', output / 'ept.json')
    ept = json.loads((output / 'ept.json').read_text())
    if ept['srs'].get('horizontal') != '3857': raise ValueError('Unexpected EPT horizontal reference system')
    box_utm = utm_box(); box_merc = mercator_box(box_utm)
    hierarchy_files = {}

    def load_hierarchy(key):
        size, digest = fetch(f'{EPT}/ept-hierarchy/{key}.json', output / 'ept-hierarchy' / f'{key}.json')
        hierarchy_files[key] = {'bytes': size, 'sha256': digest}
        return json.loads((output / 'ept-hierarchy' / f'{key}.json').read_text())

    nodes = select_nodes(load_hierarchy, ept['bounds'], box_merc)
    to_utm = Transformer.from_crs('EPSG:3857', UTM, always_xy=True)
    parts, records = [], []
    for key in nodes:
        size, digest = fetch(f'{EPT}/ept-data/{key}.laz', output / 'ept-data' / f'{key}.laz')
        las = laspy.read(output / 'ept-data' / f'{key}.laz')
        x, y = np.asarray(las.x), np.asarray(las.y)
        keep = (x >= box_merc[0]) & (x <= box_merc[2]) & (y >= box_merc[1]) & (y <= box_merc[3])
        records.append({'node': key, 'bytes': size, 'sha256': digest, 'points': int(len(x)), 'points_in_box': int(keep.sum())})
        if keep.any():
            e, n = to_utm.transform(x[keep], y[keep])
            parts.append(np.column_stack([e, n, np.asarray(las.z)[keep], np.asarray(las.classification)[keep],
                                          np.asarray(las.return_number)[keep], np.asarray(las.number_of_returns)[keep]]))
        print('node', key, int(keep.sum()), 'points in box', flush=True)
    points = np.concatenate(parts)
    inside = (points[:, 0] >= box_utm[0]) & (points[:, 0] <= box_utm[2]) & (points[:, 1] >= box_utm[1]) & (points[:, 1] <= box_utm[3])
    points = points[inside & ~np.isin(points[:, 3], NOISE_CLASSES)]
    e, n, z, cls = points[:, 0], points[:, 1], points[:, 2], points[:, 3].astype(int)
    surface = rasterize(e, n, z, box_utm, cell, 'max')
    ground_mask = cls == GROUND_CLASS
    ground = fill_nearest(rasterize(e[ground_mask], n[ground_mask], z[ground_mask], box_utm, cell, 'min'))
    origin = np.array([box_utm[0], box_utm[1], 0.0])
    np.savez_compressed(output / 'quad-points-utm18n.npz', origin=origin,
                        xyz=(points[:, :3] - origin).astype(np.float32), classification=cls.astype(np.uint8),
                        return_number=points[:, 4].astype(np.uint8), number_of_returns=points[:, 5].astype(np.uint8))
    np.savez_compressed(output / 'quad-rasters-utm18n.npz', box=np.asarray(box_utm), cell=cell, surface=surface, ground=ground)
    classes = {int(c): int((cls == c).sum()) for c in np.unique(cls)}
    report = {'schema_version': 1, 'created_utc': datetime.now(timezone.utc).isoformat(),
              'source': EPT, 'license': 'USGS 3DEP lidar: public domain (U.S. Government work)',
              'ept_json': {'bytes': ept_size, 'sha256': ept_sha}, 'hierarchy_files': hierarchy_files, 'nodes': records,
              'source_crs': 'EPSG:3857', 'output_crs': UTM, 'vertical': 'as delivered by 3DEP (metres)',
              'box_utm': list(box_utm), 'box_web_mercator': list(box_merc), 'centre_latlon': list(QUAD_CENTRE_LATLON),
              'raster_cell_m': cell, 'raster_shape': list(surface.shape), 'points_kept': int(len(points)),
              'class_counts': classes, 'ground_cells_measured_fraction': float(np.isfinite(rasterize(e[ground_mask], n[ground_mask], z[ground_mask], box_utm, cell, 'min')).mean()),
              'note': 'Surface = highest non-noise return per cell; ground = lowest ground-class return, gaps filled from neighbours.'}
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'data/lidar/NY_FingerLakes_1_2020')
    parser.add_argument('--cell', type=float, default=0.5)
    args = parser.parse_args()
    report = build(args.output, args.cell)
    print(json.dumps({k: report[k] for k in ('points_kept', 'class_counts', 'raster_shape')}, indent=2))


if __name__ == '__main__': main()
