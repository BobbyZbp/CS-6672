#!/usr/bin/env python3
"""Positive control for the identifiability certificate on modern photographs.

Every registered modern photograph in the anchored reference is re-resected from
its own anchor observations (points that at least two other cameras also see),
with focal length unknown, exactly as an archival postcard would be. Two
regimes are run per camera:

- full: all of its observations;
- postcard-like: only observations on the tower and the library facade next to
  it (the narrow strip that survives in the Boardman-era postcards).

For each, the certificate's intervals are reported with and without the
measured-ground cue, and compared with the camera's bundle-adjusted pose and
the lidar ground under it. This shows (a) how often stock COLMAP leaves a
photographer's position undetermined along the viewing ray, and (b) whether
the cue's intervals contain the reference.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from ghostmap.archival import resect
from ghostmap.archival.reference import Reference


def postcard_like(ref, p2, p3, image_width, tower_points):
    """Keep observations on the tower and nearby library facade, as in the postcards."""
    near_tower = np.linalg.norm(p3[:, :2] - tower_points[:, :2].mean(0), axis=1) <= 30.0
    return p2[near_tower], p3[near_tower]


def run(anchor_report, output=None):
    ref = Reference(anchor_report)
    tower_ids = set(ref.report['tower_point_ids'])
    tower_xyz = np.array([ref.model.points3D[i].xyz for i in tower_ids if i in ref.model.points3D])
    results = []
    for image in sorted(ref.model.images.values(), key=lambda im: im.name):
        cam = ref.model.cameras[image.camera_id]
        p2, p3, _ = ref.observations(image)
        if len(p2) < 12: continue
        ba_centre = np.asarray(image.projection_center())
        ba_height = float(ba_centre[2] - ref.ground(ba_centre[None, :2])[0])
        entry = {'name': image.name, 'bundle_adjusted': {'focal_px': float(cam.params[0]), 'centre': ba_centre.tolist(),
                                                         'height_above_ground_m': ba_height}}
        for regime, (q2, q3) in {'full': (p2, p3), 'postcard-like': postcard_like(ref, p2, p3, cam.width, tower_xyz)}.items():
            if len(q2) < 12: entry[regime] = {'status': 'too_few_anchor_observations', 'observations': int(len(q2))}; continue
            # Undistort with the bundle-adjusted radial term so the pinhole profile is fair.
            rows = resect.profile(q2, q3, cam.width, cam.height)
            cert = resect.certificate(rows, q3.mean(0), ref.ground)
            if cert['status'] != 'registered': entry[regime] = cert; continue
            summary = {'observations': int(len(q2)),
                       'ray': {'centres': [g['centre'] for g in cert['grid']], 'focal_px': [g['focal_px'] for g in cert['grid']],
                               'weights': {cue: c['weights'] for cue, c in cert['cues'].items()}}}
            for cue, c in cert['cues'].items():
                lo, hi = c['distance_to_anchors_m_95']
                ba_dist = float(np.linalg.norm(ba_centre - q3.mean(0)))
                summary[cue] = {k: c[k] for k in ('focal_px_95', 'focal_interval_ratio', 'distance_to_anchors_m_95',
                                                  'distance_interval_m', 'camera_height_above_ground_m_95',
                                                  'distance_interval_shrink_vs_anchors_only')}
                summary[cue]['bundle_adjusted_distance_inside_interval'] = bool(lo - 1.0 <= ba_dist <= hi + 1.0)
                summary[cue]['bundle_adjusted_focal_inside_interval'] = bool(c['focal_px_95'][0] * .98 <= cam.params[0] <= c['focal_px_95'][1] * 1.02)
            entry[regime] = summary
        results.append(entry)
        print(image.name[:60], {r: (entry[r].get('surviving anchors only', {}).get('distance_interval_m') if isinstance(entry.get(r), dict) else None) for r in ('full', 'postcard-like')}, flush=True)

    def tally(regime, cue, key):
        vals = [e[regime][cue][key] for e in results if isinstance(e.get(regime), dict) and cue in e[regime]]
        return vals
    summary = {}
    for regime in ('full', 'postcard-like'):
        summary[regime] = {}
        for cue in ('surviving anchors only', 'anchors + measured ground'):
            widths = tally(regime, cue, 'distance_interval_m')
            inside = tally(regime, cue, 'bundle_adjusted_distance_inside_interval')
            heights = tally(regime, cue, 'camera_height_above_ground_m_95')
            summary[regime][cue] = {'cameras': len(widths), 'median_distance_interval_m': float(np.median(widths)) if widths else None,
                                    'cameras_with_interval_over_20m': int(sum(w > 20 for w in widths)),
                                    'bundle_adjusted_inside_interval': int(sum(inside)),
                                    'height_interval_contains_standing': int(sum(lo <= 1.6 <= hi for lo, hi in heights))}
    heights = [e['bundle_adjusted']['height_above_ground_m'] for e in results]
    report = {'schema_version': 1, 'created_utc': datetime.now(timezone.utc).isoformat(),
              'anchor_report': str(anchor_report), 'cameras': results, 'summary': summary,
              'bundle_adjusted_heights_m': {'median': float(np.median(heights)), 'p10': float(np.percentile(heights, 10)),
                                            'p90': float(np.percentile(heights, 90)),
                                            'outside_0_5_to_4m': int(sum(not (0.5 <= h <= 4.0) for h in heights))},
              'limitations': ['Anchor points were triangulated with the tested camera among others (points seen by at least two other cameras are kept), so the full regime is optimistic.',
                              'Principal point fixed at the image centre and radial distortion ignored in the profile.',
                              'Reference poses are bundle-adjusted estimates, not ground truth; the lidar ground is the only external measurement.']}
    out = Path(output) if output else ref.run_path / 'archival' / 'modern-control.json'
    out.parent.mkdir(parents=True, exist_ok=True); out.write_text(json.dumps(report, indent=1) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--anchor-report', required=True, type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = run(args.anchor_report, args.output)
    print(json.dumps({'summary': report['summary'], 'bundle_adjusted_heights_m': report['bundle_adjusted_heights_m']}, indent=1))


if __name__ == '__main__': main()
