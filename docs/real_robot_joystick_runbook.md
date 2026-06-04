# Real TurtleBot3 Burger Joystick Runbook

실물 TurtleBot3 Burger에서 PC 조이스틱으로 주행하고, 카메라 2개와 센서 데이터를 기록하는 절차입니다.

## 전원 체크

- USB 전원만으로는 로봇 보드와 센서가 살아도 바퀴가 안 움직일 수 있습니다.
- 배터리 또는 모터 전원을 연결하고 OpenCR/모터 전원 스위치가 켜져 있는지 확인하세요.
- 처음 주행 테스트는 바퀴를 띄우거나 넓은 공간에서 낮은 속도로 진행하세요.

## 현재 확인된 장치

- 로봇 SSH: `ssh rpi5`
- 로봇 IP: `172.21.105.146`
- PC IP: `172.21.5.40`
- C920: `/dev/video0`, ROS namespace `/camera_c920`
- C270: `/dev/video2`, ROS namespace `/camera_c270`
- LDS-01: `/scan`
- OpenCR: `/dev/ttyACM0`
- TurtleBot3 Jazzy `turtlebot3_node`는 `/cmd_vel`을 `geometry_msgs/msg/TwistStamped`로 구독합니다. 일반 `Twist`를 보내면 움직이지 않습니다.

## 0. 빠른 실행 (스크립트 권장)

복붙 없이 PC에서 스크립트만 실행하면 됩니다. 각 스크립트는 `ssh -t` + `exec`로
**원격에 단 하나의 프로세스만** 띄우므로 Ctrl+C가 그 프로세스에 직접 전달됩니다.
특히 녹화는 SIGINT가 `ros2 bag record`에 바로 가서 bag이 깨지지 않고 마감됩니다.

> SSH 대상은 각 스크립트 상단 `ROBOT_SSH="rpi5"` 한 줄입니다. IP가 바뀌면
> `setup_rpi_ssh.sh`의 `RPI_IP`만 고치고 다시 실행하면 `rpi5` alias가 갱신됩니다.
> 브리지/녹화 로직을 바꾸려면 `udp_cmd_vel_bridge.py` 한 곳만 수정합니다.

먼저 한 번만 코드 동기화(브리지 파일이 로봇에 있어야 함):

```bash
./deploy_to_robot.sh
```

그 다음 PC에서 터미널을 나눠 실행합니다.

```bash
# 터미널 A (로봇): bringup — LDS/OpenCR/카메라 2개
./robot_bringup.sh

# 터미널 B (로봇): UDP -> /cmd_vel 브리지 (조이스틱으로 주행할 때만 필요)
./robot_cmd_bridge.sh

# 터미널 C (PC): 조이스틱 읽기 + UDP 전송 (IP 생략 시 rpi5에서 자동 해석)
./run_pc_joystick.sh

# 터미널 D (로봇): bag 녹화 — 끝낼 때 Ctrl+C 로 깨끗하게 마감
./robot_record.sh                 # 또는: ./robot_record.sh free_run
```

녹화를 멈춘 뒤 로컬로 가져오기 (`.last_bag` 기준 최신 bag 자동 선택):

```bash
./fetch_turtlebot_bag.sh
```

녹화 토픽 세트: `/scan /odom /tf /tf_static /joint_states /cmd_vel /imu`
`/battery_state /sensor_state /magnetic_field` +
`/camera_c920`, `/camera_c270`의 `image_raw/compressed`, `camera_info`.

아래 1~6은 동일한 작업을 수동 명령으로 푼 참고용입니다. (이전
`run_turtlebot_scan.sh`는 bringup+브리지+녹화를 한 세션에 묶어 Ctrl+C 시 bag이
깨지는 문제가 있었고, 위 스크립트들로 대체되었습니다.)

## 1. 로봇 bringup 실행

로봇에서 실행합니다.

