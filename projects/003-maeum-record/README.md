# 마음기록 (003 프로토타입)

하루 한 번 기분을 기록하고, 그 기록을 들고 첫 진료·상담까지 갈 수 있게 돕는 PWA 프로토타입입니다.

- 설계 문서: [ideas/003-depression-support](../../ideas/003-depression-support/idea.md)
  - [화면설계](../../ideas/003-depression-support/screens.md) · [기술 스택](../../ideas/003-depression-support/tech-stack.md)
- 상태: **프로토타입 (기록 → 달력 → 리포트 흐름 동작)**

## 실행

```bash
npm install
npm run dev       # 개발 서버 (http://localhost:5173)
npm test          # 단위 테스트 (요약 계산, 날짜, 백업)
npm run build     # 정적 빌드 → dist/
npm run preview   # 빌드 결과 확인 (PWA 서비스 워커 포함)
```

휴대폰에서 확인하려면 같은 와이파이에서 `npm run dev -- --host`로 띄운 뒤 표시되는 주소로 접속합니다.
홈 화면 설치·오프라인 동작은 HTTPS가 필요하므로 정적 호스팅에 배포한 뒤 확인합니다.

## 스택

Vue 3 + Vite + TypeScript · vue-router (hash) · vite-plugin-pwa · Dexie (IndexedDB) · Vitest

- 모든 기록은 **기기 IndexedDB에만** 저장합니다. 서버·외부 전송 없음.
- 리포트 PDF는 인쇄용 CSS + `window.print()`로 만듭니다.

## 구현 범위

| 화면 | 상태 |
|---|---|
| S-01 첫 실행 안내 | ✅ (알림은 "앱 출시 후 제공" 표시) |
| S-02 홈 (오늘 기록) | ✅ 기분·메모·태그, 오늘 기록 목록, "아주 힘듦" 안내 한 줄 |
| S-03 기록 달력 | ✅ 월 이동, 날짜별 기록 보기·추가·수정·삭제 |
| S-04 진료 준비하기 | ✅ 기간 선택, 요약, 하고 싶은 말 자동 저장, 질문 예시 |
| S-05 진료용 리포트 | ✅ 메모 포함 토글, A4 한 장 PDF |
| S-06/07 가이드 | 🟡 목록·상세 틀 (본문은 1개만, 나머지 "준비 중") |
| S-08 도움받을 곳 | 🟡 바로 전화 (번호·운영시간 **출시 전 공식 확인 필요**) |
| S-09 설정 | ✅ 백업 내보내기/불러오기(합치기·덮어쓰기), 전체 삭제, 안내 다시 보기 |

## 남은 일

- [ ] 도움받을 곳 번호·운영시간 공식 출처 확인 (`src/content/help.ts`)
- [ ] 가이드 본문 6개 작성 및 출처·기준일 표기 (`src/content/guides.ts`)
- [ ] iOS용 PNG 아이콘 (apple-touch-icon은 PNG 권장, 현재 SVG)
- [ ] 실제 기기 확인: iOS 홈 화면 PWA에서 `window.print()` 동작, 오프라인 실행
- [ ] 정적 호스팅 배포 후 테스트 사용자 모집
