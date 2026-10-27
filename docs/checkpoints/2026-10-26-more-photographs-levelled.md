# Checkpoint 2026-10-26 (afternoon): more photographs, a levelled placement, a page the audience can follow

What changed since the morning checkpoint (`2026-10-26-lidar-referee-teacher.md`), and what the numbers
are now. Every number comes from a report file named next to it.

## More photographs

- The Openverse queries were widened (the chimes, the bell tower, Libe Slope, Uris Library, Ho Plaza):
  360 Flickr candidates, 178 admitted under the same licence, place-name, historic-marker and
  near-duplicate screens (was 99) (`data/openverse/manifest.json`).
- New snapshot `baa07d85860379b83c5bc72e` (the base snapshot plus 178 training-only photographs).
  Reconstructed on the GPU in under four minutes (SuperPoint, LightGlue, NetVLAD, pycolmap), run
  `artifacts/artsquad_modern/runs/ce2e2544cf854945f0c7`. The tower-and-library fragment has 88
  photographs (was 63), 5,901 points.

## The placement, levelled

- The fly-through showed photographers of the old fragment 6.5 to 8 m under the lidar ground; the
  certificate already said only 11 of 63 cameras stood at eye height. A robust plane through the
  well-observed photographers' heights over the lidar ground had a 6.5° trend (residual 2.9 m).
- Levelling by all of it made every structural check worse on the old fragment (points within 1 m of
  footprint walls 54 % → 44 %; sparse points within 1 m of a lidar return 43 % → 35 %; in empty air
  8 % → 15 %): a photographer's distance along the line of sight is the weakest part of a placement, and
  on a slope it shows up as height too. So the plane only proposes a tilt; fits with a third, two thirds
  and all of it compete with the facade vertical on the joint objective of every cue
  (`anchor/georegister.py`, `fit_levelled`; every candidate is in the report).
- A synthetic hall given a vertical 4° off is levelled back within 1°. On the old fragment a third of the
  tilt wins (2.2°); the regression against the landmark anchor now checks heading (within 2°) and tilt
  (equal to the reported correction) separately, and passes.
- The tower detector took the top tenth of points as the tower; the larger model's stray far points
  stretched that core until the tower no longer looked like one (height 0.5 radii). It now starts from the
  densest spot among the high points (old fragment: unchanged, 2,037 points, height 12.7 radii; new
  fragment: 1,705 points, 13.5 radii).
- New fragment (`runs/ce2e2544…/anchor/0/report.json`): **usable**; scale fixed three independent ways
  (the McGraw Tower top, the walls alone — parallel walls are now in view — and the roof edges of four
  walls, ±3.9 %); levelled by two thirds of its photographers' tilt (3.7°; joint objective 2.29 → 2.40;
  cameras at eye height 13 → 18 of 88). Its own COLMAP points: 82.7 % on lidar surfaces, 15.7 % in empty
  air, 1.3 % under the ground (the noise floor for the splats).

## The campus, re-placed with the same estimator

All seven campus fragments with eight or more cameras are still refused, each for a stated reason (no
facade seen; cameras inside buildings, twice; cues disagree; scale undetermined, three times). The three
placements geotags could check were 845, 64 and 325 m off, and all three were refused. Wherever the tower
pins another fragment, its tower points coincide with the new fragment's within 0.6–1.2 m
(`artifacts/georegistration/table.md`).

## The splats

Same 80 training photographs and 8 held out (every twelfth by name), same 15,000 steps, trained in the
levelled frame (`runs/ce2e2544…/splats/*/{report,geometry}.json`; the ablation under `splat-ablations/`).

| | plain | lidar-taught | five times stronger rule |
| --- | --- | --- | --- |
| Gaussians | 1,044,899 | 647,294 | 581,535 |
| on lidar surfaces | 40.8 % | 87.8 % | 96.2 % |
| in measured-empty air | 17.9 % | 7.5 % | 1.9 % |
| under the bare ground | 41.3 % | 4.7 % | 1.8 % |
| median distance to the lidar | 3.58 m | 1.30 m | 1.34 m |
| held-out PSNR (mean of 8) | 14.38 dB | 14.51 dB | 14.76 dB |
| best-covered held-out view | 22.4 dB | 22.5 dB | 21.4 dB |
| fly-through pixels painted red or purple | 19.9 % | 3.7 % | — |

COLMAP's own points of this fragment are the noise floor: 82.7 % on lidar surfaces. The lidar-taught splat
is now above it, and the stronger rule costs about a decibel on the best-covered view instead of the four
it cost on the unlevelled placement. The plain splat was trained with the photographs kept on the host and
packed rasterisation (the same rendering; the first attempt paged the 8 GB card once it passed a million
Gaussians and stalled), the lidar-taught one before that change; the first step's loss agrees to seven digits.

## The page

- A measured city instead of a lidar sheet (`web/city_model.py`): footprint walls from the lidar bare
  ground to the lidar roof, roofs draped with the year's aerial image, one tree per lidar canopy peak,
  sky, fog and sun shadows.
- The fly-through is side by side with a map of the camera among the photographers, the photograph at
  each photographer's spot, the distance to the nearest photograph between them, and a switch that paints
  every Gaussian by the lidar's verdict. The path joins only photographers placed within 3 m of eye
  height.
- The page and the deck open with "Where COLMAP stops": five limits of COLMAP on internet photographs,
  what GhostMap adds past each, the measured evidence, a link to the chapter that shows it.

## A photograph it has never seen (evening)

- `anchor/locate.py` places a new photograph in the certified frame in about 3 s on the GPU (`web/demo_server.py`
  keeps the networks loaded); the page paints it back onto the lidar city from that pose (chapter 11).
- Leave-one-out over the fragment, scored where the reconstruction's own pose is plausible (76 of 88): placed 53,
  median 0.68 m, 90th percentile 5.6 m, worst 20 m; distance stated as open 21 (true pose a median 3.3 m from
  the stated segment, worst 81 m); refused 2, both about 115 m wrong
  (`runs/ce2e2544…/locate/leave-one-out/report.json`).
- Held out of the reconstruction: 6 tower and library photographs; 4 placed with the distance open (long lenses
  from the Arts Quad), 2 refused. Mapillary: all 120 Arts Quad frames refused.
- Tried and dropped: sight lines through lidar buildings as a check (did not separate good from bad poses);
  holding the photographer at eye height to fix the distance (leave-one-out median 1 m → 7 m).
