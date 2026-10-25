import json
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pycolmap

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pipeline'))
from run_artsquad_calibration_variant import (assert_fixed_camera_constraints, inspect_initial_database,
                                             json_options, native_options, prepare_variant_database,
                                             run, validate_source)
from run_artsquad_sfm import sha256, write_json


def fixture_database(path, names=('a.jpg', 'b.jpg')):
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as db:
        db.executescript('CREATE TABLE cameras(camera_id INTEGER PRIMARY KEY,model INTEGER,width INTEGER,height INTEGER,params BLOB,prior_focal_length INTEGER);'
                         'CREATE TABLE images(image_id INTEGER PRIMARY KEY,name TEXT,camera_id INTEGER);'
                         'CREATE TABLE keypoints(image_id INTEGER PRIMARY KEY,rows INTEGER,cols INTEGER,data BLOB);'
                         'CREATE TABLE descriptors(image_id INTEGER PRIMARY KEY,rows INTEGER,cols INTEGER,data BLOB);'
                         'CREATE TABLE matches(pair_id INTEGER PRIMARY KEY,rows INTEGER,cols INTEGER,data BLOB);'
                         'CREATE TABLE two_view_geometries(pair_id INTEGER PRIMARY KEY,rows INTEGER,cols INTEGER,data BLOB,config INTEGER);'
                         'CREATE TABLE pose_priors(image_id INTEGER,position BLOB);')
        for identifier, name in enumerate(names, 1):
            params = np.asarray([800. + identifier, 500., 400., 0.], dtype=np.float64).tobytes()
            db.execute('INSERT INTO cameras VALUES(?,?,?,?,?,?)', (identifier, 2, 1000, 800, params, 1))
            db.execute('INSERT INTO images VALUES(?,?,?)', (identifier, name, identifier))
            db.execute('INSERT INTO keypoints VALUES(?,?,?,?)', (identifier, 20, 2, b'keypoints'))
            db.execute('INSERT INTO descriptors VALUES(?,?,?,?)', (identifier, 20, 128, b'descriptors'))
        db.execute('INSERT INTO matches VALUES(?,?,?,?)', (2147483649, 20, 2, b'matches'))
        db.execute('INSERT INTO two_view_geometries VALUES(?,?,?,?,?)', (2147483649, 20, 2, b'verified-inliers', 2))
        db.execute('INSERT INTO pose_priors VALUES(?,?)', (1, b'discard-me'))


def fixture_source(root):
    source = root / 'source'
    (source / 'images').mkdir(parents=True)
    records = []
    for index, name in enumerate(('a.jpg', 'b.jpg')):
        path = source / 'images' / name
        path.write_bytes(('fixture bytes ' + name).encode())
        records.append({'filename': name, 'working_path': str(path), 'sha256_working': sha256(path),
                        'split': 'train', 'role': 'scene-candidate', 'validation': {'passed': True},
                        'exposure_group_id': 'e' + str(index), 'source_family_id': 'f' + str(index),
                        'discovery': {'targets': ['morrill']}})
    snapshot_path = root / 'snapshot.json'
    write_json(snapshot_path, {'snapshot_id': 'frozen', 'images': records})
    config = {'snapshot_sha256': sha256(snapshot_path), 'extractor': 'SuperPoint', 'matcher': 'LightGlue',
              'retrieval': 'NetVLAD', 'resize': 1200, 'keypoints': 4096,
              'torch_version': 'fixture', 'pycolmap_version': pycolmap.__version__, 'targets': []}
    write_json(source / 'configuration.json', config)
    write_json(source / 'report.json', {'status': 'sfm_complete', 'snapshot_path': str(snapshot_path),
                                      'snapshot_id': 'frozen', 'run_id': 'source', 'configuration': config,
                                      'input_images': ['a.jpg', 'b.jpg'], 'components': []})
    fixture_database(source / 'sfm/database.db')
    write_json(source / 'sfm/mapping-complete.json', {'returned': True})
    (source / 'sfm/models/0').mkdir(parents=True)
    (source / 'sfm/models/0/images.bin').write_bytes(b'global fitted poses must never be copied')
    for filename in ('matches-lightglue.h5', 'global-feats-netvlad.h5', 'feats-superpoint-n4096-r1200.h5'):
        (source / filename).write_bytes(b'cache fixture only, never published')
    (source / 'pairs.txt').write_text('a.jpg b.jpg\n')
    return source, snapshot_path


