"""Evidence of absence: a 2.5-D upper bound on a vanished building from sky pixels.

A pixel that shows open sky proves that its whole ray, from the camera to
infinity, was empty when the photograph was taken. For a building that rises
from the ground as a column of solid matter, every sky ray that passes over a
ground position (x, y) at height z proves that the building there was lower
than z. Taking the lowest such height over all sky rays, all photographs and
their posterior pose samples gives a per-column height cap: an outer bound,
never a surface. Columns that no sky ray passes over stay unbounded.

Stand-in check: run on a building that still exists, the cap must never fall
below the lidar roof (containment).
"""
from __future__ import annotations

import numpy as np


def sky_mask(image_rgb, brightness=0.55, max_saturation_gap=0.35, smooth=7):
    """Sky as the bright, smooth region connected to the top edge of the image.

    Postcard skies are painted or retouched, so this is a conservative colour
    and smoothness rule, followed by a flood fill from the top row; anything
    not connected to the top is never sky.
    """
    from scipy.ndimage import label, uniform_filter
    img = np.asarray(image_rgb, float) / 255.0
    lum = img.mean(2)
    texture = np.abs(lum - uniform_filter(lum, smooth))
    candidate = (lum > brightness) & (texture < 0.035) & ((img.max(2) - img.min(2)) < max_saturation_gap + 0.4 * (img[..., 2] > img[..., 0]))
    labels, _ = label(candidate)
    top = set(np.unique(labels[0])) - {0}
    return np.isin(labels, list(top))


def column_caps(grid_xy, ground_z, poses, sky, heights, width, height):
    """Lowest height proven empty above each ground position.

    grid_xy: (n, 2) column positions; ground_z: (n,) ground heights.
    poses: list of (R, t, f, weight) with R, t world-to-camera and f focal in pixels.
    sky: (height, width) boolean sky mask of the photograph (same pixel grid as f).
    heights: increasing heights above ground to test.
    Returns (cap, weight_of_evidence) per column; cap is +inf where unbounded.
    """
    grid_xy = np.asarray(grid_xy, float); ground_z = np.asarray(ground_z, float)
    cap = np.full(len(grid_xy), np.inf); evidence = np.zeros(len(grid_xy))
    cx, cy = width / 2, height / 2
    for R, t, f, w in poses:
        lowest = np.full(len(grid_xy), np.inf)
        for dz in heights:
            X = np.column_stack([grid_xy, ground_z + dz])
            C = X @ np.asarray(R).T + np.asarray(t)
            z = C[:, 2]
            ok = z > 0
            u = np.full(len(X), -1); v = np.full(len(X), -1)
            u[ok] = np.round(f * C[ok, 0] / z[ok] + cx).astype(int); v[ok] = np.round(f * C[ok, 1] / z[ok] + cy).astype(int)
            inside = ok & (u >= 0) & (u < width) & (v >= 0) & (v < height)
            hit = np.zeros(len(X), bool); hit[inside] = sky[v[inside], u[inside]]
            newly = hit & ~np.isfinite(lowest)
            lowest[newly] = dz
        # A weighted posterior: keep the cap that the bulk of the pose mass agrees on.
        cap = np.minimum(cap, np.where(np.isfinite(lowest), lowest, np.inf)) if w >= 0.05 else cap
        evidence += w * np.isfinite(lowest)
    return cap, evidence


def containment(cap, true_height):
    """Fraction of bounded columns whose cap is at or above the true height (should be 1)."""
    bounded = np.isfinite(cap)
    if not bounded.any(): return None
    return float(np.mean(cap[bounded] + 1e-6 >= np.asarray(true_height)[bounded]))
