# GhostMap — an interactive 3D time machine of Cornell

**Geographically grounded · time-aware · visually immersive.** GhostMap takes licensed
internet photographs of the Cornell campus (Wikimedia Commons, Flickr via Openverse),
reconstructs them with COLMAP, places the reconstructions **without GPS** inside the
world's own 3D model (public USGS 3DEP lidar and OpenStreetMap footprints), renders them
as Gaussian splats that the lidar **checks and teaches**, and replays the campus over
twenty years with dated aerial flights. Public data only; no annotation, no geotags, no
hand-picked correspondences. Built for the CS 6672 hacker presentation; the research line
is planned towards a CVPR 2027 workshop paper
([plan](docs/plans/georegistration-paper-plan.md)).

**Where** — placement with a certificate ([measurements](docs/checkpoints/2026-10-26-georegistration.md)):

- of 393 campus photographs only 129 carry GPS, and the tower-and-library fragment's 63
  photographs carry one, which is 2,000 km off: GPS alignment cannot even start;
- a cue-based estimator (walls, lidar roof edges, the tower top, photographers at eye height,
  free space along camera rays) places the 63-camera fragment in metres; its certificate
  reads usable, scale fixed by the tower top (±3.9 %) and four roof edges, and it reproduces
  the earlier landmark anchor within 1.2 % in scale;
- on the campus-wide run (339 photographs, GPU) all seven larger fragments are refused,
  each for a stated reason (a square tower cannot fix its heading, one facade cannot fix its
  scale, close-ups show no facade); the three placements GPS tags could check were 64 to
  845 m off, and every one of them was refused.

**How it looked** — the lidar as referee and teacher:

- a Gaussian splat trained in the lidar's metres can be judged Gaussian by Gaussian against
  what the lidar measured; the plain splat puts 30 % of its Gaussians on lidar surfaces,
  46 % under the ground and 25 % in air the lidar saw empty;
- trained with one lidar rule (the air above the measured surface is empty), the same
  splat puts 70 % on lidar surfaces and 10 % under the ground, halves its median distance
  to the lidar (5.2 m to 1.9 m), needs half the Gaussians and a third of the time, at the
  same held-out PSNR (14.4 against 14.2 dB; 24 dB on the best-covered held-out view).

**When** — twenty years: six New York State aerial flights 2002–2023 draped on the lidar
terrain, documented construction dates for Gates, Klarman and Milstein Hall, and every
reconstructed point of the tower fragment carrying the years photographs saw it.

Earlier stages kept as infrastructure: EXIF-anchored calibration, the landmark anchor, the
archival-postcard certificates (every Boardman Hall pose is a mirror image, so no bound on
Boardman is claimed) ([results](docs/checkpoints/2026-10-25-colmap-extensions.md)).

Live demo: `http://127.0.0.1:8080/timemachine.html` (serve `dist/`, below; ← → step through
the ten chapters, F full screen). Slides: `http://127.0.0.1:8080/presentation.html` (arrows,
F full screen, N speaker notes); talk track: `docs/presentation/talk-track.md`.

## Repository layout

```text
pipeline/
  ghostmap/            current Arts Quad pipeline, one subpackage per stage
    acquire/ prepare/ sfm/ evaluate/ dense/ surface/ status/ web/ package/ qa/
    anchor/ archival/ chronology/   lidar anchoring, archival resection, existence intervals
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
```

GPU (optional, used by the learned matching and the splats): the CUDA build of torch
(`torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cu126`) and, for
gsplat's kernels, an unprivileged CUDA 12.6 compiler installed with micromamba into `.cuda/`:

```bash
micromamba create -p .cuda -c nvidia/label/cuda-12.6.3 -c conda-forge cuda-nvcc=12.6 cuda-cudart-dev=12.6 cuda-cccl=12.6 cuda-nvcc-dev_linux-64=12.6
ln -s targets/x86_64-linux/lib .cuda/lib64
export CUDA_HOME=$PWD/.cuda PATH=$PWD/.cuda/bin:$PATH CPATH=$PWD/.cuda/targets/x86_64-linux/include LIBRARY_PATH=$PWD/.cuda/targets/x86_64-linux/lib TORCH_CUDA_ARCH_LIST=8.6
.venv/bin/python -m pip install gsplat==1.5.3 ninja   # kernels compile on first use (about five minutes)
.venv/bin/python pipeline/setup_openmvs.py                     # private OpenMVS CPU runtime in third_party/openmvs-bin
.venv/bin/python -m pip install -r requirements-geo.txt         # lidar and footprints (laspy, pyproj, shapely)
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
(six delivery milestones; the multi-building demo window is 2026-11-21 – 2026-12-05) is
[docs/plans/demo-delivery-contract.md](docs/plans/demo-delivery-contract.md);
stage outputs and recovery are in
[docs/reference/artsquad-implementation.md](docs/reference/artsquad-implementation.md).

## Run the COLMAP extensions

```bash
.venv/bin/python pipeline/run_artsquad_calibration_variant.py --source-run RUN --variant exif-anchored
PYTHONPATH=pipeline .venv/bin/python -m ghostmap.anchor.lidar          # 3DEP lidar crop, UTM 18N
PYTHONPATH=pipeline .venv/bin/python -m ghostmap.anchor.footprints     # OSM footprints
PYTHONPATH=pipeline .venv/bin/python -m ghostmap.anchor.align --run RUN --component 0
PYTHONPATH=pipeline .venv/bin/python -m ghostmap.archival.modern_control --anchor-report RUN/anchor/0/report.json
PYTHONPATH=pipeline .venv/bin/python -m ghostmap.archival.run --anchor-report RUN/anchor/0/report.json --people artifacts/archival-people/people.json
PYTHONPATH=pipeline .venv/bin/python -m ghostmap.web.ghostmap_scene    # data for dist/ghostmap.html
```

## View and test

```bash
python3 -m http.server 8080 --directory dist
# http://127.0.0.1:8080/ghostmap.html   live demo of the COLMAP extensions
# http://127.0.0.1:8080/slides.html     presentation slides
# http://127.0.0.1:8080/artsquad.html   Arts Quad Atlas (diagnostic workbench, not the multi-building demo)
# http://127.0.0.1:8080/surface-lab.html  legacy OpenMVS Surface Lab
# http://127.0.0.1:8080/baseline-v1.html  frozen v1 Boardman baseline
.venv/bin/python -m unittest discover -s tests -p 'test_artsquad*.py'   # 343 tests
```

## Legacy work

The frozen v1 Boardman feasibility study (a negative result) and the OpenMVS
"repair" experiments are documented in [docs/legacy/README.md](docs/legacy/README.md)
and reproduced with `bash run_pipeline.sh` and `bash run_repair.sh`.
