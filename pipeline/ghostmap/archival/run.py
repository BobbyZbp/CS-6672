#!/usr/bin/env python3
"""Place public-domain Boardman-era photographs through surviving structure.

For every query: anchor correspondences against the lidar-anchored modern
model, a profile-likelihood resection over focal length, and an
identifiability certificate under each cue (surviving anchors; plus the
measured ground; plus people where pedestrians are detected). Stand-in
photographs of buildings that still exist (Uris Library, McGraw Tower) run
through the identical pipeline, so their intervals can be scored against the
modern reference.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from ghostmap.archival import resect
from ghostmap.archival.reference import Reference
from ghostmap.paths import ROOT

HISTORICAL = ROOT / 'data/raw/historical'
MANIFEST = ROOT / 'data/raw/manifest.json'
# Boardman Hall (demolished 1959) with surviving structure in view.
BOARDMAN = ['114317667', '151148635', '114438099', '127452280', '192537626', '155823882',
            '150099180', '115118987', '111367559']
# Buildings that still exist, photographed in the same era: stand-ins.
STAND_INS = ['111441145', '111541271', '114171695', '114258702', '150960384', '151190611',
             '155915233', '146944394', '154792750']
# Same exposure uploaded twice (pose, focal and depth percentiles coincide).
DUPLICATES = {'151148635': '114317667'}
INLIER_PX = 12.0
MIN_ANCHORS = 12


def records():
    manifest = json.loads(MANIFEST.read_text())
    rows = manifest['sets']['historical']['images']
    return {str(r['pageid']): r for r in rows}


def run(anchor_report, people_file=None, output=None):
    from ghostmap.archival.match import correspondences
    ref = Reference(anchor_report)
    meta = records()
    queries = [q for q in BOARDMAN + STAND_INS if q in meta]
    paths = [HISTORICAL / meta[q]['filename'] for q in queries]
    work = ref.run_path / 'archival'
    corr = correspondences(ref, paths, work / 'queries')
    people = json.loads(Path(people_file).read_text()) if people_file and Path(people_file).exists() else {}
    results = []
    for q, path in zip(queries, paths):
        c = corr[path.name]; w, h = c['size']
        entry = {'pageid': q, 'filename': path.name, 'title': meta[q]['title'], 'date': meta[q]['date'],
                 'license': meta[q]['license'], 'source_url': meta[q]['source_url'],
                 'subject': 'Boardman Hall (demolished 1959)' if q in BOARDMAN else 'surviving building (stand-in)',
                 'duplicate_of': DUPLICATES.get(q), 'size': [w, h], 'anchor_correspondences': int(len(c['points2D'])),
                 'matched_model_images': c['matched_model_images']}
        if len(c['points2D']) < MIN_ANCHORS:
            entry['status'] = 'not_registered'; entry['reason'] = f'{len(c["points2D"])} anchor correspondences (< {MIN_ANCHORS})'
            results.append(entry); print(q, entry['status'], flush=True); continue
        rows = resect.profile(c['points2D'], c['points3D'], w, h, ransac_px=INLIER_PX)
        best = min((r for r in rows if r['ok']), key=lambda r: r['cost'], default=None)
        if best is None or best['inliers'] < MIN_ANCHORS:
            entry['status'] = 'not_registered'; entry['reason'] = 'absolute pose found fewer than %d inliers' % MIN_ANCHORS
            results.append(entry); print(q, entry['status'], flush=True); continue
        # Certificate on the inlier anchors of the best pose (outlier matches would otherwise dominate).
        uv, z = resect.project(c['points3D'], best['R'], best['t'], best['focal_px'], w / 2, h / 2)
        inlier = (z > 0) & (np.linalg.norm(uv - c['points2D'], axis=1) <= INLIER_PX)
        p2, p3 = c['points2D'][inlier], c['points3D'][inlier]
        rows = resect.profile(p2, p3, w, h, ransac_px=INLIER_PX)
        cert = resect.certificate(rows, p3.mean(0), ref.ground, people.get(q), w, h, ref.buildings_surface, p3)
        entry.update(status=cert['status'], inlier_anchors=int(inlier.sum()),
                     anchor_bbox_fraction=float(np.prod(np.ptp(p2, 0)) / (w * h)),
                     anchor_depth_ratio_p90_p10=float(np.percentile(np.linalg.norm(p3 - best['centre'], axis=1), 90) /
                                                      np.percentile(np.linalg.norm(p3 - best['centre'], axis=1), 10)),
                     anchor_points=p3.tolist(), anchor_pixels=p2.tolist(), certificate=cert)
        results.append(entry)
        cues = cert.get('cues', {})
        print(q, entry['status'], int(inlier.sum()), {k: (round(v['distance_interval_m'], 1), round(v['anchors_visible_fraction'], 2)) for k, v in cues.items()}, flush=True)
    report = {'schema_version': 1, 'created_utc': datetime.now(timezone.utc).isoformat(), 'anchor_report': str(anchor_report),
              'queries': results,
              'claims': {'boardman_surface_reconstructed': False, 'poses_are_ground_truth': False},
              'limitations': ['Principal point fixed at the image centre; cropped or rise-shifted postcards add error the certificate does not model.',
                              'Radial distortion ignored; hand-coloured and retouched prints may move edges.',
                              'Anchor 3D points come from the modern model, whose own frame carries a scale uncertainty of about 5 % (two independent scale estimates differ by 5.4 %).']}
    out = Path(output) if output else work / 'report.json'
    out.parent.mkdir(parents=True, exist_ok=True); out.write_text(json.dumps(report, indent=1) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--anchor-report', required=True, type=Path)
    parser.add_argument('--people', type=Path, help='JSON {pageid: [[foot_uv, head_uv], ...]} from detect_people')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    run(args.anchor_report, args.people, args.output)


if __name__ == '__main__': main()
