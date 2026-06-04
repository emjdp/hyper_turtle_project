#!/usr/bin/env bash
# robot_record.sh
# Records the standard topic set into a rosbag ON THE ROBOT, over SSH.
#
# Reliability: this opens ONE remote process (exec ros2 bag record) on an SSH
# PTY. Pressing Ctrl+C here sends SIGINT straight to that recorder, so the bag
# is finalized cleanly. No background PIDs, traps, or pkill that could corrupt
# the bag or kill an already-running bringup.
#
# Prerequisite: bringup (and the UDP bridge, if you want to drive) must already
# be running on the robot:
#   ./robot_bringup.sh        # terminal A
#   ./robot_cmd_bridge.sh     # terminal B (only needed to drive via joystick)
#   ./robot_record.sh         # terminal C  <-- this script
#
# Usage:
#   ./robot_record.sh [bag_prefix]
# Examples:
#   ./robot_record.sh
#   ./robot_record.sh free_run
set -euo pipefail

# ── Edit here if your robot changes ─────────────────────────────────────────
ROBOT_SSH="${ROBOT_SSH:-rpi5}"            # ssh alias (see setup_rpi_ssh.sh) or user@ip
ROS_DOMAIN="${ROS_DOMAIN:-30}"
TB3_MODEL="${TB3_MODEL:-burger}"
LDS="${LDS:-LDS-01}"
REMOTE_DIR="${REMOTE_DIR:-~/hyper_turtle_project}"
# ────────────────────────────────────────────────────────────────────────────

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  grep '^#' "$0" | sed 's/^# \{0,1\}//'
  exit 0
fi

BAG_PREFIX="${1:-building_scan}"

TOPICS="/scan /odom /tf /tf_static /joint_states /cmd_vel /imu /battery_state /sensor_state /magnetic_field /camera_c920/image_raw/compressed /camera_c920/camera_info /camera_c270/image_raw/compressed /camera_c270/camera_info"

read -r -d '' REMOTE <<EOF || true
set -e
cd ${REMOTE_DIR}
mkdir -p bags
export ROS_DOMAIN_ID=${ROS_DOMAIN}
export TURTLEBOT3_MODEL=${TB3_MODEL}
export LDS_MODEL=${LDS}
source /opt/ros/jazzy/setup.bash
source ~/turtlebot3_ws/install/setup.bash
source install/setup.bash

# Preflight: tell us which requested topics are live (bringup must be up).
present="\$(ros2 topic list 2>/dev/null || true)"
missing=""
for t in ${TOPICS}; do
  echo "\$present" | grep -qx "\$t" || missing="\$missing \$t"
done
if [ -n "\$missing" ]; then
  echo "[robot] WARNING not live yet:\$missing"
  echo "[robot] is bringup running? Recording starts anyway and captures them once they appear."
else
  echo "[robot] all requested topics are live."
fi

STAMP="\$(date +%Y%m%d_%H%M%S)"
BAG_DIR="bags/${BAG_PREFIX}_\$STAMP"
echo "\$BAG_DIR" > .last_bag
echo "[robot] recording to \$BAG_DIR  (Ctrl+C to stop cleanly)"
exec ros2 bag record -o "\$BAG_DIR" --topics ${TOPICS}
EOF

echo "[pc] ssh target : ${ROBOT_SSH}"
echo "[pc] bag prefix : ${BAG_PREFIX}"
echo "[pc] Press Ctrl+C to stop recording. Then: ./fetch_turtlebot_bag.sh"
exec ssh -t "${ROBOT_SSH}" "${REMOTE}"
