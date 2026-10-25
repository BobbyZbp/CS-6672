"""Fixture-only tests: no model downloads, COLMAP imports or GPU are required."""

import copy
import hashlib
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
from run_artsquad_sfm import select_training_images, stage_images, verified_graph


def record(name, *, split="train", role="scene-candidate", targets=None):
    return {"filename": name, "split": split, "role": role,
            "validation": {"passed": True},
            "exposure_group_id": "exposure-" + name,
            "source_family_id": "family-" + name,
            "discovery": {"targets": targets if targets is not None else ["morrill"]}}


def staged_record(source, name=None):
    return {"filename": name or source.name, "working_path": str(source),
            "sha256_working": hashlib.sha256(source.read_bytes()).hexdigest()}


def make_graph_database(path, images, geometries):
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE images (image_id INTEGER PRIMARY KEY, name TEXT)")
        connection.execute("CREATE TABLE two_view_geometries (pair_id INTEGER PRIMARY KEY, rows INTEGER, config INTEGER)")
        connection.executemany("INSERT INTO images VALUES (?,?)", images)
        connection.executemany("INSERT INTO two_view_geometries VALUES (?,?,?)", geometries)


def pair_id(a, b):
    a, b = sorted((a, b))
    return a * 2147483647 + b


class TrainingSelectionTests(unittest.TestCase):
    def select(self, images, targets=()):
        return select_training_images({"images": images}, targets)

    def test_only_admitted_training_scene_candidates_are_selected(self):
        accepted = [record("z.jpg"), record("a.jpg")]
        rejected = record("reject.jpg")
        rejected["validation"]["passed"] = False
        excluded = record("excluded.jpg", split="excluded")
        interior = record("interior.jpg", role="interior")
        test = record("test.jpg", split="test")
        selected = self.select(accepted + [rejected, excluded, interior, test])
        self.assertEqual([row["filename"] for row in selected], ["a.jpg", "z.jpg"])

    def test_literal_validation_true_required(self):
        images = []
        for index, value in enumerate((False, None, "True", 1, {}, [])):
            row = record(str(index) + ".jpg")
            row["validation"]["passed"] = value
            images.append(row)
        images.append(record("valid.jpg"))
        self.assertEqual([r["filename"] for r in self.select(images)], ["valid.jpg"])

    def test_missing_validation_is_not_admitted(self):
        row = record("unverified.jpg")
        del row["validation"]
        self.assertEqual(self.select([row]), [])

    def test_targets_scope_training_only_by_declared_metadata(self):
        a = record("morrill.jpg", targets=["morrill"])
        b = record("white.jpg", targets=["white"])
        bridge = record("bridge.jpg", targets=["white", "mcgraw-hall"])
        unrelated = record("context.jpg", targets=["uris"])
        selected = self.select([a, b, bridge, unrelated], ["morrill", "mcgraw-hall"])
        self.assertEqual([r["filename"] for r in selected], ["bridge.jpg", "morrill.jpg"])
        # Selection says nothing about pixel-level building identity.
        self.assertNotIn("target_identity_validated", selected[0])

    def test_missing_target_labels_do_not_satisfy_target_scope(self):
        row = record("unknown.jpg")
        del row["discovery"]
        self.assertEqual(self.select([row], ["morrill"]), [])

    def test_unscoped_run_preserves_all_admitted_targets(self):
        self.assertEqual(len(self.select([record("m.jpg"), record("w.jpg", targets=["white"])])), 2)

    def test_missing_training_group_ids_are_rejected(self):
        for key in ("filename", "exposure_group_id", "source_family_id"):
            with self.subTest(key=key):
                row = record("a.jpg")
                del row[key]
                with self.assertRaises(ValueError):
                    self.select([row])

    def test_empty_group_ids_are_rejected(self):
        for key in ("exposure_group_id", "source_family_id"):
            for value in ("", "  ", "\n"):
                with self.subTest(key=key, value=value):
                    row = record("a.jpg")
                    row[key] = value
                    with self.assertRaises(ValueError):
                        self.select([row])

    def test_filename_exposure_and_family_leakage_are_rejected(self):
        for key in ("filename", "exposure_group_id", "source_family_id"):
            with self.subTest(key=key):
                train, heldout = record("train.jpg"), record("heldout.jpg", split="test")
                heldout[key] = train[key]
                with self.assertRaises(ValueError):
                    self.select([train, heldout])

    def test_leakage_checked_against_all_test_views_not_target_subset(self):
        train = record("train.jpg", targets=["morrill"])
        heldout = record("heldout.jpg", split="test", role="interior", targets=["white"])
        heldout["source_family_id"] = train["source_family_id"]
        with self.assertRaises(ValueError):
            self.select([train, heldout], ["morrill"])

    def test_group_sharing_inside_training_is_not_test_leakage(self):
        a, b = record("frame1.jpg"), record("frame2.jpg")
        b["source_family_id"] = a["source_family_id"]
        self.assertEqual(len(self.select([a, b])), 2)

    def test_duplicate_working_filenames_are_rejected(self):
        a, b = record("same.jpg"), record("same.jpg")
        b["exposure_group_id"] = "different-group"
        with self.assertRaises(ValueError):
            self.select([a, b])

    def test_only_whitespace_free_basenames_are_accepted(self):
        for filename in ("../escape.jpg", "/absolute.jpg", "sub/f.jpg", "a b.jpg", "a\nb.jpg"):
            with self.subTest(filename=filename), self.assertRaises(ValueError):
                self.select([record(filename)])

    def test_selection_does_not_mutate_snapshot(self):
        snapshot = {"images": [record("z.jpg"), record("a.jpg")]}
        frozen = copy.deepcopy(snapshot)
        select_training_images(snapshot)
        self.assertEqual(snapshot, frozen)


