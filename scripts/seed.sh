#!/bin/bash
# 더미 데이터. 분실자 메일은 scripts/demo_owner.txt 첫 줄
cd "$(dirname "$0")/.."
owner=$(head -n1 scripts/demo_owner.txt 2>/dev/null | tr -d '[:space:]')
if [ -z "$owner" ]; then echo "❌ scripts/demo_owner.txt 에 앱으로 로그인할 학교 메일을 적어 주세요"; exit 1; fi
cd match-server && .venv/bin/python tools/seed_demo.py --owner "$owner" "$@"
