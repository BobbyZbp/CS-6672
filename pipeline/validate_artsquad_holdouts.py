"""Compatibility entry point: the code lives in pipeline/ghostmap/evaluate/holdouts.py.

Run as a script it executes ghostmap.evaluate.holdouts; imported, it is that same module object
(so tests, subprocess calls and mock.patch targets using the old name keep working).
"""
import sys

if __name__ == "__main__":
    import runpy
    runpy.run_module("ghostmap.evaluate.holdouts", run_name="__main__")
else:
    import ghostmap.evaluate.holdouts
    sys.modules[__name__] = sys.modules["ghostmap.evaluate.holdouts"]
