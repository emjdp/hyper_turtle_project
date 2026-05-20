#!/bin/bash
# deploy_to_robot.sh
# 개발 환경의 소스 코드를 로봇 보드(Raspberry Pi 등 SBC)로 업로드(동기화)하는 스크립트

# 사용법: ./deploy_to_robot.sh [로봇_IP] [사용자명] [원격_작업_폴더]
# 예시: ./deploy_to_robot.sh 172.21.104.55 ubuntu hyper_turtle_project
#       (TARGET_DIR은 SBC 홈 기준 상대경로 권장. ~ 을 쓰면 PC 쪽에서 미리 확장돼 실패함)

# 매개변수 설정 및 기본값 (현재 SBC 정보)
ROBOT_IP=${1:-"172.21.104.55"}
ROBOT_USER=${2:-"ubuntu"}
# SBC 홈(/home/ubuntu) 기준 상대경로. rsync가 remote shell로 풀어줌.
TARGET_DIR=${3:-"hyper_turtle_project"}

echo "=== 로봇(SBC) 보드 코드 업로드 스크립트 ==="
echo "대상 로봇 IP : $ROBOT_IP"
echo "계정 이름    : $ROBOT_USER"
echo "대상 디렉토리: ~$ROBOT_USER/$TARGET_DIR  (SBC 홈 기준)"
echo "----------------------------------------------"

# rsync 설치 여부 확인
if ! command -v rsync &> /dev/null; then
    echo "rsync가 설치되어 있지 않습니다. 로컬 시스템에 설치를 진행합니다..."
    sudo apt-get install -y rsync
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
cd "$SCRIPT_DIR" || exit

echo "=> 네트워크를 통한 소스 코드 동기화 중 (rsync)..."
# src 디렉토리의 내용과 필수 파일들만 전송합니다.
# (build, install, log, bags 디렉토리는 로봇 자체에서 빌드/생성하도록 제외합니다.)

rsync -avz --progress \
    --exclude='.git/' \
    --exclude='.venv/' \
    --exclude='.vscode/' \
    --exclude='.claude/' \
    --exclude='bags/' \
    --exclude='build/' \
    --exclude='install/' \
    --exclude='log/' \
    --exclude='maps/' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    -e ssh ./ "$ROBOT_USER@$ROBOT_IP:$TARGET_DIR/"

if [ $? -eq 0 ]; then
    echo ""
    echo "=> 전송이 완료되었습니다!"
    echo "----------------------------------------------"
    echo "이제 아래 명령을 복사하여 로봇에 접속한 후 코드를 빌드하세요:"
    echo "  ssh $ROBOT_USER@$ROBOT_IP"
    echo "  cd $TARGET_DIR"
    echo "  source /opt/ros/jazzy/setup.bash"
    echo "  source ~/turtlebot3_ws/install/setup.bash    # TB3 표준 워크스페이스 먼저 source"
    echo "  colcon build --symlink-install --packages-up-to hyper_turtle_bringup"
    echo ""
    echo "로봇에서 실물 launch 실행 (PC와 ROS 통신용 환경변수 포함):"
    echo "  export ROS_DOMAIN_ID=30"
    echo "  export ROS_STATIC_PEERS=172.21.7.227    # PC 주소"
    echo "  export TURTLEBOT3_MODEL=burger"
    echo "  source install/setup.bash"
    echo "  ros2 launch hyper_turtle_bringup burger_real.launch.py"
else
    echo ""
    echo "=> 전송 실패! 로봇의 전원, 네트워크 연결 및 SSH 설정을 확인해주세요."
fi
