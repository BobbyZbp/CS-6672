#!/usr/bin/env python3
"""Evaluate georegistration against held-out geotags and cross-fragment agreement.

No fit reads geotags; this module does, once, as ground truth. For every anchored fragment of the
runs given (`<run>/anchor/<fragment>/report.json`, either anchoring method):

- geotags: how many of its photographs carry GPS EXIF, how many of those are plausible (within
  1 km of the campus centre; farther ones are wrong and counted, not used), and the distance between
  each anchored camera centre and its geotag (median, 90th percentile, gross errors beyond 25 m).
  Consumer geotags themselves carry several metres of noise, so the honest reading is the gross-error
  rate and the ranking of methods, not centimetres;
- the geotag baseline: a horizontal similarity (scale, rotation about the vertical, translation)
  from the fragment's gravity-aligned camera centres to the plausible geotags, needing at least
  three; its error is leave-one-out, since it is fitted to the very geotags it is scored on;
- cross-fragment agreement: for a building whose walls hold enough points in two anchored
  fragments, the median distance from one fragment's points near it to the other's (free ground
  truth: two independent placements of the same walls must coincide);
- the certificate as a predictor: geotag errors of fragments the certificate calls usable against
  those it calls not usable.

Output: artifacts/georegistration/report.json and table.md, every number traceable to a report.

Usage: PYTHONPATH=pipeline python -m ghostmap.evaluate.georegistration --run <run> [<run> ...]
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from ghostmap.paths import ROOT

MANIFEST = ROOT / 'data/artsquad_modern/manifest.json'
OUTPUT = ROOT / 'artifacts/georegistration'
CAMPUS_CENTRE_UTM = np.array([378000.0, 4700600.0])
PLAUSIBLE_RADIUS_M = 1000.0
GROSS_ERROR_M = 25.0
NEAR_WALL_M = 2.0
MIN_SHARED_POINTS = 100


def geotags(manifest=MANIFEST):
    """Working-image name -> (easting, northing) in UTM 18N from the photographs' own GPS EXIF."""
    from pyproj import Transformer
    to_utm = Transformer.from_crs('EPSG:4326', 'EPSG:32618', always_xy=True)
    out = {}
    for r in json.loads(Path(manifest).read_text())['images']:
        e = r.get('exif') or {}
        if 'latitude' in e and 'longitude' in e:
            x, y = to_utm.transform(e['longitude'], e['latitude']); out[r['filename']] = np.array([x, y])
    return out


def with_metadata(manifest=MANIFEST):
    """Working-image names whose own EXIF was read (the Commons originals). The Flickr photographs come through
    Openverse as resized web copies, which carry no EXIF at all, so whether they had GPS is unknown."""
    return {r['filename'] for r in json.loads(Path(manifest).read_text())['images']}


def plausible(xy):
    return np.linalg.norm(xy - CAMPUS_CENTRE_UTM) <= PLAUSIBLE_RADIUS_M


def similarity_2d(src, dst):
    """Horizontal similarity dst = s R src + t (Umeyama), src and dst (n, 2), n >= 3."""
    mu_s, mu_d = src.mean(0), dst.mean(0)
    S, D = src - mu_s, dst - mu_d
    U, sig, Vt = np.linalg.svd(D.T @ S / len(src))
    sign = np.sign(np.linalg.det(U @ Vt)); C = np.diag([1, sign])
    R = U @ C @ Vt
    s = (sig * np.diag(C)).sum() / max((S ** 2).sum() / len(src), 1e-12)
    return s, R, mu_d - s * R @ mu_s


def geotag_baseline(native_xy, tagged_index, tags):
    """Leave-one-out error of the similarity fitted to the plausible geotags; None with fewer than three."""
    if len(tagged_index) < 3: return None
    errors = []
    for k in range(len(tagged_index)):
        keep = [i for i in range(len(tagged_index)) if i != k]
        s, R, t = similarity_2d(native_xy[tagged_index[keep]], tags[keep])
        pred = s * R @ native_xy[tagged_index[k]] + t
        errors.append(float(np.linalg.norm(pred - tags[k])))
    s, R, t = similarity_2d(native_xy[tagged_index], tags)
    spread = float(np.sqrt(((tags - tags.mean(0)) ** 2).sum(1).mean()))
    return {'leave_one_out_error_m': {'median': float(np.median(errors)), 'p90': float(np.percentile(errors, 90)), 'max': float(np.max(errors))},
            'geotags_used': int(len(tagged_index)), 'geotag_rms_spread_m': spread, 'scale_m_per_unit': float(s)}


