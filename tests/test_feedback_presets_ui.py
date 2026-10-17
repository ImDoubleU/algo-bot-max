from datetime import datetime

from tests.test_feedback_workspace_ui import feedback_browser as _feedback_browser
from tests.test_feedback_workspace_ui import feedback_page as _feedback_page

feedback_browser = _feedback_browser
feedback_page = _feedback_page


def test_group_click_picks_latest_past_lesson_and_generates_preset(feedback_page):
    page = feedback_page
    page.clock.install(time=datetime.fromisoformat("2026-10-18T12:00:00+03:00"))
    result = page.evaluate("""async () => {
      const group=feedbackState.group, course=feedbackState.course;
      feedbackState.schedules[group]={course,mode:'online',rows:feedbackSeries(course,'2026-10-03',1,1,6,7,feedbackState.catalog)};
      feedbackSelectGroup(group); await renderFeedback();
      return {lesson:feedbackState.lesson,date:feedbackState.date,coins:feedbackState.coins,
        mode:feedbackState.mode,text:feedbackState.text};
    }""")
    assert result["lesson"] == 3 and result["date"] == "2026-10-17"
    assert result["coins"] is True and result["mode"] == "group"
    assert "урок №03 от 17.10.2026" in result["text"]
    page.locator(".feedback-student-chips label").first.click()
    assert page.evaluate("feedbackState.generated.absent.length") == 1
    assert page.locator("[data-feedback-copy]").is_enabled()
    original = page.locator("#feedbackText").input_value()
    page.locator("#feedbackText").fill(original + "\nМои подробности урока")
    page.locator(".feedback-student-chips label").first.click()
    assert "Мои подробности урока" in page.locator("#feedbackText").input_value()
    assert page.locator("[data-feedback-copy]").is_enabled()
    assert not page.locator('#feedbackScheduleForm [name="mode"]').count()
    assert not page.locator('#feedbackComposeForm [name="coins"]').count()


def test_weekday_reflow_validation_and_repeat_sources(feedback_page):
    result = feedback_page.evaluate("""() => {
      const course=feedbackState.course;
      const schedule={course,mode:'group',cadence:{kind:'weekdays',weekdays:[1,3]},
        rows:feedbackSeries(course,'2026-10-19',1,1,4,7,feedbackState.catalog,[1,3])};
      const repeat=feedbackInsertRepeat(schedule,schedule.rows[0].id);
      const disabled=feedbackToggleLesson(schedule,schedule.rows[0].id,true);
      const removed=feedbackRemoveLesson(schedule,schedule.rows[1].id);
      const marked=feedbackMarkRepeats({...schedule,rows:[
        {...schedule.rows[0],skipped:true},{...schedule.rows[1],lesson:1}]});
      const invalid=structuredClone(schedule);invalid.rows[1].date='2026-01-01';
      let rejected=false;
      try {feedbackValidateSchedule(invalid,feedbackState.catalog);} catch {rejected=true;}
      let missingRejected=false;
      try {feedbackInsertRepeat(schedule,'missing');} catch {missingRejected=true;}
      return {repeat:repeat.rows.map(r=>r.date),
        disabled:disabled.rows.filter(r=>!r.skipped).map(r=>r.date),
        removed:removed.rows.map(r=>r.number),disabledIsRepeat:marked.rows[1].repeat,rejected,missingRejected};
    }""")
    assert result["repeat"] == [
        "2026-10-19", "2026-10-21", "2026-10-26", "2026-10-28", "2026-11-02",
    ]
    assert result["disabled"] == ["2026-10-19", "2026-10-21", "2026-10-26"]
    assert result["removed"] == [1, 2, 3]
    assert result["disabledIsRepeat"] is False
    assert result["rejected"] and result["missingRejected"]


def test_custom_individual_group_and_mobile_picker_survive_reload(feedback_page):
    page = feedback_page
    page.set_viewport_size({"width": 390, "height": 844})
    page.clock.install(time=datetime.fromisoformat("2026-10-18T12:00:00+03:00"))
    page.locator("[data-feedback-add-group]").click()
    form = page.locator("#feedbackGroupForm")
    form.locator('[name="name"]').fill("Индивидуально: Маша, сб 11:00")
    form.locator('[name="course"]').select_option(page.evaluate("feedbackState.course"))
    form.locator('[name="mode"]').select_option("individual")
    form.locator('[name="firstDate"]').fill("2026-10-03")
    form.locator('[name="members"]').fill("Маша Иванова\nПётр Петров")
    form.locator('[type="submit"]').click()
    page.wait_for_function("feedbackState.mode === 'individual'")
    assert page.evaluate("feedbackState.lesson") == 3
    assert not page.evaluate("feedbackState.coins")
    assert "астрокоины" not in page.locator("#feedbackText").input_value().lower()
    assert page.locator("#feedbackActiveLesson").is_visible()
    assert page.locator(".feedback-weeks").is_hidden()
    assert page.locator(".feedback-student-chips label").count() == 2
    page.locator("#feedbackText").fill("Свой текст для Маши")
    row_id = page.evaluate("feedbackState.rowId")
    next_row = page.evaluate("feedbackSchedule(feedbackState.group).rows[3].id")
    page.locator("#feedbackActiveLesson").select_option(next_row)
    page.wait_for_function("feedbackState.lesson === 4")
    page.locator("#feedbackActiveLesson").select_option(row_id)
    page.wait_for_function("feedbackState.lesson === 3")
    assert page.locator("#feedbackText").input_value() == "Свой текст для Маши"
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.reload(wait_until="networkidle")
    assert page.evaluate("feedbackState.mode") == "individual"
    assert page.locator("#feedbackText").input_value() == "Свой текст для Маши"
    assert page.locator(".feedback-student-chips label").count() == 2


def test_unknown_course_does_not_block_other_groups_or_manual_assignment(feedback_page):
    page = feedback_page
    page.evaluate("""async () => {
      students.push({...students[0],id:'unmatched',group:'Без курса, сб 19:00',
        course:'Неизвестный курс'});
      feedbackSelectGroup('Без курса, сб 19:00');await renderFeedback();
    }""")
    assert page.locator("#feedbackAssignCourseForm").is_visible()
    assert page.locator('#feedbackAssignCourseForm [name="course"]').input_value() == ""
    course = page.evaluate("Object.keys(feedbackState.catalog)[0]")
    page.locator('#feedbackAssignCourseForm [name="course"]').select_option(course)
    page.locator('#feedbackAssignCourseForm [type="submit"]').click()
    page.wait_for_function("feedbackState.course !== ''")
    assert page.locator("#feedbackText").input_value()
    assert page.locator('[data-feedback-tab="manual"]').is_visible()


def test_schedule_save_preserves_edited_message_on_same_lesson(feedback_page):
    page = feedback_page
    page.locator("#feedbackText").fill("Отредактированная ОС")
    page.locator(".feedback-schedule-settings > summary").click()
    page.locator('[data-feedback-schedule-row] [name="date"]').nth(3).fill("2027-01-01")
    # Changing a later date to an invalid order must be rejected without losing the message.
    page.locator('#feedbackScheduleForm [type="submit"]').click()
    assert page.evaluate("feedbackState.editorDirty")
    assert page.locator("#feedbackText").input_value() == "Отредактированная ОС"
    page.evaluate("feedbackState.editor=structuredClone(feedbackSchedule(feedbackState.group));feedbackRedrawEditor()")
    page.locator('#feedbackScheduleForm [type="submit"]').click()
    assert page.locator("#feedbackText").input_value() == "Отредактированная ОС"
    assert page.locator("#feedbackText").is_enabled()
