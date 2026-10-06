import type { NextConfig } from "next";

// 모든 페이지가 정적이므로 out/ 폴더로 내보내 Cloudflare Pages에 그대로 올립니다.
const nextConfig: NextConfig = { reactStrictMode: true, output: "export" };
export default nextConfig;
