#!/usr/bin/env python3
"""Run the learned hloc baseline only on historical-to-modern pairs.

Global NetVLAD retrieval selects candidate bridge pairs. SuperPoint and
LightGlue provide local correspondences, which are then geometrically verified
and reconstructed by COLMAP through pycolmap. No handcrafted pair is admitted.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import h5py
import pycolmap
import torch
from hloc import extract_features, match_features, pairs_from_retrieval, reconstruction


PAIR_BASE = 2147483647


def pair_rows(path: Path) -> list[tuple[str, str]]:
    return [tuple(line.split(" ", 1)) for line in path.read_text().splitlines() if line.strip()]


def match_counts(path: Path) -> dict[str, int | float]:
    counts = []
    with h5py.File(path, "r") as handle:
        def collect(_name: str, item) -> None:
            if isinstance(item, h5py.Group) and "matches0" in item:
                matches = item["matches0"][:]
                counts.append(int((matches >= 0).sum()))

        handle.visititems(collect)
    counts.sort()
    return {
        "pairs": len(counts),
        "pairs_with_matches": sum(value > 0 for value in counts),
        "median_matches": counts[len(counts) // 2] if counts else 0,
        "max_matches": max(counts, default=0),
    }


def verified_cross_era(database: Path) -> dict:
    connection = sqlite3.connect(database)
    try:
        names = {int(image_id): name for image_id, name in connection.execute("SELECT image_id, name FROM images")}
        pairs = []
        configs: dict[str, int] = {}
        for pair_id, rows, config in connection.execute(
            "SELECT pair_id, rows, config FROM two_view_geometries WHERE rows > 0 ORDER BY rows DESC"
        ):
            image_id2 = int(pair_id % PAIR_BASE)
            image_id1 = int((pair_id - image_id2) // PAIR_BASE)
            name_a, name_b = names[image_id1], names[image_id2]
            if name_a.split("__", 1)[0] == name_b.split("__", 1)[0]:
                continue
            try:
                label = pycolmap.TwoViewGeometryConfiguration(int(config)).name
            except ValueError:
                label = f"UNKNOWN_{config}"
            configs[label] = configs.get(label, 0) + 1
            pairs.append({"image_a": name_a, "image_b": name_b, "inliers": int(rows), "configuration": label})
        nondegenerate = sum(
            pair["configuration"] in {"CALIBRATED", "UNCALIBRATED"} for pair in pairs
        )
        return {
            "verified_pairs": len(pairs),
            "nondegenerate_pairs": nondegenerate,
            "configuration_counts": dict(sorted(configs.items())),
            "pairs": pairs,
        }
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", type=Path, default=Path("artifacts/work/joint/images"))
    parser.add_argument("--workspace", type=Path, default=Path("artifacts/hloc_cross_era"))
    parser.add_argument("--retrieval-neighbors", type=int, default=10)
    args = parser.parse_args()
    args.workspace.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(min(4, torch.get_num_threads()))

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "pipeline": "NetVLAD retrieval -> SuperPoint -> LightGlue -> COLMAP geometric verification/SfM",
        "device": "cuda" if torch.cuda.is_available() else "cpu",
        "retrieval_neighbors_per_historical_image": args.retrieval_neighbors,
        "status": "running",
    }
    report_path = args.workspace / "report.json"
    try:
        global_features = extract_features.main(
            extract_features.confs["netvlad"], args.images, args.workspace, as_half=False
        )
        pairs_path = args.workspace / "pairs-netvlad-cross-era.txt"
        pairs_from_retrieval.main(
            global_features,
            pairs_path,
            args.retrieval_neighbors,
            query_prefix="historical__",
            db_prefix="modern__",
        )
        report["retrieved_pairs"] = len(pair_rows(pairs_path))

        local_features = extract_features.main(
            extract_features.confs["superpoint_aachen"], args.images, args.workspace, as_half=False
        )
        matches_path = args.workspace / "matches-superpoint-lightglue-cross-era.h5"
        match_features.main(
            match_features.confs["superpoint+lightglue"],
            pairs_path,
            local_features,
            matches=matches_path,
        )
        report["learned_matches"] = match_counts(matches_path)

        sfm_path = args.workspace / "sfm"
        recovered = reconstruction.main(
            sfm_path,
            args.images,
            pairs_path,
            local_features,
            matches_path,
            camera_mode=pycolmap.CameraMode.AUTO,
            verbose=False,
        )
        report["geometric_verification"] = verified_cross_era(sfm_path / "database.db")
        if recovered is None:
            report["reconstruction"] = {"registered_images": 0, "points3D": 0, "registered_by_era": {"historical": 0, "modern": 0}}
        else:
            names = [image.name for image in recovered.images.values()]
            report["reconstruction"] = {
                "registered_images": recovered.num_reg_images(),
                "points3D": recovered.num_points3D(),
                "registered_by_era": {
                    "historical": sum(name.startswith("historical__") for name in names),
                    "modern": sum(name.startswith("modern__") for name in names),
                },
                "images": sorted(names),
            }
        geometry = report["geometric_verification"]
        registered = report["reconstruction"]["registered_by_era"]
        report["passed"] = bool(
            geometry["nondegenerate_pairs"] >= 3
            and registered["historical"] >= 3
            and registered["modern"] >= 3
        )
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
