"""Compatibility entry point: the code lives in pipeline/ghostmap/acquire/review.py.

Run as a script it executes ghostmap.acquire.review; imported, it is that same module object
(so tests, subprocess calls and mock.patch targets using the old name keep working).
"""
import sys

if __name__ == "__main__":
    import runpy
    runpy.run_module("ghostmap.acquire.review", run_name="__main__")
else:
    import ghostmap.acquire.review
    sys.modules[__name__] = sys.modules["ghostmap.acquire.review"]
