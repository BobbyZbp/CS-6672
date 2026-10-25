# Cornell Time Machine: twenty years of the campus from licensed online imagery

*Plan written 2026-10-25 evening, after the direction change. Supersedes the
COLMAP-extension plan as the main line; the extensions built under it (EXIF
calibration, lidar anchoring, batched matching, the photographer-position
certificates) are reused as infrastructure. Presentation: mid-November 2026,
live web demo plus slides, CS 6672 hacker project on COLMAP.*

## The idea in one paragraph

A time machine for Cornell that spans the years in which photographs actually
exist, 2002 to 2026, rather than the century back to Boardman Hall that the
online record cannot support. One COLMAP reconstruction holds photographs from
every year; each 3D point then carries the interval in which it was observed
(the mechanism of Scene Chronology, Matzen and Snavely 2014, rebuilt on
pycolmap), and two dated public layers that COLMAP never had are added as
observers: New York State's orthoimagery of 2002, 2007, 2012, 2015, 2018 and
2023 seen from above, and USGS lidar of 2020. The visitor drags a year slider:
Gates Hall rises from a parking lot, Klarman Hall fills the courtyard behind
Goldwin Smith Hall, and McGraw Tower, the one thing that never changes, holds
the whole timeline in place.

## What the data check found (2026-10-25, measured)

Licensed Commons photographs that pass the project's rules, by capture year;
Flickr Creative Commons through Openverse in the last column.

| Place | Commons eligible | before construction | during | after | Flickr CC |
| --- | ---: | ---: | ---: | ---: | ---: |
| Gates Hall (built March 2012 to 2014; a parking lot before) | 53 | 0 | 31 (one session, 2014) | 22 (2017-2025, 4+ authors) | 33 |
| Klarman Hall (completed 2016; the space behind Goldwin Smith Hall) | 37 | 9 near the site, none showing it | 0 | 28 (2017-2025) | 5 |
| Milstein Hall (opened 2011; a parking lot behind Sibley) | 17 | 0 | 1 | 16 | 1 |
| Goldwin Smith Hall (stable; its east side changed by Klarman) | 48 | 2003-2013: 18 | | 2016-2025: 30 | 10 |
| Olin Library and plaza | 55 | 2006-2026 throughout | | | 22 |
| Uris Library and McGraw Tower (the anchor) | 94 | 2002-2026 throughout | | | 45 |

Two consequences shape the design:

1. **At ground level there are no licensed "before" photographs of any of the
   three sites.** The pre-construction state exists only from above: the state
   orthoimagery shows the Klarman courtyard open in 2002, 2007 and 2012, under
   excavation in 2015 and roofed in 2018; the Gates site is a parking lot in
   2002-2012 and a building from 2015. So the time machine's "before" is
   aerial, draped on the lidar terrain, and is labelled as such. The 3D
   buildings exist only for years with ground photographs.
2. **The change is visible from above at every site**, and the orthoimagery
   is public, keyless and dated. That layer is certain; the ground-level 3D is
   the part with risk.

## What the visitor sees (chapters of the live demo)

1. **The campus from above, 2002 to 2023.** Lidar terrain draped with each
   year's orthoimage; a year slider; the three sites outlined. Pure data, no
   claims.
2. **Gates Hall rises.** Ground-level textured 3D of Gates Hall from 2014-2025
   photographs, anchored to the lidar; before 2014 the slider shows the parking
   lot from the air and a flat ground. Click a wall: "first photographed 2014;
   roof first visible from the air 2015; absent from the air in 2012".
3. **Klarman Hall fills the courtyard.** Goldwin Smith Hall's photographs span
   2003-2025, so its points carry twenty-year intervals while Klarman's start in
   2017; the atrium appears in the slider between the 2012 and 2018 aerials.
4. **McGraw Tower, the thing that does not change.** Ninety-four photographs
   from 2002 to 2026 registered in one model, with the dense textured tower on
   the lidar; a gallery pinned in 3D by year; the existing photographer-position
   certificates as the honesty panel. (Stretch: tower-top photographs placed
   on the belfry, looking out.)
5. **What the record cannot show.** The sites before construction at ground
   level, Boardman Hall, and the mirror-pose finding, as the limits chapter.

## Pipeline (what is built, in order)

