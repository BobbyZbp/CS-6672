#!/usr/bin/env python3
"""Keep research-only photo experiments outside the public-source dist bundle.

This creates a local artifact directory, not a server, public deployment or
rights grant. Use the loopback-only serve_artsquad_demo.py launcher separately.
"""
import argparse
import json
import shutil
from pathlib import Path

from ghostmap.web.site import ROOT, package
from ghostmap.sfm.learned import sha256, write_json

STATIC_FILES = ('artsquad.html', 'artsquad.js', 'artsquad.css', 'artsquad-evidence.css',
                'vendor/three.module.js', 'vendor/OrbitControls.js', 'vendor/OBJLoader.js',
                'vendor/MTLLoader.js', 'vendor/LICENSE.three', 'vendor/README.md')


def build(snapshot, run):
    run = Path(run).resolve()
    report = json.loads((run / 'report.json').read_text())
    identifier = report['run_id']
    if not identifier.isalnum(): raise ValueError('Unsafe native run ID')
    destination = ROOT / 'artifacts/local_previews' / identifier
    manifest = package(Path(snapshot).resolve(), run, destination, local_research_only=True)
    for name in STATIC_FILES:
        source = ROOT / 'dist' / name
        if source.is_symlink() or not source.is_file(): raise ValueError('Missing or linked viewer source: ' + name)
        target = destination / name; target.parent.mkdir(parents=True, exist_ok=True)
        if name == 'artsquad.html':
            text = source.read_text().replace('CORNELL UNIVERSITY · MODERN REFERENCE SCENE', 'CORNELL ARTS QUAD · LOCAL RESEARCH-ONLY INPUTS')
            text = text.replace('<a href="surface-lab.html">Earlier experiments ↗</a>', '<a href="http://127.0.0.1:8080/artsquad.html">Public-source workbench ↗</a>')
            text = text.replace('Only recovered observations belong in this atlas. Missing geometry stays missing.', 'Local research-only photographs and recovered observations. Redistribution rights are unresolved; missing geometry stays missing.')
            target.write_text(text)
        else: shutil.copy2(source, target)
    (destination / 'index.html').write_text('<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=artsquad.html"><title>Local research-only GhostMap preview</title><a href="artsquad.html">Open local research preview</a>')
    write_json(destination / 'local-preview-manifest.json', {'scope': 'private-research-only', 'run_id': identifier,
               'scene_sha256': sha256(manifest), 'public_redistribution_permitted': False,
               'static_files_sha256': {name: sha256(destination / name) for name in STATIC_FILES},
               'note': 'No server or public deployment started; bind loopback only. Not D0/D1 or a rights clearance.'})
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', required=True, type=Path)
    parser.add_argument('--run', required=True, type=Path)
    args = parser.parse_args()
    print(build(args.snapshot, args.run))
