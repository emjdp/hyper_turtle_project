#!/usr/bin/env bash
# robot_bringup.sh
# Starts the robot bringup (LDS + OpenCR + two cameras) ON THE ROBOT, over SSH.
# Keep this terminal open while you work; Ctrl+C stops bringup cleanly.
#
# Usage:
#   ./robot_bringup.sh
#
# Optional: to enable PC<->robot DDS discovery set PC_STATIC_PEER to your PC IP.
# It is NOT needed for the joystick (UDP) or for on-robot bag recording.
#   PC_STATIC_PEER=172.21.5.40 ./robot_bringup.sh
set -euo pipefail

# ── Edit here if your robot changes ─────────────────────────────────────────
ROBOT_SSH="${ROBOT_SSH:-rpi5}"            # ssh alias (see setup_rpi_ssh.sh) or user@ip
ROS_DOMAIN="${ROS_DOMAIN:-30}"
TB3_MODEL="${TB3_MODEL:-burger}"
LDS="${LDS:-LDS-01}"
REMOTE_DIR="${REMOTE_DIR:-~/hyper_turtle_project}"
PC_STATIC_PEER="${PC_STATIC_PEER:-}"      # optional PC IP for DDS discovery
# ────────────────────────────────────────────────────────────────────────────

read -r -d '' REMOTE <<EOF || true
set -e
cd ${REMOTE_DIR}
export ROS_DOMAIN_ID=${ROS_DOMAIN}
export TURTLEBOT3_MODEL=${TB3_MODEL}
export LDS_MODEL=${LDS}
$( [ -n "$PC_STATIC_PEER" ] && echo "export ROS_STATIC_PEERS=${PC_STATIC_PEER}" )
source /opt/ros/jazzy/setup.bash
source ~/turtlebot3_ws/install/setup.bash
source install/setup.bash
echo "[robot] launching burger_real bringup (Ctrl+C to stop)"
exec ros2 launch hyper_turtle_bringup burger_real.launch.py
EOF

echo "[pc] ssh target : ${ROBOT_SSH}"
echo "[pc] starting bringup. Keep this terminal open; Ctrl+C to stop."
exec ssh -t "${ROBOT_SSH}" "${REMOTE}"
