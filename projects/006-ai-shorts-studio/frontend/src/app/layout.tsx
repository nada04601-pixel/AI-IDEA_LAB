import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Shorts Studio",
  description: "장면별 승인으로 만드는 쇼츠 제작 도구",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        <header className="topbar">
          <Link href="/">AI Shorts Studio</Link>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
