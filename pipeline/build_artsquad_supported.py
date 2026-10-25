"""Compatibility entry point: the code lives in pipeline/ghostmap/surface/supported.py.

Run as a script it executes ghostmap.surface.supported; imported, it is that same module object
(so tests, subprocess calls and mock.patch targets using the old name keep working).
"""
import sys

if __name__ == "__main__":
    import runpy
    runpy.run_module("ghostmap.surface.supported", run_name="__main__")
else:
    import ghostmap.surface.supported
    sys.modules[__name__] = sys.modules["ghostmap.surface.supported"]
