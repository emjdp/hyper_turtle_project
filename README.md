# Hyper Turtle Project

TurtleBot3 Burger 기반 건물 스캔 및 그래피티 탐지 로봇 프로젝트입니다.
현재 1차 목표로 **시뮬레이션 기반 Xbox 게임패드 수동 조종 및 매핑** 파이프라인이 구축되어 있습니다.

## 작업 환경 및 의존성

- OS: Windows 11 + WSL2 Ubuntu 24.04
- ROS: ROS 2 Jazzy
- 시뮬레이터: Gazebo Sim
- 하드웨어 가속: WSL OpenGL GPU 가속 (GALLIUM_DRIVER=d3d12)

### 필요 패키지 설치
만약 관련 ROS 2 패키지가 설치되어 있지 않다면 아래 명령을 통해 설치하세요:

```bash
sudo apt update
sudo apt install \
  ros-jazzy-turtlebot3 \
  ros-jazzy-turtlebot3-gazebo \
  ros-jazzy-turtlebot3-simulations \
  ros-jazzy-turtlebot3-teleop \
  ros-jazzy-ros-gz \
  ros-jazzy-ros-gz-bridge \
  ros-jazzy-ros-gz-sim \
  ros-jazzy-ros-gz-image \
  ros-jazzy-slam-toolbox \
  ros-jazzy-navigation2 \
  ros-jazzy-nav2-bringup \
  ros-jazzy-nav2-map-server \
  ros-jazzy-tf2-tools \
  ros-jazzy-rviz2 \
  ros-jazzy-joy \
  ros-jazzy-teleop-twist-joy
```

---

## 빌드 명령

프로젝트 루트 디렉터리에서 다음 명령을 실행하여 워크스페이스를 빌드합니다.

```bash
cd /home/emjdp/hyper_Turtle_Project
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
```

빌드 성공 후 패키지 인식 확인:
```bash
source install/setup.bash
ros2 pkg list | grep hyper_turtle
```

---

## 매뉴얼 스캔 Workflow

다음은 터미널을 여러 개 열고 순차적으로 실행하여 수동으로 맵을 스캔하는 절차입니다.

**터미널 1: 시뮬레이션 실행**
```bash
cd /home/emjdp/hyper_Turtle_Project
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 launch hyper_turtle_bringup burger_rgbd_sim.launch.py
```

**터미널 2: Xbox 게임패드 teleop 실행**
```bash
cd /home/emjdp/hyper_Turtle_Project
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 launch hyper_turtle_control xbox_teleop.launch.py
```

**터미널 3: SLAM 실행**
```bash
cd /home/emjdp/hyper_Turtle_Project
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 launch hyper_turtle_mapping slam.launch.py use_sim_time:=true
```

**터미널 4: rosbag 데이터 저장**
수동 주행 중 맵 좌표, 센서 데이터, 게임패드 입력 등을 모두 기록합니다.
```bash
cd /home/emjdp/hyper_Turtle_Project
source /opt/ros/jazzy/setup.bash
source install/setup.bash
mkdir -p bags

ros2 bag record -o bags/manual_scan_1f_test_$(date +%Y%m%d_%H%M%S) \
  /scan \
  /odom \
  /tf \
  /tf_static \
  /joint_states \
  /joy \
  /cmd_vel \
  /camera/color/image_raw \
  /camera/color/camera_info \
  /camera/depth/image_raw \
  /camera/depth/camera_info \
  /camera/points
```

### 맵 저장 명령
스캔이 완료되면 터미널 5를 열고 맵을 저장합니다.
```bash
cd /home/emjdp/hyper_Turtle_Project
source /opt/ros/jazzy/setup.bash
source install/setup.bash
mkdir -p maps
ros2 run nav2_map_server map_saver_cli -f maps/test_map
```

---

## 토픽 및 상태 확인 명령

