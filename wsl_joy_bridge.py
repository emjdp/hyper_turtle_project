#!/usr/bin/env python3

import json
import socket
import threading
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy

PORT = 9090
PUBLISH_HZ = 30

class WslJoyBridge(Node):
    def __init__(self):
        super().__init__("wsl_joy_bridge")
        self.pub = self.create_publisher(Joy, "joy", 10)

        self.latest_axes = []
        self.latest_buttons = []
        self.lock = threading.Lock()

        self.timer = self.create_timer(1.0 / PUBLISH_HZ, self.publish_latest)

        self.thread = threading.Thread(target=self.udp_loop, daemon=True)
        self.thread.start()

        self.get_logger().info(f"Listening UDP on 0.0.0.0:{PORT}, publishing /joy at {PUBLISH_HZ} Hz")

    def udp_loop(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind(("0.0.0.0", PORT))
        except Exception as e:
            self.get_logger().error(f"UDP Bind failed: {e}")
            return

        while rclpy.ok():
            try:
                data, _ = sock.recvfrom(4096)
                packet = json.loads(data.decode("utf-8"))

                axes = packet.get("axes", [])
                buttons = packet.get("buttons", [])

                if not isinstance(axes, list):
                    axes = []
                if not isinstance(buttons, list):
                    buttons = []

                axes = [float(x) for x in axes]
                buttons = [int(x) for x in buttons]

                with self.lock:
                    self.latest_axes = axes
                    self.latest_buttons = buttons

            except Exception as e:
                # 무수히 많은 경고 로그를 막기 위해 조용히 무시 (또는 필요시만 출력)
                pass

    def publish_latest(self):
        with self.lock:
            axes = list(self.latest_axes)
            buttons = list(self.latest_buttons)
            
        # 데이터가 없으면 퍼블리시 생략
        if not axes and not buttons:
            return

        msg = Joy()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'joy'
        msg.axes = axes
        msg.buttons = buttons
        self.pub.publish(msg)

def main():
    rclpy.init()
    node = WslJoyBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()
