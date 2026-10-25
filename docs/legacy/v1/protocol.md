# GhostMap v1 experimental protocol

## Hypothesis

Publicly licensed Internet photographs contain sufficient viewpoint and appearance overlap for COLMAP to recover Boardman Hall and connect that historical component to a modern Cornell anchor without human data collection, annotation, correspondence editing, or camera initialization.

## Primary endpoint

The release endpoint requires all of the following in one learned-feature COLMAP component:

- at least three nondegenerate cross-era geometrically verified pairs;
- at least three registered images whose filenames identify Boardman Hall;
- at least 1,000 3D points observed by at least two Boardman images and by no modern image; and
- a successfully computed dense surface for the public 3D demo.

The target-specific point definition prevents stable Uris Library and McGraw Tower structure from being counted as recovered Boardman geometry.

## Secondary endpoints

- Historical reconstruction registration and point count.
- Registered image count and perceptual-hash unique-view count.
- Modern reconstruction registration and point count.
- Verified image-pair and inlier counts in each COLMAP database.
- Median/mean reprojection error and track length.
- Failure taxonomy: insufficient images, disconnected match graph, mapper initialization failure, or post-reconstruction quality failure.

## Controls against a visually persuasive false result

1. The browser loads exported COLMAP points; it contains no primitive-building generator or mesh loader.
2. A point cloud is still labeled failed when its run misses a threshold.
3. Historical and modern images are reconstructed both separately and jointly.
4. Source and artifact hashes are checked before web packaging.
5. The site states the strongest supported conclusion, including a negative one.

## Known threats to validity

- Multiple postcards may be colorizations or reproductions of the same photographic negative, inflating image count without adding baseline.
- Repetitive windows, scans, borders, printed text, and halftone patterns can create spurious local features.
- Uris Library is a stable visual anchor but is not a guarantee that Boardman Hall pixels overlap modern imagery.
- An unscaled SfM model has arbitrary similarity gauge and cannot supply metric dimensions.
- Commons category coverage is not equivalent to all images available on the public web.
- The fixed CPU budget and 1024px derivatives trade reconstruction capacity for reproducibility.
- The current pycolmap build has no CUDA support, so COLMAP PatchMatch Stereo is recorded as blocked rather than replaced with synthetic geometry.

## Decision after v1

If the joint gate fails, the zero-human constraint rules out repairing correspondences or supplying new photographs. The research direction should either (a) broaden automated acquisition to additional licensed archives and rerun the unchanged gate, or (b) be rejected under the current constraint. A hand-modeled Boardman Hall is not an acceptable fallback.

