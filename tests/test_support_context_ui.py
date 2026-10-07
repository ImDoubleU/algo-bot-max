# ruff: noqa: F811
import json
from pathlib import Path

import pytest

from tests.test_binding_ui import binding_browser  # noqa: F401


def user_record():
    school = {"slug": "test-city", "city": "Нижний Новгород", "partner": "Algo MAX"}
    return {
        "id": 7, "role": "parent", "max_user_id": "53364725", "first_name": "Анна",
        "last_name": "Иванова", "message": "Не открывается приложение",
        "source": "bot", "status": "new", "private_note": "", "photo_ids": [],
        "created_at": "2026-10-07T10:00:00Z", "replies": [], "user_context": {
            "account": {"id": "account-uuid", "name": "Анна Иванова",
                        "username": "parent", "phone": "+79990000000",
                        "created_at": "2026-10-01T10:00:00Z"},
            "origin_school": school, "staff": [], "students": [{
                "id": "student-uuid", "name": "Иванова Александра",
                "lms_id": "ST-001", "crm_id": "deal-001", "school": school,
                "group": "ОЛИП Союзный 45, сб 10:00", "course": "Основы логики",
                "venue": "Союзный 45", "teacher": "Олейник Дмитрий",
                "teacher_max_id": "424242", "status": "active", "balance": 150,
                "parent_connected": True,
                "accounts": [
                    {"max_id": "53364725", "name": "Анна Иванова", "role": "parent"},
                    {"max_id": "123", "name": "Папа Иванов", "role": "parent"},
                    {"max_id": "111", "name": "Ученик MAX", "role": "student"},
                ],
                "links": [{"id": "link-uuid", "role": "parent", "status": "active",
                           "source": "id_entry", "connected_at": "2026-10-03T12:30:00Z"}],
                "contacts": [{"id": "contact-001", "name": "Мама Александры"}],
            }],
        },
    }


@pytest.mark.parametrize("width", [320, 390, 1440])
def test_ticket_user_details_and_navigation_are_clear_and_fit_screen(binding_browser, width):
    browser, base = binding_browser
    page = browser.new_page(viewport={"width": width, "height": 900})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route("https://st.max.ru/**", lambda route: route.abort())
    page.route("**/api/v1/support/tickets?**", lambda route: route.fulfill(
        content_type="application/json", body=json.dumps({
            "items": [user_record()], "total": 1, "counts": {"new": 1},
        }),
    ))
    page.goto(base + "/miniapp?demo=1&demo_role=admin&view=help", wait_until="networkidle")
    page.evaluate("supportState.owner = true; "
                  "document.querySelector('#supportInboxTab').hidden = false")
    page.locator("#supportInboxTab").click()
    page.locator(".support-ticket > summary").click()
    panel = page.locator(".support-user-panel")
    assert "53364725" in panel.inner_text()
    assert panel.locator(".support-user-facts").first.locator(
        "div", has=page.locator("dt", has_text="Роли в системе"),
    ).locator("dd").inner_text() == "Родитель"
    assert panel.locator(".support-user-parents").inner_text().count("Папа Иванов") == 1
    assert "Анна Иванова" not in panel.locator(".support-user-parents").inner_text()
    assert "ST-001" in panel.inner_text() and "111" in panel.inner_text()
    assert "ОЛИП Союзный" in panel.inner_text() and "Олейник Дмитрий" in panel.inner_text()
    assert "150 AC" in panel.inner_text()
    page.get_by_text("Данные аккаунта", exact=True).click()
    page.get_by_text("Связи и другие ID", exact=True).click()
    assert "account-uuid" in panel.inner_text() and "deal-001" in panel.inner_text()
    assert "Ссылка из письма" in panel.inner_text() and "15:30:00" in panel.inner_text()
    assert "contact-001" in panel.inner_text()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    screenshot = Path(".deploy_tmp")
    screenshot.mkdir(exist_ok=True)
    page.screenshot(path=str(screenshot / f"ticket-context-{width}.png"), full_page=True)
    page.evaluate("openAdminStudentProfile = async id => { window.openedStudent = id }; "
                  "switchTenant = async slug => { window.openedTenant = slug }")
    page.locator("[data-audit-student]").click()
    page.wait_for_function("window.openedStudent === 'student-uuid'")
    assert page.evaluate("window.openedTenant") == "test-city"
    page.evaluate("setView('help'); supportSetTab('inbox')")
    page.locator("[data-support-user-history]").click()
    assert page.evaluate("state.adminTab") == "audit"
    assert page.evaluate("auditFeed('audit').filters.actor") == "53364725"
    assert page.evaluate("auditFeed('audit').filters.allTenants")
    assert not errors, errors
    page.close()


def test_unknown_user_and_untrusted_identity_fields_do_not_create_profiles(binding_browser):
    browser, base = binding_browser
    page = browser.new_page(viewport={"width": 320, "height": 900})
    page.route("https://st.max.ru/**", lambda route: route.abort())
    page.goto(base + "/miniapp?demo=1&demo_role=teacher&view=help", wait_until="networkidle")
    record = user_record()
    record["user_context"] = {"account": None, "students": [], "staff": []}
    record["first_name"] = '<img src=x onerror="window.xss=true">'
    page.evaluate("record => { supportState.owner = true; supportState.items = [record]; "
                  "supportSetTab('inbox'); supportRenderInbox({new:1}); }", record)
    page.locator(".support-ticket > summary").click()
    assert page.locator(".support-user-unlinked").inner_text() == "Нет привязок в системе"
    assert not page.locator("[data-audit-student]").count()
    assert not page.locator("[data-support-user-history]").count()
    assert not page.locator(".support-ticket-title img").count()
    assert not page.evaluate("Boolean(window.xss)")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.close()
