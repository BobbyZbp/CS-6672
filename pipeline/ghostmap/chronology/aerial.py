#!/usr/bin/env python3
"""Was the building there in a given year? Evidence from dated aerial imagery.

A standing building draws its own outline in an aerial image: along the
footprint boundary the image gradient is strong, while a car park or a
courtyard has no edge there. For each footprint and each orthoimagery year the
mean gradient magnitude along the outline is divided by the mean gradient in
the surrounding neighbourhood; outline segments shared with a neighbouring
building (Klarman Hall is attached to Goldwin Smith Hall on three sides) are
left out, because they exist whether or not the new building does. The
decision rule is stated and calibrated: the building is present in a year
when its outline score is at least the lowest score that any stable building
of the same site reaches in any year, minus a margin. Per-year patches are
saved so a reader can look. Images of different years are not pixel-aligned,
so the outline is dilated by a tolerance before sampling.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

from ghostmap.paths import ROOT

FOOTPRINTS = ROOT / 'data/footprints/buildings-utm18n.json'
CHANGED = {'Bill & Melinda Gates Hall', 'Klarman Hall', 'Milstein Hall'}
MARGIN = 0.15
SHARED_M = 2.5        # outline within this distance of another footprint is not the new building's own edge
TOLERANCE_M = 1.5     # misregistration between flight years


def patch(image, box, gsd, ring):
    from matplotlib.path import Path as MPath
    e = np.asarray(ring); e0, n0, e1, n1 = box
    cols = ((e[:, 0] - e0) / gsd); rows = ((n1 - e[:, 1]) / gsd)
    c0, c1 = int(max(0, cols.min())), int(min(image.shape[1], cols.max() + 1)); r0, r1 = int(max(0, rows.min())), int(min(image.shape[0], rows.max() + 1))
    if c1 - c0 < 4 or r1 - r0 < 4: return None, None
    sub = image[r0:r1, c0:c1]
    gy, gx = np.mgrid[r0:r1, c0:c1]
    inside = MPath(np.column_stack([cols, rows])).contains_points(np.column_stack([gx.ravel() + .5, gy.ravel() + .5])).reshape(sub.shape[:2])
    return sub, inside


def outline_score(grad, box, gsd, ring, others, tol_px):
    """Mean gradient along the building's own outline over the mean gradient nearby."""
    from shapely.geometry import LineString, Point, Polygon
    poly = Polygon(ring); line = poly.exterior
    other_lines = [Polygon(o).exterior for o in others]
    samples = []
    for s in np.arange(0, line.length, gsd):
        pt = line.interpolate(s)
        if any(ol.distance(pt) < SHARED_M for ol in other_lines): continue
        samples.append(pt.coords[0])
    if len(samples) < 20: return None, 0
    samples = np.asarray(samples)
    c = ((samples[:, 0] - box[0]) / gsd).astype(int); r = ((box[3] - samples[:, 1]) / gsd).astype(int)
    rows, cols = grad.shape
    ok = (c >= tol_px) & (c < cols - tol_px) & (r >= tol_px) & (r < rows - tol_px)
    if ok.sum() < 20: return None, 0
    # best gradient within the tolerance window around each outline sample
    edge = np.array([grad[r[i] - tol_px:r[i] + tol_px + 1, c[i] - tol_px:c[i] + tol_px + 1].max() for i in np.flatnonzero(ok)])
    e0, n0, e1, n1 = poly.buffer(12.0).bounds
    c0, c1 = int(max(0, (e0 - box[0]) / gsd)), int(min(cols, (e1 - box[0]) / gsd)); r0, r1 = int(max(0, (box[3] - n1) / gsd)), int(min(rows, (box[3] - n0) / gsd))
    nearby = grad[r0:r1, c0:c1]
    return float(edge.mean() / max(float(nearby.mean()), 1e-6)), int(ok.sum())


def ncc(a, b, mask):
    x, y = a[mask].astype(float), b[mask].astype(float)
    x -= x.mean(); y -= y.mean()
    d = np.sqrt((x * x).sum() * (y * y).sum())
    return float((x * y).sum() / d) if d > 0 else 0.0


