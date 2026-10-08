# 006. 새 글 알림기 — 목록 인식·새 글 판단 엔진

설계 문서: [ideas/006-new-post-alert](../../ideas/006-new-post-alert/idea.md)

게시판 URL에서 글 목록을 자동으로 찾고, 지난번과 비교해 새 글(또는 키워드가 맞는 새 글)을 골라낸다. 의존성 없음 (Node 22).

## 실행

```bash
# 인식 테스트: 어떤 글을 목록으로 찾았는지 보여준다 (● = 키워드 일치)
node scripts/check.mjs https://www.nonsan.go.kr/public/html/sub04/040102.html --include 수영,결원

# 새 글 확인: 첫 실행은 기준선 저장, 이후엔 새 글만 출력
node scripts/check.mjs <URL> --include 수영,결원 --exclude 마감 --state state.json

# 저장한 HTML로 테스트 (URL은 링크 기준 주소로만 쓴다)
node scripts/check.mjs <URL> --file page.html

npm test
```

## 동작

- **목록 찾기:** 같은 위치 구조를 가진 링크 묶음 중 개수·제목 길이·날짜 비율이 높은 것을 고른다. 메뉴(gnb/lnb)·꼬리말·페이지 번호 영역은 점수를 크게 깎는다.
- **글 구분 키:** 링크 주소(페이지 번호·정렬 값 제거) → `javascript:fnView('123')` 인자 → 글 번호 → 제목+날짜 순.
- **새 글:** 저장된 키에 없는 글만. 제목 수정, 공지 순서 변경, 아래 글이 다음 쪽으로 밀려나는 것은 새 글이 아니다.
- **키워드:** 포함 키워드 중 하나라도 있으면 일치, 제외 키워드가 있으면 불일치. 띄어쓰기·대소문자 무시.
- 목록을 못 찾으면 페이지 안 iframe 주소를 알려준다.
- 문자 인코딩: 응답 헤더 또는 `<meta charset>` (EUC-KR 지원).
