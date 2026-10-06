import Link from "next/link";
import type { Metadata } from "next";
import { tools } from "@/data/tools";
import { guides } from "@/data/guides";
import { site } from "@/data/site";

export const metadata: Metadata = { alternates: { canonical: "/" } };

export default function Home() {
  return (
    <div className="w page">
      <h1>{site.name}</h1>
      <p className="lead">{site.tagline}. 계산 결과와 함께 어떤 기준으로 계산했는지도 설명합니다.</p>
      <div className="g">
        {tools.map((t) => (
          <Link key={t.slug} href={`/tools/${t.slug}`} className="c">
            <h2>{t.title}</h2>
            <p>{t.short}</p>
          </Link>
        ))}
      </div>

      <h2>생활 계산 가이드</h2>
      <ul className="list">
        {guides.slice(0, 5).map((g) => (
          <li key={g.slug}>
            <Link href={`/guides/${g.slug}`}>{g.title}</Link>
            <p>{g.description}</p>
          </li>
        ))}
      </ul>
      <p><Link href="/guides">가이드 전체 보기 →</Link></p>
    </div>
  );
}
