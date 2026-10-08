# 마음기록 (003 프로토타입)

하루 한 번 기분을 기록하고, 그 기록을 들고 첫 진료·상담까지 갈 수 있게 돕는 PWA 프로토타입입니다.

- 설계 문서: [ideas/003-depression-support](../../ideas/003-depression-support/idea.md)
  - [화면설계](../../ideas/003-depression-support/screens.md) · [기술 스택](../../ideas/003-depression-support/tech-stack.md)
- 상태: **프로토타입 (기록 → 달력 → 리포트 흐름 동작)**
- 테스트 주소: https://nada04601-pixel.github.io/AI-IDEA_LAB/ (GitHub Pages, `gh-pages` 브랜치)
- 안드로이드 테스트 APK: [Releases → maeum-record-apk](https://github.com/nada04601-pixel/AI-IDEA_LAB/releases/tag/maeum-record-apk) (main에 푸시하면 GitHub Actions가 자동 빌드)

## 실행

```bash
npm install
npm run dev       # 개발 서버 (http://localhost:5173)
npm test          # 단위 테스트 (요약 계산, 날짜, 백업)
npm run build     # 정적 빌드 → dist/
npm run preview   # 빌드 결과 확인 (PWA 서비스 워커 포함)
npm run deploy    # GitHub Pages로 수동 배포 (gh-pages 브랜치 강제 갱신, 005의 shorts/ 폴더는 유지)
```

`main`에 003 웹 코드가 바뀌어 푸시되면 `.github/workflows/maeum-record-web.yml`이 자동으로 배포합니다. (Actions → 마음기록 웹 배포 → Run workflow로 수동 실행도 가능)

같은 gh-pages에 005 떡상 쇼츠(`/shorts/`)가 함께 올라갑니다. 서비스 워커는 `/shorts/` 접속을 가로채지 않도록 설정되어 있습니다.

휴대폰에서 확인하려면 같은 와이파이에서 `npm run dev -- --host`로 띄운 뒤 표시되는 주소로 접속합니다.
홈 화면 설치·오프라인 동작은 HTTPS가 필요하므로 정적 호스팅에 배포한 뒤 확인합니다.

## 안드로이드 앱 (Capacitor)

같은 웹 코드를 Capacitor로 감싼 안드로이드 앱입니다. (`android/`, 앱 ID `kr.co.novalabs.maeumrecord`)

```bash
npm run android:sync   # 앱용 웹 빌드(서비스 워커 제외) + android/ 동기화
cd android && ./gradlew assembleDebug   # 로컬 빌드 (Android SDK 필요)
```

- **인터넷 권한 없음.** 앱이 외부와 통신할 수 없으므로 "기록을 서버로 보내지 않아요"가 앱 권한으로 보장됩니다.
- 빌드는 `.github/workflows/maeum-record-apk.yml`이 담당합니다. 결과는 Actions 아티팩트와 Releases(`maeum-record-apk`, 프리릴리스)에 올라갑니다.
- 설치: 휴대폰에서 Releases의 `maeum-record-debug.apk`를 내려받아 실행 → "출처를 알 수 없는 앱 설치" 허용.
- 서명: `android/app/debug.keystore` 고정 키로 서명해서 새 빌드를 덮어 설치(업데이트)할 수 있습니다. 버전은 `0.1.<Actions 실행 번호>`로 빌드마다 올라가며, 앱 설정 맨 아래에 표시됩니다.
  - ⚠️ 이 키는 디버그 전용이며 공개 저장소에 있습니다. Play 스토어 출시용 키는 저장소에 넣지 않습니다.
  - 2026-10-07 14시 이전 빌드는 빌드마다 서명 키가 달라 업데이트가 안 됩니다. 이 경우 한 번만 기존 앱을 삭제하고 다시 설치해야 합니다.

**기록 알림 (앱 전용).** `@capacitor/local-notifications`로 기기에서 예약합니다. 서버가 필요 없습니다.
- 하루 1회, 정한 시각에만 보냅니다. 그날 이미 기록했으면 보내지 않습니다 (`src/lib/reminderSchedule.ts`).
- 앱을 열거나 기록할 때마다 30일치를 다시 예약합니다. 앱을 30일 넘게 열지 않으면 알림이 멈춥니다 (독촉하지 않기).
- 첫 실행 안내 3번째 장과 설정에서 켜고 끌 수 있습니다.

**백업 (앱).** 백업 파일을 앱 임시 폴더에 만든 뒤 공유 창을 띄웁니다. 저장할 곳(내 파일, 드라이브, 나에게 보내기 등)은 사용자가 고릅니다. 앱은 인터넷 권한이 없어 스스로 파일을 보내지 않습니다.
- 설정에 "마지막 백업: N일 전" 표시. 마지막 백업(없으면 첫 기록) 후 30일이 지나면 홈 아래에 한 줄로 권유합니다.

**리포트 PDF (앱).** 앱 안의 작은 플러그인(`android/.../WebPrintPlugin.java`)이 현재 화면을 안드로이드 기본 인쇄 화면으로 넘깁니다. 인쇄 화면에서 "PDF로 저장"을 고르면 웹과 같은 A4 리포트가 PDF로 저장됩니다 (인쇄용 CSS 동일 적용, 인터넷 불필요).

## 스택

Vue 3 + Vite + TypeScript · vue-router (hash) · vite-plugin-pwa · Dexie (IndexedDB) · Vitest

- 모든 기록은 **기기 IndexedDB에만** 저장합니다. 서버·외부 전송 없음.
- 리포트 PDF는 인쇄용 CSS + 인쇄 화면으로 만듭니다 (웹: `window.print()`, 앱: `WebPrint` 플러그인, `src/lib/print.ts`).

## 구현 범위

| 화면 | 상태 |
|---|---|
| S-01 첫 실행 안내 | ✅ 앱: 알림 시간 선택·켜기 / 웹: "앱에서 제공" 안내 |
| S-02 홈 (오늘 기록) | ✅ 기분·메모·태그, 오늘 기록 목록, "아주 힘듦" 안내 한 줄 |
| S-03 기록 달력 | ✅ 월 이동, 날짜별 기록 보기·추가·수정·삭제 |
| S-04 진료 준비하기 | ✅ 기간 선택, 요약, 하고 싶은 말 자동 저장, 질문 예시 |
| S-05 진료용 리포트 | ✅ 메모 포함 토글, A4 한 장 PDF |
| S-06/07 가이드 | 🟡 목록·상세 틀 (본문은 1개만, 나머지 "준비 중") |
| S-08 도움받을 곳 | ✅ 바로 전화 (109, 1577-0199 — 2026-10-07 보도·서울시 안내로 확인) |
| S-09 설정 | ✅ 알림(앱), 백업 내보내기(앱: 공유 창)/불러오기(합치기·덮어쓰기), 마지막 백업 표시, 전체 삭제 |

## 남은 일

- [x] 도움받을 곳 번호·운영시간 확인 (2026-10-07). 정식 출시 전 보건복지부 공식 안내로 재확인
- [ ] 가이드 본문 6개 작성 및 출처·기준일 표기 (`src/content/guides.ts`)
- [x] iOS용 PNG 아이콘
- [ ] 실제 기기 확인 (안드로이드): 리포트 PDF 저장 (A4 한 장, 한글 정상, 헤더·버튼 안 보임)
- [ ] 실제 기기 확인 (안드로이드): 백업 공유 → 내 파일 저장 → 불러오기 왕복
- [ ] 실제 기기 확인 (안드로이드): 알림이 정한 시각에 오는지, 재부팅 후에도 오는지, 기록한 날은 안 오는지
- [ ] 실제 기기 확인: iOS 홈 화면 PWA에서 `window.print()` 동작, 오프라인 실행
- [x] GitHub Pages 배포
- [ ] 테스트 사용자 모집
