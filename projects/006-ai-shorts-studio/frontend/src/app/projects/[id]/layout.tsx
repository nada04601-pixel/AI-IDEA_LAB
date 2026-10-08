"use client";

import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { confirmLeave } from "@/lib/useUnsavedWarning";

const TABS = [
  { href: "", label: "설정" },
  { href: "/script", label: "대본" },
  { href: "/storyboard", label: "스토리보드" },
  { href: "/review", label: "검토" },
  { href: "/render", label: "렌더링" },
  { href: "/jobs", label: "작업" },
];

export default function ProjectLayout({ children }: { children: React.ReactNode }) {
  const { id } = useParams<{ id: string }>();
  const pathname = usePathname();
  const base = `/projects/${id}`;
  const guard = (e: React.MouseEvent) => {
    if (!confirmLeave()) e.preventDefault();
  };

  return (
    <>
      <nav className="subnav">
        <Link href="/" onClick={guard}>
          ← 목록
        </Link>
        <div className="tabs">
          {TABS.map((t) => (
            <Link key={t.label} href={base + t.href} onClick={guard} className={pathname === base + t.href ? "tab active" : "tab"}>
              {t.label}
            </Link>
          ))}
        </div>
      </nav>
      {children}
    </>
  );
}
