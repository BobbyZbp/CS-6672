#!/usr/bin/env python3
"""Read-only native shared-track and calibration diagnostics for Arts Quad.

Collection labels are retrieval hypotheses, not pixel/building annotations.
Neither an epipolar edge nor a shared track certifies two-building coverage,
physical adjacency, independent exposures, metric accuracy or a demo milestone.
"""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from fractions import Fraction
from itertools import combinations
from numbers import Integral
from pathlib import Path

import numpy as np

from ghostmap.sfm.learned import select_training_images, sha256, write_json

CORE = frozenset({'morrill', 'mcgraw-hall', 'white', 'sibley', 'tjaden', 'goldwin-smith', 'lincoln'})
PAIR_BASE = 2147483647
SCHEMA_VERSION = 1
THRESHOLDS = {
    'low_pair_median_angle_degrees': 1.0,
    'very_low_pair_median_angle_degrees': .25,
    'extreme_focal_max_dimension_ratio_below': .25,
    'extreme_focal_max_dimension_ratio_above': 4.0,
    'large_simple_radial_absolute_k': .5,
    'exif35_focal_factor_outside': [0.5, 2.0],
    'camera_roundtrip_max_error_px_above': .5,
}


def percentiles(values):
    values = list(values)
    if any(not math.isfinite(float(v)) for v in values):
        raise ValueError('Non-finite geometric diagnostic')
    return {str(q): float(np.percentile(values, q)) for q in (5, 50, 95)} if values else {}


def angle_degrees(center_a, center_b, point):
    vectors = [np.asarray(c, dtype=float) - np.asarray(point, dtype=float) for c in (center_a, center_b)]
    if any(v.shape != (3,) or not np.isfinite(v).all() or np.linalg.norm(v) == 0 for v in vectors):
        raise ValueError('Invalid point or camera-center ray')
    return math.degrees(math.acos(float(np.clip(np.dot(vectors[0], vectors[1]) /
                                                   (np.linalg.norm(vectors[0]) * np.linalg.norm(vectors[1])), -1, 1))))


def camera_warnings(camera):
    """Screen fitted camera strain; thresholds are warnings, never acceptance."""
    width, height = camera['width'], camera['height']
    focal = float(camera['focal_px'])
    if min(width, height) <= 0 or not math.isfinite(focal) or focal <= 0:
        raise ValueError('Invalid camera dimensions/focal length')
    ratio = focal / max(width, height)
    warnings = []
    if ratio < THRESHOLDS['extreme_focal_max_dimension_ratio_below'] or ratio > THRESHOLDS['extreme_focal_max_dimension_ratio_above']:
        warnings.append('extreme-focal-ratio')
    k = camera.get('simple_radial_k')
    if k is not None:
        if not math.isfinite(float(k)): raise ValueError('Non-finite radial distortion')
        if abs(float(k)) > THRESHOLDS['large_simple_radial_absolute_k']: warnings.append('large-fitted-radial-distortion')
    prior = None
    value = camera.get('exif', {}).get('focal_length_35mm')
    try:
        focal35 = float(Fraction(str(value)))
        if focal35 > 0:
            prior = focal35 * math.hypot(width, height) / math.hypot(36, 24)
            factor = focal / prior
            if factor < .5 or factor > 2: warnings.append('focal-disagrees-with-weak-exif35-prior')
    except (ValueError, TypeError, ZeroDivisionError):
        pass
    roundtrip = camera.get('roundtrip')
    if roundtrip:
        if roundtrip['valid_samples'] != roundtrip['samples']: warnings.append('camera-image-grid-unprojection-failed')
        if roundtrip['maximum_error_px'] is not None and roundtrip['maximum_error_px'] > .5:
            warnings.append('camera-image-grid-roundtrip-error')
    return {'focal_max_dimension_ratio': ratio, 'weak_exif35_focal_px': prior,
            'fitted_to_weak_exif35_focal_ratio': focal / prior if prior else None, 'warnings': warnings}


