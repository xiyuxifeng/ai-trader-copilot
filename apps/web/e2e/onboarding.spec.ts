import { expect, test } from "@playwright/test";

test("complete settings and reach a truthful today page", async ({ page }, testInfo) => {
  await page.goto("/");

  const welcome = page.getByRole("heading", {
    name: "把研究交给系统，把决定留给自己。",
  });

  if (await welcome.isVisible()) {
    await page.getByRole("button", { name: "用推荐设置开始" }).click();
  } else {
    await page.getByRole("button", { name: "设置" }).click();
    await page.getByRole("button", { name: "调整偏好" }).click();
  }

  await expect(page.getByRole("heading", { name: "你通常持有多久？" })).toBeVisible();
  await page.getByLabel("波段").check();
  await page.getByRole("button", { name: "继续" }).click();

  await expect(page.getByRole("heading", { name: "你更看重哪种风险方式？" })).toBeVisible();
  await page.getByLabel("均衡").check();
  await page.getByRole("button", { name: "继续" }).click();

  await page.getByLabel("最大仓位").fill("20");
  await page.getByRole("button", { name: "继续" }).click();

  await page.getByLabel("每日摘要时间").fill("18:30");
  await page.getByRole("button", { name: "完成设置" }).click();

  await expect(page.getByRole("heading", { name: "目前不需要你做任何操作。" })).toBeVisible();
  await expect(page.getByText("行情数据尚未接入，今天不生成操作建议。")).toBeVisible();
  await expect(page.getByRole("navigation", { name: "主导航" }).getByRole("button")).toHaveCount(3);

  const horizontalOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(horizontalOverflow).toBe(false);
  await page.screenshot({ path: testInfo.outputPath("today-page.png"), fullPage: true });
});
