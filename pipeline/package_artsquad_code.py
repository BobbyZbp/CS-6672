"""Compatibility entry point: the code lives in pipeline/ghostmap/package/source_zip.py.

Run as a script it executes ghostmap.package.source_zip; imported, it is that same module object
(so tests, subprocess calls and mock.patch targets using the old name keep working).
"""
import sys

if __name__ == "__main__":
    import runpy
    runpy.run_module("ghostmap.package.source_zip", run_name="__main__")
else:
    import ghostmap.package.source_zip
    sys.modules[__name__] = sys.modules["ghostmap.package.source_zip"]
