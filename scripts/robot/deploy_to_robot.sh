#!/usr/bin/env bash
# deploy_to_robot.sh
# Syncs only the files the robot actually needs:
#   udp_cmd_vel_bridge.py  — joystick UDP bridge (runs on robot)
#   src/                   — ROS packages (built on robot with colcon)
#
# Uses the same ROBOT_SSH alias as the other scripts (default: rpi5).
# To change the target: ROBOT_SSH=ubuntu@192.168.1.10 scripts/robot/deploy_to_robot.sh
set -euo pipefail

ROBOT_SSH="${ROBOT_SSH:-rpi5}"
REMOTE_DIR="${REMOTE_DIR:-~/hyper_turtle_project}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

echo "[deploy] target : ${ROBOT_SSH}:${REMOTE_DIR}"

rsync -avz --progress \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    "${SCRIPT_DIR}/udp_cmd_vel_bridge.py" \
    "${ROBOT_SSH}:${REMOTE_DIR}/"

rsync -avz --progress \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    "${PROJECT_ROOT}/src/" \
    "${ROBOT_SSH}:${REMOTE_DIR}/src/"

echo "[deploy] done. rebuild on robot if src/ changed:"
echo "  ssh ${ROBOT_SSH} 'cd ${REMOTE_DIR} && source /opt/ros/jazzy/setup.bash && source ~/turtlebot3_ws/install/setup.bash && colcon build --symlink-install --packages-up-to hyper_turtle_bringup'"
