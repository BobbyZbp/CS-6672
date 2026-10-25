#!/usr/bin/env python3
"""Triangulate only local, jointly visible fused stereo patches.

Unlike a volumetric envelope, this mesh cannot span a large unobserved gap:
each edge must be <=12 pixels in its reference view, <=3% of local depth in
3D, and all corners must share at least two stereo support views.
"""
import argparse
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
from plyfile import PlyData
import pycolmap
from scipy.spatial import Delaunay

from ghostmap.dense.openmvs_cpu import command


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--workspace', type=Path, required=True)
    p.add_argument('--exposure-audit', type=Path)
    p.add_argument('--output-basename', default='supported')
    args = p.parse_args()
    work = args.workspace.resolve()
    export = work / 'export-cameras'
    subprocess.run(command('InterfaceCOLMAP') + ['-i', str(work/'dense.mvs'), '-o', str(export), '--binary', '0'],
                   check=True, stdout=subprocess.DEVNULL)
    cameras = pycolmap.Reconstruction(str(export / 'sparse'))
    data = PlyData.read(work / 'dense.ply')['vertex'].data
    xyz = np.column_stack([data[k] for k in ['x','y','z']]).astype(float)
    normals = np.column_stack([data[k] for k in ['nx','ny','nz']]).astype(float)
    views = [set(map(int,v)) for v in data['view_indices']]
    group_by_name={}
    if args.exposure_audit:
        audit=json.loads(args.exposure_audit.read_text())
        group_by_name={name:i for i,g in enumerate(audit['candidate_groups']) for name in g}
    image_names=[Path(im.name).name for _,im in sorted(cameras.images.items())]
    group_by_index=[group_by_name.get(n,n) for n in image_names]
    support=[{group_by_index[i] for i in v} for v in views]
    primary = np.array([int(v[int(np.argmax(w))]) for v,w in zip(data['view_indices'],data['view_weights'])])
    faces = {}
    # OpenMVS view_indices index the compact image vector; exported COLMAP
    # IMAGE_ID keeps the original ID and can contain gaps.
    for view, (image_id, image) in enumerate(sorted(cameras.images.items())):
        indices = np.array([i for i,v in enumerate(views) if view in v and len(support[i])>=3])
        if len(indices)<5:continue
        R=image.cam_from_world().rotation.matrix();t=image.cam_from_world().translation
        local=xyz[indices] @ R.T+t
        projected=local @ image.camera.calibration_matrix().T
        uv=projected[:,:2]/projected[:,2:]
        candidates=Delaunay(uv).simplices
        tri=indices[candidates]
        screen=uv[candidates]
        max_pixel_edge=np.maximum.reduce([np.linalg.norm(screen[:,a]-screen[:,b],axis=1) for a,b in [(0,1),(1,2),(2,0)]])
        max_world_edge=np.maximum.reduce([np.linalg.norm(xyz[tri[:,a]]-xyz[tri[:,b]],axis=1) for a,b in [(0,1),(1,2),(2,0)]])
        local_depth=local[candidates,2].mean(axis=1)
        inside=((screen[:,:,0]>=0)&(screen[:,:,0]<image.camera.width)&
                (screen[:,:,1]>=0)&(screen[:,:,1]<image.camera.height)).all(axis=1)
        normal_agreement=np.minimum.reduce([(normals[tri[:,a]]*normals[tri[:,b]]).sum(axis=1) for a,b in [(0,1),(1,2),(2,0)]])
        # Assign each candidate facet to the unique majority reference view.
        # All corners must still be visible and cross-view depth-supported.
        same_reference=(primary[tri]==view).sum(axis=1)>=2
        valid=(max_pixel_edge<=12)&(max_world_edge<.03*local_depth)&(normal_agreement>.7)&(local_depth>0)&same_reference&inside
        for face,coords in zip(tri[valid],screen[valid]):
            if len(views[face[0]] & views[face[1]] & views[face[2]])<2:continue
            if len(support[face[0]] & support[face[1]] & support[face[2]])<2:continue
            key=tuple(sorted(map(int,face)))
            # A deterministic single reference per exact facet.
            if key not in faces:
                faces[key]=(face,coords/image.camera.width,image)
    if not faces:raise RuntimeError('No jointly supported local facets')
    material_images={}
    basename=args.output_basename
    with (work/(basename+'.obj')).open('w') as obj:
        obj.write(f'mtllib {basename}.mtl\n')
        for point in xyz:obj.write('v %.8g %.8g %.8g\n'%tuple(point))
        uv_index=1
        previous_material=None
        for face,coords,image in faces.values():
            material=int(image.image_id)
            material_images[material]=image
            if material!=previous_material:
                obj.write(f'usemtl camera_{material}\n')
                previous_material=material
            for uv in coords:
                obj.write(f'vt {uv[0]:.8g} {1-uv[1]*image.camera.width/image.camera.height:.8g}\n')
            obj.write('f '+' '.join(f'{int(v)+1}/{uv_index+i}' for i,v in enumerate(face))+'\n')
            uv_index+=3
    with (work/(basename+'.mtl')).open('w') as mtl:
        for number,image in material_images.items():
            name=f'{basename}_camera_{number}.jpg'
            shutil.copy2(work/'colmap/images'/Path(image.name).name,work/name)
            mtl.write(f'newmtl camera_{number}\nKa 1 1 1\nKd 1 1 1\nKs 0 0 0\nd 1\nillum 0\nmap_Kd {name}\n\n')
    result={'vertices':len(xyz),'faces':len(faces),'reference_cameras':len(material_images),
            'maximum_projected_edge_pixels_at_mvs_resolution':12,'maximum_edge_fraction_of_depth':.03,
            'min_vertex_support_views':3,'min_common_facet_support_views':2,
            'min_corners_with_same_reference':2,
            'exposure_group_audit':str(args.exposure_audit) if args.exposure_audit else None,
            'support_unit':'screened candidate exposure groups' if args.exposure_audit else 'image files',
            'note':'Measured partial surface. Unknown regions remain open; camera calibration and independent-view accuracy are not certified.'}
    (work/(basename+'-mesh-report.json')).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
