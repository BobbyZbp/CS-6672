# GhostMap local demonstration and real-browser recording

The current presentation is a **diagnostic checkpoint, not accepted D0 or D1**.
A source-linked Goldwin fragment is not a complete building. Different COLMAP
components do not share a proven coordinate system and must not be presented as
a connected campus. The seven-building modern objective is unchanged.

## Open and inspect the actual package

Reuse the existing local server at <http://127.0.0.1:8080/artsquad.html>. The link
is loopback-only, not a verified HTTPS deployment. First select the computed
surface, inspect its source photograph, switch recovered cameras, and click an
actual facet for texture provenance and estimated stereo visibility. These
operations expose evidence; they do not certify accuracy or independence of
recorded source groups. Missing areas remain visibly missing.

## Repeatable 54-second clip

Once the final scene package is stable, run from the project root:

```sh
PLAYWRIGHT_BROWSERS_PATH=/home/bobby/CS6672/.cache/playwright .venv/bin/python pipeline/record_artsquad_demo.py
```

The recorder uses already-installed Chromium and the Playwright VP9 FFmpeg
runtime. It installs nothing and submits no remote work. Software WebGL checks
functionality, not real-device 30 FPS or cold-cache network performance. The
default requests reduced motion and does not run an automatic orbit; explicitly
add `--allow-motion` only when that motion is wanted for the recording.

Each attempt goes into a new directory beneath
`artifacts/demo/<run-id>/<scene-hash-prefix>/`. Existing recordings and browser
QA artifacts are preserved. Output includes:

- `ghostmap-diagnostic-tour.webm`: 1440 × 1080 actual browser video, 54 seconds.
- `recording-report.json`: exact scene/viewer hashes, actual duration, selected
  real facet/source cameras, chapter timing, errors and explicit non-claims.
- `scene-manifest.json`: the exact manifest used for that clip.
- Nine real browser chapter screenshots and a preserved untrimmed raw capture.
- `encode.log`: the existing VP9 runtime's trimming/re-encoding output.

No MP4/H.264 encoder is currently installed, so WebM is the deliverable; the
recorder does not silently install another dependency or claim an MP4 exists.
To add a successful recording to the existing local preview, append
`--bundle-local-preview` when recording, or run:

```sh
.venv/bin/python pipeline/record_artsquad_demo.py --bundle-existing artifacts/demo/<run-id>/<scene-hash-prefix>/<attempt-id>
```

Then open <http://127.0.0.1:8080/demo-reel.html>. That page exposes the actual
WebM, chapter seeking, screenshots, exact recorded scene and run hashes. It
detects when the current live atlas selects a different manifest and labels the
clip an archived checkpoint. Local bundling does not publish to the internet.
For the existing static server, the reel verifies the small WebM's SHA-256 and
loads those exact bytes into a browser Blob: native seeking then works even
without HTTP byte-range support. This changes transport only, not video frames.

Only actual captured frames are trimmed and encoded: no generated frames,
geometry completion, camera blending, joined coordinate systems or frame
interpolation. A visible text-only recording caption discloses the current
research status throughout the clip.
The trim boundary is found in decoded raw frames, rather than assuming that
Playwright's asynchronously captured video starts at the Python wall clock.
Small actual-frame probes remain with the recording evidence.

The sequence shows the actual surface, calibrated source-camera changes,
wireframe, one genuine picked facet and its source records, free component
inspection, another **separate** component, pipeline records, and pending
milestones. A recording fails rather than claiming success if a requested
artifact is absent, actual facet selection fails, the scene changes during the
tour, browser/HTTP errors appear, or the resulting duration is not 45–60 seconds.

## Live presentation fallback

Keep the WebM available locally if live WebGL is slow. State what is and is not
reconstructed before showing it. Do not describe the recording as the D1 film:
the accepted multi-building demo still requires genuine core-building
connectivity, environment support, held-out checks, rights review, real-device
performance and a verified HTTPS preview. A successful clip is not evidence for
those missing requirements.

Public redistribution of photographs/video needs the project's rights review.
This recorder creates local research artifacts only and never publishes them.

## Portable local draft ZIP

After freezing the final scene and recording that exact manifest, build:

```sh
.venv/bin/python pipeline/package_artsquad_demo.py
```

The result is a content-versioned ZIP beneath `artifacts/demo-packages/`, not a
recursive copy of `dist/`. It includes only the current manifest's dependencies,
the actual OBJ/MTL/textures, calibrated photos, sparse/evidence reports, native
COLMAP and source-only ZIPs, the exact verified recording, viewer modules,
Third-party MIT license, runbook, attribution records and a hash manifest.
Unknown/restricted photograph rights, symlinks, path escapes, missing assets,
inconsistent texture-camera provenance, a changed scene, or an older unmatched
recording cause packaging to fail. Original pools, stale experiments, caches,
weights, secrets, unknown-rights provider assets and raw video preroll are not
included. Its small navigation-only change from “Earlier experiments” to the
included recording is explicitly recorded in the bundle manifest; geometry,
camera data and milestone states are unchanged.

Extract into a new folder, then:

```sh
python serve_artsquad_demo.py --verify-only
python serve_artsquad_demo.py
```

Open <http://127.0.0.1:8082/artsquad.html> or
<http://127.0.0.1:8082/demo-reel.html>. The stdlib launcher verifies every bundled
file, binds **127.0.0.1 only**, disables listings and serves only its explicit
allowlist. It installs nothing and never kills an existing server. If 8082 is
occupied, it reports the conflict; choose another unprivileged port with
`--port 8083`. The existing workspace preview on 8080 is untouched. Stop only
this launcher with Ctrl-C. This is a local research draft package, not a public
release or passed D1; keep every photograph's attribution/license conditions.
