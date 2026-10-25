#!/usr/bin/env python3
"""Build the data for the GhostMap demo page (dist/ghostmap.html).

Collects, in the anchored local metric frame (UTM 18N minus the lidar box
origin): the lidar surface as a height grid with a building mask, OSM
footprints, the anchored modern fragment (points and photographers), each
photographer's ambiguity ray from the positive control, every archival
photograph's certificate, licensed thumbnails, and the headline numbers.
Every number on the page is copied from a report file, whose path is recorded.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

from ghostmap.paths import ROOT

# The EXIF-anchored re-mapping of the 145-photo snapshot; also the default anchored fragment.
EXIF_ANCHORED_RUN = ROOT / 'artifacts/artsquad_modern/runs/18f9388978b18815f239'
BASELINE_RUN = ROOT / 'artifacts/artsquad_modern/runs/2b7e3fa97872072dccbd'
FIXED_RADIAL_RUN = ROOT / 'artifacts/artsquad_modern/runs/bd1208237efd7b33d52d'
# Stock learned COLMAP on the 228-photo snapshot (finished 2026-10-25 after batched matching).
LARGER_SNAPSHOT_RUN = ROOT / 'artifacts/artsquad_modern/runs/6a31738f0df5d4b04328'
OUT = ROOT / 'dist/assets/ghostmap'
CROP_HALF_M = 260.0
TERRAIN_CELL_M = 1.5
THUMB_PX = 720


def mapping_row(run, label):
    r = json.loads((run / 'report.json').read_text())
    cams = [c for comp in r['components'] for c in comp['cameras']]
    return {'label': label, 'run_report': str(run / 'report.json'),
            'models': [c['registered_cameras'] for c in r['components']],
            'registered_photographs': len({c['name'] for c in cams}), 'training_photographs': len(r['input_images']),
            'focal_outside_half_to_triple': sum(not (0.5 <= c['focal_max_dimension_ratio'] <= 3) for c in cams)}


def thumbnail(source, dest):
    if dest.exists(): return
    with Image.open(source) as im:
        im = im.convert('RGB'); im.thumbnail((THUMB_PX, THUMB_PX), Image.Resampling.LANCZOS)
        im.save(dest, quality=85)


def build(output=OUT, anchored_run=EXIF_ANCHORED_RUN):
    from ghostmap.archival.reference import Reference
    output = Path(output); (output / 'photos').mkdir(parents=True, exist_ok=True)
    anchored_run = Path(anchored_run)
    anchor_report = next(iter(sorted((anchored_run / 'anchor').glob('*/report.json'))))
    ref = Reference(anchor_report)
    tower = np.array([ref.model.points3D[i].xyz for i in ref.report['tower_point_ids'] if i in ref.model.points3D]).mean(0)
    centre = tower[:2]

    # Terrain: lidar surface height grid around the south end, plus a building mask.
    from ghostmap.anchor.align import InsideMask
    xs = np.arange(centre[0] - CROP_HALF_M, centre[0] + CROP_HALF_M, TERRAIN_CELL_M)
    ys = np.arange(centre[1] - CROP_HALF_M, centre[1] + CROP_HALF_M, TERRAIN_CELL_M)
    gx, gy = np.meshgrid(xs, ys)
    grid = np.column_stack([gx.ravel(), gy.ravel()])
    surface = ref.surface(grid).astype(np.float32); ground = ref.ground(grid).astype(np.float32)
    inside = InsideMask([b['ring'] for b in ref.buildings], ref.box, ref.cell)(grid + ref.origin[:2]).astype(np.uint8)
    height = np.where(inside == 1, surface, ground).astype(np.float32)  # canopy removed: buildings + ground only
    height.tofile(output / 'terrain-height.f32'); inside.tofile(output / 'terrain-buildings.u8')
    canopy = np.clip(surface - ground, 0, 60).astype(np.float32); canopy.tofile(output / 'terrain-canopy.f32')

    footprints = []
    for b in ref.buildings:
        ring = np.asarray(b['ring']) - ref.origin[:2]
        if np.any(np.abs(ring - centre).max(1) < CROP_HALF_M + 20):
            footprints.append({'name': b['name'], 'ring': np.round(ring, 2).tolist(),
                               'ground': float(np.median(ref.ground(ring)))})

    # Anchored modern fragment.
    ids = list(ref.model.points3D.keys())
    xyz = np.array([ref.model.points3D[i].xyz for i in ids], np.float32)
    rgb = np.array([ref.model.points3D[i].color for i in ids], np.uint8)
    xyz.tofile(output / 'fragment-xyz.f32'); rgb.tofile(output / 'fragment-rgb.u8')
    tower_set = set(ref.report['tower_point_ids'])
    np.array([i in tower_set for i in ids], np.uint8).tofile(output / 'fragment-tower.u8')

    snapshot = json.loads(Path(json.loads((anchored_run / 'report.json').read_text())['snapshot_path']).read_text())
    records = {r['filename']: r for r in snapshot['images']}
    control = json.loads((anchored_run / 'archival/modern-control.json').read_text())
    control_by_name = {c['name']: c for c in control['cameras']}
    photographers = []
    for image in sorted(ref.model.images.values(), key=lambda im: im.name):
        cam = ref.model.cameras[image.camera_id]; rec = records.get(image.name, {})
        thumb = 'photos/' + image.name
        thumbnail(anchored_run / 'images' / image.name, output / thumb)
        C = np.asarray(image.projection_center())
        entry = {'name': image.name, 'title': rec.get('title', image.name), 'license': rec.get('license'),
                 'license_url': rec.get('license_url'), 'artist': rec.get('artist'), 'source_url': rec.get('source_url'),
                 'photo': thumb, 'width': cam.width, 'height': cam.height, 'focal_px': float(cam.params[0]),
                 'centre': C.tolist(), 'rotation': image.cam_from_world().rotation.matrix().tolist(),
                 'height_above_ground_m': float(C[2] - ref.ground(C[None, :2])[0])}
        c = control_by_name.get(image.name)
        if c and isinstance(c.get('postcard-like'), dict) and 'ray' in c['postcard-like']:
            ray = c['postcard-like']['ray']
            entry['ray'] = {'centres': np.round(ray['centres'], 2).tolist(), 'focal_px': ray['focal_px'],
                            'weights': {k: np.round(v, 5).tolist() for k, v in ray['weights'].items()},
                            'intervals': {k: c['postcard-like'][k] for k in ray['weights']}}
        photographers.append(entry)

    # Archival photographs.
    archival = json.loads((anchored_run / 'archival/report.json').read_text())
    people = json.loads((ROOT / 'artifacts/archival-people/people.json').read_text())
    postcards = []
    for q in archival['queries']:
        src = ROOT / 'data/raw/historical' / q['filename']
        thumb = 'photos/' + q['filename']
        thumbnail(src, output / thumb)
        with Image.open(src) as im: full = im.size
        with Image.open(output / thumb) as im: small = im.size
        entry = {k: q.get(k) for k in ('pageid', 'filename', 'title', 'date', 'license', 'source_url', 'subject',
                                       'duplicate_of', 'status', 'reason', 'anchor_correspondences', 'inlier_anchors')}
        entry.update(photo=thumb, size=q['size'], thumb_scale=small[0] / full[0])
        entry['date'] = re.sub(r'date\s*QS.*$', '', entry['date'] or '').strip()  # Commons template residue
        if q['status'] == 'registered':
            cert = q['certificate']
            entry['grid'] = [{'centre': np.round(g['centre'], 2).tolist(), 'rotation': np.round(g['rotation'], 6).tolist(),
                              'focal_px': g['focal_px']} for g in cert['grid']]
            entry['cues'] = {name: {k: c[k] for k in ('focal_px_95', 'focal_interval_ratio', 'distance_to_anchors_m_95',
                                                       'distance_interval_m', 'camera_height_above_ground_m_95', 'map_centre',
                                                       'anchors_visible_fraction', 'distance_interval_shrink_vs_anchors_only')}
                             | {'weights': np.round(c['weights'], 6).tolist()} for name, c in cert['cues'].items()}
            entry['anchor_points'] = np.round(q['anchor_points'], 2).tolist()
            if q['pageid'] in people:
                entry['people'] = people[q['pageid']]
                entry['people_implied_heights_m'] = {name: c.get('people_implied_heights_m') for name, c in cert['cues'].items()}
            if q['subject'].startswith('Boardman'):
                entry['mirror_pose'] = ('found by inspection on 2026-10-25: the pose sees Boardman to the right of the tower, '
                                        'the postcard shows it to the left; the modern model has only the tower\'s west and south faces')
        postcards.append(entry)

    numbers = {
        'mapping': [mapping_row(BASELINE_RUN, 'stock learned COLMAP (SuperPoint + LightGlue)'),
                    mapping_row(FIXED_RADIAL_RUN, 'radial distortion fixed at zero'),
                    mapping_row(EXIF_ANCHORED_RUN, 'EXIF-anchored calibration (this extension)'),
                    mapping_row(LARGER_SNAPSHOT_RUN, 'stock learned COLMAP, 228-photo snapshot (139 training)')],
        'anchored_run': str(anchored_run),
        'anchoring': {k: ref.report[k] for k in ('scale_status', 'scale_checks', 'gate', 'metric_frame_usable')}
                     | {'tower': ref.report['metrics']['tower'], 'library_wall_distance_m': ref.report['metrics']['neighbour_wall_distance_m'],
                        'photographer_heights_m': ref.report['metrics']['camera_height_above_ground_m'],
                        'report': str(anchor_report)},
        'positive_control': control['summary'] | {'report': str(anchored_run / 'archival/modern-control.json')},
        'lidar': {k: json.loads((ROOT / 'data/lidar/NY_FingerLakes_1_2020/report.json').read_text())[k]
                  for k in ('points_kept', 'class_counts', 'license', 'source')},
    }
    scene = {'schema_version': 1, 'title': 'GhostMap — what the surviving world can prove about a vanished building',
             'generated_utc': datetime.now(timezone.utc).isoformat(),
             'frame': {'crs': 'EPSG:32618 (UTM 18N) minus origin', 'origin_utm18n': ref.origin.tolist(), 'up': 'z, metres'},
             'tower_centre': tower.tolist(),
             'terrain': {'height_url': 'terrain-height.f32', 'buildings_url': 'terrain-buildings.u8', 'canopy_url': 'terrain-canopy.f32',
                         'cols': len(xs), 'rows': len(ys), 'cell_m': TERRAIN_CELL_M, 'x0': float(xs[0]), 'y0': float(ys[0])},
             'footprints': footprints, 'boardman_site': 'Olin Library',
             'fragment': {'xyz_url': 'fragment-xyz.f32', 'rgb_url': 'fragment-rgb.u8', 'tower_url': 'fragment-tower.u8', 'count': len(ids)},
             'photographers': photographers, 'postcards': postcards, 'numbers': numbers,
             'attribution': ['Lidar: USGS 3DEP NY_FingerLakes_1_2020, public domain.',
                             'Building footprints: (c) OpenStreetMap contributors, ODbL.',
                             'Photographs: Wikimedia Commons; licence and author per photo.']}
    (output / 'scene.json').write_text(json.dumps(scene) + '\n')
    return scene


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUT)
    parser.add_argument('--run', type=Path, default=EXIF_ANCHORED_RUN, help='run with anchor/ and archival/ results to show')
    args = parser.parse_args()
    scene = build(args.output, args.run)
    print(len(scene['photographers']), 'photographers,', len(scene['postcards']), 'archival photographs,',
          scene['fragment']['count'], 'points')


if __name__ == '__main__': main()
