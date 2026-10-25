#!/usr/bin/env python3
"""Count Mapillary street-level images around McGraw Tower, by direction.

Read-only probe: queries the Mapillary Graph API (v4) for images within about
250 m of the tower, and for each reports where it stands relative to the tower
(bearing, 0 = north) and whether its camera points at the tower. The question
is whether any coverage exists in the Arts Quad sector (0-110 degrees), from
which every Boardman postcard was taken. No image is downloaded.

Needs a free Mapillary access token in .secrets/mapillary.env
(MAPILLARY_TOKEN=MLY|...) or the MAPILLARY_TOKEN environment variable.
Mapillary imagery is licensed CC BY-SA 4.0.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from ghostmap.paths import ROOT

API = 'https://graph.mapillary.com/images'
FIELDS = 'id,captured_at,compass_angle,computed_compass_angle,geometry,computed_geometry,camera_type,sequence,creator,width,height'
ARTS_QUAD_SECTOR = (0.0, 110.0)
FACING_TOLERANCE_DEG = 40.0


def token():
    if os.environ.get('MAPILLARY_TOKEN'): return os.environ['MAPILLARY_TOKEN'].strip()
    path = ROOT / '.secrets/mapillary.env'
    for line in path.read_text().splitlines() if path.exists() else []:
        if line.strip().startswith('MAPILLARY_TOKEN='): return line.split('=', 1)[1].strip()
    raise SystemExit('No token: put MAPILLARY_TOKEN=MLY|... in .secrets/mapillary.env')


def tower_latlon():
    """McGraw Tower footprint centroid from the OSM footprints, as WGS84."""
    from pyproj import Transformer
    from shapely.geometry import Polygon
    from ghostmap.anchor.footprints import named
    buildings = json.loads((ROOT / 'data/footprints/buildings-utm18n.json').read_text())['buildings']
    e, n = Polygon(named(buildings, 'McGraw Tower')['ring']).centroid.coords[0]
    lon, lat = Transformer.from_crs('EPSG:32618', 'EPSG:4326', always_xy=True).transform(e, n)
    return lat, lon


def bearing_deg(lat1, lon1, lat2, lon2):
    """Initial bearing from point 1 to point 2 (0 = north, clockwise)."""
    p1, p2, dl = math.radians(lat1), math.radians(lat2), math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2); x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def distance_m(lat1, lon1, lat2, lon2):
    dy = (lat2 - lat1) * 111_320; dx = (lon2 - lon1) * 111_320 * math.cos(math.radians(lat1))
    return math.hypot(dx, dy)


def angle_gap(a, b):
    return abs((a - b + 180) % 360 - 180)


def probe(radius_m=250.0):
    lat, lon = tower_latlon()
    dlat = radius_m / 111_320; dlon = radius_m / (111_320 * math.cos(math.radians(lat)))
    params = {'fields': FIELDS, 'bbox': f'{lon - dlon},{lat - dlat},{lon + dlon},{lat + dlat}', 'limit': 2000}
    request = urllib.request.Request(API + '?' + urllib.parse.urlencode(params), headers={'Authorization': 'OAuth ' + token()})
    with urllib.request.urlopen(request, timeout=60) as response: data = json.load(response).get('data', [])
    images = []
    for im in data:
        g = (im.get('computed_geometry') or im.get('geometry') or {}).get('coordinates')
        if not g: continue
        ilon, ilat = g
        d = distance_m(lat, lon, ilat, ilon)
        if d > radius_m: continue
        from_tower = bearing_deg(lat, lon, ilat, ilon)
        to_tower = bearing_deg(ilat, ilon, lat, lon)
        heading = im.get('computed_compass_angle', im.get('compass_angle'))
        spherical = im.get('camera_type') in ('spherical', 'equirectangular')
        facing = spherical or (heading is not None and angle_gap(heading, to_tower) <= FACING_TOLERANCE_DEG)
        images.append({'id': im['id'], 'distance_m': round(d, 1), 'bearing_from_tower_deg': round(from_tower, 1),
                       'camera_heading_deg': heading, 'camera_type': im.get('camera_type'), 'faces_tower': bool(facing),
                       'captured': datetime.fromtimestamp(im['captured_at'] / 1000, timezone.utc).date().isoformat() if im.get('captured_at') else None,
                       'sequence': (im.get('sequence') or {}).get('id') if isinstance(im.get('sequence'), dict) else im.get('sequence'),
                       'creator': (im.get('creator') or {}).get('username')})
    lo, hi = ARTS_QUAD_SECTOR
    in_sector = [i for i in images if lo <= i['bearing_from_tower_deg'] <= hi]
    useful = [i for i in in_sector if i['faces_tower']]
    sectors = Counter(int(i['bearing_from_tower_deg'] // 45) * 45 for i in images)
    report = {'schema_version': 1, 'created_utc': datetime.now(timezone.utc).isoformat(), 'tower_latlon': [lat, lon], 'radius_m': radius_m,
              'images': len(images), 'by_45_degree_sector_from_tower': {f'{k}-{k + 45}': v for k, v in sorted(sectors.items())},
              'arts_quad_sector_deg': list(ARTS_QUAD_SECTOR), 'in_arts_quad_sector': len(in_sector),
              'in_arts_quad_sector_facing_tower': len(useful),
              'facing_tower_sequences': len({i['sequence'] for i in useful}), 'facing_tower_creators': len({i['creator'] for i in useful}),
              'capture_years_facing': dict(Counter((i['captured'] or '')[:4] for i in useful)),
              'licence': 'Mapillary imagery: CC BY-SA 4.0', 'records': images}
    out = ROOT / 'artifacts/provider-probes' / f"mapillary-tower-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M')}.json"
    out.parent.mkdir(parents=True, exist_ok=True); out.write_text(json.dumps(report, indent=1) + '\n')
    return report, out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--radius', type=float, default=250.0)
    report, out = probe(parser.parse_args().radius)
    print(json.dumps({k: v for k, v in report.items() if k != 'records'}, indent=1)); print('written', out)


if __name__ == '__main__': main()
