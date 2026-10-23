# AI-IDEA_LAB
개인 AI 아이디어 및 제품 개발 관리 저장소

## 💡 아이디어 및 프로젝트 현황

| 번호 | 프로젝트/아이디어명 | 진행 상태 | 바로 테스트 | 코드 저장소 | 설계 문서 |
|---|---|---|---|---|---|
| 001 | AI Excel 보고서 자동생성기 | **개발진행중 (Slice 0 완료, 화면 미리 보기는 mock으로 전체 흐름)** | 💻 로컬 `http://localhost:5173` ([방법](#001-ai-excel-보고서-자동생성기)) | [projects/001-ai-excel-report](projects/001-ai-excel-report) | [ideas/001-ai-excel-report](ideas/001-ai-excel-report/idea.md) |
| 002 | 노바랩 계산소 (novalabs.co.kr, 애드센스 수익형 계산기 사이트) | **개발진행중 (애드센스 신청 준비)** | 🌐 [novalabs.co.kr](https://novalabs.co.kr) | [novalabs-projects](https://github.com/nada04601-pixel/novalabs-projects) (별도 배포 저장소) | [README](https://github.com/nada04601-pixel/novalabs-projects#readme) |
| 003 | 마음기록 + 첫 진료 길잡이 (우울감 기록·진료 연결, A+C 통합안) | **프로토타입 (PWA·안드로이드 테스트 앱)** | 🌐 [웹(PWA)](https://nada04601-pixel.github.io/AI-IDEA_LAB/) · 📱 [APK](https://github.com/nada04601-pixel/AI-IDEA_LAB/releases/tag/maeum-record-apk) | [projects/003-maeum-record](projects/003-maeum-record) | [ideas/003-depression-support](ideas/003-depression-support/idea.md) |
| 004 | 마음장부 (주고받은 경조사비 장부·사진 등록·백업) | **개발진행중 (MVP 구현 완료, 안드로이드 테스트 앱)** | 📱 [APK](https://github.com/nada04601-pixel/AI-IDEA_LAB/releases/tag/maeum-jangbu-apk) | [projects/004-maeum-jangbu](projects/004-maeum-jangbu) | [ideas/004-gyeongjosa-ledger](ideas/004-gyeongjosa-ledger/idea.md) |
| 005 | 오늘의 떡상 쇼츠 분석기 (급상승 쇼츠·키워드 순위) | **공개 페이지 (1시간마다 자동 수집)** | 🌐 [공개 페이지](https://nada04601-pixel.github.io/AI-IDEA_LAB/shorts/) · [직접 검색](https://nada04601-pixel.github.io/AI-IDEA_LAB/shorts/search.html) | [projects/005-shorts-trend](projects/005-shorts-trend) | [ideas/005-shorts-trend](ideas/005-shorts-trend/idea.md) |
| 006 | AI Shorts Studio (주제 → 대본·장면 생성 → 장면별 승인 → MP4 렌더링) | **MVP 완료 (1~5단계, 기본 mock · 이미지 Gemini·영상 Veo 실제 연결 가능)** | 💻 로컬 `http://localhost:3000` ([방법](#006-ai-shorts-studio)) | [projects/006-ai-shorts-studio](projects/006-ai-shorts-studio) | [ideas/006-ai-shorts-studio](ideas/006-ai-shorts-studio/idea.md) |
| 007 | 쇼핑 쇼츠 메이커 (해외 숏폼 링크 → 대본·TTS·자막 교체·컷 편집·썸네일 자동화) | **개발진행중 (M6 완료, v1 전 단계)** | 💻 로컬 CLI `ssm` ([방법](#007-쇼핑-쇼츠-메이커)) | [projects/007-shopping-shorts-maker](projects/007-shopping-shorts-maker) | [ideas/007-shopping-shorts-maker](ideas/007-shopping-shorts-maker/idea.md) |
| 008 | 위탁판매 자동화 SaaS (도매매 → 스마트스토어 상품 등록·주문 자동 발주, 쿠팡 확장 예정) | **개발진행중 (SaaS로 결정, 웹 데모 공개 · 실제 키 검증 전)** | 🌐 [웹 데모](https://nada04601-pixel.github.io/AI-IDEA_LAB/dropship/) · 💻 CLI 샌드박스 ([방법](#008-위탁판매-자동화)) | [projects/008-dropship-automation](projects/008-dropship-automation) | [ideas/008-dropship-automation](ideas/008-dropship-automation/idea.md) |

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
| 008 | 🌐 위탁판매 자동화 웹 데모 (가짜 판매처·도매처, 키·가입 없이) | https://nada04601-pixel.github.io/AI-IDEA_LAB/dropship/ |

> APK는 테스트용 디버그 빌드입니다. 휴대폰에서 Releases 페이지의 `.apk`를 내려받고 "출처를 알 수 없는 앱 설치"를 허용해야 설치됩니다. 설치된 버전은 앱 설정 화면 맨 아래에서 확인할 수 있습니다.

### 프로젝트별 테스트 항목

#### 001 AI Excel 보고서 자동생성기
- 💻 화면만 볼 때: `frontend`에서 `npm install && npm run dev` → http://localhost:5173 (지금은 프런트엔드가 항상 mock 데이터로 동작해서 백엔드 없이 전체 흐름을 볼 수 있습니다)
- 💻 백엔드까지: `docker compose up -d`(DB) → `backend`에서 `./gradlew bootRun` (API는 http://localhost:8080)
- [ ] 로그인 → 새 작업 → 템플릿·데이터 업로드 → 데이터 확인 → 매핑 → 정규화 → 결과(샘플 보고서 .xlsx 내려받기)
- [ ] 작업 이력에서 지난 작업 다시 보기
- [ ] 백엔드가 뜨고 DB 마이그레이션(Flyway)이 적용되는지
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
- 기본은 mock 공급자라 API 키 없이 전체 흐름을 볼 수 있습니다. `.env`에 `AISS_IMAGE_PROVIDER=gemini`·`AISS_VIDEO_PROVIDER=gemini`와 `GEMINI_API_KEY`를 넣으면 실제 이미지(Gemini)·영상(Veo)을 만듭니다(유료).
- [ ] 1단계 주제 입력 → 프로젝트 생성
- [ ] 2단계 대본·장면(스토리보드) 생성·수정
- [ ] 3단계 장면별 승인/재생성
- [ ] 4단계 렌더링 → MP4 내려받기
- [ ] (선택, 유료) Gemini 이미지·Veo 영상으로 장면 1개 생성
- 단계별 체크리스트: [README 수동 확인 체크리스트](projects/006-ai-shorts-studio/README.md) · [사용 가이드](projects/006-ai-shorts-studio/docs/user-guide.md)

#### 007 쇼핑 쇼츠 메이커
- 💻 `setup.bat`(Windows) 또는 `./setup.sh` 설치 → `ssm doctor` 실패 항목 0개 확인
- [ ] `ssm new <샤오홍슈·도우인 링크>` → `ssm collect`로 같은 상품 영상 수집
- [ ] `ssm script --preset 2` → Claude가 쓴 대본 `ssm script --check`
- [ ] `ssm run` → 완성 영상·썸네일 3안·플랫폼별 캡션 확인
- [ ] `ssm set subtitle.size 90` / `ssm cut 3` 후 다시 실행 → 바뀐 단계만 재실행, `ssm versions`로 버전 확인
- 자세한 사용법: [README](projects/007-shopping-shorts-maker/README.md)

#### 008 위탁판매 자동화
- 🌐 [웹 데모](https://nada04601-pixel.github.io/AI-IDEA_LAB/dropship/) — 설치·키·가입 없이 브라우저에서 바로. 데이터는 그 브라우저에만 저장되고 실제 등록·주문·결제는 없습니다.
- [ ] ① 상품 소싱: **미리 보기** → 8개 중 5개 "등록 가능", 3개 "건너뜀"(최소 공급가·제외 낱말·재고) → **등록 실행**
- [ ] ② 판매 상품: 옵션·수량 골라 **주문 넣기** (결제 금액을 3000처럼 낮게 넣으면 역마진)
- [ ] ③ 주문 처리: **미리 보기** → **발주 실행** → 정상은 "발주 완료", 캠핑 텀블러는 "실패", 차량용은 "확인 필요", 역마진은 "보류"
- [ ] 보류 줄 **승인** → 다시 발주 실행 → 발주됨 / **취소 요청** 줄은 건너뜀 / ④ 도매처 주문서에서 고객 배송지로 들어간 주문 확인
- [ ] ① 상품 소싱에서 공급가·재고·"발주할 때"(거절·응답 없음)를 바꾸거나 설정에서 이익률·안전장치를 바꿔 판정이 달라지는지
- [ ] 새로 고침해도 그대로인지, **처음부터 다시**로 초기화되는지, 휴대폰 화면

💻 같은 흐름을 CLI로: `cd projects/008-dropship-automation && npm install` (Node.js 22.18 이상)

**키 없이 — CLI 샌드박스 (가짜 판매처·도매처, 데이터는 `data/sandbox/`에 따로)**
- [ ] `npm run sandbox -- source --live` → 상품 8개 중 5개 등록, 3개 건너뜀(최소 공급가·제외 낱말·재고)
- [ ] `npm run sandbox -- fake` → 등록 상품번호(9000001~) 확인
- [ ] `npm run sandbox -- fake order 9000001 --option 01 --qty 2` → `orders`(미리 보기) → `orders --live` → 발주·발주 확인, 다시 돌려도 중복 발주 없음
- [ ] 실패 상황: 9000003 주문(도매처 거절 → `failed`), 9000004 주문(응답 없음 → `unknown`), `--paid 3000`(역마진 보류), `fake cancel <줄번호>`(건너뜀) → `status`로 확인
- [ ] `data/sandbox/fake/catalog.json`에서 공급가 올리기 → 주문 → 보류 → `approve <줄번호>` → 발주
- [ ] 처음부터 다시: `npm run sandbox -- fake reset`
- `npm test && npm run typecheck`

**실제 키로 (M2, 아직 검증 전)** — `.env`·`config.json` 준비 (도매매·네이버 커머스API 키, 고정 IP 필요). 기본이 **미리 보기**라 `--live`를 붙이기 전에는 실제 등록·발주가 일어나지 않습니다.
- [ ] `npm run cli -- search 텀블러` / `inspect <상품번호>` (도매매 검색·등록 가능 여부, API 키만 있으면 됨)
- [ ] `npm run cli -- categories 텀블러` (스마트스토어 카테고리 찾기, 등록한 IP에서만)
- [ ] `npm run cli -- register <상품번호> --category <ID>` (등록 미리 보기)
- [ ] `npm run cli -- orders` (발주 미리 보기)
