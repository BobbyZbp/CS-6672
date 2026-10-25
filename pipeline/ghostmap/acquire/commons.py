#!/usr/bin/env python3
"""Download auditable, permissively licensed GhostMap inputs from Commons.

The queries cover the vanished target plus stable Uris/McGraw bridge subjects.
Every accepted image retains its discovery query, source URL, license string,
metadata, and SHA-256 digest in a machine-readable manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path

from PIL import Image


API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "GhostMap-Research/0.1 (CS6672 academic reconstruction; contact via repository)"
SETS = {
    "historical": {
        "categories": ["Postcards of Boardman Hall"],
        "searches": [
            'intitle:"Boardman Hall" Cornell',
            'intitle:"Uris Library" Cornell',
            'intitle:"McGraw Tower" Cornell',
        ],
        "limit": 60,
        "era": "historical",
    },
    "modern": {
        "categories": ["Uris Library (Cornell University)"],
        "searches": [
            'intitle:"Uris Library" Cornell',
            'intitle:"McGraw Tower" Cornell',
        ],
        "limit": 50,
        "era": "modern",
    },
}
LICENSE_ALLOWLIST = (
    "public domain",
    "cc0",
    "cc by",
    "cc-by",
    "cc by-sa",
    "cc-by-sa",
)
HISTORICAL_HINT = re.compile(r"(?:postcard|\b18\d{2}\b|\b19[0-6]\d\b)", re.I)


def fetch_json(params: dict[str, object]) -> dict:
    query = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{API}?{query}", headers={"User-Agent": USER_AGENT})
    for attempt in range(7):
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code not in {429, 500, 502, 503, 504} or attempt == 6:
                raise
            retry_after = error.headers.get("Retry-After", "")
            requested_delay = float(retry_after) if retry_after.isdigit() else 0
            delay = max(requested_delay, min(60, 3 * 2**attempt))
            print(f"API rate limited ({error.code}); retrying in {delay:.0f}s", flush=True)
            time.sleep(delay)
    raise RuntimeError("API retries exhausted")


def category_files(category: str) -> list[dict]:
    pages: list[dict] = []
    cont: dict[str, object] = {}
    while True:
        payload = fetch_json(
            {
                "action": "query",
                "generator": "categorymembers",
                "gcmtitle": f"Category:{category}",
                "gcmtype": "file",
                "gcmlimit": "max",
                "prop": "imageinfo",
                "iiprop": "url|size|mime|extmetadata",
                # 1024 is a pre-generated Commons thumbnail size. Avoiding
                # arbitrary widths prevents expensive on-demand resizes/429s.
                "iiurlwidth": 1024,
                "format": "json",
                "formatversion": 2,
                **cont,
            }
        )
        pages.extend(payload.get("query", {}).get("pages", []))
        if "continue" not in payload:
            break
        cont = payload["continue"]
    return hydrate_missing_imageinfo(pages)


def hydrate_missing_imageinfo(pages: list[dict]) -> list[dict]:
    """Refetch generator rows that Commons occasionally returns half-filled."""
    missing = [int(page["pageid"]) for page in pages if not page.get("imageinfo")]
    replacements: dict[int, dict] = {}
    for offset in range(0, len(missing), 50):
        payload = fetch_json(
            {
                "action": "query",
                "pageids": "|".join(map(str, missing[offset : offset + 50])),
                "prop": "imageinfo",
                "iiprop": "url|size|mime|extmetadata",
                "iiurlwidth": 1024,
                "format": "json",
                "formatversion": 2,
            }
        )
        replacements.update(
            {int(page["pageid"]): page for page in payload.get("query", {}).get("pages", [])}
        )
    return [replacements.get(int(page["pageid"]), page) for page in pages]


def search_files(query: str) -> list[dict]:
    """Run a strict Commons file-title search with the same metadata fields."""
    pages: list[dict] = []
    cont: dict[str, object] = {}
    while True:
        payload = fetch_json(
            {
                "action": "query",
                "generator": "search",
                "gsrsearch": query,
                "gsrnamespace": 6,
                "gsrlimit": "max",
                "prop": "imageinfo",
                "iiprop": "url|size|mime|extmetadata",
                "iiurlwidth": 1024,
                "format": "json",
                "formatversion": 2,
                **cont,
            }
        )
        pages.extend(payload.get("query", {}).get("pages", []))
        if "continue" not in payload:
            break
        cont = payload["continue"]
    return hydrate_missing_imageinfo(pages)


def plain(value: object) -> str:
    text = html.unescape(str(value or ""))
    return re.sub(r"<[^>]+>", "", text).strip()


def metadata_value(metadata: dict, key: str) -> str:
    return plain(metadata.get(key, {}).get("value", ""))


def is_allowed(page: dict, era: str) -> tuple[bool, str]:
    info = page.get("imageinfo", [{}])[0]
    metadata = info.get("extmetadata", {})
    mime = info.get("mime", "")
    if mime not in {"image/jpeg", "image/png"}:
        return False, f"unsupported mime: {mime}"
    if min(int(info.get("width", 0)), int(info.get("height", 0))) < 600:
        return False, "short side below 600 px"

    license_text = " ".join(
        [metadata_value(metadata, "LicenseShortName"), metadata_value(metadata, "UsageTerms")]
    ).lower()
    if not any(token in license_text for token in LICENSE_ALLOWLIST):
        return False, f"license not allowlisted: {license_text or 'missing'}"

    evidence = " ".join(
        [
            page.get("title", ""),
            metadata_value(metadata, "Categories"),
            metadata_value(metadata, "DateTimeOriginal"),
        ]
    )
    historical_marker = bool(HISTORICAL_HINT.search(evidence))
    if era == "modern":
        if historical_marker:
            return False, "historical date/category marker in modern anchor set"
    elif not historical_marker:
        return False, "no machine-readable historical date/category marker"
    return True, "accepted"


def safe_name(page: dict, mime: str) -> str:
    stem = re.sub(r"^File:", "", page.get("title", ""), flags=re.I)
    stem = re.sub(r"\.[A-Za-z0-9]{2,5}$", "", stem)
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("_.")[:110]
    suffix = ".png" if mime == "image/png" else ".jpg"
    return f"{int(page['pageid'])}_{stem}{suffix}"


def difference_hash(path: Path) -> str:
    with Image.open(path) as image:
        resized = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
        values = list(resized.getdata())
    bits = 0
    for row in range(8):
        for column in range(8):
            left = values[row * 9 + column]
            right = values[row * 9 + column + 1]
            bits = (bits << 1) | int(left > right)
    return f"{bits:016x}"


def download(url: str, path: Path) -> tuple[str, int]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    temporary = path.with_suffix(path.suffix + ".part")
    for attempt in range(7):
        digest = hashlib.sha256()
        size = 0
        try:
            with urllib.request.urlopen(req, timeout=120) as response, temporary.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
            temporary.replace(path)
            return digest.hexdigest(), size
        except urllib.error.HTTPError as error:
            temporary.unlink(missing_ok=True)
            if error.code not in {429, 500, 502, 503, 504} or attempt == 6:
                raise
            retry_after = error.headers.get("Retry-After", "")
            requested_delay = float(retry_after) if retry_after.isdigit() else 0
            delay = max(requested_delay, min(60, 3 * 2**attempt))
            print(f"rate limited ({error.code}); retrying in {delay:.0f}s", flush=True)
            time.sleep(delay)
    raise RuntimeError(f"download retries exhausted: {url}")


def collect_set(root: Path, set_name: str, spec: dict, force: bool) -> dict:
    target = root / set_name
    target.mkdir(parents=True, exist_ok=True)
    discovered: dict[int, dict] = {}
    discovery_sources: dict[int, list[str]] = {}
    categories = spec.get("categories", [spec["category"]] if spec.get("category") else [])
    searches = spec.get("searches", [spec["search"]] if spec.get("search") else [])
    for category in categories:
        for page in category_files(category):
            page_id = int(page["pageid"])
            discovered[page_id] = page
            discovery_sources.setdefault(page_id, []).append(f"Category:{category}")
        time.sleep(1)
    for search in searches:
        for page in search_files(search):
            page_id = int(page["pageid"])
            discovered[page_id] = page
            discovery_sources.setdefault(page_id, []).append(f"search:{search}")
        time.sleep(1)
    pages = list(discovered.values())
    accepted: list[dict] = []
    rejected: list[dict] = []
    for page in sorted(pages, key=lambda item: int(item.get("pageid", 0))):
        ok, reason = is_allowed(page, spec["era"])
        if not ok:
            rejected.append({"pageid": page.get("pageid"), "title": page.get("title"), "reason": reason})
            continue
        info = page["imageinfo"][0]
        metadata = info.get("extmetadata", {})
        filename = safe_name(page, info.get("mime", ""))
        path = target / filename
        url = info.get("thumburl") or info["url"]
        if force or not path.exists():
            sha256, byte_size = download(url, path)
            time.sleep(0.75)
        else:
            payload = path.read_bytes()
            sha256, byte_size = hashlib.sha256(payload).hexdigest(), len(payload)
        with Image.open(path) as downloaded_image:
            actual_width, actual_height = downloaded_image.size
            downloaded_image.verify()
        accepted.append(
            {
                "set": set_name,
                "era": spec["era"],
                "pageid": page["pageid"],
                "title": page.get("title", ""),
                "filename": filename,
                "source_url": info.get("descriptionurl", ""),
                "download_url": url,
                "original_url": info.get("url", ""),
                "sha256": sha256,
                "dhash64": difference_hash(path),
                "bytes": byte_size,
                "width": actual_width,
                "height": actual_height,
                "original_width": info.get("width"),
                "original_height": info.get("height"),
                "date": metadata_value(metadata, "DateTimeOriginal"),
                "artist": metadata_value(metadata, "Artist"),
                "credit": metadata_value(metadata, "Credit"),
                "license": metadata_value(metadata, "LicenseShortName"),
                "usage_terms": metadata_value(metadata, "UsageTerms"),
                "categories": metadata_value(metadata, "Categories"),
                "discovered_by": discovery_sources.get(int(page["pageid"]), []),
            }
        )
        if len(accepted) >= int(spec["limit"]):
            break
    return {
        "name": set_name,
        "categories": categories,
        "searches": searches,
        "candidate_count": len(pages),
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "images": accepted,
        "rejections": rejected,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("data/raw"))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 1,
        "source": "Wikimedia Commons MediaWiki API",
        "retrieval_policy": {
            "historical": "Boardman target plus Uris/McGraw bridge queries; requires explicit pre-1970 or postcard metadata",
            "modern": "Uris/McGraw category and title queries; excludes explicit pre-1970/postcard metadata",
            "license_allowlist": list(LICENSE_ALLOWLIST),
            "minimum_short_side_px": 600,
            "download_width_px": 1024,
        },
        "sets": {},
    }
    for name, spec in SETS.items():
        result = collect_set(args.output, name, spec, args.force)
        manifest["sets"][name] = result
        print(f"{name}: {result['accepted_count']} accepted / {result['candidate_count']} candidates")
    manifest_path = args.output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {manifest_path}")


if __name__ == "__main__":
    main()

