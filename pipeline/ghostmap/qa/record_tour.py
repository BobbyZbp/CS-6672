#!/usr/bin/env python3
"""Record a captioned tour of the GhostMap demo page, and a still of every chapter for the slides.

The fallback for the live demo: a headless Chromium walks through the ten chapters of
`dist/timemachine.html` (served at --base-url) in presentation order, waits for each chapter's data
(the snap animation, the splats), moves the year slider where the chapter is about time, and
records the whole tour as a WebM video with a caption bar. Each chapter's settled view is also
saved as a still under `dist/assets/presentation/` for `dist/presentation.html`. Page errors and
console errors are collected; a chapter whose text is empty fails the run.

Headless Chromium only has software WebGL (SwiftShader), which cannot draw the splats at all within a
screenshot's timeout; under WSL a headed window on the WSLg display reaches the real GPU (ANGLE on
D3D12), so the tour runs headed by default (a browser window appears while it records) and records
the WebGL renderer it got. `--software` forces headless SwiftShader.

Usage: PLAYWRIGHT_BROWSERS_PATH=.cache/playwright PYTHONPATH=pipeline python -m ghostmap.qa.record_tour [--base-url http://127.0.0.1:8080] [--software]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path

from ghostmap.paths import ROOT

STILLS = ROOT / 'dist/assets/presentation'
VIDEO = ROOT / 'artifacts/presentation'
# Chapter id, seconds to dwell, caption, years to step through (None: leave the slider alone).
TOUR = [
    ('colmap', 8, 'Where COLMAP stops: five limits on internet photographs of a real place, and what GhostMap builds past each one.', None),
    ('void', 6, 'Lost in space: COLMAP turns 63 internet photographs into a fragment with no scale, no up and no north.', None),
    ('snap', 12, 'Snap to the world: public lidar and OpenStreetMap footprints place it in metres, with no GPS, and say how sure that is.', None),
    ('refuse', 8, 'Knowing when it cannot: every campus fragment the evidence cannot pin down is refused, with the reason.', None),
    ('referee', 14, 'The lidar as referee: a Gaussian splat from the same photographs, judged against the lidar, Gaussian by Gaussian.', None),
    ('teacher', 24, 'The lidar as teacher: a camera path between the photographers; red is paint in air the lidar measured empty.', None),
    ('above', 10, 'Twenty years from above: public aerial flights from 2002 to 2023 draped on the lidar terrain.', [2002, 2007, 2012, 2015, 2018, 2023]),
    ('gates', 8, 'Gates Hall: a parking lot until 2012, a building from 2014.', [2007, 2013, 2016]),
    ('klarman', 8, 'Klarman Hall fills the courtyard behind Goldwin Smith Hall.', [2012, 2015, 2018]),
    ('tower', 10, 'McGraw Tower over twenty years: every point knows the years photographs saw it.', [2004, 2010, 2016, 2025]),
    ('limits', 6, 'What the record cannot show, said out loud.', None),
]


async def sweep_wipe(page, seconds):
    """Referee: slide the photograph | splat wipe across and back, so the photograph turns into the splat."""
    steps = 40
    for k in range(steps + 1):
        v = round(100 * (0.5 - 0.5 * math.cos(2 * math.pi * k / steps)))
        await page.evaluate(f"(() => {{ const w = document.querySelector('.wipe input[type=range]'); if (w) {{ w.value = {v}; w.dispatchEvent(new Event('input')); }} }})()")
        await page.wait_for_timeout(int(1000 * seconds / (steps + 1)))


async def teacher(page, seconds):
    """Teacher: let the plain | lidar-taught fly-through play, then paint it by the lidar's verdict, then one pose as a wipe."""
    await page.wait_for_timeout(int(1000 * seconds * 0.4))
    await page.evaluate("(() => { const v = document.querySelector('.fly .verdict'); if (v) { v.checked = true; v.dispatchEvent(new Event('change')); } })()")
    await page.wait_for_timeout(int(1000 * seconds * 0.35))
    await page.evaluate("(() => { const r = document.querySelector('input[name=tchmode][value=pose-0]'); if (r) { r.checked = true; r.dispatchEvent(new Event('change', { bubbles: true })); } })()")
    await sweep_wipe(page, seconds * 0.25)


