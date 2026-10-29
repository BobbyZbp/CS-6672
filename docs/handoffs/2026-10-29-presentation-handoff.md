# GhostMap, handed over for the presentation (2026-10-29)

*For another Claude session (claude.ai chat, or Claude Code on the web at claude.ai/code with this repository). It
has none of the earlier conversation; this file is the whole context it needs. The owner is Bobby (BobbyZbp), CS 6672
at Cornell, presenting a COLMAP "hacker project". Repository: github.com/BobbyZbp/CS-6672.*

给 Bobby：把这个文件（或它在 GitHub 上的链接）给 web 上的 Claude，再说你要它做什么。它读完就知道项目是什么、数字是什么、
规矩是什么。/ To the web session: read all of this before touching anything; every number below is measured and
must not be changed, rounded differently or "improved".

## What the project is, in one paragraph

COLMAP reconstructs internet photographs into a model in a frame of its own: structure from motion recovers a scene
only up to a similarity, so one scale, three rotations and three translations (seven numbers) are arbitrary. COLMAP's
own fix, `model_aligner`, needs known camera positions, usually GPS. On internet photographs of the Cornell campus the
GPS is absent or wrong where it matters (the main fragment: 88 photographs, 63 of them Flickr web copies with no
metadata at all, one GPS tag that is 1.7 km off). GhostMap fixes the seven numbers against the world's own public 3D
model instead: USGS 3DEP airborne lidar (in metres, public domain) and OpenStreetMap building footprints. A set of
geometric cues (walls, lidar roof edges, photographers standing at eye height on the lidar ground, a tower's top,
free space along lines of sight) scores a placement; a search over heading × scale with position by descent keeps
every score; a certificate says which cue fixed which number and refuses, with a stated reason, when the geometry
cannot fix one (one facade cannot fix scale; a square tower cannot fix heading). Once the model is in metres, a new
photograph is placed on the campus in about two seconds without GPS and painted back onto the lidar city; Gaussian
splats trained from the same photographs are scored Gaussian by Gaussian against the lidar (the "referee") and
trained with one lidar rule (the "teacher"); and twenty years of public aerial flights share the same frame.
Everything is built on pycolmap and hloc (SuperPoint, LightGlue, NetVLAD). Public data only.

## What exists (all in the repository unless marked local)

| Thing | Where | Notes |
| --- | --- | --- |
| The deck, 26 slides, English + Chinese speaker notes on every slide | `artifacts/presentation/ghostmap-talk.pptx` (20 MB, three embedded H.264 clips) | built by `pipeline/ghostmap/package/talk_deck.js`; **the data it reads (`dist/assets/timemachine/scene.json`, the stills, the clips) is local only, so the web cannot rebuild it; it can edit the .pptx directly** |
| The script, slide by slide, bilingual, with timings and Q&A | `docs/presentation/talk-track.md` | also the deck's speaker notes; full run ≈ 12 min, an 8-minute cut is named in its header |
| The three directions tried first, and why each stopped | `docs/presentation/directions-tried.md` | the material behind slide 3 |
| The live demo page | `dist/timemachine.html` (+ `demo_server.py` for live placement) | needs the local data and a GPU; chapters 1–11; not runnable on the web |
| Research plan, decisions log (27 decisions), measurements | `docs/plans/georegistration-paper-plan.md`, `docs/checkpoints/2026-10-26-*.md` | every number traces to a report file |
| The estimator and the new-photograph placer | `pipeline/ghostmap/anchor/georegister.py`, `anchor/locate.py` | docstrings describe the method precisely |

## The deck's story (26 slides), with the numbers on each

Part 1, what was done and why: (1) title; (2) what GhostMap does, in one picture; (3) three things tried first;
(4) seven free numbers and why GPS cannot fix them here; (5) the world already has a 3D model.
Part 2, the pipeline step by step: (6) pipeline diagram; (7) the two inputs; (8) cues; (9) search; (10) certificate;
(11) the certificate's numbers explained; (12) cue profiles + ablation; (13) video: the snap; (14) refusals;
(15) synthetic hall, all 16 cases; (16) the same building through two fragments; (17) a new photograph;
(18) video: placing one live; (19) leave-one-out; (20) what a world frame buys; (21) held-out views;
(22) video: fly-through. Part 3: (23) what is new, honestly; (24) still working on, as the final project; (25) close;
(26) backup: the synthetic hall layouts.

The numbers (do not change):
- The main fragment: 88 licensed photographs of McGraw Tower and Uris Library (Wikimedia Commons + Flickr via
  Openverse), 32 photographers, dated ones 2003–2025, 5,901 points. GPS: 1 tag, 1.7 km off; 63 with no metadata.
  Across the Commons collection 129 of 393 photographs carry GPS. A GPS fit at Gates Hall (the one fragment with six
  tags) places a held-out camera about 11 m off.
- The world: a 640 m lidar box at 0.5 m cells (two rasters, surface and bare ground, UTM 18N); 1,078 OpenStreetMap
  footprints.
- Cues and constants: eye height 1.6 ± 0.3 m; roof-edge noise ±3 m; 32 free-space samples per ray; heading grid 3°,
  scale ⅓–3× a prior; weights walls 1.0, roof edges 0.5, camera height 0.3, tower 1.0, free space 0.5, outside 0.5.
