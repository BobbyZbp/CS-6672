import pycolmap, numpy as np, sys, json
rec = pycolmap.Reconstruction(sys.argv[1])
imgs=rec.images; era={i:('h' if im.name.startswith('historical') else 'm') for i,im in imgs.items()}
X=np.array([imgs[i].cam_from_world().rotation.matrix()[0] for i in imgs]); up=np.linalg.svd(X)[2][-1]
B=[i for i in imgs if 'Boardman' in imgs[i].name]
P=np.array([p.xyz for p in rec.points3D.values() if set(era[e.image_id] for e in p.track.elements)=={'h'} and sum(e.image_id in B for e in p.track.elements)>=2])
Q=np.array([p.xyz for p in rec.points3D.values() if 'm' in set(era[e.image_id] for e in p.track.elements)])
c=P.mean(0); t=np.median(Q,0)
def flat(v): return v-up*(v@up)
ref=flat(t-c); ref/=np.linalg.norm(ref); orth=np.cross(up,ref)
for i,im in sorted(imgs.items(), key=lambda x:x[1].name):
    if era[i]!='h': continue
    C=im.projection_center(); v=flat(C-c); vt=flat(C-t)
    n=sum(1 for p in im.points2D if p.has_point3D() and 'm' in set(era[e.image_id] for e in rec.points3D[p.point3D_id].track.elements))
    print('%-58s az_about_histcentroid %7.1f  az_about_anchor %7.1f  dist_to_anchor %.2f  anchors %d'%(im.name[:58], np.degrees(np.arctan2(v@orth,v@ref)), np.degrees(np.arctan2(vt@orth,vt@ref)), np.linalg.norm(vt), n))