def fragment_rows(run, tags, buildings, read=None):
    import pycolmap
    from ghostmap.anchor.align import WallField
    from ghostmap.anchor.georegister import gravity
    from ghostmap.anchor.align import camera_up, robust_mean_direction
    run = Path(run); rows = []
    for report_path in sorted((run / 'anchor').glob('*/report.json')):
        rep = json.loads(report_path.read_text())
        model_dir = Path(rep['anchored_model'])
        if not (model_dir / 'images.bin').exists(): continue
        anchored = pycolmap.Reconstruction(str(model_dir)); origin = np.asarray(rep['local_frame']['origin_utm18n'])
        native = pycolmap.Reconstruction(str(run / rep['model_path']))
        images = sorted(anchored.images.values(), key=lambda im: im.name)
        names = [im.name for im in images]
        centres_utm = np.array([np.asarray(im.projection_center()) + origin for im in images])
        # native, gravity-aligned horizontal coordinates for the geotag baseline
        nat = {im.name: im for im in native.images.values()}
        rot = [nat[n].cam_from_world().rotation.matrix() for n in names]
        nat_c = np.array([nat[n].projection_center() for n in names])
        pts = np.array([p.xyz for p in native.points3D.values()])
        hint, _ = robust_mean_direction(camera_up(rot)); up, _ = gravity(pts, hint)
        from ghostmap.anchor.align import rotation_to_z
        Rg = rotation_to_z(up); native_xy = (nat_c @ Rg.T)[:, :2]
        tagged = [i for i, n in enumerate(names) if n in tags]
        plaus = [i for i in tagged if plausible(tags[names[i]])]
        errors = np.array([np.linalg.norm(centres_utm[i, :2] - tags[names[i]]) for i in plaus])
        cert = rep.get('certificate', {})
        verdict = cert.get('verdict') or ('usable' if rep.get('metric_frame_usable') else 'not usable')
        row = {'run': str(run), 'fragment': report_path.parent.name, 'building': rep.get('building') or rep.get('landmark_building'),
               'method': 'cue-based (georegister.py)' if rep.get('schema_version') == 2 else rep.get('method', '')[:60],
               'cameras': len(names), 'points': anchored.num_points3D(),
               'geotags': {'carried': len(tagged), 'plausible': len(plaus), 'wrong': len(tagged) - len(plaus),
                           # how far each implausible tag lies from where this placement puts its camera
                           'wrong_off_m': sorted(float(np.linalg.norm(centres_utm[i, :2] - tags[names[i]])) for i in tagged if i not in plaus),
                           'without_metadata': None if read is None else sum(1 for n in names if n not in read)},
               'verdict': verdict, 'failure_mode': cert.get('failure_mode'), 'scale_fixed_by': cert.get('scale_fixed_by'),
               'scale_status': rep.get('scale_status'),
               'ours_vs_geotags_m': ({'median': float(np.median(errors)), 'p90': float(np.percentile(errors, 90)), 'max': float(errors.max()),
                                      'gross_errors': int((errors > GROSS_ERROR_M).sum()), 'n': int(len(errors))} if len(errors) else None),
               'geotag_baseline': geotag_baseline(native_xy, np.array(plaus, dtype=int), np.array([tags[names[i]] for i in plaus])) if len(plaus) >= 3 else None,
               'anchored_points_utm': None}
        # points near each building's walls, for cross-fragment agreement
        xyz = np.array([p.xyz for p in anchored.points3D.values()]) + origin if anchored.num_points3D() else np.zeros((0, 3))
        near = {}
        for b in buildings:
            ring = np.asarray(b['ring']); c = ring.mean(0)
            if np.linalg.norm(c - np.median(xyz[:, :2], 0)) > 300 or len(xyz) == 0: continue
            box = (ring[:, 0].min() - 10, ring[:, 1].min() - 10, ring[:, 0].max() + 10, ring[:, 1].max() + 10)
            inside_box = (xyz[:, 0] >= box[0]) & (xyz[:, 0] <= box[2]) & (xyz[:, 1] >= box[1]) & (xyz[:, 1] <= box[3])
            if inside_box.sum() < MIN_SHARED_POINTS: continue
            d = WallField([ring], box)(xyz[inside_box][:, :2])
            sel = np.flatnonzero(inside_box)[d <= NEAR_WALL_M]
            if len(sel) >= MIN_SHARED_POINTS: near[b['name']] = xyz[sel]
        row['_near'] = near
        rows.append(row)
    return rows


