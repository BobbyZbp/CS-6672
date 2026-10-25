# Verified research lineage for GhostMap

Research snapshot: 2026-10-23. This is a bounded review of the Internet-photo reconstruction, image-based exploration, and long-term scene-history lineage relevant to GhostMap, not an exhaustive review of every Snavely publication. Public links and repository contents were read; linked large datasets, checkpoints, and training jobs were **not** downloaded or run in this planning review.

Verification tiers: **P** = relevant original PDF sections read; **R** = official project page and/or official code README read; **B** = bibliographic lead only, not independently evaluated. A code link establishes published availability, not reproducibility in our environment or a license to redistribute its input images.

## 1. What this literature does and does not establish

- Sparse cameras/points are an intermediate result, not a high-detail campus reconstruction. Internet-photo MVS has produced detailed real geometry since at least the 2007 community-photo work.
- A compelling interactive system is also a research lineage, not an afterthought: Photo Tourism and Finding Paths combine recovered cameras, photo correspondences, view-aware transitions, object-based navigation, and canonical tours.
- **Do not say all chronology papers assume static geometry.** Scene Chronology (2014) and the implemented Neural Scene Chronology (2023) representation largely do; 3D Time-lapse Reconstruction (2015) explicitly estimates time-varying depth and demonstrates construction/change. Its limited-path, depth-map output is not a general, complete historical 3D campus model.
- Sparse/uneven Internet data, ambiguity-aware matching, learned reconstruction, and camera-graph-aware sampling are active published work through 2026. None alone can be our novelty claim.
- Published demonstration polish does not imply fully automatic data preparation: official sources include manually selected ROIs, curated examples, geometry checks, and postprocessing. GhostMap's zero-human-data-input requirement is stricter than simply reproducing these demonstration pipelines.
- Photorealistic neural rerendering and reconstructing metrically reliable surfaces are different objectives. A learned renderer can interpolate convincing appearance without certifying measurements or unseen facade detail.

## 2. Geometry and interactive-navigation foundations

### Photo Tourism: Exploring Photo Collections in 3D — SIGGRAPH / TOG 2006 [P, R]

Noah Snavely, Steven M. Seitz, Richard Szeliski.

- Official project: https://phototour.cs.washington.edu/
- Original PDF: https://phototour.cs.washington.edu/Photo_Tourism.pdf
- Engineering: https://www.cs.cornell.edu/~snavely/bundler/ and https://github.com/snavely/bundler_sfm
- Public image collections/reconstructions linked by project: https://phototour.cs.washington.edu/datasets/

Sections 4–7: incremental camera/SfM reconstruction, photo explorer rendering, view interpolation, free-flight/object-based navigation, annotation transfer. The abstract explicitly describes a **sparse** 3D model plus image-to-model correspondences. Section 5.3 distinguishes triangulation morphs from planar morphs; the latter is the robust default. With no common points the system does not invent interpolation evidence: it fades between photographs. Section 4 discusses low-frequency drift and optionally anchoring to control/GPS/manual map correspondences. These optional manual anchors are not compatible with our automatic-only workflow.

Engineering takeaway: recover a reliable camera graph first; provide photograph-anchored exploration and quality-aware transitions even while the full scene is being densified. Do not mislabel a navigation proxy as validated mesh geometry. The Bundler page explicitly recommends PMVS/CMVS for dense output; Bundler alone outputs sparse points.

### Multi-View Stereo for Community Photo Collections — ICCV 2007 [R]

Michael Goesele, Noah Snavely, Brian Curless, Hugues Hoppe, Steven M. Seitz.

- Official project: https://grail.cs.washington.edu/projects/mvscpc/
- Original PDF linked there: https://grail.cs.washington.edu/projects/mvscpc/download/Goesele-2007-MVS.pdf

Official abstract: adaptive per-view/per-pixel source selection, sparse-point seeds, surface-normal optimization and photoconsistency, designed for lighting/scale/clutter variation in community photos. Project examples include Notre Dame: 653 Flickr images from 313 photographers, not thousands of copies of one image. The project dataset section explicitly says models were trimmed with standard mesh operations to remove spurious Poisson geometry. No claim that these historical final meshes were obtained without human cleanup.

Takeaway: independent viewing directions and view selection matter more than raw photo count. Keep dense support and surface confidence separate from mesh completion.

### Finding Paths through the World's Photos — SIGGRAPH / TOG 2008 [P, R]

Noah Snavely, Rahul Garg, Steven M. Seitz, Richard Szeliski.

- Project: https://phototour.cs.washington.edu/findingpaths/
- Original PDF: https://phototour.cs.washington.edu/findingpaths/paper/FindingPaths_siggraph08.pdf

