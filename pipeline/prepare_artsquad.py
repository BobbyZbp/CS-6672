#!/usr/bin/env python3
"""Freeze verified local Arts Quad inputs without touching a live acquisition.

All target/role labels are metadata hypotheses, not verified scene identity.
Exact original-byte duplicates share one exposure group. Perceptual candidates
are flagged, never promoted to independent captures or merged as proven copies.
"""
from __future__ import annotations

import argparse
import calendar
import hashlib
import html
import json
import re
import tempfile
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

from acquire_artsquad import assess, digest
from download_commons import metadata_value
from review_artsquad_inputs import review

ROOT = Path(__file__).resolve().parents[1]
POLICY_VERSION = 5


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()


def content_id(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def read_json_snapshot(path):
    """Read one complete manifest version; the downloader writes in place."""
    for attempt in range(5):
        try:
            payload = path.read_bytes()
            parsed = json.loads(payload)
            if not isinstance(parsed, dict):
                raise ValueError('Expected a JSON object: ' + str(path))
            return parsed, hashlib.sha256(payload).hexdigest()
        except json.JSONDecodeError:
            if attempt == 4:
                raise RuntimeError('Manifest remained incomplete during acquisition; retry preparation later.')
            time.sleep(.1)


def capture_evidence(record, minimum_year):
    """Never mistake an upload-only assertion for a photographic capture date."""
    description = ' '.join(str(record.get(key, '')) for key in ('title', 'credit'))
    # A scan/digitization timestamp cannot silently override an explicitly
    # older photo caption. Remove clearly named construction/biography dates;
    # ambiguous older years require review, not a guessed modern epoch.
    description = re.sub(r'\([^)]*\b(?:built|constructed|founded|established|born|died|renovated)\b[^)]*\)', '', description, flags=re.I)
    description = re.sub(r'\b(?:built|constructed|founded|established|born|died|renovated)\s+(?:in\s+)?(?:18|19)\d{2}\b', '', description, flags=re.I)
    old_years = sorted({int(year) for year in re.findall(r'(?<!\d)((?:18|19|20)\d{2})(?!\d)', description)
                        if int(year) < minimum_year})
    if old_years:
        return None, 'capture epoch conflict: pre-modern year in title/credit ' + ', '.join(map(str, old_years)) + '; a digitization EXIF/source timestamp cannot resolve it'
    asserted = str(record.get('capture_date_asserted', '')).strip()
    # Commons legacy fields sometimes contain ONLY the original upload date.
    cleaned = re.sub(r'(?:\d{1,2}\s+[A-Za-z]+\s+\d{4}|\d{4}-\d{2}-\d{2})\s*'
                     r'\([^)]*(?:upload|uploaded)[^)]*\)', '', asserted, flags=re.I).strip()
    exif = str(record.get('exif', {}).get('date_time_original', '')).strip()
    candidates = [('exif:DateTimeOriginal', exif), ('source:DateTimeOriginal', cleaned)]
    for origin, value in candidates:
        years = [int(y) for y in re.findall(r'(?<!\d)((?:18|19|20)\d{2})(?!\d)', value)]
        if not years:
            continue
        if min(years) < minimum_year or max(years) > datetime.now(timezone.utc).year:
            return None, 'capture date outside configured modern interval'
        # A range or multiple asserted years is not a precise capture session.
        year = min(years)
        first, last, precision = date(year, 1, 1), date(max(years), 12, 31), 'year-or-range'
        match = re.search(r'(?<!\d)(\d{4})[:-](\d{2})[:-](\d{2})(?!\d)', value)
        if match and len(set(years)) == 1:
            try:
                first = last = date(*map(int, match.groups())); precision = 'day'
            except ValueError:
                return None, 'invalid photographic capture date'
        elif len(set(years)) == 1:
            match = re.search(r'(?<!\d)(\d{4})-(\d{2})(?![-\d])', value)
            if match:
                year, month = map(int, match.groups())
                try:
                    first, last = date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])
                    precision = 'month'
                except ValueError:
                    return None, 'invalid photographic capture month'
            else:
                match = re.search(r'\b(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\b', value)
                if match:
                    for fmt in ('%d %B %Y', '%d %b %Y'):
                        try:
                            first = last = datetime.strptime(match.group(), fmt).date(); precision = 'day'; break
                        except ValueError:
                            pass
        return {'origin': origin, 'assertion': value, 'precision': precision,
                'earliest': first.isoformat(), 'latest': last.isoformat()}, None
    return None, 'capture date unknown or upload-only; upload is not capture evidence'


