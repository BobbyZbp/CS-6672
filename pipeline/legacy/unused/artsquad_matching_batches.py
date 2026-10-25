"""Validate and extend a same-run HLOC cache without trusting group existence.

Scheduling is deliberately outside scientific configuration/run identity. A
partial *set* of complete matches is resumable; an incomplete/invalid group is
never silently skipped, deleted, overwritten, or admitted to native mapping.
"""
import hashlib
import json
from pathlib import Path


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def file_sha(path):
    from run_artsquad_sfm import sha256
    return sha256(path)


def preserve_report(path):
    path = Path(path)
    if not path.exists(): return None
    payload = path.read_bytes(); digest = hashlib.sha256(payload).hexdigest()
    history = path.parent / 'report-history' / (digest + '.json')
    history.parent.mkdir(exist_ok=True)
    if history.exists() and history.read_bytes() != payload: raise ValueError('Report history hash conflict')
    if not history.exists(): history.write_bytes(payload)
    return {'sha256': digest, 'path': str(history), 'status': json.loads(payload).get('status'), 'stage': json.loads(payload).get('stage')}


def feature_cache(files, names, require_complete=True):
    import h5py
    import numpy as np
    names = set(names); counts, hashes, complete = {}, {}, True
    for kind, path in files.items():
        path = Path(path)
        if not path.exists():
            complete = False
            if require_complete: raise ValueError('Missing feature cache: ' + str(path))
            continue
        with h5py.File(path, 'r') as handle:
            present = set(handle)
            if not present <= names: raise ValueError('Feature cache contains foreign/held-out images')
            if present != names: complete = False
            if require_complete and present != names: raise ValueError('Feature cache omits current training images')
            for name in present:
                group = handle[name]
                required = ('global_descriptor', 'image_size') if kind == 'global' else ('keypoints', 'descriptors', 'scores', 'image_size')
                if any(key not in group for key in required): raise ValueError('Incomplete feature group; preserved: ' + name)
                values = {key: group[key][()] for key in required}
                if any(not np.isfinite(value).all() for value in values.values()): raise ValueError('Nonfinite cached feature: ' + name)
                size = values['image_size']
                if size.shape != (2,) or not (size > 0).all(): raise ValueError('Invalid feature image size')
                if kind == 'global':
                    descriptor = values['global_descriptor']
                    if descriptor.ndim != 1 or descriptor.size == 0: raise ValueError('Invalid cached global descriptor')
                else:
                    points, desc, scores = (values[key] for key in ('keypoints', 'descriptors', 'scores'))
                    if points.ndim != 2 or points.shape[1] != 2 or desc.ndim != 2 or desc.shape[1] != len(points) or scores.shape != (len(points),):
                        raise ValueError('Misaligned cached local features: ' + name)
                    counts[name] = len(points)
        hashes[kind] = file_sha(path)
    return {'complete': complete, 'images': len(names), 'keypoint_counts': counts, 'feature_sha256': hashes}


def expected_pairs(path, names):
    names = set(names); pairs = []
    for line in Path(path).read_text().splitlines():
        if not line.strip(): continue
        pair = tuple(line.split())
        if len(pair) != 2 or pair[0] == pair[1] or not set(pair) <= names:
            raise ValueError('Retrieval pairs contain malformed/foreign/held-out image names')
        pair = tuple(sorted(pair))
        if pair in pairs: raise ValueError('Retrieval pair list contains duplicates')
        pairs.append(pair)
    return sorted(pairs)


def match_cache(path, names, counts, expected):
    import h5py
    import numpy as np
    from reuse_artsquad_cache import _group_digest, _pair_names
    names = set(names); groups, available = {}, set()
    path = Path(path)
    if path.exists():
        with h5py.File(path, 'r') as handle:
            leaves = []
            def inspect(name, obj):
                if not isinstance(obj, h5py.Group): return
                pair = _pair_names(name, names)
                if pair is not None:
                    leaves.append((name, pair)); return
                # A normal HLOC first-image directory is only a container. All
                # actual leaves, including empty/incomplete ones, are checked.
                if '/' not in name and name in names and len(obj) and all(isinstance(child, h5py.Group) for child in obj.values()): return
                raise ValueError('Unknown or incomplete match group preserved: ' + name)
            handle.visititems(inspect)
            for name, pair in leaves:
                group = handle[name]
                if set(group) != {'matches0', 'matching_scores0'}: raise ValueError('Incomplete match datasets preserved: ' + name)
                matches, scores = group['matches0'][()], group['matching_scores0'][()]
                if matches.shape != (counts[pair[0]],) or scores.shape != matches.shape or not np.issubdtype(matches.dtype, np.integer):
                    raise ValueError('Invalid match array shapes/dtypes: ' + name)
                if not np.isfinite(scores).all() or (scores < 0).any() or (scores > 1).any() or (matches < -1).any() or (matches >= counts[pair[1]]).any():
                    raise ValueError('Invalid cached match scores/indices: ' + name)
                groups[name] = _group_digest(group)
                available.add(tuple(sorted(pair)))
    outstanding = [pair for pair in expected if pair not in available]
    return {'groups_sha256': groups, 'available_pairs': available, 'outstanding': outstanding,
            'complete_expected_pairs': len(expected) - len(outstanding), 'expected_pairs': len(expected),
            'complete_cache_groups': len(groups), 'extra_current_train_pairs': len(available - set(expected))}


