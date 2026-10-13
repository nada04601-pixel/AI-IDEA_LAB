#!/usr/bin/env bash
# macOS / Linux 처음 설정.  사용법: ./scripts/setup.sh [--youtube]
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
if [[ "${1:-}" == "--youtube" ]]; then .venv/bin/pip install -r requirements-youtube.txt
else .venv/bin/pip install -r requirements-dev.txt; fi
[[ -f .env ]] || { cp .env.example .env; echo ".env 를 만들었습니다"; }
command -v ffmpeg >/dev/null || echo "FFmpeg가 없습니다. macOS: brew install ffmpeg / Ubuntu: sudo apt install ffmpeg"
.venv/bin/python main.py doctor
