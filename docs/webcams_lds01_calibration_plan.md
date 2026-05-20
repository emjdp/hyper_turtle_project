# Webcams + LDS-01 통합 및 캘리브레이션 구현 계획

브랜치: `feature/webcams-lds01-calibration`
작성일: 2026-05-20

---

## 1. 목표

실제 TurtleBot3 Burger 위에 다음 센서를 장착하고, 토픽/프레임/TF를 정리한 뒤 rosbag으로 데이터 수집까지 가능한 상태를 만든다.

- Logitech **C270** USB 웹캠
- Logitech **C920** USB 웹캠
- TurtleBot3 Burger 기본 **LDS-01** 라이다 (LiDAR Distance Sensor)

### 최종 산출 토픽 (실물 로봇)

| 토픽 | 메시지 | 비고 |
|---|---|---|
| `/camera_c270/image_raw/compressed` | `sensor_msgs/CompressedImage` (JPEG) | C270 |
| `/camera_c270/camera_info` | `sensor_msgs/CameraInfo` | C270 intrinsics |
| `/camera_c920/image_raw/compressed` | `sensor_msgs/CompressedImage` (JPEG) | C920 |
| `/camera_c920/camera_info` | `sensor_msgs/CameraInfo` | C920 intrinsics |
| `/scan` | `sensor_msgs/LaserScan` | LDS-01 |
| `/odom` | `nav_msgs/Odometry` | TurtleBot3 펌웨어 제공 |
| `/tf`, `/tf_static` | `tf2_msgs/TFMessage` | base_link ↔ 센서 프레임 |

> `/camera_info`는 미리 캘리브레이션해서 yaml로 저장 후 `usb_cam`이 토픽으로 퍼블리시한다. 토픽으로 안 보내도 yaml만 있으면 됨.

---

## 2. 결정 사항 (요구사항 합의)

1. **두 카메라 동시 운용** — C270, C920 둘 다 켜고 독립된 네임스페이스로 퍼블리시.
2. **드라이버: `usb_cam`** (`ros-jazzy-usb-cam`) — JPEG `compressed` 토픽과 `camera_info` 모두 한 노드에서 처리.
3. **토픽 항상 네임스페이스 사용** — `/camera_c270/...`, `/camera_c920/...`. 단일 카메라 워크플로(`/image_raw/compressed`)는 만들지 않음.
4. **Gazebo 시뮬레이션도 mono RGB로 통일** — 기존 RGB-D 카메라(`rgbd_camera.xacro`)는 mono RGB 두 대로 교체. 시뮬과 실물의 토픽/프레임 이름을 일치시켜 bag 호환성 확보.

---

## 3. 프레임 / TF 트리

```
map (SLAM, 옵션)
 └─ odom
     └─ base_footprint
         └─ base_link
             ├─ base_scan          (LDS-01, turtlebot3_burger.urdf 기본)
             ├─ camera_c270_link
             │   └─ camera_c270_optical_frame   (ROS 광학 규약: z forward, x right, y down)
             └─ camera_c920_link
                 └─ camera_c920_optical_frame
```

- `base_link → camera_c*_link`: 메커닉 측정값 (x, y, z, roll, pitch, yaw). xacro arg로 관리.
- `camera_c*_link → camera_c*_optical_frame`: 고정 회전 `rpy=(-π/2, 0, -π/2)`.
- `/tf_static`은 `robot_state_publisher`가 URDF에서 자동 생성.

---

## 4. 패키지별 변경 사항

### 4.1 `hyper_turtle_description`

**신규/수정 URDF**
- `urdf/mono_camera.xacro` (신규)
  - 매크로 시그니처: `mono_camera(parent, name, x, y, z, roll, pitch, yaw, width, height, hfov, update_rate)`
  - `<link>` + `<joint>` + `optical_frame` + Gazebo `camera` 센서 플러그인 (mono RGB)
  - Gazebo 토픽: `${name}/image`, `${name}/camera_info`
- `urdf/burger_cams.urdf.xacro` (신규, 시뮬+실물 공용 베이스)
  - TurtleBot3 Burger 기본 URDF include
  - C270, C920 각각 `mono_camera` 매크로 호출
  - xacro arg로 두 카메라의 x/y/z/roll/pitch/yaw 외부 주입
- `urdf/rgbd_camera.xacro`, `urdf/burger_rgbd.urdf.xacro` → **삭제 또는 deprecated** 표시 (Gazebo mono 통일 결정에 따라)

