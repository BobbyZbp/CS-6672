# Arts Quad data checkpoint — 2026-10-24

This is the first reproducible input checkpoint for D0/D1, not a completed
multi-building reconstruction or a declaration of independent camera coverage.
The existing acquisition was left untouched. No second downloader was started.

## Frozen input to use

`artifacts/artsquad_modern/snapshots/f27fe368e880c774a3506ea1/snapshot.json`

- Preparation policy: 4; schema: 1.
- Frozen at `2026-10-24T04:39:35.020783+00:00` (00:39 EDT on October 24).
- Source manifest was `running`. This is an immutable partial acquisition, not
  the final collection. Later acquisitions require a new snapshot.
- Source manifest SHA256:
  `2bad543b5560faa99c83f6e6164b014d9d68e77d9788aac1040b5f745d98e56f`.
- Source inventory SHA256:
  `1992657239f2459f0bcefa3698dab0e710380f03399d5fb82a4eda5566bf984f`.
- Read `train.txt` and `test.txt` beside the snapshot. The manifest's
  `images_directory` points to the existing working-image directory. Original
  and working bytes are referenced by path and guarded by hashes, not copied
  into another image pool. Downstream stages must recheck those hashes.

The Commons inventory contains 581 discovered files and 231 metadata-eligible
files. These numbers are neither downloaded camera counts nor reconstruction
coverage. The snapshot covers only 96 acquired records. The existing acquisition
advanced naturally from 90 to 96 during this work; preparation did not restart,
modify or duplicate the downloader.

| Checkpoint quantity | Files / metadata groups |
|---|---:|
| Source records in snapshot | 96 |
| Raw and working hashes, dimensions, decoding and capture evidence pass | 93 |
| Ordinary exterior/context metadata candidates | 56 |
| Training candidates | 46 |
| Held-out candidates | 10 |
| Role-excluded files retained for other handling | 37 |
| Validation-rejected records | 3 |
| Distinct checked original-byte hashes, all roles | 93 |
| Metadata source families among ordinary scene candidates | 30 |

The held-out file fraction is 10/56 = 17.86%. Files are not independent views.
The distinct-original count does not certify that different files are different
exposures: rescans, crops and re-encodings can have different byte hashes.

## Core-building collection coverage and gaps

Targets are discovery/category labels. They do not prove that a building is
visible, correctly identified in pixels, registered, sufficiently observed, or
connected to another building. One source file may carry several target labels;
do not add rows as if they were disjoint independent views.

| Core target | Acquired labels | Train | Test | Role-excluded | Rejected | Scene source families | Immediate limitation |
|---|---:|---:|---:|---:|---:|---:|---|
| Morrill | 9 | 5 | 1 | 3 | 0 | 4 | Three photostitches need explicit camera handling; five training files do not establish both facades or a cross-building bridge. |
| McGraw Hall | 5 | 3 | 2 | 0 | 0 | 4 | Sparse starting collection; test registration and overlap before dense reconstruction. |
| White | 1 | 1 | 0 | 0 | 0 | 1 | No independent holdout or multi-exposure reconstruction support established. |
| Sibley | 2 | 1 | 1 | 0 | 0 | 2 | One training file alone cannot support this building's independent multi-view surface. |
| Tjaden | 2 | 2 | 0 | 0 | 0 | 1 | Both files share one metadata source family; no independent holdout stratum. |
| Goldwin Smith | 8 | 4 | 2 | 1 | 1 | 6 | One interior excluded; one upload-only date rejected; remaining views need actual geometric/semantic checks. |
| Lincoln | 5 | 4 | 1 | 0 | 0 | 2 | Several files are correlated within a source family; validate geometry and held-out overlap. |

Context limitations also matter: Stimson and Klarman each have only one ordinary
scene source family, Milstein has no acquired record, and all 14 Olin-labelled
files are excluded pending suitable role/camera handling in this snapshot.
Uris and McGraw Tower are anchors/context, not substitutes for the core quota.

## Role, date, exposure and split audit

The preparer checks both original and working SHA256 against the acquisition
record, fully decodes both files, checks recorded dimensions, reapplies metadata
admission, and separately verifies photographic capture-date evidence.

The 37 role exclusions consist of 4 panoramas/photostitches, 7 documents,
9 interiors, 7 ambiguous interior/exterior library images and 10 event/person
images. Originals remain
available for future suitable processing; exclusions are not deletions.

