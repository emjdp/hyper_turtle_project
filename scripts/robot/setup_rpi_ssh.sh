#!/bin/bash
# ─────────────────────────────────────────
# 여기에 라즈베리파이5 정보를 입력하세요
RPI_IP="172.21.106.164"        # 예: 192.168.0.42
RPI_USER="ubuntu"      # 예: ubuntu
RPI_PASSWORD="${RPI_PASSWORD:-}"  # 최초 1회만 사용 (키 등록 후 불필요)
RPI_ALIAS="rpi5" # ssh rpi5 로 접속할 별칭
# ─────────────────────────────────────────

set -e

if [[ -z "$RPI_IP" || -z "$RPI_USER" ]]; then
    echo "오류: RPI_IP, RPI_USER 를 모두 입력하세요."
    exit 1
fi

if [[ -z "$RPI_PASSWORD" ]]; then
    read -r -s -p "Raspberry Pi password for ${RPI_USER}@${RPI_IP}: " RPI_PASSWORD
    echo ""
fi

# 1. SSH 키 생성 (없으면)
KEY_PATH="$HOME/.ssh/rpi5_key"
if [[ ! -f "$KEY_PATH" ]]; then
    echo "[1/3] SSH 키 생성 중..."
    ssh-keygen -t ed25519 -f "$KEY_PATH" -N "" -C "hyper_turtle_rpi5"
else
    echo "[1/3] 기존 키 재사용: $KEY_PATH"
fi

# 2. 공개키를 라즈베리파이에 등록 (비밀번호 1회 사용)
echo "[2/3] 공개키를 라즈베리파이에 등록 중..."
sshpass -p "$RPI_PASSWORD" ssh-copy-id \
    -i "${KEY_PATH}.pub" \
    -o StrictHostKeyChecking=no \
    "${RPI_USER}@${RPI_IP}"

# 3. ~/.ssh/config 에 Host 추가/갱신 (IP가 바뀌면 덮어씀)
CONFIG_FILE="$HOME/.ssh/config"
touch "$CONFIG_FILE"
if grep -q "^Host $RPI_ALIAS\$" "$CONFIG_FILE" 2>/dev/null; then
    echo "[3/3] ~/.ssh/config 의 '$RPI_ALIAS' 갱신 중 (IP=$RPI_IP)..."
    # 기존 'Host rpi5' 블록을 제거하고 새로 씀
    awk -v alias="$RPI_ALIAS" '
        $1=="Host" { inblock = ($2==alias) }
        !inblock { print }
    ' "$CONFIG_FILE" > "${CONFIG_FILE}.tmp"
    mv "${CONFIG_FILE}.tmp" "$CONFIG_FILE"
else
    echo "[3/3] ~/.ssh/config 에 '$RPI_ALIAS' 추가 중 (IP=$RPI_IP)..."
fi
cat >> "$CONFIG_FILE" <<EOF

Host $RPI_ALIAS
    HostName $RPI_IP
    User $RPI_USER
    IdentityFile $KEY_PATH
    ServerAliveInterval 30
    ServerAliveCountMax 3
EOF

echo ""
echo "완료! 이제 아래 명령으로 접속하세요:"
echo "  ssh $RPI_ALIAS"
