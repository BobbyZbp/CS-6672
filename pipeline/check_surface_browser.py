#!/usr/bin/env python3
"""Exercise actual local WebGL loads, materials, viewpoints, and responsive UI."""
import asyncio
import hashlib
import json
from pathlib import Path
from playwright.async_api import async_playwright

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/browser-qa'


async def main():
    OUT.mkdir(parents=True,exist_ok=True)
    errors=[];failed=[];checks=[]
    manifest=json.loads((ROOT/'dist/assets/repair/manifest.json').read_text())
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,args=['--no-sandbox','--disable-dev-shm-usage','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
        page=await browser.new_page(viewport={'width':1440,'height':1100},device_scale_factor=1)
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('response',lambda r:failed.append(f'{r.status} {r.url}') if r.status>=400 else None)
        await page.goto('http://127.0.0.1:8080/',wait_until='domcontentloaded')
        await page.wait_for_url('**/artsquad.html')
        checks.append('homepage opens modern Arts Quad workbench; earlier experiments remain separate')
        await page.goto('http://127.0.0.1:8080/surface-lab.html',wait_until='domcontentloaded')
        await page.wait_for_function("document.querySelector('#load-status').textContent.includes('COMPUTED SURFACE')",timeout=45000)
        await page.wait_for_load_state('networkidle')
        stats=await page.locator('#mesh-stats').inner_text()
        assert f"{manifest['models'][0]['report']['outputs']['dense']['vertex']:,}" in stats,stats
        assert await page.locator('#source-photo').evaluate('(im)=>im.naturalWidth>0')
        await page.locator('img[src$="mask-audit.jpg"]').scroll_into_view_if_needed()
        await page.wait_for_function("document.querySelector('img[src$=\"mask-audit.jpg\"]').naturalWidth>0")
        await page.locator('#viewer').scroll_into_view_if_needed()
        await page.screenshot(path=str(OUT/'modern.png'),full_page=True)
        await page.locator('#viewport canvas').screenshot(path=str(OUT/'modern-canvas.png'))
        checks.append({'modern_loaded':stats})
        before=await page.locator('#viewport canvas').screenshot()
        await page.select_option('#display','wire')
        await page.wait_for_timeout(250)
        after=await page.locator('#viewport canvas').screenshot()
        assert hashlib.sha256(before).digest()!=hashlib.sha256(after).digest(),'display mode did not change rendered pixels'
        checks.append('wireframe changes rendered pixels')
        await page.select_option('#display','texture')
        await page.select_option('#geometry','supported')
        await page.wait_for_function("document.querySelector('#load-status').textContent.includes('COMPUTED SURFACE')",timeout=45000)
        await page.wait_for_load_state('networkidle')
        checks.append('conservative support mesh variant loads')
        await page.select_option('#geometry','native')
        await page.wait_for_function("document.querySelector('#load-status').textContent.includes('COMPUTED SURFACE')",timeout=45000)
        await page.wait_for_load_state('networkidle')
        await page.select_option('#camera','1')
        await page.wait_for_load_state('networkidle')
        assert await page.locator('#source-photo').evaluate('(im)=>im.naturalWidth>0')
        checks.append('recovered camera selection loads its source photograph')
        # Test every computed model and every texture atlas through real loads.
        options=await page.locator('#experiment option').all_text_contents()
        for i,name in enumerate(options):
            if i==0:continue
            await page.select_option('#experiment',str(i))
            await page.wait_for_function("document.querySelector('#load-status').textContent.includes('COMPUTED SURFACE')",timeout=45000)
            await page.wait_for_load_state('networkidle')
            checks.append({'experiment_loaded':name,'stats':await page.locator('#mesh-stats').inner_text()})
            if manifest['models'][i]['id'].startswith('historical-masked'):
                assert await page.locator('#geometry').input_value()=='exposure'
                await page.screenshot(path=str(OUT/(manifest['models'][i]['id']+'.png')),full_page=True)
                await page.locator('#viewport canvas').screenshot(path=str(OUT/(manifest['models'][i]['id']+'-canvas.png')))
        historical_index=next(i for i,m in enumerate(manifest['models']) if m['id']=='historical-masked08')
        await page.select_option('#experiment',str(historical_index))
        expected=f"{manifest['models'][historical_index]['report']['outputs']['dense']['vertex']:,}"
        await page.wait_for_function("s=>document.querySelector('#mesh-stats').textContent.includes(s)",arg=expected,timeout=30000)
        await page.wait_for_load_state('networkidle')
        await page.screenshot(path=str(OUT/'historical.png'),full_page=True)
        box=await page.locator('#viewport canvas').bounding_box()
        await page.mouse.move(box['x']+box['width']*.5,box['y']+box['height']*.5)
        await page.mouse.down();await page.mouse.move(box['x']+box['width']*.65,box['y']+box['height']*.55,steps=10);await page.mouse.up()
        checks.append('orbit pointer drag completed')
        await page.set_viewport_size({'width':390,'height':844})
        await page.wait_for_timeout(250)
        assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth+2'),'horizontal mobile overflow'
        await page.screenshot(path=str(OUT/'mobile.png'),full_page=True)
        checks.append('390px mobile layout fits viewport')
        await browser.close()
    result={'checks':checks,'page_errors':errors,'failed_http_responses':failed}
    (OUT/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    assert not errors and not failed,result


if __name__=='__main__':asyncio.run(main())
