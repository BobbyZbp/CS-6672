# GhostMap v1 source audit

Audit date: 2026-10-23 (America/New_York)

## Included source: Wikimedia Commons

The v1 inclusion rule requires both a direct image-delivery URL and machine-readable reuse terms. The MediaWiki API supplies those fields together with dimensions, creator/credit, date, category membership, and the canonical file-description page.

- Historical discovery: Boardman Hall, Uris Library, and McGraw Tower category/search queries, followed by a historical-date or postcard metadata filter.
- Modern discovery: Uris Library and McGraw Tower category/search queries, rejecting files with historical/postcard metadata.
- Accepted reuse labels: Public Domain, CC0, CC BY, and CC BY-SA variants.
- Image-level provenance is recorded in `data/raw/manifest.json`.
- The expanded formal rerun admits 35 license-eligible historical files and 42 modern files under deterministic page-id ordering. No image was selected or removed based on feature matches or reconstruction outcome.

Category membership is treated only as retrieval metadata. It is not a correspondence, pose, depth, or visibility label supplied to COLMAP.

## Investigated but excluded from v1: Cornell Digital Collections

The first-party catalog search for the exact phrase `"Boardman Hall"` returned 13 records, of which 11 were cataloged as images. Examples include `ss:544556` (*McGraw Tower and Boardman Hall*), `ss:551068` (*Students on Arts Quad; Boardman Hall and Library Tower in background*), and `ss:1312589` (*Boardman Hall*, dated 1958-06).

The catalog JSON available during this run exposed identifiers, collection metadata, and citation text, but the inspected record response did not expose an image-level reuse license or an official full-resolution delivery field. Those records were therefore excluded rather than silently downloaded from thumbnail hosts. They are high-value candidates for a future automated rights-resolution adapter.

Endpoints inspected:

- `https://digital.library.cornell.edu/catalog.json?q=%22Boardman+Hall%22&search_field=all_fields&per_page=100`
- `https://digital.library.cornell.edu/catalog/ss:544556.json`

## Consequence

This makes v1 conservative rather than exhaustive. The negative target-coverage result means the **currently admitted, automatically auditable public set** did not support the preregistered Boardman surface gate. It does not prove that no suitable Boardman Hall photographs exist online.