```bash
ssh rpi5
cd ~/hyper_turtle_project
export ROS_DOMAIN_ID=30
export ROS_STATIC_PEERS=172.21.5.40
export TURTLEBOT3_MODEL=burger
export LDS_MODEL=LDS-01
source /opt/ros/jazzy/setup.bash
source ~/turtlebot3_ws/install/setup.bash
source install/setup.bash
ros2 launch hyper_turtle_bringup burger_real.launch.py
```

정상 로그 예시는 다음과 같습니다.

- `Succeeded to open the port(/dev/ttyACM0)!`
- `hlds_laser_publisher ... port : /dev/ttyUSB0`
- `camera_c920 ... Starting ... (/dev/video0)`
- `camera_c270 ... Starting ... (/dev/video2)`

## 2. PC 조이스틱을 로봇으로 보내기

현재 네트워크에서는 PC의 ROS 토픽이 로봇의 `/cmd_vel` subscriber를 안정적으로 찾지 못했습니다. 그래서 PC에서는 조이스틱만 읽고 UDP로 로봇에 보내며, 로봇에서 `/cmd_vel`을 직접 발행합니다.

### 2-1. 로봇에서 UDP to `/cmd_vel` 브리지 실행

로봇에서 실행합니다. 이 브리지는 UDP `9090`을 받고 `TwistStamped /cmd_vel`을 냅니다.

```bash
ssh rpi5
cd ~/hyper_turtle_project
export ROS_DOMAIN_ID=30
export TURTLEBOT3_MODEL=burger
export LDS_MODEL=LDS-01
source /opt/ros/jazzy/setup.bash
source ~/turtlebot3_ws/install/setup.bash
source install/setup.bash
python3 -u - <<'PY'
import json, socket, time
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import TwistStamped

PORT = 9090
ENABLE_BUTTON = 7
TURBO_BUTTON = 4
LIN_AXIS = 1
ANG_AXIS = 3
LIN_SCALE = 0.15
ANG_SCALE = 0.8
LIN_TURBO = 0.22
ANG_TURBO = 1.2
TIMEOUT = 0.25

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
        self.get_logger().info(f"UDP joystick bridge listening on :{PORT}, publishing TwistStamped /cmd_vel")

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
        enabled = fresh and len(self.buttons) > ENABLE_BUTTON and self.buttons[ENABLE_BUTTON] == 1
        if enabled:
            turbo = len(self.buttons) > TURBO_BUTTON and self.buttons[TURBO_BUTTON] == 1
            lin_scale = LIN_TURBO if turbo else LIN_SCALE
            ang_scale = ANG_TURBO if turbo else ANG_SCALE
            if len(self.axes) > LIN_AXIS:
                msg.twist.linear.x = -self.axes[LIN_AXIS] * lin_scale
            if len(self.axes) > ANG_AXIS:
                msg.twist.angular.z = -self.axes[ANG_AXIS] * ang_scale
        self.pub.publish(msg)

rclpy.init()
node = UdpJoyCmdStamped()
try:
    rclpy.spin(node)
finally:
    node.destroy_node()
    rclpy.shutdown()
PY
```

### 2-2. PC에서 조이스틱 읽기

PC 프로젝트 루트에서 실행합니다.

```bash
cd /home/emjdp/dev/hyper_turtle_project
export ROS_LOCALHOST_ONLY=1
export ROS_DOMAIN_ID=77
source /opt/ros/jazzy/setup.bash
ros2 run joy joy_node --ros-args -p device_id:=0 -p deadzone:=0.05 -p autorepeat_rate:=20.0
```

### 2-3. PC에서 UDP sender 실행

다른 PC 터미널에서 실행합니다.

