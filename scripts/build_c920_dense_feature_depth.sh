#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PYTHON_BIN="${PYTHON_BIN:-python3}"
COLMAP_ROOT="${COLMAP_ROOT:-outputs/colmap_sfm}"
OUTPUT_DIR="${OUTPUT_DIR:-outputs/c920_dense_feature_depth_now}"
WORK_WIDTH="${WORK_WIDTH:-426}"
GRID_STRIDE="${GRID_STRIDE:-3}"
VOXEL_SIZE="${VOXEL_SIZE:-0.12}"
MAX_POINTS_PER_COMPONENT="${MAX_POINTS_PER_COMPONENT:-90000}"

"$PYTHON_BIN" -m final_code.validation.c920_dense_feature_depth \
  --colmap-root "$COLMAP_ROOT" \
  --output "$OUTPUT_DIR" \
  --work-width "$WORK_WIDTH" \
  --grid-stride "$GRID_STRIDE" \
  --voxel-size "$VOXEL_SIZE" \
  --max-points-per-component "$MAX_POINTS_PER_COMPONENT"

echo
echo "Viewer:"
echo "  $OUTPUT_DIR/index.html"
echo "Report:"
echo "  $OUTPUT_DIR/report.json"
