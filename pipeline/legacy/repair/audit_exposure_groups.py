#!/usr/bin/env python3
"""Conservative repeated-exposure screen, including differently colored scans.

A high global homography + warped gradient correlation flags a possible scan
copy. This is an uncertainty audit, not proof that a nonflagged view is unique.
"""
import argparse
import json
from itertools import combinations
from pathlib import Path

import cv2
import h5py
import numpy as np
from hloc.utils.io import get_matches

ROOT=Path(__file__).resolve().parents[3]


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--workspace',type=Path,default=ROOT/'artifacts/archive_target_v2')
    p.add_argument('--output',type=Path,default=ROOT/'artifacts/exposure-audit.json')
    args=p.parse_args();w=args.workspace
    with h5py.File(w/'feats-superpoint-n8192-r1600.h5') as f:
        names=sorted(f.keys());points={n:f[n]['keypoints'][:].astype('float32') for n in names}
    small={};scale={}
    for n in names:
        im=cv2.imread(str(w/'images_exterior'/n),cv2.IMREAD_GRAYSCALE)
        s=800/max(im.shape);small[n]=cv2.resize(im,None,fx=s,fy=s);scale[n]=s
    rows=[]
    for a,b in combinations(names,2):
        matches,_=get_matches(w/'matches-target-lightglue.h5',a,b)
        if len(matches)<40:continue
        x=points[a][matches[:,0]]*scale[a];y=points[b][matches[:,1]]*scale[b]
        H,inside=cv2.findHomography(x,y,cv2.USAC_MAGSAC,3,maxIters=5000,confidence=.999)
        if H is None:continue
        h,wid=small[b].shape
        warped=cv2.warpPerspective(small[a],H,(wid,h))
        overlap=cv2.warpPerspective(np.ones(small[a].shape,'uint8'),H,(wid,h))>0
        overlap=cv2.erode(overlap.astype('uint8'),np.ones((9,9),'uint8'))>0
        # Use local high-pass signal to reduce effects of hand coloring,
        # brightness, and scan tone; exclude a fixed printed border.
        overlap[:int(h*.05)]=False;overlap[int(h*.95):]=False
        overlap[:,:int(wid*.05)]=False;overlap[:,int(wid*.95):]=False
        ga=warped.astype(float)-cv2.GaussianBlur(warped,(0,0),3).astype(float)
        gb=small[b].astype(float)-cv2.GaussianBlur(small[b],(0,0),3).astype(float)
        corr=float(np.corrcoef(ga[overlap],gb[overlap])[0,1]) if overlap.sum()>1000 else 0
        ratio=float(inside.mean())
        rows.append({'a':a,'b':b,'matches':len(matches),'homography_inlier_fraction':ratio,
                     'overlap_fraction':float(overlap.mean()),'warped_highpass_correlation':corr,
                     'possible_same_exposure':bool(len(matches)>=100 and ratio>=.8 and corr>=.5 and overlap.mean()>=.35)})
    rows.sort(key=lambda r:r['warped_highpass_correlation'],reverse=True)
    parent={n:n for n in names}
    def group(n):
        while parent[n]!=n:n=parent[n]
        return n
    for r in rows:
        if r['possible_same_exposure']:parent[group(r['b'])]=group(r['a'])
    groups={}
    for n in names:groups.setdefault(group(n),[]).append(n)
    support=[]
    from plyfile import PlyData
    import pycolmap
    for directory in ['cpu_mvs_masked08_v3','cpu_mvs_masked12_v3']:
        work=ROOT/'artifacts'/directory
        if not (work/'dense.ply').exists():continue
        model=pycolmap.Reconstruction(str(work/'colmap/sparse'))
        indexed=[im.name for _,im in sorted(model.images.items())]
        data=PlyData.read(work/'dense.ply')['vertex'].data
        counts=np.array([len({group(indexed[int(i)]) for i in v}) for v in data['view_indices']])
        support.append({'workspace':directory,'dense_points':len(counts),
                        'registered_files':len(indexed),'candidate_exposure_groups':len({group(n) for n in indexed}),
                        'points_with_at_least_3_candidate_groups':int((counts>=3).sum()),
                        'note':'Conservative screening groups, not certified independent captures. Counts do not validate depth or focal calibration.'})
    result={'method':'800px homography + warped high-pass image correlation',
            'thresholds':{'min_matches_for_flag':100,'homography_inlier_fraction':.8,'highpass_correlation':.5,'overlap':.35},
            'threshold_selection':'Exploratory screening thresholds; not a preregistered duplicate benchmark.',
            'interpretation':'Screening candidates only. Nonflagged pairs are not certified independent exposures. Planar scenes can also correlate.',
            'candidate_pairs':[r for r in rows if r['possible_same_exposure']],
            'candidate_groups':list(groups.values()),'dense_support_audit':support,'pairs':rows}
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'candidates':len(result['candidate_pairs']),'top_pairs':rows[:12]},indent=2))


if __name__=='__main__':main()
