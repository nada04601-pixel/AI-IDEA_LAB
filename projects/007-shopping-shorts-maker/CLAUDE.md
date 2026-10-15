# 쇼핑 쇼츠 메이커 — Claude Code 작업 지침

해외 숏폼(샤오홍슈·도우인 등) 링크로 한국어 쇼핑 쇼츠를 만드는 CLI(`ssm`)다.
요구사항 전체는 [`ideas/007-shopping-shorts-maker/idea.md`](../../ideas/007-shopping-shorts-maker/idea.md) (v1.0).

**역할 분담 (기획서 2.1 A안):** 판단(대본 작성, 수정 요청 해석)은 Claude가, 실행(다운로드·OCR·TTS·렌더링)은 `ssm`이 한다.
대본은 Claude가 직접 써서 `workspace/{id}/script.json`에 저장한다. API 키나 유료 호출은 쓰지 않는다.

## 명령 실행 방법

- Windows: `.venv/Scripts/ssm.exe <명령>` (이 폴더에서) / Mac·Linux: `./ssm <명령>`
  - **링크는 항상 따옴표로 감싼다.** 샤오홍슈·rednote 공유 링크에는 `&`가 있고, 접근 토큰(`xsec_token`)까지 전부 있어야 열린다.
  - Windows에서 `ssm.bat`은 PowerShell·bash가 따옴표를 떼어 넘겨 `&` 뒤가 잘리므로 Claude는 `ssm.exe`를 쓴다
    (`ssm.bat`은 사람이 cmd 창에서 쓸 때만).
- 설치가 안 되어 있으면 사용자에게 `setup.bat`(Windows) 또는 `./setup.sh` 실행을 안내한다.
- 문제가 생기면 먼저 `ssm doctor`로 점검한다.

## 현재 구현 상태 (M6 완료 — v1 전 단계)

| 명령 | 상태 |
|---|---|
| `doctor`, `fonts`, `new`, `list`, `status`, `set` | 동작 |
| `collect`, `add`, `analyze`, `presets`, `script [--preset --reference --check]`, `tts`, `edit [--preview]`, `meta [--style]`, `run` | 동작 |
| `cuts [번호]`, `cut 번호 [--shot ID --reset]`, `versions`, `rollback 번호` | 동작 (M6 수정 루프) |

아직 안 되는 것: 원본 자막 인페인팅(inpaint는 지금 blur), 장면 설명으로 대본-장면 매칭, Ken Burns 줌, TikTok 검색, 플랫폼 자동 업로드(범위 밖).

AI 검사(한글 OCR·한국어 음성·CLIP 유사도·원본 자막 영역·레퍼런스 받아쓰기)는 PyTorch·CTranslate2가 필요하다.
"쓸 수 없습니다"라고 나오면 **그 검사는 하지 않은 것**이다 — 사용자에게 그대로 알리고 `ssm doctor` 안내(대개 Visual C++ 런타임)를 따르게 한다.
유사도를 모르는 후보는 안전하게 `mood`(hook·problem 구간만)로 분류된다.

구현되지 않은 단계를 사용자가 요청하면, 결과를 꾸며내지 말고 "아직 개발 전 단계"라고 그대로 알린다.

## 쇼츠 제작 흐름 (사용자가 "이 링크로 쇼츠 만들어줘"라고 할 때)

목표: 사용자 개입은 **① 시작 직후 질문 한 번(프리셋·광고 표시·상품 정보 확인)** 과 **② 결과 확인** 두 번 (기획서 1장).
그 사이에는 묻지 말고 끝까지 진행한다. 명령 출력의 [주의]는 숨기지 말고 마지막 보고에 모아서 알린다.

1. **프로젝트 만들기** — `ssm new <URL> --duration 30 --fps 30 -y`
   - 사용자가 길이·fps를 말했으면 그 값, 아니면 기본값(30초·30fps)으로 만들고 보고 때 알린다 (`ssm set project.duration_sec 45`로 바꿀 수 있음).
   - 링크 대신 직접 받은 영상 파일을 주면 `ssm new --local 파일1 --local 파일2 -y`.
