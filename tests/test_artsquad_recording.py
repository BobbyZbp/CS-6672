"""Recording contract tests. Fixtures are metadata, never public geometry."""
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
from record_artsquad_demo import CHAPTERS, bundle_local_preview, find_caption_start, local_base_url, scene_plan, video_metadata


def scene():
    return {"schema_version": 1, "run_id": "actual-run", "components": [
        {"id": "0", "sparse": {"url": "actual-points.json"}},
        {"id": "1", "mesh": {"url": "actual.obj"}, "cameras": [{"id": "a"}, {"id": "b"}],
         "source_materials": {"camera_a": "a"}, "face_evidence_url": "actual-faces.json"}]}


class RecordingContractTests(unittest.TestCase):
    def test_54_second_actual_component_tour_is_not_d1(self):
        result = scene_plan(scene())
        self.assertEqual(result["requested_seconds"], 54)
        self.assertEqual(result["surface_index"], 1)
        self.assertEqual(result["separate_index"], 0)
        self.assertIn("not accepted D1", result["chapters"][0]["caption"])
        self.assertIn("separate coordinate system", result["chapters"][6]["caption"])
        self.assertIn("pending", result["chapters"][-1]["caption"])
        self.assertEqual(len({entry[0] for entry in CHAPTERS}), len(CHAPTERS))

    def test_missing_measured_surface_or_visibility_fails(self):
        for field in ("mesh", "face_evidence_url", "source_materials", "cameras"):
            value = copy.deepcopy(scene())
            value["components"][1].pop(field)
            with self.subTest(field=field), self.assertRaises(ValueError): scene_plan(value)

    def test_one_component_cannot_appear_to_be_multiple_buildings(self):
        value = scene(); value["components"] = value["components"][1:]
        with self.assertRaises(ValueError): scene_plan(value)

    def test_single_camera_not_multiview(self):
        value = scene(); value["components"][1]["cameras"] = [{"id": "a"}]
        with self.assertRaises(ValueError): scene_plan(value)

    def test_loopback_only_no_credentials_or_external_publication(self):
        for value in ("http://127.0.0.1:8080/", "http://localhost:8080", "http://[::1]:8080"):
            self.assertEqual(local_base_url(value), value.rstrip("/"))
        for value in ("https://public.example/", "http://192.168.0.1", "file:///tmp/page", "http://x:secret@localhost:8080", "http://localhost:8080/?key=x", "http://localhost:8080/#x"):
            with self.subTest(value=value), self.assertRaises(ValueError): local_base_url(value)

    def test_video_metadata_verifies_actual_duration_and_dimensions(self):
        with patch("record_artsquad_demo.subprocess.run") as run:
            run.return_value.stdout = ""
            run.return_value.stderr = "Duration: 00:00:54.04, start: 0.000\n  Video: vp9, yuv420p, 1440x1080, 25 fps\n"
            self.assertEqual(video_metadata("ffmpeg", "actual.webm"), {"duration_seconds": 54.04, "width": 1440, "height": 1080})

    def test_unreadable_video_never_verified(self):
        with patch("record_artsquad_demo.subprocess.run") as run:
            run.return_value.stdout = ""
            run.return_value.stderr = "Invalid data found"
            with self.assertRaises(ValueError): video_metadata("ffmpeg", "not-a-video.webm")

    def bundle_fixture(self, output):
        # Metadata/file integrity fixture only: these bytes are never presented
        # as an actual recorded video, and live recording verifies the codec.
        files = {"actual.webm": b"unit-test-only", "scene-manifest.json": b"{}", "surface.png": b"test-only"}
        for name, payload in files.items(): (output / name).write_bytes(payload)
        digest = lambda name: hashlib.sha256(files[name]).hexdigest()
        report = {"status": "recorded_diagnostic_only", "source_files_unchanged": True, "claims": {"d1_passed": False},
                  "run_id": "test-only", "snapshot_id": "test-only", "created_utc": "2026-10-25T00:00:00Z",
                  "scene_manifest_sha256": digest("scene-manifest.json"), "chapters": [],
                  "video": {"path": "actual.webm", "sha256": digest("actual.webm"), "duration_seconds": 54},
                  "captures": [{"path": "surface.png", "sha256": digest("surface.png")}]}
        (output / "recording-report.json").write_text(json.dumps(report))
        return report

    def test_local_bundle_keeps_versioned_recording_and_trace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); output = root / "capture"; output.mkdir()
            self.bundle_fixture(output)
            index = json.loads(bundle_local_preview(output, root / "dist").read_text())
            self.assertEqual(index["status"], "local_diagnostic_recording")
            self.assertTrue((root / "dist" / index["video_url"]).is_file())
            self.assertEqual((root / "dist" / index["video_url"]).read_bytes(), (output / "actual.webm").read_bytes())
            self.assertIn("not accepted D0/D1", index["notice"])

    def test_local_bundle_rejects_video_manifest_and_capture_tampering(self):
        for name in ("actual.webm", "scene-manifest.json", "surface.png"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); self.bundle_fixture(root)
                (root / name).write_bytes(b"changed")
                with self.assertRaises(ValueError): bundle_local_preview(root, root / "dist")

    def test_local_bundle_rejects_positive_milestone_claim_and_escape(self):
        for change in ({"claims": {"d1_passed": True}}, {"video": {"path": "../outside.webm"}}, {"status": "error"}):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); report = self.bundle_fixture(root); report.update(change)
                (root / "recording-report.json").write_text(json.dumps(report))
                with self.assertRaises(ValueError): bundle_local_preview(root, root / "dist")

    def test_trim_uses_decoded_frame_transition_not_wall_clock(self):
        with tempfile.TemporaryDirectory() as directory:
            def decode(command, **kwargs):
                seconds = float(command[command.index("-ss") + 1])
                color = (36, 40, 32) if seconds >= 12.3 else (241, 238, 231)
                Image.new("RGB", (16, 16), color).save(command[-1])
                class Result: returncode = 0
                return Result()
            with patch("record_artsquad_demo.subprocess.run", side_effect=decode):
                start, evidence = find_caption_start("ffmpeg", "raw.webm", Path(directory), {"duration_seconds": 70, "height": 1080})
            self.assertGreaterEqual(start, 12.3)
            self.assertLess(start, 12.4)
            self.assertLess(evidence["before_seconds"], 12.3)
            self.assertGreaterEqual(evidence["after_seconds"], 12.3)
            self.assertEqual(len(evidence["probes"]), 13)

    def test_missing_disclosure_transition_rejects_raw_video(self):
        for color in ((241, 238, 231), (36, 40, 32)):
            with self.subTest(color=color), tempfile.TemporaryDirectory() as directory:
                def decode(command, **kwargs):
                    Image.new("RGB", (16, 16), color).save(command[-1])
                    class Result: returncode = 0
                    return Result()
                with patch("record_artsquad_demo.subprocess.run", side_effect=decode):
                    with self.assertRaises(ValueError): find_caption_start("ffmpeg", "raw.webm", Path(directory), {"duration_seconds": 70, "height": 1080})


if __name__ == "__main__":
    unittest.main()
