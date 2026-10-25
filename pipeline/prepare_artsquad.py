"""Compatibility entry point: the code lives in pipeline/ghostmap/prepare/snapshot.py.

Run as a script it executes ghostmap.prepare.snapshot; imported, it is that same module object
(so tests, subprocess calls and mock.patch targets using the old name keep working).
"""
import sys

if __name__ == "__main__":
    import runpy
    runpy.run_module("ghostmap.prepare.snapshot", run_name="__main__")
else:
    import ghostmap.prepare.snapshot
    sys.modules[__name__] = sys.modules["ghostmap.prepare.snapshot"]
