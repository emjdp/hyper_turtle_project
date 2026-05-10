import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

def generate_launch_description():
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    pkg_hyper_turtle_mapping = get_package_share_directory('hyper_turtle_mapping')
    
    slam_config_file = os.path.join(pkg_hyper_turtle_mapping, 'config', 'slam_toolbox.yaml')

    start_async_slam_toolbox_node = Node(
        parameters=[
          slam_config_file,
          {'use_sim_time': use_sim_time}
        ],
        package='slam_toolbox',
        executable='async_slam_toolbox_node',
        name='slam_toolbox',
        output='screen'
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='true',
            description='Use simulation (Gazebo) clock if true'),
        start_async_slam_toolbox_node
    ])
