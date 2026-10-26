#!/usr/bin/env python3
"""Score a Gaussian splat's geometry against the public lidar, building by building.

The splat lives in the anchor's local metres (UTM 18N minus the lidar crop origin), the same frame as
the lidar points of that crop, so no transform is needed: every Gaussian with enough opacity is
measured by the distance from its centre to the nearest lidar point (airborne lidar sees roofs and
ground densely and walls thinly, so wall Gaussians are judged against the nearest roof-edge or wall
return, a conservative score). Per building (OpenStreetMap footprint, 3 m buffer) and overall:
median and 90th-percentile distance, the share within 0.5, 1 and 2 m, and floaters (Gaussians more
than 5 m from any lidar point, the classic failure of in-the-wild reconstructions). Coverage says how
much of the lidar building the splat reaches: the share of lidar points above the building's ground
that have a Gaussian within 1 m.

Outputs: `<splat dir>/geometry.json`, and a distance-coloured copy of the Gaussian centres
(`geometry-xyz.f32`, `geometry-rgb.u8`: green at 0 m to red at 3 m) for the viewer.

Usage: PYTHONPATH=pipeline python -m ghostmap.evaluate.splat_geometry --splat <run>/splats/<name> [--lidar data/lidar/NY_FingerLakes_1_2020]
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


def score(splat_dir, lidar=LIDAR, footprints=FOOTPRINTS):
    from matplotlib.path import Path as MPath
    from scipy.spatial import cKDTree
    from shapely.geometry import Polygon
    splat_dir = Path(splat_dir)
    means, opacity, scales, rgb = load_gaussians(splat_dir)
    keep = opacity >= MIN_OPACITY
    cloud = np.load(Path(lidar) / 'quad-points-utm18n.npz'); origin = cloud['origin']; xyz = cloud['xyz'].astype(np.float64)
    report_lidar = json.loads((Path(lidar) / 'report.json').read_text())
    anchor_report = json.loads((splat_dir / 'report.json').read_text()) if (splat_dir / 'report.json').exists() else {}
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
                                   'lidar_building_points': int(len(building_pts)), 'coverage_within_1m': covered}
    # viewer layer: centres coloured by distance (green 0 m -> yellow 1.5 m -> red 3 m)
    t = np.clip(d_all / 3.0, 0, 1)
    colour = np.stack([np.clip(2 * t, 0, 1), np.clip(2 - 2 * t, 0, 1), np.zeros_like(t)], 1)
    means[keep].astype(np.float32).tofile(splat_dir / 'geometry-xyz.f32')
    (colour * 255).astype(np.uint8).tofile(splat_dir / 'geometry-rgb.u8')
    report = {'schema_version': 1, 'created_utc': datetime.now(timezone.utc).isoformat(), 'splat': str(splat_dir), 'lidar': str(lidar),
              'frame': 'local metres: UTM 18N minus the lidar crop origin ' + str(origin[:2].tolist()),
              'gaussians': {'total': int(len(means)), 'scored_opacity_at_least_%.1f' % MIN_OPACITY: int(keep.sum())},
              'overall_distance_to_lidar': summarize(d_all), 'per_building': per_building,
              'rules': {'distance': 'centre of each Gaussian to the nearest lidar point (airborne lidar: roofs and ground dense, walls thin)',
                        'building': 'Gaussians inside the footprint buffered by %.0f m' % BUFFER_M,
                        'coverage': 'share of lidar points inside the footprint and 2 m above its ground with a Gaussian within 1 m',
                        'floaters': 'Gaussians more than %.0f m from any lidar point' % FLOATER_M},
              'viewer_layer': {'xyz_url': 'geometry-xyz.f32', 'rgb_url': 'geometry-rgb.u8', 'colour': 'green 0 m, yellow 1.5 m, red 3 m'},
              'splat_report': anchor_report.get('psnr')}
    (splat_dir / 'geometry.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--splat', required=True, type=Path, help='the splat directory (ckpt.pt inside)')
    parser.add_argument('--lidar', type=Path, default=LIDAR)
    args = parser.parse_args()
    r = score(args.splat, args.lidar)
    print(json.dumps({'gaussians': r['gaussians'], 'overall': r['overall_distance_to_lidar'],
                      'per_building': {k: {'gaussians': v['gaussians'], 'median_m': v['distance_to_lidar']['median_m'], 'within_1m': v['distance_to_lidar']['within_1m'], 'coverage': v['coverage_within_1m']} for k, v in r['per_building'].items()}}, indent=1))


if __name__ == '__main__': main()
