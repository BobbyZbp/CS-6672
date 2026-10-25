import numpy as np, pycolmap, sys
r=pycolmap.Reconstruction(sys.argv[1])
ups=[];C=[]
for im in r.images.values():
    cw=im.cam_from_world() if callable(im.cam_from_world) else im.cam_from_world
    R=cw.rotation.matrix()
    ups.append(-R[1,:])  # camera -y in world
    C.append(im.projection_center())
up=np.mean(ups,axis=0); up/=np.linalg.norm(up)
print('up consistency (mean |cos| to mean up):',np.round(np.mean([u@up/np.linalg.norm(u) for u in ups]),3))
X=np.array([p.xyz for p in r.points3D.values() if p.track.length()>=3])
h=X@up; hc=np.array(C)@up
print('camera height p10/p50/p90:',np.round(np.percentile(hc,[10,50,90]),2))
print('point height p1/p50/p99/p99.9/max:',np.round(np.percentile(h,[1,50,99,99.9,100]),2))
print('top(p99.9) - median camera height (units):',round(np.percentile(h,99.9)-np.median(hc),2))
