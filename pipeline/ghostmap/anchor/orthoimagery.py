#!/usr/bin/env python3
"""New York State orthoimagery, one dated aerial image per flight year.

The NYS GIS Program Office serves statewide orthoimagery through a public,
keyless WMS with one service per flight year (https://orthos.its.ny.gov).
Tompkins County was flown in 2002, 2007, 2012, 2015, 2018 and 2023. Each
year's image is fetched for the same box as the lidar crop, in UTM zone 18N at
a fixed ground sample distance, so that pixels of different years and the
lidar rasters line up. Every request and response is recorded with its hash.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

from ghostmap.paths import ROOT

WMS = 'https://orthos.its.ny.gov/arcgis/services/wms/{year}/MapServer/WmsServer'
YEARS = ['2002', '2007', '2012', '2015', '2018', '2023']
LIDAR_REPORT = ROOT / 'data/lidar/NY_FingerLakes_1_2020/report.json'
OUT = ROOT / 'data/orthoimagery'
MAX_TILE_PX = 4000  # ArcGIS WMS image size limit
CREDIT = 'New York State orthoimagery, NYS GIS Program Office (public, https://orthos.its.ny.gov)'


def fetch_tile(year, bbox_utm, width, height, out, attempts=4):
    """GetMap for a UTM 18N box (EPSG:32618 is served directly? no: ask in EPSG:4326 and sample).

    The service lists EPSG:4326 and Web Mercator only, so the box is converted
    to WGS84 corners; the returned image is then warped to the UTM grid.
    """
    from pyproj import Transformer
    to_wgs = Transformer.from_crs('EPSG:32618', 'EPSG:4326', always_xy=True)
    e0, n0, e1, n1 = bbox_utm
    lons, lats = to_wgs.transform([e0, e1, e0, e1], [n0, n0, n1, n1])
    bbox = f'{min(lats)},{min(lons)},{max(lats)},{max(lons)}'  # WMS 1.3.0 + EPSG:4326: lat,lon order
    url = (WMS.format(year=year) + f'?service=WMS&request=GetMap&version=1.3.0&layers=0&styles=&crs=EPSG:4326'
           f'&bbox={bbox}&width={width}&height={height}&format=image/jpeg')
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=120) as response: data = response.read()
            Image.open(io.BytesIO(data)).verify()
            out.write_bytes(data)
            return url, hashlib.sha256(data).hexdigest(), (min(lons), min(lats), max(lons), max(lats))
        except Exception:
            if attempt == attempts - 1: raise
            time.sleep(10 * (attempt + 1))


def warp_to_utm(image_path, wgs_box, bbox_utm, gsd):
    """Resample the WGS84-boxed image onto the UTM grid (nearest neighbour)."""
    from pyproj import Transformer
    to_wgs = Transformer.from_crs('EPSG:32618', 'EPSG:4326', always_xy=True)
    src = np.asarray(Image.open(image_path).convert('RGB'))
    h, w = src.shape[:2]
    e0, n0, e1, n1 = bbox_utm
    cols, rows = int(round((e1 - e0) / gsd)), int(round((n1 - n0) / gsd))
    es = e0 + (np.arange(cols) + .5) * gsd; ns = n1 - (np.arange(rows) + .5) * gsd
    E, N = np.meshgrid(es, ns)
    lon, lat = to_wgs.transform(E.ravel(), N.ravel())
    x = ((lon - wgs_box[0]) / (wgs_box[2] - wgs_box[0]) * w).astype(int).clip(0, w - 1)
    y = ((wgs_box[3] - lat) / (wgs_box[3] - wgs_box[1]) * h).astype(int).clip(0, h - 1)
    return src[y, x].reshape(rows, cols, 3)


def build(output=OUT, gsd=0.3, years=YEARS, lidar_report=LIDAR_REPORT):
    output = Path(output); (output / 'raw').mkdir(parents=True, exist_ok=True)
    lidar = json.loads(Path(lidar_report).read_text())
    bbox = tuple(lidar['box_utm'])
    cols, rows = int(round((bbox[2] - bbox[0]) / gsd)), int(round((bbox[3] - bbox[1]) / gsd))
    if max(cols, rows) > MAX_TILE_PX: raise ValueError('Box too large for one WMS request at this ground sample distance')
    report = {'schema_version': 1, 'created_utc': datetime.now(timezone.utc).isoformat(), 'credit': CREDIT, 'crs': 'EPSG:32618',
              'box_utm': list(bbox), 'ground_sample_distance_m': gsd, 'shape': [rows, cols], 'years': {}}
    for year in years:
        raw = output / 'raw' / f'{year}.jpg'
        url, digest, wgs_box = fetch_tile(year, bbox, int(cols * 1.4), int(rows * 1.4), raw)  # oversample before warping
        warped = warp_to_utm(raw, wgs_box, bbox, gsd)
        Image.fromarray(warped).save(output / f'{year}-utm18n.jpg', quality=92)
        grey = warped.mean(2)
        report['years'][year] = {'request': url, 'raw_sha256': digest, 'raw_bytes': raw.stat().st_size,
                                 'mean_grey': float(grey.mean()), 'std_grey': float(grey.std()),
                                 'blank': bool(grey.std() < 5), 'file': f'{year}-utm18n.jpg'}
        print(year, 'std', round(float(grey.std()), 1), flush=True)
    (output / 'report.json').write_text(json.dumps(report, indent=1) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gsd', type=float, default=0.3, help='ground sample distance in metres')
    parser.add_argument('--output', type=Path, default=OUT)
    parser.add_argument('--lidar-report', type=Path, default=LIDAR_REPORT, help='lidar crop whose box is used')
    args = parser.parse_args()
    report = build(args.output, args.gsd, lidar_report=args.lidar_report)
    print(json.dumps({y: v['blank'] for y, v in report['years'].items()}))


if __name__ == '__main__': main()
