#!/usr/bin/env python3
"""Offline renders of a fragment's splats for the page, the slides and the fallback video (gsplat, GPU).

A splat is only trustworthy near the views it was trained from, and the browser renderer smears
Gaussians close to the camera, so the page and the slides show gsplat's own renders:

- **photographer poses** (`views/pose-<stem>.jpg` beside `views/photo-<stem>.jpg`): the exact pose and
  focal length of a registered photograph; the rendering's colour map and background are fitted to that
  photograph by least squares, the background is the photograph's own sky (the median of its top rows),
  as in the held-out PSNR of `dense/splats.py`, and the PSNR after the fit is recorded. The first pose is the best-covered held-out photograph, the honest test.
- **a fly-through** (`views/fly-<kkk>.jpg`): the training photographers facing the landmark, sorted by
  heading around it, with centres, rotations (slerp) and focal lengths interpolated between them; raw
  colours on a sky background, since no photograph exists between them. The same poses and path for
  every splat, so plain and lidar-taught frames line up. The same frames again with every Gaussian
  painted by the lidar's verdict on it (`views/fly-verdict-<kkk>.jpg`: red in air the lidar saw empty,
  purple under the bare ground, natural colour on surfaces, as `evaluate/splat_geometry.py` classifies),
  and per frame the camera's centre and heading and the distance to the nearest training photographer,
  so the page can show where on the path the camera is and how far it is from any photograph.
- **a walk** for the slides and the video: an eased arc around the landmark at the photographers' median
  distance and eye height, plain and lidar-taught side by side, frame for frame
  (`artifacts/presentation/splat-walk-plain-vs-lidar-taught.mp4`, its middle frame as a still), and the
  fly-through frame where the lidar's verdict separates the two most, side by side.

Each splat's `views/index.json` lists what was rendered (file names relative to `views/`). Splats live in
the lidar frame, so every view is a pose in the same metres as the lidar.

Usage: CUDA_HOME=... PYTHONPATH=pipeline python -m ghostmap.dense.splat_views [--run <run>] [--anchor 0] [--fly-frames 90] [--walk-frames 240]
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from ghostmap.paths import ROOT

STILLS = ROOT / 'dist/assets/presentation'
VIDEOS = ROOT / 'artifacts/presentation'
SPLATS = ('tower-and-library', 'tower-and-library-lidar-taught')
POSES = ('6333253_Cornell_McGraw_Tower_and_Uris_Library', '6333256_Cornell_McGraw_Tower_and_Uris_Library', '69219260_Cornell_s_McGraw_Tower', '16963770_UrisLibrary')
SKY = (0.70, 0.78, 0.86)
WIDTH = 960
PARAMS = ('means', 'quats', 'scales', 'opacities', 'sh0', 'shN')


def load_splat(path, device):
    import torch
    ck = torch.load(Path(path) / 'ckpt.pt', map_location='cpu')
    return {k: ck[k].to(device) for k in PARAMS}


def render(splat, viewmat, K, width, height, device, background=SKY, rgb=None):
    """Float image (H, W, 3) in [0, 1]; `rgb` (N, 3) replaces the splat's own view-dependent colours."""
    import torch
    from gsplat import rasterization
    colors, degree = (rgb, None) if rgb is not None else (torch.cat([splat['sh0'], splat['shN']], 1), 3)
    bg = background if hasattr(background, 'shape') else torch.tensor(background, device=device)
    with torch.no_grad():
        img, _, _ = rasterization(splat['means'], splat['quats'] / splat['quats'].norm(dim=-1, keepdim=True), torch.exp(splat['scales']),
                                  torch.sigmoid(splat['opacities']), colors, viewmat[None], K[None], width, height, sh_degree=degree, packed=False,
                                  backgrounds=bg.reshape(1, 3).float())
    return img[0].clamp(0, 1)


VERDICT_RGB = {'air': (0.88, 0.16, 0.14), 'buried': (0.55, 0.25, 0.75)}


def verdict_colours(splat, lidar_dir, device):
    """Each Gaussian's base colour, replaced by red in air the lidar saw empty and purple under the bare ground."""
    import torch
    from ghostmap.evaluate.splat_geometry import classify
    label = classify(splat['means'].cpu().numpy().astype(np.float64), lidar_dir)
    rgb = np.clip(splat['sh0'][:, 0, :].cpu().numpy() * 0.28209479177387814 + 0.5, 0, 1)
    for name, colour in VERDICT_RGB.items(): rgb[label == name] = colour
    return torch.tensor(rgb, dtype=torch.float32, device=device), {k: int((label == k).sum()) for k in ('surface', 'air', 'buried', 'far')}


