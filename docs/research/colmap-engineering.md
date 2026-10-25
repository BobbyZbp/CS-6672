# GhostMap: COLMAP, evidence, and public-demo engineering audit

Prepared 2026-10-23. This is a planning and primary-source audit, not a new
reconstruction result. Resource ranges and release targets below are proposed
engineering budgets; they are not measured performance, market quotes, or
preregistered scientific criteria.

## 1. Verified local starting point

Read-only inspection of the current checkout found:

- `artifacts/cpu_mvs_modern_full_v2/report.json`: 22 registered modern cameras,
  2,181 sparse tracks, 171,351 fused depth points, and 262,042 native mesh faces.
  This is the Uris/McGraw control component, not a recovered Arts Quad.
- The report explicitly calls the result a surface candidate. Target identity,
  independent held-out geometry, metric ground truth, and complete architecture
  are not established by these counts.
- `artifacts/browser-qa/report.json`: seven existing experiment choices load,
  wireframe changes pixels, source-photo selection loads, orbit works, and a
  390px mobile layout fits. No JavaScript or failed-HTTP errors were recorded.
  These are software checks, not depth-accuracy or mobile frame-rate tests.
- `data/artsquad_modern/inventory.json` and `coverage.json`: 581 discovered
  unique Commons files; 231 pass preliminary metadata admission. The acquisition
  manifest was still `running`, with eight admitted entries at inspection.
  Admission is not a count of independent camera centers or usable surfaces;
  this is a live acquisition snapshot, not a promised final corpus.
- Installed pycolmap is 3.13.0 without CUDA; torch is 2.14.1+cpu without CUDA.
  Host memory is 7.7 GiB; available project filesystem space was about 13 GiB.
  This is adequate for small reproducible pilots, not the proposed full research
  and high-resolution campus release.
- Existing core targets are Morrill, McGraw Hall, White, Sibley, Tjaden,
  Goldwin Smith, and Lincoln; Uris/McGraw Tower are southern anchors.

Do not erase working pilot artifacts to make storage fit. Full-scale experiments
need an additional approved storage/compute environment. No new allocation or
purchase is authorized by this audit.

## 2. What the reconstruction methods actually provide

### COLMAP SfM and pycolmap

Schönberger and Frahm, *Structure-from-Motion Revisited*, CVPR 2016, describe
feature extraction, candidate matching, geometric verification, initialization,
incremental image registration, triangulation, outlier filtering, and bundle
adjustment. Their geometric verification distinguishes homographies from
epipolar geometry, and the triangulation section explicitly avoids panoramic
image pairs with degenerate baselines. A large photo count alone cannot create
depth constraints.

Primary paper: <https://demuc.de/papers/schoenberger2016sfm.pdf>.
Official code: <https://github.com/colmap/colmap>.
Official tutorial: <https://colmap.github.io/tutorial.html>.
Official FAQ: <https://colmap.github.io/faq.html>.

The installed version, camera-model definitions, binary/database format,
coordinate conventions, random seeds, and native dependencies must be pinned in
each run. The live official documentation now describes features and APIs newer
than this project's installed 3.13.0; a feature visible in HEAD documentation is
not evidence that it is available in the installed wheel. Use explicit
compatibility tests before an upgrade, preserve the old baseline, and compare
the resulting cameras and geometry.

Prefer the simplest adequate intrinsics model; share calibration only when the
same camera/lens/settings justify it. Internet scans, resized/cropped copies,
phone panoramas, fisheye images, and ordinary camera photographs cannot all be
assigned one shared calibration. The existing historical experiment already
demonstrates that low reprojection residuals can coexist with absurd focal
lengths. Monitor focal/image-width ratios, principal points, distortion,
triangulation angles, baseline diversity, and perturbation stability separately.

### hloc and modern correspondences

