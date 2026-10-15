# 007. 쇼핑 쇼츠 메이커 (Shopping Shorts Maker)

- 상태: **기획 (요구사항 v0.2, 미결정 사항 확인 중)**
- 프로젝트 코드: 아직 없음 (`projects/007-shopping-shorts-maker` 예정)
- 문서 버전: 0.2
- 작성일: 2026-10-15
- 프로젝트 유형: 개인용 CLI + Claude Code 대화형 자동화
- 목표: 해외 숏폼 링크 하나로 수집 → 대본 → TTS → 자막 제거·한국어 자막 → 컷 편집 → 썸네일·캡션까지 자동화
- 관련 아이디어:
  - [006 AI Shorts Studio](../006-ai-shorts-studio/idea.md) — FFmpeg 렌더링·자막(SRT)·TTS 어댑터 구조가 겹치므로 재사용 여부 검토 (10장 미결정 사항 7번)
  - [005 오늘의 떡상 쇼츠 분석기](../005-shorts-trend/idea.md) — 급상승 키워드를 상품 탐색·해시태그에 활용 가능

---

> **Claude를 위한 개발 지시서 (System Prompt for Claude / Claude Code)**
> 당신은 Python 기반의 미디어 처리 및 자동화 파이프라인 구축에 능숙한 시니어 AI 엔지니어입니다. 아래에 정의된 요구사항 정의서(PRD)와 아키텍처 가이드를 바탕으로 **'쇼핑 쇼츠 제작 올인원 자동화 프로그램'**을 단계별로 구현해 주세요. 외부 유료 API 과금을 최소화하고 로컬 오픈소스와 무료 도구를 최대한 활용하는 것이 핵심입니다.
>
> **구현 원칙**
> 1. 각 모듈은 독립 실행 가능한 CLI 서브커맨드로 만들고, 입출력은 모두 `workspace/{project_id}/` 안의 파일로 주고받는다. (모듈 간 메모리 공유 금지)
> 2. "판단(대본 작성·수정 의도 해석)"은 Claude가, "실행(다운로드·OCR·TTS·렌더링)"은 Python이 담당한다. → 2장 아키텍처 참고
> 3. 마일스톤(9장) 순서대로 구현하고, 각 마일스톤의 완료 기준(Acceptance Criteria)을 만족시킨 뒤 다음으로 넘어간다.

> **v0.1 → v0.2 변경 요약:** LLM 비용 구조 명시(아키텍처 신설), 데이터 스키마·config 예시 추가, 상품 일치성 검증·BGM/라우드니스·세이프존·자막 줄바꿈 규칙 보완, 한국인 '얼굴' 판별을 현실적인 신호(한글 OCR·한국어 음성·작성자 메타데이터)로 교체, 법적 고지/리스크, 에러 처리, 마일스톤·완료 기준, 미결정 사항 추가.

---

## 1. 프로젝트 개요
* **프로젝트명:** 쇼핑 쇼츠 메이커 (Shopping Shorts Maker)
* **목적:** 해외 숏폼(샤오홍슈, 도우인 등) 링크 하나만 입력하면 원본 영상 수집부터 대본 작성, TTS 더빙, 중국어 자막 제거, 한국어 자막 생성, 컷 편집, 썸네일/설명글 생성까지 전 과정을 자동화하는 CLI 및 대화형 에이전트 기반 프로그램 구축.
* **핵심 가치:** 건당 과금되는 외부 API 없이, 기존 Claude 구독 환경(Claude Code)과 무료 TTS/오픈소스 라이브러리로 추가 비용 없이 쇼츠 영상 제작.
* **타깃 사용자:** 쿠팡 파트너스 등 제휴 마케팅으로 쇼핑 쇼츠를 운영하는 1인 크리에이터 (비개발자 포함).
* **목표 성능:** 링크 입력 → 최종 MP4까지 **10분 이내** (CPU 기준, 다운로드 시간 제외), 사람 손 개입은 "프리셋 선택"과 "최종 확인" 2회.

### 1.1 범위 밖 (Non-Goals, v1 기준)
* 플랫폼 자동 업로드(유튜브/인스타/틱톡 API 연동)
* GUI(웹/데스크톱 앱) — v1은 CLI + Claude Code 대화
* 대본 자동 번역 이외의 원본 영상 음성 활용(원본 음성은 기본 음소거)
* 실시간 인기 해시태그 크롤링 (v1은 카테고리별 프리셋 + Claude 생성)

