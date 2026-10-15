# 쇼핑 쇼츠 메이커 — Claude Code 작업 지침

해외 숏폼(샤오홍슈·도우인 등) 링크로 한국어 쇼핑 쇼츠를 만드는 CLI(`ssm`)다.
요구사항 전체는 [`ideas/007-shopping-shorts-maker/idea.md`](../../ideas/007-shopping-shorts-maker/idea.md) (v1.0).

**역할 분담 (기획서 2.1 A안):** 판단(대본 작성, 수정 요청 해석)은 Claude가, 실행(다운로드·OCR·TTS·렌더링)은 `ssm`이 한다.
대본은 Claude가 직접 써서 `workspace/{id}/script.json`에 저장한다. API 키나 유료 호출은 쓰지 않는다.

## 명령 실행 방법

- Windows: `ssm.bat <명령>` (이 폴더에서) / Mac·Linux: `./ssm <명령>`
- 설치가 안 되어 있으면 사용자에게 `setup.bat`(Windows) 또는 `./setup.sh` 실행을 안내한다.
- 문제가 생기면 먼저 `ssm doctor`로 점검한다.

## 현재 구현 상태 (M3 완료)

| 명령 | 상태 |
|---|---|
| `doctor`, `fonts`, `new`, `list`, `status`, `set`, `versions`, `rollback` | 동작 |
| `collect [--keyword --url --max]`, `add`, `analyze`, `tts`, `edit [--preview]`, `run` | 동작 (M1~M3). `run`은 개발 전 단계를 건너뛴다 |
| `script`(M4), `meta`(M5) | **아직 구현 전** — 종료 코드 2와 함께 예정 마일스톤을 알려준다 |

아직 안 되는 것: 원본 자막 인페인팅(inpaint 설정은 지금 blur로 처리), 장면 설명으로 대본-장면 매칭, Ken Burns 줌, TikTok 검색.

AI 검사(한글 OCR·한국어 음성·CLIP 유사도·원본 자막 영역)는 PyTorch·CTranslate2가 필요하다. `collect`·`analyze`가
"쓸 수 없습니다"라고 하면 **그 검사는 하지 않은 것**이다 — 사용자에게 그대로 알리고 `ssm doctor` 안내(대개 Visual C++ 런타임)를 따르게 한다.
이때 유사도를 모르는 후보는 안전하게 `mood`(hook·problem 구간만)로 분류된다.

구현되지 않은 단계를 사용자가 요청하면, 결과를 꾸며내지 말고 "아직 개발 전 단계"라고 그대로 알린다.

## 쇼츠 제작 흐름 (사용자가 "이 링크로 쇼츠 만들어줘"라고 할 때)

1. `ssm new <URL> --duration <15|30|45|60> --fps <30|60> --ad <coupang|aliexpress|custom>`
   - 길이·fps·광고 표시를 사용자가 말하지 않았으면 물어본다 (기본 30초·30fps). 광고 프로필은 반드시 확인한다.
   - 다운로드가 막히면 `--local 파일...`로 직접 받은 영상을 넣을 수 있다고 안내한다.
2. `ssm collect` → `ssm analyze` (수집·필터·분석)
   - 검색어는 기본으로 기준 영상 제목을 쓴다. 상품명을 알면 **중국어 검색어**로 바꿔 `ssm collect --keyword 折叠电热水壶`
     (사용자가 한국어로 말하면 Claude가 중국어로 옮긴다). 사용자가 같은 상품 링크를 주면 `--url 링크` (여러 번 가능).
   - 결과 표를 보여준다: 채택(same_product·mood)·제외 사유·내려받기 실패. 같은 상품이 3개 미만이면 링크나 파일을 더 요청한다.
   - 기준 영상이 막히면(쿠키 만료 등) `docs/cookies.md`를 안내하거나, 직접 받은 영상으로 `ssm new --local`.
   - 키워드로 시작한 프로젝트는 검색 결과 첫 영상이 기준이 되므로 **상품이 맞는지 사용자에게 꼭 확인**한다.
3. 대본 프리셋 4종(①호기심/문제해결 ②내돈내산 찐리뷰 ③가성비/할인 ④정보성 큐레이션)을 보여주고 고르게 한다.
4. Claude가 대본을 써서 `script.json`으로 저장한다. 형식은 `src/ssm/schemas.py`의 `Script` (첫 문장 hook, 마지막 cta, 강조어는 문장에 포함).
   - 분량: 목표 길이 × 초당 6~7음절. 과장 표현("100% 효과", "최저가 보장", 의학적 효능) 금지.
