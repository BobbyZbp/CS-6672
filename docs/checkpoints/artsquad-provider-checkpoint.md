# Quad6K bounded recovery checkpoint — 2026-10-24 evening

This advances the exact-scene lead in `artsquad-additional-data-sources.md`.
It does **not** establish a connected reconstruction, a public-use license, or
delivery of all 6,514 photographs. No existing Commons acquisition, immutable
snapshot, COLMAP run or public browser asset was modified by this work.

## What was actually delivered

The 2016 Internet Archive replay of the original DISCO release delivered a
checksum-valid tar prefix and, subsequently, exact nonzero HTTP ranges. The
standard `if_` replay variant worked for the deeper offsets. Some earlier
requests timed out or returned connection refused; those failures are preserved
in their reports and were not converted into evidence of success.

The archive advertises original length **8,718,817,280 bytes**, but explicitly
returns `Warning: 299 wayback content truncated by "time"`. That original size
is not proof that every member is available. Whole-archive completeness remains
false. Only fully delivered, individually checked members count as recovered.

Actual checksum-listed metadata members:

| Member | Tar header offset | Body bytes |
|---|---:|---:|
| `pairs.txt` | 512 | 50,832,029 |
| `geotags.txt` | 50,833,408 | 214,872 |
| `dists.txt` | 51,048,960 | 77,904 |
| `east_north.txt` | 51,127,808 | 200,221 |
| `focals.txt` | 51,329,024 | 201,896 |
| `east_north.ground_truth.txt` | 51,531,776 | 15,033 |
| `viewangles.txt` | 51,547,648 | 77,738 |

`geotags.txt`, `east_north.txt`, and `focals.txt` were recovered completely into
`data/quad6k_research_probe/`, preserving their exact bytes and SHA256 values.
The delivered first two files each contain **4,255 rows**; `focals.txt` contains
**6,514 rows**. The original release page's “about 5,000” GPS claim is therefore
not a substitute for the actual available filename associations.
The ground-truth text also appeared completely inside a bounded inspected
range; it has not been used as alignment or validation control. `pairs.txt`
was **not** downloaded. Consumer GPS and authors' survey references are not
interchangeable, and repeated coordinate rows need grouping before evaluation.

Four complete JPEG members were recovered under a **6 MiB body budget**:

| Original member | Body bytes | Decoded dimensions | Inspection |
|---|---:|---|---|
| `4883_IMG_6571.jpg` | 1,705,882 | 2000 × 1333 | Exterior facade; White Hall lettering visible |
| `0285_4402444359_b226da8831_o.jpg` | 447,916 | 1080 × 1440 | **Non-scene selfie with cat; reject as building input** |
| `5127_IMG_6815.jpg` | 1,375,650 | 2000 × 1333 | Exterior colonnaded facade, lawn, tree and paths |
| `2678_IMG_4129.jpg` | 1,006,294 | 1600 × 1067 | Exterior stone end facade and snowy ground |

The JPEG member bodies total **4,535,742 bytes**. Including four independently
retrieved 512-byte tar headers, this recovery read **4,537,790 bytes**. The
images were fully decoded, not merely accepted on JPEG magic or filenames.
Embedded metadata is preserved in the original bytes. The release's notion of
“image” does not imply a native full-camera-resolution photograph: these are
the actual delivered dataset originals at the dimensions above.

The unrelated selfie is important evidence that the catalog is not a semantic
admission list. Its consumer GPS is also far from the Quad. Do not feed every
dataset member into the scene simply because the collection is named Quad6K.
Agent visual screening is recorded by original SHA in
`data/quad6k_research_probe/role-review-20261025T0042.json`; it is explicitly
not ground-truth building identity or a physical-coverage certification.

## Provenance and use boundaries

The archived original project page is readable through the standard public
`if_` replay URL. It explicitly offers the 8 GB images/ground-truth tar, the
250 MB result/comparison ZIP, and Bundler tracks. Its exact snippets and links
are preserved in the metadata report below. This page does **not** establish a
CC photo license or public texture-redistribution permission.

