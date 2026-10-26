# Checkpoint 2026-10-26: the lidar as referee and teacher of an in-the-wild splat

The tower-and-library fragment (63 licensed photographs, McGraw Tower and Uris Library, 2003–2025),
placed in metres in the 2020 USGS lidar by the unified estimator (certificate: usable, scale fixed by
the tower top and the roof edges of four walls, ±3.9 %), trained as a Gaussian splat directly in the
lidar frame, and judged by the lidar. Numbers come from
`artifacts/artsquad_modern/runs/6406b8eaae260163b303/splats/*/{report,geometry}.json`.

## How the splats were trained (`ghostmap/dense/splats.py`)

- gsplat 1.5.3 on the RTX 3070 Ti (kernels built with an unprivileged CUDA 12.6 compiler), 15,000 steps,
  57 photographs for training and 6 held out (every twelfth by name), undistorted to pinhole by pycolmap.
- Per photograph: an affine colour map and a learned background colour (the sky), nothing else.
- The strategy's working scale is a quarter of the fragment's extent. The usual choice, the photographers'
  spread, is 190 m here because some photographers stood 240 m away; with it gsplat stops splitting
  Gaussians at two metres and the first splat was a blur.
- **Lidar as teacher** (`--lidar-prior`): inside the measured volume (the lidar crop, up to 120 m above
  its ground) a Gaussian more than 2 m above the highest lidar surface within 2.5 m is in air the lidar
  saw empty, and one more than 1 m under the lowest bare ground within 2.5 m is buried. The loss adds
  0.01 × opacity × metres of violation, and Gaussians more than 5 m beyond the margin are removed at every
  refinement step (16,889 removed).

## How they were judged (`ghostmap/evaluate/splat_geometry.py`)

Every Gaussian with opacity at least 0.3 inside the measured volume is classified as on a lidar surface,
in measured free air, or buried, with the 2.5 m horizontal tolerance (a wall point a metre outside its
footprint sits over a ground cell, and without the tolerance 28 % of the fragment's own COLMAP points
counted as "in the air"). Also: distance from each Gaussian's centre to the nearest lidar return, per
building, and how much of each lidar building the splat covers.

**Noise floor.** The fragment's own COLMAP points: 86.2 % on surfaces, 7.8 % in free air, 5.9 % buried.

## Results

| | plain | lidar-taught |
| --- | --- | --- |
| Gaussians | 1,366,024 | 755,911 |
| opaque Gaussians in the measured volume | 1,050,686 | 598,859 |
| on lidar surfaces | 29.6 % | **69.9 %** |
| in measured free air | 24.8 % | 19.8 % |
| buried under the bare ground | 45.6 % | **10.2 %** |
| median distance to the nearest lidar return | 5.21 m | **1.88 m** |
| within 1 m of a lidar return | 11.5 % | 26.2 % |
| Uris Library: median distance, within 1 m | 0.89 m, 58 % | 0.87 m, 61 % |
| McGraw Tower: median distance, coverage of the lidar tower | 1.42 m, 55 % | 1.37 m, 61 % |
| held-out PSNR (6 photographs, colour fitted per photograph) | 14.44 dB | 14.23 dB |
| training time, same 15,000 steps | 6,657 s | 1,867 s |

Reading:
- The lidar moves the splat from mostly floating and buried to mostly on measured surfaces, halves the
  Gaussians and cuts training time 3.6 times, at 0.2 dB of held-out PSNR.
- The held-out photographs split in two: the view inside the photographers' coverage (the tower and the
  library from the north-west, 23.9 dB plain and 23.8 dB taught) and views far outside it (Ho Plaza
  through trees, close-ups) at 11–14 dB for both. The lidar prior does not repair views nobody
  photographed; it removes geometry that cannot be there.
- 19.8 % of the taught splat is still in free air: 85 % of those Gaussians are 2–7 m above open ground,
  inside the band the prior penalises but does not remove. A stronger-prior ablation is below.

## Ablation: a stronger prior

Weight 0.05 and removal from 1 m beyond the margin (3 m above the surface), otherwise identical; trained
under `runs/6406b8eaae260163b303/splat-ablations/lidar-taught-strong/`.

| | plain | lidar-taught (0.01, 5 m) | stronger (0.05, 1 m) | the fragment's own COLMAP points |
| --- | --- | --- | --- | --- |
| Gaussians | 1,366,024 | 755,911 | 397,720 | 5,777 points |
| on lidar surfaces | 29.6 % | 69.9 % | **90.8 %** | 86.2 % |
| in measured free air | 24.8 % | 19.8 % | **3.6 %** | 7.8 % |
| buried | 45.6 % | 10.2 % | 5.6 % | 5.9 % |
| median distance to the lidar | 5.21 m | 1.88 m | 1.31 m | |
| held-out PSNR, mean of 6 | 14.44 dB | 14.23 dB | 14.07 dB | |
| held-out PSNR, the covered view | 23.9 dB | 23.8 dB | **19.9 dB** | |

The stronger prior passes the noise floor of the fragment's own points, and pays 4 dB on the one held-out
view the photographers covered: at that strength it carves away real structure that the anchoring's
few-metre error and the 2.5 m tolerance put outside the measured surfaces. The demo keeps the default
weight; where to stop is set by the placement's accuracy, which is the link between the two halves of
the project.

## Renders at the photographers' poses (`ghostmap/dense/splat_views.py`)

gsplat at 960 px, colour map fitted and background set to the photograph's own sky (the held-out
protocol), plain / lidar-taught: the held-out view of the tower and the library 24.0 / 23.9 dB; training
views 28.4 / 27.5, 23.2 / 22.5 and 21.9 / 25.4 dB. A 60-frame fly-through between seven training
photographers facing the tower, and an arc walk with both splats side by side
(`artifacts/presentation/splat-walk-plain-vs-lidar-taught.mp4`), show the views in between.

## Not shown, on purpose

- The page and the slides compare the plain and the lidar-taught splat at the default weight; the
  ablation is reported here, not tuned for the demo.
- The browser renderer smears Gaussians close to the camera, so the demo shows gsplat's own renders at
  the photographers' poses and along the fly-through; between and beyond the photographers every splat
  degrades, which the side-by-side walk shows for both.
