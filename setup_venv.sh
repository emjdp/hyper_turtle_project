#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "error: $PYTHON_BIN not found"
  exit 1
fi

echo "=> Creating Python virtual environment at $VENV_DIR"
"$PYTHON_BIN" -m venv --system-site-packages "$VENV_DIR"

echo "=> Installing pip dependencies from requirements-dev.txt"
source "$VENV_DIR/bin/activate"
python -m pip install -r requirements-dev.txt

echo "=> Verifying Python dependencies"
python - <<'PY'
import pygame

print(f"pygame {pygame.version.ver}")
PY

if [ -f /opt/ros/jazzy/setup.bash ]; then
  echo "=> Verifying ROS Python imports"
  set +u
  source /opt/ros/jazzy/setup.bash
  set -u
  python - <<'PY'
import rclpy
from sensor_msgs.msg import Joy

print("ROS Python imports OK")
PY
else
  echo "warning: /opt/ros/jazzy/setup.bash not found; skipping ROS Python import check"
fi

echo "=== .venv setup complete ==="
echo "Activate for development:"
echo "source /opt/ros/jazzy/setup.bash"
echo "source .venv/bin/activate"
