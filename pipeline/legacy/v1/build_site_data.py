#!/usr/bin/env python3
"""Copy only public, audited artifacts into the static site."""

from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "artifacts" / "public"
DIST = ROOT / "dist"
ASSETS = DIST / "assets"


def main() -> None:
    report = json.loads((PUBLIC / "report.json").read_text())
    manifest = json.loads((PUBLIC / "manifest.json").read_text())
    ASSETS.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PUBLIC / "report.json", ASSETS / "report.json")
    shutil.copy2(PUBLIC / "manifest.json", ASSETS / "manifest.json")
    learned = ROOT / "artifacts" / "hloc_cross_era"
    learned_files = {
        learned / "report.json": ASSETS / "hloc-cross-era-report.json",
        learned / "joint_report.json": ASSETS / "hloc-joint-report.json",
        learned / "joint_sparse.ply": ASSETS / "hloc-joint-sparse.ply",
        learned / "joint_viewer.json": ASSETS / "hloc-joint-viewer.json",
    }
    for source, target in learned_files.items():
        if source.exists():
            shutil.copy2(source, target)
    dense_reports = [
        ROOT / "artifacts" / "experiments" / "dense_hloc_joint_cuda_check" / "dense_mvs_report.json",
        ROOT / "artifacts" / "experiments" / "dense_modern_cuda_check" / "dense_mvs_report.json",
    ]
    dense_report = next((path for path in dense_reports if path.exists()), None)
    if dense_report:
        shutil.copy2(dense_report, ASSETS / "dense-mvs-report.json")
    for mode, run in report["runs"].items():
        source = PUBLIC / mode
        if not source.exists():
            continue
        target = ASSETS / mode
        target.mkdir(exist_ok=True)
        for filename in ["viewer.json", "sparse.ply"]:
            if (source / filename).exists():
                shutil.copy2(source / filename, target / filename)
    # Make a compact, explicit selection of source thumbnails available for provenance inspection.
    thumbs = ASSETS / "inputs"
    thumbs.mkdir(exist_ok=True)
    for set_name, set_data in manifest["sets"].items():
        for item in set_data["images"][:10]:
            source = ROOT / "data" / "raw" / set_name / item["filename"]
            if source.exists():
                shutil.copy2(source, thumbs / f"{set_name}__{item['filename']}")
    source_files = [
        ROOT / "README.md",
        ROOT / "requirements.txt",
        ROOT / "requirements-hloc.txt",
        ROOT / "requirements-repair.txt",
        ROOT / "requirements-artsquad.txt",
        ROOT / "run_pipeline.sh",
        ROOT / "run_repair.sh",
        ROOT / "docs" / "legacy" / "v1" / "protocol.md",
        ROOT / "docs" / "legacy" / "v1" / "data-audit.md",
        ROOT / "docs" / "legacy" / "v1" / "results-v1.md",
        ROOT / "docs" / "legacy" / "repair" / "noah-method-audit.md",
        ROOT / "docs" / "legacy" / "repair" / "results-repair.md",
        ROOT / "docs" / "plans" / "modern-artsquad-pipeline.md",
        ROOT / "docs" / "plans" / "demo-delivery-contract.md",
        ROOT / "docs" / "reference" / "artsquad-implementation.md",
        ROOT / "docs" / "checkpoints" / "artsquad-data-checkpoint.md",
        *sorted((ROOT / "docs" / "research").glob("*.md")),
        *sorted((ROOT / "config").glob("*.json")),
        *sorted((ROOT / "tests").glob("test_artsquad*.py")),
        ROOT / "dist" / "index.html",
        ROOT / "dist" / "baseline-v1.html",
        ROOT / "dist" / "styles.css",
        ROOT / "dist" / "app.js",
        ROOT / "dist" / "surface-lab.html",
        ROOT / "dist" / "surface-lab.js",
        ROOT / "dist" / "artsquad.html",
        ROOT / "dist" / "artsquad.js",
        ROOT / "dist" / "artsquad.css",
        ROOT / "dist" / "artsquad-evidence.css",
        *sorted((ROOT / "dist" / "vendor").glob("*")),
        *sorted((ROOT / "pipeline").rglob("*.py")),
    ]
    with zipfile.ZipFile(ASSETS / "ghostmap-v1-source.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in source_files:
            if path.exists():
                archive.write(path, path.relative_to(ROOT))
    print(f"site artifacts copied to {ASSETS}")


if __name__ == "__main__":
    main()

