# Arts Quad first measured pilot — 2026-10-24

**Result: executable pipeline and real diagnostic assets; D0/D1 NOT achieved.**
No adjacent core buildings are yet connected by a validated observation frame.
No accepted complete building, metric accuracy or public HTTPS delivery is
claimed. The seven-building target and 2026-11-21–12-05 D1 window are unchanged.

## Fixed inputs and provenance

Snapshot `f27fe368e880c774a3506ea1` contains 96 acquired records: 93 pass file,
date and metadata checks; 56 are ordinary exterior/context candidates; 46 train
and 10 test files are separated by conservative metadata source families.
37 role exclusions and three upload-date rejections are retained. Distinct
hashes/family IDs do not certify independent observations. See
`docs/artsquad-data-checkpoint.md` and the immutable snapshot's `role-audit.json`.

## Actual geometry and baselines

Learned run: `artifacts/artsquad_modern/runs/8563d895061e27cba81f/`.
Train-only NetVLAD / SuperPoint / LightGlue / COLMAP: 261 candidate pairs,
119 verified pairs, 118 epipolar nondegenerate configurations. Three native
components are preserved, not artificially placed in a campus coordinate frame.

| Photo-set metadata | Recovered cameras | Sparse points | Fused depth points | Native mesh faces | Interpretation |
| --- | ---: | ---: | ---: | ---: | --- |
| Morrill | 4 | 347 | 332 | 239 | Dense support is far too thin for the requested facade/demo; only two recorded source families support its fused points. |
| Goldwin Smith | 3 | 364 | 7,225 | 8,522 | Partial surface candidate only. The input includes an AD White statue view; facade/target identity and completeness are unvalidated. |
| Uris / McGraw Tower | 13 | 2,159 | Not run in this pilot | Not run | Southern reference only; does not count as a core building. |

The two dense experiments used COLMAP-undistorted cameras and OpenMVS CPU,
1280px maximum stereo resolution, three-view fusion, no artificial tower points
and no hole filling. The mesher explicitly consumed the fused dense cloud.
Camera-projected texturing preserved measured mesh coordinates; regions with
no qualified texture photograph remain gray. This does not certify every mesh
face as independently observed. Dense-support reports retain recorded camera,
exposure/family and capture-time diagnostics without changing geometry.

The raw native envelopes were visually unsuitable and are **not the default
web surfaces**. A conservative recorded-source-family screen retained 12,514
strictly local Goldwin-source facets using 7,167 of the 7,225 measured dense
vertices. These show pediment/column/window fragments, not a whole building.
Every displayed triangle now has an estimated common-image visibility index
and clickable source photographs. The three-family-per-vertex/two-common-family
screen is a conservative engineering diagnostic, not a final independence or
accuracy theorem. Morrill has only two recorded source families and zero
eligible facets under this screen; only its sparse diagnostic remains visible.
The raw cloud and envelope remain preserved offline. No gray hull is substituted
when this screen fails.

Classic baseline: `artifacts/artsquad_modern/runs/520962691464472f0e20/`.
The same 46 train files with native CPU SIFT/COLMAP yielded 31 verified pairs
and one 8-camera Uris/Tower component with 2,093 points; no core component was
retained. Runtime was 38.93 seconds on this machine. SIFT used 1,035 exhaustive
pairs and a nominal 4096-feature/1200px budget; actual SIFT counts can exceed
the detector's requested cap. Learned matching used retrieval pairs and cached
work. **This is not an equal-compute scientific comparison or a method-win
claim.** Both raw baselines and failures remain available for later equalized
experiments.

## Query-only holdout check

The ten test photographs were localized against the Morrill-source component
without changing the reference database, native models or training features;
their SHA256 values were unchanged. Exactly one query was a consistency
candidate: the Morrill western-face photo, with 98 inliers, median fitted
residual 3.44px and p95 8.15px. Other queries include different buildings not
expected to be visible in this component; 1/10 is not a whole-quad coverage or
accuracy score. Some unrelated queries fit three matches with almost zero
residual and were rejected for insufficient support. This demonstrates why
small residuals alone cannot establish localization or geometry correctness.

PnP estimates the test pose from the fitted reference map. These are
localization-consistency diagnostics, **not independent camera/surface truth**,
and do not pass any milestone. Report:
`holdouts/2-423fdeab75341b3b6551/report.json` under the learned run.

## Engineering verification and preserved failures

The new atlas shows actual measured components separately, calibrated
undistorted photos, wire/normal views, texture-photo clicks and source/rights
records. Browser QA exercises the real assets, source-camera controls, safe
downloads, unavailable/empty states and 390px layout. Software WebGL is not
real-device FPS/cold-load acceptance. The earlier seven surface experiments
and v1 audit remain available separately.

After supported-only publication, 202 focused tests passed, including native
API smoke and face-order/source-visibility checks. Actual browser QA passed
supported mesh, sparse diagnostics, stationary calibrated picking, per-face
photo selection, download links, empty/error states and mobile layout with no
page errors or failed HTTP requests. These are software checks, not independent
geometric or performance acceptance.

Native integration uncovered and fixed canonical symlink image-name changes,
the installed camera-model enum API, automatic rejection of sub-ten-camera
components, and a missing parent directory before undistortion. Browser
inspection also found that stationary clicks incorrectly replaced calibrated
projection before picking; clicks now retain K and actual-facet regression
checks the selected texture camera. Failed run reports and caches were
preserved; only hash/config-verified train descriptors and match groups were
reused, never native geometry across snapshots.

## What remains before a real demo

The immediate problem is public data coverage and geometric support, not page
styling. Establish a credible connected pair of adjacent core buildings,
acquire missing independent views, validate calibration/identity/support and
holdouts, reconstruct detailed observed environment, then optimize streaming.
No release pass is authored from these point/face counts.

The current environment has CPU-only torch/pycolmap, 7.65 GiB host RAM and about
11–12 GiB free working disk. A usable authorized research GPU/storage node,
verified HTTPS destination, real-device benchmark, 45–60 second demo film and
public-asset rights review remain outstanding. Nothing has been purchased,
submitted to a cluster, emailed to a dataset owner or deployed externally.

The new public-dataset leads, if independently verified, are documented in
`docs/artsquad-additional-data-sources.md`; metadata, historic screenshots and
old downloadable models are never counted as newly acquired/reconstructed
scene geometry.
