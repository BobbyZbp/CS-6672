import io
import sys
import tarfile
import tempfile
import unittest
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
from artsquad_provider_probe import BoundedProbe, SOURCES, allowed_url, inspect_source, parse_content_range, recover_research_member, tar_header


def tar_entry(name="ArtsQuad_dataset/photos/photo001.jpg", size=3000, kind=tarfile.REGTYPE):
    info = tarfile.TarInfo(name)
    info.size, info.type = size, kind
    return info.tobuf(format=tarfile.USTAR_FORMAT)


class Response(io.BytesIO):
    def __init__(self, body, status=206, headers=None, url=None):
        super().__init__(body)
        self.status = status
        self.headers = headers or {"Content-Range": f"bytes 0-{len(body)-1}/{len(body)}"}
        self.url = url or SOURCES["quad6k-2016"]

    def geturl(self):
        return self.url


class Opener:
    def __init__(self, responses):
        self.responses, self.requests = iter(responses), []

    def open(self, request, timeout):
        self.requests.append(request)
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


class ProviderProbeTests(unittest.TestCase):
    def test_fixed_public_provider_allowlist(self):
        for url in SOURCES.values():
            self.assertTrue(allowed_url(url))
        for url in ("file:///etc/passwd", "http://localhost/", "http://127.0.0.1/", "https://www.cs.cornell.edu.evil.test/", "https://user:secret@www.cs.cornell.edu/"):
            self.assertFalse(allowed_url(url))

    def test_exact_content_range(self):
        self.assertEqual(parse_content_range("bytes 512-1023/10000"), {"start": 512, "end": 1023, "total": 10000})
        self.assertIsNone(parse_content_range("bytes 512-511/10000"))
        self.assertIsNone(parse_content_range("bytes 0-100/100"))
        self.assertIsNone(parse_content_range("bytes */10000"))

    def test_checksum_and_member_size(self):
        row = tar_header(tar_entry())
        self.assertEqual(row["size"], 3000)
        self.assertEqual(row["next_header_delta"], 3584)
        damaged = bytearray(tar_entry())
        damaged[0] = 1
        with self.assertRaisesRegex(ValueError, "checksum"):
            tar_header(bytes(damaged))

    def test_unsafe_paths_and_links_rejected(self):
        for name in ("../a.jpg", "/a.jpg", "C:/a.jpg", "safe/../../a.jpg", "a\\b"):
            with self.assertRaisesRegex(ValueError, "Unsafe"):
                tar_header(tar_entry(name))
        for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.XHDTYPE):
            with self.assertRaisesRegex(ValueError, "type"):
                tar_header(tar_entry(kind=kind))

    def test_zero_header_is_only_end_marker(self):
        self.assertTrue(tar_header(bytes(512))["end_of_archive"])

    def test_partial_header_is_not_valid(self):
        with self.assertRaises(ValueError):
            tar_header(bytes(511))

    def test_request_and_body_budget_hard_limits(self):
        opener = Opener([Response(bytes(512))])
        probe = BoundedProbe(per_request=512, total_bytes=512, opener=opener)
        probe.fetch(SOURCES["quad6k-2016"])
        with self.assertRaisesRegex(ValueError, "budget"):
            probe.fetch(SOURCES["quad6k-2016"])
        self.assertEqual(len(opener.requests), 1)

    def test_timeout_reserves_potentially_received_bytes(self):
        opener = Opener([urllib.error.URLError("timed out")])
        probe = BoundedProbe(per_request=512, total_bytes=512, opener=opener)
        row, body = probe.fetch(SOURCES["quad6k-2016"])
        self.assertEqual(row["status"], "request_failed")
        self.assertEqual(body, b"")
        with self.assertRaisesRegex(ValueError, "budget"):
            probe.fetch(SOURCES["quad6k-2016"])

    def test_range_verified_only_when_exact(self):
        for status, headers, expected in (
            (206, {"Content-Range": "bytes 512-1023/9000"}, True),
            (200, {"Content-Length": "9000"}, False),
            (206, {"Content-Range": "bytes 0-511/9000"}, False),
            (206, {"Content-Range": "bytes 512-1023/9000", "Content-Encoding": "gzip"}, False),
            (206, {"Content-Range": "bytes 512-1024/9000"}, False),
        ):
            probe = BoundedProbe(per_request=512, opener=Opener([Response(bytes(512), status, headers)]))
            row, _ = probe.fetch(SOURCES["quad6k-2016"], 512, 512)
            self.assertEqual(row["range_delivery_verified"], expected)

    def test_rate_limit_stops_without_body_or_retry(self):
        opener = Opener([Response(b"Do not read", 429, {"Retry-After": "600"})])
        probe = BoundedProbe(per_request=512, opener=opener)
        row, body = probe.fetch(SOURCES["quad6k-2016"])
        self.assertEqual(row["status"], "rate_limited")
        self.assertEqual(row["headers"]["retry-after"], "600")
        self.assertEqual(body, b"")
        self.assertEqual(len(opener.requests), 1)
        with self.assertRaisesRegex(ValueError, "Provider limit"):
            probe.fetch(SOURCES["quad6k-2016"])
        self.assertEqual(len(opener.requests), 1)

    def test_html_200_is_not_archive_success(self):
        response = Response(b"<!doctype html><html>new homepage</html>", 200, {"Content-Type": "text/html"})
        result = inspect_source("quad6k-original", BoundedProbe(opener=Opener([response])))
        self.assertEqual(result["status"], "html_instead_of_archive")
        self.assertFalse(result["claims"]["reconstruction_input_admitted"])

    def test_header_walk_skips_photo_body_using_ranges(self):
        first = tar_entry(size=3000)
        second = tar_entry("ArtsQuad_dataset/README.txt", 800)
        opener = Opener([
            Response(first, headers={"Content-Range": "bytes 0-511/9000", "Warning": '299 wayback content truncated by "time"'}),
            Response(second, headers={"Content-Range": "bytes 3584-4095/9000"}),
        ])
        probe = BoundedProbe(per_request=512, opener=opener)
        result = inspect_source("quad6k-2016", probe, tar_headers=2)
        self.assertEqual(result["status"], "range_delivery_verified")
        self.assertEqual(result["members"][1]["offset"], 3584)
        self.assertEqual(opener.requests[1].get_header("Range"), "bytes=3584-4095")
        self.assertIn("archive_capture_truncation_warning", result)
        self.assertEqual(result["rights_status"], "unresolved_not_admitted")
        self.assertEqual(result["images_acquired"], 0)
        self.assertFalse(result["archive_completeness_verified"])
        self.assertTrue(result["nonzero_range_verified"])
        self.assertFalse(result["range_subset_feasible"])

    def test_ignored_range_does_not_trigger_large_sequential_download(self):
        opener = Opener([Response(tar_entry(), 200, {"Content-Length": "9000"})])
        result = inspect_source("quad6k-2016", BoundedProbe(per_request=512, opener=opener))
        self.assertEqual(result["status"], "tar_prefix_available_range_unverified")
        self.assertEqual(len(opener.requests), 1)

    def test_invalid_tar_binary_is_not_photo_archive(self):
        result = inspect_source("quad6k-2016", BoundedProbe(per_request=512, opener=Opener([Response(b"\xff\xd8" + bytes(510))])))
        self.assertEqual(result["status"], "not_a_supported_tar_prefix")

    def test_final_external_host_rejected(self):
        row, body = BoundedProbe(opener=Opener([Response(bytes(512), url="http://localhost/private")])).fetch(SOURCES["quad6k-2016"])
        self.assertEqual(row["status"], "request_failed")
        self.assertEqual(body, b"")

    def test_nonzero_header_offset_requires_exact_range(self):
        for status, headers, expected in (
            (200, {"Content-Length": "9000"}, "requested_nonzero_range_not_delivered"),
            (206, {"Content-Range": "bytes 3584-4095/9000"}, "range_delivery_verified"),
        ):
            probe = BoundedProbe(per_request=512, opener=Opener([Response(tar_entry(), status, headers)]))
            result = inspect_source("quad6k-2016", probe, tar_headers=1, start_offset=3584)
            self.assertEqual(result["status"], expected)

    def test_header_offset_must_be_aligned(self):
        with self.assertRaisesRegex(ValueError, "multiple"):
            inspect_source("quad6k-2016", BoundedProbe(), start_offset=7)

    def test_redirect_not_automatically_followed(self):
        opener = Opener([Response(b"", 302, {"Location": SOURCES["quad6k-2020"]})])
        result = inspect_source("disco-release", BoundedProbe(opener=opener))
        self.assertEqual(result["status"], "redirect_observed_not_followed")
        self.assertEqual(len(opener.requests), 1)

    def test_release_metadata_preserves_terms_snippets_without_granting_license(self):
        response = Response(b'<html>Arts Quad research data <a href="disco_files/README.txt">README</a> Copyright author</html>', 200, {"Content-Type": "text/html"})
        result = inspect_source("disco-release", BoundedProbe(opener=Opener([response])))
        self.assertIn("disco_files/README.txt", result["metadata_links"])
        self.assertTrue(result["metadata_evidence_snippets"])
        self.assertFalse(result["metadata_prefix_only"])
        self.assertFalse(result["claims"]["public_redistribution_permitted"])

    def test_prefix_alone_is_not_recoverable_subset(self):
        opener = Opener([Response(tar_entry(size=50832029))])
        result = inspect_source("quad6k-2016", BoundedProbe(per_request=512, opener=opener), tar_headers=1)
        self.assertTrue(result["prefix_range_verified"])
        self.assertFalse(result["range_subset_feasible"])

    def test_full_small_readme_and_nonzero_range_are_required(self):
        readme = b"Dataset release notes. Rights unknown."
        first = tar_entry("ArtsQuad_dataset/README.txt", len(readme)) + readme + bytes(512-len(readme))
        opener = Opener([
            Response(first, headers={"Content-Range": "bytes 0-1023/9000"}),
            Response(tar_entry(size=3000), headers={"Content-Range": "bytes 1024-1535/9000"}),
        ])
        result = inspect_source("quad6k-2016", BoundedProbe(per_request=1024, opener=opener), tar_headers=2)
        self.assertTrue(result["range_subset_feasible"])
        self.assertEqual(result["complete_small_members"][0]["excerpt"], readme.decode())
        self.assertFalse(result["claims"]["public_redistribution_permitted"])

    def test_complete_readme_without_nonzero_range_is_insufficient(self):
        readme = b"Research dataset notes."
        first = tar_entry("README", len(readme)) + readme + bytes(512-len(readme))
        result = inspect_source("quad6k-2016", BoundedProbe(per_request=1024, opener=Opener([Response(first)])), tar_headers=1)
        self.assertTrue(result["complete_small_members"])
        self.assertFalse(result["nonzero_range_verified"])
        self.assertFalse(result["range_subset_feasible"])

    def test_complete_member_recovery_preserves_bytes_and_unknown_rights(self):
        payload = b"Research release notes; copyright holder retains all rights."
        header = tar_entry("ArtsQuad_dataset/README.txt", len(payload))
        opener = Opener([
            Response(header, headers={"Content-Range": "bytes 512-1023/9000"}),
            Response(payload, headers={"Content-Range": f"bytes 1024-{1023+len(payload)}/9000"}),
        ])
        with tempfile.TemporaryDirectory() as temporary:
            result = recover_research_member("quad6k-2016", 512, BoundedProbe(per_request=512, opener=opener), temporary)
            self.assertEqual(result["status"], "complete_research_member_recovered")
            self.assertEqual(Path(result["file"]).read_bytes(), payload)
            self.assertFalse(result["public_redistribution_permitted"])
            self.assertFalse(result["reconstruction_input_admitted"])

    def test_partial_recovery_never_saves_corrupt_photo(self):
        header = tar_entry("ArtsQuad_dataset/photo001.jpg", 500)
        opener = Opener([
            Response(header, headers={"Content-Range": "bytes 512-1023/9000"}),
            Response(b"wrong range", status=200, headers={"Content-Length": "9000"}),
        ])
        with tempfile.TemporaryDirectory() as temporary:
            result = recover_research_member("quad6k-2016", 512, BoundedProbe(per_request=512, opener=opener), temporary)
            self.assertEqual(result["status"], "complete_member_range_not_delivered")
            self.assertEqual(list(Path(temporary).iterdir()), [])

    def test_oversized_member_is_not_downloaded(self):
        header = tar_entry(size=5000000)
        opener = Opener([Response(header, headers={"Content-Range": "bytes 512-1023/9000000"})])
        with tempfile.TemporaryDirectory() as temporary:
            result = recover_research_member("quad6k-2016", 512, BoundedProbe(per_request=512, opener=opener), temporary)
            self.assertEqual(result["status"], "member_not_an_eligible_bounded_file")
            self.assertEqual(len(opener.requests), 1)

    def test_exhausted_recovery_budget_returns_a_record(self):
        probe = BoundedProbe(per_request=512, total_bytes=512, opener=Opener([Response(bytes(512))]))
        probe.fetch(SOURCES["quad6k-2016"])
        with tempfile.TemporaryDirectory() as temporary:
            result = recover_research_member("quad6k-2016", 512, probe, temporary)
            self.assertEqual(result["status"], "probe_budget_exhausted")
            self.assertEqual(list(Path(temporary).iterdir()), [])

    def test_complete_jpeg_decode_and_chunk_ranges(self):
        from PIL import Image
        buffer = io.BytesIO()
        Image.new("RGB", (64, 48), (12, 30, 50)).save(buffer, format="JPEG")
        payload = buffer.getvalue()
        header = tar_entry("ArtsQuad_dataset/image001.jpg", len(payload))
        responses = [Response(header, headers={"Content-Range": "bytes 512-1023/9000"})]
        for offset in range(0, len(payload), 512):
            chunk = payload[offset:offset + 512]
            responses.append(Response(chunk, headers={"Content-Range": f"bytes {1024+offset}-{1023+offset+len(chunk)}/9000"}))
        with tempfile.TemporaryDirectory() as temporary:
            result = recover_research_member("quad6k-2016", 512, BoundedProbe(per_request=512, opener=Opener(responses)), temporary)
            self.assertEqual(result["status"], "complete_research_member_recovered")
            self.assertEqual(result["complete_member"]["dimensions"], [64, 48])
            self.assertEqual(Path(result["file"]).read_bytes(), payload)

    def test_complete_invalid_jpeg_never_saved(self):
        payload = b"\xff\xd8 not a complete image"
        header = tar_entry("ArtsQuad_dataset/bad.jpg", len(payload))
        opener = Opener([
            Response(header, headers={"Content-Range": "bytes 512-1023/9000"}),
            Response(payload, headers={"Content-Range": f"bytes 1024-{1023+len(payload)}/9000"}),
        ])
        with tempfile.TemporaryDirectory() as temporary:
            result = recover_research_member("quad6k-2016", 512, BoundedProbe(per_request=512, opener=opener), temporary)
            self.assertEqual(result["status"], "complete_member_failed_decode")
            self.assertEqual(list(Path(temporary).iterdir()), [])

    def test_disk_floor_checked_before_photo_body(self):
        header = tar_entry(size=1000)
        opener = Opener([Response(header, headers={"Content-Range": "bytes 512-1023/9000"})])
        with tempfile.TemporaryDirectory() as temporary:
            result = recover_research_member("quad6k-2016", 512, BoundedProbe(per_request=512, opener=opener), temporary,
                                             minimum_free_bytes=10 ** 30)
            self.assertEqual(result["status"], "insufficient_free_disk")
            self.assertEqual(len(opener.requests), 1)
            self.assertEqual(list(Path(temporary).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
