"""Compatibility entry point: the code lives in pipeline/ghostmap/qa/record_demo.py.

Run as a script it executes ghostmap.qa.record_demo; imported, it is that same module object
(so tests, subprocess calls and mock.patch targets using the old name keep working).
"""
import sys

if __name__ == "__main__":
    import runpy
    runpy.run_module("ghostmap.qa.record_demo", run_name="__main__")
else:
    import ghostmap.qa.record_demo
    sys.modules[__name__] = sys.modules["ghostmap.qa.record_demo"]
