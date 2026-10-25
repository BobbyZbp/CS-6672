"""Compatibility entry point: the code lives in pipeline/ghostmap/status/project_status.py.

Run as a script it executes ghostmap.status.project_status; imported, it is that same module object
(so tests, subprocess calls and mock.patch targets using the old name keep working).
"""
import sys

if __name__ == "__main__":
    import runpy
    runpy.run_module("ghostmap.status.project_status", run_name="__main__")
else:
    import ghostmap.status.project_status
    sys.modules[__name__] = sys.modules["ghostmap.status.project_status"]
