# 노바랩 계산소 (novalabs.co.kr)

Next.js (App Router) + TypeScript 기반 계산기 모음 사이트입니다.

## 실행
```bash
npm install
npm run dev      # http://localhost:3000
npm run build && npm start
```

## 구조
- `src/lib/calculators/` 계산 로직(순수 함수)
- `src/data/rates/2026.ts` 연도별 요율·기준값 (출처와 확인일 기록)
- `src/data/tools.ts` 도구 목록과 설명·FAQ (본문, 메타데이터, FAQ 구조화 데이터로 사용)
- `src/data/guides.ts` 가이드 글 (`/guides/[slug]`), `tool` 필드로 계산기 페이지와 서로 연결
- `src/app/ads.txt/route.ts` 게시자 ID가 설정되면 `/ads.txt` 생성
- `src/app/tools/[slug]/page.tsx` 도구 페이지 (슬러그와 컴포넌트 연결)

## 새 계산기 추가 (3단계)
1. `src/lib/calculators/`에 계산 함수 작성
2. `src/components/`에 입력·결과 컴포넌트 작성
3. `src/data/tools.ts`에 설명·FAQ 추가하고 `tools/[slug]/page.tsx`의 `calculators`에 컴포넌트 연결

## 애드센스 승인 절차
1. `src/data/site.ts`의 `email`을 실제 수신 가능한 주소로 변경 (`contact@novalabs.co.kr` 메일 수신 설정 또는 개인 메일)
2. 배포: Cloudflare Pages (아래 "Cloudflare Pages 배포" 참고) → Custom domains에 `novalabs.co.kr` 추가
3. Search Console에 도메인 등록 후 `https://novalabs.co.kr/sitemap.xml` 제출, 색인 생성 확인 (1~2주)
4. 애드센스 가입 → 사이트 `novalabs.co.kr` 추가 → 게시자 ID(`ca-pub-...`) 확인
5. Cloudflare Pages 환경변수 `NEXT_PUBLIC_ADSENSE_CLIENT`에 게시자 ID 입력 후 재배포
   - 광고 스크립트, `google-adsense-account` 메타 태그, `/ads.txt`가 자동 생성됨
6. 애드센스에서 "사이트 확인"(메타 태그 또는 ads.txt 방식) → "검토 요청"
7. 승인 후 애드센스 > 광고 > 자동 광고 켜기 (추가 코드 불필요)

승인 확률을 높이려면 가이드 글을 꾸준히 추가하세요(목표 20~30편). 새 글은 `src/data/guides.ts`에 항목을 추가하면 목록, 사이트맵, 관련 글에 자동 반영됩니다.

## Cloudflare Pages 배포
`next.config.ts`의 `output: "export"`로 모든 페이지를 `out/` 폴더에 정적 HTML로 만듭니다.

Workers & Pages → Create → Pages → Connect to Git → `AI-IDEA_LAB` 선택 후:

| 항목 | 값 |
|---|---|
| Framework preset | Next.js (Static HTML Export) |
| Root directory | `projects/002-novalab-calc` |
| Build command | `npm run build` |
| Build output directory | `out` |
| 환경변수 | `NEXT_PUBLIC_ADSENSE_CLIENT`, `NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION` (선택) |

Settings → Builds → Build watch paths의 Include paths를 `projects/002-novalab-calc/*`로 지정하면 이 폴더가 바뀔 때만 배포됩니다.
`NEXT_PUBLIC_` 값은 빌드할 때 HTML에 들어가므로, 바꾼 뒤에는 꼭 다시 배포하세요.

## 매년 점검
- 국민연금 기준소득월액 상·하한: 매년 7월
- 건강보험·장기요양 요율: 매년 초
- 소득세 세율·공제: 세법 개정 시
- 최저임금: 매년 8월 고시, 다음 해 1월 시행
- 가이드 글의 `date`와 본문 수치
