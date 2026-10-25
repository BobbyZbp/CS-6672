# Reviewer probes (read-only analyses)

Small scripts written by the adversarial feasibility reviewers during the
2026-10-24 research review ([../claude-research-review.md](../claude-research-review.md),
§3.12). They read existing COLMAP models with `pycolmap` and print numbers; they
write nothing. They are kept so the HYPOTHESIS figures quoted in the review can
be reproduced and later re-run on a clean, lidar-anchored model.

| Folder / file | Direction | What it measures | Run against |
| --- | --- | --- | --- |
| `d7-standpoint/fisher.py`, `fisher2.py`, `profile.py` | D7 | Linearised Fisher information of each Boardman-titled camera against modern-only anchors: sd(log f), centre sd along the anchor ray and vertically, anchor elevation angle; focal profile likelihood. | `artifacts/hloc_cross_era/sfm_joint` |
| `d8-detective-focal_profile2.py` | D8 | PnP residual vs. fixed focal (0.8-1.25x) using persistent anchors only; anchor bounding box and depth spread per postcard. | same |
| `d10-reoccupied/joint_geo.py`, `pp.py`, `scale.py`, `up.py` | D10 | Nearest modern standpoint per archival camera, plane+parallax sensitivity (px per metre of baseline), inverse-depth spread, scale and up-vector estimates. | same |
| `d11-ghost-hull/ghull_*.py` | D11 | Azimuth bins of registered Boardman views, oracle visual-hull area vs. the Sanborn footprint, perpendicular ray error propagation. | same |

All of these ran on the legacy joint model, which is era-contaminated (it
contains a 2021 iPhone photo labelled historical) and has no metric scale. Their
outputs are therefore hypotheses about magnitudes, not measurements of the
final system. Invoke each with the model directory as the first argument from
the repository root, e.g.

```bash
.venv/bin/python docs/research/probes/d7-standpoint/fisher2.py artifacts/hloc_cross_era/sfm_joint
```