def summarize_component(cameras, points):
    """Pure native-track summary; duplicate observations never inflate support."""
    for identifier in [c['id'] for c in cameras] + [p['id'] for p in points] + [i for p in points for i in p['image_ids']]:
        if isinstance(identifier, bool) or not isinstance(identifier, Integral):
            raise ValueError('Native camera/point/track IDs must be integral')
    lookup = {int(c['id']): c for c in cameras}
    if len(lookup) != len(cameras): raise ValueError('Duplicate native camera ID')
    if len({c['name'] for c in cameras}) != len(cameras): raise ValueError('Duplicate camera name')
    for camera in cameras:
        if any(not isinstance(camera.get(key), str) or not camera[key].strip()
               for key in ('source_family_id', 'exposure_group_id')):
            raise ValueError('Missing provenance group')
        center = np.asarray(camera['center'], dtype=float)
        if center.shape != (3,) or not np.isfinite(center).all(): raise ValueError('Invalid camera center')
    grouped = defaultdict(list)
    seen_points, ignored_observations = set(), 0
    for point in points:
        point_id = int(point['id'])
        if point_id in seen_points: raise ValueError('Duplicate native point ID')
        seen_points.add(point_id)
        observations = list(map(int, point['image_ids']))
        ids = sorted(set(observations))
        ignored_observations += len(observations) - len(ids)
        if not set(ids) <= lookup.keys(): raise ValueError('Point observes an undeclared camera')
        xyz = np.asarray(point['xyz'], dtype=float)
        if xyz.shape != (3,) or not np.isfinite(xyz).all(): raise ValueError('Invalid native point')
        for a, b in combinations(ids, 2):
            angle = angle_degrees(lookup[a]['center'], lookup[b]['center'], xyz)
            distance = (np.linalg.norm(np.asarray(lookup[a]['center']) - xyz) +
                        np.linalg.norm(np.asarray(lookup[b]['center']) - xyz)) / 2
            baseline = float(np.linalg.norm(np.asarray(lookup[a]['center']) - lookup[b]['center']))
            grouped[a, b].append((point_id, angle, baseline / distance))
    pairs = []
    for (a, b), rows in sorted(grouped.items()):
        ca, cb = lookup[a], lookup[b]
        ta, tb = set(ca.get('metadata_targets', [])) & CORE, set(cb.get('metadata_targets', [])) & CORE
        angles = percentiles(row[1] for row in rows)
        warnings = []
        if angles['50'] < THRESHOLDS['low_pair_median_angle_degrees']: warnings.append('low-triangulation-angle')
        if angles['50'] < THRESHOLDS['very_low_pair_median_angle_degrees']: warnings.append('very-low-parallax-not-proof-of-pure-rotation')
        if ca['exposure_group_id'] == cb['exposure_group_id']: warnings.append('same-exact-original-group')
        if ca['source_family_id'] == cb['source_family_id']: warnings.append('same-recorded-source-family')
        pairs.append({'a': ca['name'], 'b': cb['name'], 'image_id_a': a, 'image_id_b': b,
                      'shared_native_track_count': len(rows), 'sample_point_ids': [r[0] for r in rows[:10]],
                      'triangulation_angle_degrees_percentiles': angles,
                      'baseline_to_mean_point_distance_percentiles': percentiles(r[2] for r in rows),
                      'different_exact_original_groups': ca['exposure_group_id'] != cb['exposure_group_id'],
                      'different_recorded_source_families': ca['source_family_id'] != cb['source_family_id'],
                      'metadata_core_targets_a': sorted(ta), 'metadata_core_targets_b': sorted(tb),
                      'disjoint_nonempty_metadata_core_labels': bool(ta and tb and not ta & tb),
                      'warnings': warnings})
    diagnostics = []
    for camera in cameras:
        diagnostics.append({key: camera[key] for key in ('name', 'id', 'metadata_targets', 'source_family_id',
                                                       'exposure_group_id', 'camera_model', 'camera_parameters')}
                           | {'simple_radial_k': camera.get('simple_radial_k'),
                              'image_grid_roundtrip': camera.get('roundtrip')}
                           | camera_warnings(camera))
    return {'registered_cameras': len(cameras), 'sparse_points': len(points),
            'duplicate_track_observations_ignored': ignored_observations,
            'camera_calibration': diagnostics, 'shared_track_pairs': pairs,
            'label_disjoint_native_pair_count': sum(p['disjoint_nonempty_metadata_core_labels'] for p in pairs),
            'pair_warning_counts': dict(Counter(w for p in pairs for w in p['warnings'])),
            'camera_warning_counts': dict(Counter(w for c in diagnostics for w in c['warnings']))}