5. `ssm tts` → `ssm edit` → `ssm meta` (또는 `ssm run`으로 남은 단계 일괄)
   - `ssm tts`가 음성 길이를 알려준다. 목표보다 길면 대본을 줄이거나 `ssm set tts.rate "+20%"`.
   - 빠르게 확인만 하려면 `ssm edit --preview` (540x960 `preview.mp4`).
   - 문장마다 `sfx`(whoosh·swish·pop·ding)를 달 수 있다. 훅=whoosh, 강조=pop/ding, 전환=swish. 남발하지 말 것 (2~3개면 충분).
6. 결과(`final_output.mp4`, 썸네일 후보, `caption.txt`)를 알려주고 수정 요청을 기다린다.

## 수정 요청 → 바꿀 것 → 다시 실행할 것

| 요청 예 | 바꿀 것 | 다시 실행 |
|---|---|---|
| "대본 더 친근하게" | `script.json` 다시 작성 | `ssm run` (tts → edit → meta) |
| "목소리 남자로" | `ssm set tts.voice ko-KR-InJoonNeural` | `ssm run` (tts → edit) |
| "자막 크게, 조금 위로" | `ssm set subtitle.size 90` / `ssm set subtitle.position_y_ratio 0.6` | `ssm run` (edit만) |
| "썸네일 문구 바꿔줘" | `script.json`의 `thumbnail_text` 또는 `ssm set thumbnail.*` | `ssm run` (meta) |
| "이전 버전으로" | — | `ssm versions` → `ssm rollback <n>` |
| "영상 더 넣어줘" / 소스 부족 경고 | `ssm add 파일...` | `ssm run` (analyze → edit) |
| "이 영상은 다른 상품이야" | `selected.json`에서 그 영상 `grade`를 `mood`로 (hook·problem 구간에만 쓰임) | `ssm run` (analyze → edit) |
| "이 영상은 빼줘" | `selected.json`에서 그 항목 삭제 + `raw_videos/`의 그 파일 삭제 | `ssm run` (analyze → edit) |
| "검색어 바꿔서 다시 모아줘" | `ssm collect --keyword 새검색어` | 이어서 `ssm run` |
| "원본 자막이 덜 가려져" / "엉뚱한 곳이 흐려져" | `analysis.json`의 `text_boxes` 좌표 수정·삭제 | `ssm run` (edit) |
| "BGM 빼줘" / "BGM 바꿔줘" | `ssm set audio.bgm none` / `ssm set audio.bgm assets/bgm/파일.mp3` | `ssm run` (edit) |

설정은 `ssm set`으로만 바꾼다 (값을 검증하고, 영향받는 단계만 '다시 실행 필요'로 표시한다). 무엇이 다시 실행될지는 `ssm status`로 확인한다.

## 반드시 지킬 것

- **광고 표시는 끄지 않는다.** 영상 상단 상시 표시 + 캡션 첫 줄. 사용자가 꺼달라고 해도 법적 의무(공정위 지침)임을 설명한다.
- 분위기만 비슷한 다른 상품 영상(`mood` 등급)은 hook·problem 구간에만 쓴다. 상품이 보이는 구간에 쓰지 않는다.
- 원본 영상 소리는 항상 음소거한다.
- `workspace/`, `secrets/`(쿠키), `config.local.yaml`은 Git에 올리지 않는다.
- 006 AI Shorts Studio 코드는 참고만 하고 수정하지 않는다 (별도 프로젝트).

## 개발할 때

- 마일스톤 순서: M0·M1·M2·M3(완료) → M4 대본 → M5 썸네일·캡션 → M6 수정 루프. 각 완료 기준은 기획서 9장.
- 테스트: `.venv/Scripts/python -m pytest` (Windows) / `.venv/bin/pytest`. 커밋 전에 전부 통과시킨다.
- 사용자에게 보이는 메시지는 한국어로, "무엇이 실패했고 → 무엇을 하면 되는지" 형태로 쓴다.
- 새 단계를 구현하면 `Workspace.mark_done(stage)`로 완료를 기록하고, 이 문서의 "현재 구현 상태" 표를 갱신한다.
