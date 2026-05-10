#!/bin/bash
# install_dependencies.sh
# Ubuntu 24.04 LTS (WSL2) / ROS 2 Jazzy 의존성 설치 스크립트
# 작성자 및 협업자를 위한 개발 환경 설정 자동화 파일

echo "=== ROS 2 Jazzy 패키지 및 의존성 설치 시작 ==="

# 1. 시스템 패키지 목록 업데이트
echo "=> apt 업데이트 중..."
sudo apt update -y

# 2. ROS 2 및 TurtleBot3 기본 패키지 설치
# (README.md에 명시된 필수 패키지 + 게임패드 및 빌드 도구)
echo "=> 필수 ROS 2 패키지 및 툴 설치 중..."
sudo apt install -y \
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
  ros-jazzy-teleop-twist-joy \
  python3-colcon-common-extensions \
  python3-rosdep \
  python3-vcstool \
  jstest-gtk \
  joystick \
  rsync

# 3. rosdep 초기화 및 업데이트 (ROS 패키지 의존성 자동 관리)
echo "=> rosdep 초기화 및 업데이트 중..."
if [ ! -f /etc/ros/rosdep/sources.list.d/20-default.list ]; then
  sudo rosdep init
fi
rosdep update

# 4. 워크스페이스 내 소스 코드(src) 기반 의존성 자동 설치
echo "=> 프로젝트 src 내 패키지들의 의존성 확인 및 설치 중..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
cd "$SCRIPT_DIR" || exit

if [ -d "src" ]; then
    rosdep install --from-paths src --ignore-src -r -y --rosdistro jazzy
else
    echo "경고: 'src' 디렉토리를 찾을 수 없어 src 기반 의존성은 건너뜁니다."
fi

echo "=== 설치 완료! ==="
echo "환경 설정이 끝났습니다. 워크스페이스를 빌드하려면 다음 명령을 순서대로 실행하세요:"
echo "source /opt/ros/jazzy/setup.bash"
echo "colcon build --symlink-install"
echo "source install/setup.bash"
