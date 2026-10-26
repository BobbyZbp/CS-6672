# artifacts/ — run outputs (not versioned)

Everything here is generated. Reports record these paths, so directories are
**not moved**; this index says what each one is. Sizes measured 2026-10-24 with
the disk at 97% full (about 7 GB free).

## Current: modern Arts Quad (`artsquad_modern/`, 3.7 GB)

| Path | Size | What it is |
| --- | ---: | --- |
| `artsquad_modern/project-status.json` | 40 K | Fail-closed milestone status (stale: generated before the 228-image download finished). |
| `artsquad_modern/snapshots/<id>/` | 18 M | Immutable input snapshots. `b43ad69e` = 145 records (reconstructed); `e7cef2d8` = 228 records (latest, not yet reconstructed). |
| `artsquad_modern/images/` | 465 M | Working images staged from `data/artsquad_modern/originals`. |
| `artsquad_modern/runs/2b7e3fa9…` | 713 M | **Best learned run** (snapshot b43ad): 6 components, Uris/Tower 21 cameras, Goldwin-labelled dense patch. Used by the viewer. |
| `artsquad_modern/runs/4b9a7fc6…` | 210 M | SIFT/COLMAP CPU baseline on snapshot b43ad. |
| `artsquad_modern/runs/bd120823…` | 352 M | Calibration-sensitivity control (fixed radial) on b43ad. |
| `artsquad_modern/runs/8563d895…` | 508 M | First 46-image learned pilot (snapshot f27fe368). Used by the viewer. |
| `artsquad_modern/runs/c12e90ba…` | 239 M | Learned run on f27fe368 (1 component). Used by the viewer. |
| `artsquad_modern/runs/52096269…` | 132 M | SIFT baseline on f27fe368. |
| `artsquad_modern/runs/1b72e8e6…` | — | First attempt on the 228-photo snapshot (stopped twice by the out-of-memory killer). **Deleted 2026-10-25**, superseded by the finished run below. |
| `artsquad_modern/runs/6a31738f…` | 749 M | **Finished** learned run on the 228-photo snapshot (82 of 139 registered; Uris/Tower 26 cameras, Goldwin Smith 14, Morrill/White 11). Its `anchor/0/` holds the lidar anchoring attempt (scales 10.5 % apart, not marked usable). |
| `artsquad_modern/runs/18f93889…` | 394 M | EXIF-anchored re-mapping of the 145-photo snapshot. **The demo's reference frame**: `anchor/0/` (lidar anchoring) and `archival/` (positive control, postcard certificates). |
| `artsquad_modern/runs/6406b8ea…` | 1.6 G | Learned run on the Commons + Openverse snapshot (216 photographs; 132 registered): the **tower-and-library fragment** (63 cameras) anchored to the lidar through the tower (`anchor/0/`), its existence intervals (`chronology/0-intervals.json`), the half-resolution dense surface (`dense/tower-half/`), the Boardman certificates (`archival/`). The time machine's reference. |
| `artsquad_modern/runs/6da4ccc3…` | 141 M | Final mapping of the Gates Hall photographs (35 in the training split): fragments of 11, 8 and 3 cameras; footprint anchoring of the largest attempted, not usable. The Gates chapter's reconstruction attempt. |
| `artsquad_modern/runs/449cffd0…` | 1.5 G | **Campus-wide** learned run on the complete deduplicated snapshot (339 training photographs, GPU): 167 registered in 29 fragments, seven with 8 or more cameras (Uris Library 54, McGraw Tower 27 and 22, Morrill Hall 18, Goldwin Smith Hall 13, Olive Tjaden Hall 8, Gates Hall 8). The georegistration paper's reconstruction. |
| `artsquad_modern/runs/54149158…` | 239 M | Status `error`, yet `sfm/models/0` exists (13 images). Kept as evidence of that report/model mismatch. |
| `artsquad_modern/runs/71279029…` | 155 M | Status `error` (snapshot d43f46c8). |
| `artsquad_modern/runs/82c7cca3…` | 228 K | Interrupted, empty. |

Other current outputs: `browser-qa/` (33 M, Playwright QA), `demo/` (28 M,
recorded reel), `demo-packages/` (60 M, portable bundles; can be rebuilt),
`provider-probes/` (Quad6K range-probe ledgers), `quad6k_research/` (private
research snapshot; not redistributable), `logs/stray-root-logs/` (OpenMVS and
glog files that used to sit in the repository root).

## Legacy v1 Boardman baseline (2026-10-23)

