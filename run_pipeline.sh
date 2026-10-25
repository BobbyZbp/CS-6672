#!/usr/bin/env bash
set -euo pipefail

PYTHON="${PYTHON:-.venv/bin/python}"

"$PYTHON" pipeline/download_commons.py
"$PYTHON" pipeline/legacy/v1/run_sfm.py "$@"
"$PYTHON" pipeline/legacy/v1/validate_artifacts.py
"$PYTHON" pipeline/legacy/v1/run_hloc_cross_era.py

# Exit code 1 means the scientific gate rejected the model, not that execution
# crashed.  Preserve the negative result and continue building the audit page.
set +e
"$PYTHON" pipeline/legacy/v1/run_hloc_joint.py
JOINT_STATUS=$?
set -e
if [ "$JOINT_STATUS" -gt 1 ]; then
  exit "$JOINT_STATUS"
fi

"$PYTHON" pipeline/legacy/v1/export_hloc_viewer.py
set +e
"$PYTHON" pipeline/legacy/v1/check_dense_mvs.py \
  --model artifacts/hloc_cross_era/sfm_joint \
  --images artifacts/work/joint/images \
  --workspace artifacts/experiments/dense_hloc_joint_cuda_check
DENSE_STATUS=$?
set -e
if [ "$DENSE_STATUS" -ne 0 ] && [ "$DENSE_STATUS" -ne 2 ]; then
  exit "$DENSE_STATUS"
fi

"$PYTHON" pipeline/legacy/v1/build_site_data.py


