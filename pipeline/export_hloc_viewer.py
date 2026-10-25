#!/usr/bin/env python3
"""Export the learned-feature joint COLMAP model for the audit-only viewer."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pycolmap


ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "artifacts" / "hloc_cross_era" / "sfm_joint"
OUTPUT = ROOT / "artifacts" / "hloc_cross_era" / "joint_viewer.json"


def camera_center(image: pycolmap.Image) -> list[float]:
    try:
        return [round(float(value), 6) for value in image.projection_center()]
    except Exception:
        matrix = np.asarray(image.cam_from_world.matrix())
        center = -matrix[:, :3].T @ matrix[:, 3]
        return [round(float(value), 6) for value in center]


def main() -> None:
    reconstruction = pycolmap.Reconstruction(str(MODEL))
    points = [
        {
            "id": int(point_id),
            "p": [round(float(value), 6) for value in point.xyz],
            "c": [int(value) for value in point.color],
            "error": round(float(point.error), 4),
            "track": len(point.track.elements),
        }
        for point_id, point in reconstruction.points3D.items()
    ]
    cameras = [
        {"id": int(image_id), "name": image.name, "center": camera_center(image)}
        for image_id, image in reconstruction.images.items()
    ]
    OUTPUT.write_text(
        json.dumps({"label": "rejected hloc joint sparse diagnostic", "points": points, "cameras": cameras}, separators=(",", ":"))
        + "\n",
        encoding="utf-8",
    )
    print(f"exported {len(points)} points and {len(cameras)} cameras to {OUTPUT}")


if __name__ == "__main__":
    main()
