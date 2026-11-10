import pytest
from test_feedback_workspace_ui import feedback_browser as _browser

feedback_browser = _browser


@pytest.mark.parametrize("width", [320, 390, 1440])
def test_export_entire_catalog_download_and_button_state(feedback_browser, width):
    browser, base = feedback_browser
    context = browser.new_context(viewport={"width": width, "height": 900}, accept_downloads=True)
    page = context.new_page()
    errors, requests = [], []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route("https://st.max.ru/**", lambda route: route.abort())

    def export(route):
        requests.append(route.request.url)
        route.fulfill(body=b"PK-local-xlsx", content_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ))

    page.route("**/api/v1/miniapp/products/export?*", export)
    page.goto(base + "/miniapp?demo=1&demo_role=partner_director&view=admin",
              wait_until="networkidle")
    page.evaluate("state.adminTab='products'; renderAdminPanel()")
    button = page.locator("[data-export-products]")
    assert button.is_visible()
    assert not page.locator(".product-import-panel").get_attribute("open")
    with page.expect_download() as download:
        button.click()
    assert download.value.suggested_filename.startswith("algo-max-products-")
    assert download.value.suggested_filename.endswith(".xlsx")
    assert len(requests) == 1
    assert "include_inactive=false" not in requests[0]
    assert "max_user_id=" in requests[0]
    page.wait_for_function("state.productExporting===false")
    assert button.is_enabled()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert not errors
    context.close()
