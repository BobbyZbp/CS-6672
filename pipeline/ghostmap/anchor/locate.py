#!/usr/bin/env python3
"""Place a new photograph in a certified fragment's world frame: where the photographer stood, which way
they looked, in metres on the campus, without GPS.

COLMAP registers a new photograph only into its own arbitrary frame. Here the reference is the fragment's
anchored model (the local metres of the lidar crop, `anchor/georegister.py`), so the same registration lands
on the map. Steps (hloc on the GPU, the reconstruction's own feature configuration):

1. SuperPoint keypoints and a NetVLAD descriptor of the photograph;
2. the RETRIEVE photographs of the fragment most similar by NetVLAD, and LightGlue matches to them;
3. the 3D points behind the matched keypoints, and an absolute pose by RANSAC (pycolmap). The focal length
   of an internet photograph is unknown, so the pose is estimated from several focal priors (EXIF when there
   is one, and fractions of the image size) and refined with the focal length free; the most inliers win;
4. a long lens trades focal length against distance, and matches only on a distant tower barely fix it, so the
   poses reached from the other focal priors with at least 70 % of the best's inliers measure how far the camera
   can slide: their centres, as a segment, are the distance's uncertainty. (Holding the photographer at
   eye height over the lidar ground to fix it was tried and made leave-one-out much worse: the reconstruction's
   own cameras sit metres off eye height, and the photograph is matched against them.)
5. a certificate: placed; placed with the distance uncertain (the direction is fixed, the camera lies somewhere
   on the stated segment, and a photograph projected from anywhere on it lands on the same walls); or refused
   with the reason (too few inliers, an impossible focal length, the photographer under the ground everywhere
   along the segment). The thresholds were set on leave-one-out over 40
   photographs and checked on all 88 (`<run>/locate/leave-one-out/report.json`).

Checks that need no ground truth: the lidar-taught splat rendered from the found pose and compared with the
photograph (PSNR after a colour fit, as for held-out photographs; a wrong pose renders the wrong place).
Leave-one-out (`--leave-one-out N`): a registered photograph is taken out of the reference model, placed again
from scratch, and compared with where the reconstruction had it.

Outputs `<run>/locate/<stem>/report.json` and `photo-vs-splat.jpg`.

Usage: PYTHONPATH=pipeline python -m ghostmap.anchor.locate --run <run> [--anchor 0] photo.jpg [...]
       PYTHONPATH=pipeline python -m ghostmap.anchor.locate --run <run> --left-out <run>/images/<photograph in it> [...]
       PYTHONPATH=pipeline python -m ghostmap.anchor.locate --run <run> --leave-one-out 12
"""
from __future__ import annotations

import argparse
import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

LOCAL_FEATURES = {'output': 'feats-superpoint-n4096-r1200', 'model': {'name': 'superpoint', 'nms_radius': 3, 'max_keypoints': 4096},
                  'preprocessing': {'grayscale': True, 'resize_max': 1200}}
RETRIEVE = 10
RANSAC_PX = 12.0
FOCAL_PRIORS = (0.7, 1.0, 1.4, 2.0)          # times the longer image side, besides the EXIF focal length
MIN_INLIERS, MIN_INLIER_SHARE = 40, 0.15
FOCAL_RANGE = (0.4, 6.0)                      # plausible focal lengths, times the longer image side
LOWEST_M = -6.0                               # a photographer more than this under the lidar ground is a wrong pose
UNCERTAIN_M = 25.0                            # a valley longer than this: the direction is placed, the distance is not
VALLEY_SHARE = 0.7                            # poses from other focal priors keeping this share of the best's inliers
SPLAT = 'tower-and-library-lidar-taught'


