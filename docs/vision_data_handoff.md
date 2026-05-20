# 비전 팀 데이터 인계 스펙

스캔 로봇(TurtleBot3 Burger + 2 webcams + LDS-01)에서 녹화한 bag을 다운스트림(NeRF/3DGS, monocular depth + 2D LiDAR fusion)에 넘기기 위한 **데이터 형식·프레임·좌표계 계약**.

작성일: 2026-05-20
ROS distro: Jazzy
대상: 비전 팀 (NeRF/3DGS 학습 & depth fusion 코드 작성자)

---

## 1. 데이터 한 묶음(bag) 개요

한 번 스캔하면 다음과 같은 폴더가 떨어집니다:

```
bags/scan_YYYYMMDD_HHMMSS/
├── metadata.yaml                       # 토픽 목록·메시지 카운트·duration
└── scan_YYYYMMDD_HHMMSS_0.mcap         # 모든 메시지 (CDR 직렬화, 자체 인덱스)
```

- **포맷**: MCAP (ROS 2 Jazzy 기본). 단일 파일에 모든 토픽 + schema + index.
- **사이즈 분할**: 크면 `_0.mcap`, `_1.mcap`로 자동 split (보통은 1개 파일).
- **읽기**: `ros2 bag play`, `rosbag2_py` (Python ROS), 또는 **`mcap` 라이브러리** (ROS 없이 가능).

녹화에 포함되는 토픽 목록 (현재 확정):

| 토픽 | 메시지 타입 | 평균 rate | 비고 |
|---|---|---|---|
| `/camera_c920/image_raw/compressed` | `sensor_msgs/CompressedImage` | ~30 Hz | JPEG, 1280×720 |
| `/camera_c920/camera_info` | `sensor_msgs/CameraInfo` | ~30 Hz | 매 이미지와 1:1 매칭 |
| `/camera_c270/image_raw/compressed` | `sensor_msgs/CompressedImage` | ~30 Hz | JPEG, 1280×720 |
| `/camera_c270/camera_info` | `sensor_msgs/CameraInfo` | ~30 Hz | |
| `/scan` | `sensor_msgs/LaserScan` | ~5 Hz | LDS-01, 360 samples, 360° |
| `/odom` | `nav_msgs/Odometry` | ~30 Hz | wheel-encoder 기반, drift 있음 |
| `/tf` | `tf2_msgs/TFMessage` | ~30 Hz | 동적 TF (odom→base_footprint 등) |
| `/tf_static` | `tf2_msgs/TFMessage` | 1회 (latched) | 고정 TF (카메라 마운트 등) |

> `/tf_static`은 **`transient_local` QoS** (= latched) 라는 점에 주의 — 후처리 시 구독 QoS를 `RELIABILITY=RELIABLE, DURABILITY=TRANSIENT_LOCAL`로 맞춰야 메시지가 들어옵니다. `rosbag2_py`에서는 알아서 잘 받지만 직접 ROS 노드로 받을 땐 신경 써야 함.

---

## 2. 좌표계 (Frames)

ROS 표준을 그대로 사용합니다.

### 2.1 좌표 컨벤션

| 프레임 | 축 방향 |
|---|---|
| `base_link`, `base_footprint`, `odom` | **REP-103 (오른손)** — x **앞**, y **왼쪽**, z **위** |
| `camera_*_link` (카메라 본체) | base와 동일한 축 — x 앞, y 왼쪽, z 위 |
| `camera_*_optical_frame` (광학) | **REP-103 광학** — x **오른쪽**, y **아래**, z **앞** (OpenCV/SfM 컨벤션) |
| `base_scan` (LDS-01) | x 앞, y 왼쪽, z 위 (REP-103) — 라이다 angle 0 = +x (앞) |

**중요**: 이미지에 해당하는 카메라 광학 좌표계는 `camera_*_optical_frame`입니다. **`camera_*_link`가 아님.** OpenCV/COLMAP/NeRF는 모두 광학 컨벤션을 쓰므로 그대로 매치됩니다.

### 2.2 TF 트리 (정적 + 동적)

