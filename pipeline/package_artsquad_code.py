#!/usr/bin/env python3
"""Build a deterministic, source-only Arts Quad reproduction archive.

The archive is an explicit allowlist, not a recursive workspace export. Public
research sources and local viewer code are included; datasets, fitted models,
weights, runtime state, credentials, native binaries and caches are not.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import stat
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_ROOT = "ghostmap-artsquad-source"
MANIFEST_NAME = "SOURCE_MANIFEST.json"
FIXED_TIMESTAMP = (1980, 1, 1, 0, 0, 0)

# Every pattern is confined to one source directory and one text/source suffix.
# Public config files are enumerated instead of matching arbitrary JSON that
# might later contain credentials or host-specific runtime configuration.
SOURCE_PATTERNS = (
    "README", "README.md", "README.rst", "README.txt",
    "requirements.txt", "requirements-artsquad.txt", "requirements-hloc.txt", "requirements-repair.txt",
    "run_pipeline.sh", "run_repair.sh",
    "config/artsquad-modern.json", "config/artsquad-project.json",
    "pipeline/*.py", "tests/test_artsquad*.py",
    "docs/artsquad*.md", "docs/demo-delivery-contract.md",
    "docs/modern-artsquad-pipeline.md", "docs/research/*.md",
    "docs/results-repair.md",
    "dist/index.html", "dist/artsquad.html", "dist/artsquad.js", "dist/artsquad.css", "dist/artsquad-evidence.css", "dist/demo-reel.html",
    "dist/vendor/README.md", "dist/vendor/three.module.js",
    "dist/vendor/OrbitControls.js", "dist/vendor/OBJLoader.js", "dist/vendor/MTLLoader.js",
    "dist/vendor/LICENSE", "dist/vendor/LICENSE.*", "dist/vendor/LICENCE", "dist/vendor/LICENCE.*",
)
SENSITIVE_CONFIG_KEYS = {
    "password", "passwd", "access_token", "refresh_token", "api_key", "secret",
    "client_secret", "private_key", "authorization", "aws_access_key_id", "aws_secret_access_key",
}


def _canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def _public_config(value, path):
    """Fail closed on populated credential fields in allowlisted public configs."""
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in SENSITIVE_CONFIG_KEYS and item not in (None, "", False):
                raise ValueError("Populated credential field in public config: " + path)
            _public_config(item, path)
    elif isinstance(value, list):
        for item in value:
            _public_config(item, path)


def _source_bytes(root):
    root = Path(root).resolve()
    selected = {}
    for pattern in SOURCE_PATTERNS:
        for candidate in sorted(root.glob(pattern)):
            relative = candidate.relative_to(root)
            # A changed checkout may replace a source or an entire source
            # directory with a symlink. Never follow it into data or secrets.
            if any((root.joinpath(*relative.parts[:index])).is_symlink() for index in range(1, len(relative.parts) + 1)):
                raise ValueError("Refusing symlinked source: " + relative.as_posix())
            if not candidate.is_file():
                continue
            if not candidate.resolve().is_relative_to(root):
                raise ValueError("Source path escapes project root: " + relative.as_posix())
            payload = candidate.read_bytes()
            try:
                decoded = payload.decode("utf-8")
            except UnicodeDecodeError as error:
                raise ValueError("Source allowlist contains non-UTF-8/binary input: " + relative.as_posix()) from error
            if "\x00" in decoded or re.search(r"(?m)^\s*-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----\s*$", decoded):
                raise ValueError("Source allowlist contains binary/private-key content: " + relative.as_posix())
            if relative.parent.as_posix() == "config":
                _public_config(json.loads(decoded), relative.as_posix())
            selected[relative.as_posix()] = payload
    if not selected:
        raise ValueError("No allowlisted source files found")
    return dict(sorted(selected.items()))


def _zip_entry(name, payload):
    entry = zipfile.ZipInfo(name, date_time=FIXED_TIMESTAMP)
    entry.create_system = 3
    entry.external_attr = (stat.S_IFREG | 0o644) << 16
    entry.compress_type = zipfile.ZIP_DEFLATED
    return entry, payload


def package_source(dist: Path, root: Path = ROOT) -> Path:
    """Return a content-versioned deterministic ZIP containing allowlisted source.

    ``root`` is injectable for isolated tests. Source files are read once; the
    canonical byte manifest hashes the exact bytes stored in the ZIP, rather
    than modification times, host paths, or subsequently reread files.
    """
    sources = _source_bytes(root)
    manifest = {
        "schema_version": 1,
        "package": ARCHIVE_ROOT,
        "hash_algorithm": "sha256",
        "files": [{"path": path, "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()} for path, payload in sources.items()],
        "excludes": ["images and datasets", "caches and runtime state", "weights and native binaries", "credentials and host secrets"],
        "notice": "Source-only reproduction package. Acquire permitted data and install documented dependencies separately; scientific and public-demo acceptance are not implied.",
    }
    manifest_bytes = _canonical(manifest)
    version = hashlib.sha256(manifest_bytes).hexdigest()
    archive_path = Path(dist).resolve() / "assets/artsquad/code" / version / "ghostmap-artsquad-source.zip"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        entries = {**sources, MANIFEST_NAME: manifest_bytes}
        for name, payload in sorted(entries.items()):
            entry, content = _zip_entry(ARCHIVE_ROOT + "/" + name, payload)
            archive.writestr(entry, content, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    packed = buffer.getvalue()
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    if archive_path.exists():
        if archive_path.read_bytes() != packed:
            raise ValueError("Existing content-versioned source archive differs; refusing to overwrite: " + str(archive_path))
    else:
        archive_path.write_bytes(packed)
    return archive_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    print(package_source(args.dist))


if __name__ == "__main__":
    main()