def fake_cache(destination, source, config, records):
    for filename in ('matches-lightglue.h5', 'global-feats-netvlad.h5', 'feats-superpoint-n4096-r1200.h5'):
        shutil.copy2(source / filename, destination / filename)
    return {'database_or_native_model_reused': False, 'source_artifacts_unchanged': True}


class CalibrationVariantTests(unittest.TestCase):
    def test_fixed_radial_disables_ba_and_absolute_pose_radial_refinement(self):
        options = native_options('fixed-radial', pycolmap)
        self.assertFalse(options.ba_refine_extra_params)
        self.assertFalse(options.get_mapper().abs_pose_refine_extra_params)
        self.assertTrue(options.ba_refine_focal_length)
        self.assertTrue(options.get_mapper().abs_pose_refine_focal_length)
        self.assertFalse(options.ba_use_gpu)

    def test_fixed_intrinsics_also_disables_all_focal_refinement(self):
        options = native_options('fixed-intrinsics', pycolmap)
        self.assertFalse(options.ba_refine_extra_params)
        self.assertFalse(options.get_mapper().abs_pose_refine_extra_params)
        self.assertFalse(options.ba_refine_focal_length)
        self.assertFalse(options.get_mapper().abs_pose_refine_focal_length)
        self.assertFalse(options.ba_refine_principal_point)
        self.assertFalse(options.use_prior_position)

    def test_effective_child_bounds_propagate_and_options_serialize(self):
        options = native_options('fixed-radial', pycolmap)
        self.assertEqual(options.get_mapper().min_focal_length_ratio, .25)
        self.assertEqual(options.get_triangulation().max_focal_length_ratio, 4.)
        json.dumps(json_options(options.todict()), allow_nan=False)
        with self.assertRaises(ValueError): native_options('fakest', pycolmap)

    def test_initial_camera_copy_zeros_radial_only_and_preserves_verified_data(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory) / 'source.db', Path(directory) / 'new/database.db'
            fixture_database(source); before = sha256(source)
            result = prepare_variant_database(source, target, ['a.jpg', 'b.jpg'])
            self.assertEqual(sha256(source), before)
            self.assertFalse(result['fitted_model_or_global_poses_copied'])
            self.assertTrue(result['pairwise_geometric_verification_reused'])
            self.assertEqual(result['discarded_position_prior_count'], 1)
            with sqlite3.connect(target) as db:
                cameras = db.execute('SELECT params FROM cameras ORDER BY camera_id').fetchall()
                self.assertEqual(db.execute('SELECT COUNT(*) FROM pose_priors').fetchone()[0], 0)
            self.assertEqual(np.frombuffer(cameras[0][0], dtype=np.float64).tolist(), [801., 500., 400., 0.])
            self.assertEqual(result['initial_cameras'][0]['source_database_parameters'][-1], 0.)

    def test_existing_database_and_source_overwrite_are_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory) / 'source.db', Path(directory) / 'target.db'
            fixture_database(source); target.write_bytes(b'user-owned')
            for destination in (source, target):
                with self.assertRaises(ValueError): prepare_variant_database(source, destination, ['a.jpg', 'b.jpg'])
            self.assertEqual(target.read_bytes(), b'user-owned')

    def test_active_database_writer_sidecar_blocks_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory) / 'source.db', Path(directory) / 'target.db'
            fixture_database(source); Path(str(source) + '-wal').write_bytes(b'pending')
            with self.assertRaises(ValueError): prepare_variant_database(source, target, ['a.jpg', 'b.jpg'])
            self.assertFalse(target.exists())

    def test_foreign_or_heldout_database_names_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'source.db'; fixture_database(source)
            with self.assertRaises(ValueError): inspect_initial_database(source, ['a.jpg'])

    def test_no_verified_pairs_cannot_be_promoted(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'source.db'; fixture_database(source)
            with sqlite3.connect(source) as db: db.execute('UPDATE two_view_geometries SET rows=0')
            with self.assertRaises(ValueError): inspect_initial_database(source, ['a.jpg', 'b.jpg'])

    def test_nonzero_initial_radial_needs_fresh_verification_not_silent_reuse(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory) / 'source.db', Path(directory) / 'new.db'
            fixture_database(source)
            with sqlite3.connect(source) as db:
                db.execute('UPDATE cameras SET params=? WHERE camera_id=1',
                           (np.asarray([801., 500., 400., .1], dtype=np.float64).tobytes(),))
            with self.assertRaises(ValueError): prepare_variant_database(source, target, ['a.jpg', 'b.jpg'])
            self.assertFalse(target.exists())

    def test_unsupported_or_nonfinite_initial_cameras_rejected(self):
        for model, params in ((1, [800, 500, 400, 0]), (2, [float('nan'), 500, 400, 0])):
            with tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / 'source.db'; fixture_database(source)
                with sqlite3.connect(source) as db:
                    db.execute('UPDATE cameras SET model=?,params=? WHERE camera_id=1', (model, np.asarray(params, dtype=np.float64).tobytes()))
                with self.assertRaises(ValueError): inspect_initial_database(source, ['a.jpg', 'b.jpg'])

    def test_different_frozen_snapshot_rejected_before_db_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source, snapshot = fixture_source(root)
            different = root / 'other.json'; different.write_text(snapshot.read_text() + '\n')
            with self.assertRaises(ValueError): validate_source(source, different)

    def test_running_baseline_is_never_copied(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source, snapshot = fixture_source(root)
            report = json.loads((source / 'report.json').read_text()); report['status'] = 'running'
            write_json(source / 'report.json', report)
            with self.assertRaises(ValueError): validate_source(source)

    def test_source_native_intrinsics_not_read_for_initialization(self):
        with tempfile.TemporaryDirectory() as directory:
            source, snapshot = fixture_source(Path(directory))
            # The fixture's native binary is deliberately unreadable. The
            # preflight must still use the independent initial database.
            report, selected, frozen, records = validate_source(source)
            self.assertEqual(selected, snapshot)
            self.assertEqual(len(records), 2)

    def test_postfit_parameter_check_detects_unexpected_refinement(self):
        initial = [{'image_name': 'a.jpg', 'variant_initial_parameters': [801., 500., 400., 0.]}]
        good = [{'cameras': [{'name': 'a.jpg', 'camera_model': 'SIMPLE_RADIAL', 'camera_parameters': [801., 500., 400., 0.]}]}]
        self.assertTrue(assert_fixed_camera_constraints(good, initial, 'fixed-intrinsics')['fixed_parameters_unchanged'])
        good[0]['cameras'][0]['camera_parameters'][0] = 900.
        assert_fixed_camera_constraints(good, initial, 'fixed-radial')
        with self.assertRaises(RuntimeError): assert_fixed_camera_constraints(good, initial, 'fixed-intrinsics')
        good[0]['cameras'][0]['camera_parameters'][3] = .1
        with self.assertRaises(RuntimeError): assert_fixed_camera_constraints(good, initial, 'fixed-radial')

    def test_mock_native_execution_never_copies_global_model_and_guards_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source, snapshot = fixture_source(root)
            before = {str(p): sha256(p) for p in source.rglob('*') if p.is_file()}
            with mock.patch('pycolmap.incremental_mapping', return_value={}) as mapper, \
                 mock.patch('reuse_artsquad_cache.reuse_cache', side_effect=fake_cache):
                work = run(source, 'fixed-radial', root / 'workspace')
                self.assertEqual(mapper.call_count, 1)
                self.assertFalse((work / 'sfm/models/0/images.bin').exists())
                report = json.loads((work / 'report.json').read_text())
                self.assertEqual(report['status'], 'no_model')
                self.assertEqual(report['held_out_images_used_in_mapping'], 0)
                self.assertTrue(report['source_artifacts_unchanged'])
                self.assertEqual(work, run(source, 'fixed-radial', root / 'workspace'))
                self.assertEqual(mapper.call_count, 1)
                (work / 'sfm/database.db').write_bytes(b'changed')
                with self.assertRaises(RuntimeError): run(source, 'fixed-radial', root / 'workspace')
            self.assertEqual(before, {str(p): sha256(p) for p in source.rglob('*') if p.is_file()})


if __name__ == '__main__': unittest.main()
