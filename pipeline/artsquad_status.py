#!/usr/bin/env python3
"""Build a diagnostic/milestone status without changing existing data or models."""

import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from artsquad_contracts import evaluate_milestones

ROOT = Path(__file__).resolve().parents[1]


def _read(path):
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def validate_report_references(value, root=ROOT):
    """Copy evidence; reject passed attestations with absent/outside reports.

    A report's existence does not establish scientific truth. Only reviewed
    stage validators should author passed attestations; see the contract doc.
    """
    if isinstance(value, list):
        return [validate_report_references(item, root) for item in value]
    if not isinstance(value, dict):
        return value
    output = {key: validate_report_references(item, root) for key, item in value.items()}
    if value.get("status") == "passed":
        report = value.get("report")
        if not isinstance(report, str) or not report.strip():
            output.update(status="pending", reason="Passed claim has no report reference.")
            return output
        path = (root / report).resolve()
        try:
            path.relative_to(root.resolve())
        except ValueError:
            output.update(status="failed", reason="Validation report must be a local project artifact, not an external path.")
            return output
        if not path.is_file():
            output.update(status="pending", reason="Referenced validation report is missing: " + report)
            return output
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            output.update(status="pending", reason="Referenced validation report is unreadable: " + report)
            return output
        if value.get("report_sha256") and value["report_sha256"] != digest:
            output.update(status="failed", reason="Validation report SHA256 differs from the frozen attestation.")
        else:
            output["report_sha256"] = digest
    return output


def probe_local_resources(root=ROOT):
    """Read local hardware/build facts only; never SSH, buy or submit work."""
    disk = shutil.disk_usage(root)
    memory = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, value = line.split(":", 1)
            if key in {"MemTotal", "MemAvailable"}:
                memory[key] = int(value.strip().split()[0]) * 1024
    except (OSError, ValueError):
        pass
    code = """import importlib.util,json
r={}
for name in ('torch','pycolmap'):
    try:
        module=__import__(name)
        value={'installed':True,'version':getattr(module,'__version__','unknown')}
        if name=='torch':
            value.update(cuda_available=bool(module.cuda.is_available()),cuda_build=module.version.cuda)
        else:
            value['cuda_build']=getattr(module,'has_cuda',None)
        r[name]=value
    except Exception as error:
        r[name]={'installed':importlib.util.find_spec(name) is not None,'probe_error':type(error).__name__}
print(json.dumps(r))
"""
    try:
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=25, check=False)
        software = json.loads(result.stdout) if result.returncode == 0 else {"probe_error": "Local module probe failed."}
    except (OSError, subprocess.TimeoutExpired, ValueError):
        software = {"probe_error": "Local module probe unavailable or timed out."}
    return {"scope": "local only; no remote credentials, purchases or job submission", "python_executable": sys.executable,
            "disk_free_gib": round(disk.free / 2**30, 2), "disk_total_gib": round(disk.total / 2**30, 2),
            "host_memory_gib": round(memory.get("MemTotal", 0) / 2**30, 2) if memory else None,
            "host_available_memory_gib": round(memory.get("MemAvailable", 0) / 2**30, 2) if memory else None,
            "software": software, "remote_resource_status": "unverified", "authorized_gpu_budget_hours": None}


def inspect_existing_facts(root=ROOT):
    manifest = _read(root / "data/artsquad_modern/manifest.json")
    coverage = _read(root / "data/artsquad_modern/coverage.json")
    audit = _read(root / "data/artsquad_modern/scene-input-audit.json")
    images = manifest.get("images", [])
    records = images if isinstance(images, list) else []
    present = sum(isinstance(im, dict) and isinstance(im.get("filename"), str) and (root / "artifacts/artsquad_modern/images" / im["filename"]).is_file() for im in records)
    return {"acquisition_status": manifest.get("status", "unavailable"),
            "discovered_files": coverage.get("discovered_unique_files"),
            "metadata_eligible_files": coverage.get("metadata_eligible_unique_files"),
            "download_manifest_records": len(records), "working_files_present": present,
            "metadata_screen_counts": audit.get("counts", {}),
            "warning": "File presence and metadata categories do not establish independent views, pixel identity, valid geometry, coverage or a delivered demo."}


def build_status(evidence, root=ROOT, probe=True):
    contract = _read(root / "config/artsquad-project.json")
    validated = validate_report_references(evidence, root)
    result = evaluate_milestones(validated)
    result.update(project_id=contract.get("project_id", "ghostmap-artsquad"),
                  generated_at=datetime.now(timezone.utc).isoformat(), kickoff_date=contract.get("kickoff_date"),
                  schedule=contract.get("milestones", {}), diagnostics=inspect_existing_facts(root),
                  execution_policy=contract.get("execution_policy", {}),
                  resources=probe_local_resources(root) if probe else {"probe": "skipped; no hardware assertion made"},
                  evidence=validated)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, help="Validator-authored JSON; omitted means no achievements are inferred.")
    parser.add_argument("--output", default="artifacts/artsquad_modern/project-status.json", help="Project-relative JSON output, or '-' for stdout only.")
    parser.add_argument("--skip-resource-probe", action="store_true", help="Skip optional local module import probe.")
    args = parser.parse_args()
    evidence_path = args.evidence or ROOT / "artifacts/artsquad_modern/milestone-evidence.json"
    if args.evidence is not None:
        # Explicitly requested evidence must not be silently ignored.
        try:
            evidence = json.loads(evidence_path.read_text())
        except (OSError, ValueError) as error:
            parser.error("Cannot read evidence JSON: " + str(error))
        if not isinstance(evidence, dict):
            parser.error("Evidence JSON must be an object.")
    else:
        evidence = _read(evidence_path)
    result = build_status(evidence, probe=not args.skip_resource_probe)
    encoded = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if args.output == "-":
        print(encoded, end="")
    else:
        output = Path(args.output)
        output = output if output.is_absolute() else ROOT / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded)
        print(json.dumps({"output": str(output), "milestones": {key: value["status"] for key, value in result["milestones"].items()}, "project_complete": result["project_complete"]}, indent=2))


if __name__ == "__main__":
    main()
