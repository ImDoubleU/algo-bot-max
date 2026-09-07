from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Browser, Page, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "user-guide-assets" / "visual-v6"
BASE_URL = "http://127.0.0.1:8087/miniapp"


def new_page(browser: Browser, *, mobile: bool = False) -> Page:
    viewport = {"width": 390, "height": 844} if mobile else {"width": 1440, "height": 900}
    return browser.new_page(viewport=viewport, device_scale_factor=1)


def open_role(page: Page, role: str, view: str) -> None:
    page.goto(
        f"{BASE_URL}?demo=1&demo_role={role}&view={view}",
        wait_until="networkidle",
    )
    page.locator("main.workspace").wait_for(state="visible")
    page.wait_for_timeout(300)


def capture(page: Page, filename: str, *, full_page: bool = False) -> None:
    target = OUTPUT / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    if full_page:
        viewport = page.viewport_size or {"width": 390, "height": 844}
        document_height = page.evaluate(
            "Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)"
        )
        page.set_viewport_size({"width": viewport["width"], "height": document_height})
        page.screenshot(path=target, full_page=False)
        page.set_viewport_size(viewport)
    else:
        page.screenshot(path=target, full_page=False)
    print(target.relative_to(ROOT))


def open_admin_tab(page: Page, tab: str) -> None:
    page.locator(f'[data-admin-tab="{tab}"]').click()
    page.wait_for_timeout(180)


def capture_profiles(browser: Browser) -> None:
    desktop_roles = (
        ("student", "student-dashboard-desktop.png"),
        ("parent", "parent-dashboard-desktop.png"),
        ("teacher", "teacher-dashboard-desktop.png"),
        ("curator", "curator-dashboard-desktop.png"),
        ("admin", "admin-dashboard-desktop.png"),
        ("partner_director", "director-dashboard-desktop.png"),
    )
    for role, filename in desktop_roles:
        page = new_page(browser)
        open_role(page, role, "dashboard")
        capture(page, filename)
        page.close()

    for role, filename in (
        ("student", "student-dashboard-mobile.png"),
        ("parent", "parent-dashboard-mobile.png"),
        ("teacher", "teacher-dashboard-mobile.png"),
    ):
        page = new_page(browser, mobile=True)
        open_role(page, role, "dashboard")
        capture(page, filename, full_page=True)
        page.close()


def capture_store_and_cart(browser: Browser) -> None:
    page = new_page(browser)
    open_role(page, "student", "store")
    capture(page, "store-desktop.png")
    page.locator("#productSortMenu > summary").click()
    capture(page, "store-sort-desktop.png")
    page.close()

    page = new_page(browser, mobile=True)
    open_role(page, "student", "store")
    capture(page, "store-mobile.png", full_page=True)
    page.locator("#mobileStoreFiltersButton").click()
    page.wait_for_timeout(150)
    capture(page, "store-filters-mobile.png")
    page.locator("#closeStoreFiltersButton").click()
    page.locator("[data-product-details]").first.click()
    page.locator("#productDialog").wait_for(state="visible")
    capture(page, "product-dialog-mobile.png")
    page.close()

    page = new_page(browser, mobile=True)
    open_role(page, "student", "store")
    page.locator("[data-add]").first.click()
    page.locator("#storeCartBar").click()
    page.wait_for_timeout(150)
    capture(page, "cart-mobile.png", full_page=True)
    page.locator("#placeOrderButton").click()
    page.locator("#checkoutDialog").wait_for(state="visible")
    capture(page, "checkout-dialog-mobile.png")
    page.close()


def capture_family(browser: Browser) -> None:
    page = new_page(browser)
    open_role(page, "parent", "orders")
    capture(page, "family-orders-desktop.png")
    page.close()

    page = new_page(browser, mobile=True)
    open_role(page, "parent", "dashboard")
    capture(page, "parent-qr-mobile.png", full_page=True)
    page.locator("[data-open-student-qr]").first.click()
    page.locator("#studentQrDialog").wait_for(state="visible")
    capture(page, "parent-qr-preview-mobile.png")
    page.close()

    page = new_page(browser, mobile=True)
    open_role(page, "parent", "orders")
    capture(page, "family-orders-mobile.png", full_page=True)
    page.locator("[data-open-order]:visible").first.click()
    page.locator("#orderDialog").wait_for(state="visible")
    capture(page, "family-order-dialog-mobile.png")
    page.close()


