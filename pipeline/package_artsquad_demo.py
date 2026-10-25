#!/usr/bin/env python3
"""Package only the current local draft's explicit dependency closure.

Never recursively zip dist/, original pools, weights, caches or provider data.
The portable bundle remains a local research draft, not D1 or public approval.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import shlex
import stat
import zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_ROOT = "ghostmap-local-demo"
MAX_BYTES = 256 * 1024 * 1024
STATIC = ("index.html", "artsquad.html", "artsquad.js", "artsquad.css", "artsquad-evidence.css", "demo-reel.html",
          "vendor/three.module.js", "vendor/OrbitControls.js", "vendor/OBJLoader.js", "vendor/MTLLoader.js", "vendor/README.md", "vendor/LICENSE.three")
EXTERNAL_METADATA_KEYS = {"source_url", "page_url", "original_url", "license_url", "https_url", "base_url"}
LICENSE_RE = re.compile(r"^(?:CC BY(?:-SA)? (?:1\.0|2\.0|2\.5|3\.0|4\.0)|CC0(?: 1\.0)?|Public domain)$", re.I)


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


def contained_path(root, value, relative_to=None):
    parsed = urlsplit(str(value))
    if parsed.scheme or parsed.netloc or parsed.fragment:
        raise ValueError("Expected a confined local asset URL: " + str(value))
    decoded = unquote(parsed.path)
    if "\\" in decoded or "\x00" in decoded:
        raise ValueError("Invalid local asset path")
    path = PurePosixPath(decoded)
    if path.is_absolute() or any(part == ".." for part in path.parts):
        raise ValueError("Asset path is absolute or escapes its directory: " + str(value))
    base = Path(relative_to) if relative_to is not None else Path()
    relative = base / Path(*path.parts)
    candidate = root / relative
    if any((root.joinpath(*relative.parts[:i])).is_symlink() for i in range(1, len(relative.parts) + 1)):
        raise ValueError("Refusing symlinked bundle asset: " + str(relative))
    if not candidate.resolve().is_relative_to(root.resolve()) or not candidate.is_file():
        raise ValueError("Missing or escaping local asset: " + str(relative))
    return relative.as_posix()


def asset_references(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, str) and (key in {"url", "photo"} or key.endswith("_url")) and key not in EXTERNAL_METADATA_KEYS:
                if item:
                    yield item
            else:
                yield from asset_references(item)
    elif isinstance(value, list):
        for item in value:
            yield from asset_references(item)


def check_photo_rights(camera, source):
    license_name = camera.get("license", "")
    if not LICENSE_RE.fullmatch(license_name) or license_name != source.get("license"):
        raise ValueError("Unknown, restricted or conflicting photograph license: " + camera.get("name", "unnamed"))
    if not camera.get("attribution") or not camera.get("source_url") or camera["source_url"] != source.get("source_url"):
        raise ValueError("Photograph attribution/source record is missing or inconsistent")
    if license_name.lower().startswith("cc by"):
        version = license_name.rsplit(" ", 1)[1]
        family = "by-sa" if "BY-SA" in license_name.upper() else "by"
        expected = f"https://creativecommons.org/licenses/{family}/{version}"
        if camera.get("license_url", "").rstrip("/") != expected or camera.get("license_url", "").rstrip("/") != source.get("license_url", "").rstrip("/"):
            raise ValueError("Creative Commons attribution license requires its matching recorded license link")
    return {"camera_name": camera["name"], "source_url": camera["source_url"], "license": license_name,
            "license_url": camera.get("license_url", ""), "attribution": camera["attribution"]}


def check_zip(payload, role):
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        total = 0
        for entry in archive.infolist():
            name = PurePosixPath(entry.filename)
            if name.is_absolute() or ".." in name.parts or "\\" in entry.filename or stat.S_ISLNK(entry.external_attr >> 16):
                raise ValueError("Unsafe nested ZIP entry")
            total += entry.file_size
            if total > MAX_BYTES:
                raise ValueError("Nested ZIP exceeds local draft budget")
            if role == "native" and name.name not in {"cameras.bin", "images.bin", "points3D.bin", "frames.bin", "rigs.bin", "diagnostics.json"}:
                raise ValueError("Native COLMAP ZIP contains more than geometry/calibration diagnostics")
            if role == "source" and (name.parts[0] != "ghostmap-artsquad-source" or (name.suffix.lower() not in {".py", ".md", ".txt", ".json", ".sh", ".html", ".css", ".js", ".rst", ""} and not name.name.startswith(("LICENSE", "LICENCE")))):
                raise ValueError("Source ZIP contains an unexpected file or binary")


def collect_sources(dist):
    dist = Path(dist).resolve()
    selected, roles, rights, transformations = {}, {}, [], []

    def add(value, role="metadata", relative_to=None):
        name = contained_path(dist, value, relative_to)
        payload = (dist / name).read_bytes()
        if name in selected and selected[name] != payload:
            raise ValueError("Bundle source changed while collecting its dependency closure")
        selected[name] = payload
        roles.setdefault(name, set()).add(role)
        if sum(len(data) for data in selected.values()) > MAX_BYTES:
            raise ValueError("Explicit local draft closure exceeds 256 MiB; refusing a stale/full-dist export")
        return name

    for name in STATIC: add(name, "viewer-code")
    scene_name = add("assets/artsquad/scene.json", "scene")
    scene = json.loads(selected[scene_name])
    if scene.get("schema_version") != 1 or not scene.get("run_id") or scene.get("asset_base"):
        raise ValueError("An actual local scene without an external asset base is required")
    for value in asset_references(scene): add(value)
    sources_name = contained_path(dist, scene["sources_url"])
    sources = {record["filename"]: record for record in json.loads(selected[sources_name])["images"]}
    for component in scene.get("components", []):
        cameras = {str(camera["id"]): camera for camera in component.get("cameras", [])}
        for camera in cameras.values():
            record = sources.get(camera["name"])
            if record is None:
                raise ValueError("A displayed photograph has no frozen source/rights record")
            if camera.get("split") != "train" or record.get("split") != "train" or record.get("role") != "scene-candidate" or (record.get("validation") or {}).get("passed") is not True:
                raise ValueError("A displayed source is not an admitted reconstruction-training photograph")
            rights.append(check_photo_rights(camera, record))
            add(camera["photo"], "licensed-source-photo")
        mesh = component.get("mesh") or {}
        if mesh.get("url"):
            obj_name = add(mesh["url"], "measured-geometry")
            libraries = [shlex.split(line)[1:] for line in selected[obj_name].decode().splitlines() if line.startswith("mtllib ")]
            if len(libraries) != 1 or len(libraries[0]) != 1:
                raise ValueError("Expected one explicitly named OBJ material library")
            mtl_name = add(libraries[0][0], "material", PurePosixPath(obj_name).parent)
            if mtl_name != contained_path(dist, mesh["mtl_url"]):
                raise ValueError("OBJ material dependency differs from the scene manifest")
            material = None
            for line in selected[mtl_name].decode().splitlines():
                fields = shlex.split(line)
                if not fields: continue
                if fields[0] == "newmtl": material = " ".join(fields[1:])
                elif fields[0].lower().startswith("map_"):
                    if fields[0] != "map_Kd" or len(fields) != 2:
                        raise ValueError("Unsupported texture dependency; do not guess material options")
                    camera_id = component.get("source_materials", {}).get(material)
                    if camera_id is None or str(camera_id) not in cameras:
                        raise ValueError("Texture has no admitted licensed source camera")
                    texture = add(fields[1], "licensed-photo-texture", PurePosixPath(mtl_name).parent)
                    rights.append({**check_photo_rights(cameras[str(camera_id)], sources[cameras[str(camera_id)]["name"]]), "derived_texture": texture})
        if component.get("model_download_url"):
            name = add(component["model_download_url"], "native-colmap-zip")
            check_zip(selected[name], "native")
    if scene.get("source_code_url"):
        name = add(scene["source_code_url"], "source-only-zip")
        check_zip(selected[name], "source")

    reel_name = add("assets/artsquad/demo/latest.json", "recording-index")
    reel = json.loads(selected[reel_name])
    if reel.get("status") != "local_diagnostic_recording" or reel.get("scene_manifest_sha256") != digest(selected[scene_name]):
        raise ValueError("Final portable draft requires a verified recording of this exact current scene")
    for value in asset_references(reel): add(value, "recording")
    report_name = contained_path(dist, reel["report_url"])
    report = json.loads(selected[report_name])
    if (digest(selected[report_name]) != reel.get("recording_report_sha256") or report.get("status") != "recorded_diagnostic_only"
            or report.get("source_files_unchanged") is not True or any(report.get("claims", {}).values())):
        raise ValueError("The actual diagnostic recording report is inconsistent or elevates acceptance claims")
    if report.get("video_verification", {}).get("first_frame_disclosure_present") is not True:
        raise ValueError("The final recording must verify its actual first-frame diagnostic disclosure")
    recorded_viewer = report.get("viewer_source_sha256", {})
    required_viewer = {"dist/artsquad.html", "dist/artsquad.js", "dist/artsquad.css", "dist/artsquad-evidence.css", "dist/assets/artsquad/scene.json"}
    if not required_viewer.issubset(recorded_viewer):
        raise ValueError("The recording must identify all actual viewer and scene source bytes")
    for path in required_viewer:
        name = path.removeprefix("dist/")
        if digest(selected[name]) != recorded_viewer[path]:
            raise ValueError("Viewer code changed after recording; re-record the final frozen package")
    for url, expected in [(reel["video_url"], reel["video"]["sha256"]), (reel["scene_manifest_url"], reel["scene_manifest_sha256"]),
                          *((capture["url"], capture["sha256"]) for capture in reel.get("captures", []))]:
        if digest(selected[contained_path(dist, url)]) != expected:
            raise ValueError("A recorded asset differs from the verified recording index")

    # The earlier full experiment site is intentionally outside this small
    # portable draft. Keep its historical source in the source ZIP, but make
    # the portable navigation point to the actual included recording instead.
    html = selected["artsquad.html"].decode()
    revised = html.replace('href="surface-lab.html">Earlier experiments ↗', 'href="demo-reel.html">Recorded local draft ↗')
    if revised != html:
        transformations.append({"path": "dist/artsquad.html", "kind": "portable-navigation-only", "source_sha256": digest(selected["artsquad.html"]),
                                "detail": "Earlier experiments are not included; link points to the verified included reel. No scene data or milestone state changed."})
        selected["artsquad.html"] = revised.encode()
    before = {name: digest(payload) for name, payload in selected.items() if name != "artsquad.html"}
    for name, expected in before.items():
        if digest((dist / name).read_bytes()) != expected:
            raise ValueError("A dependency changed before the package was sealed")
    if digest((dist / "artsquad.html").read_bytes()) != (transformations[0]["source_sha256"] if transformations else digest(selected["artsquad.html"])):
        raise ValueError("The viewer changed before the package was sealed")
    return {"dist/" + name: payload for name, payload in selected.items()}, scene, reel, rights, transformations


def package(dist=ROOT / "dist", output_root=ROOT / "artifacts/demo-packages"):
    payloads, scene, reel, rights, transformations = collect_sources(dist)
    payloads["serve_artsquad_demo.py"] = (ROOT / "pipeline/serve_artsquad_demo.py").read_bytes()
    payloads["DEMO_RUNBOOK.md"] = (ROOT / "docs/artsquad-demo-runbook.md").read_bytes()
    payloads["RIGHTS_RECORDS.json"] = canonical({"local_research_draft_only": True, "public_release_approved": False,
        "notice": "Recorded per-image licenses and attribution only, not a completed legal/institutional review. Preserve CC BY/SA conditions; do not republish as an approved public release.", "records": rights})
    payloads["README.txt"] = ("GHOSTMAP — LOCAL DIAGNOSTIC DRAFT, NOT ACCEPTED D0/D1\n\n"
        "Extract this archive into a new folder. Requires Python 3.10+ and a desktop browser with WebGL2.\n"
        "Run: python serve_artsquad_demo.py\n"
        "Then open http://127.0.0.1:8082/artsquad.html or /demo-reel.html\n"
        "The launcher binds loopback only, verifies bundle hashes and never stops another server.\n"
        "Use --port 8083 if 8082 is already occupied. No package install or external service is needed.\n\n"
        "Separate components remain separate; surface fragments are incomplete, scale is unverified.\n"
        "No generated geometry, metric-accuracy, real-device performance, HTTPS, rights-clearance or D1 claim.\n"
        "This archive excludes previous runs, original pools, weights, caches and unknown-rights provider assets.\n"
        "See DEMO_RUNBOOK.md, RIGHTS_RECORDS.json and BUNDLE_MANIFEST.json for details.\n").encode()
    manifest = {"schema_version": 1, "package": ARCHIVE_ROOT, "local_draft_only": True,
        "run_id": scene["run_id"], "snapshot_id": scene.get("snapshot_id"),
        "scene_manifest_sha256": digest(payloads["dist/assets/artsquad/scene.json"]), "recording_report_sha256": reel["recording_report_sha256"],
        "milestone_pass_implied": False, "public_release_approved": False, "transformations": transformations,
        "files": [{"path": path, "bytes": len(payload), "sha256": digest(payload)} for path, payload in sorted(payloads.items())],
        "excluded": ["stale dist experiments", "original image pools", "unknown-rights provider assets", "model weights", "caches", "secrets", "raw recording preroll"]}
    manifest_bytes = canonical(manifest)
    version = digest(manifest_bytes)
    output = Path(output_root) / version / "ghostmap-local-demo.zip"
    output.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path, payload in sorted({**payloads, "BUNDLE_MANIFEST.json": manifest_bytes}.items()):
            entry = zipfile.ZipInfo(ARCHIVE_ROOT + "/" + path, date_time=(1980, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(entry, payload, compress_type=zipfile.ZIP_DEFLATED)
    packed = buffer.getvalue()
    if output.exists() and output.read_bytes() != packed:
        raise ValueError("Existing content-versioned archive differs; refusing overwrite")
    if not output.exists(): output.write_bytes(packed)
    report = {"status": "packaged_local_draft_only", "run_id": scene["run_id"], "files": len(payloads),
              "uncompressed_bytes": sum(len(payload) for payload in payloads.values()), "zip_bytes": len(packed),
              "zip_sha256": digest(packed), "bundle_manifest_sha256": version, "archive": str(output),
              "d1_passed": False, "public_release_approved": False}
    (output.parent / "package-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=ROOT / "dist")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/demo-packages")
    args = parser.parse_args()
    package(args.dist, args.output)
