#!/usr/bin/env python3
"""Headless check of the GhostMap page (dist/timemachine.html) and the decks (dist/presentation.html, dist/timemachine-slides.html).

Loads the page from a running server (python3 -m http.server 8080 --directory
dist), opens every chapter, waits for what the chapter loads (the snap animation, the
Gaussian splats), moves the year slider through the years that matter in that chapter,
and fails on page errors, console errors, an empty chapter text or a year display that
did not follow the slider; then steps through every slide of each deck that exists.
Screenshots go to artifacts/browser-qa/timemachine/.
Set PLAYWRIGHT_BROWSERS_PATH=/home/bobby/CS6672/.cache/playwright.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from ghostmap.paths import ROOT

# Chapter (in page order) -> years viewed in it: aerial flights around each documented change.
CHAPTERS = {'void': [2023], 'snap': [2023], 'refuse': [2023], 'referee': [2023], 'teacher': [2023],
            'above': [2002, 2012, 2023], 'gates': [2007, 2013, 2016], 'klarman': [2012, 2015, 2018],
            'tower': [2009, 2025], 'limits': [2023]}
# Extra settling time after opening a chapter: the snap animation and the camera flight, the splats' loading.
SETTLE_MS = {'snap': 6500, 'referee': 4000, 'teacher': 4000}
DECKS = ['presentation.html', 'timemachine-slides.html']


async def check(base_url, output):
    from playwright.async_api import async_playwright
    output.mkdir(parents=True, exist_ok=True)
    report = {'base_url': base_url, 'errors': [], 'chapters': {}, 'slides': {}}
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
        page = await browser.new_page(viewport={'width': 1440, 'height': 900})
        page.on('pageerror', lambda e: report['errors'].append('pageerror: ' + str(e)))
        page.on('console', lambda m: report['errors'].append('console: ' + m.text) if m.type == 'error' else None)
        await page.goto(base_url + '/timemachine.html')
        await page.wait_for_function('document.documentElement.dataset.ready === "true"', timeout=90000)
        for i, (chapter, years) in enumerate(CHAPTERS.items(), start=1):
            await page.click(f'#chapters button:has-text("{i} ·")')
            await page.wait_for_timeout(1500 + SETTLE_MS.get(chapter, 0))
            if chapter in ('referee', 'teacher'):   # a splat may still be loading: wait for the status line to clear
                await page.wait_for_function("!document.getElementById('status').textContent.startsWith('Loading')", timeout=180000)
                await page.wait_for_timeout(2500)
            for year in years:
                await page.evaluate(f"const s = document.getElementById('slider'); s.value = {year}; s.dispatchEvent(new Event('input'))")
                await page.wait_for_timeout(600)
                await page.screenshot(path=str(output / f'{chapter}-{year}.png'))
            text = await page.inner_text('#chapter-body')
            report['chapters'][chapter] = {'characters': len(text), 'year_shown': await page.inner_text('#year'), 'year_set': years[-1]}
        for deck in DECKS:
            if not (ROOT / 'dist' / deck).exists(): continue
            slides = await browser.new_page(viewport={'width': 1600, 'height': 900}); stem = Path(deck).stem
            slides.on('pageerror', lambda e, d=deck: report['errors'].append(f'{d} pageerror: ' + str(e)))
            await slides.goto(f'{base_url}/{deck}#1')
            await slides.wait_for_function('document.documentElement.dataset.ready === "true"', timeout=60000)
            report['slides'][deck] = {}
            for n in range(1, await slides.locator('.slide').count() + 1):
                if n > 1: await slides.keyboard.press('ArrowRight')
                await slides.wait_for_timeout(400)
                report['slides'][deck][n] = {'characters': len(await slides.inner_text('.slide.on'))}
                await slides.screenshot(path=str(output / f'{stem}-{n:02d}.png'))
            await slides.close()
        await browser.close()
    report['passed'] = (not report['errors'] and all(c['characters'] > 150 and c['year_shown'] == str(c['year_set']) for c in report['chapters'].values())
                        and all(len(s) >= 8 and all(x['characters'] > 80 for x in s.values()) for s in report['slides'].values()))
    (output / 'report.json').write_text(json.dumps(report, indent=1) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8080')
    parser.add_argument('--output', type=Path, default=ROOT / 'artifacts/browser-qa/timemachine')
    args = parser.parse_args()
    report = asyncio.run(check(args.base_url.rstrip('/'), args.output))
    print(json.dumps({'passed': report['passed'], 'errors': report['errors'], 'chapters': report['chapters'], 'slides': {d: len(s) for d, s in report['slides'].items()}}, indent=1))
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__': main()
