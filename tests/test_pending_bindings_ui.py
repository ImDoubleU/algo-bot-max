# ruff: noqa: F811
import json
from pathlib import Path

import pytest

from tests.test_binding_ui import binding_browser  # noqa: F401


@pytest.mark.parametrize("width", [320, 390, 1440])
def test_pending_inbox_is_compact_private_and_cancel_requires_confirmation(binding_browser, width):
    browser, base = binding_browser
    page = browser.new_page(viewport={"width": width, "height": 900})
    errors, mutations = [], []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route("https://st.max.ru/**", lambda route: route.abort())
    record = {"id": "waiting-id", "max_user_id": "7777777", "name": "Фролова Екатерина",
              "name_source": "ticket", "kind": "contact", "target_id": "681", "role": "parent",
              "status": "ready", "reason": "ready", "attempts": 3,
              "last_attempt_at": "2026-10-07T10:00:00Z", "expires_at": "2026-11-06T10:00:00Z",
              "notified_at": "2026-10-07T10:30:00Z", "tenant_slug": "school",
              "students": [{"id": "pupil-id", "name": "Кузнецов Александр",
                            "group": "ОЛИП Союзный 45, сб 10:00", "lms_id": "ST-001"}]}
    items = [record]

    def api(route):
        if route.request.method == "POST":
            mutations.append(route.request.url)
            items.clear()
            route.fulfill(status=204)
        else:
            route.fulfill(content_type="application/json", body=json.dumps({
                "items": items, "total": len(items),
            }))

    page.route("**/api/v1/access/pending**", api)
    page.goto(base + "/miniapp?demo=1&demo_role=admin&view=admin", wait_until="networkidle")
    page.evaluate("""() => {
      apiContext.demoMode = false; apiContext.tenantSlug = 'school'; apiContext.maxUserId = 4242;
      state.staffRoles = ['superadmin']; state.hasAccess = true; state.adminTab = 'contacts';
      renderAdminPanel();
    }""")
    page.evaluate("loadPendingBindings(true)")
    panel = page.locator(".pending-bindings-panel")
    assert "Фролова Екатерина" in panel.inner_text()
    assert "Имя из заявки" in panel.inner_text() and "MAX ID 7777777" in panel.inner_text()
    assert "Ждёт подтверждения" in panel.inner_text() and "LMS ID ST-001" in panel.inner_text()
    assert "13:30" in panel.inner_text()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    Path(".deploy_tmp").mkdir(exist_ok=True)
    panel.screenshot(path=f".deploy_tmp/pending-bindings-{width}.png")
    page.locator("[data-pending-cancel]").click()
    assert page.locator("#confirmationDialog").is_visible() and mutations == []
    page.locator("#cancelConfirmationButton").click()
    assert page.locator(".pending-binding-row").count() == 1
    page.locator("[data-pending-cancel]").click()
    page.locator("#confirmConfirmationButton").click()
    page.wait_for_function("pendingBindingsState.items.length === 0")
    assert len(mutations) == 1 and mutations[0].endswith("/waiting-id/cancel")
    page.evaluate("state.staffRoles = ['admin']; renderAdminPanel()")
    assert page.locator(".pending-bindings-panel").count() == 0
    assert not errors, errors
    page.close()
