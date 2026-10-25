"""Compatibility entry point: the code lives in pipeline/ghostmap/qa/browser.py.

Run as a script it executes ghostmap.qa.browser; imported, it is that same module object
(so tests, subprocess calls and mock.patch targets using the old name keep working).
"""
import sys

if __name__ == "__main__":
    import runpy
    runpy.run_module("ghostmap.qa.browser", run_name="__main__")
else:
    import ghostmap.qa.browser
    sys.modules[__name__] = sys.modules["ghostmap.qa.browser"]
