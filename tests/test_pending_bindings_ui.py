import pytest
from test_feedback_workspace_ui import feedback_browser as _browser

feedback_browser = _browser


@pytest.mark.parametrize("width", [320, 390, 1440])
def test_connections_do_not_render_or_load_pending_inbox(feedback_browser, width):
    browser, base = feedback_browser
    context = browser.new_context(viewport={"width": width, "height": 900})
    page = context.new_page()
    errors, requests = [], []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("request", lambda request: requests.append(request.url))
    page.route("https://st.max.ru/**", lambda route: route.abort())
    page.goto(base + "/miniapp?demo=1&demo_role=admin&view=admin", wait_until="networkidle")
    page.evaluate("state.staffRoles = ['superadmin']; renderAll();")
    page.locator('[data-admin-tab="contacts"]').click()
    page.evaluate("setView('home'); setView('admin'); renderAdminPanel();")
    assert page.locator("[data-access-child]").count() == 2
    assert page.locator(".pending-bindings-panel, #pendingBindingsTitle").count() == 0
    assert "Ожидают подключения" not in page.locator("#adminPanel").inner_text()
    assert not any("/api/v1/access/pending" in url for url in requests)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert not errors, errors
    context.close()
