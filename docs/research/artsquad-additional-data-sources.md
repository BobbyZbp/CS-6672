# Additional Arts Quad photo sources — verified feasibility leads

Checked on 2026-10-24 using public project pages, small metadata files, object
listings and asset headers. No large archive, photo collection, reconstruction
or pretrained model was downloaded. No account was used, no author contacted,
no access control bypassed, and the running Commons acquisition was untouched.

## Bottom line

There is a genuine existing Cornell Arts Quad photo collection: **Quad6K /
DISCO explicitly released 6,514 Arts Quad images with camera-position reference
data.** PhotoCity also retains a public archive with models for all seven core
buildings. These are much stronger leads than continuing to expect a handful of
Commons photographs to provide every required facade and bridge.

However, **neither collection has been acquired or cleared for this project**.
The old Quad6K host redirects away from its files; an archived 8 GB release is
indexed by the Internet Archive, but present-day binary delivery has not yet
been confirmed. PhotoCity explicitly requires contacting the maintainer for
photos. Publicly accessible thumbnails, point clouds or counts do not grant
public texture/image redistribution rights.

## 1. Quad6K / DISCO — strongest exact-scene lead

### Primary and archived primary evidence

- Cornell's live official [BigSFM page](https://www.cs.cornell.edu/projects/bigsfm/)
  lists **Quad6K (DISCO webpage), with ground-truth camera positions**.
- Its linked project URL is
  `http://vision.soic.indiana.edu/disco/`.
