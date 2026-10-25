#!/usr/bin/env python3
"""Build local family-supported patches, never a broad volumetric envelope.

Recorded source families are conservative dependency groups, NOT certified
independent exposures. Insufficient support never falls back to a native hull.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

from ghostmap.sfm.learned import ROOT, select_training_images, sha256, write_json

BASENAME = "family-supported"


def support_status(eligible_vertices, faces):
    if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in (eligible_vertices, faces)):
        raise ValueError("Measured support and face counts must be nonnegative integers")
    return "supported_fragment_candidate" if eligible_vertices > 0 and faces > 0 else "insufficient_support"


def family_audit(records, names):
    """Complete grouping: never let an unlabelled image become a new group."""
    by_name = {row["filename"]: row for row in records}
    if len(names) != len(set(names)) or any(name not in by_name for name in names):
        raise ValueError("Every component camera must be a distinct admitted training image")
    groups = defaultdict(list)
    for name in sorted(names):
        row = by_name[name]
        family = row.get("source_family_id")
        if not isinstance(family, str) or not family.strip():
            raise ValueError("Missing recorded source family: " + name)
        groups[family].append(name)
    return {"schema_version": 1, "method": "Frozen snapshot metadata source-family grouping",
            "candidate_groups": [groups[key] for key in sorted(groups)],
            "source_families": {key: groups[key] for key in sorted(groups)},
            "certified_independent_exposures": False,
            "interpretation": "Conservative recorded source families, not certified exposure independence. Same-session photos can contain real baseline but count as one family here."}


def source_materials(exported_images):
    mapping, seen = {}, set()
    for image_id, name in exported_images:
        basename = Path(name).name
        if not basename or basename in seen:
            raise ValueError("Exported camera basenames are missing or ambiguous")
        seen.add(basename)
        mapping["camera_" + str(int(image_id))] = basename
    return mapping


def verify_mesh_vertices(obj, dense_xyz):
    import numpy as np
    vertices, faces, materials = [], [], set()
    for line in Path(obj).read_text().splitlines():
        if line.startswith("v "):
            vertices.append([float(value) for value in line.split()[1:]])
        elif line.startswith("f "):
            corners = [int(value.split("/")[0]) - 1 for value in line.split()[1:]]
            if len(corners) != 3:
                raise ValueError("Supported surface must contain triangles only")
            faces.append(corners)
        elif line.startswith("usemtl "):
            materials.add(line.split(maxsplit=1)[1])
    vertices = np.asarray(vertices, dtype=float)
    dense_xyz = np.asarray(dense_xyz, dtype=float)
    if vertices.shape != dense_xyz.shape or not np.isfinite(vertices).all() or not np.allclose(vertices, dense_xyz, rtol=1e-7, atol=1e-8):
        raise ValueError("Supported OBJ changed dense vertex positions beyond text serialization precision")
    if not faces:
        raise ValueError("Supported OBJ has no local facets")
    faces = np.asarray(faces, dtype=int)
    if faces.min() < 0 or faces.max() >= len(vertices):
        raise ValueError("Supported OBJ references invalid vertices")
    return {"vertices": len(vertices), "used_vertices": len(set(faces.reshape(-1).tolist())), "faces": len(faces),
            "materials": sorted(materials), "dense_vertices_preserved_within_text_precision": True,
            "serialization_tolerance": {"relative": 1e-7, "absolute": 1e-8}}


def bundle_hashes(work):
    obj, mtl = work / (BASENAME + ".obj"), work / (BASENAME + ".mtl")
    files = [obj, mtl]
    for line in mtl.read_text().splitlines():
        if line.startswith("map_Kd "):
            name = line.split(maxsplit=1)[1].strip()
            if Path(name).name != name:
                raise ValueError("Supported material texture must be a local basename")
            path = work / name
            if not path.resolve().is_relative_to(work.resolve()):
                raise ValueError("Supported texture escapes its workspace")
            files.append(path)
    return {path.name: sha256(path) for path in files}


def build(run_path, component):
    import numpy as np
    import pycolmap
    from plyfile import PlyData
    from ghostmap.dense.openmvs_cpu import model_signature

    if not component or Path(component).name != component or component in {".", ".."}:
        raise ValueError("Component must be a local native ID")
    run_path = Path(run_path).resolve()
    report = json.loads((run_path / "report.json").read_text())
    if report.get("status") != "sfm_complete" or component not in {str(row["id"]) for row in report.get("components", [])}:
        raise ValueError("A declared completed native component is required")
    snapshot_path = Path(report["snapshot_path"])
    if sha256(snapshot_path) != report["configuration"]["snapshot_sha256"]:
        raise ValueError("Frozen snapshot hash changed")
    snapshot = json.loads(snapshot_path.read_text())
    if snapshot["snapshot_id"] != report["snapshot_id"]:
        raise ValueError("Frozen snapshot ID changed")
    records = select_training_images(snapshot)
    by_name = {row["filename"]: row for row in records}
    native_path = run_path / "sfm/models" / component
    native = pycolmap.Reconstruction(str(native_path))
    native_names = sorted(image.name for image in native.images.values() if image.has_pose)
    audit = family_audit(records, native_names)
    for name in native_names:
        if sha256(by_name[name]["working_path"]) != by_name[name]["sha256_working"]:
            raise ValueError("Frozen admitted training input changed: " + name)
    work = run_path / "mvs" / component
    mvs_report = json.loads((work / "report.json").read_text())
    signature = model_signature(native)
    if mvs_report.get("status") != "surface_candidate" or mvs_report.get("input_model_signature") != signature:
        raise ValueError("MVS candidate does not match the native model signature")
    if set(mvs_report.get("registered_names", [])) != set(native_names):
        raise ValueError("MVS camera admission differs from the selected component")
    export = pycolmap.Reconstruction(str(work / "export-cameras/sparse"))
    exported = [(int(image_id), image.name) for image_id, image in sorted(export.images.items()) if image.has_pose]
    material_map = source_materials(exported)
    image_names = list(material_map.values())
    if set(image_names) != set(native_names):
        raise ValueError("Exported MVS cameras differ from admitted native training images")
    cloud = PlyData.read(work / "dense.ply")["vertex"].data
    xyz = np.column_stack([cloud[key] for key in ("x", "y", "z")])
    if not np.isfinite(xyz).all():
        raise ValueError("Dense candidate contains nonfinite vertices")
    family_by_name = {name: family for family, names in audit["source_families"].items() for name in names}
    family_by_index = [family_by_name[name] for name in image_names]
    support_counts = []
    for views in cloud["view_indices"]:
        if any(int(view) < 0 or int(view) >= len(family_by_index) for view in views):
            raise ValueError("Dense visibility references an undeclared source image")
        support_counts.append(len({family_by_index[int(view)] for view in views}))
    eligible = sum(count >= 3 for count in support_counts)
    protected = [run_path / "report.json", snapshot_path, work / "dense.ply", work / "dense.mvs", work / "report.json"]
    protected += [path for path in native_path.iterdir() if path.suffix in {".bin", ".txt"}]
    before = {str(path): sha256(path) for path in protected}
    audit_path = work / (BASENAME + "-groups.json")
    write_json(audit_path, audit)
    result_path = work / (BASENAME + "-report.json")
    identity = {"snapshot_sha256": report["configuration"]["snapshot_sha256"], "native_model_signature": signature,
                "dense_ply_sha256": before[str(work / "dense.ply")], "family_groups_sha256": sha256(audit_path)}
    if result_path.exists():
        previous = json.loads(result_path.read_text())
        if previous.get("input_identity") != identity:
            raise ValueError("Existing supported fragment inputs differ; preserve it and use a new run")
        previous["input_model_signature"] = signature
        if previous.get("status") == "insufficient_support":
            write_json(result_path, previous)
            return previous
        if previous.get("status") == "supported_fragment_candidate":
            verify_mesh_vertices(work / (BASENAME + ".obj"), xyz)
            hashes = bundle_hashes(work)
            if previous.get("outputs_sha256") and previous["outputs_sha256"] != hashes:
                raise ValueError("Supported mesh/texture bundle changed after construction")
            previous["outputs_sha256"] = hashes
            write_json(result_path, previous)
            return previous
    elif (work / (BASENAME + ".obj")).exists():
        raise ValueError("Unreported supported OBJ exists; refusing overwrite")
    result = {"schema_version": 1, "component_id": component, "input_identity": identity, "input_model_signature": signature,
              "status": support_status(eligible, 0), "source_family_count": len(audit["source_families"]),
              "dense_points": len(xyz), "points_with_three_recorded_families": eligible, "vertices": 0, "faces": 0,
              "support_unit": "Conservative recorded metadata source families, NOT certified independent exposures",
              "minimum_vertex_family_support": 3, "minimum_common_facet_family_support": 2,
              "maximum_projected_edge_pixels_at_mvs_resolution": 12, "maximum_edge_fraction_of_depth": .03,
              "native_volumetric_candidate_preserved": True, "source_cloud_geometry_modified": False,
              "source_materials": {}, "independent_exposures_validated": False, "milestone_pass_authorized": False,
              "limitations": ["Local observed fragments only; no broad hull, gap filling, authored alignment or generated architecture.",
                              "Source-family labels are conservative metadata groups, not certified independent exposures.",
                              "Camera calibration, depth correctness, target identity, completeness and independent holdout accuracy remain unvalidated.",
                              "Surface material identifies a source photograph; no D0/D1 achievement is authorized."]}
    try:
        if not eligible:
            result["reason"] = "No fused vertex has at least three recorded source-family supports; native hull is not a fallback."
        else:
            command = [sys.executable, str(ROOT / "pipeline/mesh_supported_patches.py"), "--workspace", str(work),
                       "--exposure-audit", str(audit_path), "--output-basename", BASENAME]
            process = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
            (work / (BASENAME + "-build.log")).write_text(process.stdout)
            if process.returncode:
                if "No jointly supported local facets" not in process.stdout:
                    raise RuntimeError("Supported mesher failed; inspect " + str(work / (BASENAME + "-build.log")))
                result["reason"] = "No local facets meet family, view, depth, normal and image-edge support; native hull is not a fallback."
            else:
                measurement = verify_mesh_vertices(work / (BASENAME + ".obj"), xyz)
                if any(material not in material_map for material in measurement["materials"]):
                    raise ValueError("A supported material has no admitted exported source camera")
                result.update(measurement, status=support_status(eligible, measurement["faces"]),
                              source_materials={material: material_map[material] for material in measurement["materials"]},
                              obj=BASENAME + ".obj", mtl=BASENAME + ".mtl", outputs_sha256=bundle_hashes(work))
                # Keep the helper's exploratory artifact, but remove its
                # misleading exposure wording from the authoritative report.
                helper_path = work / (BASENAME + "-mesh-report.json")
                helper = json.loads(helper_path.read_text())
                helper.update(support_unit=result["support_unit"], certified_independent_exposures=False)
                write_json(helper_path, helper)
    except Exception as error:
        result.update(status="error", error=type(error).__name__ + ": " + str(error))
        raise
    finally:
        for name, digest in before.items():
            if not Path(name).is_file() or sha256(name) != digest:
                result.update(status="error", source_artifacts_unchanged=False)
                write_json(result_path, result)
                raise RuntimeError("Source artifact changed during supported meshing: " + name)
        result["source_artifacts_unchanged"] = True
        result["source_artifacts_sha256"] = before
        write_json(result_path, result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--component", required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.run, args.component), indent=2), flush=True)


if __name__ == "__main__":
    main()
