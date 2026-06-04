#!/usr/bin/env bash
# robot_cmd_bridge.sh
# Starts the UDP -> /cmd_vel bridge ON THE ROBOT, over SSH. The PC joystick
# sender (run_pc_joystick.sh) sends UDP packets here; this publishes
# TwistStamped /cmd_vel so the TurtleBot moves. Ctrl+C stops it.
#
# The bridge logic and tuning live in udp_cmd_vel_bridge.py (one place to edit).
# Make sure that file is on the robot first:  ./deploy_to_robot.sh
#
# Usage:
#   ./robot_cmd_bridge.sh
set -euo pipefail

# ── Edit here if your robot changes ─────────────────────────────────────────
ROBOT_SSH="${ROBOT_SSH:-rpi5}"            # ssh alias (see setup_rpi_ssh.sh) or user@ip
ROS_DOMAIN="${ROS_DOMAIN:-30}"
TB3_MODEL="${TB3_MODEL:-burger}"
LDS="${LDS:-LDS-01}"
REMOTE_DIR="${REMOTE_DIR:-~/hyper_turtle_project}"
UDP_PORT="${UDP_PORT:-9090}"
# ────────────────────────────────────────────────────────────────────────────

read -r -d '' REMOTE <<EOF || true
set -e
cd ${REMOTE_DIR}
export ROS_DOMAIN_ID=${ROS_DOMAIN}
export TURTLEBOT3_MODEL=${TB3_MODEL}
export LDS_MODEL=${LDS}
export UDP_PORT=${UDP_PORT}
source /opt/ros/jazzy/setup.bash
source ~/turtlebot3_ws/install/setup.bash
source install/setup.bash
echo "[robot] UDP -> /cmd_vel bridge on :${UDP_PORT} (Ctrl+C to stop)"
exec python3 -u udp_cmd_vel_bridge.py
EOF

echo "[pc] ssh target : ${ROBOT_SSH}"
echo "[pc] starting UDP bridge on :${UDP_PORT}. Ctrl+C to stop."
exec ssh -t "${ROBOT_SSH}" "${REMOTE}"
