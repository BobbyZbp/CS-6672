#!/usr/bin/env python3
"""Train a Gaussian splat of an anchored fragment, in the lidar frame, from its internet photographs.

Input is a COLMAP model already placed in local metres (an anchor's `model-local-metres`) and the
run's working images. The model is undistorted first (pinhole cameras, pycolmap), the splat is
initialised from the sparse points, and trained with gsplat's rasteriser and default densification.
In-the-wild photographs differ in exposure and white balance, so every image owns an affine colour
map (3 x 4) applied to the rendering before the loss, and a background colour (the sky); nothing else
is learned per image. With `--lidar-prior` the lidar's free space becomes a training prior (`LidarPrior`,
the lidar as teacher). A few images are held out for a test PSNR. Nothing is normalised: the Gaussians live in the same metres
as the lidar, so `evaluate/splat_geometry.py` can score them against it directly.

Outputs under `<run>/splats/<name>/`: `ckpt.pt` (parameters), `splat.ply` (standard 3D Gaussian
Splatting layout for viewers), `renders/` (held-out views: photograph beside rendering), `report.json`.

Usage: CUDA_HOME=<cuda prefix> PYTHONPATH=pipeline python -m ghostmap.dense.splats --run <run> --anchor <component> --name tower-and-library [--steps 15000] [--lidar-prior]
"""
from __future__ import annotations

import argparse
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from ghostmap.paths import ROOT

HOLDOUT_EVERY = 12   # every twelfth image (sorted by name) is held out for the test PSNR


def undistort(run, anchor_model, out):
    """Pinhole images and model from the anchored (local metres) SIMPLE_RADIAL model."""
    import pycolmap
    out = Path(out)
    if not (out / 'sparse' / 'images.bin').exists():
        pycolmap.undistort_images(str(out), str(anchor_model), str(Path(run) / 'images'))
    return pycolmap.Reconstruction(str(out / 'sparse')), out / 'images'


def load_views(model, image_dir, device):
    import torch
    from PIL import Image
    views = []
    for image in sorted(model.images.values(), key=lambda im: im.name):
        cam = model.cameras[image.camera_id]
        fx, fy, cx, cy = (cam.params[0], cam.params[0], cam.params[1], cam.params[2]) if cam.model.name == 'SIMPLE_PINHOLE' else tuple(cam.params[:4])
        K = torch.tensor([[fx, 0, cx], [0, fy, cy], [0, 0, 1]], dtype=torch.float32)
        R = torch.tensor(image.cam_from_world().rotation.matrix(), dtype=torch.float32); t = torch.tensor(image.cam_from_world().translation, dtype=torch.float32)
        viewmat = torch.eye(4); viewmat[:3, :3] = R; viewmat[:3, 3] = t
        # Photographs stay on the host as bytes and go to the GPU one at a time (88 photographs as floats on the GPU
        # crowded an 8 GB card into paging once a splat passed a million Gaussians).
        pixels = torch.from_numpy(np.asarray(Image.open(image_dir / image.name).convert('RGB'), dtype=np.uint8).copy())
        views.append({'name': image.name, 'K': K.to(device), 'viewmat': viewmat.to(device), 'pixels': pixels, 'width': cam.width, 'height': cam.height})
    return views


def image_of(v, device):
    """A view's photograph on the device, (H, W, 3) floats in [0, 1]."""
    return v['pixels'].to(device, non_blocking=True).float() / 255.0


