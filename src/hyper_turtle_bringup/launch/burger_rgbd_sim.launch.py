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
    # Environment variables
    # Set GALLIUM_DRIVER to d3d12 if not already set, for WSL2 GPU acceleration
    set_gallium_driver = SetEnvironmentVariable('GALLIUM_DRIVER', 'd3d12')

    # Arguments
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    world = LaunchConfiguration('world')
    gazebo_gui = LaunchConfiguration('gazebo_gui', default='true')
    rviz = LaunchConfiguration('rviz', default='true')
    xbox_teleop = LaunchConfiguration('xbox_teleop', default='true')
    joy_device_id = LaunchConfiguration('joy_device_id', default='0')

    camera_x = LaunchConfiguration('camera_x', default='0.08')
    camera_y = LaunchConfiguration('camera_y', default='0.0')
    camera_z = LaunchConfiguration('camera_z', default='0.14')
    camera_roll = LaunchConfiguration('camera_roll', default='0.0')
    camera_pitch = LaunchConfiguration('camera_pitch', default='0.0')
    camera_yaw = LaunchConfiguration('camera_yaw', default='0.0')

    # Package directories
    pkg_hyper_turtle_description = get_package_share_directory('hyper_turtle_description')
    pkg_hyper_turtle_bringup = get_package_share_directory('hyper_turtle_bringup')
    pkg_hyper_turtle_control = get_package_share_directory('hyper_turtle_control')
    pkg_ros_gz_sim = get_package_share_directory('ros_gz_sim')
    pkg_turtlebot3_gazebo = get_package_share_directory('turtlebot3_gazebo')

    # Paths
    default_world_path = os.path.join(pkg_hyper_turtle_bringup, 'worlds', 'indoor_scan_test.sdf')
    model_sdf_path = os.path.join(
        pkg_hyper_turtle_description,
        'models',
        'hyper_turtle_burger_rgbd',
        'model.sdf'
    )
    urdf_path = os.path.join(pkg_hyper_turtle_description, 'urdf', 'burger_rgbd.urdf.xacro')
    bridges_path = os.path.join(pkg_hyper_turtle_bringup, 'config', 'bridges.yaml')
    rviz_path = os.path.join(pkg_hyper_turtle_description, 'rviz', 'burger_rgbd.rviz')

    add_turtlebot3_models = AppendEnvironmentVariable(
        'GZ_SIM_RESOURCE_PATH',
        os.path.join(pkg_turtlebot3_gazebo, 'models')
    )

    # Robot State Publisher
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='both',
        parameters=[{
            'use_sim_time': use_sim_time,
            'robot_description': ParameterValue(Command(['xacro ', urdf_path,
                                        ' camera_x:=', camera_x,
                                        ' camera_y:=', camera_y,
                                        ' camera_z:=', camera_z,
                                        ' camera_roll:=', camera_roll,
                                        ' camera_pitch:=', camera_pitch,
                                        ' camera_yaw:=', camera_yaw]), value_type=str)
        }]
    )

    # Gazebo Sim server
    gazebo_server = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_ros_gz_sim, 'launch', 'gz_sim.launch.py')
        ),
        launch_arguments={
            'gz_args': ['-r -s -v4 ', world],
            'on_exit_shutdown': 'true'
        }.items()
    )

    # Gazebo Sim GUI client
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

    # Spawn Robot in Gazebo
    spawn_entity = Node(
        package='ros_gz_sim',
        executable='create',
        output='screen',
        arguments=[
            '-file', model_sdf_path,
            '-name', 'hyper_turtle_burger_rgbd',
            '-z', '0.01'
        ]
    )

    # ROS-GZ Bridge
    ros_gz_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        parameters=[{
            'config_file': bridges_path,
            'use_sim_time': use_sim_time
        }],
        output='screen'
    )

    # Xbox gamepad teleop publishes /cmd_vel, which the ROS-GZ bridge forwards to Gazebo.
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
    
    # Optional image bridge if generic bridge is not sufficient for images (often better to use ros_gz_image)
    # But we try to map them via parameter_bridge first.

    # RViz
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
        DeclareLaunchArgument('use_sim_time', default_value='true', description='Use simulation (Gazebo) clock if true'),
        DeclareLaunchArgument('world', default_value=default_world_path, description='Gazebo World file'),
        DeclareLaunchArgument('gazebo_gui', default_value='true', description='Open Gazebo Sim GUI'),
        DeclareLaunchArgument('rviz', default_value='true', description='Open RViz'),
        DeclareLaunchArgument('xbox_teleop', default_value='true', description='Start Xbox gamepad teleop'),
        DeclareLaunchArgument('joy_device_id', default_value='0', description='Joystick ID from `ros2 run joy joy_enumerate_devices`'),
        DeclareLaunchArgument('camera_x', default_value='0.08', description='Camera X position relative to base_link'),
        DeclareLaunchArgument('camera_y', default_value='0.0', description='Camera Y position relative to base_link'),
        DeclareLaunchArgument('camera_z', default_value='0.14', description='Camera Z position relative to base_link'),
        DeclareLaunchArgument('camera_roll', default_value='0.0', description='Camera roll angle'),
        DeclareLaunchArgument('camera_pitch', default_value='0.0', description='Camera pitch angle'),
        DeclareLaunchArgument('camera_yaw', default_value='0.0', description='Camera yaw angle'),
        gazebo_server,
        gazebo_client,
        robot_state_publisher,
        spawn_entity,
        ros_gz_bridge,
        xbox_teleop_launch,
        rviz_node
    ])
