#!/usr/bin/env python3
"""Check measured surface provenance and references before web publication."""
import json
import re
from pathlib import Path
import numpy as np
from plyfile import PlyData

ROOT=Path(__file__).resolve().parents[1]


def main():
    count=0
    for name in ['cpu_mvs_target_fixed08_v2','cpu_mvs_target_fixed_v2','cpu_mvs_modern_v2','cpu_mvs_archive_target_v2','cpu_mvs_modern_full_v2','cpu_mvs_masked08_v3','cpu_mvs_masked12_v3']:
        work=ROOT/'artifacts'/name
        obj=work/'supported.obj'
        if not obj.exists():continue
        data=PlyData.read(work/'dense.ply')['vertex'].data
        raw=np.column_stack([data[k] for k in ['x','y','z']])
        vertices=[];faces=[];uv=[]
        for line in obj.read_text().splitlines():
            if line.startswith('v '):vertices.append([float(x) for x in line.split()[1:]])
            elif line.startswith('vt '):uv.append([float(x) for x in line.split()[1:]])
            elif line.startswith('f '):faces.append([int(x.split('/')[0])-1 for x in line.split()[1:]])
        vertices=np.array(vertices);faces=np.array(faces);uv=np.array(uv)
        assert vertices.shape==raw.shape and np.allclose(vertices,raw,rtol=1e-6,atol=1e-7),'mesh contains non-stereo vertices'
        assert np.isfinite(vertices).all() and np.isfinite(uv).all()
        assert faces.min()>=0 and faces.max()<len(vertices)
        assert ((uv>=-1e-5)&(uv<=1+1e-5)).all(),'texture extrapolates outside a photograph'
        used=np.unique(faces)
        assert min(len(data['view_indices'][i]) for i in used)>=3
        for f in faces:
            assert len(set(data['view_indices'][f[0]]) & set(data['view_indices'][f[1]]) & set(data['view_indices'][f[2]]))>=2
        for line in (work/'supported.mtl').read_text().splitlines():
            if line.startswith('map_Kd '):assert (work/line.split(' ',1)[1]).exists()
        result={'status':'artifact_invariants_passed','stereo_vertices':len(raw),'supported_faces':len(faces),
                'used_stereo_vertices':len(used),'metric_accuracy_validated':False,
                'checked':['exact stereo vertex provenance','finite coordinates','valid indices','in-image UVs','three-view vertex support','two-view shared facet support','source textures present']}
        log=(work/'ReconstructMesh.log').read_text()
        loaded=re.search(r"Point-cloud 'dense.ply' loaded: (\d+) points",log)
        assert loaded and int(loaded[1])==len(raw),'native mesher did not load the dense cloud'
        result['native_mesher_input_points']=int(loaded[1])
        result['checked'].append('native mesher consumed the complete dense cloud')
        projected=work/'projected.obj'
        if projected.exists():
            native=PlyData.read(work/'surface.ply')
            native_xyz=np.column_stack([native['vertex'][k] for k in ['x','y','z']])
            exported=np.array([[float(v) for v in line.split()[1:]] for line in projected.read_text().splitlines() if line.startswith('v ')])
            assert exported.shape==native_xyz.shape and np.allclose(exported,native_xyz,rtol=1e-6,atol=1e-7)
            metadata=json.loads((work/'projected-texture-report.json').read_text())
            assert metadata['geometry_modified'] is False
            assert metadata['mesh_faces']==len(native['face'].data)
            result['checked'].append('camera texturing preserves native mesh geometry')
        exposure=work/'exposure-supported.obj'
        if exposure.exists():
            lines=exposure.read_text().splitlines()
            exxyz=np.array([[float(v) for v in line.split()[1:]] for line in lines if line.startswith('v ')])
            exuv=np.array([[float(v) for v in line.split()[1:]] for line in lines if line.startswith('vt ')])
            exfaces=np.array([[int(v.split('/')[0])-1 for v in line.split()[1:]] for line in lines if line.startswith('f ')])
            assert exxyz.shape==raw.shape and np.allclose(exxyz,raw,rtol=1e-6,atol=1e-7)
            assert np.isfinite(exxyz).all() and np.isfinite(exuv).all()
            assert exfaces.min()>=0 and exfaces.max()<len(raw)
            assert ((exuv>=-1e-5)&(exuv<=1+1e-5)).all()
            import pycolmap
            audit=json.loads((ROOT/'artifacts/exposure-audit.json').read_text())
            groups={n:i for i,g in enumerate(audit['candidate_groups']) for n in g}
            cameras=pycolmap.Reconstruction(str(work/'export-cameras/sparse'))
            index=[groups.get(Path(im.name).name,Path(im.name).name) for _,im in sorted(cameras.images.items())]
            support=[{index[int(i)] for i in v} for v in data['view_indices']]
            assert min(len(support[i]) for i in np.unique(exfaces))>=3
            for f in exfaces:assert len(support[f[0]]&support[f[1]]&support[f[2]])>=2
            for line in (work/'exposure-supported.mtl').read_text().splitlines():
                if line.startswith('map_Kd '):assert (work/line.split(' ',1)[1]).exists()
            result['exposure_screened_faces']=len(exfaces)
            result['checked'].append('screened facets preserve stereo vertices and require three candidate exposure groups per vertex and two per facet')
        (work/'artifact-validation.json').write_text(json.dumps(result,indent=2)+'\n')
        print(name,json.dumps(result));count+=1
    assert count>=3,'missing repair experiment'


if __name__=='__main__':main()
