# GhostMap delivery contract: Demo first, evidence before achievement

This implements the approved 2026-10-24 project plan as a machine-readable
contract, not a claim that the project or a milestone is complete. Schedule and
scope live in `config/artsquad-project.json`. The kickoff date is not silently
reset when a later run starts. Dates are America/New_York calendar dates.

| Milestone | Planned window | Scope and completion boundary |
| --- | --- | --- |
| D0 | 2026-11-07 | At least two adjacent core buildings, shared real observations, plausible cameras, independent exposures, parallax and initial surfaces |
| D1 | 2026-11-21 to 2026-12-05 | Live 2–3-core-building demo, environment, validated surfaces and source mappings, genuine holdouts, public HTTPS, 45–60 second clip and measured performance |
| D2 | 2026-12-19 to 2027-01-16 | All seven core buildings in one observed frame, per-building validation, independent geometry checks and optimized public assets |
| R1 | 2027-02-24 to 2027-06-24 | Defensible new method, strong baselines, ablations, cross-scene validation, calibrated uncertainty and reproduction |
| D3 | 2027-06-24 to 2027-08-24 | Validated Boardman geometry and historical localization, distinct exposures, calibration/holdout checks and a supported timeline |
| R2 | 2027-08-24 to 2027-10-24 | D1/D2/R1/D3 complete plus paper, reproduction, rights, public experience, media and rollback packages |

Core IDs are `morrill`, `mcgraw-hall`, `white`, `sibley`, `tjaden`,
`goldwin-smith`, `lincoln`. `uris` and `mcgraw-tower` never count toward the
minimum. Priority candidates are Morrill–McGraw Hall–White; data determine
the actual selected adjacent subset. Selecting more than three qualified
buildings does not invalidate D1. The seven-building scope does not shrink
because an early demo is smaller.

## Status meanings and trust boundary

- `pending`: evidence is absent, unmeasured or not backed by a report.
- `failed`: a known requirement failed, the supplied split leaks, or evidence
  is malformed/inconsistent. This is a milestone check, not a global project
  stop condition.
- `blocked`: only an explicit `resources.compute_blocker` with a reason can
  produce this state. It is not an agent-goal status or automatic GPU request.
- `passed`: every required check for that milestone has supplied evidence.

An existing scientific failure takes precedence over a resource blocker.
Missing evidence is never passed. Point/face/file counts, tower quality,
metadata labels, a working viewer or a claimed paper result cannot substitute
for the respective quality checks. D0/D1, D2, R1 and D3 are tracked separately;
a successful modern demo cannot complete historical or research work.

`evaluate_milestones(evidence)` is a pure evaluator of validator-authored
attestations. It does not verify scientific truth or execute validators. A
passed attestation needs `{ "status": "passed", "report": "project/relative/report.json" }`.
The CLI additionally checks that the referenced report is a readable local
project file, freezes its SHA256 and rejects a supplied hash mismatch.
Existence of a report is not proof of correctness. Never manufacture a passed
attestation by pointing at an unrelated source manifest or browser screenshot.
Stage validators and reviewed measurement reports are the authority; browser
diagnostics alone cannot authorize release.

## Evidence JSON interface

Each `*_verified` field below is an attestation object, not a boolean. Use
`{"status":"pending","reason":"..."}` while its validator is unfinished.
Use `failed` with an explicit reason for measured failures. Keep diagnostics
under `diagnostics`; unknown or extra diagnostic fields cannot pass checks.

```json
{
  "schema_version": 1,
  "modern": {
    "feasibility_buildings": ["morrill", "mcgraw-hall"],
    "shared_frame_verified": {"status": "pending"},
    "split_verified": {"status": "pending"},
    "environment_verified": {"status": "pending"},
    "feasibility_report_verified": {"status": "pending"},
    "core_buildings": [{
      "id": "morrill",
      "component_id": null,
      "registered_cameras": null,
      "training_exposure_groups": null,
      "holdout_exposure_groups": null,
      "training_source_families": null,
      "holdout_source_families": null,
      "identity_verified": {"status": "pending"},
      "exposure_groups_verified": {"status": "pending"},
      "parallax_verified": {"status": "pending"},
      "calibration_verified": {"status": "pending"},
      "initial_surface_verified": {"status": "pending"},
      "surface_verified": {"status": "pending"},
      "appearance_verified": {"status": "pending"},
      "source_mapping_verified": {"status": "pending"},
      "holdouts_verified": {"status": "pending"},
      "coverage_report_verified": {"status": "pending"}
    }],
    "real_observation_connections": [{
      "a": "morrill", "b": "mcgraw-hall",
      "real_observations_verified": {"status": "pending"},
      "adjacency_verified": {"status": "pending"}
    }]
  },
  "demo": {
    "selected_buildings": ["morrill", "mcgraw-hall"],
    "https_url": null,
    "clip_seconds": null,
    "https_verified": {"status": "pending"},
    "interactive_verified": {"status": "pending"},
    "photo_camera_switch_verified": {"status": "pending"},
    "source_inspection_verified": {"status": "pending"},
    "missing_regions_visible": {"status": "pending"},
    "quality_report_verified": {"status": "pending"},
    "public_rights_verified": {"status": "pending"},
    "clip_verified": {"status": "pending"},
    "performance": {
      "network_mbps": null, "cold_start_seconds": null, "persistent_fps": null,
      "measured": {"status": "pending"},
      "real_device_verified": {"status": "pending"},
      "cold_cache_verified": {"status": "pending"},
      "fixed_tour_verified": {"status": "pending"}
    }
  }
}
```

