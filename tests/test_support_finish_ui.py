import json

import pytest

from tests.test_binding_ui import binding_browser as _binding_browser

binding_browser = _binding_browser


@pytest.mark.parametrize("width", [320, 390, 1440])
@pytest.mark.parametrize("fail", [False, True])
def test_owner_can_finish_ticket_without_losing_notes_or_reply_draft(binding_browser, width, fail):
    browser, base = binding_browser
    page = browser.new_page(viewport={"width": width, "height": 900})
    errors, patches = [], []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route("https://st.max.ru/**", lambda route: route.abort())
    record = {"id": 7, "role": "parent", "max_user_id": "77", "first_name": "Анна",
              "last_name": "Иванова", "message": "Не открывается приложение",
              "source": "bot", "status": "new", "private_note": "Заметка", "photo_ids": [],
              "created_at": "2026-10-17T10:00:00Z", "replies": []}

    def api(route):
        if route.request.method == "PATCH":
            payload = route.request.post_data_json
            patches.append(payload)
            if fail:
                route.fulfill(status=503, content_type="application/json",
                              body=json.dumps({"detail": "Не удалось сохранить"}))
            else:
                record.update(payload)
                route.fulfill(content_type="application/json",
                              body=json.dumps({"id": record["id"], "status": record["status"]}))
        else:
            route.fulfill(content_type="application/json", body=json.dumps({
                "items": [record], "total": 1, "counts": {record["status"]: 1},
            }))

    page.route("**/api/v1/support/**", api)
    page.goto(base + "/miniapp?demo=1&demo_role=teacher&view=help", wait_until="networkidle")
    page.evaluate("supportState.owner = true; "
                  "document.querySelector('#supportInboxTab').hidden = false")
    page.locator("#supportInboxTab").click()
    page.locator(".support-ticket summary").click()
    page.locator('[name="private_note"]').fill("Важная заметка")
    page.locator('[name="reply_message"]').fill("Ответ ещё не отправлен")
    button = page.get_by_role("button", name="Завершить тикет", exact=True)
    assert button.is_visible()
    button.click()
    page.wait_for_function("!document.querySelector('[data-support-update]').dataset.saving")
    assert patches == [{"status": "resolved", "private_note": "Важная заметка"}]
    assert page.locator('[name="private_note"]').input_value() == "Важная заметка"
    assert page.locator('[name="reply_message"]').input_value() == "Ответ ещё не отправлен"
    if fail:
        assert button.is_enabled()
        assert page.locator('[name="status"]').input_value() == "new"
        assert "Не удалось" in page.locator("[data-update-result]").inner_text()
    else:
        assert not button.count()
        assert page.locator('[name="status"]').input_value() == "resolved"
        assert page.locator(".support-badge").inner_text() == "Решённые"
        # The ordinary save action can reopen it later.
        page.locator('[name="status"]').select_option("in_progress")
        page.get_by_role("button", name="Сохранить", exact=True).click()
        page.get_by_role("button", name="Завершить тикет", exact=True).wait_for()
        assert patches[-1]["status"] == "in_progress"
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.evaluate("supportState.owner = false; supportRenderInbox(supportState.counts)")
    assert not page.locator("[data-support-resolve]").count()
    assert not errors, errors
    page.close()
