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
import shutil
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


def read_ply(path, wanted=('x', 'y', 'z', 'red', 'green', 'blue')):
    """Binary little-endian PLY. Elements without list properties are read in one go; an element with
    list properties (OpenMVS dense clouds carry per-vertex view lists) is walked record by record and
    only the `wanted` scalar properties kept; a face element with a uniform list of three indices is
    returned as (n, 3) indices."""
    import struct
    types = {'float': '<f4', 'float32': '<f4', 'double': '<f8', 'uchar': 'u1', 'uint8': 'u1', 'char': 'i1', 'int8': 'i1',
             'int': '<i4', 'int32': '<i4', 'uint': '<u4', 'uint32': '<u4', 'ushort': '<u2', 'uint16': '<u2', 'short': '<i2', 'int16': '<i2'}
    with open(path, 'rb') as f:
        elements, current = [], None
        while True:
            line = f.readline().decode('ascii').strip()
            if line == 'end_header': break
            parts = line.split()
            if parts[:1] == ['format'] and parts[1] != 'binary_little_endian': raise ValueError('binary little-endian PLY expected')
            if parts[:1] == ['element']: current = {'name': parts[1], 'count': int(parts[2]), 'props': []}; elements.append(current)
            elif parts[:1] == ['property']: current['props'].append(('list', parts[2], parts[3], parts[4]) if parts[1] == 'list' else (parts[1], parts[2]))
        out = {}
        for el in elements:
            lists = [p for p in el['props'] if p[0] == 'list']
            if not lists:
                arr = np.fromfile(f, dtype=np.dtype([(p[1], types[p[0]]) for p in el['props']]), count=el['count'])
                out[el['name']] = {p[1]: arr[p[1]] for p in el['props']}
            elif len(el['props']) == 1:  # faces: a uniform list of three indices
                arr = np.fromfile(f, dtype=np.dtype([('n', types[lists[0][1]]), ('v', types[lists[0][2]], 3)]), count=el['count'])
                if not (arr['n'] == 3).all(): raise ValueError('non-triangular faces')
                out[el['name']] = {lists[0][3]: arr['v']}
            else:  # scalars mixed with lists: walk the records
                keep = [(i, p) for i, p in enumerate(el['props']) if p[0] != 'list' and p[1] in wanted]
                cols = {p[1]: np.empty(el['count'], dtype=types[p[0]]) for _, p in keep}
                sizes = {k: np.dtype(v).itemsize for k, v in types.items()}
                buf = f.read(); off = 0
                for r in range(el['count']):
                    for p in el['props']:
                        if p[0] == 'list':
                            n = int(np.frombuffer(buf, dtype=types[p[1]], count=1, offset=off)[0]); off += sizes[p[1]] + n * sizes[p[2]]
                        else:
                            if p[1] in cols: cols[p[1]][r] = np.frombuffer(buf, dtype=types[p[0]], count=1, offset=off)[0]
                            off += sizes[p[0]]
                out[el['name']] = cols
        return out


def export_mesh(dense_dir, sim, shift, out_dir, tag):
    """The OpenMVS surface of an anchored fragment in the scene's local metric frame (vertices through the
    anchor similarity plus the frame shift), coloured per vertex from the nearest dense point, written as
    compact binary arrays for the viewer. Returns the published paths and sizes."""
    from scipy.spatial import cKDTree
    dense_dir = Path(dense_dir)
    surface, dense = read_ply(dense_dir / 'surface.ply'), read_ply(dense_dir / 'dense.ply')
    v = np.column_stack([surface['vertex'][k] for k in ('x', 'y', 'z')]).astype(np.float64)
    faces = surface['face']['vertex_indices'].astype(np.uint32)
    d = np.column_stack([dense['vertex'][k] for k in ('x', 'y', 'z')]).astype(np.float64)
    rgb = np.column_stack([dense['vertex'][k] for k in ('red', 'green', 'blue')]).astype(np.uint8)
    _, nearest = cKDTree(d).query(v, k=1)
    s, R, t = sim
    out_dir.mkdir(parents=True, exist_ok=True)
    (s * (v @ R.T) + t + shift).astype(np.float32).tofile(out_dir / f'{tag}-xyz.f32')
    rgb[nearest].tofile(out_dir / f'{tag}-rgb.u8'); faces.tofile(out_dir / f'{tag}-faces.u32')
    return {'xyz_url': f'mesh/{tag}-xyz.f32', 'rgb_url': f'mesh/{tag}-rgb.u8', 'faces_url': f'mesh/{tag}-faces.u32',
            'vertices': int(len(v)), 'faces': int(len(faces)), 'colour': 'per vertex, from the nearest dense point'}