def capture_teacher_profile(browser: Browser) -> None:
    page = new_page(browser)
    open_role(page, "teacher", "dashboard")
    page.evaluate(
        """
        state.teacherProfile = {
          firstName: "",
          lastName: "",
          completed: false,
          matchedGroupNames: [],
          matchedStudentCount: 0,
        };
        apiContext.demoMode = false;
        syncTeacherProfileControl();
        apiContext.demoMode = true;
        """
    )
    page.locator("#teacherProfileDialog").wait_for(state="visible")
    capture(page, "teacher-profile-first-login-desktop.png")
    page.close()

    page = new_page(browser)
    open_role(page, "teacher", "dashboard")
    page.evaluate(
        """
        state.teacherProfile = {
          firstName: "Ольга",
          lastName: "Пушкарева",
          completed: true,
          matchedGroupNames: ["Робототехника, суббота", "Python, воскресенье"],
          matchedStudentCount: 18,
        };
        apiContext.demoMode = false;
        openTeacherProfileDialog({ required: false });
        apiContext.demoMode = true;
        """
    )
    page.locator("#teacherProfileDialog").wait_for(state="visible")
    capture(page, "teacher-profile-groups-desktop.png")
    page.close()


def capture_teacher_orders(browser: Browser) -> None:
    page = new_page(browser, mobile=True)
    open_role(page, "teacher", "dashboard")
    load_button = page.locator("[data-load-teacher-qr]")
    if load_button.count() and load_button.is_visible():
        load_button.click()
        page.wait_for_timeout(180)
    capture(page, "teacher-qr-mobile.png", full_page=True)
    page.close()

    page = new_page(browser, mobile=True)
    open_role(page, "teacher", "orders")
    capture(page, "teacher-orders-mobile.png", full_page=True)
    page.get_by_role("tab", name="На площадке", exact=False).first.click()
    page.wait_for_timeout(150)
    capture(page, "teacher-orders-venue-mobile.png", full_page=True)
    page.get_by_role("tab", name="У учителя", exact=False).first.click()
    page.wait_for_timeout(150)
    capture(page, "teacher-orders-teacher-mobile.png", full_page=True)
    issue_button = page.locator('[data-order-action="issue"]:visible').first
    if issue_button.count():
        issue_button.click()
        page.wait_for_timeout(200)
        page.get_by_role("tab", name="Получены", exact=False).first.click()
        page.wait_for_timeout(150)
        page.locator("[data-open-order]:visible").first.click()
        page.locator("#orderDialog").wait_for(state="visible")
        capture(page, "teacher-order-issued-history-mobile.png")
    page.close()


def capture_order_workflow(browser: Browser, role: str, prefix: str = "") -> None:
    page = new_page(browser)
    open_role(page, role, "orders")
    capture(page, f"{prefix}orders-tabs-desktop.png")

    page.get_by_role("tab", name="Назначить склад", exact=False).first.click()
    page.wait_for_timeout(150)
    capture(page, f"{prefix}orders-assign-desktop.png")
    page.locator("[data-open-order]:visible").first.click()
    page.locator("#orderDialog").wait_for(state="visible")
    capture(page, f"{prefix}order-warehouse-dialog-desktop.png")
    page.locator("#closeOrderDialogButton").click()

    page.get_by_role("tab", name="Собрать", exact=False).first.click()
    page.wait_for_timeout(150)
    capture(page, f"{prefix}orders-collect-desktop.png")
    page.get_by_role("tab", name="Распределить", exact=False).first.click()
    page.wait_for_timeout(150)
    capture(page, f"{prefix}orders-route-desktop.png")

    page.get_by_role("tab", name="Все", exact=False).first.click()
    page.wait_for_timeout(150)
    menu = page.locator("details.order-more-menu").first
    menu.locator("summary").click()
    menu.get_by_role("button", name="Отменить заказ", exact=True).click()
    page.locator("#orderCancelReason").wait_for(state="visible")
    capture(page, f"{prefix}order-cancel-form-desktop.png")
    page.close()


def capture_order_mobile_dialog(browser: Browser) -> None:
    page = new_page(browser, mobile=True)
    open_role(page, "admin", "orders")
    page.get_by_role("tab", name="Назначить склад", exact=False).first.click()
    page.locator("[data-open-order]:visible").first.click()
    page.locator("#orderDialog").wait_for(state="visible")
    capture(page, "order-warehouse-dialog-mobile.png")
    page.close()


