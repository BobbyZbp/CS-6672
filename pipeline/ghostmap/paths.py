"""Repository-relative locations shared by every pipeline module."""
from pathlib import Path

# pipeline/ghostmap/paths.py -> parents[2] is the repository root.
ROOT = Path(__file__).resolve().parents[2]
