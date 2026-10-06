import type { Metadata, Viewport } from "next";
import "./globals.css";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import { site } from "@/data/site";

export const metadata: Metadata = {
  metadataBase: new URL(site.url),
  title: { default: `${site.name} | ${site.tagline}`, template: `%s | ${site.name}` },
  description: site.description,
  openGraph: { siteName: site.name, type: "website", locale: "ko_KR" },
  ...(site.googleVerification && { verification: { google: site.googleVerification } }),
  // 애드센스 사이트 소유권 확인용 메타 태그
  ...(site.adsenseClient && { other: { "google-adsense-account": site.adsenseClient } }),
};

export const viewport: Viewport = { width: "device-width", initialScale: 1, viewportFit: "cover" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <head>
        {/* next/script는 data-nscript 속성을 붙여 애드센스 경고가 나므로 일반 script 태그를 씁니다.
            ID가 비어 있을 때 빈 문자열이 <head>에 텍스트로 들어가지 않도록 null을 반환합니다. */}
        {site.adsenseClient ? (
          <script
            async
            src={`https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${site.adsenseClient}`}
            crossOrigin="anonymous"
          />
        ) : null}
      </head>
      <body>
        <Header />
        <main>{children}</main>
        <Footer />
      </body>
    </html>
  );
}
