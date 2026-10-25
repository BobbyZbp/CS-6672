#!/usr/bin/env python3
"""Historical-target-first reconstruction; preserve the prior joint experiment."""
from __future__ import annotations

import argparse
import json
from itertools import combinations
from pathlib import Path

import pycolmap
import torch
from hloc import extract_features, match_features, reconstruction


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', type=Path, default=Path('artifacts/target_sfm_v2'))
    parser.add_argument('--resize', type=int, default=1600)
    parser.add_argument('--images', type=Path, default=ROOT / 'artifacts/work/joint/images')
    parser.add_argument('--fixed-focal', action='store_true')
    parser.add_argument('--focal-factor', type=float, default=1.2)
    args = parser.parse_args()
    args.workspace.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(4)
    images = args.images.resolve()
    names = sorted(p.name for p in images.iterdir() if p.name.startswith('historical__') and 'boardman' in p.name.lower())
    conf = {
        'output': f'feats-superpoint-n8192-r{args.resize}',
        'model': {'name': 'superpoint', 'nms_radius': 3, 'max_keypoints': 8192},
        'preprocessing': {'grayscale': True, 'resize_max': args.resize},
    }
    pairs = args.workspace / 'pairs-target-exhaustive.txt'
    pairs.write_text('\n'.join(f'{a} {b}' for a, b in combinations(names, 2)) + '\n')
    features = extract_features.main(conf, images, args.workspace, image_list=names, as_half=False)
    matches = args.workspace / 'matches-target-lightglue.h5'
    match_features.main(match_features.confs['superpoint+lightglue'], pairs, features, matches=matches)
    suffix = f'_fixed_focal_{args.focal_factor:g}' if args.fixed_focal else ''
    sfm = args.workspace / ('sfm' + suffix)
    model = reconstruction.main(
        sfm, images, pairs, features, matches,
        image_list=names,
        image_options={'camera_model': 'SIMPLE_PINHOLE', 'default_focal_length_factor': args.focal_factor},
        mapper_options={'num_threads': 4, 'ba_refine_extra_params': False,
                        'ba_refine_focal_length': not args.fixed_focal,
                        'max_focal_length_ratio': 4.0, 'min_focal_length_ratio': .25},
    )
    report = {
        'method': 'historical target only; exhaustive SuperPoint 8192/1600 + LightGlue + COLMAP',
        'input_images': names,
        'pairs': len(list(combinations(names, 2))),
        'registered_images': model.num_reg_images() if model else 0,
        'points3D': model.num_points3D() if model else 0,
        'summary': model.summary() if model else None,
        'registered_names': sorted(i.name for i in model.images.values()) if model else [],
        'focal_factor_prior': args.focal_factor,
        'focal_refinement': not args.fixed_focal,
        'camera_focal_ratios': {i.name: float(i.camera.focal_length / max(i.camera.width, i.camera.height)) for i in model.images.values()} if model else {},
        'claim': 'Candidate historical component; target coverage and surface still require verification.',
    }
    (args.workspace / ('report' + suffix + '.json')).write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