Official implementation: <https://github.com/cvg/Hierarchical-Localization>.
hloc supplies retrieval/local-feature/matcher orchestration and COLMAP-based
reconstruction and localization; it is not a guarantee of globally correct
geometry. A practical baseline compares SIFT against SuperPoint/LightGlue or a
pinned compatible learned alternative on the same capture groups and compute
budget. Retrieval proposes pairs; robust geometric verification must still
accept them. Use local neighbors plus deliberately sampled cross-building
bridge pairs and audit component connectivity. Exhaustive matching scales as
N(N-1)/2 and is inappropriate as the only strategy for a many-thousand-image
corpus.

### Dense geometry: COLMAP MVS and OpenMVS

Schönberger, Zheng, Pollefeys, and Frahm, *Pixelwise View Selection for
Unstructured Multi-View Stereo*, ECCV 2016, jointly estimate depth and normals,
select source views using photometric/geometric priors, and filter/fuse with
geometric consistency. Triangulation angle, incidence, image resolution, and
occlusion are important; an edge that matches in several near-duplicate scans
is not several independent depth observations.

Primary paper: <https://demuc.de/papers/schoenberger2016mvs.pdf>.
OpenMVS official code/documentation:
<https://github.com/cdcseacave/openMVS>.

Canonical stages remain cameras -> undistortion -> per-view depth/normal maps
-> consistency filtering -> fused cloud -> supported surfaces -> texture.
OpenMVS CPU is a valid local fallback already exercised here; GPU COLMAP MVS
and OpenMVS should be compared on a frozen representative pilot before scaling.
The current wrapper's `--pointcloud-file dense.ply` and mesher-log count check
must remain regression tests: an earlier interface integration silently meshed
sparse points. Disable artificial tower insertion and unobserved hole filling
in evidence releases. Preserve untextured/unsupported regions explicitly.

Global SfM first, then overlapping high-resolution facade/ground tiles in that
same coordinate frame, avoids independently scaled buildings masquerading as a
single campus. Meshing may interpolate between measured samples; distinguish
measured vertices, supported interpolation, and unobserved space. Do not call
every triangle independently observed merely because all three vertices have
some support.

### Appearance is a separate product from geometry

Kerbl et al., *3D Gaussian Splatting for Real-Time Radiance Field Rendering*,
SIGGRAPH 2023, optimize a radiance representation initialized from calibrated
sparse points. The paper targets novel-view synthesis, not proof of a surveyed
surface. Good image metrics, photorealism, and many Gaussians do not validate
metric architecture, unseen roofs, or historic building existence.

Official paper/project:
<https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/>.
Official implementation: <https://github.com/graphdeco-inria/gaussian-splatting>.

The official README lists a CUDA GPU and 24 GB VRAM for paper-evaluation-quality
training, while discussing reduced-memory tradeoffs. Treat that as the original
implementation's reference setup, not a universal lower bound or a promise for
Arts Quad. A splat layer may produce a compelling public tour **after** camera
and surface quality passes, but retain a one-click switch to measured geometry,
support, source photos, and missing data. View/exposure embeddings must not use
held-out test pixels to tune evaluation appearance.

## 3. Data is an evidence graph, not a download folder

Use immutable originals and a derivative registry with byte hashes, source URL,
author, per-item rights, original and working resolution, orientation/crop
transforms, capture-time interval, upload date separately, EXIF/GPS confidence,
provider request status, and rejection reason. Retry with provider-compliant
backoff; no access circumvention. Keep research-use-only images out of the
public texture/source bundle unless reuse has been established.

The identity unit is an **exposure/capture group**, not a filename. Exact hashes,
perceptual duplicate retrieval, local-feature/homography checks, crop/scan
lineage, same-center panoramas, bursts, and contiguous video all inform groups.
Group uncertainty must be retained: an unflagged duplicate is not certified
independent. Avoid training/test leakage through separately colored postcards,
scans, adjacent frames, or different crops of one photograph.

For each facade/ground tile preserve at least: source groups, camera poses and
calibration version, view angles, range/resolution distribution, depth
agreement, visibility/occlusion tests, transient/vegetation class, capture-time
span, calibration-sensitivity score, and processing-run hash. A click in the
viewer should trace a displayed patch to its actual supporting images.

