"""Immutable-map holdout tests; HLOC inference is mocked, never downloaded."""

import hashlib
import json
import math
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import h5py
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
from validate_artsquad_holdouts import (assert_unchanged, camera_prior, immutable_hashes,
                                       run, select_holdout_images, summarize_residuals,
                                       validate_feature_names, validate_frozen_files)


def record(name, split="train", role="scene-candidate"):
    return {"filename": name, "split": split, "role": role,
            "validation": {"passed": True}, "exposure_group_id": "exp-" + name,
            "source_family_id": "family-" + name, "discovery": {"targets": ["morrill"]}}


def feature_file(path, names):
    with h5py.File(path, "w") as file:
        for name in names:
            file.create_group(name).create_dataset("keypoints", data=[[1., 2.]])


class HoldoutSelectionTests(unittest.TestCase):
    def test_only_admitted_test_scene_images_become_queries(self):
        images = [record("train.jpg"), record("test.jpg", "test"), record("excluded.jpg", "excluded"),
                  record("interior.jpg", "test", "interior"), record("rejected.jpg", "test")]
        images[-1]["validation"]["passed"] = False
        selected = select_holdout_images({"images": images}, ["train.jpg"])
        self.assertEqual([r["filename"] for r in selected], ["test.jpg"])

    def test_query_filename_exposure_and_family_leakage_rejected(self):
        for key in ("filename", "exposure_group_id", "source_family_id"):
            with self.subTest(key=key):
                train, query = record("train.jpg"), record("test.jpg", "test")
                query[key] = train[key]
                with self.assertRaises(ValueError):
                    select_holdout_images({"images": [train, query]}, ["train.jpg"])

    def test_leakage_is_global_not_just_selected_component(self):
        selected, other, query = record("selected.jpg"), record("other.jpg"), record("test.jpg", "test")
        query["source_family_id"] = other["source_family_id"]
        with self.assertRaises(ValueError):
            select_holdout_images({"images": [selected, other, query]}, ["selected.jpg"])

    def test_model_cannot_contain_test_excluded_or_undeclared_images(self):
        images = [record("train.jpg"), record("test.jpg", "test"), record("excluded.jpg", "excluded")]
        for names in (["test.jpg"], ["excluded.jpg"], ["unknown.jpg"], ["train.jpg", "train.jpg"]):
            with self.subTest(names=names), self.assertRaises(ValueError):
                select_holdout_images({"images": images}, names)

    def test_missing_query_group_ids_fail_closed(self):
        for key in ("filename", "exposure_group_id", "source_family_id"):
            for value in (None, "", "  "):
                query = record("test.jpg", "test")
                query[key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    select_holdout_images({"images": [record("train.jpg"), query]}, ["train.jpg"])

    def test_query_names_are_safe_basenames(self):
        for name in ("../test.jpg", "/test.jpg", "two words.jpg"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                select_holdout_images({"images": [record("train.jpg"), record(name, "test")]}, ["train.jpg"])

    def test_duplicate_query_filenames_fail(self):
        with self.assertRaises(ValueError):
            select_holdout_images({"images": [record("train.jpg"), record("q.jpg", "test"), record("q.jpg", "test")]}, ["train.jpg"])

    def test_no_test_images_is_not_fabricated_validation(self):
        self.assertEqual(select_holdout_images({"images": [record("train.jpg")]}, ["train.jpg"]), [])


class CameraPriorTests(unittest.TestCase):
    def test_equivalent_35mm_uses_diagonal_convention(self):
        prior = camera_prior({"exif": {"focal_length_35mm": "50"}}, 1200, 800)
        self.assertAlmostEqual(prior["params"][0], 50 * 1200 / 36)
        self.assertFalse(prior["unknown_focal"])
        self.assertEqual(prior["params"][1:], [600, 400, 0])

    def test_portrait_and_non_35mm_aspect_are_not_width_sensor_assumptions(self):
        prior = camera_prior({"exif": {"focal_length_35mm": "35/1"}}, 900, 1200)
        self.assertAlmostEqual(prior["params"][0], 35 * 1500 / math.hypot(36, 24))

    def test_millimeter_only_exif_does_not_invent_sensor_width(self):
        prior = camera_prior({"exif": {"focal_length_mm": "5.8"}}, 1600, 1200)
        self.assertTrue(prior["unknown_focal"])
        self.assertEqual(prior["params"][0], 1920)
        self.assertEqual(prior["source"], "explicit-unknown-focal-factor")

    def test_invalid_exif_is_explicit_unknown(self):
        for value in (None, "", "0", "nan", "1/0", "-35", "3000"):
            with self.subTest(value=value):
                prior = camera_prior({"exif": {"focal_length_35mm": value}}, 1200, 800, 0.8)
                self.assertTrue(prior["unknown_focal"])
                self.assertEqual(prior["params"][0], 960)

    def test_bad_dimensions_or_prior_rejected(self):
        for dimensions in ((0, 800), (1000, -1), (1200.5, 800)):
            with self.subTest(dimensions=dimensions), self.assertRaises(ValueError):
                camera_prior({}, *dimensions)
        for value in (0, -1, float("nan"), float("inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                camera_prior({}, 1200, 800, value)


class ImmutableInputTests(unittest.TestCase):
    def test_frozen_hash_verified_and_changed_input_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "query.jpg"
            path.write_bytes(b"initial")
            row = {"working_path": str(path), "sha256_working": hashlib.sha256(b"initial").hexdigest()}
            validate_frozen_files([row])
            path.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "Frozen input changed"):
                validate_frozen_files([row])

    def test_reference_before_after_hashes_detect_mutation_or_deletion(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mapping.db"
            path.write_bytes(b"immutable")
            before = immutable_hashes([path])
            assert_unchanged(before)
            path.write_bytes(b"mutated")
            with self.assertRaisesRegex(RuntimeError, "mutated"):
                assert_unchanged(before)
            path.unlink()
            with self.assertRaisesRegex(RuntimeError, "mutated"):
                assert_unchanged(before)

    def test_reference_features_cannot_contain_test_or_undeclared_names(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "features.h5"
            feature_file(path, ["train.jpg"])
            self.assertEqual(validate_feature_names(path, ["train.jpg"]), {"train.jpg"})
            feature_file(path, ["train.jpg", "heldout.jpg"])
            with self.assertRaisesRegex(ValueError, "undeclared"):
                validate_feature_names(path, ["train.jpg"])

    def test_empty_feature_file_does_not_validate(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "features.h5"
            feature_file(path, [])
            with self.assertRaises(ValueError):
                validate_feature_names(path, ["train.jpg"])

    def test_empty_or_nonfinite_residuals_do_not_report_zero_error(self):
        for values in ([], [float("nan"), float("inf")]):
            result = summarize_residuals(values)
            self.assertEqual(result["finite_count"], 0)
            self.assertIsNone(result["median_px"])
        result = summarize_residuals([3., 4.])
        self.assertEqual(result["median_px"], 3.5)
        self.assertAlmostEqual(result["rms_px"], math.sqrt(12.5))


class MockedLocalizationTests(unittest.TestCase):
    """Exercise separation and failure reporting without invoking any ML model."""

    def fixture(self, root, with_query=True):
        run_path = root / "run"
        model_path = run_path / "sfm/models/0"
        model_path.mkdir(parents=True)
        (model_path / "images.bin").write_bytes(b"native-model-bytes")
        (run_path / "sfm/database.db").write_bytes(b"native-database-bytes")
        rows = [record("train.jpg")]
        if with_query:
            rows.append(record("query.jpg", "test"))
        for row in rows:
            path = root / row["filename"]
            Image.new("RGB", (160, 120), "gray").save(path)
            row.update(working_path=str(path), sha256_working=hashlib.sha256(path.read_bytes()).hexdigest())
        snapshot_path = root / "snapshot.json"
        snapshot_path.write_text(json.dumps({"snapshot_id": "fixture-snapshot", "images": rows}))
        config = {"keypoints": 4096, "resize": 1200, "snapshot_sha256": hashlib.sha256(snapshot_path.read_bytes()).hexdigest()}
        report = {"status": "sfm_complete", "run_id": "fixture-run", "snapshot_id": "fixture-snapshot",
                  "snapshot_path": str(snapshot_path), "components": [{"id": "0"}], "configuration": config}
        (run_path / "report.json").write_text(json.dumps(report))
        feature_file(run_path / "global-feats-netvlad.h5", ["train.jpg"])
        feature_file(run_path / "feats-superpoint-n4096-r1200.h5", ["train.jpg"])
        return run_path

    def modules(self, run_path, mutate_database=False):
        train = types.SimpleNamespace(name="train.jpg", has_pose=True)
        model = types.SimpleNamespace(images={1: train})
        pycolmap = types.SimpleNamespace(__version__="fixture", Reconstruction=Mock(return_value=model), Camera=Mock())
        torch = types.SimpleNamespace(__version__="fixture", set_num_threads=Mock())
        extract_calls, match_calls = [], []

        def extract(conf, image_dir, output, *, image_list, as_half):
            extract_calls.append(list(image_list))
            path = output / (conf["output"] + ".h5")
            feature_file(path, image_list)
            return path

        def retrieval(features, pairs, count, *, query_list, db_list, db_descriptors):
            self.assertEqual(query_list, ["query.jpg"])
            self.assertEqual(db_list, ["train.jpg"])
            self.assertEqual(db_descriptors, run_path / "global-feats-netvlad.h5")
            pairs.write_text("query.jpg train.jpg\n")

        def match(conf, pairs, features, *, matches, features_ref):
            match_calls.append({"query_features": features, "reference_features": features_ref})
            self.assertIn("holdouts", str(features))
            self.assertEqual(features_ref, run_path / "feats-superpoint-n4096-r1200.h5")
            matches.write_bytes(b"mock query-only matches")

        def pose(*args):
            if mutate_database:
                (run_path / "sfm/database.db").write_bytes(b"unexpected-reference-mutation")
            return None, {"num_matches": 0, "points3D_ids": [], "keypoint_index_to_db": ([], [])}

        hloc = types.SimpleNamespace(extract_features=types.SimpleNamespace(confs={"netvlad": {"output": "query-global"}}, main=extract),
                                     match_features=types.SimpleNamespace(confs={"superpoint+lightglue": {}}, main=match),
                                     pairs_from_retrieval=types.SimpleNamespace(main=retrieval))
        modules = {"pycolmap": pycolmap, "torch": torch, "hloc": hloc,
                   "hloc.localize_sfm": types.SimpleNamespace(QueryLocalizer=Mock(), pose_from_cluster=pose),
                   "hloc.utils.parsers": types.SimpleNamespace(parse_retrieval=lambda _: {"query.jpg": ["train.jpg"]})}
        return modules, extract_calls, match_calls

    def test_failed_pnp_never_falls_back_to_nearest_training_camera(self):
        with tempfile.TemporaryDirectory() as directory:
            run_path = self.fixture(Path(directory))
            database_before = (run_path / "sfm/database.db").read_bytes()
            modules, extract_calls, match_calls = self.modules(run_path)
            with patch.dict(sys.modules, modules):
                result = run(run_path, "0")
            report = json.loads((result / "report.json").read_text())
            self.assertEqual(extract_calls, [["query.jpg"], ["query.jpg"]])
            self.assertEqual(len(match_calls), 1)
            self.assertEqual(report["status"], "consistency_complete")
            self.assertEqual(report["localized_consistency_candidates"], 0)
            self.assertEqual(report["queries"][0]["status"], "not_localized")
            self.assertNotIn("cam_from_world", report["queries"][0])
            self.assertFalse(report["geometry_accuracy_validated"])
            self.assertFalse(report["milestone_pass_authorized"])
            self.assertTrue(report["reference_artifacts_unchanged"])
            self.assertEqual(report["mapping_database_sha256_before"], report["mapping_database_sha256_after"])
            self.assertEqual((run_path / "sfm/database.db").read_bytes(), database_before)

    def test_no_queries_is_explicit_and_does_not_run_feature_extraction(self):
        with tempfile.TemporaryDirectory() as directory:
            run_path = self.fixture(Path(directory), with_query=False)
            modules, extract_calls, match_calls = self.modules(run_path)
            with patch.dict(sys.modules, modules):
                result = run(run_path, "0")
            report = json.loads((result / "report.json").read_text())
            self.assertEqual(report["status"], "no_queries")
            self.assertEqual(report["query_count"], 0)
            self.assertEqual(extract_calls, [])
            self.assertEqual(match_calls, [])
            self.assertFalse(report["milestone_pass_authorized"])

    def test_reference_mutation_is_an_error_not_a_completed_run(self):
        with tempfile.TemporaryDirectory() as directory:
            run_path = self.fixture(Path(directory))
            modules, _, _ = self.modules(run_path, mutate_database=True)
            with patch.dict(sys.modules, modules), self.assertRaisesRegex(RuntimeError, "mutated"):
                run(run_path, "0")
            reports = list((run_path / "holdouts").glob("*/report.json"))
            report = json.loads(reports[0].read_text())
            self.assertEqual(report["status"], "error")
            self.assertFalse(report["reference_artifacts_unchanged"])


if __name__ == "__main__":
    unittest.main()
