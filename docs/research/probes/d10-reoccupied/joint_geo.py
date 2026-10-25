import sys, numpy as np, pycolmap, json
path=sys.argv[1]
r=pycolmap.Reconstruction(path)
imgs={i.image_id:i for i in r.images.values()}
pts=r.points3D
C={}; depths={}
for iid,im in imgs.items():
    c=im.projection_center(); C[iid]=c
    cw=im.cam_from_world() if callable(im.cam_from_world) else im.cam_from_world
    ds=[]
    for p2 in im.points2D:
        if p2.has_point3D():
            X=pts[p2.point3D_id].xyz
            ds.append((cw*X)[2])
    depths[iid]=np.array(ds)
allX=np.array([p.xyz for p in pts.values()])
med_depth=np.median(np.concatenate([d for d in depths.values() if len(d)]))
print('n_img',len(imgs),'n_pts',len(pts),'median depth (model units)',round(med_depth,3))
names={iid:im.name for iid,im in imgs.items()}
def is_hist(n): return n.startswith('hist') or 'historical' in n
H=[i for i in imgs if is_hist(names[i])]; M=[i for i in imgs if not is_hist(names[i])]
print('hist',len(H),'modern',len(M))
print('--- per image: name | f/maxdim | depth p10/p50/p90 | inv-depth spread (1/p10-1/p90)*med | nearest modern centre dist / med_depth')
for i in sorted(imgs,key=lambda k:names[k]):
    im=imgs[i]; cam=r.cameras[im.camera_id]
    f=cam.params[0]/max(cam.width,cam.height)
    d=depths[i]
    if len(d)<5: continue
    p10,p50,p90=np.percentile(d,[10,50,90])
    spread=(1/p10-1/p90)*med_depth
    others=[j for j in M if j!=i]
    nn=min(np.linalg.norm(C[i]-C[j]) for j in others)/med_depth
    print(f"{names[i][:60]:60s} f={f:5.2f} d={p10/med_depth:.2f}/{p50/med_depth:.2f}/{p90/med_depth:.2f} invspread={spread:.2f} nnModern={nn:.3f} nobs={len(d)}")