def capture_students_and_ac(browser: Browser) -> None:
    page = new_page(browser)
    open_role(page, "admin", "wallet")
    capture(page, "student-registry-desktop.png")
    page.locator("details[data-student-card]").first.locator("summary").click()
    page.wait_for_timeout(180)
    capture(page, "student-card-desktop.png")
    page.close()

    page = new_page(browser)
    open_role(page, "admin", "wallet")
    page.locator("[data-toggle-student-create]").click()
    page.wait_for_timeout(150)
    capture(page, "student-create-desktop.png")
    page.close()

    for role, filename in (
        ("teacher", "teacher-student-registry-desktop.png"),
        ("curator", "curator-student-registry-desktop.png"),
    ):
        page = new_page(browser)
        open_role(page, role, "wallet")
        capture(page, filename)
        page.close()

    page = new_page(browser, mobile=True)
    open_role(page, "teacher", "accrual")
    capture(page, "accrual-mobile.png", full_page=True)
    page.locator("#groupAccrualReason").select_option("__custom__")
    page.wait_for_timeout(120)
    capture(page, "accrual-custom-mobile.png", full_page=True)
    page.close()

    for role, prefix in (
        ("admin", "admin"),
        ("curator", "curator"),
        ("partner_director", "director"),
    ):
        page = new_page(browser)
        open_role(page, role, "accrual")
        capture(page, f"{prefix}-accrual-desktop.png")
        page.close()

        page = new_page(browser)
        open_role(page, role, "report")
        capture(page, f"{prefix}-ac-report-desktop.png")
        page.close()

    page = new_page(browser)
    open_role(page, "admin", "report")
    capture(page, "ac-report-desktop.png")
    page.close()

    page = new_page(browser)
    open_role(page, "admin", "accrual")
    page.locator("#openAccrualRulesButton").click()
    page.locator("#accrualRulesDialog").wait_for(state="visible")
    capture(page, "birthday-accrual-rule-desktop.png")
    page.close()


def capture_broadcasts(browser: Browser) -> None:
    for role, filename in (
        ("admin", "admin-broadcast-targets-desktop.png"),
        ("curator", "curator-broadcast-targets-desktop.png"),
        ("partner_director", "director-broadcast-targets-desktop.png"),
    ):
        page = new_page(browser)
        open_role(page, role, "broadcasts")
        capture(page, filename)
        if role == "admin":
            capture(page, "broadcast-targets-desktop.png")
        page.close()

    page = new_page(browser, mobile=True)
    open_role(page, "admin", "broadcasts")
    page.locator("#addBroadcastVenueButton").click()
    page.wait_for_timeout(120)
    capture(page, "broadcast-venue-editor-mobile.png", full_page=True)
    page.close()

    page = new_page(browser, mobile=True)
    open_role(page, "curator", "broadcasts")
    page.locator('[data-broadcast-step="2"]').click()
    page.locator("#broadcastTitle").fill("Открытый урок")
    page.locator("#broadcastMessage").fill("В субботу ждем учеников на открытом уроке.")
    capture(page, "broadcast-news-mobile.png", full_page=True)
    page.locator("#broadcastEmojiButton").click()
    capture(page, "broadcast-news-emoji-mobile.png", full_page=True)
    page.locator('[data-broadcast-step="3"]').click()
    page.wait_for_timeout(120)
    capture(page, "broadcast-review-mobile.png", full_page=True)
    page.close()


def capture_management(browser: Browser, role: str, prefix: str = "") -> None:
    page = new_page(browser)
    open_role(page, role, "admin")
    capture(page, f"{prefix}management-summary-desktop.png")
    for tab, filename in (
        ("staff", "staff-list-desktop.png"),
        ("products", "products-desktop.png"),
        ("warehouses", "warehouses-desktop.png"),
        ("crm", "crm-import-desktop.png"),
        ("contacts", "contacts-desktop.png"),
        ("history", "admin-history-desktop.png"),
    ):
        open_admin_tab(page, tab)
        capture(page, f"{prefix}{filename}")
    page.close()


def capture_staff_management(browser: Browser) -> None:
    page = new_page(browser)
    open_role(page, "partner_director", "admin")
    open_admin_tab(page, "staff")
    capture(page, "staff-combined-roles-desktop.png")

    menu = page.locator("details.admin-row-menu").first
    menu.locator("summary").click()
    capture(page, "staff-actions-desktop.png")
    menu.locator("[data-add-staff-role]").click()
    page.wait_for_timeout(120)
    capture(page, "staff-add-role-desktop.png")

    page.locator("[data-cancel-additional-staff-role]").click()
    menu = page.locator("details.admin-row-menu").first
    menu.locator("summary").click()
    menu.locator("[data-edit-staff-profile]").click()
    page.wait_for_timeout(120)
    capture(page, "staff-edit-name-desktop.png")
    page.close()

    page = new_page(browser, mobile=True)
    open_role(page, "admin", "admin")
    open_admin_tab(page, "staff")
    page.locator("#staffInviteButton").click()
    capture(page, "staff-invite-mobile.png", full_page=True)
    page.evaluate(
        """
        state.staffInvitationRole = "teacher";
        state.staffInvitationLink = "https://max.ru/example?start=staff_invite_example";
        state.staffInvitationExpiresAt = "2026-09-12T12:00:00+03:00";
        renderAdminPanel();
        """
    )
    capture(page, "staff-invite-link-mobile.png", full_page=True)
    page.close()


