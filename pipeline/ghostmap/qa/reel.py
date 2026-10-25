#!/usr/bin/env python3
"""Check actual local WebM playback, trace hashes and honest reel states.

Headless/software WebGL is a functional check, not device/network performance.
The actual reel is played and sought; no substitute video is generated.
"""
import argparse
import asyncio
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

from playwright.async_api import async_playwright

from ghostmap.paths import ROOT
async def check(base_url, output=None):
    output = Path(output) if output else ROOT / "artifacts/browser-qa/artsquad-reel"
    output.mkdir(parents=True, exist_ok=True)
    index_path = ROOT / "dist/assets/artsquad/demo/latest.json"
    index_bytes = index_path.read_bytes()
    index = json.loads(index_bytes)
    checks, errors, failed = [], [], []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        page = await browser.new_page(viewport={"width": 1440, "height": 1080}, reduced_motion="reduce")
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("response", lambda response: failed.append({"status": response.status, "url": response.url}) if response.status >= 400 else None)
        await page.goto(base_url + "/demo-reel.html")
        await page.wait_for_function("document.querySelector('#video').readyState >= 2", timeout=30000)
        video = page.locator("#video")
        metadata = await video.evaluate("v=>({duration:v.duration,width:v.videoWidth,height:v.videoHeight,paused:v.paused,autoplay:v.autoplay})")
        assert 45 <= metadata["duration"] <= 60
        assert (metadata["width"], metadata["height"]) == (index["video"]["width"], index["video"]["height"])
        assert metadata["paused"] and not metadata["autoplay"], "Recording must not autoplay on arrival"
        checks.append({"actual_webm_metadata": metadata})
        await video.evaluate("v=>v.play()")
        await page.wait_for_timeout(300)
        assert await video.evaluate("v=>v.currentTime>0 && !v.paused && !v.error")
        await video.evaluate("v=>v.pause()")
        checks.append("Actual captured WebM decodes and plays; no substitute frames")
        buttons = page.locator("#chapters button")
        assert await buttons.count() == len(index["chapters"])
        facet_index = next(i for i, chapter in enumerate(index["chapters"]) if chapter["id"] == "facet")
        await buttons.nth(facet_index).click()
        target = index["chapters"][facet_index]["start_seconds"]
        try:
            await page.wait_for_function("target=>Math.abs(document.querySelector('#video').currentTime-target)<0.2 && !document.querySelector('#video').seeking", arg=target)
        except Exception:
            print(json.dumps(await video.evaluate("v=>({currentTime:v.currentTime,seeking:v.seeking,readyState:v.readyState,networkState:v.networkState,error:v.error?{code:v.error.code,message:v.error.message}:null,seekable:Array.from({length:v.seekable.length},(_,i)=>[v.seekable.start(i),v.seekable.end(i)]),buffered:Array.from({length:v.buffered.length},(_,i)=>[v.buffered.start(i),v.buffered.end(i)])})"), indent=2))
            raise
        checks.append("Actual chapter seeking reaches the recorded facet evidence")
        await page.screenshot(path=str(output / "actual-reel.png"), full_page=True)
        for field in ("video_url", "report_url", "scene_manifest_url"):
            response = await page.request.get(urljoin(page.url, index[field]))
            assert response.ok
            payload = await response.body()
            expected = index["video"]["sha256"] if field == "video_url" else index["recording_report_sha256"] if field == "report_url" else index["scene_manifest_sha256"]
            assert hashlib.sha256(payload).hexdigest() == expected, field + " differs from its recorded hash"
        checks.append("Actual served clip, recording report and recorded scene match their hashes")
        assert "not accepted D0 or D1" in await page.locator(".boundary").inner_text()
        assert "exact currently selected" in await page.locator("#current-comparison").inner_text() or "archived checkpoint" in await page.locator("#current-comparison").inner_text()
        await page.set_viewport_size({"width": 390, "height": 844})
        assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth+2")
        await page.screenshot(path=str(output / "actual-mobile.png"), full_page=True)
        checks.append("Recording and evidence layout fits a 390px viewport")
        await page.close()

        archived = await browser.new_page()
        archived.on("pageerror", lambda error: errors.append(str(error)))
        await archived.route("**/assets/artsquad/scene.json", lambda route: route.fulfill(json={"run_id": "browser-comparison-test-only"}))
        await archived.goto(base_url + "/demo-reel.html")
        await archived.wait_for_function("document.querySelector('#current-comparison').textContent.includes('archived checkpoint')")
        checks.append("A different current manifest explicitly marks the real video as an archived checkpoint")
        await archived.close()

        unavailable = await browser.new_page()
        unavailable.on("pageerror", lambda error: errors.append(str(error)))
        await unavailable.route("**/assets/artsquad/demo/latest.json", lambda route: route.fulfill(status=503, body="Recording unavailable"))
        await unavailable.goto(base_url + "/demo-reel.html")
        await unavailable.wait_for_function("document.querySelector('#recording-status').textContent.includes('NO VERIFIED RECORDING')")
        assert await unavailable.locator("#video").is_hidden()
        assert await unavailable.locator("#empty").is_visible()
        assert await unavailable.locator("#download-video").is_hidden()
        await unavailable.screenshot(path=str(output / "no-recording.png"), full_page=True)
        checks.append("Missing recording index exposes an honest empty state without another clip")
        await browser.close()
    assert index_path.read_bytes() == index_bytes, "The recording index changed during its QA"
    report = {"checked_utc": datetime.now(timezone.utc).isoformat(), "base_url": base_url, "run_id": index["run_id"],
              "scene_manifest_sha256": index["scene_manifest_sha256"], "recording_index_sha256": hashlib.sha256(index_bytes).hexdigest(),
              "checks": checks, "page_errors": errors, "failed_http_responses": failed,
              "performance_certified": False, "milestone_acceptance_implied": False}
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    assert not errors and not failed, report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--output", type=Path, help="Separate QA directory, useful for an extracted portable bundle")
    args = parser.parse_args()
    asyncio.run(check(args.base_url.rstrip("/"), args.output))