2. **수집·분석** — `ssm collect` → `ssm analyze`
   - collect 결과 표(채택·제외 사유)를 기억해 둔다. 기준 영상이 막히면(쿠키 만료 등) `docs/cookies.md`를 안내하고 멈춘다.
   - 같은 상품이 3개 미만이어도 계속 진행하되, 보고 때 같은 상품 링크·파일을 더 달라고 한다.
3. **질문 한 번 (AskUserQuestion으로 한꺼번에)**
   - 대본 프리셋: `ssm presets`의 4종 (①호기심/문제해결 ②내돈내산 찐리뷰 ③가성비/할인 ④정보성 큐레이션). 상품에 맞는 것을 추천 표시.
   - 광고 표시: 쿠팡 파트너스 / 알리익스프레스 어필리에이트 / 직접 입력 — **반드시 확인** (법적 의무).
   - 상품 정보 확인: `candidates.json` 기준 영상의 제목·설명(중국어)과 장면을 보고 만든 상품명·핵심 특징 3개 초안, 가격대(모르면 사용자에게 물음).
   - 답을 받으면 `ssm set ad_disclosure.profile coupang` (custom이면 `ssm set ad_disclosure.custom_text "문구"`도).
4. **대본 요청서** — `ssm script --preset N` (사용자가 따라 하고 싶은 영상·대본을 줬으면 `--reference 링크|파일|대본.txt`)
   - 출력된 `script_prompt.md`를 읽고, `script_frames.jpg`(장면 모음)를 **직접 열어 본다**. 요청서 규칙대로 쓴다.
5. **대본·문구 작성** — `script.json`과 `meta.json`(제목 3·썸네일 문구 3안·캡션 요약·해시태그·카테고리) 저장 → `ssm script --check`
   - 형식은 `src/ssm/schemas.py`의 `Script`. 분량은 길이 × 초당 6~7음절. 금지 표현(과장·최저가·의학적 효능 등)은 검사에서 막힌다.
   - 오류가 나오면 고쳐서 다시 검사한다. [주의](훅 길이·CTA 등)도 가능하면 고친다.
6. **렌더링** — `ssm run` (tts → edit → meta)
   - `ssm tts`가 음성 길이를 알려준다. 목표보다 많이 길면 대본을 줄이거나 `ssm set tts.rate "+20%"` 후 `ssm run`.
7. **보고 (개입 ②)** — `final_output.mp4` 경로·길이, `thumbnails_preview.jpg`(썸네일 3안, **직접 열어 보고** 어떤 안인지 설명),
   `caption.txt`(제목 후보 3개 포함), 프리셋, 대본 전문, 모아 둔 [주의](OCR 못 함·소스 부족·BGM 없음 등)를 알리고
   썸네일 고르기와 수정 요청을 기다린다.
   - 빠르게 확인용이면 `ssm edit --preview` (540x960 `preview.mp4`).
   - 문장마다 `sfx`(whoosh·swish·pop·ding)를 달 수 있다. 훅=whoosh, 강조=pop/ding, 전환=swish. 2~3개면 충분.

## 수정 요청 → 바꿀 것 → 다시 실행할 것