def export_splat(splat_dir, lidar, shift, path, min_opacity=0.05, max_gaussians=600_000, max_scale_m=3.0):
    """A compact `.splat` (32 bytes per Gaussian: position, scale, RGBA, rotation) for the page's splat renderer.
    Only Gaussians inside the lidar's measured volume are kept (the far field, mostly sky, would hang over the
    campus), and so are Gaussians larger than `max_scale_m` along any axis (the blurred fans a splat grows where no
    photograph constrains it, which dominate any view away from the photographers); colour is the view-independent
    term; sorted by opacity and capped at the `max_gaussians` most opaque, so the page loads quickly and `?splats=N`
    loads a meaningful prefix. The scores use every Gaussian; this only shapes what is drawn."""
    import torch
    from ghostmap.evaluate.splat_geometry import classify
    ck = torch.load(Path(splat_dir) / 'ckpt.pt', map_location='cpu')
    means = ck['means'].numpy().astype(np.float64); opacity = torch.sigmoid(ck['opacities']).numpy()
    scales = np.exp(ck['scales'].numpy()); quats = ck['quats'].numpy(); quats = quats / np.linalg.norm(quats, axis=1, keepdims=True)
    rgb = np.clip(0.5 + 0.28209479177387814 * ck['sh0'][:, 0, :].numpy(), 0, 1)
    keep = (opacity >= min_opacity) & (scales.max(1) <= max_scale_m) & (classify(means, lidar) != 'far')
    order = np.argsort(-opacity[keep])[:max_gaussians]
    m, s, c, o, q = means[keep][order] + shift, scales[keep][order], rgb[keep][order], opacity[keep][order], quats[keep][order]
    record = np.zeros(len(m), dtype=[('pos', '<f4', 3), ('scale', '<f4', 3), ('rgba', 'u1', 4), ('rot', 'u1', 4)])
    record['pos'] = m; record['scale'] = s
    record['rgba'] = np.column_stack([c * 255, o * 255]).round().clip(0, 255)
    record['rot'] = (q * 128 + 128).round().clip(0, 255)
    record.tofile(path)
    return int(len(m))


def splat_views(src, dest, url_prefix):
    """The gsplat renderings of a splat (dense/splat_views.py): its photographer poses with the photograph beside each,
    and the fly-through frames, copied for the page. None when they have not been rendered."""
    index = Path(src) / 'index.json'
    if not index.exists(): return None
    ix = json.loads(index.read_text())
    if Path(dest).exists(): shutil.rmtree(dest)
    Path(dest).mkdir(parents=True)
    poses = []
    for p in ix.get('poses', []):
        stem = p.get('stem') or p.get('photo')
        render = p.get('render') or f'pose-{stem}.jpg'; photograph = p.get('photograph') or f'photo-{stem}.jpg'
        if not ((Path(src) / render).exists() and (Path(src) / photograph).exists()): continue
        shutil.copy2(Path(src) / render, Path(dest) / render); shutil.copy2(Path(src) / photograph, Path(dest) / photograph)
        held = p.get('kind') == 'held-out' if 'kind' in p else not p.get('is_training', True)
        poses.append({'photo': stem, 'title': p.get('photo') if p.get('stem') else stem, 'held_out': bool(held), 'psnr': p.get('psnr_fitted', p.get('psnr_here')),
                      'render_url': url_prefix + render, 'photo_url': url_prefix + photograph, 'size': p.get('size')})
    fly = ix.get('fly') or {}
    pattern = fly.get('pattern', 'fly-%03d.jpg'); frames = 0
    for k in range(int(fly.get('frames', 0))):
        f = Path(src) / (pattern % k)
        if not f.exists(): break
        shutil.copy2(f, Path(dest) / f.name); frames += 1
    return {'poses': poses, 'fly': {'frames': frames, 'url_pattern': url_prefix + pattern, 'size': fly.get('size')} if frames else None}


def certificate_summary(path):
    """What the page shows of a fragment's certificate (anchor/georegister.py report)."""
    r = json.loads(Path(path).read_text()); c = r['certificate']; m = r['metrics']
    prof = c.get('profiles', {})
    return {'verdict': c['verdict'], 'failure_mode': c['failure_mode'], 'reasons': c['reasons'], 'scale_fixed_by': c['scale_fixed_by'],
            'scale_uncertainty_relative': c.get('scale_uncertainty_relative'), 'scale_band': c['scale_band'],
            'yaw_contrast': m['yaw']['contrast'], 'cue_scores': {k: v['score_at_optimum'] for k, v in r['cues'].items()},
            'cue_ablation': c['cue_ablation'], 'landmark': r.get('landmark_building'), 'building': r['building'],
            'points_within_1m_of_walls': m['points_within_1m_of_walls'], 'cameras_in_height_band': m['cameras_in_height_band'], 'cameras': m['cameras'],
            'scale_m_per_unit': r['similarity']['scale_m_per_model_unit'],
            'profiles': {k: prof[k] for k in prof if k in ('scale_grid_m_per_unit', 'all', 'only_walls', 'only_roof_edges', 'only_landmark', 'only_camera_height', 'without_landmark', 'without_roof_edges')},
            'report': str(path)}


