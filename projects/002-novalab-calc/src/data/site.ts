export const site = {
  name: "노바랩 계산소",
  domain: "novalabs.co.kr",
  url: "https://novalabs.co.kr",
  tagline: "월급부터 대출까지, 헷갈리는 계산을 쉽게",
  description:
    "연봉 실수령액, 퇴직금, 대출이자처럼 생활에 필요한 계산을 무료로 해보고 계산 기준까지 확인할 수 있는 노바랩 계산소입니다.",
  email: "contact@novalabs.co.kr", // TODO: 실제 수신 가능한 주소로 변경
  year: 2026,
  // 애드센스 게시자 ID(ca-pub-로 시작). 비워두면 광고 스크립트와 ads.txt가 나가지 않습니다.
  adsenseClient: process.env.NEXT_PUBLIC_ADSENSE_CLIENT ?? "",
  // Search Console HTML 태그 인증값(content 속성 값)
  googleVerification: process.env.NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION ?? "",
};
