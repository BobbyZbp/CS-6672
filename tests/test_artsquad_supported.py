"""Local fragment wrapper rejects unsupported or invented geometry."""

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
from build_artsquad_supported import family_audit, source_materials, support_status, verify_mesh_vertices


class SupportedFragmentTests(unittest.TestCase):
    def test_metadata_families_are_conservative_not_exposure_certification(self):
        records = [{"filename": "a.jpg", "source_family_id": "session-a"},
                   {"filename": "b.jpg", "source_family_id": "session-a"},
                   {"filename": "c.jpg", "source_family_id": "session-b"}]
        audit = family_audit(records, ["c.jpg", "a.jpg", "b.jpg"])
        self.assertEqual(audit["candidate_groups"], [["a.jpg", "b.jpg"], ["c.jpg"]])
        self.assertFalse(audit["certified_independent_exposures"])

    def test_missing_family_never_silently_becomes_independent_view(self):
        for family in (None, "", " "):
            with self.subTest(family=family), self.assertRaises(ValueError):
                family_audit([{"filename": "a.jpg", "source_family_id": family}], ["a.jpg"])

    def test_unadmitted_or_duplicate_camera_is_refused(self):
        records = [{"filename": "train.jpg", "source_family_id": "session"}]
        for names in (["holdout.jpg"], ["train.jpg", "train.jpg"]):
            with self.subTest(names=names), self.assertRaises(ValueError):
                family_audit(records, names)

    def test_material_ids_use_exported_camera_ids_not_compact_indices(self):
        mapping = source_materials([(7, "../colmap/images/a.jpg"), (37, "../colmap/images/b.jpg")])
        self.assertEqual(mapping, {"camera_7": "a.jpg", "camera_37": "b.jpg"})
        self.assertNotIn("camera_0", mapping)

    def test_ambiguous_export_basename_is_refused(self):
        with self.assertRaises(ValueError):
            source_materials([(7, "folder/a.jpg"), (37, "other/a.jpg")])

    def obj(self, path, xyz=None, face="1/1 2/2 3/3"):
        xyz = np.array([[0., 0., 5.], [.01, 0., 5.], [0., .01, 5.]]) if xyz is None else np.asarray(xyz)
        lines = ["mtllib family-supported.mtl"]
        lines.extend("v " + " ".join(map(str, point)) for point in xyz)
        lines.append("usemtl camera_7")
        if face:
            lines.append("f " + face)
        path.write_text("\n".join(lines) + "\n")
        return xyz

    def test_mesh_vertices_are_unchanged_fused_source_positions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "family-supported.obj"
            xyz = self.obj(path)
            report = verify_mesh_vertices(path, xyz)
            self.assertEqual(report["faces"], 1)
            self.assertEqual(report["used_vertices"], 3)
            self.assertEqual(report["materials"], ["camera_7"])
            self.assertTrue(report["dense_vertices_preserved_within_text_precision"])

    def test_invented_or_changed_vertex_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "family-supported.obj"
            xyz = self.obj(path)
            changed = xyz.copy()
            changed[0, 0] += 1.
            with self.assertRaisesRegex(ValueError, "changed dense"):
                verify_mesh_vertices(path, changed)

    def test_empty_invalid_or_nontriangle_mesh_is_not_a_candidate(self):
        for face in (None, "1/1 2/2 4/4", "1 2 3 1"):
            with self.subTest(face=face), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "family-supported.obj"
                xyz = self.obj(path, face=face)
                with self.assertRaises(ValueError):
                    verify_mesh_vertices(path, xyz)

    def test_reports_do_not_promote_zero_support_or_certify_d1(self):
        self.assertEqual(support_status(0, 239), "insufficient_support")
        self.assertEqual(support_status(0, 0), "insufficient_support")
        self.assertEqual(support_status(7225, 0), "insufficient_support")
        self.assertEqual(support_status(7225, 12514), "supported_fragment_candidate")
        for counts in ((-1, 1), (1, -1), (None, 1), (True, 1)):
            with self.subTest(counts=counts), self.assertRaises(ValueError):
                support_status(*counts)


if __name__ == "__main__":
    unittest.main()
