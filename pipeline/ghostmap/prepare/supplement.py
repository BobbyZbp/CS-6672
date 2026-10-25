#!/usr/bin/env python3
"""Extend a frozen snapshot with a training-only geometry supplement.

The base snapshot's records, splits and held-out photographs are copied
unchanged. Each supplement record (from acquire/openverse.py) is re-hashed,
decoded, screened by the same metadata role review, given its own exposure
group and a per-photographer source family, and placed in the training split
only. Its capture date is unknown; that is recorded in the record and in the
snapshot's limitations. The result is a new content-addressed snapshot.
"""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from ghostmap.acquire.artsquad import digest
from ghostmap.acquire.review import review
from ghostmap.paths import ROOT
from ghostmap.prepare.snapshot import content_id

SUPPLEMENT = ROOT / 'data/openverse/manifest.json'
WORKING = ROOT / 'artifacts/artsquad_modern/images'


def build(base_snapshot, supplement=SUPPLEMENT, workspace=ROOT / 'artifacts/artsquad_modern'):
    base = json.loads(Path(base_snapshot).read_text())
    manifest = json.loads(Path(supplement).read_text())
    originals = Path(supplement).parent / 'originals'
    added, rejected = [], []
    for raw in manifest['images']:
        record = dict(raw); errors = []
        source = originals / raw['original_filename']
        working = WORKING / raw['filename']
        try:
            if digest(source) != raw['sha256_original']: errors.append('original sha256 mismatch')
            if not working.exists(): shutil.copy2(source, working)  # 1024 px copies are already working size
            with Image.open(working) as im: im.load(); size = list(im.size)
        except OSError as error:
            errors.append('decode: ' + str(error)); size = None
        role, note = review(raw['title'], '', 'unknown')
        record.update(original_path=str(source), working_path=str(working), sha256_working=digest(working) if working.exists() else None,
                      working_size=size, oriented_original_size=size, projection_hint='unknown',
                      scope_review_hint='geometry supplement', role=role if not errors else 'validation-rejected', role_note=note,
                      capture_evidence={'origin': 'none', 'assertion': 'provider supplies no capture date', 'precision': 'unknown',
                                        'earliest': None, 'latest': None},
                      validation={'passed': not errors, 'checks': ['original-sha256', 'decode', 'metadata-admission', 'historic-marker-screen'],
                                  'errors': errors},
                      target_identity_verified=False, geometric_support_verified=False, independent_capture_verified=False,
                      exposure_group_id='exposure-' + raw['sha256_original'][:24],
                      source_family_basis='openverse photographer: ' + (raw['artist'] or 'unknown'),
                      source_family_id='family-' + content_id(['openverse', raw['artist'] or raw['pageid']])[:24],
                      split='train' if not errors and role == 'scene-candidate' else 'excluded')
        (added if record['split'] == 'train' else rejected).append(record)
    images = base['images'] + added + rejected
    config = dict(base['config']); config['supplement'] = {'manifest': str(Path(supplement).resolve()), 'manifest_sha256': digest(Path(supplement)),
                                                          'base_snapshot_id': base['snapshot_id'], 'policy': 'training-only geometry supplement'}
    snapshot_id = content_id({'images': images, 'config': config})[:24]
    out = Path(workspace) / 'snapshots' / snapshot_id; out.mkdir(parents=True, exist_ok=True)
    counts = dict(base['counts']); counts.update(supplement_records=len(manifest['images']), supplement_train=len(added),
                                                 train_files=base['counts']['train_files'] + len(added))
    snapshot = {**{k: base[k] for k in ('schema_version', 'source_manifest_sha256', 'source_inventory_sha256', 'source_manifest_path',
                                         'source_manifest_status', 'images_directory', 'by_target', 'perceptual_copy_candidates')},
                'snapshot_id': snapshot_id, 'created_utc': datetime.now(timezone.utc).isoformat(), 'config': config,
                'base_snapshot_id': base['snapshot_id'], 'images': images, 'counts': counts,
                'rejected_records': base['rejected_records'] + [{'filename': r['filename'], 'pageid': r['pageid'], 'reasons': r['validation']['errors'] or ['role: ' + r['role']]} for r in rejected],
                'limitations': base['limitations'] + [f'{len(added)} training-only supplement photographs from Openverse (Flickr CC) have no capture date; they are screened for historic markers only.'],
                'claims': base['claims']}
    (out / 'snapshot.json').write_text(json.dumps(snapshot, indent=1, ensure_ascii=False) + '\n')
    (out / 'train.txt').write_text(''.join(i['filename'] + '\n' for i in images if i.get('split') == 'train'))
    (out / 'test.txt').write_text(''.join(i['filename'] + '\n' for i in images if i.get('split') == 'test'))
    return out / 'snapshot.json', len(added), len(rejected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True, type=Path)
    parser.add_argument('--supplement', type=Path, default=SUPPLEMENT)
    args = parser.parse_args()
    path, added, rejected = build(args.base, args.supplement)
    print(path, added, 'added to training,', rejected, 'excluded')


if __name__ == '__main__': main()
