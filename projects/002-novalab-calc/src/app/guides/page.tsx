import Link from "next/link";
import type { Metadata } from "next";
import { guides } from "@/data/guides";

export const metadata: Metadata = {
  title: "생활 계산 가이드",
  description: "월급, 퇴직금, 대출, 예적금, 부동산 계산에 필요한 기준과 제도를 쉽게 풀어 쓴 가이드 모음입니다.",
  alternates: { canonical: "/guides" },
};

export default function Guides() {
  return (
    <div className="w page">
      <h1>생활 계산 가이드</h1>
      <p className="lead">계산기에 숫자를 넣기 전에 알아두면 좋은 기준과 제도를 정리했습니다.</p>
      <ul className="list">
        {guides.map((g) => (
          <li key={g.slug}>
            <Link href={`/guides/${g.slug}`}>{g.title}</Link>
            <p>{g.description}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
