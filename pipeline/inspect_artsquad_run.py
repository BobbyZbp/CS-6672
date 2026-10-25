"""Compatibility entry point: the code lives in pipeline/ghostmap/sfm/inspect_run.py.

Run as a script it executes ghostmap.sfm.inspect_run; imported, it is that same module object
(so tests, subprocess calls and mock.patch targets using the old name keep working).
"""
import sys

if __name__ == "__main__":
    import runpy
    runpy.run_module("ghostmap.sfm.inspect_run", run_name="__main__")
else:
    import ghostmap.sfm.inspect_run
    sys.modules[__name__] = sys.modules["ghostmap.sfm.inspect_run"]
