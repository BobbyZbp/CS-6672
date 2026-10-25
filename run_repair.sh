#!/usr/bin/env bash
set -euo pipefail
GHOSTMAP_PYTHON="${GHOSTMAP_PYTHON:-.venv/bin/python}"

if [ ! -f third_party/openmvs-bin/DensifyPointCloud ]; then
  "$GHOSTMAP_PYTHON" pipeline/setup_openmvs.py
fi

# Consumes the acquired public image set and preserves all v1 artifacts.
"$GHOSTMAP_PYTHON" pipeline/run_target_sfm.py --fixed-focal --focal-factor 0.8
"$GHOSTMAP_PYTHON" pipeline/run_target_sfm.py --fixed-focal --focal-factor 1.2
"$GHOSTMAP_PYTHON" pipeline/run_target_sfm.py --fixed-focal --focal-factor 1.8
"$GHOSTMAP_PYTHON" pipeline/run_cpu_mvs.py --model artifacts/target_sfm_v2/sfm_fixed_focal_0.8 --workspace artifacts/cpu_mvs_target_fixed08_v2
"$GHOSTMAP_PYTHON" pipeline/run_cpu_mvs.py --model artifacts/target_sfm_v2/sfm_fixed_focal_1.2 --workspace artifacts/cpu_mvs_target_fixed_v2
"$GHOSTMAP_PYTHON" pipeline/run_cpu_mvs.py --model artifacts/hloc_cross_era/sfm_joint --workspace artifacts/cpu_mvs_modern_v2 --era modern
"$GHOSTMAP_PYTHON" pipeline/run_cpu_mvs.py --model artifacts/hloc_cross_era/sfm_joint --workspace artifacts/cpu_mvs_modern_full_v2 --era modern --resolution-level 0

for GHOSTMAP_RUN in cpu_mvs_target_fixed08_v2 cpu_mvs_target_fixed_v2 cpu_mvs_modern_v2 cpu_mvs_modern_full_v2; do
  "$GHOSTMAP_PYTHON" pipeline/mesh_supported_patches.py --workspace "artifacts/$GHOSTMAP_RUN"
  "$GHOSTMAP_PYTHON" pipeline/texture_from_cameras.py --workspace "artifacts/$GHOSTMAP_RUN"
  MPLCONFIGDIR=/tmp/ghostmap-mpl "$GHOSTMAP_PYTHON" pipeline/inspect_surface.py --workspace "artifacts/$GHOSTMAP_RUN" --basename supported
  MPLCONFIGDIR=/tmp/ghostmap-mpl "$GHOSTMAP_PYTHON" pipeline/inspect_surface.py --workspace "artifacts/$GHOSTMAP_RUN"
done
"$GHOSTMAP_PYTHON" pipeline/measure_focal_sensitivity.py
"$GHOSTMAP_PYTHON" pipeline/validate_repair.py
if [ "${1:-}" = '--archives' ]; then
  "$GHOSTMAP_PYTHON" pipeline/download_cornell_archive.py
  "$GHOSTMAP_PYTHON" pipeline/run_target_sfm.py --workspace artifacts/archive_target_v2 --images artifacts/archive_target_v2/images_exterior --fixed-focal --focal-factor 0.8
  "$GHOSTMAP_PYTHON" pipeline/run_cpu_mvs.py --model artifacts/archive_target_v2/sfm_fixed_focal_0.8 --images artifacts/archive_target_v2/images_exterior --workspace artifacts/cpu_mvs_archive_target_v2
  "$GHOSTMAP_PYTHON" pipeline/mesh_supported_patches.py --workspace artifacts/cpu_mvs_archive_target_v2
  "$GHOSTMAP_PYTHON" pipeline/texture_from_cameras.py --workspace artifacts/cpu_mvs_archive_target_v2
  MPLCONFIGDIR=/tmp/ghostmap-mpl "$GHOSTMAP_PYTHON" pipeline/inspect_surface.py --workspace artifacts/cpu_mvs_archive_target_v2 --basename supported
  MPLCONFIGDIR=/tmp/ghostmap-mpl "$GHOSTMAP_PYTHON" pipeline/inspect_surface.py --workspace artifacts/cpu_mvs_archive_target_v2
  "$GHOSTMAP_PYTHON" pipeline/validate_repair.py
fi
if [ "${1:-}" = '--masked' ]; then
  "$GHOSTMAP_PYTHON" pipeline/download_cornell_archive.py
  "$GHOSTMAP_PYTHON" pipeline/run_target_sfm.py --workspace artifacts/archive_target_v2 --images artifacts/archive_target_v2/images_exterior --fixed-focal --focal-factor 0.8
  HF_HOME=/home/bobby/CS6672/.cache/huggingface HF_HUB_DISABLE_XET=1 "$GHOSTMAP_PYTHON" pipeline/run_masked_target.py
  for GHOSTMAP_FOCAL in 0.8 1.2; do
    if [ "$GHOSTMAP_FOCAL" = 0.8 ]; then GHOSTMAP_MASK_RUN=cpu_mvs_masked08_v3; else GHOSTMAP_MASK_RUN=cpu_mvs_masked12_v3; fi
    "$GHOSTMAP_PYTHON" pipeline/run_cpu_mvs.py --model "artifacts/masked_target_v3/sfm_focal_$GHOSTMAP_FOCAL" --images artifacts/archive_target_v2/images_exterior --workspace "artifacts/$GHOSTMAP_MASK_RUN" --masks artifacts/masked_target_v3/masks --resolution-level 0 --max-resolution 1600
    "$GHOSTMAP_PYTHON" pipeline/mesh_supported_patches.py --workspace "artifacts/$GHOSTMAP_MASK_RUN"
    "$GHOSTMAP_PYTHON" pipeline/texture_from_cameras.py --workspace "artifacts/$GHOSTMAP_MASK_RUN"
    MPLCONFIGDIR=/tmp/ghostmap-mpl "$GHOSTMAP_PYTHON" pipeline/inspect_surface.py --workspace "artifacts/$GHOSTMAP_MASK_RUN"
    MPLCONFIGDIR=/tmp/ghostmap-mpl "$GHOSTMAP_PYTHON" pipeline/inspect_surface.py --workspace "artifacts/$GHOSTMAP_MASK_RUN" --basename supported
  done
  "$GHOSTMAP_PYTHON" pipeline/measure_focal_sensitivity.py --workspace artifacts/masked_target_v3 --prefix sfm_focal_
  "$GHOSTMAP_PYTHON" pipeline/audit_exposure_groups.py
  for GHOSTMAP_MASK_RUN in cpu_mvs_masked08_v3 cpu_mvs_masked12_v3; do
    "$GHOSTMAP_PYTHON" pipeline/mesh_supported_patches.py --workspace "artifacts/$GHOSTMAP_MASK_RUN" --exposure-audit artifacts/exposure-audit.json --output-basename exposure-supported
    MPLCONFIGDIR=/tmp/ghostmap-mpl "$GHOSTMAP_PYTHON" pipeline/inspect_surface.py --workspace "artifacts/$GHOSTMAP_MASK_RUN" --basename exposure-supported
  done
  "$GHOSTMAP_PYTHON" pipeline/validate_repair.py
fi
"$GHOSTMAP_PYTHON" pipeline/build_repair_site.py
