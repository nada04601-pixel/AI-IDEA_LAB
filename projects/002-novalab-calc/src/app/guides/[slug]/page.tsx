import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { getGuide, guides } from "@/data/guides";
import { getTool } from "@/data/tools";
import { site } from "@/data/site";

type Props = { params: Promise<{ slug: string }> };

export function generateStaticParams() {
  return guides.map((g) => ({ slug: g.slug }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const guide = getGuide((await params).slug);
  if (!guide) return {};
  return {
    title: guide.title,
    description: guide.description,
    alternates: { canonical: `/guides/${guide.slug}` },
    openGraph: { type: "article", title: guide.title, description: guide.description },
  };
}

export default async function GuidePage({ params }: Props) {
  const guide = getGuide((await params).slug);
  if (!guide) notFound();
  const tool = guide.tool ? getTool(guide.tool) : undefined;
  const others = guides.filter((g) => g.slug !== guide.slug && g.tool === guide.tool).slice(0, 3);

  return (
    <article className="w page">
      <h1>{guide.title}</h1>
      <p className="meta">
        <time dateTime={guide.date}>{guide.date.replaceAll("-", ".")}</time> · {site.name}
      </p>
      <p className="lead">{guide.description}</p>

      {guide.sections.map((s) => (
        <section key={s.heading}>
          <h2>{s.heading}</h2>
          {s.body.map((para, i) => <p key={i}>{para}</p>)}
        </section>
      ))}

      {tool && (
        <p>
          <Link className="btn" href={`/tools/${tool.slug}`}>{tool.title} 바로가기</Link>
        </p>
      )}

      {others.length > 0 && (
        <aside className="related">
          <h2>함께 읽으면 좋은 글</h2>
          <ul>
            {others.map((g) => <li key={g.slug}><Link href={`/guides/${g.slug}`}>{g.title}</Link></li>)}
          </ul>
        </aside>
      )}

      <p className="note">
        이 글은 작성일 기준의 일반적인 정보이며 법령이나 제도가 바뀌면 달라질 수 있습니다. 개별 상황에 대한 판단은 관계 기관이나 전문가에게 확인하세요.
      </p>

      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "Article",
            headline: guide.title,
            description: guide.description,
            datePublished: guide.date,
            dateModified: guide.date,
            author: { "@type": "Organization", name: site.name, url: site.url },
            mainEntityOfPage: `${site.url}/guides/${guide.slug}`,
          }),
        }}
      />
    </article>
  );
}
