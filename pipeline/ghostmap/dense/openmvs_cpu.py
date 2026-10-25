#!/usr/bin/env python3
"""COLMAP camera undistortion -> OpenMVS CPU stereo -> mesh -> texture.

Temporal groups are densified separately. No points are synthesized to seed the
scene (OpenMVS tower mode is explicitly disabled). All process output is saved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path

import pycolmap


from ghostmap.paths import ROOT


def command(tool: str) -> list[str]:
    binary = ROOT / 'third_party/openmvs-bin' / tool
    runtime = ROOT / 'third_party/openmvs-runtime/usr/lib/x86_64-linux-gnu'
    loader = runtime / 'ld-linux-x86-64.so.2'
    if loader.exists():
        return [str(loader), '--library-path', f'{runtime}:/lib/x86_64-linux-gnu', str(binary)]
    return [str(binary)]


def ply_counts(path: Path) -> dict:
    result = {}
    with path.open('rb') as f:
        for _ in range(100):
            line = f.readline().decode('ascii').strip()
            if line.startswith('element '):
                _, label, count = line.split()
                result[label] = int(count)
            if line == 'end_header':
                break
    return result


def reports_zero_fused_points(log_text: str) -> bool:
    return bool(re.search(r'Densifying point-cloud completed:\s*0\s+points\b', log_text))


def model_signature(model: pycolmap.Reconstruction) -> str:
    payload={
        'images':[(int(k),im.name,im.camera.params.tolist(),im.cam_from_world().matrix().tolist())
                  for k,im in sorted(model.images.items()) if im.has_pose],
        'points':[(int(k),p.xyz.tolist(),sorted((int(e.image_id),int(e.point2D_idx)) for e in p.track.elements))
                  for k,p in sorted(model.points3D.items())],
    }
    return hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--images', type=Path, default=ROOT / 'artifacts/work/joint/images')
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--era', choices=['historical', 'modern', 'all'], default='historical')
    parser.add_argument('--max-resolution', type=int, default=1280)
    parser.add_argument('--resolution-level', type=int, default=1)
    parser.add_argument('--rebuild-mesh', action='store_true')
    parser.add_argument('--masks', type=Path)
    args = parser.parse_args()
    work = args.workspace.resolve()
    work.mkdir(parents=True, exist_ok=True)
    report_file=work/'report.json'
    prior_report=json.loads(report_file.read_text()) if report_file.exists() else None
    if prior_report:
        history = work / 'report-history'; history.mkdir(exist_ok=True)
        payload = report_file.read_bytes(); digest = hashlib.sha256(payload).hexdigest()
        archive = history / (digest + '.json')
        if not archive.exists(): archive.write_bytes(payload)
    report = {'model': str(args.model), 'era': args.era, 'engine': 'COLMAP + OpenMVS v2.4.0 CPU',
              'status': 'running', 'steps': [], 'outputs': {},
              'claim': 'Measured surface candidate; target identity and held-out-view validation are required.'}
    start = time.monotonic()

    def save():
        report['elapsed_seconds'] = round(time.monotonic() - start, 2)
        report_file.write_text(json.dumps(report, indent=2) + '\n')

    def run(tool, options):
        cached = {'InterfaceCOLMAP': 'scene.mvs', 'DensifyPointCloud': 'dense.ply',
                  'ReconstructMesh': 'surface.mvs', 'TextureMesh': 'textured.obj'}
        rebuild=args.rebuild_mesh and tool in {'ReconstructMesh','TextureMesh'}
        if (work / cached[tool]).exists() and not rebuild:
            report['steps'].append({'tool': tool, 'status': 'cached', 'artifact': cached[tool]})
            save()
            return
        cmd = command(tool) + options + ['--max-threads', '4']
        step = {'tool': tool, 'command': cmd, 'status': 'running'}
        report['steps'].append(step)
        save()
        print('RUN', tool, flush=True)
        with (work / f'{tool}.log').open('w') as log:
            result = subprocess.run(cmd, cwd=work, stdout=log, stderr=subprocess.STDOUT,
                                    env={**os.environ, 'OMP_NUM_THREADS': '4'})
        step['returncode'] = result.returncode
        step['status'] = 'complete' if result.returncode == 0 else 'error'
        save()
        if result.returncode:
            raise RuntimeError(f'{tool} exited {result.returncode}; see {tool}.log')

    try:
        model = pycolmap.Reconstruction(str(args.model))
        for image in list(model.images.values()):
            if args.era != 'all' and not image.name.startswith(args.era + '__'):
                model.deregister_frame(image.frame_id)
        report['registered_images'] = model.num_reg_images()
        report['sparse_points'] = model.num_points3D()
        report['registered_names'] = sorted(i.name for i in model.images.values() if i.has_pose)
        selected = work / 'selected_sparse'
        signature=model_signature(model)
        if (work/'scene.mvs').exists() and (selected/'images.bin').exists():
            cached=pycolmap.Reconstruction(str(selected))
            if model_signature(cached)!=signature:
                report_file=work/'cache-validation-error.json'
                raise RuntimeError('Input model differs from the cached MVS workspace. Use a new workspace to preserve earlier measurements.')
        report['input_model_signature']=signature
        report['configuration']={'max_resolution':args.max_resolution,'resolution_level':args.resolution_level,'minimum_fusion_views':3,'tower_mode':0,'close_holes':0,'masks':str(args.masks) if args.masks else None}
        if (work/'dense.ply').exists() and prior_report:
            previous=prior_report.get('configuration',{})
            previous={**previous,'masks':previous.get('masks')}
            if previous!=report['configuration']:
                report_file=work/'cache-validation-error.json'
                raise RuntimeError('Dense configuration differs from the cached result. Use a new workspace rather than relabeling an existing measurement.')
        selected.mkdir(exist_ok=True)
        model.write(str(selected))
        dense = work / 'colmap'
        if not (dense/'sparse/images.bin').exists():
            pycolmap.undistort_images(str(dense), str(selected), str(args.images))
        # OpenMVS accepts the legacy COLMAP text camera convention reliably.
        undistorted = pycolmap.Reconstruction(str(dense / 'sparse'))
        undistorted.write_text(str(dense / 'sparse'))
        run('InterfaceCOLMAP', ['-i', str(dense), '-o', 'scene.mvs', '--image-folder', str(dense / 'images')])
        mask_options=['--mask-path',str(args.masks.resolve()),'--ignore-mask-label','0'] if args.masks else []
        run('DensifyPointCloud', ['scene.mvs', '-o', 'dense.mvs', '--resolution-level', str(args.resolution_level),
             '--max-resolution', str(args.max_resolution), '--min-resolution', '640',
             '--number-views', '5', '--number-views-fuse', '3', '--tower-mode', '0',
             '--estimate-roi', '0', '--crop-to-roi', '0', '--remove-dmaps', '0']+mask_options)
        if not (work / 'dense.ply').is_file():
            log_text = (work / 'DensifyPointCloud.log').read_text(errors='replace')
            if not reports_zero_fused_points(log_text):
                raise RuntimeError('Densifier returned without dense.ply and without a known zero-fusion result; inspect DensifyPointCloud.log')
            report.update(status='insufficient_depth_support', claim='No dense surface recovered; no mesh or texture is accepted.', reason='Three-view depth fusion produced zero points. Sparse points retained in dense.mvs are NOT a dense reconstruction.')
            report['outputs']['dense'] = {'vertex': 0}; save(); print(json.dumps(report, indent=2), flush=True); return
        report['outputs']['dense'] = ply_counts(work / 'dense.ply')
        if not report['outputs']['dense'].get('vertex', 0):
            report.update(status='insufficient_depth_support', claim='No dense surface recovered; no mesh or texture is accepted.', reason='Dense point cloud is empty; no mesh or texture is fabricated.')
            save(); print(json.dumps(report, indent=2), flush=True); return
        save()
        run('ReconstructMesh', ['dense.mvs', '--pointcloud-file', 'dense.ply', '-o', 'surface.mvs', '--decimate', '1',
                                '--close-holes', '0', '--archive-type', '2'])
        report['outputs']['mesh'] = ply_counts(work / 'surface.ply')
        save()
        run('TextureMesh', ['surface.mvs', '-o', 'textured.mvs', '--export-type', 'obj',
                            '--empty-color', '0'])
        report['status'] = 'surface_candidate'
        save()
    except Exception as exc:
        report['status'] = 'error'
        report['error'] = str(exc)
        save()
        raise
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
