#!/usr/bin/env python3
"""Install official OpenMVS binaries and a private Ubuntu runtime locally."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import urllib.request
import zipfile

from ghostmap.paths import ROOT
DEST = ROOT / 'third_party/openmvs-bin'
RUNTIME = ROOT / 'third_party/openmvs-runtime'
TOOLS = ['InterfaceCOLMAP', 'DensifyPointCloud', 'ReconstructMesh', 'RefineMesh', 'TextureMesh']
DOWNLOADS = {
    'openmvs.zip': 'https://github.com/cdcseacave/openMVS/releases/download/v2.4.0/OpenMVS_Ubuntu_x64.zip',
    'libc6.deb': 'https://archive.ubuntu.com/ubuntu/pool/main/g/glibc/libc6_2.39-0ubuntu8_amd64.deb',
    'libstdc.deb': 'https://archive.ubuntu.com/ubuntu/pool/main/g/gcc-14/libstdc++6_14-20240412-0ubuntu1_amd64.deb',
}


def main():
    cache = ROOT / 'artifacts/tool-cache'
    cache.mkdir(parents=True, exist_ok=True)
    DEST.mkdir(parents=True, exist_ok=True)
    provenance = {}
    for name, url in DOWNLOADS.items():
        path = cache / name
        if not path.exists():
            print('Downloading', name, flush=True)
            req = urllib.request.Request(url, headers={'User-Agent': 'GhostMap/0.2'})
            part = path.with_suffix(path.suffix + '.part')
            with urllib.request.urlopen(req, timeout=180) as response, part.open('wb') as out:
                shutil.copyfileobj(response, out)
            part.replace(path)
        provenance[name] = {'url': url, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    with zipfile.ZipFile(cache / 'openmvs.zip') as archive:
        for tool in TOOLS:
            with archive.open(tool) as source, (DEST / tool).open('wb') as out:
                shutil.copyfileobj(source, out)
            os.chmod(DEST / tool, 0o755)
    for name in ['libc6.deb', 'libstdc.deb']:
        subprocess.run(['dpkg-deb', '-x', str(cache / name), str(RUNTIME)], check=True)
    (DEST / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    print('OpenMVS v2.4.0 ready; system libraries unchanged.')


if __name__ == '__main__':
    main()
