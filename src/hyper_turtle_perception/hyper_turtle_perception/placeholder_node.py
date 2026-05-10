import rclpy
from rclpy.node import Node

class PlaceholderNode(Node):
    def __init__(self):
        super().__init__('placeholder_node')
        self.get_logger().info('Perception Placeholder Node started.')
        self.get_logger().info('TODO: Implement Graffiti Detection here.')

def main(args=None):
    rclpy.init(args=args)
    node = PlaceholderNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