Automatically discovers orbit paths, panoramas, canonical views, and paths connecting views; uses control-adaptive reprojection as the user navigates. It combines scene-specific controls and free-viewpoint browsing, not simply “render an arbitrary camera path through whatever mesh is available.” (The project page says five degrees of freedom, while the PDF abstract says six; no claim here depends on that wording discrepancy.)

Takeaway: our flagship Arts Quad tour should follow a recovered, high-support camera/view manifold; arbitrary unsupported viewpoints need a visible coverage warning or photo fallback. Showcase an automatically selected building-to-building route, not only an orbit around McGraw Tower.

### Building Rome in a Day — ICCV 2009 [P, R]

Sameer Agarwal, Noah Snavely, Ian Simon, Steven M. Seitz, Richard Szeliski. Do not conflate this five-author 2009 conference paper with the seven-author 2011 CACM extension (which adds Yasutaka Furukawa and Brian Curless).

- Project and engineering discussion: https://grail.cs.washington.edu/projects/rome/
- Original ICCV PDF: https://grail.cs.washington.edu/projects/rome/rome_paper.pdf

Distributed matching, clustering/SfM and large image collections. The official Rome example has 150,000 input photos and 496 CPU cores; matching took 21 hours. The Venice example reports 250,000 inputs and 27 hours each for matching/reconstruction on 496 cores. These are historical resource figures, not a runtime estimate for modern COLMAP or our hardware. Bundler is released; the project does not establish availability of the entire original distributed stack.

Takeaway: matching every pair is not a large-campus default. Use retrieval, metadata/view-graph candidates, spatial clusters, bridge edges, local reconstruction and joint refinement; cache every stage and preserve disconnected components.

### Robust Global Translations with 1DSfM — ECCV 2014 [R]

Kyle Wilson, Noah Snavely.

- Project/paper: https://www.cs.cornell.edu/projects/1dsfm/ and https://www.cs.cornell.edu/projects/1dsfm/docs/1DSfM_ECCV14.pdf
- Code: https://github.com/wilsonkl/SfM_Init

Official abstract: robust translation estimation from a noisy epipolar graph using low-dimensional outlier subproblems plus averaging. Project provides numerical problems and image collections, including a reported failure case and corrected coordinate-system/principal-point issues. It is a useful global-geometry baseline/reference, not proof that a large component is correct.

## 3. The scene-history / time-machine branch

### Scene Chronology — ECCV 2014, Best Paper [P, R]

Kevin Matzen, Noah Snavely.

- Project: https://www.cs.cornell.edu/projects/chronology/
- Original PDF: https://www.cs.cornell.edu/~snavely/publications/matzen_eccv2014.pdf

Section 3 says: “the geometry of the scene is largely static,” requires enough persistent content/continuity for correct cameras, and approximates urban scene geometry with planes. Sections 4.1–4.5: initialize Bundler from 20,000 random photos, register remaining images by 2D–3D matching, CMVS + modified PMVS dense patches, compute projection-visible versus photoconsistent-visible observations, infer existence intervals, and fit plane-time cuboids. Crucially, it uses both **positive and negative observations**; an object not appearing in a view can be informative only after accounting for visibility/occlusion.

Code/data availability: the official page provides the paper, poster, and visualization; no working code/data download was found in the current page. A commented-out “Code and data coming soon” block is **not** evidence of a downloadable release. Do not budget the original complete pipeline as turnkey.

Takeaway: carry time/existence/confidence at patch/object level and retain visibility evidence. We cannot infer demolition merely because matching failed.

### Time-lapse Mining from Internet Photos — SIGGRAPH / TOG 2015 [P, R]

Ricardo Martin-Brualla, David Gallup, Steven M. Seitz. **Snavely is not an author.** This is the adjacent UW/Google lineage often remembered together with his work.

- Project: https://grail.cs.washington.edu/projects/timelapse/
- Original PDF: https://grail.cs.washington.edu/projects/timelapse/TimelapseMiningSIGGRAPH15.pdf

Clusters 86 million timestamped/geotagged images into landmarks/viewpoints; discovers candidates with at least 300 photos; recovers/uses one depth map for alignment to a common view and temporally regularizes appearance. Section 5 explicitly says geometry change is **not modeled** by that one global depth map. It uses image inpainting at occlusions and reports some example-specific depth parameter tuning, so neither “hole-free video” nor “automated overview” means fully measured geometry or no author choices.

Code/data: no public implementation/data link found on the inspected official page; do not promise exact reproduction without further artifact discovery.

### 3D Time-lapse Reconstruction from Internet Photos — ICCV 2015 [P, R]