Environment is valuable, but not all environment is equally stable: walls,
stone stairs, paths, and retaining structures can be reference anchors;
people/vehicles are transient; trees, leaves, shadows, snow, and grass need
separate confidence/time treatment. Never use a successfully reconstructed tree
as a permanent cross-century landmark without further evidence.

## 4. Evaluation that can support a research claim

### Freeze the split before tuning

Create train/validation/test capture groups, stratified by building, facade,
season, camera source, capture year, and viewpoint. Reserve approximately
15-20% groups for testing **where there are enough independent groups**; on
tiny historical strata use repeated group-wise leave-one-out and report its
limitations, not one cherry-picked split. Test original-epoch data are never
included in SfM/MVS or appearance fitting for the principal novel-view test.
Using test photos to estimate a PnP evaluation pose is disclosed separately
from using them to estimate the scene.

Per-building reporting prevents a heavily photographed tower from hiding
unreconstructed Quad facades. Report all failures, including no result, not
only registered views. Bootstrap by capture group/building, not by pixels or
millions of correlated surface points. Use frozen baselines and equalized
data, resolution, and compute alongside full-budget results.

### Three metric families, with different meanings

1. Geometry: registration rate over eligible independent groups; verified
   track/angle distributions; focal and distortion plausibility; forward/back
   depth consistency; geometric stability under capture-group resampling and
   calibration perturbations; independent reference accuracy/completeness when
   such a reference exists. Pixel residuals on fitted training tracks are only
   a diagnostic. Point/triangle counts are throughput, not accuracy.
2. Coverage: visible facade/ground support at stated resolution and view
   diversity, with exact denominator defined in advance; per-building
   holes/occlusions and unrecovered regions. An image-space recoverable-surface
   coverage measure is not the same as percentage of the entire real building.
   Without ground-truth surfaces, do not claim full 3D completeness.
3. Appearance and use: grouped held-out PSNR/SSIM/LPIPS with valid masks and
   view-pose protocol; cross-view edge/occlusion artifacts; guided-tour quality;
   browser load time, sustained frame times, memory, crashes, and evidence-click
   correctness. Photometric scores alone cannot certify the geometry.

ETH3D supplies an example of evaluating reconstruction against laser-scan
reference rather than self-consistency: <https://www.eth3d.net/>. Use public
benchmarks with existing reference geometry to validate the implementation and
research method under the same no-user-annotation constraint. They do not
retroactively establish centimeter accuracy at Cornell.

If Cornell-specific independent public LiDAR/survey/reference geometry cannot
be found and its license/epoch/resolution verified, explicitly publish
consistency and relative stability rather than unsupported absolute accuracy.
Synthetic known-camera/known-surface sequences can test code and controlled
failure modes but cannot replace the real-world Cornell test.

### Metric scale and georegistration

An ordinary SfM component is determined only up to a similarity transform.
COLMAP `model_aligner` can estimate a robust Sim(3) from at least three camera
center correspondences; the docs' numerical minimum is not a quality standard.
Use spatially distributed, nondegenerate anchors with provenance/uncertainty,
and reserve independent anchors or distances for checks. EXIF GPS is noisy;
map/OSM footprints may be stale or offset; a georeferenced visualization is not
a survey. Do not use the same controls for both alignment and accuracy scoring.
Keep a local ENU frame and preserve its transform to any Earth frame. Until
checks pass, disable meter-accurate measurement claims and show scale unknown.

The evidence release should distinguish reproducible support heuristics from
statistically calibrated uncertainty: calling a score “confidence” does not
make it calibrated. Establish risk-versus-coverage or interval-coverage tests
on held-out/reference data before advertising probabilistic reliability.

## 5. Public visualization architecture and acceptance

Keep the evidence/master package lossless and separate from compressed web
derivatives. Preserve camera/feature/depth/visibility metadata outside meshes.
Use hashed artifacts and a versioned scene manifest so every tour screenshot
identifies a reconstruction, epoch, and level of detail.

