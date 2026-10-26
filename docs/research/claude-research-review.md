# GhostMap: Research Direction Review

*Date: 2026-10-24. Prepared for the GhostMap handoff ([docs/handoffs/GHOSTMAP_CLAUDE_HANDOFF.md](../handoffs/GHOSTMAP_CLAUDE_HANDOFF.md)), section 8 format.*

**How this document was produced.** A read-only audit of the repository (every run report, native COLMAP model, snapshot and manifest; see §1), a web literature sweep (five themes, 114 works, 111 of them opened and verified, plus a gap check per candidate direction), three independent idea generators, a merge into eleven directions, one adversarial novelty reviewer and one adversarial feasibility/geometry reviewer per direction (22 reviews), a ranking pass, and this write-up. The ranking and the first draft were produced before the directions standpoint-certificate to Ghost Hull reviews were available to them; §3.12 adds those reviews and corrects the affected scores. Status words follow the handoff taxonomy: **VERIFIED** (read from files, with paths), **REPORTED**, **HYPOTHESIS**, **FAILED/BLOCKED**. Every probe number that comes from the legacy `artifacts/hloc_cross_era/sfm_joint` model is HYPOTHESIS: that model is era-contaminated and unscaled.

**Short version.** No Quad-wide model exists; the only alignable modern fragment is the 21-camera Uris/McGraw Tower component. The historical Boardman surface is not identifiable from the surviving online record. The recommended project is therefore: anchor that fragment to public-domain USGS lidar (the modern-reference stage), build the "dolly-zoom certificate" interaction on unknown-focal archival cameras (the interaction stage, direction 7), and pursue certified occupancy *bounds* for Boardman (the research stage, direction 11) only where the certificate passes, with the honest expectation that the Boardman result is a rigorous negative with a map of what is missing.


*Read-only assessment, 2026-10-24. Nothing under `/home/bobby/CS6672` was modified and no pipeline was run. Repo paths are relative to `/home/bobby/CS6672` unless absolute.*

**Short version.** The repo has no Quad-wide model. It has disconnected fragments. The best one is a 21-camera Uris Library / McGraw Tower sparse component. About 65% of its observations come from a single 5-image burst, and it is in no metric or geographic frame. Boardman Hall's surface cannot be identified from the archival photos as they are currently registered, because the focal length is unknown. Most of the provocative directions I examined already have close published neighbours. What survives review is narrower:

1. Snap the one good fragment onto public USGS lidar, metric and georeferenced, with held-out checks. This is infrastructure, not the contribution.
2. Use the lidar-measured set of places a photographer could have stood to cut the dolly-zoom ambiguity of unknown-focal archival cameras. Report per-voxel identifiability for Boardman instead of a surface.
3. Only where that identifiability is certified, compute occupancy bounds on the vanished building. Test them first on surviving buildings that are treated as vanished.

The most likely honest Boardman outcome is "not identifiable as a surface; here is the map of why." I ask for approval of this pivot before any implementation (§6, §8).

**Evidence labels used throughout:** VERIFIED (audited from files in this session, with path), VERIFIED† (recomputed read-only by an adversarial reviewer in this session; not in `audit.json`), REPORTED (from earlier notes or generators; not checked), HYPOTHESIS (untested), FAILED/BLOCKED.

---

## 1. Reality check: audited inventory

### 1.0 Repository layout after the reorganization (VERIFIED by `ls`)

- **Code.** The code lives in `pipeline/ghostmap/<group>/`, with groups `acquire`, `prepare`, `sfm`, `dense`, `surface`, `evaluate`, `qa`, `package` and `status`, plus `cli.py`. The top-level `pipeline/*.py` files are compatibility shims. For example, `pipeline/run_artsquad.py` does `runpy.run_module("ghostmap.cli")`.
- **Legacy code.** Legacy code is in `pipeline/legacy/{v1,repair,unused}`. For example:
  - `pipeline/legacy/v1/run_hloc_cross_era.py`
  - `pipeline/legacy/v1/build_site_data.py`
  - `pipeline/legacy/repair/measure_focal_sensitivity.py`
  - `pipeline/legacy/repair/run_target_sfm.py`
- **Docs.** Docs are in `docs/{plans,reference,checkpoints,research,legacy,handoffs}`. The audit cited older locations, which map as follows:
  - `docs/artsquad-local-checkpoint-145.md` → `docs/checkpoints/artsquad-local-checkpoint-145.md`
  - `docs/artsquad-provider-checkpoint.md` → `docs/checkpoints/…`
  - `docs/artsquad-additional-data-sources.md` → `docs/research/…`
  - `docs/results-repair.md` → `docs/legacy/repair/results-repair.md`
- **Unmoved.** `artifacts/`, `data/` and `dist/` were not moved. Runs live under `artifacts/artsquad_modern/runs/<id>/`; this review names runs by what they are (for example "the best learned run on the 145-photo snapshot"), and `artifacts/README.md` maps each description to its directory.

### 1.1 What exists now

| # | Claim | Status | Evidence |
|---|---|---|---|
| 1 | No milestone the six delivery milestones has passed; `project_complete=false`. Only 3 of 122 the impossible-photographer direction checks pass, and none of them is geometric (selection, two split-leakage checks). | VERIFIED | `artifacts/artsquad_modern/project-status.json` |
| 2 | `project-status.json` is stale. It says 163 records and 9.38 GiB free, but disk shows 228 acquired and 7.2 GB free. Its `evidence={}` is empty, and the `dist/` copy has a different sha256. | VERIFIED (contradicts the status file) | same file; `data/artsquad_modern/coverage.json`; `df -h` |
| 3 | There are 10 runs. Complete: the best learned run on the 145-photo snapshot, the SIFT baseline run, the SIFT run on the 46-photo snapshot, the first 46-photo pilot run, a second 46-photo learned run, the fixed-radial calibration control run. Errors: an error-status run (mapping), another error-status run (verification). Interrupted: 82c7, and the interrupted 228-photo run (SIGTERM during matching at 144 of 585 new pairs, no model). | VERIFIED | `runs/*/report.json`; `runs/the interrupted 228-photo run…/process-interruption.json` |
| 4 | The newest snapshot, the 228-photo snapshot (228 records; 139 train / 30 test; 65 metadata families), has **never been reconstructed**. | FAILED/BLOCKED | `artifacts/artsquad_modern/the 228-photo snapshot/snapshot.json` |
| 5 | Best learned run, the best learned run on the 145-photo snapshot (snapshot the 145-photo snapshot, 77 train images): 443 candidate pairs, of which 205 are verified and 204 nondegenerate. 36 of 77 images register (46.8%), in 6 components of 21/5/3/3/2/2 cameras. | VERIFIED | `runs/the best learned run on the 145-photo snapshot…/report.json`; pycolmap on `sfm/models/0..5` |
| 6 | The verified-pair graph is nearly connected: 65 of the 67 images that have any edge form one graph component. The mapper still produced 6 models. Inter-component edges are weak (0-4: 4, 0-1: 2, 0-2: 1, 1-4: 1, 1-5: 1, 2-5: 5). Of the 24 verified pairs between images with disjoint building labels, only 2 share native tracks. | VERIFIED | `runs/the best learned run on the 145-photo snapshot…/bridge-analysis.json` |
| 7 | Calibration blow-ups:<br>- the best learned run on the 145-photo snapshot/m2 (Morrill): focal/max-dim ratio 0.14.<br>- the fixed-radial calibration control run/m4: ratios 0.03 and 463.78.<br>- the fixed-radial calibration control run/m3: 40.81.<br>- a second 46-photo learned run/m0: image 69219202 at f = 18.7M px, k = -8.07M.<br>- Image 5858036 is fitted at ratios 0.27, 3028 and 6519 across runs of one snapshot.<br>bridge-analysis flags 11 cameras in the best learned run on the 145-photo snapshot and 7 in the fixed-radial calibration control run. | VERIFIED | pycolmap `Camera.params`; `bridge-analysis.json` |
| 8 | In the fixed-radial calibration control run, models 0 and 1 share 20 cameras (model 1 is a subset of model 0). There are 37 distinct registered cameras, not 57. **Never sum them.** | VERIFIED | pycolmap name sets of the fixed-radial calibration control run m0/m1 |
| 9 | Run an error-status run reports `status=error`, yet `sfm/models/0` exists on disk: 13 images, 2,171 points, 1.218 px, and one camera at focal ratio 6519. | VERIFIED (contradicts its report) | pycolmap on `runs/an error-status run…/sfm/models/0` |
| 10 | SIFT baseline the SIFT baseline run: exhaustive matching over 2,926 pairs gives 43 verified and 36 nondegenerate pairs. It yields an 8-camera Uris/Tower model (2,093 points, 0.388 px) and a 3-camera Goldwin model (30 points), in 97.68 s. The pair budget differs from the best learned run on the 145-photo snapshot, so this is not an equal-compute comparison. | VERIFIED | `runs/the SIFT baseline run…/report.json` |
| 11 | Only accepted modern dense surface: the best learned run on the 145-photo snapshot the Goldwin Smith fragment (Goldwin Smith label, 5 cameras).<br>- 15,502 fused OpenMVS points from 4 depth maps (3.4M depths, about 0.45% kept).<br>- Native mesh: 10,070 vertices / 20,086 faces. Family-screened mesh: 26,433 faces.<br>- Every point has 3-view (8,953) or 4-view (6,549) support.<br>- **Accuracy, calibration and building identity are not validated.** | VERIFIED | `runs/the best learned run on the 145-photo snapshot…/mvs/1/*report.json`; `DensifyPointCloud.log` |
| 12 | Morrill dense fusion: 0 points in the best learned run on the 145-photo snapshot mvs/2. In the first 46-photo pilot run mvs/2, 332 points, but 0 faces survive the family screen. | FAILED/BLOCKED | `mvs/2/report.json` in both runs |
| 13 | Holdouts:<br>- Against the best learned run on the 145-photo snapshot the Goldwin Smith fragment, 1 of 20 queries is a consistency candidate (5980428: 264 inliers, median/p95 4.00/8.94 px). The other 19 have 4-10 inliers.<br>- Against the first 46-photo pilot run the Morrill fragment, 1 of 10 (98 inliers).<br>- No independent ground truth. | VERIFIED | `runs/the best learned run on the 145-photo snapshot…/holdouts/1-…/report.json` |
| 14 | Non-scene images got past admission: a DeSantis/Putin photo, portraits, political graffiti, the Sibley plaque, and the Uris atrium interior. | VERIFIED | holdout image listing; `bridge-analysis.json` |
| 15 | The checkpoint doc's numbers match the files. It predates the fixed-radial calibration control run and the interrupted 228-photo run. "213 tests passed" was not re-run. | VERIFIED / REPORTED | `docs/checkpoints/artsquad-local-checkpoint-145.md` |
| 16 | Browser QA is functional only: no page errors, no failed HTTP requests, software WebGL, `performance_certified=false`. | VERIFIED | `artifacts/browser-qa/artsquad/report.json` |

**Earlier claims from the handoff (§2), reconciled with the files:**

| Handoff claim | Status | What the files show |
|---|---|---|
| Early v1: about 8 modern cameras and about 1.5k points | VERIFIED (contradicts the handoff; superseded) | `artifacts/public/modern/model` now holds 13 images / 1,756 points / 0.512 px. The 8/1,562 figure is the overwritten earlier state. The v1 gate failed. The v1 historical model has 4 images (3 unique views) and 718 points; its gate failed. |
| 77-image cross-era experiment: 178 pairs; 14 historical + 22 modern registered; about 2,724 points | VERIFIED, but contaminated | `artifacts/hloc_cross_era/sfm_joint`: 36 images, 2,724 points, 1.206 px, 178 UNCALIBRATED pairs (median 33 inliers), 358 points seen from both eras. Three "historical" items are dated 1970 or later. Commons 100749005 is a **2021 iPhone 7 photo with California GPS**, credited as a photo of an antique print. It appears in 14 of the 178 pairs and is also a modern test image in the 228-photo snapshot. |
| About 203 target points from about 6 Boardman photos | VERIFIED under that definition | 203 historical-only points are seen by 2 or more of the 6 Boardman-titled images. Those images also show the library tower, so the points are not necessarily on Boardman. |
| MVS repair: about 171k points / 262k triangles | VERIFIED counts; legacy lineage | `artifacts/cpu_mvs_modern_full_v2`: 171,351 vertices / 262,042 faces, from the 22 modern images of the old `sfm_joint` (Uris/Tower only). `metric_accuracy_validated=false`. It is not part of the frozen `artsquad_modern` lineage. |
| Modern reset: 581 candidates, 231 accepted | VERIFIED | 581 discovered, 231 metadata-eligible, 228 downloaded (3 DNS skips, 1.49 GB). |

### 1.2 Legally fetchable sources and actually usable views

- **Modern Commons (VERIFIED).** All 228 of 228 images come from `upload.wikimedia.org`. Licence counts:
  - CC BY-SA 4.0: 106; CC BY 4.0: 49; CC BY 3.0: 35; CC BY-SA 2.0: 13; CC BY 2.0: 12; CC BY-SA 3.0: 8; public domain: 3; CC0: 1; CC BY 2.5: 1.
  - Each record carries its licence, artist, sha256, dhash64 and EXIF.