---

## 2. 시스템 아키텍처 (신설)

### 2.1 "추가 비용 0원"의 실제 의미
대본 생성(Module 2)과 자연어 수정 해석(Module 6)은 **LLM이 반드시 필요**합니다. 별도 API 키 없이 이를 해결하는 방식은 다음 중 하나이며, **기본값은 A안**입니다.

| 방식 | 설명 | 비용 | 비고 |
|---|---|---|---|
| **A. Claude Code 오케스트레이션 (기본)** | 사용자는 Claude Code 안에서 대화. Claude가 `ssm` CLI를 도구처럼 호출하고, 대본(`script.json`)은 Claude가 직접 작성해 파일로 저장 | Claude 구독료 외 0원 | `CLAUDE.md`에 워크플로우·명령어를 상세히 기술 |
| B. Anthropic API | `main.py`가 API로 대본 생성 | 토큰 과금 | 완전 자동화(배치)용 옵션 |
| C. 로컬 LLM (Ollama) | Qwen/EXAONE 등 로컬 모델 | 0원 (GPU 권장) | 한국어 카피 품질 낮음 |

→ `scripter.py`는 `LLMProvider` 인터페이스로 분리하고, A안에서는 "프롬프트 생성 + 결과 스키마 검증"만 담당한다.

### 2.2 데이터 흐름
```text
[URL/키워드]
   │ collect
   ▼
raw_videos/*.mp4 + candidates.json ──(filter: 한글OCR·한국어음성·상품일치)──► selected.json
   │ analyze (장면 분할·하이라이트 점수·자막 영역 감지)
   ▼
analysis.json
   │ script (Claude가 작성 → 스키마 검증)
   ▼
script.json
   │ tts
   ▼
tts.mp3 + word_timings.json + subtitles.srt
   │ edit (자막 제거 → 컷 배치 → 자막/광고표시 오버레이 → 오디오 믹스)
   ▼
final_output.mp4
   │ meta
   ▼
thumbnail.png + caption.txt
```

### 2.3 단계 의존성 및 캐시 무효화
* `workspace/{project_id}/state.json`에 단계별 **입력 해시**와 완료 시각을 기록한다.
* 어떤 단계의 입력(이전 산출물 또는 관련 config 값)이 바뀌면 그 단계와 **하위 단계만** 재실행한다.

| 변경 내용 | 재실행 단계 |
|---|---|
| 대본 톤/내용 | script → tts → edit → meta(캡션) |
| TTS 목소리/속도 | tts → edit |
| 자막 스타일(폰트·크기·위치) | edit의 오버레이·렌더링만 (컷 타임라인 재사용) |
| 썸네일 문구 | meta(썸네일)만 |
| 원본 영상 교체 | analyze 이후 전체 |

---

## 3. 핵심 기능 요구사항 (Functional Requirements)

### Module 1. 원본 영상 수집 및 필터링 (`collector.py`)
* **입력:** 타깃 상품 영상 URL(샤오홍슈/도우인/틱톡) 또는 키워드(중국어 키워드 권장, 한국어 입력 시 Claude가 중국어 검색어로 변환).
* **유사 영상 다중 다운로드:** 해당 영상을 포함해 같은 상품의 원본 영상을 **최대 N개(기본 5개, 후보는 10개까지 탐색)** 검색·다운로드.
  * 플랫폼별 다운로더를 `Downloader` 인터페이스로 분리 (`yt-dlp` 우선 → 실패 시 `playwright` 폴백).
  * 샤오홍슈/도우인은 비로그인 접근이 제한되므로 **브라우저 쿠키 파일(`cookies.txt`) 경로**를 config로 받는다. 쿠키 만료 시 명확한 안내 메시지 출력.
  * 워터마크 없는 원본 URL을 우선 사용, 불가 시 플랫폼 워터마크 위치를 `analysis.json`에 기록해 Module 4에서 함께 가린다.
  * 요청 간 랜덤 지연(2~5초), 동시 다운로드 2개 이하 (차단 방지).