def normalized_author(record):
    author = html.unescape(re.sub('<[^>]+>', '', str(record.get('artist', '')))).strip().lower()
    author = re.sub(r'^the original uploader was\s+|^user:', '', author)
    author = re.sub(r'\s+(?:at (?:english wikipedia|en\.wikipedia)|from\s+).*$', '', author)
    author = re.sub(r'[^a-z0-9]+', ' ', author).strip()
    return '' if author in {'', 'unknown', 'anonymous', 'own work'} else author


class Groups:
    def __init__(self, n): self.parents = list(range(n))
    def find(self, i):
        while self.parents[i] != i:
            self.parents[i] = self.parents[self.parents[i]]; i = self.parents[i]
        return i
    def union(self, i, j):
        a, b = self.find(i), self.find(j)
        self.parents[max(a, b)] = min(a, b)


def assign_groups(images):
    families = Groups(len(images)); by_original = {}; explicit = {}; authors = defaultdict(list)
    for i, image in enumerate(images):
        sha = image.get('sha256_original', '')
        # Only successfully checked hashes establish exact exposure identity.
        image['exposure_group_id'] = ('exposure-' + sha[:24] if image['validation']['passed']
                                      else 'unverified-' + content_id([image.get('pageid'), image['filename']])[:24])
        if image['validation']['passed']:
            if sha in by_original: families.union(i, by_original[sha])
            by_original[sha] = i
        known = []
        for container in (image, image.get('discovery', {})):
            for key in ('capture_session_id', 'capture_session', 'source_family_id', 'source_family', 'source_session', 'video_id', 'video_url'):
                if container.get(key): known.append((key, str(container[key])))
        for key in known:
            if key in explicit: families.union(i, explicit[key])
            explicit[key] = i
        evidence = image.get('capture_evidence')
        author = normalized_author(image)
        # Unknown authors are deliberately over-grouped by overlapping date.
        image['source_family_basis'] = {'author_normalized': author or None,
                                        'capture_evidence': evidence, 'explicit_session_keys': known,
                                        'author_identity_verified': False}
        if evidence:
            authors[author or '__unknown-author__'].append(i)
    for members in authors.values():
        for offset, i in enumerate(members):
            a = images[i]['capture_evidence']
            for j in members[offset + 1:]:
                b = images[j]['capture_evidence']
                if max(a['earliest'], b['earliest']) <= min(a['latest'], b['latest']):
                    families.union(i, j)
    components = defaultdict(list)
    for i, image in enumerate(images): components[families.find(i)].append(image)
    for members in components.values():
        family_id = 'family-' + content_id(sorted(i['exposure_group_id'] for i in members))[:24]
        for image in members: image['source_family_id'] = family_id


