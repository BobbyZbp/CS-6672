#!/usr/bin/env python3
"""Package the presentation website for offline use: one zip that runs on any laptop with Python 3.

The bundle holds the demo page (`timemachine.html` and its script and stylesheet), the slide deck
(`presentation.html`) with its stills under `assets/presentation/`, the vendored three.js and Gaussian-splat
modules with their licences, and everything under `assets/timemachine/`. Each file referenced by `scene.json` must
exist, or packaging stops. A small `serve.py` serves the folder on http://127.0.0.1:8080 (ES modules and
binary assets need an HTTP server; opening the HTML file directly does not work). A manifest records
every file's size and SHA-256.

Usage: PYTHONPATH=pipeline python -m ghostmap.package.presentation_bundle [--output artifacts/presentation]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from ghostmap.paths import ROOT

DIST = ROOT / 'dist'
OUTPUT = ROOT / 'artifacts/presentation'
PAGES = ['timemachine.html', 'timemachine.js', 'ghostmap.css', 'presentation.html']
ASSET_DIRS = ['assets/timemachine', 'assets/presentation']
VENDOR = ['vendor/three.module.js', 'vendor/OrbitControls.js', 'vendor/LICENSE.three', 'vendor/gaussian-splats-3d.module.js', 'vendor/LICENSE.gaussian-splats-3d']

SERVE = '''#!/usr/bin/env python3
"""Serve this folder at http://127.0.0.1:8080 (the demo needs HTTP; opening the files directly does not work)."""
import functools, http.server, mimetypes, os, sys, webbrowser
mimetypes.add_type('text/javascript', '.js'); mimetypes.add_type('application/octet-stream', '.splat')
port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=os.path.dirname(os.path.abspath(__file__)))
with http.server.ThreadingHTTPServer(('127.0.0.1', port), handler) as httpd:
    print(f'GhostMap demo: http://127.0.0.1:{port}/  (slides: /presentation.html)  Ctrl+C to stop')
    try: webbrowser.open(f'http://127.0.0.1:{port}/')
    except Exception: pass
    httpd.serve_forever()
'''

INDEX = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="0;url=timemachine.html"><title>GhostMap</title></head>
<body><p><a href="timemachine.html">GhostMap live demo</a> · <a href="presentation.html">Slides</a></p></body></html>
'''

README = '''GhostMap: Cornell rebuilt from internet photographs inside the world's own 3D model.

Run:   python3 serve.py        (then the browser opens http://127.0.0.1:8080/)
Demo:  timemachine.html        Slides: presentation.html (arrow keys; F for full screen)
Needs: Python 3 and a recent Chrome, Edge, Firefox or Safari with WebGL 2. No internet connection.
Data:  USGS 3DEP lidar (public domain), New York State orthoimagery (public), OpenStreetMap footprints (ODbL),
       photographs from Wikimedia Commons and Flickr via Openverse under their own licences (credited on the page).
'''


def referenced(scene, base='assets/timemachine/'):
    """Every asset path a scene.json refers to (keys ending in _url, and the photo / crop paths)."""
    out = set()
    def walk(v, key=''):
        if isinstance(v, dict):
            for k, x in v.items(): walk(x, k)
        elif isinstance(v, list):
            for x in v: walk(x, key)
        elif isinstance(v, str) and not v.startswith(('http:', 'https:')) and (key.endswith('_url') or key == 'url' or (key == 'photo' and '/' in v)):
            out.add(base + v)   # a 'photo' without a folder is a photograph's identifier, not a file
    walk(scene)
    return out


def package(dist=DIST, output=OUTPUT):
    dist, output = Path(dist), Path(output); output.mkdir(parents=True, exist_ok=True)
    scene = json.loads((dist / 'assets/timemachine/scene.json').read_text())
    # the demo's data, and the stills the slide deck shows (dist/assets/presentation, written by qa/record_tour.py)
    files = set(PAGES + VENDOR) | {p.relative_to(dist).as_posix() for folder in ASSET_DIRS for p in (dist / folder).rglob('*') if p.is_file()}
    missing = sorted(p for p in (referenced(scene) | set(PAGES + VENDOR)) if not (dist / p).exists())
    if missing: raise SystemExit('missing files referenced by the demo: ' + ', '.join(missing[:12]))
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')
    zpath = output / f'ghostmap-demo-{stamp}.zip'
    manifest = []
    with zipfile.ZipFile(zpath, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for rel in sorted(files):
            data = (dist / rel).read_bytes(); manifest.append({'path': rel, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
            z.writestr(f'ghostmap-demo/{rel}', data)
        z.writestr('ghostmap-demo/serve.py', SERVE); z.writestr('ghostmap-demo/index.html', INDEX); z.writestr('ghostmap-demo/README.txt', README)
        z.writestr('ghostmap-demo/manifest.json', json.dumps({'created_utc': datetime.now(timezone.utc).isoformat(), 'scene_generated_utc': scene.get('generated_utc'), 'files': manifest}, indent=1))
    report = {'zip': str(zpath), 'files': len(manifest) + 4, 'bytes': zpath.stat().st_size, 'scene_generated_utc': scene.get('generated_utc')}
    (output / 'bundle-report.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--dist', type=Path, default=DIST)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    print(json.dumps(package(args.dist, args.output), indent=2))


if __name__ == '__main__': main()
