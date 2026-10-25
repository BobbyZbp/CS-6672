#!/usr/bin/env python3
"""Compare geometry under focal priors using shared feature-track identities."""
from collections import Counter
import argparse
import json
from pathlib import Path

import numpy as np
import pycolmap

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'artifacts/target_sfm_v2'


def compare(a,b):
    votes=Counter()
    named={im.name:im for im in b.images.values()}
    for image in a.images.values():
        if image.name not in named:continue
        other=named[image.name]
        for p,q in zip(image.points2D,other.points2D):
            if a.exists_point3D(p.point3D_id) and b.exists_point3D(q.point3D_id):
                votes[int(p.point3D_id),int(q.point3D_id)]+=1
    pairs=[k for k,v in votes.items() if v>=2]
    if len(pairs)<6:return {'shared_tracks':len(pairs),'status':'too_few_common_tracks'}
    x=np.array([a.points3D[i].xyz for i,j in pairs]);y=np.array([b.points3D[j].xyz for i,j in pairs])
    keep=np.ones(len(x),dtype=bool)
    for _ in range(4):
        mx=x[keep].mean(0);my=y[keep].mean(0)
        xc=x[keep]-mx;yc=y[keep]-my
        U,s,V=np.linalg.svd(yc.T@xc/len(xc));sign=np.ones(3);sign[-1]=np.linalg.det(U@V)
        R=U@np.diag(sign)@V
        scale=np.sum(s*sign)/np.mean(np.sum(xc**2,axis=1))
        error=np.linalg.norm(scale*(x-mx)@R.T+my-y,axis=1)
        keep=error<=np.quantile(error,.8)
    radius=np.median(np.linalg.norm(y-np.median(y,axis=0),axis=1))
    return {'shared_tracks':len(pairs),'similarity_scale':float(scale),
            'median_displacement_relative_to_scene_radius':float(np.median(error)/radius),
            'p90_displacement_relative_to_scene_radius':float(np.quantile(error,.9)/radius),
            'interpretation':'Sensitivity after robust similarity alignment; not an error against ground truth.'}


def main():
    p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,default=WORK);p.add_argument('--prefix',default='sfm_fixed_focal_');args=p.parse_args()
    models={f:pycolmap.Reconstruction(str(args.workspace/(args.prefix+f))) for f in ['0.8','1.2','1.8'] if (args.workspace/(args.prefix+f)/'images.bin').exists()}
    results={f'0.8_vs_{f}':compare(models['0.8'],m) for f,m in models.items() if f!='0.8'}
    (args.workspace/'focal-geometry-sensitivity.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps(results,indent=2))


if __name__=='__main__':main()
