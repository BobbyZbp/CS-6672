# Bounded Quad6K private research preparation

This is a separate **private local diagnostic** input lane. Commons licensing,
capture-date and publication gates are unchanged. Quad6K's source paper,
dataset availability and archived delivery do not grant a photo redistribution
license. All recovered photos and derivatives remain `license: UNKNOWN`,
`public_redistribution_permitted: false`; research-use permission is not
certified either. Do not publish these assets under `dist` or a public URL.

```bash
.venv/bin/python pipeline/prepare_quad6k_research.py \
  --manifest data/quad6k_research_probe/manifest-quad6k-four-originals-20261025T0041.json \
  --manifest data/quad6k_research_probe/manifest-quad6k-reference-members-20261025T0054.json \
  --role-review data/quad6k_research_probe/role-review-20261025T0042.json
.venv/bin/python -m unittest discover -s tests -p 'test_artsquad_quad6k_research.py'
```

The preparer consumes only fully recovered member ledgers. It verifies original
file size and SHA256; checksum-listed, aligned tar-member boundaries; exact
HTTP206 header evidence; contiguous full payload ranges; and **every range
chunk hash against the actual corresponding original bytes**. A decoder fully
loads the original and derived image. Partial members, altered chunks, paths
outside the designated input directory, symlinks and unsupported rights flags
cannot become admitted training images. It neither downloads nor extracts the
whole tar archive.

Working JPEGs normalize EXIF orientation once and keep a declared 2400-pixel
maximum dimension. A small rebuilt EXIF whitelist retains physical camera
make/model/focal data and date assertions; GPS is removed from working images.
Original bytes and their complete EXIF remain unchanged. The original nested
`DateTimeOriginal` wins over modification-time `DateTime`. Where absent, a
modification-time assertion is explicitly weak; missing or weak dates never
become certified modern capture epochs. Unknown dates are conservatively
grouped together instead of called independent captures.

Generic `artsquad-context` is the only collection target. It is not one of the
seven core-building labels and never certifies a visible building. A declared,
generous scope box (latitude42.446–42.4525, longitude-76.488–-76.481) screens
release/EXIF GPS assertions for clearly out-of-area or conflicting metadata.
Inside-box metadata does **not** prove scene identity or physical accuracy.
Neither these GPS values, published `focals.txt`, survey coordinates, original
camera poses nor reference reconstructions are fitted poses or evaluation truth.
Published focal/survey/reference files are provenance only; geotags have the
additional explicitly disclosed scope-screening use.

Optional role notes are tied to original SHA256 and describe agent inspection,
not building ground truth. The first clearly non-scene selfie is independently
excluded by its out-of-area GPS assertions; there is no filename-specific
denylist. No manual core labels or correspondences enter reconstruction.

The existing conservative exact-byte/source-family grouping and deterministic
group split are reused. A single family remains entirely training and its
unavailable independent holdout is reported. Metadata-family membership and
requested file fractions are not evidence of independent exposures. New
members create new immutable snapshots; old inputs and snapshots are preserved.

## Actual first four-member checkpoint

Generated snapshot:
`artifacts/quad6k_research/snapshots/1c09084327f39a3141fe3b62/snapshot.json`.

- Four complete original JPEGs independently passed byte-range/hash/decode
  checks; none was relabelled as openly licensed.
- Three provisional scene-context candidates; one out-of-scope exclusion.
- Two training photos and one held-out photo, from two conservative recorded
  source families. The 33.3% file holdout is explicitly outside the requested
  15–20%; no family was split to improve that percentage.
- All four actually contain nested original capture-date assertions. The selfie
  original date is 2009-02-05, different from its 2009-06-18 modification date.
  The other three assert March2010. These are metadata assertions, not certified
  capture dates.

This checkpoint is not enough to assert overlapping reconstruction, two core
buildings, an accurate surface, D0 or D1. Larger bounded recovery must create
a fresh snapshot and a new native COLMAP run. No reconstruction was performed
by this preparer and no source/global pose was reused.