The sample is deliberately incomplete and cannot pass. It is not an assertion
that Morrill or McGraw Hall has been recovered. Metadata target labels do not
establish pixel-level building identity, adjacency, or recovered coverage.

### Building and split requirements

D0 needs at least two registered cameras and two distinct training exposure
groups per selected building, plus identity/exposure/parallax/calibration and
initial-surface validation. These are engineering minima, not accuracy claims.

D1/D2 additionally need at least three registered cameras, three distinct
training exposure groups, a genuinely held-out exposure group per building,
training/test source-family IDs and each detailed validation report. A scan
copy is not a new exposure. Video frames may have real baseline but remain in
one source family for splitting. Cross-building exposure/family leakage also
fails; the split is checked globally, not separately per building. Holdout
validation reports must establish that test images never entered SfM, MVS,
texture selection or learned appearance. Unique strings by themselves cannot
prove independence.

Selected components must agree and `shared_frame_verified` must pass. A
spanning set of edges needs both real-observation and separate physical
adjacency validation. An authored map placement, same component label, file
category co-occurrence or unverified epipolar match is insufficient.

### D1 presentation requirements

Every demo attestation is required. The clip must be 45–60 seconds. HTTPS must
be verified against a public destination, not merely spelled `https` or pointed
at localhost/private IP. Rights review must cover the actual public assets.

Performance needs a real-device report, cold cache and fixed tour, network
shaped to 20 Mbps or slower, desktop time-to-interactive <=5 seconds and
sustained >=30 FPS. A headless software-WebGL screenshot is an interaction
diagnostic, not real-device performance evidence. These numbers define D1
engineering acceptance, not an unmeasured guarantee.

### Later-stage attestation keys

- `modern`: `per_building_report_verified`,
  `independent_geometry_validation_verified`, `lod_streaming_verified`,
  `modern_release_verified` (D2, plus all seven detailed building checks).
- `research`: `novelty_review_verified`, `method_verified`,
  `strong_baselines_verified`, `ablations_verified`, `cross_scene_verified`,
  `heldout_protocol_verified`, `uncertainty_calibration_verified`,
  `reproducibility_verified` (R1).
- `historical`: `boardman_geometry_verified`, `photo_localization_verified`,
  `independent_exposures_verified`, `parallax_verified`,
  `calibration_stability_verified`, `heldout_validation_verified`,
  `persistent_structure_frame_verified`, `unknowns_explicit`,
  `timeline_verified`, `rights_verified` (D3, also dependent on D2).
- `release`: `paper_package_verified`, `reproduction_package_verified`,
  `rights_review_verified`, `public_experience_verified`,
  `media_package_verified`, `rollback_verified` (R2, dependent on D1/D2/R1/D3).

An alternative historical building cannot fill the Boardman field without an
approved contract revision. Publication, press coverage and university
endorsement are external outcomes, not falsifiable internal completion flags.

## Commands and current state

```bash
.venv/bin/python pipeline/artsquad_status.py
.venv/bin/python pipeline/artsquad_status.py --evidence artifacts/artsquad_modern/milestone-evidence.json
.venv/bin/python -m unittest discover -s tests -p 'test_artsquad_contracts.py'
```

Default output is `artifacts/artsquad_modern/project-status.json`; `--output -`
prints JSON without writing a status artifact. When no evidence path is given,
the CLI reads the conventional milestone-evidence file if it exists, otherwise
it makes no achievement assertions. An explicitly supplied unreadable evidence
file is a CLI error. `--skip-resource-probe` avoids the optional local module
import. Default resource probing reads local RAM/disk, imports local torch and
pycolmap and records their CUDA availability. It does not SSH, inspect remote
credentials, request allocations, purchase resources or submit jobs.

The resource plan is 48 GiB CUDA VRAM, 128 GiB host memory and about 2 TiB working
storage with backup. A local probe is not proof of an authorized remote node;
that remains explicitly unverified until separately established.

The first implementation adds a frozen contract, pure evaluator, honest
diagnostic status and adversarial regression tests. It does not complete a
multi-building dense scene, public HTTPS delivery, real-device benchmark or
research contribution. Sparse pilot outputs and metadata inventories must stay
diagnostics until the corresponding validators and deliverables exist.