```
map (옵션, SLAM 사용 시)
 └─ odom                              ← 녹화 시작점이 원점, 누적
     └─ base_footprint                ← /odom 토픽의 child
         └─ base_link                 ← 로봇 본체
             ├─ base_scan             ← LDS-01 회전 중심
             ├─ camera_c920_link
             │   └─ camera_c920_optical_frame   ← C920 이미지의 frame_id
             ├─ camera_c270_link
             │   └─ camera_c270_optical_frame   ← C270 이미지의 frame_id
             ├─ caster_back_link
             ├─ imu_link
             ├─ wheel_left_link       (동적, /joint_states로 회전)
             └─ wheel_right_link      (동적, /joint_states로 회전)
```

- `odom → base_footprint`: **동적**, `/tf`에 매 시각 publish. 로봇이 움직이면 변함.
- `base_link → camera_*_link`: **정적**, `/tf_static`. 마운트 위치 (캘리브해서 측정).
- `camera_*_link → camera_*_optical_frame`: **정적**, `/tf_static`. 회전만 (rpy = -π/2, 0, -π/2).

### 2.3 현재 마운트값 (`/tf_static`에 들어가는 값)

| 변환 | translation (x, y, z) m | rotation (rpy rad) |
|---|---|---|
| `base_link → camera_c920_link` | (0.075, 0.000, 0.135) | (0, 0, 0) |
| `base_link → camera_c270_link` | (0.060, 0.035, 0.135) | (0, 0, +0.7854) ← +45° yaw |
| `camera_*_link → camera_*_optical_frame` | (0, 0, 0) | (−π/2, 0, −π/2) |

> 위 값은 측정/조정 가능. launch arg(`c920_x`, `c270_yaw` 등)로 외부에서 변경 가능. **실제 녹화된 bag의 `/tf_static`을 단일 출처(source of truth)로 쓰면 launch arg가 무엇이든 일치**합니다.

---

## 3. 토픽별 상세 스키마

### 3.1 `/camera_*/image_raw/compressed` — `sensor_msgs/CompressedImage`

```
header:
  stamp:      builtin_interfaces/Time { sec, nanosec }   ← 캡처 시각
  frame_id:   "camera_c920_optical_frame" 또는 "camera_c270_optical_frame"
format:       "jpeg"
data:         uint8[]                                    ← JPEG raw bytes
```

→ `data` 바이트 그대로 `.jpg`로 저장 가능. 디코딩은 OpenCV `cv2.imdecode` 로.

### 3.2 `/camera_*/camera_info` — `sensor_msgs/CameraInfo`

```
header.stamp, header.frame_id           ← 위와 동일
height:           uint32                ← 720
width:            uint32                ← 1280
distortion_model: "plumb_bob"
d:                float64[5]            ← [k1, k2, t1, t2, k3]  (OpenCV 표준 5-param)
k:                float64[9]            ← row-major 3×3 intrinsic
                                            [fx, 0, cx, 0, fy, cy, 0, 0, 1]
r:                float64[9]            ← rectification (stereo가 아니면 identity)
p:                float64[12]           ← row-major 3×4 projection
                                            [fx, 0, cx, 0, 0, fy, cy, 0, 0, 0, 1, 0]
```

- **`k`가 핵심** — 단안 카메라 intrinsic. NeRF/depth에 그대로 쓰면 됩니다.
- **`d`** — undistortion 시 사용. OpenCV `cv2.undistort(img, K, D)`.
- 캘리브가 안 끝났다면 `k = [0,0,0,0,0,0,0,0,1]`로 0행렬이 옵니다. **`k[0]>0` 체크로 캘리브 완료 여부 판단** 가능.

> **C920 autofocus 주의**: focus가 매 프레임 바뀌면 fx/fy도 미세하게 변합니다. 녹화 전 반드시 `focus_automatic_continuous=0`, `focus_absolute=<고정값>`으로 잠그고 그 상태에서 캘리브해야 합니다. 그렇지 않으면 K가 부정확해서 NeRF가 흐릿해짐.

### 3.3 `/scan` — `sensor_msgs/LaserScan` (LDS-01)

```
header.stamp, header.frame_id="base_scan"
angle_min:        0.0                    rad  ← LDS-01은 0~2π 컨벤션
angle_max:        6.2831...              rad  (=2π)
angle_increment:  0.01745...             rad  (≈1°)
time_increment:   ~0 (single shot 360)
scan_time:        ~0.2 s                       (5 Hz)
range_min:        0.12 m
range_max:        3.5 m
ranges:           float32[360]                ← 각 각도별 거리, NaN/inf는 무효
intensities:      float32[]                   ← LDS-01은 빈 배열일 수 있음
```

