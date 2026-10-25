#!/usr/bin/env python3
"""OpenStreetMap building footprints around the Arts Quad, in UTM zone 18N.

Footprints give the wall positions that airborne lidar barely samples. The
query, response hash and attribution are stored next to the output. OSM data
is (c) OpenStreetMap contributors, available under the ODbL.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from ghostmap.anchor.lidar import AGENT, UTM, QUAD_CENTRE_LATLON, HALF_SIZE_M
from ghostmap.paths import ROOT

OVERPASS = 'https://overpass-api.de/api/interpreter'


def bbox_latlon(centre=QUAD_CENTRE_LATLON, half=HALF_SIZE_M):
    dlat = half / 111_320.0
    import math
    dlon = half / (111_320.0 * math.cos(math.radians(centre[0])))
    return (centre[0] - dlat, centre[1] - dlon, centre[0] + dlat, centre[1] + dlon)


def to_utm_polygons(payload):
    """Closed building ways and multipolygon outer rings as UTM rings."""
    from pyproj import Transformer
    to_utm = Transformer.from_crs('EPSG:4326', UTM, always_xy=True)
    nodes = {e['id']: (e['lon'], e['lat']) for e in payload['elements'] if e['type'] == 'node'}
    ways = {e['id']: e for e in payload['elements'] if e['type'] == 'way'}
    buildings = []

    def ring(way):
        coords = [nodes[i] for i in way['nodes'] if i in nodes]
        if len(coords) < 4 or way['nodes'][0] != way['nodes'][-1]: return None
        e, n = to_utm.transform([c[0] for c in coords], [c[1] for c in coords])
        return [[float(a), float(b)] for a, b in zip(e, n)]

    for way in ways.values():
        tags = way.get('tags', {})
        if 'building' not in tags and 'building:part' not in tags: continue
        r = ring(way)
        if r: buildings.append({'osm': f"way/{way['id']}", 'name': tags.get('name', ''), 'tags': tags, 'ring': r})
    for rel in (e for e in payload['elements'] if e['type'] == 'relation'):
        tags = rel.get('tags', {})
        if 'building' not in tags: continue
        for member in rel.get('members', []):
            if member.get('role') == 'outer' and member.get('ref') in ways:
                r = ring(ways[member['ref']])
                if r: buildings.append({'osm': f"relation/{rel['id']}", 'name': tags.get('name', ''), 'tags': tags, 'ring': r})
    return buildings


def build(output=ROOT / 'data/footprints'):
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    s, w, n, e = bbox_latlon()
    query = f'[out:json][timeout:60];(way["building"]({s},{w},{n},{e});way["building:part"]({s},{w},{n},{e});relation["building"]({s},{w},{n},{e}););(._;>;);out body;'
    raw = output / 'overpass-response.json'
    if not raw.exists():
        request = urllib.request.Request(OVERPASS, data=urllib.parse.urlencode({'data': query}).encode(), headers={'User-Agent': AGENT})
        with urllib.request.urlopen(request, timeout=120) as response: raw.write_bytes(response.read())
    payload = json.loads(raw.read_text())
    buildings = to_utm_polygons(payload)
    result = {'schema_version': 1, 'created_utc': datetime.now(timezone.utc).isoformat(), 'crs': UTM,
              'source': OVERPASS, 'query': query, 'response_sha256': hashlib.sha256(raw.read_bytes()).hexdigest(),
              'attribution': '(c) OpenStreetMap contributors, ODbL 1.0', 'buildings': buildings}
    (output / 'buildings-utm18n.json').write_text(json.dumps(result, indent=1) + '\n')
    return result


def named(buildings, *names):
    """First footprint whose name contains any of the given names (case-insensitive)."""
    for name in names:
        for b in buildings:
            if name.lower() in b['name'].lower(): return b
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'data/footprints')
    result = build(parser.parse_args().output)
    print(len(result['buildings']), 'footprints:', sorted({b['name'] for b in result['buildings'] if b['name']}))


if __name__ == '__main__': main()