* **기본 토픽 목록:** `ros2 topic list`
* **카메라 토픽 목록:** `ros2 topic list | grep camera`
* **토픽 출력(1회):**
  - `ros2 topic echo /odom --once`
  - `ros2 topic echo /scan --once`
  - `ros2 topic echo /joy --once`
  - `ros2 topic echo /cmd_vel --once`
* **카메라 Update Rate 확인:**
  - `ros2 topic hz /camera/color/image_raw`
  - `ros2 topic hz /camera/depth/image_raw`
* **TF 확인:**
  - `ros2 run tf2_tools view_frames`
  - `ros2 run tf2_ros tf2_echo base_link camera_link`
  - `ros2 run tf2_ros tf2_echo base_link camera_color_optical_frame`

* **GPU 가속 상태 확인:**
  - `glxinfo -B | grep -E 'renderer|Accelerated'`

---

## 실물 도착 후 검증할 항목 (TODO)

현재는 시뮬레이션 기반 구성이므로, 하드웨어 도착 후 아래 항목들에 대한 검증이 필요합니다:
1. **Xbox 게임패드 연결 확인:**
   - 컨트롤러가 인식되지 않으면 `/dev/input/js*` 확인 및 WSL 입력 장치 연결 상태 확인
   - `jstest /dev/input/js0` 로 축/버튼 동작 확인
   - `ros2 run joy joy_node` 및 `ros2 topic echo /joy` 로 매핑 검증 및 `xbox_teleop.yaml` 파라미터 수정 (Deadman/Turbo 버튼)
2. **실제 로봇 주행 안전 테스트:**
   - 실제 로봇에서 처음 테스트할 때는 바퀴를 띄운 상태 또는 넓은 공간에서 낮은 속도로 테스트
3. **RGB-D 카메라 장착 및 TF 보정:**
   - 실제 카메라를 TurtleBot3 상단 브라켓에 장착 후 `base_link` 기준 `x, y, z, roll, pitch, yaw` 측정
   - 측정한 값을 xacro argument로 업데이트하여 시뮬레이션 및 실제 모델과 일치화
   - USB 케이블이 라이다 시야나 회전부에 방해되지 않도록 정리
4. **실제 카메라 드라이버 실행 (RealSense 등):**
   - 실제 카메라의 ros2 드라이버 설치 및 실행
5. **실제 Nav2 및 SLAM 성능 테스트:**
   - 실제 환경에서 SLAM 성능 평가 및 Nav2 튜닝

---

## 향후 계획 (TODO)

1. **자율주행 (Nav2) 전환:**
   - 수동 SLAM으로 저장된 `maps/<map_name>.yaml`을 Nav2 map_server에 로드
   - AMCL/Nav2 localization 구성
   - `nav2_simple_commander` 등 waypoint 기반 자율 순찰 구현 (2차 작업: `hyper_turtle_navigation` 패키지 활성화)
2. **그래피티 탐지 파이프라인 (Perception):**
   - 저장된 rosbag을 재생(`ros2 bag play bags/<bag_name>`)하면서 `/camera/color/image_raw`, `/camera/depth/image_raw`, `/odom`, `/tf` 데이터를 활용
   - 그래피티/스티커/오염 탐지 노드 개발 (`hyper_turtle_perception` 패키지)
   - 탐지 결과를 Depth 정보 및 로봇 Pose(Map 기준 좌표)와 융합하여 지도에 마킹

---

## 알려진 한계 및 주의사항
- WSL 환경에서 Gazebo 성능이 저하(버벅임)될 경우 Gazebo 창 크기를 줄이거나, RViz와 동시에 띄우는 것을 지양하세요.
- 카메라 Update Rate나 PointCloud2 처리 등 무거운 연산은 성능 문제를 일으킬 수 있으므로 필요시에만 활성화하거나 해상도를 낮춰 사용하세요.
- TurtleBot3 Gazebo의 `/cmd_vel` 타입이 `Twist` 또는 `TwistStamped`인지 ros_gz_bridge 설정과 일치하는지 실제 토픽 리스트(`ros2 topic list` 및 `gz topic -l`)를 통해 검증이 필요할 수 있습니다.
