#!/usr/bin/env python3
"""Texture the unchanged dense mesh from calibrated supporting photographs.

Faces without shared stereo visibility remain gray. This avoids the ambiguous
OpenMVS atlas orientation and keeps explicit source-camera UV provenance.
"""
import argparse
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
from plyfile import PlyData
import pycolmap
from scipy.spatial import cKDTree

from run_cpu_mvs import command


def main():
    p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True);args=p.parse_args()
    work=args.workspace.resolve()
    export=work/'export-cameras'
    if not (export/'sparse/images.txt').exists():
        subprocess.run(command('InterfaceCOLMAP')+['-i',str(work/'dense.mvs'),'-o',str(export),'--binary','0'],check=True,stdout=subprocess.DEVNULL)
    calibration=pycolmap.Reconstruction(str(export/'sparse'))
    cameras=sorted(calibration.images.items())
    cloud=PlyData.read(work/'dense.ply')['vertex'].data
    points=np.column_stack([cloud[k] for k in ['x','y','z']]).astype(float)
    data=PlyData.read(work/'surface.ply')
    xyz=np.column_stack([data['vertex'][k] for k in ['x','y','z']]).astype(float)
    faces=np.stack(data['face']['vertex_indices']).astype(int)
    nearest=cKDTree(points).query(xyz,workers=4)[1]
    visibility=np.zeros((len(points),len(cameras)),dtype=bool)
    for i,views in enumerate(cloud['view_indices']):visibility[i,views]=True
    corners=xyz[faces];centers=corners.mean(1)
    normals=np.cross(corners[:,1]-corners[:,0],corners[:,2]-corners[:,0])
    normals/=np.maximum(np.linalg.norm(normals,axis=1,keepdims=True),1e-12)
    best=np.full(len(faces),-np.inf);chosen=np.full(len(faces),-1,dtype=int)
    uv=np.zeros((len(faces),3,2),dtype=np.float32)
    vertex_nearest=nearest[faces]
    for view,(_,image) in enumerate(cameras):
        supported=visibility[vertex_nearest,view].all(axis=1)
        indices=np.flatnonzero(supported)
        if not len(indices):continue
        R=image.cam_from_world().rotation.matrix();t=image.cam_from_world().translation
        cam=xyz@R.T+t;projected=cam@image.camera.calibration_matrix().T
        pixel=projected[:,:2]/projected[:,2:]
        projected_faces=pixel[faces[indices]]
        width,height=image.camera.width,image.camera.height
        inside=((projected_faces[:,:,0]>=0)&(projected_faces[:,:,0]<width)&(projected_faces[:,:,1]>=0)&(projected_faces[:,:,1]<height)).all(axis=1)
        depth=(cam[faces[indices],2]>0).all(axis=1)
        pixel_edge=np.maximum.reduce([np.linalg.norm(projected_faces[:,a]-projected_faces[:,b],axis=1) for a,b in [(0,1),(1,2),(2,0)]])
        direction=image.projection_center()-centers[indices]
        distance=np.linalg.norm(direction,axis=1)
        cosine=(normals[indices]*direction).sum(1)/np.maximum(distance,1e-12)
        focal=float(image.camera.calibration_matrix()[0,0])
        score=focal**2*np.maximum(cosine,0)/np.maximum(distance**2,1e-12)
        valid=inside&depth&(cosine>.05)&(pixel_edge<=32)&(score>best[indices])
        selected=indices[valid]
        best[selected]=score[valid];chosen[selected]=view
        uv[selected]=projected_faces[valid]/np.array([width,height])
    with (work/'projected.obj').open('w') as obj,(work/'projected.mtl').open('w') as mtl:
        obj.write('mtllib projected.mtl\n')
        for point in xyz:obj.write('v %.9g %.9g %.9g\n'%tuple(point))
        mtl.write('newmtl unobserved\nKd 0.25 0.27 0.25\nillum 0\n\n')
        texcoord=1
        for view in sorted(set(map(int,chosen))):
            indices=np.flatnonzero(chosen==view)
            if view<0:
                obj.write('usemtl unobserved\n')
                for f in faces[indices]:obj.write('f '+' '.join(str(v+1) for v in f)+'\n')
                continue
            image=cameras[view][1]
            name=f'projected_camera_{view}.jpg'
            shutil.copy2(work/'colmap/images'/Path(image.name).name,work/name)
            mtl.write(f'newmtl camera_{view}\nKd 1 1 1\nillum 0\nmap_Kd {name}\n\n')
            obj.write(f'usemtl camera_{view}\n')
            for index in indices:
                for coord in uv[index]:obj.write(f'vt {coord[0]:.9g} {1-coord[1]:.9g}\n')
                obj.write('f '+' '.join(f'{v+1}/{texcoord+i}' for i,v in enumerate(faces[index]))+'\n')
                texcoord+=3
    result={'mesh_vertices':len(xyz),'mesh_faces':len(faces),'textured_faces':int((chosen>=0).sum()),
            'untextured_faces':int((chosen<0).sum()),'geometry_modified':False,
            'texture_policy':'All three nearest stereo vertices share the source view; front-facing; inside image; maximum projected edge 32px. Highest projected resolution selected. Unobserved faces stay gray.',
            'source_cameras':{str(i):cameras[i][1].name for i in sorted(set(chosen)) if i>=0}}
    (work/'projected-texture-report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