def match_batch(work, config, names, pairs_path, feature_files, matches, batch_size, match_function):
    from run_artsquad_sfm import write_json
    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or not 0 <= batch_size <= 100:
        raise ValueError('Matching batch size must be 0 (legacy unbounded) or 1–100')
    work = Path(work)
    feature_summary = feature_cache(feature_files, names)
    expected = expected_pairs(pairs_path, names)
    before = match_cache(matches, names, feature_summary['keypoint_counts'], expected)
    identity = {'configuration': config, 'training_names': sorted(names), 'feature_sha256': feature_summary['feature_sha256'],
                'pairs_sha256': file_sha(pairs_path)}
    progress_path = work / 'matching-progress.json'
    previous = json.loads(progress_path.read_text()) if progress_path.exists() else None
    if previous:
        if previous['identity'] != identity: raise ValueError('Same-run feature/pair identity changed; cache preserved')
        if any(before['groups_sha256'].get(name) != digest for name, digest in previous['groups_sha256'].items()):
            raise ValueError('A previously validated match group changed or disappeared')
    selected = before['outstanding'][:batch_size] if batch_size else before['outstanding']
    batch_number = (previous or {}).get('batch_number', 0) + 1
    batch_directory = work / 'matching-batches'; batch_directory.mkdir(exist_ok=True)
    batch_payload = ''.join(a + ' ' + b + '\n' for a, b in selected)
    batch_path = batch_directory / f'{batch_number:04d}-{hashlib.sha256(batch_payload.encode()).hexdigest()[:16]}.txt'
    if batch_path.exists() and batch_path.read_text() != batch_payload: raise ValueError('Existing batch list differs')
    if not batch_path.exists(): batch_path.write_text(batch_payload)
    progress = {'schema_version': 1, 'identity': identity, 'batch_number': batch_number, 'batch_size': batch_size,
                'batch_pair_count': len(selected), 'batch_pairs_path': str(batch_path.relative_to(work)),
                'status': 'matching_batch_running' if selected else 'matching_complete',
                'groups_sha256': before['groups_sha256'], 'complete_expected_pairs': before['complete_expected_pairs'],
                'expected_pairs': len(expected), 'remaining_pairs': len(before['outstanding']),
                'interpretation': 'Execution scheduling only. A partial set of validated complete groups is resumable; malformed groups are preserved and rejected. No scientific milestone acceptance.'}
    if progress_path.exists():
        history = work / 'matching-history'; history.mkdir(exist_ok=True)
        old = progress_path.read_bytes(); archived = history / (hashlib.sha256(old).hexdigest() + '.json')
        if not archived.exists(): archived.write_bytes(old)
    write_json(progress_path, progress)
    if selected: match_function(batch_path)
    after_features = feature_cache(feature_files, names)
    if after_features['feature_sha256'] != feature_summary['feature_sha256']: raise ValueError('Feature cache changed during matching')
    after = match_cache(matches, names, after_features['keypoint_counts'], expected)
    if any(after['groups_sha256'].get(name) != digest for name, digest in before['groups_sha256'].items()):
        raise ValueError('Matching modified or removed a previously complete group')
    if any(pair not in after['available_pairs'] for pair in selected): raise ValueError('Matcher did not completely finish its declared batch')
    if not (after['available_pairs'] - before['available_pairs']) <= set(selected): raise ValueError('Matcher wrote undeclared pairs outside its bounded batch')
    progress.update(status='matching_pending' if after['outstanding'] else 'matching_complete',
                    groups_sha256=after['groups_sha256'], complete_expected_pairs=after['complete_expected_pairs'],
                    complete_cache_groups=after['complete_cache_groups'], extra_current_train_pairs=after['extra_current_train_pairs'],
                    remaining_pairs=len(after['outstanding']), newly_matched_pairs=after['complete_expected_pairs']-before['complete_expected_pairs'],
                    feature_files_unchanged=True)
    write_json(progress_path, progress)
    return progress
