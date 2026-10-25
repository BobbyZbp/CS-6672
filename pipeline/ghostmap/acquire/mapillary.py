#!/usr/bin/env python3
"""Mapillary street-level photographs facing McGraw Tower from the Arts Quad.

Selection comes from the coverage probe (acquire/mapillary_probe.py): images
within 400 m of the tower, standing in the Arts Quad sector (0-110 degrees from
the tower) and pointing within 60 degrees of it. Frames of one walk are nearly
identical, so each sequence is thinned to one frame per SPACING_M metres.
Each kept image's metadata is read with the user token saved by
acquire/mapillary_login.py and its 2048 px version is downloaded. Mapillary
imagery is CC BY-SA 4.0; author, capture time and image ID are recorded. The
output manifest has the same record shape as the Openverse supplement.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import math
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from ghostmap.acquire.commons import difference_hash
from ghostmap.acquire.mapillary_probe import distance_m, tower_latlon, user_token
from ghostmap.paths import ROOT

OUT = ROOT / 'data/mapillary'
FACING_DEG = 60.0
SPACING_M = 4.0
MAX_IMAGES = 120
FIELDS = 'id,captured_at,compass_angle,computed_compass_angle,computed_geometry,geometry,camera_type,make,model,width,height,creator,sequence,thumb_2048_url'


def select(probe_report):
    rows = [r for r in probe_report['records']
            if r['bearing_from_tower_deg'] <= 110 and r['camera_heading_deg'] is not None
            and abs(((r['camera_heading_deg'] - (r['bearing_from_tower_deg'] + 180)) + 180) % 360 - 180) <= FACING_DEG]
    return rows


def metadata(image_id, token):
    url = f'https://graph.mapillary.com/{image_id}?' + urllib.parse.urlencode({'fields': FIELDS})
    request = urllib.request.Request(url, headers={'Authorization': 'OAuth ' + token})
    with urllib.request.urlopen(request, timeout=60) as response: return json.load(response)


def thin(items, spacing=SPACING_M):
    """Keep one frame per `spacing` metres along each sequence (in capture order)."""
    kept, by_sequence = [], {}
    for item in sorted(items, key=lambda m: (m['sequence'], m['captured_at'])):
        lon, lat = (item.get('computed_geometry') or item['geometry'])['coordinates']
        last = by_sequence.get(item['sequence'])
        if last is None or distance_m(last[0], last[1], lat, lon) >= spacing:
            kept.append(item); by_sequence[item['sequence']] = (lat, lon)
    return kept


def build(output=OUT):
    token = user_token()
    if not token: raise SystemExit('No user token: run  PYTHONPATH=pipeline .venv/bin/python -m ghostmap.acquire.mapillary_login')
    probe_path = sorted(glob.glob(str(ROOT / 'artifacts/provider-probes/mapillary-tower-*.json')))[-1]
    candidates = select(json.loads(Path(probe_path).read_text()))
    output = Path(output); originals = output / 'originals'; originals.mkdir(parents=True, exist_ok=True)
    cache = output / 'metadata'; cache.mkdir(exist_ok=True)
    metas = []
    for row in candidates:
        path = cache / f"{row['id']}.json"
        if not path.exists():
            path.write_text(json.dumps(metadata(row['id'], token)) + '\n'); time.sleep(0.2)
        meta = json.loads(path.read_text())
        if meta.get('thumb_2048_url') and meta.get('sequence'): metas.append(meta)
    kept = thin(metas)[:MAX_IMAGES]
    lat_t, lon_t = tower_latlon()
    records = []
    for meta in kept:
        name = f"mapillary-{meta['id']}.jpg"; path = originals / name
        if not path.exists():
            urllib.request.urlretrieve(meta['thumb_2048_url'], path); time.sleep(0.2)
        with Image.open(path) as im: im.verify()
        with Image.open(path) as im: size = list(im.size)
        lon, lat = (meta.get('computed_geometry') or meta['geometry'])['coordinates']
        creator = (meta.get('creator') or {}).get('username') or 'unknown'
        captured = datetime.fromtimestamp(meta['captured_at'] / 1000, timezone.utc)
        records.append({'pageid': 'mapillary-' + meta['id'], 'provider': 'mapillary', 'title': f"Mapillary {meta['id']} ({creator}, {captured.date()})",
                        'filename': 'modern__' + name, 'original_filename': name, 'original_url': meta['thumb_2048_url'].split('?')[0],
                        'source_url': f"https://www.mapillary.com/app/?pKey={meta['id']}", 'capture_date_asserted': captured.isoformat(),
                        'license': 'CC BY-SA 4.0', 'license_url': 'https://creativecommons.org/licenses/by-sa/4.0/', 'artist': creator,
                        'credit': f'{creator} via Mapillary, CC BY-SA 4.0', 'session': meta['sequence'],
                        'discovery': {'sources': ['mapillary: Arts Quad sector facing McGraw Tower'], 'targets': ['mcgraw-tower']},
                        'sha256_original': hashlib.sha256(path.read_bytes()).hexdigest(), 'original_size': size,
                        'dhash64': difference_hash(path), 'exif': {'make': meta.get('make'), 'model': meta.get('model')},
                        'mapillary': {'compass_angle': meta.get('computed_compass_angle', meta.get('compass_angle')),
                                      'latlon': [lat, lon], 'distance_to_tower_m': round(distance_m(lat_t, lon_t, lat, lon), 1),
                                      'camera_type': meta.get('camera_type'), 'original_size': [meta.get('width'), meta.get('height')]},
                        'admission': 'Mapillary geometry supplement; position and heading are Mapillary estimates, not used by the reconstruction'})
        print('KEPT', len(records), name, size, flush=True)
    manifest = {'schema_version': 1, 'created_utc': datetime.now(timezone.utc).isoformat(), 'provider': 'Mapillary', 'probe': probe_path,
                'policy': __doc__, 'candidates_facing': len(candidates), 'metadata_ok': len(metas), 'kept_after_thinning': len(records),
                'images': records, 'rejected': []}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=1) + '\n')
    return manifest


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    m = build()
    print(m['candidates_facing'], 'facing candidates,', m['metadata_ok'], 'with metadata,', m['kept_after_thinning'], 'kept after thinning')


if __name__ == '__main__': main()
