#!/usr/bin/env python3
"""Fail closed if the public report and exported geometry disagree."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import pycolmap


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def learned_target_coverage(model: pycolmap.Reconstruction) -> dict[str, int]:
    names = {int(image_id): image.name for image_id, image in model.images.items()}
    boardman = {image_id for image_id, name in names.items() if "boardman" in name.lower()}
    historical = {image_id for image_id, name in names.items() if name.startswith("historical__")}
    modern = {image_id for image_id, name in names.items() if name.startswith("modern__")}
    counts = {
        "historical_only_points": 0,
        "cross_era_points": 0,
        "points_observed_by_boardman_image": 0,
        "boardman_multiview_historical_only_points": 0,
        "registered_boardman_images": len(boardman),
    }
    for point in model.points3D.values():
        track = {int(element.image_id) for element in point.track.elements}
        has_historical = bool(track & historical)
        has_modern = bool(track & modern)
        boardman_views = len(track & boardman)
        counts["historical_only_points"] += int(has_historical and not has_modern)
        counts["cross_era_points"] += int(has_historical and has_modern)
        counts["points_observed_by_boardman_image"] += int(boardman_views >= 1)
        counts["boardman_multiview_historical_only_points"] += int(boardman_views >= 2 and not has_modern)
    return counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, default=Path("data/raw"))
    parser.add_argument("--public", type=Path, default=Path("artifacts/public"))
    parser.add_argument("--learned", type=Path, default=Path("artifacts/hloc_cross_era"))
    parser.add_argument(
        "--dense-report",
        type=Path,
        default=Path("artifacts/experiments/dense_hloc_joint_cuda_check/dense_mvs_report.json"),
    )
    args = parser.parse_args()
    manifest_path = args.raw / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    report = json.loads((args.public / "report.json").read_text())
    assert report["input_manifest_sha256"] == sha256(manifest_path), "manifest digest mismatch"
    assert set(report["runs"]) == {"historical", "modern", "joint"}, "missing reconstruction mode"

    input_count = 0
    for set_name, dataset in manifest["sets"].items():
        assert dataset["accepted_count"] == len(dataset["images"])
        for item in dataset["images"]:
            path = args.raw / set_name / item["filename"]
            assert path.exists(), f"missing input: {path}"
            assert sha256(path) == item["sha256"], f"input digest mismatch: {path}"
            assert item["source_url"].startswith("https://commons.wikimedia.org/"), "untraceable input"
            assert item["license"] or item["usage_terms"], "missing license"
            assert len(item["dhash64"]) == 16 and int(item["dhash64"], 16) >= 0, "invalid perceptual hash"
            input_count += 1

    for mode, run in report["runs"].items():
        assert run["quality"]["passed"] == all(run["quality"]["checks"].values())
        selected = run["selected_model"]
        if selected is None:
            assert not run["quality"]["passed"]
            continue
        root = args.public / mode
        viewer_path = root / "viewer.json"
        ply_path = root / "sparse.ply"
        assert viewer_path.exists() and ply_path.exists(), f"missing public geometry: {mode}"
        assert sha256(viewer_path) == run["artifacts"]["viewer_sha256"]
        assert sha256(ply_path) == run["artifacts"]["ply_sha256"]
        viewer = json.loads(viewer_path.read_text())
        assert len(viewer["points"]) == selected["sparse_points"]
        assert len(viewer["cameras"]) == selected["registered_images"]
        for point in viewer["points"]:
            assert len(point["p"]) == 3 and all(math.isfinite(v) for v in point["p"])
            assert len(point["c"]) == 3 and all(0 <= v <= 255 for v in point["c"])
            assert point["track"] >= 2

    learned_validated = False
    joint_report_path = args.learned / "joint_report.json"
    if joint_report_path.exists():
        joint = json.loads(joint_report_path.read_text())
        model = pycolmap.Reconstruction(str(args.learned / "sfm_joint"))
        reconstruction = joint["reconstruction"]
        assert model.num_reg_images() == reconstruction["registered_images"]
        assert model.num_points3D() == reconstruction["points3D"]
        names = [image.name for image in model.images.values()]
        assert reconstruction["registered_by_era"] == {
            "historical": sum(name.startswith("historical__") for name in names),
            "modern": sum(name.startswith("modern__") for name in names),
        }
        observed = learned_target_coverage(model)
        for key, value in observed.items():
            assert joint["target_coverage"][key] == value, f"learned target mismatch: {key}"
        gate = joint["quality_gate"]
        expected_pass = bool(
            joint["geometric_verification"]["nondegenerate_pairs"]
            >= gate["min_cross_era_nondegenerate_pairs"]
            and observed["registered_boardman_images"] >= gate["min_registered_boardman_images"]
            and observed["boardman_multiview_historical_only_points"]
            >= gate["min_boardman_multiview_historical_only_points"]
        )
        assert joint["passed"] == expected_pass
        viewer = json.loads((args.learned / "joint_viewer.json").read_text())
        assert len(viewer["points"]) == model.num_points3D()
        assert len(viewer["cameras"]) == model.num_reg_images()
        assert (args.learned / "joint_sparse.ply").stat().st_size > 0
        if args.dense_report.exists():
            dense = json.loads(args.dense_report.read_text())
            assert dense["registered_images"] == model.num_reg_images()
            assert dense["sparse_points"] == model.num_points3D()
            assert dense["status"] in {"blocked", "patch_match_complete"}
        learned_validated = True
    suffix = " plus the learned joint model" if learned_validated else ""
    print(f"validated {input_count} inputs and {len(report['runs'])} classic reconstruction modes{suffix}")


if __name__ == "__main__":
    main()

