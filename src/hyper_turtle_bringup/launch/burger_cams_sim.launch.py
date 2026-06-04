import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import AppendEnvironmentVariable, DeclareLaunchArgument, IncludeLaunchDescription, SetEnvironmentVariable
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, Command
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    set_gallium_driver = SetEnvironmentVariable('GALLIUM_DRIVER', 'd3d12')

    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    world = LaunchConfiguration('world')
    gazebo_gui = LaunchConfiguration('gazebo_gui', default='true')
    rviz = LaunchConfiguration('rviz', default='true')
    xbox_teleop = LaunchConfiguration('xbox_teleop', default='true')
    joy_device_id = LaunchConfiguration('joy_device_id', default='0')

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

    pkg_hyper_turtle_description = get_package_share_directory('hyper_turtle_description')
    pkg_hyper_turtle_bringup = get_package_share_directory('hyper_turtle_bringup')
    pkg_hyper_turtle_control = get_package_share_directory('hyper_turtle_control')
    pkg_ros_gz_sim = get_package_share_directory('ros_gz_sim')
    pkg_turtlebot3_gazebo = get_package_share_directory('turtlebot3_gazebo')

    default_world_path = os.path.join(pkg_hyper_turtle_bringup, 'worlds', 'indoor_scan_test.sdf')
    model_sdf_path = os.path.join(
        pkg_hyper_turtle_description,
        'models',
        'hyper_turtle_burger_cams',
        'model.sdf'
    )
    urdf_path = os.path.join(pkg_hyper_turtle_description, 'urdf', 'burger_cams.urdf.xacro')
    bridges_path = os.path.join(pkg_hyper_turtle_bringup, 'config', 'bridges.yaml')
    rviz_path = os.path.join(pkg_hyper_turtle_description, 'rviz', 'burger_cams.rviz')

    add_turtlebot3_models = AppendEnvironmentVariable(
        'GZ_SIM_RESOURCE_PATH',
        os.path.join(pkg_turtlebot3_gazebo, 'models')
    )

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
            ]), value_type=str)
        }]
    )

    gazebo_server = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_ros_gz_sim, 'launch', 'gz_sim.launch.py')
        ),
        launch_arguments={
            'gz_args': ['-r -s -v4 ', world],
            'on_exit_shutdown': 'true'
        }.items()
    )

    gazebo_client = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_ros_gz_sim, 'launch', 'gz_sim.launch.py')
        ),
        launch_arguments={
            'gz_args': '-g -v4 ',
            'on_exit_shutdown': 'true'
        }.items(),
        condition=IfCondition(gazebo_gui)
    )

    spawn_entity = Node(
        package='ros_gz_sim',
        executable='create',
        output='screen',
        arguments=[
            '-file', model_sdf_path,
            '-name', 'hyper_turtle_burger_cams',
            '-z', '0.01'
        ]
    )

    # parameter_bridge: clock, odom, tf, scan, imu, joint_states, cmd_vel, camera_info
    ros_gz_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        parameters=[{
            'config_file': bridges_path,
            'use_sim_time': use_sim_time
        }],
        output='screen'
    )

    # image_bridge for raw images uses image_transport, which auto-publishes
    # the compressed transport => /<topic>/compressed (JPEG) is created for free.
    image_bridge = Node(
        package='ros_gz_image',
        executable='image_bridge',
        name='image_bridge',
        arguments=[
            '/camera_c920/image_raw',
            '/camera_c270/image_raw',
        ],
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}],
    )

    xbox_teleop_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_hyper_turtle_control, 'launch', 'xbox_teleop.launch.py')
        ),
        launch_arguments={
            'cmd_vel_topic': '/cmd_vel',
            'joy_device_id': joy_device_id,
        }.items(),
        condition=IfCondition(xbox_teleop)
    )

    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        arguments=['-d', rviz_path],
        parameters=[{'use_sim_time': use_sim_time}],
        condition=IfCondition(rviz)
    )

    return LaunchDescription([
        set_gallium_driver,
        add_turtlebot3_models,
        DeclareLaunchArgument('use_sim_time', default_value='true'),
        DeclareLaunchArgument('world', default_value=default_world_path),
        DeclareLaunchArgument('gazebo_gui', default_value='true'),
        DeclareLaunchArgument('rviz', default_value='true'),
        DeclareLaunchArgument('xbox_teleop', default_value='true'),
        DeclareLaunchArgument('joy_device_id', default_value='0'),
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
        gazebo_server,
        gazebo_client,
        robot_state_publisher,
        spawn_entity,
        ros_gz_bridge,
        image_bridge,
        xbox_teleop_launch,
        rviz_node,
    ])