| Step | Reuses | New |
| --- | --- | --- |
| Acquisition of the three sites | Commons discovery (categories, title and location search), Openverse supplement, licence rules | Gates Hall target and location searches added to `config/artsquad-modern.json` |
| Dated aerial layer | — | `anchor/orthoimagery.py`: NYS orthoimagery WMS per year, cropped to the Quad and Gates sites, georeferenced in UTM 18N like the lidar |
| Reconstruction per site | learned SfM, batched matching, cache reuse | one snapshot for the Quad (Goldwin Smith + Klarman + tower + Olin) and one for Gates Hall |
| Anchoring | tower-landmark anchoring for the Quad | a footprint-based variant for Gates Hall (facade gravity, footprint walls, lidar eave height); gate: two independent scales within 10 % |
| Existence intervals | — | `chronology/intervals.py`: per point, first and last capture year among observing images, plus "should have been visible but was not" negatives from registered cameras of other years (visibility tested against the lidar building model); per building, roof presence per aerial year by change detection against the lidar footprint |
| Dense textured surfaces | OpenMVS on CPU | one textured mesh per site, textured only from post-construction photographs |
| Viewer | lidar terrain, photo frusta, click-through provenance | year slider, aerial drape per year, building meshes shown only inside their intervals, "first photographed / first seen from the air" panel, tower gallery |
| Slides and QA | slides page, browser QA stage | rewritten around the five chapters |

## Gates and honesty rules

- A building appears in a given year only if (a) a registered photograph from
  that year or earlier observes it, or (b) the aerial image of that year shows
  its roof inside its footprint. Each case is labelled differently in the
  viewer.
- No ground-level geometry is shown for years without ground photographs;
  the aerial drape alone stands in, with the label "no licensed ground-level
  photograph of this state exists online".
- Lidar is from 2020 and is used only for terrain and for the anchored frame;
  buildings that did not exist in 2020 are not an issue here (all three were
  complete by then), but the lidar is never shown as pre-2020 geometry.
- Every number on the page comes from a report file; every photograph shows
  its licence and author.

## Timeline

- **Week of 2026-10-26.** Acquisition for the three sites (Commons throttles
  originals to about one per ten minutes, so this runs in the background from
  tonight); orthoimagery layer; snapshots; reconstructions; anchoring; existence
  intervals. Go/no-go for Gates Hall anchoring by 2026-10-30.
- **Week of 2026-11-02.** Dense meshes; the new viewer with the year slider;
  the tower chapter; first full run-through.
- **Week of 2026-11-09.** Polish (the viewer was judged rough: dense textures,
  smooth camera moves, photo-through-camera), slides, rehearsal, buffer.

## Cut order if time runs short

1. Tower-top photographs on the belfry.
2. Milstein Hall (16 photographs after, none before).
3. Negative-evidence intervals (keep first-seen/last-seen only).
4. Dense meshes for Klarman (keep Gates and the tower).

## Decisions log

1. **2026-10-25: direction changed from Boardman Hall to a twenty-year time
   machine.** The Boardman postcards cannot be placed correctly through the
   surviving buildings (every registered pose is a mirror image; no licensed
   modern photograph looks at the tower from the Arts Quad side), so the
   century-scale time machine fails on data. The twenty-year version has
   dated photographs and dated aerial imagery for the buildings that changed.
2. **The "before" state is aerial.** Checked on 2026-10-25: no licensed
   ground-level photograph of the Gates, Klarman or Milstein sites before
   construction exists on Commons; the nine pre-2014 photographs near the
   Klarman site show Goldwin Smith's front, Lincoln Hall and Rockefeller Hall.
3. **Disk.** To make room (4.2 GB free, acquisition refuses below 5 GB), the
   staged image copies, feature caches, holdout and query folders of the
   finished runs were deleted (reports and native models kept), together with
   five legacy OpenMVS output directories whose built copies remain under
   `dist/assets/repair/`, and the pip cache. Recorded in `artifacts/README.md`.
4. **Aerial roof-presence test is a diagnostic, not the decision.** The own-outline edge score shows the change at every site (Klarman 2.0-2.4 before 2015, 3.7-4.1 from 2015; Gates 2.4-3.1 before 2015, 4.0-5.7 from 2015; Milstein 2.3-3.0 before 2015, 3.3-4.8 after), but stable buildings vary between flight years by as much, so no global or per-building threshold separates the two groups cleanly at this resolution. The timeline therefore rests on three sources shown side by side: documented dates (Wikipedia: Gates Hall construction March 2012, dedicated October 2014; Klarman Hall completed 2016; Milstein Hall opened 2011), the per-year aerial crops for the reader to see, and the first year a registered ground photograph observes the building. The automatic score is reported with the crops.
5. **Footprints now cover 900 m around the campus centre** (1,078 buildings, including Gates Hall) because the first fetch box stopped 60 m short of the Gates site; raster helpers skip footprints outside their box.

