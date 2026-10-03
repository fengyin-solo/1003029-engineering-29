#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install -q -r requirements.txt
# 监听地址可用 APP_HOST/APP_PORT 覆盖（换机器部署时与就绪探测的配置对齐），默认值不变
exec .venv/bin/uvicorn app.main:app --host "${APP_HOST:-127.0.0.1}" --port "${APP_PORT:-8000}"
