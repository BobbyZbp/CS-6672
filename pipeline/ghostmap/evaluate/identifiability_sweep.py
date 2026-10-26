#!/usr/bin/env python3
"""Identifiability curves on the synthetic hall: which cues fix which degrees of freedom, and when they cannot.

Sweeps the facades that carry points (one, two adjacent, two parallel, three), the lidar roof-edge error, the
camera-height noise and the cue set, fitting the unified estimator each time and recording the scale ratio,
the yaw error, the photographers' position error and the certificate's verdict. The paper's identifiability
figure is drawn from `artifacts/georegistration/identifiability.json`.

Usage: PYTHONPATH=pipeline python -m ghostmap.evaluate.identifiability_sweep [--quick]
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from ghostmap.anchor.georegister import WEIGHTS, fit_arrays
from ghostmap.evaluate.synthetic import hall, score
from ghostmap.paths import ROOT

OUTPUT = ROOT / 'artifacts/georegistration/identifiability.json'
FACADES = {'one facade': ('south',), 'two adjacent facades': ('south', 'east'), 'two parallel facades': ('south', 'north'), 'three facades': ('south', 'east', 'west')}


def sweep(quick=False, seeds=(0, 1, 2)):
    rows = []
    roof_errors = [0.0, 1.5, 3.0] if not quick else [0.0, 3.0]
    height_noise = [0.0, 0.3] if not quick else [0.0]
    cue_sets = {'all cues': list(WEIGHTS), 'without roof edges': [c for c in WEIGHTS if c != 'roof_edges'], 'without walls': [c for c in WEIGHTS if c != 'walls'],
                'walls and roof edges only': ['walls', 'roof_edges']}
    if quick: cue_sets = {k: cue_sets[k] for k in ('all cues', 'without roof edges')}
    for facade_name, facades in FACADES.items():
        for roof in roof_errors:
            for noise in height_noise:
                for cue_name, cues in cue_sets.items():
                    for seed in (seeds[:1] if quick else seeds):
                        d = hall(seed=seed, facades=facades, roof_edge_error_m=roof, camera_height_noise_m=noise)
                        t0 = time.time()
                        report, sim = fit_arrays(d['points'], d['centres'], d['rotations'], 'Hall', d['buildings'], d['rasters'], d['observations'],
                                                 cues=cues, yaw_step_deg=6.0, scale_steps=11)
                        row = {'facades': facade_name, 'roof_edge_error_m': roof, 'camera_height_noise_m': noise, 'cues': cue_name, 'seed': seed,
                               'seconds': round(time.time() - t0, 1), **score(report, sim, d['truth']), 'gravity': report['gravity']['from']}
                        rows.append(row); print(json.dumps(row), flush=True)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--quick', action='store_true', help='fewer settings, one seed')
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    rows = sweep(args.quick)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({'created_utc': datetime.now(timezone.utc).isoformat(), 'quick': args.quick, 'rows': rows}, indent=1) + '\n')
    print('wrote', args.output, len(rows), 'fits')


if __name__ == '__main__': main()
