# Arts Quad native bridge and calibration audit

Date: 2026-10-24. This is a **read-only diagnostic**, not acceptance of a
two-building scene or a reconstruction improvement by itself. No image labels,
manual correspondence marks, camera edits, model merging or alignment were
fed into the reconstruction. The larger 228-record experiment is separate;
the results below describe the completed 145-record checkpoint only.

## Reproduce

```bash
.venv/bin/python pipeline/analyze_artsquad_bridges.py \
  --run artifacts/artsquad_modern/runs/2b7e3fa97872072dccbd
.venv/bin/python -m unittest discover -s tests -p 'test_artsquad_bridges.py'
```

The first command writes `bridge-analysis.json` alongside the run. It reads
the actual saved native COLMAP folders, not manager return indices. It checks
frozen training hashes and globally disjoint held-out provenance groups, reads
the database in SQLite read-only mode, then checks that the snapshot, report,
native binaries, database and fitted training images did not change. It never
performs pose fitting, triangulation, map merging or geometry modification.

Each camera reports fitted focal / maximum image dimension, SIMPLE_RADIAL `k`,
a weak EXIF35-based focal comparison when available, and a 5x5 image-grid
unprojection/reprojection diagnostic. Each native camera pair reports shared
track count, actual triangulation-angle percentiles, similarity-invariant
baseline / point-distance ratios, exact-original and recorded-family overlap.
Diagnostic thresholds are exported in JSON; none is an acceptance rule.

## What the completed 145-record experiment establishes

The six native components contain **205 verified database pairs**. Twenty-four
pairs have nonempty, disjoint *collection* core labels, but only **two** such
pairs share actual native tracks. Eleven of the 36 component cameras trigger
at least one calibration warning. These counts do not establish eleven wrong
cameras or two genuine cross-building connections.

| Native component | Relevant numerical evidence | Interpretation |
| --- | --- | --- |
| 0 | Goldwin-labelled 18671006 versus McGraw-labelled 69219215: 15 common tracks; 10.21 degree median fitted angle | Their labels do not identify the observed surfaces; the component is already quarantined for a separate capture-epoch conflict. |
| 1 | Five Goldwin-labelled cameras, five recorded families, 737 sparse points; all ten camera pairs share tracks; median pair angles range 1.63–12.92 degrees | Best current local surface candidate; no shared native component with another core building. One camera fails unprojection on part of a 5x5 image grid. This is not whole-facade calibration validation. |
| 2 | Three Morrill-labelled cameras; fitted focal ratios 0.140, 0.658, 1.016; one `k=1.413`; pair median fitted angles 49.48–111.14 degrees | Strong calibration sensitivity candidate, not simply an insufficient-angle case. Large fitted angles do not prove correct shape. Three-view dense fusion was zero. |
| 3 | One overview camera: fitted focal ratio 7.380 and `k=-14.828` | Extreme fitted calibration warning; do not use its apparent spatial arrangement as a campus reference. |
| 4 | Two overview cameras, 45 points; `k=12.652` and `17.736` | Two-camera support, extreme radial strain, and overlapping labels cannot establish two core buildings. |
| 5 | McGraw-labelled versus White-labelled images: 31 common tracks; 13.39 degree median fitted angle; `k=1.871` and `0.701` | Small, suspect repeated-facade association, not an accepted bridge. |

Focal ratios and radial parameters come directly from native models, not from
the viewer or hand positioning. World-frame baselines remain unscaled.
Different recorded families and exact hashes are not verified independent
capture sessions.

## Image-level diagnostic inspection

The following observations explain why metadata counts cannot be used as
multi-building evidence. They are analyst inspection notes, not newly certified
annotations and were not used to change the frozen input, matches or fit.

- `modern__18671006_Cornell_University_arts_quad.jpg`, collected under Goldwin,
  visibly shows a foreground statue and Uris / McGraw Tower rather than a
  Goldwin facade. `modern__69219215_McGraws_in_the_Mist_1131329493.jpg` also shows
  the clock tower plus a nearer tower. Shared clock-tower structure can explain
  the apparent label-disjoint association without reconstructing two core
  buildings.
- The 145-inlier database pair `modern__6338540_Cornell_Morrill_Hall_March09.jpg`
  versus `modern__98978091_CU_Places_White_Hall_West_Front_1.jpg` initially looks
  promising numerically. The first image visibly contains the signed MORRILL
  HALL entrance, the other the signed WHITE HALL entrance; both are cropped,
  highly repetitive stone / arched-window facades, without a visibly common
  structure. This is a strong false-association warning, not a plausible bridge
  solely because RANSAC accepted 145 matches. They did not enter one saved
  native component.
