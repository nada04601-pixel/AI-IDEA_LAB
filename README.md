# AI-IDEA_LAB
개인 AI 아이디어 및 제품 개발 관리 저장소

## 💡 아이디어 및 프로젝트 현황

| 번호 | 프로젝트/아이디어명 | 진행 상태 | 바로 테스트 | 코드 저장소 | 설계 문서 |
|---|---|---|---|---|---|
| 001 | AI Excel 보고서 자동생성기 | **개발진행중 (Slice 0 완료)** | 로컬 `http://localhost:5173` ([방법](#001-ai-excel-보고서-자동생성기)) | [projects/001-ai-excel-report](projects/001-ai-excel-report) | [ideas/001-ai-excel-report](ideas/001-ai-excel-report/idea.md) |
| 002 | 노바랩 계산소 (novalabs.co.kr, 애드센스 수익형 계산기 사이트) | **개발진행중 (애드센스 신청 준비)** | 🌐 [novalabs.co.kr](https://novalabs.co.kr) | [novalabs-projects](https://github.com/nada04601-pixel/novalabs-projects) (별도 배포 저장소) | [README](https://github.com/nada04601-pixel/novalabs-projects#readme) |
| 003 | 마음기록 + 첫 진료 길잡이 (우울감 기록·진료 연결, A+C 통합안) | **프로토타입 (PWA, [테스트 링크](https://nada04601-pixel.github.io/AI-IDEA_LAB/))** | 🌐 [웹(PWA)](https://nada04601-pixel.github.io/AI-IDEA_LAB/) · 📱 [APK](https://github.com/nada04601-pixel/AI-IDEA_LAB/releases/tag/maeum-record-apk) | [projects/003-maeum-record](projects/003-maeum-record) | [ideas/003-depression-support](ideas/003-depression-support/idea.md) |
| 004 | 마음장부 (주고받은 경조사비 장부·사진 등록·백업) | **개발진행중 (MVP 구현 완료, 안드로이드 테스트 앱)** | 📱 [APK](https://github.com/nada04601-pixel/AI-IDEA_LAB/releases/tag/maeum-jangbu-apk) | [projects/004-maeum-jangbu](projects/004-maeum-jangbu) | [ideas/004-gyeongjosa-ledger](ideas/004-gyeongjosa-ledger/idea.md) |
| 005 | 오늘의 떡상 쇼츠 분석기 (급상승 쇼츠·키워드 순위) | **공개 페이지 (1시간마다 자동 수집, [링크](https://nada04601-pixel.github.io/AI-IDEA_LAB/shorts/))** | 🌐 [공개 페이지](https://nada04601-pixel.github.io/AI-IDEA_LAB/shorts/) · [직접 검색](https://nada04601-pixel.github.io/AI-IDEA_LAB/shorts/search.html) | [projects/005-shorts-trend](projects/005-shorts-trend) | [ideas/005-shorts-trend](ideas/005-shorts-trend/idea.md) |
| 006 | AI Shorts Studio (주제 → 대본·장면 생성 → 장면별 승인 → MP4 렌더링) | **MVP 완료 (1~5단계, mock 공급자 — 실제 AI 연결 전)** | 로컬 `http://localhost:3000` ([방법](#006-ai-shorts-studio)) | [projects/006-ai-shorts-studio](projects/006-ai-shorts-studio) | [ideas/006-ai-shorts-studio](ideas/006-ai-shorts-studio/idea.md) |
| 007 | 쇼핑 쇼츠 메이커 (해외 숏폼 링크 → 대본·TTS·자막 교체·컷 편집·썸네일 자동화) | **개발진행중 (M6 완료, v1 전 단계)** | 로컬 CLI `ssm` ([방법](#007-쇼핑-쇼츠-메이커)) | [projects/007-shopping-shorts-maker](projects/007-shopping-shorts-maker) | [ideas/007-shopping-shorts-maker](ideas/007-shopping-shorts-maker/idea.md) |
| 008 | 위탁판매 자동화 (도매매 → 스마트스토어 상품 등록·주문 자동 발주, 쿠팡 확장 예정) | **구상 단계 (프로토타입 CLI, 실제 키 검증 전)** | 로컬 CLI 미리 보기 ([방법](#008-위탁판매-자동화)) | [projects/008-dropship-automation](projects/008-dropship-automation) | [ideas/008-dropship-automation](ideas/008-dropship-automation/idea.md) |

## 🧪 바로 테스트해 보기

🌐 = 설치 없이 브라우저에서 바로 · 📱 = 안드로이드 휴대폰에 설치 · 💻 = 내 컴퓨터에서 실행

### 바로 열어 볼 수 있는 주소

| 번호 | 무엇을 | 주소 |
|---|---|---|
| 002 | 🌐 노바랩 계산소 (계산기 사이트) | https://novalabs.co.kr |
| 003 | 🌐 마음기록 웹앱 (PWA, 휴대폰에서 "홈 화면에 추가" 가능) | https://nada04601-pixel.github.io/AI-IDEA_LAB/ |
| 003 | 📱 마음기록 테스트 APK | https://github.com/nada04601-pixel/AI-IDEA_LAB/releases/tag/maeum-record-apk |
| 004 | 📱 마음장부 테스트 APK | https://github.com/nada04601-pixel/AI-IDEA_LAB/releases/tag/maeum-jangbu-apk |
| 005 | 🌐 오늘의 떡상 쇼츠 (공개 페이지, 1시간마다 갱신) | https://nada04601-pixel.github.io/AI-IDEA_LAB/shorts/ |
| 005 | 🌐 떡상 쇼츠 직접 검색 (내 YouTube API 키 또는 샘플 데이터) | https://nada04601-pixel.github.io/AI-IDEA_LAB/shorts/search.html |

> APK는 테스트용 디버그 빌드입니다. 휴대폰에서 Releases 페이지의 `.apk`를 내려받고 "출처를 알 수 없는 앱 설치"를 허용해야 설치됩니다. 설치된 버전은 앱 설정 화면 맨 아래에서 확인할 수 있습니다.

### 프로젝트별 테스트 항목

#### 001 AI Excel 보고서 자동생성기
- 💻 실행: `docker compose up -d`(DB) → `backend`에서 `./gradlew bootRun` → `frontend`에서 `npm install && npm run dev` → http://localhost:5173 (API는 http://localhost:8080)
- 지금은 Slice 0(준비)까지라 기능 화면은 아직 없습니다.
- [ ] 백엔드가 뜨고 DB 마이그레이션(Flyway)이 적용되는지
- [ ] http://localhost:5173 에서 빈 로그인 화면이 보이는지
- 자세한 시나리오: [test-plan.md](ideas/001-ai-excel-report/test-plan.md) · [실행 가이드](projects/001-ai-excel-report/README.md)

#### 002 노바랩 계산소
- 🌐 https://novalabs.co.kr
- [ ] PC·휴대폰에서 계산기별 입력 → 결과가 맞는지
- [ ] 화면 깨짐·느린 페이지 없는지 (애드센스 신청 전 점검)

#### 003 마음기록 + 첫 진료 길잡이
- 🌐 https://nada04601-pixel.github.io/AI-IDEA_LAB/ · 📱 [APK](https://github.com/nada04601-pixel/AI-IDEA_LAB/releases/tag/maeum-record-apk)
- [ ] 홈에서 오늘 기분·메모·태그 기록 → 달력에서 날짜별 보기·수정·삭제
- [ ] 진료 준비하기: 기간 선택 → 요약 → 진료용 리포트 → 인쇄/"PDF로 저장" (A4 한 장, 한글 정상)
- [ ] 도움받을 곳: 바로 전화 버튼 (109, 1577-0199)
- [ ] 백업 내보내기 → 다시 불러오기
- [ ] 휴대폰 "홈 화면에 추가" 후 인터넷 끊고 열리는지 (PWA)

#### 004 마음장부
- 📱 [APK](https://github.com/nada04601-pixel/AI-IDEA_LAB/releases/tag/maeum-jangbu-apk) (`main`·`claude/**` 브랜치에 푸시할 때마다 새로 빌드) · 💻 화면만 볼 때는 `npm run dev` → http://localhost:5173 (가짜 연락처)
- [ ] 경조사 주고받은 기록 추가·수정·삭제, 금액 합계
- [ ] 사진으로 등록
- [ ] 연락처에서 이름 불러오기 (1명 / 여러 명)
- [ ] 백업(암호) 내보내기·불러오기, 엑셀·CSV 내보내기
- [ ] 알림 설정

#### 005 오늘의 떡상 쇼츠 분석기
- 🌐 [공개 페이지](https://nada04601-pixel.github.io/AI-IDEA_LAB/shorts/) · [직접 검색](https://nada04601-pixel.github.io/AI-IDEA_LAB/shorts/search.html)
- [ ] 🇰🇷 한국 · 🌏 해외 · 📱 다른 플랫폼 탭 전환, 갱신 시각이 1시간 이내인지
- [ ] 키워드 순위 확인
- [ ] 아래 "URL로 썸네일·이미지 저장"에 유튜브 쇼츠 주소 넣어 썸네일 저장
- [ ] 직접 검색: 샘플 데이터 모드 → 내 API 키로 국가·기간·분야 검색

#### 006 AI Shorts Studio
- 💻 `cd projects/006-ai-shorts-studio && ./start.sh` (Windows: `start-windows.bat` 더블클릭) → http://localhost:3000 · API 문서 http://localhost:8000/docs
- 지금은 mock 공급자라 API 키 없이 전체 흐름을 볼 수 있습니다.
- [ ] 1단계 주제 입력 → 프로젝트 생성
- [ ] 2단계 대본·장면(스토리보드) 생성·수정
- [ ] 3단계 장면별 승인/재생성
- [ ] 4단계 렌더링 → MP4 내려받기
- 단계별 체크리스트: [README 수동 확인 체크리스트](projects/006-ai-shorts-studio/README.md) · [사용 가이드](projects/006-ai-shorts-studio/docs/user-guide.md)

#### 007 쇼핑 쇼츠 메이커
- 💻 `setup.bat`(Windows) 또는 `./setup.sh` 설치 → `ssm doctor` 실패 항목 0개 확인
- [ ] `ssm new <샤오홍슈·도우인 링크>` → `ssm collect`로 같은 상품 영상 수집
- [ ] `ssm script --preset 2` → Claude가 쓴 대본 `ssm script --check`
- [ ] `ssm run` → 완성 영상·썸네일 3안·플랫폼별 캡션 확인
- [ ] `ssm set subtitle.size 90` / `ssm cut 3` 후 다시 실행 → 바뀐 단계만 재실행, `ssm versions`로 버전 확인
- 자세한 사용법: [README](projects/007-shopping-shorts-maker/README.md)

#### 008 위탁판매 자동화
- 💻 `cd projects/008-dropship-automation && npm install` → `.env`·`config.json` 준비 (도매매·네이버 커머스API 키, 고정 IP 필요)
- 기본이 **미리 보기**라 `--live`를 붙이기 전에는 실제 등록·발주가 일어나지 않습니다.
- [ ] `npm run cli -- categories 텀블러` (스마트스토어 카테고리 찾기)
- [ ] `npm run cli -- search 텀블러` / `inspect <상품번호>` (도매매 검색·등록 가능 여부)
- [ ] `npm run cli -- register <상품번호> --category <ID>` (등록 미리 보기)
- [ ] `npm run cli -- orders` (발주 미리 보기)
- 키 없이 확인: `npm test && npm run typecheck`