For a Quad-sized first release, building/facade chunks with glTF/GLB, explicit
LOD, texture mipmaps, KTX2/BasisU, and mesh compression are a practical starting
point. OGC 3D Tiles becomes useful for spatially streaming a larger campus;
it is not mandatory overhead for the first connected Quad component. Verify
browser/loader extension support and retain a simpler fallback.

Primary specs:

- glTF 2.0: <https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html>.
- KHR_texture_basisu:
  <https://github.com/KhronosGroup/glTF/tree/main/extensions/2.0/Khronos/KHR_texture_basisu>.
- EXT_meshopt_compression:
  <https://github.com/KhronosGroup/glTF/tree/main/extensions/2.0/Vendor/EXT_meshopt_compression>.
- OGC 3D Tiles: <https://www.ogc.org/standard/3dtiles/> and
  <https://github.com/CesiumGS/3d-tiles/tree/main/specification>.

The experience needs two complementary entry modes: a polished 60-90 second
guided campus story and a free explorer. Required controls: orbit/walk,
building bookmarks, collision-safe paths only where geometry is observed,
source-camera photo transitions, measured mesh/appearance/support/missing-data
switches, a clearly dated modern layer, and later a historically qualified
timeline. A guided tour may choose strong viewpoints; it must not imply that
unobserved backsides are recovered. Do not show procedural campus buildings,
map extrusions, generated skies/backgrounds, or aesthetic infill as recovered
data. Optional illustration/context needs separate labeling and must not enter
metric evaluation.

Proposed release targets, to be benchmarked on named real devices/network
profiles and frozen after the pilot:

| Acceptance dimension | Proposed target and evidence |
| --- | --- |
| First interaction | Coarse usable scene <=5 s desktop, <=8 s selected midrange mobile under a documented 20 Mbps profile; cold cache, record p50/p95 |
| Sustained tour | >=30 FPS on named integrated-GPU laptop and midrange phone for a fixed 60 s route; report p95 frame time and dropped frames, not one peak FPS |
| Initial payload | Aim <=15 MB compressed coarse entry; stream detail on demand; no multi-hundred-MB blocking OBJ download |
| Browser memory | Instrument budgets before scaling; initial planning caps ~1 GB desktop / ~400 MB mobile, with adaptive LOD and graceful fallback |
| Reliability | Automated URL/asset/interaction checks plus real Chrome/Firefox/Safari and Android/iOS checks; no JS errors, context-loss loops, or missing attributions |
| Evidence interaction | Random sampled patch-to-photo/source mappings verified; unsupported gaps remain visible in evidence mode; screenshots identify epoch/run |
| Accessibility | Keyboard controls, pause/reduced motion, readable contrast, touch UI, and a non-WebGL image/video/evidence fallback |

These targets are a quality contract proposal, not a claim the present local
viewer meets them. Playwright software WebGL cannot replace mobile GPU profiling.
Public deployment additionally requires HTTPS hosting, CORS/cache configuration,
error monitoring, right-sized CDN/object storage, rollback, a stable URL, and a
download/evidence manifest. A local 127.0.0.1 URL is not a public deployment.

## 6. Rights and release constraints

Public Internet availability is not permission to download at scale,
redistribute originals, publish textures, or train arbitrary models. Source
discovery should distinguish reusable Commons/CC/public-domain files from
research-only archive access and unknown rights. Publish per-item attribution,
license, modifications, source, and share-alike obligations; retain original
rights statements. If reuse cannot be established automatically, quarantine the
asset from the public release rather than assume permission.

Official Commons reuse guidance:
<https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia>.
Cornell Library's footer points to its official guidelines:
<https://hdl.handle.net/1813.001/CULCopyright>.
Those guidelines say copyright/restriction responsibility remains with the
researcher and absence of restrictions is no guarantee of public-domain status.
An accessible IIIF image service is not a redistribution license.

Software licenses also need a release audit, not a blanket claim that every
open-source component is permissive:

- COLMAP is BSD-licensed; third-party dependencies have separate terms:
  <https://github.com/colmap/colmap/blob/main/README.md>.
