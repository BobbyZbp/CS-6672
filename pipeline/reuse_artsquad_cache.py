"""Compatibility entry point: the code lives in pipeline/ghostmap/sfm/cache_reuse.py.

Run as a script it executes ghostmap.sfm.cache_reuse; imported, it is that same module object
(so tests, subprocess calls and mock.patch targets using the old name keep working).
"""
import sys

if __name__ == "__main__":
    import runpy
    runpy.run_module("ghostmap.sfm.cache_reuse", run_name="__main__")
else:
    import ghostmap.sfm.cache_reuse
    sys.modules[__name__] = sys.modules["ghostmap.sfm.cache_reuse"]
