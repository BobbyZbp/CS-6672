#!/usr/bin/env python3
"""Reuse only compatible training feature/match groups across frozen snapshots.

No database, camera model, held-out feature or complete HDF5 file is copied.
Feature/match file existence alone is never sufficient for reuse.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path

from run_artsquad_sfm import select_training_images, sha256, write_json

FINGERPRINT_FIELDS = ("resize", "keypoints", "torch_version", "pycolmap_version", "extractor", "matcher", "retrieval")


def _fingerprint(configuration):
    missing = [key for key in FINGERPRINT_FIELDS if key not in configuration]
    if missing:
        raise ValueError("Missing feature fingerprint fields: " + ", ".join(missing))
    return {key: configuration[key] for key in FINGERPRINT_FIELDS}


def _group_digest(group):
    """Content digest survives legitimate additions elsewhere in an HDF5 file."""
    import h5py
    digest = hashlib.sha256()
    def visit(name, obj):
        digest.update(name.encode())
        for key in sorted(obj.attrs):
            value = obj.attrs[key]
            digest.update(key.encode())
            digest.update(str(getattr(value, "dtype", type(value).__name__)).encode())
            digest.update(value.tobytes() if hasattr(value, "tobytes") else repr(value).encode())
        if isinstance(obj, h5py.Dataset):
            digest.update(str(obj.shape).encode())
            digest.update(str(obj.dtype).encode())
            value = obj[()]
            digest.update(value.tobytes() if hasattr(value, "tobytes") else repr(value).encode())
    visit("", group)
    group.visititems(visit)
    return digest.hexdigest()


def _pair_names(group_name, allowed_names):
    """Preserve normal and legacy HLOC pair orientation, never guess identity."""
    if "/" in group_name:
        parts = group_name.split("/")
        return tuple(parts) if len(parts) == 2 and parts[0] in allowed_names and parts[1] in allowed_names and parts[0] != parts[1] else None
    candidates = [(name, group_name[len(name) + 1:]) for name in allowed_names
                  if group_name.startswith(name + "_") and group_name[len(name) + 1:] in allowed_names]
    candidates = [pair for pair in candidates if pair[0] != pair[1]]
    if len(candidates) > 1:
        raise ValueError("Ambiguous legacy HLOC pair name: " + group_name)
    return candidates[0] if candidates else None


def _pair_groups(file):
    import h5py
    groups = []
    def visit(name, obj):
        if isinstance(obj, h5py.Group) and "matches0" in obj:
            groups.append(name)
    file.visititems(visit)
    return sorted(groups)


def _feature_names(file):
    return set(file.keys())


def _assert_sources_unchanged(hashes):
    for path, digest in hashes.items():
        if not Path(path).is_file() or sha256(path) != digest:
            raise RuntimeError("Source artifact changed during cache reuse: " + path)


def _validate_complete_cache(source, feature_files, match_name, training_names):
    """Feature/match completeness is independent of a failed native importer."""
    import h5py
    import numpy as np
    counts = {}
    for filename in feature_files:
        with h5py.File(source / filename, "r") as file:
            if _feature_names(file) != set(training_names):
                raise ValueError("Source feature cache must contain exactly every declared training image, never held-out groups")
            for name in sorted(training_names):
                group = file[name]
                required = ("global_descriptor", "image_size") if filename.startswith("global-") else ("keypoints", "descriptors", "scores", "image_size")
                if any(key not in group for key in required):
                    raise ValueError("Source feature datasets are incomplete: " + filename + ":" + name)
                size = group["image_size"][()]
                if size.shape != (2,) or not np.isfinite(size).all() or not (size > 0).all():
                    raise ValueError("Invalid source feature image dimensions: " + name)
                for key in required:
                    if not np.isfinite(group[key][()]).all():
                        raise ValueError("Nonfinite source features: " + name + ":" + key)
                if filename.startswith("global-"):
                    if group["global_descriptor"].ndim != 1 or not group["global_descriptor"].size:
                        raise ValueError("Invalid source global descriptor: " + name)
                else:
                    points, descriptors, scores = group["keypoints"], group["descriptors"], group["scores"]
                    if points.ndim != 2 or points.shape[1] != 2 or descriptors.ndim != 2 or descriptors.shape[1] != len(points) or scores.shape != (len(points),):
                        raise ValueError("Invalid source local feature dimensions: " + name)
                    counts[name] = len(points)
    pairs_path = source / "pairs.txt"
    expected = []
    for line in pairs_path.read_text().splitlines():
        if not line.strip():
            continue
        pair = line.split()
        if len(pair) != 2 or pair[0] not in training_names or pair[1] not in training_names or pair[0] == pair[1]:
            raise ValueError("Source retrieval pairs contain undeclared image names")
        expected.append(tuple(pair))
    with h5py.File(source / match_name, "r") as file:
        groups = _pair_groups(file)
        available = {}
        for group_name in groups:
            pair = _pair_names(group_name, set(training_names))
            if pair is None:
                raise ValueError("Source match cache contains undeclared or ambiguous image names")
            group = file[group_name]
            if "matching_scores0" not in group:
                raise ValueError("Source match scores are incomplete: " + group_name)
            matches, scores = group["matches0"][()], group["matching_scores0"][()]
            if matches.shape != (counts[pair[0]],) or scores.shape != matches.shape or not np.issubdtype(matches.dtype, np.integer):
                raise ValueError("Source match array dimensions are incomplete: " + group_name)
            if not np.isfinite(scores).all() or (matches < -1).any() or (matches >= counts[pair[1]]).any():
                raise ValueError("Source matches contain invalid scores or reference indices: " + group_name)
            available.setdefault(frozenset(pair), []).append(group_name)
        if any(frozenset(pair) not in available for pair in expected):
            raise ValueError("Source expected pair matching is incomplete")
    return {"feature_images": len(training_names), "expected_pairs": len(expected), "complete_match_groups": len(groups),
            "validated": True, "basis": "Exact training image groups, finite aligned descriptor arrays, complete expected pairs, oriented match/scores shapes and valid reference indices."}


def reuse_cache(destination: Path, source: Path, config: dict, records: list) -> dict:
    import h5py

    destination, source = Path(destination).resolve(), Path(source).resolve()
    if destination == source:
        raise ValueError("Source and destination runs must differ")
    source_report_path = source / "report.json"
    source_report = json.loads(source_report_path.read_text())
    if source_report.get("status") not in {"sfm_complete", "no_model", "error"}:
        raise ValueError("Cache source must be completed or errored after a fully validated feature/match cache")
    previous_config = source_report["configuration"]
    fingerprint = _fingerprint(config)
    if fingerprint != _fingerprint(previous_config):
        raise ValueError("Incompatible feature fingerprint; refusing cache reuse")
    snapshot_path = Path(source_report["snapshot_path"]).resolve()
    if sha256(snapshot_path) != previous_config["snapshot_sha256"]:
        raise ValueError("Source frozen snapshot hash changed")
    snapshot = json.loads(snapshot_path.read_text())
    if snapshot["snapshot_id"] != source_report["snapshot_id"]:
        raise ValueError("Source snapshot ID disagrees with the completed report")
    old_training = select_training_images(snapshot, previous_config.get("targets", ()))
    old_by_name = {row["filename"]: row for row in old_training}
    declared_source_inputs = source_report.get("input_images")
    if not isinstance(declared_source_inputs, list) or set(declared_source_inputs) != set(old_by_name):
        raise ValueError("Source input image list disagrees with its frozen training selection")
    current = {}
    for row in records:
        if not isinstance(row, Mapping) or row.get("split") != "train" or row.get("role") != "scene-candidate" or row.get("validation", {}).get("passed") is not True:
            raise ValueError("Only admitted current training records may reuse a cache")
        name = row.get("filename")
        if not isinstance(name, str) or not name or Path(name).name != name or any(char.isspace() for char in name) or name in current:
            raise ValueError("Current training names must be distinct safe basenames")
        current[name] = row
    common_names = sorted(set(current) & set(old_by_name))
    for name in common_names:
        current_row, old_row = current[name], old_by_name[name]
        if not current_row.get("sha256_working") or current_row["sha256_working"] != old_row.get("sha256_working"):
            raise ValueError("Working hash changed across snapshots: " + name)
        for row in (current_row, old_row):
            path = Path(row["working_path"])
            if not path.is_file() or sha256(path) != row["sha256_working"]:
                raise ValueError("Frozen working input changed: " + name)
    local_name = f"feats-superpoint-n{config['keypoints']}-r{config['resize']}.h5"
    feature_files = ("global-feats-netvlad.h5", local_name)
    match_name = "matches-lightglue.h5"
    names = (*feature_files, match_name)
    guard_files = [source_report_path, snapshot_path, source / "pairs.txt"] + [source / name for name in names]
    if (source / "configuration.json").is_file():
        recorded_config = json.loads((source / "configuration.json").read_text())
        if recorded_config != previous_config:
            raise ValueError("Source report/configuration disagree")
        guard_files.append(source / "configuration.json")
    if (source / "sfm/database.db").is_file():
        guard_files.append(source / "sfm/database.db")
    model_root = source / "sfm/models"
    if model_root.exists():
        guard_files.extend(path for path in model_root.rglob("*") if path.is_file() and path.suffix in {".bin", ".txt"})
    before = {str(path): sha256(path) for path in guard_files}
    cache_validation = _validate_complete_cache(source, feature_files, match_name, set(old_by_name))
    identity = {"version": 1, "source_run_id": source_report["run_id"], "source_directory": str(source),
                "source_snapshot_sha256": previous_config["snapshot_sha256"], "destination_snapshot_sha256": config.get("snapshot_sha256"),
                "fingerprint": fingerprint, "current_training_names": sorted(current),
                "common_training_images": {name: current[name]["sha256_working"] for name in common_names},
                "source_artifacts_sha256": before}
    destination.mkdir(parents=True, exist_ok=True)
    marker = destination / "cache-reuse.json"
    if marker.exists():
        provenance = json.loads(marker.read_text())
        if provenance.get("identity") != identity:
            raise ValueError("Existing cache-reuse identity differs; refusing ambiguous reuse")
        for filename, groups in provenance["copied_groups_sha256"].items():
            with h5py.File(destination / filename, "r") as output:
                if filename in feature_files and not _feature_names(output) <= set(current):
                    raise ValueError("Destination features contain undeclared current images")
                if filename == match_name and any(_pair_names(group, set(current)) is None for group in _pair_groups(output)):
                    raise ValueError("Destination matches contain undeclared current images")
                for group, digest in groups.items():
                    if group not in output or _group_digest(output[group]) != digest:
                        raise ValueError("Previously reused HDF5 group changed: " + filename + ":" + group)
        _assert_sources_unchanged(before)
        return provenance
    if any((destination / filename).exists() for filename in names):
        raise ValueError("Destination cache already exists without matching reuse provenance; no files replaced")
    copied = {}
    pair_count = 0
    try:
        for filename in feature_files:
            copied[filename] = {}
            with h5py.File(source / filename, "r") as original, h5py.File(destination / (filename + ".reuse-tmp"), "x") as output:
                if not _feature_names(original) <= set(old_by_name):
                    raise ValueError("Source feature cache contains undeclared or held-out image groups")
                for name in common_names:
                    if name not in original:
                        raise ValueError("Common training image is absent from source features: " + name)
                    original.copy(name, output, name=name)
                    copied[filename][name] = _group_digest(output[name])
        copied[match_name] = {}
        with h5py.File(source / match_name, "r") as original, h5py.File(destination / (match_name + ".reuse-tmp"), "x") as output:
            for group in _pair_groups(original):
                pair = _pair_names(group, set(old_by_name))
                if pair is None:
                    raise ValueError("Source match cache contains an undeclared/ambiguous pair: " + group)
                if not set(pair) <= set(common_names):
                    continue
                parent_name, _, leaf = group.rpartition("/")
                parent = output.require_group(parent_name) if parent_name else output
                original.copy(group, parent, name=leaf)
                copied[match_name][group] = _group_digest(output[group])
                pair_count += 1
        _assert_sources_unchanged(before)
        for filename in names:
            target = destination / filename
            if target.exists():
                raise ValueError("Destination appeared during cache staging; no replacement permitted")
            (destination / (filename + ".reuse-tmp")).replace(target)
        provenance = {"schema_version": 1, "status": "cache_reused", "identity": identity,
                      "source_sfm_status": source_report["status"], "source_sfm_error": source_report.get("error"),
                      "source_cache_validation": cache_validation,
                      "reused_images": len(common_names), "reused_pairs": pair_count,
                      "current_training_images": len(current), "images_requiring_extraction": len(current) - len(common_names),
                      "copied_groups_sha256": copied, "source_artifacts_unchanged": True,
                      "source_artifacts_sha256_before": before, "source_artifacts_sha256_after": dict(before),
                      "database_or_native_model_reused": False, "heldout_features_reused": False,
                      "limitations": ["Only compatible descriptor/match groups are reused; every camera, verified graph and SfM model must be recomputed.",
                                      "Hash and split compatibility do not certify independent exposures or correct building identity.",
                                      "The unchanged-source guard covers consumed reports/snapshot/features/matches plus existing mapping database and native models, not unrelated dense workspaces."]}
        write_json(marker, provenance)
        return provenance
    finally:
        _assert_sources_unchanged(before)