def image_grid_roundtrip(camera):
    pixels = np.asarray([(x, y) for x in np.linspace(0, camera.width, 5)
                         for y in np.linspace(0, camera.height, 5)], dtype=float)
    rays = np.asarray(camera.cam_from_img(pixels), dtype=float)
    valid = np.isfinite(rays).all(axis=1)
    errors = []
    if valid.any():
        projected = np.asarray(camera.img_from_cam(np.c_[rays[valid], np.ones(valid.sum())]), dtype=float)
        finite = np.isfinite(projected).all(axis=1)
        errors = np.linalg.norm(projected[finite] - pixels[valid][finite], axis=1).tolist()
    return {'samples': len(pixels), 'valid_samples': len(errors), 'maximum_error_px': max(errors) if errors else None}


def native_component(model, records):
    lookup = {r['filename']: r for r in records}
    cameras = []
    for image in model.images.values():
        if not image.has_pose: continue
        if image.name not in lookup: raise ValueError('Native camera outside admitted frozen training input')
        record, camera = lookup[image.name], image.camera
        params = list(map(float, camera.params))
        cameras.append({'id': int(image.image_id), 'name': image.name,
                        'center': list(map(float, image.projection_center())),
                        'camera_model': camera.model.name, 'camera_parameters': params,
                        'width': int(camera.width), 'height': int(camera.height),
                        'focal_px': float(camera.calibration_matrix()[0, 0]),
                        'simple_radial_k': params[3] if camera.model.name == 'SIMPLE_RADIAL' else None,
                        'roundtrip': image_grid_roundtrip(camera), 'exif': record.get('exif', {}),
                        'metadata_targets': record.get('discovery', {}).get('targets', []),
                        'source_family_id': record['source_family_id'], 'exposure_group_id': record['exposure_group_id']})
    points = [{'id': int(point_id), 'xyz': list(map(float, point.xyz)),
               'image_ids': [int(e.image_id) for e in point.track.elements]} for point_id, point in model.points3D.items()]
    return summarize_component(cameras, points)


def database_edges(database, records, memberships):
    lookup = {r['filename']: r for r in records}
    edges = []
    with sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True) as connection:
        names = dict(connection.execute('SELECT image_id,name FROM images'))
        if set(names.values()) != lookup.keys(): raise ValueError('Database images differ from frozen training selection')
        for pair_id, inliers, config in connection.execute('SELECT pair_id,rows,config FROM two_view_geometries ORDER BY pair_id'):
            if not inliers: continue
            a_id, b_id = divmod(pair_id, PAIR_BASE)
            a, b = names[a_id], names[b_id]
            ta = set(lookup[a].get('discovery', {}).get('targets', [])) & CORE
            tb = set(lookup[b].get('discovery', {}).get('targets', [])) & CORE
            edges.append({'a': a, 'b': b, 'inliers': int(inliers), 'native_configuration': int(config),
                          'nondegenerate_epipolar': int(config) in (2, 3, 9),
                          'metadata_core_targets_a': sorted(ta), 'metadata_core_targets_b': sorted(tb),
                          'disjoint_nonempty_metadata_core_labels': bool(ta and tb and not ta & tb),
                          'shared_native_components': sorted(set(memberships.get(a, [])) & set(memberships.get(b, []))),
                          'different_recorded_source_families': lookup[a]['source_family_id'] != lookup[b]['source_family_id'],
                          'different_exact_original_groups': lookup[a]['exposure_group_id'] != lookup[b]['exposure_group_id']})
    return edges