ACTIONS = {'referee': sweep_wipe, 'teacher': teacher}
CAPTION_JS = """(text) => {
  let bar = document.getElementById('tour-caption');
  if (!bar) { bar = document.createElement('div'); bar.id = 'tour-caption';
    bar.style.cssText = 'position:fixed;left:50%;bottom:18px;transform:translateX(-50%);max-width:78%;z-index:99;background:rgba(20,24,21,.86);color:#fff;font:600 18px/1.35 system-ui,sans-serif;padding:10px 18px;border-radius:10px;box-shadow:0 4px 18px rgba(0,0,0,.25)';
    document.body.appendChild(bar); }
  bar.textContent = text; bar.style.display = text ? 'block' : 'none';
}"""


RENDERER_JS = """() => { const gl = document.createElement('canvas').getContext('webgl2'); if (!gl) return null;
  const e = gl.getExtension('WEBGL_debug_renderer_info'); return e ? gl.getParameter(e.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER); }"""


async def tour(base_url, stills=STILLS, video_dir=VIDEO, width=1600, height=900, software=False):
    from playwright.async_api import async_playwright
    stills.mkdir(parents=True, exist_ok=True); video_dir.mkdir(parents=True, exist_ok=True)
    raw = video_dir / 'raw'; shutil.rmtree(raw, ignore_errors=True); raw.mkdir()
    report = {'base_url': base_url, 'errors': [], 'chapters': {}, 'created_utc': datetime.now(timezone.utc).isoformat()}
    async with async_playwright() as p:
        args = ['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] if software else ['--no-sandbox', '--use-angle=gl', '--ignore-gpu-blocklist']
        browser = await p.chromium.launch(headless=software, args=args)
        context = await browser.new_context(viewport={'width': width, 'height': height}, record_video_dir=str(raw), record_video_size={'width': width, 'height': height})
        page = await context.new_page()
        page.on('pageerror', lambda e: report['errors'].append('pageerror: ' + str(e)))
        page.on('console', lambda m: report['errors'].append('console: ' + m.text) if m.type == 'error' else None)
        page.set_default_timeout(120000)
        await page.goto(base_url + '/timemachine.html#colmap')
        report['webgl_renderer'] = await page.evaluate(RENDERER_JS)
        await page.wait_for_function('document.documentElement.dataset.ready === "true"', timeout=120000)
        for chapter, dwell, caption, years in TOUR:
            await page.evaluate(CAPTION_JS, caption)
            await page.click(f'#chapters button[data-chapter="{chapter}"]')
            # Chapters that load splats say so in #status; wait until it clears (or give up after two minutes).
            try: await page.wait_for_function("!(document.getElementById('status') || {}).textContent", timeout=120000)
            except Exception: report['errors'].append(f'{chapter}: still loading after two minutes')
            if chapter in ACTIONS:
                await ACTIONS[chapter](page, dwell)
            elif years:
                for y in years:
                    await page.evaluate(f"const s = document.getElementById('slider'); s.value = {y}; s.dispatchEvent(new Event('input'))")
                    await page.wait_for_timeout(int(1000 * dwell / len(years)))
            else:
                await page.wait_for_timeout(1000 * dwell)
            await page.evaluate(CAPTION_JS, '')
            try: await page.screenshot(path=str(stills / f'{chapter}.png'), timeout=180000)
            except Exception as e: report['errors'].append(f'{chapter}: screenshot failed ({type(e).__name__})')
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
    parser.add_argument('--software', action='store_true', help='headless software WebGL (no splats in reasonable time)')
    args = parser.parse_args()
    report = asyncio.run(tour(args.base_url.rstrip('/'), software=args.software))
    print(json.dumps({k: report[k] for k in ('passed', 'errors', 'video', 'webgl_renderer') if k in report}, indent=1))
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__': main()
