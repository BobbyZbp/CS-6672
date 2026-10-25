# data/ — downloaded inputs (not versioned)

| Path | Size | Contents | Rights |
| --- | ---: | --- | --- |
| `artsquad_modern/` | 1.4 G | Modern Arts Quad Commons acquisition: `inventory.json` (581 discovered files), `manifest.json` (228 acquired, 3 skipped), `coverage.json`, `originals/`, `api-cache/`. Written by `acquire_artsquad.py`. | Per-file Commons licences (CC BY / CC BY-SA / PD / CC0), recorded with author and credit per image. |
| `raw/` | 46 M | v1 Boardman / Uris / McGraw Commons sets and `manifest.json`. Written by `download_commons.py`. | Commons allowlist (PD / CC0 / CC BY / CC BY-SA). Note: 3 "historical" items are dated 1970 or later. |
| `cornell_archive/` | 3.9 M | 10 Cornell Digital Library Boardman items (IIIF). Written by `legacy/repair/download_cornell_archive.py`. | Research use only; no redistribution licence established. |
| `quad6k_research_probe/` | 5.1 M | 4 recovered Quad6K JPEGs plus geotag / focal / ground-truth text files. | No licence; private research lane only. |
| `openverse/` | 25 M | 77 Flickr Creative Commons photographs of the tower and library found through Openverse (training-only supplement; no capture dates). Written by `ghostmap.acquire.openverse`. | CC BY / BY-SA / CC0 per photo, recorded with author and attribution. |
| `mapillary/` | 52 M | 120 street-level frames near McGraw Tower (dashcam views along East Avenue; judged not useful). Written by `ghostmap.acquire.mapillary`. | CC BY-SA 4.0. |
| `lidar/` | 82 M | USGS 3DEP airborne lidar crops: `NY_FingerLakes_1_2020/` (the Quad, 640 m box) and `gates-site/` (400 m box), reprojected to UTM 18N with surface and ground rasters. Written by `ghostmap.anchor.lidar`. | Public domain (U.S. Government). |
| `orthoimagery/` | 23 M | New York State orthoimagery for 2002, 2007, 2012, 2015, 2018 and 2023, warped to the same UTM boxes (`quad/`, `gates-site/`), plus the roof-presence test outputs. Written by `ghostmap.anchor.orthoimagery`. | Public (NYS GIS Program Office). |
| `footprints/` | — | OpenStreetMap building footprints (1,078 within 900 m of the campus centre) in UTM 18N. Written by `ghostmap.anchor.footprints`. | ODbL, (c) OpenStreetMap contributors. |

Snapshots under `artifacts/artsquad_modern/snapshots/` freeze exact subsets of
these files by hash; reconstruct from a snapshot, not from this directory directly.