Ricardo Martin-Brualla, David Gallup, Steven M. Seitz. Again, not Snavely-authored.

- Project: https://grail.cs.washington.edu/projects/timelapse3d/
- Original PDF: https://grail.cs.washington.edu/projects/timelapse3d/3DTimelapseReconstructionICCV15.pdf

Introduction and Sections 3–5 explicitly extend the previous work to **time-varying geometry**, with temporally consistent depth maps and 3D tracks/color profiles. A user specifies a virtual camera path; source views are selected near a reference camera. This supports parallax and construction/glacier changes, but is a depth-map/track representation for producing a path-dependent video, not a globally complete 4D mesh with unrestricted exploration. Neural Scene Chronology's related-work section also identifies this limited viewpoint range.

Takeaway: structural-change precedent exists and must be compared, not dismissed. Our opportunity is global, evidence-calibrated, cross-era geometry with explicit unknown regions, rather than claiming to be first to represent changing geometry from Internet photos.

### Neural Scene Chronology — CVPR 2023 [P, R]

Haotong Lin, Qianqian Wang, Ruojin Cai, Sida Peng, Hadar Averbuch-Elor, Xiaowei Zhou, Noah Snavely.

- Project: https://haotongl.github.io/neusc/
- Original PDF: https://openaccess.thecvf.com/content/CVPR2023/papers/Lin_Neural_Scene_Chronology_CVPR_2023_paper.pdf
- Correct arXiv: https://arxiv.org/abs/2306.07970 (2303.14084 is unrelated).
- Official code: https://github.com/zju3dv/NeuSC
- Public 5Pointz data link: https://landmark.cs.cornell.edu/data/neural_scene_chronology/5pointz.zip

Section 3.1, Eqs. 2–3: static `Fgeo(x)` density/geometry and time-varying `Fapp(x, v, t, illumination, direction)` appearance. Text states geometry is mostly constant; extending it to time-varying geometry is suggested, not implemented evidence that it recovers a demolished building. Temporal step functions disentangle discrete content changes from lighting. Semantic and learned transient masks suppress people/cars.

Table 1: 5Pointz 23,628 retrieved / 6,503 calibrated / 3,521 selected images; Times Square 289,794 / 29,629 / 5,965. Section 3: approximately 800k iterations, ~40 hours on RTX 3090 for convergence. Section 4.1: some full-scene COLMAP calibration takes weeks on a multi-server cluster. Official README separately says the published checkpoint used 400k iterations on two A6000 GPUs; do not merge those distinct configurations.

README custom data: COLMAP SfM → undistort → dense mesh → **manual MeshLab ROI** → semantic maps → noisy-view filtering. This is not our automatic-only pipeline out of the box.

Takeaway: benchmark lighting/time disentanglement separately from true topology change. Use evidence-driven automatic ROI/quality filtering. Reproduce at least a published 5Pointz slice before suggesting an extension is better.

## 4. Appearance, detailed geometry, and current successors

### Neural Rerendering in the Wild — CVPR 2019 [R]

Moustafa Meshry, Dan B Goldman, Sameh Khamis, Hugues Hoppe, Rohit Pandey, Noah Snavely, Ricardo Martin-Brualla.

- Project: https://moustafameshry.github.io/neural_rerendering_in_the_wild/
- Code: https://github.com/google/neural_rerendering_in_the_wild
- Paper linked by official homepage: https://arxiv.org/abs/1904.04290

Official abstract: learn a rerenderer from projected scene points/deep framebuffers with latent appearance and transient semantic masks, varying season/time-of-day/view. This is a rendering-quality precedent; it is not a guarantee that synthesized details are observed geometry.

### Crowdsampling the Plenoptic Function — ECCV 2020 [R]

Zhengqi Li, Wenqi Xian, Abe Davis, Noah Snavely.

- Project: https://research.cs.cornell.edu/crowdplenoptic/
- Paper: https://arxiv.org/abs/2007.15194
- Code/data/pretrained models: https://github.com/zhengqili/Crowdsampling-the-Plenoptic-Function

DeepMPI/light-field reconstruction supports view and illumination interpolation, including real-time synthesis, without requiring temporal registration. It is not historical birth/death inference. The released README warns its unoptimized evaluation needs four GPUs with >11GB each; do not mistake real-time rendering for cheap training/evaluation.

### Neural 3D Reconstruction in the Wild — SIGGRAPH 2022 [P, R]

Jiaming Sun, Xi Chen, Qianqian Wang, Zhengqi Li, Hadar Averbuch-Elor, Xiaowei Zhou, Noah Snavely.

