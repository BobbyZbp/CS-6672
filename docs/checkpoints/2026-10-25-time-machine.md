# Checkpoint 2026-10-25 (night): the Cornell Time Machine, first complete pass

What exists at the end of the day, what is measured, and what the demo says. Numbers come from the
report files named below; nothing here is typed from memory.

## The page

`dist/timemachine.html` (served from `dist/`), five chapters, one year slider from 2002 to 2026:

1. **From above.** USGS 2020 lidar terrain for the Arts Quad (640 m box) and the Gates Hall site
   (400 m box), draped with the New York State orthoimagery of the 2002, 2007, 2012, 2015, 2018 and
   2023 flights. Steep lidar faces are drawn as plain walls so the aerial image is not smeared down
   them. Changed buildings are flattened to the ground before their documented construction and shown
   as lidar volumes afterwards (`config/timeline.json`, dates cited to Wikipedia).
2. **Gates Hall.** Documented dates; the six aerial crops with the own-outline edge score (a
   diagnostic); the ground record: 37 licensed photographs by 4 photographers, 35 dated, first
   2014-06-06; the reconstruction attempt (below) and why no ground model is shown.
3. **Klarman Hall.** Same structure: 8 photographs by 4 photographers, 6 dated, first 2017-10-21;
   not yet reconstructed.
4. **McGraw Tower.** The 63-photograph tower-and-library fragment anchored to the lidar (two
   independent scales 2.0 % apart), 25 photographs dated 2003 to 2025, every point carrying the years
   it was observed, photographers by year, click-through to each photograph and licence.
5. **Limits.** No licensed ground-level "before" photograph of any site; volumes are the 2020 lidar
   shape; the single-facade scale ambiguity; the Boardman mirror-pose finding from the earlier work.

Build command for the current page (the builder's defaults omit the ground records):
`PYTHONPATH=pipeline .venv/bin/python -m ghostmap.web.timemachine_scene --run artifacts/artsquad_modern/runs/6406b8eaae260163b303 --snapshot artifacts/artsquad_modern/snapshots/90d1dc5d21b4f9c5c08e15ab/snapshot.json --ground-run artifacts/artsquad_modern/runs/6da4ccc327cb12bf14df`.

Slides: `dist/timemachine-slides.html` (ten slides; the tower and Gates numbers are filled from
`scene.json`). Check: `ghostmap/qa/timemachine_page.py` walks every chapter, year and slide
(`artifacts/browser-qa/timemachine/report.json`, passed).

## Measured facts added today

| Fact | Where |
| --- | --- |
| Tower fragment: 63 photographers, 5,777 points, lidar-anchored, scales 2.0 % apart | `runs/6406b8eaae260163b303/anchor/0/report.json` |
| Existence intervals for that fragment; 25 dated photographs | `runs/6406b8eaae260163b303/chronology/0-intervals.json` |
| Aerial outline score per building per flight (diagnostic) | `data/orthoimagery/*/roof-presence/report.json` |
| Footprint anchoring recovers a known similarity on a synthetic hall: scale within 3 %, yaw within 0.1 degrees, photographers within 2 m | `tests/test_artsquad_footprint_anchor.py` |
| Goldwin Smith portico fragment (15 photographs): anchoring attempted, frame not usable | `runs/6406b8eaae260163b303/anchor/2/report.json` |
| Gates Hall: 37 licensed photographs (35 dated); the 35 Commons ones in the training split map into fragments of 11, 8 and 3 cameras; anchoring of the largest attempted, not usable (42 % of its points within a metre of a wall) | `runs/6da4ccc327cb12bf14df/report.json`, `.../anchor/0/report.json` |

## Findings worth saying out loud

- **A single facade cannot fix its own scale.** Without the tower in view, the Goldwin Smith
  portico fits walls of different heights at different scales; the fit reports it. The chapter rests
  on the flights and the documented dates.
- **The Gates Hall photographs are close-ups.** One photographer's walk (2014-06-08) uploaded to both
  Flickr and Commons supplied most of the collection; the entrance undercroft, stairs and bike racks
  are in them, the facades are not. Deduplicated, they barely register together.
- **The same photograph can arrive twice.** The supplement stage now screens Openverse photographs
  against the base snapshot by dHash (17 rejected in the latest snapshot).
- **Commons throttling** (an original roughly every ten minutes when it throttles) shaped the day:
  the downloader now takes the sites the demo needs first.

## Not done yet

- The dense textured surface of the tower fragment exists at half resolution (OpenMVS on CPU;
  the full-resolution fusion was killed by the 7.6 GB memory limit): 368,530 faces, shown on request
  in the tower chapter in place of the points. It covers what the photographs see (the tower's
  Quad-facing sides and parts of the library), not the whole buildings.
- The complete photograph collection (393 eligible pages) is still downloading; the Quad
  reconstruction has not been rerun on it.
- Tower-top photographs placed on the belfry; negative evidence of absence; dense surfaces per site.
