import pytest

from tests.test_feedback_workspace_ui import feedback_browser as _feedback_browser
from tests.test_feedback_workspace_ui import feedback_page as _feedback_page

feedback_browser = _feedback_browser
feedback_page = _feedback_page


@pytest.mark.parametrize("width", [390, 1440])
def test_added_lesson_33_generates_template_and_attendance_without_course_text(
    feedback_page, width,
):
    page = feedback_page
    page.set_viewport_size({"width": width, "height": 900})
    page.evaluate("""async () => {
      const group=feedbackState.group, course=feedbackState.course;
      feedbackState.schedules[group]={course,mode:'group',
        rows:feedbackSeries(course,'2026-01-03',1,1,32,7,feedbackState.catalog)};
      feedbackState.messages=Object.create(null);feedbackSelectGroup(group);await renderFeedback();
    }""")
    page.locator(".feedback-schedule-settings > summary").click()
    page.locator("[data-feedback-add-custom]").click()
    assert page.locator('[data-feedback-schedule-row] [name="topic"]').input_value() == ""
    page.locator('#feedbackScheduleForm [type="submit"]').click()
    row = page.evaluate("feedbackSchedule(feedbackState.group).rows.at(-1)")
    assert row["number"] == 33 and row["lesson"] is None
    if width < 640:
        page.locator("#feedbackActiveLesson").select_option(row["id"])
        page.wait_for_function("feedbackState.generated?.offset === 33")
    else:
        page.locator(f'.feedback-weeks [data-feedback-row="{row["id"]}"]').click()
    assert page.locator(".feedback-student-chips label").count()
    page.locator(".feedback-student-chips label").first.click()
    result = page.evaluate("""() => ({text:feedbackState.text,absent:feedbackState.absent[0],
      hasCourseText:feedbackState.catalog[feedbackState.course].some(
        lesson=>feedbackState.text.includes(lesson.educational_results)),
      date:feedbackState.date.split('-').reverse().join('.')})""")
    assert f"урок №33 от {result['date']}" in result["text"]
    assert result["absent"] in result["text"]
    assert "уважаемые родители!\n\n\n\n" in result["text"]
    assert "Начислены астрокоины" in result["text"]
    assert "На онлайн-платформе" in result["text"]
    assert not result["hasCourseText"]
    assert page.locator("[data-feedback-copy]").is_enabled()
    page.reload(wait_until="networkidle")
    assert page.evaluate("feedbackState.lesson") is None
    assert page.locator("#feedbackText").input_value() == result["text"]
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


def test_existing_lesson_can_switch_to_no_topic_and_back_without_changing_number(feedback_page):
    page = feedback_page
    original_number = page.evaluate("feedbackState.lesson+feedbackState.offset")
    original_text = page.locator("#feedbackText").input_value()
    page.locator("#feedbackLesson").select_option("")
    page.wait_for_function("feedbackState.generated?.lesson === null")
    assert page.evaluate("feedbackState.generated.offset") == original_number
    assert page.locator("#feedbackText").input_value() != original_text
    assert not page.locator(".feedback-material").count()
    page.locator("#feedbackLesson").select_option("1")
    page.wait_for_function("feedbackState.generated?.lesson === 1")
    number = page.evaluate("feedbackState.generated.lesson+feedbackState.generated.offset")
    assert number == original_number
    assert page.locator(".feedback-material").is_visible()


def test_no_topic_schedule_choice_persists_and_is_not_a_repeat_source(feedback_page):
    page = feedback_page
    page.locator(".feedback-schedule-settings > summary").click()
    row = page.locator("[data-feedback-schedule-row]").nth(1)
    row_id = row.get_attribute("data-feedback-schedule-row")
    row.locator('[name="lesson"]').select_option("")
    page.locator('#feedbackScheduleForm [type="submit"]').click()
    page.locator(f'.feedback-weeks [data-feedback-row="{row_id}"]').click()
    assert page.evaluate("feedbackState.lesson") is None
    assert "урок №02" in page.locator("#feedbackText").input_value()
    page.locator("[data-feedback-add-row]").click()
    assert not page.locator(f'#feedbackRepeatForm option[value="{row_id}"]').count()
    page.locator("[data-feedback-close-repeat]").click()
    page.reload(wait_until="networkidle")
    assert page.evaluate("feedbackState.lesson") is None


def test_manual_no_topic_template_restores_with_absent_names(feedback_page):
    page = feedback_page
    page.locator('[data-feedback-tab="manual"]').click()
    page.locator("#feedbackLesson").select_option("")
    page.wait_for_function("feedbackState.generated?.lesson === null")
    page.locator('#feedbackComposeForm [name="extraAbsent"]').fill("Иван Иванов")
    page.locator('#feedbackComposeForm [name="extraAbsent"]').press("Tab")
    template = page.locator("#feedbackText").input_value()
    assert "Иван Иванов" in template and "урок №01" in template
    page.reload(wait_until="networkidle")
    assert page.evaluate("feedbackState.tab") == "manual"
    assert page.evaluate("feedbackState.lesson") is None
    assert page.locator("#feedbackText").input_value() == template