class Reference:
    """A fragment's anchored model with its features, descriptors and lidar ground, ready to place photographs."""

    def __init__(self, run, anchor='0'):
        import pycolmap
        from ghostmap.anchor.lidar import fill_nearest
        self.run = Path(run).resolve(); self.anchor = str(anchor)
        self.report = json.loads((self.run / 'anchor' / self.anchor / 'report.json').read_text())
        if not self.report.get('metric_frame_usable'): raise ValueError('the fragment has no usable frame to place photographs in')
        self.model = pycolmap.Reconstruction(self.report['anchored_model'])
        self.origin = np.asarray(self.report['local_frame']['origin_utm18n'])
        rasters = np.load(Path(self.report['lidar_report']).parent / 'quad-rasters-utm18n.npz')
        self.box, self.cell, self.ground = tuple(rasters['box']), float(rasters['cell']), fill_nearest(rasters['ground'])
        self.features = self.run / f"{LOCAL_FEATURES['output']}.h5"; self.descriptors = self.run / 'global-feats-netvlad.h5'
        self.names = sorted(im.name for im in self.model.images.values())

    def height_over_ground(self, centre):
        from ghostmap.anchor.align import raster_lookup
        return float(centre[2] - raster_lookup(self.ground, self.box, self.cell, (np.asarray(centre[:2]) + self.origin[:2])[None])[0])

    def inside_building(self, centre):
        from ghostmap.anchor.align import InsideMask, FOOTPRINTS
        if not hasattr(self, '_inside'):
            rings = [b['ring'] for b in json.loads(Path(FOOTPRINTS).read_text())['buildings']]
            self._inside = InsideMask(rings, self.box, self.cell)
        return bool(self._inside((np.asarray(centre[:2]) + self.origin[:2])[None])[0])


def describe(photos, work):
    """SuperPoint keypoints and NetVLAD descriptors of the photographs (copied into `work/images` as given names)."""
    from hloc import extract_features
    names = [p.name for p in photos]
    local = extract_features.main(LOCAL_FEATURES, work / 'images', image_list=names, feature_path=work / 'feats-query.h5', as_half=False, overwrite=True)
    glob = extract_features.main(extract_features.confs['netvlad'], work / 'images', image_list=names, feature_path=work / 'global-query.h5', overwrite=True)
    return local, glob


def match(ref, names, work, db_names=None):
    """Retrieval among the fragment's photographs, then LightGlue matches to the retrieved ones."""
    from hloc import match_features, pairs_from_retrieval
    pairs = work / 'pairs-query.txt'
    pairs_from_retrieval.main(work / 'global-query.h5', pairs, RETRIEVE, query_list=names, db_list=db_names or ref.names, db_descriptors=ref.descriptors)
    matches = work / 'matches-query.h5'
    if matches.exists(): matches.unlink()
    match_features.main(match_features.confs['superpoint+lightglue'], pairs, work / 'feats-query.h5', matches=matches, features_ref=ref.features, overwrite=True)
    from hloc.utils.parsers import parse_retrieval
    return parse_retrieval(pairs), matches


