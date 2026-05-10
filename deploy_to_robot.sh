#!/bin/bash
# deploy_to_robot.sh
# 개발 환경의 소스 코드를 로봇 보드(Raspberry Pi 등 SBC)로 업로드(동기화)하는 스크립트

# 사용법: ./deploy_to_robot.sh [로봇_IP] [사용자명] [원격_작업_폴더]
# 예시: ./deploy_to_robot.sh 192.168.0.100 ubuntu ~/hyper_Turtle_Project

# 매개변수 설정 및 기본값
ROBOT_IP=${1:-"192.168.0.100"}   # 실제 로봇의 IP 주소로 변경하세요.
ROBOT_USER=${2:-"ubuntu"}        # 실제 로봇의 SSH 계정명으로 변경하세요.
TARGET_DIR=${3:-"~/hyper_Turtle_Project"}

echo "=== 로봇(SBC) 보드 코드 업로드 스크립트 ==="
echo "대상 로봇 IP : $ROBOT_IP"
echo "계정 이름    : $ROBOT_USER"
echo "대상 디렉토리: $TARGET_DIR"
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
    --exclude='bags/' \
    --exclude='build/' \
    --exclude='install/' \
    --exclude='log/' \
    --exclude='maps/' \
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
    echo "  colcon build --symlink-install"
else
    echo ""
    echo "=> 전송 실패! 로봇의 전원, 네트워크 연결 및 SSH 설정을 확인해주세요."
fi
