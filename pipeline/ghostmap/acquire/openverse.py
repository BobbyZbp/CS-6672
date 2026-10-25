#!/usr/bin/env python3
"""Openverse (Flickr Creative Commons) photographs as a geometry supplement.

Commons photographs of McGraw Tower and Uris Library are almost all taken from
Libe Slope and Ho Plaza, so the modern model lacks the faces seen from the Arts
Quad. Openverse indexes Flickr's Creative Commons photographs and needs no key.

Policy for this provider (stricter on licence and provenance, looser on two
points the provider cannot supply):
- licences CC BY, CC BY-SA, CC0 or public-domain mark only (no NC/ND);
- Flickr records only (Openverse's Wikimedia records duplicate Commons);
- no capture date is available (Flickr's resized copies carry no EXIF), so any
  title or creator with a historic marker (a pre-2000 year, "circa",
  "postcard", "LCCN", archives) is rejected, and every admitted record is
  labelled "capture date unknown";
- the title or tags must name the place (Cornell, Ithaca, Arts Quad, McGraw
  Tower, Uris or Olin Library, Libe Slope): search also matches descriptions of
  unrelated photographs (the McGraw-Hill buildings in New York, for example);
- Openverse serves 1024 px copies, so the short-side minimum is 640 px;
- near-duplicates of photographs already downloaded from Commons (dHash
  Hamming distance <= 6) and exact byte duplicates are skipped.
Admitted images are used only to train geometry of buildings unchanged since
the 1890s; they never enter a held-out split.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from ghostmap.acquire.commons import difference_hash
from ghostmap.paths import ROOT

API = 'https://api.openverse.org/v1/images/'
AGENT = 'GhostMap-Research/0.3 (Cornell Arts Quad; public academic imagery)'
OUT = ROOT / 'data/openverse'
QUERIES = [('McGraw Tower', 'mcgraw-tower'), ('Cornell clock tower', 'mcgraw-tower'), ('Uris Library Cornell', 'uris'),
           ('Cornell library tower', 'uris'), ('Cornell Arts Quad', None), ('Arts Quadrangle Cornell', None),
           ('Olin Library Cornell', 'olin')]
LICENCES = {'by': 'CC BY', 'by-sa': 'CC BY-SA', 'cc0': 'CC0', 'pdm': 'Public domain'}
HISTORIC = re.compile(r'LCCN|postcard|circa|\bc\.\s*1[89]\d\d|(?<!\d)1[89]\d\d(?!\d)|stereograph|lithograph|library of congress|archives?\b|historic|kheel center', re.I)
PLACE = re.compile(r'cornell|ithaca|arts\s*quad|mcgraw\s*tower|uris\s*library|olin\s*library|libe\s*slope', re.I)
MIN_SHORT_SIDE = 640
NEAR_DUPLICATE_HAMMING = 6


def api(params, cache):
    key = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()
    path = cache / (key + '.json')
    if path.exists(): return json.loads(path.read_text())
    request = urllib.request.Request(API + '?' + urllib.parse.urlencode(params), headers={'User-Agent': AGENT})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=40) as response: payload = json.load(response)
            path.write_text(json.dumps(payload) + '\n'); time.sleep(2.0)
            return payload
        except urllib.error.HTTPError as error:
            if error.code not in (429, 500, 502, 503) or attempt == 4: raise
            time.sleep(30 * (attempt + 1))
    raise RuntimeError('Openverse retries exhausted')


def admission(row):
    if row.get('source') != 'flickr': return False, 'not a Flickr record (Wikimedia records duplicate Commons)'
    if row.get('license') not in LICENCES: return False, 'licence outside CC BY / BY-SA / CC0 / public domain'
    text = ' '.join(str(row.get(k) or '') for k in ('title', 'creator'))
    if HISTORIC.search(text): return False, 'historic marker in title or creator; capture epoch cannot be checked'
    named = ' '.join([str(row.get('title') or '')] + [str(t.get('name', '')) for t in row.get('tags') or []])
    if not PLACE.search(named): return False, 'title and tags do not name the place'
    if min(row.get('width') or 0, row.get('height') or 0) < MIN_SHORT_SIDE: return False, 'short side below 640 px'
    return True, 'admitted as geometry supplement; capture date unknown'


def existing_hashes(directory):
    hashes = []
    for path in Path(directory).glob('*.jpg'):
        try: hashes.append(int(difference_hash(path), 16))
        except OSError: pass
    return hashes


def build(output=OUT, commons_images=ROOT / 'artifacts/artsquad_modern/images'):
    output = Path(output); cache = output / 'api-cache'; originals = output / 'originals'
    cache.mkdir(parents=True, exist_ok=True); originals.mkdir(exist_ok=True)
    found = {}
    for query, target in QUERIES:
        page = 1
        while True:
            d = api({'q': query, 'license': ','.join(LICENCES), 'source': 'flickr', 'page_size': 20, 'page': page}, cache)
            for row in d.get('results', []):
                entry = found.setdefault(row['id'], {'row': row, 'queries': [], 'targets': []})
                if query not in entry['queries']: entry['queries'].append(query)
                if target and target not in entry['targets']: entry['targets'].append(target)
            if page >= min(d.get('page_count') or 1, 10): break
            page += 1
    commons = existing_hashes(commons_images)
    records, rejected, seen_sha, seen_dhash = [], [], {}, []
    for uid, entry in sorted(found.items()):
        row = entry['row']; ok, reason = admission(row)
        if not ok: rejected.append({'id': uid, 'title': row.get('title'), 'reason': reason}); continue
        stem = re.sub(r'[^A-Za-z0-9._-]+', '_', row.get('title') or 'untitled').strip('_.')[:80] or 'untitled'
        name = f'openverse-{uid[:12]}_{stem}.jpg'; path = originals / name
        try:
            if not path.exists():
                request = urllib.request.Request(row['url'], headers={'User-Agent': AGENT})
                with urllib.request.urlopen(request, timeout=60) as response: path.write_bytes(response.read())
                time.sleep(0.5)
            with Image.open(path) as im: im.verify()
        except Exception as error:
            rejected.append({'id': uid, 'title': row.get('title'), 'reason': 'download / decode error: ' + str(error)}); continue
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        dh = int(difference_hash(path), 16)
        if sha in seen_sha:
            rejected.append({'id': uid, 'title': row.get('title'), 'reason': 'exact byte duplicate of ' + seen_sha[sha]}); continue
        near = min((bin(dh ^ h).count('1') for h in commons + seen_dhash), default=64)
        if near <= NEAR_DUPLICATE_HAMMING:
            rejected.append({'id': uid, 'title': row.get('title'), 'reason': f'near-duplicate of an existing photograph (dHash distance {near})'}); continue
        seen_sha[sha] = uid; seen_dhash.append(dh)
        with Image.open(path) as im: size = list(im.size)
        licence = LICENCES[row['license']] + (' ' + row['license_version'] if row.get('license_version') and row['license'] in ('by', 'by-sa') else '')
        records.append({'pageid': 'openverse-' + uid, 'provider': 'openverse/flickr', 'title': row.get('title') or '',
                        'filename': 'modern__' + name, 'original_filename': name, 'original_url': row['url'],
                        'source_url': row.get('foreign_landing_url'), 'capture_date_asserted': '',
                        'license': licence, 'license_url': row.get('license_url'), 'artist': row.get('creator') or '',
                        'credit': row.get('attribution') or '', 'discovery': {'sources': ['openverse:' + q for q in entry['queries']], 'targets': entry['targets']},
                        'sha256_original': sha, 'original_size': size, 'dhash64': f'{dh:016x}', 'exif': {},
                        'admission': reason})
        print('ADMITTED', len(records), name, size, flush=True)
    manifest = {'schema_version': 1, 'created_utc': datetime.now(timezone.utc).isoformat(), 'provider': 'Openverse (Flickr CC)',
                'api': API, 'queries': QUERIES, 'policy': __doc__, 'candidates': len(found), 'images': records, 'rejected': rejected}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + '\n')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUT)
    manifest = build(parser.parse_args().output)
    from collections import Counter
    print(manifest['candidates'], 'candidates,', len(manifest['images']), 'admitted;', Counter(r['reason'].split(';')[0].split('(')[0].strip() for r in manifest['rejected']).most_common())


if __name__ == '__main__': main()
