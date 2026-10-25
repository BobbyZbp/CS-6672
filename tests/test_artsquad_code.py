import hashlib
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
from package_artsquad_code import ARCHIVE_ROOT, FIXED_TIMESTAMP, package_source


class SourceArchiveTests(unittest.TestCase):
    def fixture(self, root):
        sources = {
            "README.md": "# Reproduction\n",
            "requirements-artsquad.txt": "example==1.0\n",
            "config/artsquad-modern.json": '{"targets":[]}\n',
            "config/artsquad-project.json": '{"project_id":"test"}\n',
            "pipeline/run_artsquad.py": 'print("source only")\n',
            "tests/test_artsquad_fixture.py": "# test source\n",
            "docs/artsquad-implementation.md": "# Implementation\n",
            "docs/demo-delivery-contract.md": "# Delivery\n",
            "docs/modern-artsquad-pipeline.md": "# Pipeline\n",
            "docs/research/colmap-engineering.md": "# Research\n",
            "docs/results-repair.md": "# Baseline\n",
            "dist/index.html": "<!doctype html>\n",
            "dist/artsquad.html": "<!doctype html>\n",
            "dist/artsquad.js": "// source\n",
            "dist/artsquad.css": "body {}\n",
            "dist/vendor/three.module.js": "// local vendored source\n",
            "dist/vendor/LICENSE": "MIT\n",
        }
        for name, content in sources.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        return sources

    def test_source_only_and_manifest_matches_exact_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources = self.fixture(root)
            for name in (".env", ".aws/credentials", "config/credentials.json", "config/host-runtime.json", "data/photo.jpg", "artifacts/model.bin", "dist/assets/image.jpg", ".cache/secret.py", "third_party/native-binary", "tests/unrelated.py", "pipeline/__pycache__/runtime.pyc"):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"not part of the source package")
            output = package_source(root / "dist", root=root)
            with zipfile.ZipFile(output) as archive:
                names = archive.namelist()
                self.assertEqual(names, sorted(names))
                self.assertEqual(set(names), {ARCHIVE_ROOT + "/" + name for name in sources} | {ARCHIVE_ROOT + "/SOURCE_MANIFEST.json"})
                manifest_bytes = archive.read(ARCHIVE_ROOT + "/SOURCE_MANIFEST.json")
                manifest = json.loads(manifest_bytes)
                self.assertEqual(output.parent.name, hashlib.sha256(manifest_bytes).hexdigest())
                for record in manifest["files"]:
                    payload = archive.read(ARCHIVE_ROOT + "/" + record["path"])
                    self.assertEqual(record["bytes"], len(payload))
                    self.assertEqual(record["sha256"], hashlib.sha256(payload).hexdigest())
                for entry in archive.infolist():
                    self.assertEqual(entry.date_time, FIXED_TIMESTAMP)
                    self.assertEqual((entry.external_attr >> 16) & 0o777, 0o644)
                    self.assertFalse(entry.filename.startswith("/"))
                    self.assertNotIn("..", Path(entry.filename).parts)

    def test_mtime_and_unrelated_outputs_do_not_change_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            first = package_source(root / "dist", root=root)
            first_bytes = first.read_bytes()
            os.utime(root / "README.md", (1800000000, 1800000000))
            (root / "dist/assets").mkdir(exist_ok=True)
            (root / "dist/assets/runtime.json").write_text('{"run":"later"}')
            second = package_source(root / "dist", root=root)
            self.assertEqual(first, second)
            self.assertEqual(first_bytes, second.read_bytes())

    def test_source_change_creates_new_version_without_overwriting(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            first = package_source(root / "dist", root=root)
            original = first.read_bytes()
            (root / "pipeline/run_artsquad.py").write_text('print("new source")\n')
            second = package_source(root / "dist", root=root)
            self.assertNotEqual(first, second)
            self.assertEqual(first.read_bytes(), original)

    def test_symlinked_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            (root / "outside-secret").write_text("not a source")
            (root / "pipeline/linked.py").symlink_to(root / "outside-secret")
            with self.assertRaisesRegex(ValueError, "symlinked"):
                package_source(root / "dist", root=root)

    def test_populated_credentials_in_public_config_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            (root / "config/artsquad-project.json").write_text('{"nested":{"api_key":"credential"}}')
            with self.assertRaisesRegex(ValueError, "credential field"):
                package_source(root / "dist", root=root)

    def test_private_key_or_binary_source_is_rejected(self):
        for content in (b"\x00binary", b"-----BEGIN PRIVATE KEY-----\nnot-public", b"\xff"):
            with self.subTest(content=content), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.fixture(root)
                (root / "pipeline/not_source.py").write_bytes(content)
                with self.assertRaises(ValueError):
                    package_source(root / "dist", root=root)

    def test_source_guard_can_include_its_own_header_check(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            (root / "pipeline/header_check.py").write_text('marker = "-----BEGIN PRIVATE KEY-----"\n')
            self.assertTrue(package_source(root / "dist", root=root).is_file())

    def test_existing_content_version_cannot_be_silently_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            output = package_source(root / "dist", root=root)
            output.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
                package_source(root / "dist", root=root)

    def test_empty_root_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "No allowlisted"):
                package_source(root / "dist", root=root)


if __name__ == "__main__":
    unittest.main()