class StagingTests(unittest.TestCase):
    def test_declared_hash_checked_images_stage_as_independent_byte_copies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.jpg"
            source.write_bytes(b"fixture-image-bytes")
            destination = root / "stage"
            rows = [staged_record(source, "train.jpg")]
            stage_images(rows, destination)
            self.assertFalse((destination / "train.jpg").is_symlink())
            self.assertEqual((destination / "train.jpg").read_bytes(), source.read_bytes())
            self.assertNotEqual((destination / "train.jpg").stat().st_ino, source.stat().st_ino)
            stage_images(rows, destination)  # Exact cache reuse is permitted.
            self.assertEqual(source.read_bytes(), b"fixture-image-bytes")

    def test_changed_frozen_input_hash_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.jpg"
            source.write_bytes(b"initial")
            row = staged_record(source)
            source.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "Frozen input changed"):
                stage_images([row], root / "stage")
            self.assertFalse((root / "stage/source.jpg").exists())

    def test_changed_hash_cannot_reuse_previous_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.jpg"
            source.write_bytes(b"initial")
            row = staged_record(source)
            stage_images([row], root / "stage")
            source.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "Frozen input changed"):
                stage_images([row], root / "stage")

    def test_undeclared_file_is_refused_and_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stage = root / "stage"
            stage.mkdir()
            unexpected = stage / "holdout.jpg"
            unexpected.write_bytes(b"must-not-enter-sfm")
            source = root / "train.jpg"
            source.write_bytes(b"train")
            with self.assertRaisesRegex(ValueError, "undeclared"):
                stage_images([staged_record(source)], stage)
            self.assertEqual(unexpected.read_bytes(), b"must-not-enter-sfm")
            self.assertFalse((stage / "train.jpg").exists(), "Preflight should reject undeclared inputs before staging anything.")

    def test_non_symlink_destination_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.jpg"
            source.write_bytes(b"input")
            stage = root / "stage"
            stage.mkdir()
            (stage / "train.jpg").write_bytes(b"existing-user-file")
            with self.assertRaisesRegex(ValueError, "changed staged input"):
                stage_images([staged_record(source, "train.jpg")], stage)
            self.assertEqual((stage / "train.jpg").read_bytes(), b"existing-user-file")

    def test_symlink_to_wrong_source_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, wrong = root / "source.jpg", root / "other.jpg"
            source.write_bytes(b"input")
            wrong.write_bytes(b"not-declared")
            stage = root / "stage"
            stage.mkdir()
            (stage / "train.jpg").symlink_to(wrong)
            with self.assertRaisesRegex(ValueError, "symlink is unsafe"):
                stage_images([staged_record(source, "train.jpg")], stage)
            self.assertEqual((stage / "train.jpg").resolve(), wrong.resolve())


