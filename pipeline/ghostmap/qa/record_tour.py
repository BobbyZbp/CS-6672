#!/usr/bin/env python3
"""Record a captioned tour of the GhostMap demo page, and a still of every chapter for the slides.

The fallback for the live demo: a headless Chromium walks through the ten chapters of
`dist/timemachine.html` (served at --base-url) in presentation order, waits for each chapter's data
(the snap animation, the splats), moves the year slider where the chapter is about time, and
records the whole tour as a WebM video with a caption bar. Each chapter's settled view is also
saved as a still under `dist/assets/presentation/` for `dist/presentation.html`. Page errors and
console errors are collected; a chapter whose text is empty fails the run.

Headless WebGL is SwiftShader (software), so splats render slowly: the waits are generous and the
video plays at the speed the page drew, not real time on a laptop GPU.

Usage: PLAYWRIGHT_BROWSERS_PATH=.cache/playwright PYTHONPATH=pipeline python -m ghostmap.qa.record_tour [--base-url http://127.0.0.1:8080]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from ghostmap.paths import ROOT

STILLS = ROOT / 'dist/assets/presentation'
VIDEO = ROOT / 'artifacts/presentation'
# Chapter id, seconds to dwell, caption, years to step through (None: leave the slider alone).
TOUR = [
    ('void', 6, 'Lost in space: COLMAP turns 63 internet photographs into a fragment with no scale, no up and no north.', None),
    ('snap', 12, 'Snap to the world: public lidar and OpenStreetMap footprints place it in metres, with no GPS, and say how sure that is.', None),
    ('refuse', 8, 'Knowing when it cannot: every campus fragment the evidence cannot pin down is refused, with the reason.', None),
    ('referee', 14, 'The lidar as referee: a Gaussian splat from the same photographs, judged against the lidar, Gaussian by Gaussian.', None),
    ('teacher', 14, 'The lidar as teacher: train with the lidar\'s free space and the floaters disappear.', None),
    ('above', 10, 'Twenty years from above: public aerial flights from 2002 to 2023 draped on the lidar terrain.', [2002, 2007, 2012, 2015, 2018, 2023]),
    ('gates', 8, 'Gates Hall: a parking lot until 2012, a building from 2014.', [2007, 2013, 2016]),
    ('klarman', 8, 'Klarman Hall fills the courtyard behind Goldwin Smith Hall.', [2012, 2015, 2018]),
    ('tower', 10, 'McGraw Tower over twenty years: every point knows the years photographs saw it.', [2004, 2010, 2016, 2025]),
    ('limits', 6, 'What the record cannot show, said out loud.', None),
]
CAPTION_JS = """(text) => {
  let bar = document.getElementById('tour-caption');
  if (!bar) { bar = document.createElement('div'); bar.id = 'tour-caption';
    bar.style.cssText = 'position:fixed;left:50%;bottom:18px;transform:translateX(-50%);max-width:78%;z-index:99;background:rgba(20,24,21,.86);color:#fff;font:600 18px/1.35 system-ui,sans-serif;padding:10px 18px;border-radius:10px;box-shadow:0 4px 18px rgba(0,0,0,.25)';
    document.body.appendChild(bar); }
  bar.textContent = text; bar.style.display = text ? 'block' : 'none';
}"""


async def tour(base_url, stills=STILLS, video_dir=VIDEO, width=1600, height=900):
    from playwright.async_api import async_playwright
    stills.mkdir(parents=True, exist_ok=True); video_dir.mkdir(parents=True, exist_ok=True)
    raw = video_dir / 'raw'; shutil.rmtree(raw, ignore_errors=True); raw.mkdir()
    report = {'base_url': base_url, 'errors': [], 'chapters': {}, 'created_utc': datetime.now(timezone.utc).isoformat()}
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'])
        context = await browser.new_context(viewport={'width': width, 'height': height}, record_video_dir=str(raw), record_video_size={'width': width, 'height': height})
        page = await context.new_page()
        page.on('pageerror', lambda e: report['errors'].append('pageerror: ' + str(e)))
        page.on('console', lambda m: report['errors'].append('console: ' + m.text) if m.type == 'error' else None)
        await page.goto(base_url + '/timemachine.html#void')
        await page.wait_for_function('document.documentElement.dataset.ready === "true"', timeout=120000)
        for n, (chapter, dwell, caption, years) in enumerate(TOUR, start=1):
            await page.evaluate(CAPTION_JS, caption)
            await page.click(f'#chapters button:has-text("{n} ·")')
            # Chapters that load splats say so in #status; wait until it clears (or give up after two minutes).
            try: await page.wait_for_function("!(document.getElementById('status') || {}).textContent", timeout=120000)
            except Exception: report['errors'].append(f'{chapter}: still loading after two minutes')
            if years:
                for y in years:
                    await page.evaluate(f"const s = document.getElementById('slider'); s.value = {y}; s.dispatchEvent(new Event('input'))")
                    await page.wait_for_timeout(int(1000 * dwell / len(years)))
            else:
                await page.wait_for_timeout(1000 * dwell)
            await page.evaluate(CAPTION_JS, '')
            await page.screenshot(path=str(stills / f'{chapter}.png'))
            text = await page.inner_text('#chapter-body')
            report['chapters'][chapter] = {'characters': len(text), 'still': f'assets/presentation/{chapter}.png'}
        await context.close(); await browser.close()
    videos = sorted(raw.glob('*.webm'))
    if videos:
        dest = video_dir / 'ghostmap-tour.webm'; shutil.move(str(videos[-1]), dest); report['video'] = str(dest)
    shutil.rmtree(raw, ignore_errors=True)
    report['passed'] = not report['errors'] and len(report['chapters']) == len(TOUR) and all(c['characters'] > 120 for c in report['chapters'].values())
    (video_dir / 'tour-report.json').write_text(json.dumps(report, indent=1) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--base-url', default='http://127.0.0.1:8080')
    args = parser.parse_args()
    report = asyncio.run(tour(args.base_url.rstrip('/')))
    print(json.dumps({k: report[k] for k in ('passed', 'errors', 'video') if k in report}, indent=1))
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__': main()
