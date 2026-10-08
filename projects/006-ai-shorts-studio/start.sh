#!/usr/bin/env bash
# AI Shorts Studio 개발 서버 실행 (macOS·Linux, Windows는 Git Bash 또는 WSL)
# - 처음 실행하면 백엔드 가상환경과 프런트엔드 패키지를 설치한다.
# - 백엔드 http://localhost:8000, 프런트엔드 http://localhost:3000
# - Ctrl+C로 둘 다 종료한다.
set -euo pipefail
cd "$(dirname "$0")"

need() { command -v "$1" >/dev/null 2>&1 || { echo "❌ $1 이(가) 필요합니다. $2"; exit 1; }; }
need python3 "Python 3.11 이상을 설치하세요."
need npm "Node.js 20 이상을 설치하세요."
command -v ffmpeg >/dev/null 2>&1 || echo "⚠️  FFmpeg가 없습니다. 영상 생성과 MP4 렌더링만 안 되고 나머지는 동작합니다."

if [ ! -x backend/.venv/bin/python ]; then
  echo "▶ 백엔드 가상환경 만들기"
  python3 -m venv backend/.venv
  backend/.venv/bin/pip install -q -r backend/requirements-dev.txt
fi
if [ ! -d frontend/node_modules ]; then
  echo "▶ 프런트엔드 패키지 설치"
  (cd frontend && npm install --no-audit --no-fund)
fi

pids=()
cleanup() { trap - INT TERM EXIT; kill "${pids[@]}" 2>/dev/null || true; wait 2>/dev/null || true; }
trap cleanup INT TERM EXIT

(cd backend && exec .venv/bin/python -m uvicorn app.main:app --reload --port 8000) &
pids+=($!)
(cd frontend && exec npm run dev -- -p 3000) &
pids+=($!)

echo "✅ 브라우저에서 http://localhost:3000 을 여세요. (종료: Ctrl+C)"
wait -n "${pids[@]}"
