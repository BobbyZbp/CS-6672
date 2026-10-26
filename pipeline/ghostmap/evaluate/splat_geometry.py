#!/usr/bin/env python3
"""Score a Gaussian splat's geometry against the public lidar, building by building.

The splat lives in the anchor's local metres (UTM 18N minus the lidar crop origin), the same frame as
the lidar points of that crop, so no transform is needed: every Gaussian with enough opacity is
measured by the distance from its centre to the nearest lidar point (airborne lidar sees roofs and
ground densely and walls thinly, so wall Gaussians are judged against the nearest roof-edge or wall
return, a conservative score). Per building (OpenStreetMap footprint, 3 m buffer) and overall:
median and 90th-percentile distance, the share within 0.5, 1 and 2 m. Free space is judged with the
lidar surface and ground rasters: inside the measured volume (the crop's horizontal box, up to 120 m
above its ground) a Gaussian more than 2 m above the highest lidar surface within 2.5 m sits in air the lidar
saw empty, and one more than 1 m under the lowest bare ground within 2.5 m is buried; both are floaters the lidar proves, the classic
failure of in-the-wild reconstructions. Gaussians outside the measured volume (sky, distant background)
are counted as far field and not judged. Coverage says how much of the lidar building the splat
reaches: the share of lidar points above the building's ground that have a Gaussian within 1 m.

Outputs: `<splat dir>/geometry.json`, and a distance-coloured copy of the Gaussian centres
(`geometry-xyz.f32`, `geometry-rgb.u8`: green on lidar surfaces to yellow 3 m off them, red in free air,
purple buried) for the viewer.

Usage: PYTHONPATH=pipeline python -m ghostmap.evaluate.splat_geometry --splat <run>/splats/<name> [--lidar <crop>]
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
MIN_OPACITY = 0.3
FLOATER_M = 5.0
BUFFER_M = 3.0


def load_gaussians(splat_dir):
    import torch
    ckpt = torch.load(Path(splat_dir) / 'ckpt.pt', map_location='cpu')
    means = ckpt['means'].numpy().astype(np.float64)
    opacity = torch.sigmoid(ckpt['opacities']).numpy()
    scales = np.exp(ckpt['scales'].numpy())
    rgb = np.clip(ckpt['sh0'][:, 0, :].numpy() * 0.28209479177387814 + 0.5, 0, 1)
    return means, opacity, scales, rgb


def summarize(d):
    return {'n': int(len(d)), 'median_m': float(np.median(d)), 'p90_m': float(np.percentile(d, 90)),
            'within_0_5m': float(np.mean(d <= 0.5)), 'within_1m': float(np.mean(d <= 1.0)), 'within_2m': float(np.mean(d <= 2.0)),
            'floaters_beyond_5m': float(np.mean(d > FLOATER_M))} if len(d) else None


NEIGHBOURHOOD_M = 2.5   # walls are vertical: a wall point a metre outside its footprint sits over a ground cell


def tolerant_rasters(r, radius_m=NEIGHBOURHOOD_M):
    """The highest lidar surface and the lowest bare ground within `radius_m` horizontally of every cell, so points on
    walls and under eaves are judged against the building they belong to, not the lawn beside it."""
    from scipy.ndimage import maximum_filter, minimum_filter
    from ghostmap.anchor.lidar import fill_nearest
    k = 2 * int(round(radius_m / float(r['cell']))) + 1
    return maximum_filter(fill_nearest(r['surface']), size=k), minimum_filter(fill_nearest(r['ground']), size=k)


def classify(means, lidar):
    """Per Gaussian: 'far' (outside the measured volume), 'air' (more than 2 m above the lidar surface), 'buried'
    (more than 1 m under the bare ground) or 'surface'. `means` in the crop's local metres."""
    from ghostmap.anchor.align import raster_lookup
    from ghostmap.anchor.lidar import fill_nearest
    r = np.load(Path(lidar) / 'quad-rasters-utm18n.npz'); box = tuple(float(v) for v in r['box']); cell = float(r['cell'])
    origin = np.load(Path(lidar) / 'quad-points-utm18n.npz')['origin']
    dsm, dtm = tolerant_rasters(r)
    en = means[:, :2] + origin[:2]
    in_box = (en[:, 0] >= box[0]) & (en[:, 0] <= box[2]) & (en[:, 1] >= box[1]) & (en[:, 1] <= box[3])
    ceiling = float(np.nanmedian(r['ground'])) + 120.0
    surf = raster_lookup(dsm, box, cell, en); ground = raster_lookup(dtm, box, cell, en)
    label = np.full(len(means), 'surface', dtype=object)
    label[means[:, 2] > surf + 2.0] = 'air'; label[means[:, 2] < ground - 1.0] = 'buried'
    label[~in_box | (means[:, 2] > ceiling)] = 'far'
    return label


