from __future__ import annotations

import re
from pathlib import Path

from playwright.sync_api import Browser, Page, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "user-guide-assets" / "visual-v6"
BASE_URL = "http://127.0.0.1:8087/miniapp"


def open_role(page: Page, role: str, view: str) -> None:
    page.goto(f"{BASE_URL}?demo=1&demo_role={role}&view={view}", wait_until="networkidle")
    page.locator("main.workspace").wait_for(state="visible")
    page.wait_for_timeout(550)


def capture(page: Page, filename: str, *, full_page: bool = False) -> None:
    target = OUTPUT / filename
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


def new_page(browser: Browser, *, mobile: bool) -> Page:
    viewport = {"width": 390, "height": 844} if mobile else {"width": 1440, "height": 900}
    return browser.new_page(viewport=viewport, device_scale_factor=1)


def capture_family(browser: Browser) -> None:
    page = new_page(browser, mobile=True)
    open_role(page, "parent", "dashboard")
    capture(page, "parent-dashboard-mobile.png", full_page=True)
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


def capture_teacher(browser: Browser) -> None:
    page = new_page(browser, mobile=True)
    open_role(page, "teacher", "dashboard")
    load_button = page.locator("[data-load-teacher-qr]")
    if load_button.count() and load_button.is_visible():
        load_button.click()
        page.wait_for_timeout(300)
    capture(page, "teacher-dashboard-mobile.png", full_page=True)
    capture(page, "teacher-qr-mobile.png", full_page=True)
    page.close()

    page = new_page(browser, mobile=True)
    open_role(page, "teacher", "orders")
    capture(page, "teacher-orders-mobile.png", full_page=True)
    venue_tab = page.get_by_role("tab", name=re.compile(r"^На площадке"))
    if venue_tab.count():
        venue_tab.first.click()
        page.wait_for_timeout(250)
    capture(page, "teacher-orders-venue-mobile.png", full_page=True)

    teacher_tab = page.get_by_role("tab", name=re.compile(r"^У учителя"))
    teacher_tab.first.click()
    page.wait_for_timeout(250)
    capture(page, "teacher-orders-teacher-mobile.png", full_page=True)
    issue_button = page.locator('[data-order-action="issue"]:visible').first
    issue_button.click()
    page.wait_for_timeout(300)
    received_tab = page.get_by_role("tab", name=re.compile(r"^Получены"))
    received_tab.first.click()
    page.wait_for_timeout(250)
    page.locator("[data-open-order]:visible").first.click()
    page.locator("#orderDialog").wait_for(state="visible")
    capture(page, "teacher-order-issued-history-mobile.png")
    page.close()


def click_order_tab(page: Page, title: str) -> None:
    page.get_by_role("tab", name=re.compile(rf"^{re.escape(title)}")).first.click()
    page.wait_for_timeout(250)


def close_order_dialog(page: Page) -> None:
    button = page.locator("#closeOrderDialogButton")
    if button.count() and button.is_visible():
        button.click()
        page.wait_for_timeout(150)


def capture_order_workflow(browser: Browser, role: str, prefix: str) -> None:
    page = new_page(browser, mobile=False)
    open_role(page, role, "orders")
    tabs_filename = f"{prefix}orders-tabs-desktop.png" if prefix else "admin-orders-tabs-desktop.png"
    capture(page, tabs_filename)

    click_order_tab(page, "Назначить склад")
    capture(page, f"{prefix}orders-assign-desktop.png")
    page.locator("[data-open-order]:visible").first.click()
    page.locator("#orderDialog").wait_for(state="visible")
    capture(page, f"{prefix}order-warehouse-dialog-desktop.png")
    close_order_dialog(page)

    click_order_tab(page, "Собрать")
    capture(page, f"{prefix}orders-collect-desktop.png")
    click_order_tab(page, "Распределить")
    capture(page, f"{prefix}orders-route-desktop.png")

    click_order_tab(page, "Все")
    menu = page.locator("details.order-more-menu").first
    menu.locator("summary").click()
    menu.get_by_role("button", name="Отменить заказ", exact=True).click()
    page.locator("#orderCancelReason").wait_for(state="visible")
    capture(page, f"{prefix}order-cancel-form-desktop.png")
    page.close()


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            capture_family(browser)
            capture_teacher(browser)
            capture_order_workflow(browser, "admin", "")
            capture_order_workflow(browser, "partner_director", "director-")
        finally:
            browser.close()


if __name__ == "__main__":
    main()
