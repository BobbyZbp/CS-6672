#!/usr/bin/env python3
"""Run an auditable COLMAP dense-MVS capability check on a sparse model.

This command never substitutes synthetic geometry when PatchMatch Stereo is
unavailable.  It writes a machine-readable report and exits non-zero.
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pycolmap


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report_path = args.workspace / "dense_mvs_report.json"
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "engine": f"pycolmap {pycolmap.__version__}",
        "cuda_available": bool(pycolmap.has_cuda),
        "model": str(args.model),
        "images": str(args.images),
        "status": "not_started",
        "error": None,
    }

    if args.workspace.exists():
        shutil.rmtree(args.workspace)
    args.workspace.mkdir(parents=True)

    reconstruction = pycolmap.Reconstruction(str(args.model))
    report["registered_images"] = reconstruction.num_reg_images()
    report["sparse_points"] = reconstruction.num_points3D()

    try:
        pycolmap.undistort_images(
            output_path=str(args.workspace),
            input_path=str(args.model),
            image_path=str(args.images),
            image_names=[image.name for image in reconstruction.images.values()],
        )
        report["status"] = "undistorted"
        pycolmap.patch_match_stereo(str(args.workspace))
        report["status"] = "patch_match_complete"
    except Exception as exc:  # pycolmap exposes multiple C++ exception types
        report["status"] = "blocked"
        report["error"] = f"{type(exc).__name__}: {exc}"
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 2

    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
