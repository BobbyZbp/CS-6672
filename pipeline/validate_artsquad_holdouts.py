#!/usr/bin/env python3
"""Query-only localization consistency against an immutable Arts Quad SfM map.

This never triangulates, bundle-adjusts or writes the reference map. A low PnP
residual on its estimated pose is NOT independent geometry or camera truth.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import time
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

from run_artsquad_sfm import select_training_images, sha256, stage_images, write_json

VERSION = 1


def select_holdout_images(snapshot, model_names):
    """Validate global split before selecting admitted query-only photographs."""
    training = select_training_images(snapshot)  # Global exposure/family check.
    train_by_name = {row["filename"]: row for row in training}
    names = list(model_names)
    if len(names) != len(set(names)) or any(name not in train_by_name for name in names):
        raise ValueError("Map cameras must be distinct admitted training images from the frozen snapshot")
    queries = [row for row in snapshot["images"] if row.get("split") == "test"
               and row.get("role") == "scene-candidate" and row.get("validation", {}).get("passed") is True]
    train_groups = {row["exposure_group_id"] for row in training}
    train_families = {row["source_family_id"] for row in training}
    for row in queries:
        for key in ("filename", "exposure_group_id", "source_family_id"):
            value = row.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ValueError("Held-out query is missing " + key)
        name = row["filename"]
        if Path(name).name != name or any(c.isspace() for c in name):
            raise ValueError("Query filenames must be whitespace-free basenames")
        if row["exposure_group_id"] in train_groups or row["source_family_id"] in train_families:
            raise ValueError("Held-out query leaks a global training exposure or source family")
    if len(queries) != len({row["filename"] for row in queries}):
        raise ValueError("Duplicate held-out query filename")
    return sorted(queries, key=lambda row: row["filename"])


def camera_prior(record, width, height, unknown_focal_factor=1.2):
    """Return an explicit, imperfect focal prior; no hidden sensor assumptions."""
    if not isinstance(width, int) or not isinstance(height, int) or min(width, height) <= 0:
        raise ValueError("Positive decoded image dimensions are required")
    if not math.isfinite(unknown_focal_factor) or unknown_focal_factor <= 0:
        raise ValueError("Unknown focal factor must be finite and positive")
    raw = (record.get("exif") or {}).get("focal_length_35mm")
    try:
        f35 = float(Fraction(str(raw)))
    except (TypeError, ValueError, ZeroDivisionError, OverflowError):
        f35 = 0.0
    if math.isfinite(f35) and 0 < f35 <= 2000:
        # The 35 mm equivalent convention is diagonal field of view, not an
        # assumption that every Internet camera has a 36 mm-wide sensor.
        focal = f35 * math.hypot(width, height) / math.hypot(36, 24)
        source = "source-EXIF-35mm-equivalent-diagonal"
        unknown = False
    else:
        focal = unknown_focal_factor * max(width, height)
        source = "explicit-unknown-focal-factor"
        unknown = True
    return {"model": "SIMPLE_RADIAL", "width": width, "height": height,
            "params": [focal, width / 2, height / 2, 0.0], "source": source,
            "unknown_focal": unknown, "source_focal_length_35mm": raw,
            "unknown_focal_factor": unknown_focal_factor if unknown else None,
            "assumptions": ["Centered principal point; initially zero radial distortion.",
                            "EXIF equivalence and image crop may be imperfect; this is a prior, not calibrated ground truth.",
                            "Millimeter-only focal EXIF is not converted without verified sensor dimensions."]}


def validate_frozen_files(records):
    for row in records:
        path = Path(row["working_path"])
        if not path.is_file() or sha256(path) != row.get("sha256_working"):
            raise ValueError("Frozen input changed or missing: " + str(path))


def immutable_hashes(paths):
    return {str(Path(path).resolve()): sha256(path) for path in paths}


def assert_unchanged(before):
    for name, digest in before.items():
        path = Path(name)
        if not path.is_file() or sha256(path) != digest:
            raise RuntimeError("Reference artifact mutated during holdout localization: " + name)


def validate_feature_names(path, allowed_names):
    """Reference/query HDF5 files must not contain undeclared image groups."""
    import h5py
    names = set()
    with h5py.File(path, "r") as source:
        def visit(_, obj):
            if isinstance(obj, h5py.Dataset):
                names.add(obj.parent.name.strip("/"))
        source.visititems(visit)
    if not names or not names <= set(allowed_names):
        raise ValueError("Feature file is empty or contains undeclared image names: " + str(path))
    return names


def summarize_residuals(values):
    """Finite statistics only; an empty/failed query cannot report zero error."""
    import numpy as np
    values = np.asarray(values, dtype=float)
    finite = values[np.isfinite(values)]
    if not len(finite):
        return {"finite_count": 0, "median_px": None, "p95_px": None, "rms_px": None}
    return {"finite_count": len(finite), "median_px": float(np.median(finite)),
            "p95_px": float(np.percentile(finite, 95)), "rms_px": float(np.sqrt(np.mean(finite ** 2)))}


def run(run_path, component, neighbors=10, unknown_focal_factor=1.2, ransac_thresh=8.0, min_inliers=12, max_queries=0):
    import hashlib
    import numpy as np
    import pycolmap
    import torch
    from PIL import Image
    from hloc import extract_features, match_features, pairs_from_retrieval
    from hloc.localize_sfm import QueryLocalizer, pose_from_cluster
    from hloc.utils.parsers import parse_retrieval

    if not isinstance(component, str) or not component or Path(component).name != component or component in {".", ".."}:
        raise ValueError("Component must be one local component ID")
    if (neighbors < 1 or min_inliers < 4 or max_queries < 0 or not math.isfinite(ransac_thresh) or ransac_thresh <= 0
            or not math.isfinite(unknown_focal_factor) or unknown_focal_factor <= 0):
        raise ValueError("Invalid retrieval/PnP budget")
    run_path = Path(run_path).resolve()
    reference_report = json.loads((run_path / "report.json").read_text())
    if reference_report.get("status") != "sfm_complete":
        raise ValueError("Reference SfM run must be complete before localization")
    if component not in {str(item["id"]) for item in reference_report.get("components", [])}:
        raise ValueError("Component was not declared by the completed SfM report")
    reference_config = reference_report["configuration"]
    if reference_config.get('extractor') == 'SIFT':
        raise ValueError('This query-only validator uses SuperPoint/LightGlue; SIFT localization needs its own compatible query descriptor path')
    snapshot_path = Path(reference_report["snapshot_path"])
    if sha256(snapshot_path) != reference_config["snapshot_sha256"]:
        raise ValueError("Frozen snapshot hash differs from the mapping run")
    snapshot = json.loads(snapshot_path.read_text())
    if snapshot["snapshot_id"] != reference_report["snapshot_id"]:
        raise ValueError("Snapshot IDs disagree")
    model_path = run_path / "sfm/models" / component
    model = pycolmap.Reconstruction(str(model_path))
    model_names = sorted(image.name for image in model.images.values() if image.has_pose)
    if not model_names:
        raise ValueError("Selected component has no registered training cameras")
    queries = select_holdout_images(snapshot, model_names)
    if max_queries:
        queries = queries[:max_queries]
    records = {row["filename"]: row for row in snapshot["images"]}
    map_records = [records[name] for name in model_names]
    validate_frozen_files(map_records + queries)
    database = run_path / "sfm/database.db"
    reference_local = run_path / f"feats-superpoint-n{reference_config['keypoints']}-r{reference_config['resize']}.h5"
    reference_global = run_path / "global-feats-netvlad.h5"
    all_training_names = [row["filename"] for row in select_training_images(snapshot)]
    for features_path in (reference_local, reference_global):
        if not set(model_names) <= validate_feature_names(features_path, all_training_names):
            raise ValueError("Reference features are missing registered training cameras")
    immutable_files = [database, reference_local, reference_global] + [path for path in model_path.iterdir() if path.suffix in {".bin", ".txt"}]
    before = immutable_hashes(immutable_files)
    configuration = {"version": VERSION, "reference_run_id": reference_report["run_id"], "component_id": component,
                     "snapshot_sha256": sha256(snapshot_path), "immutable_reference_sha256": before,
                     "query_names": [row["filename"] for row in queries], "neighbors": neighbors,
                     "unknown_focal_factor": unknown_focal_factor, "ransac_threshold_px": ransac_thresh,
                     "minimum_inliers_for_consistency_candidate": min_inliers, "max_queries": max_queries,
                     "pycolmap_version": pycolmap.__version__, "torch_version": torch.__version__}
    config_hash = hashlib.sha256(json.dumps(configuration, sort_keys=True).encode()).hexdigest()[:20]
    work = run_path / "holdouts" / (component + "-" + config_hash)
    work.mkdir(parents=True, exist_ok=True)
    if (work / "configuration.json").exists() and json.loads((work / "configuration.json").read_text()) != configuration:
        raise ValueError("Holdout cache configuration changed")
    write_json(work / "configuration.json", configuration)
    report_path = work / "report.json"
    if report_path.exists() and json.loads(report_path.read_text()).get("status") in {"consistency_complete", "no_queries"}:
        assert_unchanged(before)
        return work
    report = {"schema_version": 1, "status": "running", "stage": "preflight", "configuration": configuration,
              "created_utc": datetime.now(timezone.utc).isoformat(), "queries": [], "query_count": len(queries),
              "query_images_used_in_mapping": 0, "query_images_used_in_mvs_or_texture": 0,
              "geometry_accuracy_validated": False, "camera_accuracy_validated": False, "milestone_pass_authorized": False,
              "limitations": ["PnP residuals evaluate consistency on an estimated query pose, not independent geometric or camera accuracy.",
                              "Query focal length may be estimated/refined; low residual alone cannot validate shape or unknown intrinsics.",
                              "Snapshot group splitting is conservative but does not certify all perceptual copies are distinct exposures.",
                              "No query features, matches or poses are imported into the mapping database, triangulation, MVS or texture selection."]}
    started = time.monotonic()
    def save(stage):
        report.update(stage=stage, elapsed_seconds=round(time.monotonic() - started, 2))
        write_json(report_path, report)
    torch.set_num_threads(4)
    os.environ.setdefault("OMP_NUM_THREADS", "4")
    try:
        if not queries:
            report["status"] = "no_queries"
            return work
        save("query_features")
        stage_images(queries, work / "images")
        query_names = [row["filename"] for row in queries]
        global_features = extract_features.main(extract_features.confs["netvlad"], work / "images", work,
                                                image_list=query_names, as_half=False)
        local_conf = {"output": "query-superpoint", "model": {"name": "superpoint", "nms_radius": 3,
                      "max_keypoints": reference_config["keypoints"]},
                      "preprocessing": {"grayscale": True, "resize_max": reference_config["resize"]}}
        local_features = extract_features.main(local_conf, work / "images", work, image_list=query_names, as_half=False)
        validate_feature_names(global_features, query_names)
        validate_feature_names(local_features, query_names)
        pairs = work / "query-to-train-pairs.txt"
        pairs_from_retrieval.main(global_features, pairs, min(neighbors, len(model_names)),
                                 query_list=query_names, db_list=model_names, db_descriptors=reference_global)
        retrieval = parse_retrieval(pairs)
        if any(query not in query_names or any(name not in model_names for name in refs) for query, refs in retrieval.items()):
            raise ValueError("Retrieval contains undeclared query/reference names")
        matches = work / "query-to-train-matches.h5"
        save("query_matching")
        match_features.main(match_features.confs["superpoint+lightglue"], pairs, local_features,
                            matches=matches, features_ref=reference_local)
        name_to_id = {image.name: iid for iid, image in model.images.items() if image.has_pose}
        save("query_localization")
        for record in queries:
            name = record["filename"]
            db_names = retrieval.get(name, [])
            with Image.open(record["working_path"]) as image:
                width, height = image.size
            prior = camera_prior(record, width, height, unknown_focal_factor)
            camera = pycolmap.Camera(model=prior["model"], width=width, height=height, params=prior["params"])
            options = {"estimation": {"estimate_focal_length": prior["unknown_focal"],
                       "ransac": {"max_error": ransac_thresh, "random_seed": 0}},
                       "refinement": {"refine_focal_length": True, "refine_extra_params": False}}
            entry = {"name": name, "exposure_group_id": record["exposure_group_id"],
                     "source_family_id": record["source_family_id"], "metadata_targets": record.get("discovery", {}).get("targets", []),
                     "source_url": record.get("source_url"), "camera_prior": prior, "pose_options": options,
                     "retrieved_training_images": db_names, "status": "not_localized", "independent_ground_truth": False}
            if not db_names:
                entry["reason"] = "No training reference retrieved. No nearest-camera pose substitution is made."
                report["queries"].append(entry)
                continue
            localizer = QueryLocalizer(model, options)
            pose, log = pose_from_cluster(localizer, name, camera, [name_to_id[n] for n in db_names], local_features, matches)
            entry.update(raw_matches_to_triangulated_points=int(log["num_matches"]),
                         candidate_2d_3d_correspondences=len(log["points3D_ids"]),
                         unique_query_keypoints=len(set(log["keypoint_index_to_db"][0])))
            if pose is None:
                entry["reason"] = "PnP returned no pose. No nearest-camera pose substitution is made."
            else:
                xyz = np.asarray([model.points3D[point_id].xyz for point_id in log["points3D_ids"]])
                camera_xyz = pose["cam_from_world"] * xyz
                projected = camera.img_from_cam(camera_xyz)
                residuals = np.linalg.norm(projected - log["keypoints_query"], axis=1)
                residuals[camera_xyz[:, 2] <= 0] = np.nan
                mask = np.asarray(pose["inlier_mask"], dtype=bool)
                count = int(pose["num_inliers"])
                unique_inliers = len(set(np.asarray(log["keypoint_index_to_db"][0])[mask].tolist()))
                entry.update(status="consistency_candidate" if count >= min_inliers and unique_inliers >= min_inliers else "insufficient_inliers",
                             num_inliers=count, unique_inlier_query_keypoints=unique_inliers,
                             inlier_fraction=float(mask.mean()) if len(mask) else 0.,
                             positive_depth_correspondences=int((camera_xyz[:, 2] > 0).sum()),
                             all_reprojection=summarize_residuals(residuals), inlier_reprojection=summarize_residuals(residuals[mask]),
                             refined_camera={"model": camera.model.name, "width": camera.width, "height": camera.height, "params": camera.params.tolist()},
                             cam_from_world={"rotation_xyzw": pose["cam_from_world"].rotation.quat.tolist(), "translation": pose["cam_from_world"].translation.tolist()})
                correspondences = {"query_keypoints_colmap_pixels": log["keypoints_query"].tolist(),
                                   "point3D_ids": [int(i) for i in log["points3D_ids"]], "inlier_mask": mask.tolist(),
                                   "residual_px": [float(value) if np.isfinite(value) else None for value in residuals]}
                name_hash = hashlib.sha256(name.encode()).hexdigest()[:16]
                artifact = work / ("correspondences-" + name_hash + ".json")
                write_json(artifact, correspondences)
                entry["correspondences_artifact"] = artifact.name
            report["queries"].append(entry)
            save("query_localization")
        report["status"] = "consistency_complete"
        report["localized_consistency_candidates"] = sum(row["status"] == "consistency_candidate" for row in report["queries"])
        report["query_count"] = len(queries)
    except Exception as error:
        report.update(status="error", error=type(error).__name__ + ": " + str(error))
        raise
    finally:
        try:
            assert_unchanged(before)
            report["reference_artifacts_unchanged"] = True
            report["mapping_database_sha256_before"] = before[str(database.resolve())]
            report["mapping_database_sha256_after"] = sha256(database)
        except Exception as error:
            report.update(status="error", reference_artifacts_unchanged=False,
                          integrity_error=type(error).__name__ + ": " + str(error))
            save("integrity_failed")
            raise
        save("finished" if report["status"] in {"consistency_complete", "no_queries"} else report["stage"])
    return work


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True, help="Completed snapshot-bound SfM run directory")
    parser.add_argument("--component", required=True, help="Native component ID, e.g. 0")
    parser.add_argument("--neighbors", type=int, default=10)
    parser.add_argument("--unknown-focal-factor", type=float, default=1.2)
    parser.add_argument("--ransac-thresh", type=float, default=8.)
    parser.add_argument("--min-inliers", type=int, default=12)
    parser.add_argument("--max-queries", type=int, default=0, help="0 means all admitted queries; capped runs disclose the subset")
    args = parser.parse_args()
    print(run(args.run, args.component, args.neighbors, args.unknown_focal_factor,
              args.ransac_thresh, args.min_inliers, args.max_queries), flush=True)


if __name__ == "__main__":
    main()
