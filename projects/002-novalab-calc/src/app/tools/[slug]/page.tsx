import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { getTool, tools } from "@/data/tools";
import { RATES } from "@/data/rates/2026";
import Link from "next/link";
import { guidesForTool } from "@/data/guides";
import NetSalaryCalculator from "@/components/NetSalaryCalculator";
import SeveranceCalculator from "@/components/SeveranceCalculator";
import LoanCalculator from "@/components/LoanCalculator";
import SavingsCalculator from "@/components/SavingsCalculator";
import WeeklyHolidayPayCalculator from "@/components/WeeklyHolidayPayCalculator";
import BrokerageCalculator from "@/components/BrokerageCalculator";

type Props = { params: Promise<{ slug: string }> };

export function generateStaticParams() {
  return tools.map((t) => ({ slug: t.slug }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const tool = getTool((await params).slug);
  if (!tool) return {};
  return {
    title: tool.title,
    description: tool.metaDescription,
    alternates: { canonical: `/tools/${tool.slug}` },
  };
}

// 새 도구를 추가하면 여기에 슬러그와 컴포넌트를 연결하세요.
const calculators: Record<string, React.ReactNode> = {
  "net-salary": <NetSalaryCalculator />,
  "severance-pay": <SeveranceCalculator />,
  "loan-interest": <LoanCalculator />,
  "savings-interest": <SavingsCalculator />,
  "weekly-holiday-pay": <WeeklyHolidayPayCalculator />,
  "brokerage-fee": <BrokerageCalculator />,
};

export default async function ToolPage({ params }: Props) {
  const tool = getTool((await params).slug);
  if (!tool) notFound();
  const related = guidesForTool(tool.slug);

  return (
    <article className="w page">
      <h1>{tool.title}</h1>
      <p className="lead">{tool.intro}</p>
      {calculators[tool.slug]}

      {tool.howTo.map((s) => (
        <section key={s.heading}>
          <h2>{s.heading}</h2>
          <p>{s.body}</p>
        </section>
      ))}

      <section>
        <h2>자주 묻는 질문</h2>
        {tool.faq.map((f) => (
          <details key={f.q}>
            <summary>{f.q}</summary>
            <p>{f.a}</p>
          </details>
        ))}
      </section>

      {related.length > 0 && (
        <aside className="related">
          <h2>관련 가이드</h2>
          <ul>
            {related.map((g) => <li key={g.slug}><Link href={`/guides/${g.slug}`}>{g.title}</Link></li>)}
          </ul>
        </aside>
      )}

      <p className="note">
        적용 기준: {RATES.year}년 요율(확인 {RATES.checkedAt}). 참고용 추정치이며 실제 금액은 회사, 금융회사, 관계 기관의 안내를 따릅니다.
      </p>

      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "FAQPage",
            mainEntity: tool.faq.map((f) => ({
              "@type": "Question",
              name: f.q,
              acceptedAnswer: { "@type": "Answer", text: f.a },
            })),
          }),
        }}
      />
    </article>
  );
}
