"""Compatibility entry point: the code lives in pipeline/ghostmap/surface/dense_support.py.

Run as a script it executes ghostmap.surface.dense_support; imported, it is that same module object
(so tests, subprocess calls and mock.patch targets using the old name keep working).
"""
import sys

if __name__ == "__main__":
    import runpy
    runpy.run_module("ghostmap.surface.dense_support", run_name="__main__")
else:
    import ghostmap.surface.dense_support
    sys.modules[__name__] = sys.modules["ghostmap.surface.dense_support"]