def pose(ref, model, name, photo, retrieved, work, matches):
    """The pose of the photograph, or None: the best over a few focal priors, each refined with the focal length free.
    The poses the other priors reach with at least 70 % of the best's inliers measure how well the distance is fixed:
    a long lens trades focal length against distance, and a distant tower alone barely fixes it. Their camera centres,
    as a segment, are the distance's uncertainty."""
    import pycolmap
    from hloc.localize_sfm import QueryLocalizer, pose_from_cluster
    by_name = {im.name: i for i, im in model.images.items()}
    db_ids = [by_name[n] for n in retrieved if n in by_name]
    exif = pycolmap.infer_camera_from_image(str(photo))   # EXIF focal length when the photograph has one
    w, h = exif.width, exif.height; side = max(w, h)
    def solve(f, refine_focal):
        localizer = QueryLocalizer(model, {'estimation': {'ransac': {'max_error': RANSAC_PX}},
                                           'refinement': {'refine_focal_length': refine_focal, 'refine_extra_params': refine_focal}})
        cam = pycolmap.Camera(model='SIMPLE_RADIAL', width=w, height=h, params=[f, w / 2, h / 2, 0.0])
        ret, log = pose_from_cluster(localizer, name, cam, db_ids, work / 'feats-query.h5', matches)
        if ret is None: return None
        R = ret['cam_from_world'].rotation.matrix(); c = -R.T @ np.asarray(ret['cam_from_world'].translation)
        return {'ret': ret, 'log': log, 'inliers': int(ret['num_inliers']), 'centre': c, 'height': ref.height_over_ground(c), 'focal': float(ret['camera'].params[0])}
    priors = [('EXIF or default', float(exif.params[0]))] + [(f'{k:g} x image side', k * side) for k in FOCAL_PRIORS]
    found = [(label, s) for label, s in ((label, solve(f, True)) for label, f in priors) if s is not None]
    if not found: return None
    label, best = max(found, key=lambda x: x[1]['inliers'])
    valley = [s for _, s in found if s['inliers'] >= VALLEY_SHARE * best['inliers']]
    extent = float(max(np.linalg.norm(a['centre'] - best['centre']) for a in valley))
    info = {'focal_prior': label, 'valley_m': extent,
            'priors': [{'prior': l, 'focal_over_side': s['focal'] / side, 'inliers': s['inliers'], 'height_m': s['height']} for l, s in found]}
    # The near-best poses as a segment of possible camera centres, ordered along its longest direction.
    C = np.array([s['centre'] for s in valley]); axis = np.linalg.svd(C - C.mean(0))[2][0] if len(C) > 1 else np.zeros(3)
    order = np.argsort((C - C.mean(0)) @ axis)
    info['segment'] = [{'centre_local_m': C[i].tolist(), 'height_m': valley[i]['height']} for i in (order[0], order[-1])]
    return best['ret'], best['log'], label, info


def segment_distance(point, segment):
    """Distance from a point to the segment of possible camera centres (a single centre when the segment is one point)."""
    if not segment: return None
    a, b = (np.asarray(s['centre_local_m']) for s in segment); d = b - a
    u = 0.0 if not d.any() else float(np.clip((point - a) @ d / (d @ d), 0, 1))
    return float(np.linalg.norm(point - (a + u * d)))


def certify(ref, ret, log, image_size, info=None):
    """Placed, or refused with the reason; and what the pose says."""
    reasons, info = [], info or {}
    if ret is None: return {'verdict': 'refused', 'reasons': ['no pose: the photograph shares too few features with the fragment']}, None
    cfw = ret['cam_from_world']; R = cfw.rotation.matrix(); t = np.asarray(cfw.translation); centre = -R.T @ t
    cam = ret['camera']; f = float(cam.params[0]); side = max(image_size)
    inliers = int(ret['num_inliers']); share = inliers / max(len(log['points3D_ids']), 1)
    height = ref.height_over_ground(centre); inside = ref.inside_building(centre)
    if inliers < MIN_INLIERS: reasons.append(f'only {inliers} correspondences agree on a pose (at least {MIN_INLIERS} needed): the photograph shows little of what the fragment saw')
    if share < MIN_INLIER_SHARE: reasons.append(f'only {100 * share:.0f} % of the matched points agree on the pose')
    if not FOCAL_RANGE[0] <= f / side <= FOCAL_RANGE[1]: reasons.append(f'the focal length came out at {f / side:.2f} times the image side, not a camera')
    valley = info.get('valley_m', 0.0); segment = info.get('segment') or []
    uncertain = valley > UNCERTAIN_M
    if height < LOWEST_M:
        if uncertain and any(s['height_m'] >= LOWEST_M for s in segment): uncertain = True   # somewhere along the segment the photographer stands above ground
        else: reasons.append(f'the photographer would stand {-height:.0f} m under the lidar ground')
    notes = []
    if uncertain and not reasons:
        notes.append(f'the direction is placed, the distance is not: poses {valley:.0f} m apart along the line of sight fit the photograph almost equally well (a long lens on a distant building)')
    elif height > 6 and not reasons: notes.append('taken from above the ground: a window, a roof or the tower')
    if inside and not uncertain: notes.append('inside a building footprint: a window or a doorway')
    fwd = R[2]
    out = {'valley_m': valley, 'segment': segment, 'centre_local_m': centre.tolist(), 'centre_utm18n': (centre + ref.origin).tolist(),
           'cam_from_world_rotation': R.tolist(), 'heading_deg': float(np.degrees(np.arctan2(fwd[1], fwd[0]))), 'pitch_deg': float(np.degrees(np.arcsin(np.clip(fwd[2], -1, 1)))),
           'focal_px': f, 'focal_over_side': f / side, 'height_over_lidar_ground_m': height, 'inside_a_footprint': inside,
           'inliers': inliers, 'correspondences': int(len(log['points3D_ids'])), 'inlier_share': share, 'retrieved': len(log['db'])}
    return {'verdict': 'refused' if reasons else ('placed, distance uncertain' if uncertain else 'placed'), 'reasons': reasons, 'notes': notes}, out


