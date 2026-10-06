import Link from "next/link";
import { site } from "@/data/site";

export default function Header() {
  return (
    <header>
      <div className="w">
        <Link href="/" className="logo">{site.name}</Link>
        <nav>
          <Link href="/">계산기</Link>
          <Link href="/guides">가이드</Link>
          <Link href="/about">소개</Link>
        </nav>
      </div>
    </header>
  );
}
