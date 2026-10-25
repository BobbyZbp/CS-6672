"""Compatibility entry point: the code lives in pipeline/ghostmap/acquire/artsquad.py.

Run as a script it executes ghostmap.acquire.artsquad; imported, it is that same module object
(so tests, subprocess calls and mock.patch targets using the old name keep working).
"""
import sys

if __name__ == "__main__":
    import runpy
    runpy.run_module("ghostmap.acquire.artsquad", run_name="__main__")
else:
    import ghostmap.acquire.artsquad
    sys.modules[__name__] = sys.modules["ghostmap.acquire.artsquad"]
