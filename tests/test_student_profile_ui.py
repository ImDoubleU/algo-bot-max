"""Student cards must separate read access from administrative mutations."""

import pytest
from test_feedback_workspace_ui import feedback_browser as _browser

feedback_browser = _browser


@pytest.mark.parametrize("width", [390, 1440])
@pytest.mark.parametrize("role", ["teacher", "admin"])
def test_staff_can_open_student_finances(feedback_browser, width, role, tmp_path):
    browser, base = feedback_browser
    context = browser.new_context(viewport={"width": width, "height": 1000})
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route("https://st.max.ru/**", lambda route: route.abort())
    try:
        page.goto(
            f"{base}/miniapp?demo=1&demo_role={role}&view=wallet",
            wait_until="networkidle",
        )
        card = page.locator(".student-registry-card").first
        student_id = card.get_attribute("data-open-student-profile")
        assert student_id
        assert card.is_enabled()
        card.click()
        assert page.locator(".student-profile-page").is_visible()
        if role == "admin":
            assert page.locator("[data-student-profile-form]").count() == 1
            assert page.locator("[data-student-balance-form]").count() == 1
            page.locator('.student-profile-tabs [data-profile-tab="finance"]').click()
        else:
            assert page.locator(".student-profile-tabs button").all_text_contents() == [
                "Обзор", "Астрокоины",
            ]
            assert page.locator("[data-student-profile-form]").count() == 0
            assert page.locator("[data-student-balance-form]").count() == 0
            assert page.locator('[data-profile-tab="data"]').count() == 0
            assert page.locator('[data-profile-panel="history"]').count() == 0
        assert page.locator(".student-ledger-history").is_visible()
        assert page.locator(".student-ledger-entry").count() > 0
        assert page.locator(".student-bank-history").is_visible()
        page.locator('[data-student-ledger-filter="purchase"]').click()
        assert page.locator('[data-student-ledger-filter="purchase"]').get_attribute(
            "aria-pressed"
        ) == "true"
        page.locator('[data-student-ledger-filter="all"]').click()
        page.evaluate("refreshAllData()")
        assert page.locator(".student-ledger-entry").count() > 0
        assert page.evaluate("state.studentProfileId") == student_id
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=str(tmp_path / f"student-finances-{role}-{width}.png"))
        page.locator("[data-close-student-profile]").click()
        assert page.locator(".student-registry-card").first.is_visible()
        assert not errors, errors
    finally:
        context.close()


@pytest.mark.parametrize("role", ["parent", "student"])
def test_family_cannot_open_staff_student_profile(feedback_browser, role):
    browser, base = feedback_browser
    context = browser.new_context()
    page = context.new_page()
    page.route("https://st.max.ru/**", lambda route: route.abort())
    try:
        page.goto(
            f"{base}/miniapp?demo=1&demo_role={role}&view=wallet",
            wait_until="networkidle",
        )
        page.evaluate("openAdminStudentProfile(students[0].id)")
        assert page.evaluate("canViewStudentProfiles()") is False
        assert page.evaluate("state.studentProfileId") == ""
        assert page.locator(".student-profile-page").count() == 0
    finally:
        context.close()
