#!/usr/bin/env python3
"""Recompute diagnostics from completed native checkpoints without editing geometry."""
import argparse
import json
from pathlib import Path

from run_artsquad_sfm import saved_component_reports, select_training_images, sha256, write_json


def inspect(run):
    run = Path(run).resolve(); report_path = run / 'report.json'
    report = json.loads(report_path.read_text())
    if not (run / 'sfm/mapping-complete.json').is_file():
        raise ValueError('Mapper completion marker missing; interrupted geometry is not automatically promoted')
    snapshot_path = Path(report['snapshot_path'])
    if sha256(snapshot_path) != report['configuration']['snapshot_sha256']: raise ValueError('Frozen snapshot changed')
    snapshot = json.loads(snapshot_path.read_text())
    records = select_training_images(snapshot, report['configuration'].get('targets', []))
    if {r['filename'] for r in records} != set(report['input_images']): raise ValueError('Frozen training selection differs')
    for row in records:
        if sha256(row['working_path']) != row['sha256_working']: raise ValueError('Frozen image changed')
    binaries = list((run / 'sfm/models').glob('*/*.bin'))
    before = {str(path): sha256(path) for path in binaries}
    old_digest = sha256(report_path)
    write_json(run / 'report-history' / (old_digest + '.json'), report)
    report['components'] = saved_component_reports(run / 'sfm/models', records)
    if any(sha256(Path(name)) != digest for name, digest in before.items()): raise RuntimeError('Native model changed during inspection')
    report['status'] = 'sfm_complete' if report['components'] else 'no_model'
    report['component_identity'] = 'Native saved directory ID, not API ReconstructionManager key'
    report['diagnostic_reinspection'] = {'previous_report_sha256': old_digest, 'native_geometry_unchanged': True,
                                       'reason': 'Verify saved component path, camera names and counts; no model alignment or geometry modification.'}
    registered = {c['name'] for component in report['components'] for c in component['cameras']}
    report['unregistered_images'] = sorted(set(report['input_images']) - registered)
    write_json(report_path, report)
    return report_path


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--run', type=Path, required=True)
    print(inspect(parser.parse_args().run))


if __name__ == '__main__': main()
