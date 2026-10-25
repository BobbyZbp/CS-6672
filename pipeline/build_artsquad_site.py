#!/usr/bin/env python3
"""Package only measured, provenance-bearing Arts Quad artifacts for the web.

Components keep their original, unrelated similarity frames. No footprint,
basemap, authored building or generative asset is accepted by this packager.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from artsquad_status import build_status
from prepare_artsquad import capture_evidence
from run_artsquad_sfm import sha256, write_json

ROOT = Path(__file__).resolve().parents[1]
CORE = {'morrill', 'mcgraw-hall', 'white', 'sibley', 'tjaden', 'goldwin-smith', 'lincoln'}


def clean_text(value):
    return ' '.join(html.unescape(re.sub('<[^>]*>', '', str(value or ''))).split())


def component_display_order(component):
    """Show measured surface fragments first, never promote category counts.

    The order is presentation only. It confers neither building identity nor
    scientific acceptance on a component with more cameras or facets.
    """
    return (-bool(component.get('mesh')), -component['stats']['mesh_faces'],
            -component['stats']['registered_cameras'], str(component['id']))


def check_distribution_scope(snapshot, destination, local_research_only=False, private_root=None):
    """Never let a research-only provider silently enter the public dist tree."""
    restricted = (snapshot.get('public_redistribution_permitted') is False
                  or snapshot.get('scope') == 'private-research-only'
                  or any(row.get('public_redistribution_permitted') is False for row in snapshot.get('images', [])))
    if local_research_only:
        private_root = Path(private_root or ROOT / 'artifacts/local_previews').resolve()
        destination = Path(destination).resolve()
        if destination == private_root or not destination.is_relative_to(private_root):
            raise ValueError('Research-only preview must use a dedicated subdirectory of artifacts/local_previews, never public dist')
    elif restricted:
        raise ValueError('Research-only source rights prohibit copying this snapshot into a public-source web package')
    return 'private-research-only' if local_research_only else 'public-source-local-preview-release-unreviewed'


def check_terminal_run_status(run):
    if run is not None and run.get('status') not in {'sfm_complete', 'no_model'}:
        raise ValueError('Only a terminal SfM run can replace the displayed package; preserve the previous working preview during matching or execution failure')


def checked_file(parent, name):
    if not name or Path(name).name != name: raise ValueError('Asset must be a local basename: ' + str(name))
    source = (parent / name).resolve()
    if not source.is_relative_to(parent.resolve()) or not source.is_file():
        raise ValueError('Missing or escaping asset: ' + str(source))
    return source


def obj_bundle_files(source):
    """Explicit dependency closure; do not copy working dirs/credentials/original pools."""
    obj = checked_file(source.parent, source.name)
    libraries = [line.split(maxsplit=1)[1].strip() for line in obj.read_text().splitlines() if line.startswith('mtllib ')]
    if len(libraries) != 1: raise ValueError('Expected one explicit material library')
    mtl = checked_file(source.parent, libraries[0]); dependencies = [obj, mtl]
    for line in mtl.read_text().splitlines():
        if line.startswith('map_Kd '): dependencies.append(checked_file(source.parent, line.split(maxsplit=1)[1].strip()))
    return obj, mtl, sorted(set(dependencies))


def copy_obj_bundle(source, target):
    obj, mtl, dependencies = obj_bundle_files(source)
    target.mkdir(parents=True, exist_ok=True)
    for file in set(dependencies): shutil.copy2(file, target / file.name)
    return obj.name, mtl.name


def make_photo(source, destination):
    with Image.open(source) as image:
        image = image.convert('RGB'); image.thumbnail((1280, 1280))
        image.save(destination, quality=87, optimize=True)


def package(snapshot_path, run_path=None, dist=ROOT / 'dist', evidence_path=None, local_research_only=False):
    import numpy as np
    import pycolmap
    snapshot_path = Path(snapshot_path).resolve(); snapshot = json.loads(snapshot_path.read_text())
    records = {i['filename']: i for i in snapshot['images']}
    dist = Path(dist).resolve()
    distribution_scope = check_distribution_scope(snapshot, dist, local_research_only)
    run = json.loads((run_path / 'report.json').read_text()) if run_path else None
    check_terminal_run_status(run)
    if run and (run['snapshot_id'] != snapshot['snapshot_id'] or run['configuration']['snapshot_sha256'] != sha256(snapshot_path)):
        raise ValueError('Run and snapshot hashes disagree; refusing mislabeled web assets')
    assets = dist / 'assets/artsquad'; assets.mkdir(parents=True, exist_ok=True)
    if evidence_path:
        evidence = json.loads(evidence_path.read_text())
    else:
        default_evidence = ROOT / 'artifacts/artsquad_modern/milestone-evidence.json'
        evidence = json.loads(default_evidence.read_text()) if default_evidence.exists() else {}
    status = build_status(evidence, probe=True)
    write_json(ROOT / 'artifacts/artsquad_modern/project-status.json', status)
    # Public status excludes host absolute paths and full input metadata.
    public_status = {k: status[k] for k in ('schema_version', 'milestones', 'project_complete', 'schedule', 'resources', 'interpretation', 'execution_policy')}
    public_status['resources'].pop('python_executable', None)
    write_json(assets / 'project-status.json', public_status)
    run_id = run['run_id'] if run else 'snapshot-' + snapshot['snapshot_id']
    if not re.fullmatch('[A-Za-z0-9_-]+', run_id): raise ValueError('Unsafe run identifier')
    destination = assets / 'runs' / run_id; destination.mkdir(parents=True, exist_ok=True)
    def url(path): return path.relative_to(dist).as_posix()
    if run:
        public_run = {k: run[k] for k in ('schema_version', 'run_id', 'snapshot_id', 'configuration', 'input_images',
                      'status', 'stage', 'created_utc', 'elapsed_seconds', 'components', 'candidate_pairs',
                      'verified_pairs', 'nondegenerate_pairs', 'unregistered_images', 'limitations') if k in run}
        public_run['compute_note'] = 'Elapsed time can include cache reuse; it is not an equal-compute comparison.'
        write_json(destination / 'run-report.json', public_run)
    provenance = []; current_epoch_issues = []
    target_names = {t['id']: t['name'] for t in snapshot['by_target']}
    for image in snapshot['images']:
        row = {key: image.get(key) for key in ('filename', 'title', 'source_url', 'original_url', 'capture_date_asserted',
                           'license', 'license_url', 'artist', 'credit', 'sha256_original', 'sha256_working',
                           'exposure_group_id', 'source_family_id', 'role', 'split', 'validation', 'discovery')}
        epoch_reason = capture_evidence(image, snapshot['config']['acquisition']['capture_year_min'])[1]
        row['current_capture_epoch_screen'] = {'status': 'review' if epoch_reason else 'metadata-consistent-not-certified', 'reason': epoch_reason}
        if image.get('split') in {'train', 'test'} and epoch_reason:
            current_epoch_issues.append({'filename': image['filename'], 'reason': epoch_reason})
        provenance.append(row)
    write_json(destination / 'sources.json', {'snapshot_id': snapshot['snapshot_id'], 'images': provenance,
                                             'limitations': snapshot['limitations'],
                                             'distribution_scope': distribution_scope,
                                             'rights_notice': ('Research-only source images: redistribution rights are unresolved. This dedicated loopback preview is not a public release; do not publish or include it in the public-source demo ZIP.' if local_research_only else 'Per-item source license records retained. Admission is not an institutional/public-release legal review. No restricted archive photographs or weights included.')})
    components = []; quarantined = []
    for component in (run or {}).get('components', []):
        cid = str(component['id'])
        if not re.fullmatch('[0-9]+', cid) or component['model_path'] != 'sfm/models/' + cid:
            raise ValueError('Unexpected component path')
        model_path = (run_path / component['model_path']).resolve()
        if not model_path.is_relative_to(run_path.resolve()): raise ValueError('Escaping component path')
        model = pycolmap.Reconstruction(str(model_path))
        selected_records = [records[im.name] for im in model.images.values() if im.has_pose]
        if (sorted(row['filename'] for row in selected_records) != sorted(c['name'] for c in component['cameras'])
                or len(selected_records) != component['registered_cameras'] or model.num_points3D() != component['sparse_points']):
            raise ValueError('Native saved component and diagnostic identities disagree. Run inspect_artsquad_run.py; never relabel a different model.')
        if any(i['split'] != 'train' or i.get('validation', {}).get('passed') is not True for i in selected_records):
            raise ValueError('Unadmitted/held-out image found in mapping model')
        epoch_issues = [{'filename': record['filename'], 'reason': capture_evidence(record, snapshot['config']['acquisition']['capture_year_min'])[1]}
                        for record in selected_records if capture_evidence(record, snapshot['config']['acquisition']['capture_year_min'])[1]]
        if epoch_issues and not local_research_only:
            quarantined.append({'component_id': str(component['id']), 'issues': epoch_issues,
                                'action': 'Native run retained; whole component withheld from the modern viewer, never edited into a different geometry.'})
            continue
        # Recheck the frozen input bytes even when no new feature run was needed.
        for record in selected_records:
            if sha256(record['working_path']) != record['sha256_working']: raise ValueError('Changed frozen source')
        mvs = run_path / 'mvs' / cid
        mesh = mvs / 'projected.obj'
        mesh_report = mvs / 'projected-texture-report.json'
        family_report_path = mvs / 'family-supported-report.json'
        family_report = json.loads(family_report_path.read_text()) if family_report_path.exists() else None
        if family_report and family_report.get('status') == 'supported_fragment_candidate':
            mesh = mvs / 'family-supported.obj'; mesh_report = family_report_path
            if not mesh.is_file(): raise ValueError('Supported fragment report has no mesh artifact')
        # Native volumetric envelopes stay offline, even before screening runs.
        publish_mesh = mesh.exists() and bool(family_report and family_report.get('status') == 'supported_fragment_candidate')
        mvs_report = json.loads((mvs / 'report.json').read_text()) if (mvs / 'report.json').exists() else {}
        if publish_mesh and (not mesh_report.exists() or mvs_report.get('status') != 'surface_candidate'):
            raise ValueError('Mesh exists without a completed measured MVS/texture report')
        if publish_mesh:
            from run_cpu_mvs import model_signature
            if mvs_report.get('input_model_signature') != model_signature(model):
                raise ValueError('MVS model does not match the selected SfM component')
            if not family_report and json.loads(mesh_report.read_text()).get('geometry_modified') is not False:
                raise ValueError('Photo projection must preserve measured geometry')
            if family_report and family_report.get('input_model_signature') != mvs_report.get('input_model_signature'):
                raise ValueError('Supported fragment report belongs to a different native model')
            if family_report:
                if family_report.get('source_cloud_geometry_modified') is not False or family_report.get('dense_vertices_preserved_within_text_precision') is not True:
                    raise ValueError('Supported fragments must retain measured dense vertices')
                for name, digest in family_report['outputs_sha256'].items():
                    if sha256(checked_file(mvs, name)) != digest: raise ValueError('Supported mesh bundle changed after validation')
            _, _, dependencies = obj_bundle_files(mesh)
            asset_version = hashlib.sha256(json.dumps([(p.name, sha256(p)) for p in dependencies]).encode()).hexdigest()[:12]
        else: asset_version = 'sparse'
        output = destination / ('component-' + cid + '-' + asset_version); output.mkdir(parents=True, exist_ok=True)
        undistorted = mvs / 'colmap' if (mvs / 'colmap/sparse/images.bin').exists() else run_path / 'web-undistorted' / cid
        if not (undistorted / 'sparse/images.bin').exists():
            undistorted.parent.mkdir(parents=True, exist_ok=True)
            pycolmap.undistort_images(str(undistorted), str(model_path), str(run_path / 'images'),
                                      undistort_options=pycolmap.UndistortCameraOptions(max_image_size=1600))
        calibrated = pycolmap.Reconstruction(str(undistorted / 'sparse'))
        original_views = {i.name: i for i in model.images.values() if i.has_pose}
        calibrated_views = {i.name: i for i in calibrated.images.values() if i.has_pose}
        if original_views.keys() != calibrated_views.keys(): raise ValueError('Stale or foreign undistorted cameras')
        for name, image in calibrated_views.items():
            if records[name]['split'] != 'train' or not np.allclose(image.cam_from_world().matrix(), original_views[name].cam_from_world().matrix(), atol=1e-8):
                raise ValueError('Undistorted cameras do not preserve the train component poses')
        points = sorted(model.points3D.items())
        write_json(output / 'sparse.json', {'positions': [p.xyz.tolist() for _, p in points],
                                           'colors': [p.color.tolist() for _, p in points],
                                           'claim': 'Unvalidated sparse diagnostic, not a surface.'})
        views = []
        for iid, image in sorted(calibrated.images.items()):
            if not image.has_pose: continue
            record = records[image.name]; photo = output / ('photo-' + str(iid) + '.jpg')
            make_photo(undistorted / 'images' / image.name, photo)
            matrix = np.eye(4); matrix[:3, :3] = image.cam_from_world().rotation.matrix().T @ np.diag([1, -1, -1])
            matrix[:3, 3] = image.projection_center()
            views.append({'id': int(iid), 'name': image.name, 'photo': url(photo), 'world_matrix': matrix.tolist(),
                          'K': image.camera.calibration_matrix().tolist(), 'width': image.camera.width,
                          'height': image.camera.height, 'camera_convention': 'opengl', 'photo_is_undistorted': True,
                          'split': 'train', 'exposure_group_id': record['exposure_group_id'],
                          'source_family_id': record['source_family_id'], 'source_url': record['source_url'],
                          'attribution': clean_text(record.get('artist')) + ' · ' + clean_text(record.get('license')),
                          'license': record.get('license'), 'license_url': record.get('license_url')})
        diagnostics = {**component, 'limitations': run['limitations'], 'metric_units': False,
                       'measured_surface_candidate': publish_mesh, 'supported_fragment_screen': family_report,
                       'public_release_validated': False}
        write_json(output / 'diagnostics.json', diagnostics)
        # Geometry/calibration only: no images, descriptors, weights or database.
        with zipfile.ZipFile(output / 'native-colmap.zip', 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for name in ('cameras.bin', 'images.bin', 'points3D.bin', 'frames.bin', 'rigs.bin', 'diagnostics.json'):
                if (model_path / name).is_file(): archive.write(model_path / name, name)
        metadata_core = sorted(set(component['metadata_target_camera_counts']) & CORE)
        source_label = ' / '.join(target_names[t] for t in metadata_core) if metadata_core else ('Quad6K research' if local_research_only else 'Context')
        entry = {'id': cid, 'label': f'{source_label} photo set · component {cid} · {len(views)} cameras',
                 'core_target_ids': [], 'metadata_core_candidates': metadata_core,
                 'stats': {'registered_cameras': len(views), 'sparse_points': model.num_points3D(),
                           'dense_points': mvs_report.get('outputs', {}).get('dense', {}).get('vertex', 0) if publish_mesh else 0,
                           'dense_attempt_points': mvs_report.get('outputs', {}).get('dense', {}).get('vertex', 0),
                           'mesh_faces': (family_report['faces'] if family_report else mvs_report.get('outputs', {}).get('mesh', {}).get('face', 0)) if publish_mesh else 0},
                 'cameras': views, 'mesh': None, 'sparse': {'url': url(output / 'sparse.json')},
                 'report_url': url(output / 'diagnostics.json'), 'evidence_url': url(destination / 'sources.json'),
                 'model_download_url': url(output / 'native-colmap.zip'),
                 'scale_status': 'Unverified similarity frame', 'target_identity_validated': False}
        entry['dense_attempt_status'] = mvs_report.get('status', 'not_run')
        if mvs_report.get('status') == 'insufficient_depth_support':
            entry['limitations'] = ['Three-view stereo fusion produced zero dense points. No sparse-to-mesh substitution or fabricated surface is displayed.']
        if publish_mesh:
            obj, mtl = copy_obj_bundle(mesh, output)
            entry['mesh'] = {'url': url(output / obj), 'mtl_url': url(output / mtl), 'basename': mesh.stem, 'texture_flip_y': True}
            texturing = json.loads(mesh_report.read_text()); write_json(output / mesh_report.name, texturing)
            by_basename = {Path(v['name']).name: v['id'] for v in views}
            if len(by_basename) != len(views): raise ValueError('Ambiguous camera basenames')
            materials = texturing['source_materials'] if family_report else {f'camera_{i}': name for i, name in texturing['source_cameras'].items()}
            entry['source_materials'] = {material: by_basename[Path(name).name] for material, name in materials.items()}
            entry['limitations'] = ['Surface clicks identify the texture photograph, not a certified independent per-face geometry support set.',
                                     'No independent holdout, completeness or metric validation has passed.']
            entry['default_camera_id'] = int(max(model.images.values(), key=lambda image: int(image.num_points3D)).image_id)
            support = mvs / 'dense-support-report.json'
            if support.exists():
                shutil.copy2(support, output / support.name); entry['dense_support_report_url'] = url(output / support.name)
            face_evidence = mvs / 'family-face-evidence.json'
            if family_report and face_evidence.exists():
                face_index = json.loads(face_evidence.read_text())
                hashes = face_index.get('source_hashes', {})
                if (hashes.get('obj_sha256') != sha256(mesh) or hashes.get('family_report_sha256') != sha256(mesh_report)
                        or hashes.get('snapshot_sha256') != sha256(snapshot_path) or face_index.get('snapshot_id') != snapshot['snapshot_id']
                        or str(face_index.get('component_id')) != cid or face_index.get('face_count') != family_report['faces']):
                    raise ValueError('Per-face evidence does not match the displayed mesh')
                shutil.copy2(face_evidence, output / face_evidence.name)
                entry['face_evidence_url'] = url(output / face_evidence.name)
        elif family_report:
            entry['limitations'] = ['Conservative source-family surface screen found insufficient support. The native dense attempt is preserved but no gray-envelope replacement is shown.',
                                     'Recorded source families are uncertain and can over-group genuine viewpoints; this screen does not prove the real building is unreconstructable.']
        holdout_reports = sorted((run_path / 'holdouts').glob(cid + '-*/report.json'), key=lambda p: p.stat().st_mtime)
        if holdout_reports:
            shutil.copy2(holdout_reports[-1], output / 'holdout-report.json')
            entry['holdout_report_url'] = url(output / 'holdout-report.json')
        components.append(entry)
    components.sort(key=component_display_order)
    counts = snapshot['counts']
    limitations = list(snapshot['limitations']) + [
        'D0/D1 have not passed. Components are separate, unscaled COLMAP frames; they are never laid out as a fabricated campus.',
        'Core-building identity and surface coverage are not inferred from filenames or category membership.',
        'Public HTTPS, an actual demo film, real-device performance and independent held-out validation are not complete.',
        'Source-count table is collection coverage, not recovered facade coverage. Unknown surfaces are not filled.']
    if not components: limitations.append('No reconstructed component has been supplied to this site package.')
    if local_research_only:
        limitations.insert(0, 'LOCAL RESEARCH-ONLY. Source-image redistribution rights and capture-epoch independence are unresolved. Do not publish or redistribute this preview; it is not accepted D0/D1.')
    if quarantined: limitations.append(f'{len(quarantined)} native component(s) withheld because capture-epoch evidence conflicts with the modern scope; inspect the quarantine report.')
    if current_epoch_issues: limitations.append(f'{len(current_epoch_issues)} candidate source record(s) need capture-epoch review. ' + ('They may be inspected only as unvalidated local research, not accepted modern geometry.' if local_research_only else 'Any component using them is withheld; frozen experiments are not rewritten.'))
    write_json(destination / 'epoch-quarantine.json', {'components': quarantined, 'candidate_source_issues': current_epoch_issues,
                                                     'rule': 'Current capture-evidence screen reapplied before display; old native experiments are preserved.'})
    scene = {'schema_version': 1, 'status': 'diagnostic' if components else 'not_ready',
             'distribution_scope': distribution_scope,
             'title': 'GhostMap · Modern Arts Quad', 'generated_utc': datetime.now(timezone.utc).isoformat(),
             'run_id': run_id, 'snapshot_id': snapshot['snapshot_id'], 'components': components,
             'data': {'downloaded': counts['source_records'], 'scene_candidates': counts['metadata_scene_candidates'],
                      'train_images': counts['train_files'], 'test_images': counts['test_files'],
                      'by_target': [{'id': t['id'], 'name': t['name'], 'role': 'core' if t['id'] in CORE else 'context',
                                     'downloaded': t['files'], 'train': t['split_counts'].get('train', 0),
                                     'test': t['split_counts'].get('test', 0)} for t in snapshot['by_target']]},
             'milestones': status['milestones'], 'resources': public_status['resources'], 'limitations': limitations,
             'status_url': url(assets / 'project-status.json'), 'sources_url': url(destination / 'sources.json')}
    scene['epoch_quarantine_url'] = url(destination / 'epoch-quarantine.json')
    unique_cameras = {view['name'] for component in components for view in component['cameras']}
    surfaces = sum(bool(component['mesh']) for component in components)
    queried_components = sum(bool(component.get('holdout_report_url')) for component in components)
    scene['pipeline'] = [
        {'name': '01 · Public photographs', 'status': 'partial acquisition', 'detail': f"{counts['source_records']} frozen records. Originals, SHA256, capture assertions and rights retained; collection may continue.", 'report_url': scene['sources_url']},
        {'name': '02 · Groups and split', 'status': 'provisional grouping', 'detail': f"{counts['train_files']} train / {counts['test_files']} test. Documents, interiors and stitched cameras separated; source-family independence remains uncertain.", 'report_url': scene['sources_url']},
        {'name': '03 · Cameras and structure', 'status': (run or {}).get('status', 'not computed'), 'detail': f"{len(unique_cameras)} unique recovered cameras in {len(components)} separate components. No authored campus alignment.", 'report_url': url(destination / 'run-report.json') if run else None},
        {'name': '04 · Depth and local surfaces', 'status': 'unvalidated fragments' if surfaces else 'no displayed surface', 'detail': f"{surfaces} displayed component(s) use measured dense vertices and local source-family-screened facets. Native broad envelopes remain offline."},
        {'name': '05 · Patch evidence', 'status': 'estimated visibility only', 'detail': 'Click an indexed facet to inspect its texture photo and common fitted-MVS source images. This is not independent ground truth.'},
        {'name': '06 · Held-out localization', 'status': 'consistency diagnostics' if queried_components else 'not yet measured', 'detail': f"{queried_components} component(s) have query-only reports. Test images never fit the reference geometry; estimated PnP residuals do not certify accuracy."},
        {'name': '07 · Demo acceptance', 'status': status['milestones']['D1']['status'], 'detail': 'Connected core buildings, independent geometry checks, rights, HTTPS, film and real-device performance must each pass separately.', 'report_url': scene['status_url']},
    ]
    write_json(destination / 'pipeline-report.json', {'run_id': run_id, 'snapshot_id': snapshot['snapshot_id'],
                                                     'stages': scene['pipeline'], 'milestones': status['milestones']})
    scene['pipeline_report_url'] = url(destination / 'pipeline-report.json')
    from package_artsquad_code import package_source
    scene['source_code_url'] = url(package_source(dist))
    shutil.copy2(ROOT / 'config/artsquad-project.json', assets / 'project-contract.json')
    scene['project_contract_url'] = url(assets / 'project-contract.json')
    write_json(assets / 'scene.json', scene)
    return assets / 'scene.json'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--run', type=Path)
    parser.add_argument('--dist', type=Path, default=ROOT / 'dist')
    parser.add_argument('--evidence', type=Path)
    parser.add_argument('--local-research-only', action='store_true', help='Private diagnostic assets only; requires a dedicated artifacts/local_previews subdirectory')
    args = parser.parse_args()
    print(package(args.snapshot, args.run.resolve() if args.run else None, args.dist, args.evidence, args.local_research_only), flush=True)


if __name__ == '__main__': main()
