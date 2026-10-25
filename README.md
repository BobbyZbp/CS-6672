# GhostMap — Cornell Arts Quad from online photographs

GhostMap reconstructs the **modern Cornell Arts Quad** (several buildings plus
their observed surroundings) from automatically collected, licensed online
photographs, using measured geometry only (COLMAP / hloc SfM, OpenMVS). The
reconstruction is meant to become a reference world for a later historical
question: localizing archival photographs and recovering demolished structures
such as Boardman Hall (now the Olin Library site). Historical work is deferred
until the modern scene is validated.

**Status (2026-10-24).** No Quad-wide model exists yet. The best results are
disconnected fragments: a 21-camera Uris Library / McGraw Tower sparse component
and a 5-camera Goldwin Smith-labelled dense patch. No delivery milestone has
passed. See the [latest checkpoint](docs/checkpoints/artsquad-local-checkpoint-145.md)
and the [docs index](docs/README.md) for measured details.

## Repository layout

```text
pipeline/
  ghostmap/            current Arts Quad pipeline, one subpackage per stage
    acquire/ prepare/ sfm/ evaluate/ dense/ surface/ status/ web/ package/ qa/
    cli.py             the `run_artsquad.py` stage runner
  legacy/              frozen v1 Boardman baseline and OpenMVS "repair" scripts
  <old_name>.py        compatibility entry points (e.g. run_artsquad.py) -> ghostmap.*
  serve_artsquad_demo.py  standalone server copied into portable demo bundles
tests/                 unittest suite (test_artsquad_*.py)
config/                Arts Quad target boundary and project contract inputs
docs/                  plans, reference, checkpoints, research, legacy, handoffs
dist/                  static viewer (served as-is); dist/assets is generated
data/, artifacts/      downloaded inputs and run outputs (not versioned; see their README.md)
third_party/           pinned hloc checkout, NeuSC, OpenMVS CPU binaries
```

[pipeline/README.md](pipeline/README.md) maps every stage to its module.

## Setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-artsquad.txt   # chains repair -> hloc -> base
.venv/bin/python pipeline/setup_openmvs.py                     # private OpenMVS CPU runtime in third_party/openmvs-bin
```

Requirements chain with `-r`: `requirements.txt` (pycolmap, Pillow) ←
`requirements-hloc.txt` (torch, hloc, LightGlue) ← `requirements-repair.txt`
(trimesh, plyfile, scipy, …) ← `requirements-artsquad.txt` (Playwright).

Compute note: this machine has an RTX 3070 Ti (8 GB) under WSL2, but the current
`.venv` holds CPU-only builds (`torch 2.14.1+cpu`, pycolmap without CUDA), so COLMAP
PatchMatch is unavailable and dense work runs through OpenMVS on CPU.
`requirements-hloc.txt` pins `torch==2.14.1` without an index URL; choose the CPU or
CUDA wheel deliberately when installing.

## Run the Arts Quad pipeline

```bash
.venv/bin/python pipeline/acquire_artsquad.py --inventory-only   # discover Commons candidates
.venv/bin/python pipeline/acquire_artsquad.py --download         # fetch admitted originals
.venv/bin/python pipeline/run_artsquad.py prepare                # freeze an immutable snapshot
.venv/bin/python pipeline/run_artsquad.py pilot --snapshot SNAPSHOT/snapshot.json
.venv/bin/python pipeline/run_artsquad.py sfm --method sift --snapshot SNAPSHOT/snapshot.json  # SIFT baseline
.venv/bin/python pipeline/run_artsquad.py dense --run RUN_DIRECTORY --components 0
.venv/bin/python pipeline/run_artsquad.py site --snapshot SNAPSHOT/snapshot.json --run RUN_DIRECTORY
.venv/bin/python pipeline/run_artsquad.py holdouts --run LEARNED_RUN_DIRECTORY --components 0
.venv/bin/python pipeline/run_artsquad.py status
```

Components are reconstructed and shown separately; nothing aligns them without
measured evidence. Status evaluation is fail-closed: unknown evidence never
passes, and a working webpage is not a reconstruction. The acceptance contract
(D0/D1/D2/R1/D3/R2; D1 window 2026-11-21 – 2026-12-05) is
[docs/plans/demo-delivery-contract.md](docs/plans/demo-delivery-contract.md);
stage outputs and recovery are in
[docs/reference/artsquad-implementation.md](docs/reference/artsquad-implementation.md).

## View and test

```bash
python3 -m http.server 8080 --directory dist
# http://127.0.0.1:8080/artsquad.html   Arts Quad Atlas (diagnostic workbench, not the D1 demo)
# http://127.0.0.1:8080/surface-lab.html  legacy OpenMVS Surface Lab
# http://127.0.0.1:8080/baseline-v1.html  frozen v1 Boardman baseline
.venv/bin/python -m unittest discover -s tests -p 'test_artsquad*.py'   # 326 tests
```

## Legacy work

The frozen v1 Boardman feasibility study (a negative result) and the OpenMVS
"repair" experiments are documented in [docs/legacy/README.md](docs/legacy/README.md)
and reproduced with `bash run_pipeline.sh` and `bash run_repair.sh`.
