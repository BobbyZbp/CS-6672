#!/usr/bin/env python3
"""Package real v2 surface experiments and their original camera views."""
import json
import shutil
import zipfile
from pathlib import Path

import numpy as np
import pycolmap

ROOT = Path(__file__).resolve().parents[3]
ASSETS = ROOT / 'dist/assets/repair'
EXPERIMENTS = [
    ('modern-full', 'Modern Uris / McGraw · higher-resolution stereo', 'cpu_mvs_modern_full_v2', 'Measured modern surface at higher stereo resolution; unseen regions remain incomplete.'),
    ('historical-masked08', 'Historical · building mask · focal prior 0.8', 'cpu_mvs_masked08_v3', 'Automatic building-only matching and dense stereo. Historical focal calibration and completeness remain unvalidated.'),
    ('historical-masked12', 'Historical · building mask · focal prior 1.2', 'cpu_mvs_masked12_v3', 'Alternate focal-prior hypothesis after automatic vegetation/sky filtering; compare the remaining geometry sensitivity.'),
    ('modern', 'Modern Uris / McGraw', 'cpu_mvs_modern_v2', 'Control surface; completeness not established.'),
    ('historical-archive', 'Historical · Commons + Cornell archive', 'cpu_mvs_archive_target_v2', 'Research-only archival inputs; partial historical surface under a focal prior, not a validated complete building.'),
    ('historical08', 'Historical · fixed f / width = 0.8', 'cpu_mvs_target_fixed08_v2', 'Focal-prior hypothesis; historical geometry remains unvalidated.'),
    ('historical12', 'Historical · fixed f / width = 1.2', 'cpu_mvs_target_fixed_v2', 'Focal-prior hypothesis; historical geometry remains unvalidated.'),
]


def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    models = []
    for key, label, directory, verdict in EXPERIMENTS:
        source = ROOT / 'artifacts' / directory
        if not (source / 'textured.obj').exists():
            continue
        target = ASSETS / key
        target.mkdir(parents=True, exist_ok=True)
        report = json.loads((source / 'report.json').read_text())
        basename='projected' if (source/'projected.obj').exists() else 'textured'
        for pattern in ['textured*', 'supported*', 'projected*', 'exposure-supported*']:
            for p in source.glob(pattern):
                if p.suffix.lower() in {'.obj', '.mtl', '.png', '.jpg', '.jpeg', '.json'}:
                    shutil.copy2(p, target / p.name)
        for name in ['report.json', 'surface-inspection.json', 'surface-projections.jpg', 'artifact-validation.json']:
            if (source / name).exists():
                shutil.copy2(source / name, target / name)
        if basename=='supported' and (source/'supported-projections.jpg').exists():
            shutil.copy2(source/'supported-projections.jpg',target/'surface-projections.jpg')
        model = pycolmap.Reconstruction(str(source / 'colmap/sparse'))
        cameras = []
        # Record full camera intrinsics/extrinsics so the browser can snap to a
        # photograph's actual recovered viewpoint instead of a hand-set pose.
        for image in sorted(model.images.values(), key=lambda im: -int(im.num_points3D)):
            camera = image.camera
            R = image.cam_from_world().rotation.matrix()
            world = np.eye(4)
            world[:3, :3] = R.T @ np.diag([1, -1, -1])
            world[:3, 3] = image.projection_center()
            thumb_dir = target / 'photos'
            thumb_dir.mkdir(exist_ok=True)
            shutil.copy2(source / 'colmap/images' / image.name, thumb_dir / image.name)
            cameras.append({'name': image.name, 'world_matrix': world.tolist(),
                            'K': camera.calibration_matrix().tolist(),
                            'width': camera.width, 'height': camera.height,
                            'observations': int(image.num_points3D),
                            'photo': f'assets/repair/{key}/photos/{image.name}'})
        archive_path = target / 'surface-download.zip'
        with zipfile.ZipFile(archive_path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            default='exposure-supported' if (source/'exposure-supported.obj').exists() else basename
            archive.writestr('README.txt',f'Open {default}.obj with its matching .mtl and source images in this folder.\nThe projected mesh preserves OpenMVS geometry and uses calibrated photographs for texture. Gray faces have no qualifying source view.\nExposure-supported facets retain exact stereo vertices and screen repeated-exposure candidates. Group screening does not certify independent captures.\nHistorical calibration and metric accuracy remain unvalidated.\nSource images retain their original rights; Cornell research access does not establish a redistribution license. See included provenance manifests.\n')
            for pattern in ['textured*', 'supported*', 'projected*', 'exposure-supported*']:
                for p in target.glob(pattern):
                    archive.write(p, p.name)
            archive.write(source / 'report.json', 'report.json')
            for path,name in [(ROOT/'data/raw/manifest.json','commons-provenance.json'),(ROOT/'data/cornell_archive/manifest.json','cornell-archive-provenance.json'),(ROOT/'artifacts/exposure-audit.json','exposure-audit.json')]:
                if path.exists():archive.write(path,name)
            for name in ['artifact-validation.json','surface-inspection.json']:
                if (source/name).exists():archive.write(source/name,name)
        models.append({'id': key, 'label': label, 'verdict': verdict,
                       'path': f'assets/repair/{key}/', 'report': report, 'cameras': cameras,
                       'mesh_basename': basename, 'has_supported_mesh':(source/'supported.obj').exists(),
                       'has_exposure_mesh':(source/'exposure-supported.obj').exists()})
    sensitivity = []
    for p in sorted((ROOT / 'artifacts/target_sfm_v2').glob('report*.json')):
        report = json.loads(p.read_text())
        sensitivity.append({'name': p.stem, 'registered': report['registered_images'],
                            'points': report['points3D'], 'focal_prior': report.get('focal_factor_prior'),
                            'focal_refinement': report.get('focal_refinement', True)})
    (ASSETS / 'manifest.json').write_text(json.dumps({'models': models, 'focal_sensitivity': sensitivity}, indent=2) + '\n')
    focal_geometry=ROOT/'artifacts/target_sfm_v2/focal-geometry-sensitivity.json'
    if focal_geometry.exists():
        shutil.copy2(focal_geometry,ASSETS/'focal-geometry-sensitivity.json')
    exposure=ROOT/'artifacts/exposure-audit.json'
    if exposure.exists():shutil.copy2(exposure,ASSETS/'exposure-audit.json')
    shutil.copy2(ROOT / 'docs/legacy/repair/noah-method-audit.md', ASSETS / 'noah-method-audit.md')
    semantic=ROOT/'artifacts/masked_target_v3'
    if (semantic/'report.json').exists():
        target=ASSETS/'semantic';target.mkdir(exist_ok=True)
        for name in ['report.json','mask-audit.jpg','focal-geometry-sensitivity.json']:
            if (semantic/name).exists():shutil.copy2(semantic/name,target/name)
    print('Packaged', len(models), 'computed surface experiments')


if __name__ == '__main__':
    main()
