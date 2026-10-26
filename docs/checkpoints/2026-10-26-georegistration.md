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