| Path | Size | What it is |
| --- | ---: | --- |
| `public/` | 4.8 M | v1 SIFT reports and models (`report.json`, `historical/`, `modern/`, `joint/`). |
| `hloc_cross_era/` | 146 M | v1 learned cross-era and joint models (`sfm_joint`: 14 historical + 22 modern cameras). |
| `work/` | 185 M | v1 staged images; `work/joint/images` is also the input to the repair runs. |
| `experiments/` | 46 M | Dense-MVS capability checks (PatchMatch blocked: no CUDA build). |

## Legacy OpenMVS repair / Surface Lab (2026-10-23)

| Path | Size | Referenced by |
| --- | ---: | --- |
| `cpu_mvs_modern_full_v2/` | 576 M | `run_repair.sh`, `build_repair_site.py` (171,351 dense points, Uris/Tower only) |
| `cpu_mvs_masked08_v3/` | 288 M | masked historical experiment |
| `cpu_mvs_target_fixed08_v2/`, `cpu_mvs_target_fixed_v2/` | 147 M, 119 M | fixed-focal historical experiments |
| `cpu_mvs_archive_target_v2/` | 130 M | Cornell-archive historical experiment (research-use rights only) |
| `archive_target_v2/`, `target_sfm_v2/`, `masked_target_v3/` | 93 M, 40 M, 7 M | historical Boardman SfM inputs and models |
| `exposure-audit.json` | 68 K | repeated-exposure screen |

`dist/assets/repair/` (662 M) holds built copies of these outputs for `surface-lab.html`.

## Cleanup log

Deleted 2026-10-25 with the owner's approval (nothing in code, `dist/` or docs
referenced them): `cpu_mvs_joint_historical/`, `cpu_mvs_target_v2/`,
`work_v11/`, `work_v12/`, `work_focal_prior/`, `experiment_v11/`,
`experiment_v12/`, `experiment_focal_prior/` (about 0.36 GB). Also deleted on 2026-10-25, under the same approval, to make room for dense reconstruction: `cpu_mvs_modern_v2/` and `cpu_mvs_masked12_v3/` (about 0.6 GB; built copies remain in `dist/assets/repair/` for the Surface Lab page; rebuilding them needs `run_repair.sh`).

Deleted 2026-10-25 evening to make room for the time-machine acquisition
(the acquirer refuses to download below 5 GB free): the staged image copies,
feature caches, holdout and query folders of every finished run except the
current demo run (reports, configurations and native models are kept, so the
numbers remain reproducible from `report.json`; features are regenerable);
the legacy OpenMVS outputs `cpu_mvs_modern_full_v2/`, `cpu_mvs_masked08_v3/`,
`cpu_mvs_target_fixed08_v2/`, `cpu_mvs_target_fixed_v2/` and
`cpu_mvs_archive_target_v2/` (their built copies remain under
`dist/assets/repair/` for the Surface Lab page); and the pip cache.
Deleted 2026-10-25 (night): the depth maps and undistorted images of the full-resolution OpenMVS attempt on the tower fragment, `artsquad_modern/runs/6406b8eaae260163b303/dense/tower/` (841 MB; fusion was killed by the memory limit; `report.json` and the tool logs remain). The half-resolution attempt lives beside it in `dense/tower-half/`.
Deleted 2026-10-26 (approved in the research plan, to make room for a CUDA toolchain): the image copies and feature/match caches of the two superseded Gates Hall mapping attempts (`artsquad_modern/runs/7cce507a4a0abf005269/`, `.../323064cf0ac9718e0e90/`; superseded by the final mapping `6da4ccc327cb12bf14df`) and of the calibration-control run on the 145-photo snapshot (`.../bd1208237efd7b33d52d/`); reports and native models of all three remain. Also the depth maps, undistorted images and OpenMVS scene files of the half-resolution dense workspace (`.../6406b8eaae260163b303/dense/tower-half/`; `dense.ply`, `surface.ply`, the report and the logs remain, and the viewer's copy of the surface lives under `dist/assets/timemachine/mesh/`). About 2.3 GB.

## presentation/ (2026-10-26)

| Path | What it is |
| --- | --- |
| `presentation/ghostmap-tour.webm` | Captioned tour of the ten demo chapters, recorded on the GPU (`ghostmap/qa/record_tour.py`); the fallback if the live demo fails. `tour-report.json` beside it. |
| `presentation/splat-walk-plain-vs-lidar-taught.mp4` | gsplat walk around the tower, plain and lidar-taught side by side (`ghostmap/dense/splat_views.py`). |
| `presentation/ghostmap-demo-<stamp>.zip` | The offline bundle: demo page, slides, vendored modules, all assets, `serve.py` (`ghostmap/package/presentation_bundle.py`); checked standalone with the page check. |
