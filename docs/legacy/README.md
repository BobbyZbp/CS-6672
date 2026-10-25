# Legacy experiments (frozen)

These two earlier lines of work are kept for provenance. Their code lives in
`pipeline/legacy/v1/` and `pipeline/legacy/repair/`, their outputs stay at the
`artifacts/` paths recorded in their reports, and their pages are still served
from `dist/` (`baseline-v1.html`, `surface-lab.html`). The current project is the
modern Arts Quad pipeline described in the [root README](../../README.md).

Shared stages (`run_cpu_mvs`, `texture_from_cameras`, `mesh_supported_patches`,
`setup_openmvs`, `download_commons`) now live in `pipeline/ghostmap/`; the old
`pipeline/<name>.py` entry points still work, so both shell scripts are unchanged
apart from the legacy script paths.

## Surface Lab (OpenMVS repair, 2026-10-23)

The new **Surface Lab** is at `http://127.0.0.1:8080/surface-lab.html`.
CPU dense stereo now works, with actual textured partial surfaces and camera
viewpoints. See `docs/legacy/repair/results-repair.md` for measured repair results and
`docs/legacy/repair/noah-method-audit.md` for the Snavely paper/code audit.
Install `requirements-repair.txt` and run `bash run_repair.sh` to reproduce it.
Run the initial acquisition / learned-SfM pipeline below first if its cached
inputs are absent. `bash run_repair.sh --masked` additionally acquires the
Cornell archive scans and runs automatic semantic filtering and the two
masked, higher-resolution historical experiments. These are CPU-heavy jobs;
cached computations are reused.

The modern higher-resolution experiment has 22 recovered cameras, 171,351 fused
depth points, and 262,042 mesh faces. The masked historical experiments have
16 / 17 recovered cameras and 20,555 / 13,702 fused points. Historical focal
calibration, completeness, metric accuracy, and cross-era alignment are still
unvalidated. These real partial surface experiments do **not** establish a
paper-quality reconstruction of Boardman Hall.
The historical viewer defaults to local facets screened against repeated-scan
groups; raw dense counts are not counts of independent geometric evidence.

### Frozen v1 baseline

GhostMap v1 is a zero-human-in-the-loop feasibility study for reconstructing Cornell's demolished Boardman Hall from public Internet imagery. The v1 result is **negative**: learned matching recovers a real historical/modern camera component, but the Boardman-specific geometry and dense-surface release gates fail. The website therefore withholds a finished 3D demo.

### Formal result

The 2026-10-23 run automatically admitted 77 Wikimedia Commons images: 35 historical and 42 modern.

| Stage | Measured result | Decision |
| --- | ---: | --- |
| Classic SIFT joint model | 0 historical + 12 modern cameras | fail |
| HLoc cross-era-only model | 12 historical + 16 modern cameras, 560 points | bridge established |
| HLoc full joint model | 14 historical + 22 modern cameras, 2,724 points | SfM established |
| Cross-era geometry | 178 nondegenerate verified pairs | pass |
| Boardman-labelled cameras | 6 | pass |
| Boardman multiview historical-only points | 203 / 1,000 required | **fail** |
| Dense COLMAP surface | PatchMatch unavailable in the CPU-only build | **blocked / fail** |

The full model has 358 tracks observed in both eras and 401 historical-only tracks. Only 203 points satisfy the stricter target definition: observed by at least two registered Boardman-labelled historical images and by no modern image. Stable Uris Library or McGraw Tower points therefore cannot masquerade as recovered Boardman Hall structure.

### Reproduce

Python 3.10+ is required. The first learned-feature run downloads pretrained NetVLAD, SuperPoint, and LightGlue weights.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-hloc.txt
bash run_pipeline.sh --force
python3 -m http.server 8080 --directory dist
```

Open `http://127.0.0.1:8080/`.

`run_pipeline.sh` treats a scientific gate failure as a completed negative experiment: it still packages the reports and website. Execution errors still stop the script. Cached features and matches are reused on later runs.

### Pipeline

1. Retrieve Boardman Hall, Uris Library, and McGraw Tower imagery through the Wikimedia Commons API.
2. Enforce machine-readable license, image type, resolution, and historical/modern metadata rules; retain source URL, author, dimensions, and SHA-256.
3. Run a classic COLMAP SIFT baseline.
4. Retrieve candidate overlap with NetVLAD; extract SuperPoint; match with LightGlue; run COLMAP geometric verification, incremental mapping, and bundle adjustment.
5. Measure cross-era constraints and Boardman-specific historical multiview tracks.
6. Attempt COLMAP dense MVS and publish a surface only when every release gate passes.

No image is manually added, removed, cropped, masked, annotated, or assigned a pose. No mesh, footprint extrusion, or facade proxy is substituted after failure.

### Public artifacts

| Path | Meaning |
| --- | --- |
| `data/raw/manifest.json` | Input provenance, licenses, dimensions, hashes, and automatic admission decisions |
| `artifacts/public/report.json` | Classic SIFT/COLMAP baseline |
| `artifacts/hloc_cross_era/report.json` | Cross-era-only HLoc/COLMAP run |
| `artifacts/hloc_cross_era/joint_report.json` | Full learned-feature joint run and Boardman target-coverage counts |
| `artifacts/hloc_cross_era/sfm_joint/` | Native selected COLMAP sparse model |
| `artifacts/hloc_cross_era/joint_sparse.ply` | Rejected sparse diagnostic, not a recovered building |
| `artifacts/experiments/dense_hloc_joint_cuda_check/dense_mvs_report.json` | Exact dense-MVS capability failure |
| `dist/` | Buildless audit website |

### Scope

The temporal motivation follows Matzen and Snavely, *Scene Chronology* (ECCV 2014), and Lin et al., *Neural Scene Chronology* (CVPR 2023). GhostMap v1 tests whether the automatically auditable public data can support the geometry needed for that direction. It does not claim metric scale, architectural completeness, recovered interiors, a dense Boardman surface, or photorealistic novel views.

See `docs/legacy/v1/protocol.md`, `docs/legacy/v1/data-audit.md`, and `docs/legacy/v1/results-v1.md` for the target definition declared before the full joint run, source policy, and failure analysis.
