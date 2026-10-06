import Link from "next/link";
import { site } from "@/data/site";

export default function Footer() {
  return (
    <footer>
      <div className="w">
        <nav>
          <Link href="/about">소개</Link>
          <Link href="/contact">문의</Link>
          <Link href="/terms">이용약관</Link>
          <Link href="/privacy">개인정보처리방침</Link>
        </nav>
        <p>계산 결과는 참고용이며 실제 금액과 다를 수 있습니다. 중요한 결정 전에는 공식 기관이나 전문가에게 확인하세요.</p>
        <p>© {site.year} {site.name} ({site.domain})</p>
      </div>
    </footer>
  );
}
