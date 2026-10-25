#!/usr/bin/env python3
"""Index actual supported OBJ triangles to estimated MVS source visibility.

The index preserves sequential OBJ face order for Three.js OBJLoader raycasts.
It does not alter geometry or certify per-face accuracy, independence, semantic
building identity, coverage, or any project milestone.
"""
from __future__ import annotations

import argparse
import json
import numbers
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from ghostmap.surface.dense_support import normalized_basename, summarize_visibility


def parse_faces(obj_text, dense_xyz):
    """Return one actual face per source OBJ f line, without triangulation."""
    vertices, faces, materials = [], [], []
    material = None; object_declarations = 0; saw_faces = False
    for line_number, raw in enumerate(obj_text.splitlines(), 1):
        line = raw.partition('#')[0].strip()
        if not line: continue
        fields = line.split(); opcode = fields[0]
        if opcode in {'o', 'g'}:
            object_declarations += 1
            if object_declarations > 1 or saw_faces:
                raise ValueError('Multiple OBJ objects/groups could change OBJLoader faceIndex order')
        elif opcode in {'l', 'p'}:
            raise ValueError('OBJ lines/points are not a single triangle mesh')
        elif opcode == 'v':
            if len(fields) != 4: raise ValueError(f'Line {line_number}: expected unchanged XYZ vertex only')
            try: vertices.append([float(value) for value in fields[1:]])
            except ValueError as error: raise ValueError(f'Line {line_number}: invalid XYZ') from error
        elif opcode == 'usemtl':
            if len(fields) != 2: raise ValueError('Expected one explicit material name')
            material = fields[1]
        elif opcode == 'f':
            if len(fields) != 4: raise ValueError('Only existing triangle faces are accepted; no implicit triangulation')
            if material is None: raise ValueError('Face has no explicit source texture material')
            try:
                indices = [int(value.split('/')[0]) - 1 for value in fields[1:]]
            except ValueError as error: raise ValueError(f'Line {line_number}: invalid vertex index') from error
            if any(index < 0 for index in indices): raise ValueError('Only positive absolute OBJ vertex indices are supported')
            if len(set(indices)) != 3: raise ValueError('Triangle repeats a vertex')
            faces.append(indices); materials.append(material); saw_faces = True
    vertices = np.asarray(vertices, dtype=float)
    dense_xyz = np.asarray(dense_xyz, dtype=float)
    if (vertices.shape != dense_xyz.shape or vertices.ndim != 2 or vertices.shape[1] != 3
            or not np.isfinite(vertices).all() or not np.isfinite(dense_xyz).all()
            or not np.allclose(vertices, dense_xyz, rtol=1e-7, atol=1e-8)):
        raise ValueError('OBJ must retain every dense XYZ row in original order within %.8g serialization tolerance')
    if not faces: raise ValueError('Supported OBJ contains no actual triangle facets')
    if max(max(face) for face in faces) >= len(vertices): raise ValueError('Face references an out-of-range dense vertex')
    return faces, materials


def build_face_index(obj_text, dense_xyz, visibility, records, camera_names, material_sources=None):
    """Pure face-order index; all visibility remains an estimated diagnostic."""
    parsed_faces, materials = parse_faces(obj_text, dense_xyz)
    admission = summarize_visibility(records, camera_names, [])
    cameras = admission['camera_provenance']
    try: visibility = list(visibility)
    except TypeError as error: raise ValueError('Dense visibility must contain one sequence per vertex') from error
    if len(visibility) != len(dense_xyz): raise ValueError('Dense visibility row count does not match retained XYZ rows')
    checked = []
    for point, views in enumerate(visibility):
        if isinstance(views, (str, bytes, dict)): raise ValueError('Malformed dense visibility row')
        try: views = list(views)
        except TypeError as error: raise ValueError('Malformed dense visibility row') from error
        if any(isinstance(view, bool) or not isinstance(view, numbers.Integral) for view in views):
            raise ValueError('Dense visibility must use integer compact camera indices')
        if any(view < 0 or view >= len(cameras) for view in views):
            raise ValueError(f'Dense vertex {point}: visibility index outside exported camera order')
        checked.append(set(map(int, views)))
    family_sets = [{cameras[index]['source_family_id'] for index in views} for views in checked]
    normalized_materials = ({name: normalized_basename(source) for name, source in material_sources.items()}
                            if material_sources is not None else None)
    faces = []
    for face_index, (corners, material) in enumerate(zip(parsed_faces, materials)):
        common = sorted(set.intersection(*(checked[index] for index in corners)))
        images = [cameras[index]['filename'] for index in common]
        if normalized_materials is not None:
            if material not in normalized_materials: raise ValueError('Actual face material has no admitted camera mapping: ' + material)
            if normalized_materials[material] not in images:
                raise ValueError('Texture camera is not present in all three vertices\' estimated visibility')
        faces.append({'face_index': face_index, 'vertex_indices': corners,
                      'common_images': images,
                      'common_recorded_exposure_groups': sorted({cameras[index]['exposure_group_id'] for index in common}),
                      'common_recorded_source_families': sorted({cameras[index]['source_family_id'] for index in common}),
                      'vertex_min_recorded_source_families': min(len(family_sets[index]) for index in corners),
                      'texture_material': material})
    return {'schema_version': 1, 'status': 'estimated_mvs_face_visibility',
            'face_count': len(faces), 'vertex_count': len(dense_xyz),
            'face_index_convention': 'Zero-based sequential triangle f records in the unchanged single-object OBJ; matches OBJLoader Mesh faceIndex only when face order is retained. Material switches do not reset face_index.',
            'camera_index_convention': admission['camera_index_convention'],
            'dense_vertices_preserved_within_text_precision': True,
            'serialization_tolerance': {'relative': 1e-7, 'absolute': 1e-8},
            'camera_provenance': cameras, 'faces': faces,
            'claims': {'geometry_modified': False, 'independent_captures_certified': False,
                       'per_face_geometry_accuracy_certified': False, 'semantic_coverage_certified': False,
                       'milestone_passed': False},
            'limitations': ['Common images are the intersection of the three retained vertices\' estimated MVS visibility, not independently verified per-face observations.',
                           'Exact-hash exposure IDs and metadata source-family IDs do not certify independent captures.',
                           'Vertex visibility does not prove that an entire triangle has correct depth, calibration, occlusion or texture.',
                           'No generated surface, geometric repair, completeness claim or automatic D0/D1 acceptance is introduced.']}


