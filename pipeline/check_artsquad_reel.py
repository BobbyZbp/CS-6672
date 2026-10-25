"""Compatibility entry point: the code lives in pipeline/ghostmap/qa/reel.py.

Run as a script it executes ghostmap.qa.reel; imported, it is that same module object
(so tests, subprocess calls and mock.patch targets using the old name keep working).
"""
import sys

if __name__ == "__main__":
    import runpy
    runpy.run_module("ghostmap.qa.reel", run_name="__main__")
else:
    import ghostmap.qa.reel
    sys.modules[__name__] = sys.modules["ghostmap.qa.reel"]
