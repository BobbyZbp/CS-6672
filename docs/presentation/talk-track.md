# GhostMap: run of show for the CS 6672 hacker presentation

Ten to twelve minutes: slides for the idea, where COLMAP stops, and the numbers, the live page for the moments that only work
live (the snap, the splats, the year slider). Every number on the slides is read from
`dist/assets/timemachine/scene.json`, the same file the demo page reads, so the two cannot disagree.

## Before the talk (pre-flight, 10 minutes)

1. `cd ~/CS6672 && python3 -m http.server 8080 --directory dist` (or `python3 serve.py` inside the offline
   bundle `artifacts/presentation/ghostmap-demo-*.zip`).
2. Open two tabs in Chrome or Edge with hardware acceleration on (check `chrome://gpu`: WebGL 2 hardware accelerated):
   - `http://127.0.0.1:8080/presentation.html` (slides; `F` full screen, arrows, `N` speaker notes)
   - `http://127.0.0.1:8080/timemachine.html#colmap` (demo; opens on chapter 0, where COLMAP stops)
3. Warm the demo: click chapters 4 and 5 once so both splats are downloaded and sorted (a few seconds each),
   then return to chapter 0. Close everything else that uses the GPU.
4. Fallbacks ready: the tour video `artifacts/presentation/ghostmap-tour.webm` (plays in any browser) and the
   chapter stills on the slides themselves.

## Run of show

| Time | Where | What to show | What to say |
| --- | --- | --- | --- |
| 0:00 | Slide 1 | title | The United States already has a public 3D model of itself. Internet-photo reconstructions have always ignored it. We put Cornell's internet photographs inside it, and then let it judge them and teach them. |
| 0:45 | Slide 2 | the idea | Lidar is public domain and covers most of the country. COLMAP gives a fragment with no scale, no up, no north; GPS would help, but look how few photographs carry it, and how many of those are wrong. |
| 1:15 | Slide 3 (or demo `#colmap`) | where COLMAP stops | Why this is a COLMAP hack: everything starts from COLMAP's cameras and points, and on internet photographs of a real place five of its limits show. No scale or north without GPS; no warning when a placement cannot be trusted; fragments in separate frames; splats with paint in mid-air; one static scene. Each row is a chapter of the demo. |
| 2:00 | Slide 4 → demo `#void` | the fragment floating | This is the biggest fragment of the Arts Quad, in COLMAP's own frame. Rotate it: it is a tower and a library, but nothing says how big or which way is up. |
| 2:15 | demo `#snap` | the snap animation | No geotags, no clicked correspondences: gravity from the facades, the walls of the footprints, the lidar roof edges, photographers at eye height, the tower top. It lands. And it comes with a certificate. |
| 3:15 | Slide 6 | the certificate | The scale profile is peaked: the tower top and four roof edges fix the scale to a few percent. The other three yaw quadrants score far below the best one. Removing any single cue barely moves the answer. |
| 4:00 | Slide 7 → demo `#refuse` | knowing when it can't | The interesting part is the refusals. Every other campus fragment is refused, each with a reason: a square tower cannot fix its yaw, one facade cannot fix its scale, close-ups see no facade. The placements geotags could check were tens to hundreds of metres off, and every one of them had been refused. |
| 5:15 | demo `#referee` | the plain splat and its lidar classes | Now the photographs as a Gaussian splat, in the lidar frame. Green is on a lidar surface, red is in air the lidar saw empty. Floaters are the classic failure of in-the-wild splats; here we count them against a measurement. |
| 6:15 | demo `#teacher` | the fly-through, then plain/taught at the same pose | Same photographs, same steps, one extra term: the measured free space is empty. The fly-through walks a camera path no photographer took: the map shows where it is, and at each photographer's spot the real photograph appears. Between them the splat has to invent the view. Tick "paint by the lidar's verdict": red is paint in air the lidar measured empty, purple is under the ground. Slide 9 has the numbers. |
| 7:15 | demo `#above` → `#gates` → `#tower` | the year slider | And because everything is in one metric frame, time comes for free: six public aerial flights, Gates Hall rising from a parking lot, and every point of the tower knowing which years photographs saw it. |
| 8:45 | Slide 11 | limits | What the record cannot show, said out loud: no ground photographs of any site before construction, lidar thin on walls, splats keep only what was photographed. |
| 9:30 | Slide 12–13 | what is new, reproducible | Kaminsky 2009 aligned to overhead images; we add lidar heights, metric cues and a certificate. Everything is public data and reproducible wherever 3DEP exists. |
| 10:15 | Slide 14 | thanks | Questions, and the demo stays open. |

## Likely questions

- **How accurate is the placement?** Three independent things fix the scale of the 88-photograph fragment: the
  tower top (±3.9 %), the walls alone and four lidar roof edges. Its heading agrees with the earlier landmark method
  within 2°. The photographers' heights over the lidar ground showed a leftover tilt; levelling by two thirds of it
  (3.7°) scored best on all cues together, levelling by all of it made the walls fit worse. The certificate states
  all of this (slide 6).
- **Why not just use GPS?** Look at slide 2: few photographs carry it, the tower fragment has essentially none,
  and some tags are thousands of kilometres off. Where geotags exist we use them only as held-out truth.
- **Is the lidar a fair referee for walls?** Airborne lidar sees roofs and ground densely and walls thinly, so
  the free-space test allows 2.5 m horizontally and the nearest-return distance on walls is conservative. The
  fragment's own COLMAP points give the noise floor (shown on slide 8).
- **Does the lidar prior just delete everything inconvenient?** It only acts inside the measured volume (the
  lidar box up to 120 m above the ground) and only on Gaussians more than 2 m above the highest lidar surface
  within 2.5 m; held-out photographs (never trained on) are the check that the rendering did not get worse for
  views the training never saw.
- **Why not push the prior harder?** We tried: five times the weight puts 96 % of the Gaussians on lidar
  surfaces and the mean held-out PSNR rises (14.5 to 14.8 dB), but the best-covered held-out view loses about
  a decibel (22.5 to 21.4 dB). On the earlier, unlevelled placement the same push cost 4 dB: how hard the
  lidar can teach is set by how well we placed the fragment.
- **What about change over time? The lidar is from 2020.** Exactly why the time machine shows documented dates
  and aerial flights; the free-space prior would wrongly delete a building that stood only before 2020, so it is
  applied to a fragment of buildings that stood throughout (the tower and the library).
- **Is this a paper?** The target is a CVPR 2027 workshop: placement with certificates, and the lidar as referee
  and teacher for in-the-wild reconstruction, on a second site as well.

## If something breaks

- Splat does not appear: the GPU driver is not used by the browser (check `chrome://gpu`); show slides 8–9 and the video.
- Page blank: the server is not running from `dist/` (ES modules need HTTP), or the port is taken: `python3 serve.py 8090`.
- Projector resolution: the page is responsive; the slides keep 16:9 inside any window.
