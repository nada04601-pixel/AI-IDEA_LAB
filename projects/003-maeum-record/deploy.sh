#!/usr/bin/env bash
# GitHub Pages(gh-pages 브랜치)로 배포한다.
# 배포 주소: https://nada04601-pixel.github.io/AI-IDEA_LAB/
set -euo pipefail
cd "$(dirname "$0")"
REMOTE=$(git -C ../.. remote get-url origin)
npm run build
touch dist/.nojekyll
TMP=$(mktemp -d)
cp -r dist/. "$TMP"
# 같은 gh-pages에 있는 005 떡상 쇼츠(shorts/, 1시간마다 자동 갱신)는 그대로 둔다
if git -C ../.. fetch -q "$REMOTE" gh-pages; then
  git -C ../.. archive FETCH_HEAD shorts 2>/dev/null | tar -x -C "$TMP" || true
fi
cd "$TMP"
git init -q -b gh-pages
git add -A
git commit -qm "deploy: maeum-record $(date +%Y-%m-%d)"
git push -q -f "$REMOTE" gh-pages
echo "배포 완료: https://nada04601-pixel.github.io/AI-IDEA_LAB/ (반영까지 1~2분)"
