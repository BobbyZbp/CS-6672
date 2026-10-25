# GhostMap milestone M1: modern Arts Quad reference scene

## Objective and boundary

First reconstruct a **modern multi-building scene** around Cornell's Arts Quad,
with observed environmental context. Historical reconstruction is a later
milestone and must not consume this milestone's validation budget.

The seven core targets are Morrill, McGraw Hall, White, Sibley, Tjaden, Goldwin
Smith and Lincoln. Uris Library / McGraw Tower are southern anchors, not a
substitute for quad coverage. Rand, Milstein, Stimson, Klarman and Olin are
context candidates. The list defines collection scope, not a claim that all
these buildings have already been reconstructed.

Config: `config/artsquad-modern.json`. All runs and data are separate from v1.

## Stages and inspectable outputs

| Stage | Work | Required output / exit condition |
| --- | --- | --- |
| M1.1 Data and coverage | Discover originals by building and quad-wide views, record capture dates / rights / EXIF / hashes, remove exact copies, screen repeated exposures | Source manifest, per-building candidate counts, unknown / rejected reasons; no arbitrary 50-image ceiling |
| M1.2 View graph | Retrieve local neighbors plus cross-building bridge candidates; verify matches; group scan copies / pure panorama rotations before partitioning | Connected components, verified edges, capture-group labels; disconnected buildings stay disconnected |
| M1.3 Camera geometry | COLMAP SfM / bundle adjustment with plausible intrinsics, triangulation-angle checks and grouped held-out views | All components and cameras, tracks, residual distributions, calibration-sensitivity and registration-coverage reports |
| M1.4 Dense measured surfaces | Multiview depth / normal estimation and fusion; require distinct capture support, retain per-point visibility, separate transient / vegetation support | Depth maps, confidence / visibility, dense clouds, local-resolution and observed-surface support maps |
| M1.5 Surface and appearance | Mesh supported geometry and texture from calibrated photographs | Mesh + UVs + source-view provenance, holes and unknown areas retained, no invented architecture |
| M1.6 Validation | Held-out camera reprojection / depth consistency, per-building / facade coverage, duplicate leakage and independent baseline checks | Separate geometry, completeness and appearance results; point count alone cannot pass |
| M1.7 Interactive reference scene | Orbit / zoom / walk through measured connected components; inspect cameras, source photos, support and missing regions | Working browser viewer and downloadable reproducible artifacts; unaligned components visibly separate |

M1.1 must expose what data exist **before** a detailed campus scene is promised.
More images are useful when they add independent viewpoints, resolution, shared
context or capture diversity. Multiple scans / crops of one exposure and
panorama tiles from one camera center cannot supply new triangulation baseline.

## Global-to-local detail strategy

Use wide and intermediate views to establish a connected quad-scale camera
frame first. Then densify individual buildings / facade tiles at higher native
image resolution **using cameras in that same frame**, retaining shared views
at tile boundaries. This supports detail without pretending independently
scaled building models already form a coherent campus. Coarse global context
and detailed local surfaces are different resolution levels of measured data.

Capture dates >=2000 define a collection pool, not a single unchanged physical
epoch. Building additions, construction, scaffolding and foliage changes must
be separated or flagged during graph / geometry validation. An Internet photo
set spanning 25 years is not automatically a faithful 2026 campus snapshot.

## Environmental context and future historical localization

Preserve observed grounds, paths, neighboring facades, persistent architectural
edges and recoverable trees. Do not simply remove the entire environment with
a building mask. Keep moving people / vehicles and nonrigid vegetation on
separate reliability layers; a tree surface is not a permanent historical
anchor just because it reconstructs in one modern epoch.

Retain original photos, derivatives, camera calibration / poses, feature
descriptors, verified matches, sparse tracks, depth maps, normals and per-surface
source visibility. Later historical PnP should use persistent *measured* modern
features, with RANSAC / independent-view verification. Cross-building overlap
must actually connect the coordinate frame; map positions cannot manufacture
such a connection.

An SfM similarity frame has no known meter scale by default. GPS, surveyed or
independently validated dimension constraints can later establish scale and
georeferencing with uncertainty. Keep metric claims disabled until this is
verified. A basemap / footprint is comparison context, never recovered geometry.

## Quality contract

- Preserve as much **observed** detail as supported by native photo resolution,
  camera baseline and depth agreement; do not upscale images into new evidence.
- Report per-core-building coverage separately from tower / library counts.
  Category / filename labels are collection hints, not pixel-level identity or
  proof that a building's facade was recovered.
- Split held-out data by exposure group, not individual file; avoid adjacent
  video-frame and duplicate-scan leakage. Store split rules before scoring.
- Compare local support, triangulation angles, held-out residuals, completeness,
  capture-time consistency and camera-calibration plausibility. Numerical
  release thresholds will be explicitly versioned before the full experiment;
  provisional engineering checks are not a preregistered paper benchmark.
- A photorealistic renderer, if added, is an appearance layer. It does not
  certify geometric accuracy or turn unobserved surfaces into measured ones.

## Execute the first independent stage

```bash
.venv/bin/python pipeline/acquire_artsquad.py --inventory-only
.venv/bin/python pipeline/acquire_artsquad.py --download
.venv/bin/python pipeline/review_artsquad_inputs.py
```

The first command only discovers and audits metadata. The second downloads
eligible originals, records exact hashes / EXIF, and creates orientation-correct
2400px working derivatives with separate hashes. Metadata-only candidates are
not counted as acquired images. Cached successful downloads are reused.

Disk is constrained in this checkout: collection uses an explicit 3 GiB input
budget and leaves at least 5 GiB free for computation. Budget-skipped files are
reported, not silently labelled invalid. Provider, inventory and download
failures are retained rather than presented as zero available imagery.