def fit_colours(img, photo):
    """Least-squares affine colour map from the rendering to the photograph; the mapped rendering and its PSNR."""
    import torch
    X = torch.cat([img.reshape(-1, 3), torch.ones(img.shape[0] * img.shape[1], 1, device=img.device)], 1)
    M = torch.linalg.lstsq(X, photo.reshape(-1, 3)).solution
    pred = (X @ M).reshape(img.shape).clamp(0, 1)
    return pred, float(10 * torch.log10(1 / ((pred - photo) ** 2).mean()))


def to_u8(x):
    return (x.cpu().numpy() * 255).round().astype(np.uint8)


def camera_of(image, model, width=WIDTH):
    """World-to-camera matrix, intrinsics scaled to `width`, and the matching even height."""
    cam = model.cameras[image.camera_id]; s = width / cam.width; h = int(round(cam.height * s / 2)) * 2
    fx, fy, cx, cy = (cam.params[0], cam.params[0], cam.params[1], cam.params[2]) if cam.model.name == 'SIMPLE_PINHOLE' else tuple(cam.params[:4])
    V = np.eye(4); V[:3, :3] = image.cam_from_world().rotation.matrix(); V[:3, 3] = image.cam_from_world().translation
    return V, np.array([[fx * s, 0, cx * s], [0, fy * s, cy * s], [0, 0, 1]]), h


def look_at(centre, target):
    f = target - centre; f /= np.linalg.norm(f)
    r = np.cross(f, [0, 0, 1.0]); r /= np.linalg.norm(r)
    R = np.vstack([r, np.cross(f, r), f]); V = np.eye(4); V[:3, :3] = R; V[:3, 3] = -R @ centre
    return V


def landmark_centre(anchor_report):
    """The landmark footprint's centroid in the anchor's local metres."""
    name = anchor_report.get('landmark_building') or 'McGraw Tower'
    b = next(x for x in json.loads((ROOT / 'data/footprints/buildings-utm18n.json').read_text())['buildings'] if x['name'] == name)
    return np.asarray(b['ring'])[:-1].mean(0) - np.asarray(anchor_report['local_frame']['origin_utm18n'][:2])


def fly_path(model, centre_xy, holdout, frames, count=7):
    """Training photographers facing the landmark, sorted by heading around it, interpolated into `frames` views."""
    from scipy.spatial.transform import Rotation, Slerp
    rows = []
    for im in model.images.values():
        if im.name in holdout: continue
        C = np.asarray(im.projection_center()); d = C[:2] - centre_xy
        fwd = im.cam_from_world().rotation.matrix()[2]   # the camera's viewing direction in the world
        facing = float(-(d / np.linalg.norm(d)) @ (fwd[:2] / max(np.linalg.norm(fwd[:2]), 1e-9)))
        n = sum(1 for p in im.points2D if p.has_point3D())
        if facing > 0.9 and 30 < np.linalg.norm(d) < 160: rows.append((n, float(np.arctan2(d[1], d[0])), im))
    rows = sorted(rows, key=lambda r: -r[0])[:count]
    rows.sort(key=lambda r: r[1])
    keys = [r[2] for r in rows]
    Vs, Ks = zip(*[camera_of(im, model)[:2] for im in keys])
    Rs = Rotation.from_matrix([V[:3, :3] for V in Vs]); Cs = np.array([-V[:3, :3].T @ V[:3, 3] for V in Vs]); fs = np.array([K[0, 0] for K in Ks])
    slerp = Slerp(np.arange(len(keys)), Rs); out = []
    for x in np.linspace(0, len(keys) - 1, frames):
        i = min(int(x), len(keys) - 2); t = x - i
        R = slerp([x]).as_matrix()[0]; C = (1 - t) * Cs[i] + t * Cs[i + 1]; f = (1 - t) * fs[i] + t * fs[i + 1]
        V = np.eye(4); V[:3, :3] = R; V[:3, 3] = -R @ C
        out.append((V, f))
    return out, [im.name for im in keys], [float(k) * (frames - 1) / (len(keys) - 1) for k in range(len(keys))]


def verdict_still(splats_dir, names, frames):
    """The fly-through frame where the lidar's verdict separates the splats most (share of pixels painted red or purple,
    first splat minus second), side by side, for the slides (`verdict-plain-vs-lidar-taught.jpg`)."""
    from PIL import Image
    def flagged(name, k):
        x = np.asarray(Image.open(Path(splats_dir) / name / 'views' / f'fly-verdict-{k:03d}.jpg').convert('RGB')).astype(float) / 255
        return float(np.mean([(np.abs(x - c).max(-1) < 0.12).mean() for c in VERDICT_RGB.values()]) * len(VERDICT_RGB))
    shares = [(flagged(names[0], k), flagged(names[1], k)) for k in range(frames)]
    k = int(np.argmax([a - b for a, b in shares]))
    pair = [Image.open(Path(splats_dir) / n / 'views' / f'fly-verdict-{k:03d}.jpg').convert('RGB') for n in names]
    out = Image.new('RGB', (pair[0].width * 2 + 12, pair[0].height), (255, 255, 255))
    out.paste(pair[0], (0, 0)); out.paste(pair[1], (pair[0].width + 12, 0))
    out.save(STILLS / 'verdict-plain-vs-lidar-taught.jpg', quality=90)
    return {'frame': k, 'flagged_pixels': {names[0]: round(shares[k][0], 3), names[1]: round(shares[k][1], 3)},
            'mean_flagged_pixels': {n: round(float(np.mean([s[j] for s in shares])), 3) for j, n in enumerate(names)}}


