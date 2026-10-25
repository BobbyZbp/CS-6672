"""Compatibility entry point: the code lives in pipeline/ghostmap/web/site.py.

Run as a script it executes ghostmap.web.site; imported, it is that same module object
(so tests, subprocess calls and mock.patch targets using the old name keep working).
"""
import sys

if __name__ == "__main__":
    import runpy
    runpy.run_module("ghostmap.web.site", run_name="__main__")
else:
    import ghostmap.web.site
    sys.modules[__name__] = sys.modules["ghostmap.web.site"]