| 요청 예 | 바꿀 것 | 다시 실행 |
|---|---|---|
| "대본 더 친근하게" | `script.json` 다시 작성 → `ssm script --check` | `ssm run` (tts → edit) |
| "다른 프리셋으로" | `ssm script --preset N` → 요청서대로 `script.json` 다시 작성 → `ssm script --check` | `ssm run` (tts → edit) |
| "이 영상 말투처럼" | `ssm script --reference 링크·파일·대본.txt` → 다시 작성 → `ssm script --check` | `ssm run` |
| "목소리 남자로" | `ssm set tts.voice ko-KR-InJoonNeural` | `ssm run` (tts → edit) |
| "자막 크게, 조금 위로" | `ssm set subtitle.size 90` / `ssm set subtitle.position_y_ratio 0.6` | `ssm run` (edit만) |
| "썸네일 문구 바꿔줘" / "제목·해시태그 바꿔줘" | `meta.json`의 `thumbnail_texts` / `titles` / `hashtags` | `ssm run` (meta만) |
| "썸네일 글씨 크게·색 바꿔" | `ssm set thumbnail.top_size 170` / `ssm set thumbnail.top_color "#FF4D4D"` | `ssm run` (meta만) |
| "이 썸네일 스타일처럼" | `ssm meta --style 이미지` (색·위치를 뽑아 `thumbnail_style.json`, 이미지를 보고 값 보정 가능) | (자동 실행) |
| "세 번째 컷 다른 장면으로" / "이 장면 별로야" | `ssm cuts`로 번호 확인 → `ssm cut 3` (자동으로 다른 좋은 장면) 또는 `ssm cut 3 --shot 02-004` (`ssm cuts 3`이 후보를 보여줌). 취소는 `ssm cut 3 --reset` | `ssm run` (edit만) |
| "이전 버전으로" | — | `ssm versions`(보관 시각·메모) → `ssm rollback <n>` |
| "영상 더 넣어줘" / 소스 부족 경고 | `ssm add 파일...` | `ssm run` (analyze → edit) |
| "이 영상은 다른 상품이야" | `selected.json`에서 그 영상 `grade`를 `mood`로 (hook·problem 구간에만 쓰임) | `ssm run` (analyze → edit) |
| "이 영상은 빼줘" | `selected.json`에서 그 항목 삭제 + `raw_videos/`의 그 파일 삭제 | `ssm run` (analyze → edit) |
| "검색어 바꿔서 다시 모아줘" | `ssm collect --keyword 새검색어` | 이어서 `ssm run` |
| "원본 자막이 덜 가려져" / "엉뚱한 곳이 흐려져" | `analysis.json`의 `text_boxes` 좌표 수정·삭제 | `ssm run` (edit) |
| "BGM 빼줘" / "BGM 바꿔줘" | `ssm set audio.bgm none` / `ssm set audio.bgm assets/bgm/파일.mp3` | `ssm run` (edit) |

설정은 `ssm set`으로만 바꾼다 (값을 검증하고, 영향받는 단계만 '다시 실행 필요'로 표시한다). 무엇이 다시 실행될지는 `ssm status`로 확인한다.
`script.json`·`meta.json`은 Claude가 직접 고쳐도 된다 — `ssm run`이 바뀐 것을 알아채고 (대본이면 검사부터) 필요한 단계만 다시 돌린다.

버전: `ssm run`(또는 tts·edit·meta)이 **성공할 때마다** 그 결과를 `versions/v{n}`에 보관한다 (같은 내용이면 새로 만들지 않음).
수정 요청을 처리한 뒤 보고할 때 몇 번 버전인지 알려 두면 "아까 걸로 돌려줘"에 바로 `ssm rollback`할 수 있다.
컷 배치는 같은 대본·영상이면 매번 똑같이 나온다 — 그래서 자막·설정만 바꿔도 컷이 그대로이고, `ssm cut`으로 바꾼 컷도 유지된다.
대본이 바뀌어 컷 위치가 달라지면 바꿨던 컷 설정은 적용되지 않고 [주의]로 알려준다 (그때 `ssm cuts`로 다시 확인).

## 반드시 지킬 것

- **광고 표시는 끄지 않는다.** 영상 상단 상시 표시 + 캡션 첫 줄. 사용자가 꺼달라고 해도 법적 의무(공정위 지침)임을 설명한다.
- 분위기만 비슷한 다른 상품 영상(`mood` 등급)은 hook·problem 구간에만 쓴다. 상품이 보이는 구간에 쓰지 않는다.
- 원본 영상 소리는 항상 음소거한다.
- `workspace/`, `secrets/`(쿠키), `config.local.yaml`은 Git에 올리지 않는다.
- 006 AI Shorts Studio 코드는 참고만 하고 수정하지 않는다 (별도 프로젝트).

## 개발할 때

- 마일스톤 M0~M6 모두 완료 (기획서 9장). 이후 작업은 '아직 안 되는 것' 목록과 실제 사용에서 나온 문제를 우선한다.
- 테스트: `.venv/Scripts/python -m pytest` (Windows) / `.venv/bin/pytest`. 커밋 전에 전부 통과시킨다.
- 사용자에게 보이는 메시지는 한국어로, "무엇이 실패했고 → 무엇을 하면 되는지" 형태로 쓴다.
- 새 단계를 구현하면 `Workspace.mark_done(stage)`로 완료를 기록하고, 이 문서의 "현재 구현 상태" 표를 갱신한다.
