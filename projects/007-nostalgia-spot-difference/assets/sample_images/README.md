# 샘플 이미지 (IMAGE_SOURCE=sample)

직접 그렸거나 이용 권한이 확인된 그림만 넣으세요. 파일 이름이 주제 id로 시작하면 그 주제에 사용합니다.
예: `old_kitchen_01.png`, `corner_store_rainy.jpg` (id 목록은 `data/topics.json`)

- 그림은 10:7 비율로 가운데가 잘려 사용됩니다.
- 이 경로의 차이는 자동 편집(색 바꾸기·반전·소품 붙이기 등)이라 **항상 검수 대상(needs_review)**이 됩니다.
  `output/previews/` 의 정답 미리보기를 확인한 뒤 `python main.py approve <작업ID>` 하세요.
- 참고 채널의 영상·이미지를 캡처해서 넣지 마세요.