- Project: https://zju3dv.github.io/neuralrecon-w/
- Paper: https://arxiv.org/abs/2205.12955
- Code/evaluation: https://github.com/zju3dv/NeuralRecon-W
- Public ground-truth source: https://openheritage3d.org/

Hybrid voxel/surface-guided sampling of a neural implicit surface improves detailed surface recovery under Internet-photo lighting variation. Section 4 introduces **Heritage-Recon**, with independent LiDAR for Brandenburg Gate, Pantheon Exterior, Lincoln Memorial, Palacio de Bellas Artes; visibility-aware evaluation avoids treating unobserved areas as failures. It includes manual ROI selection and tuned ICP alignment; reports <1px reprojection alignment consistency. Section 5 uses eight A100 GPUs. The README includes custom COLMAP-workspace preprocessing, model/mesh extraction, and evaluation scripts.

Takeaway: use this as a modern detailed-geometry baseline and external benchmark before making centimeter-accuracy claims about Cornell. Held-out Cornell photo appearance alone is insufficient ground truth for metric geometry. Public third-party LiDAR is compatible with online-only data, but benchmark data curation should not be misrepresented as human-free.

### MegaScenes: Scene-Level View Synthesis at Scale — ECCV 2024 [R]

Joseph Tung, Gene Chou, Ruojin Cai, Guandao Yang, Kai Zhang, Gordon Wetzstein, Bharath Hariharan, Noah Snavely.

- Project: https://megascenes.github.io/
- Dataset engineering: https://github.com/MegaScenes/dataset
- Public web viewer: https://megascenes.github.io/web-viewer/
- Paper: https://arxiv.org/abs/2406.11819

README: roughly 430k scenes/9M images, >100k SfM reconstructions from 2M images; Wikimedia metadata, per-image rights/EXIF, COLMAP databases and native binary reconstructions. Individual files/subsets accessible without downloading the whole dataset. The dataset is not all uniformly correct, complete, or dense; later MegaDepth-X filters it explicitly. Its public viewer is a relevant engineering reference, not a license to copy unverified Cornell geometry.

### Doppelgangers: Learning to Disambiguate Images of Similar Structures — ICCV 2023 [R, bibliographic identity verified]

Ruojin Cai, Joseph Tung, Qianqian Wang, Bharath Hariharan, Hadar Averbuch-Elor, Noah Snavely.

- https://doppelgangers-3d.github.io/
- https://github.com/RuojinCai/Doppelgangers

### Doppelgangers++: Improved Visual Disambiguation with Geometric 3D Features — CVPR 2025 [R]

Yuanbo Xiangli, Ruojin Cai, Hanyu Chen, Jeffrey Byrne, Noah Snavely.

- Project/paper: https://doppelgangers25.github.io/doppelgangers_plusplus/ and https://arxiv.org/abs/2412.05826
- Public code: https://github.com/doppelgangers25/doppelgangers-plusplus

Uses geometric 3D network features to improve pairwise ambiguity classification and prune erroneous view-graph edges. Official projects expose baseline-vs-method 3D reconstruction comparisons. Relevant to repeated windows, towers, symmetrical sides, and visually similar Cornell stone facades; ordinary epipolar inliers do not guarantee the *same* real-world structure was matched.

### Long-Tail Internet Photo Reconstruction — CVPR 2026 [P, R]

Yuan Li, Yuanbo Xiangli, Hadar Averbuch-Elor, Noah Snavely, Ruojin Cai.

- Project: https://megadepth-x.github.io/
- Paper: https://arxiv.org/abs/2604.22714
- Code: https://github.com/MegaDepth-X/Megadepth-X
- Data and checkpoints: https://huggingface.co/datasets/y-u-a-n-l-i/MegaDepth-X

Sections 3–4: curate **MegaDepth-X**, 1,865 reconstructions / ~440k images from MegaScenes; MASt3R-SfM + Doppelgangers++ sparse reconstruction; COLMAP MVS followed by semantic, stability, and monocular-ordinal/gradient filtering. Final scenes are manually checked against external maps/satellite imagery. Sparsity-aware view-graph sampling simulates fragmented/wide-baseline photo collections from well-reconstructed scenes, then finetunes π³ and VGGT. Supplement C.1: four A6000 GPUs for experiments. Supplement C.5: truly disconnected indoor/outdoor collections can still be fused into an incorrect shared structure, even by the finetuned model.

Crucial precedent: **“learn from sparse degraded subsets of well-captured Internet scenes” is already published.** Our research must go beyond this via temporal/structural evidence, calibrated rejection, or a demonstrably new objective/representation. Monocular predictions can filter or initialize proposals, but cannot be promoted to independent multiview observations.