class VerifiedGraphTests(unittest.TestCase):
    def test_pair_id_parsing_and_configuration_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "colmap.db"
            ids = [1, 3, 8, 2147483646]
            names = {i: "image-" + str(i) + ".jpg" for i in ids}
            geometries = [(pair_id(3, 8), 20, 2), (pair_id(1, 3), 9, 3),
                          (pair_id(1, 8), 8, 4), (pair_id(8, 2147483646), 12, 5),
                          (pair_id(1, 2147483646), 0, 2)]
            make_graph_database(database, list(names.items()), geometries)
            records = [record(name, targets=["metadata-target-" + str(i)]) for i, name in names.items()]
            result = verified_graph(database, records)
            edges = {(edge["a"], edge["b"]): edge for edge in result["edges"]}
            self.assertEqual(len(edges), 5)
            self.assertEqual(result["verified_pairs"], 4)
            self.assertEqual(result["nondegenerate_pairs"], 2)
            calibrated = edges[(names[3], names[8])]
            self.assertTrue(calibrated["nondegenerate_epipolar"])
            self.assertEqual(calibrated["metadata_targets_a"], ["metadata-target-3"])
            self.assertEqual(calibrated["metadata_targets_b"], ["metadata-target-8"])
            self.assertTrue(edges[(names[1], names[3])]["nondegenerate_epipolar"])
            self.assertFalse(edges[(names[1], names[8])]["nondegenerate_epipolar"])
            self.assertFalse(edges[(names[8], names[2147483646])]["nondegenerate_epipolar"])

    def test_graph_labels_remain_metadata_not_semantic_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "colmap.db"
            make_graph_database(database, [(1, "a.jpg"), (2, "b.jpg")], [(pair_id(1, 2), 2000, 2)])
            result = verified_graph(database, [record("a.jpg", targets=["morrill"]), record("b.jpg", targets=["white"])])
            self.assertEqual(result["verified_pairs"], 1)
            self.assertIn("necessary, not sufficient", result["interpretation"])
            edge = result["edges"][0]
            self.assertNotIn("target_identity_validated", edge)
            self.assertNotIn("adjacency_verified", edge)
            self.assertNotIn("real_observations_verified", edge)

    def test_empty_graph_has_zero_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "colmap.db"
            make_graph_database(database, [(1, "a.jpg")], [])
            result = verified_graph(database, [record("a.jpg")])
            self.assertEqual(result["edges"], [])
            self.assertEqual(result["verified_pairs"], 0)
            self.assertEqual(result["nondegenerate_pairs"], 0)

    def test_missing_database_is_not_silently_created(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "absent.db"
            with self.assertRaises((FileNotFoundError, sqlite3.Error)):
                verified_graph(database, [])
            self.assertFalse(database.exists())

    def test_database_names_must_belong_to_frozen_record_set(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "colmap.db"
            make_graph_database(database, [(1, "a.jpg"), (2, "undeclared.jpg")], [(pair_id(1, 2), 20, 2)])
            with self.assertRaises((ValueError, KeyError)):
                verified_graph(database, [record("a.jpg")])

    def test_graph_inspection_does_not_modify_database(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "colmap.db"
            make_graph_database(database, [(1, "a.jpg"), (2, "b.jpg")], [(pair_id(1, 2), 20, 2)])
            before = database.read_bytes()
            verified_graph(database, [record("a.jpg"), record("b.jpg")])
            self.assertEqual(database.read_bytes(), before)
            self.assertEqual({path.name for path in root.iterdir()}, {"colmap.db"})


if __name__ == "__main__":
    unittest.main()