- The certificate on the main fragment: usable; scale ±3.9 %, fixed three independent ways (tower top, parallel
  walls, roof edges of four walls), 17.8 m per COLMAP unit; runner-up heading 72 % of the winner (rule: under 80 %);
  levelled 3.7° (the photographers' heights proposed 5.5°, two thirds won); 18 of 88 photographers at eye height;
  83 % of COLMAP's points within 2.5 m of a lidar surface, 43 % within 1 m of a wall; cue scores at the optimum: tower
  1.00, free space 0.85, outside 0.97, roof edges 0.42, walls 0.25, camera height 0.12. Ablation: removing the tower
  moves the optimum 1.0 m and 0.7°; any other cue under 0.3 m.
- Refusals: the whole campus collection, 339 photographs, 29 fragments, 7 with eight or more cameras; all 7 refused
  with a reason (no facade seen, cameras inside buildings, cues disagree, scale undetermined, yaw ambiguous); the 3
  that GPS could check would have been 845, 64 and 325 m off, and all 3 were refused.
- Synthetic hall (known answer): one facade → scale undetermined; two parallel facades → position undetermined;
  a corner or three facades → usable within 1 % scale and 0.1° heading. With a 3 m roof-edge error the corner comes
  out 23 % too large and is still certified usable (the known hole); parallel walls and three facades catch the same
  error as "cues disagree".
- Two fragments, same building: McGraw Tower agrees within 1.2 m against every campus fragment; Uris Library is
  13–23 m apart where the campus fragment's heading was refused.
- New photograph: NetVLAD top 10 of the 88; SuperPoint (4,096 keypoints at 1,200 px) + LightGlue; pycolmap RANSAC
  (12 px) from the EXIF focal length and 4 guesses, focal refined free, ≥ 40 inliers; poses from other guesses keeping
  70 % of the inliers form a segment, > 25 m means "distance open". Leave-one-out over 76 trustworthy references: 53
  placed (median 0.7 m, 90th percentile 5.6 m, worst 20 m), 21 distance open (true spot a median 3.3 m from the
  line), 2 refused (each ≈ 115 m wrong); 120 of 120 Mapillary street photographs from the Arts Quad side refused
  (nobody online photographed the tower from there). Live placement: 1–2 s on a laptop GPU.
- Splats, plain → lidar-taught (same photographs, same 15,000 steps, one added rule): on lidar surfaces 41 % → 88 %;
  under the bare ground 41 % → 5 %; in measured-empty air 18 % → 8 %; pixels the lidar refutes along the fly-through
  20 % → 4 %; held-out PSNR 14.4 → 14.5 dB (best-covered view 22.4 → 22.5 dB).
- Time: six New York State aerial flights 2002–2023 on the lidar terrain; Gates Hall a parking lot until 2012.
- The three directions tried first: Boardman Hall from public-domain postcards (203 target points where 1,000 were
  required; every placed Boardman view a mirror image: modern photographs all from the south-west, postcards from the
  north-east, the tower's faces alike); one model of the whole Arts Quad (8 of 14 buildings got no camera; 339
  photographs → 29 pieces); a twenty-year time machine (0 licensed ground-level photographs of any site before
  construction; the per-point-years mechanism is Scene Chronology, 2014).

## What is new, honestly (say it this way)

Pieces exist: Kaminsky, Snavely, Seitz, Szeliski (CVPR workshops 2009) aligned SfM to overhead images with edges and
free space; Wang, Wilson, Snavely (3DV 2013) georegistered from Flickr geotags and Google Earth models; Zhang et al.
(Remote Sensing 2019) aligned ground SfM to airborne lidar, GPS-initialised; degeneracy-aware registration (Zhang,
Kaess, Singh ICRA 2016; X-ICP) is its own literature; lidar-constrained Gaussian splatting exists. The defensible
claim: cue-based grounding of sparse internet fragments with no GPS at all, against public lidar and footprints,
with a per-number diagnosis that can refuse; a method-and-system claim. Not shown yet: that it beats a fair baseline,
that the diagnosis cuts wrong acceptances, a second site. The plan (slide 24): own phone photographs with GPS as
independent truth; baselines (footprint-only alignment, a Kaminsky-style fit, scale-aware point-cloud registration,
this method without its diagnosis); acceptance coverage against false acceptances; a second 3DEP-covered campus;
written up as a workshop paper as the final project.

## Rules the owner has given (binding)

- No codenames anywhere: no run hashes, no "comp 0", no "D7", no "Slide A"; name fragments by their buildings and
  describe things in words.
- Engineering and environment problems (CUDA, memory, disk, throttling) are never slide content; Q&A at most.
- Keep the repository organised; commits under the owner's name only, no co-author lines.
- Every number on a slide comes from a measurement; if a number is not in this file or the repository's reports,
  it does not go on a slide.
- The owner reads Chinese; the audience hears English. Slide text in English; notes bilingual.

## What the web session is likely asked to do, and how

- **Restyle or polish the deck:** edit `artifacts/presentation/ghostmap-talk.pptx` directly (the generator cannot
  run without the local data). Keep every number, the slide order and the speaker notes; design is free. If slides
  are added or reordered, update `docs/presentation/talk-track.md` to match (its "### Slide N · title" headings are
  the deck's notes).
- **An 8-minute version:** the header of `talk-track.md` names the slides to skip (7, 11–13, 15–16, 18, 21–22).
- **A rehearsal or Q&A drill:** the script's "Likely questions" section has the prepared answers.
