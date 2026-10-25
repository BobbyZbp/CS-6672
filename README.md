# GhostMap — reconstruction experiments

Current milestone: **modern Arts Quad first**, including multiple buildings and
observed environmental context. Historical Boardman reconstruction is deferred.
The staged outputs and evidence requirements are in
[`docs/modern-artsquad-pipeline.md`](docs/modern-artsquad-pipeline.md), with the
collection boundary in `config/artsquad-modern.json`.

```bash
.venv/bin/python pipeline/acquire_artsquad.py --inventory-only
.venv/bin/python pipeline/acquire_artsquad.py --download
```

## Arts Quad implementation (2026-10-24)

The new interactive **Arts Quad Atlas** is at
`http://127.0.0.1:8080/artsquad.html`. It loads only the selected measured run,
keeps disconnected components separate, and shows source counts, cameras,
photographs, missing evidence and milestone status. It is a diagnostic workbench,
**not the accepted D1 multi-building demo**.

```bash
# Freeze the successfully downloaded local inputs; does not start a downloader.
.venv/bin/python pipeline/run_artsquad.py prepare
# SfM + actual-asset web package, using the immutable snapshot printed above.
.venv/bin/python pipeline/run_artsquad.py pilot --snapshot SNAPSHOT/snapshot.json
# Separate CPU SIFT baseline (exhaustive pairs; not equal-compute comparison).
.venv/bin/python pipeline/run_artsquad.py sfm --method sift --snapshot SNAPSHOT/snapshot.json
# Explicit component selection; no fabricated alignment between components.
.venv/bin/python pipeline/run_artsquad.py dense --run RUN_DIRECTORY --components 0
.venv/bin/python pipeline/run_artsquad.py site --snapshot SNAPSHOT/snapshot.json --run RUN_DIRECTORY
.venv/bin/python pipeline/run_artsquad.py holdouts --run LEARNED_RUN_DIRECTORY --components 0
.venv/bin/python pipeline/run_artsquad.py status
.venv/bin/python -m unittest discover -s tests -p 'test_artsquad*.py'
```

Setup uses `requirements-artsquad.txt`, pinned hloc/LightGlue and the private
OpenMVS CPU runtime described in `docs/results-repair.md`. Do not reinstall a
CPU torch wheel over an intentionally configured GPU environment. The local
pilot can require several minutes; native COLMAP models, logs and every
component are retained. Full high-resolution processing needs separately
confirmed compute/storage. No remote job, purchase or HTTPS deployment is
performed by these commands.

See [`docs/artsquad-implementation.md`](docs/artsquad-implementation.md) for
stage outputs, recovery and remaining work, and
[`docs/demo-delivery-contract.md`](docs/demo-delivery-contract.md) for the frozen
D0/D1/D2/R1/D3/R2 acceptance contract. The kickoff remains 2026-10-24 and D1's
planned window remains 2026-11-21–2026-12-05. Status evaluation is fail-closed:
unknown evidence never passes, and a working webpage is not a reconstruction.

Latest measured local checkpoint:
[`145-record CPU experiment`](docs/artsquad-local-checkpoint-145.md).
It includes a five-camera Goldwin-labelled local surface, unsuccessful Morrill
depth fusion and the capture-date quarantine; no two-core-building demo has
passed. The current execution decision is local CPU data work and small-scale
validation only, without a GPU purchase or remote job submission.

The existing Surface Lab below is the earlier Uris / McGraw control and
historical diagnostics; its artifacts remain preserved.

The new **Surface Lab** is at `http://127.0.0.1:8080/surface-lab.html`.
CPU dense stereo now works, with actual textured partial surfaces and camera
viewpoints. See `docs/results-repair.md` for measured repair results and
`docs/noah-method-audit.md` for the Snavely paper/code audit.
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

## Frozen v1 baseline

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

## Reproduce

Python 3.10+ is required. The first learned-feature run downloads pretrained NetVLAD, SuperPoint, and LightGlue weights.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-hloc.txt
bash run_pipeline.sh --force
python3 -m http.server 8080 --directory dist
```

Open `http://127.0.0.1:8080/`.

`run_pipeline.sh` treats a scientific gate failure as a completed negative experiment: it still packages the reports and website. Execution errors still stop the script. Cached features and matches are reused on later runs.

## Pipeline

1. Retrieve Boardman Hall, Uris Library, and McGraw Tower imagery through the Wikimedia Commons API.
2. Enforce machine-readable license, image type, resolution, and historical/modern metadata rules; retain source URL, author, dimensions, and SHA-256.
3. Run a classic COLMAP SIFT baseline.
4. Retrieve candidate overlap with NetVLAD; extract SuperPoint; match with LightGlue; run COLMAP geometric verification, incremental mapping, and bundle adjustment.
5. Measure cross-era constraints and Boardman-specific historical multiview tracks.
6. Attempt COLMAP dense MVS and publish a surface only when every release gate passes.

No image is manually added, removed, cropped, masked, annotated, or assigned a pose. No mesh, footprint extrusion, or facade proxy is substituted after failure.

## Public artifacts

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

## Scope

The temporal motivation follows Matzen and Snavely, *Scene Chronology* (ECCV 2014), and Lin et al., *Neural Scene Chronology* (CVPR 2023). GhostMap v1 tests whether the automatically auditable public data can support the geometry needed for that direction. It does not claim metric scale, architectural completeness, recovered interiors, a dense Boardman surface, or photorealistic novel views.

See `docs/protocol.md`, `docs/data-audit.md`, and `docs/results-v1.md` for the target definition declared before the full joint run, source policy, and failure analysis.