def index(run, component):
    import pycolmap
    from plyfile import PlyData
    from ghostmap.sfm.learned import sha256, write_json

    if not re.fullmatch('[A-Za-z0-9_-]+', component): raise ValueError('Unsafe component ID')
    run = Path(run).resolve(); workspace = run / 'mvs' / component
    run_report = json.loads((run / 'report.json').read_text())
    if run_report.get('status') != 'sfm_complete': raise ValueError('Completed SfM run required')
    declared = [item for item in run_report['components'] if str(item['id']) == component]
    if len(declared) != 1: raise ValueError('Component absent or ambiguous in run')
    snapshot_path = Path(run_report['snapshot_path']).resolve()
    family_report_path = workspace / 'family-supported-report.json'
    family_report = json.loads(family_report_path.read_text())
    if family_report.get('status') != 'supported_fragment_candidate':
        raise ValueError('A successful family-supported surface is required; insufficient support has no face index')
    if str(family_report.get('component_id')) != component: raise ValueError('Supported surface component mismatch')
    snapshot_sha = sha256(snapshot_path)
    if (snapshot_sha != run_report['configuration']['snapshot_sha256']
            or snapshot_sha != family_report['input_identity']['snapshot_sha256']):
        raise ValueError('Frozen snapshot provenance mismatch')
    snapshot = json.loads(snapshot_path.read_text())
    if snapshot['snapshot_id'] != run_report['snapshot_id']: raise ValueError('Snapshot identity mismatch')
    obj_path = workspace / 'family-supported.obj'; dense_path = workspace / 'dense.ply'
    sources = {'snapshot_sha256': snapshot_sha, 'dense_ply_sha256': sha256(dense_path),
               'obj_sha256': sha256(obj_path), 'family_report_sha256': sha256(family_report_path)}
    if sources['dense_ply_sha256'] != family_report['input_identity']['dense_ply_sha256']:
        raise ValueError('Supported surface dense provenance mismatch')
    exported_path = workspace / 'export-cameras/sparse'
    calibration = pycolmap.Reconstruction(str(exported_path))
    exported = sorted(calibration.images.items())
    if any(not image.has_pose for _, image in exported): raise ValueError('Exported camera is unposed')
    camera_names = [image.name for _, image in exported]
    if {normalized_basename(name) for name in camera_names} != {
            normalized_basename(item['name']) for item in declared[0]['cameras']}:
        raise ValueError('Exported camera names differ from run component')
    material_sources = {'camera_' + str(image_id): image.name for image_id, image in exported}
    reported_materials = family_report.get('source_materials', {})
    for material, name in reported_materials.items():
        if material not in material_sources or normalized_basename(name) != normalized_basename(material_sources[material]):
            raise ValueError('Supported texture material provenance disagrees with exported cameras')
    cloud = PlyData.read(dense_path)['vertex'].data
    xyz = np.column_stack([cloud[key] for key in ('x', 'y', 'z')])
    if 'view_indices' not in cloud.dtype.names: raise ValueError('Dense PLY has no recorded visibility')
    result = build_face_index(obj_path.read_text(), xyz, cloud['view_indices'], snapshot['images'],
                              camera_names, reported_materials)
    if result['face_count'] != family_report['faces'] or result['vertex_count'] != family_report['vertices']:
        raise ValueError('OBJ counts differ from successful supported report')
    minimum_vertex = family_report['minimum_vertex_family_support']
    minimum_common = family_report['minimum_common_facet_family_support']
    if any(face['vertex_min_recorded_source_families'] < minimum_vertex
           or len(face['common_recorded_source_families']) < minimum_common for face in result['faces']):
        raise ValueError('Actual facet fails the supported report\'s recorded family thresholds')
    if (sha256(snapshot_path) != sources['snapshot_sha256'] or sha256(dense_path) != sources['dense_ply_sha256']
            or sha256(obj_path) != sources['obj_sha256'] or sha256(family_report_path) != sources['family_report_sha256']):
        raise ValueError('Source artifacts changed during face indexing')
    result.update(created_utc=datetime.now(timezone.utc).isoformat(), run_id=run_report['run_id'],
                  component_id=component, snapshot_id=snapshot['snapshot_id'], source_hashes=sources)
    destination = workspace / 'family-face-evidence.json'
    write_json(destination, result)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--component', required=True)
    args = parser.parse_args()
    print(index(args.run, args.component))


if __name__ == '__main__': main()