```bash
cd /home/emjdp/dev/hyper_turtle_project
export ROS_LOCALHOST_ONLY=1
export ROS_DOMAIN_ID=77
source /opt/ros/jazzy/setup.bash
python3 -u - <<'PY'
import json, socket
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy

TARGET = "172.21.105.146"
PORT = 9090

class JoyUdpSender(Node):
    def __init__(self):
        super().__init__("joy_udp_sender")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sub = self.create_subscription(Joy, "/joy", self.cb, 10)
        self.count = 0
        self.get_logger().info(f"Sending /joy UDP to {TARGET}:{PORT}")

    def cb(self, msg):
        packet = {"axes": list(msg.axes), "buttons": list(msg.buttons)}
        self.sock.sendto(json.dumps(packet).encode("utf-8"), (TARGET, PORT))
        self.count += 1
        if self.count % 50 == 0:
            self.get_logger().info(f"sent {self.count} joy packets")

rclpy.init()
node = JoyUdpSender()
try:
    rclpy.spin(node)
finally:
    node.destroy_node()
    rclpy.shutdown()
PY
```

## 3. 조작법

- Enable: button `7`을 누른 상태에서만 움직입니다.
- Turbo: button `4`를 같이 누릅니다.
- 전후진: axis `1`
- 회전: axis `3`
- UDP 입력이 0.25초 이상 끊기거나 enable 버튼을 놓으면 0 속도가 발행됩니다.

## 4. 주행 명령 확인

로봇에서 실행합니다. button `7`을 누른 상태로 스틱을 움직이면 값이 나와야 합니다.

```bash
ssh rpi5
cd ~/hyper_turtle_project
export ROS_DOMAIN_ID=30
export TURTLEBOT3_MODEL=burger
export LDS_MODEL=LDS-01
source /opt/ros/jazzy/setup.bash
source ~/turtlebot3_ws/install/setup.bash
source install/setup.bash
ros2 topic echo /cmd_vel geometry_msgs/msg/TwistStamped --once
```

subscriber 타입 확인:

```bash
ros2 topic info /cmd_vel -v
```

정상 상태에서는 publisher와 subscriber가 둘 다 `geometry_msgs/msg/TwistStamped`여야 합니다.

## 5. 카메라/센서 확인

로봇에서 실행합니다.

```bash
ros2 topic hz /camera_c920/image_raw
ros2 topic hz /camera_c270/image_raw
ros2 topic hz /scan
ros2 topic echo /odom --once
```

확인된 대략적인 rate:

- C920: 약 9 Hz
- C270: 약 10 Hz
- LDS `/scan`: 약 5 Hz

## 6. 테스트 bag 기록

로봇에서 실행합니다.

```bash
cd ~/hyper_turtle_project
mkdir -p bags
export ROS_DOMAIN_ID=30
export ROS_STATIC_PEERS=172.21.5.40
export TURTLEBOT3_MODEL=burger
export LDS_MODEL=LDS-01
source /opt/ros/jazzy/setup.bash
source ~/turtlebot3_ws/install/setup.bash
source install/setup.bash
ros2 bag record -o bags/real_joystick_cam_test_$(date +%Y%m%d_%H%M%S) \
  /scan \
  /odom \
  /tf \
  /tf_static \
  /joint_states \
  /cmd_vel \
  /camera_c920/image_raw/compressed \
  /camera_c920/camera_info \
  /camera_c270/image_raw/compressed \
  /camera_c270/camera_info
```

로컬로 가져오기:

```bash
cd /home/emjdp/dev/hyper_turtle_project
mkdir -p bags
rsync -avz --progress rpi5:~/hyper_turtle_project/bags/<bag_directory> ./bags/
```

## 7. teleop_twist_joy를 쓰는 경우

로봇에 컨트롤러를 직접 연결하고 로봇에서 `joy_node + teleop_twist_joy`를 실행하면 UDP 우회 없이 더 단순하게 구성할 수 있습니다. 다만 현재 TurtleBot3 노드는 `/cmd_vel`을 `TwistStamped`로 구독하므로, 사용하는 `teleop_twist_joy`가 `TwistStamped` 출력을 지원하는지 확인해야 합니다. 지원하지 않으면 `Twist`를 `TwistStamped`로 바꾸는 변환 노드가 추가로 필요합니다.
