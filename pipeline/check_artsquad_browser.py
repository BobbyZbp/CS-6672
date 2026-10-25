#!/usr/bin/env python3
"""Browser regression for the real atlas and explicit no-data/error states.

Uses software WebGL for functional checks, not GPU performance certification.
No reconstruction fixture is fabricated. Empty-state metadata is intercepted in
the browser only; actual artifacts, when present, are loaded from the server.
"""
import argparse
import asyncio
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse, urljoin

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/browser-qa/artsquad"


async def wait_view(page):
    await page.wait_for_function(
        "['mesh','sparse','empty','error'].includes(document.documentElement.dataset.viewerState)",
        timeout=120000,
    )
    await page.wait_for_load_state("networkidle")


async def wait_source_photo(page):
    # A cached image selection can reach networkidle before its load/decode
    # event. Check the visible decoded image itself, not just network activity.
    await page.wait_for_function("""() => {
        const image = document.querySelector('#source-photo');
        return image && image.complete && image.naturalWidth > 0 && !image.hidden;
    }""", timeout=15000)


async def check_registered_photo_overlay(page, component):
    index = int(await page.locator('#source-select').input_value())
    expected_photo = urljoin(page.url, component['cameras'][index]['photo'])
    toggle = page.locator('#photo-overlay-toggle')
    assert await toggle.is_enabled()
    before = await page.locator('#viewport').screenshot()
    await toggle.check()
    await page.wait_for_function("""() => {
        const image = document.querySelector('#registered-photo');
        return !document.querySelector('#photo-overlay').hidden && image.complete && image.naturalWidth > 0;
    }""", timeout=15000)
    assert await page.locator('#registered-photo').get_attribute('src') == expected_photo
    after = await page.locator('#viewport').screenshot()
    assert hashlib.sha256(before).digest() != hashlib.sha256(after).digest(), 'Registered photograph overlay did not alter displayed pixels'
    await page.locator('#photo-overlay-opacity').fill('75')
    assert await page.locator('#photo-overlay-value').inner_text() == '75%'
    assert await page.locator('#photo-overlay').evaluate("panel => getComputedStyle(panel).opacity") == '0.75'
    await page.locator('#fit-scene').click()
    assert await page.locator('#photo-overlay').is_hidden(), 'A training photograph stayed over a free-camera projection'
    assert await toggle.is_disabled()
    await page.locator('#snap-camera').click()
    await toggle.uncheck()
    return 'Registered-photo overlay uses selected actual camera photo and disappears in free-camera views'


async def artifact_links(page, record, mapping):
    """Optional download/report links must not survive an unsupported selection."""
    checked = []
    for field, selector in mapping.items():
        anchor = page.locator(selector)
        if record.get(field):
            assert await anchor.is_visible(), field + " link is unexpectedly hidden"
            url = await anchor.get_attribute("href")
            assert url and url.startswith(("http://", "https://")), field + " has no safe artifact URL"
            response = await page.request.head(url)
            assert response.ok, f"{field}: HTTP {response.status} {url}"
            checked.append(field)
        else:
            assert await anchor.is_hidden(), field + " leaked from another component"
    return checked


