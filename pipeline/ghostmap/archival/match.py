"""2D-3D anchor correspondences for archival photographs against the anchored model.

Archival images are queries only: SuperPoint features are extracted for them
with the reference run's settings and matched with LightGlue to every
registered modern image; each match to a modern keypoint that belongs to a
triangulated 3D point becomes an anchor correspondence. Nothing is added to
the modern model.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np


def correspondences(reference, query_paths, work, keypoints=4096, resize=1200):
    from hloc import extract_features, match_features
    import h5py
    work = Path(work); images = work / 'images'; images.mkdir(parents=True, exist_ok=True)
    names = []
    for path in query_paths:
        dest = images / Path(path).name
        if not dest.exists(): shutil.copy2(path, dest)
        names.append(dest.name)
    run = reference.run_path
    config = json.loads((run / 'report.json').read_text())['configuration']
    ref_features = run / f"feats-superpoint-n{config['keypoints']}-r{config['resize']}.h5"
    conf = {'output': 'query-superpoint', 'model': {'name': 'superpoint', 'nms_radius': 3, 'max_keypoints': config['keypoints']},
            'preprocessing': {'grayscale': True, 'resize_max': config['resize']}}
    features = extract_features.main(conf, images, work, image_list=names, as_half=False)
    db = sorted(im.name for im in reference.model.images.values())
    pairs = work / 'pairs-query-to-model.txt'
    pairs.write_text(''.join(f'{q} {d}\n' for q in names for d in db))
    matches = work / 'matches-query-to-model.h5'
    match_features.main(match_features.confs['superpoint+lightglue'], pairs, features, matches=matches, features_ref=ref_features)
    from hloc.utils.io import get_keypoints, get_matches
    by_name = {im.name: im for im in reference.model.images.values()}
    out = {}
    for q in names:
        kq = get_keypoints(features, q)
        best = {}
        for d in db:
            try: m, scores = get_matches(matches, q, d)
            except KeyError: continue
            image = by_name[d]
            for (iq, idb), sc in zip(m, scores):
                p2 = image.points2D[int(idb)]
                if not p2.has_point3D(): continue
                pid = int(p2.point3D_id)
                # One correspondence per query keypoint: keep the strongest.
                if iq not in best or sc > best[iq][2]: best[iq] = (pid, d, float(sc))
        q2 = np.array([kq[i] + 0.5 for i in best]) if best else np.zeros((0, 2))  # COLMAP pixel-centre convention
        pids = np.array([v[0] for v in best.values()], int)
        q3 = np.array([reference.model.points3D[p].xyz for p in pids]) if len(pids) else np.zeros((0, 3))
        with __import__('PIL.Image', fromlist=['Image']).open(images / q) as im: size = im.size
        out[q] = {'points2D': q2, 'points3D': q3, 'point3D_ids': pids, 'size': size,
                  'matched_model_images': sorted({v[1] for v in best.values()})}
    return out
