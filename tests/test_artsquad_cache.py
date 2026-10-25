"""Cross-snapshot cache reuse copies only compatible training HDF5 groups."""

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

import h5py
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
from reuse_artsquad_cache import FINGERPRINT_FIELDS, reuse_cache


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CacheReuseTests(unittest.TestCase):
    def fixture(self, root, status="sfm_complete"):
        source, destination = root / "old-run", root / "new-run"
        source.mkdir()
        rows = []
        for name in ("a.jpg", "b.jpg", "c.jpg", "oldtest.jpg", "new.jpg"):
            path = root / name
            path.write_bytes(("working-photo-" + name).encode())
            rows.append({"filename": name, "split": "test" if name == "oldtest.jpg" else "train",
                         "role": "scene-candidate", "validation": {"passed": True},
                         "exposure_group_id": "exposure-" + name, "source_family_id": "family-" + name,
                         "working_path": str(path), "sha256_working": digest(path),
                         "discovery": {"targets": ["morrill"]}})
        old_rows = [row for row in rows if row["filename"] != "new.jpg"]
        snapshot = root / "source-snapshot.json"
        snapshot.write_text(json.dumps({"snapshot_id": "old-snapshot", "images": old_rows}))
        config = {"resize": 1200, "keypoints": 4096, "torch_version": "fixture-torch",
                  "pycolmap_version": "fixture-pycolmap", "extractor": "SuperPoint", "matcher": "LightGlue",
                  "retrieval": "NetVLAD", "targets": [], "retrieval_neighbors": 8, "snapshot_sha256": digest(snapshot)}
        report = {"status": status, "run_id": "old-run-id", "snapshot_path": str(snapshot),
                  "snapshot_id": "old-snapshot", "configuration": config, "input_images": ["a.jpg", "b.jpg", "c.jpg"]}
        (source / "report.json").write_text(json.dumps(report))
        (source / "configuration.json").write_text(json.dumps(config))
        for filename in ("global-feats-netvlad.h5", "feats-superpoint-n4096-r1200.h5"):
            with h5py.File(source / filename, "w") as file:
                for index, name in enumerate(report["input_images"]):
                    group = file.create_group(name)
                    group.attrs["fixture"] = "source-group"
                    group.create_dataset("image_size", data=[1200, 800])
                    if filename.startswith("global"):
                        group.create_dataset("global_descriptor", data=np.arange(8) + index)
                    else:
                        group.create_dataset("keypoints", data=[[index + 1., index + 2.]])
                        group["keypoints"].attrs["uncertainty"] = np.float32(1.0)
                        group.create_dataset("descriptors", data=np.ones((4, 1), dtype=np.float32) * index)
                        group.create_dataset("scores", data=np.ones(1, dtype=np.float32))
        with h5py.File(source / "matches-lightglue.h5", "w") as file:
            # Deliberately reversed orientation; it must remain c/a, not a/c.
            for pair in ("c.jpg/a.jpg", "a.jpg/b.jpg", "c.jpg/b.jpg"):
                group = file.create_group(pair)
                group.create_dataset("matches0", data=np.array([0], dtype=np.int16))
                group.create_dataset("matching_scores0", data=np.array([.8], dtype=np.float16))
        (source / "pairs.txt").write_text("c.jpg a.jpg\na.jpg b.jpg\nc.jpg b.jpg\n")
        (source / "sfm/models/0").mkdir(parents=True)
        (source / "sfm/database.db").write_bytes(b"do-not-copy-db")
        (source / "sfm/models/0/images.bin").write_bytes(b"do-not-copy-model")
        # b.jpg has become a new holdout/exclusion; it MUST NOT be reused.
        current = [copy.deepcopy(row) for row in rows if row["filename"] in {"a.jpg", "c.jpg", "new.jpg"}]
        new_config = {**config, "snapshot_sha256": "new-frozen-snapshot", "targets": ["morrill"], "retrieval_neighbors": 99}
        return source, destination, new_config, current

    def test_only_common_current_training_features_and_pairs_are_copied(self):
        with tempfile.TemporaryDirectory() as directory:
            source, destination, config, records = self.fixture(Path(directory))
            before = {str(path): digest(path) for path in source.rglob("*") if path.is_file()}
            report = reuse_cache(destination, source, config, records)
            for filename in ("global-feats-netvlad.h5", "feats-superpoint-n4096-r1200.h5"):
                with h5py.File(destination / filename) as output:
                    self.assertEqual(set(output), {"a.jpg", "c.jpg"})
                    self.assertNotIn("b.jpg", output)
                    self.assertNotIn("oldtest.jpg", output)
                    self.assertNotIn("new.jpg", output)
            with h5py.File(destination / "matches-lightglue.h5") as output:
                self.assertIn("c.jpg/a.jpg", output)
                self.assertNotIn("a.jpg/c.jpg", output)
                self.assertNotIn("a.jpg/b.jpg", output)
                np.testing.assert_array_equal(output["c.jpg/a.jpg/matches0"], [0])
            self.assertEqual(report["reused_images"], 2)
            self.assertEqual(report["reused_pairs"], 1)
            self.assertEqual(report["images_requiring_extraction"], 1)
            self.assertFalse(report["database_or_native_model_reused"])
            self.assertFalse(report["heldout_features_reused"])
            self.assertFalse((destination / "sfm").exists())
            self.assertTrue(report["source_artifacts_unchanged"])
            self.assertEqual(before, {str(path): digest(path) for path in source.rglob("*") if path.is_file()})

    def test_source_no_model_is_allowed_after_complete_feature_pipeline(self):
        with tempfile.TemporaryDirectory() as directory:
            source, destination, config, records = self.fixture(Path(directory), status="no_model")
            self.assertEqual(reuse_cache(destination, source, config, records)["status"], "cache_reused")

    def test_running_or_unknown_source_cannot_be_reused(self):
        for status in ("running", "unknown"):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as directory:
                source, destination, config, records = self.fixture(Path(directory), status=status)
                with self.assertRaisesRegex(ValueError, "completed"):
                    reuse_cache(destination, source, config, records)

    def test_every_feature_fingerprint_field_must_match(self):
        for field in FINGERPRINT_FIELDS:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                source, destination, config, records = self.fixture(Path(directory))
                config[field] = "incompatible-value"
                with self.assertRaisesRegex(ValueError, "fingerprint"):
                    reuse_cache(destination, source, config, records)

    def test_missing_fingerprint_is_not_compatible(self):
        with tempfile.TemporaryDirectory() as directory:
            source, destination, config, records = self.fixture(Path(directory))
            del config["matcher"]
            with self.assertRaisesRegex(ValueError, "fingerprint"):
                reuse_cache(destination, source, config, records)

    def test_source_frozen_snapshot_changed_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, destination, config, records = self.fixture(root)
            with (root / "source-snapshot.json").open("a") as file:
                file.write(" ")
            with self.assertRaisesRegex(ValueError, "snapshot hash changed"):
                reuse_cache(destination, source, config, records)

    def test_current_working_digest_changed_across_snapshots_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            source, destination, config, records = self.fixture(Path(directory))
            records[0]["sha256_working"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "hash changed"):
                reuse_cache(destination, source, config, records)

    def test_changed_actual_working_bytes_are_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            source, destination, config, records = self.fixture(Path(directory))
            Path(records[0]["working_path"]).write_bytes(b"changed-input")
            with self.assertRaisesRegex(ValueError, "Frozen working input changed"):
                reuse_cache(destination, source, config, records)

    def test_test_excluded_rejected_records_never_reused(self):
        for field, value in (("split", "test"), ("role", "interior"), ("validation", {"passed": False})):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                source, destination, config, records = self.fixture(Path(directory))
                records[0][field] = value
                with self.assertRaisesRegex(ValueError, "current training"):
                    reuse_cache(destination, source, config, records)

    def test_source_heldout_feature_group_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            source, destination, config, records = self.fixture(Path(directory))
            with h5py.File(source / "global-feats-netvlad.h5", "a") as file:
                file.create_group("oldtest.jpg").create_dataset("global_descriptor", data=[0., 1.])
            with self.assertRaisesRegex(ValueError, "held-out groups"):
                reuse_cache(destination, source, config, records)

    def test_source_report_must_match_training_input_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            source, destination, config, records = self.fixture(Path(directory))
            path = source / "report.json"
            report = json.loads(path.read_text())
            report["input_images"].append("oldtest.jpg")
            path.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, "training selection"):
                reuse_cache(destination, source, config, records)

    def test_existing_destination_cache_is_preserved_not_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            source, destination, config, records = self.fixture(Path(directory))
            destination.mkdir()
            path = destination / "global-feats-netvlad.h5"
            path.write_bytes(b"existing-user-cache")
            with self.assertRaisesRegex(ValueError, "no files replaced"):
                reuse_cache(destination, source, config, records)
            self.assertEqual(path.read_bytes(), b"existing-user-cache")

    def test_same_run_source_and_destination_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            source, _, config, records = self.fixture(Path(directory))
            with self.assertRaisesRegex(ValueError, "must differ"):
                reuse_cache(source, source, config, records)

    def test_repeat_import_verifies_copied_group_content(self):
        with tempfile.TemporaryDirectory() as directory:
            source, destination, config, records = self.fixture(Path(directory))
            first = reuse_cache(destination, source, config, records)
            self.assertEqual(reuse_cache(destination, source, config, records), first)
            with h5py.File(destination / "feats-superpoint-n4096-r1200.h5", "a") as file:
                file["a.jpg/keypoints"][0, 0] = 999
            with self.assertRaisesRegex(ValueError, "group changed"):
                reuse_cache(destination, source, config, records)

    def test_resume_allows_new_declared_training_groups_not_query_groups(self):
        with tempfile.TemporaryDirectory() as directory:
            source, destination, config, records = self.fixture(Path(directory))
            first = reuse_cache(destination, source, config, records)
            for filename in ("global-feats-netvlad.h5", "feats-superpoint-n4096-r1200.h5"):
                with h5py.File(destination / filename, "a") as file:
                    file.create_group("new.jpg").create_dataset("new_feature", data=[1])
            with h5py.File(destination / "matches-lightglue.h5", "a") as file:
                file.create_group("new.jpg/a.jpg").create_dataset("matches0", data=[0])
            self.assertEqual(reuse_cache(destination, source, config, records), first)
            with h5py.File(destination / "global-feats-netvlad.h5", "a") as file:
                file.create_group("b.jpg").create_dataset("heldout_feature", data=[1])
            with self.assertRaisesRegex(ValueError, "undeclared current images"):
                reuse_cache(destination, source, config, records)

    def test_legacy_pair_orientation_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            source, destination, config, records = self.fixture(Path(directory))
            with h5py.File(source / "matches-lightglue.h5", "a") as file:
                del file["c.jpg/a.jpg"]
                group = file.create_group("c.jpg_a.jpg")
                group.create_dataset("matches0", data=np.array([0], dtype=np.int16))
                group.create_dataset("matching_scores0", data=[.8])
            report = reuse_cache(destination, source, config, records)
            self.assertEqual(report["reused_pairs"], 1)
            with h5py.File(destination / "matches-lightglue.h5") as file:
                self.assertIn("c.jpg_a.jpg", file)

    def test_errored_native_mapping_can_reuse_only_a_fully_validated_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            source, destination, config, records = self.fixture(Path(directory), status="error")
            report = reuse_cache(destination, source, config, records)
            self.assertEqual(report["source_sfm_status"], "error")
            self.assertTrue(report["source_cache_validation"]["validated"])
            self.assertFalse(report["database_or_native_model_reused"])

    def test_incomplete_pairs_in_errored_source_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            source, destination, config, records = self.fixture(Path(directory), status="error")
            with h5py.File(source / "matches-lightglue.h5", "a") as file:
                del file["a.jpg/b.jpg"]
            with self.assertRaisesRegex(ValueError, "matching is incomplete"):
                reuse_cache(destination, source, config, records)

    def test_missing_match_scores_in_errored_source_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            source, destination, config, records = self.fixture(Path(directory), status="error")
            with h5py.File(source / "matches-lightglue.h5", "a") as file:
                del file["c.jpg/a.jpg/matching_scores0"]
            with self.assertRaisesRegex(ValueError, "scores are incomplete"):
                reuse_cache(destination, source, config, records)

    def test_bad_match_indices_and_shapes_in_errored_source_are_rejected(self):
        for values in ([1], [-2], [0, 0]):
            with self.subTest(values=values), tempfile.TemporaryDirectory() as directory:
                source, destination, config, records = self.fixture(Path(directory), status="error")
                with h5py.File(source / "matches-lightglue.h5", "a") as file:
                    del file["c.jpg/a.jpg/matches0"]
                    file["c.jpg/a.jpg"].create_dataset("matches0", data=np.array(values, dtype=np.int16))
                with self.assertRaises(ValueError):
                    reuse_cache(destination, source, config, records)


if __name__ == "__main__":
    unittest.main()