def textured_face_targets(component):
    """Project actual OBJ facet centroids into their actual texture cameras.

    Tiny recovered patches can occupy far less than a grid cell. Deriving a
    click from measured triangles tests real picking without inventing geometry
    or waiving the provenance assertion for small components.
    """
    mesh_url = component.get("mesh", {}).get("url")
    if not mesh_url:
        return []
    path = (ROOT / "dist" / unquote(urlparse(mesh_url).path).lstrip("/")).resolve()
    if not path.is_relative_to((ROOT / "dist").resolve()):
        raise ValueError("Mesh source escapes the local dist folder")
    cameras = {str(view["id"]): (index, view) for index, view in enumerate(component.get("cameras", []))}
    source_materials = component.get("source_materials") or {}
    vertices, targets, material = [], [], None
    for line in path.read_text().splitlines():
        if line.startswith("v "):
            vertices.append(tuple(float(value) for value in line.split()[1:4]))
        elif line.startswith("usemtl "):
            material = line.split(maxsplit=1)[1].strip()
        elif line.startswith("f ") and str(source_materials.get(material)) in cameras:
            source_index, view = cameras[str(source_materials[material])]
            indices = [int(value.split("/")[0]) for value in line.split()[1:]]
            polygon = [vertices[index - 1 if index > 0 else len(vertices) + index] for index in indices]
            matrix, intrinsics = view["world_matrix"], view["K"]

            def project(point):
                delta = [point[axis] - matrix[axis][3] for axis in range(3)]
                local = [sum(matrix[axis][column] * delta[axis] for axis in range(3)) for column in range(3)]
                if local[2] >= -1e-8:
                    return None
                normalized = [local[0] / -local[2], -local[1] / -local[2], 1]
                return tuple(sum(intrinsics[row][column] * normalized[column] for column in range(3)) for row in range(2))

            for corner in range(1, len(polygon) - 1):
                triangle = [polygon[0], polygon[corner], polygon[corner + 1]]
                projected = [project(point) for point in triangle]
                center = project(tuple(sum(point[axis] for point in triangle) / 3 for axis in range(3)))
                if not center or not all(projected) or not (2 < center[0] < view["width"] - 2 and 2 < center[1] < view["height"] - 2):
                    continue
                a, b, c = projected
                area = abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) / 2
                if area > 0:
                    targets.append({"source_index": source_index, "u": center[0], "v": center[1], "width": view["width"], "height": view["height"], "area": area, "material": material})
    return sorted(targets, key=lambda target: -target["area"])


async def check_facet_provenance(page, component):
    canvas = page.locator("#viewport canvas")
    box = await canvas.bounding_box()
    targets = textured_face_targets(component)
    assert targets, "Measured textured component has no projectable texture-camera facets"
    for target in targets[:40]:
        await page.select_option("#source-select", str(target["source_index"]))
        await page.locator("#snap-camera").click()
        scale = min(box["width"] / target["width"], box["height"] / target["height"])
        x = (box["width"] - scale * target["width"]) / 2 + scale * target["u"]
        y = (box["height"] - scale * target["height"]) / 2 + scale * target["v"]
        await canvas.click(position={"x": x, "y": y})
        if "texture provenance only" in await page.locator("#evidence-copy").inner_text():
            assert "CALIBRATED CAMERA VIEW" in await page.locator("#load-status").inner_text(), "A stationary surface click changed the calibrated camera projection"
            await page.wait_for_load_state("networkidle")
            await wait_source_photo(page)
            texture_source = await page.locator('#source-name').inner_text()
            if component.get('face_evidence_url'):
                await page.wait_for_function("document.querySelector('#surface-evidence').dataset.state === 'loaded'", timeout=15000)
                face_index = int(await page.locator('#surface-evidence').get_attribute('data-face-index'))
                response = await page.request.get(urljoin(page.url, component['face_evidence_url']))
                assert response.ok
                record = (await response.json())['faces'][face_index]
                buttons = page.locator('#surface-support-photos button')
                names = await buttons.evaluate_all("buttons => buttons.map(b => b.dataset.cameraName.split('/').pop()).sort()")
                assert names == sorted(record['common_images']), 'Displayed facet support does not match actual indexed source visibility'
                assert len(record['common_recorded_source_families']) >= 2
                await buttons.first.click()
                await page.wait_for_load_state('networkidle')
                await wait_source_photo(page)
                selected_index = int(await page.locator('#source-select').input_value())
                expected_photo = urljoin(page.url, component['cameras'][selected_index]['photo'])
                assert await page.locator('#source-photo').get_attribute('src') == expected_photo
                assert 'estimated stereo visibility' in await page.locator('#evidence-copy').inner_text()
            await page.screenshot(path=str(OUT / (component["id"] + "-calibrated.png")), full_page=True)
            await canvas.screenshot(path=str(OUT / (component["id"] + "-calibrated-canvas.png")))
            await page.locator("#source-photo").screenshot(path=str(OUT / (component["id"] + "-texture-source.png")))
            return {"facet_texture_provenance": component["id"], "target_material": target["material"], "selected_source": texture_source, "stationary_click_keeps_calibration": True, "per_face_visibility_index_checked": bool(component.get('face_evidence_url'))}
    await page.screenshot(path=str(OUT / (component["id"] + "-pick-failure.png")), full_page=True)
    raise AssertionError("No actual projected textured facet could be linked to its source camera")