## 5. Leads intentionally not claimed as fully reviewed

- Schindler and Dellaert, *Probabilistic Temporal Inference on Reconstructed 3D Scenes*, CVPR 2010: verified as reference [40] and discussed in Neural Scene Chronology's related work, explicitly about buildings appearing/disappearing over decades. Original PDF/code not independently inspected in this pass; must read before any “first historical structural-change reconstruction” claim.
- ZipMap, *Linear-Time Stateful 3D Reconstruction via Test-Time Training*, CVPR 2026, Snavely coauthor: official publication listing https://www.cs.cornell.edu/~snavely/ links https://haian-jin.github.io/ZipMap/ and https://github.com/Haian-Jin/ZipMap . Pipeline-scale comparison lead; not evaluated here.
- C3Po, cross-view/cross-modality correspondence, NeurIPS 2025: official listing links https://c3po-correspondence.github.io/ and https://github.com/c3po-correspondence/c3po . Relevant cross-era matching lead, not evidence that generated or cross-modal correspondences are automatically correct. A separate correspondence review should assess it and the user's “virtual correspondence” reference.
- MegaDepth (Li and Snavely, CVPR 2018), original project https://www.cs.cornell.edu/projects/megadepth/ : foundational depth-supervision/filtering source used by the 2026 successor; method not reread in full in this pass.

## 6. Actionable plan implications

1. **Modern Arts Quad is the first independent deliverable.** Multi-building globally connected cameras, local high-resolution dense depth/geometry, environmental context, a streamed interactive scene, and source-photo navigation. Report coverage per building/facade/ground cell rather than a single large point count.
2. **Choose the scientific question before a huge implementation.** Promising candidate: distinguish observed historical surfaces, model-supported geometric hypotheses, and genuinely unidentifiable regions while recovering cross-era coordinates through persistent structures. Explicitly model survival/change/occlusion, calibration and duplicate-photo dependence. This is a hypothesis, not an already established novel contribution.
3. **Treat disconnection as a valid result.** A symmetric facade or learned 3D prior must not force separate buildings/eras into one model. Retain candidate components/hypotheses; require cross-view and held-out evidence to merge.
4. **Separate three benchmark tasks:** detailed modern geometry (Heritage-Recon + Cornell independent data if found), cross-era localization/registration (persistent anchors and withheld observations), and temporal rendering/change reasoning (NeuSC-style scenes plus structural-change cases). Rendering PSNR/LPIPS alone does not validate geometry or demolition.
5. **Pre-register baselines and ablations:** SIFT/COLMAP; SuperPoint/LightGlue/hloc+COLMAP; MASt3R-SfM+Doppelgangers++; a current pretrained long-tail model; MVS versus a neural surface baseline; naive joint-era SfM versus era-specific geometry with persistent-anchor registration. Time/appearance comparisons include Scene Chronology/NeuSC where the assumptions fit, and time-varying-depth precedent where geometry changes.
6. **Test automatic rejection quantitatively.** Source-family-disjoint splits; repeat under focal/calibration changes, duplicates and fake candidate matches; precision versus accepted coverage and risk/coverage curves. Synthetic photo degradation is useful but, given MegaDepth-X, is not itself novel. No internally produced COLMAP geometry should be labeled independent ground truth.
7. **Polished visual story stays evidence-backed.** Guided route, source-image fly-ins, same-camera now/then comparison, high-resolution architectural details, environment, time slider where evidence supports it, and a one-click “show evidence / unknown” layer. Restrict default camera paths to validated support; no imaginary building completion for a prettier reveal.
8. **Resource plan needs staged calibration.** Literature ranges from one consumer GPU to multi-server SfM/eight-A100 neural training. Benchmark runtime/VRAM/storage on a representative subset before promising Cornell-wide fidelity or a completion date. Reusing published checkpoints is much cheaper than reproducing their full training.

## 7. Open questions to resolve before paper claims

- Exact identity of “virtual correspondence” intended by the user; assess multiple candidates without silently choosing one.
- Whether public Cornell photographs provide enough independent multi-building bridge views, roofs, and ground context; raw image counts do not answer this.
- Whether public metric/geospatial/LiDAR references cover Arts Quad with compatible rights and enough accuracy for independent validation.
- Whether Boardman can be constrained in more than a single facade/near-planar image family; existing low reprojection error and dense fragments do not establish that.
- Whether the proposed evidence/rejection contribution beats current long-tail and cross-modal baselines on multiple external sites, not only one Cornell showcase.
- Which copyrighted archive outputs can be shown in a public press demo versus used only in private research; page visibility is not redistribution permission.

