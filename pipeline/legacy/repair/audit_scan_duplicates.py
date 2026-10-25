#!/usr/bin/env python3
"""Audit homography-dominated scan pairs; never count file copies as new views."""
import argparse
import json
import sqlite3
from itertools import combinations
from pathlib import Path

import cv2
import h5py
import numpy as np
from hloc.utils.io import get_matches


def main():
    p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True);args=p.parse_args()
    w=args.workspace
    with h5py.File(w/'feats-superpoint-n8192-r1600.h5') as f:
        names=sorted(f.keys())
        keypoints={n:f[n]['keypoints'][:].astype(np.float32) for n in names}
    dominated=[]
    verified={}
    database=w/'sfm_fixed_focal_0.8/database.db'
    if database.exists():
        with sqlite3.connect(database) as db:
            image_names=dict(db.execute('SELECT image_id,name FROM images'))
            for pair_id,rows,data in db.execute('SELECT pair_id,rows,data FROM two_view_geometries WHERE rows>=50'):
                j=pair_id%2147483647;i=(pair_id-j)//2147483647
                verified[(image_names[i],image_names[j])]=np.frombuffer(data,dtype=np.uint32).reshape(-1,2)
    for a,b in combinations(names,2):
        if (a,b) in verified:matches=verified[a,b]
        elif (b,a) in verified:matches=verified[b,a][:,::-1]
        else:continue
        if len(matches)<50:continue
        x,y=keypoints[a][matches[:,0]],keypoints[b][matches[:,1]]
        H,inliers=cv2.findHomography(x,y,cv2.USAC_MAGSAC,3.0,maxIters=5000,confidence=.999)
        if H is None:continue
        ratio=float(inliers.mean())
        if ratio>=.9:
            dominated.append({'a':a,'b':b,'matches':len(matches),'homography_inlier_fraction':ratio})
    result={'homography_dominated_pairs':dominated,
            'interpretation':'These are scan-copy / planar-scene candidates. A homography alone does not prove duplication; independent camera baseline must be verified before treating them as separate support.',
            'match_basis':'COLMAP geometrically verified inliers',
            'thresholds':{'min_matches':50,'min_homography_inlier_fraction':.9,'reprojection_threshold_pixels':3}}
    (w/'duplicate-scan-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(len(dominated),'homography-dominated scan-pair candidates')


if __name__=='__main__':main()