**중요**:
- `ranges[0]` = 로봇 정면(+x). 이후 반시계 방향으로 증가 (REP-103: +z 위 방향 회전).
- 즉 `ranges[90]` ≈ 왼쪽(+y), `ranges[180]` ≈ 뒤(−x), `ranges[270]` ≈ 오른쪽(−y).
- 무효 측정(범위 밖, 반사 없음 등)은 `range_min` 이하/`range_max` 이상 또는 `inf`/`NaN`. **마스킹 필수**.

각 라이다 점의 3D 좌표 (base_scan 기준):
```
for i in 0..359:
    r = ranges[i]
    if r < range_min or r > range_max or not finite(r): continue
    angle = angle_min + i * angle_increment
    x = r * cos(angle)
    y = r * sin(angle)
    z = 0   # 2D 라이다
```

### 3.4 `/odom` — `nav_msgs/Odometry`

```
header.stamp, header.frame_id="odom", child_frame_id="base_footprint"
pose.pose.position:    {x, y, z=0}         m   ← world 누적 (녹화 시작 = (0,0,0))
pose.pose.orientation: {x, y, z, w}        quaternion ← yaw 누적
pose.covariance:       float64[36]              row-major 6×6, 잘 안 채워질 수 있음
twist.twist.linear:    {x, y, z}           m/s
twist.twist.angular:   {x, y, z}           rad/s
```

- **`pose`는 `odom` 프레임 기준 누적값**. 시작점이 원점이고 yaw=0.
- **drift 있음** (wheel slip / IMU 없는 burger). 짧은 스캔(<5분)이면 ~10cm 정도, 긴 스캔은 의미 있게 흐름.
- **회전축**: quaternion이지만 2D 평면 이동이라 사실상 yaw만 변합니다. `yaw = 2 * atan2(qz, qw)`.

### 3.5 `/tf`, `/tf_static` — `tf2_msgs/TFMessage`

```
transforms: TransformStamped[]   ← 한 메시지에 여러 transform 묶음
  - header.stamp
    header.frame_id       (parent)
    child_frame_id
    transform.translation {x, y, z}
    transform.rotation    {x, y, z, w}
```

- **`/tf`**: 동적 transform 모음. `odom→base_footprint` (로봇 이동), `base_footprint→base_link` 등.
- **`/tf_static`**: 정적 (마운트, 광학 frame 회전). **녹화 시작 시 한 번만** publish됨 (transient_local).

---

## 4. 각 이미지의 6-DoF world pose 도출 (핵심 파이프라인)

NeRF/3DGS에 필요한 `transforms.json` 같은 데이터셋을 만들 때 **이미지 1장 → 4×4 world pose** 매핑이 핵심.

### 4.1 개념

이미지 timestamp `t`에 대해, world 기준 카메라 광학 frame pose:

```
T_world_camopt(t) =  T_odom_base(t)        ← /tf 에서 보간
                   * T_base_camlink         ← /tf_static 상수
                   * T_camlink_camopt       ← /tf_static 상수 (-π/2, 0, -π/2)
```

이게 한 줄 식이고, **`odom` 프레임을 world로 그대로 채택**한 결과 (스캔 시작점이 원점인 world).

### 4.2 시간 동기화

- 이미지 stamp 와 정확히 같은 시각의 `/tf` 메시지가 없을 수 있음 → **앞/뒤 두 TF를 시간선형 보간**.
- translation은 선형 보간, rotation은 **slerp** (quaternion spherical linear interpolation).
- 이미지와 TF의 시간차가 > 50ms면 해당 이미지는 버리는 게 안전 (로봇이 빠르게 움직일 때).

### 4.3 좌표계 변환 (광학 → world)

`T_world_camopt`는 4×4 SE(3) 매트릭스. NeRF는 보통 다음 컨벤션을 요구:
- **nerfstudio / instant-ngp**: camera-to-world, OpenCV 광학 컨벤션 (우리 frame과 일치) ✓
- **3DGS (original)**: COLMAP 컨벤션 — camera-to-world, OpenCV (역시 일치) ✓

즉 `T_world_camopt` 그대로 4×4 매트릭스로 export하면 됩니다.

### 4.4 Python 의사코드