def ssim(a, b, window=11, sigma=1.5):
    """Structural similarity of two (H, W, 3) images, Gaussian window."""
    import torch, torch.nn.functional as F
    x = a.permute(2, 0, 1)[None]; y = b.permute(2, 0, 1)[None]
    g = torch.exp(-(torch.arange(window, device=a.device) - window // 2) ** 2 / (2 * sigma ** 2)); g = (g / g.sum())
    w = (g[:, None] * g[None, :])[None, None].repeat(3, 1, 1, 1)
    mu_x = F.conv2d(x, w, padding=window // 2, groups=3); mu_y = F.conv2d(y, w, padding=window // 2, groups=3)
    sxx = F.conv2d(x * x, w, padding=window // 2, groups=3) - mu_x ** 2; syy = F.conv2d(y * y, w, padding=window // 2, groups=3) - mu_y ** 2
    sxy = F.conv2d(x * y, w, padding=window // 2, groups=3) - mu_x * mu_y
    c1, c2 = 0.01 ** 2, 0.03 ** 2
    return (((2 * mu_x * mu_y + c1) * (2 * sxy + c2)) / ((mu_x ** 2 + mu_y ** 2 + c1) * (sxx + syy + c2))).mean()


def initial_gaussians(model, device):
    import torch
    from scipy.spatial import cKDTree
    pts = np.array([p.xyz for p in model.points3D.values()], dtype=np.float32)
    rgb = np.array([p.color for p in model.points3D.values()], dtype=np.float32) / 255.0
    d, _ = cKDTree(pts).query(pts, k=4); nn = np.clip(d[:, 1:].mean(1), 0.05, 5.0).astype(np.float32)
    params = torch.nn.ParameterDict({
        'means': torch.nn.Parameter(torch.from_numpy(pts).to(device)),
        'scales': torch.nn.Parameter(torch.log(torch.from_numpy(nn).to(device))[:, None].repeat(1, 3)),
        'quats': torch.nn.Parameter(torch.tensor([1., 0, 0, 0], device=device).repeat(len(pts), 1)),
        'opacities': torch.nn.Parameter(torch.logit(torch.full((len(pts),), 0.1, device=device))),
        'sh0': torch.nn.Parameter(((torch.from_numpy(rgb).to(device) - 0.5) / 0.28209479177387814)[:, None, :]),
        'shN': torch.nn.Parameter(torch.zeros(len(pts), 15, 3, device=device)),
    })
    return params


class LidarPrior:
    """The lidar's free space as a training prior: within the measured volume (the lidar crop's horizontal box, up to
    120 m above its ground) the air more than `margin` above the highest lidar surface within 2.5 m was seen empty in
    2020, and nothing lies more than a metre under the lowest bare ground within 2.5 m. Gaussians there are floaters; the loss makes them transparent (and lets
    them sink onto the surface), and the ones far in the air are removed at every refinement step."""

    def __init__(self, crop, origin_xy, device, margin_m=2.0, ceiling_m=120.0):
        import torch
        from ghostmap.evaluate.splat_geometry import tolerant_rasters
        r = np.load(Path(crop) / 'quad-rasters-utm18n.npz')
        self.box = [float(v) for v in r['box']]; self.cell = float(r['cell'])
        self.origin = np.asarray(origin_xy, float)
        dsm, dtm = tolerant_rasters(r)   # the same 2.5 m tolerance the scorer uses (walls are vertical)
        self.dsm = torch.tensor(dsm, dtype=torch.float32, device=device)
        self.dtm = torch.tensor(dtm, dtype=torch.float32, device=device)
        self.margin, self.ceiling = margin_m, float(np.nanmedian(r['ground'])) + ceiling_m

    def lookup(self, xyz):
        import torch
        e = xyz[:, 0] + float(self.origin[0]); n = xyz[:, 1] + float(self.origin[1])
        rows, cols = self.dsm.shape
        r = ((self.box[3] - n) / self.cell).long(); c = ((e - self.box[0]) / self.cell).long()
        inside = (r >= 0) & (r < rows) & (c >= 0) & (c < cols) & (xyz[:, 2] < self.ceiling)
        r = r.clamp(0, rows - 1); c = c.clamp(0, cols - 1)
        return self.dsm[r, c], self.dtm[r, c], inside

    def violation(self, xyz):
        """Metres into lidar-measured free air (above the surface) or under the ground; zero outside the measured volume."""
        import torch
        dsm, dtm, inside = self.lookup(xyz)
        v = torch.relu(xyz[:, 2] - (dsm + self.margin)) + torch.relu((dtm - 1.0) - xyz[:, 2])
        return torch.where(inside, v, torch.zeros_like(v))


def train(run, anchor, name, steps=15000, sh_degree=3, device='cuda', seed=0, lidar_prior=False, prior_weight=0.01, prune_above_m=5.0):
    import torch
    from gsplat import rasterization
    from gsplat.strategy import DefaultStrategy
    from gsplat.strategy.ops import remove
    torch.manual_seed(seed); np.random.seed(seed)
    run = Path(run).resolve(); out = run / 'splats' / name; out.mkdir(parents=True, exist_ok=True)
    anchor_dir = run / 'anchor' / str(anchor); anchor_report = json.loads((anchor_dir / 'report.json').read_text())
    model, image_dir = undistort(run, anchor_dir / 'model-local-metres', run / 'splats' / f'undistorted-{anchor}')
    views = load_views(model, image_dir, device)
    test = views[::HOLDOUT_EVERY]; train_views = [v for i, v in enumerate(views) if i % HOLDOUT_EVERY]
    params = initial_gaussians(model, device)
    # The strategy's working scale: a quarter of the fragment's extent (sparse points, 5th to 95th percentile), so
    # Gaussians split down to centimetres. The photographers' spread would be the usual choice, but internet
    # photographers stand up to 240 m away and that scale stopped splitting at two metres (a blurred first splat).
    pts = params['means'].detach().cpu().numpy()
    scene_scale = float(np.linalg.norm(np.percentile(pts, 95, 0) - np.percentile(pts, 5, 0)) / 4)
    lr = {'means': 1.6e-4 * scene_scale, 'scales': 5e-3, 'quats': 1e-3, 'opacities': 5e-2, 'sh0': 2.5e-3, 'shN': 2.5e-3 / 20}
    optimizers = {k: torch.optim.Adam([{'params': params[k], 'lr': lr[k], 'name': k}], eps=1e-15) for k in params}
    # Per image: an affine colour map (exposure, white balance) and a background colour (the sky), both learned.
    affine = torch.nn.Parameter(torch.eye(3, 4, device=device)[None].repeat(len(views), 1, 1))
    background = torch.nn.Parameter(torch.stack([image_of(v, device)[: max(1, v['height'] // 20)].reshape(-1, 3).median(0).values for v in views]))
    opt_image = torch.optim.Adam([{'params': [affine], 'lr': 1e-3}, {'params': [background], 'lr': 1e-2}])
    strategy = DefaultStrategy(verbose=False, refine_start_iter=500, refine_stop_iter=int(steps * 0.6), reset_every=3000, refine_every=100)
    strategy.check_sanity(params, optimizers)
    state = strategy.initialize_state(scene_scale=scene_scale)
    sched = torch.optim.lr_scheduler.ExponentialLR(optimizers['means'], gamma=0.01 ** (1.0 / steps))
    view_index = {v['name']: i for i, v in enumerate(views)}
    prior = None
    if lidar_prior:
        lidar_crop = Path(anchor_report['lidar_report']).parent
        prior = LidarPrior(lidar_crop, anchor_report['local_frame']['origin_utm18n'][:2], device)

    def render(v, step=None, bg=None):
        sh = min(step // 1000, sh_degree) if step is not None else sh_degree
        colors = torch.cat([params['sh0'], params['shN']], 1)
        # Packed rasterization (the memory-lean layout, same image); the background is composited here, as gsplat
        # would (colour + (1 - alpha) * background), since its packed path rejects a background tensor.
        img, alpha, info = rasterization(params['means'], params['quats'] / params['quats'].norm(dim=-1, keepdim=True), torch.exp(params['scales']),
                                         torch.sigmoid(params['opacities']), colors, v['viewmat'][None], v['K'][None], v['width'], v['height'],
                                         sh_degree=sh, packed=True, absgrad=False)
        bg = bg if bg is not None else torch.ones(3, device=device)
        return img[0] + (1 - alpha[0]) * bg, alpha[0], info

    t0 = time.time(); log = []; pruned_by_prior = 0
    for step in range(steps):
        v = train_views[np.random.randint(len(train_views))]; i = view_index[v['name']]
        img, alpha, info = render(v, step, background[i].clamp(0, 1))
        A = affine[i]
        pred = (img @ A[:, :3].T + A[:, 3]).clamp(0, 1)
        target = image_of(v, device)
        l1 = (pred - target).abs().mean(); s = ssim(pred, target)
        loss = 0.8 * l1 + 0.2 * (1 - s)
        prior_loss = None
        if prior is not None:
            prior_loss = (torch.sigmoid(params['opacities']) * prior.violation(params['means'])).mean()
            loss = loss + prior_weight * prior_loss
        strategy.step_pre_backward(params, optimizers, state, step, info)
        loss.backward()
        for o in optimizers.values(): o.step(); o.zero_grad(set_to_none=True)
        opt_image.step(); opt_image.zero_grad(set_to_none=True); sched.step()
        strategy.step_post_backward(params, optimizers, state, step, info, packed=True)
        if prior is not None and step >= 500 and step % 100 == 0:
            with torch.no_grad(): far = prior.violation(params['means']) > prune_above_m
            if far.any() and int((~far).sum()) > 1000:
                remove(params=params, optimizers=optimizers, state=state, mask=far); pruned_by_prior += int(far.sum())
        if step % 500 == 0 or step == steps - 1:
            log.append({'step': step, 'loss': float(loss), 'prior_loss': None if prior_loss is None else float(prior_loss),
                        'gaussians': int(len(params['means'])), 'pruned_by_prior': pruned_by_prior, 'seconds': round(time.time() - t0, 1)})
            print(json.dumps(log[-1]), flush=True)

    # Held-out PSNR: the held-out photograph's colour map and background are not trained, so they are fitted to it
    # (least squares on the rendering, the usual protocol for in-the-wild collections).
    def psnr_of(v, i=None):
        with torch.no_grad():
            photo = image_of(v, device)
            bg = background[i].clamp(0, 1) if i is not None else photo[: max(1, v['height'] // 20)].reshape(-1, 3).median(0).values
            img, alpha, _ = render(v, bg=bg)
            X = torch.cat([img.reshape(-1, 3), torch.ones(img.shape[0] * img.shape[1], 1, device=device)], 1); Y = photo.reshape(-1, 3)
            M = torch.linalg.lstsq(X, Y).solution; pred = (X @ M).reshape(img.shape).clamp(0, 1)
            return float(10 * torch.log10(1 / ((pred - photo) ** 2).mean())), pred
    (out / 'renders').mkdir(exist_ok=True)
    from PIL import Image
    test_psnr = []
    for v in test:
        p, pred = psnr_of(v); test_psnr.append({'image': v['name'], 'psnr': p})
        side = np.concatenate([v['pixels'].numpy().astype(np.float32) / 255.0, pred.cpu().numpy()], 1)
        Image.fromarray((side * 255).astype(np.uint8)).save(out / 'renders' / (Path(v['name']).stem + '.jpg'), quality=90)
    train_psnr = [psnr_of(v, view_index[v['name']])[0] for v in train_views[:8]]
    # The per-photograph colour maps and backgrounds are saved too (renders at training poses need no refit).
    torch.save({**{k: v.detach().cpu() for k, v in params.items()}, 'affine': affine.detach().cpu(), 'background': background.detach().cpu(),
                'image_names': [v['name'] for v in views]}, out / 'ckpt.pt')
    write_ply(params, out / 'splat.ply')
    report = {'schema_version': 2, 'created_utc': datetime.now(timezone.utc).isoformat(), 'run': str(run), 'anchor': str(anchor), 'name': name,
              'frame': 'local metres of the anchor (UTM 18N minus the lidar crop origin)', 'images': {'train': len(train_views), 'test': len(test)},
              'steps': steps, 'gaussians': int(len(params['means'])), 'working_scale_m': scene_scale, 'seconds': round(time.time() - t0, 1),
              'lidar_prior': ({'weight': prior_weight, 'margin_m': prior.margin, 'prune_above_m': prune_above_m, 'pruned': pruned_by_prior,
                               'rule': f'opacity times metres into lidar free air (beyond the 2 m margin) or under the ground, inside the measured volume; Gaussians more than {prune_above_m:g} m beyond the margin removed at each refinement'}
                              if prior is not None else None),
              'psnr': {'train_first8_mean': float(np.mean(train_psnr)), 'test': test_psnr, 'test_mean': float(np.mean([t['psnr'] for t in test_psnr])) if test_psnr else None,
                       'protocol': 'held-out photographs: colour map and background fitted to the photograph by least squares'},
              'loss_log': log, 'outputs': {'ckpt': str(out / 'ckpt.pt'), 'ply': str(out / 'splat.ply'), 'renders': str(out / 'renders')},
              'claim': 'A rendering of what the photographs saw, in the lidar frame; its geometry is scored separately against the lidar.'}
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def write_ply(params, path):
    """Standard 3D Gaussian Splatting PLY (x y z nx ny nz f_dc_* f_rest_* opacity scale_* rot_*)."""
    import torch
    means = params['means'].detach().cpu().numpy(); sh0 = params['sh0'].detach().cpu().numpy().reshape(len(means), -1)
    shN = params['shN'].detach().cpu().numpy().transpose(0, 2, 1).reshape(len(means), -1)   # (N, 3, 15) -> f_rest ordered by channel
    opac = params['opacities'].detach().cpu().numpy(); scales = params['scales'].detach().cpu().numpy(); quats = params['quats'].detach().cpu().numpy()
    names = ['x', 'y', 'z', 'nx', 'ny', 'nz'] + [f'f_dc_{i}' for i in range(3)] + [f'f_rest_{i}' for i in range(shN.shape[1])] + ['opacity'] + [f'scale_{i}' for i in range(3)] + [f'rot_{i}' for i in range(4)]
    data = np.concatenate([means, np.zeros_like(means), sh0, shN, opac[:, None], scales, quats], 1).astype(np.float32)
    header = 'ply\nformat binary_little_endian 1.0\nelement vertex %d\n' % len(data) + ''.join(f'property float {n}\n' for n in names) + 'end_header\n'
    with open(path, 'wb') as f: f.write(header.encode('ascii')); f.write(data.tobytes())


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--anchor', required=True, help='anchored fragment id (its model-local-metres is the input)')
    parser.add_argument('--name', required=True, help='name of the splat, e.g. tower-and-library')
    parser.add_argument('--steps', type=int, default=15000)
    parser.add_argument('--lidar-prior', action='store_true', help='train with the lidar free-space prior (the lidar as teacher)')
    parser.add_argument('--prior-weight', type=float, default=0.01)
    parser.add_argument('--prune-above', type=float, default=5.0, help='remove Gaussians this many metres beyond the 2 m margin into lidar free air')
    args = parser.parse_args()
    report = train(args.run, args.anchor, args.name, args.steps, lidar_prior=args.lidar_prior, prior_weight=args.prior_weight, prune_above_m=args.prune_above)
    print(json.dumps({k: report[k] for k in ('gaussians', 'seconds', 'psnr')}, indent=1))


if __name__ == '__main__': main()
