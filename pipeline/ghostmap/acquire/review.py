#!/usr/bin/env python3
"""Screen scene candidates, documents, interiors and structural-epoch risks.

Metadata screening is not semantic or geometric ground truth. All originals
are retained, including files excluded from the outdoor SfM input list.
"""
import json
import re
from collections import Counter

from PIL import Image,ImageDraw
from ghostmap.acquire.commons import metadata_value

from ghostmap.paths import ROOT


def review(title,categories,projection):
    text=(title+' '+categories).lower()
    if re.search(r'\bplans?\b|\bfloor.?plans?\b|\baxon\b|\baxonometric\b|\bdiagrams?\b|\bblueprints?\b|thesis review',title,re.I):
        return 'reference-document','Do not import a plan, drawing or review-board image as a scene camera.'
    if projection=='equirectangular' or re.search(r'photo.?stitch|\bstitched\b|\bpanoram(?:a|ic)\b',title,re.I):
        return 'panorama-camera-review','Needs spherical / derived-perspective cameras; tiles are not new baselines.'
    if re.search(r'edit.?a.?thon|art\s*(?:\+|and|&)\s*feminism|artandfeminism|'
                 r'\beditors?\b.*\b(?:work|researching|collaborating|event)\b|'
                 r'\bresearching for edits\b|\bediting (?:for|during)\b',text,re.I):
        return 'interior-event-review','Event/person-focused imagery; outdoor scene and static geometry need visual review before mapping.'
    if re.search(r'\binteriors?\b|reading.?rooms?|library stacks|\binside\b',text):
        return 'interior','Keep separate from the outdoor quad camera graph.'
    if re.search(r'\brenovation\b|\bconstruction\b|\bscaffolding\b',text):
        return 'structural-epoch-review','Do not silently mix changed geometry into one timeless campus.'
    if re.search(r'mui ho|fine arts library|\blibrary [1-9]\b',title,re.I):
        return 'interior-exterior-review','Ambiguous library title; needs automatic visual / overlap review.'
    if re.search(r'\bbust of\b|\bportrait of\b',title,re.I):
        return 'isolated-object-review','Object photography alone does not establish an outdoor scene connection.'
    return 'scene-candidate','Metadata only: scene identity, independent baseline and geometric support remain unverified.'


def main():
    root=ROOT/'data/artsquad_modern';manifest=json.loads((root/'manifest.json').read_text())
    if manifest['status']=='running':raise RuntimeError('Wait for acquisition to finish before creating a stable input list.')
    inventory=json.loads((root/'inventory.json').read_text())
    pages={p['pageid']:p for p in inventory['pages']};records=[]
    for im in manifest['images']:
        page=pages[im['pageid']];meta=page.get('imageinfo',[{}])[0].get('extmetadata',{})
        role,note=review(im['title'],metadata_value(meta,'Categories'),im.get('projection_hint'))
        records.append({'filename':im['filename'],'pageid':im['pageid'],'role':role,'note':note,'targets':im['discovery']['targets']})
    counts=dict(Counter(r['role'] for r in records))
    output={'method':'deterministic metadata-only input-role screen','counts':counts,'images':records,
            'claims':{'visual_classification_verified':False,'independent_captures_verified':False,'geometric_coverage_verified':False}}
    work=ROOT/'artifacts/artsquad_modern'
    (work/'scene-image-list.txt').write_text(''.join(r['filename']+'\n' for r in records if r['role']=='scene-candidate'))
    contact=work/'input-audit';contact.mkdir(exist_ok=True)
    role_by_name={r['filename']:r['role'] for r in records};per_target=[]
    for target in manifest['config']['targets']:
        images=[im for im in manifest['images'] if target['id'] in im['discovery']['targets']]
        if not images:continue
        cols=3;cell_w=320;cell_h=240
        sheet=Image.new('RGB',(cols*cell_w,cell_h*((len(images)+cols-1)//cols)),'#eeece5')
        draw=ImageDraw.Draw(sheet)
        for i,im in enumerate(images):
            x=i%cols*cell_w;y=i//cols*cell_h
            with Image.open(work/'images'/im['filename']) as photo:
                small=photo.copy();small.thumbnail((310,185));sheet.paste(small,(x,y))
            draw.text((x+3,y+188),str(im['pageid'])+' '+im['capture_date_asserted'][:20],fill='black')
            draw.text((x+3,y+205),role_by_name[im['filename']],fill='black')
            draw.text((x+3,y+222),im['title'][5:44],fill='black')
        sheet.save(contact/(target['id']+'.jpg'))
        per_target.append({'id':target['id'],'name':target['name'],'role':target['role'],
                           'acquired':len(images),'scene_candidates':sum(role_by_name[i['filename']]=='scene-candidate' for i in images)})
    output['by_target']=per_target
    (root/'scene-input-audit.json').write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps({'counts':counts,'by_target':per_target},indent=2))


if __name__=='__main__':main()
