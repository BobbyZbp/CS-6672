# Method audit: Snavely's chronology papers and GhostMap

Read against the official papers and code on 2026-10-23.

## Scene Chronology (Matzen and Snavely, ECCV 2014)

Official paper: https://www.cs.cornell.edu/~snavely/publications/matzen_eccv2014.pdf

Sections 3 and 4.1 explicitly assume recoverable cameras, sufficient persistent scene content, and geometry that is largely static. The authors initialize Bundler from a random set of 20,000 photographs, register remaining photographs using 2D-to-3D matching, and use CMVS plus modified PMVS for a **dense** patch reconstruction. They then build visibility/photoconsistency observations, estimate existence intervals, and fit plane-time cuboids. Section 5.1 renders either patches or photograph-textured planes.

Consequences for GhostMap: sparse SfM is only the camera stage. The analogous missing stage was dense stereo. A demolished building also violates the largely static geometry assumption, so historical and modern surfaces must be reconstructed separately before transferring coordinates through persistent structures.

## Neural Scene Chronology (Lin et al., CVPR 2023)

Official paper: https://openaccess.thecvf.com/content/CVPR2023/papers/Lin_Neural_Scene_Chronology_CVPR_2023_paper.pdf

Official code: https://github.com/zju3dv/NeuSC

Correct arXiv identifier: **2306.07970**. The earlier 2303.14084 link was unrelated and was not used as evidence for this implementation.

Section 3.1, equations 2 and 3, separates static density/geometry from time-dependent appearance. Table 1 reports 23,628 retrieved / 6,503 calibrated / 3,521 selected images for 5Pointz. Section 4.1 describes COLMAP calibration and region selection; training is reported at roughly 40 hours on an RTX 3090.

The official README's custom-data instructions require COLMAP SfM, undistortion, dense reconstruction, and a mesh, then select the region in MeshLab. Semantic maps remove transient objects; scripts discard weakly supported views. `scripts/colmap/gen_trash.py` excludes views with <=300 observations and <10% registered features (among other checks). The README's published checkpoint was trained for 400k iterations with two A6000 GPUs.

Consequences for GhostMap: simply running NeuSC cannot supply missing Boardman multiview evidence. The useful transferable pieces are calibrated cameras, dense stereo, view-quality filtering, and photometric validation. Its manual MeshLab selection is incompatible with the required automatic workflow and must be replaced by an auditable automatic selection rule.

## Implemented repair experiments

1. Preserve v1 baselines; run target-first SfM on every historical filename matching Boardman, with exhaustive pairs, 1,600px SuperPoint extraction, 8,192 keypoints, and LightGlue. Use the pinhole scan camera model without fictitious lens distortion.
2. Densify each era separately using COLMAP camera undistortion followed by OpenMVS CPU PatchMatch, depth consistency, and fusion requiring at least three supporting views.
3. Reconstruct the surface without closing unsupported holes. Texture it from the calibrated original photographs.
4. Explicitly disable OpenMVS tower mode, which otherwise may append an artificial cylinder of seed points. Keep generated depth maps and logs.
5. Evaluate target coverage and projection consistency before changing the scientific success verdict. Boardman-labelled input membership is a candidate-selection heuristic, not pixel-level proof of target identity.

6. Use conservative local reference-view triangulation to prevent volumetric mesh envelopes from spanning unsupported gaps. The resulting partial facets preserve stereo vertices and real source textures.
7. Expand acquisition through Cornell's official viewer-linked IIIF services, retain research-use and rights metadata, and test focal calibration sensitivity across shared tracks.
8. Adapt NeuSC's semantic filtering idea using a pinned CLIPSeg model to mask buildings against vegetation and sky automatically. Apply masks to learned correspondences before COLMAP and to dense stereo; retain before/after counts and mask audit images.

Code: `pipeline/legacy/repair/run_target_sfm.py` and `pipeline/run_cpu_mvs.py`.
