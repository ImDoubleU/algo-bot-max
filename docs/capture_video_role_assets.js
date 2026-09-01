async (page) => {
  const baseUrl = "http://127.0.0.1:8087/miniapp";
  const outputRoot = "D:/algo_bot_max/docs/user-guide-assets/visual-v6";

  await page.setViewportSize({ width: 1476, height: 900 });

  async function openRole(role, view) {
    await page.goto(`${baseUrl}?demo=1&demo_role=${role}&view=${view}`);
    await page.getByRole("main").waitFor();
    await page.waitForTimeout(500);
  }

  async function capture(filename) {
    await page.screenshot({
      path: `${outputRoot}/${filename}`,
      fullPage: false,
    });
  }

  async function openAdminTab(label, filename) {
    await page.getByRole("button", { name: label, exact: true }).click();
    await page.waitForTimeout(250);
    await capture(filename);
  }

  async function captureManagement(role, prefix) {
    await openRole(role, "admin");
    await capture(`${prefix}-management-summary-desktop.png`);
    await openAdminTab("Сотрудники", `${prefix}-staff-list-desktop.png`);
    await openAdminTab("Товары и остатки", `${prefix}-products-desktop.png`);
    await openAdminTab("Склады", `${prefix}-warehouses-desktop.png`);
    await openAdminTab("Импорт данных", `${prefix}-crm-import-desktop.png`);
    await openAdminTab("Связи", `${prefix}-contacts-desktop.png`);
    await openAdminTab("История", `${prefix}-history-desktop.png`);
  }

  async function captureOrderStages(role, prefix) {
    await openRole(role, "orders");
    await capture(`${prefix}-orders-tabs-desktop.png`);
    for (const [label, suffix] of [
      ["Назначить склад", "orders-assign-desktop.png"],
      ["Собрать", "orders-collect-desktop.png"],
      ["Распределить", "orders-route-desktop.png"],
    ]) {
      const button = page.getByRole("tab", { name: new RegExp(`^${label}`) }).first();
      if (await button.count()) {
        await button.click();
        await page.waitForTimeout(250);
        await capture(`${prefix}-${suffix}`);
      }
    }
  }

  async function captureCancellation(role, filename) {
    await openRole(role, "orders");
    await page.getByRole("tab", { name: /^Все/ }).click();
    await page.waitForTimeout(250);
    const menu = page.locator("details.order-more-menu").first();
    await menu.locator("summary").click();
    await menu.getByRole("button", { name: "Отменить заказ", exact: true }).click();
    await page.waitForTimeout(250);
    await capture(filename);
  }

  await openRole("admin", "accrual");
  await capture("admin-accrual-desktop.png");
  await openRole("admin", "report");
  await capture("admin-ac-report-desktop.png");
  await openRole("admin", "broadcasts");
  await capture("admin-broadcast-targets-desktop.png");
  await openRole("admin", "admin");
  await page.getByRole("button", { name: "Сотрудники", exact: true }).click();
  await page.getByRole("button", { name: "Пригласить сотрудника", exact: true }).click();
  await page.waitForTimeout(250);
  await capture("admin-staff-invite-desktop.png");

  await captureManagement("partner_director", "director");
  await captureOrderStages("partner_director", "director");
  await captureCancellation("partner_director", "director-order-cancel-form-desktop.png");
  await openRole("partner_director", "report");
  await capture("director-ac-report-desktop.png");
  await openRole("partner_director", "broadcasts");
  await capture("director-broadcast-targets-desktop.png");

  await openRole("curator", "wallet");
  await capture("curator-student-registry-desktop.png");
  await openRole("curator", "accrual");
  await capture("curator-accrual-desktop.png");
  await openRole("curator", "broadcasts");
  await capture("curator-broadcast-targets-desktop.png");
}