**캘리브레이션 yaml**
- `config/camera_c270.yaml` (신규, 빈 템플릿 → 캘리브레이션 후 갱신)
- `config/camera_c920.yaml` (신규)
- `CMakeLists.txt`의 `install(DIRECTORY ... )`에 `config` 추가.

**RViz**
- `rviz/burger_real.rviz` (신규) — Image (compressed) 2개, LaserScan, TF, Odometry 디스플레이.

### 4.2 `hyper_turtle_bringup`

**시뮬 launch 수정**
- `launch/burger_rgbd_sim.launch.py` → `launch/burger_cams_sim.launch.py`로 교체 (또는 신규).
- xacro arg를 양쪽 카메라용으로 분리: `c270_x/y/z/...`, `c920_x/y/z/...`.
- `config/bridges.yaml` 수정:
  - 기존 `camera/color/...`, `camera/depth/...`, `camera/points` 제거
  - 신규: `camera_c270/image`, `camera_c270/camera_info`, `camera_c920/image`, `camera_c920/camera_info`
  - GZ→ROS 이미지 토픽은 `ros_gz_image image_bridge`로 띄우는 편이 압축 친화적 — 별도 노드로 추가

**실물 launch 신규**
- `launch/burger_real.launch.py`
  - `robot_state_publisher` (mono URDF)
  - `usb_cam` 노드 2개 (C270, C920) — 각각 네임스페이스, device, pixel_format(`mjpeg2rgb`), `camera_info_url` 파라미터
  - TurtleBot3 펌웨어 bringup (`turtlebot3_bringup robot.launch.py` include) — `/odom`, `/scan`(LDS-01), `/tf` 제공
  - 옵션 인자: 어떤 카메라를 띄울지(`enable_c270`, `enable_c920`)
- `config/usb_cam_c270.yaml`, `config/usb_cam_c920.yaml` — usb_cam 파라미터(해상도, fps, pixel_format, camera_info_url, frame_id 등)
- `CMakeLists.txt`에 신규 디렉터리 등록.

### 4.3 `hyper_turtle_mapping`, `hyper_turtle_control` 등
- 이번 브랜치에서는 손대지 않음. (`xbox_teleop.yaml`의 작업 중 변경분은 보존)

---

## 5. 작업 단계 (Step-by-step)

각 단계 끝에 verify 기준을 명시한다.

### Step 1. URDF 리팩터링 (mono 카메라)
- `mono_camera.xacro`, `burger_cams.urdf.xacro` 작성.
- 시뮬 launch가 새 xacro를 가리키도록 변경.
- **verify:** `ros2 launch hyper_turtle_bringup burger_cams_sim.launch.py rviz:=true xbox_teleop:=false` 실행 → RViz에서 `base_link → camera_c270_link`, `base_link → camera_c920_link` TF 보임. `ros2 run tf2_tools view_frames` 결과에 두 광학 프레임 존재.

### Step 2. Gazebo 브릿지 정리
- `bridges.yaml`에서 RGB-D 토픽 제거, mono 두 개로 교체.
- `ros_gz_image image_bridge` 추가하거나 일반 bridge로 처리.
- **verify:** `ros2 topic list | grep camera_c` 로 4개(image, camera_info × 2) 노출. `ros2 topic hz /camera_c270/image_raw` 가 15Hz 근처.

### Step 3. 실물용 launch 작성 (드라이브 미연결 상태에서도 동작 검증)
- `burger_real.launch.py` + `usb_cam_*.yaml` 작성.
- 웹캠 미연결 환경에서는 usb_cam 노드만 실패하도록(전체는 뜨도록) `respawn=False`, `output='screen'`로 가시화.
- **verify:** WSL/노트북에서 더미 실행 시 robot_state_publisher와 launch description 자체는 에러 없이 뜸. USB 웹캠 꽂힌 환경(또는 실물)에서 `ros2 topic echo /camera_c270/image_raw/compressed --once` 가 데이터 출력.

### Step 4. 카메라 내부 파라미터 캘리브레이션 (수동, 실물에서)
- 체커보드 준비(예: 8x6, 25mm). README에 명시.
- 명령(C270 예시):
  ```bash
  ros2 run camera_calibration cameracalibrator \
    --size 8x6 --square 0.025 \
    image:=/camera_c270/image_raw camera:=/camera_c270
  ```
- 결과 `ost.yaml` → `hyper_turtle_description/config/camera_c270.yaml`로 복사 후 commit.
- **verify:** `usb_cam` 재시작 시 `/camera_c270/camera_info` 에 fx, fy, cx, cy, D가 채워져 echo됨. 0 행렬이면 미적용.

