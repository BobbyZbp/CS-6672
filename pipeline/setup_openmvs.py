"""Compatibility entry point: the code lives in pipeline/ghostmap/dense/setup_openmvs.py.

Run as a script it executes ghostmap.dense.setup_openmvs; imported, it is that same module object
(so tests, subprocess calls and mock.patch targets using the old name keep working).
"""
import sys

if __name__ == "__main__":
    import runpy
    runpy.run_module("ghostmap.dense.setup_openmvs", run_name="__main__")
else:
    import ghostmap.dense.setup_openmvs
    sys.modules[__name__] = sys.modules["ghostmap.dense.setup_openmvs"]
