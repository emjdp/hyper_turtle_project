#!/usr/bin/env bash
# fetch_turtlebot_bag.sh
# Pulls a bag from the robot to ./bags/ and verifies it with ros2 bag info.
# If no bag name is given, uses ~/hyper_turtle_project/.last_bag (written by
# robot_record.sh), falling back to the newest bag directory.
#
# Usage:
#   ./fetch_turtlebot_bag.sh [bag_dir_or_name]
# Examples:
#   ./fetch_turtlebot_bag.sh
#   ./fetch_turtlebot_bag.sh building_scan_20260531_123456
set -euo pipefail

# ── Edit here if your robot changes ─────────────────────────────────────────
ROBOT_SSH="${ROBOT_SSH:-rpi5}"            # ssh alias (see setup_rpi_ssh.sh) or user@ip
REMOTE_DIR="${REMOTE_DIR:-~/hyper_turtle_project}"
# ────────────────────────────────────────────────────────────────────────────

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  grep '^#' "$0" | sed 's/^# \{0,1\}//'
  exit 0
fi

BAG_ARG="${1:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
mkdir -p bags

if [[ -z "$BAG_ARG" ]]; then
  REMOTE_BAG="$(ssh -o StrictHostKeyChecking=accept-new "$ROBOT_SSH" \
    "cd ${REMOTE_DIR} && if [[ -s .last_bag ]]; then cat .last_bag; else ls -td bags/* 2>/dev/null | head -1; fi")"
elif [[ "$BAG_ARG" == bags/* ]]; then
  REMOTE_BAG="$BAG_ARG"
else
  REMOTE_BAG="bags/$BAG_ARG"
fi

if [[ -z "$REMOTE_BAG" ]]; then
  echo "[fetch] no bag found on robot" >&2
  exit 1
fi

LOCAL_BAG="bags/$(basename "$REMOTE_BAG")"

echo "[fetch] robot      : $ROBOT_SSH"
echo "[fetch] remote bag : ${REMOTE_DIR}/$REMOTE_BAG"
echo "[fetch] local bag  : $LOCAL_BAG"

rsync -avz --progress -e "ssh -o StrictHostKeyChecking=accept-new" \
  "$ROBOT_SSH:${REMOTE_DIR}/$REMOTE_BAG" ./bags/

set +u
source /opt/ros/jazzy/setup.bash
set -u
echo "[fetch] verifying local bag..."
ros2 bag info "$LOCAL_BAG"
