#!/usr/bin/env python3
"""Frozen-snapshot CPU SIFT/COLMAP baseline, retaining every native component.

Pinned initial settings: 1200px SIFT, requested 4096-feature cap, exhaustive
pairs, four CPU threads, independent SIMPLE_RADIAL cameras, no held-out views.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from ghostmap.sfm.learned import (ROOT, component_report, select_training_images,
                              sha256, stage_images, verified_graph, write_json, saved_component_reports)

VERSION = 1
RESIZE = 1200
KEYPOINTS = 4096
THREADS = 4


def baseline_configuration(snapshot_sha256, targets=(), label="default", pycolmap_version="unknown"):
    return {"pipeline_version": VERSION, "method": "SIFT-COLMAP-CPU", "snapshot_sha256": snapshot_sha256,
            "resize": RESIZE, "keypoints": KEYPOINTS, "targets": sorted(set(targets)), "run_label": label,
            "camera_model": "SIMPLE_RADIAL", "camera_mode": "PER_IMAGE", "default_focal_length_factor": 1.2,
            "threads": THREADS, "use_gpu": False, "minimum_saved_component_cameras": 2,
            "pycolmap_version": pycolmap_version, "extractor": "SIFT", "matcher": "SIFT-ratio-mutual",
            "pairing": "exhaustive", "sift_normalization": "L1_ROOT", "ratio_threshold": .8,
            "descriptor_distance_threshold": .7, "cross_check": True, "guided_matching": False,
            "geometric_verification_max_error_px": 4., "random_seed": 0,
            "minimum_focal_length_ratio": .25, "maximum_focal_length_ratio": 4.0}


def configuration_id(configuration):
    return hashlib.sha256(json.dumps(configuration, sort_keys=True).encode()).hexdigest()[:20]


def native_options(pycolmap):
    """Installed pycolmap 3.13 option structure; no old sift_options argument."""
    extraction = pycolmap.FeatureExtractionOptions()
    extraction.max_image_size = RESIZE
    extraction.num_threads = THREADS
    extraction.use_gpu = False
    extraction.sift.max_num_features = KEYPOINTS
    extraction.sift.normalization = pycolmap.Normalization.L1_ROOT
    matching = pycolmap.FeatureMatchingOptions()
    matching.num_threads = THREADS
    matching.use_gpu = False
    matching.guided_matching = False
    matching.sift.max_ratio = .8
    matching.sift.max_distance = .7
    matching.sift.cross_check = True
    verification = pycolmap.TwoViewGeometryOptions()
    verification.ransac.max_error = 4.
    verification.ransac.random_seed = 0
    reader = pycolmap.ImageReaderOptions()
    reader.camera_model = "SIMPLE_RADIAL"
    reader.default_focal_length_factor = 1.2
    mapping = pycolmap.IncrementalPipelineOptions()
    mapping.num_threads = THREADS
    mapping.min_model_size = 2
    mapping.multiple_models = True
    mapping.ba_use_gpu = False
    mapping.min_focal_length_ratio = .25
    mapping.max_focal_length_ratio = 4.
    mapping.ba_refine_focal_length = True
    mapping.ba_refine_extra_params = True
    mapping.random_seed = 0
    return {"extraction": extraction, "matching": matching, "verification": verification,
            "reader": reader, "mapping": mapping, "pairing": pycolmap.ExhaustivePairingOptions(),
            "device": pycolmap.Device.cpu}


def database_feature_summary(database, expected_names):
    """Read-only check that COLMAP stored exactly the declared basenames."""
    with sqlite3.connect(Path(database).resolve().as_uri() + "?mode=ro", uri=True) as db:
        rows = list(db.execute("SELECT images.name,keypoints.rows FROM images LEFT JOIN keypoints ON images.image_id=keypoints.image_id ORDER BY images.name"))
    names = [name for name, _ in rows]
    if len(names) != len(set(names)) or set(names) != set(expected_names):
        raise ValueError("Native database contains undeclared, held-out or noncanonical image names")
    if any(count is None or count < 0 for _, count in rows):
        raise ValueError("Native feature extraction is incomplete")
    counts = [int(count) for _, count in rows]
    return {"image_count": len(rows), "keypoints_total": sum(counts), "keypoints_min": min(counts, default=0),
            "keypoints_max": max(counts, default=0), "by_image": {name: int(count) for name, count in rows},
            "note": "Requested SIFT cap is a detector option; actual counts are reported, not assumed identical to learned features."}


def run(snapshot_path, workspace=ROOT / "artifacts/artsquad_modern", targets=(), label="default"):
    import pycolmap

    snapshot_path = Path(snapshot_path).resolve()
    snapshot = json.loads(snapshot_path.read_text())
    records = select_training_images(snapshot, targets)
    if len(records) < 2:
        raise ValueError("At least two admitted training images are required")
    configuration = baseline_configuration(sha256(snapshot_path), targets, label, pycolmap.__version__)
    run_id = configuration_id(configuration)
    work = Path(workspace).resolve() / "runs" / run_id
    work.mkdir(parents=True, exist_ok=True)
    config_path, report_path = work / "configuration.json", work / "report.json"
    if config_path.exists() and json.loads(config_path.read_text()) != configuration:
        raise ValueError("Baseline configuration changed; refusing ambiguous cache reuse")
    write_json(config_path, configuration)
    stage_images(records, work / "images")
    if report_path.exists() and json.loads(report_path.read_text()).get("status") in {"sfm_complete", "no_model"}:
        return work
    names = [row["filename"] for row in records]
    report = {"schema_version": 1, "run_id": run_id, "snapshot_path": str(snapshot_path),
              "snapshot_id": snapshot["snapshot_id"], "configuration": configuration, "input_images": names,
              "held_out_images_used_in_mapping": 0, "status": "running", "stage": "features", "components": [],
              "created_utc": datetime.now(timezone.utc).isoformat(), "candidate_pairs": len(names) * (len(names) - 1) // 2,
              "limitations": ["CPU SIFT baseline; no target identity, independent exposure, held-out localization, surface or metric validation has passed.",
                              "Exhaustive SIFT uses a different pair budget from learned NetVLAD-neighbor matching; this initial pilot is not an equal-compute comparison.",
                              "All native components are retained in separate unverified similarity frames; no campus alignment is authored.",
                              "SIFT and learned features share the initial 1200px/4096 requested budgets, not necessarily identical achieved feature counts."]}
    started = time.monotonic()
    def save(stage):
        report.update(stage=stage, elapsed_seconds=round(time.monotonic() - started, 2))
        write_json(report_path, report)
    options = native_options(pycolmap)
    if hasattr(pycolmap, "set_random_seed"):
        pycolmap.set_random_seed(0)
    sfm = work / "sfm"
    sfm.mkdir(exist_ok=True)
    database, ready = sfm / "database.db", sfm / "database-ready.json"
    try:
        if ready.exists():
            frozen = json.loads(ready.read_text())
            if frozen.get("configuration") != configuration or frozen.get("database_sha256") != sha256(database):
                raise ValueError("Baseline database ready marker/hash mismatch; use a new run label")
        else:
            if database.exists():
                raise RuntimeError("Interrupted database preserved; use a new --run-label rather than overwrite it")
            save("features")
            pycolmap.extract_features(str(database), str(work / "images"), image_names=names,
                                      camera_mode=pycolmap.CameraMode.PER_IMAGE, camera_model="SIMPLE_RADIAL",
                                      reader_options=options["reader"], extraction_options=options["extraction"], device=options["device"])
            report["feature_summary"] = database_feature_summary(database, names)
            save("matching_and_geometric_verification")
            pycolmap.match_exhaustive(str(database), matching_options=options["matching"],
                                     pairing_options=options["pairing"], verification_options=options["verification"],
                                     device=options["device"])
            write_json(ready, {"configuration": configuration, "database_sha256": sha256(database)})
        report["feature_summary"] = database_feature_summary(database, names)
        graph = verified_graph(database, records)
        write_json(work / "view-graph.json", graph)
        report.update(verified_pairs=graph["verified_pairs"], nondegenerate_pairs=graph["nondegenerate_pairs"])
        save("mapping")
        model_root = sfm / "models"
        if model_root.exists() and any(model_root.iterdir()):
            raise RuntimeError("Interrupted native components preserved; use a new --run-label")
        model_root.mkdir(exist_ok=True)
        models = pycolmap.incremental_mapping(str(database), str(work / "images"), str(model_root), options=options["mapping"])
        write_json(sfm / "mapping-complete.json", {"component_ids": sorted(map(int, models)), "meaning": "Mapper returned; not milestone acceptance."})
        report['components'] = saved_component_reports(model_root, records)
        report['component_identity'] = 'Native saved directory ID, not API ReconstructionManager key'
        registered = {camera["name"] for entry in report["components"] for camera in entry["cameras"]}
        report["unregistered_images"] = sorted(set(names) - registered)
        report["status"] = "sfm_complete" if models else "no_model"
        report["mapping_database_sha256"] = sha256(database)
        save("finished")
    except Exception as error:
        report.update(status="error", error=type(error).__name__ + ": " + str(error))
        save(report["stage"])
        raise
    return work


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, default=ROOT / "artifacts/artsquad_modern")
    parser.add_argument("--targets", nargs="*", default=[])
    parser.add_argument("--run-label", default="default")
    args = parser.parse_args()
    print(run(args.snapshot, args.workspace, args.targets, args.run_label), flush=True)


if __name__ == "__main__":
    main()
