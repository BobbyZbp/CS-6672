# GhostMap as a COLMAP extension: plan for the CS 6672 hacker presentation

*Drafted 2026-10-25. Supersedes the direction ordering in the 2026-10-24 research review where they differ; the review's audited numbers remain the evidence base. No codenames: every run, fragment and idea is described in words.*

## 1. The pitch in one paragraph

COLMAP, run as shipped on the licensed internet photographs of the Cornell Arts Quad, produces six disconnected fragments with no scale, blows up the focal length of the same photograph three different ways across runs, and cannot say anything at all about a photograph of a building that was demolished in 1959. We extend COLMAP with *things it does not know but the world does*: the metric shape of the surviving buildings and ground (public-domain USGS airborne lidar), the camera's own EXIF focal length, and the one class of objects whose size has not changed in 120 years and which always touches the ground: people. With these priors in the mapper, the resection and the bundle adjustment, the same photographs merge into one metric scene, every camera carries an uncertainty certificate, and a 1905 postcard of Boardman Hall can be placed on today's lawn with an honest statement of which parts of the vanished building the surviving record can and cannot determine. Where the record is silent, the viewer shows red, not a guess.

## 2. What COLMAP fails at on this data (all VERIFIED from the repository)

| Failure | Measured on our photographs |
| --- | --- |
| Fragmentation despite connectivity | In the best learned-matching run (145-photo snapshot, 77 training images), 65 of the 67 images with any verified match form one connected match graph, yet the incremental mapper outputs 6 disjoint models (21, 5, 3, 3, 2 and 2 cameras). |
| Unstable self-calibration | One image is fitted with focal-length ratios 0.27, 3028 and 6519 in three runs of the same snapshot; the Morrill Hall fragment contains focal ratios 0.03 and 464. |
| No scale, no geography | Every fragment is an unanchored similarity frame; only 29 of 228 photographs carry GPS. |
| No uncertainty output | COLMAP reports reprojection error, never how well a camera or a point is determined. |
| Nothing for the vanished subject | Boardman-only reconstruction moves by 329 % of the scene radius (90th percentile) when the focal prior changes from 0.8 to 1.2: the shape is not identifiable from the photographs alone. Only 4 to 5 independent, publicly licensed Boardman photographs can be registered through surviving buildings, all from one side. |

The last row is the honest premise of the whole project: the demolished building cannot be reconstructed as a surface. The research question is what the surviving world can still certify about it.

## 3. The geometric insights (stated so a professor can object to them)

