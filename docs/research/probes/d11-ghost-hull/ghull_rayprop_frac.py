# Read-only: propagate anchor-only resection covariance (Fisher, pp fixed) to ray displacement at hist-only points
import sys, numpy as np, pycolmap
FRAC=float(sys.argv[2])
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
    if 'Boardman' not in im.name: continue
    cam=r.cameras[im.camera_id]; f0,cx0,cy0,k=cam.params
    A=[];xa=[];H=[];xh=[]
    for p in im.points2D:
        if not p.has_point3D(): continue
        ids=set(e.image_id for e in r.points3D[p.point3D_id].track.elements)
        (A if ids&modern else H).append(r.points3D[p.point3D_id].xyz); (xa if ids&modern else xh).append(p.xy)
    A=np.array(A); xa=np.array(xa); H=np.array(H); xh=np.array(xh)
    R0=im.cam_from_world().rotation.matrix(); C0=im.projection_center()
    def params(th): return rodr(th[:3])@R0, C0+th[3:6], f0*np.exp(th[6])
    def proj(th,P):
        R,C,f=params(th); Xc=(R@(P-C).T).T; u=Xc[:,:2]/Xc[:,2:3]; r2=(u**2).sum(1,keepdims=True)
        return (f*u*(1+k*r2)+[cx0,cy0]).ravel()
    e=proj(np.zeros(7),A)-xa.ravel(); sig=np.sqrt(np.mean(e**2)); h=1e-6
    J=np.zeros((len(e),7))
    for j in range(7):
        d=np.zeros(7); d[j]=h; J[:,j]=(proj(d,A)-proj(-d,A))/(2*h)
    Cov=np.linalg.inv(J.T@J)*sig**2
    if len(H)==0: continue
    # ray point at the true depth of each hist-only point, for its observed pixel (undistortion ignored: use pinhole of observed px)
    depth=np.full(len(H), FRAC*np.median(((R0@(A-C0).T).T)[:,2]))
    def raypts(th):
        R,C,f=params(th); u=(xh-[cx0,cy0])/f; d=np.c_[u,np.ones(len(u))]
        return C+ (R.T@(d*depth[:,None]).T).T
    G=np.zeros((H.size,7))
    for j in range(7):
        d=np.zeros(7); d[j]=h; G[:,j]=((raypts(d)-raypts(-d))/(2*h)).ravel()
    S=G@Cov@G.T
    sds=[]
    for i in range(len(H)):
        Si=S[3*i:3*i+3,3*i:3*i+3]; ray=(H[i]-C0)/np.linalg.norm(H[i]-C0)
        Pp=np.eye(3)-np.outer(ray,ray); sds.append(np.sqrt(np.trace(Pp@Si@Pp)))
    sds=np.array(sds)
    print(f"{im.name[12:52]:42s} anchors={len(A):3d} hist-only pts={len(H):3d} median depth={np.median(depth):.2f}u  perp-ray 1sd at those pts: p50={np.median(sds):.3f}u p90={np.percentile(sds,90):.3f}u")
