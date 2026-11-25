#!/bin/bash
# 처음 한 번: 두 서버 가상환경 + 패키지 설치, server/.env 만들기
set -e
cd "$(dirname "$0")/.."
[ -f "$HOME/.local/bin/env" ] && source "$HOME/.local/bin/env"
for d in match-server server; do
  echo "== $d 설치 =="
  (cd "$d" && { [ -d .venv ] || uv venv -q -p 3.12; } && uv pip install -q -r requirements.txt --python .venv/bin/python)
done
if [ -f server/.env ]; then
  echo "server/.env 이미 있음 (그대로 둠)"
else
  python3 scripts/make_server_env.py
fi
echo "✅ 설정 끝"
