#!/usr/bin/env bash
# 老的启动方式不变：./run.sh 或 make backend。
# 需要换端口时 PORT=9000 ./run.sh，就绪探测会跟着同一份配置走。
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install -q -r requirements.txt
PORT="${PORT:-8000}"
export APP_PORT="$PORT"
exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$PORT"