### Step 5. 카메라 외부 파라미터(TF) 보정
- 실물 마운트 후 줄자/3D 모델로 base_link 기준 x, y, z, roll, pitch, yaw 측정.
- 측정값을 `burger_real.launch.py`의 xacro arg 기본값에 반영(또는 yaml 분리).
- **verify:** `ros2 run tf2_ros tf2_echo base_link camera_c270_optical_frame` 가 측정값과 부호 일관성 가짐. RViz에서 LaserScan과 카메라 frustum이 물리적으로 그럴듯한 위치에 있음.

### Step 6. LDS-01 동작 확인
- 별도 코드 변경 없음. TurtleBot3 bringup이 `/scan` 제공.
- **verify:** `ros2 topic hz /scan` ≈ 5Hz, `ros2 topic echo /scan --once`에 `frame_id: base_scan` 노출. RViz LaserScan 디스플레이에 360° 데이터.

### Step 7. rosbag 녹화 검증
- 녹화 명령 (README/docs에 추가):
  ```bash
  ros2 bag record -o bags/real_$(date +%Y%m%d_%H%M%S) \
    /camera_c270/image_raw/compressed /camera_c270/camera_info \
    /camera_c920/image_raw/compressed /camera_c920/camera_info \
    /scan /odom /tf /tf_static
  ```
- **verify:** 30초 녹화 → `ros2 bag info` 결과에 모든 토픽이 message_count > 0. `ros2 bag play` 재생 시 RViz에서 동영상 + LaserScan + 로봇 위치 동기 재생.

### Step 8. 문서화
- README에 새 launch/녹화 절차, 캘리브레이션 절차 추가.
- 이 계획서 (`docs/webcams_lds01_calibration_plan.md`)는 완료 항목 체크하며 유지.

---

## 6. 파일 추가/수정 요약

```
docs/
  └─ webcams_lds01_calibration_plan.md         (신규, 본 문서)

src/hyper_turtle_description/
  ├─ urdf/mono_camera.xacro                    (신규)
  ├─ urdf/burger_cams.urdf.xacro               (신규)
  ├─ urdf/rgbd_camera.xacro                    (삭제 후보)
  ├─ urdf/burger_rgbd.urdf.xacro               (삭제 후보)
  ├─ config/camera_c270.yaml                   (신규, intrinsics)
  ├─ config/camera_c920.yaml                   (신규, intrinsics)
  ├─ rviz/burger_real.rviz                     (신규)
  └─ CMakeLists.txt                            (install에 config 추가)

src/hyper_turtle_bringup/
  ├─ launch/burger_cams_sim.launch.py          (신규 or 기존 교체)
  ├─ launch/burger_real.launch.py              (신규)
  ├─ config/bridges.yaml                       (RGB-D → mono 2개로 변경)
  ├─ config/usb_cam_c270.yaml                  (신규)
  └─ config/usb_cam_c920.yaml                  (신규)

README.md                                      (실물 launch, 캘리브 절차 섹션 추가)
```

---

## 7. 의존성 추가

`install_dependencies.sh` / README 패키지 목록에 추가:
- `ros-jazzy-usb-cam`
- `ros-jazzy-camera-calibration` (캘리브레이션 도구)
- `ros-jazzy-image-transport-plugins` (compressed transport)
- `ros-jazzy-ros-gz-image` (Gazebo image bridge — 이미 설치 권장 목록에 있음)

---

## 8. 오픈 이슈 / 확인 필요

1. **실물 TurtleBot3 SBC 위에서 직접 카메라 노드를 띄울지, WSL/PC에서 띄울지** — USB 대역폭과 ROS_DOMAIN_ID 설정에 영향. 우선 SBC에 두 대 모두 연결한다고 가정.
2. **두 웹캠 동시 USB 대역폭** — C920은 1080p@30fps 시 YUYV로 USB2.0 한 포트 점유. 두 대 동시 운용 시 둘 다 MJPEG(JPEG)으로 받고 해상도/fps 조정 필요(예: 둘 다 640×480@30 또는 1280×720@15부터 시작).
3. **`/odom` 출처** — 실물에서는 TurtleBot3 펌웨어가 제공. 별도 EKF는 본 브랜치에서 미도입.
4. **시뮬에서 LDS-01 토픽 이름** — Gazebo 모델은 `scan`을 그대로 사용. 실물과 일치하므로 변경 불필요.
5. **체커보드 사양** — 팀이 가진 보드 사양(가로×세로 코너 수, 한 칸 크기)을 확정해 README에 명시 필요.
