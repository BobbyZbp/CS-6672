# pipeline/

All reconstruction code. Run scripts from the repository root with
`.venv/bin/python pipeline/<entry>.py`; `pipeline/` is the import root, so modules
import each other as `ghostmap.<group>.<module>`. Newer stages have no
compatibility entry point and run as `PYTHONPATH=pipeline .venv/bin/python -m ghostmap.<group>.<module>`.

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
| | `acquire/openverse.py` | `-m ghostmap.acquire.openverse` | Openverse (Flickr CC) photographs as a training-only geometry supplement: licence, place-name and historic-marker screens, dHash dedup against Commons. |
| | `acquire/provider_probe.py` | `artsquad_provider_probe.py` | Bounded HTTP-range probes of Quad6K / DISCO / BigSfM / PhotoCity releases. |
| | `acquire/timeline_probe.py` | `-m ghostmap.acquire.timeline_probe` | Per-building, per-year counts of licensed Commons photographs around the time-machine sites (how much dated ground evidence exists). |
| | `acquire/mapillary_probe.py` | `-m ghostmap.acquire.mapillary_probe` | Mapillary coverage counts near the Quad from the public coverage tiles; token helpers (`.secrets/mapillary.env`). |
| | `acquire/mapillary_login.py` | `-m ghostmap.acquire.mapillary_login` | Interactive Mapillary OAuth login; stores the user token under `.secrets/`. |
| | `acquire/mapillary.py` | `-m ghostmap.acquire.mapillary` | Download Mapillary frames that face McGraw Tower from the Arts Quad sector (CC BY-SA). |
| prepare | `prepare/snapshot.py` | `prepare_artsquad.py` | Freeze a content-addressed snapshot: hash checks, capture-date evidence, families, train/test split. |
| | `prepare/supplement.py` | `-m ghostmap.prepare.supplement` | Extend a frozen snapshot with supplement photographs in the training split only. |
| | `prepare/quad6k_research.py` | `prepare_quad6k_research.py` | Private research-only Quad6K snapshot (not redistributable). |
| sfm | `sfm/learned.py` | `run_artsquad_sfm.py` | NetVLAD + SuperPoint + LightGlue + pycolmap mapping on the train split; shared `sha256`, `write_json`, `select_training_images`. |
| | `sfm/sift.py` | `run_artsquad_sift.py` | Pinned CPU SIFT/COLMAP baseline on the same inputs. |
| | `sfm/cache_reuse.py` | `reuse_artsquad_cache.py` | Reuse verified feature/match HDF5 groups from a completed run. |
| | `sfm/calibration_variant.py` | `run_artsquad_calibration_variant.py` | Same-snapshot remap: fixed radial, fixed intrinsics, or EXIF-anchored (cameras with an EXIF focal prior held constant). |
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
| status | `status/contracts.py` | `artsquad_contracts.py` | Pure, fail-closed evaluator of the six delivery milestones (see `docs/plans/demo-delivery-contract.md`). |
| | `status/project_status.py` | `artsquad_status.py` | Build `artifacts/artsquad_modern/project-status.json`. |
| web | `web/site.py` | `build_artsquad_site.py` | Validate a run and write the viewer data under `dist/assets/artsquad/`. |
| | `web/local_preview.py` | `build_local_research_preview.py` | Private research preview under `artifacts/local_previews/`. |
| package | `package/source_zip.py` | `package_artsquad_code.py` | Deterministic source-only ZIP from an explicit allowlist. |
| | `package/demo_bundle.py` | `package_artsquad_demo.py` | Portable offline demo bundle with hash manifest. |
| qa | `qa/browser.py` | `check_artsquad_browser.py` | Playwright functional checks of `dist/artsquad.html`. |
| anchor | `anchor/lidar.py` | `-m ghostmap.anchor.lidar` | USGS 3DEP lidar around the Quad: only intersecting octree nodes, Web Mercator to UTM 18N, surface and ground rasters. |
| | `anchor/footprints.py` | `-m ghostmap.anchor.footprints` | OSM building footprints (ODbL) in UTM 18N. |
| | `anchor/align.py` | `-m ghostmap.anchor.align` | Similarity from a COLMAP fragment to lidar: facade gravity, tower landmark, photographer scale, one yaw; independent scale check. |
| | `anchor/footprint.py` | `-m ghostmap.anchor.footprint` | Anchor a fragment without the tower through one building's footprint: walls for yaw and position, lidar roof edges for the scale; walls-only scale, yaw quadrants and photographer heights as checks. |
| | `anchor/orthoimagery.py` | `-m ghostmap.anchor.orthoimagery` | Dated New York State orthoimagery (2002–2023) warped onto the lidar grid in UTM 18N, per site. |
| chronology | `chronology/intervals.py` | `-m ghostmap.chronology.intervals` | Existence intervals per reconstructed point from the capture years of the photographs that observed it; per-building summaries. |
| | `chronology/aerial.py` | `-m ghostmap.chronology.aerial` | Own-outline edge score of each changed building in each aerial year (a diagnostic; documented dates drive the timeline). |
| archival | `archival/resect.py` | — | Profile-likelihood resection over focal length; standpoint and pedestrian cues; certificates; line-of-sight test. |
| | `archival/match.py` | — | 2D-3D anchors for archival queries via SuperPoint + LightGlue against the anchored model. |
| | `archival/run.py` | `-m ghostmap.archival.run` | Certificates for the public-domain Boardman-era photographs and surviving-building stand-ins. |
| | `archival/modern_control.py` | `-m ghostmap.archival.modern_control` | Positive control: re-resect every modern photographer from its own anchors. |
| | `archival/people.py` | `-m ghostmap.archival.people` | Standing-pedestrian detection (foot and head pixels). |
| | `web/ghostmap_scene.py` | `-m ghostmap.web.ghostmap_scene` | Data for the earlier demo `dist/ghostmap.html` (lidar anchoring, postcards, certificates). |
| | `web/timemachine_scene.py` | `-m ghostmap.web.timemachine_scene` | Data for the Cornell Time Machine `dist/timemachine.html`: terrain, dated aerial textures, changed-building volumes, dated point clouds, per-building ground records and dense surfaces. The current page is built with `--run artifacts/artsquad_modern/runs/6406b8eaae260163b303 --snapshot artifacts/artsquad_modern/snapshots/90d1dc5d21b4f9c5c08e15ab/snapshot.json --ground-run artifacts/artsquad_modern/runs/6da4ccc327cb12bf14df`; without `--snapshot` the ground records are absent. |
| | `qa/timemachine_page.py` | `-m ghostmap.qa.timemachine_page` | Playwright checks of `dist/timemachine.html`: every chapter and year, no page errors. |
| | `qa/reel.py` | `check_artsquad_reel.py` | Playwright checks of `dist/demo-reel.html`. |
| | `qa/record_demo.py` | `record_artsquad_demo.py` | Scripted headless tour recording. |

## Conventions

- Keep stage outputs under `artifacts/artsquad_modern/` and inputs under `data/`;
  reports record those paths, so don't move them.
- Third-party imports that are optional for tests (pycolmap, torch, hloc) stay
  lazy (inside functions) where they already are.
- `sha256`, `write_json` and the canonical-JSON helpers define snapshot and run
  IDs. Changing their bytes changes every ID, so treat them as frozen.
