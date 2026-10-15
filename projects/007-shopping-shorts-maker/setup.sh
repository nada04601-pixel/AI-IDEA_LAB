#!/usr/bin/env bash
# 쇼핑 쇼츠 메이커 설치 (Mac/Linux). 여러 번 실행해도 안전하다.
# 옵션: --cpu (GPU가 있어도 CPU용 PyTorch), --reinstall-torch
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(pwd)"
VENV_PY="$ROOT/.venv/bin/python"
FORCE_CPU=0; REINSTALL=0
for arg in "$@"; do
  case "$arg" in
    --cpu) FORCE_CPU=1 ;;
    --reinstall-torch) REINSTALL=1 ;;
  esac
done
info() { printf '\033[36m%s\033[0m\n' "$1"; }
ok() { printf '  \033[32m[완료]\033[0m %s\n' "$1"; }
warn() { printf '  \033[33m[주의]\033[0m %s\n' "$1"; }
die() { printf '\n\033[31m[오류]\033[0m %s\n\n' "$1"; exit 1; }
pip_install() { "$VENV_PY" -m pip install --disable-pip-version-check "$@" || die "패키지 설치 실패: pip install $*"; }

info "[1/7] Python 확인"
BASE_PY=""
for c in python3.12 python3.11 python3; do
  if command -v "$c" >/dev/null 2>&1; then
    v=$("$c" -c 'import sys; print("%d.%d" % sys.version_info[:2])')
    if [ "$v" = "3.12" ] || [ "$v" = "3.11" ]; then BASE_PY="$c"; break; fi
  fi
done
[ -n "$BASE_PY" ] || die "Python 3.12(또는 3.11)이 필요합니다. (Mac: brew install python@3.12)"
ok "Python $v ($(command -v "$BASE_PY"))"

info "[2/7] 가상환경(.venv)"
if [ ! -x "$VENV_PY" ]; then "$BASE_PY" -m venv .venv; ok "새로 만듦"; else ok "이미 있음"; fi
"$VENV_PY" -m pip install --disable-pip-version-check -q --upgrade pip

info "[3/7] GPU 확인 및 PyTorch 설치"
HAS_GPU=0
if [ "$FORCE_CPU" = 0 ] && command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L >/dev/null 2>&1; then
  HAS_GPU=1; ok "NVIDIA GPU: $(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)"
else
  warn "NVIDIA GPU를 쓰지 않습니다 → CPU 모드 (Mac은 CPU/Apple GPU)"
fi
STATE=$("$VENV_PY" -c "import torch; print('cuda' if torch.cuda.is_available() else 'cpu')" 2>/dev/null || echo none)
WANT=cpu; [ "$HAS_GPU" = 1 ] && WANT=cuda
if [ "$STATE" = "$WANT" ] && [ "$REINSTALL" = 0 ]; then
  ok "PyTorch 이미 설치됨 ($STATE)"
else
  [ "$STATE" != none ] && "$VENV_PY" -m pip uninstall -y -q torch torchvision
  if [ "$HAS_GPU" = 1 ]; then
    pip_install torch torchvision --index-url https://download.pytorch.org/whl/cu128 \
      || pip_install torch torchvision --index-url https://download.pytorch.org/whl/cu126
  elif [ "$(uname)" = "Darwin" ]; then
    pip_install torch torchvision
  else
    pip_install torch torchvision --index-url https://download.pytorch.org/whl/cpu
  fi
  ok "PyTorch 설치"
fi

info "[4/7] 필수·AI 패키지 설치"
pip_install -q -r requirements.txt -r requirements-ml.txt
pip_install -q --upgrade yt-dlp
"$VENV_PY" -m playwright install chromium || warn "브라우저(Chromium)를 받지 못했습니다. 나중에 .venv/bin/python -m playwright install chromium"
pip_install -q -e . --no-deps
ok "패키지 설치"

info "[5/7] FFmpeg 확인"
if command -v ffmpeg >/dev/null 2>&1; then ok "FFmpeg 있음"
elif [ "$(uname)" = "Darwin" ]; then warn "FFmpeg가 없습니다: brew install ffmpeg"
else warn "FFmpeg가 없습니다: sudo apt install ffmpeg (또는 배포판 패키지 매니저)"; fi

info "[6/7] 폰트 내려받기"
"$VENV_PY" -m ssm fonts || warn "폰트를 받지 못했습니다. 인터넷 연결 후 ./ssm fonts 를 실행하세요."

info "[7/7] 설치 점검 (ssm doctor)"
if "$VENV_PY" -m ssm doctor; then
  printf '\n\033[32m설치가 끝났습니다. 이 폴더에서 Claude Code를 열거나 ./ssm 으로 명령을 쓸 수 있습니다.\033[0m\n'
else
  die "점검에서 실패한 항목이 있습니다. 위 안내대로 고친 뒤 ./setup.sh를 다시 실행하세요."
fi
