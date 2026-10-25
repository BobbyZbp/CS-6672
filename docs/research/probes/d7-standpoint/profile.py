import sys, numpy as np, pycolmap, cv2
r=pycolmap.Reconstruction(sys.argv[1])
modern=set(i for i,im in r.images.items() if im.name.startswith('modern'))
# up vector: mean of -y axis of modern cameras in world
ups=[]
for i in modern:
    R=r.images[i].cam_from_world().rotation.matrix(); ups.append(-R[1])
up=np.mean(ups,0); up/=np.linalg.norm(up)
allxyz=np.array([p.xyz for p in r.points3D.values()]); cen=np.median(allxyz,0)
rad=np.median(np.linalg.norm(allxyz-cen,axis=1))
print('up',up,'scene radius(median)',rad)
for iid,im in sorted(r.images.items(), key=lambda x:x[1].name):
    if im.name.startswith('modern'): continue
    cam=r.cameras[im.camera_id]
    X=[];x=[]
    for p in im.points2D:
        if not p.has_point3D(): continue
        P=r.points3D[p.point3D_id]
        if set(e.image_id for e in P.track.elements)&modern:
            X.append(P.xyz); x.append(p.xy)
    X=np.array(X,float); x=np.array(x,float)
    if len(X)<8: print(im.name[:50],'too few',len(X)); continue
    W,H=cam.width,cam.height; m=max(W,H); f0=cam.params[0]; k=cam.params[3]
    cx,cy=cam.params[1],cam.params[2]
    # anchor stats
    R0=im.cam_from_world().rotation.matrix(); t0=im.cam_from_world().translation
    Xc=(R0@X.T).T+t0; d=Xc[:,2]
    bb=(x.max(0)-x.min(0))/np.array([W,H])
    res=[]
    for ratio in np.exp(np.linspace(np.log(0.4),np.log(4.0),41)):
        f=ratio*m
        K=np.array([[f,0,cx],[0,f,cy],[0,0,1.]])
        ok,rv,tv=cv2.solvePnP(X,x,K,None,flags=cv2.SOLVEPNP_SQPNP)
        ok,rv,tv=cv2.solvePnP(X,x,K,None,rv,tv,True,flags=cv2.SOLVEPNP_ITERATIVE)
        pr,_=cv2.projectPoints(X,rv,tv,K,None); e=np.linalg.norm(pr[:,0]-x,axis=1)
        Rm,_=cv2.Rodrigues(rv); C=(-Rm.T@tv).ravel()
        res.append((ratio,np.sqrt(np.mean(e**2)),np.median(e),C))
    rms=np.array([q[1] for q in res]); best=rms.argmin()
    n=len(X); sig2=rms[best]**2
    # profile-likelihood-ish 95%: n*(rms^2 - rms_min^2)/sig2 < 3.84 (2 dims per point -> 2n residuals)
    chi=2*n*(rms**2-rms[best]**2)/sig2
    ins=[q[0] for q,c in zip(res,chi) if c<3.84]
    ratios=np.array([q[0] for q in res])
    Cb=res[best][3]
    lo,hi=min(ins),max(ins)
    Clo=[q[3] for q in res if q[0]==lo][0]; Chi=[q[3] for q in res if q[0]==hi][0]
    dv=Chi-Clo
    vert=np.dot(dv,up); 
    print(f"{im.name[12:60]:48s} n={n:3d} f_col={f0/m:.2f} k={k:+.3f} bbox={bb[0]:.2f}x{bb[1]:.2f} depthratio={np.percentile(d,95)/np.percentile(d,5):.2f} best={ratios[best]:.2f} rms={rms[best]:.2f}px 95%f=[{lo:.2f},{hi:.2f}] dC/rad={np.linalg.norm(dv)/rad:.2f} vertfrac={abs(vert)/max(np.linalg.norm(dv),1e-9):.2f} rms@0.4={rms[0]:.1f} rms@4={rms[-1]:.1f}")