```python
import numpy as np
from scipy.spatial.transform import Rotation as R, Slerp
from mcap_ros2.reader import read_ros2_messages

# 1) bag 전체에서 TF 시퀀스 수집
tf_dynamic = []   # [(t_ns, frame_id, child_id, T_4x4), ...]
tf_static  = {}   # {(parent, child): T_4x4}
images = {"c920": [], "c270": []}  # [(t_ns, jpeg_bytes), ...]
cam_info = {}

for msg in read_ros2_messages(bag_path):
    topic = msg.channel.topic
    m = msg.ros_msg
    t_ns = msg.publish_time_ns
    if topic in ("/tf", "/tf_static"):
        for tr in m.transforms:
            T = transform_to_matrix(tr.transform)   # 4x4
            if topic == "/tf_static":
                tf_static[(tr.header.frame_id, tr.child_frame_id)] = T
            else:
                tf_dynamic.append((stamp_to_ns(tr.header.stamp),
                                   tr.header.frame_id, tr.child_frame_id, T))
    elif topic.endswith("/image_raw/compressed"):
        cam = "c920" if "c920" in topic else "c270"
        images[cam].append((t_ns, bytes(m.data)))
    elif topic.endswith("/camera_info") and topic not in cam_info:
        cam = "c920" if "c920" in topic else "c270"
        cam_info[cam] = {"K": np.array(m.k).reshape(3, 3),
                         "D": np.array(m.d),
                         "w": m.width, "h": m.height}

# 2) odom→base_footprint 보간기 만들기
times = [t for (t, p, c, T) in tf_dynamic if p == "odom" and c == "base_footprint"]
mats  = [T for (t, p, c, T) in tf_dynamic if p == "odom" and c == "base_footprint"]
# scipy Slerp + numpy interp 사용

# 3) base_link → camera_optical_frame (정적, 한 번에 계산)
T_base_camopt = {
  "c920": tf_static[("base_link","camera_c920_link")] @
          tf_static[("camera_c920_link","camera_c920_optical_frame")],
  "c270": tf_static[("base_link","camera_c270_link")] @
          tf_static[("camera_c270_link","camera_c270_optical_frame")],
}
# 주의: tf_static에 'base_footprint→base_link' 도 있음. 그 변환도 곱해야 정확.
T_base_camopt = {k: tf_static[("base_footprint","base_link")] @ v
                 for k, v in T_base_camopt.items()}

# 4) 각 이미지의 world pose
for cam, frames in images.items():
    for t_ns, jpeg in frames:
        T_world_base = interpolate_tf(t_ns, times, mats)    # SE(3) 보간
        T_world_camopt = T_world_base @ T_base_camopt[cam]
        # T_world_camopt 가 nerfstudio/3DGS에 들어갈 4x4 pose
```

전체 export 스크립트는 따로 만들 예정 (`scripts/bag_to_nerf.py` 등). 위는 알고리즘만.

### 4.5 결과 예시 — `transforms.json` (nerfstudio 형식)

```json
{
  "camera_model": "OPENCV",
  "fl_x": 1080.5, "fl_y": 1081.2,
  "cx": 640.3, "cy": 360.1,
  "w": 1280, "h": 720,
  "k1": -0.12, "k2": 0.04, "p1": 0.001, "p2": -0.0005, "k3": 0.0,
  "frames": [
    {
      "file_path": "images/c920/1779280176_345922756.jpg",
      "transform_matrix": [
        [r11, r12, r13, tx],
        [r21, r22, r23, ty],
        [r31, r32, r33, tz],
        [0,   0,   0,   1 ]
      ]
    },
    ...
  ]
}
```

> 두 카메라는 다른 intrinsic을 가지므로 **`transforms.json`을 2개 만들거나**, nerfstudio의 `per-image intrinsics` 모드 (frame당 `fl_x` 등 따로)로 합쳐서 하나로.

---

## 5. 2D LiDAR + Monocular Depth 융합 — 필요한 데이터

### 5.1 입력
- `/scan` (한 시각 1개 메시지)
- 같은 시각 가까운 카메라 이미지 (보통 C920 전방)
- `/camera_c920/camera_info` (K, D)
- `T_base_scan ← /tf_static` (base_link → base_scan)
- `T_base_camopt ← /tf_static * /tf_static` (base_link → camera_optical_frame)

### 5.2 LiDAR 점을 카메라 image plane에 투영

