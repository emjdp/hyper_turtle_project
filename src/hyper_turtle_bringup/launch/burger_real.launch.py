"""Real TurtleBot3 Burger launch with two Logitech webcams + LDS-01.

Composition:
- Includes turtlebot3_bringup robot.launch.py — provides robot_state_publisher (with TB3 URDF),
  turtlebot3_node (OpenCR: /odom, /imu, /joint_states, /tf), and the LDS driver (/scan).
  We do NOT replicate those nodes ourselves because turtlebot3_node needs ~10 static parameters
  that the standard launch loads from share/turtlebot3_bringup/param/<model>.yaml.
- Adds 4 static_transform_publisher nodes for the camera frames, since the stock TB3 URDF
  doesn't include them.
- usb_cam x 2 (C920, C270) with our yamls.
- TimerAction(+5s): v4l2-ctl to enforce brightness/gain/exposure_dynamic_framerate.

Bag-recording topics: /camera_c{920,270}/image_raw/compressed, /camera_c{920,270}/camera_info,
                     /scan, /odom, /tf, /tf_static

Camera mount poses are exposed as launch arguments; defaults match the sim model.
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    IncludeLaunchDescription,
    TimerAction,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    use_sim_time = LaunchConfiguration('use_sim_time', default='false')

    c920_x = LaunchConfiguration('c920_x', default='0.075')
    c920_y = LaunchConfiguration('c920_y', default='0.0')
    c920_z = LaunchConfiguration('c920_z', default='0.135')
    c920_roll = LaunchConfiguration('c920_roll', default='0.0')
    c920_pitch = LaunchConfiguration('c920_pitch', default='0.0')
    c920_yaw = LaunchConfiguration('c920_yaw', default='0.0')

    c270_x = LaunchConfiguration('c270_x', default='0.060')
    c270_y = LaunchConfiguration('c270_y', default='0.035')
    c270_z = LaunchConfiguration('c270_z', default='0.135')
    c270_roll = LaunchConfiguration('c270_roll', default='0.0')
    c270_pitch = LaunchConfiguration('c270_pitch', default='0.0')
    c270_yaw = LaunchConfiguration('c270_yaw', default='0.0')

    pkg_bringup = get_package_share_directory('hyper_turtle_bringup')
    pkg_tb3_bringup = get_package_share_directory('turtlebot3_bringup')

    usb_cam_c920_yaml = os.path.join(pkg_bringup, 'config', 'usb_cam_c920.yaml')
    usb_cam_c270_yaml = os.path.join(pkg_bringup, 'config', 'usb_cam_c270.yaml')
    tb3_robot_launch = os.path.join(pkg_tb3_bringup, 'launch', 'robot.launch.py')

    tb3_bringup = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(tb3_robot_launch),
        launch_arguments={'use_sim_time': use_sim_time}.items(),
    )

    # ROS optical convention rotation: rpy(-pi/2, 0, -pi/2) = (-1.5707963, 0, -1.5707963)
    optical_rpy = ['--roll', '-1.5707963', '--pitch', '0', '--yaw', '-1.5707963']

    stp_c920_link = Node(
        package='tf2_ros', executable='static_transform_publisher',
        name='stp_camera_c920_link',
        arguments=[
            '--x', c920_x, '--y', c920_y, '--z', c920_z,
            '--roll', c920_roll, '--pitch', c920_pitch, '--yaw', c920_yaw,
            '--frame-id', 'base_link', '--child-frame-id', 'camera_c920_link',
        ],
        parameters=[{'use_sim_time': use_sim_time}],
    )
    stp_c920_optical = Node(
        package='tf2_ros', executable='static_transform_publisher',
        name='stp_camera_c920_optical',
        arguments=[
            '--x', '0', '--y', '0', '--z', '0', *optical_rpy,
            '--frame-id', 'camera_c920_link',
            '--child-frame-id', 'camera_c920_optical_frame',
        ],
        parameters=[{'use_sim_time': use_sim_time}],
    )
    stp_c270_link = Node(
        package='tf2_ros', executable='static_transform_publisher',
        name='stp_camera_c270_link',
        arguments=[
            '--x', c270_x, '--y', c270_y, '--z', c270_z,
            '--roll', c270_roll, '--pitch', c270_pitch, '--yaw', c270_yaw,
            '--frame-id', 'base_link', '--child-frame-id', 'camera_c270_link',
        ],
        parameters=[{'use_sim_time': use_sim_time}],
    )
    stp_c270_optical = Node(
        package='tf2_ros', executable='static_transform_publisher',
        name='stp_camera_c270_optical',
        arguments=[
            '--x', '0', '--y', '0', '--z', '0', *optical_rpy,
            '--frame-id', 'camera_c270_link',
            '--child-frame-id', 'camera_c270_optical_frame',
        ],
        parameters=[{'use_sim_time': use_sim_time}],
    )

    usb_cam_c920 = Node(
        package='usb_cam',
        executable='usb_cam_node_exe',
        name='usb_cam',
        namespace='camera_c920',
        parameters=[usb_cam_c920_yaml, {'use_sim_time': use_sim_time}],
        output='screen',
    )

    usb_cam_c270 = Node(
        package='usb_cam',
        executable='usb_cam_node_exe',
        name='usb_cam',
        namespace='camera_c270',
        parameters=[usb_cam_c270_yaml, {'use_sim_time': use_sim_time}],
        output='screen',
    )

    # Enforce v4l2 controls that usb_cam parameters can't set reliably on modern kernels.
    v4l2_normalize = TimerAction(
        period=5.0,
        actions=[
            ExecuteProcess(
                cmd=['v4l2-ctl', '-d', '/dev/video0',
                     '-c', 'brightness=128',
                     '-c', 'gain=0',
                     '-c', 'exposure_dynamic_framerate=0'],
                output='screen',
            ),
            ExecuteProcess(
                cmd=['v4l2-ctl', '-d', '/dev/video2',
                     '-c', 'brightness=128',
                     '-c', 'gain=0',
                     '-c', 'exposure_dynamic_framerate=0'],
                output='screen',
            ),
        ],
    )

    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        DeclareLaunchArgument('c920_x', default_value='0.075'),
        DeclareLaunchArgument('c920_y', default_value='0.0'),
        DeclareLaunchArgument('c920_z', default_value='0.135'),
        DeclareLaunchArgument('c920_roll', default_value='0.0'),
        DeclareLaunchArgument('c920_pitch', default_value='0.0'),
        DeclareLaunchArgument('c920_yaw', default_value='0.0'),
        DeclareLaunchArgument('c270_x', default_value='0.060'),
        DeclareLaunchArgument('c270_y', default_value='0.035'),
        DeclareLaunchArgument('c270_z', default_value='0.135'),
        DeclareLaunchArgument('c270_roll', default_value='0.0'),
        DeclareLaunchArgument('c270_pitch', default_value='0.0'),
        DeclareLaunchArgument('c270_yaw', default_value='0.0'),
        tb3_bringup,
        stp_c920_link,
        stp_c920_optical,
        stp_c270_link,
        stp_c270_optical,
        usb_cam_c920,
        usb_cam_c270,
        v4l2_normalize,
    ])
