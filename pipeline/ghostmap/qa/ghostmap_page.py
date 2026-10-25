#!/usr/bin/env python3
"""Headless check of the live demo (dist/ghostmap.html) and slides (dist/slides.html).

Loads both pages from a running server (python3 -m http.server 8080 --directory
dist), opens every demo chapter and every slide, and fails on page errors,
console errors or missing numbers. Screenshots go to artifacts/browser-qa/ghostmap/.
Set PLAYWRIGHT_BROWSERS_PATH=/home/bobby/CS6672/.cache/playwright.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from ghostmap.paths import ROOT

CHAPTERS = ['stock', 'anchor', 'photographers', 'postcards', 'mirror', 'certificates']


async def check(base_url, output):
    from playwright.async_api import async_playwright
    output.mkdir(parents=True, exist_ok=True)
    report = {'base_url': base_url, 'errors': [], 'chapters': {}, 'slides': {}}
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
        page = await browser.new_page(viewport={'width': 1440, 'height': 900})
        page.on('pageerror', lambda e: report['errors'].append('pageerror: ' + str(e)))
        page.on('console', lambda m: report['errors'].append('console: ' + m.text) if m.type == 'error' else None)
        await page.goto(base_url + '/ghostmap.html')
        await page.wait_for_function('document.documentElement.dataset.ready === "true"', timeout=60000)
        for i, chapter in enumerate(CHAPTERS, start=1):
            await page.click(f'#chapters button:has-text("{i} ·")')
            await page.wait_for_timeout(1200)
            text = await page.inner_text('#chapter-body')
            report['chapters'][chapter] = {'characters': len(text), 'missing_numbers': text.count('—') if chapter != 'certificates' else None}
            await page.screenshot(path=str(output / f'demo-{chapter}.png'))
        slides = await browser.new_page(viewport={'width': 1600, 'height': 900})
        slides.on('pageerror', lambda e: report['errors'].append('slides pageerror: ' + str(e)))
        await slides.goto(base_url + '/slides.html#1')
        await slides.wait_for_function('document.documentElement.dataset.ready === "true"', timeout=30000)
        count = await slides.locator('.slide').count()
        for n in range(1, count + 1):
            await slides.keyboard.press('ArrowRight') if n > 1 else None
            await slides.wait_for_timeout(250)
            text = await slides.inner_text('.slide.on')
            report['slides'][n] = {'characters': len(text)}
            await slides.screenshot(path=str(output / f'slide-{n:02d}.png'))
        await browser.close()
    report['passed'] = not report['errors'] and all(c['characters'] > 200 for c in report['chapters'].values())
    (output / 'report.json').write_text(json.dumps(report, indent=1) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8080')
    parser.add_argument('--output', type=Path, default=ROOT / 'artifacts/browser-qa/ghostmap')
    args = parser.parse_args()
    report = asyncio.run(check(args.base_url.rstrip('/'), args.output))
    print(json.dumps({'passed': report['passed'], 'errors': report['errors'], 'slides': len(report['slides'])}, indent=1))
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__': main()