```python
# 라이다 점 (base_scan 기준) → camera_c920_optical 기준
T_camopt_scan = inv(T_base_camopt_c920) @ T_base_scan   # 4x4

for i, r in enumerate(scan.ranges):
    if r < range_min or r > range_max or not finite(r): continue
    angle = scan.angle_min + i * scan.angle_increment
    pt_scan = np.array([r*cos(angle), r*sin(angle), 0, 1])  # 4x1
    pt_cam = T_camopt_scan @ pt_scan                   # in optical frame
    if pt_cam[2] <= 0: continue                        # 카메라 뒤
    uv = K @ (pt_cam[:3] / pt_cam[2])                  # pixel
    u, v, depth = uv[0], uv[1], pt_cam[2]
    if 0 <= u < W and 0 <= v < H:
        sparse_depth[round(v), round(u)] = depth        # m 단위 sparse depth map
```

→ **카메라 시야 안쪽**의 라이다 점들이 픽셀 위 sparse depth로 매핑됩니다. 여기서 `depth`(미터)와 monocular network 추정값을 비교해서 **스케일 계수**를 fit합니다 (예: median ratio, 또는 RANSAC).

### 5.3 시간 동기화 주의

- LDS-01은 5Hz, 카메라는 30Hz라 timestamp 차이가 최대 ±100ms.
- 로봇 정지 상태라면 무시 가능, 이동 중이라면 라이다 점을 (현재 시각 카메라 pose 기준이 아닌) **라이다 시각 pose**에서 카메라 시각으로 transform 해주는 게 정확:

```
pt_world = T_world_base(t_scan) * T_base_scan * pt_scan
pt_cam   = inv(T_base_camopt) * inv(T_world_base(t_image)) * pt_world
```

천천히 주행하는 매핑 단계에서는 그냥 같은 stamp로 두고 ±100ms 오차 무시해도 깊이 추정 스케일 정확도엔 큰 영향 없음.

---

## 6. 권장 export 디렉토리 구조

bag 한 개에서 다음 폴더 구조를 만드는 걸 표준으로 합니다 (`scripts/bag_to_dataset.py`가 만들 예정):

```
dataset/scan_YYYYMMDD_HHMMSS/
├── README.md                       # 녹화 메타 (날짜·환경·캘리브 상태 등)
├── images/
│   ├── c920/
│   │   ├── 1779280176_345922756.jpg     # 파일명 = "{sec}_{nanosec}.jpg"
│   │   └── ...
│   └── c270/
│       └── ...
├── calibration/
│   ├── camera_c920.yaml            # ROS CameraInfo 그대로 (K, D, ...)
│   └── camera_c270.yaml
├── poses/
│   ├── transforms_c920.json        # nerfstudio 형식
│   ├── transforms_c270.json
│   └── odom.csv                    # 원본 /odom (time_ns, x, y, qz, qw)
├── lidar/
│   ├── scan_1779280176_400000000.npz   # ranges, angle_min, angle_increment 저장
│   └── ...
└── tf_static.yaml                  # 모든 정적 TF 출력 (debug용)
```

- **타임스탬프 = 파일명** → 동일 시각 이미지·스캔을 쉽게 매칭.
- **calibration yaml** = ROS CameraInfo 표준 → OpenCV/COLMAP/NeRF 모두 호환.

---

## 7. 알아둘 함정 / 데이터 품질 체크

### 7.1 녹화 전 반드시 확인

1. **C920 autofocus OFF + focus 값 고정** — 안 그러면 K가 프레임마다 흔들림
   ```bash
   v4l2-ctl -d /dev/video2 -c focus_automatic_continuous=0 -c focus_absolute=<값>
   ```
2. **C920/C270 auto white balance OFF + manual** — frame 간 색온도 흔들리면 NeRF 색이 흐려짐
3. **노출 고정** (`auto_exposure=1`, `exposure_time_absolute=<값>`) — 같은 이유
4. **`exposure_dynamic_framerate=0`** — 안 그러면 fps 절반으로 떨어짐

### 7.2 데이터 받고 처음 확인할 것

```bash
ros2 bag info bag_path
```
- 각 토픽 메시지 카운트 (스캔 시간 × 예상 rate 와 비슷한지)
- 카메라 ~30Hz × duration, scan ~5Hz × duration, odom ~30Hz × duration

