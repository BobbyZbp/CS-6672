"""CPU baseline configuration plus tiny installed-native API integration tests."""

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
from run_artsquad_sift import (KEYPOINTS, RESIZE, baseline_configuration,
                               configuration_id, database_feature_summary,
                               native_options)
from run_artsquad_sfm import component_report

try:
    import pycolmap
except ImportError:
    pycolmap = None


class SiftConfigurationTests(unittest.TestCase):
    def test_frozen_budget_cpu_and_distinct_method_are_explicit(self):
        config = baseline_configuration("frozen-sha", ["white", "morrill"], "baseline", "3.13.0")
        self.assertEqual(config["resize"], 1200)
        self.assertEqual(config["keypoints"], 4096)
        self.assertEqual(config["camera_mode"], "PER_IMAGE")
        self.assertEqual(config["camera_model"], "SIMPLE_RADIAL")
        self.assertEqual(config["minimum_saved_component_cameras"], 2)
        self.assertFalse(config["use_gpu"])
        self.assertEqual(config["method"], "SIFT-COLMAP-CPU")
        self.assertEqual(config["pairing"], "exhaustive")

    def test_hash_is_deterministic_and_changes_with_input_or_method(self):
        first = baseline_configuration("sha", ["morrill", "white"], "a", "3.13")
        reordered = baseline_configuration("sha", ["white", "morrill", "white"], "a", "3.13")
        self.assertEqual(configuration_id(first), configuration_id(reordered))
        self.assertNotEqual(configuration_id(first), configuration_id({**first, "snapshot_sha256": "new"}))
        self.assertNotEqual(configuration_id(first), configuration_id({**first, "method": "learned"}))
        self.assertNotEqual(configuration_id(first), configuration_id({**first, "run_label": "retry"}))

    def database(self, path, rows):
        with sqlite3.connect(path) as connection:
            connection.execute("CREATE TABLE images(image_id INTEGER PRIMARY KEY,name TEXT)")
            connection.execute("CREATE TABLE keypoints(image_id INTEGER PRIMARY KEY,rows INTEGER)")
            for index, (name, count) in enumerate(rows, start=1):
                connection.execute("INSERT INTO images VALUES (?,?)", (index, name))
                if count is not None:
                    connection.execute("INSERT INTO keypoints VALUES (?,?)", (index, count))

    def test_database_summary_read_only_and_exact_input_set(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "features.db"
            self.database(path, [("a.jpg", 500), ("b.jpg", 200)])
            before = path.read_bytes()
            summary = database_feature_summary(path, ["a.jpg", "b.jpg"])
            self.assertEqual(summary["keypoints_total"], 700)
            self.assertEqual(summary["keypoints_max"], 500)
            self.assertEqual(path.read_bytes(), before)

    def test_database_summary_refuses_undeclared_or_canonicalized_names(self):
        for name in ("heldout.jpg", "../../../images/a.jpg"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "features.db"
                self.database(path, [(name, 100)])
                with self.assertRaisesRegex(ValueError, "noncanonical"):
                    database_feature_summary(path, ["a.jpg"])

    def test_missing_feature_rows_is_not_completed_extraction(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "features.db"
            self.database(path, [("a.jpg", None)])
            with self.assertRaisesRegex(ValueError, "incomplete"):
                database_feature_summary(path, ["a.jpg"])

    def test_summary_does_not_create_missing_database(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.db"
            with self.assertRaises(sqlite3.Error):
                database_feature_summary(path, [])
            self.assertFalse(path.exists())


@unittest.skipIf(pycolmap is None, "Installed pycolmap is optional for pure helper tests")
class NativeSiftApiTests(unittest.TestCase):
    def test_installed_native_option_structure_and_cpu_device(self):
        options = native_options(pycolmap)
        self.assertEqual(options["device"], pycolmap.Device.cpu)
        self.assertEqual(options["extraction"].max_image_size, RESIZE)
        self.assertEqual(options["extraction"].sift.max_num_features, KEYPOINTS)
        self.assertFalse(options["extraction"].use_gpu)
        self.assertFalse(options["matching"].use_gpu)
        self.assertFalse(options["mapping"].ba_use_gpu)
        self.assertEqual(options["mapping"].min_model_size, 2)
        self.assertTrue(options["mapping"].multiple_models)

    def test_tiny_real_native_extractor_matcher_stores_only_declared_basenames(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image_dir = root / "images"
            image_dir.mkdir()
            pixels = np.random.default_rng(0).integers(0, 256, (180, 240, 3), dtype=np.uint8)
            Image.fromarray(pixels).save(image_dir / "a.jpg")
            Image.fromarray(pixels).save(image_dir / "b.jpg")
            Image.fromarray(pixels).save(image_dir / "heldout.jpg")
            database = root / "database.db"
            options = native_options(pycolmap)
            pycolmap.extract_features(str(database), str(image_dir), image_names=["a.jpg", "b.jpg"],
                                      camera_mode=pycolmap.CameraMode.PER_IMAGE, camera_model="SIMPLE_RADIAL",
                                      reader_options=options["reader"], extraction_options=options["extraction"], device=options["device"])
            summary = database_feature_summary(database, ["a.jpg", "b.jpg"])
            self.assertEqual(summary["image_count"], 2)
            self.assertGreater(summary["keypoints_total"], 0)
            pycolmap.match_exhaustive(str(database), matching_options=options["matching"],
                                     pairing_options=options["pairing"], verification_options=options["verification"], device=options["device"])
            with sqlite3.connect(database) as connection:
                names = {row[0] for row in connection.execute("SELECT name FROM images")}
                self.assertEqual(names, {"a.jpg", "b.jpg"})
                self.assertGreaterEqual(connection.execute("SELECT COUNT(*) FROM matches").fetchone()[0], 1)

    def test_component_report_uses_real_native_camera_model_enum(self):
        options = pycolmap.SyntheticDatasetOptions()
        options.num_rigs = 1
        options.num_frames_per_rig = 2
        options.num_points3D = 8
        options.num_points2D_without_point3D = 0
        model = pycolmap.synthesize_dataset(options)
        records = [{"filename": image.name, "exposure_group_id": "exp-" + image.name,
                    "source_family_id": "family-" + image.name, "discovery": {"targets": ["morrill"]}}
                   for image in model.images.values()]
        report = component_report(model, "0", records)
        self.assertEqual(report["registered_cameras"], 2)
        self.assertEqual(report["sparse_points"], 8)
        self.assertTrue(all(camera["camera_model"] == "SIMPLE_RADIAL" for camera in report["cameras"]))
        self.assertFalse(report["target_identity_validated"])
        self.assertFalse(report["independent_exposures_validated"])


if __name__ == "__main__":
    unittest.main()
