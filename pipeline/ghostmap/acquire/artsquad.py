#!/usr/bin/env python3
"""Stage M1.1: auditable modern Arts Quad originals and working derivatives."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
import socket
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageOps

from ghostmap.acquire.commons import difference_hash, metadata_value, safe_name

from ghostmap.paths import ROOT
API='https://commons.wikimedia.org/w/api.php'
AGENT='GhostMap-Research/0.2 (Cornell Arts Quad; public academic imagery)'
LAST_API_REQUEST=0.0


def wait_retry(error,attempt,label):
    from email.utils import parsedate_to_datetime
    header=error.headers.get('Retry-After','')
    required=0
    if header.isdigit():required=int(header)
    elif header:
        try:required=max(0,(parsedate_to_datetime(header)-datetime.now(timezone.utc)).total_seconds())
        except (ValueError,TypeError):pass
    delay=max(required,min(60,5*2**attempt))
    print(label,error.code,'respecting retry delay',round(delay,1),'seconds',flush=True)
    while delay>0:
        chunk=min(15,delay);time.sleep(chunk);delay-=chunk


def api(params):
    global LAST_API_REQUEST
    cache=ROOT/'data/artsquad_modern/api-cache';cache.mkdir(parents=True,exist_ok=True)
    key=hashlib.sha256(json.dumps(params,sort_keys=True).encode()).hexdigest()
    cached=cache/(key+'.json')
    if cached.exists():return json.loads(cached.read_text())
    req=urllib.request.Request(API+'?'+urllib.parse.urlencode({**params,'format':'json','formatversion':2,'maxlag':5}),headers={'User-Agent':AGENT})
    for attempt in range(7):
        try:
            time.sleep(max(0,1.5-(time.monotonic()-LAST_API_REQUEST)))
            LAST_API_REQUEST=time.monotonic()
            with urllib.request.urlopen(req,timeout=40) as r:payload=json.load(r)
            if payload.get('error',{}).get('code') in {'cirrussearch-too-busy-error','maxlag'} and attempt<6:
                time.sleep(15*(attempt+1));continue  # transient search overload: wait and retry
            if 'error' in payload:raise RuntimeError(str(payload['error']))
            cached.write_text(json.dumps(payload,ensure_ascii=False)+'\n')
            return payload
        except urllib.error.HTTPError as exc:
            if exc.code not in {429,500,502,503,504} or attempt==6:raise
            wait_retry(exc,attempt,'API')
        except (urllib.error.URLError,socket.timeout,TimeoutError):
            if attempt==6:raise
            time.sleep(min(15,2**attempt))
    raise RuntimeError('API retries exhausted')


def members(category):
    result=[];cont={}
    while True:
        d=api({'action':'query','list':'categorymembers','cmtitle':'Category:'+category,'cmtype':'file|subcat','cmlimit':'max',**cont})
        result.extend(d.get('query',{}).get('categorymembers',[]))
        if 'continue' not in d:return result
        cont=d['continue']


def search(query):
    result=[];cont={}
    while True:
        d=api({'action':'query','list':'search','srsearch':query,'srnamespace':6,'srlimit':100,**cont})
        result.extend(d.get('query',{}).get('search',[]))
        if 'continue' not in d:return result
        cont=d['continue']


def geosearch(lat,lon,radius_m):
    """Commons files whose recorded camera or object location lies within radius_m."""
    d=api({'action':'query','list':'geosearch','gscoord':f'{lat}|{lon}','gsradius':int(radius_m),'gsnamespace':6,'gslimit':500})
    return d.get('query',{}).get('geosearch',[])


def license_allowed(text):
    return bool(re.search(r'\bcc[ -]by(?:[ -]sa)?\b|\bcc0\b|public domain',text,re.I))


def assess(page,config):
    info=(page.get('imageinfo') or [{}])[0];meta=info.get('extmetadata',{})
    if info.get('mime') not in {'image/jpeg','image/png'}:return False,'not a supported still photograph'
    if min(info.get('width',0),info.get('height',0))<config['minimum_short_side']:return False,'native image resolution below minimum'
    license=' '.join(metadata_value(meta,k) for k in ['LicenseShortName','UsageTerms'])
    if not license_allowed(license):return False,'license is absent or outside CC / public-domain policy'
    # A building's construction date and an upload timestamp are not evidence
    # of the photographic capture epoch.
    date=metadata_value(meta,'DateTimeOriginal')
    years=[int(y) for y in re.findall(r'(?<!\d)((?:18|19|20)\d{2})(?!\d)',date)]
    current=datetime.now(timezone.utc).year
    if not years:return False,'capture date unknown; not silently treated as modern'
    if min(years)<config['capture_year_min'] or max(years)>current:return False,'capture date outside modern collection interval'
    subject=(page.get('title','')+' '+metadata_value(meta,'ObjectName')).lower()
    if re.search(r'postcard|engraving|lithograph|floor.?plan|historic photo|historic map',subject):return False,'likely reproduced historical or non-photographic document'
    if page.get('discovery'):
        # Full-text search can find portraits of alumni or unrelated pages
        # merely mentioning a building. Category membership or an explicit
        # scene title is required; keyword hits alone are not scene evidence.
        sources=page['discovery']['sources']
        compact=re.sub('[^a-z0-9]','',subject)
        named=any(re.sub('[^a-z0-9]','',t['name'].lower()) in compact for t in config['targets'])
        context='artsquad' in compact or 'artsquadrangle' in compact
        # A recorded location inside the Quad is spatial evidence, but bench
        # plaques and inscriptions near it are not scene views.
        located=any(s.startswith('geosearch:') for s in sources)
        if located and re.search(r'openbenches|inscription|plaque',subject):return False,'geolocated close-up of an inscription, not a scene view'
        if not(any(s.startswith('Category:') for s in sources) or named or context or located):return False,'full-text search hit without target category or explicit scene title'
    return True,'metadata eligible; scene identity and independent view still need geometric audit'


def discover(config,root):
    cached=root/'inventory.json'
    if cached.exists():return json.loads(cached.read_text())
    found={};origins={};category_log=[];errors=[]
    def add(page,source,target):
        key=int(page['pageid']);found[key]=page
        origins.setdefault(key,{'sources':[],'targets':[]})
        if source not in origins[key]['sources']:origins[key]['sources'].append(source)
        if target and target not in origins[key]['targets']:origins[key]['targets'].append(target)
    for target in config['targets']:
        try:
            direct=members(target['category']);files=0
            for row in direct:
                if row['ns']==6:add(row,'Category:'+target['category'],target['id']);files+=1
                elif row['ns']==14:
                    for sub in members(row['title'].removeprefix('Category:')):
                        if sub['ns']==6:add(sub,row['title'],target['id']);files+=1
            # Search titles as well as explicit categories, without broad
            # university-wide data collection or arbitrary per-building caps.
            query='intitle:"'+target['name']+'" Cornell'
            results=search(query)
            for row in results:add(row,'search:'+query,target['id'])
            category_log.append({'target':target['id'],'category':target['category'],'direct_and_child_files':files,'search_hits':len(results)})
            print(target['name'],files,'category files,',len(results),'search hits',flush=True)
        except Exception as exc:errors.append({'target':target['id'],'error':str(exc)})
    for query in config['context_searches']:
        try:
            for row in search(query):add(row,'search:'+query,None)
        except Exception as exc:errors.append({'query':query,'error':str(exc)})
    for area in config.get('geo_searches',[]):
        try:
            rows=geosearch(area['lat'],area['lon'],area['radius_m'])
            for row in rows:add(row,'geosearch:'+area['label'],None)
            print('geosearch',area['label'],len(rows),'files',flush=True)
        except Exception as exc:errors.append({'geosearch':area['label'],'error':str(exc)})
    pages=[];ids=sorted(found)
    for offset in range(0,len(ids),40):
        d=api({'action':'query','pageids':'|'.join(map(str,ids[offset:offset+40])),
               'prop':'imageinfo','iiprop':'url|size|mime|extmetadata'})
        for page in d.get('query',{}).get('pages',[]):
            page['discovery']=origins[int(page['pageid'])]
            if not page['discovery']['targets'] and any(s.startswith('geosearch:') for s in page['discovery']['sources']):
                # Located files carry no query target; take it from their own
                # Commons categories when one names a target building.
                categories=metadata_value(page.get('imageinfo',[{}])[0].get('extmetadata',{}),'Categories')
                page['discovery']['targets']=[t['id'] for t in config['targets'] if t['category'] in categories]
            ok,reason=assess(page,config);page['admission']={'eligible':ok,'reason':reason};pages.append(page)
    result={'created_utc':datetime.now(timezone.utc).isoformat(),'status':'partial_provider_errors' if errors else 'complete',
            'config':config,'category_audit':category_log,'provider_errors':errors,'pages':pages}
    cached.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    return result


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def exif_record(image):
    exif=image.getexif();result={}
    for tag,label in [(271,'make'),(272,'model'),(306,'date_time'),(274,'orientation')]:
        if tag in exif:result[label]=str(exif[tag])
    try:
        sub=exif.get_ifd(34665)
        for tag,label in [(36867,'date_time_original'),(37386,'focal_length_mm'),(41989,'focal_length_35mm')]:
            if tag in sub:result[label]=str(sub[tag])
        gps=exif.get_ifd(34853)
        if gps:
            def degrees(v):return float(v[0])+float(v[1])/60+float(v[2])/3600
            if 2 in gps and 4 in gps:
                result['latitude']=degrees(gps[2])*(-1 if gps.get(1)=='S' else 1)
                result['longitude']=degrees(gps[4])*(-1 if gps.get(3)=='W' else 1)
    except (KeyError,TypeError,ValueError,ZeroDivisionError):pass
    return result


def download_original(url,path):
    request=urllib.request.Request(url,headers={'User-Agent':AGENT})
    temporary=path.with_suffix(path.suffix+'.part')
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request,timeout=45) as response,temporary.open('wb') as output:
                for chunk in iter(lambda:response.read(1024*1024),b''):output.write(chunk)
            temporary.replace(path)
            time.sleep(.3)
            return
        except urllib.error.HTTPError as exc:
            if exc.code not in {429,500,502,503,504} or attempt==4:raise
            wait_retry(exc,attempt,'Original download')
        except (urllib.error.URLError,socket.timeout,TimeoutError):
            if attempt==4:raise
            time.sleep(min(15,2**attempt))


def acquire(inventory,root,working):
    config=inventory['config'];originals=root/'originals';originals.mkdir(exist_ok=True);working.mkdir(parents=True,exist_ok=True)
    records=[];skipped=[];hashes={};budget=int(config['maximum_download_gib']*1024**3)
    used=sum(p.stat().st_size for p in originals.iterdir() if p.is_file() and not p.name.endswith('.part'))
    for page in inventory['pages']:
        if not page['admission']['eligible']:continue
        info=page['imageinfo'][0];meta=info.get('extmetadata',{});name=safe_name(page,info['mime']);path=originals/name
        try:
            if not path.exists():
                size=int(info.get('size',0))
                if used+size>budget or shutil.disk_usage(root).free-size<config['minimum_free_disk_gib']*1024**3:
                    skipped.append({'pageid':page['pageid'],'reason':'disk / download budget; not a quality rejection'});continue
                download_original(info['url'],path);used+=path.stat().st_size
            sha=digest(path)
            if sha in hashes:
                skipped.append({'pageid':page['pageid'],'reason':'exact byte duplicate','same_as':hashes[sha]});continue
            hashes[sha]=page['pageid']
            derivative=working/('modern__'+Path(name).stem+'.jpg')
            with Image.open(path) as image:
                original_size=image.size;exif=exif_record(image)
                orientation=int(image.getexif().get(274,1))
                oriented_size=original_size[::-1] if orientation in {5,6,7,8} else original_size
                xmp=image.info.get('XML:com.adobe.xmp') or image.info.get('xmp',b'')
                if isinstance(xmp,bytes):xmp=xmp.decode('utf-8','ignore')
                projection_hint='equirectangular' if 'equirectangular' in str(xmp).lower() else 'unknown'
                if not derivative.exists():
                    resized=ImageOps.exif_transpose(image).convert('RGB')
                    resized.thumbnail((config['working_image_max_dimension'],)*2,Image.Resampling.LANCZOS)
                    # Keep physical focal / camera metadata when present.
                    # exif_transpose removes the original orientation flag.
                    resized.save(derivative,quality=96,subsampling=0,exif=resized.info.get('exif',b''))
            with Image.open(derivative) as check:size=check.size
            records.append({'pageid':page['pageid'],'title':page['title'],'filename':derivative.name,'original_filename':name,
                            'original_url':info['url'],'source_url':info.get('descriptionurl'),
                            'capture_date_asserted':metadata_value(meta,'DateTimeOriginal'),
                            'license':metadata_value(meta,'LicenseShortName'),'license_url':metadata_value(meta,'LicenseUrl'),
                            'artist':metadata_value(meta,'Artist'),'credit':metadata_value(meta,'Credit'),
                            'discovery':page['discovery'],'sha256_original':sha,'sha256_working':digest(derivative),
                            'original_size':original_size,'working_size':size,'dhash64':difference_hash(derivative),'exif':exif})
            records[-1]['oriented_original_size']=oriented_size
            records[-1]['projection_hint']=projection_hint
            records[-1]['scope_review_hint']='interior candidate' if re.search(r'interior|reading room|library stacks|inside',page['title'],re.I) else 'unverified exterior / context candidate'
            print('ACQUIRED',len(records),name,original_size,flush=True)
        except Exception as exc:skipped.append({'pageid':page['pageid'],'reason':'download / decode error','error':str(exc)})
        (root/'manifest.json').write_text(json.dumps({'status':'running','images':records,'skipped':skipped},indent=2,ensure_ascii=False)+'\n')
    report={'created_utc':datetime.now(timezone.utc).isoformat(),'status':'acquired_with_skips' if skipped else 'acquired',
            'config':config,'images':records,'skipped':skipped,'source_original_bytes':used,
            'claims':{'scene_reconstructed':False,'capture_independence_verified':False,'metric_scale_known':False}}
    (root/'manifest.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    return report


def main():
    p=argparse.ArgumentParser();p.add_argument('--inventory-only',action='store_true');p.add_argument('--download',action='store_true')
    args=p.parse_args()
    if not(args.inventory_only or args.download):p.error('Choose --inventory-only or --download')
    root=ROOT/'data/artsquad_modern';root.mkdir(parents=True,exist_ok=True)
    config=json.loads((ROOT/'config/artsquad-modern.json').read_text())
    inventory=discover(config,root);pages=inventory['pages']
    # Re-audit cached raw API metadata using the current explicit admission
    # policy; an old search snapshot must not bypass later scope checks.
    for page in pages:
        ok,reason=assess(page,config);page['admission']={'eligible':ok,'reason':reason}
    inventory['admission_policy_version']=2
    (root/'inventory.json').write_text(json.dumps(inventory,indent=2,ensure_ascii=False)+'\n')
    counts=[]
    for target in config['targets']:
        group=[x for x in pages if target['id'] in x['discovery']['targets']]
        counts.append({'id':target['id'],'name':target['name'],'role':target['role'],'discovered':len(group),
                       'metadata_eligible':sum(x['admission']['eligible'] for x in group)})
    summary={'provider_status':inventory['status'],'discovered_unique_files':len(pages),
             'metadata_eligible_unique_files':sum(x['admission']['eligible'] for x in pages),'by_target':counts,
             'interpretation':'Metadata and query membership are not camera registration or geometric building coverage.'}
    if args.download:
        acquired=acquire(inventory,root,ROOT/'artifacts/artsquad_modern/images')
        summary['acquired_images']=len(acquired['images']);summary['skipped']=len(acquired['skipped'])
        for row in counts:row['acquired']=sum(row['id'] in x['discovery']['targets'] for x in acquired['images'])
    (root/'coverage.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
