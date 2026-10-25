"""Compatibility entry point: the code lives in pipeline/ghostmap/dense/openmvs_cpu.py.

Run as a script it executes ghostmap.dense.openmvs_cpu; imported, it is that same module object
(so tests, subprocess calls and mock.patch targets using the old name keep working).
"""
import sys

if __name__ == "__main__":
    import runpy
    runpy.run_module("ghostmap.dense.openmvs_cpu", run_name="__main__")
else:
    import ghostmap.dense.openmvs_cpu
    sys.modules[__name__] = sys.modules["ghostmap.dense.openmvs_cpu"]
