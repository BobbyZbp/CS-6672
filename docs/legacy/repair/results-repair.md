# GhostMap surface repair experiments

The v1 CPU-CUDA blocker has been removed. The implemented path is COLMAP
camera estimation and undistortion, followed by CPU OpenMVS PatchMatch,
multi-view consistency, dense fusion, and actual photo-textured facets.

## Measured outputs

| Experiment | Cameras | Sparse points | Fused depth points | Dense mesh faces | Conservative facets |
| --- | ---: | ---: | ---: | ---: | ---: |
| Modern, higher stereo resolution | 22 | 2,181 | 171,351 | 262,042 | 270,852 |
| Modern Uris/McGraw control | 22 | 2,181 | 67,122 | 111,733 | 94,600 |
| Historical, fixed focal / image width 0.8 | 17 | 1,143 | 6,101 | 8,844 | 7,205 |
| Historical, fixed focal / image width 1.2 | 15 | 659 | 6,440 | 8,134 | 9,322 |
| Historical with Cornell archives, fixed focal 0.8 | 18 | 821 | 5,269 | 8,428 | 6,928 |
| Building-mask + 1600px stereo, focal 0.8 | 16 | 900 | 20,555 | 32,632 | 32,954 |
| Building-mask + 1600px stereo, focal 1.2 | 17 | 830 | 13,702 | 18,046 | 22,492 |
| Historical, unconstrained focal | 17 | 1,132 | 49,067 | 2,422 | rejected calibration |

The unconstrained model optimizes some focal ratios to 9,747 and 1,937,825.
Its low reprojection error is therefore misleading. It remains visible only as
an explicitly rejected calibration experiment.

Across 460 shared feature tracks, the 0.8 and 1.2 prior models differ by a median
10.6% of the scene radius after robust similarity alignment; the 0.8 and 1.8
models differ by 21.2% across 228 shared tracks. This measures calibration
sensitivity, not ground-truth error. `focal-geometry-sensitivity.json` retains
the complete comparison.

## Surface support and visualization

A final integration check found that OpenMVS interface-format MVS files can
retain sparse points even after a separate dense PLY is exported. The mesher
now receives `--pointcloud-file dense.ply` explicitly. The validation script
checks the native mesher log against the dense PLY vertex count, so the mesh
cannot silently fall back to sparse SfM points. The modern high-resolution
model uses all 171,351 dense input points and produces 262,042 faces.

OpenMVS graph-cut envelopes can span poorly observed regions. An additional
conservative mesher now uses only fused depth observations. Each local facet
requires three-view support at every vertex, two common supporting views across
all corners, normal agreement, a maximum projected edge of 12 pixels, and an
edge length below 3% of local depth. A facet uses the majority reference view
of its corners; gaps without local stereo support remain open. Every mesh vertex comes directly from the fused
stereo cloud, with no added architectural geometry. Textures are sampled from
the real calibrated source photograph.

The default dense mesh uses a calibrated-camera texture export while preserving
its vertices and facets exactly. A source photograph is eligible only if all
three nearest fused stereo vertices share that view, the facet faces the
camera, and its projected corners are inside the photograph. Unsupported faces
are gray. The modern high-resolution model has 254,161 photograph-textured
facets and 7,881 untextured facets. The raw OpenMVS atlas and the conservative
local-facet alternative remain in the download for audit.

The Surface Lab exposes texture/solid/wireframe display, recovered photo
viewpoints, mesh downloads, source images, and training-camera projection
figures. It is a local research viewer, not certification of recovered complete
architecture. There is no metric ground truth, and independent held-out
geometric validation remains outstanding. Historical coverage is fragmented,
particularly around the roof and occluded facades.

## Primary-source method review

See `noah-method-audit.md`. Both Snavely chronology papers start from usable
multi-view geometry; NeuSC explicitly models primarily static geometry and
time-varying appearance. Its assumptions do not by themselves solve building
demolition. The repair adopts its dense preprocessing and view filtering while
keeping historical and modern surface estimation separate.

## Additional Cornell archive acquisition

The official Cornell viewer exposes public IIIF image services. A new adapter
retrieved 10 research scans, preserves the catalog and rights statements, and
automatically excludes portrait/interior metadata from exterior reconstruction.
Seven eligible archival images expand the target set from 19 to 26. These
research inputs remain separate from the redistributable Commons manifest.

The expanded reconstruction registered 18 of 26 images, including Cornell's
1958 Boardman photograph and its 1890s campus view, producing 821 sparse points
with a mean reprojection residual of 1.228 px under the 0.8 focal prior. Five of
the seven new exterior records did not enter this component. The result is
reported directly rather than treating every acquired image as useful evidence.

## Automatic semantic filtering

Following the foreground-filtering idea in NeuSC's custom-data preprocessing,
an automatic CLIPSeg building/vegetation/sky mask filters both cached
SuperPoint/LightGlue correspondences and dense stereo pixels. The pinned model
revision is recorded in `artifacts/masked_target_v3/report.json`. No per-image
manual masks or annotations are supplied. Printed scan borders are excluded
with one fixed rule. Correspondences decrease from 23,411 to 13,199.

The combined masked + higher-resolution historical configuration produces
20,555 or 13,702 fused points under the two focal priors. This comparison
changes both masking and stereo resolution relative to the earlier low-memory
run, so the point-count difference is not attributed solely to masking.
Shared-track geometry still differs by a median 11.2% of scene radius after
similarity alignment. Semantic filtering improves input targeting but does not
certify camera calibration, unseen facades, or metric accuracy.

## Repeated-exposure screen and stricter historical display

Global homography fitting and warped high-pass image correlation flag four
pairs in two possible same-exposure groups. One group contains three differently
colored Boardman postcard versions, the other two library / Boardman scans.
The thresholds are exploratory screening rules, not a preregistered benchmark.
A nonflagged pair is not certified independent, and a planar scene can also
correlate; retain all pair measurements in `artifacts/exposure-audit.json`.

Grouping these candidates reduces 16 / 17 registered files to 13 / 14 candidate
exposure groups. Only 11,131 / 4,107 of the fused vertices have at least three
group labels. Camera/depth geometry has not been re-estimated after grouping.
The historical default display now requires three candidate groups per vertex,
two common groups per facet, and the existing local edge / normal rules. It
contains 16,955 / 6,722 facets with unchanged stereo vertices. These are
screened partial surfaces, not a verified complete building. The full native
meshes remain available as diagnostic alternatives.

Browser verification loads all seven experiments, the local-support variants,
photo viewpoints, display modes, and a 390px mobile layout. Passing these
software checks does not establish reconstruction accuracy.