def assign_split(images, seed='ghostmap-artsquad-v1', fraction=.175):
    eligible = [image for image in images if image['validation']['passed'] and image['role'] == 'scene-candidate']
    groups = defaultdict(list); strata = defaultdict(set)
    for image in eligible:
        groups[image['source_family_id']].append(image)
        for target in image.get('discovery', {}).get('targets', []): strata[target].add(image['source_family_id'])
    names = sorted(groups, key=lambda g: content_id([seed, g]))
    count = len(eligible)
    constraints = [families for families in strata.values() if len(families) >= 2]

    def score(held):
        n_test = sum(len(groups[g]) for g in held)
        proportion = n_test / max(1, count)
        # Keep both sides represented whenever source-family constraints allow.
        # A tiny one-family target stays in training, with its unavailable
        # independent holdout explicitly reported, rather than disappearing
        # from reconstruction just to improve global split percentages.
        missing_train = sum(f <= held for f in strata.values())
        missing_test = sum(not (f & held) for f in constraints)
        empty = int(bool(count) and not held) + int(bool(count) and len(held) == len(names))
        outside = max(0, .15 - proportion, proportion - .20)
        return (empty + missing_train, missing_test, round(outside, 10),
                round(abs(proportion - fraction), 10), tuple(sorted(held)))

    best = set()
    # Multiple deterministic starts reduce local minima from shared target labels.
    for start in range(min(12, max(1, len(names)))):
        held = set(names[start::max(2, round(1 / fraction))])
        for _ in range(max(1, 2 * len(names))):
            candidates = [held ^ {g} for g in names]
            candidates.extend((held - {a}) | {b} for a in sorted(held) for b in names if b not in held)
            candidate = min(candidates, key=score, default=held)
            if score(candidate) >= score(held): break
            held = candidate
        if score(held) < score(best): best = held
    for image in images:
        image['split'] = ('rejected' if not image['validation']['passed'] else
                          'excluded' if image['role'] != 'scene-candidate' else
                          'test' if image['source_family_id'] in best else 'train')
    limits = []
    actual = sum(i['split'] == 'test' for i in images) / max(1, count)
    if count and not .15 <= actual <= .20:
        limits.append(f'Source-family/target constraints prevent the requested 15–20% file holdout in this snapshot; actual {actual:.1%}. Do not interpret file fraction as independent-view fraction.')
    for target, families in sorted(strata.items()):
        if len(families) < 2:
            limits.append(f'{target}: only {len(families)} metadata source family; independent train and test coverage cannot both be established.')
        elif not (families & best) or families <= best:
            limits.append(f'{target}: globally shared source families leave no independent {"test" if not (families & best) else "train"} stratum; no per-target validation claim allowed.')
    if not eligible: limits.append('No metadata-eligible exterior/context candidates; train and test are both empty.')
    return limits


def perceptual_candidates(images, threshold=4):
    candidates = []
    valid = [i for i in images if i['validation']['passed'] and re.fullmatch('[0-9a-fA-F]{16}', str(i.get('dhash64', '')))]
    for offset, first in enumerate(valid):
        for second in valid[offset + 1:]:
            if first['exposure_group_id'] == second['exposure_group_id']: continue
            distance = (int(first['dhash64'], 16) ^ int(second['dhash64'], 16)).bit_count()
            if distance <= threshold:
                candidates.append({'filenames': [first['filename'], second['filename']], 'dhash_hamming': distance,
                                   'status': 'needs-geometric-exposure-audit',
                                   'cross_split_risk': {first['split'], second['split']} == {'train', 'test'}})
    return candidates


def checked_path(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()): raise ValueError('path escapes input directory')
    return path


def validate_image(path, expected_hash, expected_size):
    if not re.fullmatch('[0-9a-f]{64}', str(expected_hash)):
        raise ValueError('missing or invalid expected SHA256')
    if digest(path) != expected_hash: raise ValueError('SHA256 mismatch: ' + path.name)
    with Image.open(path) as photo: photo.verify()
    with Image.open(path) as photo:
        photo.load(); size = list(photo.size)
    if expected_size and size != list(expected_size): raise ValueError('recorded dimensions differ from decoded image')
    return size


