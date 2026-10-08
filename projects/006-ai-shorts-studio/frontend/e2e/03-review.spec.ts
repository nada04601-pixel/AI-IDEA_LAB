import { expect, test } from "@playwright/test";
import { api, collectPageErrors, expectNoHorizontalScroll, ffprobe, hasFfprobe, projectWithScenes } from "./helpers";
import { writeFileSync } from "node:fs";

test("장면 생성·승인·반려·재시도 (3단계)", async ({ page, request }, testInfo) => {
  const errors = collectPageErrors(page);
  page.on("dialog", (d) => d.accept());
  const { project, scenes } = await projectWithScenes(request, "검토 테스트", "첫 장면\n\n둘째 장면\n\n셋째 장면", 9);
  await api(request, `/api/scenes/${scenes[1].id}`, "PATCH", { image_prompt: "cat [mock-fail-once]" });

  await page.goto(`/projects/${project.id}/review`);
  await expect(page.getByText(/승인 0\/3/)).toBeVisible();
  const [c1, c2, c3] = [1, 2, 3].map((n) => page.getByTestId(`review-${n}`));

  await expect(c1.getByRole("button", { name: "승인" })).toBeDisabled();
  await c1.getByRole("button", { name: "이미지 생성" }).click();
  await expect(c1.getByText("검토 필요")).toBeVisible();
  await expect(c1.locator("img")).toHaveJSProperty("complete", true);
  await c1.getByRole("button", { name: "승인" }).click();
  await expect(page.getByText(/승인 1\/3/)).toBeVisible();

  await c2.getByRole("button", { name: "이미지 생성" }).click();
  await expect(c2.getByText(/이미지 생성 실패: mock 일시 실패/)).toBeVisible();
  await c2.getByRole("button", { name: "재시도" }).click();
  await expect(c2.getByText("검토 필요")).toBeVisible();
  await c2.getByRole("button", { name: "반려" }).click();
  await c2.getByRole("button", { name: "반려 확정" }).click();
  await expect(c2.getByText("반려 사유를 입력하세요.")).toBeVisible();
  await c2.getByPlaceholder(/무엇을 고쳐야 하나요/).fill("고양이가 너무 작음");
  await c2.getByRole("button", { name: "반려 확정" }).click();
  await expect(c2.getByText(/반려 사유: 고양이가 너무 작음/)).toBeVisible();
  await expect(c2.getByRole("button", { name: "승인" })).toBeDisabled();

  await c3.getByRole("button", { name: "영상 생성" }).click();
  await expect(c3.locator("video")).toBeVisible({ timeout: 60_000 });
  const src = await c3.locator("video").getAttribute("src");
  const head = await request.get(src!, { headers: { Range: "bytes=0-99" } });
  expect(head.status()).toBe(206);
  expect(head.headers()["content-type"]).toBe("video/mp4");
  if (hasFfprobe()) {
    // 테스트용 Chromium은 H.264를 재생하지 못하므로 파일을 직접 확인한다
    const file = testInfo.outputPath("scene3.mp4");
    writeFileSync(file, await (await request.get(src!)).body());
    const info = ffprobe(file);
    expect(info.streams[0].codec_name).toBe("h264");
    expect(Math.abs(Number(info.format.duration) - scenes[2].duration_sec)).toBeLessThan(0.3);
  }

  await c1.getByRole("button", { name: "이미지 재생성" }).click();
  await expect(c1.getByRole("button", { name: "v2" })).toBeVisible();
  await expect(c1.getByRole("button", { name: "v1" })).toBeVisible();
  await expect(c1.getByText("검토 필요")).toBeVisible();

  await page.getByRole("link", { name: "작업" }).click();
  await expect(page.locator("table.jobs tbody tr")).toHaveCount(4);
  await expect(page.getByText(/실제 비용 합계 무료/)).toBeVisible();
  await page.getByRole("button", { name: /^성공 / }).click();
  await expect(page.locator("table.jobs tbody tr")).toHaveCount(4);
  await page.getByLabel("작업 종류").selectOption("video");
  await expect(page.locator("table.jobs tbody tr")).toHaveCount(1);

  await expectNoHorizontalScroll(page);
  expect(errors).toEqual([]);
});
