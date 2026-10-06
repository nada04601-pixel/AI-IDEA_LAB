import type { Metadata } from "next";
import { site } from "@/data/site";

export const metadata: Metadata = { title: "개인정보처리방침" };

export default function Privacy() {
  return (
    <div className="w page">
      <h1>개인정보처리방침</h1>
      <p>{site.name}(이하 &quot;사이트&quot;)는 이용자의 개인정보를 소중히 다루며, 아래와 같이 처리합니다.</p>

      <h2>1. 수집하는 정보</h2>
      <p>계산기에 입력한 값(연봉, 금액 등)은 이용자의 브라우저에서만 계산되며 서버로 전송하거나 저장하지 않습니다. 문의 메일을 보내면 이메일 주소와 본문 내용을 답변 목적으로만 사용합니다.</p>

      <h2>2. 쿠키와 광고</h2>
      <p>사이트는 서비스 개선과 광고 게재를 위해 쿠키를 사용할 수 있습니다. Google을 포함한 제3자 광고 공급업체는 쿠키를 사용해 이용자의 이전 방문 기록을 바탕으로 광고를 게재할 수 있습니다. Google이 광고 쿠키를 사용하면 Google과 파트너가 이 사이트나 다른 사이트 방문 기록을 바탕으로 광고를 게재할 수 있습니다.</p>
      <p>이용자는 <a href="https://adssettings.google.com" target="_blank" rel="noopener noreferrer">Google 광고 설정</a>에서 맞춤 광고를 해제하거나, <a href="https://www.aboutads.info/choices" target="_blank" rel="noopener noreferrer">www.aboutads.info</a>에서 제3자 공급업체의 맞춤 광고 쿠키를 해제할 수 있습니다. Google의 데이터 사용 방식은 <a href="https://policies.google.com/technologies/partner-sites" target="_blank" rel="noopener noreferrer">Google 파트너 사이트 정책</a>에서 확인할 수 있습니다. 브라우저 설정으로 쿠키를 차단할 수도 있으나, 일부 기능이 제한될 수 있습니다.</p>

      <h2>3. 방문 통계</h2>
      <p>방문 수와 페이지 이용 현황을 파악하기 위해 통계 도구를 사용할 수 있으며, 개인을 식별하지 않는 형태로 집계됩니다.</p>

      <h2>4. 보관과 파기</h2>
      <p>문의 메일은 처리가 끝난 뒤 지체 없이 삭제합니다. 법령에 따라 보관이 필요한 경우는 예외입니다.</p>

      <h2>5. 문의</h2>
      <p>개인정보와 관련한 문의는 {site.email}로 보내주세요.</p>
      <p className="note">시행일: 2026년 10월 6일</p>
    </div>
  );
}
