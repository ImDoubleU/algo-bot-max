import json
from io import BytesIO
from uuid import uuid4

import pytest
from PIL import Image
from test_feedback_workspace_ui import feedback_browser as _feedback_browser

feedback_browser = _feedback_browser


@pytest.mark.parametrize("width", [390, 1280])
def test_report_form_photo_submission_and_layout(feedback_browser, width):
    browser, base = feedback_browser
    page = browser.new_page(viewport={"width": width, "height": 850})
    page.route("https://st.max.ru/**", lambda route: route.abort())
    calls = []
    photo_id = str(uuid4())

    def api(route):
        if route.request.url.endswith("/photos"):
            route.fulfill(status=201, content_type="application/json",
                          body=json.dumps({"id": photo_id}))
        else:
            calls.append(route.request.post_data_json)
            route.fulfill(status=201, content_type="application/json", body='{"id":12}')

    page.route("**/api/v1/support/**", api)
    page.goto(base + "/miniapp?demo=1&demo_role=teacher&view=help")
    page.locator("#helpView [data-support-open]").click()
    assert not page.locator("#supportFormFields").is_visible()
    page.locator('[data-support-role="parent"]').click()
    page.locator('#supportForm [name="first_name"]').fill("Анна")
    page.locator('#supportForm [name="last_name"]').fill("Иванова")
    page.locator('#supportForm [name="message"]').fill("Пропала привязка")
    output = BytesIO()
    Image.new("RGB", (20, 20), "blue").save(output, "PNG")
    page.locator("#supportFileInput").set_input_files({
        "name": "screen.png", "mimeType": "image/png", "buffer": output.getvalue(),
    })
    assert page.locator("#supportPhotos img").count() == 1
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.locator('#supportForm button[type="submit"]').click()
    page.wait_for_function("document.querySelector('#supportFormStatus').textContent.includes('№12')")
    assert calls[0]["photo_ids"] == [photo_id]
    assert "max_user_id" not in calls[0]
    assert calls[0]["role"] == "parent"
    assert not page.locator("#supportFormFields").is_visible()
    page.close()


def test_report_text_survives_reopening_and_reload(feedback_browser):
    browser, base = feedback_browser
    page = browser.new_page()
    page.route("https://st.max.ru/**", lambda route: route.abort())
    url = base + "/miniapp?demo=1&demo_role=teacher&view=help"
    page.goto(url)
    page.locator("#helpView [data-support-open]").click()
    page.locator('[data-support-role="student"]').click()
    page.locator('#supportForm [name="first_name"]').fill("Дмитрий")
    page.locator('#supportForm [name="message"]').fill("Не открывается заказ")
    page.locator("[data-support-close]").click()
    page.reload()
    page.locator("#helpView [data-support-open]").click()
    assert page.locator('#supportForm [name="first_name"]').input_value() == "Дмитрий"
    assert page.locator('#supportForm [name="message"]').input_value() == "Не открывается заказ"
    assert page.locator("#supportRole").input_value() == "student"
    page.close()


def test_inbox_escapes_user_text_and_preserves_unsaved_note(feedback_browser):
    browser, base = feedback_browser
    page = browser.new_page(viewport={"width": 390, "height": 850})
    page.route("https://st.max.ru/**", lambda route: route.abort())
    ticket = {"id": 1, "role": "staff", "max_user_id": "77", "first_name": "Иван",
              "last_name": "Петров", "message": '<img src=x onerror="window.hacked=1">',
              "source": "bot", "status": "new", "private_note": "", "photo_ids": [],
              "tenant_slug": "test", "created_at": "2026-10-07T10:00:00Z"}
    page.route("**/api/v1/support/tickets?**", lambda route: route.fulfill(
        status=200, content_type="application/json",
        body=json.dumps({"items": [ticket], "total": 1, "counts": {"new": 1}})))
    page.goto(base + "/miniapp?demo=1&demo_role=teacher&view=help")
    assert not page.locator("#supportInboxTab").is_visible()
    page.evaluate("supportState.owner = true; "
                  "document.querySelector('#supportInboxTab').hidden = false")
    page.locator("#supportInboxTab").click()
    page.locator(".support-ticket summary").click()
    assert page.locator(".support-ticket-message").inner_text() == ticket["message"]
    assert page.evaluate("window.hacked === undefined")
    assert page.locator(".support-ticket-message img").count() == 0
    page.locator('[name="private_note"]').fill("Не потерять заметку")
    page.locator("#supportRefresh").click()
    page.wait_for_function("document.querySelector('#supportInboxStatus').textContent === ''")
    assert page.locator('[name="private_note"]').input_value() == "Не потерять заметку"
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.close()


def test_reply_button_queues_personal_answer_and_shows_delivery_state(feedback_browser):
    browser, base = feedback_browser
    page = browser.new_page(viewport={"width": 390, "height": 850})
    page.route("https://st.max.ru/**", lambda route: route.abort())
    record = {"id": 7, "role": "parent", "max_user_id": "77", "first_name": "Анна",
              "last_name": "Иванова", "message": "Не открывается приложение",
              "source": "bot", "status": "new", "private_note": "", "photo_ids": [],
              "tenant_slug": "test", "created_at": "2026-10-07T10:00:00Z", "replies": []}
    sent = []

    def api(route):
        if route.request.method == "POST":
            body = route.request.post_data_json
            sent.append(body)
            record["status"] = "in_progress"
            record["replies"] = [{"message": body["message"], "status": "queued"}]
            payload = {"status": "queued"}
        else:
            payload = {"items": [record], "total": 1, "counts": {record["status"]: 1}}
        route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))

    page.route("**/api/v1/support/**", api)
    page.goto(base + "/miniapp?demo=1&demo_role=teacher&view=help")
    page.evaluate("supportState.owner = true; "
                  "document.querySelector('#supportInboxTab').hidden = false")
    page.locator("#supportInboxTab").click()
    page.locator(".support-ticket summary").click()
    page.locator('[name="reply_message"]').fill("Попробуйте открыть приложение снова")
    page.locator('[data-support-reply] button').click()
    page.wait_for_function("document.querySelector('.support-reply') !== null")
    assert sent[0]["message"] == "Попробуйте открыть приложение снова"
    assert set(sent[0]) == {"message", "request_id"}
    assert page.locator('[data-support-reply] button').is_disabled()
    assert "Ожидает отправки" in page.locator(".support-reply").inner_text()
    record["status"] = "resolved"
    record["replies"][0]["status"] = "sent"
    page.locator("#supportRefresh").click()
    page.wait_for_function("document.querySelector('.support-reply').textContent.includes('Отправлен')")
    assert page.locator('[data-support-reply] button').is_enabled()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.close()