Four files are explicitly excluded from the ordinary pinhole-camera input:

- `modern__26037734_Cornell_University_campus_panorama_from_McGraw_Tower.jpg`
- `modern__6968245_Cornell_Morrill_Hall_photostitch_May_2009.jpg`
- `modern__6968505_Cornell_Morrill_Hall_photostitch_rectilinear_May_2009.jpg`
- `modern__6968603_Cornell_Morrill_Hall_photostitch_rectilinear_corrected_May_2009.jpg`

Their title metadata identifies panorama/stitch processing even though the
downloaded XMP projection hint was unknown. Derived perspective views may become
usable after explicit camera recovery, but their tiles are not new baselines.

The Olin contact sheet also exposed ten indoor event/person/table photographs
labelled Art + Feminism, Edit-a-thon, editors or researching. Generic event
screening now marks them `interior-event-review`; metadata building/category
membership does not make them exterior observations. The ordinary Olin Library
1–4 photographs remain conservatively excluded as ambiguous library imagery;
this checkpoint does not silently override their role based on manual viewing.

Three records are rejected because only an original upload date is asserted,
with no acceptable photographic capture evidence:

- `modern__16963761_UrisLibrary24.jpg`
- `modern__52379834_McGrawTowerPumpkin.jpg`
- `modern__6341137_Andrew-Dickson-White-Statue.jpg`

The older acquisition admission can mistake these legacy date strings for
capture dates. Preparation closes that gap without rewriting the acquisition
manifest or its metadata. This is not a change to the retained source records.

Exact checked original-byte duplicates share an exposure ID. Distinct originals
are not automatically certified independent. The perceptual screen flags one
pair, the two AD White Reading Room images; both are already excluded interiors,
so there is no flagged outdoor cross-split pair in this checkpoint. This screen
cannot rule out all crops, re-encodings or related exposures.

Source families conservatively combine exact exposures, explicit known sessions
or video identities, and overlapping capture-day/partial-date periods for the
same normalized author. Unknown author aliases and incomplete metadata remain
limitations. Distinct frames can provide real baseline while still belonging
to one statistical family.

Splitting is deterministic and source-family-aware. The only family for a tiny
target stays in training; its unavailable independent holdout is explicitly
reported. Training/test independence remains uncertified until exposure and
scene audits are complete. No held-out file may enter feature extraction,
mapping, MVS, texture fitting or neural appearance training for the main test.

## Correction history — preserve, do not silently replace

| Snapshot | What happened | Status |
|---|---|---|
| `9ce9535319a796d4ca16f349` | Initial 90-record snapshot: 64 scene candidates, 52 train / 12 test. Contact-sheet inspection exposed three title-labelled Morrill photostitches plus a panorama that the old role screen admitted as pinhole candidates. | Superseded; retained for audit only. |
| `44024c79c50cc8218251aa26` | Four stitch/panorama candidates excluded. A split-selection issue then put the large cross-building source family into test, leaving the only White/Tjaden family out of reconstruction and giving a 30% holdout. | Superseded; not the pilot input. |
| `d43f46c823f25bc95b7affff` | Policy 3 retains tiny strata in train with explicit no-holdout limitations, while keeping eligible multi-family strata represented where possible: 49 train / 11 test. Later contact inspection found ten indoor event photos admitted by the generic screen. | Superseded; the associated CPU SfM pilot is retained for diagnostic history only. |
| `f27fe368e880c774a3506ea1` | Policy 4 excludes ten Olin event/person images. The live downloader had meanwhile added six valid source records, giving 96 total, 56 scene candidates and 46 train / 10 test. | Current checkpoint for exterior work. The older 49-train run is a superseded diagnostic, not a publishable outdoor result. |

These are input-preparation corrections, not alternate successful modern
reconstructions. Their immutability makes the reason for each change visible.

## Next measured work

The next step is the snapshot-bound COLMAP pilot on the 46 training files,
retaining every recovered component and its unresolved similarity frame. A
large component or a cross-target edge does not by itself verify two buildings
or an Arts Quad connection. Camera degeneracy, repeated facades, target pixel
identity, independent baseline and surface support must still be checked.

D0/D1 remain unpassed at this data checkpoint. The preparation implementation
has 15 focused preparation tests, plus 15 fused-visibility provenance tests.
These are software checks, not a
scientific geometry acceptance result.