* **상품 일치성 검증 (신설):** 유사 영상이 *다른 상품*일 경우 교차 편집 시 영상이 망가지므로, 기준 영상의 대표 프레임과 후보 영상 프레임 간 **CLIP 임베딩 유사도**(`open_clip`, CPU 가능)를 비교해 임계값(기본 0.80) 미만은 제외.
* **국내 콘텐츠 필터링 (필수):** 다음 중 하나라도 해당하면 제외하고 사유를 `candidates.json`에 기록.
  1. **한글 텍스트:** 영상 길이 기준 균등 8프레임 샘플링 → OCR → 한글 음절(U+AC00–U+D7A3) 비율이 인식 문자 중 10% 이상 또는 한글 4자 이상 연속 검출.
  2. **한국어 음성:** 원본 오디오 앞 30초를 `faster-whisper`(tiny/base) 언어 감지 → `ko` 확률 0.5 이상.
  3. **작성자 메타데이터:** 작성자 IP 표시 지역/프로필 소개/제목에 한국·한글이 포함된 경우.
  > ⚠️ 원안의 "한국인 출연 여부(얼굴로 국적 판별)"는 기술적으로 신뢰할 수 없고 차별 소지가 있어 **제외**했습니다. 대신 위 3가지 신호를 조합합니다.
* **출력:** `raw_videos/{idx}.mp4`, `candidates.json`(전체 후보·점수·제외 사유), `selected.json`(최종 채택 목록)
* **완료 기준:** 샤오홍슈 URL 1개 입력 시 3개 이상의 동일 상품 영상이 확보되고, 한글 자막이 박힌 테스트 영상은 100% 제외됨.

### Module 1.5. 영상 분석 (`analyzer.py`, 신설)
Module 2·4가 공통으로 쓰는 분석 결과를 한 번만 계산해 캐시합니다.
* **장면 분할:** `PySceneDetect`(ContentDetector)로 샷 경계 검출.
* **하이라이트 점수:** 샷별로 선명도(Laplacian 분산), 움직임량(프레임 차분), 밝기, 얼굴/손 등장 여부를 정규화해 가중합.
* **자막·워터마크 영역 감지:** OCR 바운딩 박스를 여러 프레임에 걸쳐 누적 → 일정 비율 이상 반복 등장한 영역을 "고정 텍스트 영역"으로 판정.
* **장면 설명(선택):** 대표 프레임을 Claude에게 보여 "이 장면에서 보이는 것"을 한 줄로 기록 → 대본-장면 매칭에 활용 (A안에서만, 추가 비용 없음).
* **출력:** `analysis.json`

### Module 2. 대본(Script) 생성 (`scripter.py`)
* **대본 프리셋 제공:** 다음 프리셋을 제시하고 선택받음. 각 프리셋은 `presets/scripts/*.yaml`에 [훅 패턴, 문장 길이, 어미 스타일, 금지 표현, 예시 대본 2개]로 정의.
  * ① 호기심 유발/문제 해결형, ② 내돈내산 찐리뷰형, ③ 가성비/할인 강조형, ④ 정보성 큐레이션형(계정 육성용)
* **상품 정보 입력:** 상품명, 핵심 특징 3개, 가격대(선택). 원본 영상 제목/설명(중국어)을 번역·요약해 초안을 자동 채우고 사용자가 확인.
* **레퍼런스 클로닝:** 벤치마킹 영상 링크 → `faster-whisper`로 음성 전사 → 화법(문장 길이, 훅 구조, 어미, 말 속도)을 분석해 동일 스타일로 대본 생성. 텍스트 예시를 직접 붙여넣는 것도 지원.
* **분량 규칙:** 목표 길이(기본 **30초**, 범위 15~60초) × 한국어 TTS 기준 약 **초당 6~7음절**로 글자 수 상한 계산.
* **구조:** `hook(0~3초)` → `problem/curiosity` → `product demo` → `benefit` → `CTA` 섹션으로 구성하고, 각 문장에 강조 키워드와 효과음 큐를 태깅.
* **CTA 자동 삽입:** 영상 후반부에 댓글 유도 문구 자동 포함 (예: "상품 정보 궁금하시면 댓글에 '링크' 남겨주세요!").
* **금지 표현 검사:** 과장·허위 광고 소지 표현("100% 효과", "최저가 보장", 의학적 효능 등) 목록을 두고 생성 후 자동 검사.
* **출력:** `script.json` (스키마는 6장 참고)

