#!/usr/bin/env python3
"""Project a measured mesh into calibrated input views; write audit figures."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
import numpy as np
from PIL import Image
import pycolmap
import trimesh
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--basename', default='textured')
    args = parser.parse_args()
    work = args.workspace
    mesh = trimesh.load(work / (args.basename+'.obj'), force='mesh', process=False)
    model = pycolmap.Reconstruction(str(work / 'colmap/sparse'))
    images = sorted(model.images.values(), key=lambda im: (-int(im.num_points3D), im.name))
    # Include both target-labelled and anchor views for identity inspection.
    candidates = [im for im in images if 'boardman' in im.name.lower()]
    audit_file=Path(__file__).resolve().parents[3]/'artifacts/exposure-audit.json'
    groups={}
    if audit_file.exists():
        audit=json.loads(audit_file.read_text())
        groups={n:i for i,g in enumerate(audit['candidate_groups']) for n in g}
    chosen=[];seen=set()
    for im in candidates:
        group=groups.get(im.name,im.name)
        if group in seen:continue
        chosen.append(im);seen.add(group)
        if len(chosen)==3:break
    if not chosen:
        chosen=images[:3]
    fig, axes = plt.subplots(len(chosen), 2, figsize=(12, 3.7 * len(chosen)), squeeze=False)
    rows = []
    for row, im in enumerate(chosen):
        source = Image.open(work / 'colmap/images' / im.name).convert('RGB')
        R = im.cam_from_world().rotation.matrix()
        t = im.cam_from_world().translation
        points = mesh.vertices @ R.T + t
        projected = points @ im.camera.calibration_matrix().T
        uv = projected[:, :2] / projected[:, 2:]
        faces = mesh.faces[np.all(points[mesh.faces, 2] > 0, axis=1)]
        polygons = uv[faces]
        for col in range(2):
            ax = axes[row, col]
            ax.imshow(source)
            if col:
                ax.add_collection(PolyCollection(polygons, facecolor=(0.0, .7, .9, .22),
                                                  edgecolor=(0, .45, .75, .4), linewidth=.2))
            ax.set_xlim(0, source.width); ax.set_ylim(source.height, 0)
            ax.axis('off')
            ax.set_title(('INPUT: ' if col == 0 else 'PROJECTED COMPUTED SURFACE: ') + im.name.split('__')[-1][:52], fontsize=8)
        rows.append({'image': im.name, 'visible_candidate_faces': len(faces),
                     'sparse_observations': int(im.num_points3D)})
    fig.tight_layout()
    prefix=args.basename if args.basename in {'supported','exposure-supported'} else 'surface'
    fig.savefig(work / (prefix+'-projections.jpg'), dpi=135)
    plt.close(fig)
    # Use an explicit sparse graph: trimesh's repair-based split can expand
    # pathological input facets and is unnecessary for this audit statistic.
    # OBJ texture seams duplicate positions. Merge position indices only for
    # connectivity measurement; leave the actual textured mesh unchanged.
    welded_vertices, inverse = np.unique(np.round(mesh.vertices, 7), axis=0, return_inverse=True)
    welded_faces = inverse[mesh.faces]
    edges = np.vstack((welded_faces[:, [0, 1]], welded_faces[:, [1, 2]], welded_faces[:, [2, 0]]))
    adjacency = coo_matrix((np.ones(len(edges)), (edges[:, 0], edges[:, 1])), shape=(len(welded_vertices), len(welded_vertices)))
    n_components, labels = connected_components(adjacency, directed=False)
    face_components = labels[welded_faces[:, 0]]
    component_sizes = np.bincount(face_components, minlength=n_components)
    summary = {'vertices': len(mesh.vertices), 'triangles': len(mesh.faces),
               'connected_components': int(n_components),
               'largest_component_triangles': int(component_sizes.max()) if len(component_sizes) else 0,
               'watertight': bool(mesh.is_watertight),
               'views': rows,
               'validation_scope': 'Training-camera projection inspection; not a held-out reconstruction accuracy score.'}
    (work / (prefix+'-inspection.json')).write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
