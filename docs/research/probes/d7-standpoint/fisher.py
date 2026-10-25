import sys, numpy as np, pycolmap
r=pycolmap.Reconstruction(sys.argv[1])
modern=set(i for i,im in r.images.items() if im.name.startswith('modern'))
X=np.array([r.images[i].cam_from_world().rotation.matrix()[0] for i in r.images]); up=np.linalg.svd(X)[2][-1]
allxyz=np.array([p.xyz for p in r.points3D.values()]); rad=np.median(np.linalg.norm(allxyz-np.median(allxyz,0),axis=1))
def rodr(w):
    th=np.linalg.norm(w)
    if th<1e-12: return np.eye(3)
    k=w/th; K=np.array([[0,-k[2],k[1]],[k[2],0,-k[0]],[-k[1],k[0],0]])
    return np.eye(3)+np.sin(th)*K+(1-np.cos(th))*K@K
for iid,im in sorted(r.images.items(), key=lambda x:x[1].name):
    if 'Boardman' not in im.name and '154792750' not in im.name: continue
    cam=r.cameras[im.camera_id]; f0,cx0,cy0,k=cam.params
    P=[];x=[]
    for p in im.points2D:
        if p.has_point3D() and set(e.image_id for e in r.points3D[p.point3D_id].track.elements)&modern:
            P.append(r.points3D[p.point3D_id].xyz); x.append(p.xy)
    P=np.array(P); x=np.array(x)
    R0=im.cam_from_world().rotation.matrix(); C0=im.projection_center()
    def proj(th):
        R=rodr(th[:3])@R0; C=C0+th[3:6]; f=f0*np.exp(th[6]); cx=cx0+th[7]; cy=cy0+th[8]
        Xc=(R@(P-C).T).T; u=Xc[:,:2]/Xc[:,2:3]; r2=(u**2).sum(1,keepdims=True)
        return (f*u*(1+k*r2)+[cx,cy]).ravel()
    th0=np.zeros(9); e=proj(th0)-x.ravel(); sig=np.sqrt(np.mean(e**2))
    J=np.zeros((len(e),9)); h=1e-6
    for j in range(9):
        d=np.zeros(9); d[j]=h; J[:,j]=(proj(d)-proj(-d))/(2*h)
    out=[]
    for free_pp in (False,True):
        idx=list(range(7))+([7,8] if free_pp else [])
        Jr=J[:,idx]; Cov=np.linalg.inv(Jr.T@Jr)*sig**2
        sf=np.sqrt(Cov[6,6])   # log f std
        z=R0[2]; sC=np.sqrt(z@Cov[3:6,3:6]@z)
        out.append((sf,sC/rad))
    # null direction
    Jr=J; s,V=np.linalg.svd(Jr/np.linalg.norm(Jr,axis=0),full_matrices=False)[1:]
    print(f"{im.name[12:55]:44s} n={len(P):3d} sig={sig:.2f}px  pp-fixed: sd(logf)={out[0][0]:.3f} sd(C_axis)={out[0][1]:.2f}rad | pp-free: sd(logf)={out[1][0]:.3f} sd(C_axis)={out[1][1]:.2f}rad  cond={s[0]/s[-1]:.0f}")