### Module 3. 음성 합성(TTS) 및 오디오 처리 (`tts_engine.py`)
* **무료 TTS 기본 연동:** `edge-tts` 기본 탑재 (`ko-KR-SunHiNeural`, `ko-KR-InJoonNeural`, `ko-KR-HyunsuMultilingualNeural` 등). 속도(`rate`, 기본 +10%)·피치 조절 지원.
* **음성 타임스탬프 추출:** `WordBoundary` 이벤트로 단어 단위 타이밍을 받아 `word_timings.json`에 저장하고, 이를 자막 규칙(Module 4)에 따라 묶어 `subtitles.srt` 생성.
* **문장 단위 생성 후 결합:** 문장별로 TTS를 생성해 이어 붙인다(문장 사이 무음 120~200ms). 부분 수정 시 바뀐 문장만 재생성.
* **커스텀 TTS 확장 구조:** `TTSProvider` 인터페이스(`synthesize(text, voice) -> (audio_path, word_timings)`). ElevenLabs/OpenAI/Typecast 등은 API 키가 있을 때만 활성화. 타임스탬프를 주지 않는 엔진은 `faster-whisper` 강제 정렬로 보완.
* **효과음(SFX) 믹싱:** `script.json`의 SFX 큐 위치에 `assets/sfx/` 에셋 자동 배치 (훅=whoosh, 강조=pop/ding, 전환=swish).
* **BGM (신설):** `assets/bgm/`의 저작권 프리 음원을 깔고, 음성 구간에서 **사이드체인 덕킹**(FFmpeg `sidechaincompress`)으로 BGM을 -18dB 수준으로 낮춤.
* **라우드니스 정규화 (신설):** 최종 오디오 **-14 LUFS, True Peak -1.0 dBTP** (`loudnorm` 2-pass).
* **실패 처리:** edge-tts는 비공식 엔드포인트라 차단·변경될 수 있음 → 3회 재시도 후 실패 시 대체 엔진(로컬 TTS 또는 사용자 API 키)으로 전환 안내.

### Module 4. 영상 편집 및 후처리 (`video_editor.py`)
* **기존 외국어 자막 제거/가리기:** Module 1.5의 "고정 텍스트 영역"을 대상으로 아래 방식 중 config로 선택.
  * `crop` (기본 후보): 자막이 화면 상·하단 가장자리에만 있으면 잘라내고 9:16으로 재확대
  * `blur` (기본값): 해당 영역 가우시안 블러 + 반투명 박스. 새 한국어 자막을 그 위에 얹어 자연스럽게 가림
  * `inpaint` (선택): OpenCV `cv2.inpaint`(빠름, 품질 낮음) / LaMa·ProPainter(고품질, GPU 필요)
  * 자막 영역이 프레임마다 달라지는 경우(동적 자막)는 프레임별 OCR 마스크를 적용하되, 처리 시간 상한(기본 2분)을 넘으면 `blur` 박스로 폴백.
* **9:16 정규화:** 가로/정사각 원본은 블러 배경 + 중앙 배치(또는 스마트 크롭)로 1080x1920 변환.
* **자동 컷 편집 및 싱크 매칭:**
  * TTS 전체 길이에 맞춰 `analysis.json`의 하이라이트 샷을 2~3초 단위로 배치.
  * **문장 경계에 컷 전환을 맞춘다** (단어 타이밍 기준, ±0.2초 스냅).
  * 같은 샷 재사용 금지, 같은 원본 영상 연속 2컷 이하, 첫 컷(훅 구간)은 하이라이트 점수 1위 샷.
  * 장면 설명이 있으면 문장 키워드와 장면 설명의 유사도로 매칭 (예: "물 부으니까" ↔ 물을 붓는 장면).
  * 원본보다 영상 소스가 부족하면 속도 0.9~1.1배 조정·줌인(Ken Burns)으로 길이 보충.