def analyze(run, output=None):
    import pycolmap
    run = Path(run).resolve()
    report_path = run / 'report.json'
    report = json.loads(report_path.read_text())
    if report.get('status') != 'sfm_complete' or not (run / 'sfm/mapping-complete.json').is_file():
        raise ValueError('Analyze completed native mapping only')
    snapshot_path = Path(report['snapshot_path']).resolve()
    if sha256(snapshot_path) != report['configuration']['snapshot_sha256']: raise ValueError('Frozen snapshot hash changed')
    snapshot = json.loads(snapshot_path.read_text())
    records = select_training_images(snapshot, report['configuration'].get('targets', []))
    if {r['filename'] for r in records} != set(report['input_images']): raise ValueError('Frozen selection changed')
    models = run / 'sfm/models'
    directories = sorted((p for p in models.iterdir() if p.is_dir() and (p / 'images.bin').is_file()), key=lambda p: int(p.name))
    if any(p.is_symlink() or not p.resolve().is_relative_to(models.resolve()) for p in directories):
        raise ValueError('Native model directory escapes run')
    inputs = [report_path, snapshot_path, run / 'sfm/database.db', run / 'sfm/mapping-complete.json']
    inputs += [p for directory in directories for p in directory.glob('*.bin')]
    inputs += [run / 'images' / record['filename'] for record in records]
    before = {str(p): sha256(p) for p in inputs}
    for record in records:
        if before[str(run / 'images' / record['filename'])] != record['sha256_working']:
            raise ValueError('Fitted training image hash differs from frozen snapshot')
    components, memberships = [], defaultdict(list)
    for directory in directories:
        native = pycolmap.Reconstruction(str(directory))
        component = native_component(native, records)
        component['id'] = directory.name
        for camera in component['camera_calibration']: memberships[camera['name']].append(directory.name)
        components.append(component)
    edges = database_edges(run / 'sfm/database.db', records, memberships)
    after = {str(p): sha256(p) for p in inputs}
    if after != before: raise RuntimeError('Native input changed during read-only bridge analysis')
    result = {'schema_version': SCHEMA_VERSION, 'status': 'diagnostic', 'run_id': report['run_id'],
              'snapshot_id': snapshot['snapshot_id'], 'created_utc': datetime.now(timezone.utc).isoformat(),
              'pycolmap_version': pycolmap.__version__,
              'components': components, 'verified_database_edges': edges, 'thresholds': THRESHOLDS,
              'summary': {'native_components': len(components), 'verified_database_pairs': len(edges),
                          'label_disjoint_verified_pair_count': sum(e['disjoint_nonempty_metadata_core_labels'] for e in edges),
                          'label_disjoint_native_shared_track_pair_count': sum(c['label_disjoint_native_pair_count'] for c in components),
                          'calibration_warning_cameras': sum(bool(c['warnings']) for component in components for c in component['camera_calibration'])},
              'source_sha256': before, 'source_inputs_unchanged': True,
              'claims': {'physical_adjacency_validated': False, 'building_pixel_identity_validated': False,
                         'independent_exposures_validated': False, 'geometry_accuracy_validated': False,
                         'multi_building_coverage_validated': False, 'milestone_passed': False},
              'limitations': [
                  'Metadata targets are collection labels, not verified image regions; even a label-disjoint pair may observe one and the same building.',
                  'Native shared tracks demonstrate fitted component association only. Repeated facades, trees, statues, correlated sources and erroneous calibration can explain apparent bridges.',
                  'Small triangulation angles flag weak parallax; they cannot distinguish pure rotation from distant structure or certify depth.',
                  'Focal and distortion thresholds screen strain, not physical invalidity. EXIF35 is a weak uncropped-image prior, not calibration ground truth.',
                  'Different exact original hashes and recorded source families do not prove independent exposures or photographing sessions.',
                  'No pose fitting, triangulation, alignment, relabeling, model mutation, map merging or rendering is performed.']}
    output = Path(output).resolve() if output else run / 'bridge-analysis.json'
    if output in inputs or output.is_relative_to(models.resolve()) or output.name in {'report.json', 'configuration.json', 'snapshot.json'}:
        raise ValueError('Refusing to overwrite native/source report inputs')
    write_json(output, result)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    print(analyze(args.run, args.output))


if __name__ == '__main__': main()
