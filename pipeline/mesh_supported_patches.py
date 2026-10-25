"""Compatibility entry point: the code lives in pipeline/ghostmap/dense/mesh_supported_patches.py.

Run as a script it executes ghostmap.dense.mesh_supported_patches; imported, it is that same module object
(so tests, subprocess calls and mock.patch targets using the old name keep working).
"""
import sys

if __name__ == "__main__":
    import runpy
    runpy.run_module("ghostmap.dense.mesh_supported_patches", run_name="__main__")
else:
    import ghostmap.dense.mesh_supported_patches
    sys.modules[__name__] = sys.modules["ghostmap.dense.mesh_supported_patches"]
