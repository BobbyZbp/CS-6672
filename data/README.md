# data/ — downloaded inputs (not versioned)

| Path | Size | Contents | Rights |
| --- | ---: | --- | --- |
| `artsquad_modern/` | 1.4 G | Modern Arts Quad Commons acquisition: `inventory.json` (581 discovered files), `manifest.json` (228 acquired, 3 skipped), `coverage.json`, `originals/`, `api-cache/`. Written by `acquire_artsquad.py`. | Per-file Commons licences (CC BY / CC BY-SA / PD / CC0), recorded with author and credit per image. |
| `raw/` | 46 M | v1 Boardman / Uris / McGraw Commons sets and `manifest.json`. Written by `download_commons.py`. | Commons allowlist (PD / CC0 / CC BY / CC BY-SA). Note: 3 "historical" items are dated 1970 or later. |
| `cornell_archive/` | 3.9 M | 10 Cornell Digital Library Boardman items (IIIF). Written by `legacy/repair/download_cornell_archive.py`. | Research use only; no redistribution licence established. |
| `quad6k_research_probe/` | 5.1 M | 4 recovered Quad6K JPEGs plus geotag / focal / ground-truth text files. | No licence; private research lane only. |

Snapshots under `artifacts/artsquad_modern/snapshots/` freeze exact subsets of
these files by hash; reconstruct from a snapshot, not from this directory directly.
