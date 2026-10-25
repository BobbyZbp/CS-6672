"""Compatibility entry point: the code lives in pipeline/ghostmap/acquire/provider_probe.py.

Run as a script it executes ghostmap.acquire.provider_probe; imported, it is that same module object
(so tests, subprocess calls and mock.patch targets using the old name keep working).
"""
import sys

if __name__ == "__main__":
    import runpy
    runpy.run_module("ghostmap.acquire.provider_probe", run_name="__main__")
else:
    import ghostmap.acquire.provider_probe
    sys.modules[__name__] = sys.modules["ghostmap.acquire.provider_probe"]
