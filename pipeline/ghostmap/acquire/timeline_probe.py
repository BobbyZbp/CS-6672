#!/usr/bin/env python3
"""Can the last twenty years of Cornell be seen in licensed online photographs?

For each building that changed (Gates Hall built 2012-14, Klarman Hall 2014-16,
Milstein Hall 2009-11) and each stable neighbour, count Wikimedia Commons
photographs by capture year, keeping only those that pass the project's
licence, size and date rules, plus Flickr Creative Commons photographs through
Openverse. Discovery uses the building's Commons category (with
subcategories), a title search, and a location search around its footprint.
Nothing is downloaded; the per-year table decides whether a year slider can
show the change.
"""
from __future__ import annotations

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from ghostmap.acquire.artsquad import AGENT, api, assess, geosearch, members, search
from ghostmap.acquire.commons import metadata_value
from ghostmap.paths import ROOT

# (label, Commons category, title-search names, approximate centre lat/lon, radius m, construction window)
PLACES = [
    ('Gates Hall (built 2012-2014)', 'Bill & Melinda Gates Hall', ['Gates Hall'], (42.4449, -76.4812), 120, (2012, 2014)),
    ('Klarman Hall (built 2014-2016)', 'Klarman Hall', ['Klarman Hall'], (42.4491, -76.4832), 100, (2014, 2016)),
    ('Milstein Hall (built 2009-2011)', 'Milstein Hall', ['Milstein Hall'], (42.4510, -76.4836), 100, (2009, 2011)),
    ('Goldwin Smith Hall (stable; east side changed by Klarman)', 'Goldwin Smith Hall (Cornell University)', ['Goldwin Smith Hall'], (42.4490, -76.4838), 100, None),
    ('Olin Library and plaza', 'Olin Library (Cornell University)', ['Olin Library'], (42.4478, -76.4842), 80, None),
    ('Uris Library and McGraw Tower (stable anchor)', 'McGraw Tower (Cornell University)', ['McGraw Tower', 'Uris Library'], (42.4476, -76.4850), 80, None),
]
CONFIG = {'minimum_short_side': 800, 'capture_year_min': 2000, 'targets': [{'name': n} for p in PLACES for n in p[2]]}


def year_of(page):
    date = metadata_value((page.get('imageinfo') or [{}])[0].get('extmetadata', {}), 'DateTimeOriginal')
    years = [int(y) for y in re.findall(r'(?<!\d)((?:19|20)\d{2})(?!\d)', date)]
    return min(years) if years else None


def commons_pages(category, names, centre, radius):
    found, origin = {}, defaultdict(set)
    def add(row, how):
        found[int(row['pageid'])] = row; origin[int(row['pageid'])].add(how)
    for row in members(category):
        if row['ns'] == 6: add(row, 'category')
        elif row['ns'] == 14:
            for sub in members(row['title'].removeprefix('Category:')):
                if sub['ns'] == 6: add(sub, 'subcategory')
    for name in names:
        for row in search(f'intitle:"{name}" Cornell'): add(row, 'title search')
    for row in geosearch(centre[0], centre[1], radius): add(row, 'location')
    pages, ids = [], sorted(found)
    for offset in range(0, len(ids), 40):
        d = api({'action': 'query', 'pageids': '|'.join(map(str, ids[offset:offset + 40])), 'prop': 'imageinfo', 'iiprop': 'url|size|mime|extmetadata'})
        for page in d.get('query', {}).get('pages', []):
            page['discovery'] = {'sources': ['Category:' + category] if 'category' in origin[page['pageid']] else [], 'targets': []}
            if 'location' in origin[page['pageid']]: page['discovery']['sources'].append('geosearch:probe')
            pages.append(page)
    return pages


def openverse_years(query):
    """Flickr CC photographs via Openverse; Openverse exposes no capture date, so only a count."""
    url = 'https://api.openverse.org/v1/images/?' + urllib.parse.urlencode({'q': query, 'source': 'flickr', 'license': 'by,by-sa,cc0,pdm', 'page_size': 1})
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': AGENT}), timeout=40) as r: n = json.load(r).get('result_count', 0)
    except OSError: n = None
    time.sleep(2)
    return n


def probe():
    report = {'created_utc': datetime.now(timezone.utc).isoformat(), 'places': []}
    for label, category, names, centre, radius, window in PLACES:
        pages = commons_pages(category, names, centre, radius)
        eligible = [p for p in pages if assess(p, CONFIG)[0]]
        years = Counter(year_of(p) for p in eligible)
        before = after = during = 0
        if window:
            before = sum(v for y, v in years.items() if y and y < window[0])
            during = sum(v for y, v in years.items() if y and window[0] <= y <= window[1])
            after = sum(v for y, v in years.items() if y and y > window[1])
        entry = {'place': label, 'commons_found': len(pages), 'commons_eligible': len(eligible),
                 'eligible_by_year': {str(k): v for k, v in sorted(years.items(), key=lambda kv: (kv[0] is None, kv[0]))},
                 'before_construction': before, 'during': during, 'after': after,
                 'openverse_flickr_reusable': openverse_years(names[0] + ' Cornell')}
        report['places'].append(entry)
        print(f"{label:58s} commons {len(pages):4d} found, {len(eligible):4d} eligible | before {before:3d} during {during:3d} after {after:3d} | flickr CC {entry['openverse_flickr_reusable']}", flush=True)
        print('    by year:', ' '.join(f'{y}:{v}' for y, v in sorted(years.items(), key=lambda kv: (kv[0] is None, kv[0])) if y), flush=True)
    out = ROOT / 'artifacts/provider-probes' / f"timeline-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M')}.json"
    out.write_text(json.dumps(report, indent=1) + '\n'); print('written', out)
    return report


def main():
    argparse.ArgumentParser(description=__doc__).parse_args(); probe()


if __name__ == '__main__': main()
