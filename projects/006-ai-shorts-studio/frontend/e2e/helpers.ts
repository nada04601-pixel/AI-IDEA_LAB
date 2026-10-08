import { execFileSync } from "node:child_process";
import { expect, type APIRequestContext, type Page } from "@playwright/test";

export const API = "http://localhost:8100";

export async function api<T = any>(request: APIRequestContext, path: string, method = "GET", data?: unknown): Promise<T> {
  const res = await request.fetch(API + path, { method, data });
  expect(res.ok(), `${method} ${path} → ${res.status()} ${await res.text()}`).toBeTruthy();
  return res.status() === 204 ? (undefined as T) : res.json();
}

/** 프로젝트의 진행 중인 작업이 모두 끝날 때까지 기다린다. */
export async function waitJobs(request: APIRequestContext, projectId: number) {
  await expect
    .poll(async () => (await api<any[]>(request, `/api/projects/${projectId}/jobs`)).filter((j) => ["queued", "running"].includes(j.status)).length, {
      timeout: 60_000,
    })
    .toBe(0);
}

/** 대본을 넣고 스토리보드까지 만든 프로젝트. */
export async function projectWithScenes(request: APIRequestContext, title: string, script: string, target = 6) {
  const project = await api(request, "/api/projects", "POST", { title, topic: "고양이", target_duration_sec: target });
  await api(request, `/api/projects/${project.id}`, "PATCH", { script });
  const scenes = await api<any[]>(request, `/api/projects/${project.id}/storyboard`, "POST");
  return { project, scenes };
}

export function collectPageErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  return errors;
}

export async function expectNoHorizontalScroll(page: Page) {
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)).toBe(false);
}

export function hasFfprobe(): boolean {
  try {
    execFileSync("ffprobe", ["-version"], { stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
}

export function ffprobe(file: string): { streams: { codec_type: string; codec_name: string; width?: number; height?: number }[]; format: { duration: string } } {
  return JSON.parse(
    execFileSync("ffprobe", ["-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height:format=duration", "-of", "json", file]).toString(),
  );
}