def build(output=OUT, anchored_runs=None, record_snapshot=None, ground_runs=None, with_splats=True):
    import pycolmap
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
        # A dense textured surface of this fragment, when the dense stage has produced one for its model.
        mesh = None
        for ply in sorted((Path(run) / 'dense').glob('*/surface.ply')):
            dense_report = json.loads((ply.parent / 'report.json').read_text()) if (ply.parent / 'report.json').exists() else {}
            if Path(dense_report.get('model', '')).resolve() != (Path(run) / ref.report['model_path']).resolve(): continue
            sim = (ref.report['similarity']['scale_m_per_model_unit'], np.array(ref.report['similarity']['rotation']),
                   np.array(ref.report['similarity']['translation_utm18n']) - ref.origin)
            mesh = export_mesh(ply.parent, sim, shift, output / 'mesh', tag); mesh['dense_report'] = str(ply.parent / 'report.json')
            break
        # Gaussian splats of this fragment scored against the lidar (dense/splats.py, evaluate/splat_geometry.py): each
        # becomes a compact .splat for the renderer, a layer of its centres coloured by their lidar class, its scores
        # and a few held-out photographs beside their renderings.
        from ghostmap.evaluate.splat_geometry import classify
        lidar_crop = Path(ref.report['lidar_report']).parent
        splats = []
        for geometry in (sorted((Path(run) / 'splats').glob('*/geometry.json')) if with_splats else []):
            splat_report = json.loads((geometry.parent / 'report.json').read_text()) if (geometry.parent / 'report.json').exists() else {}
            if str(splat_report.get('anchor')) != comp or splat_report.get('schema_version', 1) < 2: continue
            g = json.loads(geometry.read_text()); name = geometry.parent.name; key = f'{tag}-{name}'
            (output / 'splats').mkdir(exist_ok=True)
            xyz_g = np.fromfile(geometry.parent / g['viewer_layer']['xyz_url'], dtype=np.float32).reshape(-1, 3) + shift.astype(np.float32)
            xyz_g.tofile(output / 'splats' / f'{key}-geometry.f32'); shutil.copy2(geometry.parent / g['viewer_layer']['rgb_url'], output / 'splats' / f'{key}-geometry.u8')
            shown = export_splat(geometry.parent, lidar_crop, shift, output / 'splats' / f'{key}.splat')
            renders = []
            for jpg in sorted((geometry.parent / 'renders').glob('*.jpg')):
                dest = output / 'splats' / f'{key}-render-{jpg.name}'
                from PIL import Image
                with Image.open(jpg) as im: im.thumbnail((1200, 600)); im.save(dest, quality=85)
                psnr = next((x['psnr'] for x in (splat_report.get('psnr') or {}).get('test', []) if Path(x['image']).stem == jpg.stem), None)
                renders.append({'url': f'splats/{dest.name}', 'photo': jpg.stem, 'psnr': psnr})
            renders.sort(key=lambda r: -(r['psnr'] or 0))   # best-covered held-out view first; every one is listed with its PSNR
            views = splat_views(geometry.parent / 'views', output / 'splats' / f'{key}-views', f'splats/{key}-views/')
            splats.append({'name': name, 'lidar_taught': bool(splat_report.get('lidar_prior')), 'prior': splat_report.get('lidar_prior'), 'views': views,
                           'splat_url': f'splats/{key}.splat', 'splat_gaussians': shown,
                           'xyz_url': f'splats/{key}-geometry.f32', 'rgb_url': f'splats/{key}-geometry.u8', 'colour': g['viewer_layer']['colour'],
                           'gaussians': g['gaussians'], 'free_space': g['free_space'], 'overall': g['overall_distance_to_lidar'],
                           'per_building': {k: {'gaussians': v['gaussians'], 'median_m': v['distance_to_lidar']['median_m'], 'within_1m': v['distance_to_lidar']['within_1m'],
                                                'in_free_air': v.get('in_free_air'), 'coverage': v['coverage_within_1m']} for k, v in g['per_building'].items()},
                           'psnr': splat_report.get('psnr'), 'images': splat_report.get('images'), 'steps': splat_report.get('steps'),
                           'seconds': splat_report.get('seconds'), 'renders': renders, 'geometry_report': str(geometry)})
        splats.sort(key=lambda s: s['lidar_taught'])
        # The fragment before placement: its native COLMAP coordinates (arbitrary scale, orientation and origin) and the
        # similarity that places it, so the page can show it floating and then snapping into the lidar.
        native = pycolmap.Reconstruction(str(Path(run) / ref.report['model_path']))
        native_xyz = np.array([native.points3D[i].xyz for i in ids], dtype=np.float32)
        native_xyz.tofile(output / f'points-{tag}-native.f32')
        native_centres = {im.name: np.asarray(im.projection_center()).round(5).tolist() for im in native.images.values()}
        for p_ in photographers:
            if p_['reconstruction'] == tag: p_['centre_native'] = native_centres.get(p_['name'])
        from scipy.spatial.transform import Rotation as Rot
        S = ref.report['similarity']
        free = classify(xyz.astype(np.float64) - shift, lidar_crop)
        cert_path = Path(run) / 'certificates' / comp / 'report.json'
        placement = {'native_url': f'points-{tag}-native.f32', 'scale': S['scale_m_per_model_unit'],
                     'quaternion_xyzw': Rot.from_matrix(np.array(S['rotation'])).as_quat().tolist(),
                     'translation': (np.array(S['translation_utm18n']) - ref.origin + shift).tolist(),
                     'sparse_points_free_space': {k: float(np.mean(free == k)) for k in ('surface', 'air', 'buried', 'far')},
                     'certificate': certificate_summary(cert_path) if cert_path.exists() else None}
        reconstructions.append({'tag': tag, 'run': str(run), 'anchor_report': str(report), 'intervals_report': str(intervals_path) if intervals else None, 'mesh': mesh, 'splats': splats, 'placement': placement,
                                'points': len(ids), 'dated_photographs': intervals['dated_photographs'] if intervals else None,
                                'xyz_url': f'points-{tag}.f32', 'rgb_url': f'points-{tag}.u8', 'first_url': f'points-{tag}-first.i16', 'last_url': f'points-{tag}-last.i16',
                                'scale_status': ref.report['scale_status'], 'anchored_through': ref.report.get('landmark_building'),
                                'covers': [b for b in (ref.report.get('landmark_building'), ref.report.get('neighbour_building')) if b]})

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

    # The placement study (evaluate/georegistration.py, evaluate/identifiability_sweep.py): every campus fragment's
    # certificate against held-out geotags and against the validated frame, the synthetic identifiability table,
    # and how many of the collection's photographs carry a usable geotag at all.
    study = {}
    geo = ROOT / 'artifacts/georegistration'
    if (geo / 'report.json').exists():
        g = json.loads((geo / 'report.json').read_text())
        study['fragments'] = [{k: f.get(k) for k in ('fragment', 'building', 'cameras', 'geotags', 'verdict', 'failure_mode', 'scale_fixed_by', 'ours_vs_geotags_m', 'geotag_baseline')}
                              | {'run': Path(f['run']).name[:8]} for f in g['fragments']]
        study['agreement_with_validated_frame'] = [a for a in g['cross_fragment_agreement'] if any(x.startswith('6406b8ea') for x in a['fragments'])]
        study['summary'] = g['summary']
        campus = [Path(r) for r in g['runs'] if not Path(r).name.startswith('6406b8ea')]
        if campus and (campus[0] / 'report.json').exists():
            cr = json.loads((campus[0] / 'report.json').read_text())
            study['campus_run'] = {'run': campus[0].name[:8], 'photographs': len(cr.get('input_images', [])),
                                   'registered': len(cr.get('input_images', [])) - len(cr.get('unregistered_images', [])), 'fragments': len(cr.get('components', []))}
    if (geo / 'identifiability.json').exists():
        study['identifiability'] = json.loads((geo / 'identifiability.json').read_text())['rows']
    manifest = ROOT / 'data/artsquad_modern/manifest.json'
    if manifest.exists():
        from ghostmap.evaluate.georegistration import geotags, plausible
        tags = geotags(manifest); images = json.loads(manifest.read_text())['images']
        study['geotags'] = {'photographs': len(images), 'with_gps': len(tags), 'plausible': sum(1 for v in tags.values() if plausible(v))}

    scene = {'schema_version': 2, 'title': 'GhostMap', 'generated_utc': datetime.now(timezone.utc).isoformat(), 'placement_study': study,
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
    parser.add_argument('--without-splats', action='store_true', help='leave the Gaussian splats out (while they are still training)')
    args = parser.parse_args()
    s = build(args.output, args.run, args.snapshot, args.ground_run, with_splats=not args.without_splats)
    print(len(s['sites']), 'sites,', len(s['buildings']), 'buildings,', sum(r['points'] for r in s['reconstructions']), 'points,', len(s['photographers']), 'photographers')


if __name__ == '__main__': main()
