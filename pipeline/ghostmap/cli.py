#!/usr/bin/env python3
"""Local modern-Atlas entry point; no implicit remote job, purchase or publication.

Acquisition is explicit, so a running compliant downloader is never duplicated by
the reconstruction stages. 'pilot' freezes local inputs, runs SfM, then packages
the measured diagnostic viewer; it does NOT mean D0 or D1 has passed.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from ghostmap.paths import ROOT


def call(script, *arguments):
    command = [sys.executable, str(ROOT / 'pipeline' / script), *map(str, arguments)]
    print('RUN', ' '.join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def require_disk(workspace, minimum_gib):
    workspace.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(workspace).free / 2**30
    if free < minimum_gib: raise RuntimeError(f'{free:.2f} GiB free; minimum {minimum_gib:g} GiB. No files removed.')


def surface_fragments(run_path, cid):
    call('build_artsquad_supported.py', '--run', run_path, '--component', cid)
    report = json.loads((run_path / 'mvs' / cid / 'family-supported-report.json').read_text())
    if report.get('status') == 'supported_fragment_candidate':
        call('index_artsquad_faces.py', '--run', run_path, '--component', cid)


def densify(run_path, component_ids, max_resolution, resolution_level):
    report = json.loads((run_path / 'report.json').read_text())
    if report.get('status') != 'sfm_complete': raise ValueError('A completed sparse run is required')
    by_id = {str(c['id']): c for c in report['components']}
    # Preflight all requested components before any expensive stage.
    for cid in component_ids:
        if cid not in by_id or not cid.isdigit(): raise ValueError('Unknown component: ' + cid)
        if by_id[cid]['registered_cameras'] < 3: raise ValueError('Three-view stereo fusion requires at least three recovered cameras')
    for cid in component_ids:
        require_disk(run_path, 5)
        mvs = run_path / 'mvs' / cid
        call('run_cpu_mvs.py', '--model', run_path / by_id[cid]['model_path'], '--images', run_path / 'images',
             '--workspace', mvs, '--era', 'all', '--max-resolution', max_resolution,
             '--resolution-level', resolution_level)
        dense_report = json.loads((mvs / 'report.json').read_text())
        if dense_report.get('status') == 'insufficient_depth_support':
            print('NEGATIVE DENSE RESULT', cid, dense_report.get('reason'), flush=True)
            continue
        if dense_report.get('status') != 'surface_candidate': raise RuntimeError('Dense execution did not produce a measured surface candidate')
        call('texture_from_cameras.py', '--workspace', mvs)
        call('audit_artsquad_dense_support.py', '--run', run_path, '--component', cid)
        surface_fragments(run_path, cid)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['acquire', 'prepare', 'sfm', 'pilot', 'dense', 'patches', 'holdouts', 'support', 'site', 'status'])
    parser.add_argument('--snapshot', type=Path)
    parser.add_argument('--run', type=Path)
    parser.add_argument('--workspace', type=Path, default=ROOT / 'artifacts/artsquad_modern')
    parser.add_argument('--manifest', type=Path, default=ROOT / 'data/artsquad_modern/manifest.json')
    parser.add_argument('--inventory', type=Path, default=ROOT / 'data/artsquad_modern/inventory.json')
    parser.add_argument('--download', action='store_true', help='Only applies to acquire; otherwise inventory-only')
    parser.add_argument('--resize', type=int, default=1200)
    parser.add_argument('--keypoints', type=int, default=4096)
    parser.add_argument('--neighbors', type=int, default=8)
    parser.add_argument('--run-label', default='default')
    parser.add_argument('--reuse-from', type=Path)
    parser.add_argument('--method', choices=['learned', 'sift'], default='learned')
    parser.add_argument('--targets', nargs='*', default=[])
    parser.add_argument('--components', nargs='+', help='Explicit measured component IDs for dense stage')
    parser.add_argument('--max-queries', type=int, help='Explicit holdout diagnostic budget; default all test images')
    parser.add_argument('--max-resolution', type=int, default=1280)
    parser.add_argument('--resolution-level', type=int, default=0)
    parser.add_argument('--evidence', type=Path)
    parser.add_argument('--dist', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    try:
        if args.stage == 'acquire':
            call('acquire_artsquad.py', '--download' if args.download else '--inventory-only'); return
        if args.stage == 'status':
            call('artsquad_status.py', *(['--evidence', args.evidence] if args.evidence else [])); return
        if args.stage == 'dense':
            if not args.run or not args.components: parser.error('dense requires --run and explicit --components')
            if args.max_resolution < 640 or args.resolution_level < 0: parser.error('Invalid stereo resolution')
            densify(args.run.resolve(), args.components, args.max_resolution, args.resolution_level); return
        if args.stage == 'patches':
            if not args.run or not args.components: parser.error('patches requires --run and --components')
            for cid in args.components:
                if not cid.isdigit(): parser.error('Native component IDs must be numeric')
                surface_fragments(args.run.resolve(), cid)
            return
        if args.stage in {'holdouts', 'support'}:
            if not args.run or not args.components: parser.error(args.stage + ' requires --run and --components')
            for cid in args.components:
                if not cid.isdigit(): parser.error('Component IDs must be native numeric component IDs')
                optional = ['--max-queries', args.max_queries] if args.stage == 'holdouts' and args.max_queries is not None else []
                call('validate_artsquad_holdouts.py' if args.stage == 'holdouts' else 'audit_artsquad_dense_support.py',
                     '--run', args.run.resolve(), '--component', cid, *optional)
            return
        from ghostmap.prepare.snapshot import prepare
        snapshot = args.snapshot.resolve() if args.snapshot else None
        if args.stage in {'prepare', 'sfm', 'pilot'} and not snapshot:
            snapshot = prepare(args.manifest.resolve(), args.inventory.resolve(), args.workspace.resolve()) / 'snapshot.json'
        if args.stage == 'prepare': print(snapshot); return
        if not snapshot: parser.error('site requires --snapshot corresponding to the selected run')
        run_path = args.run.resolve() if args.run else None
        if args.stage in {'sfm', 'pilot'}:
            if args.resize < 640 or args.keypoints < 512 or args.neighbors < 1: parser.error('Invalid feature budget')
            require_disk(args.workspace, 5)
            if args.method == 'sift':
                if args.reuse_from or args.resize != 1200 or args.keypoints != 4096:
                    parser.error('The SIFT pilot pins 1200px/4096 requested features and never imports learned feature caches')
                from ghostmap.sfm.sift import run
                run_path = run(snapshot, args.workspace, args.targets, args.run_label)
            else:
                from ghostmap.sfm.learned import run
                run_path = run(snapshot, args.workspace, args.resize, args.keypoints, args.neighbors, args.targets, args.run_label, args.reuse_from)
        if args.stage in {'pilot', 'site'}:
            from ghostmap.web.site import package
            manifest = package(snapshot, run_path, args.dist, args.evidence)
            print(json.dumps({'scene_manifest': str(manifest), 'run': str(run_path) if run_path else None,
                              'local_page': 'http://127.0.0.1:8080/artsquad.html',
                              'delivery_status': 'diagnostic only; D0/D1/HTTPS not inferred'}, indent=2))
        else: print(run_path)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        parser.exit(2, type(error).__name__ + ': ' + str(error) + '\n')


if __name__ == '__main__': main()
