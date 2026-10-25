# Modern Arts Quad: executable implementation and boundaries

The approved long project starts on 2026-10-24. This implementation connects
the first modern-data, geometry, diagnostic validation and interaction stages.
It does not turn a first-day pilot into a completed D1 or a PhD contribution.
The immutable schedule, seven core IDs and no-fake-geometry constraints are in
`config/artsquad-project.json`; the evidence API and acceptance contract are in
`docs/plans/demo-delivery-contract.md`. Research references and method limitations
remain in `docs/research/`.

## Executable stages

| Stage | Implementation | Output / important invariant |
| --- | --- | --- |
| Public acquisition | `acquire_artsquad.py` | Immutable original bytes, rights, metadata, EXIF and separate derivatives. Explicit command only; never start a second downloader while one is running. |
| Preparation | `prepare_artsquad.py` | Content-addressed snapshots, decoded/hash-checked images, role exclusions, exact-copy groups, conservative source families, train/test lists and contact sheets. Running downloads may continue without modifying a snapshot. |
| Retrieval / SfM | `run_artsquad_sfm.py` | Train-only NetVLAD → SuperPoint → LightGlue → COLMAP geometric verification and incremental mapping. Every native component retained in `sfm/models/<id>`. |
| Classic baseline | `run_artsquad_sift.py` / `--method sift` | CPU SIFT/COLMAP, same frozen train inputs, 1200px/4096 requested features, exhaustive pairs and all components. Pair/actual-feature budgets differ; not an equal-compute research comparison. |
| Geometry diagnostics | SfM report and `view-graph.json` | Epipolar configurations/inliers, track-angle and residual distributions, focal ratios, exact-hash group counts, unregistered images. None establishes semantic building coverage or accuracy. |
| Independent-query consistency | `validate_artsquad_holdouts.py` | Separate query-only features, retrieval and 2D–3D PnP; training database/model/features guarded by before/after SHA256. No fallback pose or geometry-accuracy claim after failed localization. |
| CPU dense pilot | `run_cpu_mvs.py` via `run_artsquad.py dense` | COLMAP undistortion → OpenMVS depth/fusion → measured mesh → photo texture. At least three cameras; tower insertion and hole filling disabled. Mesh uses `dense.ply`, not sparse input. |
| Texture provenance | `texture_from_cameras.py` | Unchanged measured mesh with explicitly selected camera UVs; unsupported texture faces gray. Mapping source is not independent geometric validation. |
| Supported-only display | `build_artsquad_supported.py` | Local facets use unchanged dense vertices, short projected/3D edges and common recorded-family visibility. Native broad envelopes stay offline; insufficient support never triggers a hull fallback. |
| Face-level inspection | `index_artsquad_faces.py` | OBJ face-order index to estimated common source images and recorded exposure/family IDs; geometry and input hashes guarded. This is estimated visibility, not independent accuracy certification. |
| Fused-point provenance | `audit_artsquad_dense_support.py` | Recorded camera/exposure/source-family visibility and capture-time spans; no certified independent-view, per-face or stable-environment claim. |
| Web packaging | `build_artsquad_site.py` | Actual native camera poses, undistorted photo previews and measured artifacts only. Capture-epoch conflicts quarantine affected components; native experiments remain offline. Source/rights JSON, complete texture-bundle content hash, no map-placed campus. |
| Milestone contract | `artsquad_contracts.py`, `artsquad_status.py` | D0/D1/D2/R1/D3/R2 separately pending/failed/blocked/passed. Missing reports cannot pass. Local resource probe cannot authorize a GPU job. |
| Interactive inspection | `dist/artsquad.*` | Component selection, orbit/zoom, mesh/wire/normal, recovered camera snap, photographs, texture-photo clicks, coverage/limitations/status. No fabricated fallback geometry. |
| Functional browser QA | `check_artsquad_browser.py` | Actual artifacts, source/camera controls, material change, 390px layout, no-data/error behavior and JS/HTTP failures. Software WebGL is not a device-performance benchmark. |

## Reproduce a frozen pilot

Use the existing environment, or install `requirements-artsquad.txt` into a
separate environment and set up the pinned OpenMVS CPU runtime as documented in
`docs/legacy/repair/results-repair.md`. First learned-feature use can download pretrained
weights. Keep weights outside the public package and honor their licenses.

```bash
.venv/bin/python pipeline/run_artsquad.py prepare
.venv/bin/python pipeline/run_artsquad.py pilot --snapshot SNAPSHOT/snapshot.json
```

The pilot prints `RUN_DIRECTORY` and the packaged scene path. Feature budget
defaults to 1200px / 4096 SuperPoint keypoints / 8 retrieval neighbors. These are
small local pilot settings, not the final detailed-campus resolution. To add a
measured surface for one real component:

