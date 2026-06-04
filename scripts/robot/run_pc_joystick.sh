#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/robot/run_pc_joystick.sh [turtlebot_ip] [joy_device_id]

Runs everything needed on the laptop side:
- local ROS joy_node reads the Xbox controller
- local UDP sender forwards /joy packets to the TurtleBot UDP bridge

If turtlebot_ip is omitted, it is resolved from the ssh alias in ROBOT_SSH
(default: rpi5), so you only edit the IP in one place (setup_rpi_ssh.sh).
UDP needs the real IP, not the alias, which is why we resolve it.

Controls:
- hold button 7 to enable motion
- left stick vertical: forward/back
- right stick horizontal: turn
- LB/button 4: turbo, handled on the TurtleBot side
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

ROBOT_SSH="${ROBOT_SSH:-rpi5}"
ROBOT_IP="${1:-}"
if [[ -z "$ROBOT_IP" ]]; then
  ROBOT_IP="$(ssh -G "$ROBOT_SSH" 2>/dev/null | awk '/^hostname /{print $2; exit}')"
fi
if [[ -z "$ROBOT_IP" ]]; then
  echo "[pc] could not resolve robot IP from ssh alias '$ROBOT_SSH'." >&2
  echo "[pc] pass it explicitly: scripts/robot/run_pc_joystick.sh <turtlebot_ip>" >&2
  exit 1
fi
JOY_DEVICE_ID="${2:-0}"
UDP_PORT="${UDP_PORT:-9090}"
ROS_LOCAL_DOMAIN="${ROS_LOCAL_DOMAIN:-77}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "$PROJECT_ROOT"

set +u
source /opt/ros/jazzy/setup.bash
set -u
export ROS_LOCALHOST_ONLY=1
export ROS_DOMAIN_ID="$ROS_LOCAL_DOMAIN"

JOY_PID=""
cleanup() {
  echo ""
  echo "[pc] stopping joystick processes..."
  if [[ -n "$JOY_PID" ]] && kill -0 "$JOY_PID" 2>/dev/null; then
    kill "$JOY_PID" 2>/dev/null || true
    wait "$JOY_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "[pc] target TurtleBot: ${ROBOT_IP}:${UDP_PORT}"
echo "[pc] starting joy_node, device_id=${JOY_DEVICE_ID}"
ros2 run joy joy_node --ros-args \
  -p device_id:="$JOY_DEVICE_ID" \
  -p deadzone:=0.05 \
  -p autorepeat_rate:=20.0 &
JOY_PID=$!

sleep 1

echo "[pc] starting UDP sender. Press Ctrl+C here when done."
python3 -u - <<PY_SENDER
import json
import socket
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy

TARGET = "${ROBOT_IP}"
PORT = int("${UDP_PORT}")

class JoyUdpSender(Node):
    def __init__(self):
        super().__init__("joy_udp_sender")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sub = self.create_subscription(Joy, "/joy", self.cb, 10)
        self.count = 0
        self.get_logger().info(f"Sending /joy UDP to {TARGET}:{PORT}")

    def cb(self, msg):
        packet = {"axes": list(msg.axes), "buttons": list(msg.buttons)}
        self.sock.sendto(json.dumps(packet).encode("utf-8"), (TARGET, PORT))
        self.count += 1
        if self.count % 50 == 0:
            self.get_logger().info(f"sent {self.count} joy packets")

rclpy.init()
node = JoyUdpSender()
try:
    rclpy.spin(node)
finally:
    node.destroy_node()
    rclpy.shutdown()
PY_SENDER
