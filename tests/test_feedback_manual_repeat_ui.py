import pytest
from test_feedback_workspace_ui import feedback_browser as _feedback_browser
from test_feedback_workspace_ui import feedback_page as _feedback_page

feedback_browser = _feedback_browser
feedback_page = _feedback_page


@pytest.mark.parametrize("width", [390, 1280])
def test_manual_material_is_not_treated_as_a_repeat(feedback_page, width):
    page = feedback_page
    page.set_viewport_size({"width": width, "height": 900})
    page.locator('[data-feedback-tab="manual"]').click()
    for lesson in ("3", "4"):
        page.locator("#feedbackLesson").select_option(lesson)
        page.locator('#feedbackComposeForm [type="submit"]').click()
        assert page.evaluate("feedbackState.repeat") is False
        assert page.locator(".feedback-repeat-note").count() == 0
        assert "повторяли тему предыдущего занятия" not in (
            page.locator("#feedbackText").input_value())
        assert page.evaluate(
            "document.querySelector('#feedbackText').value.includes("
            "feedbackState.catalog[feedbackState.course][feedbackState.lesson-1].educational_results)"
        )
    page.reload(wait_until="networkidle")
    assert page.evaluate("feedbackState.tab") == "manual"
    assert page.evaluate("feedbackState.repeat") is False
    assert page.evaluate("feedbackState.generated.repeat") is False


@pytest.mark.parametrize("edited", [False, True])
def test_old_manual_repeat_snapshot_recovers_without_losing_user_edits(feedback_page, edited):
    page = feedback_page
    page.locator('[data-feedback-tab="manual"]').click()
    page.locator('#feedbackComposeForm [type="submit"]').click()
    page.evaluate("""(edited) => {
      feedbackState.repeat = true;
      feedbackState.generated.repeat = true;
      feedbackState.text = edited ? 'Мой вручную исправленный текст'
        : 'Сегодня мы с ребятами повторяли тему предыдущего занятия';
      feedbackState.edited = edited;
      feedbackPersist();
    }""", edited)
    page.reload(wait_until="networkidle")
    assert page.evaluate("feedbackState.repeat") is False
    assert page.locator(".feedback-repeat-note").count() == 0
    if edited:
        assert page.locator("#feedbackText").input_value() == "Мой вручную исправленный текст"
        assert page.locator(".feedback-stale-note").is_visible()
        assert page.locator("[data-feedback-copy]").is_disabled()
    else:
        assert page.evaluate("feedbackState.generated.repeat") is False
        assert "повторяли тему предыдущего занятия" not in (
            page.locator("#feedbackText").input_value())