def run(ortho_dir, output=None, min_area_m2=150.0):
    ortho_dir = Path(ortho_dir); rep = json.loads((ortho_dir / 'report.json').read_text())
    box, gsd = rep['box_utm'], rep['ground_sample_distance_m']
    years = sorted(rep['years']); latest = years[-1]
    images = {y: np.asarray(Image.open(ortho_dir / rep['years'][y]['file']).convert('L')) for y in years}
    from scipy.ndimage import gaussian_filter, sobel
    grads = {}
    for y, im in images.items():
        sm = gaussian_filter(im.astype(float), 1.0); grads[y] = np.hypot(sobel(sm, 0), sobel(sm, 1))
    tol_px = max(1, int(round(TOLERANCE_M / gsd)))
    buildings = json.loads(FOOTPRINTS.read_text())['buildings']
    from shapely.geometry import Polygon
    out = (Path(output) if output else ortho_dir / 'roof-presence'); (out / 'patches').mkdir(parents=True, exist_ok=True)
    rows = []
    for b in buildings:
        ring = np.asarray(b['ring'])
        if not (box[0] < ring[:, 0].mean() < box[2] and box[1] < ring[:, 1].mean() < box[3]) or Polygon(ring).area < min_area_m2: continue
        ref_patch, mask = patch(images[latest], box, gsd, ring)
        if ref_patch is None or mask.sum() < 50: continue
        per_year = {}
        strip = []
        others = [np.asarray(o['ring']) for o in buildings if o is not b and Polygon(np.asarray(o['ring'])).distance(Polygon(ring)) < SHARED_M]
        for y in years:
            p, m = patch(images[y], box, gsd, ring)
            score, n = outline_score(grads[y], box, gsd, ring, others, tol_px)
            per_year[y] = {'outline_edge_ratio': score, 'own_outline_samples': n, 'ncc_with_latest': ncc(p, ref_patch, m), 'mean_grey': float(p[m].mean())}
            strip.append(Image.fromarray(p).resize((160, int(160 * p.shape[0] / p.shape[1]) or 1)))
        sheet = Image.new('L', (160 * len(strip), max(s.height for s in strip)), 255)
        for i, s in enumerate(strip): sheet.paste(s, (i * 160, 0))
        name = b['name'] or b['osm'].replace('/', '-')
        sheet.save(out / 'patches' / (name.replace(' ', '_').replace('&', 'and') + '.png'))
        rows.append({'name': name, 'changed_site': b['name'] in CHANGED, 'area_m2': round(Polygon(ring).area), 'years': per_year})
    rows = [r for r in rows if all(v['outline_edge_ratio'] is not None for v in r['years'].values())]
    stable = [r for r in rows if not r['changed_site']]
    floor = min(v['outline_edge_ratio'] for r in stable for v in r['years'].values()) if stable else 1.0
    threshold = max(1.0, floor - MARGIN)
    for r in rows:
        r['roof_present_years'] = [y for y in years if r['years'][y]['outline_edge_ratio'] >= threshold]
        r['first_year_present'] = r['roof_present_years'][0] if r['roof_present_years'] else None
        r['absent_years'] = [y for y in years if y not in r['roof_present_years']]
    result = {'schema_version': 1, 'created_utc': datetime.now(timezone.utc).isoformat(), 'orthoimagery': str(ortho_dir), 'years': years,
              'latest_year': latest, 'rule': f'present when the own-outline edge ratio >= {threshold:.2f} (stable buildings reach at least {floor:.2f} in every year; margin {MARGIN})',
              'threshold': threshold, 'stable_buildings_min_ratio': floor, 'buildings': rows}
    (out / 'report.json').write_text(json.dumps(result, indent=1) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--orthoimagery', type=Path, default=ROOT / 'data/orthoimagery/quad')
    parser.add_argument('--output', type=Path)
    r = run(parser.parse_args().orthoimagery, parser.parse_args().output)
    print(r['rule'])
    for b in r['buildings']:
        flag = ' *' if b['changed_site'] else ''
        print(f"{b['name'][:28]:28s}{flag:2s} " + ' '.join(f"{y}:{b['years'][y]['outline_edge_ratio']:.2f}" for y in r['years']) + f"  present {b['roof_present_years']}")


if __name__ == '__main__': main()
