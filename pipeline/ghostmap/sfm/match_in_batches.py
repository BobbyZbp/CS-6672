#!/usr/bin/env python3
"""Finish LightGlue matching for a learned run in small, separate processes.

On this 7.6 GB machine hloc's matcher can grow until the kernel's
out-of-memory killer stops the run (this happened twice on the 228-photo
snapshot). Each batch of still-missing pairs is matched in its own short
process, so memory is returned after every batch; results go into the run's
own matches-lightglue.h5, which hloc reads and skips on the next normal run.
The matcher configuration is the run's own (SuperPoint + LightGlue).
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

BATCH = 60


def missing_pairs(run):
    import h5py
    pairs = [tuple(line.split()) for line in (run / 'pairs.txt').read_text().splitlines() if line.strip()]
    matches = run / 'matches-lightglue.h5'
    if not matches.exists(): return pairs
    with h5py.File(matches, 'r') as f:
        def stored(a, b):
            a, b = a.replace('/', '-'), b.replace('/', '-')
            return (a in f and b in f[a]) or (b in f and a in f[b])
        return [p for p in pairs if not stored(*p)]


def run(run_path, batch=BATCH):
    run_path = Path(run_path).resolve()
    import json
    config = json.loads((run_path / 'configuration.json').read_text())
    features = run_path / f"feats-superpoint-n{config['keypoints']}-r{config['resize']}.h5"
    todo = missing_pairs(run_path)
    print(len(todo), 'pairs left to match', flush=True)
    for start in range(0, len(todo), batch):
        with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False) as handle:
            handle.write(''.join(f'{a} {b}\n' for a, b in todo[start:start + batch]))
        code = ('from pathlib import Path; from hloc import match_features; '
                f"match_features.main(match_features.confs['superpoint+lightglue'], Path({handle.name!r}), "
                f"features=Path({str(features)!r}), matches=Path({str(run_path / 'matches-lightglue.h5')!r}))")
        subprocess.run([sys.executable, '-c', code], check=True)
        Path(handle.name).unlink()
        print('matched', min(start + batch, len(todo)), 'of', len(todo), flush=True)
    return len(missing_pairs(run_path))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--batch', type=int, default=BATCH)
    args = parser.parse_args()
    left = run(args.run, args.batch)
    print(left, 'pairs still missing'); raise SystemExit(0 if left == 0 else 1)


if __name__ == '__main__': main()
