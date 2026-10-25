"""Compatibility entry point: the code lives in pipeline/ghostmap/evaluate/bridges.py.

Run as a script it executes ghostmap.evaluate.bridges; imported, it is that same module object
(so tests, subprocess calls and mock.patch targets using the old name keep working).
"""
import sys

if __name__ == "__main__":
    import runpy
    runpy.run_module("ghostmap.evaluate.bridges", run_name="__main__")
else:
    import ghostmap.evaluate.bridges
    sys.modules[__name__] = sys.modules["ghostmap.evaluate.bridges"]
