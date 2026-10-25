#!/usr/bin/env python3
"""Record an honest, repeatable 54-second tour of the actual local atlas.

This is a browser recording, not a renderer or reconstruction stage. It never
changes scene geometry, calibrated cameras, photographs, or milestone state.
Visible captions explain that disconnected diagnostic components are not D1.
The existing Playwright VP9 runtime is sufficient; no install is performed.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

from PIL import Image
from playwright.async_api import async_playwright

from ghostmap.qa.browser import textured_face_targets, wait_source_photo, wait_view

from ghostmap.paths import ROOT
CHAPTERS = (
    ("intro", 4, "Actual photographs. Actual computed artifacts. A research checkpoint—not accepted D1."),
    ("surface", 8, "A measured surface fragment. Missing geometry stays missing; scale is unverified."),
    ("cameras", 8, "Recorded camera poses/intrinsics and optional photo overlay. Training-view consistency is not independent validation."),
    ("wireframe", 6, "The actual recovered facets. Display modes do not improve or certify the geometry."),
    ("facet", 7, "Click a real facet: texture provenance and estimated stereo visibility are inspectable."),
    ("exploration", 6, "Inspect the component in its own coordinates. It is not a complete building."),
    ("separate", 6, "Another component, a separate coordinate system. No artificial campus alignment."),
    ("pipeline", 5, "The recorded pipeline and reports. Successful execution is not scientific acceptance."),
    ("boundary", 4, "D0 and D1 remain pending. Two reliably connected core buildings are still required."),
)
VIEWPORT = {"width": 1440, "height": 1080}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def local_base_url(value):
    parsed = urlparse(value)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Recording is local-preview only; use an unauthenticated loopback HTTP URL")
    return value.rstrip("/")


def scene_plan(scene):
    if scene.get("schema_version") != 1 or not scene.get("run_id"):
        raise ValueError("A versioned actual run manifest is required")
    components = scene.get("components", [])
    mesh_indices = [i for i, c in enumerate(components) if (c.get("mesh") or {}).get("url") and c.get("cameras")]
    if not mesh_indices:
        raise ValueError("No actual computed surface with recorded cameras is available to record")
    first = mesh_indices[0]
    surface = components[first]
    if not surface.get("face_evidence_url") or not surface.get("source_materials"):
        raise ValueError("The surface tour requires actual facet provenance and estimated visibility records")
    other = next((i for i, c in enumerate(components) if i != first and ((c.get("sparse") or {}).get("url") or (c.get("mesh") or {}).get("url"))), None)
    if other is None:
        raise ValueError("No separate computed component is available; do not imply a second building")
    if len(surface["cameras"]) < 2:
        raise ValueError("At least two recovered cameras are needed for the source-camera chapter")
    return {"surface_index": first, "separate_index": other,
            "surface_component_id": str(surface["id"]), "separate_component_id": str(components[other]["id"]),
            "chapters": [{"id": key, "seconds": seconds, "caption": caption} for key, seconds, caption in CHAPTERS],
            "requested_seconds": sum(item[1] for item in CHAPTERS)}


def existing_ffmpeg():
    system = shutil.which("ffmpeg")
    candidates = ([Path(system)] if system else []) + sorted((ROOT / ".cache/playwright").glob("ffmpeg-*/ffmpeg-linux"), reverse=True)
    for candidate in candidates:
        if candidate.is_file():
            result = subprocess.run([str(candidate), "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and "libvpx-vp9" in result.stdout:
                return candidate.resolve()
    raise RuntimeError("An existing VP9-capable FFmpeg is required; this script does not install dependencies")


def video_metadata(ffmpeg, path):
    result = subprocess.run([str(ffmpeg), "-hide_banner", "-i", str(path)], capture_output=True, text=True, timeout=20)
    diagnostic = result.stdout + result.stderr
    duration = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", diagnostic)
    dimensions = re.search(r"Video:.*?\b(\d{2,5})x(\d{2,5})\b", diagnostic)
    if not duration or not dimensions:
        raise ValueError("Cannot verify the actual recorded WebM duration/dimensions: " + diagnostic[-1500:])
    hours, minutes, seconds = map(float, duration.groups())
    return {"duration_seconds": hours * 3600 + minutes * 60 + seconds,
            "width": int(dimensions[1]), "height": int(dimensions[2])}


def find_caption_start(ffmpeg, raw_path, output, metadata):
    """Locate the actual captured disclosure, not an assumed wall-clock offset.

    Playwright's asynchronous screencast can lag the Python wall clock under
    CPU load. Before our fixed full-width caption exists, the outer bottom-left
    page background is light. Afterwards those pixels are always dark. Inspect
    actual decoded frames and keep the probes as evidence of the trim boundary.
    """
    probes = output / "trim-probes"
    probes.mkdir()
    observations = []

    def present(seconds):
        path = probes / f"probe-{len(observations):02d}.png"
        command = [str(ffmpeg), "-hide_banner", "-nostdin", "-ss", str(seconds), "-i", str(raw_path),
                   "-frames:v", "1", "-threads", "1", "-vf", f"crop=16:16:0:{metadata['height']-16}", str(path)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=30)
        if result.returncode or not path.is_file():
            raise RuntimeError("Could not inspect the actual raw video trim marker")
        with Image.open(path) as image:
            pixels = list(image.convert("RGB").getdata())
        # All sampled pixels are in the page's outer gutter, not its 3D canvas.
        # The dark caption has RGB~36/40/32; the prior gutter is light paper.
        average = [sum(pixel[channel] for pixel in pixels) / len(pixels) for channel in range(3)]
        found = all(channel < 80 for channel in average)
        observations.append({"time_seconds": seconds, "average_rgb": average, "caption_present": found, "frame": str(path.relative_to(output))})
        return found

    low, high = 0.0, metadata["duration_seconds"] - .2
    if present(low) or not present(high):
        raise ValueError("The raw video does not have the expected actual disclosure transition")
    for _ in range(11):
        mid = (low + high) / 2
        if present(mid): high = mid
        else: low = mid
    # Move one captured 25-fps frame forward so the final first frame visibly
    # includes the diagnostic disclosure, rather than racing its DOM paint.
    return high + .04, {"method": "decoded actual bottom-gutter disclosure transition", "before_seconds": low,
                         "after_seconds": high, "probes": observations}


def source_hashes(manifest_path):
    # Hash the viewer sources as well as the manifest. This guards a concurrent
    # rebuild during recording without exporting data, credentials or caches.
    paths = [manifest_path, *(ROOT / "dist" / name for name in ("artsquad.html", "artsquad.js", "artsquad.css", "artsquad-evidence.css"))]
    return {str(path.relative_to(ROOT)): sha256(path) for path in paths}


def bundle_local_preview(output, dist=ROOT / "dist"):
    """Copy one verified real capture into the local static preview, not online.

    The clip is versioned independently of scene.json: a later reconstruction
    must not make an older recording look as if it documented the newer run.
    """
    output, dist = Path(output).resolve(), Path(dist).resolve()
    report_path = output / "recording-report.json"
    report = json.loads(report_path.read_text())
    if report.get("status") != "recorded_diagnostic_only" or report.get("source_files_unchanged") is not True:
        raise ValueError("Only a successful unchanged-source diagnostic recording can enter the local reel")
    if any(report.get("claims", {}).values()):
        raise ValueError("The local diagnostic reel cannot elevate reconstruction, rights or public-release claims")
    video = report.get("video", {})
    names = ["recording-report.json", "scene-manifest.json", video.get("path"), *(capture.get("path") for capture in report.get("captures", []))]
    if any(not isinstance(name, str) or Path(name).name != name for name in names):
        raise ValueError("Recording artifacts must be confined basenames")
    if sha256(output / video["path"]) != video.get("sha256"):
        raise ValueError("The recorded video no longer matches its verified hash")
    scene_path = output / "scene-manifest.json"
    if sha256(scene_path) != report.get("scene_manifest_sha256"):
        raise ValueError("The captured scene manifest no longer matches its recorded hash")
    for capture in report.get("captures", []):
        if sha256(output / capture["path"]) != capture.get("sha256"):
            raise ValueError("A chapter screenshot no longer matches the recorded hash")
    version = hashlib.sha256(report_path.read_bytes()).hexdigest()
    target = dist / "assets/artsquad/demo" / version
    target.mkdir(parents=True, exist_ok=True)
    for name in names:
        source, destination = output / name, target / name
        if source.is_symlink() or not source.is_file():
            raise ValueError("Refusing missing or symlinked recording artifact")
        if destination.exists() and destination.read_bytes() != source.read_bytes():
            raise ValueError("Existing content-versioned recording differs; refusing overwrite")
        if not destination.exists():
            shutil.copyfile(source, destination)
    relative = target.relative_to(dist).as_posix() + "/"
    index = {"schema_version": 1, "status": "local_diagnostic_recording", "run_id": report["run_id"],
             "snapshot_id": report.get("snapshot_id"), "recorded_utc": report["created_utc"],
             "scene_manifest_sha256": report["scene_manifest_sha256"],
             "recording_report_sha256": version,
             "report_url": relative + "recording-report.json", "scene_manifest_url": relative + "scene-manifest.json",
             "video_url": relative + video["path"], "poster_url": relative + "surface.png",
             "video": video, "chapters": report["chapters"],
             "captures": [{**capture, "url": relative + capture["path"]} for capture in report.get("captures", [])],
             "notice": "Local draft only. Recorded disconnected diagnostics, not accepted D0/D1 or an accuracy/performance/rights certification."}
    index_path = dist / "assets/artsquad/demo/latest.json"
    index_path.write_text(json.dumps(index, indent=2) + "\n")
    return index_path


async def caption(page, key, text):
    await page.evaluate("""({key,text}) => {
      let panel=document.querySelector('#ghostmap-recording-caption');
      if(!panel){panel=document.createElement('aside');panel.id='ghostmap-recording-caption';
        panel.setAttribute('aria-label','Recording chapter and scientific limitations');
        Object.assign(panel.style,{position:'fixed',bottom:'0',left:'0',right:'0',zIndex:'1000',
          background:'#242820f5',color:'#f1eee7',padding:'14px 4%',borderTop:'2px solid #b64a40',
          font:'14px/1.5 Arial, sans-serif',pointerEvents:'none'});document.body.append(panel);}
      panel.replaceChildren();const title=document.createElement('strong');
      title.textContent='GHOSTMAP · DIAGNOSTIC / NOT D1 · '+key.toUpperCase()+'  ';title.style.fontSize='11px';
      panel.append(title,document.createTextNode(text));
    }""", {"key": key, "text": text})


async def scroll_to(page, selector, offset=14):
    await page.locator(selector).evaluate("(node,offset)=>window.scrollTo({top:Math.max(0,node.getBoundingClientRect().top+scrollY-offset),behavior:'instant'})", offset)


async def pick_actual_facet(page, targets):
    canvas = page.locator("#viewport canvas")
    for target in targets[:30]:
        await page.select_option("#source-select", str(target["source_index"]))
        await wait_source_photo(page)
        await page.locator("#snap-camera").click()
        box = await canvas.bounding_box()
        scale = min(box["width"] / target["width"], box["height"] / target["height"])
        x = (box["width"] - scale * target["width"]) / 2 + scale * target["u"]
        y = (box["height"] - scale * target["height"]) / 2 + scale * target["v"]
        await canvas.click(position={"x": x, "y": y})
        if "texture provenance only" in await page.locator("#evidence-copy").inner_text():
            await page.wait_for_function("document.querySelector('#surface-evidence').dataset.state === 'loaded'", timeout=15000)
            assert "CALIBRATED CAMERA VIEW" in await page.locator("#load-status").inner_text()
            return {"face_index": int(await page.locator("#surface-evidence").get_attribute("data-face-index")),
                    "texture_material": target["material"],
                    "source_camera_index": target["source_index"],
                    "visible_source_camera_names": await page.locator("#surface-support-photos button").evaluate_all("nodes=>nodes.map(n=>n.dataset.cameraName)")}
    raise ValueError("No actually projected textured facet could be selected; refusing a staged evidence claim")


async def record(args):
    base_url = local_base_url(args.base_url)
    manifest_path = ROOT / "dist/assets/artsquad/scene.json"
    scene_bytes = manifest_path.read_bytes()
    scene = json.loads(scene_bytes)
    plan = scene_plan(scene)
    before = source_hashes(manifest_path)
    manifest_sha = hashlib.sha256(scene_bytes).hexdigest()
    ffmpeg = existing_ffmpeg()
    output = args.output or ROOT / "artifacts/demo" / str(scene["run_id"]) / manifest_sha[:16] / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = output.resolve()
    if not output.is_relative_to(ROOT) or output.exists():
        raise ValueError("Use a new project-local output directory; existing recordings are never overwritten")
    output.mkdir(parents=True)
    report = {"schema_version": 1, "status": "recording", "created_utc": datetime.now(timezone.utc).isoformat(),
              "base_url": base_url, "run_id": scene["run_id"], "snapshot_id": scene.get("snapshot_id"),
              "scene_manifest_sha256": manifest_sha, "viewer_source_sha256": before,
              "plan": plan, "viewport": VIEWPORT, "reduced_motion": not args.allow_motion,
              "caption_overlay": "Text-only disclosure inside the recorded browser; no geometry, photographs, camera poses or intrinsics changed.",
              "rendering": "Headless Chromium software WebGL; actual browser capture, no frame interpolation.",
              "claims": {"d0_passed": False, "d1_passed": False, "connected_core_buildings_verified": False,
                         "geometry_accuracy_certified": False, "real_device_performance_certified": False,
                         "public_rights_review_complete": False, "https_publication_verified": False},
              "page_errors": [], "failed_http_responses": [], "chapters": []}
    (output / "scene-manifest.json").write_bytes(scene_bytes)
    targets = textured_face_targets(scene["components"][plan["surface_index"]])
    if not targets:
        raise ValueError("The actual surface has no projectable source-camera facets")
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
            context = await browser.new_context(viewport=VIEWPORT, device_scale_factor=1,
                                                reduced_motion="no-preference" if args.allow_motion else "reduce",
                                                record_video_dir=str(output / "raw"), record_video_size=VIEWPORT)
            page = await context.new_page()
            raw_started = time.monotonic()
            video = page.video
            page.on("pageerror", lambda error: report["page_errors"].append(str(error)))
            page.on("response", lambda response: report["failed_http_responses"].append({"status": response.status, "url": response.url}) if response.status >= 400 else None)
            served = await page.request.get(urljoin(base_url + "/", "assets/artsquad/scene.json"))
            if not served.ok or await served.body() != scene_bytes:
                raise ValueError("The serving preview is not the same frozen scene manifest as the local package")
            await page.goto(base_url + "/artsquad.html", wait_until="domcontentloaded")
            await wait_view(page)
            await page.select_option("#component-select", str(plan["surface_index"]))
            await wait_view(page)
            assert await page.locator("html").get_attribute("data-viewer-state") == "mesh"
            # Warm the real facet index before the timed segment; the recorded
            # chapter repeats the actual click, rather than inserting a still.
            await scroll_to(page, "#explorer")
            actual_pick = await pick_actual_facet(page, targets)
            face_response = await page.request.get(urljoin(page.url, scene["components"][plan["surface_index"]]["face_evidence_url"]))
            face = (await face_response.json())["faces"][actual_pick["face_index"]]
            assert sorted(Path(name).name for name in actual_pick["visible_source_camera_names"]) == sorted(face["common_images"])
            report["picked_facet"] = actual_pick
            await scroll_to(page, ".site-header", 0)
            await caption(page, "intro", CHAPTERS[0][2])
            tour_started = time.monotonic()
            deadline = tour_started
            cameras = scene["components"][plan["surface_index"]]["cameras"]
            for key, seconds, text in CHAPTERS:
                await caption(page, key, text)
                started = time.monotonic()
                detail = {}
                if key == "surface":
                    await scroll_to(page, "#explorer")
                    await page.locator('[data-display="texture"]').click()
                    await page.select_option("#source-select", str(actual_pick["source_camera_index"]))
                    await page.locator("#snap-camera").click()
                elif key == "cameras":
                    for index in [actual_pick["source_camera_index"], (actual_pick["source_camera_index"] + 1) % len(cameras)]:
                        await page.select_option("#source-select", str(index))
                        await wait_source_photo(page)
                        await page.locator("#snap-camera").click()
                        await page.wait_for_timeout(2100)
                    detail["camera_indices"] = [actual_pick["source_camera_index"], (actual_pick["source_camera_index"] + 1) % len(cameras)]
                    if await page.locator("#photo-overlay-toggle").count():
                        await page.locator("#photo-overlay-toggle").check()
                        await page.wait_for_function("() => {const image=document.querySelector('#registered-photo');return image && image.complete && image.naturalWidth>0 && !document.querySelector('#photo-overlay').hidden;}")
                        assert "not independent geometric validation" in await page.locator("#photo-overlay-note").inner_text()
                        await page.wait_for_timeout(1400)
                        await page.locator("#photo-overlay-toggle").uncheck()
                        detail["registered_photo_overlay_shown"] = True
                        detail["overlay_is_independent_validation"] = False
                elif key == "wireframe":
                    await page.locator('[data-display="wire"]').click()
                    await page.wait_for_timeout(2400)
                    await page.locator('[data-display="texture"]').click()
                elif key == "facet":
                    detail = await pick_actual_facet(page, targets)
                    await scroll_to(page, ".evidence-detail", 470)
                elif key == "exploration":
                    await scroll_to(page, "#explorer")
                    await page.locator("#show-cameras").check()
                    await page.locator("#fit-scene").click()
                    if args.allow_motion:
                        await page.locator("#tour-toggle").click()
                    else:
                        assert await page.locator("#tour-toggle").is_disabled()
                    detail["automatic_orbit_enabled"] = args.allow_motion
                elif key == "separate":
                    if args.allow_motion:
                        await page.locator("#tour-toggle").click()
                    await page.select_option("#component-select", str(plan["separate_index"]))
                    await wait_view(page)
                    await page.locator("#fit-scene").click()
                    detail["component_id"] = plan["separate_component_id"]
                elif key == "pipeline":
                    await scroll_to(page, "#pipeline", 15)
                    detail["rendered_stage_count"] = await page.locator("#pipeline-rows tr").count()
                    assert detail["rendered_stage_count"] == len(scene.get("pipeline", []))
                elif key == "boundary":
                    await scroll_to(page, "#milestones", 25)
                await page.screenshot(path=str(output / (key + ".png")))
                deadline += seconds
                remaining = deadline - time.monotonic()
                if remaining > 0:
                    await page.wait_for_timeout(remaining * 1000)
                report["chapters"].append({"id": key, "start_seconds": started - tour_started,
                                           "end_seconds": time.monotonic() - tour_started,
                                           "scheduled_seconds": seconds, "detail": detail})
            report["tour_wall_seconds"] = time.monotonic() - tour_started
            report["raw_trim_wall_estimate_seconds"] = max(0, tour_started - raw_started)
            await context.close()
            raw_path = Path(await video.path())
            await browser.close()
        if source_hashes(manifest_path) != before:
            raise ValueError("The scene/viewer changed during recording; preserve this attempt and rerun the frozen final package")
        if report["page_errors"] or report["failed_http_responses"]:
            raise ValueError("The actual recording had browser or HTTP errors")
        if not 45 <= report["tour_wall_seconds"] <= 60:
            raise ValueError("The actual tour exceeded the 45–60 second delivery window")
        report["raw_video"] = {"path": str(raw_path.relative_to(output)), "sha256": sha256(raw_path), **video_metadata(ffmpeg, raw_path)}
        report["raw_trim_start_seconds"], report["actual_trim_marker"] = find_caption_start(ffmpeg, raw_path, output, report["raw_video"])
        video_path = output / "ghostmap-diagnostic-tour.webm"
        command = [str(ffmpeg), "-hide_banner", "-nostdin", "-ss", str(report["raw_trim_start_seconds"]),
                   "-i", str(raw_path), "-t", str(plan["requested_seconds"]), "-an", "-c:v", "libvpx-vp9",
                   "-threads", "2", "-deadline", "realtime", "-cpu-used", "8", "-row-mt", "1",
                   "-crf", "32", "-b:v", "0", str(video_path)]
        encoding = subprocess.run(command, capture_output=True, text=True, timeout=180)
        (output / "encode.log").write_text(encoding.stdout + encoding.stderr)
        if encoding.returncode:
            raise RuntimeError("Existing FFmpeg could not finalize the actual browser recording; see encode.log")
        metadata = video_metadata(ffmpeg, video_path)
        if not 45 <= metadata["duration_seconds"] <= 60 or (metadata["width"], metadata["height"]) != (VIEWPORT["width"], VIEWPORT["height"]):
            raise ValueError("Encoded browser video failed actual duration/dimensions verification")
        first_frame = output / "verified-first-frame.png"
        decoded = subprocess.run([str(ffmpeg), "-hide_banner", "-nostdin", "-i", str(video_path),
                                  "-frames:v", "1", "-threads", "1", str(first_frame)], capture_output=True, text=True, timeout=20)
        if decoded.returncode or not first_frame.is_file():
            raise ValueError("Cannot decode the final actual WebM first frame")
        with Image.open(first_frame) as image:
            corner = list(image.convert("RGB").crop((0, image.height-16, 16, image.height)).getdata())
        if not all(sum(pixel[channel] for pixel in corner) / len(corner) < 80 for channel in range(3)):
            raise ValueError("The final video's first frame lacks the visible diagnostic disclosure")
        report.update(status="recorded_diagnostic_only", video={"path": video_path.name, "sha256": sha256(video_path), **metadata},
                      video_verification={"first_frame_disclosure_present": True, "first_frame": first_frame.name, "first_frame_sha256": sha256(first_frame)},
                      source_files_unchanged=True,
                      captures=[{"path": path.name, "sha256": sha256(path)} for path in sorted(output.glob("*.png"))])
    except Exception as error:
        report.update(status="error", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        (output / "recording-report.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({"status": report["status"], "output": str(output), "video": report.get("video"), "error": report.get("error")}, indent=2))
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--output", type=Path, help="New project-local directory; never overwrite an existing recording")
    parser.add_argument("--allow-motion", action="store_true", help="Explicitly allow the six-second native orbit preview; default respects reduced motion")
    parser.add_argument("--bundle-local-preview", action="store_true", help="Also copy this verified clip to the existing local static preview; does not publish externally")
    parser.add_argument("--bundle-existing", type=Path, help="Validate and bundle an already completed recording directory without re-recording")
    args = parser.parse_args()
    if args.bundle_existing:
        print(bundle_local_preview(args.bundle_existing))
    else:
        output = asyncio.run(record(args))
        if args.bundle_local_preview:
            print(bundle_local_preview(output))


if __name__ == "__main__":
    main()