async def main(base_url):
    OUT.mkdir(parents=True, exist_ok=True)
    checks, errors, failed = [], [], []
    manifest_file = ROOT / "dist/assets/artsquad/scene.json"
    manifest_bytes = manifest_file.read_bytes() if manifest_file.exists() else None
    manifest = json.loads(manifest_bytes) if manifest_bytes is not None else None
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
        )
        # No-data state must be useful without silently inserting the old tower.
        empty_page = await browser.new_page(viewport={"width": 1440, "height": 1100})
        empty_page.on("pageerror", lambda error: errors.append(str(error)))
        empty_manifest = {
            "schema_version": 1, "status": "not_ready", "run_id": "browser-empty-state-only",
            "data": {"downloaded": 0, "scene_candidates": 0, "train_images": 0, "test_images": 0, "by_target": []},
            "components": [], "milestones": {},
            "limitations": ["Browser-only no-data regression; not a reconstruction result."],
        }
        await empty_page.route("**/assets/artsquad/scene.json", lambda route: route.fulfill(json=empty_manifest))
        await empty_page.goto(base_url + "/artsquad.html", wait_until="domcontentloaded")
        await wait_view(empty_page)
        assert await empty_page.locator("html").get_attribute("data-viewer-state") == "empty"
        assert await empty_page.locator("#empty-state").is_visible()
        assert await empty_page.locator("#component-select").is_disabled()
        assert "No multi-building reconstruction" in await empty_page.locator("#empty-title").inner_text()
        await artifact_links(empty_page, {}, {"source_code_url": "#source-code-link", "project_contract_url": "#project-contract-link", "model_download_url": "#component-model-download", "holdout_report_url": "#component-holdout", "dense_support_report_url": "#component-dense-support"})
        await empty_page.screenshot(path=str(OUT / "no-data.png"), full_page=True)
        checks.append("No-data state is explicit; no substitute building or positive milestone claim")
        await empty_page.set_viewport_size({"width": 390, "height": 844})
        await empty_page.wait_for_timeout(100)
        assert await empty_page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2")
        await empty_page.screenshot(path=str(OUT / "no-data-mobile.png"), full_page=True)
        checks.append("No-data layout fits a 390px viewport")
        await empty_page.close()

        if manifest:
            page = await browser.new_page(viewport={"width": 1440, "height": 1100}, device_scale_factor=1)
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("response", lambda response: failed.append(f"{response.status} {response.url}") if response.status >= 400 else None)
            await page.goto(base_url + "/artsquad.html", wait_until="domcontentloaded")
            await wait_view(page)
            assert await page.locator("html").get_attribute("data-manifest-state") == "loaded"
            assert await page.locator("#data-downloaded").inner_text() == f"{manifest['data']['downloaded']:,}"
            checks.append("Actual run manifest and source counts load")
            if any(component.get('mesh') for component in manifest.get('components', [])):
                assert manifest['components'][0].get('mesh'), 'Default component must show an available measured surface, not collection-label-ranked sparse points'
                assert await page.locator('html').get_attribute('data-viewer-state') == 'mesh'
                checks.append('Available measured surface is the default, without implying building acceptance')
            if manifest.get('pipeline'):
                assert await page.locator('#pipeline-rows tr').count() == len(manifest['pipeline'])
                checks.append('All recorded pipeline stages are rendered')
                await artifact_links(page, manifest, {'pipeline_report_url': '#pipeline-report-link'})
            manifest_links = await artifact_links(page, manifest, {"source_code_url": "#source-code-link", "project_contract_url": "#project-contract-link"})
            if manifest_links:
                checks.append({"public_source_contract_links": manifest_links})
            for index, component in enumerate(manifest.get("components", [])):
                await page.select_option("#component-select", str(index))
                await wait_view(page)
                expected = "mesh" if (component.get("mesh") or {}).get("url") else "sparse" if (component.get("sparse") or {}).get("url") else "empty"
                assert await page.locator("html").get_attribute("data-viewer-state") == expected, await page.locator("#asset-error").inner_text()
                assert not await page.locator("#asset-error").is_visible()
                component_links = await artifact_links(page, component, {"model_download_url": "#component-model-download", "holdout_report_url": "#component-holdout", "dense_support_report_url": "#component-dense-support", "face_evidence_url": "#component-face-evidence"})
                if component_links:
                    checks.append({"component_report_download_links": component_links})
                checks.append({"real_component": component["id"], "artifact_type": expected})
                if expected == "mesh":
                    before = await page.locator("#viewport canvas").screenshot()
                    await page.locator('[data-display="wire"]').click()
                    await page.wait_for_timeout(150)
                    after = await page.locator("#viewport canvas").screenshot()
                    assert hashlib.sha256(before).digest() != hashlib.sha256(after).digest(), "Display mode did not alter visible pixels"
                    await page.locator('[data-display="texture"]').click()
                    checks.append("Mesh wireframe changes rendered pixels")
                cameras = component.get("cameras", [])
                if cameras:
                    source_index = min(1, len(cameras) - 1)
                    await page.select_option("#source-select", str(source_index))
                    await page.wait_for_load_state("networkidle")
                    if cameras[source_index].get("photo"):
                        await wait_source_photo(page)
                        checks.append("Real source photograph is displayed")
                    if not await page.locator("#snap-camera").is_disabled():
                        await page.locator("#snap-camera").click()
                        assert "CALIBRATED CAMERA VIEW" in await page.locator("#load-status").inner_text()
                        checks.append("Recorded intrinsics and camera pose can be selected")
                        if expected == 'mesh':
                            checks.append(await check_registered_photo_overlay(page, component))
                if expected == "mesh" and any(value is not None for value in component.get("source_materials", {}).values()):
                    checks.append(await check_facet_provenance(page, component))
                await page.locator("#show-cameras").check()
                if expected != "empty":
                    await page.locator("#fit-scene").click()
                await page.screenshot(path=str(OUT / (component["id"] + ".png")), full_page=True)
                await page.locator("#viewport canvas").screenshot(path=str(OUT / (component["id"] + "-fit-canvas.png")))
            await page.set_viewport_size({"width": 390, "height": 844})
            await page.wait_for_timeout(150)
            assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2"), "Mobile layout overflows horizontally"
            await page.screenshot(path=str(OUT / "actual-mobile.png"), full_page=True)
            checks.append("Actual run layout fits a 390px viewport")
            await page.close()

        unavailable = await browser.new_page()
        unavailable.on("pageerror", lambda error: errors.append(str(error)))
        await unavailable.route("**/assets/artsquad/scene.json", lambda route: route.fulfill(status=503, body="unavailable"))
        await unavailable.goto(base_url + "/artsquad.html", wait_until="domcontentloaded")
        await unavailable.wait_for_function("document.documentElement.dataset.manifestState === 'error'")
        assert await unavailable.locator("#asset-error").is_visible()
        assert "unavailable" in await unavailable.locator("#empty-title").inner_text()
        checks.append("Unavailable manifest produces an honest visible error")
        await browser.close()

    if manifest_bytes is not None:
        assert manifest_file.read_bytes() == manifest_bytes, 'Scene manifest changed during browser QA; rerun against one frozen package'
    report = {"checked_utc": datetime.now(timezone.utc).isoformat(), "base_url": base_url,
              "run_id": (manifest or {}).get('run_id'), "snapshot_id": (manifest or {}).get('snapshot_id'),
              "scene_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest() if manifest_bytes is not None else None,
              "checks": checks, "actual_manifest_present": bool(manifest), "page_errors": errors, "failed_http_responses": failed, "performance_certified": False, "rendering": "headless Chromium software WebGL functional QA"}
    (OUT / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    assert not errors and not failed, report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    asyncio.run(main(parser.parse_args().base_url.rstrip("/")))
