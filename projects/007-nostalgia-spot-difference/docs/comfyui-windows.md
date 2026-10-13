# 3단계: ComfyUI 연결 (Windows · RTX 3060 12GB)

이 문서대로 하면 내장 그림 대신 **SDXL로 그린 수채화풍 장면**을 원본으로 쓰고, "생긴 물건/사라진 물건" 차이를 **인페인팅**(그림 일부만 다시 그리기)으로 만듭니다.

> 이 프로젝트의 Python 3.12와 ComfyUI는 따로 동작합니다. ComfyUI 휴대용(portable) 버전은 자체 Python을 함께 담고 있어 따로 설치할 것이 없습니다.

## 1. 준비물

| 항목 | 내용 |
|---|---|
| NVIDIA 드라이버 | 최신 Game Ready / Studio 드라이버 (NVIDIA 앱 또는 nvidia.com) |
| 7-Zip | ComfyUI 압축(.7z) 풀기용 — `winget install --id 7zip.7zip -e` |
| 디스크 | ComfyUI 약 5GB + SDXL 모델 약 7GB |

## 2. ComfyUI 설치 (휴대용)

1. https://github.com/comfyanonymous/ComfyUI/releases 에서 **`ComfyUI_windows_portable_nvidia.7z`**를 내려받습니다.
2. 경로에 한글·공백이 없는 곳에 풉니다. 예: `C:\AI\ComfyUI_windows_portable`
3. `run_nvidia_gpu.bat`을 더블클릭 → 검은 창에 `To see the GUI go to: http://127.0.0.1:8188`이 나오면 성공입니다. 브라우저로 그 주소를 열어 화면이 보이는지 확인합니다.

## 3. 모델 받기

**권장: SDXL 1.0 base** — 라이선스 CreativeML Open RAIL++-M (상업적 이용 가능, 유해 용도 금지 조항 준수)

1. https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0 → Files → **`sd_xl_base_1.0.safetensors`** (약 6.9GB)
2. 파일을 `C:\AI\ComfyUI_windows_portable\ComfyUI\models\checkpoints\` 에 넣습니다.
3. ComfyUI를 껐다 켭니다.

RTX 3060 12GB에서 SDXL은 무리 없이 돌아갑니다. 생성 해상도는 SDXL 기본 크기 중 10:7에 가장 가까운 **1216×832**로 설정해 두었습니다.

다른 모델을 쓰려면 파일명만 `.env`의 `COMFYUI_CHECKPOINT`에 적으면 됩니다. **Civitai 등에서 받은 모델·LoRA는 모델 페이지의 상업적 이용 허용 여부를 반드시 확인**하세요. FLUX.1 [dev]는 비상업 라이선스라 수익 채널에 쓰면 안 됩니다. ([LICENSES.md](LICENSES.md))

## 4. 프로젝트 설정

`.env`를 메모장으로 열어 아래처럼 바꿉니다.

```ini
IMAGE_SOURCE=comfyui
COMFYUI_URL=http://127.0.0.1:8188
COMFYUI_CHECKPOINT=sd_xl_base_1.0.safetensors
COMFYUI_INPAINT=true
# 예약 실행 때 ComfyUI가 꺼져 있으면 자동으로 켜기 (선택)
COMFYUI_START_CMD=C:\AI\ComfyUI_windows_portable\run_nvidia_gpu.bat
```

## 5. 확인

PowerShell에서 프로젝트 폴더로 이동한 뒤:

```powershell
.\.venv\Scripts\python.exe main.py doctor          # ComfyUI 연결됨, 장치: NVIDIA GeForce RTX 3060 (12.0GB) 확인
.\.venv\Scripts\python.exe main.py comfyui-test    # 원본 1장 + 인페인팅 1번, 걸린 시간 표시
```

`output\images\comfyui_test_base.png`(원본)와 `comfyui_test_inpaint.png`(아래 가운데에 장독 추가)를 열어 그림체와 인페인팅 품질을 확인합니다. 처음 한 번은 모델을 불러오느라 더 오래 걸립니다.

괜찮으면 영상 1개를 만들어 봅니다.

```powershell
.\.venv\Scripts\python.exe main.py make --source comfyui
```

AI 그림으로 만든 문제는 **항상 `needs_review`(검수 대상)**가 됩니다. `output\previews\<작업ID>_answer.png`에서 정답 원 5개가 모두 알아볼 만한 차이를 감싸는지 확인한 뒤 승인합니다.

```powershell
.\.venv\Scripts\python.exe main.py approve <작업ID>
```

## 6. 차이를 만드는 방식

| 차이 | AI 그림(comfyui)에서 | 품질 |
|---|---|---|
| 생긴 물건 | 바닥 쪽 빈 곳에 장독·바구니·고무신 등 옛 소품을 **인페인팅으로 그려 넣음** | 좋음 — 그림체가 자연스럽게 맞음 |
| 사라진 물건 | 디테일이 많은 곳을 "빈 바닥"으로 **인페인팅해 지움** | 보통 — 물체가 아닌 곳을 고를 때가 있음 |
| 색 / 방향 / 무늬 | 디테일이 많은 영역의 색 바꾸기·좌우 반전·무늬 덧입히기 | 보통 — 사람 확인 필요 |

- 인페인팅 결과는 **마스크 안쪽만** 원본에 합성하므로, 정답 영역 밖은 원본과 똑같이 유지되고 자동 검사가 이를 확인합니다.
- 인페인팅이 실패하면(서버 오류 등) 그 차이는 내장 방식(소품 붙이기·옆 영역 복사)으로 대신하고 로그에 남깁니다.
- 자동 선택이 마음에 들지 않는 날은 `IMAGE_SOURCE=procedural`(내장 그림)로 돌리면 사람 확인 없이 `ready`까지 갑니다. 두 방식을 섞어 쓰는 것을 권장합니다.

## 7. 문제 해결

| 증상 | 해결 |
|---|---|
| `ComfyUI 서버에 연결할 수 없습니다` | `run_nvidia_gpu.bat` 창이 떠 있는지, 주소가 `COMFYUI_URL`과 같은지 확인 |
| `/prompt 오류 400` + `ckpt_name` | 모델 파일명이 `COMFYUI_CHECKPOINT`와 정확히 같은지, `models\checkpoints\`에 있는지 확인 |
| `CUDA out of memory` | 다른 GPU 프로그램(게임·영상 편집)을 끄거나, `run_nvidia_gpu.bat`을 메모장으로 열어 줄 끝에 ` --lowvram`을 붙임 |
| 생성이 너무 느림 (수 분) | 작업 관리자 → 성능 → GPU에서 NVIDIA GPU가 쓰이는지 확인. `run_cpu.bat`으로 실행한 것은 아닌지 확인 |
| 시간 초과 | `.env`의 `COMFYUI_TIMEOUT`(초)을 늘림 |
| 그림에 사람·글자·다른 나라 건물이 나옴 | `src/image_generator.py`의 `NEGATIVE_PROMPT`에 단어 추가, 또는 다른 seed로 다시 생성 |

## 8. 예약 실행과 함께 쓰기

`COMFYUI_START_CMD`를 적어 두면 `main.py daily`가 ComfyUI가 꺼져 있을 때 한 번 켜고 최대 3분 기다립니다. 작업 스케줄러 등록은 README의 5단계를 따릅니다. 컴퓨터가 절전 상태면 실행되지 않으니, 작업 스케줄러에서 "작업을 실행하기 위해 절전 모드 해제"를 켜 두세요.