All recovered files therefore remain **unknown-rights local research inspection
data**, separate from Commons and public `dist/`. `public_redistribution_permitted`
and `reconstruction_input_admitted` remain false in the provider ledger. Local
acquisition was explicitly authorized; admission to a separate research-only
experiment needs source validation and screening. Public photo/texture display
needs a separate terms decision. No author was contacted, no account/API key
was used, and no certificate or access control was bypassed.

The exact source URL used for successful member recovery is:

`https://web.archive.org/web/20161130144459if_/http://vision.soic.indiana.edu/disco_files/ArtsQuad_dataset.tar`

Recovery records contain original member name, checksum-valid header offset,
header SHA, exact HTTP `Content-Range`, per-chunk SHA256, complete file SHA256,
decode dimensions/EXIF, unchanged-original flag, source replay timestamp and
truncation warning. Failed and incomplete ranges are never saved as images.
There is no invented pose, inferred camera frame or public-model substitution.

Primary local evidence:

- `artifacts/provider-probes/quad6k-2016-range-20261025T0030.json`
- `artifacts/provider-probes/quad6k-offset50833408-20261025T0033.json`
- `artifacts/provider-probes/quad6k-terms-and-header-20261025T0039.json`
- `artifacts/provider-probes/quad6k-alternate-replay-offset-20261025T0041.json`
- `artifacts/provider-probes/quad6k-headerwalk51531776-20261025T0052.json`
- `artifacts/provider-probes/quad6k-reference-members-20261025T0054.json`
- `artifacts/provider-probes/quad6k-four-originals-20261025T0041.json`

Report filenames are checkpoint identifiers; authoritative request/checkpoint
times are the embedded UTC values, not the labels in those filenames.

**Correction to earliest probe schema:** early immutable reports set
`range_subset_feasible:true` from a valid prefix alone. That flag is too weak
and must not be used as acquisition evidence. Current schema requires both a
verified nonzero range and a complete small README or decoded image before
asserting it. `prefix_range_verified`, `nonzero_range_verified`, complete-member
records, actual decoded files and body-range hashes are the authoritative
granular evidence. Even the strengthened feasibility flag is not a license,
archive-completeness, overlap or milestone claim.

## Executable bounded interface

`pipeline/artsquad_provider_probe.py` has fixed provider hosts, no automatic
redirects, bounded reads, checksum/path/type checks, no arbitrary tar extraction,
and byte reservations even on timeout. A 429/503 stops all further requests in
the same probe; Retry-After is preserved, never bypassed. Existing reports and
differing original bytes are not overwritten. Pure inspection never admits or
saves photos; recovery requires explicit known member offsets and stores only
complete checked files in the separate research quarantine.

```bash
.venv/bin/python -m unittest discover -s tests -p test_artsquad_provider_probe.py

# Header-only index: at most 64 × 512 bytes; never scans through photo bodies.
.venv/bin/python pipeline/artsquad_provider_probe.py \
  --source quad6k-2016-frame \
  --tar-start-offset 58184704 --tar-headers 64 \
  --per-request-bytes 512 --request-limit 64 --total-bytes 32768 \
  --output artifacts/provider-probes/NEW-HEADER-CHECKPOINT.json

# One already checksum-listed original, local research only.
.venv/bin/python pipeline/artsquad_provider_probe.py \
  --source quad6k-2016-frame --recover-member-offset 51626496 \
  --per-request-bytes 1048576 --request-limit 4 --total-bytes 2097152 \
  --output artifacts/provider-probes/NEW-RESEARCH-MEMBER-CHECKPOINT.json
```

The explicit research budget was subsequently increased to **at most 128 MiB
additional payload**, with the local 5 GiB free-space floor retained. This is
not authorization for the full 8 GB archive. Broader header indexing is in
progress; no overlapping multi-building subset is yet verified. Archive order
is random, not an exposure sequence. Select photos using actual scene evidence,
source/session metadata and geometric overlap, preserve exclusions, then run
our own COLMAP. Published Bundler outputs are references only, not our results.
