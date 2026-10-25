# Documentation index

When documents disagree, trust them in this order: **contract > implementation
reference > latest checkpoint > older checkpoints**. Numbers in checkpoints are
dated measurements; re-check the files they cite before quoting them as current.

## plans/ — what we committed to build

| Document | Purpose |
| --- | --- |
| [demo-delivery-contract.md](plans/demo-delivery-contract.md) | Frozen acceptance contract for the six delivery milestones (the document itself uses short milestone codes) (evaluated by `ghostmap/status/contracts.py`). |
| [modern-artsquad-pipeline.md](plans/modern-artsquad-pipeline.md) | Modern-Arts-Quad-first scope and staged outputs M1.1–M1.7. |
| [cornell-time-machine-plan.md](plans/cornell-time-machine-plan.md) | **Current plan (2026-10-25 evening)**: a twenty-year Cornell time machine on one COLMAP model with dated aerial and lidar layers; data check, chapters, pipeline, gates, timeline, decisions log. |
| [colmap-extension-plan.md](plans/colmap-extension-plan.md) | 2026-10-25 plan for the COLMAP extensions (EXIF calibration, lidar anchoring, cross-era certificates); superseded as the main line, its modules are reused. |

## reference/ — how the current pipeline works

| Document | Purpose |
| --- | --- |
| [artsquad-implementation.md](reference/artsquad-implementation.md) | Stage outputs, recovery, remaining work. |
| [artsquad-demo-runbook.md](reference/artsquad-demo-runbook.md) | Portable demo bundle and recording runbook (shipped inside the bundle). |
| [artsquad-quad6k-research-preparation.md](reference/artsquad-quad6k-research-preparation.md) | Private, research-only Quad6K lane. |

Module-level map: [../pipeline/README.md](../pipeline/README.md).

## checkpoints/ — dated measurements (oldest first)

| Document | What it records |
| --- | --- |
| [artsquad-data-checkpoint.md](checkpoints/artsquad-data-checkpoint.md) | First frozen data snapshot (superseded). |
| [artsquad-first-pilot.md](checkpoints/artsquad-first-pilot.md) | First 46-image learned pilot run. |
| [artsquad-local-checkpoint-145.md](checkpoints/artsquad-local-checkpoint-145.md) | 145-record snapshot and its best learned run (6 disjoint fragments, 5-camera Goldwin-labelled surface). |
| [artsquad-bridge-analysis.md](checkpoints/artsquad-bridge-analysis.md) | Why fragments did not merge; the fixed-radial calibration control run. |
| [artsquad-provider-checkpoint.md](checkpoints/artsquad-provider-checkpoint.md) | Quad6K / DISCO provider recovery probes. |
| [artsquad-tonight-draft.md](checkpoints/artsquad-tonight-draft.md) | Draft for the 228-record snapshot; its first run stopped during matching (resumed 2026-10-25). |
| [2026-10-25-colmap-extensions.md](checkpoints/2026-10-25-colmap-extensions.md) | **Latest**: EXIF-anchored calibration, lidar anchoring, cross-era resection certificates, the mirror-pose finding. |
| [2026-10-25-time-machine.md](checkpoints/2026-10-25-time-machine.md) | **Latest**: the time machine's first complete pass; measured facts, findings (single-facade scale ambiguity, Gates close-ups, duplicate screen), what is not done. |

## research/ — literature and direction

| Document | Purpose |
| --- | --- |
| [claude-research-review.md](research/claude-research-review.md) | **2026-10-24 research direction review**: audited inventory, literature constraints, 11 directions with adversarial reviews, decision matrix, top-3 pitches, thesis, roadmap with go/no-go gates. |
| [probes/](research/probes/) | Read-only reviewer scripts behind the review's HYPOTHESIS numbers. |
| [snavely-lineage.md](research/snavely-lineage.md) | Photo Tourism → Scene Chronology → Neural Scene Chronology notes. |
| [virtual-correspondence.md](research/virtual-correspondence.md) | Wei-Chiu Ma et al., extreme-view geometry notes. |
| [colmap-engineering.md](research/colmap-engineering.md) | COLMAP / hloc / MVS engineering notes. |
| [artsquad-additional-data-sources.md](research/artsquad-additional-data-sources.md) | Candidate data providers (PhotoCity, MegaScenes, Quad6K, …). |

## legacy/ — frozen earlier work

[legacy/README.md](legacy/README.md) summarizes both lines of work.
`legacy/v1/` holds the Boardman v1 protocol, data audit and negative result;
`legacy/repair/` holds the OpenMVS repair results and the Snavely method audit.

## handoffs/

[GHOSTMAP_CLAUDE_HANDOFF.md](handoffs/GHOSTMAP_CLAUDE_HANDOFF.md) is the
2026-10-24 research handoff prompt (constraints, candidate directions, required
review format). It is an agent brief, not project documentation.