```bash
# camera_info의 K가 진짜로 들어왔는지
ros2 bag play bag_path --rate 0.5   # 다른 터미널에서 echo로 확인
```

### 7.3 좌표/시간 sanity check

- `T_odom_base(t)`가 t 증가하면서 **부드럽게** 변하는지 (jump 있으면 odometry 망가짐)
- 라이다 점을 카메라에 투영했을 때 **벽 같은 정적 구조물에 점이 잘 안착**하는지 (벽 위에 라이다 점이 안 찍히고 빈 공간에 떠 있으면 TF 마운트 잘못됨)

### 7.4 알려진 한계

- `/odom`는 wheel encoder만 사용. 슬립/장애물 충돌 시 drift. 긴 스캔에서는 SLAM(slam_toolbox) 출력 `map→odom` 도 같이 녹화하는 게 좋음. (현재 본 launch에는 SLAM 미포함 — 필요하면 별도 launch 추가)
- LDS-01 회전 1회당 0.2초. 빠르게 회전 중이면 한 scan 안에서도 angular drift 있음 (motion distortion). 천천히 움직이는 게 좋음.
- 카메라와 라이다 stamp가 **각자의 내부 시각 기준**. 시스템 시각 동기는 보통 잘 맞지만, 큰 jitter(±100ms+)는 SBC가 부하 받을 때 가능.

---

## 8. 비전 팀이 짤 코드에서 의존하면 좋은 라이브러리

- **mcap (Python)**: `pip install mcap mcap-ros2-support` — ROS 없이 bag 읽기.
- **opencv-python**: JPEG 디코드 + undistort
- **scipy** (`spatial.transform.Rotation`, `Slerp`): quaternion ↔ matrix, 시간 보간
- **numpy / scipy** for 일반 행렬 연산
- (선택) **nerfstudio** for NeRF/3DGS 파이프라인
- (선택) **foxglove** 데스크탑 앱 — bag 시각화/디버깅

---

## 9. 인계 후 확정해야 할 항목 체크리스트

- [ ] **체커보드 사양 확정** (예: 8×6, 25mm) → 캘리브 일관성
- [ ] **C920 focus 고정값** (예: `focus_absolute=0` for 무한대) 합의
- [ ] **녹화 시 v4l2 자동 컨트롤 OFF 스크립트** 본 launch에 합치기
- [ ] **`scripts/bag_to_dataset.py`** 작성 → 본 문서 §6 디렉토리 구조 만들기
- [ ] **SLAM(map→odom) 녹화 옵션** 추가 여부 결정 (긴 스캔에 필요)
- [ ] **외부 캘리브** (base_link → camera_*_link) 정확도 검증 (벽 투영 sanity check)

---

## 부록 A — 한 줄 요약

```
[녹화]
ros2 bag record -o bags/scan_$(date +%Y%m%d_%H%M%S) \
  /camera_c920/image_raw/compressed /camera_c920/camera_info \
  /camera_c270/image_raw/compressed /camera_c270/camera_info \
  /scan /odom /tf /tf_static

[bag → dataset (TBD 스크립트)]
python scripts/bag_to_dataset.py bags/scan_YYYYMMDD_HHMMSS dataset/

[NeRF 학습]
ns-train nerfacto --data dataset/scan_YYYYMMDD_HHMMSS
```

## 부록 B — `/tf_static` raw 예시 (디버깅용)

```yaml
# tf_static.yaml 추출 예 (변환값은 실제 launch arg에 따라 달라짐)
- parent: base_footprint
  child:  base_link
  xyz:    [0.0, 0.0, 0.010]
  rpy:    [0, 0, 0]
- parent: base_link
  child:  base_scan
  xyz:    [-0.032, 0.0, 0.171]
  rpy:    [0, 0, 0]
- parent: base_link
  child:  camera_c920_link
  xyz:    [0.075, 0.000, 0.135]
  rpy:    [0, 0, 0]
- parent: camera_c920_link
  child:  camera_c920_optical_frame
  xyz:    [0, 0, 0]
  rpy:    [-1.5708, 0, -1.5708]
- parent: base_link
  child:  camera_c270_link
  xyz:    [0.060, 0.035, 0.135]
  rpy:    [0, 0, 0.7854]
- parent: camera_c270_link
  child:  camera_c270_optical_frame
  xyz:    [0, 0, 0]
  rpy:    [-1.5708, 0, -1.5708]
```
