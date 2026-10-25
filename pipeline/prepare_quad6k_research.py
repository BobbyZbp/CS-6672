"""Compatibility entry point: the code lives in pipeline/ghostmap/prepare/quad6k_research.py.

Run as a script it executes ghostmap.prepare.quad6k_research; imported, it is that same module object
(so tests, subprocess calls and mock.patch targets using the old name keep working).
"""
import sys

if __name__ == "__main__":
    import runpy
    runpy.run_module("ghostmap.prepare.quad6k_research", run_name="__main__")
else:
    import ghostmap.prepare.quad6k_research
    sys.modules[__name__] = sys.modules["ghostmap.prepare.quad6k_research"]
