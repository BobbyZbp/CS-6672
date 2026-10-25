# pipeline/

All reconstruction code. Run scripts from the repository root with
`.venv/bin/python pipeline/<entry>.py`; `pipeline/` is the import root, so modules
import each other as `ghostmap.<group>.<module>`.

## Layout

| Path | Contents |
| --- | --- |
| `ghostmap/` | The current modern Arts Quad pipeline, one subpackage per stage (table below). `ghostmap/paths.py` defines `ROOT`, the repository root. |
| `<old_name>.py` | Compatibility entry points. Each one runs or aliases a `ghostmap` module, so existing commands, `run_artsquad.py` subprocess stages, the shell scripts, tests and recorded report commands keep working. Add new code under `ghostmap/`, not here. |
| `serve_artsquad_demo.py` | Standalone stdlib-only server copied byte-for-byte into portable demo bundles. It must not import `ghostmap`. |
| `legacy/v1/` | Frozen v1 Boardman baseline (Commons SIFT/hloc joint model). Run through `run_pipeline.sh`. |
| `legacy/repair/` | Frozen OpenMVS "repair" / Surface Lab historical experiments. Run through `run_repair.sh`. |
| `legacy/unused/` | Code that nothing calls (kept for reference, not wired in). |

## Stage map (current pipeline)

`run_artsquad.py` (`ghostmap/cli.py`) runs the stages below, either in-process or
as a subprocess through its entry-point name.

| Stage | Module (`ghostmap/…`) | Entry point | Role |
| --- | --- | --- | --- |
| acquire | `acquire/artsquad.py` | `acquire_artsquad.py` | Discover Commons candidates, apply license/metadata rules, download originals with provenance. |
| | `acquire/commons.py` | `download_commons.py` | Commons metadata, filename and dHash helpers (also the v1 downloader `main()`). |
| | `acquire/review.py` | `review_artsquad_inputs.py` | Metadata-only role screen (interior, event, reference document, scene candidate, …). |
| | `acquire/provider_probe.py` | `artsquad_provider_probe.py` | Bounded HTTP-range probes of Quad6K / DISCO / BigSfM / PhotoCity releases. |
| prepare | `prepare/snapshot.py` | `prepare_artsquad.py` | Freeze a content-addressed snapshot: hash checks, capture-date evidence, families, train/test split. |
| | `prepare/quad6k_research.py` | `prepare_quad6k_research.py` | Private research-only Quad6K snapshot (not redistributable). |
| sfm | `sfm/learned.py` | `run_artsquad_sfm.py` | NetVLAD + SuperPoint + LightGlue + pycolmap mapping on the train split; shared `sha256`, `write_json`, `select_training_images`. |
| | `sfm/sift.py` | `run_artsquad_sift.py` | Pinned CPU SIFT/COLMAP baseline on the same inputs. |
| | `sfm/cache_reuse.py` | `reuse_artsquad_cache.py` | Reuse verified feature/match HDF5 groups from a completed run. |
| | `sfm/calibration_variant.py` | `run_artsquad_calibration_variant.py` | Same-snapshot remap with fixed radial or fixed intrinsics (calibration control). |
| | `sfm/inspect_run.py` | `inspect_artsquad_run.py` | Recompute component reports from saved native models. |
| evaluate | `evaluate/holdouts.py` | `validate_artsquad_holdouts.py` | Localize held-out test images against a frozen component. |
| | `evaluate/bridges.py` | `analyze_artsquad_bridges.py` | Inter-component edges, triangulation angles, calibration-strain warnings. |
| dense | `dense/openmvs_cpu.py` | `run_cpu_mvs.py` | COLMAP undistortion -> OpenMVS CPU densify / mesh / texture. |
| | `dense/texture_from_cameras.py` | `texture_from_cameras.py` | Texture the unchanged mesh from calibrated source cameras. |
| | `dense/mesh_supported_patches.py` | `mesh_supported_patches.py` | Conservative local-facet mesh from fused points with support filters. |
| | `dense/setup_openmvs.py` | `setup_openmvs.py` | Install the pinned OpenMVS v2.4.0 CPU runtime into `third_party/openmvs-bin`. |
| surface | `surface/dense_support.py` | `audit_artsquad_dense_support.py` | Per-point view/source-family provenance of the fused cloud. |
| | `surface/supported.py` | `build_artsquad_supported.py` | Family-supported surface fragments. |
| | `surface/faces.py` | `index_artsquad_faces.py` | Face -> source-photo index for the viewer's click-through evidence. |
| status | `status/contracts.py` | `artsquad_contracts.py` | Pure, fail-closed D0–R2 milestone evaluator (see `docs/plans/demo-delivery-contract.md`). |
| | `status/project_status.py` | `artsquad_status.py` | Build `artifacts/artsquad_modern/project-status.json`. |
| web | `web/site.py` | `build_artsquad_site.py` | Validate a run and write the viewer data under `dist/assets/artsquad/`. |
| | `web/local_preview.py` | `build_local_research_preview.py` | Private research preview under `artifacts/local_previews/`. |
| package | `package/source_zip.py` | `package_artsquad_code.py` | Deterministic source-only ZIP from an explicit allowlist. |
| | `package/demo_bundle.py` | `package_artsquad_demo.py` | Portable offline demo bundle with hash manifest. |
| qa | `qa/browser.py` | `check_artsquad_browser.py` | Playwright functional checks of `dist/artsquad.html`. |
| | `qa/reel.py` | `check_artsquad_reel.py` | Playwright checks of `dist/demo-reel.html`. |
| | `qa/record_demo.py` | `record_artsquad_demo.py` | Scripted headless tour recording. |

## Conventions

- Keep stage outputs under `artifacts/artsquad_modern/` and inputs under `data/`;
  reports record those paths, so don't move them.
- Third-party imports that are optional for tests (pycolmap, torch, hloc) stay
  lazy (inside functions) where they already are.
- `sha256`, `write_json` and the canonical-JSON helpers define snapshot and run
  IDs. Changing their bytes changes every ID, so treat them as frozen.
