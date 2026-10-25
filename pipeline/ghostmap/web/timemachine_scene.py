#!/usr/bin/env python3
"""Build the data for the Cornell Time Machine page (dist/timemachine.html).

One local metric frame (UTM 18N minus the Quad lidar box origin) holds:
- the lidar terrain of each site as a height grid with a building mask,
- one orthoimage per flight year per site, as textures that drape the terrain,
- building footprints with their documented dates, their per-year aerial
  crops and outline scores, and the first year a ground photograph observed
  them,
- the anchored reconstruction(s) with per-point first and last observed year,
- the dated photographers with licensed thumbnails.
Every number comes from a report file whose path is recorded.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

from ghostmap.paths import ROOT

OUT = ROOT / 'dist/assets/timemachine'
TIMELINE = ROOT / 'config/timeline.json'
SITES = {'quad': {'lidar': ROOT / 'data/lidar/NY_FingerLakes_1_2020', 'ortho': ROOT / 'data/orthoimagery/quad'},
         'gates-site': {'lidar': ROOT / 'data/lidar/gates-site', 'ortho': ROOT / 'data/orthoimagery/gates-site'}}
TERRAIN_CELL_M = 1.5
TEXTURE_PX = 2048
THUMB_PX = 640
CROP_MARGIN_M = 18.0


def thumbnail(source, dest, size=THUMB_PX):
    if dest.exists(): return
    with Image.open(source) as im:
        im = im.convert('RGB'); im.thumbnail((size, size), Image.Resampling.LANCZOS); im.save(dest, quality=85)


def terrain(site, origin, out):
    from ghostmap.anchor.align import InsideMask
    from ghostmap.anchor.lidar import fill_nearest
    ras = np.load(SITES[site]['lidar'] / 'quad-rasters-utm18n.npz')
    box, cell = tuple(ras['box']), float(ras['cell'])
    surface, ground = fill_nearest(ras['surface']), ras['ground']
    buildings = json.loads((ROOT / 'data/footprints/buildings-utm18n.json').read_text())['buildings']
    mask = InsideMask([b['ring'] for b in buildings], box, cell).mask
    height = np.where(mask, surface, ground)
    step = int(round(TERRAIN_CELL_M / cell))
    h = height[::step, ::step].astype(np.float32); m = mask[::step, ::step].astype(np.uint8)
    rows, cols = h.shape
    h.tofile(out / f'{site}-height.f32'); m.tofile(out / f'{site}-buildings.u8')
    x0, y1 = box[0] - origin[0], box[3] - origin[1]
    # Row 0 is the north edge (raster convention); the viewer builds the grid accordingly.
    return {'height_url': f'{site}-height.f32', 'buildings_url': f'{site}-buildings.u8', 'rows': rows, 'cols': cols,
            'cell_m': cell * step, 'x0': float(x0), 'y_top': float(y1), 'x1': float(box[2] - origin[0]), 'y_bottom': float(box[1] - origin[1]),
            'z_offset': float(-origin[2])}


def orthos(site, out, years):
    rep = json.loads((SITES[site]['ortho'] / 'report.json').read_text())
    result = {}
    for y in years:
        if y not in rep['years']: continue
        src = SITES[site]['ortho'] / rep['years'][y]['file']; dest = out / f'{site}-{y}.jpg'
        if not dest.exists():
            with Image.open(src) as im:
                im = im.convert('RGB'); im.thumbnail((TEXTURE_PX, TEXTURE_PX), Image.Resampling.LANCZOS); im.save(dest, quality=86)
        result[y] = {'url': f'{site}-{y}.jpg', 'blank': rep['years'][y]['blank']}
    return result, rep


def aerial_crops(site, ring_utm, name, out, years):
    """Per-year colour crops of a footprint, for the evidence panel."""
    rep = json.loads((SITES[site]['ortho'] / 'report.json').read_text())
    box, gsd = rep['box_utm'], rep['ground_sample_distance_m']
    r = np.asarray(ring_utm); e0, n0, e1, n1 = r[:, 0].min() - CROP_MARGIN_M, r[:, 1].min() - CROP_MARGIN_M, r[:, 0].max() + CROP_MARGIN_M, r[:, 1].max() + CROP_MARGIN_M
    c0, c1 = int((e0 - box[0]) / gsd), int((e1 - box[0]) / gsd); r0, r1 = int((box[3] - n1) / gsd), int((box[3] - n0) / gsd)
    urls = {}
    slug = name.replace(' ', '_').replace('&', 'and')
    for y in years:
        if y not in rep['years']: continue
        dest = out / 'crops' / f'{slug}-{y}.jpg'
        if not dest.exists():
            with Image.open(SITES[site]['ortho'] / rep['years'][y]['file']) as im:
                im.crop((max(0, c0), max(0, r0), min(im.width, c1), min(im.height, r1))).save(dest, quality=88)
        urls[y] = f'crops/{slug}-{y}.jpg'
    return urls


def build(output=OUT, anchored_runs=None, record_snapshot=None, ground_runs=None):
    from ghostmap.archival.reference import Reference
    output = Path(output); (output / 'photos').mkdir(parents=True, exist_ok=True); (output / 'crops').mkdir(exist_ok=True)
    timeline = json.loads(TIMELINE.read_text()); years = timeline['aerial_years']
    quad_lidar = json.loads((SITES['quad']['lidar'] / 'report.json').read_text())
    origin = np.array(quad_lidar['box_utm'][:2] + [0.0])
    footprints_all = json.loads((ROOT / 'data/footprints/buildings-utm18n.json').read_text())['buildings']

    sites = {}
    for site in SITES:
        if not (SITES[site]['lidar'] / 'report.json').exists(): continue
        tex, rep = orthos(site, output, years)
        sites[site] = {'terrain': terrain(site, origin, output), 'orthoimagery': tex,
                       'ortho_box_local': [rep['box_utm'][0] - origin[0], rep['box_utm'][1] - origin[1], rep['box_utm'][2] - origin[0], rep['box_utm'][3] - origin[1]]}

    # Roof-presence diagnostics per site.
    roof = {}
    for site in sites:
        p = SITES[site]['ortho'] / 'roof-presence/report.json'
        if p.exists():
            r = json.loads(p.read_text()); roof.update({b['name']: {'site': site, 'rule': r['rule'], 'years': b['years']} for b in r['buildings']})

    # Reconstructions with intervals.
    reconstructions, photographers = [], []
    ground_first_seen = {}
    # Every fragment of every run whose anchored frame is usable (a fragment with 'anchoring attempted;
    # frame not usable' stays out of the scene).
    for run, report in [(r, p) for r in (anchored_runs or []) for p in sorted((Path(r) / 'anchor').glob('*/report.json'))]:
        if not json.loads(report.read_text()).get('metric_frame_usable'): continue
        ref = Reference(report)
        comp = report.parent.name
        intervals_path = Path(run) / 'chronology' / f'{comp}-intervals.json'
        intervals = json.loads(intervals_path.read_text()) if intervals_path.exists() else None
        shift = ref.origin - origin  # this run's local frame -> the scene's local frame
        ids = list(ref.model.points3D.keys())
        xyz = (np.array([ref.model.points3D[i].xyz for i in ids]) + shift).astype(np.float32)
        rgb = np.array([ref.model.points3D[i].color for i in ids], np.uint8)
        first = np.zeros(len(ids), np.int16); last = np.zeros(len(ids), np.int16)
        if intervals:
            by_id = {r['id']: r for r in intervals['point_intervals']}
            for k, i in enumerate(ids):
                r = by_id.get(int(i), {})
                first[k] = r.get('first_seen') or 0; last[k] = r.get('last_seen') or 0
            for name, b in intervals['buildings'].items(): ground_first_seen[name] = b
        tag = f'{Path(run).name[:8]}-{comp}'
        xyz.tofile(output / f'points-{tag}.f32'); rgb.tofile(output / f'points-{tag}.u8')
        first.tofile(output / f'points-{tag}-first.i16'); last.tofile(output / f'points-{tag}-last.i16')
        snapshot = json.loads(Path(json.loads((Path(run) / 'report.json').read_text())['snapshot_path']).read_text())
        records = {r['filename']: r for r in snapshot['images']}
        for image in sorted(ref.model.images.values(), key=lambda im: im.name):
            rec = records.get(image.name, {}); ev = rec.get('capture_evidence') or {}
            year = (ev.get('earliest') or '')[:4]
            thumb = 'photos/' + image.name
            thumbnail(Path(run) / 'images' / image.name, output / thumb)
            cam = ref.model.cameras[image.camera_id]; C = np.asarray(image.projection_center()) + shift
            photographers.append({'name': image.name, 'title': rec.get('title', image.name), 'year': int(year) if year.isdigit() else None,
                                  'date': ev.get('earliest'), 'license': rec.get('license'), 'license_url': rec.get('license_url'),
                                  'artist': rec.get('artist'), 'source_url': rec.get('source_url'), 'photo': thumb,
                                  'width': cam.width, 'height': cam.height, 'focal_px': float(cam.params[0]),
                                  'centre': C.round(2).tolist(), 'rotation': np.round(image.cam_from_world().rotation.matrix(), 6).tolist(),
                                  'reconstruction': tag})
        reconstructions.append({'tag': tag, 'run': str(run), 'anchor_report': str(report), 'intervals_report': str(intervals_path) if intervals else None,
                                'points': len(ids), 'dated_photographs': intervals['dated_photographs'] if intervals else None,
                                'xyz_url': f'points-{tag}.f32', 'rgb_url': f'points-{tag}.u8', 'first_url': f'points-{tag}-first.i16', 'last_url': f'points-{tag}-last.i16',
                                'scale_status': ref.report['scale_status'], 'anchored_through': ref.report.get('landmark_building')})

    # The ground record per building: the licensed photographs of its acquisition target in the snapshot
    # (deduplicated), their photographers and capture dates, whether or not they could be reconstructed.
    ground_record = {}
    if record_snapshot:
        snap = json.loads(Path(record_snapshot).read_text())
        by_target = {}
        for rec in snap['images']:
            if rec.get('split') == 'excluded': continue
            for target in (rec.get('discovery') or {}).get('targets', []): by_target.setdefault(target, []).append(rec)
        for b in timeline['buildings']:
            recs = by_target.get(b.get('target'), [])
            if not recs: continue
            dated = sorted((r for r in recs if (r.get('capture_evidence') or {}).get('earliest')), key=lambda r: r['capture_evidence']['earliest'])
            strip = []
            for r in dated[:6]:
                src = Path(r.get('working_path') or (ROOT / 'artifacts/artsquad_modern/images' / r['filename']))
                if not src.exists(): continue
                thumb = 'photos/' + r['filename']; thumbnail(src, output / thumb)
                strip.append({'photo': thumb, 'date': r['capture_evidence']['earliest'][:10], 'title': r.get('title'), 'artist': r.get('artist'),
                              'license': r.get('license'), 'source_url': r.get('source_url')})
            ground_record[b['footprint']] = {'photographs': len(recs), 'photographers': len({r.get('artist') for r in recs}), 'dated': len(dated),
                                             'earliest': dated[0]['capture_evidence']['earliest'][:10] if dated else None,
                                             'latest': dated[-1]['capture_evidence']['earliest'][:10] if dated else None, 'strip': strip,
                                             'snapshot': str(record_snapshot)}
    # Reconstruction attempts per building: a run mapped on one target, its fragments, and the anchoring outcome.
    for run in (ground_runs or []):
        report = json.loads((Path(run) / 'report.json').read_text())
        targets = report.get('configuration', {}).get('targets') or []
        for b in timeline['buildings']:
            if b.get('target') not in targets or b['footprint'] not in ground_record: continue
            fragments = sorted(report.get('components', []), key=lambda c: -c['registered_cameras'])
            anchors = [json.loads(p.read_text()) for p in sorted((Path(run) / 'anchor').glob('*/report.json'))]
            ground_record[b['footprint']]['reconstruction'] = {
                'run': str(run), 'photographs_mapped': len(report.get('input_images', [])),
                'registered': sum(c['registered_cameras'] for c in fragments), 'fragments': len(fragments),
                'largest_fragment': {'cameras': fragments[0]['registered_cameras'], 'points': fragments[0]['sparse_points']} if fragments else None,
                'anchoring': [{'fragment_cameras': next((c['registered_cameras'] for c in fragments if str(c['id']) == a['component_id']), None),
                               'building': a.get('landmark_building'), 'usable': bool(a.get('metric_frame_usable')), 'status': a.get('scale_status'),
                               'points_within_1m_of_walls': a.get('metrics', {}).get('building', {}).get('points_within_1m_of_own_walls')} for a in anchors]}

    # Buildings: footprints near either site, with documented dates where known.
    documented = {b['footprint']: b for b in timeline['buildings']}
    buildings = []
    for b in footprints_all:
        ring = np.asarray(b['ring'])
        site = next((s for s in sites if (lambda bx: bx[0] - 20 < ring[:, 0].mean() - origin[0] < bx[2] + 20 and bx[1] - 20 < ring[:, 1].mean() - origin[1] < bx[3] + 20)(sites[s]['ortho_box_local'])), None)
        if site is None: continue
        from ghostmap.anchor.align import raster_lookup
        lid = np.load(SITES[site]['lidar'] / 'quad-rasters-utm18n.npz')
        ground = float(np.nanmedian(raster_lookup(lid['ground'], tuple(lid['box']), float(lid['cell']), ring)))
        top = float(np.nanmax(raster_lookup(np.nan_to_num(lid['surface'], nan=-1e9), tuple(lid['box']), float(lid['cell']), ring)))
        entry = {'name': b['name'], 'site': site, 'ring': np.round(ring - origin[:2], 2).tolist(), 'ground': ground - origin[2], 'lidar_top': top - origin[2]}
        doc = documented.get(b['name'])
        if doc:
            entry['documented'] = {k: v for k, v in doc.items() if k not in ('footprint', 'site')}
            entry['aerial_crops'] = aerial_crops(site, ring, b['name'], output, years)
            if b['name'] in roof: entry['aerial_outline_score'] = {y: v['outline_edge_ratio'] for y, v in roof[b['name']]['years'].items()}
            if b['name'] in ground_first_seen: entry['ground_photographs'] = ground_first_seen[b['name']]
            if b['name'] in ground_record: entry['ground_record'] = ground_record[b['name']]
        buildings.append(entry)

    scene = {'schema_version': 1, 'title': 'Cornell Time Machine', 'generated_utc': datetime.now(timezone.utc).isoformat(),
             'frame': {'crs': 'EPSG:32618 minus origin', 'origin_utm18n': origin.tolist(), 'up': 'z, metres'},
             'years': years, 'sites': sites, 'buildings': buildings, 'reconstructions': reconstructions, 'photographers': photographers,
             'roof_rule': next(iter({v['rule'] for v in roof.values()}), None),
             'attribution': [timeline['aerial_source'], 'Lidar: USGS 3DEP NY_FingerLakes_1_2020, public domain.',
                             'Building footprints: (c) OpenStreetMap contributors, ODbL.', 'Photographs: Wikimedia Commons and Flickr (via Openverse); licence and author per photo.']}
    (output / 'scene.json').write_text(json.dumps(scene, allow_nan=False) + '\n')
    return scene


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUT)
    parser.add_argument('--run', type=Path, nargs='*', default=[ROOT / 'artifacts/artsquad_modern/runs/6406b8eaae260163b303'], help='anchored runs to include')
    parser.add_argument('--snapshot', type=Path, help='deduplicated snapshot whose photographs give each building its ground record')
    parser.add_argument('--ground-run', type=Path, nargs='*', default=[], help='runs mapped on one building target, reported as reconstruction attempts')
    args = parser.parse_args()
    s = build(args.output, args.run, args.snapshot, args.ground_run)
    print(len(s['sites']), 'sites,', len(s['buildings']), 'buildings,', sum(r['points'] for r in s['reconstructions']), 'points,', len(s['photographers']), 'photographers')


if __name__ == '__main__': main()
