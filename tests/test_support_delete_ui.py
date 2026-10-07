# ruff: noqa: F811
import json

import pytest

from tests.test_binding_ui import binding_browser  # noqa: F401


@pytest.mark.parametrize("width", [320, 390, 1440])
@pytest.mark.parametrize("fail", [False, True])
def test_delete_ticket_requires_confirmation_and_preserves_data_on_error(
    binding_browser, width, fail,
):
    browser, base = binding_browser
    page = browser.new_page(viewport={"width": width, "height": 850})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route("https://st.max.ru/**", lambda route: route.abort())
    record = {"id": 7, "role": "parent", "max_user_id": "77", "first_name": "Анна",
              "last_name": "Иванова", "message": "Не открывается приложение",
              "source": "bot", "status": "new", "private_note": "", "photo_ids": [],
              "created_at": "2026-10-07T10:00:00Z", "replies": []}
    items = [record]
    calls = []

    def api(route):
        if route.request.method == "DELETE":
            calls.append(route.request.url)
            if fail:
                route.fulfill(status=503, content_type="application/json", body='{}')
            else:
                items.clear()
                route.fulfill(status=204)
        else:
            route.fulfill(status=200, content_type="application/json", body=json.dumps({
                "items": items, "total": len(items), "counts": {"new": len(items)},
            }))

    page.route("**/api/v1/support/**", api)
    page.goto(base + "/miniapp?demo=1&demo_role=teacher&view=help", wait_until="networkidle")
    page.evaluate("supportState.owner = true; "
                  "document.querySelector('#supportInboxTab').hidden = false")
    page.locator("#supportInboxTab").click()
    page.locator(".support-ticket summary").click()
    page.locator('[name="private_note"]').fill("Не потерять заметку")
    page.locator('[name="reply_message"]').fill("Черновик ответа")
    page.evaluate("auditFeed('audit').rows = [{id:'cached-ticket-history'}]; "
                  "supportState.replyKeys.set(7, 'reply-key'); "
                  "const cachedPhoto = URL.createObjectURL(new Blob(['photo'])); "
                  "supportState.imageUrls.set('photo-cache', cachedPhoto); "
                  "supportState.items[0].photo_ids = ['photo-cache']")
    page.locator("[data-support-delete]").click()
    assert page.locator("#confirmationDialog").is_visible()
    assert "№7" in page.locator("#confirmationDialogTitle").inner_text()
    assert "Восстановить" in page.locator("#confirmationDialogMessage").inner_text()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert calls == []
    page.locator("#cancelConfirmationButton").click()
    assert page.locator(".support-ticket").count() == 1
    assert page.locator('[name="private_note"]').input_value() == "Не потерять заметку"
    assert page.locator('[name="reply_message"]').input_value() == "Черновик ответа"
    assert calls == []
    page.locator("[data-support-delete]").click()
    page.locator("#confirmConfirmationButton").click()
    page.wait_for_function("supportState.deleting.size === 0")
    assert len(calls) == 1 and calls[0].endswith("/tickets/7")
    if fail:
        assert page.locator(".support-ticket").count() == 1
        assert page.locator('[name="private_note"]').input_value() == "Не потерять заметку"
        assert page.locator('[name="reply_message"]').input_value() == "Черновик ответа"
        assert page.locator("[data-support-delete]").is_enabled()
        assert page.locator("#supportInboxStatus").inner_text()
        assert page.evaluate("supportState.unsaved.has(7) && supportState.replyKeys.has(7)")
    else:
        assert page.locator(".support-ticket").count() == 0
        assert page.locator("#supportNewCount").is_hidden()
        assert page.evaluate("supportState.total === 0 && !supportState.unsaved.has(7) "
                             "&& !supportState.replyDrafts.has(7) "
                             "&& !supportState.replyKeys.has(7) "
                             "&& !supportState.openTickets.has(7) && !supportState.imageUrls.size "
                             "&& !auditFeeds.size")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert not errors, errors
    page.close()


def test_deletion_of_only_item_on_last_page_goes_to_previous_page(binding_browser):
    browser, base = binding_browser
    page = browser.new_page()
    page.route("https://st.max.ru/**", lambda route: route.abort())
    offsets = []

    def api(route):
        offsets.append(route.request.url)
        route.fulfill(status=200, content_type="application/json",
                      body='{"items":[],"total":30,"counts":{"new":30}}')

    page.route("**/api/v1/support/tickets?**", api)
    page.route("**/api/v1/support/tickets/7", lambda route: route.fulfill(status=204))
    page.goto(base + "/miniapp?demo=1&demo_role=teacher&view=help", wait_until="networkidle")
    page.evaluate("""() => {
      supportState.owner = true; supportState.offset = 30; supportState.total = 31;
      supportState.items = [{id:7, status:'new', photo_ids:[]}];
      window.deletion = supportDeleteTicket(7);
    }""")
    page.locator("#confirmConfirmationButton").click()
    page.evaluate("window.deletion")
    assert page.evaluate("supportState.offset") == 0
    assert len(offsets) == 1 and "offset=0" in offsets[0]
    page.close()
