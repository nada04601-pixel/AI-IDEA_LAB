import { expect, test } from "@playwright/test";
import { api, collectPageErrors, expectNoHorizontalScroll } from "./helpers";

test("대본 생성·저장과 스토리보드 편집 (2단계)", async ({ page, request }) => {
  const errors = collectPageErrors(page);
  const dialogs: string[] = [];
  page.on("dialog", (d) => {
    dialogs.push(d.message());
    d.accept();
  });
  const project = await api(request, "/api/projects", "POST", { title: "대본 테스트", topic: "고양이가 상자를 좋아하는 이유" });
  await page.goto(`/projects/${project.id}/script`);
  await expect(page.getByRole("button", { name: "스토리보드로 나누기" })).toBeDisabled();

  await page.getByRole("button", { name: "대본 초안 생성 (mock)" }).click();
  const editor = page.locator("textarea.script");
  await expect(editor).toHaveValue(/^\[mock\] 잠깐! 고양이가 상자를 좋아하는 이유/);
  expect(dialogs).toEqual([]);

  await editor.fill("첫 장면 내레이션\n\n두 번째 장면\n\n세 번째 장면");
  await expect(page.getByText("저장 안 됨")).toBeVisible();
  await expect(page.getByText(/장면 3개 예상/)).toBeVisible();

  // 저장하지 않고 탭을 옮기려 하면 확인창이 뜬다 (여기서는 이동 취소)
  page.removeAllListeners("dialog");
  page.once("dialog", (d) => {
    dialogs.push(d.message());
    d.dismiss();
  });
  await page.getByRole("link", { name: "설정" }).click();
  await expect(page).toHaveURL(/\/script$/);
  expect(dialogs.at(-1)).toContain("저장하지 않은 변경");
  page.on("dialog", (d) => {
    dialogs.push(d.message());
    d.accept();
  });

  await page.getByRole("button", { name: "저장", exact: true }).click();
  await expect(page.getByText("대본을 저장했습니다.")).toBeVisible();
  await page.reload();
  await expect(editor).toHaveValue("첫 장면 내레이션\n\n두 번째 장면\n\n세 번째 장면");

  await page.getByRole("button", { name: "스토리보드로 나누기" }).click();
  await page.waitForURL(/\/storyboard$/);
  await expect(page.getByText("장면 3개 · 합계 30초 / 목표 30초")).toBeVisible();

  const s2 = page.getByTestId("scene-2");
  await s2.locator("textarea").nth(2).fill("cute cat jumping into a cardboard box");
  await s2.locator('input[type="number"]').fill("12");
  await expect(page.getByText("저장 안 된 장면 1개")).toBeVisible();
  await s2.getByRole("button", { name: "장면 저장" }).click();
  await expect(page.getByText("저장 안 된 장면")).toHaveCount(0);

  await page.getByTestId("scene-3").getByRole("button", { name: "위로" }).click();
  await expect(page.getByTestId("scene-2").locator("textarea").first()).toHaveValue("세 번째 장면");
  await page.getByRole("button", { name: "+ 장면 추가" }).click();
  await expect(page.getByTestId("scene-4")).toBeVisible();
  await page.getByTestId("scene-1").getByRole("button", { name: "장면 삭제" }).click();
  await expect(page.getByTestId("scene-4")).toHaveCount(0);

  await page.reload();
  const cards = page.locator('[data-testid^="scene-"]');
  await expect(cards).toHaveCount(3);
  const dialogues = await cards.evaluateAll((els) => els.map((el) => el.querySelector("textarea")!.value));
  expect(dialogues).toEqual(["세 번째 장면", "두 번째 장면", ""]);

  await expectNoHorizontalScroll(page);
  expect(errors).toEqual([]);
});
