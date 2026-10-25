#!/usr/bin/env python3
"""Verify and serve one extracted GhostMap draft, on loopback only.

No dependency installation, external binding, authentication or existing-server
termination. Requests are limited to the hash-verified bundle allowlist.
"""
import argparse
import functools
import hashlib
import json
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit


def verify_bundle(root):
    root = Path(root).resolve()
    manifest = json.loads((root / "BUNDLE_MANIFEST.json").read_text())
    if manifest.get("schema_version") != 1 or manifest.get("local_draft_only") is not True:
        raise ValueError("Expected a versioned local GhostMap draft manifest")
    allowed = set()
    for record in manifest["files"]:
        name = PurePosixPath(record["path"])
        if name.is_absolute() or ".." in name.parts or "\\" in str(name):
            raise ValueError("Unsafe bundle path")
        path = root / Path(*name.parts)
        if any(root.joinpath(*name.parts[:i]).is_symlink() for i in range(1, len(name.parts) + 1)) or not path.is_file() or not path.resolve().is_relative_to(root):
            raise ValueError("Missing/escaping/symlinked bundle file: " + str(name))
        payload = path.read_bytes()
        if len(payload) != record["bytes"] or hashlib.sha256(payload).hexdigest() != record["sha256"]:
            raise ValueError("Bundle integrity failed: " + str(name))
        if name.parts[0] == "dist": allowed.add(PurePosixPath(*name.parts[1:]).as_posix())
    if "artsquad.html" not in allowed or "demo-reel.html" not in allowed:
        raise ValueError("The local bundle is missing its presentation pages")
    return manifest, allowed


class DraftHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory, allowed, **kwargs):
        self.bundle_directory = Path(directory).resolve()
        self.allowed = allowed
        super().__init__(*args, directory=str(directory), **kwargs)

    def _admitted(self):
        path = unquote(urlsplit(self.path).path)
        if path == "/": self.path = "/artsquad.html"; path = self.path
        relative = PurePosixPath(path.lstrip("/"))
        if ".." in relative.parts or "\\" in path or "\x00" in path or relative.as_posix() not in self.allowed:
            self.send_error(404, "Not in this local draft bundle")
            return False
        for index in range(1, len(relative.parts) + 1):
            if self.bundle_directory.joinpath(*relative.parts[:index]).is_symlink():
                self.send_error(404, "Bundle symlink not served")
                return False
        return True

    def do_GET(self):
        if self._admitted(): super().do_GET()

    def do_HEAD(self):
        if self._admitted(): super().do_HEAD()

    def list_directory(self, path):
        self.send_error(404, "Directory listings disabled")
        return None

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--port", type=int, default=8082)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535: parser.error("Use an unprivileged local port between 1024 and 65535")
    try:
        manifest, allowed = verify_bundle(args.root)
        print(f"Verified {len(manifest['files'])} files. Local diagnostic draft only; D1 not implied.", flush=True)
        if args.verify_only: return
        handler = functools.partial(DraftHandler, directory=args.root.resolve() / "dist", allowed=allowed)
        with ThreadingHTTPServer(("127.0.0.1", args.port), handler) as server:
            print(f"Local: http://127.0.0.1:{args.port}/artsquad.html", flush=True)
            print(f"Recorded tour: http://127.0.0.1:{args.port}/demo-reel.html", flush=True)
            print("Ctrl-C stops only this launcher. No external publication.", flush=True)
            try: server.serve_forever()
            except KeyboardInterrupt: pass
    except (ValueError, OSError, KeyError) as error:
        print(f"Local draft not started: {error}. No existing server was stopped.", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