def render_check(ref, photo, placed, out_dir, splat=SPLAT, width=960):
    """The lidar-taught splat from the found pose beside the photograph; PSNR after a colour fit."""
    import torch
    from PIL import Image
    from ghostmap.dense.splat_views import fit_colours, load_splat, render, to_u8
    path = ref.run / 'splats' / splat
    if not (path / 'ckpt.pt').exists(): return None
    device = 'cuda'
    with Image.open(photo) as im: im = im.convert('RGB'); W0, H0 = im.size; s = width / W0; h = int(round(H0 * s / 2)) * 2
    img = torch.tensor(np.asarray(im.resize((width, h), Image.Resampling.LANCZOS)), dtype=torch.float32, device=device) / 255
    V = np.eye(4); R = np.asarray(placed['cam_from_world_rotation']); V[:3, :3] = R; V[:3, 3] = -R @ np.asarray(placed['centre_local_m'])
    f = placed['focal_px'] * s
    K = torch.tensor([[f, 0, width / 2], [0, f, h / 2], [0, 0, 1]], dtype=torch.float32, device=device)
    sky = img[: max(1, h // 20)].reshape(-1, 3).median(0).values
    g = load_splat(path, device)
    fitted, psnr = fit_colours(render(g, torch.tensor(V, dtype=torch.float32, device=device), K, width, h, device, sky), img)
    Image.fromarray(np.concatenate([to_u8(img), to_u8(fitted)], 1)).save(out_dir / 'photo-vs-splat.jpg', quality=88)
    del g; torch.cuda.empty_cache()
    return {'splat': splat, 'psnr_fitted_db': psnr, 'image': 'photo-vs-splat.jpg'}


def locate(run, photos, anchor='0', render=True, ref=None, left_out=False, out_root=None):
    """Place each photograph; reports under `<run>/locate/<stem>/`. With `left_out`, the photographs are ones the
    reconstruction holds: each is first taken out of the reference model (its observations removed, and it is not
    a retrieval candidate), so it is placed from scratch, and the report says how far it lands from where the
    reconstruction had it."""
    ref = ref or Reference(run, anchor)
    work = ref.run / 'locate' / 'work'; shutil.rmtree(work, ignore_errors=True); (work / 'images').mkdir(parents=True)
    photos = [Path(p) for p in photos]; staged = []
    for p in photos:
        q = work / 'images' / ('query__' + p.name); shutil.copy2(p, q); staged.append(q)
    t0 = time.time(); describe(staged, work)
    if not left_out: retrieval, matches = match(ref, [q.name for q in staged], work)
    t_match = time.time() - t0
    results = {}
    for p, q in zip(photos, staged):
        t1 = time.time(); model, truth = ref.model, None
        if left_out:
            import pycolmap
            model = pycolmap.Reconstruction(ref.report['anchored_model'])
            image = next(x for x in model.images.values() if x.name == p.name); truth = np.asarray(image.projection_center())
            model.deregister_frame(image.frame_id)
            retrieval, matches = match(ref, [q.name], work, db_names=[n for n in ref.names if n != p.name])
        best = pose(ref, model, q.name, q, retrieval.get(q.name, []), work, matches)
        from PIL import Image
        with Image.open(p) as im: size = im.size
        verdict, placed = certify(ref, *(best[:2] if best else (None, None)), size, best[3] if best else None)
        out = Path(out_root or ref.run / 'locate') / p.stem; out.mkdir(parents=True, exist_ok=True)
        report = {'schema_version': 1, 'created_utc': datetime.now(timezone.utc).isoformat(), 'photo': str(p), 'run': str(ref.run), 'anchor': ref.anchor,
                  'frame': ref.report['local_frame'], 'certificate': verdict, 'pose': placed, 'focal_prior': best[2] if best else None,
                  'seconds': {'features_and_matches_per_photo': t_match / len(photos), 'pose': time.time() - t1},
                  'rule': f'NetVLAD retrieval of {RETRIEVE} photographs of the fragment, SuperPoint + LightGlue, RANSAC absolute pose ({RANSAC_PX:g} px) from {len(FOCAL_PRIORS) + 1} focal priors, refined with the focal length free; '
                          f'placed with at least {MIN_INLIERS} inliers, {100 * MIN_INLIER_SHARE:.0f} % of the correspondences, a focal length of {FOCAL_RANGE[0]}-{FOCAL_RANGE[1]} image sides, and the photographer no more than {-LOWEST_M:.0f} m under the lidar ground'}
        if left_out:
            report['left_out_of_reconstruction'] = True
            report['reconstruction_pose_error_m'] = float(np.linalg.norm(np.asarray(placed['centre_local_m']) - truth)) if placed else None
        if render and placed is not None and verdict['verdict'].startswith('placed'): report['splat_check'] = render_check(ref, p, placed, out)
        (out / 'report.json').write_text(json.dumps(report, indent=1) + '\n')
        results[p.name] = report
    return results


def leave_one_out(run, count=12, anchor='0', seed=0):
    """Take registered photographs out of the reference model one at a time, place them again from scratch, and
    compare with where the reconstruction had them."""
    import pycolmap
    ref = Reference(run, anchor)
    images = sorted(ref.model.images.values(), key=lambda im: im.name)
    pick = [images[i] for i in np.random.default_rng(seed).choice(len(images), min(count, len(images)), replace=False)]
    work = ref.run / 'locate' / 'leave-one-out'; shutil.rmtree(work, ignore_errors=True); (work / 'images').mkdir(parents=True)
    staged = []
    for im in pick:
        q = work / 'images' / ('query__' + im.name); shutil.copy2(ref.run / 'images' / im.name, q); staged.append(q)
    describe(staged, work)
    rows = []
    for im, q in zip(pick, staged):
        model = pycolmap.Reconstruction(ref.report['anchored_model'])
        image = next(x for x in model.images.values() if x.name == im.name)
        model.deregister_frame(image.frame_id)   # its observations leave the model's tracks
        retrieval, matches = match(ref, [q.name], work, db_names=[n for n in ref.names if n != im.name])
        best = pose(ref, model, q.name, q, retrieval.get(q.name, []), work, matches)
        from PIL import Image
        with Image.open(q) as pil: size = pil.size
        verdict, placed = certify(ref, *(best[:2] if best else (None, None)), size, best[3] if best else None)
        truth = np.asarray(im.projection_center())
        # The reconstruction's own pose is the reference only when it passes the same plausibility test (COLMAP can
        # register a photograph kilometres away on a handful of points).
        reference_ok = sum(1 for x in im.points2D if x.has_point3D()) >= MIN_INLIERS and ref.height_over_ground(truth) >= LOWEST_M
        row = {'photo': im.name, 'verdict': verdict['verdict'], 'reasons': verdict['reasons'], 'reference_plausible': bool(reference_ok)}
        if placed:
            Rt = im.cam_from_world().rotation.matrix(); Rq = np.asarray(placed['cam_from_world_rotation'])
            row.update({'position_error_m': float(np.linalg.norm(np.asarray(placed['centre_local_m']) - truth)),
                        'rotation_error_deg': float(np.degrees(np.arccos(np.clip((np.trace(Rq @ Rt.T) - 1) / 2, -1, 1)))),
                        'inliers': placed['inliers'], 'inlier_share': placed['inlier_share'], 'height_m': placed['height_over_lidar_ground_m'],
                        'valley_m': placed['valley_m'], 'focal_over_side': placed['focal_over_side'],
                        'truth_to_segment_m': segment_distance(truth, placed['segment'])})
        rows.append(row); print(json.dumps(row), flush=True)
    scored = [r for r in rows if r['reference_plausible']]; placed = [r for r in scored if r['verdict'] == 'placed']
    loose = [r for r in scored if r['verdict'] == 'placed, distance uncertain']
    err = np.array([r['position_error_m'] for r in placed]) if placed else np.zeros(0)
    refused = [r for r in scored if r['verdict'] == 'refused' and 'position_error_m' in r]
    summary = {'photographs': len(rows), 'with_a_plausible_reference_pose': len(scored), 'placed': len(placed), 'refused': sum(1 for r in scored if r['verdict'] == 'refused'),
               'placed_position_error_m': {'median': float(np.median(err)), 'p75': float(np.percentile(err, 75)), 'p90': float(np.percentile(err, 90)), 'max': float(err.max()),
                                           'over_10m': int((err > 10).sum()), 'over_25m': int((err > 25).sum())} if len(err) else None,
               'placed_rotation_error_deg_median': float(np.median([r['rotation_error_deg'] for r in placed])) if placed else None,
               'refused_position_error_m_median': float(np.median([r['position_error_m'] for r in refused])) if refused else None,
               'placed_distance_uncertain': len(loose),
               'distance_uncertain_truth_to_segment_m': {'median': float(np.median([r['truth_to_segment_m'] for r in loose])), 'max': float(max(r['truth_to_segment_m'] for r in loose))} if loose else None,
               'distance_uncertain_rotation_error_deg_median': float(np.median([r['rotation_error_deg'] for r in loose])) if loose else None}
    (work / 'report.json').write_text(json.dumps({'created_utc': datetime.now(timezone.utc).isoformat(), 'summary': summary, 'rows': rows}, indent=1) + '\n')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--anchor', default='0')
    parser.add_argument('--leave-one-out', type=int, default=0, help='place this many registered photographs again with each one left out')
    parser.add_argument('--no-render', action='store_true')
    parser.add_argument('--left-out', action='store_true', help='the photographs are in the reconstruction: take each out first, then place it')
    parser.add_argument('photos', nargs='*', type=Path)
    args = parser.parse_args()
    if args.leave_one_out:
        print(json.dumps(leave_one_out(args.run, args.leave_one_out, args.anchor), indent=1)); return
    for name, r in locate(args.run, args.photos, args.anchor, render=not args.no_render, left_out=args.left_out).items():
        c, p = r['certificate'], r['pose'] or {}
        print(json.dumps({'photo': name, 'verdict': c['verdict'], 'reasons': c['reasons'], 'notes': c.get('notes'), 'inliers': p.get('inliers'),
                          'height_m': p.get('height_over_lidar_ground_m'), 'focal_over_side': p.get('focal_over_side'),
                          'splat_psnr': (r.get('splat_check') or {}).get('psnr_fitted_db'), 'seconds': r['seconds']}))


if __name__ == '__main__': main()
