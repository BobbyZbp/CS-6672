#!/usr/bin/env python3
"""The demo's web server: `dist/` as static files, plus live placement of a photograph dropped onto the page.

`python3 -m http.server --directory dist` serves the page as well; this server adds `POST /api/locate`, which
places the photograph in the request body with `anchor/locate.py` (GPU) in the page's fragment and answers with
what the page shows of it (`web/timemachine_scene.py`, `located_entry`): the certificate, the pose in the scene's
frame, the focal length. Dropped photographs and their reports are kept under `artifacts/live-photos/`, outside
`dist/`, so they never enter the offline bundle; the page fetches them from `assets/timemachine/located-live/`.

Usage: PYTHONPATH=pipeline python -m ghostmap.web.demo_server [--port 8080] [--run <run>] [--anchor 0]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import threading
import time
import urllib.parse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np

from ghostmap.paths import ROOT

DIST = ROOT / 'dist'
LIVE = ROOT / 'artifacts/live-photos'
LIVE_URL = '/assets/timemachine/located-live/'
MAX_BYTES = 40 * 1024 * 1024
IDLE_S = 300   # seconds without a placement before the warm-up placement runs again


def keep_models_loaded():
    """hloc builds SuperPoint, NetVLAD and LightGlue afresh on every call (seconds each); in a server that keeps
    running, each is built once and reused (same weights, same configuration every call)."""
    from hloc import extract_features, match_features
    cache = {}
    def cached(load):
        def dynamic_load(module, name):
            Model = load(module, name)
            def build(conf):
                key = (Model, json.dumps(conf, sort_keys=True, default=str))
                if key not in cache: cache[key] = Model(conf)
                return cache[key]
            return build
        return dynamic_load
    extract_features.dynamic_load = cached(extract_features.dynamic_load)
    match_features.dynamic_load = cached(match_features.dynamic_load)


class Placer:
    """The fragment, loaded once; one placement at a time on the GPU."""

    def __init__(self, run, anchor):
        from ghostmap.anchor.locate import Reference
        self.ref = Reference(run, anchor); self.lock = threading.Lock()
        keep_models_loaded()
        scene = json.loads((DIST / 'assets/timemachine/scene.json').read_text())
        self.shift = self.ref.origin - np.asarray(scene['frame']['origin_utm18n'])   # the anchor's local frame -> the scene's
        # Warm up (the networks load and the GPU compiles its kernels on the first placement, about 25 s), so the first
        # photograph dropped during the talk is placed in seconds.
        t0 = time.time(); self.warm()
        print(f'warmed up in {time.time() - t0:.0f} s', flush=True)
        # Left idle, the GPU and the memory go cold (a first placement after a quiet hour took 11 s instead of 1-2 s):
        # the warm-up placement runs again whenever nothing was placed for a few minutes.
        threading.Thread(target=self.keep_warm, daemon=True).start()

    def warm(self):
        from ghostmap.anchor.locate import locate
        with self.lock:
            locate(self.ref.run, [self.ref.run / 'images' / self.ref.names[0]], self.ref.anchor, render=False, ref=self.ref, out_root=LIVE / 'warm-up')
            self.last = time.time()

    def keep_warm(self, idle_s=IDLE_S):
        while True:
            time.sleep(30)
            if time.time() - self.last > idle_s:
                try: self.warm()
                except Exception as error: print(f'keeping warm failed: {error}', flush=True)

    def place(self, data, filename):
        from PIL import Image
        from ghostmap.anchor.locate import locate
        from ghostmap.web.timemachine_scene import PROJECT_PX, located_entry, thumbnail
        stem = hashlib.sha256(data).hexdigest()[:10] + '-' + (re.sub(r'[^A-Za-z0-9._-]+', '_', Path(filename).stem)[:60] or 'photo')
        LIVE.mkdir(parents=True, exist_ok=True)
        src = LIVE / (stem + '.jpg')
        with open(src, 'wb') as f: f.write(data)
        with Image.open(src) as im: im.convert('RGB').save(src, quality=95)   # whatever came in, a plain JPEG goes on
        shown = LIVE / (stem + '-shown.jpg'); thumbnail(src, shown, PROJECT_PX)
        with self.lock:
            t0 = time.time(); report = locate(self.ref.run, [src], self.ref.anchor, render=False, ref=self.ref, out_root=LIVE / 'reports')[src.name]
            self.last = time.time()
        with Image.open(src) as a, Image.open(shown) as b: sizes = (a.size, b.size)
        entry = located_entry(report, self.shift, 'located-live/' + shown.name, *sizes)
        entry.update({'title': filename, 'live': True, 'seconds': round(time.time() - t0, 1)})
        return entry


class Handler(SimpleHTTPRequestHandler):
    placer = None

    def translate_path(self, path):
        clean = urllib.parse.urlparse(path).path
        if clean.startswith(LIVE_URL): return str(LIVE / Path(urllib.parse.unquote(clean[len(LIVE_URL):])).name)
        return super().translate_path(path)

    def do_POST(self):
        if urllib.parse.urlparse(self.path).path.rstrip('/').endswith('/api/locate'):
            size = int(self.headers.get('Content-Length') or 0)
            if not 0 < size <= MAX_BYTES: return self.send_error(413, 'a photograph up to 40 MB')
            data = self.rfile.read(size); name = urllib.parse.unquote(self.headers.get('X-Filename') or 'photo.jpg')
            try:
                body = json.dumps(self.placer.place(data, name)).encode(); code = 200
            except Exception as error:   # a photograph that cannot be read is answered, not fatal to the server
                body = json.dumps({'error': f'{type(error).__name__}: {error}'}).encode(); code = 422
            self.send_response(code); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(body))); self.end_headers()
            self.wfile.write(body); return
        self.send_error(404)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--run', type=Path, default=ROOT / 'artifacts/artsquad_modern/runs/ce2e2544cf854945f0c7')
    parser.add_argument('--anchor', default='0')
    args = parser.parse_args()
    Handler.placer = Placer(args.run, args.anchor)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), partial(Handler, directory=str(DIST)))
    print(f'GhostMap demo on http://127.0.0.1:{args.port}/timemachine.html (live placement at /api/locate)', flush=True)
    server.serve_forever()


if __name__ == '__main__': main()