```bash
.venv/bin/python pipeline/run_artsquad.py dense --run RUN_DIRECTORY --components COMPONENT_ID --max-resolution 1280 --resolution-level 0
.venv/bin/python pipeline/run_artsquad.py site --snapshot SNAPSHOT/snapshot.json --run RUN_DIRECTORY
.venv/bin/python pipeline/run_artsquad.py holdouts --run RUN_DIRECTORY --components COMPONENT_ID
# Rebuild only local supported facets/evidence for an existing dense attempt.
.venv/bin/python pipeline/run_artsquad.py patches --run RUN_DIRECTORY --components COMPONENT_ID
```

Open `http://127.0.0.1:8080/artsquad.html` if the existing preview server is
running; otherwise run `python3 -m http.server 8080 --directory dist` locally.
Use a trusted local machine; this is not an Internet hosting service.

```bash
PLAYWRIGHT_BROWSERS_PATH=/home/bobby/CS6672/.cache/playwright .venv/bin/python pipeline/check_artsquad_browser.py
.venv/bin/python -m unittest discover -s tests -p 'test_artsquad*.py'
```

PyTorch workers and Chromium need normal local IPC/network-loopback support.
Sandbox-denied IPC is an execution error, not evidence that reconstruction or
the website passed. Run with the product's normal approved execution permission
when necessary; never bypass source-provider limits or access controls.

## Data / cache safety

`snapshot.json` freezes inputs, split, source manifest digest and policy. Working
photo bytes are rehashed before staging and publication. Only train images are
copied byte-for-byte into a run's image directory (not symlinked: COLMAP resolves
symlink targets and would change image names). No held-out image enters retrieval's
mapping database, bundle adjustment, dense stereo or texture fitting. Exact
hash groups are only a lower-bound copy detector; separate files are not
automatically independently captured observations.

The run ID includes snapshot hash, feature budget, target scope, library
versions and an explicit run label. Changed parameters create another run;
source/feature caches are not silently relabeled. Interrupted native database
or mapping stages are preserved and refused for destructive replay; select a
new `--run-label recovery-1` to restart them. Completed runs are reusable after
input-hash checks. Logs, failed reports and disconnected models remain visible.

`--reuse-from OLD_RUN_DIRECTORY` optionally imports only individually verified,
compatible training descriptor/match groups. Both photo hashes and all feature
fingerprint fields must agree. Current test/excluded photographs are never
copied, even if an older experiment used them for training. Entire HDF5 files,
databases and geometry are never reused across snapshots. A native-SfM-failed
source may supply a cache only after complete feature/pair-array verification;
its error status remains in the cache provenance and is not promoted to success.

Mesh material dependencies are explicitly enumerated. The packager rejects
escaping paths, unknown/held-out cameras, model/mesh mismatches and geometry-
modifying photo projection. All browser camera coordinates are OpenGL camera-
to-world; COLMAP OpenCV rotations are converted with `diag(1,-1,-1)`. Photo
previews are undistorted; intrinsics and image dimensions refer to that
calibrated model. No meter units are claimed.

## Remaining critical path (not implemented away by the website)

1. Finish compliant acquisition and seek additional public sources with verified
   reuse rights and genuinely overlapping views. Current White/Tjaden source
   families and several facade/viewpoint strata are insufficient for validation.
2. Establish two adjacent core buildings connected by genuine independent
   observations; audit repeated facades, unknown focal lengths, pure rotations,
   calibration sensitivity and target identity. Collection labels alone cannot
   establish this. Preserve all failed/unregistered views.
3. Verify the initial surfaces, supported environment, holdout localization and
   image/geometry consistency. A held-out PnP pose residual is not independent
   ground truth. Independently validate the available estimated per-face
   visibility index, depth consistency and exposure relationships; add
   transient/vegetation layers before promoting a scene to validated coverage.
4. Confirm an approved single-GPU research environment and storage. This local
   checkout is CPU-only, about 8 GiB RAM and ~12 GiB free at initial inspection.
   No cloud spend, Slurm job or GPU allocation is authorized by the plan.
5. Add shared-frame high-resolution tiles and measured LOD/texture compression;
   validate the frozen route on a real desktop at 20 Mbps, cold cache <=5 sec,
   sustained >=30 FPS. The current OBJ pilot does not prove those targets.
6. Produce an actual 45–60 sec capture, rights-reviewed screenshots/report,
   HTTPS release and rollback package. This session has no callable hosting
   publisher or verified destination; localhost and ZIP files do not count as
   delivered HTTPS. Do not create an unapproved tunnel/account.
7. Continue seven-building D2, equal-budget baselines, method/ablation/cross-scene
   research, calibrated refusal, then qualified historical localization and
   Boardman recovery. Modern success does not waive historical feasibility or
   establish a novel research contribution.

The Sites workflow influenced local preview, design and error-state QA. No
synthetic image-generation workflow is used. Publicity and paper acceptance
remain external outcomes, never completion assertions in the status file.
