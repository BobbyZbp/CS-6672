#!/usr/bin/env python3
"""Same-snapshot CPU remapping sensitivity test, never a calibration truth claim.

A new run copies the baseline's verified database, including pairwise geometry,
but NEVER its fitted model or global poses. Intrinsics start from database
initialization, not reconstructed cameras. Source artifacts remain unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from ghostmap.sfm.learned import ROOT, saved_component_reports, select_training_images, sha256, stage_images, verified_graph, write_json

VERSION = 1
MODES = ('fixed-radial', 'fixed-intrinsics', 'exif-anchored')
# exif-anchored: cameras whose database focal came from EXIF (COLMAP's image
# reader sets prior_focal_length from the 35 mm equivalent or its sensor-width
# table) are held constant; the rest refine focal inside a tighter window.
EXIF_ANCHORED_FOCAL_RATIO = (.5, 3.)
PROTECTED_TABLES = ('images', 'keypoints', 'descriptors', 'matches', 'two_view_geometries')


def native_options(mode, pycolmap, exif_camera_ids=()):
    if mode not in MODES: raise ValueError('Unknown calibration variant')
    options = pycolmap.IncrementalPipelineOptions()
    options.num_threads = 4
    options.random_seed = 0
    options.min_model_size = 2
    options.multiple_models = True
    options.ba_use_gpu = False
    options.min_focal_length_ratio = .25
    options.max_focal_length_ratio = 4.
    options.max_extra_param = 1.
    options.ba_refine_extra_params = False
    options.ba_refine_principal_point = False
    options.ba_refine_focal_length = mode != 'fixed-intrinsics'
    options.mapper.abs_pose_refine_extra_params = False
    options.mapper.abs_pose_refine_focal_length = mode != 'fixed-intrinsics'
    options.use_prior_position = False
    if mode == 'exif-anchored':
        options.min_focal_length_ratio, options.max_focal_length_ratio = EXIF_ANCHORED_FOCAL_RATIO
        options.constant_cameras = set(int(i) for i in exif_camera_ids)
    return options


def exif_camera_ids(initial):
    """Database cameras whose initial focal length is an EXIF prior."""
    return sorted(camera['camera_id'] for camera in initial if camera['database_prior_focal_length'])


def json_options(value):
    if isinstance(value, dict): return {str(k): json_options(v) for k, v in value.items()}
    if isinstance(value, (tuple, list, set)): return [json_options(v) for v in sorted(value)] if isinstance(value, set) else [json_options(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None: return value
    if hasattr(value, 'name'): return value.name
    raise ValueError('Unserializable native option: ' + type(value).__name__)


def _assert_unchanged(hashes):
    for path, digest in hashes.items():
        if not Path(path).is_file() or sha256(path) != digest:
            raise RuntimeError('Baseline/source artifact changed: ' + path)


def _ro(database):
    return sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True)


def _table_digests(connection):
    """Exact logical rows: SQLite file headers may change on a normal open."""
    available = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    hashes = {}
    for table in PROTECTED_TABLES:
        if table not in available: raise ValueError('Verified database lacks required table: ' + table)
        digest = hashlib.sha256()
        for row in connection.execute('SELECT * FROM ' + table + ' ORDER BY 1'):
            for value in row:
                blob = value if isinstance(value, bytes) else json.dumps(value, allow_nan=False).encode()
                digest.update(len(blob).to_bytes(8, 'big')); digest.update(blob)
        hashes[table] = digest.hexdigest()
    return hashes


def inspect_initial_database(database, expected_names):
    """Use only initial DB cameras; never read fitted native camera parameters."""
    with _ro(database) as db:
        images = list(db.execute('SELECT image_id,name,camera_id FROM images ORDER BY image_id'))
        names = [row[1] for row in images]
        if len(names) != len(set(names)) or set(names) != set(expected_names):
            raise ValueError('Verified source database must contain exactly this frozen training selection')
        if len({row[2] for row in images}) != len(images): raise ValueError('Per-image initial cameras required')
        cameras = list(db.execute('SELECT camera_id,model,width,height,params,prior_focal_length FROM cameras ORDER BY camera_id'))
        if {row[0] for row in cameras} != {row[2] for row in images}: raise ValueError('Unused or missing database cameras')
        initial = []
        for identifier, model, width, height, blob, prior in cameras:
            params = np.frombuffer(blob, dtype=np.float64).copy() if isinstance(blob, bytes) else np.asarray([])
            if model != 2 or params.shape != (4,): raise ValueError('Only SIMPLE_RADIAL database initialization is supported')
            if not np.isfinite(params).all() or params[0] <= 0 or min(width, height) <= 0: raise ValueError('Invalid initial database camera')
            if abs(params[3]) > 1e-12:
                raise ValueError('Verified database initial k must already be zero; changing verification intrinsics requires fresh two-view verification')
            initial.append({'camera_id': int(identifier), 'image_name': next(row[1] for row in images if row[2] == identifier),
                            'model': 'SIMPLE_RADIAL', 'width': int(width), 'height': int(height),
                            'source_database_parameters': params.tolist(),
                            'variant_initial_parameters': [float(params[0]), float(params[1]), float(params[2]), 0.],
                            'database_prior_focal_length': bool(prior)})
        logical_hashes = _table_digests(db)
        positive_pairs = int(db.execute('SELECT COUNT(*) FROM two_view_geometries WHERE rows>0').fetchone()[0])
        if positive_pairs == 0: raise ValueError('Source database has no geometrically verified pairs')
        available = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'rig_sensors' in available and db.execute('SELECT COUNT(*) FROM rig_sensors').fetchone()[0]:
            raise ValueError('Non-reference multi-sensor rigs are outside this per-image sensitivity experiment')
    return initial, logical_hashes, positive_pairs


def prepare_variant_database(source, destination, expected_names):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination or destination.exists(): raise ValueError('New database path required; no overwrite or in-place edit')
    for suffix in ('-wal', '-journal'):
        sidecar = Path(str(source) + suffix)
        if sidecar.exists() and sidecar.stat().st_size:
            raise ValueError('Source SQLite writer/transaction sidecar is active; wait for terminal baseline')
    before = sha256(source)
    initial, logical_hashes, positive_pairs = inspect_initial_database(source, expected_names)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    if sha256(destination) != before: raise RuntimeError('Database copy did not preserve exact source bytes')
    with sqlite3.connect(destination) as db:
        for camera in initial:
            blob = np.asarray(camera['variant_initial_parameters'], dtype=np.float64).tobytes()
            db.execute('UPDATE cameras SET params=? WHERE camera_id=?', (blob, camera['camera_id']))
        available = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        cleared_priors = int(db.execute('SELECT COUNT(*) FROM pose_priors').fetchone()[0]) if 'pose_priors' in available else 0
        if 'pose_priors' in available: db.execute('DELETE FROM pose_priors')
        if _table_digests(db) != logical_hashes: raise RuntimeError('Training images/features/verified matches changed during intrinsics initialization')
    if sha256(source) != before: raise RuntimeError('Source database changed during copying')
    return {'source_database_sha256': before, 'initialized_database_sha256': sha256(destination),
            'initial_cameras': initial, 'verified_pair_count': positive_pairs,
            'preserved_verified_input_tables_sha256': logical_hashes,
            'discarded_position_prior_count': cleared_priors,
            'fitted_model_or_global_poses_copied': False,
            'pairwise_geometric_verification_reused': True,
            'initialization': 'Source database focal/principal point, k reset to zero; never final native-model intrinsics.'}


def validate_source(source, snapshot_path=None):
    source = Path(source).resolve()
    report_path = source / 'report.json'
    report = json.loads(report_path.read_text())
    if report.get('status') not in {'sfm_complete', 'no_model'} or not (source / 'sfm/mapping-complete.json').is_file():
        raise ValueError('Completed baseline mapping required; do not copy a live database')
    config = report['configuration']
    if config.get('extractor') != 'SuperPoint' or config.get('matcher') != 'LightGlue':
        raise ValueError('This remapper currently requires the learned SuperPoint/LightGlue baseline')
    if json.loads((source / 'configuration.json').read_text()) != config: raise ValueError('Baseline report/configuration differ')
    original_snapshot = Path(report['snapshot_path']).resolve()
    snapshot_path = Path(snapshot_path).resolve() if snapshot_path else original_snapshot
    if sha256(original_snapshot) != config['snapshot_sha256'] or sha256(snapshot_path) != config['snapshot_sha256']:
        raise ValueError('Verified database cannot be reused across different frozen snapshots')
    snapshot = json.loads(snapshot_path.read_text())
    if snapshot['snapshot_id'] != report['snapshot_id']: raise ValueError('Baseline snapshot identity mismatch')
    records = select_training_images(snapshot, config.get('targets', []))
    if {r['filename'] for r in records} != set(report['input_images']): raise ValueError('Baseline training list differs from frozen selection')
    for row in records:
        if sha256(row['working_path']) != row['sha256_working'] or sha256(source / 'images' / row['filename']) != row['sha256_working']:
            raise ValueError('Training bytes changed: ' + row['filename'])
    inspect_initial_database(source / 'sfm/database.db', [r['filename'] for r in records])
    return report, snapshot_path, snapshot, records


def assert_fixed_camera_constraints(components, initial, mode):
    """Inspect actual saved parameters; flags alone are not proof of freezing."""
    if mode not in MODES: raise ValueError('Unknown calibration variant')
    lookup = {camera['image_name']: camera for camera in initial}
    checked = 0
    for component in components:
        for camera in component['cameras']:
            if camera['name'] not in lookup or camera['camera_model'] != 'SIMPLE_RADIAL':
                raise RuntimeError('Unexpected saved camera in calibration variant')
            params = np.asarray(camera['camera_parameters'], dtype=float)
            if params.shape != (4,) or not np.isfinite(params).all() or abs(params[3]) > 1e-12:
                raise RuntimeError('Native output violated fixed radial k=0')
            expected = np.asarray(lookup[camera['name']]['variant_initial_parameters'])
            if not np.allclose(params[1:3], expected[1:3], atol=1e-9, rtol=0):
                raise RuntimeError('Native output changed the fixed principal point')
            if mode == 'fixed-intrinsics' and not np.allclose(params, expected, atol=1e-9, rtol=1e-12):
                raise RuntimeError('Native output violated fixed database-initial intrinsics')
            if mode == 'exif-anchored' and lookup[camera['name']]['database_prior_focal_length'] and not np.allclose(params, expected, atol=1e-9, rtol=1e-12):
                raise RuntimeError('Native output changed an EXIF-anchored camera')
            checked += 1
    return {'checked_native_component_cameras': checked, 'fixed_parameters_unchanged': True,
            'interpretation': 'Parameter freezing verified, not correct calibration or geometry.'}


def run(source, mode, workspace=ROOT / 'artifacts/artsquad_modern', label='default', snapshot_path=None):
    import pycolmap
    from ghostmap.sfm.cache_reuse import reuse_cache

    source = Path(source).resolve()
    source_report, snapshot_path, snapshot, records = validate_source(source, snapshot_path)
    initial, _, _ = inspect_initial_database(source / 'sfm/database.db', [r['filename'] for r in records])
    options = native_options(mode, pycolmap, exif_camera_ids(initial))
    source_files = [source / 'report.json', source / 'configuration.json', source / 'sfm/database.db',
                    source / 'sfm/mapping-complete.json', Path(source_report['snapshot_path']).resolve(), snapshot_path]
    source_files += list((source / 'sfm/models').glob('*/*.bin'))
    source_files += [source / 'images' / row['filename'] for row in records]
    source_files += [source / 'pairs.txt', source / 'matches-lightglue.h5', source / 'global-feats-netvlad.h5',
                     source / f"feats-superpoint-n{source_report['configuration']['keypoints']}-r{source_report['configuration']['resize']}.h5"]
    before = {str(p): sha256(p) for p in source_files}
    config = dict(source_report['configuration'])
    config.update(pipeline_version=VERSION, method='same-snapshot-calibration-sensitivity', calibration_variant=mode,
                  run_label=label, source_run_id=source_report['run_id'], source_database_sha256=sha256(source / 'sfm/database.db'),
                  source_configuration_sha256=sha256(source / 'configuration.json'),
                  pycolmap_version=pycolmap.__version__, native_mapping_options=json_options(options.todict()),
                  initial_calibration='source-database-initial-not-fitted-cameras; SIMPLE_RADIAL k=0',
                  estimated_global_poses_reused=False, verified_database_reused_same_snapshot_only=True)
    run_id = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:20]
    work = Path(workspace).resolve() / 'runs' / run_id
    if work == source: raise ValueError('Variant source and destination must differ')
    if work.exists() and any(work.iterdir()):
        config_path, report_path = work / 'configuration.json', work / 'report.json'
        if config_path.is_file() and report_path.is_file() and json.loads(config_path.read_text()) == config:
            completed = json.loads(report_path.read_text())
            if completed.get('status') in {'sfm_complete', 'no_model'} and completed.get('source_artifacts_unchanged') is True:
                _assert_unchanged(before)
                if not (work / 'sfm/mapping-complete.json').is_file() or not completed.get('output_artifacts_sha256'):
                    raise ValueError('Completed variant lacks native completion/integrity evidence')
                _assert_unchanged(completed['output_artifacts_sha256'])
                return work
        raise RuntimeError('Existing/interrupted variant preserved; use a new --run-label, never overwrite native outputs')
    work.mkdir(parents=True, exist_ok=True)
    write_json(work / 'configuration.json', config)
    names = [r['filename'] for r in records]
    report = {'schema_version': 1, 'run_id': run_id, 'snapshot_id': snapshot['snapshot_id'],
              'snapshot_path': str(snapshot_path), 'configuration': config, 'input_images': names,
              'held_out_images_used_in_mapping': 0, 'status': 'running', 'stage': 'preflight', 'components': [],
              'created_utc': datetime.now(timezone.utc).isoformat(),
              'source_artifacts_sha256': before,
              'limitations': ['Calibration sensitivity test, not an accuracy, target identity, independent exposure or multi-building validation.',
                              'A fixed zero-distortion or fixed database-initial focal camera can itself be wrong; no variant is selected by aesthetic quality.',
                              'Only the same frozen training database and its pairwise verification are reused. No global fitted poses, points or final native camera parameters are loaded.',
                              'No held-out images, manual correspondences, geographic layout priors, component alignment, dense surface or generated geometry are introduced.']}
    started = time.monotonic()
    def save(stage):
        report.update(stage=stage, elapsed_seconds=round(time.monotonic() - started, 2))
        write_json(work / 'report.json', report)
    save('preflight')
    try:
        stage_images(records, work / 'images')
        report['cache_reuse'] = reuse_cache(work, source, config, records)
        # The cache helper copies descriptor/match groups only. The separate,
        # explicitly scoped same-snapshot database copy below is not its action.
        shutil.copy2(source / 'pairs.txt', work / 'pairs.txt')
        report['database_reuse'] = prepare_variant_database(source / 'sfm/database.db', work / 'sfm/database.db', names)
        write_json(work / 'sfm/database-ready.json', {'configuration': config,
                   'database_sha256': sha256(work / 'sfm/database.db'), 'same_snapshot_verification_provenance': report['database_reuse']})
        graph = verified_graph(work / 'sfm/database.db', records)
        write_json(work / 'view-graph.json', graph)
        report.update(candidate_pairs=len((work / 'pairs.txt').read_text().splitlines()), verified_pairs=graph['verified_pairs'], nondegenerate_pairs=graph['nondegenerate_pairs'])
        _assert_unchanged(before)
        save('mapping')
        models_path = work / 'sfm/models'; models_path.mkdir()
        if hasattr(pycolmap, 'set_random_seed'): pycolmap.set_random_seed(0)
        returned = pycolmap.incremental_mapping(str(work / 'sfm/database.db'), str(work / 'images'), str(models_path), options=options)
        write_json(work / 'sfm/mapping-complete.json', {'api_manager_keys': sorted(map(int, returned)),
                   'meaning': 'Native sensitivity mapper returned; not calibration or milestone validation.'})
        report['components'] = saved_component_reports(models_path, records)
        report['fixed_parameter_check'] = assert_fixed_camera_constraints(report['components'], report['database_reuse']['initial_cameras'], mode)
        report['component_identity'] = 'Native saved directory ID, not API ReconstructionManager key'
        report['unregistered_images'] = sorted(set(names) - {c['name'] for component in report['components'] for c in component['cameras']})
        report['output_native_sha256'] = {str(p): sha256(p) for p in models_path.glob('*/*.bin')}
        report['mapping_database_sha256'] = sha256(work / 'sfm/database.db')
        output_files = list(models_path.glob('*/*.bin')) + [work / 'sfm/database.db', work / 'sfm/mapping-complete.json', work / 'configuration.json']
        output_files += [work / 'images' / name for name in names]
        output_files += [work / filename for filename in ('pairs.txt', 'matches-lightglue.h5', 'global-feats-netvlad.h5',
                         f"feats-superpoint-n{config['keypoints']}-r{config['resize']}.h5")]
        report['output_artifacts_sha256'] = {str(p): sha256(p) for p in output_files}
        _assert_unchanged(before)
        report['source_artifacts_unchanged'] = True
        report['status'] = 'sfm_complete' if report['components'] else 'no_model'
        save('finished')
    except Exception as error:
        report.update(status='error', error=type(error).__name__ + ': ' + str(error))
        save(report['stage'])
        raise
    finally:
        _assert_unchanged(before)
    return work


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-run', required=True, type=Path)
    parser.add_argument('--variant', choices=MODES, required=True)
    parser.add_argument('--snapshot', type=Path, help='Optional explicit identical frozen snapshot; differing hashes are rejected')
    parser.add_argument('--workspace', type=Path, default=ROOT / 'artifacts/artsquad_modern')
    parser.add_argument('--run-label', default='default')
    args = parser.parse_args()
    print(run(args.source_run, args.variant, args.workspace, args.run_label, args.snapshot), flush=True)


if __name__ == '__main__': main()