* **한국어 자막 합성:**
  * 한 줄 최대 **14자**, 최대 2줄, 한 화면 표시 0.6~2.5초. 조사·어절 단위로 줄바꿈(단어 중간 분리 금지).
  * 강조 키워드는 색상 변경(기본 노란색), 외곽선 6~8px, 선택적 반투명 배경 박스.
  * 렌더링 방식: Pillow로 자막 PNG 생성 후 FFmpeg `overlay` (Windows에서 `drawtext`/libass 폰트 경로 문제 회피). ASS 자막 방식은 옵션.
* **광고 표시:** 영상 **시작부터 끝까지** 상단 고정. 문구는 `config.yaml`에서 지정 (6장 config 예시 참고).
* **플랫폼 세이프존 (신설):** 자막·광고표시가 UI에 가리지 않도록 **상단 250px, 하단 400px, 우측 150px**는 핵심 텍스트 배치 금지. 자막 기본 위치는 화면 높이 62~70% 지점.
* **표준 규격 렌더링:** `1080x1920`, `30fps`(기본) 또는 `60fps`, `H.264 High / yuv420p / CRF 20 / AAC 192kbps / +faststart`.
* **미리보기 모드:** `--preview` 시 540x960, `ultrafast` 프리셋으로 빠르게 렌더링해 확인 후 최종 렌더.
* **출력:** `timeline.json`(컷 목록 — 자막만 바꿀 때 재사용), `final_output.mp4`

### Module 5. 썸네일 및 메타데이터 생성 (`metadata_gen.py`)
* **썸네일 자동 생성:** 하이라이트 상위 샷에서 선명도·밝기·상품 중심성 점수가 가장 높은 프레임 선택 → 1080x1920 썸네일. 기본 2줄 레이아웃(상단 노란색 강조어 + 하단 흰색 요약어), 텍스트는 세이프존 안쪽 중앙 상단 배치.
  * 썸네일 문구 후보 3개를 생성해 `thumbnail_1~3.png`로 출력하고 사용자가 선택.
* **썸네일 스타일 복제:** 레퍼런스 이미지 제공 시 주요 색상(k-means 팔레트), 텍스트 위치·크기 비율, 외곽선 유무를 추출해 `thumbnail_style.json`으로 저장 후 재사용. (Claude가 이미지를 보고 스타일 파라미터를 채우는 방식 병행)
* **설명글(캡션) 생성:** 플랫폼별로 `caption.txt` 안에 구역을 나눠 저장.
  * 공통: 첫 줄 훅 문장, 상품 요약 2~3줄, CTA, **광고 표시 문구(본문 첫머리)**
  * 해시태그 10~15개: 카테고리별 프리셋(`presets/hashtags/*.yaml`) + 상품 특화 태그 조합. 유튜브 쇼츠용은 `#shorts` 포함·3~5개 요약본 별도 제공.
  * 쇼츠 제목(100자 이내) 후보 3개 포함.

### Module 6. 자연어 기반 대화형 수정 루프 (`main.py` / Claude Code)
* 결과물 생성 후 세션을 종료하지 않고 사용자의 자연어 피드백을 대기.
* **A안(기본):** Claude Code가 피드백을 해석해 `config`/`script.json`/`overrides.json`을 수정하고 해당 CLI 단계만 재실행. `CLAUDE.md`에 "요청 유형 → 수정할 파일 → 재실행 명령" 매핑 표를 둔다.
* **B안:** `main.py chat` 모드에서 API로 의도 분류(JSON function-calling) 후 동일하게 처리.
* *수정 명령 예시:*
  * "대본 결을 조금 더 친근하게 바꿔서 다시 만들어줘" → script → tts → edit → meta(캡션)
  * "썸네일 문구를 '자취생 필수템'으로 수정해줘" → meta(썸네일)만
  * "자막 폰트 크기 좀 키우고 위치 살짝 올려줘" → edit 오버레이·렌더만 (`timeline.json` 재사용)
  * "세 번째 컷 다른 장면으로 바꿔줘" → edit (`timeline.json`의 해당 컷만 교체)
* **버전 관리:** 재렌더 시 이전 결과를 `versions/v{n}/`에 보관하고 `ssm rollback`으로 되돌리기 가능.

---

## 4. 비기능 및 시스템 요구사항 (Non-Functional Requirements)

