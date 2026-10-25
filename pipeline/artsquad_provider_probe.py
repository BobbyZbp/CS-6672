#!/usr/bin/env python3
"""Bounded public Arts Quad provider probes and explicit research-member recovery.

Default operation inspects small responses/headers only. Explicit recovery of
already checksum-listed ordinary members is quarantined for local research,
never admitted to Commons or copied into public assets. This is not a rights
validator, bulk tar extractor, account workflow, or TLS/access-control bypass.
Even valid archive bytes do not establish redistribution permission.
"""

import argparse
import hashlib
import html
import http.client
import io
import json
import re
import shutil
import socket
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "quad6k-2020": "https://web.archive.org/web/20200713205836id_/http://vision.soic.indiana.edu/disco_files/ArtsQuad_dataset.tar",
    "quad6k-2016": "https://web.archive.org/web/20161130144459id_/http://vision.soic.indiana.edu/disco_files/ArtsQuad_dataset.tar",
    "quad6k-2016-frame": "https://web.archive.org/web/20161130144459if_/http://vision.soic.indiana.edu/disco_files/ArtsQuad_dataset.tar",
    "quad6k-2016-port80": "https://web.archive.org/web/20161130144459id_/http://vision.soic.indiana.edu:80/disco_files/ArtsQuad_dataset.tar",
    "quad6k-original": "https://vision.soic.indiana.edu/disco_files/ArtsQuad_dataset.tar",
    "disco-release": "https://web.archive.org/web/20111231082144id_/http://vision.soic.indiana.edu:80/disco",
    "disco-release-2012": "https://web.archive.org/web/20120704082646id_/http://vision.soic.indiana.edu:80/disco",
    "disco-release-2011-frame": "https://web.archive.org/web/20111231082144if_/http://vision.soic.indiana.edu:80/disco",
    "cornell-bigsfm": "https://www.cs.cornell.edu/projects/bigsfm/",
    "photocity-terms": "http://www.photocitygame.com/data",
}
ALLOWED_HOSTS = {
    "web.archive.org", "vision.soic.indiana.edu", "vision.luddy.iu.edu",
    "www.cs.cornell.edu", "www.photocitygame.com",
}
MAX_REQUEST_BYTES = 1024 * 1024
MAX_TOTAL_BYTES = 128 * MAX_REQUEST_BYTES
MAX_REQUESTS = 256
USER_AGENT = "GhostMapResearch/0.1 (bounded public Arts Quad dataset availability check)"


def allowed_url(url):
    parsed = urllib.parse.urlsplit(url)
    return (parsed.scheme in {"http", "https"}
            and parsed.hostname in ALLOWED_HOSTS
            and parsed.port in {None, 80, 443}
            and parsed.username is None and parsed.password is None)


class RestrictedRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed_url(newurl):
            raise ValueError("Redirect outside the fixed public provider allowlist")
        if urllib.parse.urlsplit(req.full_url).scheme == "https" and urllib.parse.urlsplit(newurl).scheme != "https":
            raise ValueError("HTTPS downgrade refused")
        # A redirect remains evidence, not another unbudgeted HTTP request.
        # Operators may explicitly probe a discovered, allowlisted destination.
        return None


def parse_content_range(value):
    match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+|\*)", value or "")
    if not match:
        return None
    start, end = int(match[1]), int(match[2])
    total = None if match[3] == "*" else int(match[3])
    if end < start or (total is not None and end >= total):
        return None
    return {"start": start, "end": end, "total": total}


