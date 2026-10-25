"""Isolated metadata/bytes fixtures, never fabricated scientific demo assets."""
import copy
import hashlib
import io
import json
import stat
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
from package_artsquad_demo import STATIC, check_photo_rights, check_zip, collect_sources, contained_path, package
from serve_artsquad_demo import verify_bundle


def sha(data): return hashlib.sha256(data).hexdigest()


def put(root, path, payload):
    destination = root / path; destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload if isinstance(payload, bytes) else json.dumps(payload).encode())


def fixture(root):
    for name in STATIC:
        put(root, name, 'Unit test only. <a href="surface-lab.html">Earlier experiments ↗</a>'.encode())
    cameras = [{"id": i, "name": f"photo-{i}.jpg", "photo": f"assets/current/photo-{i}.jpg",
                "split": "train",
                "license": "CC BY-SA 4.0", "license_url": "https://creativecommons.org/licenses/by-sa/4.0",
                "source_url": f"https://commons.wikimedia.org/wiki/File:photo-{i}.jpg", "attribution": "Test metadata only"} for i in (1, 2)]
    scene = {"schema_version": 1, "run_id": "test-metadata-only", "snapshot_id": "test", "sources_url": "assets/current/sources.json",
             "source_code_url": "assets/current/source.zip", "components": [{"id": "0", "cameras": cameras,
                "mesh": {"url": "assets/current/fragment.obj", "mtl_url": "assets/current/fragment.mtl"},
                "source_materials": {"camera_1": 1}, "model_download_url": "assets/current/native.zip"}]}
    put(root, "assets/artsquad/scene.json", scene)
    put(root, "assets/current/sources.json", {"images": [{**camera, "filename": camera["name"], "role": "scene-candidate", "validation": {"passed": True}} for camera in cameras]})
    for camera in cameras: put(root, camera["photo"], b"unit-test-only-photo")
    put(root, "assets/current/fragment.obj", b"mtllib fragment.mtl\n")
    put(root, "assets/current/fragment.mtl", b"newmtl camera_1\nmap_Kd texture.jpg\n")
    put(root, "assets/current/texture.jpg", b"unit-test-only-texture")
    for name, entries in [("source.zip", {"ghostmap-artsquad-source/README.md": b"source fixture"}), ("native.zip", {"cameras.bin": b"native fixture"})]:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for path, payload in entries.items(): archive.writestr(path, payload)
        put(root, "assets/current/" + name, buffer.getvalue())
    video = b"unit-test-only-never-served-as-video"
    manifest_bytes = (root / "assets/artsquad/scene.json").read_bytes()
    report = {"status": "recorded_diagnostic_only", "source_files_unchanged": True, "claims": {"d1_passed": False},
              "video_verification": {"first_frame_disclosure_present": True},
              "viewer_source_sha256": {"dist/" + name: sha((root / name).read_bytes()) for name in ("artsquad.html", "artsquad.js", "artsquad.css", "artsquad-evidence.css", "assets/artsquad/scene.json")}}
    put(root, "assets/artsquad/demo/version/clip.webm", video)
    put(root, "assets/artsquad/demo/version/report.json", report)
    put(root, "assets/artsquad/demo/version/scene.json", manifest_bytes)
    reel = {"status": "local_diagnostic_recording", "scene_manifest_sha256": sha(manifest_bytes),
            "report_url": "assets/artsquad/demo/version/report.json", "recording_report_sha256": sha((root / "assets/artsquad/demo/version/report.json").read_bytes()),
            "video_url": "assets/artsquad/demo/version/clip.webm", "video": {"sha256": sha(video)},
            "scene_manifest_url": "assets/artsquad/demo/version/scene.json", "captures": []}
    put(root, "assets/artsquad/demo/latest.json", reel)
    put(root, "stale-secret.txt", b"must not be bundled")
    put(root, "assets/stale-run/unknown-provider.jpg", b"must not be bundled")
    return scene, reel