- OpenMVS is AGPL-3.0; assess the actual modifications/distribution/service
  arrangement, include required notices/source where applicable:
  <https://github.com/cdcseacave/openMVS/blob/master/LICENSE>.
- The original Gaussian Splatting implementation has a research/noncommercial
  license, not a generic permissive software license:
  <https://github.com/graphdeco-inria/gaussian-splatting/blob/main/LICENSE.md>.

This is an engineering flag, not legal advice. Do not contact a rights holder,
buy a license, upload restricted images, or make university branding/media
commitments without separate authorization. A press-ready package can be built;
Cornell publicity and paper acceptance remain external editorial decisions.

## 7. Month-scale engineering gates and resource scenarios

One technically strong full-time lead plus automation is a planning assumption,
not a statement that automation supplies scientific supervision. Research
claims, literature novelty, and publication still require critical review.

| Window | Concrete deliverable | Gate before expanding |
| --- | --- | --- |
| Month 1 | Source/rights inventory, capture groups, per-facade availability, 100-300-group reproducible pilot, environment/compute benchmark | Can public-only data create independent-baseline depth and bridges for >=2 neighboring core buildings? If not, stop promising a full Quad and report the coverage bottleneck without requesting user photos |
| Months 2-3 | One unified modern reference frame; detailed supported facade/ground tiles; conservative mesh and optional appearance layer; first streamed explorer | Per-building coverage is reported; components are not hand-aligned; frozen held-out protocol runs; scale claims are qualified; a second person can reproduce the pilot from manifests |
| Months 3-4 | Evidence graph, temporal/capture grouping, automatic failure detection, research benchmark interface | Existing algorithms are reproduced and weaknesses quantified before new-method claims; benchmark split/compute budgets frozen |
| Months 4-7 | New correspondence/uncertainty/temporal method experiments, ablations, cross-site tests, and qualified historical components | Improvement over strongest fair baseline survives grouped confidence intervals; false geometry and false temporal changes are measured, not hidden |
| Months 7-9 | Full research package, repeatable release, optimized public explorer, guided film, figures, limitations and press kit | Reproduction, rights, geometry-vs-appearance, mobile profiling, and independent research review pass; otherwise extend or release a narrower honest result |

The 6-9+ month research range can lengthen if coverage or novelty fails; a
three-month engineering demo and a PhD-level research contribution are not the
same milestone. Keep the modern component as a standalone valid deliverable if
the historical recovery gate fails. No phase claims an unseen roof can be
measured from unavailable photographs.

| Scenario | Planning hardware/storage | Appropriate scope |
| --- | --- | --- |
| Current local | ~8 GB RAM, CPU-only, ~13 GB free | Pipeline tests, small components, source review, lightweight web QA; not a full detail-rich Quad research run |
| Lean research node | One CUDA GPU with ~24 GB VRAM, 64 GB RAM, 1-2 TB SSD plus backed-up object storage | Tilewise modern reconstruction, one appearance experiment at a time, small frozen ablations; benchmark first |
| Comfortable study | One/two 24-48 GB GPUs, 128 GB RAM, 2-4 TB working SSD and durable originals/artifacts | Parallel components/resolutions, repeated seeds/splits, method ablations, cross-site tests, high-resolution release generation |

Allocate a small benchmark tranche first, e.g. 20-50 GPU-hours, then extrapolate
measured feature/matching/MVS/training throughput, RAM/VRAM, and artifact sizes
per capture group and pixel. A provisional study envelope of hundreds to low
thousands of GPU-hours is a budget scenario, not measured Arts Quad demand or
a vendor quote. Cost model: approved GPU-hour rate x measured/allocated hours
+ persistent storage + backups + egress/hosting; do not fabricate a dollar
total before choosing a provider. Preserve failure logs and cap retries/cost.
Cornell allocation availability and permitted workload are unverified; do not
assume free GPUs, and never run compute on university login nodes.

The limiting factor may be independent imagery, not compute. More GPUs cannot
recover photographs that were never taken, make one camera center triangulate,
or turn publicity goals into scientific novelty.
