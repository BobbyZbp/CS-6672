# GhostMap v1 results

Formal run date: 2026-10-23  
Sparse engine: pycolmap/COLMAP 3.13.0  
Learned front end: NetVLAD retrieval, SuperPoint, LightGlue  
Inputs: 77 licensed Internet images (35 historical, 42 modern)

## Result summary

| Experiment | Registered images | Sparse points | Cross-era verified pairs | Result |
| --- | ---: | ---: | ---: | --- |
| Classic joint SIFT | 0 historical + 12 modern | 1,827 | 0 | fail |
| HLoc cross-era-only | 12 historical + 16 modern | 560 | 169 | camera bridge |
| HLoc full joint | 14 historical + 22 modern | 2,724 | 178 | sparse SfM |

The full learned-feature model has a mean reprojection error of 1.2063 px and a mean track length of 4.272 observations. Those aggregate statistics do not establish that the disappeared target was recovered.

## Target-specific test

The full joint model contains:

- 401 historical-only 3D points;
- 358 cross-era 3D points;
- 331 points observed by at least one Boardman-labelled image;
- 6 registered Boardman-labelled images; and
- **203 points observed by at least two Boardman-labelled historical images and by no modern image**.

The v1 release gate requires 1,000 points under the final definition. The result is therefore **fail**. The definition intentionally excludes Uris Library and McGraw Tower points that are useful for coordinate transfer but are not evidence for Boardman Hall surface recovery.

## Dense reconstruction

COLMAP successfully undistorted all 36 registered images in the learned joint component. PatchMatch Stereo then stopped with the exact error:

```text
[mvs.cc:40] PatchMatch requires CUDA but COLMAP was not compiled with it.
```

The dense stage is recorded as `blocked`; it is not replaced by Poisson completion, an extruded footprint, or a hand-authored building. Even with a CUDA build, the sparse Boardman target gate already fails, so GPU availability alone would not turn this run into an accepted result.

## Interpretation

Learned features materially improve the scientific result: they change the conclusion from “no cross-era localization” to “cross-era camera connectivity is feasible.” They do **not** provide enough target-specific multiview support for a paper-quality Boardman Hall surface from the admitted public set.

Under the zero-human constraint, the v1 topic should be rejected in its current form or rerun only after an automated, rights-aware adapter adds a substantially stronger archive. The website presents this as a negative feasibility result and keeps the raw sparse model behind an explicitly rejected diagnostic panel.
