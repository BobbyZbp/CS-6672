#!/usr/bin/env python3
"""Count Mapillary street-level images around McGraw Tower, by direction.

Read-only probe: reads Mapillary's public coverage vector tile for images
within about 400 m of the tower, and for each reports where it stands relative to the tower
(bearing, 0 = north) and whether its camera points at the tower. The question
is whether any coverage exists in the Arts Quad sector (0-110 degrees), from
which every Boardman postcard was taken. No image is downloaded.

Needs a free Mapillary access token in .secrets/mapillary.env
(MAPILLARY_TOKEN=MLY|... or the bare token) or the MAPILLARY_TOKEN environment variable.
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

ARTS_QUAD_SECTOR = (0.0, 110.0)
FACING_TOLERANCE_DEG = 40.0


def token():
    if os.environ.get('MAPILLARY_TOKEN'): return os.environ['MAPILLARY_TOKEN'].strip()
    path = ROOT / '.secrets/mapillary.env'
    for line in path.read_text().splitlines() if path.exists() else []:
        line = line.strip()
        if line.startswith('MAPILLARY_TOKEN='): return line.split('=', 1)[1].strip()
        if line.startswith('MLY|'): return line  # a bare token is accepted too
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


def tile_index(lat, lon, z):
    n = 2 ** z
    return int((lon + 180) / 360 * n), int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)


def coverage_points(lat, lon, z=14):
    """Image points from Mapillary's public coverage vector tile (works with any valid token)."""
    import mapbox_vector_tile
    x, y = tile_index(lat, lon, z)
    url = f'https://tiles.mapillary.com/maps/vtp/mly1_public/2/{z}/{x}/{y}?access_token={token()}'
    with urllib.request.urlopen(url, timeout=60) as response: layer = mapbox_vector_tile.decode(response.read())['image']
    extent, n, points = layer.get('extent', 4096), 2 ** z, []
    for feature in layer['features']:
        px, py = feature['geometry']['coordinates']
        X, Y = (x + px / extent) / n, (y + (extent - py) / extent) / n  # the decoder flips y
        points.append((math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * Y)))), X * 360 - 180, feature['properties']))
    return points


def probe(radius_m=400.0):
    lat, lon = tower_latlon()
    images = []
    for ilat, ilon, prop in coverage_points(lat, lon):
        d = distance_m(lat, lon, ilat, ilon)
        if d > radius_m: continue
        from_tower = bearing_deg(lat, lon, ilat, ilon); to_tower = (from_tower + 180) % 360
        heading = prop.get('compass_angle')
        facing = bool(prop.get('is_pano')) or (heading is not None and angle_gap(heading, to_tower) <= FACING_TOLERANCE_DEG)
        images.append({'id': prop.get('id'), 'distance_m': round(d, 1), 'bearing_from_tower_deg': round(from_tower, 1),
                       'camera_heading_deg': heading, 'panorama': bool(prop.get('is_pano')), 'faces_tower': facing,
                       'captured': datetime.fromtimestamp(prop['captured_at'] / 1000, timezone.utc).date().isoformat() if prop.get('captured_at') else None,
                       'sequence': prop.get('sequence_id'), 'creator': prop.get('creator_id')})
    lo, hi = ARTS_QUAD_SECTOR
    in_sector = [i for i in images if lo <= i['bearing_from_tower_deg'] <= hi]
    useful = [i for i in in_sector if i['faces_tower']]
    sectors = Counter(int(i['bearing_from_tower_deg'] // 45) * 45 for i in images)
    report = {'schema_version': 2, 'created_utc': datetime.now(timezone.utc).isoformat(), 'source': 'Mapillary coverage vector tiles (zoom 14)',
              'tower_latlon': [lat, lon], 'radius_m': radius_m, 'facing_tolerance_deg': FACING_TOLERANCE_DEG,
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
    parser.add_argument('--radius', type=float, default=400.0)
    report, out = probe(parser.parse_args().radius)
    print(json.dumps({k: v for k, v in report.items() if k != 'records'}, indent=1)); print('written', out)


if __name__ == '__main__': main()
