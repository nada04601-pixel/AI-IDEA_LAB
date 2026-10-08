#!/usr/bin/env bash
# 앱에 들어가면 안 되는 권한 검사 (tech-stack.md 1-1)
#   인터넷·네트워크 상태: 기록을 밖으로 보내지 않는다는 약속
#   카메라: 촬영은 기본 카메라 앱이 하므로 필요 없음
#   정확한 알람: 알림은 정확한 시각이 필요 없음 (Play 정책 대상 권한)
# 사용: scripts/check-permissions.sh <app.apk | 병합된 AndroidManifest.xml>
set -euo pipefail
target="${1:?APK 또는 AndroidManifest.xml 경로가 필요해요}"
[ -f "$target" ] || { echo "::error::검사할 파일이 없어요: $target"; exit 1; }

if [[ "$target" == *.apk ]]; then
  AAPT2="$(ls -d "$ANDROID_HOME"/build-tools/*/ | sort -V | tail -1)aapt2"
  perms="$("$AAPT2" dump permissions "$target" | grep -o "name='[^']*'" | tr -d "'" | sed 's/^name=//')"
else
  perms="$(grep -o '<uses-permission[^>]*' "$target" | grep -v 'tools:node="remove"' | grep -o 'android:name="[^"]*"' | sed 's/android:name="//; s/"$//')"
fi
echo "권한 목록:"
echo "$perms" | sed 's/^/  /'

bad="$(echo "$perms" | grep -E '^android\.permission\.(INTERNET|ACCESS_NETWORK_STATE|CAMERA|SCHEDULE_EXACT_ALARM|USE_EXACT_ALARM)$' || true)"
if [ -n "$bad" ]; then
  echo "::error::들어가면 안 되는 권한이 있어요: $(echo $bad) — AndroidManifest.xml의 tools:node=\"remove\"를 확인하세요."
  exit 1
fi
echo "확인 완료: 인터넷·카메라·정확한 알람 권한 없음"