- **Independence (VERIFIED).** Exposure groups are exact-hash groups only: 223 groups for 223 validated files. Source families come from metadata and are explicitly "not certified independent". One Commons series (6333251-57) supplies 5 of the 21 library-and-tower fragment cameras and 6,935 of its 10,739 observations. The number of truly independent views is therefore far below 228, and nobody has measured it.
- **EXIF (VERIFIED in the lidar-glued Quad direction/the sun-and-shadow direction texts).** 209 of 228 the 228-photo snapshot images have DateTimeOriginal. 29 have GPS, 27 of them within about 1 km. Reviewers found only 1-2 GPS-tagged images registered in any component. They disagree on 69219263, whose GPS would put it about 1.8 km off-site. No fragment has 3 or more GPS cameras, so a Doppelgangers++-style geotag check cannot run on any fragment.
- **Historical (VERIFIED).**
  - `data/raw/manifest.json` historical set: 35 accepted of 73 (33 PD). The modern set there: 42 of 89.
  - `data/cornell_archive`: 10 items, all "research use; no explicit redistribution licence".
  - **Rights issue:** two of those items, `ss_1312589` and `ss_575160`, feed `cpu_mvs_archive_target_v2`, whose outputs are served from `dist/assets/repair/historical-archive/`. This redistribution question is unresolved and should be fixed before anything is shared.
- **External, from literature.json:**
  - Commons Category:Boardman_Hall: 24 files (4 plus 20 postcards), PD or "no restrictions", dated 1898-1934.
  - Cornell RMC: about 8 Boardman images, mostly "inquire". The June 1958 photo is Cornell-copyrighted.
  - USGS 3DEP `NY_FingerLakes_1_2020` EPT: public domain, 25.24B points, bounds contain the Quad. Reported specs: QL2, about 0.7 m spacing, 6.4 cm NVA, May 2020.
  - NYS orthoimagery for Ithaca, 2002-2023: licence not stated.
  - LoC Sanborn maps for Ithaca, 1888-1919 digitized, PD; campus coverage not verified.
  - Flickr CC "Arts Quad Cornell": about 145 hits. Needs an API key, which is a user decision under the credential constraint. Licence IDs 1/2/3/6 are NC/ND.
  - Quad6K: 4 JPEGs (1 is a selfie) plus 348 DGPS ground-truth rows. No licence (VERIFIED, `data/quad6k_research_probe`).
