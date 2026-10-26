# Checkpoint 2026-10-26: georegistration, first measurements

The unified estimator (`ghostmap/anchor/georegister.py`) and its evaluation (`ghostmap/evaluate/georegistration.py`,
`identifiability_sweep.py`) after one night. Numbers come from `artifacts/georegistration/` and the anchor reports named.

## Identifiability on the synthetic hall (quick sweep, one seed)

A 60 x 30 m hall, photographers at eye height on a sloping lawn, an annex where flipped photographers would stand;
the truth is a known similarity (scale 23 m per unit, yaw 37°). "Roof-edge error" is a wrong lidar roof height for the
hall; "without roof edges" removes that cue from the fit.

| facades in view | lidar roof-edge error | cues | scale ratio | yaw error | photographers | verdict |
|---|---|---|---|---|---|---|
| one facade | 0 m | all cues | 0.970 | 2.0° | 2.4 m | not usable — scale undetermined |
| one facade | 0 m | without roof edges | 0.959 | 2.0° | 1.9 m | not usable — scale undetermined |
| one facade | 3 m | all cues | 1.217 | 2.0° | 8.5 m | not usable — scale undetermined |
| one facade | 3 m | without roof edges | 0.923 | 2.0° | 3.5 m | not usable — scale undetermined |
| two adjacent facades | 0 m | all cues | 0.993 | 0.1° | 0.3 m | usable |
| two adjacent facades | 0 m | without roof edges | 1.102 | 0.1° | 4.2 m | usable |
| two adjacent facades | 3 m | all cues | 1.230 | 0.1° | 9.5 m | usable |
| two adjacent facades | 3 m | without roof edges | 1.064 | 0.2° | 2.7 m | not usable — scale undetermined |
| two parallel facades | 0 m | all cues | 0.999 | 2.2° | 1.1 m | not usable — position undetermined |
| two parallel facades | 0 m | without roof edges | 0.999 | 2.2° | 1.2 m | not usable — position undetermined |
| two parallel facades | 3 m | all cues | 1.270 | 2.2° | 18.0 m | not usable — cues disagree |
| two parallel facades | 3 m | without roof edges | 1.000 | 2.2° | 1.1 m | not usable — scale undetermined |
| three facades | 0 m | all cues | 1.003 | 0.1° | 0.4 m | usable |
| three facades | 0 m | without roof edges | 1.002 | 0.2° | 0.4 m | usable |
| three facades | 3 m | all cues | 1.227 | 0.1° | 12.8 m | not usable — cues disagree |
| three facades | 3 m | without roof edges | 1.003 | 0.1° | 0.4 m | not usable — scale undetermined |

What it says: three facades or two adjacent ones with a correct roof edge are placed to 1 % in scale and 0.1° in yaw.
Two parallel facades fix scale and yaw but slide along the walls, and the certificate says so. One facade cannot fix
its scale and the certificate says so, whether or not the fit happens to be close. A 3 m roof-edge error biases the
scale of a corner fragment by 23 % and the certificate cannot see it (nothing else in the fragment measures scale),
which is why the report states the scale uncertainty implied by the fixing cue; where the walls do fix the scale
(parallel walls, three facades) the same error is caught as "cues disagree".

## The tower-and-library fragment (the regression)

The unified estimator reproduces the landmark method's placement of the 63-camera fragment: 1.2 % in scale, 1.1° in
rotation, 54 % of points within a metre of a wall in both; usable, scale fixed by the tower top (±3.9 %) and four roof
edges (`tests/test_artsquad_georegister.py`, `GHOSTMAP_SLOW_TESTS=1`).

## The campus-wide run (339 photographs, GPU, 7 minutes): seven fragments, none certified

`artifacts/artsquad_modern/runs/449cffd01d83846382c3`, every fragment with eight or more cameras anchored by the unified
estimator; evaluated together with the validated tower-and-library placement of the earlier run (`6406b8ea…/0`).
Geotags are the photographs' own GPS EXIF, never read by any fit; "plausible" means within 1 km of the campus.