def tar_header(block):
    """Inspect one header without extracting it; reject unsafe or invalid names."""
    if len(block) != 512:
        raise ValueError("A tar header must contain exactly 512 bytes")
    if not any(block):
        return {"end_of_archive": True}
    try:
        expected = int(block[148:156].rstrip(b"\0 ").lstrip(b" ") or b"0", 8)
        observed = sum(block[:148]) + 8 * ord(" ") + sum(block[156:])
        if expected != observed:
            raise ValueError("Tar header checksum mismatch")
        # GNU base-256 sizes are not needed for these bounded legacy probes.
        size_bytes = block[124:136].rstrip(b"\0 ").lstrip(b" ")
        size = int(size_bytes or b"0", 8)
        name = block[:100].split(b"\0", 1)[0].decode("utf-8", "strict")
        prefix = block[345:500].split(b"\0", 1)[0].decode("utf-8", "strict") if block[257:262] == b"ustar" else ""
    except (UnicodeDecodeError, TypeError, OverflowError) as error:
        raise ValueError("Unsupported tar header encoding") from error
    if prefix:
        name = prefix + "/" + name
    path = PurePosixPath(name)
    if (not name or path.is_absolute() or ".." in path.parts or "\\" in name
            or "\x00" in name or re.match(r"^[A-Za-z]:", name)):
        raise ValueError("Unsafe tar member name")
    kind = block[156:157]
    if kind not in {b"\0", b"0", b"5"}:
        raise ValueError("Tar member type is not an ordinary file or directory")
    if size < 0:
        raise ValueError("Negative tar member size")
    return {"name": name, "size": size, "type": "directory" if kind == b"5" else "file",
            "next_header_delta": 512 + ((size + 511) // 512) * 512,
            "end_of_archive": False}


def inspect_complete_member(header, payload):
    """Recognize a fully delivered small README or decoded image, never admit it."""
    if header.get("type") != "file" or len(payload) != header.get("size"):
        return None
    name = PurePosixPath(header["name"]).name
    record = {"name": header["name"], "size": len(payload),
              "sha256": hashlib.sha256(payload).hexdigest()}
    release_metadata = bool(re.match(r"^(readme|licen[cs]e|copying|copyright)(\.[A-Za-z0-9]+)?$", name, re.I))
    if release_metadata or (PurePosixPath(name).suffix.lower() in {".txt", ".csv", ".json"} and len(payload) <= 256 * 1024):
        try:
            text = payload.decode("utf-8", "strict")
        except UnicodeDecodeError:
            return None
        record.update(kind="release_metadata" if release_metadata else "reference_metadata",
                      excerpt=text[:8192], excerpt_only=len(text) > 8192)
        return record
    if PurePosixPath(name).suffix.lower() in {".jpg", ".jpeg", ".png"}:
        try:
            from PIL import Image
            with Image.open(io.BytesIO(payload)) as image:
                dimensions, format_name = list(image.size), image.format
                image.verify()
            record.update(kind="image", dimensions=dimensions, format=format_name)
            return record
        except (ImportError, OSError, ValueError):
            return None
    return None


class BoundedProbe:
    def __init__(self, *, per_request=65536, total_bytes=524288, request_limit=8,
                 timeout=18, opener=None):
        if not 512 <= per_request <= MAX_REQUEST_BYTES:
            raise ValueError("per_request must be 512..1048576")
        if not per_request <= total_bytes <= MAX_TOTAL_BYTES:
            raise ValueError("total_bytes must be at least per_request and at most 128 MiB")
        if not 1 <= request_limit <= MAX_REQUESTS or not 1 <= timeout <= 30:
            raise ValueError("Invalid request count or timeout")
        self.per_request, self.total_bytes = per_request, total_bytes
        self.request_limit, self.timeout = request_limit, timeout
        self.opener = opener or urllib.request.build_opener(RestrictedRedirects())
        self.requests, self.bytes_read, self.bytes_reserved = [], 0, 0
        self.halted_for_provider_limit = False

    def fetch(self, url, start=0, length=None):
        if self.halted_for_provider_limit:
            raise ValueError("Provider limit observed; no further requests in this probe")
        if not allowed_url(url):
            raise ValueError("URL outside fixed public provider allowlist")
        if isinstance(start, bool) or not isinstance(start, int) or start < 0:
            raise ValueError("Invalid range offset")
        length = self.per_request if length is None else length
        if not isinstance(length, int) or not 1 <= length <= self.per_request:
            raise ValueError("Invalid range length")
        if len(self.requests) >= self.request_limit or self.bytes_reserved + length > self.total_bytes:
            raise ValueError("Probe request or byte budget exhausted")
        # Reserve before I/O: a timeout can consume bytes even if read() raises.
        self.bytes_reserved += length
        row = {"url": url, "range_requested": [start, start + length - 1]}
        self.requests.append(row)
        request = urllib.request.Request(url, headers={
            "User-Agent": USER_AGENT, "Range": f"bytes={start}-{start + length - 1}",
            "Accept-Encoding": "identity",
        })
        try:
            response = self.opener.open(request, timeout=self.timeout)
        except urllib.error.HTTPError as error:
            response = error
        except (urllib.error.URLError, OSError, ValueError) as error:
            row.update(status="request_failed", error=type(error).__name__ + ": " + str(error))
            return row, b""
        try:
            with response:
                final_url = response.geturl()
                if not allowed_url(final_url):
                    raise ValueError("Final URL outside fixed public provider allowlist")
                headers = {key.lower(): value for key, value in response.headers.items()}
                row.update(http_status=response.status, final_url=final_url,
                           headers={key: headers[key] for key in (
                               "content-type", "content-length", "content-range", "content-encoding",
                               "accept-ranges", "location", "retry-after", "etag", "last-modified",
                               "warning", "memento-datetime", "x-archive-orig-content-length",
                               "x-archive-src",
                           ) if key in headers})
                if response.status in {429, 503}:
                    self.halted_for_provider_limit = True
                    row.update(status="rate_limited", retry_policy="No automatic retry; respect Retry-After")
                    return row, b""
                if 300 <= response.status < 400:
                    row.update(status="redirect_observed_not_followed")
                    return row, b""
                body = response.read(length)
                self.bytes_read += len(body)
                row.update(bytes_read=len(body), prefix_sha256=hashlib.sha256(body).hexdigest())
                content_range = parse_content_range(headers.get("content-range"))
                valid_range = (response.status == 206 and content_range is not None
                               and content_range["start"] == start
                               and content_range["end"] <= start + length - 1
                               and content_range["end"] - start + 1 == len(body)
                               and headers.get("content-encoding", "identity").lower() == "identity")
                row.update(range_delivery_verified=bool(valid_range), content_range=content_range,
                           status="response_observed")
                return row, body
        except (OSError, ValueError, socket.timeout, http.client.HTTPException) as error:
            row.update(status="request_failed", error=type(error).__name__ + ": " + str(error))
            return row, b""


def inspect_source(name, probe, *, tar_headers=4, start_offset=0, on_header=None):
    if name not in SOURCES:
        raise ValueError("Unknown named source")
    if not 1 <= tar_headers <= 64:
        raise ValueError("At most 64 tar headers may be inspected")
    if (not isinstance(start_offset, int) or isinstance(start_offset, bool)
            or start_offset < 0 or start_offset % 512):
        raise ValueError("Tar start offset must be a nonnegative multiple of 512")
    if start_offset and not name.startswith("quad6k"):
        raise ValueError("Nonzero offsets only apply to named tar sources")
    url = SOURCES[name]
    row, body = probe.fetch(url, start_offset)
    result = {"source": name, "url": url, "request": row, "members": [], "complete_small_members": [],
              "rights_status": "unresolved_not_admitted", "images_acquired": 0,
              "archive_completeness_verified": False,
              "prefix_range_verified": bool(row.get("range_delivery_verified") and not start_offset),
              "nonzero_range_verified": bool(row.get("range_delivery_verified") and start_offset),
              "range_subset_feasible": False,
              "claims": {"reconstruction_input_admitted": False,
                         "public_redistribution_permitted": False}}
    warning = row.get("headers", {}).get("warning", "")
    if "truncat" in warning.lower():
        result["archive_capture_truncation_warning"] = warning
    if not body:
        result["status"] = row["status"]
        return result
    prefix = body.lstrip()[:128].lower()
    is_html = (prefix.startswith((b"<!doctype html", b"<html", b"<!--"))
            or "text/html" in row.get("headers", {}).get("content-type", "").lower())
    if not name.startswith("quad6k"):
        result["status"] = "metadata_prefix_observed" if 200 <= row.get("http_status", 0) < 300 else "http_error"
        text = body.decode("utf-8", "replace")
        result["metadata_excerpt"] = re.sub(r"\s+", " ", text)[:1600]
        result["metadata_evidence_snippets"] = [
            re.sub(r"\s+", " ", html.unescape(text[max(0, match.start() - 100):match.end() + 260]))
            for match in list(re.finditer(r"Arts.?Quad|6,?514|research|licen[cs]e|copyright|ground.?truth|contact|differential.?GPS", text, re.I))[:30]
        ]
        result["metadata_links"] = [html.unescape(link) for link in re.findall(r'href\s*=\s*["\']([^"\']+)', text, re.I)
                                    if re.search(r"quad|arts|zip|readme|licen[cs]e|camera|gps|tar|disco", link, re.I)][:40]
        result["metadata_prefix_only"] = len(body) == probe.per_request
        return result
    if is_html:
        result.update(status="html_instead_of_archive", metadata_excerpt=body[:300].decode("utf-8", "replace"))
        return result
    if not 200 <= row.get("http_status", 0) < 300:
        result["status"] = "http_error"
        return result
    if start_offset and not row.get("range_delivery_verified"):
        result["status"] = "requested_nonzero_range_not_delivered"
        return result
    offset = start_offset
    current = body
    try:
        for index in range(tar_headers):
            header = tar_header(current[:512])
            header["offset"] = offset
            header["header_sha256"] = hashlib.sha256(current[:512]).hexdigest()
            result["members"].append(header)
            if on_header is not None:
                on_header(header)
            if header["end_of_archive"]:
                break
            member_start = offset - start_offset + 512
            member_end = member_start + header["size"]
            if member_end <= len(body):
                member = inspect_complete_member(header, body[member_start:member_end])
                if member:
                    result["complete_small_members"].append(member)
            offset += header["next_header_delta"]
            relative = offset - start_offset
            if relative + 512 <= len(body):
                current = body[relative:relative + 512]
            elif index + 1 < tar_headers and row.get("range_delivery_verified"):
                next_row, current = probe.fetch(url, offset, 512)
                if (not next_row.get("range_delivery_verified")
                        or next_row["content_range"]["total"] != row["content_range"]["total"]):
                    result["header_walk_stopped"] = "Subsequent exact byte range not delivered"
                    break
                result["nonzero_range_verified"] = True
            else:
                break
        result["status"] = "range_delivery_verified" if row.get("range_delivery_verified") else "tar_prefix_available_range_unverified"
        result["range_subset_feasible"] = bool(result["nonzero_range_verified"]
                                               and any(item["kind"] in {"release_metadata", "image"}
                                                       for item in result["complete_small_members"]))
        result["range_subset_scope"] = "At least one complete small README or decoded image plus a verified nonzero tar-header range; never whole archive availability, rights or image admission"
    except ValueError as error:
        result.update(status="not_a_supported_tar_prefix", reason=str(error), range_subset_feasible=False)
    return result


def recover_research_member(name, offset, probe, output_root, *, maximum_member_bytes=2 * 1024 * 1024,
                            minimum_free_bytes=5 * 1024 ** 3):
    """Fetch one checksum-listed complete member into a separate research quarantine.

    No Commons manifest, public browser asset or training snapshot is touched.
    Unknown photo rights remain unknown; this performs bounded local inspection,
    not a legal clearance or reconstruction-admission decision.
    """
    if name not in SOURCES or not name.startswith("quad6k"):
        raise ValueError("Recovery requires a named Quad6K tar source")
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0 or offset % 512:
        raise ValueError("Member offset must be a nonnegative multiple of 512")
    if not 1 <= maximum_member_bytes <= 4 * 1024 * 1024:
        raise ValueError("Maximum member body must be 1 byte..4 MiB")
    output_root = Path(output_root)
    if any(path.is_symlink() for path in (output_root, *output_root.parents)):
        raise ValueError("Research output must not traverse symlinks")
    disk_root = output_root
    while not disk_root.exists():
        disk_root = disk_root.parent
    url = SOURCES[name]
    try:
        row, block = probe.fetch(url, offset, 512)
    except ValueError as error:
        return {"source": name, "url": url, "header_offset": offset,
                "status": "probe_budget_exhausted", "reason": str(error),
                "rights_status": "unknown_local_research_inspection_only",
                "public_redistribution_permitted": False, "reconstruction_input_admitted": False}
    result = {"source": name, "url": url, "header_offset": offset, "header_request": row,
              "rights_status": "unknown_local_research_inspection_only",
              "public_redistribution_permitted": False,
              "reconstruction_input_admitted": False, "archive_completeness_verified": False}
    if not row.get("range_delivery_verified") or len(block) != 512:
        result["status"] = "header_range_not_delivered"
        return result
    try:
        header = tar_header(block)
    except ValueError as error:
        result.update(status="unsafe_or_invalid_header", reason=str(error))
        return result
    result.update(member=header, header_sha256=hashlib.sha256(block).hexdigest())
    if header.get("end_of_archive") or header.get("type") != "file" or not 0 < header["size"] <= maximum_member_bytes:
        result["status"] = "member_not_an_eligible_bounded_file"
        return result
    if shutil.disk_usage(disk_root).free - header["size"] < minimum_free_bytes:
        result["status"] = "insufficient_free_disk"
        return result
    basename = PurePosixPath(header["name"]).name
    if not (PurePosixPath(basename).suffix.lower() in {".jpg", ".jpeg", ".png"}
            or (PurePosixPath(basename).suffix.lower() in {".txt", ".csv", ".json"} and header["size"] <= 256 * 1024)
            or re.match(r"^(readme|licen[cs]e|copying|copyright)(\.[A-Za-z0-9]+)?$", basename, re.I)):
        result["status"] = "member_not_photo_or_bounded_reference_metadata"
        return result
    payload = bytearray()
    total = row["content_range"]["total"]
    try:
        while len(payload) < header["size"]:
            length = min(probe.per_request, header["size"] - len(payload))
            chunk_row, chunk = probe.fetch(url, offset + 512 + len(payload), length)
            if (not chunk_row.get("range_delivery_verified") or len(chunk) != length
                    or chunk_row["content_range"]["total"] != total):
                result["status"] = "complete_member_range_not_delivered"
                return result
            payload.extend(chunk)
    except ValueError as error:
        result.update(status="probe_budget_exhausted", reason=str(error))
        return result
    payload = bytes(payload)
    inspected = inspect_complete_member(header, payload)
    if inspected is None:
        result["status"] = "complete_member_failed_decode"
        return result
    if inspected["kind"] == "image":
        from PIL import Image, ExifTags
        try:
            with Image.open(io.BytesIO(payload)) as image:
                # Fully decode: JPEG header/magic and verify() alone are not enough.
                image.load()
                exif = image.getexif()
                exif_data = dict(exif)
                if 34665 in exif:
                    exif_data.update(exif.get_ifd(34665))
                inspected["exif"] = {ExifTags.TAGS.get(key, str(key)): str(value)[:1000]
                                     for key, value in exif_data.items()
                                     if key in {271, 272, 274, 306, 315, 33432, 33434, 33437,
                                                34855, 36867, 36868, 37386, 41989, 42036}}
        except (OSError, ValueError) as error:
            result.update(status="complete_member_failed_decode", reason=str(error))
            return result
    destination = output_root / (inspected["sha256"][:20] + "__" + basename)
    if destination.is_symlink():
        raise ValueError("Refusing a symlinked research member destination")
    if shutil.disk_usage(disk_root).free - len(payload) < minimum_free_bytes:
        result["status"] = "insufficient_free_disk"
        return result
    if destination.exists() and destination.read_bytes() != payload:
        raise ValueError("Refusing to overwrite differing research member bytes")
    output_root.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        destination.write_bytes(payload)
    result.update(status="complete_research_member_recovered", file=str(destination),
                  complete_member=inspected, original_bytes_preserved=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append", choices=SOURCES, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--per-request-bytes", type=int, default=65536)
    parser.add_argument("--total-bytes", type=int, default=524288)
    parser.add_argument("--request-limit", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=18)
    parser.add_argument("--tar-headers", type=int, default=4)
    parser.add_argument("--tar-start-offset", type=int, default=0,
                        help="Previously verified tar member offset; must be 512-byte aligned")
    parser.add_argument("--recover-member-offset", type=int, action="append",
                        help="Explicit checksum-listed member offset to recover for local research inspection only")
    parser.add_argument("--maximum-member-bytes", type=int, default=2 * 1024 * 1024)
    parser.add_argument("--progress", action="store_true", help="Print checksum-verified member names/offsets as they arrive")
    args = parser.parse_args()
    output = args.output.resolve()
    try:
        output.relative_to((ROOT / "artifacts" / "provider-probes").resolve())
    except ValueError:
        parser.error("Reports must be under artifacts/provider-probes, never an acquisition manifest")
    if output.exists():
        parser.error("Refusing to overwrite an existing probe report")
    probe = BoundedProbe(per_request=args.per_request_bytes, total_bytes=args.total_bytes,
                         request_limit=args.request_limit, timeout=args.timeout)
    if args.recover_member_offset and (len(args.source) != 1 or len(args.recover_member_offset) > 64):
        parser.error("Research recovery needs exactly one named source and at most 64 explicit members")
    research_root = ROOT / "data" / "quad6k_research_probe"
    recovered = ([recover_research_member(args.source[0], offset, probe, research_root,
                                         maximum_member_bytes=args.maximum_member_bytes)
                  for offset in args.recover_member_offset] if args.recover_member_offset else [])
    inspections = []
    if not args.recover_member_offset:
        for name in args.source:
            try:
                inspections.append(inspect_source(name, probe, tar_headers=args.tar_headers,
                                                  start_offset=args.tar_start_offset,
                                                  on_header=(lambda header: print(json.dumps({"event": "verified_tar_header", "source": name, "member": header}), flush=True)) if args.progress else None))
            except ValueError as error:
                inspections.append({"source": name, "status": "probe_budget_or_argument_failure", "reason": str(error),
                                    "rights_status": "unresolved_not_admitted", "range_subset_feasible": False})
    report = {"schema_version": 2, "created_utc": datetime.now(timezone.utc).isoformat(),
              "probe_implementation_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "budget": {"per_request_bytes": args.per_request_bytes, "total_reserved_bytes": args.total_bytes,
                         "request_limit": args.request_limit, "timeout_seconds": args.timeout,
                         "minimum_free_disk_bytes": 5 * 1024 ** 3},
              "policy": "Bounded public requests only; no general extraction, image admission, public redistribution, account, contact, TLS bypass or retries",
              "sources": inspections,
              "recovered_research_members": recovered,
              "requests": probe.requests, "bytes_read": probe.bytes_read,
              "bytes_reserved_including_timeouts": probe.bytes_reserved}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    if recovered:
        research_root.mkdir(parents=True, exist_ok=True)
        manifest = research_root / ("manifest-" + output.stem + ".json")
        if manifest.exists():
            raise ValueError("Refusing to overwrite a research-probe manifest")
        manifest.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"report": str(output.relative_to(ROOT)), "bytes_read": probe.bytes_read,
                      "sources": [{"source": row["source"], "status": row["status"]} for row in report["sources"]],
                      "recovered_members": [{"source": row["source"], "status": row["status"]} for row in recovered]}))


if __name__ == "__main__":
    main()
