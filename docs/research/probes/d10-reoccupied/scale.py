import json, numpy as np, pycolmap, sys, re
snap=json.load(open('artifacts/artsquad_modern/snapshots/b43ad69e17eab9af2734acbf/snapshot.json'))
gps={}
for im in snap['images']:
    e=im.get('exif') or {}
    if 'latitude' in e and 'longitude' in e: gps[str(im['pageid'])]=(e['latitude'],e['longitude'],e.get('altitude'))
r=pycolmap.Reconstruction(sys.argv[1])
P=[];G=[];N=[]
allC={}
for im in r.images.values():
    m=re.search(r'(\d{6,})',im.name); pid=m.group(1) if m else None
    allC[im.name]=im.projection_center()
    if pid in gps and abs(gps[pid][0]-42.45)<0.01:
        lat,lon,_=gps[pid]
        x=(lon+76.4835)*111320*np.cos(np.radians(42.4475)); y=(lat-42.4475)*110540
        P.append(im.projection_center()); G.append([x,y]); N.append(im.name)
print('registered with Ithaca GPS:',len(P))
for n,g in zip(N,G): print('  ',n[:60],np.round(g,1))
if len(P)>=3:
    P=np.array(P);G=np.array(G)
    # scale from pairwise distance ratios (horizontal GPS vs 3D model distance), robust median
    rat=[]
    for i in range(len(P)):
        for j in range(i+1,len(P)):
            dg=np.linalg.norm(G[i]-G[j]); dp=np.linalg.norm(P[i]-P[j])
            if dg>15: rat.append(dg/dp)
    print('pairwise m/unit ratios (GPS dist>15 m):',np.round(sorted(rat),1))
# pairwise baselines in model units
names=list(allC); C=np.array([allC[n] for n in names])
D=np.linalg.norm(C[:,None]-C[None],axis=-1)
iu=np.triu_indices(len(names),1)
print('n cams',len(names),'pairs',len(iu[0]))
print('pairwise baseline percentiles (units) p5/p25/p50:',np.round(np.percentile(D[iu],[5,25,50]),3))
nn=np.sort(D,axis=1)[:,1]
print('nearest-neighbour baseline per camera (units):',np.round(np.sort(nn),3))
