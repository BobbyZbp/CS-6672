#!/usr/bin/env python3
"""Snapshot-bound modern SfM. Preserve every component; never assemble a campus by hand.

Only train images enter feature extraction, matching, database or bundle adjustment.
Target labels are collection metadata, not proof of reconstructed building identity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import sqlite3
import time
from collections import Counter
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPELINE_VERSION = 2


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()


def write_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    temporary.replace(path)


def select_training_images(snapshot, targets=()):
    """Selection is declared, deterministic, and never borrows held-out views."""
    images = snapshot['images']
    train = [i for i in images if i.get('split') == 'train' and i.get('role') == 'scene-candidate'
             and i.get('validation', {}).get('passed') is True]
    if targets:
        train = [i for i in train if set(targets) & set(i.get('discovery', {}).get('targets', []))]
    test = [i for i in images if i.get('split') == 'test']
    for key in ('filename', 'exposure_group_id', 'source_family_id'):
        a, b = {i.get(key) for i in train}, {i.get(key) for i in test}
        if any(not isinstance(v, str) or not v.strip() for v in a) or a & b:
            raise ValueError('Missing or leaking train/test ' + key)
    if len({i['filename'] for i in train}) != len(train):
        raise ValueError('Duplicate working filenames')
    for image in train:
        if Path(image['filename']).name != image['filename'] or any(c.isspace() for c in image['filename']):
            raise ValueError('Working filenames must be whitespace-free basenames')
    return sorted(train, key=lambda i: i['filename'])


def stage_images(records, directory):
    directory.mkdir(parents=True, exist_ok=True)
    if {p.name for p in directory.iterdir()} - {i['filename'] for i in records}:
        raise ValueError('Staged image directory contains undeclared inputs')
    for image in records:
        source = Path(image['working_path']).resolve()
        if sha256(source) != image['sha256_working']:
            raise ValueError('Frozen input changed: ' + str(source))
        destination = directory / image['filename']
        if destination.is_symlink():
            raise ValueError('Staged symlink is unsafe for COLMAP canonical image naming; preserve it and use a new run: ' + str(destination))
        elif destination.exists():
            if not destination.is_file() or sha256(destination) != image['sha256_working']:
                raise ValueError('Refusing to replace a changed staged input: ' + str(destination))
        else:
            shutil.copy2(source, destination)
            if sha256(destination) != image['sha256_working']: raise ValueError('Copy hash mismatch')
    if {p.name for p in directory.iterdir()} != {i['filename'] for i in records}:
        raise ValueError('Staged image directory contains undeclared inputs')


def verified_graph(database, records):
    """Verified pair graph, not semantic cross-building connectivity certification."""
    lookup = {i['filename']: i for i in records}; edges = []
    with sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True) as db:
        names = dict(db.execute('SELECT image_id,name FROM images'))
        for pair_id, count, config in db.execute('SELECT pair_id,rows,config FROM two_view_geometries'):
            a, b = divmod(pair_id, 2147483647)
            edges.append({'a': names[a], 'b': names[b], 'inliers': count, 'configuration': config,
                          'nondegenerate_epipolar': config in (2, 3),
                          'metadata_targets_a': lookup[names[a]].get('discovery', {}).get('targets', []),
                          'metadata_targets_b': lookup[names[b]].get('discovery', {}).get('targets', [])})
    return {'edges': edges, 'verified_pairs': sum(e['inliers'] > 0 for e in edges),
            'nondegenerate_pairs': sum(e['inliers'] > 0 and e['nondegenerate_epipolar'] for e in edges),
            'interpretation': 'Epipolar verification is necessary, not sufficient: repeated facades, rotations, exposure dependence and target identity still require checks.'}


def component_report(model, component_id, records):
    import numpy as np
    lookup = {i['filename']: i for i in records}
    cameras, errors, angles, group_counts = [], [], [], []
    centers = {int(k): im.projection_center() for k, im in model.images.items() if im.has_pose}
    for point in model.points3D.values():
        errors.append(float(point.error))
        ids = sorted({int(e.image_id) for e in point.track.elements} & centers.keys())
        group_counts.append(len({lookup[model.images[k].name]['exposure_group_id'] for k in ids}))
        # Small sparse tracks: maximum observed triangulation angle, no metric units.
        directions = [centers[k] - point.xyz for k in ids]
        directions = [v / np.linalg.norm(v) for v in directions if np.linalg.norm(v) > 0]
        maximum = max((math.degrees(math.acos(float(np.clip(np.dot(a, b), -1, 1))))
                       for a, b in combinations(directions, 2)), default=0.)
        angles.append(maximum)
    for image in model.images.values():
        if not image.has_pose: continue
        K = image.camera.calibration_matrix(); record = lookup[image.name]
        ratio = float(K[0, 0] / max(image.camera.width, image.camera.height))
        cameras.append({'name': image.name, 'id': int(image.image_id), 'camera_model': image.camera.model.name,
                        'camera_parameters': image.camera.params.tolist(), 'focal_max_dimension_ratio': ratio,
                        'registered_points': int(image.num_points3D),
                        'exposure_group_id': record['exposure_group_id'], 'source_family_id': record['source_family_id'],
                        'exif': record.get('exif', {}),
                        'metadata_targets': record.get('discovery', {}).get('targets', [])})
    def distribution(values):
        return {str(q): float(np.percentile(values, q)) for q in (5, 50, 95)} if values else {}
    return {'id': component_id, 'model_path': 'sfm/models/' + component_id,
            'registered_cameras': len(cameras), 'sparse_points': int(model.num_points3D()),
            'reprojection_error_px_percentiles': distribution(errors),
            'maximum_track_angle_degrees_percentiles': distribution(angles),
            'points_with_three_exact_hash_groups': sum(n >= 3 for n in group_counts),
            'metadata_target_camera_counts': dict(Counter(t for c in cameras for t in c['metadata_targets'])),
            'cameras': sorted(cameras, key=lambda c: c['name']), 'scale_status': 'similarity-frame-unverified',
            'target_identity_validated': False, 'independent_exposures_validated': False,
            'claim': 'Raw SfM component. Metadata labels and small reprojection errors do not validate building shape or completeness.'}


def saved_component_reports(models_path, records, loader=None):
    """Saved directory IDs, not API ReconstructionManager keys, are authoritative.

    pycolmap 3.13 may return manager keys in a different order from the model
    directories it writes. Never attach one model's labels to another's files.
    """
    if loader is None:
        import pycolmap
        loader = pycolmap.Reconstruction
    allowed = {row['filename'] for row in records}; components = []
    directories = [p for p in Path(models_path).iterdir() if p.is_dir() and (p / 'images.bin').is_file()]
    if any(not p.name.isdigit() for p in directories): raise ValueError('Unexpected native model directory ID')
    if any(p.is_symlink() or not p.resolve().is_relative_to(Path(models_path).resolve()) for p in directories):
        raise ValueError('Native model directory escapes its run')
    for directory in sorted(directories, key=lambda p: int(p.name)):
        model = loader(str(directory))
        if any(image.name not in allowed for image in model.images.values() if image.has_pose):
            raise ValueError('Saved native model contains undeclared cameras')
        entry = component_report(model, directory.name, records)
        write_json(directory / 'diagnostics.json', entry)
        model.export_PLY(str(directory / 'sparse.ply'))
        components.append(entry)
    return components


def run(snapshot_path, workspace, resize=1200, keypoints=4096, neighbors=8, targets=(), label='default', reuse_from=None):
    import pycolmap
    import torch
    from hloc import extract_features, match_features, pairs_from_retrieval, reconstruction
    from hloc.triangulation import import_features, import_matches, estimation_and_geometric_verification

    snapshot_path = Path(snapshot_path).resolve(); snapshot = json.loads(snapshot_path.read_text())
    records = select_training_images(snapshot, targets)
    if len(records) < 2: raise ValueError('At least two admitted train images are required')
    config = {'pipeline_version': PIPELINE_VERSION, 'snapshot_sha256': sha256(snapshot_path),
              'resize': resize, 'keypoints': keypoints, 'retrieval_neighbors': neighbors,
              'targets': sorted(targets), 'run_label': label, 'camera_model': 'SIMPLE_RADIAL',
              'camera_mode': 'PER_IMAGE', 'threads': 4, 'minimum_saved_component_cameras': 2,
              'torch_version': torch.__version__, 'pycolmap_version': pycolmap.__version__,
              'extractor': 'SuperPoint', 'matcher': 'LightGlue', 'retrieval': 'NetVLAD'}
    run_id = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:20]
    work = Path(workspace).resolve() / 'runs' / run_id; work.mkdir(parents=True, exist_ok=True)
    report_path = work / 'report.json'
    if (work / 'configuration.json').exists() and json.loads((work / 'configuration.json').read_text()) != config:
        raise ValueError('Run configuration mismatch; refusing cache reuse')
    write_json(work / 'configuration.json', config)
    stage_images(records, work / 'images')
    if report_path.exists() and json.loads(report_path.read_text()).get('status') in {'sfm_complete', 'no_model'}:
        return work
    names = [i['filename'] for i in records]
    report = {'schema_version': 1, 'run_id': run_id, 'snapshot_path': str(snapshot_path),
              'snapshot_id': snapshot['snapshot_id'], 'configuration': config, 'input_images': names,
              'held_out_images_used_in_mapping': 0, 'status': 'running', 'stage': 'features',
              'created_utc': datetime.now(timezone.utc).isoformat(), 'components': [],
              'limitations': ['No target identity, independent exposure, held-out localization, metric scale or surface validation has passed.',
                              'This CPU pilot uses only the currently frozen acquisition; later downloads require a new snapshot/run.']}
    started = time.monotonic()
    def save(stage):
        report['stage'] = stage; report['elapsed_seconds'] = round(time.monotonic() - started, 2)
        write_json(report_path, report)
    torch.set_num_threads(4); os.environ.setdefault('OMP_NUM_THREADS', '4')
    if hasattr(pycolmap, 'set_random_seed'): pycolmap.set_random_seed(0)
    try:
        save('features')
        if reuse_from:
            from reuse_artsquad_cache import reuse_cache
            report['cache_reuse'] = reuse_cache(work, Path(reuse_from).resolve(), config, records)
            save('features')
        global_features = extract_features.main(extract_features.confs['netvlad'], work / 'images', work,
                                                image_list=names, as_half=False)
        local_conf = {'output': f'feats-superpoint-n{keypoints}-r{resize}',
                      'model': {'name': 'superpoint', 'nms_radius': 3, 'max_keypoints': keypoints},
                      'preprocessing': {'grayscale': True, 'resize_max': resize}}
        features = extract_features.main(local_conf, work / 'images', work, image_list=names, as_half=False)
        save('matching')
        raw_pairs = work / 'pairs-retrieval.txt'
        pairs_from_retrieval.main(global_features, raw_pairs, min(neighbors, len(names) - 1), query_list=names, db_list=names)
        unique = sorted({tuple(sorted(line.split())) for line in raw_pairs.read_text().splitlines() if line.strip()})
        pairs = work / 'pairs.txt'; pairs.write_text(''.join(a + ' ' + b + '\n' for a, b in unique))
        report['candidate_pairs'] = len(unique)
        matches = work / 'matches-lightglue.h5'
        match_features.main(match_features.confs['superpoint+lightglue'], pairs, features, matches=matches)
        sfm = work / 'sfm'; sfm.mkdir(exist_ok=True); database = sfm / 'database.db'
        ready = sfm / 'database-ready.json'
        if not ready.exists():
            if database.exists(): raise RuntimeError('Interrupted database preserved. Use a new --run-label to rebuild without overwriting it.')
            save('geometric_verification')
            reconstruction.create_empty_db(database)
            reconstruction.import_images(work / 'images', database, pycolmap.CameraMode.PER_IMAGE, names,
                                          {'camera_model': 'SIMPLE_RADIAL', 'default_focal_length_factor': 1.2})
            ids = reconstruction.get_image_ids(database)
            with pycolmap.Database.open(database) as db:
                import_features(ids, db, features); import_matches(ids, db, pairs, matches)
            estimation_and_geometric_verification(database, pairs, False)
            write_json(ready, {'configuration': config, 'database_sha256': sha256(database)})
        graph = verified_graph(database, records); write_json(work / 'view-graph.json', graph)
        report['verified_pairs'] = graph['verified_pairs']; report['nondegenerate_pairs'] = graph['nondegenerate_pairs']
        save('mapping')
        models_path = sfm / 'models'
        if models_path.exists() and any(models_path.iterdir()):
            raise RuntimeError('Interrupted mapping preserved. Use a new --run-label rather than overwrite components.')
        models_path.mkdir(exist_ok=True)
        models = pycolmap.incremental_mapping(database, work / 'images', models_path,
                    options={'num_threads': 4, 'ba_refine_focal_length': True,
                             'ba_refine_extra_params': True, 'min_focal_length_ratio': .25,
                             'max_focal_length_ratio': 4.0, 'min_model_size': 2})
        write_json(sfm / 'mapping-complete.json', {'api_manager_keys': sorted(map(int, models)),
                                                 'meaning': 'Mapper returned; not scientific milestone acceptance.'})
        report['components'] = saved_component_reports(models_path, records)
        report['component_identity'] = 'Native saved directory ID, not API ReconstructionManager key'
        report['unregistered_images'] = sorted(set(names) - {c['name'] for comp in report['components'] for c in comp['cameras']})
        report['status'] = 'sfm_complete' if models else 'no_model'
        save('finished')
    except Exception as error:
        report.update(status='error', error=type(error).__name__ + ': ' + str(error)); save(report['stage'])
        raise
    return work


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--workspace', type=Path, default=ROOT / 'artifacts/artsquad_modern')
    parser.add_argument('--resize', type=int, default=1200)
    parser.add_argument('--keypoints', type=int, default=4096)
    parser.add_argument('--neighbors', type=int, default=8)
    parser.add_argument('--targets', nargs='*', default=[])
    parser.add_argument('--run-label', default='default')
    parser.add_argument('--reuse-from', type=Path, help='Reuse only hash/config-verified train features and pair matches, never native geometry')
    args = parser.parse_args()
    if args.resize < 640 or args.keypoints < 512 or args.neighbors < 1: parser.error('Invalid feature/retrieval budget')
    print(run(args.snapshot, args.workspace, args.resize, args.keypoints, args.neighbors, args.targets, args.run_label, args.reuse_from), flush=True)


if __name__ == '__main__': main()
