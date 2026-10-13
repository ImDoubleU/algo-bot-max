import json
from pathlib import Path
from uuid import uuid4

import pytest
from test_feedback_workspace_ui import feedback_browser as _feedback_browser

feedback_browser = _feedback_browser


@pytest.mark.parametrize("width", [390, 1280])
def test_conversation_authors_photos_read_state_and_layout(feedback_browser, width):
    browser, base = feedback_browser
    page = browser.new_page(viewport={"width": width, "height": 900})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route("https://st.max.ru/**", lambda route: route.abort())
    incoming_id, photo_id = str(uuid4()), str(uuid4())
    record = {"id": 8, "role": "parent", "max_user_id": "77", "first_name": "Анна",
              "last_name": "Иванова", "message": "Не могу войти по ссылке из письма",
              "source": "bot", "status": "new", "private_note": "Проверить контакт в CRM",
              "photo_ids": [photo_id], "tenant_slug": "test", "unread_count": 1,
              "created_at": "2026-10-12T10:00:00Z", "replies": [
                  {"id": str(uuid4()), "message": "Проверьте, выбран ли нужный город.",
                   "author": "staff", "status": "sent", "photo_ids": [],
                   "created_at": "2026-10-12T10:05:00Z", "sent_at": "2026-10-12T10:05:01Z"},
                  {"id": incoming_id,
                   "message": 'Город верный. <img src=x onerror="window.hacked=1">',
                   "author": "user", "status": "received", "photo_ids": [photo_id],
                   "read_at": None, "created_at": "2026-10-12T10:06:00Z"},
              ]}
    reads = []

    def api(route):
        if route.request.url.endswith("/read"):
            reads.append(route.request.post_data_json)
            route.fulfill(status=204)
        elif "/photos/" in route.request.url:
            from test_support import image
            route.fulfill(status=200, content_type="image/png", body=image())
        else:
            route.fulfill(status=200, content_type="application/json", body=json.dumps({
                "items": [record], "total": 1, "counts": {"new": 1}, "unread_total": 1}))

    page.route("**/api/v1/support/**", api)
    page.goto(base + "/miniapp?demo=1&demo_role=teacher&view=help")
    page.evaluate("supportState.owner = true; "
                  "document.querySelector('#supportInboxTab').hidden = false")
    page.locator("#supportInboxTab").click()
    page.locator(".support-unread").wait_for()
    assert not reads
    page.locator(".support-ticket > summary").click()
    page.locator(".support-reply-history img").wait_for()
    page.wait_for_function("!document.querySelector('.support-unread')")
    assert reads == [{"reply_ids": [incoming_id]}]
    assert page.locator(".support-reply-user").count() == 2
    assert page.locator(".support-reply-staff").count() == 1
    assert "Поддержка" in page.locator(".support-reply-staff").inner_text()
    assert "13:06" in page.locator(".support-reply-user").last.inner_text()
    assert page.locator(".support-reply-history img").count() == 1
    assert page.locator('[data-support-reply] button').is_enabled()
    assert page.evaluate("window.hacked === undefined")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert page.locator('[name="private_note"]').input_value() == "Проверить контакт в CRM"
    page.locator(".support-reply-history").scroll_into_view_if_needed()
    output = Path(__file__).parents[1] / "output" / "support-conversation"
    output.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(output / f"conversation-{width}.png"), full_page=True)
    assert not errors
    page.close()