| fragment | building | cameras | geotags (plausible/carried, wrong) | verdict | failure | ours vs geotags: median / p90 / gross | geotag baseline (LOO median) |
|---|---|---|---|---|---|---|---|
| 6406b8ea/0 | McGraw Tower | 63 | 0/1, 1 wrong | usable |  | no geotags | cannot run |
| 6406b8ea/2 | Goldwin Smith Hall | 15 | 0/0, 0 wrong | not usable |  | no geotags | cannot run |
| 6406b8ea/6 | Uris Library | 17 | 0/0, 0 wrong | not usable |  | no geotags | cannot run |
| 449cffd0/0 | Uris Library | 54 | 0/1, 1 wrong | not usable | no facade seen | no geotags | cannot run |
| 449cffd0/1 | Morrill Hall | 18 | 2/2, 0 wrong | not usable | cameras inside buildings | 844.6 / 1505.1 / 1 of 2 | cannot run |
| 449cffd0/2 | McGraw Tower | 27 | 0/1, 1 wrong | not usable | yaw ambiguous | no geotags | cannot run |
| 449cffd0/3 | Goldwin Smith Hall | 13 | 0/0, 0 wrong | not usable | scale undetermined | no geotags | cannot run |
| 449cffd0/4 | McGraw Tower | 22 | 0/1, 1 wrong | not usable | cues disagree | no geotags | cannot run |
| 449cffd0/7 | Olive Tjaden Hall | 8 | 1/1, 0 wrong | not usable | scale undetermined | 64.2 / 64.2 / 1 of 1 | cannot run |
| 449cffd0/9 | Bill and Melinda Gates Hall | 8 | 6/6, 0 wrong | not usable | scale undetermined | 324.8 / 206918.9 / 6 of 6 | 10.6 m (6 tags) |

| building | fragments | verdicts | points | median / p90 distance (m) |
|---|---|---|---|---|
| Uris Library | 6406b8eaae260163b303/0 vs 449cffd01d83846382c3/0 | usable / not usable | 2470 / 217 | 24.67 / 37.93 |
| McGraw Tower | 6406b8eaae260163b303/0 vs 449cffd01d83846382c3/0 | usable / not usable | 1889 / 1419 | 0.56 / 1.48 |
| McGraw Tower | 6406b8eaae260163b303/0 vs 449cffd01d83846382c3/2 | usable / not usable | 1889 / 1991 | 1.21 / 2.35 |
| Uris Library | 6406b8eaae260163b303/0 vs 449cffd01d83846382c3/4 | usable / not usable | 2470 / 120 | 23.07 / 35.36 |
| McGraw Tower | 6406b8eaae260163b303/0 vs 449cffd01d83846382c3/4 | usable / not usable | 1889 / 824 | 1.68 / 3.34 |
| Goldwin Smith Hall | 6406b8eaae260163b303/2 vs 449cffd01d83846382c3/3 | not usable / not usable | 1652 / 1182 | 114.71 / 116.52 |
| McGraw Tower | 449cffd01d83846382c3/0 vs 449cffd01d83846382c3/2 | not usable / not usable | 1419 / 1991 | 1.25 / 2.44 |
| Uris Library | 449cffd01d83846382c3/0 vs 449cffd01d83846382c3/4 | not usable / not usable | 217 / 120 | 2.33 / 4.26 |
| McGraw Tower | 449cffd01d83846382c3/0 vs 449cffd01d83846382c3/4 | not usable / not usable | 1419 / 824 | 1.66 / 3.37 |
| McGraw Tower | 449cffd01d83846382c3/2 vs 449cffd01d83846382c3/4 | not usable / not usable | 1991 / 824 | 0.63 / 1.58 |

How to read it:

- **Where GPS is needed it is absent or wrong.** The Quad fragments carry 0 or 1 geotags, and the one tower geotag is
  2,000 km away. The geotag baseline can run on exactly one fragment (the Gates Hall walk, 6 tags, 10.6 m leave-one-out).
- **Every refusal has a reason, and the gross errors are all refused.** The two tower-only fragments cannot fix their
  yaw (a square tower; runner-up at 95 %) or have their walls and roof edges disagree; the single-facade fragments
  (Goldwin Smith's portico, Tjaden Hall, Gates Hall) cannot fix their scale; the Morrill Hall fragment would put its
  photographers inside buildings. The three placements that could be scored against geotags are 845 m, 64 m and
  325 m off — and all three are certified not usable. No fragment was certified and then found wrong.
- **The cross-run check is the sharpest instrument.** Wherever the tower pins a campus fragment, its tower points
  coincide with the validated placement within 0.6–1.7 m; the 54-camera fragment's library points are 25 m off, so
  its yaw around the tower is wrong, and its certificate says not usable (for the wrong reason: "no facade seen"
  rather than "yaw ambiguous"; the runner-up yaw reached 76 % of the best, just under the 80 % limit).
- **The fragments themselves are the weak link.** The campus run split the tower-and-library photographs into three
  fragments (54, 27 and 22 cameras) where the earlier run held one of 63; fragments named by their majority target
  are mixtures (the "Morrill Hall" fragment holds library views that agree with the validated frame within 1.9 m).

## Next

1. Better fragments: more retrieval neighbours on the GPU (8 is a CPU-era budget), and name fragments by the
   buildings their points actually lie on rather than by their photographs' targets.
2. The yaw check before the wall check when a landmark pins the position: a fragment whose runner-up yaw puts far more
   points on walls has a search problem, not a facade problem.
3. Cue weights: with few off-tower points, free space and camera height outvote the walls; the ablation table on the
   validated fragment is the place to measure that.
4. Then the full identifiability sweep (three seeds), the Kaminsky-style baseline, and the second site.