1. **원클릭 설치 (One-Click Setup):**
   * `setup.bat`(Windows) / `setup.sh`(Mac/Linux) 제공.
   * Python 3.10~3.12 확인 → 가상환경 생성 → `requirements.txt` 설치 → FFmpeg 확인(없으면 Windows는 `winget install Gyan.FFmpeg`, Mac은 `brew install ffmpeg`, Linux는 패키지 매니저 안내) → 폰트 자동 다운로드 → `ssm doctor`로 설치 검증.
   * 폰트는 **상업적 이용이 허용된 라이선스(OFL 등)** 만 사용하고, GitHub 릴리스 등 **고정 다운로드 URL + SHA256 체크섬**으로 받는다. (예: Pretendard — OFL)
   * 무거운 의존성(OCR 모델, CLIP, whisper)은 첫 실행 시 지연 다운로드하고 진행률 표시.
2. **상태 저장 및 캐싱 (Workspace Management):**
   * `workspace/{project_id}/`에 단계별 산출물 저장, `state.json`으로 부분 재실행 (2.3 참고).
   * `project_id` 형식: `YYYYMMDD-HHMM-{상품슬러그}`.
3. **하드웨어 요구사항:** 최소 CPU 4코어 / RAM 8GB / 여유 디스크 5GB. NVIDIA GPU가 있으면 OCR·whisper·inpaint 자동 가속.
4. **크로스 플랫폼:** 모든 파일 입출력 UTF-8 고정, 경로는 `pathlib` 사용, 한글/공백 포함 경로 테스트 필수.
5. **로깅·에러 처리:** 단계별 로그를 `workspace/{id}/logs/`에 저장. 사용자에게는 "무엇이 실패했고 → 무엇을 하면 되는지" 형태의 한국어 메시지 출력. 네트워크 작업은 지수 백오프 재시도.
6. **테스트:** 각 모듈 단위 테스트(`pytest`) + 샘플 영상 3개(`tests/fixtures/`, 직접 제작한 저작권 문제 없는 영상)로 E2E 스모크 테스트.

---

## 5. 권장 기술 스택 (Recommended Tech Stack for Claude)

| 용도 | 라이브러리 | 비고 |
|---|---|---|
| 언어 | Python 3.10+ | |
| CLI | `typer`, `rich` | 서브커맨드·진행률 표시 |
| 설정/스키마 | `pyyaml`, `pydantic` v2 | `script.json` 등 스키마 검증 |
| 영상 다운로드 | `yt-dlp`, `playwright` | 쿠키 파일 지원 |
| OCR | `paddleocr`(중국어 정확도 우수) 또는 `easyocr` | 한글 감지 + 중국어 자막 영역 감지 겸용 |
| 음성 인식/언어감지 | `faster-whisper` | 한국어 음성 필터, 레퍼런스 전사, 강제 정렬 |
| 상품 일치 검증 | `open_clip_torch` | CPU 가능 |
| 장면 분할 | `scenedetect` | |
| 무료 TTS | `edge-tts` | WordBoundary 타임스탬프 |
| 영상/오디오 편집 | `FFmpeg`(subprocess 직접 제어), `opencv-python` | `moviepy`는 미리보기 외 사용 지양(속도) |
| 이미지/자막/썸네일 | `Pillow` | |
| 테스트 | `pytest` | |

---

## 6. 데이터 스키마 및 설정 예시 (신설)

### 6.1 `script.json`
```json
{
  "version": 1,
  "preset": "curiosity",
  "target_duration_sec": 30,
  "product": { "name": "접이식 실리콘 전기포트", "features": ["접으면 5cm", "1분 만에 끓음", "여행용"], "price_hint": "2만원대" },
  "sentences": [
    { "id": "s1", "section": "hook", "text": "아직도 여행 갈 때 포트 못 챙기세요?", "emphasis": ["포트"], "sfx": "whoosh" },
    { "id": "s2", "section": "demo", "text": "이건 접으면 두께가 5센티밖에 안 돼요.", "emphasis": ["5센티"], "sfx": "pop", "scene_hint": "접는 장면" },
    { "id": "s9", "section": "cta", "text": "궁금하시면 댓글에 '링크' 남겨주세요!", "emphasis": ["링크"], "sfx": null }
  ],
  "thumbnail_text": { "top": "여행 필수템", "bottom": "접으면 5cm 전기포트" }
}
```

