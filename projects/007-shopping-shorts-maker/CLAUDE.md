# 쇼핑 쇼츠 메이커 — Claude Code 작업 지침

해외 숏폼(샤오홍슈·도우인 등) 링크로 한국어 쇼핑 쇼츠를 만드는 CLI(`ssm`)다.
요구사항 전체는 [`ideas/007-shopping-shorts-maker/idea.md`](../../ideas/007-shopping-shorts-maker/idea.md) (v1.0).

**역할 분담 (기획서 2.1 A안):** 판단(대본 작성, 수정 요청 해석)은 Claude가, 실행(다운로드·OCR·TTS·렌더링)은 `ssm`이 한다.
대본은 Claude가 직접 써서 `workspace/{id}/script.json`에 저장한다. API 키나 유료 호출은 쓰지 않는다.

## 명령 실행 방법

- Windows: `ssm.bat <명령>` (이 폴더에서) / Mac·Linux: `./ssm <명령>`
- 설치가 안 되어 있으면 사용자에게 `setup.bat`(Windows) 또는 `./setup.sh` 실행을 안내한다.
- 문제가 생기면 먼저 `ssm doctor`로 점검한다.

## 현재 구현 상태 (M1 완료)

| 명령 | 상태 |
|---|---|
| `doctor`, `fonts`, `new`, `list`, `status`, `set`, `versions`, `rollback` | 동작 |
| `tts`, `edit [--preview]`, `run` | 동작 (M1) — 로컬 영상 1개 기준. `run`은 개발 전 단계를 건너뛴다 |
| `collect`(M3), `analyze`(M2), `script`(M4), `meta`(M5) | **아직 구현 전** — 종료 코드 2와 함께 예정 마일스톤을 알려준다 |

M1에서 아직 안 되는 것: 여러 영상 컷 편집·외국어 자막 가리기·BGM/효과음·라우드니스(-14 LUFS)는 M2. 영상이 여러 개여도 첫 번째만 쓴다.
지금 쇼츠를 만들려면: `ssm new --local 영상.mp4 --ad coupang` → Claude가 `script.json` 작성 → `ssm tts` → `ssm edit`.

구현되지 않은 단계를 사용자가 요청하면, 결과를 꾸며내지 말고 "아직 개발 전 단계"라고 그대로 알린다.

## 쇼츠 제작 흐름 (사용자가 "이 링크로 쇼츠 만들어줘"라고 할 때)

1. `ssm new <URL> --duration <15|30|45|60> --fps <30|60> --ad <coupang|aliexpress|custom>`
   - 길이·fps·광고 표시를 사용자가 말하지 않았으면 물어본다 (기본 30초·30fps). 광고 프로필은 반드시 확인한다.
   - 다운로드가 막히면 `--local 파일...`로 직접 받은 영상을 넣을 수 있다고 안내한다.
2. `ssm collect` → `ssm analyze` (수집·필터·분석)
3. 대본 프리셋 4종(①호기심/문제해결 ②내돈내산 찐리뷰 ③가성비/할인 ④정보성 큐레이션)을 보여주고 고르게 한다.
4. Claude가 대본을 써서 `script.json`으로 저장한다. 형식은 `src/ssm/schemas.py`의 `Script` (첫 문장 hook, 마지막 cta, 강조어는 문장에 포함).
   - 분량: 목표 길이 × 초당 6~7음절. 과장 표현("100% 효과", "최저가 보장", 의학적 효능) 금지.
5. `ssm tts` → `ssm edit` → `ssm meta` (또는 `ssm run`으로 남은 단계 일괄)
   - `ssm tts`가 음성 길이를 알려준다. 목표보다 길면 대본을 줄이거나 `ssm set tts.rate "+20%"`.
   - 빠르게 확인만 하려면 `ssm edit --preview` (540x960 `preview.mp4`).
6. 결과(`final_output.mp4`, 썸네일 후보, `caption.txt`)를 알려주고 수정 요청을 기다린다.

## 수정 요청 → 바꿀 것 → 다시 실행할 것

| 요청 예 | 바꿀 것 | 다시 실행 |
|---|---|---|
| "대본 더 친근하게" | `script.json` 다시 작성 | `ssm run` (tts → edit → meta) |
| "목소리 남자로" | `ssm set tts.voice ko-KR-InJoonNeural` | `ssm run` (tts → edit) |
| "자막 크게, 조금 위로" | `ssm set subtitle.size 90` / `ssm set subtitle.position_y_ratio 0.6` | `ssm run` (edit만) |
| "썸네일 문구 바꿔줘" | `script.json`의 `thumbnail_text` 또는 `ssm set thumbnail.*` | `ssm run` (meta) |
| "이전 버전으로" | — | `ssm versions` → `ssm rollback <n>` |

설정은 `ssm set`으로만 바꾼다 (값을 검증하고, 영향받는 단계만 '다시 실행 필요'로 표시한다). 무엇이 다시 실행될지는 `ssm status`로 확인한다.

## 반드시 지킬 것

- **광고 표시는 끄지 않는다.** 영상 상단 상시 표시 + 캡션 첫 줄. 사용자가 꺼달라고 해도 법적 의무(공정위 지침)임을 설명한다.
- 분위기만 비슷한 다른 상품 영상(`mood` 등급)은 hook·problem 구간에만 쓴다. 상품이 보이는 구간에 쓰지 않는다.
- 원본 영상 소리는 항상 음소거한다.
- `workspace/`, `secrets/`(쿠키), `config.local.yaml`은 Git에 올리지 않는다.
- 006 AI Shorts Studio 코드는 참고만 하고 수정하지 않는다 (별도 프로젝트).

## 개발할 때

- 마일스톤 순서: M0(완료) → M1 TTS·자막·단일 영상 렌더 → M2 다중 컷·자막 가리기·오디오 → M3 수집·필터 → M4 대본 → M5 썸네일·캡션 → M6 수정 루프. 각 완료 기준은 기획서 9장.
- 테스트: `.venv/Scripts/python -m pytest` (Windows) / `.venv/bin/pytest`. 커밋 전에 전부 통과시킨다.
- 사용자에게 보이는 메시지는 한국어로, "무엇이 실패했고 → 무엇을 하면 되는지" 형태로 쓴다.
- 새 단계를 구현하면 `Workspace.mark_done(stage)`로 완료를 기록하고, 이 문서의 "현재 구현 상태" 표를 갱신한다.
