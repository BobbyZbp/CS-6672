#!/usr/bin/env python3
"""Audit recorded fused-point visibility without changing geometry.

Recorded camera, exact-original-hash and metadata-family counts are provenance
diagnostics, not certified independent captures, semantic coverage, per-face
support, geometry accuracy or a D0/D1 acceptance decision.
"""
from __future__ import annotations

import argparse
import json
import numbers
import re
import subprocess
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path, PurePosixPath


def normalized_basename(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('Camera/source filename must be a nonempty string')
    name = PurePosixPath(value.replace('\\', '/')).name
    if not name or name in {'.', '..'}:
        raise ValueError('Invalid camera/source basename')
    return name


def _date_range(record):
    evidence = record.get('capture_evidence')
    if not isinstance(evidence, dict): return None
    try:
        earliest = date.fromisoformat(evidence['earliest'])
        latest = date.fromisoformat(evidence['latest'])
        if latest < earliest: return None
        return earliest, latest
    except (ValueError, TypeError, KeyError):
        return None


def _histogram(counter):
    return {str(key): int(counter[key]) for key in sorted(counter)}


def summarize_visibility(records, camera_names, visibility):
    """Pure diagnostic summary; reject malformed or leaked provenance.

    ``records`` is the full snapshot image list (including test/excluded
    records), ``camera_names`` is the compact MVS camera-index order, and
    ``visibility`` is one integer-index sequence per fused point. Different
    camera names can intentionally share an exposure or source-family ID.
    """
    if not isinstance(records, (list, tuple)):
        raise ValueError('records must be the full snapshot image list')
    lookup = {}
    train_groups = {'exposure_group_id': set(), 'source_family_id': set()}
    test_groups = {'exposure_group_id': set(), 'source_family_id': set()}
    for record in records:
        if not isinstance(record, dict): raise ValueError('Malformed snapshot record')
        name = normalized_basename(record.get('filename'))
        if name in lookup: raise ValueError('Ambiguous duplicate normalized source basename: ' + name)
        lookup[name] = record
        if record.get('split') in {'train', 'test'}:
            groups = train_groups if record['split'] == 'train' else test_groups
            for field in groups:
                value = record.get(field)
                if not isinstance(value, str) or not value.strip():
                    raise ValueError('Missing global ' + record['split'] + ' ' + field)
                groups[field].add(value)
    for field in train_groups:
        if train_groups[field] & test_groups[field]:
            raise ValueError('Global train/test leakage: ' + field)
    if isinstance(camera_names, (str, bytes)):
        raise ValueError('camera_names must be an ordered sequence of image names')
    try: camera_names = iter(camera_names)
    except TypeError as error: raise ValueError('camera_names must be an ordered sequence of image names') from error
    cameras, names = [], []
    for source in camera_names:
        name = normalized_basename(source)
        if name in names: raise ValueError('Duplicate normalized exported camera: ' + name)
        if name not in lookup: raise ValueError('Foreign exported camera absent from snapshot: ' + name)
        record = lookup[name]
        validation = record.get('validation')
        if (record.get('split') != 'train' or record.get('role') != 'scene-candidate'
                or not isinstance(validation, dict) or validation.get('passed') is not True):
            raise ValueError('Held-out, excluded or unadmitted exported camera: ' + name)
        cameras.append(record); names.append(name)
    if not cameras: raise ValueError('No admitted training cameras supplied')
    ranges = [_date_range(camera) for camera in cameras]
    histograms = {name: Counter() for name in ('raw_camera_count', 'exact_original_exposure_group_count',
                  'metadata_source_family_count', 'unknown_capture_camera_count', 'capture_span_days_bucket',
                  'earliest_capture_year', 'latest_capture_year')}
    total = 0; duplicate_camera_entries = 0; unknown_temporal_points = 0
    thresholds = Counter()
    try: iterator = iter(visibility)
    except TypeError as error: raise ValueError('visibility must contain per-point index sequences') from error
    for point, indices in enumerate(iterator):
        if isinstance(indices, (str, bytes, dict)):
            raise ValueError(f'Point {point}: malformed visibility sequence')
        try: entries = list(indices)
        except TypeError as error: raise ValueError(f'Point {point}: visibility must be an index sequence') from error
        if any(isinstance(index, bool) or not isinstance(index, numbers.Integral) for index in entries):
            raise ValueError(f'Point {point}: visibility indices must be integers (not floats/bools)')
        entries = [int(index) for index in entries]
        if any(index < 0 or index >= len(cameras) for index in entries):
            raise ValueError(f'Point {point}: visibility index outside compact camera vector')
        # Count an image once, even if a malformed producer repeated its index.
        unique = sorted(set(entries)); duplicate_camera_entries += len(entries) - len(unique)
        exposures = {cameras[index]['exposure_group_id'] for index in unique}
        families = {cameras[index]['source_family_id'] for index in unique}
        known = [ranges[index] for index in unique if ranges[index] is not None]
        unknown = len(unique) - len(known)
        histograms['raw_camera_count'][len(unique)] += 1
        histograms['exact_original_exposure_group_count'][len(exposures)] += 1
        histograms['metadata_source_family_count'][len(families)] += 1
        histograms['unknown_capture_camera_count'][unknown] += 1
        if known:
            earliest = min(first for first, _ in known); latest = max(last for _, last in known)
            span = (latest - earliest).days
            bucket = '0' if not span else '1-30' if span <= 30 else '31-365' if span <= 365 else '366-1826' if span <= 1826 else '1827+'
            histograms['capture_span_days_bucket'][bucket] += 1
            histograms['earliest_capture_year'][earliest.year] += 1
            histograms['latest_capture_year'][latest.year] += 1
        else:
            histograms['capture_span_days_bucket']['unknown'] += 1
        if unknown or not unique: unknown_temporal_points += 1
        for threshold in (2, 3):
            thresholds[f'points_with_at_least_{threshold}_recorded_cameras'] += len(unique) >= threshold
            thresholds[f'points_with_at_least_{threshold}_recorded_exposure_groups'] += len(exposures) >= threshold
            thresholds[f'points_with_at_least_{threshold}_recorded_source_families'] += len(families) >= threshold
        total += 1
    known_camera_ranges = [value for value in ranges if value]
    return {
        'schema_version': 1, 'status': 'diagnostic', 'point_count': total,
        'camera_count': len(cameras), 'camera_names': names,
        'camera_provenance': [{'index': index, 'filename': names[index],
                               'exposure_group_id': camera['exposure_group_id'],
                               'source_family_id': camera['source_family_id'], 'split': 'train'}
                              for index, camera in enumerate(cameras)],
        'camera_index_convention': 'Compact zero-based MVS image vector, joined by normalized basename; exported COLMAP images sorted by original image ID, not IMAGE_ID minus one.',
        'histograms': {key: _histogram(value) for key, value in histograms.items()},
        'point_counts': {**dict(thresholds), 'points_with_empty_visibility': histograms['raw_camera_count'][0],
                         'points_with_unknown_or_incomplete_capture_range': unknown_temporal_points},
        'duplicate_visibility_entries_ignored': duplicate_camera_entries,
        'source_grouping': {'exact_original_exposure_groups': len({c['exposure_group_id'] for c in cameras}),
                            'metadata_source_families': len({c['source_family_id'] for c in cameras}),
                            'global_train_test_exposure_and_family_disjoint': True,
                            'independent_capture_count': None},
        'temporal_ranges': {
            'known_camera_ranges': len(known_camera_ranges), 'unknown_camera_ranges': len(cameras) - len(known_camera_ranges),
            'earliest_asserted_capture': min((first for first, _ in known_camera_ranges), default=None).isoformat() if known_camera_ranges else None,
            'latest_asserted_capture': max((last for _, last in known_camera_ranges), default=None).isoformat() if known_camera_ranges else None,
            'per_camera': [{'index': index, 'filename': names[index],
                            'earliest': value[0].isoformat() if value else None,
                            'latest': value[1].isoformat() if value else None,
                            'evidence': cameras[index].get('capture_evidence')} for index, value in enumerate(ranges)],
            'interpretation': 'Capture metadata interval of contributing cameras, not an estimated building existence interval; mixed-year visibility does not prove unchanged geometry.'},
        'claims': {'geometry_modified': False, 'independent_captures_certified': False,
                   'geometry_accuracy_validated': False, 'per_face_support_validated': False,
                   'semantic_building_coverage_validated': False, 'milestone_passed': False},
        'limitations': [
            'Counts describe recorded fused-point visibility only; no mesh face, facade or target identity is certified.',
            'Exact-byte duplicates detected are only a subset of true exposure relationships; these counts are not a certified lower bound on independent captures.',
            'Metadata source families may under-group unknown relationships or conservatively over-group sessions. Disjoint IDs do not certify statistical independence.',
            'MVS visibility is estimated from the fitted cameras and images, not independent geometric ground truth.',
            'Temporal spans include asserted date uncertainty and cannot prove that structures persisted across the span.',
            'This report never changes dense points, modifies meshes or passes D0/D1.']}


def audit(run, component):
    from plyfile import PlyData
    import pycolmap
    from run_artsquad_sfm import sha256, write_json
    from run_cpu_mvs import command

    run = Path(run).resolve()
    if not re.fullmatch('[A-Za-z0-9_-]+', component): raise ValueError('Unsafe component identifier')
    run_report = json.loads((run / 'report.json').read_text())
    if run_report.get('status') != 'sfm_complete': raise ValueError('SfM run is not complete')
    components = [item for item in run_report['components'] if str(item['id']) == component]
    if len(components) != 1: raise ValueError('Component absent or ambiguous in SfM report')
    snapshot_path = Path(run_report['snapshot_path']).resolve()
    if sha256(snapshot_path) != run_report['configuration']['snapshot_sha256']:
        raise ValueError('Frozen snapshot SHA256 differs from the run configuration')
    snapshot = json.loads(snapshot_path.read_text())
    if snapshot['snapshot_id'] != run_report['snapshot_id']: raise ValueError('Snapshot and SfM identities disagree')
    workspace = run / 'mvs' / component
    mvs_report = json.loads((workspace / 'report.json').read_text())
    if mvs_report.get('status') != 'surface_candidate': raise ValueError('MVS workspace has not completed')
    expected_model = (run / components[0]['model_path']).resolve()
    if Path(mvs_report['model']).resolve() != expected_model:
        raise ValueError('MVS input model differs from the declared run component')
    export = workspace / 'export-cameras'
    if not (export / 'sparse/images.txt').is_file():
        with (workspace / 'dense-support-camera-export.log').open('w') as output:
            subprocess.run(command('InterfaceCOLMAP') + ['-i', str(workspace / 'dense.mvs'),
                           '-o', str(export), '--binary', '0'], cwd=workspace,
                           check=True, stdout=output, stderr=subprocess.STDOUT)
    calibration = pycolmap.Reconstruction(str(export / 'sparse'))
    cameras = sorted(calibration.images.items())
    if any(not image.has_pose for _, image in cameras): raise ValueError('Export contains an unposed camera')
    camera_names = [image.name for _, image in cameras]
    if {normalized_basename(name) for name in camera_names} != {
            normalized_basename(item['name']) for item in components[0]['cameras']}:
        raise ValueError('Exported camera identities do not match the run component')
    cloud_path = workspace / 'dense.ply'
    cloud = PlyData.read(cloud_path)['vertex'].data
    if 'view_indices' not in cloud.dtype.names: raise ValueError('Dense PLY lacks view_indices')
    result = summarize_visibility(snapshot['images'], camera_names, cloud['view_indices'])
    result.update(created_utc=datetime.now(timezone.utc).isoformat(), run_id=run_report['run_id'],
                  component_id=component, snapshot_id=snapshot['snapshot_id'],
                  source_hashes={'snapshot_sha256': sha256(snapshot_path), 'dense_ply_sha256': sha256(cloud_path),
                                 'dense_mvs_sha256': sha256(workspace / 'dense.mvs'),
                                 'export_images_sha256': sha256(export / 'sparse/images.txt')})
    destination = workspace / 'dense-support-report.json'
    write_json(destination, result)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--component', required=True)
    args = parser.parse_args()
    print(audit(args.run, args.component))


if __name__ == '__main__': main()
