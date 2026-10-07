# 마음장부 (004)

주고받은 경조사비를 사람별로 기록하고, 다가오는 경조사에 예전 기록을 참고할 수 있게 돕는 안드로이드 앱입니다.

- 설계 문서: [ideas/004-gyeongjosa-ledger](../../ideas/004-gyeongjosa-ledger/idea.md)
  - [화면설계](../../ideas/004-gyeongjosa-ledger/screens.md) · [기술 스택](../../ideas/004-gyeongjosa-ledger/tech-stack.md)
- 상태: **개발 1~3단계 완료 (장부 + 백업 + 엑셀·PDF)** — tech-stack.md 6장 개발 순서 기준
- 안드로이드 테스트 APK: [Releases → maeum-jangbu-apk](https://github.com/nada04601-pixel/AI-IDEA_LAB/releases/tag/maeum-jangbu-apk) (main 또는 `claude/**` 브랜치에 푸시하면 GitHub Actions가 자동 빌드)

## 실행

```bash
npm install
npm run dev       # 개발 서버 (http://localhost:5173) — 브라우저에서 화면 확인용
npm test          # 단위 테스트 (금액 표기, 장부 계산, 백업 암호화·합치기, 알림 일정, 엑셀·CSV 왕복)
npm run build     # 타입 검사 + 정적 빌드 → dist/
```

## 안드로이드 앱 (Capacitor)

앱 ID `kr.co.novalabs.maeumjangbu`. 003 마음기록의 안드로이드 설정을 복사해 이름만 바꿨습니다.

```bash
npm run android:sync                     # 앱용 웹 빌드 + android/ 동기화
cd android && ./gradlew assembleDebug    # 로컬 빌드 (Android SDK 필요)
```

- **인터넷 권한 없음.** 기록이 휴대폰 밖으로 나가지 않는다는 약속을 앱 권한으로 보장합니다 (tech-stack.md 1-1).
- 빌드: `.github/workflows/maeum-jangbu-apk.yml` → Actions 아티팩트 + Releases(`maeum-jangbu-apk`, 프리릴리스).
- 설치: 휴대폰에서 Releases의 `maeum-jangbu-debug.apk`를 내려받아 실행 → "출처를 알 수 없는 앱 설치" 허용.
- 서명: `android/app/debug.keystore` 고정 디버그 키(003과 같은 키)로 서명해 새 빌드를 덮어 설치할 수 있습니다. ⚠️ 디버그 전용. Play 스토어 출시용 키는 저장소에 넣지 않습니다.

## 구조

| 경로 | 내용 |
|---|---|
| `src/lib/types.ts` | 데이터 구조 (사람·행사·내역), 표시 이름 |
| `src/lib/db.ts` | IndexedDB(Dexie) 저장, 변경 시 "백업 이후 변경 건수" 증가 |
| `src/lib/money.ts` | 금액 표기 (`10만` / `100,000원` / `10만원`), 금액 입력 해석 |
| `src/lib/ledger.ts` | 사람별·행사별 합계, 차이 문구, 기록 참고, 다가오는/기록이 비어 있는 경조사 |
| `src/lib/backup.ts` · `crypto.ts` | 백업 파일 형식, 비밀번호 암호화(PBKDF2 + AES-GCM), 합치기·동명이인 확인, 백업 상태 |
| `src/lib/notifySchedule.ts` · `notify.ts` | 경조사 D-day·백업(30일) 알림 일정 계산 / 기기 예약 |
| `src/lib/sheet.ts` | 내보내기 표 (전체 내역·사람별 장부·행사별 명단), 범위, CSV 쓰기·읽기 |
| `src/lib/excel.ts` | ExcelJS로 엑셀 만들기·읽기 (내보내기·가져오기 화면에서만 불러옴, 약 930KB) |
| `src/lib/importData.ts` | 엑셀·CSV 표 → 장부 데이터 (흔한 열 이름 인식, 읽을 수 없는 줄 안내) |
| `src/lib/print.ts` | PDF 명단 인쇄 (웹: `window.print()`, 앱: `WebPrintPlugin`) |
| `src/lib/share.ts` | 파일(글자·엑셀)을 만들어 공유 창 띄우기 (앱) / 다운로드 (웹) |
| `src/pages/` | 화면 (screens.md S-01 ~ S-13) |

## 구현 범위

| 화면 | 상태 |
|---|---|
| S-01 첫 실행 안내 | ✅ 3장, "무엇부터 할까요?"에서 바로 이동 |
| S-02 홈 | ✅ 백업 카드(없음/30일 경과/최근), 다가오는 경조사, 기록이 비어 있는 경조사([기록 안 함]), 최근 기록 |
| S-03 / S-04 사람 | ✅ 검색·관계 필터·정렬, 사람별 받음·보냄·차이, 편집·합치기·삭제 |
| S-05 / S-06 행사 | ✅ 내 행사 합계·감사 인사 체크, 상대 행사 D-day·기록 참고, [기록 안 함] |
| S-07 내역 입력 | ✅ 행사 종류 직접 입력(칠순·집들이 등, 최근 입력 버튼), 이름 자동 완성, 기록 참고, 금액 빠른 선택(만원 단위 직접 입력), 상대 경조사 등록 모드 |
| S-08 빠른 연속 입력 | ✅ [저장하고 다음]으로만 저장, 관계·방식 유지, 동명이인 확인, 20건 이상 입력 시 백업 제안 |
| S-09 / S-10 사진으로 등록 | ⏳ 안내 화면만 (개발 4단계, OCR 사전 테스트 후) |
| S-11 내보내기·백업 | ✅ 원탭 백업, 비밀번호(선택), 비밀번호 없이 공유 시 매번 안내 |
| 엑셀·CSV·PDF 내보내기 | ✅ 엑셀 3종 시트(금액 숫자 서식·틀 고정·필터·합계 행), CSV(BOM), 범위(전체·행사·기간·사람), A4 답례 명단 PDF, 매번 공유 안내 |
| S-12 가져오기·복원 | ✅ 백업·엑셀·CSV, 미리보기, 합치기/덮어쓰기, 이름·소속 같으면 자동 연결, 동명이인 확인(한꺼번에 답하기), 읽을 수 없는 줄 안내, 엑셀 양식 받기, 덮어쓰기 되돌리기 |
| S-13 설정 | ✅ 경조사 알림(시점·시각), 백업 알림, 글자 크기, 새 휴대폰으로 옮기기, 전체 삭제 |

## 남은 일

- [ ] 실제 기기 확인 (안드로이드): 백업 공유 → 내 파일 저장 → 다른 휴대폰에서 복원 왕복, 비밀번호 백업 처리 시간
- [ ] 실제 기기 확인 (안드로이드): 경조사 알림·백업 알림이 정한 시각에 오는지, 알림을 누르면 해당 화면이 열리는지
- [x] 3단계: 엑셀(ExcelJS)·CSV 내보내기·가져오기, PDF 답례 명단 (003 `WebPrintPlugin` 사용)
- [ ] 실제 기기 확인 (안드로이드): 엑셀 공유 → 휴대폰 엑셀·구글 시트에서 열림, PDF 명단 저장 (A4, 한글, 버튼 안 보임)
- [ ] 4단계: OCR 사전 테스트(tech-stack.md 4장) → 사진으로 등록
- [ ] 5단계: 연락처 불러오기
