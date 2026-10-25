#!/usr/bin/env python3
"""Build a full learned-feature joint model with explicit target coverage.

This extends the cross-era bridge graph with within-era retrieval pairs. The
result can therefore contain historical-only tracks on vanished Boardman Hall,
while shared Uris/McGraw tracks place them in the modern coordinate frame.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import h5py
import pycolmap
import torch
from hloc import extract_features, match_features, pairs_from_retrieval, reconstruction

from run_hloc_cross_era import match_counts, pair_rows, verified_cross_era


ROOT = Path(__file__).resolve().parents[3]
IMAGES = ROOT / "artifacts" / "work" / "joint" / "images"
WORK = ROOT / "artifacts" / "hloc_cross_era"


def canonical_pair(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a < b else (b, a)


def target_coverage(model: pycolmap.Reconstruction) -> dict:
    images = {int(image_id): image.name for image_id, image in model.images.items()}
    boardman_ids = {image_id for image_id, name in images.items() if "boardman" in name.lower()}
    historical_ids = {image_id for image_id, name in images.items() if name.startswith("historical__")}
    modern_ids = {image_id for image_id, name in images.items() if name.startswith("modern__")}
    historical_only = 0
    cross_era = 0
    boardman_observed = 0
    boardman_multiview_historical_only = 0
    for point in model.points3D.values():
        track_ids = {int(element.image_id) for element in point.track.elements}
        has_historical = bool(track_ids & historical_ids)
        has_modern = bool(track_ids & modern_ids)
        boardman_views = len(track_ids & boardman_ids)
        historical_only += int(has_historical and not has_modern)
        cross_era += int(has_historical and has_modern)
        boardman_observed += int(boardman_views >= 1)
        boardman_multiview_historical_only += int(boardman_views >= 2 and not has_modern)
    observations = {
        name: int(model.images[image_id].num_points3D)
        for image_id, name in images.items()
        if image_id in boardman_ids
    }
    return {
        "historical_only_points": historical_only,
        "cross_era_points": cross_era,
        "points_observed_by_boardman_image": boardman_observed,
        "boardman_multiview_historical_only_points": boardman_multiview_historical_only,
        "registered_boardman_images": len(boardman_ids),
        "boardman_image_observations": dict(sorted(observations.items())),
    }


def main() -> int:
    torch.set_num_threads(min(4, torch.get_num_threads()))
    report_path = WORK / "joint_report.json"
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "pipeline": "NetVLAD joint retrieval -> SuperPoint -> LightGlue -> COLMAP joint SfM",
        "device": "cuda" if torch.cuda.is_available() else "cpu",
        "status": "running",
    }
    try:
        global_features = extract_features.main(
            extract_features.confs["netvlad"], IMAGES, WORK, as_half=False
        )
        local_features = extract_features.main(
            extract_features.confs["superpoint_aachen"], IMAGES, WORK, as_half=False
        )
        all_raw = WORK / "pairs-netvlad-all-raw.txt"
        pairs_from_retrieval.main(global_features, all_raw, 15)
        cross_path = WORK / "pairs-netvlad-cross-era.txt"
        pairs = {canonical_pair(*pair) for pair in pair_rows(all_raw)}
        pairs.update(canonical_pair(*pair) for pair in pair_rows(cross_path))
        joint_pairs = WORK / "pairs-netvlad-joint.txt"
        joint_pairs.write_text("\n".join(f"{a} {b}" for a, b in sorted(pairs)) + "\n")
        report["candidate_pairs"] = len(pairs)

        cross_matches = WORK / "matches-superpoint-lightglue-cross-era.h5"
        joint_matches = WORK / "matches-superpoint-lightglue-joint.h5"
        if cross_matches.exists() and not joint_matches.exists():
            shutil.copy2(cross_matches, joint_matches)
        match_features.main(
            match_features.confs["superpoint+lightglue"],
            joint_pairs,
            local_features,
            matches=joint_matches,
        )
        report["learned_matches"] = match_counts(joint_matches)

        sfm_path = WORK / "sfm_joint"
        model = reconstruction.main(
            sfm_path,
            IMAGES,
            joint_pairs,
            local_features,
            joint_matches,
            camera_mode=pycolmap.CameraMode.AUTO,
            verbose=False,
        )
        report["geometric_verification"] = verified_cross_era(sfm_path / "database.db")
        if model is None:
            report["reconstruction"] = {"registered_images": 0, "points3D": 0}
            report["target_coverage"] = target_coverage(pycolmap.Reconstruction())
        else:
            names = [image.name for image in model.images.values()]
            report["reconstruction"] = {
                "registered_images": model.num_reg_images(),
                "points3D": model.num_points3D(),
                "mean_reprojection_error_px": model.compute_mean_reprojection_error(),
                "registered_by_era": {
                    "historical": sum(name.startswith("historical__") for name in names),
                    "modern": sum(name.startswith("modern__") for name in names),
                },
                "images": sorted(names),
            }
            report["target_coverage"] = target_coverage(model)
            model.export_PLY(str(WORK / "joint_sparse.ply"))
        coverage = report["target_coverage"]
        report["passed"] = bool(
            report["geometric_verification"]["nondegenerate_pairs"] >= 3
            and coverage["registered_boardman_images"] >= 3
            and coverage["boardman_multiview_historical_only_points"] >= 1000
        )
        report["quality_gate"] = {
            "min_cross_era_nondegenerate_pairs": 3,
            "min_registered_boardman_images": 3,
            "min_boardman_multiview_historical_only_points": 1000,
            "dense_surface_required_for_demo": True,
        }
        report["status"] = "complete"
    except Exception as exc:
        report["status"] = "error"
        report["passed"] = False
        report["error"] = f"{type(exc).__name__}: {exc}"
        report_path.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        return 2
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
