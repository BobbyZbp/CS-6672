"""Compatibility entry point: the code lives in pipeline/ghostmap/package/demo_bundle.py.

Run as a script it executes ghostmap.package.demo_bundle; imported, it is that same module object
(so tests, subprocess calls and mock.patch targets using the old name keep working).
"""
import sys

if __name__ == "__main__":
    import runpy
    runpy.run_module("ghostmap.package.demo_bundle", run_name="__main__")
else:
    import ghostmap.package.demo_bundle
    sys.modules[__name__] = sys.modules["ghostmap.package.demo_bundle"]
