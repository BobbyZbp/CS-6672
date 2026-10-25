# plane+parallax sensitivity per historical image using only surviving (cross-era) points
import numpy as np, pycolmap, sys
r=pycolmap.Reconstruction(sys.argv[1]); M_PER_UNIT=float(sys.argv[2])
imgs=r.images; pts=r.points3D
hist={i for i,im in imgs.items() if im.name.startswith('hist')}
def seen_by_modern(p): return any(el.image_id not in hist for el in p.track.elements)
mod=[i for i in imgs if i not in hist]
for i in sorted(hist,key=lambda k:imgs[k].name):
    im=imgs[i]; cam=r.cameras[im.camera_id]; f=cam.params[0]
    cw=im.cam_from_world() if callable(im.cam_from_world) else im.cam_from_world
    X=[pts[p.point3D_id].xyz for p in im.points2D if p.has_point3D() and seen_by_modern(pts[p.point3D_id])]
    nall=sum(1 for p in im.points2D if p.has_point3D())
    if len(X)<8: print(f"{im.name[:55]:55s} surviving pts={len(X)} (of {nall}) -> too few"); continue
    Xc=np.array([cw*x for x in X]); Z=Xc[:,2]
    # LS plane in camera coords
    c0=Xc.mean(0); u,s,vt=np.linalg.svd(Xc-c0); n=vt[2]; h=(Xc-c0)@n; dpi=abs(c0@n)
    S=f*np.abs(h)/(Z*max(dpi,1e-6))/M_PER_UNIT   # px of parallax per metre of baseline
    dinv=(1/np.percentile(Z,10)-1/np.percentile(Z,90))/M_PER_UNIT
    C=im.projection_center(); nn=min(np.linalg.norm(C-imgs[j].projection_center()) for j in mod)*M_PER_UNIT
    print(f"{im.name[:55]:55s} surv={len(X):3d}/{nall:3d} f={f:6.0f}px Zmed={np.median(Z)*M_PER_UNIT:5.0f}m dInvZ(p10-p90)={dinv:.4f}/m plane-rms={np.sqrt(np.mean(h**2))*M_PER_UNIT:5.1f}m S_p50/p90={np.percentile(S,50):5.1f}/{np.percentile(S,90):5.1f} px/m  nnModern={nn:5.1f}m")
