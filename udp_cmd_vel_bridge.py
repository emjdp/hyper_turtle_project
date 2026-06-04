#!/usr/bin/env python3
"""UDP -> /cmd_vel bridge (robot side).

PC sends joystick packets (JSON {"axes": [...], "buttons": [...]}) over UDP.
This node receives them and publishes geometry_msgs/TwistStamped on /cmd_vel,
which TurtleBot3 (Jazzy) subscribes to.

Tune everything here in one place. All values can be overridden with env vars
so the launcher script does not need editing:

  UDP_PORT       listen port                         (default 9090)
  ENABLE_BUTTON  hold this button to allow motion     (default 7)
  TURBO_BUTTON   hold for turbo speeds                (default 4)
  LIN_AXIS       forward/back axis                    (default 1)
  ANG_AXIS       turn axis                            (default 3)
  LIN_SCALE / ANG_SCALE   normal max speeds           (default 0.15 / 0.8)
  LIN_TURBO / ANG_TURBO   turbo max speeds            (default 0.22 / 1.2)
  CMD_TIMEOUT    seconds without packets -> stop      (default 0.25)
"""

import json
import os
import socket
import time

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import TwistStamped


def _envf(name, default):
    return float(os.environ.get(name, default))


def _envi(name, default):
    return int(os.environ.get(name, default))


PORT = _envi("UDP_PORT", 9090)
ENABLE_BUTTON = _envi("ENABLE_BUTTON", 7)
TURBO_BUTTON = _envi("TURBO_BUTTON", 4)
LIN_AXIS = _envi("LIN_AXIS", 1)
ANG_AXIS = _envi("ANG_AXIS", 3)
LIN_SCALE = _envf("LIN_SCALE", 0.15)
ANG_SCALE = _envf("ANG_SCALE", 0.8)
LIN_TURBO = _envf("LIN_TURBO", 0.22)
ANG_TURBO = _envf("ANG_TURBO", 1.2)
TIMEOUT = _envf("CMD_TIMEOUT", 0.25)


class UdpJoyCmdStamped(Node):
    def __init__(self):
        super().__init__("udp_joy_cmd_bridge")
        self.pub = self.create_publisher(TwistStamped, "/cmd_vel", 10)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", PORT))
        self.sock.setblocking(False)
        self.axes = []
        self.buttons = []
        self.last = 0.0
        self.timer = self.create_timer(0.05, self.tick)
        self.get_logger().info(
            f"UDP joystick bridge listening on :{PORT}, publishing TwistStamped /cmd_vel"
        )

    def tick(self):
        while True:
            try:
                data, _ = self.sock.recvfrom(8192)
            except BlockingIOError:
                break
            try:
                packet = json.loads(data.decode("utf-8"))
                self.axes = [float(x) for x in packet.get("axes", [])]
                self.buttons = [int(x) for x in packet.get("buttons", [])]
                self.last = time.monotonic()
            except Exception as exc:
                self.get_logger().warn(f"bad UDP joystick packet: {exc}")

        msg = TwistStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        fresh = time.monotonic() - self.last <= TIMEOUT
        enabled = (
            fresh
            and len(self.buttons) > ENABLE_BUTTON
            and self.buttons[ENABLE_BUTTON] == 1
        )
        if enabled:
            turbo = len(self.buttons) > TURBO_BUTTON and self.buttons[TURBO_BUTTON] == 1
            lin_scale = LIN_TURBO if turbo else LIN_SCALE
            ang_scale = ANG_TURBO if turbo else ANG_SCALE
            if len(self.axes) > LIN_AXIS:
                msg.twist.linear.x = -self.axes[LIN_AXIS] * lin_scale
            if len(self.axes) > ANG_AXIS:
                msg.twist.angular.z = -self.axes[ANG_AXIS] * ang_scale
        self.pub.publish(msg)


def main():
    rclpy.init()
    node = UdpJoyCmdStamped()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
