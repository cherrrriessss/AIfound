#!/bin/bash
# 사용: bash scripts/run.sh match   (8000)  |  bash scripts/run.sh server  (8001)
cd "$(dirname "$0")/.."
if [ "$1" = "match" ]; then dir=match-server; port=8000; else dir=server; port=8001; fi
if lsof -nP -iTCP:$port -sTCP:LISTEN >/dev/null 2>&1; then
  echo "✅ $dir 는 이미 켜져 있어요 (포트 $port). 다른 창에서 실행 중인 걸 그대로 씁니다."
  exit 0
fi
cd "$dir" && exec .venv/bin/uvicorn app.main:app --reload --reload-dir app --host 0.0.0.0 --port $port
