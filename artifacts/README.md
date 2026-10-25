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
| `artsquad_modern/runs/1b72e8e6…` | 724 M | 228-record run on e7cef2d8, **stopped during matching**. Holds features and partial matches that a resumed run can reuse. |
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
| `cpu_mvs_modern_v2/` | 299 M | `run_repair.sh`, `build_repair_site.py` |
| `cpu_mvs_masked08_v3/`, `cpu_mvs_masked12_v3/` | 288 M, 298 M | masked historical experiments |
| `cpu_mvs_target_fixed08_v2/`, `cpu_mvs_target_fixed_v2/` | 147 M, 119 M | fixed-focal historical experiments |
| `cpu_mvs_archive_target_v2/` | 130 M | Cornell-archive historical experiment (research-use rights only) |
| `archive_target_v2/`, `target_sfm_v2/`, `masked_target_v3/` | 93 M, 40 M, 7 M | historical Boardman SfM inputs and models |
| `exposure-audit.json` | 68 K | repeated-exposure screen |

`dist/assets/repair/` (662 M) holds built copies of these outputs for `surface-lab.html`.

## Candidates for cleanup (not done; needs the owner's decision)

None of these is referenced by current code, `dist/`, or docs (grep, 2026-10-24):

| Path | Size | Note |
| --- | ---: | --- |
| `cpu_mvs_joint_historical/` | 118 M | unreferenced repair-era run |
| `cpu_mvs_target_v2/` | 107 M | unreferenced; superseded by the fixed-focal runs |
| `work_v12/`, `work_v11/`, `work_focal_prior/` | 53 M, 15 M, 18 M | v1 parameter-sweep working dirs |
| `experiment_v11/`, `experiment_v12/`, `experiment_focal_prior/` | 2.8 M total | their small reports (keep, or archive alongside) |

Deleting all of them frees about 0.3 GB. Bigger savings need a decision about
provenance: `runs/54149158…` and `runs/71279029…` (error runs, 0.4 GB),
`demo-packages/` (rebuildable, 60 M), and the repair outputs above, which
`dist/assets/repair/` duplicates (about 1.5 GB in total).