def cross_fragment(rows):
    """Median nearest-neighbour distance between two fragments' points near the same building."""
    from scipy.spatial import cKDTree
    out = []
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            for name in set(rows[i]['_near']) & set(rows[j]['_near']):
                a, b = rows[i]['_near'][name], rows[j]['_near'][name]
                d_ab = cKDTree(b).query(a, k=1)[0]; d_ba = cKDTree(a).query(b, k=1)[0]
                out.append({'building': name, 'fragments': [f"{Path(rows[i]['run']).name}/{rows[i]['fragment']}", f"{Path(rows[j]['run']).name}/{rows[j]['fragment']}"],
                            'verdicts': [rows[i]['verdict'], rows[j]['verdict']], 'points': [int(len(a)), int(len(b))],
                            'median_distance_m': float(np.median(np.concatenate([d_ab, d_ba]))), 'p90_distance_m': float(np.percentile(np.concatenate([d_ab, d_ba]), 90))})
    return out


def evaluate(runs, output=OUTPUT):
    from ghostmap.anchor.align import FOOTPRINTS
    buildings = json.loads(FOOTPRINTS.read_text())['buildings']
    tags, read = geotags(), with_metadata()
    rows = [r for run in runs for r in fragment_rows(run, tags, buildings, read)]
    agreement = cross_fragment(rows)
    for r in rows: r.pop('_near', None); r.pop('anchored_points_utm', None)
    usable = [r['ours_vs_geotags_m']['median'] for r in rows if r['verdict'] == 'usable' and r['ours_vs_geotags_m']]
    not_usable = [r['ours_vs_geotags_m']['median'] for r in rows if r['verdict'] != 'usable' and r['ours_vs_geotags_m']]
    summary = {'fragments': len(rows), 'with_plausible_geotags': sum(1 for r in rows if r['ours_vs_geotags_m']),
               'geotag_baseline_possible': sum(1 for r in rows if r['geotag_baseline']),
               'wrong_geotags_total': sum(r['geotags']['wrong'] for r in rows), 'geotags_total': sum(r['geotags']['carried'] for r in rows),
               'certificate_as_predictor': {'usable_median_error_m': float(np.median(usable)) if usable else None, 'usable_fragments_with_geotags': len(usable),
                                            'not_usable_median_error_m': float(np.median(not_usable)) if not_usable else None, 'not_usable_fragments_with_geotags': len(not_usable)}}
    report = {'schema_version': 1, 'created_utc': datetime.now(timezone.utc).isoformat(), 'runs': [str(r) for r in runs],
              'rules': {'plausible_geotag': f'within {PLAUSIBLE_RADIUS_M:.0f} m of the campus centre', 'gross_error_m': GROSS_ERROR_M,
                        'geotag_baseline': 'horizontal similarity (Umeyama) on gravity-aligned camera centres, leave-one-out, at least three plausible geotags',
                        'cross_fragment': f'points within {NEAR_WALL_M} m of a building\'s walls in both fragments, at least {MIN_SHARED_POINTS} each'},
              'summary': summary, 'fragments': rows, 'cross_fragment_agreement': agreement}
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    (output / 'report.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    lines = ['| fragment | building | cameras | geotags (plausible/carried, wrong) | verdict | failure | ours vs geotags: median / p90 / gross | geotag baseline (LOO median) |', '|---|---|---|---|---|---|---|---|']
    for r in rows:
        g = r['geotags']; o = r['ours_vs_geotags_m']; b = r['geotag_baseline']
        lines.append(f"| {Path(r['run']).name[:8]}/{r['fragment']} | {r['building']} | {r['cameras']} | {g['plausible']}/{g['carried']}, {g['wrong']} wrong | {r['verdict']} | {r['failure_mode'] or ''} | "
                     + (f"{o['median']:.1f} / {o['p90']:.1f} / {o['gross_errors']} of {o['n']}" if o else 'no geotags') + ' | '
                     + (f"{b['leave_one_out_error_m']['median']:.1f} m ({b['geotags_used']} tags)" if b else 'cannot run') + ' |')
    if agreement:
        lines += ['', '| building | fragments | verdicts | points | median / p90 distance (m) |', '|---|---|---|---|---|']
        for a in agreement: lines.append(f"| {a['building']} | {' vs '.join(a['fragments'])} | {' / '.join(a['verdicts'])} | {a['points'][0]} / {a['points'][1]} | {a['median_distance_m']:.2f} / {a['p90_distance_m']:.2f} |")
    (output / 'table.md').write_text('\n'.join(lines) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--run', type=Path, nargs='+', required=True)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    report = evaluate(args.run, args.output)
    print(json.dumps(report['summary'], indent=2)); print((Path(args.output) / 'table.md').read_text())


if __name__ == '__main__': main()
