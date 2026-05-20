# Sample bags — 2026-05-20 인계

녹화 환경: PC(galaxybook)에서 ROS 2 Jazzy로 wifi 너머의 SBC(turtlebot3)가 publish하는 토픽을 `ros2 bag record`로 받음.

포함된 bag 2개. 둘 다 **부분 데이터**임을 먼저 명시합니다.

---

## scan_20260520_232800

- 파일: `scan_20260520_232800_0.mcap` (4.2 MiB)
- Duration: **34.18 s**
- 총 메시지 수: 559

| 토픽 | 타입 | 카운트 | 예상 (rate × 34s) | 비고 |
|---|---|---|---|---|
| `/camera_c920/image_raw/compressed` | `sensor_msgs/CompressedImage` | **8** | ~1020 (30Hz) | 0.23 Hz |
| `/camera_c920/camera_info` | `sensor_msgs/CameraInfo` | 189 | ~1020 | 5.5 Hz |
| `/camera_c270/image_raw/compressed` | `sensor_msgs/CompressedImage` | **11** | ~1020 (30Hz) | 0.32 Hz |
| `/camera_c270/camera_info` | `sensor_msgs/CameraInfo` | 330 | ~1020 | 9.7 Hz |
| `/scan` | `sensor_msgs/LaserScan` | **16** | ~170 (5Hz) | 0.47 Hz |
| `/tf_static` | `tf2_msgs/TFMessage` | 5 | 5~6 | latched |
| `/tf` | `tf2_msgs/TFMessage` | **0** | 다수 | **부재** |
| `/odom` | `nav_msgs/Odometry` | **(토픽 자체 없음)** | 다수 | **부재** |

### 빠진 것 / 비정상

- `/odom` 토픽 자체가 bag에 없음. 녹화 시 publisher 부재.
- `/tf` 메시지 0개. 동적 transform 없음.
- 이미지·스캔 카운트가 목표의 ~1% 수준. (publisher는 정상 rate로 publish했으나 PC가 wifi 너머로 거의 못 받음)
- `/camera_*/camera_info`도 image rate와 비대칭. CameraInfo는 작은 메시지(<1KB)라 비교적 살아남고, CompressedImage(~40KB)는 대부분 drop된 패턴.

---

## scan_20260520_233259

- 파일: `scan_20260520_233259_0.mcap` (12.1 MiB)
- Duration: **24.95 s**
- 총 메시지 수: 402

| 토픽 | 타입 | 카운트 | 예상 (rate × 25s) | 비고 |
|---|---|---|---|---|
| `/camera_c920/image_raw/compressed` | `sensor_msgs/CompressedImage` | **38** | ~750 (30Hz) | 1.5 Hz |
| `/camera_c920/camera_info` | `sensor_msgs/CameraInfo` | 90 | ~750 | 3.6 Hz |
| `/camera_c270/image_raw/compressed` | `sensor_msgs/CompressedImage` | **54** | ~750 (30Hz) | 2.2 Hz |
| `/camera_c270/camera_info` | `sensor_msgs/CameraInfo` | 200 | ~750 | 8.0 Hz |
| `/scan` | `sensor_msgs/LaserScan` | **15** | ~125 (5Hz) | 0.6 Hz |
| `/tf_static` | `tf2_msgs/TFMessage` | 5 | 5~6 | latched |
| `/tf` | `tf2_msgs/TFMessage` | **0** | 다수 | **부재** |
| `/odom` | `nav_msgs/Odometry` | **(토픽 자체 없음)** | 다수 | **부재** |

### 빠진 것 / 비정상

- 232800 bag과 동일하게 `/odom` 부재, `/tf` 0개.
- 이미지 rate가 직전 bag(0.2~0.3Hz) 대비 5~7배 개선됐지만 여전히 목표의 5~7%.
- `/scan`도 비슷한 수준으로 drop.

---

## 두 bag 공통 — 들어가 있는 정적 정보

`/tf_static`에는 transform이 **5개** 들어 있음. 예상 6개 중 1개 누락. 들어있는 것들은 (이름만 정확히 확인 필요):

- `base_footprint → base_link`
- `base_link → base_scan` (LDS-01)
- `base_link → camera_c920_link`
- `camera_c920_link → camera_c920_optical_frame`
- `base_link → camera_c270_link`
- `camera_c270_link → camera_c270_optical_frame`

> 실제 어느 1개가 빠졌는지는 bag을 직접 디코드해야 확인 가능. 5개 중 어느 게 누락됐는지에 따라 사용 가능 범위가 달라짐.

`camera_info`의 `k` matrix는 **캘리브레이션 전 상태일 가능성 큼** (`[0, 0, 0, 0, 0, 0, 0, 0, 1]`). 직접 echo로 확인 필요.

---

## 한 줄 요약

| 항목 | 232800 | 233259 |
|---|---|---|
| 정적 TF | 부분 (5/6) | 부분 (5/6) |
| Camera intrinsics 메시지 | 들어옴 | 들어옴 |
| 이미지 (C920/C270) | 8/11 | 38/54 |
| LaserScan | 16 | 15 |
| 동적 TF (`/tf`) | 없음 | 없음 |
| 로봇 위치 (`/odom`) | 없음 | 없음 |