6. **Downloader order (2026-10-25 evening).** The Commons downloader read the config stored inside the inventory, which predates the `download_priority` list, so the sites the time machine needs were not fetched first. The live config's list is now passed in and the downloader was restarted; originals already on disk are reused, nothing is downloaded twice. Commons still throttles originals to roughly one every ten minutes at worst, so the Gates Hall set (35 eligible) takes hours, not minutes.
7. **Viewer terrain.** The terrain triangles were wound facing downward, so the draped aerial image was never lit from above and the ground rendered as flat grey; fixed. Steep faces of the lidar surface (building walls) are drawn in a flat wall colour instead of the aerial image smeared down them, and the walls of a changed building vanish with it when its site is flattened for the years before it stood. The Gates-site terrain is trimmed against the Quad terrain with a one-cell overlap instead of a gap.
8. **The time machine page is the main demo.** `dist/index.html` opens `dist/timemachine.html`; the earlier COLMAP-extension page stays reachable as the earlier demo, and its lidar anchoring and chronology feed the tower chapter. The page has its own Playwright check (`ghostmap/qa/timemachine_page.py`).
9. **Footprint anchoring (2026-10-25 evening).** Fragments without McGraw Tower are anchored by `ghostmap/anchor/footprint.py`: gravity from facade normals; yaw and position from the named building's walls (a precision-and-recall wall score, so a fragment cannot shrink onto one wall line), photographers outside every footprint and at eye height; scale from a wide grid, chosen by the same wall score together with a roof-edge term (the model's facade top along each wall, taken where the point density ends, against the lidar surface just inside that wall). The walls-only scale profile, the other yaw quadrants, the per-wall spread and the photographer heights are reported as checks. On a synthetic hall with a known similarity (two facades, clutter, a neighbour where flipped photographers would stand, a sloping lawn) the fit recovers the scale within 3 %, the yaw within 0.1 degrees and the photographers within 2 m (`tests/test_artsquad_footprint_anchor.py`). Two search bugs found on the way: a single position descent from the footprint centre got stuck between walls (now a position grid first), and scipy's default Nelder-Mead simplex stepped kilometres in UTM coordinates (now explicit steps).
10. **The Goldwin Smith fragment does not anchor.** Its fifteen photographs see the portico and the A. D. White statue from the lawn, plus three views down from the tower. One facade of unknown scale matches walls of different heights at different scales (the portico shrunk onto a nine-metre wing wall scores as well as the portico at its own fifteen-metre wall), only one wall ever holds enough points, and the fit is reported as "anchoring attempted; frame not usable". The Klarman chapter therefore rests on the aerial flights and the documented dates, and this failure goes into the limits chapter as what a single facade cannot fix. Gates Hall, a long box with three facades of 15 to 19 m roof edge, is the case the method was built for.
11. **Gates Hall from the ground (2026-10-25 night).** Forty-one licensed records, but thirty-five are one photographer's walk on 2014-06-08, uploaded both to Flickr (reached through Openverse) and to Commons; the supplement stage had no near-duplicate screen against the base snapshot, so each of those photographs entered twice, and the largest fragment's ten cameras are five viewpoints. The screen is now a dHash comparison at supplement time. The photographs themselves are close-ups of the entrance undercroft, the stairs and the bike racks; the facades the lidar measures are not in them, so the fragment cannot be anchored through the footprint walls (eight per cent of its points lie within a metre of any wall). The Gates chapter therefore shows the dated photographs as the ground record ("first licensed photograph 2014-06-08") beside the flights and the documented dates, and says why there is no anchored ground model.
12. **Deduplicated, the Gates Hall photographs barely register.** With the duplicate screen in place, 24 photographs map into fragments of 3, 3 and 2 cameras; the largest (579 points) collapses onto one wall in the footprint fit and is reported as not usable. The chapter shows the ground record (dated photographs) and this attempt; the volume stays the lidar shape.