- **Sanborn (REPORTED).** A downscaled JPEG of the September 1919 Ithaca sheet 35 and its index sheet were fetched from the Library of Congress Sanborn collection (public domain; https://www.loc.gov/collections/sanborn-maps/?q=ithaca+new+york) into session scratch space, which is not retained. Two reviewers viewed the thumbnail: it shows "Boardman Hall Law College" south of President Ave, between the University Library and Stimson Hall, at 200 ft/in; the footprint measures roughly 58-60 m by 18 m. Drafting accuracy and georeferencing are unchecked.

### 1.3 Per-building coverage (best run the best learned run on the 145-photo snapshot; labels come from discovery metadata, not verified image regions)

| Target | the 145-photo snapshot train images → registered (component) | Surface status | the 228-photo snapshot train/test |
|---|---|---|---|
| Uris Library | 28 → 21 (the library-and-tower fragment) | sparse only in this lineage | 38/4 |
| McGraw Tower | 30 → 17 (the library-and-tower fragment) + 2 (a three-camera fragment) | sparse only | 34/6 |
| Goldwin Smith | 8 → 5 (the Goldwin Smith fragment) + 1 (the library-and-tower fragment) + 1 (a three-camera fragment) | 15,502-point dense patch; identity uncertain (an A.D. White statue image and "Ithaca_NY_08" are in the set) | 17/2 |
| Morrill | 6 → 3 (the Morrill fragment: 275 points, only 28 with track length ≥ 3) | dense: 0 points | 9/5 |
| McGraw Hall | 5 → 1 (the library-and-tower fragment) + 2 (a two-camera fragment) + 1 (another two-camera fragment) | none; comps 4/5 are 2-camera models with all tracks of length 2 | 10/3 |
| White | 2 → 1 (a two-camera fragment) + 1 (another two-camera fragment) | none | 6/1 |
| Sibley / Tjaden / Lincoln | 4 / 3 / 2 → **0** | none | 12/1, 6/3, 6/5 |
| Stimson, Rand, Milstein, Klarman, Olin | 1, 2, 2, 3, 5 → **0** | none | — |

**8 of 14 targets have zero cameras. No two quad-core buildings share a component.** VERIFIED.

### 1.4 Best validated modern geometry

There is **no Quad-wide model**. Every component has `scale_status = similarity-frame-unverified`.

**Best sparse fragment: the best learned run on the 145-photo snapshot the library-and-tower fragment, Uris/Tower.** VERIFIED.
- 21 cameras, 2,686 points, 10,739 observations.
- Mean track length 4.00 (max 19); 2,150 points with track length ≥ 3.
- Reprojection error: mean 1.236 px, p50/p95 1.23/2.19 px.
- Max track angle p5/p50/p95: 7.5/24.9/60.1°.
- Calibration flags: grid-unprojection failure, k = 0.57, EXIF disagreement.
- **Quarantined from the viewer** because modern__114998420 has a "1996" title but a 2005 timestamp.

Additional facts recomputed by reviewers (VERIFIED†):
- Point spread is volumetric (PCA standard deviations 0.28/0.47/1.26 model units).
- One D300 camera (73626995, 90 mm-equivalent) is fitted at f/max 0.90, while EXIF implies about 2.5.

**Other fragments, reviewer recomputation (VERIFIED†):**

| Component | What it is | Problems |
|---|---|---|
| the Goldwin Smith fragment (Goldwin) | 5 cameras, 737 points, track-angle p50 9.7° | 2 of 5 cameras have impossible focals: 119250070 fitted 0.46 where EXIF implies 0.81-0.84; 73627005 fitted 1.01 where EXIF implies 1.58. The dense patch may be distorted. |
| the Morrill fragment (Morrill) | a single vertical facade (PCA thickness 0.035 vs 0.50/0.75) | camera 106329855 fitted 0.14 where EXIF implies about 0.39 |
| a three-camera fragment | two "from McGraw Tower" views plus one ground shot, **not** a Stone Row piece | one camera at f = 16,038 px on a 2173 px image, k = -14.83 |
| comps 4/5 | 2-camera models | k = 17.7/12.6 and 1.87/0.70 |
| the fixed-radial calibration control run m4 (the "ratio 463" Morrill) | has collapsed: point extent about 0.002 against camera baselines of about 10 | — |

**Realistically, one fragment can be anchored (the library-and-tower fragment), possibly two.**

### 1.5 Historical status (VERIFIED)

- **Boardman-only SfM.**
  - `artifacts/target_sfm_v2`: 17 of 19 images register; 1,132 points; mean track length 3.11.
  - `archive_target_v2`: 18 of 26 images at fixed focal 0.8; 821 points.
  - `masked_target_v3`: 16-17 images; 830-900 points.
- **Focal sensitivity** (`artifacts/target_sfm_v2/focal-geometry-sensitivity.json`). Between focal priors 0.8 and 1.2, after similarity alignment:
  - scale 0.81;
  - median displacement 10.6% of scene radius;
  - **p90 displacement 329%**.
  - Masked variant: p90 62%. Priors 0.8 vs 1.8: p90 96%.
- **Historical OpenMVS outputs** (e.g. masked08: 20,555 points, 32,632 faces) are all `surface_candidate` with `metric_accuracy_validated=false`.
- **Conclusion: there is no verified Boardman surface.** Cross-era joint registration exists only at the level of verified pairs and registered cameras, and era mislabelling contaminates it.

### 1.6 Blockers, ranked, with the evidence that tells them apart

1. **Content: few overlapping building-specific views.**
   - 8 of 14 targets have zero cameras, from 1-5 train images each.
   - 41 of 77 images do not register.
   - Exhaustive SIFT over 2,926 pairs found 43 verified pairs; NetVLAD over 443 pairs found 205. A bigger pair budget does not create content.
2. **Calibration instability.**
   - The graph has 65 of 67 images connected, yet the mapper builds 6 models.
   - The same image gets three wildly different focals across runs.
   - The fixed-radial control the fixed-radial calibration control run changes component membership.
   - This competes with blocker 1 as an explanation for the fragmentation. §8 gate  is the cheap test that separates them.
3. **Dense MVS software.** The GPU is present but the stack is CPU-only (§1.7), so COLMAP PatchMatch is refused. Morrill's 0-point fusion comes from weak geometry, not from compute.
4. **No shared or metric frame.** There is no geo or metric anchor anywhere. The Quad6K ground truth is unused, and its licence is unknown.
5. **Repeated structure.** Not measured. No Doppelgangers check has been run. Only 2 of the 24 label-disjoint pairs share tracks.
6. **Storage and process limits.** Disk is 97% full. The 228-image run was killed.
7. **Provenance and labels.** Era leakage (100749005), the "1996" image, uncertified families, and non-scene images.

**The web viewer is not a blocker.**

### 1.7 Environment (VERIFIED)

- **GPU:** RTX 3070 Ti Laptop, 8,192 MiB, driver 546.30, CUDA 12.3, visible in WSL2. Project files claim there is no GPU; that is wrong.
- **Software:** torch 2.14.1+cpu, pycolmap 3.13.0 built without CUDA, hloc 1.5, OpenMVS 2.4.0 (CPU). There is no `colmap` CLI on PATH. COLMAP stereo `depth_maps` directories are empty.
- **CPU and memory:** i9-12900H, 20 threads. 7 GB RAM total with about 4 GB available (7.65 GiB recorded).
- **Disk:** 7.2 GB free (97% used). `artifacts` takes about 6.9 GB, of which `runs` is 3.2 GB. `dist` takes 775 MB, 662 MB of it under `repair`.
- **Lidar tooling** (from the lidar-glued Quad direction/the sun-and-shadow direction reviews): PDAL, laspy, pvlib and astropy are not installed in `.venv`.

---

## 2. What existing papers already solve, and how that constrains novelty

Caveats carried from the sweep and the reviews:
- Several sources were read from abstracts only: Wang/Wilson/Snavely 2013 (TLS error), the Heinly 2014 project page (404), and Untzelmann 2013 and LoD-Loc (search snippets only).
- Scene Chronology's timestamp mechanism was not verified from primary text.
- Hauagge 2014, Wehrwein 2015, Cohen 2015, Kaminsky 2009, Zeisl 2015 and Maiwald 2022 were read in full by reviewers.

**Internet-photo 3D and time (Snavely lineage)**

| Work | What it already does | Constraint on GhostMap |
|---|---|---|
| [Photo Tourism, 2006](https://phototour.cs.washington.edu/) | SfM from unstructured photos; browsing photos in 3D | 3D photo browsing and frusta are baseline features, not contributions |
| [Scene Chronology, ECCV 2014](https://mlanthology.org/eccv/2014/matzen2014eccv-scene); [Schindler & Dellaert, CVPR 2010](https://mlanthology.org/cvpr/2010/schindler2010cvpr-probabilistic) | Existence intervals for 3D elements from dated photos | A "3D + timeline" view, and inferring when something existed, are taken |
| [Neural Scene Chronology, CVPR 2023](https://arxiv.org/abs/2306.07970) | Disentangles time and illumination; renders unseen time-viewpoint combinations | A time slider over reconstructed appearance is taken |
| [Hauagge et al., BMVC 2014](https://bmva-archive.org.uk/bmvc/2014/files/paper057.pdf); [Wehrwein et al., 3DV 2015](https://www.cs.cornell.edu/projects/shadows) | Per-photo timestamps and clock correction from a sun-sky model; per-image sun direction over SfM | The modern "photo clock" is taken. Raw EXIF had a 211-minute median error on CASTLE, so EXIF is not ground truth |
| [Doppelgangers, ICCV 2023](https://arxiv.org/abs/2309.02420); [Doppelgangers++, CVPR 2025](https://arxiv.org/abs/2412.05826) | Learned rejection of look-alike pairs; a geotag-inlier-ratio check of model correctness | Must be a baseline for the Stone Row. DG++ out-of-domain precision is described as suboptimal |
| [MegaScenes, ECCV 2024](https://arxiv.org/abs/2406.11819) | Commons category → COLMAP at scale | Cornell is barely covered (Sage Chapel: 10 images, 1,148 points; Uris has no reconstruction). The pipeline is theirs, so the modern model is engineering |
| [MegaDepth-X / Long-Tail, CVPR 2026](https://megadepth-x.github.io/) | MASt3R-SfM + DG++ data; π³/VGGT fine-tuned for sparse, symmetric scenes | A COLMAP-only stack is behind the lineage's own state of the art for sparse scenes |
| [Crandall et al., CVPR 2011](https://vision.luddy.iu.edu/projects/general-papers/discrete-continuous-optimization.html); [PhotoCity](https://grail.cs.washington.edu/projects/photocity/) | 6,514-image Arts Quad SfM with 348 DGPS cameras; gamified Arts Quad acquisition | A "validated Arts Quad" is not new. The DGPS data could be free ground truth if a licence is found |

**Extreme-view geometry (Wei-Chiu Ma and Cornell collaborators)**

| Work | What it does | Constraint |
|---|---|---|
| [Virtual Correspondence, CVPR 2022](https://arxiv.org/pdf/2206.08365) | Correspondences without co-visible surface, using humans as a shape prior; its Eq. 3 reduces to classic BA | Surviving-building anchors are ordinary co-visible surfaces, **not** VC. Hybrid BA with non-co-visible terms is not new |
| [Ext-3DFMs, CVPR 2026](https://cornell-vailab.github.io/Ext-3DFMs/); [Bezalel, CVPR 2025](https://arxiv.org/abs/2411.07096) | Pretrained VGGT gets under 30° rotation error on about half of non-overlapping pairs; a bias-only fine-tune | Same-era no-overlap relative pose is largely addressed. Use as a baseline |
| [SGAM](https://yshen47.github.io/sgam/), [CADSim](https://arxiv.org/abs/2311.01447) | Generative and simulation world building | Inspiration only. Synthesised content violates the measured-only constraint |

**Historical photogrammetry**

| Work | What it does | Constraint |
|---|---|---|
| [Maiwald & Sardemann, ISPRS 2022](https://isprs-archives.copernicus.org/articles/XLIII-B2-2022/823/2022/) | hloc + SuperGlue + pycolmap resection of historical photos into a modern model. Judged inaccurate; fell back to manual points. Reports that resection fails when contemporary geometry covers only a small part of the frame. Median \|Δc\| = 261 px | Our localization step is not new, and Boardman/Olin is exactly the regime where it fails |
| [Maiwald et al., IJGI 2021](https://mdpi-res.com/d_attachment/ijgi/ijgi-10-00748/article_deploy/ijgi-10-00748.pdf) | Fully automatic historical pose estimation. Symmetric facades caused near-180° flips; about 1 px reprojection did not predict correctness | Low reprojection error is not evidence of a correct cross-era pose |
| [HistReNeRF, arXiv 2608.15420 (Aug 2026)](https://arxiv.org/abs/2608.15420) | Relocalizes archival photos in a modern reconstruction: 1.6-6.6 m mean error; 58 of 230 queries kept as GT via SIFT+PnP | Archival localization framing is taken. Its GT is circular, which leaves room for non-circular evaluation |
| [Coloring the Past, 2023](https://arxiv.org/abs/2311.17810) | Reconstructs a demolished theatre from archival photos alone (COLMAP + LightGlue + MVS); no historical ground truth | "Pipeline on archival photos" is taken. It needs a self-consistent archival SfM, which is shown unidentifiable here |
| [Mikolka-Flöry et al., 2022](https://api.openalex.org/works/doi:10.1016/j.ophoto.2022.100026); [Bansal & Daniilidis, CVPR 2014](https://mlanthology.org/cvpr/2014/bansal2014cvpr-geometric) | Unknown-focal orientation from the DEM horizon (alpine); urban DEM-skyline localization | Skyline and horizon registration is not new |
| [Bae et al., TOG 2010](https://people.csail.mit.edu/soonmin/rephoto/rephoto.pdf); [ARephotography, CHI EA 2023](https://api.openalex.org/works/doi:10.1145/3544549.3585646) | Rephotography (6-8 user clicks); single-photo learned 3D placed in AR | In-situ "time portal" demos exist, though not with measured geometry |
| [Bitelli 2017](https://isprs-archives.copernicus.org/articles/XLII-5-W1/113/2017/); [Agnello 2023](https://isprs-archives.copernicus.org/articles/XLVIII-M-2-2023/43/2023/); [Bevilacqua 2019](https://isprs-archives.copernicus.org/articles/XLII-2-W9/119/2019/) | Manual restitution of destroyed buildings against TLS/lidar of surviving neighbours | The concept "orient archival photos against lidar of survivors" is old. Only automation is unclaimed |

**Georegistration and fragment merging**

| Work | What it does | Constraint |
|---|---|---|
| [Kaminsky et al., CVPRW 2009](https://mlanthology.org/cvprw/2009/kaminsky2009cvprw-alignment) | 2D alignment of SfM to overhead maps, with a camera-to-point free-space term | Free space as an alignment term is taken |
| [Wang, Wilson, Snavely, 3DV 2013](https://research.cs.cornell.edu/georegister) (not re-fetched) | Georegistration of internet SfM to Google Earth / Street View | Single-model georegistration is taken |
| [Wendel et al., CVPRW 2011](https://mlanthology.org/cvprw/2011/wendel2011cvprw-automatic) | Snaps SfM onto a DSM by height-map correlation, initialised from GPS | "SfM onto DSM" is taken |
| [Strecha et al., CVPR 2010](https://www.epfl.ch/labs/cvlab/research/completed/research-surface-calibration/); [Cohen et al., ICCV 2015](https://openaccess.thecvf.com/content_iccv_2015/papers/Cohen_Merging_the_Unmatchable_ICCV_2015_paper.pdf) | Merges disconnected clusters through geodata; merges visually disconnected models, using free-space and sky conflicts to test merges | Track-free merging, and free space as a merge test, are taken |
| [Daruna et al., arXiv 2608.29211 (IGARSS 2026)](https://arxiv.org/html/2608.29211) | Merges disjoint SfM submodels into one metric ENU frame through satellite cross-view pose plus KDE/RANSAC Sim(3); flags unreliable submodels (2D, 2-7 m error) | Pre-empts the lidar-glued Quad direction's headline |
| [Shan et al., 3DV 2014](https://grail.cs.washington.edu/projects/sq_ground2aerial) | Automatic ground-to-aerial georegistration of internet MVS models (41 of 59 succeed) | Automatic georegistration of connected models is taken |
| [Zeisl et al., ICCV 2015](https://openaccess.thecvf.com/content_iccv_2015/papers/Zeisl_Camera_Pose_Voting_ICCV_2015_paper.pdf); [Hoiem et al., CVPR 2006](https://mlanthology.org/cvpr/2006/hoiem2006cvpr-putting) | Camera-height band (±5 m) as a localization prior; camera-height reasoning | A height prior by itself is not new |
| [US 12,008,777  (Argo AI)](https://patents.google.com/patent/US12008777) | Validates SfM points against lidar depth | Points-vs-lidar checking is taken |

**SfM software, feed-forward models, uncertainty and active selection**

| Work | Constraint |
|---|---|
| [COLMAP 4.x changelog](https://colmap.github.io/changelog.html) (global_mapper/GLOMAP, ALIKED/LightGlue, multi-component global models); [GLOMAP](https://arxiv.org/abs/2407.20219); [GLUEMAP, CVPR 2026](https://arxiv.org/abs/2605.26103) | The prior "learned matching into COLMAP" pipeline is now a stock configuration. On full internet collections, GLOMAP+SIFT still beats GLUEMAP |
| [MASt3R-SfM](https://arxiv.org/abs/2409.19152); [VGGT](https://arxiv.org/abs/2503.11651) | Baselines and proposal generators. No validated 8 GB configuration was found |
| [Calibration audit of feed-forward confidence, arXiv 2608.29705](https://arxiv.org/abs/2608.29705) | Feed-forward confidence is at least 2.4x overconfident. "We output uncertainty" needs independent calibration |
| [Polic et al., ECCV 2018](https://arxiv.org/abs/1808.02414) | Camera covariance is solved; certificates must add calibration evidence, not just compute a covariance |
| [Schönberger et al., CVPR 2015](https://www.cv-foundation.org/openaccess/content_cvpr_2015/papers/Schonberger_From_Single_Image_2015_CVPR_paper.pdf); [Shen et al., ACCV 2018](https://arxiv.org/abs/1811.10343); [FisherRF, ECCV 2024](https://jiangwenpl.github.io/FisherRF/) | Retrieval for detail; retrieval for matchability; active view selection over **posed** candidates. Ranking **unposed** web photos by expected gain is the most open slot found |
| [Bui et al., ECCV 2020](https://arxiv.org/abs/2004.04807) | Multi-hypothesis pose with uncertainty is taken (learned, modern) |

**Compositing, occluders, carving and change**

| Work | Constraint |
|---|---|
| [Whyte, Sivic, Zisserman, BMVC 2009](https://www.di.ens.fr/willow/research/inpainting/); [Photo Uncrop, ECCV 2014](https://grail.cs.washington.edu/projects/sq_photo_uncrop/); [Boehm 2004](https://WWW.ISPRS.org/proceedings/XXXV/congress/comm5/papers/671.pdf); [Hammoudi 2012](https://mural.maynoothuniversity.ie/id/eprint/20863/1/Generating_occlusion-free_textures_for_virtual_3D_model_of_urban_facades_by_fusing_image_and_laser_street_data.pdf); [PhotoCloud 2013](https://api.openalex.org/works/doi:10.1109/MCG.2012.92) | See-through compositing from other people's photos, with a per-pixel source-label map, plus point-to-photo browsing, are taken |
| [Kutulakos & Seitz, IJCV 2000](https://www.cs.toronto.edu/%7Ekyros/pubs/00.ijcv.carve.pdf); [Taneja et al., ICCV 2011](https://mlanthology.org/iccv/2011/taneja2011iccv-image); [Ulusoy & Mundy, ECCV 2014](https://mlanthology.org/eccv/2014/ulusoy2014eccv-image) | Carving, and forward-in-time calibrated change detection, are taken |

**What the literature leaves open.** These are the sweep's gaps, each stated against the specific work it contrasts with.

1. **Non-circular ground truth for cross-era poses and geometry.** HistReNeRF's GT comes from the same model it evaluates.
2. **Recovering anything about a building with no modern counterpart, when the archival set cannot reconstruct itself.** Coloring the Past assumes a self-consistent archival SfM.
3. **Calibrated uncertainty for cross-era registration.** The 2608.29705 calibration audit shows learned confidence fails here.
4. **Handling the focal-depth ambiguity of single historical images in automatic pipelines.** Maiwald 2022 quantifies it but offers no fix.
5. **Ranking unposed web candidates by expected gain.** FisherRF assumes posed candidates.

---

## 3. Eleven directions

Origins: the lidar-glued Quad, impossible-photographer, sun-and-shadow, leaf-off see-through, simulated-demolition and re-occupied-standpoint directions are new (six ideas not on the handoff list). The active-acquisition direction corresponds to the handoff's active-retrieval candidate; the standpoint-certificate and belfry-vantage directions to its impossible-localization candidate; the geometric-detective direction to its detective candidate; and the Ghost Hull direction to its time-portal and time-dependent-architecture candidates. The evidence X-ray candidate is absorbed into the leaf-off see-through direction and the viewer. The different-site candidate is handled through the simulated-demolition direction, the pivot question and the alternative-site census.

**Evidence asymmetry.** All eleven directions received an adversarial novelty review and an adversarial feasibility/geometry review. The ranking pass and the per-direction write-ups below were drafted before the directions standpoint-certificate to Ghost Hull reviews were available to them, so for directions standpoint-certificate to Ghost Hull the write-ups rest on the generators' closest-work lists plus the ranker's read-only probes. **§3.12 adds the directions standpoint-certificate to Ghost Hull reviews and overrides the write-ups where they disagree.** Those probes ran on the legacy, era-contaminated, unscaled `artifacts/hloc_cross_era/sfm_joint`, so all the standpoint-certificate direction/the geometric-detective direction/the re-occupied-standpoint direction/the Ghost Hull direction probe numbers are HYPOTHESIS. The probe scripts are kept in [docs/research/probes/](probes/) (`d7-standpoint/`, `d8-detective-focal_profile2.py`, `d10-reoccupied/`, `d11-ghost-hull/`).

**Shared prerequisite: "single-fragment lidar anchoring".** This is a 3DEP lidar crop reprojected to UTM 18N, plus a Sim(3) of the library-and-tower fragment into that frame that passes held-out gates. Every direction that needs a metric frame depends on it.

---

### Lidar-Glued Quad: a metric, georeferenced frame from track-disconnected fragments, with per-fragment refutation
*NEW · modern-only · reviewed: novelty 2/5, feasibility 3/5*

- **Demo.** Six floating fragments drop onto the public-domain lidar Quad. The held-out tower top lands within 1 m. A bad fragment turns red and refuses to snap.
- **Problem and geometry.** Each fragment is an unknown 7-DoF similarity registered to an independent metric observation (the 3DEP DSM, plus wall planes derived from lidar). Constraints:
  - gravity from vanishing points;
  - ground and roof point-to-plane distance;
  - roofline tangency;
  - free space in 3D: camera-to-point rays may not cross lidar solids.

  Outputs: a Sim(3) posterior per fragment, an explicit null-space report, and a refutation statistic for fragments whose internal geometry is not a similarity of the world.
- **Closest work.** Daruna 2026 (disjoint submodels → one geo-frame, with unreliable-submodel flags); Wendel 2011 (SfM onto a DSM); Strecha 2010; Kaminsky 2009; Cohen 2015; Shan 2014; DG++.
- **What could still be new (after review).** Narrow:
  - GPS-free 7-DoF placement of very small, badly calibrated fragments against untextured QL2 lidar. Daruna is 3-DoF and needs per-image satellite localization; Wendel needs GPS.
  - A calibrated refutation ROC on injected focal errors, which must beat a trivial EXIF/extent sanity check.

  The reviewer's verdict: this is good Stage-A engineering, not a new capability.
- **Data and rights.** 3DEP EPT (PD), the best learned run on the 145-photo snapshot comps, OSM (ODbL; the "58 building ways" is generator-reported). There is a trap: the EPT is in EPSG:3857, so horizontal distances are stretched by 1/cos 42.45° ≈ 1.355. A Sim(3) fitted there is wrong by construction. Reproject to UTM 18N first.
- **Feasibility probe.** Fit the library-and-tower fragment on Uris roof/eaves, the DTM and lidar-derived walls, holding out the tower. Then predict the tower's roof/parapet plane (not the apex, which is biased low at 0.7 m spacing) and the footprint centroid.
- **Unknowns.**
  - QL2 barely samples facades.
  - The March09 burst means the library-and-tower fragment is effectively a 5-image fit.
  - Single-facade fragments always admit a lidar-consistent Sim(3), so refutation has no power on them.
  - The Stone Row gives about 6 symmetric modes.
  - Bridge edges (15-22 inliers) cannot support a 3 px epipolar test.
- **Observed 3D.** No new surface. Existing tracks and the Goldwin patch become georeferenced, with residuals. Lidar is rendered as a separate measured layer.
- **Kill test (revised by the reviewer; 4 days, CPU).**
  - **Day 0.5 preconditions:** the projection check; at least 50 lidar returns inside the tower footprint; at least 100 library-and-tower fragment points within 1 m of lidar surfaces, drawn from at least 5 non-March09 families.
  - **the held-out-tower gate (held-out tower):** at most 1.0 m vertical and 1.5 m horizontal error, inside the method's own 95% interval; scale interval ±2%; beats ICP by at least 30%; leave-March09-out refits agree within 1 m.
    - Why 1.5 m: at 100 m it is 0.86°, about 25-30 px at f ≈ 1900. That is the basin archival resection needs, and it is below Stone Row building spacing.
  - **the camera-height gate:** at least 17 of 21 camera centres sit 0.5-3 m above the DTM, outside building volume. This is the test that catches focal-distance errors.
  - **the merge gate (merge):** a second fragment with a unimodal posterior (likelihood ratio at least 20:1) and a 95% horizontal interval under 3 m.
  - **the refutation gate (refutation):** AUROC at least 0.80 on at least 20 corrupted variants that internal checks cannot detect.
  - **Decisions:** the held-out-tower gate+the camera-height gate → keep as infrastructure; +the merge gate → merge claim; +the refutation gate → refutation claim; the held-out-tower gate fails → kill.
- **Paper path.** Lidar-gauged multi-fragment BA with observability reports. Baselines: GPS similarity, ICP, Kaminsky-style ortho alignment, COLMAP 4.x global_mapper, MASt3R-SfM, GLUEMAP.
- **Verdict.** Keep **single-fragment lidar anchoring** (the held-out-tower gate/the camera-height gate) as Stage-A infrastructure. Drop the merge and refutation claims unless new volumetric fragments appear.

### Impossible Photographer: lidar admissibility of camera placements as a geotag-free verifier of look-alike merges
*NEW · modern-only · reviewed: novelty 2/5, feasibility 2/5*

- **Demo.** A "verified" bridge would put three photographers 9 m inside McGraw Hall. The alternative merge puts everyone on lidar ground at eye height.
- **Problem.** Score each merge hypothesis by A(H), which combines:
  - (a) camera centres in lidar free space;
  - (b) a height-above-ground mixture;
  - (c) unoccluded line of sight;
  - (d) points near lidar surfaces.
- **Closest work.** Every term has a precedent that a reviewer read: Cohen 2015 (free space as a merge test); Kaminsky 2009 (line of sight); Zeisl 2015 (height band); Argo US12008777 (points against lidar). DG/DG++, [XDG (arXiv 2608.29733)](https://arxiv.org/abs/2608.29733) and [HiSfM (arXiv 2609.04718)](https://arxiv.org/abs/2609.04718) are learned or intrinsic competitors that use no lidar.
- **What could still be new.** Composing these terms camera-first against public lidar, as a pair/merge classifier, with a head-to-head benchmark. That is an engineering and benchmark contribution only.
- **Data.** Lidar plus the best learned run on the 145-photo snapshot. The Stone Row is 7 cameras in comps 2, 4 and 5, all with calibration pathologies. Only one, possibly two, GPS-tagged cameras are registered (106329855, ratio 0.14; reviewers disagree on a second).
- **Fatal geometry.** A Stone Row look-alike merge is roughly a translation along the row. It maps lawn cameras at eye height to lawn cameras at eye height, looking at a lidar-supported look-alike facade, so all four terms stay satisfied. The dramatic failures are gross scale or rotation errors, which inlier counts, Heinly 2014 and Cohen 2015 already catch. The proposed probe is also circular, because the lidar-glued Quad direction's objective already forces cameras into free space.
- **Observed 3D.** About 100% measured, and adds no surface.
- **Kill test (revised).** Day 0 is lidar-only and synthetic. Sample 2/3/5-camera photographer sets in front of Morrill, McGraw and White, apply the row-swap transforms, and measure detection power. **Kill** if power is below 0.5 noise-free, or below 0.3 at the lidar-glued Quad direction's own pose noise, at a 10% false-reject rate.
- **Paper path.** "Where could the photographer stand?" as a view-graph filter, benchmarked on MegaScenes scenes with 3DEP coverage.
- **Verdict. Abandon.** The failure is structural, not a matter of missing data (§4).

### The sun as a cross-century landmark: shadows as photo clock, registration validator and height gauge
*NEW · reviewed: novelty 2/5, feasibility 2/5*

- **Demo.** Hide a photo's EXIF and recover its hour from lidar-rendered tower shadows. On a postcard, the sun rejects a mirror pose.
- **Problem.** The ephemeris sun direction s(t) is known in both 1905 and 2026. Render lidar cast shadows through each photo's pose to get a time posterior p(t | I). The planned uses:
  - use (time minus EXIF) as a registration check;
  - for archival photos, test solar feasibility (the sun-reachable band at 42.45° N), single-light consistency, and Boardman's height via the episolar constraint.
- **Closest work.** [Hauagge 2014](https://bmva-archive.org.uk/bmvc/2014/files/paper057.pdf) (photo timestamps and clock correction); [Wehrwein 2015](https://www.cs.cornell.edu/projects/shadows); [Troccoli & Allen 2004](http://www.cs.columbia.edu/~atroccol/ivr04/ivr04.pdf) (ephemeris shadows on a scanned model); [Lynch](https://maths.ucd.ie/~plynch/Publications/Kingstown-Postcard.pdf) (hand-dated c.1905 postcard, including the solstice ambiguity); [IMAGEGUARD](https://arxiv.org/abs/1811.08951); [Sundial](https://pubs.usgs.gov/publication/70271686); [Episolar](https://mlanthology.org/cvpr/2013/abrams2013cvpr-episolar).
- **What could still be new.** Only the historical stage: solar gating of cross-era pose hypotheses, and an episolar height for a vanished caster. The rest is published.
- **Data reality (reviewer contact-sheet census; HYPOTHESIS).**
  - Comp 0 has about 11 sunny independent sessions. Two of them have physically impossible clocks (18671006 and 69219202), leaving about 9 for evaluation.
  - Only 1-3 sessions show a building shadow on lidar ground. The direction's own Day-1 bar is 6.
  - The named demo photo 16963770 has the sun behind the camera.
  - Of the 19 local Boardman files, at least 13 are hand-coloured or lithographic, leaving about 10-12 independent exposures. 0-2 are usable for shadows.
  - The reviewer's thumbnail contact sheet was made in session scratch space and is not retained; the images are the library-and-tower fragment members listed in `artifacts/artsquad_modern/the best learned run on the 145-photo snapshot/report.json`.
- **Geometry.** Attached shading cancels elevation, so it pins azimuth only to about a 90° quadrant. The "16:05" demo moment is therefore unreachable for that photo. The sun at infinity constrains rotation only, so scale-error detection is about chance (AUROC ~0.5).
  - What survives: a 180° yaw flip falls 16-64° outside the band, and was rejected for all 9 sunny library-and-tower fragment suns.
  - What does not: an east-west mirror is never rejected.
- **Observed 3D.** Measured lidar plus physics. Historical heights would be fewer than 10 single-view numbers with error bars.
- **Kill test (revised).** Day 0.5, lidar-free: fit the frame yaw from EXIF suns and predict held-out tower-face lit patterns. Pass needs at least 80% correct against about 50% chance. Also, the EXIF-impossibility flag must catch exactly the 2 bad clocks. **Kill** the dating demo if fewer than 4 sessions have an automatically detected building shadow of at least 200 px. **Kill** the height stage if fewer than 3 photographic prints qualify.
- **Paper path.** Only as a solar likelihood term inside archival resection.
- **Verdict.** Demoted to a **module**: the solar-flip rejection inside the standpoint-certificate direction/the geometric-detective direction.

### Leaf-off X-ray: see through elms using other people's measured pixels, with provenance and honest holes
*NEW (absorbs C) · reviewed (text truncated): novelty 2/5, feasibility 3/5*

- **Demo.** Toggle "season". Foliage in an October photo becomes transparent, and the facade behind it is filled only from leaf-off photos whose rays hit the same measured surface. Hover a pixel to see its source, date and licence. Unobserved areas stay checkerboard.
- **Problem.** Occluder-aware image transfer through a measured surface S (OpenMVS plus lidar), with depth tests, incidence limits and an MRF over source labels. The research claim is that per-point leaf-off source selection raises MVS completeness on tree-occluded facades.
- **Closest work.** [Whyte 2009](https://www.di.ens.fr/willow/research/inpainting/) is the demo minus 3D: affine colour transform, MRF and a per-pixel label map. Photo Uncrop 2014 adds 3D. Boehm 2004 and Hammoudi 2012 make occlusion-free facade textures through trees. Petrovska & Jutzi (ISPRS Open J. 2025) and the companion [ISPRS Annals X-G-2025 3DGS study](https://isprs-annals.copernicus.org/articles/X-G-2025/641/2025/) measure completeness behind vegetation. Facciolo 2017 does season-aware pair selection for satellite MVS.
- **What could still be new.** Per-point, season-conditioned view selection for ground-level internet photos. The reviewer's objection is that COLMAP PatchMatch already infers occlusion per pixel.
- **Data reality (ranking numbers from the review).** Leaf-off evidence is effectively 2 sessions, both from Libe Slope. Dropping March09 removes 84% of the 3+-view points. Default view selection is already 79% leaf-off by observations. Leaf-on and leaf-off views mostly see different faces (median ray angle 35-50°). The dense surface S does not exist for the library-and-tower fragment.
- **Observed 3D.** About 100% measured; holes are explicit.
- **Kill test.** First, OpenMVS on the library-and-tower fragment. **Kill** if 3-view coverage is below 30% of the Uris facade area. Then leave-one-out transfer must beat 2D inpainting on at least 70% of patches, and the season gain must be at least 5%.
- **Verdict.** Not research on this data. Keep **provenance and honest holes** as a Stage-B viewer feature.

### Simulated demolition: lidar-ground-truthed identifiability curves on surviving buildings
*NEW (operationalises G) · modern-only · ranked, review summarised*

- **Demo.** "Pretend Goldwin Smith was demolished and only N postcards survive." As N falls, the roofline drifts from the lidar truth, and the error band predicted in advance widens with it. Boardman's real configuration appears as a dot on the same chart.
- **Problem.** Is a surface identifiable from K degraded, unknown-focal photos, and can a predictor based on camera configuration alone forecast the true error against lidar?
- **Closest work.** Polic 2018; MegaDepth-X; Coloring the Past; Maiwald & Sardemann 2022; the calibration audit. The ranking also cites Szeliski & Kang 1996, Condorelli & Rinaudo 2019, Maiwald 2017 and Liu et al. 2022 (not opened here).
- **What could still be new.** Scene-level calibration of the identifiability predictor against independent lidar, and a pre-registered pivot threshold.
- **Data.** Surrogate pools: Uris/Tower (21 cameras) and Goldwin (5). Degradation is matched to the Boardman corpus: 413-3826 px, grayscale, halftone, crops.
- **Problems.**
  - The Boardman kill has effectively already fired: p90 329% unmasked and 62% masked, against a 25% bar.
  - K = 17 cannot be tested on a 21-camera pool dominated by one burst.
  - Goldwin is planar.
- **Kill test (revised by the ranking).**
  - Day 0: recompute Boardman sensitivity as the masked median/p75 displacement over the bbox diagonal, because p90 is non-monotone.
  - Then K-sweeps {6, 9, 12, 15} on Uris/Tower, scored on the Uris wing with scale fixed on the tower.
  - Keep the predictor only if within-K Spearman is at least 0.4 and beats track-count and angle baselines by at least 0.1.
- **Verdict.** Re-scope as the **calibration harness for the standpoint-certificate direction's certificate**.

### Lidar-scored active acquisition of unposed web photos
*From the handoff's active-retrieval candidate · modern-only · ranked, review summarised*

- **Demo.** Click Tjaden (0 cameras). About 300 unposed licensed thumbnails are ranked by expected geometric gain, the top 25 are downloaded, and a lidar-checked facade appears. A popularity ranking would have spent the same budget on more tower views.
- **Problem.** Expected information gain marginalised over a pose prior built from geotag, text and thumbnail retrieval. Gains are scored only by lidar/OSM, so the policy cannot be rewarded for confidently wrong geometry.
- **Closest work.** Schönberger 2015; Shen 2018; PhotoCity; FisherRF (posed candidates only); Skeletal Sets; MatchMiner; Mauro 2014; COVER.
- **What could still be new.** The most open slot found: ranking **unposed** candidates.
- **Problems.** For zero-camera buildings the triangulation-gain term is undefined, so EIG collapses to "download whatever is labelled Tjaden". Content is unmeasured, and Flickr needs a key. At an observed 0.47 registration rate × 0.76 scene rate, 10 downloads give about 4.7 registrations, below a 5-camera facade floor.
- **Kill test (revised).**
  - Day 1, content kill: per Quad-facing facade, at least 30 eligible deduplicated images (dhash ≤ 6) from at least 5 owners. The figure is ≈ 14 × 2-3; 14 is the number of downloads expected to yield 5 registered cameras.
  - Budget at least 25 per facade.
  - The method claim needs EIG at least 15% above both NetVLAD-to-model and geotag-greedy, with a 90% CI excluding 0. Relabel it a dedup heuristic if more than 80% of the gain comes from burst rejection.
- **Verdict.** The best modern-only research bet, *if* the content kill passes. Gated by a user decision on the Flickr key.

### Standpoint manifold and identifiability certificates for unknown-focal archival cameras
*From the handoff's impossible-localization candidate · adversarial review in §3.12*

- **Demo.** Drag a postcard camera along its dolly-zoom ray, and Boardman's points stretch like taffy. Toggle "the photographer stood on the ground": lidar ground plus eye height cuts the ray, the camera snaps, and the points that stay stretched glow red as "not identifiable".
- **Problem and geometry.** With distant or near-planar anchors, unknown-focal resection has a near-null direction: scale f and slide the centre along the optical axis.
  - The repo's 329% p90 sensitivity is this effect, and Maiwald 2022 reports median |Δc| = 261 px.
  - The cut: S = {DSM ground + h, h ∈ [1.2, 1.8] m} ∪ {lidar-measured elevated vantages}. Add anchor depth spread and Manhattan vanishing points.
  - The certificate is the Fisher/profile likelihood over (R, t, f, principal point), propagated to a covariance for each candidate Boardman point.
- **Closest work.** Maiwald & Sardemann 2022 (reports the failure, no fix); Mikolka-Flöry 2022 (horizon, centre free); [PFG 2025 monoplotting uncertainty](https://repositum.tuwien.at/handle/20.500.12708/220730?mode=full); Polic 2018; Hoiem 2006 and Zeisl 2015 (height priors); Bae 2010 (zoom/dolly resolved by a live photographer).
- **What could still be new.** A measured standpoint manifold as the constraint that cuts the dolly null space for cameras registered only through surviving structure. Plus a per-voxel identifiability map for a subject that no longer exists, calibrated on surviving controls. The risk is that it reduces to "resection with a height prior".
- **Probe (HYPOTHESIS, legacy model).** For 6 Boardman-titled views:
  - sd(C_ray) 0.86-1.66 model units, against a scene radius of 0.707u;
  - sd(C_up) 0.13-0.28u;
  - anchor elevation 2-13°.

  The expected leverage of a vertical prior is about 5-13x. It hinges on 1900-vs-2020 grading of the ground (Olin construction, Libe Slope), which is unverified.
- **Data.** Existing `artifacts/target_sfm_v2` and `masked_target_v3`, the library-and-tower fragment, the lidar crop, and about 10 deduplicated Commons PD prints. Exclude 100749005 and RMC items.
- **Unknowns.** Cropped postcards (unknown principal point); elevated standpoints outside S; regrading; multimodal posteriors; lens distortion; era-contaminated tracks that must be recomputed.
- **Observed 3D.** No new surface. Uncertainty is attached to geometry made elsewhere.
- **Kill test.** On degraded library-and-tower fragment controls (EXIF stripped, grayscale, halftone, crops): **kill** if the prior cuts median along-ray σ by less than 3x, or if nominal 90% intervals cover the SfM centre in fewer than 80% of views. Then re-resect Boardman on a focal grid of 0.6-1.8.
- **Paper path.** Certified cross-era resection, with a next-best-archival-view query (feeding the active-acquisition direction). Baselines: free-focal pycolmap resection, the hloc Maiwald pipeline, HistReNeRF, VGGT/Ext-3DFMs confidence.
- **Verdict.** **Recommended core**, with the corrections in §3.12: feasibility 2 not 3, and the realistic outcome is a per-image identifiability table (a calibrated negative) rather than a collapse of Boardman's points. It stays true when it fails.

### Geometric detective: era-masked multi-hypothesis registration of postcards, validated by held-out anchors
*From the handoff's geometric-detective and impossible-localization candidates · adversarial review in §3.12*

- **Demo.** Drop an unlabelled 1910s postcard. The photographer appears on the lidar Quad, along with the implied focal length, the three surviving structures that prove the pose, and the rejected look-alike poses with their scores.
- **Problem.** A multi-hypothesis posterior from three sources: anchor matches; near-field DSM skylines with buildings that postdate the photo masked out (via the Sanborn 1919 content, generator-reported); and metric-anchor focal identification. Validation: predict a held-out anchor, such as the Stimson cornice.
- **Closest work.** Bansal & Daniilidis 2014; [Skyline2GPS](https://www.merl.com/publications/TR2010-097); Mikolka-Flöry 2022; Bui 2020; HistReNeRF; Ext-3DFMs.
- **What could still be new.** A method for the regime Maiwald 2022 reports as failing, plus held-out-anchor validation.
- **Problems.** The Quad's near-field skyline has low entropy: tree-occluded rooflines and look-alike halls. Only about 10-12 independent Boardman exposures exist. Anchor depth ratio is 0.02-0.20 in the legacy model (HYPOTHESIS).
- **Kill test.** **Kill** if fewer than 60% of degraded modern controls come back within 5 m / 3° and 10% focal, or if fewer than 5 of the 24 postcards reach a unimodal posterior with at least 2 anchors.
- **Verdict.** Its era masks and held-out anchors become **modules** for the standpoint-certificate direction/the Ghost Hull direction.

### Pinned Belfry Vantage: tower-top views registered with the centre fixed to the lidar tower
*From the handoff's impossible-localization candidate · adversarial review in §3.12*

- **Demo.** The 1902 LoC cyclorama "from McGraw Tower" rotates into register with a 2013 CC BY tower-top panorama. Where 2013 shows Olin's roof, 1902 shows Boardman's.
- **Problem.** With the centre on the measured tower, unknowns drop to rotation, height and intrinsics. The 360° field of view removes the focal/depth ambiguity.
- **Closest work.** Mikolka-Flöry 2022; Maiwald 2022; HistReNeRF; Bae 2010. Known-centre rotation is textbook.
- **Problems.**
  - All tower-top views share one centre, so they cannot triangulate Boardman among themselves. A second vantage at least 5° away is needed.
  - Only 2 modern tower views are registered (a three-camera fragment), and one of them is broken.
  - The cyclorama's camera rotation may not be linear.
  - Titles disagree ("from McGraw Tower" vs "from McGraw Hall").
  - Per-file rights and content are unchecked (generator-reported counts).
- **Kill test.** Modern sanity first: median residual at most 0.2°. Then at least 2 historical views reach at most 1° with at least 8 anchors, and at least one Boardman feature is seen from two vantages at least 5° apart.
- **Verdict.** A special case of the standpoint-certificate direction's elevated-standpoint set.

### Re-occupied standpoints: calibration-free cross-era ray transfer certified by plane+parallax
*NEW · adversarial review in §3.12*

- **Demo.** A 1905 postcard is auto-paired with a modern photo taken from almost the same spot, with "standpoints coincide within 0.6 m" certified by parallax.
- **Geometry.** If the two centres coincide, H = K_m R K_h⁻¹ holds for every depth. Each archival pixel then becomes a world ray without ever separating out K_h. The [Irani & Anandan 1996](https://mlanthology.org/eccv/1996/irani1996eccv-parallax) parallax residual bounds the baseline.
- **Closest work.** Bae 2010; ARephotography 2023; [Time-lapse Mining](https://grail.cs.washington.edu/projects/timelapse/); Finding Paths. This is a modest trick.
- **Probe (HYPOTHESIS, legacy).** The nearest modern camera to each Boardman view is 0.46-1.56 median scene depths away. The only near-coincident historical view (0.08) is a library view, not a Boardman view.
- **Kill test.** **Kill** if no archival-modern pair certifies a baseline of at most 2 m, or if the bound under-covers the true baseline in more than 20% of modern-modern pairs.
- **Verdict.** **Killed on current data** (§3.12): the reviewer ran the Day-0 test read-only and every registered archival image misses the certificate's own sensitivity gate by 18-200x. Only an elevated-vantage rescue remains, and it needs a Quad-wide model that does not exist.

### Ghost Hull: certified occupancy bounds on Boardman by carving cross-era rays against the measured modern background
*From the handoff's time-portal and time-dependent-architecture candidates · adversarial review in §3.12*

- **Demo.** Drop postcards one at a time. Sky pixels become green free rays, and "something blocked the library" pixels become red must-hit segments. A translucent outer bound rises on the Olin site, with no feature ever matched on Boardman. Toggle Sanborn 1919: its footprint falls inside. Remove a postcard, and that face bulges and relabels "unobserved".
- **Problem.** Each archival image is registered only through surviving anchors and keeps its pose/focal posterior samples (from the standpoint-certificate direction). The lidar plus the library-and-tower fragment give modern background depth and class per pixel. Per-pixel rules:
  - sky → free along the ray to infinity;
  - agreement with surviving surface → free up to the modern depth;
  - disagreement → occupied somewhere on that interval.

  This gives an outer bound and a hitting-set lower bound, marginalised over the posterior.
- **Closest work.** Kutulakos-Seitz; Taneja 2011/2013 and Ulusoy-Mundy 2014 (forward in time, calibrated); Schindler-Dellaert (existence intervals, not volumes); Coloring the Past (needs an archival SfM); Bitelli, Agnello and Bevilacqua (manual).
- **What could still be new (3/5).** Backward-in-time carving under a pose/focal posterior, with no archival self-reconstruction. Plus non-circular evaluation by leave-one-surviving-building-out and containment against a dated map. That no prior work does this is "not found", not proof.
- **Data.** 24 Commons PD Boardman files; LoC 1900 panoramas (generator-reported); Sanborn 1919 (PD); lidar; the library-and-tower fragment. Archival views of surviving Uris/Tower exist in the legacy joint model (e.g. 114171695 "Uris Library 1900", 151190611 "1906", 154792750, 111441145), giving built-in controls.
- **Probe (HYPOTHESIS, legacy).**
  - Boardman-titled cameras span only about 53° of azimuth, from one quadrant, and include duplicate pairs (114317667/151148635; 155823882 front/back). That leaves about 4 independent views.
  - Perpendicular ray 1-sd at mid-depth: 0.06-0.10u, against a scene radius of 0.71u.
  - So expect an open wedge on the far side.
- **Observed 3D.** 0% Boardman surface by design. It is a measured constraint set with ray provenance for every face.
- **Kill test.**
  - Sanborn georeference RMSE above 5 m kills map validation.
  - Fewer than 3 independent prints passing the standpoint-certificate direction's gate, or azimuth spread under 60°, kills the Boardman stage.
  - The tower control must contain the lidar tower, overestimate its volume by less than 3x, and change width by less than 25% under ±1° and ±5% focal perturbations.
- **Paper path.** "Measuring what is gone." Baselines: Coloring-the-Past-style archival SfM+MVS (the repo's focal-unstable outputs), feed-forward reconstruction of the archival set, naive single-pose change detection. Evaluation: leave-one-surviving-building-out across buildings visible before 1934.
- **Verdict.** **Best publication bet**, built on the standpoint-certificate direction, with the coverage floor from §3.12: on the registered views a closed volume is unreachable, so the certifiable output is a 2.5D bound (north facade, east-west extent, roof cap) unless a third azimuth bin registers.

### 3.12 Adversarial reviews of directions standpoint-certificate to Ghost Hull (added after drafting)

Each direction below had one reviewer trying to show it is already published and one trying to show it cannot work on online-only data on this machine. Where they disagree with the write-ups above, these reviews win. Numbers from `artifacts/hloc_cross_era/sfm_joint` are HYPOTHESIS; numbers from `report.json` files, `data/raw/manifest.json` and the Commons/LoC pages are VERIFIED.

**the standpoint-certificate direction Standpoint certificates.** *Novelty 3, not already done. Feasibility 2, robustness 3.*
- Closest prior the write-up missed: Mikolka-Flöry et al., *Uncertainty of object points monoplotted from terrestrial images* (PFG 2025, full text read) and the moniQue QGIS plugin (ISPRS OJPRS 2026) already propagate unknown-focal resection uncertainty of c.1900 photos against a lidar DTM to per-pixel maps. What they do not do: a camera-position prior (their centre uncertainty "may reach several meters"), points off the surviving surface (monoplotting intersects the terrain), or a next-view query. That residue is the standpoint-certificate direction's claim, and it is incremental per part.
- Geometry, measured by a linearised Fisher analysis with R, C, f, cx, cy free: the null direction runs from the centre toward the anchor centroid, not along the optical axis, so the standpoint manifold S cuts it only through sin(anchor elevation). Elevations of the five independent exposures are 12.6°, 4.6°, 4.7°, 2.2° and 0.1°; predicted along-ray shrink from S is about 80 / 60 / 30 / 20 / 0 %. sd(log f) is 0.12-0.26 (0.63 for the Stimson card); freeing the principal point roughly doubles it, and cropped postcards require it free. The write-up's "5-13x leverage" and "≥3x median" kill threshold are therefore too optimistic; the reviewer's bar is a ≥30 % f-interval shrink on at least 3 independent images with the post-S along-ray interval ≤10 % of the anchor distance, and an ablation of S against parallax and vanishing points, so the shrink cannot be attributed to the other terms.
- Data: 114317667/151148635 are one 1934 Curt Teich card; 127452280/192537626 may be one negative reused by two publishers. That leaves 4-5 independent anchored exposures in two viewing clusters about 45° apart, each with 11-39 anchor matches confined to a near-planar strip (depth ratio 1.02-1.21). Ceiling about 5-6.
- Dependence: S is undefined until the library-and-tower fragment is registered to lidar with gravity tilt σ ≤ 0.5°, scale σ ≤ 3 % and vertical σ ≤ 0.5 m. The modern control as written is circular (full-frame library-and-tower fragment cameras scored against their own bundle); it must be leave-one-out with tower-strip-matched anchor subsets.
- Revised 4-day kill test: Day 0.5 dedup and count (KILL the Boardman claim if fewer than 4 independent anchored exposures); Day 1 re-resect against the library-and-tower fragment with f, cx, cy, k1 free and pre-register each image's predicted shrink; Day 2 lidar frame gate; Day 3 non-circular control; Day 4 GO only if ≥3 images pass both bars, and KILL if the only passing image is the tilted 1934 card or if measured shrinks disagree with Day-1 predictions by more than 2x (which would mean the certificate itself is miscalibrated).
- Effect on the decision: the standpoint-certificate direction stays the recommended core, because its negative is a deliverable, but the plan must present the identifiability table as the expected result and the "snap" as the hoped-for one.

**the geometric-detective direction Geometric detective.** *Novelty 3, not already done (a setting and an evaluation, not a mechanism). Feasibility 2, robustness 2.*
- The write-up's central claim is wrong: a known metric anchor height H fixes only f/Z (h = fH/Z). Separating f from Z needs anchor depth variation or vanishing points with a known principal point. Measured on the six registered postcards with persistent anchors only: anchor bounding boxes cover 2.8-23 % of the frame, depth spread p90/p10 is 1.01-1.20, PnP with f fixed anywhere in 0.8-1.25x keeps the median residual at 1.1-2.4 px, and the centre slides 20-25 % of the range. **0 of 6 are identified with persistent anchors alone.** The sharp focal minimum seen with all points comes from Boardman-only tracks triangulated by the same images, i.e. it is circular.
- The held-out-anchor test has little power: library and tower are one rigid cluster at one depth, so a held-out anchor at that depth reprojects correctly for every member of the ambiguous family. Stimson is the only depth-diverse anchor and has 0 registered modern cameras.
- Prior work to add as baselines: moniQue 2026 and the Mikolka-Flöry rendered-scene matcher; Schindler & Dellaert 2010 for era-aware visibility; Russell 2011 and Aubry 2014 for painting/photo-to-3D alignment (not opened).
- Salvage (HYPOTHESIS): use Sanborn footprint corners as vertical lines at known XY (depth ratio 2-3 against the tower), which also brings the ~9 anchor-free frontal views into scope, but then Sanborn can no longer be the validator and its 1-3 m drafting/georeferencing error enters directly.
- Effect: the geometric-detective direction's modules (era masks, multi-hypothesis output) still feed the standpoint-certificate direction/the Ghost Hull direction, but its own "detective" claim is not supportable on 5-9 independent queries.

**the belfry-vantage direction Pinned Belfry Vantage.** *Novelty 2, already done in substance (Acar 2012 locates a vanished building from a 1903-07 photo with surviving control, 1.84 m error; Agnello 2019 and Sant'Alberto 2017 do it with TLS; Luhmann 2004 and Parian & Gruen 2005 cover panorama sensor models). Feasibility 3, robustness 2.*
- Every tower view shares one centre to within the belfry width, so the tower set has zero mutual baseline for Boardman. All depth must come from a non-tower vantage, and that vantage is exactly the standpoint-certificate direction/the geometric-detective direction regime. A 5° triangulation angle is not a GO criterion: at ~5 m lateral error on the second ray it implies ~60 m depth σ, the length of Boardman; single-digit metres need ~30°, which the geometry does allow from the north end of the Quad.
- Data: of the 23 "Views from McGraw Tower" files, one measurement-grade historical view (the 1902 Sheldon cyclorama, 3487x448 px on Commons, titled "from McGraw Hall" in the filename) plausibly covers Boardman's azimuth; the Troy colour postcards are retouched photomechanical prints; the NARA "1892" is a series date. The 2013 panorama is a software stitch of unknown projection and cannot be the datum.
- Effect: a module of the standpoint-certificate direction elevated-vantage set, not a direction. Its Day-0 test (open the LoC TIFF, check coverage ≥300° and that Boardman's band is unoccluded) costs an hour and should run before anything else is built on the cyclorama.

**the re-occupied-standpoint direction Re-occupied standpoints.** *Novelty 2. Feasibility 1, robustness 1. Day-0 kill already fired on existing data.*
- The mechanism (homography to a co-located reference camera, then lift rays) is the Mountain Legacy Project IAT pipeline (Tricker et al. 2023, full text read) and Bae 2010 §4.5. The certificate is not a valid bound: a single homography absorbs parallax, and the forward (dolly) baseline component vanishes near the principal point where the tower sits.
- Measured on every genuine registered archival image, persistent-anchor points only: inverse-depth spread Δ(1/Z) between the 10th and 90th percentiles is 0.0000-0.0011 /m against the direction's own gate of 0.02 /m; plane+parallax sensitivity is ≤0.7 px per metre of baseline (11 of 13 images ≤0.2 px/m) against a required 1.5 px/m. At a realistic 2-3 px cross-era residual no image certifies better than 3-4 m, most only 10-30 m. The near layer that would give sensitivity (lamp posts, paths, trees) is exactly what did not survive the century, so more modern photos cannot fix it.
- Effect: moved from "deferred" to **killed on current data**. The only rescue is physically constrained elevated standpoints (tower level, building windows) with a surviving near layer; that needs a Quad-wide model and at least 2 PD from-tower archival views of the Boardman site, and is listed as a contingent HYPOTHESIS only.

**the Ghost Hull direction Ghost Hull.** *Novelty 3, not already done end to end (Guan 2006 conservative hulls under known occluders; Kutulakos-Seitz carving; Urban Radiance Fields sky rays; Du 2016 old-imagery-vs-new-lidar demolition detection; Bitelli 2017 and Bevilacqua 2019 manual lost-volume restitution; HistReNeRF 2026 relocalisation). Feasibility 2, robustness 2.*
- Coverage floor, which pose precision cannot fix: the registered Boardman views fall in two azimuth bins about 50-55° apart (about -90° and -140° about the Boardman centroid; all 14 registered historical images lie in one 90° sector). An oracle hull carved from *perfect* silhouettes in plan is 2.4-3.7x the Sanborn footprint area (1.7-2.3x with a ground-support prior). The write-up's "<2x Sanborn" gate is therefore at or beyond the geometric floor on current data. A third bin (candidates 115118987 from the east with Stimson, 150099180 from the Goldwin Smith arcade) is unregistered; Stimson has 0 modern cameras.
- Inliers: cross-era anchor observations per image are 39, 37 (duplicate), 25, 23, 15 and 11, so only one independent negative clears the direction's own 30-inlier bar.
- Pose is not the kill for the lawn cards: perpendicular ray error at half the anchor depth is 0.06-0.10 scene units, roughly 1.2-2.5 m if 1 unit ≈ 20-25 m (unverified scale); the Stimson card is nearly useless (6-8 m). The ±1° / ±5 % sensitivity test in the write-up is 2-9x narrower than the measured posterior and would pass vacuously.
- The lower bound is near-vacuous: the modern background along Boardman rays is Olin, which must be deleted, leaving "occupied somewhere before a far background". Ground rays are grazing (~27 m depth error per degree at 50 m). Hand-coloured cards can have retouched rooflines, which breaks one-sidedness. The McGraw Tower leave-one-out control is infeasible because the tower *is* the anchor in these frames; Stimson (post-1903 images only) is the usable control.
- Honest identifiable output on current data: a 2.5D bound (north facade plane, east-west extent, roofline cap, each ±3-5 m at 2σ), not a volume. The defensible contribution is the evaluation protocol (leave-one-surviving-building-out against lidar plus containment in an independently georeferenced dated map), which could stand as a protocol/benchmark paper by itself.
- Revised gates. Day 0: oracle coverage ≤1.5x the Sanborn footprint (currently 1.7-3.7x, so no volume claim unless a third viewing direction registers). Day 1: Sanborn georeference RMSE ≤2 m on ≥6 persistent footprints, and lidar fit RMSE ≤1 m with the unit-to-metre scale agreeing with the tower height within 10 %. Days 1-2: third-direction rescue with ≥30 inliers on ≥2 distinct buildings and 2σ perpendicular ray displacement ≤3 m at the facade. Days 3-4: real carve with Sanborn containment ≥90 %, real/oracle area ≤1.3, per-face slack ≤5 m, ridge-height spread ≤4 m, and the Stimson control passing the same bars.

**Does §3.12 change the recommendation?** Not the ordering, but the framing. single-fragment lidar anchoring → the standpoint-certificate direction remains the balanced default and the Ghost Hull direction the publication path, because both have a legitimate negative output. the re-occupied-standpoint direction is removed from the deferred list. Three things become mandatory in the plan: (1) the Boardman expectation is stated up front as "unidentifiable surface, 2.5D bound at best, with a map of the missing standpoint"; (2) the standpoint-certificate direction's kill test uses the reviewer's bars and ablation, not the write-up's; (3) the one-hour the belfry-vantage direction Day-0 check on the 1902 cyclorama and a Commons/LoC search for a third azimuth bin run first, because they decide whether the Ghost Hull direction can ever be more than 2.5D.

---

## 4. Decision matrix

Scores are 1-5. Do not average them. Every direction carries both adversarial reviews; the directions standpoint-certificate to Ghost Hull rows below use the reviewers' scores from §3.12 where they differ from the ranking pass (the standpoint-certificate direction feasibility 3→2 and robustness 4→3; the geometric-detective direction novelty 2→3; the Ghost Hull direction unchanged at 3/2/2).

| Direction | Demo surprise | Novelty | Feasibility | Robustness | Modern-asset value | Publication path | Strongest objection |
|---|---|---|---|---|---|---|---|
| the lidar-glued Quad direction Lidar-Glued Quad | 3 | 2 | 3 | 3 | **5** | 2 | Daruna 2026, Wendel 2011 and Strecha 2010 already merge/snap through geodata. Only the library-and-tower fragment is a usable input. Refutation has no power on planar fragments and is matched by an EXIF sanity check |
| the impossible-photographer direction Impossible Photographer | 4 | 2 | 2 | **1** | 2 | 2 | Blind to the real Stone Row error (row translation keeps every term satisfied). Every term has a precedent. Circular with the lidar-glued Quad direction. Zero placeable Stone Row fragments |
| the sun-and-shadow direction Sun as landmark | 3 | 2 | 2 | 2 | 2 | 2 | Photo clock published (Hauagge 2014, Wehrwein 2015, Troccoli 2004, Lynch). 1-3 of the 6 needed shadow sessions. The demo photo has no qualifying shadow. EXIF is not ground truth |
| the leaf-off see-through direction Leaf-off X-ray | 3 | 2 | 3 | 2 | 3 | 2 | Whyte 2009 is the demo. Season is confounded with one session (84% of 3+-view points from March09). PatchMatch already selects views per pixel. No dense S |
| the simulated-demolition direction Simulated demolition | 3 | 2 | 3 | 3 | 4 | 2 | Classical network-design pre-analysis. The Boardman kill has already fired. K = 17 cannot be tested on a burst-dominated 21-camera pool |
| the active-acquisition direction Active acquisition | 4 | **3** | 2 | 2 | **5** | 3 | EIG is undefined for zero-camera buildings. Content is unmeasured. Flickr needs a key. 10 downloads give about 4.7 registrations |
| the standpoint-certificate direction Standpoint certificates | 4 | 3 | 2 | 3 | 3 | 3 | PFG 2025 / moniQue 2026 already propagate unknown-focal resection uncertainty against lidar terrain. S cuts the null direction only through sin(anchor elevation): predicted shrink 80/60/30/20/0 % on the five independent exposures, so the "≥3x" bar is unrealistic. 4-5 independent exposures, near-planar anchors, free principal point doubles sd(log f) |
| the geometric-detective direction Geometric detective | **5** | 3 | 2 | 2 | 4 | 3 | Known anchor height fixes only f/Z; measured 0 of 6 postcards identified with persistent anchors alone (residuals flat over 0.8-1.25x focal). Held-out anchors at one depth have no power. 5-9 independent queries |
| the belfry-vantage direction Pinned Belfry | 4 | 2 | 3 | 2 | 3 | 2 | Known-centre rotation is textbook. One centre cannot triangulate. Only 2 modern tower views are registered, one of them broken |
| the re-occupied-standpoint direction Re-occupied standpoints | 3 | 2 | **1** | **1** | 2 | 2 | IAT/Bae 2010 mechanism; certificate is not a bound. Day-0 kill fired: sensitivity ≤0.7 px/m vs 1.5 required, Δ(1/Z) ≤0.0011 vs 0.02 /m, on every registered archival image |
| the Ghost Hull direction Ghost Hull | **5** | **3** | 2 | 2 | 4 | **4** | Oracle hull from perfect silhouettes in the two registered azimuth bins is 2.4-3.7x the Sanborn footprint, so a closed volume needs a third bin that is not registered. One independent view clears 30 inliers. Certifiable output today is 2.5D |

**Choices:**
- **Best demo-first:** the standpoint-certificate direction as the "dolly-zoom ray" interaction, built on single-fragment lidar anchoring. If the cut fails, the demo honestly shows the stretch and the red labels. The ambiguity it visualises is VERIFIED (p90 329%, median 10.6%). Runner-up: single-fragment lidar anchoring "snap the library-and-tower fragment onto lidar, with the tower held out".
- **Best publication potential:** the Ghost Hull direction, with the standpoint-certificate direction as its engine and the simulated-demolition direction re-scoped as its calibration harness.
- **Best balanced (recommended default):** single-fragment lidar anchoring → the standpoint-certificate direction, with the simulated-demolition direction's harness folded in, upgrading to the Ghost Hull direction only if it is certified.
- **Abandon: the impossible-photographer direction.** The row-translation doppelganger leaves free space, height, line of sight and the point-to-surface terms all satisfied. The method only catches gross errors that existing tools already catch. This is a structural failure, not a missing-data problem.
- **Demoted, not abandoned:**
  - the sun-and-shadow direction: keep the solar-flip rejection as a module.
  - the re-occupied-standpoint direction: killed on current data (§3.12); only the elevated-vantage rescue remains as a HYPOTHESIS.
  - the leaf-off see-through direction: keep provenance and holes as viewer features.
  - the geometric-detective direction and the belfry-vantage direction: become modules of the standpoint-certificate direction leading into the Ghost Hull direction chain.

**Tradeoffs.**
1. **The common bottleneck.** Every direction is limited by the same thing: one alignable fragment and no metric frame. The real trade is between how much a direction depends on single-fragment lidar anchoring and how far it reaches.
2. **Surprise vs. truth.** The highest-surprise directions (the geometric-detective direction, the Ghost Hull direction) sit on the thinnest data. the standpoint-certificate direction is one point less surprising but cannot be "falsified into embarrassment".
3. **Novelty vs. feasibility.** The best residual novelty (the active-acquisition direction, the Ghost Hull direction; 3/5) is gated by unmeasured content and by closure.
4. **Infrastructure vs. contribution.** the lidar-glued Quad direction has the best asset value but should be infrastructure, not the claimed contribution.

---

## 5. Top 3 pitches

### Pitch 1: Dolly-zoom certificate (single-fragment lidar anchoring + the standpoint-certificate direction), the recommended default

- **10-second script.** "This 1905 postcard was registered using only the surviving library tower. Drag its camera along this ray: every position fits the tower equally well, and Boardman Hall stretches like taffy. Now tell it the photographer stood on the ground. The lidar lawn cuts the ray, the camera snaps, and most of Boardman's roofline collapses to a tight band. The red parts never collapse: the surviving record cannot tell you where they were."
- **Hypothesis.** For archival cameras registered only through surviving structure with anchor elevation of about 2-13°, the focal-dolly null direction is long. Legacy probe (HYPOTHESIS): along-ray sd 0.86-1.66u, vertical component sd 0.13-0.28u.
  - A lidar standpoint prior (ground + 1.2-1.8 m, with a grading-uncertainty term, union measured elevated vantages) should cut along-ray σ by about sd(C_ray)/sd(C_up), roughly 5-13x.
  - The resulting intervals should be calibrated: on degraded modern controls, the truth falls inside the nominal 90% interval for at least 80% of cameras.
- **Data.**
  - 3DEP EPT (PD), cropped about 300 × 300 m around Uris/Olin and reprojected to UTM 18N.
  - the best learned run on the 145-photo snapshot the library-and-tower fragment (Commons CC BY/BY-SA).
  - About 10 deduplicated PD Boardman prints. Exclude 100749005, RMC items and interiors.
  - Degraded library-and-tower fragment controls.
  - Optional: Sanborn 1919 sheet 35.
- **Kill test (4 days, CPU).**
  - **Day 0.5:** EPSG:3857 → UTM 18N, checking the 1.355x horizontal stretch against an OSM edge. **Kill** the frame if the reprojected edge misfits the lidar edge by more than 0.5 m.
  - **Days 1-2:** single-fragment lidar anchoring the held-out-tower gate/the camera-height gate (§3 the lidar-glued Quad direction). **Kill** all metric claims if the held-out-tower gate fails.
  - **Day 3:** positive control, re-resecting degraded library-and-tower fragment views from anchors only, with and without the prior. **Kill** the certificate if σ drops by less than 3x, or if coverage is below 80%.
  - **Day 4:** clean re-resection of the Boardman prints against the library-and-tower fragment on a focal grid of 0.6-1.8, with per-camera profile likelihood and per-voxel σ.
  - **Pre-registered pivot:** a Boardman surface claim is allowed only if at least 3 independent prints reach along-ray 1σ ≤ 3 m, pairwise triangulation angle ≥ 5° and azimuth spread ≥ 60°. Otherwise ship the certificate map as the result.

### Pitch 2: Ghost Hull with surviving-building controls (the Ghost Hull direction on the standpoint-certificate direction engine)

- **10-second script.** "Drop 1900s postcards onto today's lidar Quad one at a time. Sky pixels become green free rays and blocked pixels become red must-hit segments. With no feature ever matched on Boardman itself, a translucent outer bound rises on today's Olin site. Toggle the 1919 fire-insurance map: its footprint lies inside. Pull out one postcard and that face bulges and turns 'unobserved'."
- **Hypothesis.** Backward carving under a the standpoint-certificate direction posterior gives outer and lower bounds that contain the truth.
  - Test it first on surviving Uris and the Tower treated as vanished: the hull must contain the lidar tower at less than 3x its volume.
  - Only then apply it to Boardman: closed on at least 3 sides in plan, containing at least 90% of the georeferenced Sanborn footprint at less than 2x its area.
- **Data.** Pitch 1's data; archival Uris/Tower views from the 35 accepted historical images, with era labels re-audited; LoC Sanborn 1919 georeferenced to at least 6 persistent footprints; an off-the-shelf sky segmenter, recorded as a learned cue.
- **Kill test.**
  - **Day 1:** Sanborn RMSE above 5 m kills map validation. Fewer than 3 independent prints passing the standpoint-certificate direction's gate, or azimuth spread under 60° (legacy suggests about 53°), kills the Boardman stage.
  - **Days 2-3:** carve a 0.5 m voxel grid.
  - **Day 4:** the tower control must contain the lidar tower at less than 3x volume, with width change under 25% at ±1° and ±5% focal perturbations.
  - If the tower control passes but Boardman fails closure: publish the method on surviving controls and show Boardman as an honestly open wedge.

### Pitch 3: Content-first active acquisition for zero-camera facades (the active-acquisition direction), modern-only

- **10-second script.** "The Quad map is coloured by measured support. Tjaden, Sibley and Lincoln are black: zero cameras. Click Tjaden. The system scores about 300 licensed, unposed thumbnails, downloads the top 25, and a Tjaden facade appears, checked against lidar roof edges. A popularity ranking spent the same budget on more McGraw Tower views."
- **Hypothesis.** Enough licensed content exists. EIG marginalised over a pose prior buys more lidar-anchored 3-view facade cells per CPU-hour than NetVLAD-to-model or geotag-greedy. Most of the gain should come from avoiding rotation-only shots and bursts.
- **Data.** The Commons tree (228 downloaded); Flickr licence IDs 4/5/7/8/9/10 only (key needed, user decision); the 963 Quad6K Flickr IDs re-resolved for licence; lidar/OSM as truth.
- **Kill test.**
  - **Day 1:** the per-facade content kill: at least 30 eligible unique images from at least 5 owners.
  - **Day 2:** resume the interrupted 228-photo run; single-fragment lidar anchoring. If the wall residual on held-out anchors exceeds 0.5 m, label results "unanchored".
  - **Days 3-4:** policies at a 40% budget with bootstrap. The method claim needs EIG at least 15% above both baselines, with the 90% CI excluding 0.

---

## 6. Recommended thesis

**"What can the surviving world prove about the vanished one?" Certified cross-era evidence on the Cornell Arts Quad.**

**What is new.** Each item is stated as a delta against specific work.
1. **A lidar-measured standpoint manifold** used to break the focal-dolly null direction of unknown-focal archival cameras registered only through surviving structure.
   - Zeisl 2015 uses an internal ±5 m band for modern localization.
   - Mikolka-Flöry 2022 handles alpine far-field horizons, with no missing subject and a free centre.
   - Maiwald & Sardemann 2022 report exactly this regime failing.
2. **Per-voxel identifiability certificates for the vanished subject.** They are calibrated at scene level, not asserted, using degraded modern controls and leave-one-surviving-building-out against lidar. Polic 2018 computes covariance; the calibration audit (2608.29705) shows learned confidence is miscalibrated.
3. **Backward-in-time occupancy bounds, only where certified.**
   - Taneja and Ulusoy-Mundy work forward in time with calibrated cameras.
   - Schindler-Dellaert infer existence intervals, not volumes.
   - Coloring the Past requires an archival self-reconstruction, which is unidentifiable here.

Novelty per component is modest (2-3/5). The paper's value is the combination plus a **non-circular evaluation protocol for cross-era geometry**. HistReNeRF's ground truth is circular, and the sweep found no terrestrial cross-era benchmark with trustworthy ground truth.

**What is genuinely reconstructed.**
- Comp 0 (21 cameras, 2,686 points), plus OpenMVS where fusion succeeds, in a metric UTM frame with stated residuals.
- A separately rendered, measured 3DEP lidar layer.
- Archival camera *posteriors*, not point poses.
- For Boardman: bounds and an identifiability map, **never a surface**, unless the pre-registered gate passes. Current evidence (p90 329%, median 10.6%) predicts it will not.

**Why the Arts Quad.**
- Public-domain QL2 lidar covers it (verified against the EPT bounds).
- McGraw Tower is a tall persistent vertical anchor (built 1891), seen in both eras.
- The Boardman/Olin site is adjacent to the only alignable modern fragment.
- There are 24 PD Boardman prints (1898-1934), plus 1900-1906 views of the surviving Uris and Tower, which act as built-in controls.
- A dated PD Sanborn map provides independent footprint validation.
- It sits inside the Cornell/Snavely lineage (Quad6K, PhotoCity), which makes the question "what does internet-photo 3D still fail to certify?" easy to place.

**Decision requested.** Before any implementation, I ask the user to approve:
- the pivot from "reconstruct Boardman" to "certify what can be known about Boardman";
- the  software installs;
- whether to obtain a Flickr API key (needed for the active-acquisition direction only).

---

## 7. Modern Arts Quad improvement strategy

The evidence points two ways. Rank by what is binding, and run the cheaper discriminating test first.

**Most impactful improvement: more good, independent views of the facades that have no support.**
- 8 of 14 targets have zero cameras from 1-5 train images each.
- 41 of 77 images do not register.
- Exhaustive SIFT found fewer verified pairs (43) than NetVLAD (205).
- Comp 0 is 65% one burst.

No SfM strategy can triangulate Tjaden from 3 photos. The content source is uncertain, though: Commons is largely harvested, the Flickr CC count is unmeasured, and IDs 1/2/3/6 are NC/ND.

**Cheapest first action, which separates the two hypotheses.** Add crop-aware EXIF focal priors (131 of 228 records carry a 35mm-equivalent focal, per the ranking) and re-map the existing the best learned run on the 145-photo snapshot database. Also resume the interrupted 228-photo run.
- If the 65/67-connected graph stops fragmenting into 6 models, with focals inside EXIF bounds, calibration was splitting the graph.
- If not, content dominates.

The ranking step counted 269 of 772 pairs remaining in the interrupted 228-photo run, while the audit records 144 of 585 *new* pairs done. Reconcile the accounting before resuming.

| Priority | Area | Actions |
|---|---|---|
| 1 | Data acquisition | Per-facade content counts first (the active-acquisition direction Day 1). Dedup and group by owner; stop admitting bursts as independent views. Reject non-scene images. Re-audit era labels (114998420, 100749005). Resolve or withdraw the two Cornell-archive items served from `dist/assets/repair/historical-archive/`. |
| 2 | Geometry | EXIF focal priors and fixed-radial controls. After freeing about 1 GB of regenerable artifacts, try a CUDA torch build (about 2.5 GB) and a CUDA COLMAP/pycolmap; this unblocks PatchMatch, and the GPU is already present. **Check, don't assume,** whether the installed build exposes a global mapper. Run a Doppelgangers-style check on Stone Row pairs before any merge. OpenMVS on CPU for the library-and-tower fragment at 1280 px. |
| 3 | Validation (the real trust lever) | single-fragment lidar anchoring metric frame in UTM 18N with the held-out-tower gate/the camera-height gate. Family- and session-disjoint holdouts, including leave-March09-out. Per-facade 3-view coverage against lidar footprints. Full reprojection distributions, not means. Completeness reported with holes. |
| 4 | Viewer (last; not the blocker) | Per-region support colouring. The lidar layer kept visibly distinct from photo geometry. Click-through provenance (URL, licence, hash). Keep the library-and-tower fragment's epoch quarantine until 114998420 is resolved. |

**Smallest viable target scene.** The south end of the Quad: Uris Library, McGraw Tower, the Olin/Boardman site, and the Stimson/Goldwin edges, about 250-300 m square of lidar. Quad-wide work stays the ambition, unlocked by gate  in §8.

---

## 8. Next experiments and go/no-go gates

None of this has been executed. Installs and downloads need user approval. Ordered by cost.

| Step | Cost | Test | GO | NO-GO consequence | Why this threshold |
|---|---|---|---|---|---|
| Free disk | minutes | Disk plan (recommendation only). About 1 GB is regenerable: `cpu_mvs_modern_v2` 299M, `cpu_mvs_target_v2` 107M, `cpu_mvs_joint_historical` 118M, failed runs another error-status run (155M) and an error-status run (239M), a duplicate 148 MB SuperPoint h5 in the first 46-photo pilot run/a second 46-photo learned run | user approves | no installs | 7.2 GB free at 97% use |
| Lidar crop and reprojection | hours | Install laspy[lazrs] + pyproj; crop the EPT; reproject EPSG:3857 → UTM 18N (EPSG:6347); check for building class 6 | reprojected OSM/lidar edge ≤ 0.5 m; stretch ≈ 1.355x confirmed | stop all metric work. If there is no class 6, use DSM − DTM with a vegetation mask | a Sim(3) fitted in Web Mercator is wrong by construction |
| Boardman sensitivity recomputed | hours | Recompute Boardman sensitivity as masked median/p75 over the bbox diagonal | — | informs  | p90 is non-monotone |
| Re-map with EXIF focal priors | hours | Re-map the best learned run on the 145-photo snapshot database with crop-aware EXIF focal priors; resume the interrupted 228-photo run on the 228-photo snapshot | components merge with sane focals → calibration was the culprit. Quad-wide GO if the 228-photo snapshot yields ≥ 30 Uris/Tower cameras from ≥ 10 families, March09 < 35% of observations, and ≥ 1 non-library-and-tower fragment volumetric fragment | content-first (the active-acquisition direction) | separates blocker 1 from blocker 2 |
| Anchor the library-and-tower fragment | 1-2 days | single-fragment lidar anchoring the held-out-tower gate (held-out tower: ≤ 1.0 m vertical, ≤ 1.5 m horizontal, inside own 95% interval; scale ±2%; ≥ 30% better than ICP; leave-March09-out within 1 m) and the camera-height gate (≥ 17 of 21 centres 0.5-3 m above the DTM) | both pass | viewer stays similarity-only, labelled "unanchored"; historical stages stop | 1.5 m at 100 m ≈ 0.86° ≈ 25-30 px at f ≈ 1900, the resection basin; below building spacing |
| Dense surface for that fragment | ~1 day | OpenMVS on the library-and-tower fragment; per-facade 3-view coverage against lidar footprint edges | report coverage | report holes as holes | — |
| Content count per facade | 1 day (optional) | the active-acquisition content count: ≥ 30 eligible unique images from ≥ 5 owners per facade | per facade | drop that facade from the demo | 5 cameras / (0.47 × 0.76) ≈ 14, × 2-3 |
| Re-resect the Boardman prints | 1-2 days | Clean re-resection of about 10 deduplicated PD prints against lidar-anchored the library-and-tower fragment, with era masks (the geometric-detective direction), solar-flip rejection (the sun-and-shadow direction) and the belfry vantage (the belfry-vantage direction) | — | — | — |
| Positive control for the certificate | 1 day | the standpoint-certificate direction positive control on degraded library-and-tower fragment views | σ cut ≥ 3x and 90% coverage ≥ 80% | ship the dolly demo labelled "uncertified" | below 3x the cut does not change any downstream decision |
| Boardman surface decision | — | Boardman surface pivot (pre-registered) | ≥ 3 independent prints with along-ray 1σ ≤ 3 m, angle ≥ 5°, azimuth spread ≥ 60° | bounds only (the Ghost Hull direction) | 3 m is below one window bay and half a storey |
| Simulated-demolition harness | 1 week | the simulated-demolition direction harness: K ∈ {6, 9, 12, 15} on Uris/Tower; does sensitivity or covariance predict true lidar error? | within-K Spearman ≥ 0.4 and ≥ 0.1 above track-count/angle baselines | certificate is uncalibrated | — |
| Ghost Hull bounds | 1-2 weeks | the Ghost Hull direction: tower control (contains lidar tower, < 3x volume, stable under ±1° and ±5% focal), then Boardman (closed on ≥ 3 sides, ≥ 90% of Sanborn footprint, < 2x area, georeference RMSE < 3 m) | both pass | publish the method on surviving controls; Boardman shown as an open wedge | — |

**Commands for the lidar step, after approval.** These are illustrative; exact crop code is to be written then.
```
.venv/bin/pip install "laspy[lazrs]" pyproj
# EPT source (public domain): https://s3-us-west-2.amazonaws.com/usgs-lidar-public/NY_FingerLakes_1_2020/ept.json
# Reproject every crop EPSG:3857 -> EPSG:6347 (UTM 18N) before any fitting; log the class histogram.
```

**Proposed architecture (conditional on approval of the pivot):**
1. A 3DEP lidar crop in UTM 18N, kept as a separate measured layer (DSM, DTM, building/vegetation classes).
2. A library-and-tower fragment Sim(3) into that frame, gated by the held-out-tower gate/the camera-height gate, with residuals and the epoch quarantine stored with the transform.
3. Anchor-only archival resection: focal-grid posterior samples, the standpoint-manifold prior, era masks and the solar-flip test.
4. Per-camera profile likelihood, and per-voxel certificates calibrated on degraded modern controls and surviving buildings.
5. Carving only on certified voxels, with an outer bound, must-hit segments, and per-face ray provenance.
6. A viewer that keeps three layers distinct (measured photo geometry, measured lidar, bounds and certificates), with click-through provenance, explicit holes, and the quarantine kept.

**Do not**, in this phase:
- run a Quad-wide reconstruction or a download campaign;
- install a CUDA stack before freeing disk space;
- touch the site;
- treat any legacy `sfm_joint` number as clean cross-era evidence.

---

## 9. What I would tell a skeptical 3D-vision professor

1. **Little here is new as a component.** All of these are published, and we do not claim them:
   - lidar/DSM georegistration of SfM (Wendel 2011; Daruna 2026);
   - track-free merging (Strecha 2010; Cohen 2015);
   - photo dating from sun and shadows (Hauagge 2014; Wehrwein 2015);
   - see-through compositing (Whyte 2009; Photo Uncrop 2014);
   - skyline orientation (Bansal 2014; Mikolka-Flöry 2022);
   - camera-height priors (Zeisl 2015);
   - archival relocalization (HistReNeRF 2026; Maiwald 2022);
   - carving and change detection.
2. **The claim is narrow and testable.** For archival cameras registered only through surviving structure, a lidar-measured standpoint manifold cuts the focal-dolly null direction enough to give *calibrated* per-voxel identifiability for a vanished building. Where certified, backward carving gives occupancy bounds that contain the truth. This is tested first on surviving buildings treated as vanished, then against a dated public-domain Sanborn footprint.
3. **Limitations, stated up front.**
   - Exactly one alignable modern fragment exists: 21 cameras, 65% from one burst.
   - No metric frame has been established.
   - Calibration is unstable (the same image is fitted at focal ratios 0.27, 3028 and 6519).
   - About 4 independent Boardman views exist, from one azimuth quadrant, mostly hand-coloured.
   - The probe numbers I quote come from an unscaled, era-contaminated legacy model.
   - The standpoint prior depends on unverified 1900-vs-2020 grading.
   - **The most likely Boardman outcome is "surface unidentifiable; here is the map of why."**
4. **Why it is still worth doing.** The negative result is rigorous and visual. The evaluation protocol fills a gap the sweep found. The lidar-anchored modern fragment is reusable.
5. **What would falsify us cheaply:** the UTM projection check (hours); the held-out-tower gate tower holdout (2 days); degraded-control interval coverage (1 day); the tower-hull control. If they fail, we say so and stop.

---

## Appendix: answers to the handoff's §7 questions

**Why did Noah's demos surprise?** Each one unlocked a capability, not a rendering style:
- 2006: the collective photo record became a navigable 3D space that no single photographer had.
- 2014: 3D points acquired lifetimes, so time could be read off geometry.
- 2023: appearance and change were disentangled, so unseen time-viewpoint combinations became renderable.

In each case, 3D made a hidden variable of the collection observable. The open question here: when the subject is gone and the cameras are uncalibrated, what does the collection still *certify*? The 3D-plus-timeline overlay itself is prior art.

**What might make Wei-Chiu Ma see "an idea here"?** I make no claim about his preferences. A crisp primitive in VC's spirit, where a physical cue supplies geometry that co-visible texture cannot: **the photographer's standpoint is a measured surface.**
- Unknown-focal archival resection has a one-parameter dolly-zoom null direction.
- The lidar-measured set of places a camera could physically have stood (ground plus eye height, union the belfry) cuts that line, much as human bodies constrain extreme-view geometry in VC.
- The companion primitive is carving backward in time against a measured present.

Honest caveat: mathematically this is a height prior plus visibility reasoning. It counts as an idea only if the certificate is shown calibrated.

**Does the Boardman data give identifiable baselines?** No, not for a surface.
- VERIFIED: focal-prior sensitivity p90 is 329% (62% masked; median 10.6%).
- HYPOTHESIS (legacy model): anchor-only along-ray sd is 0.86-1.66u against a 0.71u scene radius, with sd(log f) about 0.10-0.25. About 53° of single-quadrant azimuth and duplicate pairs leave about 4 independent views.

Demonstrate the unidentifiability instead of hiding it:
- per-camera profile likelihood along the dolly direction;
- per-voxel posterior σ;
- the simulated-demolition direction's surrogate showing the same configuration fails on a surviving building with lidar truth;
- in the viewer, red "not identifiable" regions plus the missing standpoint that would fix them (next-best-archival-view).

**Can surviving buildings anchor archival localization?** Yes, under these conditions:
- at least about 30 inlier 2D-3D matches on persistent structure;
- real anchor depth spread (only 0.02-0.27 relative inverse-depth spread for most Boardman views in the legacy model, HYPOTHESIS);
- an independent standpoint or vantage prior, or a wide field of view, to cut the dolly direction;
- era masks so that buildings constructed after the photo are not predicted.

It reduces to existing tools: PnP with priors, skyline registration (Bansal 2014; Mikolka-Flöry 2022) and multi-hypothesis posteriors (Bui 2020). It is **not** virtual correspondence: VC uses a body prior without shared surface, while surviving anchors are ordinary co-visible surfaces. The defensible novelty is what gets *certified downstream*, not the localization.

**The single most impactful modern improvement?** More independent good views of the zero-camera facades. Exhaustive SIFT found 43 verified pairs against 205 from NetVLAD, 8 of 14 targets have zero cameras, and 41 of 77 images are unregistered: the problem is content, not pair budget.

Run the cheaper discriminating test first: EXIF focal priors, a re-map of the best learned run on the 145-photo snapshot, and resuming the interrupted 228-photo run. If the 65/67-connected graph stops fragmenting, calibration was the culprit; the same image is fitted at focal ratios 0.27, 3028 and 6519.

Third priority is evaluation (single-fragment lidar anchoring), because without it no quality claim can be checked. Dense MVS and the GPU come after. Morrill's 0-point fusion is weak geometry, not missing compute.

**An interaction only 3D enables?** Grab an archival camera and drag it along its dolly-zoom ray. The vanished building's evidence stretches. Toggling "photographer stood on measured ground" snaps it, and whatever stays stretched glows "not identifiable".

Second interaction: drop a postcard and watch its sky pixels carve free space while its blocked pixels place must-hit segments. A bounded envelope rises on the Olin site. Remove a postcard and that face reverts to "unobserved".

The surprise is triggered by the user's drag or drop, and it needs metric 3D plus measured lidar. It is not an orbit, a slider or a fly-through.

**Days versus weeks?**
- **Days:** the lidar crop and UTM check; the library-and-tower fragment Sim(3) with the held-out-tower gate/the camera-height gate; the EXIF-prior re-map and resuming the interrupted 228-photo run; OpenMVS on the library-and-tower fragment; the Boardman re-resection and the dolly demo; the active-acquisition direction content count. Together these make a strong class demonstration.
- **Weeks:** a calibrated certificate (degraded controls, K-sweeps, coverage statistics); Ghost Hull with surviving controls and Sanborn containment; an the 228-photo snapshot or Flickr scale-up on a CUDA stack; generalisation to another 3DEP-covered landmark. That is paper-level methodology.

Paper-level *claims* need the calibration and control results, not the demo.

**When is a pivot justified?** These thresholds are pre-registered and tied to downstream use.

A Boardman surface claim requires all of:
- at least 3 deduplicated independent prints with along-ray 1σ ≤ 3 m after the standpoint prior (below one window bay and half a storey);
- triangulation angle ≥ 5° at Boardman points;
- azimuth spread ≥ 60°;
- the simulated-demolition direction showing that the Day-0 masked median/p75 sensitivity is pessimistic relative to lidar truth.

If any of these fails, pivot to bounds (Ghost Hull). If the tower control also fails (it misses the lidar tower, overestimates by more than 3x, or the hull cannot close on 3 sides), pivot again: to the certificate/method paper on surviving controls, plus the modern-only the active-acquisition direction track, or to another destroyed Cornell structure. Commons has categories for Morse Hall, the Old Armory, the McGraw-Fiske Mansion and the 1890 Boathouse. Their counts, rights and independence are unverified, so run the same Day-1 census on them before switching. A reliable alternative beats a fake Boardman.
## Related work for the georegistration paper (checked 2026-10-26)

- Kaminsky, Snavely, Seitz, Szeliski, *Alignment of 3D point clouds to overhead images*, CVPR Workshops 2009 (DOI 10.1109/CVPRW.2009.5204180): SfM to an orthographic overhead image through point-to-edge matching and free-space penalties from camera visibility; a search over rotation, scale and translation. Our free-space cue follows it; we add lidar heights, explicit metric cues and a certificate.
- Wang, Wilson, Snavely, *Accurate georegistration of point clouds using geographic data*, 3DV 2013: Flickr geotags as the start, Google Street View / Google Earth models as the reference. We use neither.
- Goebbels, Pohle-Fröhlich, *Line-based registration of photogrammetric point clouds with 3D city models*, 2018 (SciTePress 65330): wall planes made vertical, footprints matched to CityGML; needs a coarse georeference first.
- Zhang et al., *Improving details of building façades in open LiDAR data using ground images*, Remote Sensing 11(4):420, 2019: ground-image SfM to open airborne lidar through building outlines; GPS initialisation.
- Sarlin et al., *OrienterNet: visual localization in 2D public maps with neural matching*, CVPR 2023: one image to OpenStreetMap, 3-DoF, learned; no lidar, no fragment, no scale cues beyond the map.
- Kinoshita, Nishino, *Camera height doesn't change*, ECCV 2024: constant camera height as metric supervision for monocular road-scene depth. The same physical principle as our photographers-at-eye-height cue, applied to a different problem.
- Untzelmann, Sattler, Middelberg, Kobbelt, *A scalable collaborative online system for city reconstruction*, ICCV Workshops 2013 (to verify before citing: OSM building outlines used to place SfM fragments).
- Temporal line: Matzen, Snavely, *Scene Chronology*, ECCV 2014; Lin et al., *Neural Scene Chronology*, CVPR 2023; *ChronoGS* (arXiv 2511.18794, Nov 2025); *LTGS* (arXiv 2510.09881, Oct 2025).
- Nothing found that georegisters internet SfM fragments to public lidar and OSM without any GPS, with explicit metric cues and per-degree-of-freedom identifiability.
