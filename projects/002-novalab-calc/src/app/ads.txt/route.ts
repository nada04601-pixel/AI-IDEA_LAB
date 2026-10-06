import { site } from "@/data/site";

export const dynamic = "force-static";

// 애드센스 게시자 ID가 설정되어 있으면 /ads.txt를 제공합니다.
export function GET() {
  const pub = site.adsenseClient.replace(/^ca-/, "");
  if (!pub) return new Response("Not Found", { status: 404 });
  return new Response(`google.com, ${pub}, DIRECT, f08c47fec0942fa0\n`, {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}
