import pycolmap, numpy as np, sys
r=pycolmap.Reconstruction(sys.argv[1])
X=np.array([r.images[i].cam_from_world().rotation.matrix()[0] for i in r.images]); up=np.linalg.svd(X)[2][-1]
allxyz=np.array([p.xyz for p in r.points3D.values()]); rad=np.median(np.linalg.norm(allxyz-np.median(allxyz,0),axis=1))
hs=allxyz@up
if np.median(hs - np.array([r.images[i].projection_center()@up for i in r.images]).mean())<0: up=-up; hs=-hs
print('scene radius units', round(rad,3), 'height p1/p99 span', round(np.percentile(hs,99)-np.percentile(hs,1),3), 'p0.1/p99.9', round(np.percentile(hs,99.9)-np.percentile(hs,0.1),3))
modern=set(i for i,im in r.images.items() if im.name.startswith('modern'))
for iid,im in r.images.items():
    if 'Boardman' not in im.name: continue
    C=im.projection_center()
    P=np.array([r.points3D[p.point3D_id].xyz for p in im.points2D if p.has_point3D() and set(e.image_id for e in r.points3D[p.point3D_id].track.elements)&modern])
    d=np.linalg.norm(P-C,axis=1)
    # depth extent of anchor along viewing ray
    z=im.cam_from_world().rotation.matrix()[2]; depth=(P-C)@z
    print(im.name[12:50], 'anchor median dist %.2f u; anchor depth range p5-p95 %.2f u; ratio %.3f'%(np.median(d), np.percentile(depth,95)-np.percentile(depth,5), (np.percentile(depth,95)-np.percentile(depth,5))/np.median(depth)))
