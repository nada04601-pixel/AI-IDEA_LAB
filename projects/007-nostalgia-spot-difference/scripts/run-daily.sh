#!/usr/bin/env bash
# cron 에서 호출.  예) crontab -e 에 추가:
#   10 7 * * * /절대경로/007-nostalgia-spot-difference/scripts/run-daily.sh
set -uo pipefail
cd "$(dirname "$0")/.."
mkdir -p output/logs
.venv/bin/python main.py daily >> output/logs/scheduler.log 2>&1
