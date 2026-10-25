#!/usr/bin/env python3
"""When did each reconstructed point exist? Existence intervals from dated photographs.

COLMAP knows which photographs observe each 3D point, and the photographs
carry capture dates. So every point has a first and a last observed year.
Between them it existed. Outside them the evidence is weaker and is counted
rather than assumed: for every dated registered photograph that does not
observe the point, the point is tested for being "in view" (in front of the
camera, inside the frame, and not hidden behind a building of the lidar
model); a point that was in view of several photographs of a year and seen by
none of them has evidence of absence for that year. This is the reasoning of
Scene Chronology (Matzen and Snavely, ECCV 2014) rebuilt on pycolmap, with
the lidar buildings as the occluder model and with the absence evidence kept
separate from the observation interval instead of being folded into one
estimate.

Per building (OpenStreetMap footprint), the point intervals are summarised,
so the viewer can say "first photographed in 2014" and show which years
would have seen it and did not.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from ghostmap.paths import ROOT

MIN_VIEWS_FOR_ABSENCE = 3
MARGIN_PX = 0


def capture_years(snapshot):
    years = {}
    for image in snapshot['images']:
        ev = image.get('capture_evidence') or {}
        y = (ev.get('earliest') or '')[:4]
        if y.isdigit(): years[image['filename']] = int(y)
    return years


def in_view(points, image, camera, occluder=None, origin=None, step=1.0):
    """Which points lie inside the image frame, in front of it, and unobstructed."""
    R = image.cam_from_world().rotation.matrix(); t = np.asarray(image.cam_from_world().translation)
    X = points @ R.T + t; z = X[:, 2]
    f, cx, cy = camera.params[0], camera.params[1], camera.params[2]
    ok = z > 1.0
    u = np.where(ok, f * X[:, 0] / np.where(ok, z, 1) + cx, -1); v = np.where(ok, f * X[:, 1] / np.where(ok, z, 1) + cy, -1)
    ok &= (u >= MARGIN_PX) & (u < camera.width - MARGIN_PX) & (v >= MARGIN_PX) & (v < camera.height - MARGIN_PX)
    if occluder is not None and ok.any():
        C = np.asarray(image.projection_center())
        idx = np.flatnonzero(ok)
        for i in idx:
            d = points[i] - C; L = np.linalg.norm(d)
            if L < 3 * step: continue
            ts = np.arange(2.0, L - 2.0, step)
            P = C + ts[:, None] * (d / L)
            if np.any(occluder(P[:, :2]) > P[:, 2] + 1.0): ok[i] = False
    return ok


def point_intervals(model, years, occluder=None):
    ids = np.array(list(model.points3D.keys()))
    xyz = np.array([model.points3D[i].xyz for i in ids])
    observed = defaultdict(Counter); in_view_unobserved = defaultdict(Counter)
    index = {pid: k for k, pid in enumerate(ids)}
    for image in model.images.values():
        year = years.get(image.name)
        if year is None: continue
        seen = {p.point3D_id for p in image.points2D if p.has_point3D()}
        seen_mask = np.zeros(len(ids), bool)
        for pid in seen:
            if pid in index: seen_mask[index[pid]] = True
        for k in np.flatnonzero(seen_mask): observed[int(ids[k])][year] += 1
        view = in_view(xyz, image, model.cameras[image.camera_id], occluder)
        for k in np.flatnonzero(view & ~seen_mask): in_view_unobserved[int(ids[k])][year] += 1
    rows = []
    for k, pid in enumerate(ids):
        obs = observed.get(int(pid), Counter()); miss = in_view_unobserved.get(int(pid), Counter())
        first = min(obs) if obs else None; last = max(obs) if obs else None
        absent = sorted(y for y, n in miss.items() if n >= MIN_VIEWS_FOR_ABSENCE and y not in obs and (first is None or y < first or y > last))
        rows.append({'id': int(pid), 'xyz': xyz[k].round(3).tolist(), 'first_seen': first, 'last_seen': last,
                     'observed_years': dict(sorted(obs.items())), 'in_view_unobserved_years': dict(sorted(miss.items())),
                     'absence_evidence_years': absent})
    return rows


def building_summary(rows, footprints_local, buffer_m=3.0):
    from shapely.geometry import Point, Polygon
    out = {}
    for name, ring in footprints_local.items():
        poly = Polygon(ring).buffer(buffer_m)
        inside = [r for r in rows if r['first_seen'] is not None and poly.contains(Point(r['xyz'][0], r['xyz'][1]))]
        if not inside: continue
        firsts = Counter(r['first_seen'] for r in inside); lasts = Counter(r['last_seen'] for r in inside)
        absent = Counter(y for r in inside for y in r['absence_evidence_years'])
        out[name] = {'points': len(inside), 'first_seen_years': dict(sorted(firsts.items())), 'last_seen_years': dict(sorted(lasts.items())),
                     'earliest_photograph': min(firsts), 'latest_photograph': max(lasts),
                     'points_with_absence_evidence_by_year': dict(sorted(absent.items()))}
    return out


def run(run_path, component, anchor_report=None, output=None):
    import pycolmap
    from ghostmap.archival.reference import Reference
    run_path = Path(run_path).resolve()
    report = json.loads((run_path / 'report.json').read_text())
    snapshot = json.loads(Path(report['snapshot_path']).read_text())
    years = capture_years(snapshot)
    ref = Reference(anchor_report) if anchor_report else None
    model = ref.model if ref else pycolmap.Reconstruction(str(run_path / next(c['model_path'] for c in report['components'] if str(c['id']) == str(component))))
    rows = point_intervals(model, years, ref.buildings_surface if ref else None)
    footprints = {}
    if ref:
        for b in ref.buildings:
            if b['name']: footprints[b['name']] = np.asarray(b['ring']) - ref.origin[:2]
    buildings = building_summary(rows, footprints) if footprints else {}
    dated = sum(1 for im in model.images.values() if im.name in years)
    result = {'schema_version': 1, 'created_utc': datetime.now(timezone.utc).isoformat(), 'run_id': report['run_id'], 'component_id': str(component),
              'frame': 'anchored local metres' if ref else 'model units (unanchored)', 'registered_photographs': len(model.images),
              'dated_photographs': dated, 'capture_years': dict(sorted(Counter(years[im.name] for im in model.images.values() if im.name in years).items())),
              'points': len(rows), 'points_with_dates': sum(r['first_seen'] is not None for r in rows),
              'points_with_absence_evidence': sum(bool(r['absence_evidence_years']) for r in rows),
              'min_views_for_absence': MIN_VIEWS_FOR_ABSENCE, 'buildings': buildings,
              'method': __doc__.strip().split('\n')[0], 'point_intervals': rows}
    out = Path(output) if output else run_path / 'chronology' / f'{component}-intervals.json'
    out.parent.mkdir(parents=True, exist_ok=True); out.write_text(json.dumps(result) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--component', required=True)
    parser.add_argument('--anchor-report', type=Path, help='use the lidar-anchored copy and the building occluder model')
    args = parser.parse_args()
    r = run(args.run, args.component, args.anchor_report)
    print(json.dumps({k: r[k] for k in ('registered_photographs', 'dated_photographs', 'capture_years', 'points', 'points_with_dates', 'points_with_absence_evidence')}, indent=1))
    for name, b in r['buildings'].items(): print(f"{name:24s} points {b['points']:5d}  first {b['earliest_photograph']}  last {b['latest_photograph']}  first-seen {b['first_seen_years']}")


if __name__ == '__main__': main()
