import { writeFileSync } from "node:fs";
import { expect, test } from "@playwright/test";
import { api, collectPageErrors, expectNoHorizontalScroll, ffprobe, hasFfprobe, projectWithScenes, waitJobs } from "./helpers";

test("음성·자막·MP4 렌더링과 내려받기 (4단계)", async ({ page, request }, testInfo) => {
  const errors = collectPageErrors(page);
  page.on("dialog", (d) => d.accept());
  const ffmpeg = await api(request, "/api/system/ffmpeg");
  test.skip(!ffmpeg.available, "FFmpeg가 없어 렌더링을 확인할 수 없습니다.");

  const { project, scenes } = await projectWithScenes(request, "렌더 E2E", "고양이는 상자를 좋아해요.\n\n상자 안은 안전하니까요!", 6);
  await api(request, `/api/scenes/${scenes[0].id}/generate-image`, "POST");
  await waitJobs(request, project.id);

  await page.goto(`/projects/${project.id}/render`);
  await expect(page.getByText(/FFmpeg \S+ 사용 가능/)).toBeVisible();
  const problems = page.getByTestId("problems");
  await expect(problems).toContainText("장면 1이(가) 아직 승인되지");
  await expect(problems).toContainText("장면 2에 이미지나 영상이 없습니다");
  await expect(problems).toContainText("음성이 없습니다");
  await expect(page.getByRole("button", { name: "MP4 렌더링" })).toBeDisabled();
  await expect(page.locator("ol.cues li")).toHaveCount(2);

  await api(request, `/api/scenes/${scenes[0].id}/approve`, "POST");
  await api(request, `/api/scenes/${scenes[1].id}/generate-video`, "POST");
  await waitJobs(request, project.id);
  await api(request, `/api/scenes/${scenes[1].id}/approve`, "POST");
  await page.reload();

  await page.getByRole("button", { name: "음성 만들기 (2개 장면)" }).click();
  await expect(page.getByRole("button", { name: "모든 음성 준비됨" })).toBeVisible();
  await expect(page.getByText("렌더링 준비가 끝났습니다.")).toBeVisible();
  await expect(page.getByTestId("render-scene-2")).toContainText("영상");

  await page.getByRole("button", { name: "MP4 렌더링" }).click();
  const result = page.getByTestId("render-result");
  await expect(result).toBeVisible({ timeout: 90_000 });
  await expect(result).toContainText("v1");
  await expect(result).toContainText("1080×1920");
  await expect(result).toContainText("음성 포함");

  const href = await page.getByRole("link", { name: "MP4 내려받기" }).getAttribute("href");
  const res = await request.get(href!);
  expect(decodeURIComponent(res.headers()["content-disposition"])).toContain("렌더_E2E_v1.mp4");
  if (hasFfprobe()) {
    const file = testInfo.outputPath("final.mp4");
    writeFileSync(file, await res.body());
    const info = ffprobe(file);
    const kinds = Object.fromEntries(info.streams.map((s) => [s.codec_type, s]));
    expect([kinds.video.codec_name, kinds.video.width, kinds.video.height]).toEqual(["h264", 1080, 1920]);
    expect(kinds.audio.codec_name).toBe("aac");
    expect(kinds.subtitle.codec_name).toBe("mov_text");
    expect(Math.abs(Number(info.format.duration) - 6)).toBeLessThan(0.15);
  }

  await api(request, `/api/scenes/${scenes[1].id}`, "PATCH", { dialogue: "바뀐 대사" });
  await page.reload();
  await expect(page.getByTestId("render-scene-2")).toContainText("대사 바뀜");
  await expect(page.getByRole("button", { name: "다시 렌더링" })).toBeDisabled();
  await page.getByRole("checkbox", { name: "음성 넣기" }).uncheck();
  await expect(problems).not.toContainText("음성");

  await page.goto("/");
  await expect(page.getByRole("link", { name: /렌더 E2E/ })).toContainText("렌더 v1");

  await expectNoHorizontalScroll(page);
  expect(errors).toEqual([]);
});