- A public archived copy of that original project page is readable:
  [DISCO release page, 2011 capture](https://web.archive.org/web/20111231082144id_/http://vision.soic.indiana.edu:80/disco).
- Authors on that page are David Crandall, Andrew Owens, Noah Snavely and
  Daniel P. Huttenlocher. This is the CVPR 2011 discrete-continuous SfM work,
  not a newly discovered unrelated dataset with a similar name.

The original page explicitly describes:

| Released item | Original page's description |
|---|---|
| Arts Quad photos + camera reference | 6,514 images, 8 GB tar archive |
| Consumer geotags | About 5,000 photographs with iPhone 3G GPS |
| Survey reference | 348 camera positions measured using differential GPS, claimed accuracy about 10 cm |
| Results and comparison code | 250 MB ZIP, including similarity-aligned camera comparison |
| Bundler tracks | 350 MB tar archive |

The 10 cm number is the original authors' camera-position survey claim, **not**
an accuracy measurement of our recovered surfaces. No assertion is made that
every facade, modern addition or environmental region is covered. Actual
capture dates, file completeness and building boundaries still require reading
the delivered metadata and images.

### Actual URL and availability checks

The project page's original photo archive link is:

`http://vision.soic.indiana.edu/disco_files/ArtsQuad_dataset.tar`

On this check, both HTTP and HTTPS versions redirected to the general
`https://vision.luddy.iu.edu/` homepage and returned HTML, **not** a tar file.
The corresponding new-host path returned 404. The original results ZIP link
also redirected to HTML. A 200 status alone therefore must not be accepted by
an adapter as successful dataset delivery.

The Internet Archive's public CDX metadata returned two successful historical
tar captures, including:

| Capture | Indexed MIME | Indexed compressed record length |
|---|---|---:|
| 2016-11-30 14:44:59 UTC | `application/x-tar` | 1,385,317,945 bytes |
| 2020-07-13 20:58:36 UTC | `application/x-tar` | 8,631,240,107 bytes |

CDX query used:

`https://web.archive.org/cdx/search/cdx?url=vision.soic.indiana.edu%2Fdisco_files%2FArtsQuad_dataset.tar&output=json&filter=statuscode%3A200&fl=timestamp%2Coriginal%2Cstatuscode%2Cmimetype%2Clength&limit=3`

The corresponding 2020 archived asset URL is:

`https://web.archive.org/web/20200713205836id_/http://vision.soic.indiana.edu/disco_files/ArtsQuad_dataset.tar`

A headers-only request timed out after 20 seconds. No asset body was read.
An indexed capture is therefore **a concrete recovery lead, not verified
present-day download availability or proof of complete archive contents**.
The smaller 2016 record must not be assumed complete from its length.

### Rights and adapter decision

The archived release page offers research downloads but does not state an
explicit photo redistribution license. Do not mark the photo collection CC BY
or copy it into a public demo based on download availability alone. The release
README, per-image notices and author terms must be inspected; public display,
texture redistribution and derivative model terms require separate clearance
where those terms do not answer the question.

Concrete next adapter, after resource and use conditions permit:

1. Resolve a working official or archived file; verify status, final URL,
   MIME/magic, range/resume behavior and completeness before a large transfer.
2. Keep this provider separate from Commons. Record release URL, archive
   timestamp, content hashes and unresolved rights explicitly.
3. List archive members before safe extraction; reject traversal/symlink
   escapes. Preserve original bytes and EXIF. Do not trust file extensions.
4. Recover capture dates, authors/sessions, image identifiers and camera
   reference associations. Group exposures and sessions before any split.
5. Run our own COLMAP pipeline from admitted photos; retain published Bundler
   outputs as clearly labelled reference/baseline data, not as our result.
6. Reserve independent survey cameras for validation. Do not align using all
   survey controls and then call those same controls held-out ground truth.
7. Evaluate a bounded, genuinely connected 2–3-building subset before scaling
   to all 6,514 photographs.

An 8 GB source archive plus extraction, working images, feature caches and dense
depths does not fit comfortably in the current small local disk budget. Acquire
on the approved research storage, or validate streaming/range extraction first;
do not start an uncontrolled local full download.

## 2. PhotoCity Archive — exact buildings, photo access by request

### Verified public access and source statements

- Official UW project page:
  [PhotoCity](https://grail.cs.washington.edu/projects/photocity/).
  It explicitly names the **Arts Quad at Cornell** and states roughly 50,000
  photos each of UW and Cornell campuses, with contact required to use datasets.
- Noah Snavely's [official homepage](https://www.cs.cornell.edu/~snavely/)
  links `http://www.photocitygame.com/`.
- That exact **www + HTTP** endpoint currently serves the public PhotoCity
  Archive. The no-www host did not resolve on this check. The www HTTPS endpoint
  failed hostname certificate validation; no TLS verification was disabled.
- Live [Data page](http://www.photocitygame.com/data) states approximately
  **150,000 photos total**, primarily Cornell/UW, captured **2009–2011**.
  It lists **1600-pixel maximum dimension**, original EXIF tags, model/player
  association and GPS estimates from **SfM/manual map alignment**.
- It lists Bundler files and dense PMVS clouds for approximately 100 models,
  but under “How to Get Access” explicitly says to contact Kathleen Tuite for
  photos, with geographic/model subsets available.

The available 1600 px archive images are not asserted to be full-resolution
camera originals. Preserved original EXIF does not mean preserved original
pixels. The archive GPS estimates are also not an independent survey.

### Concrete core-model boundaries

The public [model map JSON](http://www.photocitygame.com/mapObjects.js) and
individual model pages identify these Cornell models. Counts below are copied
from live model-page HTML, not inferred from clouds and not downloaded files.

| Core building | Model ID and page | Page-reported photos |
|---|---|---:|
| Morrill | [90](http://www.photocitygame.com/model/90) | 594 |
| McGraw Hall | [68](http://www.photocitygame.com/model/68) | 1,663 |
| White | [78](http://www.photocitygame.com/model/78) | 527 |
| Sibley | [92](http://www.photocitygame.com/model/92) | 670 |
| Olive Tjaden | [106](http://www.photocitygame.com/model/106) | 334 |
| Lincoln | [107](http://www.photocitygame.com/model/107) | 250 |
| Goldwin Smith | [104](http://www.photocitygame.com/model/104) | 433 |

Additional Cornell revisions/models exist, including White 233, Tjaden 218,
Goldwin Smith 240 and older McGraw 24. These are **not additional independent
datasets by default**. Models, snapshots and contributions may reuse photos.
Do not sum counts across versions as distinct captures. Public map point counts
also differ from full model-page counts; retain their field/source semantics.

The map includes Cornell zones 2, 17, 23 and 25. Zone IDs and bounding boxes help
request an actual Arts Quad subset but do not establish cross-model geometric
connectivity. PhotoCity's original gameplay encouraged multi-view coverage;
usable shared views still need to be verified after acquisition.

### What is and is not publicly downloadable

Public model-info and snapshot pages expose thumbnail and reconstruction-render
links in the public `photocity-archive` S3 namespace. The inspected snapshot
page links a small photograph, not a full-resolution archive. The model viewer
requires obsolete Flash. Neither public thumbnails nor old viewer assets are a
substitute for the maintained photo release and permission.

No public photo license or self-service original-photo bundle was found on the
inspected Data/model pages. The page explicitly asks users to contact
`kathleen.tuite@gmail.com`. **No email was sent.** External contact or obtaining
nonpublic releases requires separate authorization; it cannot be silently
counted as a completed zero-human public-data step.

If access/terms are approved, the adapter should import the maintainer's
region/model manifest and delivered files, preserve upload/player/model IDs,
group sessions and duplicates across snapshots, and label its capture epoch.
It must not enumerate guessed private object keys or scrape thumbnails into a
fake full-resolution dataset.

**Epoch warning:** 2009–2011 is a valuable modern photographic reference era,
but not a claim to represent Cornell in 2026. Milstein/Klarman-era alterations,
renovation and changing vegetation must be separated rather than optimized as
one timeless static scene.

## 3. MegaScenes — public cache, limited new core-building coverage

- [Official dataset code and access instructions](https://github.com/MegaScenes/dataset).
- [Official datasheet](https://github.com/MegaScenes/datasheet).
- Public, credential-free S3/HTTPS access is documented. Individual objects can
  be retrieved without downloading the whole dataset.
- The public category index was read in memory only (20,144,093 bytes), yielding
  431,035 category mappings. Cornell-labelled matches include Uris Library,
  Sage Chapel, the War Memorial and Ezra Cornell statue; no Cornell-labelled
  seven-core Arts Quad scene was found in this bounded category search.

Verified useful IDs and metadata:

| Scene | ID / path | Verified availability |
|---|---|---|
| Uris Library | 112856 / `112/856` | Public subcategory metadata and image-object listing |
| Sage Chapel | 036298 / `036/298` | Public subcategory metadata |

Example direct metadata URL:

`https://megascenes.s3.us-west-2.amazonaws.com/metadata/subcat/112/856/subcats.json`

The Uris graph lists McGraw Tower, Views from McGraw Tower and A.D. White
Reading Room. A public object listing under `images/112/856/` returned 38
picture-path image keys and three JSON files, with no truncation. Those keys
include historical/document imagery; they are not 38 verified modern exterior
photographs. A listing under
`reconstruct/112/856/` returned no keys. **No Uris reconstruction asset is
therefore assumed available.** No listed photo was downloaded in this check.

The datasheet explicitly states most images were downsized to maximum 1800 px
width; these are not guaranteed source originals. It also warns of duplicates
within and across scenes. This provider can improve cache/reproducibility and
possibly reveal missed contextual views, but is not a verified new seven-core
photo collection. Many files will overlap the current Commons sources.

The dataset has CC BY 4.0 terms; photos retain their own individual licenses.
An adapter must read raw metadata, match Commons source identity, compare
hashes/exposure relationships, preserve per-item licenses and mark the resized
image provenance. Existing published reconstructions are pseudo-ground truth,
not independent measurement of our geometry.

## 4. Other primary dataset pages — not Cornell data fixes

- [Photo Tourism datasets](https://phototour.cs.washington.edu/datasets/) currently
  lists Notre Dame, not Arts Quad. It specifies noncommercial use and per-image
  Creative Commons attribution requirements. It is a useful external benchmark,
  not a Cornell photo source.
- [1DSfM](https://www.cs.cornell.edu/projects/1dsfm/) lists its landmark scenes and
  separate image downloads; none of the listed scenes is Cornell Arts Quad.
- [MegaDepth](https://www.cs.cornell.edu/projects/megadepth/) provides 196 locations,
  large model/depth releases and per-image license caveats. This page alone does
  not establish a Cornell Arts Quad subset.
- Bounded public GitHub repository searches for “Arts Quad”, Cornell
  photogrammetry, Cornell 3D reconstruction and Quad6K did not find a usable
  original-photo release. The `dyhsiao/photocity` repository is a historical
  software export, not proof of an available/redistributable photo dataset.
  Public repository search is not an exhaustive survey of student work.

## Recommended acquisition order

1. **Recover and inspect the official Quad6K release metadata/README first.**
   It is the exact geographic scene with the clearest existing multi-view and
   independent camera-reference evidence. Verify actual binary delivery and
   rights before scheduling the full transfer.
2. Keep the current Commons collection running under its existing safeguards;
   add only new, admitted photographs to future immutable snapshots. Do not
   overwrite prior runs or spend more dense compute expecting absent viewpoints
   to appear.
3. If authorized, ask the PhotoCity maintainer for a seven-building Arts Quad
   subset, pixel-resolution availability, shared-view mapping, capture/session
   metadata and explicit research/public-demo derivative permissions. This is
   a coordination dependency, not an automated acquisition already completed.
4. Add a small MegaScenes metadata/cache adapter only where it contributes
   genuinely new eligible views or helps reproduce existing sources. Do not
   count mirrored copies as new observations.

The scientifically honest current status is **strong data leads identified;
no additional source acquired yet**, not “enough data confirmed for the entire
Quad.” All later feasibility decisions must be based on delivered photos,
capture/session structure, real geometric overlap and independently checked
coverage—not the impressive historical dataset totals.
