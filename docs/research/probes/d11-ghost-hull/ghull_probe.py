import pycolmap, numpy as np, sys
rec = pycolmap.Reconstruction(sys.argv[1])
imgs = {im.image_id: im for im in rec.images.values()}
era = {i: ('historical' if im.name.startswith('historical') else 'modern') for i, im in imgs.items()}
pt_eras = {}
for pid, p in rec.points3D.items():
    s = set(era[e.image_id] for e in p.track.elements)
    pt_eras[pid] = s
def center(im):
    try: return np.array(im.projection_center())
    except Exception: return np.array(im.cam_from_world().inverse().translation)
B = [i for i, im in imgs.items() if 'Boardman' in im.name]
for i in sorted(B, key=lambda k: imgs[k].name):
    im = imgs[i]; cam = rec.cameras[im.camera_id]
    obs = [p2 for p2 in im.points2D if p2.has_point3D()]
    cross = [p2 for p2 in obs if 'modern' in pt_eras[p2.point3D_id]]
    xs = np.array([p2.xy for p2 in cross]) if cross else np.zeros((0,2))
    span = (xs.max(0)-xs.min(0)) if len(xs) else None
    f = cam.params[0]; md = max(cam.width, cam.height)
    print(im.name[12:60], 'model', cam.model_name if hasattr(cam,'model_name') else cam.model, 'f/maxdim %.2f' % (f/md), 'WxH', cam.width, cam.height,
          'obs', len(obs), 'cross-era obs', len(cross), 'cross bbox px', None if span is None else span.round(0), 'C', center(im).round(2))
# scene scale: modern camera spread
Cm = np.array([center(im) for i, im in imgs.items() if era[i]=='modern'])
Ch = np.array([center(imgs[i]) for i in B])
print('modern cam centroid', Cm.mean(0).round(2), 'modern cam spread (std)', Cm.std(0).round(2))
# historical-only points observed by >=2 Boardman imgs
P = np.array([rec.points3D[pid].xyz for pid,s in pt_eras.items() if s=={'historical'} and sum(1 for e in rec.points3D[pid].track.elements if e.image_id in B)>=2])
Q = np.array([rec.points3D[pid].xyz for pid,s in pt_eras.items() if 'modern' in s])
print('hist-only>=2B pts', len(P), 'centroid', P.mean(0).round(2), 'cross pts', len(Q), 'centroid', Q.mean(0).round(2))
c = P.mean(0)
# up direction: approx via PCA of modern camera centers? use average camera y-axis (image down) instead
ups = []
for i, im in imgs.items():
    R = np.array(im.cam_from_world().rotation.matrix()); ups.append(-R[1])
up = np.mean(ups, 0); up /= np.linalg.norm(up); print('approx up', up.round(3))
def az(v):
    v = v - up*np.dot(v, up); return v
ref = az(Q.mean(0)-c); ref/=np.linalg.norm(ref); ortho = np.cross(up, ref)
for i in sorted(B, key=lambda k: imgs[k].name):
    v = az(center(imgs[i]) - c)
    a = np.degrees(np.arctan2(np.dot(v, ortho), np.dot(v, ref)))
    print('%-50s azimuth about hist-only centroid (rel. cross-pt dir) %7.1f deg, dist %.2f' % (imgs[i].name[12:60], a, np.linalg.norm(v)))
print('dist cross-centroid to hist centroid', np.linalg.norm(az(Q.mean(0)-c)).round(2))