def score(splat_dir, lidar=None, footprints=FOOTPRINTS):
    from matplotlib.path import Path as MPath
    from scipy.spatial import cKDTree
    from shapely.geometry import Polygon
    splat_dir = Path(splat_dir)
    anchor_report_path = None
    splat_report = json.loads((splat_dir / 'report.json').read_text()) if (splat_dir / 'report.json').exists() else {}
    if lidar is None:   # the lidar crop the fragment was anchored with
        a = Path(splat_report['run']) / 'anchor' / str(splat_report['anchor']) / 'report.json' if splat_report else None
        lidar = Path(json.loads(a.read_text())['lidar_report']).parent if a and a.exists() else LIDAR
    means, opacity, scales, rgb = load_gaussians(splat_dir)
    label_all = classify(means, lidar)
    keep = (opacity >= MIN_OPACITY) & (label_all != 'far')
    far = (opacity >= MIN_OPACITY) & (label_all == 'far')
    labels = label_all[keep]
    cloud = np.load(Path(lidar) / 'quad-points-utm18n.npz'); origin = cloud['origin']; xyz = cloud['xyz'].astype(np.float64)
    anchor_report = splat_report
    tree = cKDTree(xyz)
    d_all, _ = tree.query(means[keep], k=1)
    buildings = json.loads(Path(footprints).read_text())['buildings']
    local = lambda ring: np.asarray(ring) - origin[:2]
    centre = np.median(means[keep][:, :2], 0)
    per_building = {}
    coverage_tree = cKDTree(means[keep])
    for b in buildings:
        ring = local(b['ring'])
        if np.linalg.norm(ring.mean(0) - centre) > 300: continue
        poly = Polygon(ring).buffer(BUFFER_M)
        path = MPath(np.asarray(poly.exterior.coords))
        inside = path.contains_points(means[keep][:, :2])
        if inside.sum() < 50: continue
        # lidar points of the building: inside the footprint and at least 2 m above its surrounding ground
        lid_inside = MPath(ring).contains_points(xyz[:, :2])
        ground = float(np.percentile(xyz[lid_inside][:, 2], 5)) if lid_inside.sum() else None
        building_pts = xyz[lid_inside & (xyz[:, 2] > (ground or 0) + 2.0)] if lid_inside.sum() else np.zeros((0, 3))
        covered = float(np.mean(coverage_tree.query(building_pts, k=1)[0] <= 1.0)) if len(building_pts) else None
        per_building[b['name']] = {'gaussians': int(inside.sum()), 'distance_to_lidar': summarize(d_all[inside]),
                                   'in_free_air': float(np.mean(labels[inside] == 'air')), 'buried': float(np.mean(labels[inside] == 'buried')),
                                   'lidar_building_points': int(len(building_pts)), 'coverage_within_1m': covered}
    # viewer layer: Gaussians on lidar surfaces green (0 m) to yellow (3 m or more from the nearest lidar return),
    # Gaussians in air the lidar saw empty red, buried ones purple.
    t = np.clip(d_all / 3.0, 0, 1)
    colour = np.stack([0.15 + 0.8 * t, 0.75 - 0.05 * t, 0.2 * (1 - t)], 1)
    colour[labels == 'air'] = (0.88, 0.16, 0.14); colour[labels == 'buried'] = (0.55, 0.25, 0.75)
    means[keep].astype(np.float32).tofile(splat_dir / 'geometry-xyz.f32')
    (colour * 255).astype(np.uint8).tofile(splat_dir / 'geometry-rgb.u8')
    report = {'schema_version': 1, 'created_utc': datetime.now(timezone.utc).isoformat(), 'splat': str(splat_dir), 'lidar': str(lidar),
              'frame': 'local metres: UTM 18N minus the lidar crop origin ' + str(origin[:2].tolist()),
              'gaussians': {'total': int(len(means)), 'opaque': int((opacity >= MIN_OPACITY).sum()), 'in_measured_volume': int(keep.sum()), 'far_field': int(far.sum())},
              'free_space': {'in_free_air': float(np.mean(labels == 'air')), 'buried': float(np.mean(labels == 'buried')), 'on_surfaces': float(np.mean(labels == 'surface')),
                             'of': 'opaque Gaussians inside the measured volume'},
              'overall_distance_to_lidar': summarize(d_all), 'per_building': per_building,
              'rules': {'measured_volume': 'the lidar crop box, up to 120 m above its median ground; opacity at least %.1f' % MIN_OPACITY,
                        'free_air': 'more than 2 m above the highest lidar surface within 2.5 m (first returns, 0.5 m raster)', 'buried': 'more than 1 m under the lowest lidar bare ground within 2.5 m',
                        'distance': 'centre of each Gaussian to the nearest lidar point (airborne lidar: roofs and ground dense, walls thin)',
                        'building': 'Gaussians inside the footprint buffered by %.0f m' % BUFFER_M,
                        'coverage': 'share of lidar points inside the footprint and 2 m above its ground with a Gaussian within 1 m',
                        'floaters': 'Gaussians more than %.0f m from any lidar point' % FLOATER_M},
              'viewer_layer': {'xyz_url': 'geometry-xyz.f32', 'rgb_url': 'geometry-rgb.u8', 'colour': 'green on the lidar surface to yellow 3 m off it; red in air the lidar saw empty; purple buried'},
              'splat_report': anchor_report.get('psnr')}
    (splat_dir / 'geometry.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--splat', required=True, type=Path, help='the splat directory (ckpt.pt inside)')
    parser.add_argument('--lidar', type=Path, help='lidar crop; default: the one the fragment was anchored with')
    args = parser.parse_args()
    r = score(args.splat, args.lidar)
    print(json.dumps({'gaussians': r['gaussians'], 'free_space': r['free_space'], 'overall': r['overall_distance_to_lidar'],
                      'per_building': {k: {'gaussians': v['gaussians'], 'median_m': v['distance_to_lidar']['median_m'], 'within_1m': v['distance_to_lidar']['within_1m'], 'coverage': v['coverage_within_1m']} for k, v in r['per_building'].items()}}, indent=1))


if __name__ == '__main__': main()