def make_contacts(snapshot_dir, images, targets):
    for target in targets:
        subset = [i for i in images if target['id'] in i.get('discovery', {}).get('targets', [])]
        if not subset: continue
        width, height, columns = 320, 245, 3
        sheet = Image.new('RGB', (width * columns, height * ((len(subset) + columns - 1) // columns)), '#efede5')
        draw = ImageDraw.Draw(sheet)
        for j, image in enumerate(subset):
            x, y = j % columns * width, j // columns * height
            try:
                with Image.open(image['working_path']) as photo:
                    small = ImageOps.exif_transpose(photo).convert('RGB'); small.thumbnail((310, 180))
                    sheet.paste(small, (x + 4, y + 4))
            except (OSError, ValueError, KeyError): draw.text((x + 4, y + 50), 'FAILED FILE VALIDATION', fill='red')
            draw.text((x + 4, y + 187), str(image.get('pageid')) + ' ' + image['split'], fill='black')
            draw.text((x + 4, y + 204), image['role'][:43], fill='black')
            draw.text((x + 4, y + 221), image.get('title', '')[:43], fill='black')
        sheet.save(snapshot_dir / ('input-contact-' + target['id'] + '.jpg'), quality=88)


def prepare(manifest_path, inventory_path, workspace):
    manifest, manifest_sha = read_json_snapshot(manifest_path)
    inventory, inventory_sha = read_json_snapshot(inventory_path)
    config = manifest.get('config') or inventory.get('config')
    if not config: raise ValueError('Configuration absent from manifest and inventory')
    pages = {p['pageid']: p for p in inventory.get('pages', [])}
    images, rejected = [], []
    filenames = Counter(i.get('filename') for i in manifest.get('images', []))
    for raw in sorted(manifest.get('images', []), key=lambda i: (str(i.get('pageid')), i.get('filename', ''))):
        image = dict(raw); errors = []; page = pages.get(raw.get('pageid'))
        image['validation'] = {'passed': False, 'checks': ['original-sha256', 'working-sha256', 'decode-both', 'capture-date', 'metadata-admission']}
        if filenames[raw.get('filename')] > 1: errors.append('duplicate working filename in manifest')
        for kind, base, name, sha, size in (
            ('original', manifest_path.parent / 'originals', raw.get('original_filename', ''), raw.get('sha256_original'), raw.get('original_size')),
            ('working', workspace / 'images', raw.get('filename', ''), raw.get('sha256_working'), raw.get('working_size')),
        ):
            try:
                path = checked_path(base, name); image[kind + '_path'] = str(path)
                validate_image(path, sha, size)
            except (OSError, ValueError, TypeError, Image.DecompressionBombError) as error:
                errors.append(kind + ': ' + str(error))
        evidence, reason = capture_evidence(raw, config['capture_year_min'])
        image['capture_evidence'] = evidence
        if reason: errors.append(reason)
        if not page: errors.append('source inventory page missing; metadata admission cannot be verified')
        else:
            admitted, reason = assess(page, config)
            if not admitted: errors.append('metadata: ' + reason)
        metadata = (page or {}).get('imageinfo', [{}])[0].get('extmetadata', {})
        role, note = review(raw.get('title', ''), metadata_value(metadata, 'Categories'), raw.get('projection_hint'))
        image.update(role=role if not errors else 'validation-rejected', role_note=note,
                     target_identity_verified=False, geometric_support_verified=False,
                     independent_capture_verified=False)
        image['validation'].update(passed=not errors, errors=errors)
        if errors: rejected.append({'filename': raw.get('filename'), 'pageid': raw.get('pageid'), 'reasons': errors})
        elif role != 'scene-candidate': rejected.append({'filename': raw['filename'], 'pageid': raw['pageid'],
                                                        'reasons': ['excluded from outdoor SfM: ' + role], 'retained_for_other_roles': True})
        images.append(image)
    assign_groups(images)
    limits = assign_split(images)
    suspicious = perceptual_candidates(images)
    if suspicious: limits.append(f'{len(suspicious)} perceptual-copy candidate pairs need geometric exposure audit; source-independent captures and split independence are not certified.')
    if any(not normalized_author(i) for i in images): limits.append('Unknown authors conservatively share overlapping capture-date families; author aliases remain unverified.')
    if any(i.get('capture_evidence', {}).get('precision') != 'day' for i in images if i.get('capture_evidence')):
        limits.append('Partial capture dates conservatively merge overlapping same-author periods; they do not establish distinct sessions.')
    limits.append('Discovery target membership and metadata role screening are not verified building identity, visibility, coverage or independent baseline.')
    if manifest.get('status') == 'running': limits.append('Immutable partial acquisition snapshot: downloader may add records later; this is not the final collection.')
    frozen_config = {'acquisition': config, 'preparation_policy_version': POLICY_VERSION,
                     'split_seed': 'ghostmap-artsquad-v1', 'test_file_fraction_target': .175,
                     'perceptual_copy_hamming_threshold': 4}
    snapshot_id = content_id({'images': images, 'config': frozen_config})[:24]
    destination = workspace / 'snapshots' / snapshot_id
    if (destination / 'snapshot.json').exists(): return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.' + snapshot_id + '-', dir=destination.parent))
    counts = {'source_records': len(images), 'files_passing_validation': sum(i['validation']['passed'] for i in images),
              'metadata_scene_candidates': sum(i['role'] == 'scene-candidate' for i in images),
              'train_files': sum(i['split'] == 'train' for i in images), 'test_files': sum(i['split'] == 'test' for i in images),
              'excluded_files': sum(i['split'] == 'excluded' for i in images), 'rejected_files': sum(i['split'] == 'rejected' for i in images),
              'exact_original_exposure_groups': len({i['exposure_group_id'] for i in images if i['validation']['passed']}),
              'metadata_source_families': len({i['source_family_id'] for i in images if i['split'] in {'train', 'test'}})}
    targets = []
    for target in config.get('targets', []):
        subset = [i for i in images if target['id'] in i.get('discovery', {}).get('targets', [])]
        targets.append({**target, 'files': len(subset), 'split_counts': dict(Counter(i['split'] for i in subset)),
                        'role_counts': dict(Counter(i['role'] for i in subset)), 'target_identity_verified': False,
                        'scene_source_families': len({i['source_family_id'] for i in subset if i['split'] in {'train', 'test'}})})
    report = {'schema_version': 1, 'snapshot_id': snapshot_id, 'created_utc': datetime.now(timezone.utc).isoformat(),
              'source_manifest_sha256': manifest_sha, 'source_inventory_sha256': inventory_sha,
              'source_manifest_path': str(manifest_path.resolve()), 'source_manifest_status': manifest.get('status'),
              'images_directory': str((workspace / 'images').resolve()), 'config': frozen_config, 'images': images,
              'counts': counts, 'limitations': limits, 'by_target': targets, 'rejected_records': rejected,
              'perceptual_copy_candidates': suspicious,
              'claims': {'scene_reconstructed': False, 'capture_independence_verified': False,
                         'geometric_coverage_verified': False, 'split_independence_certified': False}}
    for split in ('train', 'test'):
        (staging / (split + '.txt')).write_text(''.join(i['filename'] + '\n' for i in images if i['split'] == split))
    audit = {key: report[key] for key in ('schema_version', 'snapshot_id', 'counts', 'by_target', 'rejected_records',
                                         'perceptual_copy_candidates', 'limitations', 'claims')}
    (staging / 'role-audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
    make_contacts(staging, images, config.get('targets', []))
    # The completion marker is last. Inputs remain in-place, guarded by hashes.
    (staging / 'snapshot.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    staging.rename(destination)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=ROOT / 'data/artsquad_modern/manifest.json')
    parser.add_argument('--inventory', type=Path, default=ROOT / 'data/artsquad_modern/inventory.json')
    parser.add_argument('--workspace', type=Path, default=ROOT / 'artifacts/artsquad_modern')
    args = parser.parse_args()
    print(prepare(args.manifest.resolve(), args.inventory.resolve(), args.workspace.resolve()))


if __name__ == '__main__': main()
