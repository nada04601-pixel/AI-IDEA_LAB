import type { MetadataRoute } from "next";
import { tools } from "@/data/tools";
import { guides } from "@/data/guides";
import { site } from "@/data/site";

export const dynamic = "force-static";

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();
  const pages = ["", "/guides", "/about", "/contact", "/terms", "/privacy"].map((p) => ({
    url: `${site.url}${p}`,
    lastModified: now,
  }));
  const toolPages = tools.map((t) => ({ url: `${site.url}/tools/${t.slug}`, lastModified: now }));
  const guidePages = guides.map((g) => ({ url: `${site.url}/guides/${g.slug}`, lastModified: new Date(g.date) }));
  return [...pages, ...toolPages, ...guidePages];
}
