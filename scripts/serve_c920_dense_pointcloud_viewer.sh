#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PYTHON_BIN="${PYTHON_BIN:-python3}"
PORT="${PORT:-8902}"
OUTPUT_DIR="${OUTPUT_DIR:-outputs/c920_dense_feature_depth_now}"

"$PYTHON_BIN" - <<'PY'
from __future__ import annotations

import os
from pathlib import Path
import signal

ports = {"8901", "8902", "8903"}
own = os.getpid()
parent = os.getppid()
for proc in Path("/proc").iterdir():
    if not proc.name.isdigit():
        continue
    pid = int(proc.name)
    if pid in {own, parent}:
        continue
    try:
        cmdline = (proc / "cmdline").read_bytes().decode("utf-8", errors="ignore").replace("\x00", " ")
    except Exception:
        continue
    if "http.server" not in cmdline:
        continue
    if any(f" {port} " in f" {cmdline} " for port in ports):
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"killed viewer server pid={pid}")
        except ProcessLookupError:
            pass
PY

if [ ! -f "$OUTPUT_DIR/index.html" ]; then
  echo "Dense pointcloud output missing; building it first..."
  scripts/build_c920_dense_feature_depth.sh
fi

setsid "$PYTHON_BIN" -m http.server "$PORT" --bind 127.0.0.1 --directory "$OUTPUT_DIR" \
  > "$OUTPUT_DIR/server.log" 2>&1 < /dev/null &
echo "$!" > "$OUTPUT_DIR/server.pid"

sleep 0.4
echo "C920 dense pointcloud viewer:"
echo "http://127.0.0.1:$PORT/index.html"
