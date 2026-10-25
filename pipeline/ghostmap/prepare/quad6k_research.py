#!/usr/bin/env python3
"""Freeze bounded, fully recovered Quad6K members for PRIVATE local research.

This is a distinct admission policy, not a Commons-license/date-gate bypass.
UNKNOWN rights never become CC; snapshots and all derivatives forbid public
redistribution. Original archive cameras, published focals, GPS positions and
reference models are not fitted geometry or independent accuracy evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from PIL import Image, ImageOps, __version__ as PILLOW_VERSION

from ghostmap.acquire.artsquad import exif_record
from ghostmap.acquire.provider_probe import SOURCES
from ghostmap.acquire.commons import difference_hash
from ghostmap.prepare.snapshot import assign_groups, assign_split, capture_evidence, content_id, make_contacts, perceptual_candidates, read_json_snapshot
from ghostmap.sfm.learned import ROOT, sha256, write_json

VERSION = 1
TARGET = {'id': 'artsquad-context', 'name': 'Cornell Arts Quad research context', 'role': 'research-context'}
BBOX = {'minimum_latitude': 42.446, 'maximum_latitude': 42.4525,
        'minimum_longitude': -76.488, 'maximum_longitude': -76.481}


def _integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def validate_range(request, start, end, total, url):
    expected = {'start': start, 'end': end, 'total': total}
    if (request.get('range_delivery_verified') is not True or request.get('http_status') != 206
            or request.get('range_requested') != [start, end]
            or request.get('content_range') != expected or request.get('bytes_read') != end - start + 1
            or request.get('url') != url or request.get('headers', {}).get('content-encoding', 'identity').lower() != 'identity'
            or not re.fullmatch('[0-9a-f]{64}', str(request.get('prefix_sha256', '')))):
        raise ValueError('Missing/inconsistent exact unencoded HTTP206 range evidence')


def validate_recovered_member(row, manifest, input_root):
    """Recheck member bytes, full chunk hashes and contiguous range coverage."""
    if row.get('status') != 'complete_research_member_recovered' or row.get('original_bytes_preserved') is not True:
        raise ValueError('Member recovery is not complete')
    if row.get('public_redistribution_permitted') is not False:
        raise ValueError('Research member must explicitly forbid public redistribution')
    if row.get('rights_status') != 'unknown_local_research_inspection_only':
        raise ValueError('Unexpected rights status; this policy never grants a license')
    if not str(row.get('source', '')).startswith('quad6k') or SOURCES.get(row.get('source')) != row.get('url'):
        raise ValueError('Member is not from the declared Quad6K public archive source')
    member, complete = row.get('member', {}), row.get('complete_member', {})
    name, size, offset = member.get('name'), member.get('size'), row.get('header_offset')
    path = PurePosixPath(str(name))
    if (not isinstance(name, str) or not name or path.is_absolute() or '..' in path.parts or '\\' in name
            or '\x00' in name or re.match(r'^[A-Za-z]:', name) or member.get('type') != 'file'
            or not _integer(size) or size <= 0 or not _integer(offset) or offset < 0 or offset % 512):
        raise ValueError('Unsafe/non-file member or invalid tar boundary')
    if member.get('next_header_delta') != 512 + ((size + 511) // 512) * 512:
        raise ValueError('Member tar length/padding is inconsistent')
    if complete.get('name') != name or complete.get('size') != size:
        raise ValueError('Complete member identity/size mismatch')
    original = Path(row.get('file', ''))
    if not original.is_absolute(): original = Path(input_root) / original
    original = original.absolute()
    root = Path(input_root).resolve()
    if not original.resolve().is_relative_to(root) or any(p.is_symlink() for p in [original, *original.parents] if p.is_relative_to(root)):
        raise ValueError('Original member escapes research input root or follows a symlink')
    if original.stat().st_size != size: raise ValueError('Original member size mismatch')
    expected_sha = complete.get('sha256')
    if not re.fullmatch('[0-9a-f]{64}', str(expected_sha)) or sha256(original) != expected_sha:
        raise ValueError('Original complete-member SHA256 mismatch')
    header = row.get('header_request', {})
    total = header.get('content_range', {}).get('total')
    if not _integer(total) or total <= offset + 512 + size: raise ValueError('Unknown/inconsistent archive byte extent')
    validate_range(header, offset, offset + 511, total, row.get('url'))
    if header['prefix_sha256'] != row.get('header_sha256'): raise ValueError('Tar header digest ledger mismatch')
    start, end = offset + 512, offset + 512 + size - 1
    chunks = {}
    for request in manifest.get('requests', []):
        interval = request.get('content_range') or {}
        a, b = interval.get('start'), interval.get('end')
        if request.get('url') != row.get('url') or not _integer(a) or not _integer(b) or a < start or b > end or a > b:
            continue
        validate_range(request, a, b, total, row['url'])
        if (a, b) in chunks and chunks[a, b]['prefix_sha256'] != request['prefix_sha256']:
            raise ValueError('Conflicting duplicate body range evidence')
        chunks[a, b] = request
    cursor = start
    with original.open('rb') as source:
        for (a, b), request in sorted(chunks.items()):
            if a != cursor: raise ValueError('Missing or overlapping recovered member body ranges')
            payload = source.read(b - a + 1)
            if len(payload) != b - a + 1 or hashlib.sha256(payload).hexdigest() != request['prefix_sha256']:
                raise ValueError('Recovered byte chunk differs from HTTP range digest ledger')
            cursor = b + 1
    if cursor != end + 1: raise ValueError('Recovered body range evidence does not cover complete member')
    return original.resolve()


def capture_assertion(exif):
    original = exif.get('date_time_original', '')
    value = original or exif.get('date_time', '')
    evidence, reason = capture_evidence({'title': 'Quad6K research photographic member', 'credit': '',
                                         'exif': {'date_time_original': original}, 'capture_date_asserted': value}, 2000)
    if evidence:
        evidence['origin'] = 'exif:DateTimeOriginal' if original else 'exif:DateTime-weak-not-original'
        evidence['capture_epoch_certified'] = False
    return evidence, reason, value


def working_exif(photo, working_size):
    """Preserve physical optics/date assertions, strip GPS and unknown metadata."""
    raw = photo.getexif(); result = Image.Exif()
    for tag in (271, 272, 306):
        if tag in raw: result[tag] = raw[tag]
    try: nested = raw.get_ifd(34665)
    except (KeyError, TypeError, ValueError): nested = {}
    subset = {tag: nested[tag] for tag in (36867, 36868, 37386, 41989) if tag in nested}
    subset.update({40962: working_size[0], 40963: working_size[1]})
    result[34665] = subset
    return result


def parse_geotags(paths):
    locations = {}
    for path in paths:
        for line in Path(path).read_text(encoding='utf-8').splitlines():
            fields = line.split()
            if len(fields) != 3: raise ValueError('Malformed geotags reference row')
            name, lat, lon = fields
            try: coordinates = float(lat), float(lon)
            except ValueError as error: raise ValueError('Non-numeric geotag reference') from error
            if not all(math.isfinite(v) for v in coordinates) or not -90 <= coordinates[0] <= 90 or not -180 <= coordinates[1] <= 180:
                raise ValueError('Invalid geotag reference coordinates')
            if name in locations and locations[name] != coordinates: raise ValueError('Conflicting release geotag assertions')
            locations[name] = coordinates
    return locations


def location_screen(name, exif, release_locations, bbox=BBOX):
    candidates = []
    if name in release_locations:
        candidates.append({'origin': 'release-geotags-metadata', 'latitude': release_locations[name][0], 'longitude': release_locations[name][1]})
    if 'latitude' in exif and 'longitude' in exif:
        candidates.append({'origin': 'original-exif-gps-metadata', 'latitude': exif['latitude'], 'longitude': exif['longitude']})
    for candidate in candidates:
        lat, lon = candidate['latitude'], candidate['longitude']
        candidate['inside_declared_scope'] = bool(bbox['minimum_latitude'] <= lat <= bbox['maximum_latitude']
                                                   and bbox['minimum_longitude'] <= lon <= bbox['maximum_longitude'])
    outside = any(not c['inside_declared_scope'] for c in candidates)
    return {'status': 'outside-or-conflicting-location-review' if outside else 'within-asserted-region' if candidates else 'location-unknown',
            'assertions': candidates, 'scope_bbox': bbox, 'fitted_pose_prior': False,
            'inside_scope_proves_building_identity': False, 'consumer_gps_is_independent_truth': False}


def _role_reviews(paths):
    reviews, sources = {}, {}
    for path in sorted(map(Path, paths)):
        payload = json.loads(path.read_text()); sources[str(path.resolve())] = sha256(path)
        for row in payload.get('records', []):
            digest = row.get('sha256_original')
            if not re.fullmatch('[0-9a-f]{64}', str(digest)): raise ValueError('Visual role review lacks exact original hash')
            if digest in reviews and reviews[digest].get('role') != row.get('role'): raise ValueError('Conflicting hash-bound role reviews')
            if row.get('building_identity_validated') is not False: raise ValueError('Role notes cannot certify building identity')
            reviews[digest] = {'role': row['role'], 'reason': row.get('reason', ''), 'method': payload.get('method', 'unverified role note')}
    return reviews, sources


def prepare(manifests, workspace=ROOT / 'artifacts/quad6k_research', input_root=ROOT / 'data/quad6k_research_probe', role_reviews=(), maximum_dimension=2400):
    workspace, input_root = Path(workspace).resolve(), Path(input_root).resolve()
    if workspace.is_relative_to((ROOT / 'dist').resolve()): raise ValueError('Private research assets must never be prepared in public dist')
    if not _integer(maximum_dimension) or not 128 <= maximum_dimension <= 4096: raise ValueError('Working maximum dimension must be128–4096')
    sources, entries, references, rejected = {}, {}, [], []
    for path in sorted(map(Path, manifests)):
        manifest, digest = read_json_snapshot(path)
        sources[str(path.resolve())] = digest
        for row in manifest.get('recovered_research_members', []):
            identifier = (row.get('url'), row.get('header_offset'), row.get('complete_member', {}).get('sha256'))
            try:
                original = validate_recovered_member(row, manifest, input_root)
                provenance = {'manifest_path': str(path.resolve()), 'manifest_sha256': digest,
                              'archive_url': row['url'], 'archive_member_name': row['member']['name'],
                              'header_offset': row['header_offset'], 'header_sha256': row['header_sha256'],
                              'original_path': str(original), 'sha256_original': row['complete_member']['sha256'],
                              'complete_member_size_bytes': row['complete_member']['size'],
                              'archive_completeness_verified': False, 'member_range_coverage_verified': True}
                if row['complete_member'].get('kind') != 'image':
                    references.append(provenance | {'use': 'scope-admission-metadata-only' if original.name.endswith('__geotags.txt') else 'provenance-only-not-fitted-calibration-or-ground-truth'})
                    continue
                if identifier in entries: entries[identifier]['provenance'].append(provenance)
                else: entries[identifier] = {'row': row, 'original': original, 'provenance': [provenance]}
            except (OSError, ValueError, TypeError, KeyError) as error:
                rejected.append({'archive_member_name': row.get('member', {}).get('name'),
                                 'manifest_path': str(path.resolve()), 'reason': str(error)})
    reviews, review_sources = _role_reviews(role_reviews)
    geotags = parse_geotags(sorted({p['original_path'] for p in references if p['archive_member_name'].endswith('/geotags.txt')}))
    (workspace / 'images').mkdir(parents=True, exist_ok=True)
    images, originals_guard = [], {}
    for entry in sorted(entries.values(), key=lambda e: e['row']['member']['name']):
        row, original = entry['row'], entry['original']
        member_name = row['member']['name']; digest = row['complete_member']['sha256']; errors = []
        safe_name = re.sub('[^A-Za-z0-9_.-]+', '_', PurePosixPath(member_name).name)
        name = 'quad6k__' + digest[:20] + '__r' + str(maximum_dimension) + '__' + Path(safe_name).stem + '.jpg'
        working = workspace / 'images' / name
        record = {'filename': name, 'original_filename': original.name, 'original_path': str(original),
                  'title': 'Quad6K recovered photographic image: ' + PurePosixPath(member_name).name,
                  'source_url': row['url'], 'original_url': row['url'], 'artist': '', 'credit': 'Original Quad6K release member; license unresolved',
                  'license': 'UNKNOWN', 'license_url': '', 'rights_status': 'unknown_local_research_only',
                  'public_redistribution_permitted': False, 'research_use_permission_certified': False,
                  'scope': 'private-research-only', 'archive_member_name': member_name,
                  'sha256_original': digest, 'source_provenance': entry['provenance'],
                  'discovery': {'targets': [TARGET['id']], 'sources': ['Quad6K original release bounded member retrieval']},
                  'target_identity_verified': False, 'independent_capture_verified': False, 'geometric_support_verified': False,
                  'validation': {'passed': False, 'checks': ['complete-member-hash', 'exact-contiguous-range-ledger', 'decode-original-and-working', 'orientation-normalization', 'metadata-scope-screen'], 'errors': errors}}
        try:
            with Image.open(original) as photo: photo.verify()
            with Image.open(original) as photo:
                photo.load(); source_exif = exif_record(photo)
                if list(photo.size) != row['complete_member'].get('dimensions'): raise ValueError('Original dimensions differ from recovery ledger')
                if photo.format != row['complete_member'].get('format'): raise ValueError('Original format differs from recovery ledger')
                orientation = int(photo.getexif().get(274, 1))
                if orientation not in range(1, 9): raise ValueError('Unknown EXIF orientation')
                original_size = list(photo.size)
                oriented = ImageOps.exif_transpose(photo).convert('RGB')
                oriented_size = list(oriented.size)
                oriented.thumbnail((maximum_dimension, maximum_dimension), Image.Resampling.LANCZOS)
                derived_exif = working_exif(photo, oriented.size)
                with tempfile.NamedTemporaryFile(prefix='.quad6k-', suffix='.jpg', dir=workspace / 'images', delete=False) as temporary:
                    temporary_path = Path(temporary.name)
                oriented.save(temporary_path, quality=96, subsampling=0, exif=derived_exif)
            candidate_hash = sha256(temporary_path)
            if working.exists():
                if working.is_symlink() or sha256(working) != candidate_hash: raise ValueError('Existing derivative differs; no overwrite permitted')
                temporary_path.unlink()
            else: temporary_path.rename(working)
            with Image.open(working) as check:
                check.load()
                if check.getexif().get_ifd(34853): raise ValueError('Working derivative unexpectedly retains GPS')
                working_size = list(check.size)
            evidence, date_reason, asserted = capture_assertion(source_exif)
            location = location_screen(PurePosixPath(member_name).name, source_exif, geotags)
            role = 'out-of-scope-location-review' if location['status'] == 'outside-or-conflicting-location-review' else reviews.get(digest, {}).get('role', 'scene-candidate')
            record.update(working_path=str(working), sha256_working=candidate_hash, original_size=original_size,
                          oriented_original_size=oriented_size, working_size=working_size, dhash64=difference_hash(working),
                          exif={k: v for k, v in source_exif.items() if k not in {'latitude', 'longitude'}},
                          source_exif_provenance=source_exif, capture_evidence=evidence, capture_date_asserted=asserted,
                          capture_date_limitation=date_reason, capture_epoch_verified=False,
                          original_exif_orientation=orientation, working_orientation_normalized=True,
                          location_scope_screen=location, role=role, role_note='Generic research context, not verified exterior/core-building visibility.',
                          visual_role_note=reviews.get(digest), projection_hint='unknown')
            if not evidence:
                record['source_session'] = 'quad6k-unknown-capture-metadata-conservative-group'
            record['validation']['passed'] = True
            originals_guard[str(original)] = digest
        except (OSError, ValueError, TypeError, KeyError, Image.DecompressionBombError) as error:
            errors.append(str(error)); record.update(role='validation-rejected')
            rejected.append({'archive_member_name': member_name, 'reason': str(error)})
        images.append(record)
    assign_groups(images)
    limits = assign_split(images, seed='ghostmap-quad6k-private-v1')
    suspicious = perceptual_candidates(images)
    limits += ['UNKNOWN image rights: local research only; no public redistribution or permission certification.',
               'The complete archive was not downloaded or validated. This snapshot contains only explicitly recovered, complete members.',
               'Generic Arts Quad collection context is not building identity, independent capture, view coverage or valid camera geometry.',
               'Release geotags are used only for conservative scope screening. Neither GPS nor published focal/reference data fit or validate poses.',
               'Working photos preserve original EXIF optics/date assertions but remove GPS; no published focals.txt values are applied.',
               'Partial/weak/missing EXIF capture assertions are retained only under this private diagnostic policy, never called validated modern epochs.',
               'The group split is conservative metadata grouping, not certified independent exposures or an accuracy evaluation.']
    if suspicious: limits.append('Perceptual-copy candidates remain unresolved; no split-independence claim.')
    config = {'scope': 'private-research-only', 'public_redistribution_permitted': False,
              'research_preparation_policy_version': VERSION, 'maximum_working_dimension': maximum_dimension,
              'pillow_version': PILLOW_VERSION, 'split_seed': 'ghostmap-quad6k-private-v1',
              'test_file_fraction_target': .175, 'scope_bbox': BBOX,
              'acquisition': {'capture_year_min': 2000, 'targets': [TARGET]}}
    snapshot_id = content_id({'images': images, 'config': config, 'source_manifests_sha256': sources,
                              'role_review_sha256': review_sources, 'reference_members': references})[:24]
    destination = workspace / 'snapshots' / snapshot_id
    counts = {'source_records': len(images), 'files_passing_validation': sum(i['validation']['passed'] for i in images),
              'metadata_scene_candidates': sum(i['role'] == 'scene-candidate' for i in images),
              'train_files': sum(i['split'] == 'train' for i in images), 'test_files': sum(i['split'] == 'test' for i in images),
              'excluded_files': sum(i['split'] == 'excluded' for i in images), 'rejected_files': sum(i['split'] == 'rejected' for i in images),
              'rejected_member_ledger_records': len(rejected),
              'exact_original_exposure_groups': len({i['exposure_group_id'] for i in images if i['validation']['passed']}),
              'metadata_source_families': len({i['source_family_id'] for i in images if i['split'] in {'train', 'test'}})}
    report = {'schema_version': 1, 'snapshot_id': snapshot_id, 'created_utc': datetime.now(timezone.utc).isoformat(),
              'scope': 'private-research-only', 'public_redistribution_permitted': False,
              'source_manifests_sha256': sources, 'role_review_sha256': review_sources,
              'source_manifest_status': 'bounded-partial-research-recovery', 'images_directory': str(workspace / 'images'),
              'config': config, 'images': images, 'counts': counts, 'limitations': limits,
              'by_target': [TARGET | {'files': len(images), 'split_counts': dict(Counter(i['split'] for i in images)),
                                      'target_identity_verified': False, 'scene_source_families': counts['metadata_source_families']}],
              'reference_members_provenance': references, 'rejected_records': rejected, 'perceptual_copy_candidates': suspicious,
              'claims': {'scene_reconstructed': False, 'capture_independence_verified': False,
                         'geometric_coverage_verified': False, 'split_independence_certified': False,
                         'modern_capture_epoch_validated': False, 'public_rights_review_passed': False}}
    # Guard originals and every consumed ledger/review before committing an immutable snapshot.
    references_guard = {p['original_path']: p['sha256_original'] for p in references}
    for path, digest in (sources | review_sources | originals_guard | references_guard).items():
        if sha256(path) != digest: raise RuntimeError('Research source changed during preparation: ' + path)
    if (destination / 'snapshot.json').exists(): return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.' + snapshot_id + '-', dir=destination.parent))
    for split in ('train', 'test'):
        (staging / (split + '.txt')).write_text(''.join(i['filename'] + '\n' for i in images if i['split'] == split))
    make_contacts(staging, images, [TARGET])
    write_json(staging / 'role-audit.json', {k: report[k] for k in ('schema_version', 'snapshot_id', 'scope', 'counts', 'rejected_records', 'limitations', 'claims')})
    write_json(staging / 'snapshot.json', report)
    staging.rename(destination)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, action='append', required=True)
    parser.add_argument('--role-review', type=Path, action='append', default=[])
    parser.add_argument('--input-root', type=Path, default=ROOT / 'data/quad6k_research_probe')
    parser.add_argument('--workspace', type=Path, default=ROOT / 'artifacts/quad6k_research')
    parser.add_argument('--maximum-dimension', type=int, default=2400)
    args = parser.parse_args()
    print(prepare(args.manifest, args.workspace, args.input_root, args.role_review, args.maximum_dimension), flush=True)


if __name__ == '__main__': main()
