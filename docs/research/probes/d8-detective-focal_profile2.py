import sys, numpy as np, pycolmap, cv2
rec = pycolmap.Reconstruction(sys.argv[1])
sel = sys.argv[2] if len(sys.argv) > 2 else 'historical'
MODERN = len(sys.argv) > 3
for iid, im in sorted(rec.images.items(), key=lambda x: x[1].name):
    if sel not in im.name: continue
    cam = rec.cameras[im.camera_id]
    f0, cx, cy, k = cam.params[:4]
    uv = []; X = []
    for p in im.points2D:
        if p.has_point3D():
            P = rec.points3D[p.point3D_id]
            names = [rec.images[e.image_id].name for e in P.track.elements]
            if MODERN and not any(n.startswith('modern') for n in names): continue
            uv.append(p.xy); X.append(P.xyz)
    uv = np.array(uv); X = np.array(X)
    W, H = cam.width, cam.height
    bb = (np.ptp(uv[:,0])*np.ptp(uv[:,1]))/(W*H)
    # camera-frame depths
    T = im.cam_from_world() if callable(getattr(im,'cam_from_world',None)) else im.cam_from_world
    Xc = (T.rotation.matrix() @ X.T).T + T.translation
    z = Xc[:,2]
    C = -T.rotation.matrix().T @ T.translation
    # scene radius proxy: distance of camera to points median
    d = np.linalg.norm(X - C, axis=1)
    # undistort observed pixels with fitted model to isolate pinhole focal profile
    xn = (uv - [cx, cy]) / f0
    # simple radial undistort by fixed point
    xu = xn.copy()
    for _ in range(20):
        r2 = (xu**2).sum(1, keepdims=True); xu = xn / (1 + k*r2)
    res = []
    for s in [0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.25, 1.5, 1.8]:
        f = f0*s
        K = np.array([[f,0,cx],[0,f,cy],[0,0,1.]])
        pix = xu*f0 + [cx, cy]  # pinhole pixels at f0; re-express in pixel units
        ok, rv, tv, inl = cv2.solvePnPRansac(X.astype(np.float64), pix.astype(np.float64), K, None, reprojectionError=8.0, iterationsCount=2000, flags=cv2.SOLVEPNP_SQPNP)
        if not ok: res.append((s, None)); continue
        ok, rv, tv = cv2.solvePnP(X, pix, K, None, rv, tv, True, flags=cv2.SOLVEPNP_ITERATIVE)
        pr, _ = cv2.projectPoints(X, rv, tv, K, None)
        e = np.linalg.norm(pr.reshape(-1,2)-pix, axis=1)
        R, _ = cv2.Rodrigues(rv); Cs = (-R.T @ tv).ravel()
        res.append((s, round(float(np.median(e)),2), round(float(np.mean(e<4)),2), round(float(np.linalg.norm(Cs-C)/np.median(d)),3)))
    print(im.name[:70], 'n=%d bbox_frac=%.3f depth_spread(p90/p10)=%.2f f/maxdim=%.2f k=%.2f' % (len(X), bb, np.percentile(z,90)/max(np.percentile(z,10),1e-6), f0/max(W,H), k))
    for r in res: print('   f_scale,median_px,frac<4px,centre_shift/median_range', r)