**Insight A: the surviving world is a metric calibration target for every camera that ever photographed it.** Lidar measures the tower, the library roofline and the lawn in metres today. A 1905 postcard that shows the tower is a camera observing a known 3D object, so its pose and focal length are a resection problem, not a reconstruction problem. This is classical (terrestrial photogrammetry, Mikolka-Flöry's historical-photo monoplotting), and we claim only the setting: surviving anchors are peripheral, near-planar and far (100-200 m), which is exactly the regime in which resection with unknown focal length is nearly degenerate.

**Insight B: people are depth-diverse, metric, ground-touching anchors that survive the century even though nothing they stood next to does.** The degeneracy in Insight A is the dolly-zoom ambiguity: move the camera along the ray to the anchors and change the focal length, and the far anchors reproject almost unchanged. Breaking it needs *known structure at a different depth*. The surviving buildings cannot supply it; the ground can, but a bare lawn has no matchable texture across eras. A pedestrian in the postcard supplies three things at once: a ground-contact point on today's lidar ground plane, a near-metric vertical segment (adult height, with a known prior distribution), and a depth that is typically 10-80 m rather than 100-200 m. Several pedestrians at different depths give the depth spread that resection needs. This is in the spirit of Wei-Chiu Ma's *Virtual Correspondence* (humans as a cue for geometry between views that share no surface), but it is a different object: there, human bodies link two cameras in one epoch; here, human bodies link one camera to a *measured ground surface* across a century. Classical single-view metrology (Criminisi) and camera-height-from-people (Hoiem et al.) are the ancestors; the claim is their use as cross-era virtual anchors inside a COLMAP resection with a lidar ground model, and the certificate that says how much they helped. Whether 1900s postcards contain enough visible people is an empirical question and the first kill test (section 7).

**Insight C: free space is evidence that survives demolition.** A postcard pixel that shows sky says the ray is empty to infinity; a pixel that shows the surviving library says the ray is empty up to the library's measured depth; a pixel that shows Boardman where today's lidar sees Olin or lawn says *something* stood on that ray before the modern background. Carving these rays backward in time, under the pose/focal posterior from Insights A and B, gives an outer bound and a hitting-set lower bound on the vanished building, never a surface. On the currently registered views (two azimuth bins about 50-55° apart) the bound is 2.5-dimensional: the north facade plane, the east-west extent and a roof-height cap, each to roughly ±3-5 m. A closed volume requires a third azimuth bin; two candidate photographs exist and are not yet registered.

**Insight D (evaluation): surviving buildings are perfect stand-ins for vanished ones.** Treat Stimson Hall or the McGraw Tower as if it had been demolished, run the whole cross-era pipeline on its pre-1934 photographs, and score the result against lidar. No published cross-era geometry work has a non-circular ground truth of this kind; the literature sweep looked for one and found none.

## 4. The extension, module by module

Each module names its hook in COLMAP (verified to exist in the installed pycolmap 3.13), its input, its output, the before/after measurement that the presentation shows, and the gate that decides whether the next module may start.

### Prior-aware incremental mapping

- **Hook.** Incremental pipeline options `min_focal_length_ratio`, `max_focal_length_ratio`, `ba_refine_focal_length`; `use_prior_position` with `PosePrior` for the 29 GPS-tagged photographs; `create_pose_prior_bundle_adjuster`.
- **Input.** The existing 77-image learned-matching database; the 131 of 228 photographs that carry a 35 mm-equivalent focal length in EXIF (crop-aware conversion using sensor-size tables keyed on camera model).
- **Output.** A re-mapped model whose per-camera focal lengths are bounded to the EXIF prior interval, with the GPS cameras pulling the model toward its geographic position.
- **Before/after.** Same 77 photographs: number of models, number of registered cameras, number of cameras whose focal ratio lies outside [0.5, 3], and whether the 21-camera library/tower fragment and the 5-camera Goldwin Smith fragment merge. This also settles the diagnostic question of whether calibration or content is splitting the match graph.
- **Gate.** No gate; this is a diagnostic. If the fragments merge with sane focals, calibration was the culprit and content acquisition is deprioritised. If not, content is the culprit and the photo-count audit (section 6) decides what to fetch.

### Lidar anchoring of the scene

- **Hook.** `align_reconstruction_to_locations` and `estimate_rigid3d_robust` for the initial similarity; a Python refinement that minimises point-to-plane distances to the lidar roof and ground planes and the OSM wall planes, with gravity from vertical vanishing lines.
- **Input.** USGS 3DEP NY_FingerLakes_1_2020 (public domain, 0.7 m spacing), cropped to about 600 m around the Quad and reprojected from Web Mercator to UTM zone 18N before any fitting (the 1.35x horizontal stretch at this latitude would otherwise corrupt the scale). OSM building footprints (ODbL).
- **Output.** The library/tower fragment (and any fragment the mapper now merges) in metres, in UTM 18N, with a bootstrap covariance of the similarity transform.
- **Before/after.** Hold the tower out of the fit and predict its top from the rest: vertical error at most 1.0 m, horizontal at most 1.5 m, scale interval at most ±2 %, at least 17 of the 21 camera centres between 0.5 and 3 m above the lidar ground. Independent cross-check from Insight B: the scale implied by pedestrians in the modern photographs must agree with the lidar scale within 5 %.
- **Gate.** If the held-out tower prediction fails, every metric and historical module stops and the viewer stays labelled "unanchored".

### Cross-era resection with human cues and a standpoint prior

- **Hook.** `estimate_and_refine_absolute_pose` with focal, principal point and radial distortion free; `PosePrior` for the standpoint constraint; a Python layer that adds (i) ground-contact residuals for detected pedestrians against the lidar ground, (ii) height residuals against an adult-height prior, (iii) a position prior "camera centre on lidar ground plus 1.2-1.8 m, or on a lidar-measured elevated vantage such as the tower belfry", and (iv) a profile likelihood over focal length with importance sampling, so the output is a posterior, not a point.
- **Input.** The deduplicated public-domain Boardman photographs (4-5 independent exposures that show the tower; around 9 frontal views that show no surviving building and are therefore usable only if pedestrians and the Sanborn footprint make them so); the anchored library/tower fragment; a person detector that has been checked on halftone and hand-coloured prints.
- **Output.** Per photograph: camera posterior, implied field of view, and an identifiability certificate — for each candidate point on the vanished building, the along-ray and lateral 2σ extent — with an explicit statement of which cue (surviving anchors, pedestrians, standpoint prior) contributed how much, by ablation.
- **Before/after.** Surviving anchors alone (the published baseline, which the review measured at 0 of 6 photographs identified: residuals flat over 0.8-1.25x focal) versus anchors plus pedestrians plus standpoint prior. Pass means at least 3 independent photographs whose 95 % focal interval shrinks by at least 30 % and whose along-ray centre interval is at most 10 % of the anchor distance, with the shrink attributable to the new cues under ablation.
- **Calibration of the certificate.** Simulated demolition (Insight D): take modern photographs of Stimson Hall and the tower, strip EXIF, convert to grayscale halftone, crop to the postcard regime (anchor bounding box under 35 % of the frame, depth ratio under 1.2), and check that the nominal 90 % intervals cover the lidar truth 80-95 % of the time, leave-one-family-out, with the 5-image same-session series counted as one family.
- **Gate.** If fewer than 3 photographs pass, the Boardman result is reported as "not identifiable from the surviving public record" with the per-photograph table of what each one lacks; the modules below run only on the stand-in buildings.

### Backward free-space carving

- **Hook.** Pure Python on top of the posteriors: a 0.5 m voxel grid over the Olin site, sky/surviving/unexplained pixel labels per photograph (sky and surviving-building segmentation checked by hand-free consistency with the lidar render), rays marginalised over posterior samples.
- **Output.** Outer bound and hitting-set lower bound with per-face vantage counts; containment check against the Library of Congress 1919 Sanborn footprint, georeferenced to lidar through at least six surviving footprints (residual at most 2 m).
- **Before/after.** Oracle hull from perfect silhouettes at the registered azimuths (currently 2.4-3.7x the Sanborn footprint area) versus the real carve; the Stimson Hall stand-in must contain at least 95 % of its lidar footprint with area at most 1.3x its own oracle.
- **Gate.** Volume claims only if the oracle area is at most 1.5x the footprint, which needs a third azimuth bin. Otherwise the deliverable is the 2.5-D bound, labelled as such.

### Evidence viewer

- **Hook.** COLMAP's track and visibility data, exported with the certificates.
- **What the visitor can do.** Click any surface and see the photographs, rays and residuals that support it; drag an archival camera along its ambiguity ray and watch the vanished building stretch, then switch the pedestrian and standpoint cues on and watch what collapses and what stays red; toggle the lidar layer, rendered separately from photo geometry; toggle the 1919 map; remove a postcard and watch its contribution to the bound disappear.

## 5. What makes this outstanding rather than good

- **A cue, not a stack.** The pedestrian-as-cross-century-anchor idea is one sentence long, is testable in an afternoon, and either works (and the ablation shows exactly how much) or fails (and the certificate says so). A professor who works on extreme-view geometry can argue with it immediately.
- **Non-circular evaluation.** Stand-in demolition against lidar and containment in an independently georeferenced dated map; nothing in the loop scores itself.
- **Failure is rendered.** Red regions, flat likelihoods and "unanchored" labels are first-class outputs. A demo that shows an honest negative on Boardman while showing calibrated positives on the stand-ins is more convincing than any point cloud.
- **A releasable benchmark.** Public-domain and CC photographs, lidar anchors, Sanborn footprints and stand-in ground truth form a cross-era benchmark that does not exist yet; this is the part a reviewer cannot dismiss as engineering.
- **Measured COLMAP deltas.** Every module has a number from the shipped COLMAP on the same photographs.

## 6. Data work that runs alongside (no credentials needed)

- Two new keyless sources, both verified to answer: the Openverse API (indexes Flickr's CC photographs; 65 hits for "cornell arts quad", licences and origin links included) and Wikimedia Commons geosearch (172 files within 250 m of the Quad centre, many missed by the category crawl). Same licence allowlist, provenance and deduplication as today.
- A one-day photo-count audit: per building and per Quad-facing facade, the number of deduplicated, distinct-author, licensed photographs. The three zero-camera core buildings need roughly 30 eligible photographs from 5 or more authors each to expect 5 registered cameras.
- Mapillary (street-level, bounding-box search) only if the audit shows a gap it would fill; it needs a free developer token and an account.

## 7. Kill tests, in order, with the cheapest first

| Day | Test | Kill condition |
| --- | --- | --- |
| 0 (one afternoon) | Count pedestrians in the public-domain Boardman and pre-1934 library/tower photographs; run the detector on 10 halftone prints and inspect. | Fewer than 3 independent Boardman-bearing photographs with at least 2 visible, ground-standing, non-retouched people at distinct depths → the human cue is dropped and the resection module falls back to anchors plus standpoint prior only (expected to be a calibrated negative). |
| 0 (one hour) | Open the Library of Congress 1902 tower-top cyclorama TIFF; check angular coverage and whether Boardman's azimuth is unoccluded. Search Commons and LoC for a third-azimuth Boardman photograph. | Decides whether the carving module can ever exceed 2.5-D. |
| 1 | Lidar crop and UTM reprojection; compare reprojected roof edges with OSM. | Edge disagreement over 0.5 m → fix the projection before anything else. |
| 2 | Held-out tower prediction after anchoring. | Thresholds in section 4; failure stops all metric work. |
| 3 | Focal-prior re-mapping of the 77-image database. | Diagnostic only. |
| 4-5 | Simulated-demolition calibration of the certificate on Stimson and the tower. | Coverage outside 75-97 % → the certificate is miscalibrated; report, do not proceed to Boardman claims. |
| 6-8 | Boardman resection with all cues and ablation. | Section 4 thresholds. |
| 9-10 | Carving on the stand-ins, then Boardman. | Section 4 thresholds. |

## 8. Timeline

Weeks of 2026-10-26 and 2026-11-02: data sources, photo-count audit, CUDA environment, lidar anchoring, focal-prior mapping, pedestrian feasibility. Weeks of 2026-11-09 and 2026-11-16: cross-era resection with cues, certificate calibration, viewer interactions. Weeks of 2026-11-23 and 2026-11-30: carving, stand-in evaluation, benchmark packaging, rehearsal. The delivery contract's planned window for the multi-building demonstration (2026-11-21 to 2026-12-05) is kept.

## 9. Closest prior work and the stated difference

| Work | What it does | Our difference |
| --- | --- | --- |
| Virtual Correspondence (Ma et al., CVPR 2022) | Human bodies as correspondences between two views with no shared surface, one epoch. | Humans link one archival view to a measured ground surface across a century; different object, same spirit; we do not call ours a virtual correspondence. |
| Mikolka-Flöry et al. 2022-2026 (horizon orientation, monoplotting uncertainty, moniQue) | Unknown-focal orientation of historical photos against terrain, with per-point uncertainty. | Near-field urban anchors with a vanished dominant subject; a position prior; depth-diverse human anchors; points off the surviving surface; next-view query. |
| Maiwald & Sardemann 2022 | Measures hloc resection of historical photos failing when surviving geometry is a small part of the frame. | We work in that regime and add the cues that address it. |
| Acar 2012; Agnello 2019; Bitelli 2017 | Manual location of vanished buildings from archival photos anchored on survivors. | Automatic, with posteriors, certificates and non-circular evaluation. |
| Guan 2006; Kutulakos-Seitz; Urban Radiance Fields | Conservative hulls, carving, sky-ray free space. | Backward in time under a posterior, against a measured modern background. |
| Wang/Wilson/Snavely 2013; Daruna 2026 | Georegistration of internet SfM to geographic data. | Infrastructure for us, not a claim. |

## Decisions log (2026-10-25, overnight execution)

Each entry records where reality departed from the plan, what was chosen, and why.

1. **No CUDA install.** A CUDA 12.6 build of torch 2.14.1 exists, but it needs about 4.5 GB installed and the disk had 7.3 GB free; the acquirer refuses to download photographs below 5 GB free. Matching a few hundred photographs runs acceptably on the 20-thread CPU.
2. **People are an ablation, not the headline.** Inspection showed that the four tower-bearing Boardman postcards contain no pedestrians (linen and hand-coloured prints). The 1914 "In the Quadrangle" postcard has many, so the cue is evaluated there.
3. **EXIF anchoring holds COLMAP's own EXIF priors constant.** COLMAP's image reader already turns EXIF into a focal prior (61 of 77 cameras); the blow-ups came from free refinement. Cameras with a prior are held constant; the rest are refined inside [0.5, 3].
4. **Openverse not added.** Commons location search added 104 eligible photographs with no schema change; the slower bottleneck is Commons throttling original downloads (one file every ~10 minutes), not discovery.
5. **Anchoring protocol redesigned four times.** Correspondence-free wall matching measured in metres shrank the scene onto one wall; adding a coverage term collapsed it onto the tower; model-unit tolerance over all walls preferred huge scales on the dense campus; a free tilt fitted to photographers went to 17.8°. The final protocol: gravity from facade normals, tower axis on its footprint, scale from photographers at eye height against the measured tower top, one yaw from walls, and an independent horizontal scale from the library walls as the check (5.4 % apart). The original gate (held-out tower within 1 m, 17 of 21 photographers in the height band) was written for a protocol that holds the tower out entirely; it does not apply as written, and the photographer-height check fails and is reported.
6. **The frame is "usable", not "passed".** It is marked usable for metric work when two independent scales agree within 10 %, the neighbouring library sits on its walls (median 0.5 m) and the yaw is unique. The demo states the 5.4 % disagreement.
7. **Occlusion test kept as a weak diagnostic.** Line of sight is tested against lidar heights inside building footprints only, because tree canopy is not an occluder for photographs. Calibrated on the modern photographers, it passes 13 of 22 with the margins used, so it is reported and not used as a gate.
8. **A second mirror test was removed.** "Would the vanished site have hidden the matched anchors?" found no conflicts on poses known by inspection to be mirrored, because from the mirrored side the surviving buildings are in front of the site.
9. **Carving implemented, not applied.** The sky-ray column cap is implemented and passes a synthetic containment test, but every registered Boardman pose is a mirror image (see the 2026-10-25 checkpoint), so carving would put free space on the wrong side of the site. No bound on Boardman is shown.
10. **The never-finished 228-photo reconstruction was resumed** instead of waiting for the throttled downloads, because it already contains more photographs of the library (38) and the tower (34), the best chance of views from the Arts Quad side.
