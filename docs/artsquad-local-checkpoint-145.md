# Arts Quad local CPU checkpoint — 145 frozen records

Date: 2026-10-24. This records a completed **small-scale engineering and
reconstruction experiment**, not D0, D1 or the completed GhostMap project.
The user confirmed that no GPU is currently available: continue local data
work and small-scale CPU validation. No purchase, remote submission or public
hosting deployment was performed. The original project dates and seven-core
building scope remain unchanged; their feasibility is not guaranteed by this
checkpoint.

## Reproducible inputs and run identity

- Frozen snapshot: `artifacts/artsquad_modern/snapshots/b43ad69e17eab9af2734acbf/snapshot.json`.
- Learned SfM run: `artifacts/artsquad_modern/runs/2b7e3fa97872072dccbd/`.
- Native SIFT baseline: `artifacts/artsquad_modern/runs/4b9a7fc66cce07aaf436/`.
- Software: CPU PyTorch 2.14.1, pycolmap 3.13.0, hloc/SuperPoint/LightGlue,
  NetVLAD retrieval, OpenMVS CPU. Reference cameras use per-image SIMPLE_RADIAL.
- Local machine: approximately 7.65 GiB RAM, no available CUDA. High-resolution
  full-campus processing is not authorized or implied by the future resource plan.

The frozen metadata inventory has 145 source records: 142 pass file/date/metadata
checks, 97 are exterior/context candidates, 77 are training images and 20 are
held-out images. Forty-five records are excluded and three rejected. The 58
recorded metadata source families are **not certified independent exposures**.
The 20.6% file holdout is slightly outside the requested 15–20% interval because
of source-family and target constraints. A perceptual-copy candidate remains
unresolved. These are provisional split diagnostics, not an independence claim.
Collection can continue separately; later downloads are not silently included
in this fitted model or these counts.

## What actually reconstructed

The learned pipeline tested 443 candidate pairs: 205 geometrically verified,
204 nondegenerate. Native COLMAP saved six separate components. They have not
been aligned into a synthetic campus.

| Saved component | Cameras | Sparse points | Collection labels, not validated identity | Current display |
| --- | ---: | ---: | --- | --- |
| 0 | 21 | 2,686 | Primarily Uris / tower | Quarantined: one capture-epoch conflict |
| 1 | 5 | 737 | Goldwin Smith | Measured local surface fragments |
| 2 | 3 | 275 | Morrill | Sparse diagnostic; zero dense fusion |
| 3 | 3 | 256 | Tower / Goldwin | Sparse diagnostic |
| 4 | 2 | 45 | McGraw Hall / White | Sparse diagnostic; no accepted connection |
| 5 | 2 | 31 | McGraw Hall / White | Sparse diagnostic; no accepted connection |

Component 1 produced **15,502 fused depth points** and a native 20,086-face
surface candidate. The public workbench instead shows **26,433 local facets**
using 15,079 of the unchanged dense vertices. Facets are local triangulations,
not a newly observed point cloud; their count cannot be compared as a quality
score against the native mesh. The screen requires three recorded source
families per vertex, two common families per facet, bounded projected edge
length and depth-relative edge length. It does not certify independent captures,
calibration, depth accuracy, complete facades or building identity. Broad
volumetric envelopes remain offline rather than becoming a gray replacement
building. Unknown regions remain missing.

Component 2 produced **zero** points under three-view depth fusion. OpenMVS
returned exit code zero but wrote no dense PLY; its MVS interface still contained
sparse points. The pipeline now explicitly recognizes this negative result and
does not mesh the retained sparse points or claim that an execution return code
means a surface was recovered. The earlier error report is preserved.

The native SIFT baseline used the same 77 training images, but tested 2,926
exhaustive pairs rather than retrieval's 443. It produced 43 verified pairs,
36 nondegenerate pairs, an eight-camera Uris component with 2,093 sparse points,
and a three-camera Goldwin-labelled component with 30 sparse points. Its
97.68-second runtime and the learned run's cached runtime are **not an
equal-compute scientific comparison**.

## Source and validation checks

Each displayed local facet has an index linking its texture camera and the
common estimated MVS-visible photographs of its three vertices. The workbench
can snap to actual recovered camera intrinsics/poses and open these source
photos. Visibility records are fitted-MVS estimates, not external geometric
ground truth. Source-family labels remain uncertain.

Query-only localization evaluated 20 held-out images against component 1.
One Goldwin-labelled photo yielded a consistency candidate with 264 inlier
keypoints and approximately 4.00 px median fitted reprojection residual
(8.94 px at the 95th percentile). Other queries cover different buildings:
`1/20` is not an Arts Quad localization accuracy statistic. Query poses and
features do not enter the reference reconstruction, depth or texture fitting;
map/database/feature hashes were unchanged. Unknown focal estimation and lack
of independent query poses mean that this result **does not establish physical
accuracy**.

A metadata conflict was found in a training image titled
`Cornell University, Ithaca, New York (1996)`: its metadata asserts a 2005
capture date. This may be a digitization date rather than the original exposure;
neither date is treated as certified. Preparation policy 5 rejects such
unresolved pre-modern caption/date conflicts in future snapshots. The old
snapshot and native experiment are immutable; the publisher quarantines the
entire affected component 0 instead of removing one camera and relabeling its
old geometry as a modern-only reconstruction.

A native API identity issue was also corrected: returned ReconstructionManager
keys are not necessarily saved directory IDs. Diagnostic reports are now
derived from the actual saved model directories and publication checks native
camera identities and counts. Earlier reports are archived by SHA-256; native
model binaries and poses were not rewritten.

## Interactive deliverable and checks

Local workbench: `http://127.0.0.1:8080/artsquad.html` (existing local server).
The measured Goldwin-labelled fragment component is the default. Other
components remain separate, clearly marked diagnostics. The viewer provides
orbit/zoom, texture/wireframe, camera selection, source photographs, per-facet
visibility records, seven executed pipeline stages, source rights records,
native COLMAP model downloads and a source-only reproduction ZIP.

The focused regression suite passed **213 tests**. Tests cover preparation, split boundaries, native model identity,
cache isolation, holdout non-mutation, dense support, local-facet dependencies,
safe publication and fail-closed milestone evaluation. Browser functional QA
loads actual assets and tests source-camera picking, per-facet source buttons,
links, error/empty states and a 390 px layout. Its machine-readable result is
`artifacts/browser-qa/artsquad/report.json`; the actual five displayed components
passed with no JavaScript errors or failed HTTP responses. A cached-image
timing assertion was corrected to wait for a visible, decoded image and check
its selected-camera URL. Headless software WebGL is **not** a
real-device FPS, 20 Mbps cold-cache or five-second loading certification.

## What remains before D0/D1

There is still no accepted reconstruction of two adjacent core buildings in
one supported coordinate frame, no complete detailed building, no independently
validated Cornell geometry, no accepted environment surface and no certified
metric scale. D0/D1 and all later milestones remain pending. HTTPS publication,
rights review, a 45–60-second actual demo film and real-device performance
acceptance remain unfinished.

The immediate bottleneck is **usable overlapping multiview data**, not adding
surface counts or styling the workbench. Continue provider-compliant collection,
caption/EXIF and exposure checks, candidate overlap analysis and bounded CPU
experiments. The separate
[`artsquad-additional-data-sources.md`](artsquad-additional-data-sources.md)
records original Quad6K/DISCO and PhotoCity leads, their access/licensing
uncertainties and storage limits. Original project data or geometry is not our
reconstruction, and neither unverified archive delivery nor permission to
redistribute those photographs is assumed.
