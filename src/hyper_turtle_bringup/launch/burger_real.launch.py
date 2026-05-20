"""Real TurtleBot3 Burger launch with two Logitech webcams + LDS-01.

Runs on the SBC. Composition:
- robot_state_publisher with our burger_cams.urdf.xacro (publishes /tf_static for all frames,
  including camera_c920/c270 _link and _optical_frame). The Burger base + LDS frames also
  come from this URDF, so we don't include turtlebot3_bringup's robot_state_publisher.
- turtlebot3_node (OpenCR driver — /odom, /joint_states, /tf base->odom, /imu)
- hlds_laser_publisher (LDS-01 driver — /scan)
- usb_cam x 2 (C920, C270) — /camera_c*/image_raw, /image_raw/compressed, /camera_info
- v4l2-ctl normalization triggered 5s after start (brightness/gain/exposure_dynamic_framerate)

Topics for bag recording:
  /camera_c920/image_raw/compressed
  /camera_c920/camera_info
  /camera_c270/image_raw/compressed
  /camera_c270/camera_info
  /scan
  /odom
  /tf
  /tf_static
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    TimerAction,
)
from launch.substitutions import LaunchConfiguration, Command
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


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
    c270_yaw = LaunchConfiguration('c270_yaw', default='0.7853981634')

    pkg_description = get_package_share_directory('hyper_turtle_description')
    pkg_bringup = get_package_share_directory('hyper_turtle_bringup')

    urdf_path = os.path.join(pkg_description, 'urdf', 'burger_cams.urdf.xacro')
    usb_cam_c920_yaml = os.path.join(pkg_bringup, 'config', 'usb_cam_c920.yaml')
    usb_cam_c270_yaml = os.path.join(pkg_bringup, 'config', 'usb_cam_c270.yaml')

    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='both',
        parameters=[{
            'use_sim_time': use_sim_time,
            'robot_description': ParameterValue(Command([
                'xacro ', urdf_path,
                ' c920_x:=', c920_x,
                ' c920_y:=', c920_y,
                ' c920_z:=', c920_z,
                ' c920_roll:=', c920_roll,
                ' c920_pitch:=', c920_pitch,
                ' c920_yaw:=', c920_yaw,
                ' c270_x:=', c270_x,
                ' c270_y:=', c270_y,
                ' c270_z:=', c270_z,
                ' c270_roll:=', c270_roll,
                ' c270_pitch:=', c270_pitch,
                ' c270_yaw:=', c270_yaw,
            ]), value_type=str),
        }],
    )

    # TurtleBot3 OpenCR driver: /odom, /joint_states, /imu, /tf (odom->base_footprint), motor cmd
    turtlebot3_node = Node(
        package='turtlebot3_node',
        executable='turtlebot3_ros',
        name='turtlebot3_node',
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}],
    )

    # LDS-01 driver: /scan
    hlds_laser = Node(
        package='hls_lfcd_lds_driver',
        executable='hlds_laser_publisher',
        name='hlds_laser_publisher',
        output='screen',
        parameters=[{
            'port': '/dev/ttyUSB0',
            'frame_id': 'base_scan',
        }],
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

    # Apply v4l2 controls that usb_cam parameters can't set reliably.
    # Run a few seconds after start so the cameras are fully opened.
    v4l2_normalize = TimerAction(
        period=5.0,
        actions=[
            ExecuteProcess(
                cmd=['v4l2-ctl', '-d', '/dev/video2',
                     '-c', 'brightness=128',
                     '-c', 'gain=0',
                     '-c', 'exposure_dynamic_framerate=0'],
                output='screen',
            ),
            ExecuteProcess(
                cmd=['v4l2-ctl', '-d', '/dev/video0',
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
        DeclareLaunchArgument('c270_yaw', default_value='0.7853981634'),
        robot_state_publisher,
        turtlebot3_node,
        hlds_laser,
        usb_cam_c920,
        usb_cam_c270,
        v4l2_normalize,
    ])
