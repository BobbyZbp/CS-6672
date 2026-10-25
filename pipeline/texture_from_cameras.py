"""Compatibility entry point: the code lives in pipeline/ghostmap/dense/texture_from_cameras.py.

Run as a script it executes ghostmap.dense.texture_from_cameras; imported, it is that same module object
(so tests, subprocess calls and mock.patch targets using the old name keep working).
"""
import sys

if __name__ == "__main__":
    import runpy
    runpy.run_module("ghostmap.dense.texture_from_cameras", run_name="__main__")
else:
    import ghostmap.dense.texture_from_cameras
    sys.modules[__name__] = sys.modules["ghostmap.dense.texture_from_cameras"]