def capture_product_management(browser: Browser) -> None:
    page = new_page(browser)
    open_role(page, "admin", "admin")
    open_admin_tab(page, "products")
    capture(page, "product-warehouse-filter-desktop.png")

    warehouse_select = page.locator("#productWarehouseFilter")
    options = warehouse_select.locator("option")
    if options.count() > 1:
        warehouse_select.select_option(index=1)
        page.wait_for_timeout(100)
        capture(page, "product-filtered-by-warehouse-desktop.png")
        warehouse_select.select_option("all")

    page.get_by_role("button", name="Редактировать", exact=True).first.click()
    page.wait_for_timeout(120)
    capture(page, "product-editor-desktop.png")
    page.locator("#productCancelEditButtonBottom").click()

    page.locator("details.product-import-panel > summary").click()
    capture(page, "product-import-desktop.png")

    page.locator("[data-delete-product]").first.click()
    page.locator("#confirmationDialog").wait_for(state="visible")
    capture(page, "product-delete-confirmation-desktop.png")
    page.close()

    page = new_page(browser)
    open_role(page, "admin", "admin")
    open_admin_tab(page, "products")
    page.get_by_role("button", name="Добавить товар", exact=True).click()
    page.locator("#productFulfillmentType").select_option("digital_code")
    page.wait_for_timeout(100)
    capture(page, "digital-product-editor-desktop.png")
    page.close()


def capture_warehouses(browser: Browser) -> None:
    page = new_page(browser, mobile=True)
    open_role(page, "admin", "admin")
    open_admin_tab(page, "warehouses")
    page.locator("#warehouseCreateButton").click()
    capture(page, "warehouse-editor-mobile.png", full_page=True)
    page.close()

    page = new_page(browser)
    open_role(page, "admin", "admin")
    open_admin_tab(page, "warehouses")
    page.evaluate(
        """
        if (catalogWarehouses.length > 0) catalogWarehouses[0].isOwner = false;
        renderAdminPanel();
        """
    )
    capture(page, "warehouse-connected-desktop.png")
    page.close()


def capture_city_and_combined_profile(browser: Browser) -> None:
    page = new_page(browser)
    open_role(page, "partner_director", "dashboard")
    page.evaluate(
        """
        state.currentTenant = {
          tenant_slug: "bor",
          tenant_name: "Бор / Algo MAX",
          city_name: "Бор",
          partner_name: "Algo MAX",
        };
        state.availableTenants = [
          { tenant_slug: "bor", tenant_name: "Бор / Algo MAX", city_name: "Бор", partner_name: "Algo MAX" },
          { tenant_slug: "nizhny", tenant_name: "Нижний Новгород / Algo MAX", city_name: "Нижний Новгород", partner_name: "Algo MAX" },
          { tenant_slug: "kirov", tenant_name: "Киров / Algo MAX", city_name: "Киров", partner_name: "Algo MAX" },
        ];
        state.canManageTenants = true;
        state.canCreateTenants = false;
        apiContext.tenantSlug = "bor";
        apiContext.demoMode = false;
        renderTenantControl();
        openTenantDialog();
        apiContext.demoMode = true;
        """
    )
    page.locator("#tenantDialog").wait_for(state="visible")
    capture(page, "director-city-switcher-desktop.png")
    page.close()

    page = new_page(browser)
    open_role(page, "admin", "dashboard")
    page.evaluate(
        """
        state.staffRoles = ["admin", "teacher"];
        state.teacherProfile = {
          firstName: "Татьяна",
          lastName: "Китова",
          completed: true,
          matchedGroupNames: ["Python, воскресенье"],
          matchedStudentCount: 8,
        };
        renderAll();
        """
    )
    capture(page, "combined-role-profile-desktop.png")
    page.close()


def capture_help(browser: Browser) -> None:
    page = new_page(browser)
    open_role(page, "student", "help")
    capture(page, "help-desktop.png")
    page.close()

    page = new_page(browser, mobile=True)
    open_role(page, "student", "help")
    capture(page, "help-mobile.png")
    page.close()


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            capture_profiles(browser)
            capture_store_and_cart(browser)
            capture_family(browser)
            capture_teacher_profile(browser)
            capture_teacher_orders(browser)
            capture_order_workflow(browser, "admin")
            capture_order_workflow(browser, "partner_director", "director-")
            capture_order_mobile_dialog(browser)
            capture_students_and_ac(browser)
            capture_broadcasts(browser)
            capture_management(browser, "admin")
            capture_management(browser, "partner_director", "director-")
            capture_staff_management(browser)
            capture_product_management(browser)
            capture_warehouses(browser)
            capture_city_and_combined_profile(browser)
            capture_help(browser)
        finally:
            browser.close()


if __name__ == "__main__":
    main()