class PortablePackageTests(unittest.TestCase):
    def test_closure_excludes_stale_assets_but_keeps_real_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); fixture(root)
            files, _, _, rights, transformations = collect_sources(root)
            self.assertIn("dist/assets/current/texture.jpg", files)
            self.assertIn("dist/assets/current/native.zip", files)
            self.assertNotIn("dist/stale-secret.txt", files)
            self.assertNotIn("dist/assets/stale-run/unknown-provider.jpg", files)
            self.assertEqual(len(rights), 3)
            self.assertIn(b'href="demo-reel.html">Recorded local draft', files["dist/artsquad.html"])
            self.assertEqual(transformations[0]["kind"], "portable-navigation-only")

    def test_unknown_rights_or_wrong_texture_camera_reject_package(self):
        for change in ("unknown-rights", "foreign-texture-camera"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); scene, _ = fixture(root)
                if change == "unknown-rights": scene["components"][0]["cameras"][0]["license"] = "Unknown"
                else: scene["components"][0]["source_materials"]["camera_1"] = 99
                put(root, "assets/artsquad/scene.json", scene)
                with self.assertRaises(ValueError): collect_sources(root)

    def test_final_reel_must_match_exact_scene_and_first_frame(self):
        for change in ("scene", "first-frame", "tampered-video", "viewer-drift"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); _, reel = fixture(root)
                if change == "scene":
                    reel["scene_manifest_sha256"] = "different"; put(root, "assets/artsquad/demo/latest.json", reel)
                elif change == "first-frame":
                    report = {"status": "recorded_diagnostic_only", "source_files_unchanged": True, "claims": {"d1_passed": False}}
                    put(root, "assets/artsquad/demo/version/report.json", report)
                    reel["recording_report_sha256"] = sha((root / "assets/artsquad/demo/version/report.json").read_bytes())
                    put(root, "assets/artsquad/demo/latest.json", reel)
                elif change == "viewer-drift": put(root, "artsquad.js", b"changed")
                else: put(root, "assets/artsquad/demo/version/clip.webm", b"changed")
                with self.assertRaises(ValueError): collect_sources(root)

    def test_confined_paths_reject_escape_external_and_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); put(root, "okay.txt", b"okay")
            (root / "symlink.txt").symlink_to(root / "okay.txt")
            for value in ("../okay.txt", "%2e%2e/okay.txt", "/okay.txt", "https://external.example/x", "symlink.txt", "a\\b", "okay.txt#fragment"):
                with self.subTest(value=value), self.assertRaises(ValueError): contained_path(root, value)
            self.assertEqual(contained_path(root, "okay.txt?v=1"), "okay.txt")

    def test_license_family_and_version_cannot_conflict(self):
        camera = {"name": "test", "license": "CC BY 4.0", "source_url": "https://example.org", "license_url": "https://creativecommons.org/licenses/by/4.0", "attribution": "Test"}
        source = copy.deepcopy(camera)
        self.assertEqual(check_photo_rights(camera, source)["license"], "CC BY 4.0")
        for url in ("https://creativecommons.org/licenses/by-sa/4.0", "https://creativecommons.org/licenses/by/2.0", "http://creativecommons.org/licenses/by/4.0"):
            changed = {**camera, "license_url": url}
            with self.assertRaises(ValueError): check_photo_rights(changed, source)

    def test_excluded_or_heldout_photo_cannot_enter_portable_scene(self):
        for change in ({"split": "test"}, {"role": "interior"}, {"validation": {"passed": 1}}):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); fixture(root)
                path = root / "assets/current/sources.json"; sources = json.loads(path.read_text())
                sources["images"][0].update(change); put(root, "assets/current/sources.json", sources)
                with self.assertRaises(ValueError): collect_sources(root)

    def test_nested_zip_unknown_files_and_symlinks_rejected(self):
        for filename, symlink in (("../outside.bin", False), ("photo.jpg", False), ("cameras.bin", True)):
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w") as archive:
                entry = zipfile.ZipInfo(filename)
                if symlink: entry.external_attr = (stat.S_IFLNK | 0o777) << 16
                archive.writestr(entry, b"test-only")
            with self.subTest(filename=filename, symlink=symlink), self.assertRaises(ValueError): check_zip(buffer.getvalue(), "native")

    def test_deterministic_archive_extracts_and_verifies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); dist = root / "dist"; dist.mkdir(); fixture(dist)
            first = package(dist, root / "packages")
            self.assertEqual(first, package(dist, root / "packages"))
            extracted = root / "extracted"
            with zipfile.ZipFile(first) as archive: archive.extractall(extracted)
            bundle = extracted / "ghostmap-local-demo"
            manifest, allowed = verify_bundle(bundle)
            self.assertTrue(manifest["local_draft_only"])
            self.assertFalse(manifest["milestone_pass_implied"])
            self.assertIn("artsquad.html", allowed)
            (bundle / "dist/artsquad.js").write_bytes(b"tampered")
            with self.assertRaises(ValueError): verify_bundle(bundle)


if __name__ == "__main__": unittest.main()