- The component-5 McGraw March09 full-front image and the cropped White West
  Front image similarly show different named buildings with repeated facade
  motifs. The 31 shared fitted tracks are not accepted as physical overlap.
- `modern__65378432_Overview_Cornell_University_Ithaca_New_York.jpg` visibly has
  a hard horizontal sky-strip transition and a hard right-edge strip transition.
  This suggests an edited/composite frame that requires review before treating
  it as an ordinary pinhole photo. This observation is not a certified stitch
  classification. The other component-4 frame is very wide (2400x790), which
  alone is not proof of panorama or invalidity.

The correct next action is to check actual shared feature locations, descriptor
ambiguity, calibration stability and multi-view cycle consistency. An epipolar
inlier count alone is not enough to merge buildings or loosen D0/D1 gates.

## Bounded next experiment: calibration stability, not aesthetic selection

Retain the free-focal/free-radial learned baseline unchanged. On the **same
frozen training selection**, reuse only verified feature/match caches into new
versioned run directories; never reuse fitted poses or insert held-out views.
Run these small CPU mapping variants before spending time on more dense depth:

1. Fixed radial `k=0`, per-image focal initialized from EXIF35 when present or
   the declared default otherwise; allow focal refinement, disable radial
   refinement both in global/local BA and absolute-pose registration.
2. Fixed radial and fixed focal using the same stated initialization. This is
   a **sensitivity stress test**, not a claim that zero distortion or EXIF is
   true. A cropped source can invalidate an EXIF35-derived focal prior.
3. If unknown-focal cameras drive a candidate bridge, declare a small focal
   prior sweep before execution rather than selecting the most attractive
   result afterwards. Keep every variant and its failures.

Compare component memberships, common-camera pair distance ratios, rotation
changes, common feature-track observations, held-out query consistency and
calibration diagnostics. Pose/point comparisons may use an explicitly reported
similarity fit **for diagnostics only**, never to place disconnected components
into the public campus. Fewer fitted points can be a more useful result if an
unsupported bridge disappears. More stable geometry is still not independent
physical truth or proof of complete facade coverage.

Use the larger current snapshot first for genuine overlapping views; the
calibration experiment must not manufacture overlap or repair repeated-facade
matches by calling a shared architectural motif a correspondence. Select the
next dense candidate only after reviewing these reports. No new dense/SfM job
was launched by this audit.

## pycolmap option propagation check

An installed pycolmap 3.13.0 API probe created `IncrementalPipelineOptions`
with focal ratios `.25` / `4.0` and maximum extra parameter `.5`. Its stored
`mapper` and `triangulation` representations still showed default `.1` / `10`
and `1`, but **`get_mapper()` and `get_triangulation()` returned the correctly
propagated `.25` / `4.0` / `.5`**. Thus the nested repr is not evidence that
pipeline bounds were ignored. Final fitted parameters nevertheless need a
post-fit audit; an option setting or successful native process exit is not a
camera-calibration validation.

## Executable same-snapshot sensitivity runner

`pipeline/run_artsquad_calibration_variant.py` implements the two declared
variants in new, content-identified run directories. Example commands (native
mapping must not be run concurrently with another memory-intensive CPU pilot):

```bash
.venv/bin/python pipeline/run_artsquad_calibration_variant.py \
  --source-run artifacts/artsquad_modern/runs/2b7e3fa97872072dccbd \
  --variant fixed-radial --run-label calibration-check-1
.venv/bin/python pipeline/run_artsquad_calibration_variant.py \
  --source-run artifacts/artsquad_modern/runs/2b7e3fa97872072dccbd \
  --variant fixed-intrinsics --run-label calibration-check-1
```

These examples are executable instructions, **not claims that their mappings
were executed during this audit**. Fifteen focused tests cover the runner;
twenty-one cover the bridge analyzer. The runner deliberately requires the
baseline database's **initial** SIMPLE_RADIAL `k` to be zero already: this is
true of the checked 145-record baseline. Reusing verified E/F/pairwise poses
after changing a nonzero verification-time calibration would be a different
experiment and is rejected instead of silently carrying over incompatible
geometry. Database-initial focal and principal point are logged camera by
camera; no final fitted native intrinsics are used for initialization.

The source and variant must share the exact frozen snapshot hash and admitted
training names/bytes. A byte-identical copy of the verified database retains
its training features, inlier matches and two-view geometry; those logical
tables are checked unchanged. Position priors are cleared. No baseline fitted
global pose or point model is copied. Descriptor caches are copied through the
existing fully validated group-level helper for later holdout compatibility.
Source database/model/cache/image hashes are checked unchanged, while actual
saved variant camera parameters are checked for fixed `k`, principal point
and, in fixed-intrinsics mode, focal length. A terminal native return with no
model stays a negative result; parameter freezing is not calibration truth.