def title(name):
    return name.replace('modern__', '').rsplit('.', 1)[0].replace('_', ' ')


def run(run_path, anchor='0', names=SPLATS, fly_frames=90, walk_frames=240, device='cuda'):
    import imageio.v2 as imageio
    import pycolmap
    import torch
    from PIL import Image
    run_path = Path(run_path).resolve(); STILLS.mkdir(parents=True, exist_ok=True); VIDEOS.mkdir(parents=True, exist_ok=True)
    anchor_report = json.loads((run_path / 'anchor' / str(anchor) / 'report.json').read_text())
    model = pycolmap.Reconstruction(str(run_path / 'splats' / f'undistorted-{anchor}' / 'sparse'))
    image_dir = run_path / 'splats' / f'undistorted-{anchor}' / 'images'
    holdout = set(sorted(im.name for im in model.images.values())[::12])   # the trainer holds out every twelfth by name
    centre_xy = landmark_centre(anchor_report)
    path, fly_keys, key_frames = fly_path(model, centre_xy, holdout, fly_frames)
    fly_h = int(round(WIDTH * 0.75 / 2)) * 2
    # Where the camera is on every frame, and how far from the nearest photographer the splat was trained on.
    trained = np.array([im.projection_center() for im in model.images.values() if im.name not in holdout])
    cameras = []
    for V, f in path:
        C = -V[:3, :3].T @ V[:3, 3]; fwd = V[2, :3]
        cameras.append({'centre': [round(float(v), 2) for v in C], 'heading_deg': round(float(np.degrees(np.arctan2(fwd[1], fwd[0]))), 1),
                        'fov_deg': round(float(2 * np.degrees(np.arctan(WIDTH / 2 / f))), 1), 'nearest_photographer_m': round(float(np.linalg.norm(trained - C, axis=1).min()), 1)})
    keys = [{'frame': round(k, 2), 'photo': title(n), 'image': n, 'centre': [round(float(v), 2) for v in next(im for im in model.images.values() if im.name == n).projection_center()]}
            for k, n in zip(key_frames, fly_keys)]
    lidar_dir = Path(anchor_report['lidar_report']).parent
    summary = {}
    for name in names:
        splat = load_splat(run_path / 'splats' / name, device)
        views = run_path / 'splats' / name / 'views'; views.mkdir(exist_ok=True)
        index = {'schema_version': 1, 'created_utc': datetime.now(timezone.utc).isoformat(), 'splat': name, 'background': SKY, 'poses': [], 'fly': None}
        for key in POSES:
            image = next((im for im in model.images.values() if key in im.name), None)
            if image is None: continue
            V, K, h = camera_of(image, model); stem = key.split('_')[0]
            photo = torch.tensor(np.asarray(Image.open(image_dir / image.name).convert('RGB').resize((WIDTH, h), Image.Resampling.LANCZOS)), dtype=torch.float32, device=device) / 255
            sky = photo[: max(1, h // 20)].reshape(-1, 3).median(0).values   # the photograph's own sky, as in the trainer's held-out protocol
            img = render(splat, torch.tensor(V, dtype=torch.float32, device=device), torch.tensor(K, dtype=torch.float32, device=device), WIDTH, h, device, sky)
            fitted, psnr = fit_colours(img, photo)
            Image.fromarray(to_u8(fitted)).save(views / f'pose-{stem}.jpg', quality=90)
            Image.fromarray(to_u8(photo)).save(views / f'photo-{stem}.jpg', quality=90)
            # The slides use the same files (dist/assets/presentation/view-<stem>-photo.jpg and -<splat>.jpg).
            Image.fromarray(to_u8(fitted)).save(STILLS / f'view-{stem}-{name}.jpg', quality=90)
            Image.fromarray(to_u8(photo)).save(STILLS / f'view-{stem}-photo.jpg', quality=90)
            index['poses'].append({'stem': stem, 'photo': title(image.name), 'image': image.name, 'psnr_fitted': psnr, 'is_training': image.name not in holdout,
                                   'render': f'pose-{stem}.jpg', 'photograph': f'photo-{stem}.jpg', 'size': [WIDTH, h]})
        verdict, counts = verdict_colours(splat, lidar_dir, device)
        for k, (V, f) in enumerate(path):
            K = torch.tensor([[f, 0, WIDTH / 2], [0, f, fly_h / 2], [0, 0, 1]], dtype=torch.float32, device=device)
            Vt = torch.tensor(V, dtype=torch.float32, device=device)
            Image.fromarray(to_u8(render(splat, Vt, K, WIDTH, fly_h, device))).save(views / f'fly-{k:03d}.jpg', quality=85)
            Image.fromarray(to_u8(render(splat, Vt, K, WIDTH, fly_h, device, rgb=verdict))).save(views / f'fly-verdict-{k:03d}.jpg', quality=85)
        index['fly'] = {'frames': len(path), 'pattern': 'fly-%03d.jpg', 'verdict_pattern': 'fly-verdict-%03d.jpg', 'size': [WIDTH, fly_h], 'poses_used': [title(n) for n in fly_keys],
                        'frame': 'the anchor\'s local metres (UTM 18N minus the lidar crop origin)', 'cameras': cameras, 'keys': keys, 'verdict_counts': counts,
                        'verdict_rule': 'red: more than 2 m above the highest lidar surface within 2.5 m; purple: more than 1 m under the lowest bare ground within 2.5 m; otherwise the Gaussian\'s own base colour',
                        'rule': 'training photographers facing the landmark (heading within 25 degrees, 30-160 m away), the 7 with most registered points, sorted by heading; centres, rotations (slerp) and focal lengths interpolated; raw colours on a sky background'}
        (views / 'index.json').write_text(json.dumps(index, indent=1) + '\n')
        summary[name] = {'poses': [(p['stem'], round(p['psnr_fitted'], 2), p['is_training']) for p in index['poses']], 'fly_frames': len(path)}
        del splat; torch.cuda.empty_cache()

    summary['verdict_still'] = verdict_still(run_path / 'splats', names, len(path))

    # The walk: plain and lidar-taught side by side, frame for frame.
    splats = {n: load_splat(run_path / 'splats' / n, device) for n in names}
    C = np.array([im.projection_center() for im in model.images.values()])
    d = C[:, :2] - centre_xy; dist = np.linalg.norm(d, axis=1); near = dist < np.percentile(dist, 80)
    az = np.unwrap(np.sort(np.arctan2(d[near, 1], d[near, 0])))
    a0, a1 = np.percentile(az, 10), np.percentile(az, 90)
    radius = float(np.median(dist[near])); eye = float(np.median(C[near, 2]))
    target = np.array([centre_xy[0], centre_xy[1], eye + 12.0])
    f = (WIDTH / 2) / np.tan(np.radians(27))
    K = torch.tensor([[f, 0, WIDTH / 2], [0, f, fly_h / 2], [0, 0, 1]], dtype=torch.float32, device=device)
    video = VIDEOS / 'splat-walk-plain-vs-lidar-taught.mp4'
    writer = imageio.get_writer(video, fps=30, codec='libx264', quality=8, macro_block_size=8)
    for k in range(walk_frames):
        t = 0.5 - 0.5 * np.cos(np.pi * k / max(walk_frames - 1, 1))
        a = a0 + (a1 - a0) * t
        pos = np.array([centre_xy[0] + radius * np.cos(a), centre_xy[1] + radius * np.sin(a), eye])
        V = torch.tensor(look_at(pos, target), dtype=torch.float32, device=device)
        frame = np.concatenate([to_u8(render(splats[n], V, K, WIDTH, fly_h, device)) for n in names], 1)
        writer.append_data(frame)
        if k == walk_frames // 2: Image.fromarray(frame).save(STILLS / 'walk-plain-vs-lidar-taught.jpg', quality=90)
    writer.close()
    summary['walk'] = {'video': str(video), 'radius_m': radius, 'eye_height_m': eye, 'azimuth_deg': [float(np.degrees(a0)), float(np.degrees(a1))],
                       'frames': walk_frames, 'layout': 'left plain, right lidar-taught'}
    (VIDEOS / 'splat-views-report.json').write_text(json.dumps(summary, indent=1) + '\n')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--run', type=Path, default=ROOT / 'artifacts/artsquad_modern/runs/6406b8eaae260163b303')
    parser.add_argument('--anchor', default='0')
    parser.add_argument('--fly-frames', type=int, default=90)
    parser.add_argument('--walk-frames', type=int, default=240)
    args = parser.parse_args()
    print(json.dumps(run(args.run, args.anchor, fly_frames=args.fly_frames, walk_frames=args.walk_frames), indent=1))


if __name__ == '__main__': main()
