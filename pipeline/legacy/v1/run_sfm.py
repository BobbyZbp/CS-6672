#!/usr/bin/env python3
"""Run three reproducible COLMAP reconstructions and emit audit artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import shutil
import sqlite3
import statistics
import sys
import time
from pathlib import Path

import numpy as np
import pycolmap


QUALITY_GATES = {
    "min_registered_images": 5,
    "min_unique_views": 5,
    "min_registration_ratio": 0.5,
    "min_sparse_points": 1000,
    "max_median_reprojection_error_px": 1.0,
    "min_median_track_length": 2.5,
    "min_nondegenerate_registered_pairs": 3,
    "min_cross_era_images_per_era": 3,
    "duplicate_hash_hamming_threshold": 10,
}
SFM_PRESETS = {
    "baseline": {
        "max_image_size_px": 1600,
        "max_sift_features": 4096,
        "feature_threads": 4,
        "matching_threads": 2,
        "exhaustive_block_size": 8,
        "guided_matching": True,
        "camera_model": "SIMPLE_RADIAL",
        "random_seed": 7,
        "estimate_affine_shape": False,
        "domain_size_pooling": False,
        "sift_peak_threshold": 0.006666666666666667,
        "sift_max_ratio": 0.8,
        "sift_cross_check": True,
        "assume_default_focal_prior": False,
    },
    "focal-prior": {
        "max_image_size_px": 1600,
        "max_sift_features": 4096,
        "feature_threads": 4,
        "matching_threads": 2,
        "exhaustive_block_size": 8,
        "guided_matching": True,
        "camera_model": "SIMPLE_RADIAL",
        "random_seed": 7,
        "estimate_affine_shape": False,
        "domain_size_pooling": False,
        "sift_peak_threshold": 0.006666666666666667,
        "sift_max_ratio": 0.8,
        "sift_cross_check": True,
        "assume_default_focal_prior": True,
    },
    # Archival scans violate SIFT's usual assumptions through print texture,
    # colorization, rescanning, and oblique reproductions. This remains native
    # COLMAP geometry, but uses COLMAP's affine-shape and DSP-SIFT options.
    "archival": {
        "max_image_size_px": 1600,
        "max_sift_features": 4096,
        "feature_threads": 4,
        "matching_threads": 1,
        "exhaustive_block_size": 4,
        "guided_matching": True,
        "camera_model": "SIMPLE_RADIAL",
        "random_seed": 7,
        "estimate_affine_shape": True,
        "domain_size_pooling": True,
        "sift_peak_threshold": 0.006666666666666667,
        "sift_max_ratio": 0.85,
        "sift_cross_check": True,
        "assume_default_focal_prior": True,
    },
}
SFM_CONFIG = dict(SFM_PRESETS["baseline"])


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def image_names(reconstruction: pycolmap.Reconstruction) -> list[str]:
    return sorted(image.name for image in reconstruction.images.values())


def camera_center(image) -> list[float]:
    try:
        return [float(v) for v in image.projection_center()]
    except Exception:
        matrix = np.asarray(image.cam_from_world.matrix())
        center = -matrix[:, :3].T @ matrix[:, 3]
        return [float(v) for v in center]


def count_unique_views(names: list[str], hashes: dict[str, str], threshold: int = QUALITY_GATES["duplicate_hash_hamming_threshold"]) -> int:
    clusters: list[list[int]] = []
    for name in names:
        value = hashes.get(name)
        if not value:
            clusters.append([])
            continue
        encoded = int(value, 16)
        placed = False
        for cluster in clusters:
            if cluster and min((encoded ^ member).bit_count() for member in cluster) <= threshold:
                cluster.append(encoded)
                placed = True
                break
        if not placed:
            clusters.append([encoded])
    return len(clusters)


def registered_pair_geometry(database: Path, names: list[str]) -> dict:
    """Audit whether registered views have actual parallax, not postcard copies.

    COLMAP configuration 4/5/6 identifies planar, panoramic, or ambiguous
    homography geometry. Such a pair can align two scans of one postcard but
    cannot support a 3D baseline.
    """
    connection = sqlite3.connect(database)
    try:
        ids_by_name = {
            name: int(image_id)
            for image_id, name in connection.execute("SELECT image_id, name FROM images")
        }
        wanted_ids = {ids_by_name[name] for name in names if name in ids_by_name}
        pair_base = 2147483647
        counts: dict[str, int] = {}
        accepted = 0
        tested = 0
        for pair_id, rows, config in connection.execute(
            "SELECT pair_id, rows, config FROM two_view_geometries WHERE rows > 0"
        ):
            image_id2 = int(pair_id % pair_base)
            image_id1 = int((pair_id - image_id2) // pair_base)
            if image_id1 not in wanted_ids or image_id2 not in wanted_ids:
                continue
            tested += 1
            try:
                label = pycolmap.TwoViewGeometryConfiguration(int(config)).name
            except ValueError:
                label = f"UNKNOWN_{config}"
            counts[label] = counts.get(label, 0) + 1
            if int(config) in {
                pycolmap.TwoViewGeometryConfiguration.CALIBRATED.value,
                pycolmap.TwoViewGeometryConfiguration.UNCALIBRATED.value,
            }:
                accepted += 1
        return {
            "tested_registered_pairs": tested,
            "nondegenerate_registered_pairs": accepted,
            "configuration_counts": dict(sorted(counts.items())),
        }
    finally:
        connection.close()


def summarize_model(
    model_id: int,
    reconstruction: pycolmap.Reconstruction,
    hashes: dict[str, str],
    database: Path,
) -> dict:
    points = list(reconstruction.points3D.values())
    errors = [float(point.error) for point in points if math.isfinite(float(point.error))]
    track_lengths = [len(point.track.elements) for point in points]
    names = image_names(reconstruction)
    eras = sorted({name.split("__", 1)[0] for name in names if "__" in name})
    summary = {
        "model_id": int(model_id),
        "registered_images": len(reconstruction.images),
        "registered_unique_views": count_unique_views(names, hashes),
        "sparse_points": len(points),
        "observations": int(sum(track_lengths)),
        "median_reprojection_error_px": round(statistics.median(errors), 4) if errors else None,
        "mean_reprojection_error_px": round(statistics.mean(errors), 4) if errors else None,
        "median_track_length": round(statistics.median(track_lengths), 3) if track_lengths else None,
        "mean_track_length": round(statistics.mean(track_lengths), 3) if track_lengths else None,
        "images": names,
        "eras": eras,
    }
    summary["registered_pair_geometry"] = registered_pair_geometry(database, names)
    return summary


def gate(summary: dict, mode: str, input_images: int) -> dict:
    pair_geometry = summary["registered_pair_geometry"]
    checks = {
        "registered_images": summary["registered_images"] >= QUALITY_GATES["min_registered_images"],
        "unique_views": summary["registered_unique_views"] >= QUALITY_GATES["min_unique_views"],
        "registration_ratio": summary["registered_images"] / max(input_images, 1)
        >= QUALITY_GATES["min_registration_ratio"],
        "sparse_points": summary["sparse_points"] >= QUALITY_GATES["min_sparse_points"],
        "reprojection_error": summary["median_reprojection_error_px"] is not None
        and summary["median_reprojection_error_px"] <= QUALITY_GATES["max_median_reprojection_error_px"],
        "track_length": summary["median_track_length"] is not None
        and summary["median_track_length"] >= QUALITY_GATES["min_median_track_length"],
        "nondegenerate_registered_pairs": pair_geometry["nondegenerate_registered_pairs"]
        >= QUALITY_GATES["min_nondegenerate_registered_pairs"],
    }
    if mode == "joint":
        names = summary["images"]
        historical = sum(name.startswith("historical__") for name in names)
        modern = sum(name.startswith("modern__") for name in names)
        minimum = QUALITY_GATES["min_cross_era_images_per_era"]
        checks["cross_era_registration"] = historical >= minimum and modern >= minimum
        summary["registered_by_era"] = {"historical": historical, "modern": modern}
    return {"passed": all(checks.values()), "checks": checks, "thresholds": QUALITY_GATES}


def export_model(reconstruction: pycolmap.Reconstruction, output: Path, label: str) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    model_directory = output / "model"
    model_directory.mkdir(exist_ok=True)
    reconstruction.write(str(model_directory))
    reconstruction.export_PLY(str(output / "sparse.ply"))
    points = []
    for point_id, point in reconstruction.points3D.items():
        xyz = [round(float(v), 6) for v in point.xyz]
        rgb = [int(v) for v in point.color]
        points.append({"id": int(point_id), "p": xyz, "c": rgb, "error": round(float(point.error), 4), "track": len(point.track.elements)})
    cameras = []
    for image_id, image in reconstruction.images.items():
        cameras.append({"id": int(image_id), "name": image.name, "center": camera_center(image)})
    viewer = {"label": label, "points": points, "cameras": cameras}
    (output / "viewer.json").write_text(json.dumps(viewer, separators=(",", ":")))
    return {"ply_sha256": digest(output / "sparse.ply"), "viewer_sha256": digest(output / "viewer.json")}


def database_stats(path: Path) -> dict:
    if not path.exists():
        return {}
    connection = sqlite3.connect(path)
    try:
        counts = {}
        for table in ["images", "keypoints", "descriptors", "matches", "two_view_geometries"]:
            counts[table] = int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        verified_rows = connection.execute(
            "SELECT pair_id, rows FROM two_view_geometries WHERE rows > 0 ORDER BY rows DESC"
        ).fetchall()
        counts["verified_pairs"] = len(verified_rows)
        counts["total_verified_inliers"] = int(
            connection.execute("SELECT COALESCE(SUM(rows), 0) FROM two_view_geometries").fetchone()[0]
        )
        names = {int(image_id): name for image_id, name in connection.execute("SELECT image_id, name FROM images")}
        pair_base = 2147483647
        pairs = []
        graph = {image_id: set() for image_id in names}
        for pair_id, inliers in verified_rows:
            image_id2 = int(pair_id % pair_base)
            image_id1 = int((pair_id - image_id2) // pair_base)
            graph.setdefault(image_id1, set()).add(image_id2)
            graph.setdefault(image_id2, set()).add(image_id1)
            if len(pairs) < 50:
                pairs.append(
                    {"image_a": names.get(image_id1, str(image_id1)), "image_b": names.get(image_id2, str(image_id2)), "inliers": int(inliers)}
                )
        counts["top_verified_pairs"] = pairs
        components = []
        unseen = set(graph)
        while unseen:
            seed = unseen.pop()
            stack = [seed]
            component = [seed]
            while stack:
                for neighbor in graph.get(stack.pop(), set()):
                    if neighbor in unseen:
                        unseen.remove(neighbor)
                        stack.append(neighbor)
                        component.append(neighbor)
            components.append(sorted(names.get(image_id, str(image_id)) for image_id in component))
        components.sort(key=len, reverse=True)
        counts["match_graph_component_sizes"] = [len(component) for component in components]
        return counts
    finally:
        connection.close()


def mark_default_focal_priors(path: Path) -> None:
    """Mark COLMAP's automatic focal estimate as an optimizable prior.

    Archival scans have no EXIF focal length. COLMAP already initializes these
    cameras to 1.2 times the maximum image dimension; setting the prior flag
    lets two-view verification use calibrated essential geometry. Bundle
    adjustment still refines the focal length later.
    """
    connection = sqlite3.connect(path)
    try:
        connection.execute("UPDATE cameras SET prior_focal_length = 1")
        connection.commit()
    finally:
        connection.close()


def prepare_images(raw_root: Path, work_images: Path, mode: str, manifest: dict) -> list[str]:
    work_images.mkdir(parents=True, exist_ok=True)
    names: list[str] = []
    source_sets = [mode] if mode != "joint" else ["historical", "modern"]
    for set_name in source_sets:
        for item in manifest["sets"][set_name]["images"]:
            source = raw_root / set_name / item["filename"]
            prefix = f"{set_name}__" if mode == "joint" else ""
            target_name = prefix + item["filename"]
            target = work_images / target_name
            if not target.exists():
                try:
                    os.link(source, target)
                except OSError:
                    shutil.copy2(source, target)
            names.append(target_name)
    return sorted(names)


def mode_hashes(mode: str, manifest: dict) -> dict[str, str]:
    result = {}
    source_sets = [mode] if mode != "joint" else ["historical", "modern"]
    for set_name in source_sets:
        for item in manifest["sets"][set_name]["images"]:
            prefix = f"{set_name}__" if mode == "joint" else ""
            result[prefix + item["filename"]] = item.get("dhash64", "")
    return result


def mode_input_signature(mode: str, manifest: dict) -> str:
    source_sets = [mode] if mode != "joint" else ["historical", "modern"]
    rows = []
    for set_name in source_sets:
        rows.extend(
            f"{set_name}/{item['filename']}:{item['sha256']}"
            for item in manifest["sets"][set_name]["images"]
        )
    rows.append(json.dumps(SFM_CONFIG, sort_keys=True))
    return hashlib.sha256("\n".join(sorted(rows)).encode()).hexdigest()


def run_reconstruction(mode: str, raw_root: Path, work_root: Path, export_root: Path, manifest: dict, force: bool) -> dict:
    start = time.time()
    workspace = work_root / mode
    signature = mode_input_signature(mode, manifest)
    signature_path = workspace / ".input_signature"
    previous_signature = signature_path.read_text().strip() if signature_path.exists() else None
    if (force or (previous_signature is not None and previous_signature != signature)) and workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    signature_path.write_text(signature + "\n")
    images = workspace / "images"
    names = prepare_images(raw_root, images, mode, manifest)
    database = workspace / "database.db"
    sparse = workspace / "sparse"
    if sparse.exists():
        shutil.rmtree(sparse)
    sparse.mkdir(exist_ok=True)
    public_mode = export_root / mode
    if public_mode.exists():
        shutil.rmtree(public_mode)

    if len(names) < 2:
        return {
            "mode": mode,
            "input_signature": signature,
            "input_images": len(names),
            "database": {},
            "models_found": 0,
            "models": [],
            "selected_model": None,
            "quality": {"passed": False, "checks": {"minimum_inputs": False}, "thresholds": QUALITY_GATES},
            "runtime_seconds": round(time.time() - start, 2),
        }

    if not database.exists():
        extraction = pycolmap.FeatureExtractionOptions()
        extraction.max_image_size = SFM_CONFIG["max_image_size_px"]
        extraction.num_threads = min(SFM_CONFIG["feature_threads"], os.cpu_count() or 1)
        extraction.sift.max_num_features = SFM_CONFIG["max_sift_features"]
        extraction.sift.estimate_affine_shape = SFM_CONFIG["estimate_affine_shape"]
        extraction.sift.domain_size_pooling = SFM_CONFIG["domain_size_pooling"]
        extraction.sift.peak_threshold = SFM_CONFIG["sift_peak_threshold"]
        pycolmap.extract_features(
            database_path=str(database),
            image_path=str(images),
            camera_mode=pycolmap.CameraMode.AUTO,
            camera_model=SFM_CONFIG["camera_model"],
            extraction_options=extraction,
            device=pycolmap.Device.cpu,
        )
        if SFM_CONFIG["assume_default_focal_prior"]:
            mark_default_focal_priors(database)
        matching = pycolmap.FeatureMatchingOptions()
        matching.num_threads = min(SFM_CONFIG["matching_threads"], os.cpu_count() or 1)
        matching.guided_matching = SFM_CONFIG["guided_matching"]
        matching.sift.max_ratio = SFM_CONFIG["sift_max_ratio"]
        matching.sift.cross_check = SFM_CONFIG["sift_cross_check"]
        pairing = pycolmap.ExhaustivePairingOptions()
        pairing.block_size = SFM_CONFIG["exhaustive_block_size"]
        verification = pycolmap.TwoViewGeometryOptions()
        verification.ransac.max_error = 4.0
        verification.ransac.min_inlier_ratio = 0.05
        verification.multiple_models = True
        pycolmap.match_exhaustive(
            database_path=str(database),
            matching_options=matching,
            pairing_options=pairing,
            verification_options=verification,
            device=pycolmap.Device.cpu,
        )

    options = pycolmap.IncrementalPipelineOptions()
    options.multiple_models = True
    options.max_num_models = 20
    options.min_model_size = 2
    options.min_num_matches = 12
    options.random_seed = SFM_CONFIG["random_seed"]
    options.mapper.init_min_num_inliers = 40
    options.mapper.init_min_tri_angle = 4.0
    options.mapper.abs_pose_min_num_inliers = 20
    options.mapper.abs_pose_min_inlier_ratio = 0.15
    options.mapper.max_reg_trials = 5
    options.mapper.filter_max_reproj_error = 4.0
    options.triangulation.min_angle = 1.0
    options.max_runtime_seconds = 1200
    reconstructions = pycolmap.incremental_mapping(
        database_path=str(database), image_path=str(images), output_path=str(sparse), options=options
    )

    hashes = mode_hashes(mode, manifest)
    summaries = [summarize_model(model_id, rec, hashes, database) for model_id, rec in reconstructions.items()]
    summaries.sort(
        key=lambda item: (item["registered_unique_views"], item["registered_images"], item["sparse_points"]),
        reverse=True,
    )
    chosen = None
    if mode == "joint":
        mixed = [item for item in summaries if "historical" in item["eras"] and "modern" in item["eras"]]
        chosen = mixed[0] if mixed else (summaries[0] if summaries else None)
    elif summaries:
        chosen = summaries[0]

    result = {
        "mode": mode,
        "input_signature": signature,
        "input_images": len(names),
        "database": database_stats(database),
        "models_found": len(summaries),
        "models": summaries,
        "selected_model": chosen,
        "quality": {"passed": False, "checks": {}, "thresholds": QUALITY_GATES},
        "runtime_seconds": round(time.time() - start, 2),
    }
    if chosen is not None:
        result["quality"] = gate(chosen, mode, len(names))
        rec = reconstructions[chosen["model_id"]]
        result["artifacts"] = export_model(rec, public_mode, mode)
    return result


def main() -> None:
    global SFM_CONFIG
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, default=Path("data/raw"))
    parser.add_argument("--work", type=Path, default=Path("artifacts/work"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/public"))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--preset", choices=sorted(SFM_PRESETS), default="baseline")
    parser.add_argument("--modes", nargs="+", choices=["historical", "modern", "joint"], default=["historical", "modern", "joint"])
    args = parser.parse_args()
    SFM_CONFIG = dict(SFM_PRESETS[args.preset])
    manifest_path = args.raw / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    args.output.mkdir(parents=True, exist_ok=True)
    report = {
        "schema_version": 1,
        "project": "GhostMap v1",
        "claim_policy": "Only COLMAP-derived geometry is published; failed gates remain visibly failed.",
        "software": {
            "pycolmap": pycolmap.__version__,
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "numpy": np.__version__,
        },
        "input_manifest_sha256": digest(manifest_path),
        "quality_gates": QUALITY_GATES,
        "sfm_preset": args.preset,
        "sfm_config": SFM_CONFIG,
        "runs": {},
    }
    for mode in args.modes:
        print(f"\n=== {mode} ===", flush=True)
        report["runs"][mode] = run_reconstruction(mode, args.raw, args.work, args.output, manifest, args.force)
        chosen = report["runs"][mode]["selected_model"] or {}
        print(
            f"{mode}: images={chosen.get('registered_images', 0)} points={chosen.get('sparse_points', 0)} "
            f"pass={report['runs'][mode]['quality']['passed']}",
            flush=True,
        )
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    shutil.copy2(manifest_path, args.output / "manifest.json")
    print(f"wrote {args.output / 'report.json'}")


if __name__ == "__main__":
    main()

