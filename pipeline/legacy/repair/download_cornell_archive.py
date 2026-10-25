#!/usr/bin/env python3
"""Acquire public research scans via Cornell's official viewer-linked IIIF.

Archive permissions are not invented: retain the source's rights statement and
mark these scans research-only when no explicit redistribution license appears.
This separate dataset does not change the Commons release manifest.
"""
import hashlib
import argparse
import html
import json
import re
import shutil
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'data/cornell_archive'


def read(url):
    req=urllib.request.Request(url,headers={'User-Agent':'GhostMap-CS6672-research/0.2'})
    with urllib.request.urlopen(req,timeout=45) as r:return r.read()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--prepare-only',action='store_true')
    args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    if args.prepare_only:
        prepare_inputs(json.loads((OUT/'manifest.json').read_text())['images'])
        return
    search='https://digital.library.cornell.edu/catalog.json?'+urllib.parse.urlencode({'q':'"Boardman Hall"','search_field':'all_fields','per_page':100})
    records=json.loads(read(search))['data']
    accepted=[];rejected=[]
    for record in records:
        rid=record['id'];attributes=record.get('attributes',{})
        fields={k:v['attributes']['value'] for k,v in attributes.items() if isinstance(v,dict) and 'attributes' in v}
        if fields.get('format_tesim')!='Image':continue
        if str(fields.get('date_tesim','')).startswith('2012'):
            rejected.append({'id':rid,'reason':'modern-date record'});continue
        source='https://digital.library.cornell.edu/catalog/'+rid
        try:
            raw=read(source).decode()
            tile=re.search(r'data-openseadragon-options="([^"]+)"',raw)
            if not tile:raise ValueError('no official viewer-linked IIIF metadata')
            options=json.loads(html.unescape(tile[1]));info_url=options['tileSources']
            if not isinstance(info_url,str):raise ValueError('unsupported multi-image viewer')
            info=json.loads(read(info_url))
            base=info.get('@id',info.get('id'))
            # 1600-2000 pixels retains scan detail without requesting expensive
            # huge derivatives; the full dimensions and service remain audited.
            maxdim=max(info['width'],info['height'])
            width=round(info['width']*min(1,2000/maxdim))
            image_url=f'{base}/full/{width},/0/default.jpg'
            filename='cornell_'+rid.replace(':','_')+'_Boardman_archive.jpg'
            dest=OUT/filename
            if not dest.exists():dest.write_bytes(read(image_url))
            with Image.open(dest) as im:size=im.size;im.verify()
            title=re.search(r'<title>(.*?)</title>',raw,re.S)
            accepted.append({'id':rid,'title':html.unescape(title[1]) if title else rid,
                'source_url':source,'info_url':info_url,'image_url':image_url,
                'original_size':[info['width'],info['height']],'download_size':list(size),
                'filename':filename,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),
                'rights':'Research use; no explicit redistribution license established.',
                'rights_source':'https://www.library.cornell.edu/about/policies/copyright/',
                'catalog_metadata':fields})
            print(rid,size,accepted[-1]['title'],flush=True)
        except Exception as e:
            rejected.append({'id':rid,'source_url':source,'error':str(e)})
            print('excluded',rid,str(e),flush=True)
    (OUT/'manifest.json').write_text(json.dumps({'source':search,'images':accepted,'rejections':rejected},indent=2)+'\n')
    # New research input folder; originals and release dataset are untouched.
    prepare_inputs(accepted)
    print('acquired',len(accepted),'archive research images')


def prepare_inputs(accepted):
    inputs=ROOT/'artifacts/archive_target_v2/images_exterior';inputs.mkdir(parents=True,exist_ok=True)
    for p in (ROOT/'artifacts/work/joint/images').iterdir():
        if p.name.startswith('historical__') and 'boardman' in p.name.lower():shutil.copy2(p,inputs/p.name)
    excluded=[]
    for item in accepted:
        if re.search(r'law (?:school )?library|portrait',item['title'],re.I):
            excluded.append({'id':item['id'],'title':item['title'],'reason':'metadata identifies interior or portrait'})
            continue
        shutil.copy2(OUT/item['filename'],inputs/('historical__'+item['filename']))
    (inputs.parent/'input-filter.json').write_text(json.dumps({'excluded':excluded,'input_images':sorted(p.name for p in inputs.iterdir())},indent=2)+'\n')
    print(len(list(inputs.iterdir())),'combined exterior target inputs')


if __name__=='__main__':main()
