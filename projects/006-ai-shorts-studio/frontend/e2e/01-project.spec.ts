import { expect, test } from "@playwright/test";
import { collectPageErrors, expectNoHorizontalScroll } from "./helpers";

test("프로젝트 만들기·수정·삭제 (1단계)", async ({ page }) => {
  const errors = collectPageErrors(page);
  page.on("dialog", (d) => d.accept());
  await page.goto("/");

  await page.getByRole("button", { name: "프로젝트 만들기" }).click();
  await expect(page.getByText("제목을 입력하세요.")).toBeVisible();

  const title = `고양이 쇼츠 ${Date.now()}`;
  await page.getByPlaceholder("예: 고양이가 상자를 좋아하는 이유").fill(title);
  await page.getByPlaceholder("쇼츠로 다룰 내용을 적어 주세요").fill("고양이가 상자를 좋아하는 이유");
  await page.getByRole("button", { name: "프로젝트 만들기" }).click();
  const link = page.getByRole("link", { name: new RegExp(title) });
  await expect(link).toContainText("장면 없음");
  await link.click();

  await expect(page.getByRole("heading", { name: title })).toBeVisible();
  await page.getByPlaceholder("예: 따뜻한 수채화, 빠른 컷 편집").fill("수채화");
  await page.getByRole("button", { name: "저장" }).click();
  await expect(page.getByText("저장했습니다.")).toBeVisible();
  await page.reload();
  await expect(page.getByPlaceholder("예: 따뜻한 수채화, 빠른 컷 편집")).toHaveValue("수채화");

  await page.getByRole("button", { name: "삭제" }).click();
  await page.waitForURL(/\/$/);
  await expect(page.getByRole("link", { name: new RegExp(title) })).toHaveCount(0);

  await expectNoHorizontalScroll(page);
  expect(errors).toEqual([]);
});

test("없는 프로젝트 주소는 안내 문구를 보여준다", async ({ page }) => {
  await page.goto("/projects/999999");
  await expect(page.getByText("프로젝트를 찾을 수 없습니다.")).toBeVisible();
  await page.goto("/projects/abc/script");
  await expect(page.getByText("프로젝트 번호는 정수여야 합니다.")).toBeVisible();
});