### 6.2 `config.yaml` (주요 항목)
```yaml
video:   { width: 1080, height: 1920, fps: 30, crf: 20 }
subtitle:
  font: assets/fonts/Pretendard-ExtraBold.otf
  size: 78
  max_chars_per_line: 14
  position_y_ratio: 0.66
  color: "#FFFFFF"
  emphasis_color: "#FFE14D"
  stroke_width: 7
  box: false
foreign_sub_removal: blur        # crop | blur | inpaint
ad_disclosure:
  enabled: true
  text: "유료 광고 포함 · 쿠팡 파트너스 활동의 일환으로 일정액의 수수료를 제공받습니다"
  position: top_center
tts:     { provider: edge, voice: ko-KR-SunHiNeural, rate: "+10%" }
audio:   { bgm: auto, bgm_duck_db: -18, target_lufs: -14 }
collector:
  max_videos: 5
  clip_similarity_threshold: 0.80
  cookies_file: null
llm:     { provider: claude_code }   # claude_code | anthropic_api | ollama
```

### 6.3 CLI 명령어
```text
ssm new <url|keyword>          # 프로젝트 생성 + collect + analyze
ssm script <id> --preset 1     # (A안) 프롬프트 출력 / (B안) 대본 생성
ssm tts <id>
ssm edit <id> [--preview]
ssm meta <id>
ssm run <id>                   # 남은 단계 일괄 실행 (state.json 기준)
ssm status <id> | rollback <id> v2 | doctor
```

---

## 7. 권장 디렉토리 구조 (Directory Structure)

```text
shopping-shorts-maker/
├── CLAUDE.md                 # Claude Code용 워크플로우, 명령어, 수정 요청→재실행 매핑표
├── setup.bat / setup.sh      # 원클릭 설치
├── requirements.txt
├── config.yaml
├── assets/
│   ├── fonts/                # 상업용 무료 폰트 (setup 시 다운로드)
│   ├── sfx/                  # whoosh.mp3, pop.mp3 ... (라이선스 확인된 것만)
│   └── bgm/                  # 저작권 프리 BGM
├── presets/
│   ├── scripts/              # 대본 프리셋 yaml
│   ├── hashtags/             # 카테고리별 해시태그
│   └── banned_phrases.txt    # 과장광고 금지 표현
├── src/ssm/
│   ├── __init__.py
│   ├── main.py               # typer CLI 엔트리포인트
│   ├── workspace.py          # state.json, 캐시 무효화, 버전 관리
│   ├── schemas.py            # pydantic 스키마
│   ├── collector.py          # 다운로드 + 필터링
│   ├── analyzer.py           # 장면 분할, 하이라이트, 자막영역 감지
│   ├── scripter.py           # 프리셋·프롬프트·LLMProvider
│   ├── tts_engine.py         # TTSProvider, 타임스탬프, SFX/BGM 믹스
│   ├── video_editor.py       # 자막 제거, 컷 편집, 오버레이, 렌더
│   ├── subtitle.py           # 줄바꿈 규칙, 자막 PNG 렌더
│   └── metadata_gen.py       # 썸네일, 캡션, 해시태그
├── tests/
│   ├── fixtures/
│   └── test_*.py
└── workspace/                # 프로젝트별 작업 폴더 (자동 생성, .gitignore)
```

---

## 8. 법적 고지 및 리스크 (신설 — 반드시 읽을 것)

