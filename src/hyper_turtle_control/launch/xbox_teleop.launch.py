import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue

def generate_launch_description():
    pkg_hyper_turtle_control = get_package_share_directory('hyper_turtle_control')
    
    cmd_vel_topic = LaunchConfiguration('cmd_vel_topic', default='/cmd_vel')
    joy_device_id = LaunchConfiguration('joy_device_id', default='0')
    config_filepath = os.path.join(pkg_hyper_turtle_control, 'config', 'xbox_teleop.yaml')

    joy_node = Node(
        package='joy',
        executable='joy_node',
        name='joy_node',
        parameters=[{
            'device_id': ParameterValue(joy_device_id, value_type=int),
            'deadzone': 0.05,
            'autorepeat_rate': 20.0,
        }]
    )

    teleop_twist_joy_node = Node(
        package='teleop_twist_joy',
        executable='teleop_node',
        name='teleop_twist_joy_node',
        parameters=[config_filepath],
        remappings={('/cmd_vel', cmd_vel_topic)}
    )

    return LaunchDescription([
        DeclareLaunchArgument('cmd_vel_topic', default_value='/cmd_vel', description='Target cmd_vel topic'),
        DeclareLaunchArgument('joy_device_id', default_value='0', description='Joystick device ID from joy_enumerate_devices'),
        joy_node,
        teleop_twist_joy_node
    ])
