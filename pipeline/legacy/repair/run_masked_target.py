#!/usr/bin/env python3
"""Automatic building-only correspondence ablation inspired by NeuSC preprocessing."""
import json
import shutil
from pathlib import Path

import cv2
import h5py
import numpy as np
from PIL import Image,ImageDraw
import pycolmap
import torch
from transformers import CLIPSegForImageSegmentation,CLIPSegProcessor
from hloc import reconstruction
from hloc.utils.io import find_pair

ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT/'artifacts/archive_target_v2'
OUT=ROOT/'artifacts/masked_target_v3'
REVISION='999e0328d9e10b484360c477313983f9afdd7050'


def main():
    OUT.mkdir(parents=True,exist_ok=True);masks=OUT/'masks';masks.mkdir(exist_ok=True)
    images=SOURCE/'images_exterior'
    names=sorted(p.name for p in images.iterdir())
    torch.set_num_threads(4)
    processor=None;model=None;stats=[];allowed={};thumbs=[]
    features=SOURCE/'feats-superpoint-n8192-r1600.h5'
    with h5py.File(features) as f:
        for name in names:
            image=Image.open(images/name).convert('RGB');width,height=image.size
            path=masks/(name+'.mask.png')
            if path.exists():mask=np.asarray(Image.open(path))>0
            else:
                if model is None:
                    cache=ROOT/'.cache/huggingface'
                    processor=CLIPSegProcessor.from_pretrained('CIDAS/clipseg-rd64-refined',revision=REVISION,cache_dir=cache)
                    model=CLIPSegForImageSegmentation.from_pretrained('CIDAS/clipseg-rd64-refined',revision=REVISION,cache_dir=cache).eval()
                prompts=['a stone building with a roof','trees and foliage','the sky']
                inputs=processor(text=prompts,images=[image]*3,padding=True,return_tensors='pt')
                with torch.inference_mode():logits=model(**inputs).logits
                prob=torch.sigmoid(torch.nn.functional.interpolate(logits[:,None],size=(height,width),mode='bilinear',align_corners=False)[:,0]).numpy()
                mask=(prob[0]>.25)&(prob[0]>prob[1])&(prob[0]>prob[2])
                mask=cv2.dilate(mask.astype('uint8'),np.ones((7,7),'uint8'))>0
                mask[:int(height*.03)]=False;mask[int(height*.97):]=False
                mask[:,:int(width*.02)]=False;mask[:,int(width*.98):]=False
                Image.fromarray(mask.astype('uint8')*255).save(path)
            points=f[name]['keypoints'][:]
            # OpenMVS uses the basename without the image extension; retain
            # both aliases for explicit compatibility with its mask loader.
            alias=masks/(Path(name).stem+'.mask.png')
            if not alias.exists():shutil.copy2(path,alias)
            xy=np.rint(points).astype(int)
            xy[:,0]=np.clip(xy[:,0],0,width-1);xy[:,1]=np.clip(xy[:,1],0,height-1)
            allowed[name]=mask[xy[:,1],xy[:,0]]
            row={'image':name,'building_mask_fraction':float(mask.mean()),'kept_keypoints':int(allowed[name].sum()),'original_keypoints':len(points)}
            stats.append(row);print(json.dumps(row),flush=True)
            thumb=image.copy();thumb.thumbnail((260,175))
            mt=Image.fromarray(mask.astype('uint8')*255).convert('RGB');mt=mt.resize(thumb.size)
            card=Image.new('RGB',(530,205),'white');card.paste(thumb,(0,0));card.paste(mt,(270,0));ImageDraw.Draw(card).text((2,181),name[-65:],fill='black');thumbs.append(card)
    sheet=Image.new('RGB',(530*2,205*((len(thumbs)+1)//2)), '#ddd')
    for i,t in enumerate(thumbs):sheet.paste(t,((i%2)*530,(i//2)*205))
    sheet.save(OUT/'mask-audit.jpg')
    matches=OUT/'matches-building-only.h5';shutil.copy2(SOURCE/'matches-target-lightglue.h5',matches)
    pairs=SOURCE/'pairs-target-exhaustive.txt';before=after=0
    with h5py.File(matches,'r+') as f:
        for line in pairs.read_text().splitlines():
            a,b=line.split();group,reverse=find_pair(f,a,b)
            if reverse:a,b=b,a
            m=f[group]['matches0'][:];valid=m>=0;before+=int(valid.sum())
            keep=valid&allowed[a]
            keep[valid]&=allowed[b][m[valid]]
            m[~keep]=-1;f[group]['matches0'][:]=m
            scores=f[group]['matching_scores0'][:];scores[~keep]=0;f[group]['matching_scores0'][:]=scores
            after+=int(keep.sum())
    report={'semantic_model':'CIDAS/clipseg-rd64-refined','revision':REVISION,'input_images':len(names),
            'mask_policy':'building probability > .25 and exceeds tree/sky; 7px dilation; fixed scan-border exclusion',
            'views':stats,'raw_matches':before,'building_only_matches':after,'runs':{}}
    for focal in [.8,1.2]:
        sfm=OUT/f'sfm_focal_{focal}'
        recovered=reconstruction.main(sfm,images,pairs,features,matches,image_list=names,
            image_options={'camera_model':'SIMPLE_PINHOLE','default_focal_length_factor':focal},
            mapper_options={'num_threads':4,'ba_refine_focal_length':False,'ba_refine_extra_params':False})
        report['runs'][str(focal)]={'registered_images':recovered.num_reg_images() if recovered else 0,
            'points3D':recovered.num_points3D() if recovered else 0,'summary':recovered.summary() if recovered else None,
            'images':sorted(im.name for im in recovered.images.values()) if recovered else []}
        (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report['runs'],indent=2))


if __name__=='__main__':main()
