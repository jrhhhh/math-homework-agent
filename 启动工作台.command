#!/bin/bash
cd "$(dirname "$0")" || exit 1

PORT=8765
if command -v lsof >/dev/null 2>&1 && lsof -iTCP:$PORT -sTCP:LISTEN >/dev/null 2>&1; then
  open "http://127.0.0.1:$PORT/"
  exit 0
fi

if command -v python3 >/dev/null 2>&1; then
  exec python3 run.py --open
fi

echo "未找到 python3。请先安装 Python 3.10 或以上。"
read -r