| 리스크 | 내용 | 대응 |
|---|---|---|
| **원본 영상 저작권** | 해외 영상이라도 저작권은 원작자에게 있음. "국내 크리에이터 필터"는 분쟁 가능성을 줄일 뿐 **적법성을 보장하지 않음**. 플랫폼 신고 시 채널 경고·수익 정지 가능 | 판매자 공식 영상·허락받은 영상 우선, 원작자 출처 표기 옵션, 사용자 책임 고지를 첫 실행 시 표시 |
| **플랫폼 약관** | 샤오홍슈·도우인 스크래핑은 약관 위반 소지, 계정 차단 가능 | 부계정 쿠키 사용 권장, 요청 속도 제한 |
| **광고 표시 의무** | 공정위 「추천·보증 등에 관한 표시·광고 심사지침」: 광고 표시는 영상 **시작 부분과 전체**, 그리고 게시물 **제목/본문 첫머리**에 명확히 | 광고 워터마크 상시 고정 + 캡션 첫 줄 자동 삽입 (끌 수 없도록 기본값 강제) |
| **과장 광고** | 효능·최저가 단정 표현은 표시광고법 위반 소지 | 금지 표현 사전 검사 (Module 2) |
| **edge-tts** | Microsoft의 공식 상업용 API가 아닌 Edge 읽어주기 엔드포인트 사용 → 약관 회색지대, 예고 없이 중단 가능 | `TTSProvider`로 교체 가능하게 설계, 수익화 규모가 커지면 정식 TTS 전환 권장 |
| **폰트·효과음·BGM** | 라이선스 위반 시 분쟁 | 상업 이용 가능 에셋만 번들, 출처를 `assets/LICENSES.md`에 기록 |

---

## 9. 개발 마일스톤 및 완료 기준 (신설)

| 단계 | 내용 | 완료 기준 |
|---|---|---|
| M0 | 뼈대: 디렉토리, `setup.*`, `config.yaml`, `workspace.py`, CLI 골격, `ssm doctor` | 새 PC에서 setup 1회 실행 후 `ssm doctor` 전 항목 통과 |
| M1 | TTS + 자막 + 단일 영상 렌더 (로컬 mp4 입력) | 로컬 영상 1개 + 대본 json → 자막·광고표시 포함 1080x1920 MP4 생성 |
| M2 | 다중 영상 컷 편집 + 외국어 자막 블러 + BGM/SFX/라우드니스 | 샘플 3개 영상으로 30초 쇼츠, 컷이 문장 경계에 맞음, -14 LUFS ±1 |
| M3 | 수집기 + 필터 (yt-dlp → playwright 폴백) | 완료 기준은 Module 1 참고 |
| M4 | 대본 프리셋·레퍼런스 클로닝 + `CLAUDE.md` 워크플로우 | Claude Code에서 "이 링크로 쇼츠 만들어줘" 한 문장으로 끝까지 진행 |
| M5 | 썸네일·캡션 | 썸네일 3안 + 플랫폼별 캡션 생성 |
| M6 | 수정 루프·버전 관리·캐시 무효화 | 3장 Module 6의 예시 4개가 해당 단계만 재실행되며 동작 |

> M1을 수집기(M3)보다 먼저 하는 이유: 다운로드는 외부 사이트 변화에 가장 취약하므로, 로컬 입력으로 핵심 편집 파이프라인을 먼저 완성해 두면 수집 문제와 무관하게 진척을 확인할 수 있습니다.

---

## 10. 미결정 사항 (Open Questions)
1. LLM 방식: A(Claude Code) / B(API) / C(로컬) 중 기본값 확정 필요
2. 주 사용 OS (Windows 우선 여부), GPU 유무
3. 광고 표시 문구 기본값 — 쿠팡 파트너스 고정인지, 다른 제휴(알리 어필리에이트 등)도 지원하는지
4. 유사 영상 검색 범위 — "같은 상품의 다른 영상"인지, "비슷한 분위기의 다른 상품 영상"까지 허용인지
5. 원본 영상의 음성/배경음 처리 — 완전 음소거 vs 낮은 볼륨 유지
6. 목표 영상 길이 기본값(30초 제안)과 60fps 필요 여부
7. 006 AI Shorts Studio와의 관계 — 별도 CLI 프로젝트로 갈지, 006의 렌더링·TTS·자막 모듈을 공유(또는 006에 '쇼핑 모드'로 통합)할지

---

## 11. Claude에게 바로 입력할 첫 번째 개발 프롬프트

> **"첨부한 `shopping_shorts_maker_spec.md` 문서를 숙지해 줘. 9장 마일스톤 M0부터 시작하자. 7장 디렉토리 구조에 맞춰 뼈대 파일, `requirements.txt`, `config.yaml`, `setup.bat`/`setup.sh`, `workspace.py`, `ssm doctor` 명령까지 작성하고, M0 완료 기준을 어떻게 확인했는지 알려줘. 그다음 M1로 넘어가기 전에 나에게 확인받아."**
