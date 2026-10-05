"""Browser regressions for the local-only feedback workspace; never touch production."""

import json
import os
import threading
from datetime import date
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import pytest

MINIAPP = Path(__file__).parents[1] / "app/web/static/miniapp"


@pytest.fixture(scope="module")
def feedback_browser():
    playwright = pytest.importorskip("playwright.sync_api")

    class Handler(SimpleHTTPRequestHandler):
        def translate_path(self, path):
            path = urlsplit(path).path
            if path == "/miniapp":
                return str(MINIAPP / "index.html")
            if path.startswith("/miniapp/static/"):
                target = (MINIAPP / path.removeprefix("/miniapp/static/")).resolve()
                if target.is_relative_to(MINIAPP.resolve()):
                    return str(target)
            return str(MINIAPP / "nonexistent")

        def do_GET(self):
            if urlsplit(self.path).path == "/api/v1/miniapp/feedback/catalog":
                source = MINIAPP.parents[3] / "data" / "courses.json"
                raw = json.loads(source.read_text(encoding="utf-8"))
                topics = json.loads(
                    (source.parent / "feedback_topics.json").read_text(encoding="utf-8")
                )
                catalog = {
                    course: [
                        {
                            "title": title,
                            "educational_results": lesson["educational_results"],
                            "topic": topics[course][title],
                        }
                        for title, lesson in lessons.items()
                    ]
                    for course, lessons in raw.items()
                }
                payload = json.dumps(catalog).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            super().do_GET()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    with playwright.sync_playwright() as runtime:
        try:
            browser = runtime.chromium.launch(channel="msedge" if os.name == "nt" else None)
        except playwright.Error as error:
            server.shutdown()
            server.server_close()
            if "Executable doesn't exist" in str(error) or "distribution 'msedge'" in str(error):
                pytest.skip("Install a Playwright Chromium browser to run UI regressions")
            raise
        yield browser, f"http://127.0.0.1:{server.server_port}"
        browser.close()
    server.shutdown()
    server.server_close()


@pytest.fixture
def feedback_page(feedback_browser):
    browser, base = feedback_browser
    context = browser.new_context(viewport={"width": 1400, "height": 1000})
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route("https://st.max.ru/**", lambda route: route.abort())
    page.goto(
        base + "/miniapp?demo=1&demo_role=teacher&feedback_preview=1&view=feedback",
        wait_until="networkidle",
    )
    page.wait_for_selector("#feedbackComposeForm")
    yield page
    context.close()
    assert not errors, errors


def test_production_feedback_is_exclusive_to_superadmin(feedback_page):
    results = feedback_page.evaluate("""() => {
      apiContext.demoMode = false;
      // A manually set preview flag must not bypass the production role check.
      apiContext.feedbackPreview = true;
      state.role = 'admin';
      const denied = ['teacher', 'curator', 'admin', 'partner_director', 'student', 'parent', ''];
      const hidden = denied.every(role => {
        state.staffRoles = role ? [role] : [];
        setView('feedback');
        return !roleViews('admin').includes('feedback') && state.view === 'dashboard';
      });
      state.staffRoles = ['superadmin'];
      return {hidden, allowed: canAccessFeedback() && roleViews('admin').includes('feedback')};
    }""")
    assert results == {"hidden": True, "allowed": True}


def test_feedback_uses_own_teacher_groups_without_changing_admin_scope(feedback_page):
    result = feedback_page.evaluate("""async () => {
      apiContext.demoMode = false;
      apiContext.feedbackPreview = false;
      state.role = 'admin';
      state.staffRoles = ['superadmin', 'teacher'];
      students.forEach((student, index) => {
        student.staffVisible = true;
        student.teacherVisible = index === 0;
      });
      const before = studentsForCurrentRole().map(student => student.id);
      const ownGroup = studentGroupName(students[0]);
      const ownStudents = feedbackStudents().map(student => student.id);
      feedbackState.group = '';
      await renderFeedback();
      return {ownStudents, expected:[students[0].id],
        groups:feedbackGroups(), ownGroup,
        cards:document.querySelectorAll('[data-feedback-group]').length,
        unchanged:JSON.stringify(before) ===
          JSON.stringify(studentsForCurrentRole().map(s => s.id))};
    }""")
    assert result["ownStudents"] == result["expected"]
    assert result["groups"] == [result["ownGroup"]]
    assert result["cards"] == 1
    assert result["unchanged"] is True
    # Production uses the superadmin role, never the localhost preview flag.
    feedback_page.locator("#feedbackComposeForm button[type=submit]").click()
    assert feedback_page.locator("#feedbackText").input_value()
    assert feedback_page.locator('[data-feedback-tab="history"]').count() == 0


def test_switching_school_keeps_separate_feedback_cache(feedback_page):
    result = feedback_page.evaluate("""async () => {
      const key=feedbackStorageKey;
      feedbackState.schedules[feedbackState.group].rows[0].date='2020-01-01';
      feedbackPersist();
      apiContext.tenantSlug='another-school';
      await renderFeedback();
      return {separate:key!==feedbackStorageKey,
        date:feedbackSchedule(feedbackState.group).rows[0].date,
        retained:JSON.parse(localStorage.getItem(key)).schedules};
    }""")
    assert result["separate"] is True
    assert result["date"] != "2020-01-01"
    assert any(
        schedule["rows"][0]["date"] == "2020-01-01" for schedule in result["retained"].values()
    )


def test_server_schedule_migration_authority_and_failed_save(feedback_page):
    page = feedback_page
    remote = {}
    calls = []
    fail_save = False

    def schedules(route):
        if route.request.method == "GET":
            route.fulfill(json={"schedules": remote})
            return
        data = route.request.post_data_json
        calls.append(data)
        if fail_save:
            route.fulfill(status=503, json={"detail": "Сервер временно недоступен"})
            return
        previous = remote.get(data["group_name"], {"revision": 0})
        if data["revision"] != previous["revision"]:
            route.fulfill(status=409, json={"detail": "Конфликт версии"})
            return
        entry = {"schedule": data["schedule"], "revision": data["revision"] + 1}
        remote[data["group_name"]] = entry
        route.fulfill(json=entry)

    page.route("**/miniapp/feedback/schedules*", schedules)
    page.evaluate("""async () => {
      apiContext.demoMode=false; state.role='admin'; state.staffRoles=['superadmin','teacher'];
      students.forEach(student=>{student.staffVisible=true;student.teacherVisible=true;
        student.course='Питон Старт 1-й год';});
      await feedbackLoadServerSchedules();
    }""")
    assert remote
    assert len(calls) == len(remote)
    group = page.evaluate("feedbackState.group")
    remote[group]["schedule"]["rows"][0]["date"] = "2026-09-01"
    page.evaluate("""async () => {
      feedbackState.schedules[feedbackState.group].rows[0].date='2026-10-04';
      await feedbackLoadServerSchedules(); await renderFeedback();
    }""")
    assert page.evaluate("feedbackSchedule(feedbackState.group).rows[0].date") == "2026-09-01"
    assert len(calls) == len(remote)
    page.locator(".feedback-schedule-settings > summary").click()
    page.locator('#feedbackScheduleForm [name="firstDate"]').fill("2026-10-04")
    page.locator('#feedbackScheduleForm [name="firstDate"]').press("Tab")
    fail_save = True
    page.locator('#feedbackScheduleForm [type="submit"]').click()
    page.wait_for_function("!feedbackState.scheduleSaving")
    assert page.evaluate("feedbackState.editorDirty") is True
    assert page.evaluate("feedbackState.editor.rows[0].date") == "2026-10-04"
    assert remote[group]["schedule"]["rows"][0]["date"] == "2026-09-01"
    fail_save = False
    page.locator('#feedbackScheduleForm [type="submit"]').click()
    page.wait_for_function("!feedbackState.editorDirty")
    assert remote[group]["schedule"]["rows"][0]["date"] == "2026-10-04"
    assert remote[group]["revision"] == 2


def test_switching_courses_resizes_schedule_before_anchor_edit(feedback_page):
    page = feedback_page
    page.locator(".feedback-schedule-settings > summary").click()
    count = page.evaluate('feedbackState.catalog["Основы логики и программирования"].length')
    page.locator("#feedbackScheduleForm [name=course]").select_option(
        "Основы логики и программирования"
    )
    assert page.locator("[data-feedback-schedule-row]").count() == count
    assert page.locator("#feedbackScheduleForm select[name=lesson]").evaluate_all(
        '(items) => items.every(item => item.value !== "")'
    )
    page.locator("#feedbackScheduleForm [name=firstDate]").fill("2026-10-04")
    page.locator("#feedbackScheduleForm [name=firstDate]").press("Tab")
    assert page.evaluate("feedbackState.editor.rows[1].date") == "2026-10-11"
    page.locator("[data-feedback-add-row]").click()
    page.locator("#feedbackRepeatForm [type=submit]").click()
    assert page.locator("#feedbackScheduleForm .feedback-repeat-badge").count() == 1
    assert page.locator("input[name=repeat]").count() == 0
    page.locator("#feedbackScheduleForm [type=submit]").click()
    page.reload(wait_until="networkidle")
    assert page.evaluate("feedbackSchedule(feedbackState.group).course") == (
        "Основы логики и программирования"
    )
    assert page.evaluate("feedbackSchedule(feedbackState.group).rows.length") == count + 1
    page.locator(".feedback-schedule-settings > summary").click()
    page.locator("#feedbackScheduleForm [name=course]").select_option("Питон Старт 1-й год")
    assert page.locator("[data-feedback-schedule-row]").count() == 37
    assert page.locator("#feedbackScheduleForm .feedback-repeat-badge").count() == 1
    assert page.evaluate("feedbackState.editor.rows[0].date") == "2026-10-04"


def test_first_row_date_rebases_following_lessons_and_selects_first(feedback_page):
    page = feedback_page
    page.evaluate("""async () => {
      const group=feedbackState.group;
      feedbackSelectGroup(group,feedbackSchedule(group).rows[4].id);
      await renderFeedback();
    }""")
    page.locator(".feedback-schedule-settings > summary").click()
    page.locator('[data-feedback-schedule-row] input[name="date"]').first.fill("2026-09-05")
    page.locator('[data-feedback-schedule-row] input[name="date"]').first.press("Tab")
    assert page.evaluate("feedbackState.editor.rows.slice(0,3).map(r=>r.date)") == [
        "2026-09-05", "2026-09-12", "2026-09-19"
    ]
    page.locator('#feedbackScheduleForm [type="submit"]').click()
    assert page.evaluate("feedbackState.lesson") == 1
    assert page.evaluate("feedbackState.date") == "2026-09-05"
    page.reload(wait_until="networkidle")
    assert page.evaluate("feedbackState.lesson") == 1


def test_imported_course_names_resolve_exactly_without_python_fallback(feedback_page):
    result = feedback_page.evaluate("""() => {
      const names=['Основы логики и программирования','Питон Старт 1-й год',
        'Питон Старт 2й год','Питон Старт 2-й год','Питон Профессиональный 1-й год',
        'Питон Профессиональный 2-й год','Создание веб-сайтов','Геймдизайн',
        'Визуальное программирование','Визуальное программирование 1 год',
        'Компьютерная грамотность'];
      return {matches:names.map(name=>feedbackResolveCourse(name,feedbackState.catalog)),
        unknown:feedbackResolveCourse('Графический дизайн 12-14',feedbackState.catalog),
        old:Object.hasOwn(feedbackState.catalog,'Геймдизайн OLD'),
        initial:feedbackState.lesson,
        firstDate:feedbackSchedule(feedbackState.group).rows[0].date,
        selectedDate:feedbackState.date};
    }""")
    assert all(result["matches"])
    assert result["matches"][0] == "Основы логики и программирования"
    assert result["matches"][2] == "Питон Старт 2-й год"
    assert result["unknown"] == ""
    assert not result["old"]
    assert result["initial"] == 1
    assert result["firstDate"] == result["selectedDate"]


def test_group_schedule_uses_imported_course_and_its_actual_lesson_count(feedback_page):
    result = feedback_page.evaluate("""() => {
      const group=feedbackState.group;
      students.filter(s=>studentGroupName(s)===group).forEach(s=>{
        s.course='Основы логики и программирования';
      });
      delete feedbackState.schedules[group];
      const schedule=feedbackSchedule(group);
      feedbackSelectGroup(group);
      return {course:schedule.course,count:schedule.rows.length,
        lesson:feedbackState.lesson,date:feedbackState.date,first:schedule.rows[0].date};
    }""")
    assert result["course"] == "Основы логики и программирования"
    assert result["count"] == 32
    assert result["lesson"] == 1
    assert result["date"] == result["first"]


def test_legacy_course_names_keep_saved_dates_and_ignore_old_drafts(feedback_page):
    result = feedback_page.evaluate("""() => {
      const group=feedbackState.group;
      const schedule=structuredClone(feedbackSchedule(group));
      schedule.course='Python Start 1 год';
      const draft={id:'draft',group,course:'Python Start 1 год',lesson:1,offset:0,
        date:'2026-09-05',mode:'group',text:'Сохранённый текст'};
      const restored=feedbackRestore({schedules:{[group]:schedule},drafts:[draft]},
        feedbackState.catalog,[group]);
      return {course:restored.schedules[group].course,date:restored.schedules[group].rows[0].date,
        original:schedule.rows[0].date,drafts:Object.hasOwn(restored,"drafts"),recovered:restored.recovered};
    }""")
    assert result["course"] == "Питон Старт 1-й год"
    assert result["date"] == result["original"]
    assert result["drafts"] is False
    assert result["recovered"] == 0


def test_every_course_pair_has_complete_valid_materials_after_switch(feedback_page):
    failures = feedback_page.evaluate("""() => {
      const failures=[];
      for (const source of Object.keys(feedbackState.catalog)) {
        const schedule={course:source,mode:'group',rows:feedbackSeries(source,'2026-09-05',
          1,1,feedbackState.catalog[source].length,7,feedbackState.catalog)};
        for (const target of Object.keys(feedbackState.catalog)) {
          const next=feedbackChangeCourse(schedule,target,feedbackState.catalog);
          if (next.rows.length!==feedbackState.catalog[target].length ||
            new Set(next.rows.map(row=>row.lesson)).size!==feedbackState.catalog[target].length)
            failures.push({source,target});
          feedbackValidateSchedule(next,feedbackState.catalog);
        }
      }
      return failures;
    }""")
    assert failures == []


def test_weekday_and_time_group_order(feedback_page):
    ordered = feedback_page.evaluate("""() => {
      const groups=['ВП сб 14:00', 'ПП вс 14-00', 'КГ сб 12:00', 'ПС вс 10:00', 'ГД пн 18:00'];
      return groups.sort((a,b) => {const x=feedbackGroupOrder(a), y=feedbackGroupOrder(b);
        return x[0]-y[0] || x[1]-y[1];});
    }""")
    assert ordered == ["ГД пн 18:00", "КГ сб 12:00", "ВП сб 14:00", "ПС вс 10:00", "ПП вс 14-00"]


def test_anchor_date_repeat_insertion_and_disabled_lesson_reflow(feedback_page):
    page = feedback_page
    page.locator(".feedback-schedule-settings > summary").click()
    before = page.evaluate("structuredClone(feedbackState.editor.rows)")
    page.locator("#feedbackScheduleForm [name=firstDate]").fill("2026-09-05")
    page.locator("#feedbackScheduleForm [name=firstDate]").press("Tab")
    assert page.evaluate("feedbackState.editor.rows[1].date") == "2026-09-12"
    # A manual exception follows the anchor shift while keeping its own offset.
    page.locator("[data-feedback-schedule-row]").nth(3).locator("[name=date]").fill("2026-09-28")
    page.locator("[data-feedback-schedule-row]").nth(3).locator("[name=date]").press("Tab")
    page.locator("[data-feedback-add-row]").click()
    assert page.locator("#feedbackRepeatDialog").is_visible()
    page.locator("#feedbackRepeatForm [name=repeatRow]").select_option(before[1]["id"])
    page.locator("#feedbackRepeatForm [type=submit]").click()
    inserted = page.evaluate("structuredClone(feedbackState.editor.rows)")
    assert len(inserted) == len(before) + 1
    assert inserted[2]["lesson"] == before[1]["lesson"]
    assert inserted[2]["repeat"] is True
    assert inserted[2]["date"] == "2026-09-19"
    assert inserted[3]["id"] == before[2]["id"]
    assert inserted[3]["date"] == "2026-09-26"
    assert inserted[4]["date"] == "2026-10-05"
    assert [row["number"] for row in inserted] == list(range(1, len(inserted) + 1))
    disabled_id = inserted[1]["id"]
    page.locator(f'[data-feedback-schedule-row="{disabled_id}"] [name=skipped]').check()
    disabled = page.evaluate("structuredClone(feedbackState.editor.rows)")
    assert disabled[1]["skipped"] is True
    assert disabled[2]["number"] == 2
    assert disabled[2]["date"] == "2026-09-12"
    assert [row["lesson"] for row in disabled] == [row["lesson"] for row in inserted]
    page.locator(f'[data-feedback-schedule-row="{disabled_id}"] [name=skipped]').uncheck()
    assert page.evaluate("feedbackState.editor.rows") == inserted
    page.locator("#feedbackScheduleForm [type=submit]").click()
    assert page.locator(".feedback-lesson-topic").first.inner_text()
    page.reload(wait_until="networkidle")
    assert page.evaluate("feedbackSchedule(feedbackState.group).rows") == inserted


def test_disable_first_lesson_preserves_anchor_and_can_be_restored(feedback_page):
    result = feedback_page.evaluate("""() => {
      const schedule=structuredClone(feedbackSchedule(feedbackState.group));
      const next=feedbackToggleLesson(schedule,schedule.rows[0].id,true);
      const restored=feedbackToggleLesson(next,schedule.rows[0].id,false);
      return {number:next.rows[1].number, date:next.rows[1].date,
        expected:schedule.rows[0].date, same:JSON.stringify(restored)===JSON.stringify(schedule)};
    }""")
    assert result["number"] == 1
    assert result["date"] == result["expected"]
    assert result["same"] is True


def test_every_source_lesson_generates_the_correct_material(feedback_page):
    results = feedback_page.evaluate("""() => {
      const results = [];
      for (const [course, lessons] of Object.entries(feedbackState.catalog)) {
        lessons.forEach((lesson, index) => {
          Object.assign(feedbackState, {course, lesson:index+1, date:'2026-10-03', offset:0,
            mode:'group', repeat:false, coins:false, absent:[], extraAbsent:''});
          const text = feedbackBuildText();
          results.push({course, lesson:index+1, correct:text.includes(lesson.educational_results)
            && text.includes('от 03.10.2026') && !text.includes('undefined')});
        });
      }
      return results;
    }""")
    assert len(results) == 700
    failures = [item for item in results if not item["correct"]]
    assert not failures, failures


def test_calendar_validation_including_leap_years_and_invalid_dates(feedback_page):
    candidates = [
        f"{year}-{month:02d}-{day:02d}"
        for year in (2000, 2024, 2025, 2026, 2100)
        for month in (1, 2, 4, 12)
        for day in (0, 1, 28, 29, 30, 31, 32)
    ]
    candidates += ["", "bad", "2026-1-3", "1999-12-31", "2101-01-01", "2026-13-01"]
    expected = []
    for value in candidates:
        try:
            parsed = date.fromisoformat(value)
            expected.append(
                parsed.isoformat() == value and date(2000, 1, 1) <= parsed <= date(2100, 12, 31)
            )
        except ValueError:
            expected.append(False)
    actual = feedback_page.evaluate("values => values.map(feedbackValidDate)", candidates)
    assert actual == expected


def test_message_rejects_fractional_nonfinite_and_invalid_context(feedback_page):
    outcomes = feedback_page.evaluate("""() => {
      const base = {course:Object.keys(feedbackState.catalog)[0], lesson:5,
        offset:0, date:'2026-10-03', mode:'group'};
      const bad = [{date:''},{date:'2026-02-31'},{mode:'invalid'},{course:'missing'},
        {offset:Infinity},{offset:NaN},{offset:.5},{offset:-5},{offset:null},{offset:''},
        {lesson:0},{lesson:1.5},{lesson:999},{offset:999},{offset:true}];
      return bad.map(change => {try {
        feedbackValidateMessage({...base,...change},feedbackState.catalog);
        return false;
      }catch{return true;}});
    }""")
    assert all(outcomes)


def test_per_lesson_dates_material_numbers_and_repetition_persist(feedback_page):
    page = feedback_page
    page.locator(".feedback-schedule-settings > summary").click()
    row = page.locator("[data-feedback-schedule-row]").nth(1)
    row_id = row.get_attribute("data-feedback-schedule-row")
    row.locator('[name="date"]').fill("2026-10-07")
    row.locator('[name="number"]').fill("101")
    row.locator('[name="lesson"]').select_option("1")
    assert row.locator(".feedback-repeat-badge").is_visible()
    assert page.locator('input[name="repeat"]').count() == 0
    page.locator('#feedbackScheduleForm [type="submit"]').click()
    page.locator(f'[data-feedback-row="{row_id}"]').click()
    page.locator('#feedbackComposeForm [type="submit"]').click()
    text = page.locator("#feedbackText").input_value()
    assert "урок №101 от 07.10.2026" in text
    assert "повторяли тему предыдущего занятия" in text
    assert page.locator(
        f'.feedback-weeks [data-feedback-row="{row_id}"] .feedback-repeat-badge'
    ).is_visible()
    page.reload(wait_until="networkidle")
    row = page.locator(f'[data-feedback-schedule-row="{row_id}"]')
    page.locator(".feedback-schedule-settings > summary").click()
    assert row.locator('[name="date"]').input_value() == "2026-10-07"
    assert row.locator('[name="number"]').input_value() == "101"
    assert row.locator('[name="lesson"]').input_value() == "1"
    assert row.locator(".feedback-repeat-badge").is_visible()


def test_message_edits_need_confirmation_before_regeneration_or_switch(feedback_page):
    page = feedback_page
    row_id = page.evaluate("feedbackState.rowId")
    submit = page.locator('#feedbackComposeForm [type="submit"]')
    submit.click()
    text = page.locator("#feedbackText").input_value() + "\n\nМоя ручная правка"
    page.locator("#feedbackText").fill(text)
    submit.click()
    assert page.locator("#confirmationDialog").is_visible()
    page.locator("#cancelConfirmationButton").click()
    assert page.locator("#feedbackText").input_value() == text
    next_row = page.locator(f'.feedback-weeks button:not([data-feedback-row="{row_id}"])').first
    next_row.click()
    assert page.locator("#confirmationDialog").is_visible()
    page.locator("#cancelConfirmationButton").click()
    assert page.locator("#feedbackText").input_value() == text
    next_row.click()
    page.locator("#confirmConfirmationButton").click()
    assert page.locator("#feedbackText").input_value() == ""
    page.reload(wait_until="networkidle")
    assert page.locator("#feedbackText").input_value() == ""


def test_schedule_remove_confirmation_undo_and_unsaved_guard(feedback_page):
    page = feedback_page
    page.locator(".feedback-schedule-settings > summary").click()
    count = page.locator("[data-feedback-schedule-row]").count()
    page.locator("[data-feedback-remove-row]").first.click()
    page.locator("#cancelConfirmationButton").click()
    assert page.locator("[data-feedback-schedule-row]").count() == count
    page.locator("[data-feedback-remove-row]").first.click()
    page.locator("#confirmConfirmationButton").click()
    assert page.locator("[data-feedback-schedule-row]").count() == count - 1
    page.locator("[data-feedback-undo]").click()
    assert page.locator("[data-feedback-schedule-row]").count() == count
    page.locator('[data-feedback-tab="manual"]').click()
    assert page.locator("#confirmationDialog").is_visible()
    page.locator("#cancelConfirmationButton").click()
    assert page.locator("#feedbackScheduleForm").is_visible()
    page.locator('[data-feedback-tab="manual"]').click()
    page.locator("#confirmConfirmationButton").click()
    assert page.locator("#feedbackComposeForm").is_visible()
    page.locator('[data-feedback-tab="groups"]').click()
    assert not page.locator("#confirmationDialog").is_visible()


def test_cancelled_lesson_cannot_generate_feedback(feedback_page):
    page = feedback_page
    selected = page.evaluate("feedbackState.rowId")
    page.locator(".feedback-schedule-settings > summary").click()
    page.locator(f'[data-feedback-schedule-row="{selected}"] [name="skipped"]').check()
    page.locator('#feedbackScheduleForm [type="submit"]').click()
    page.locator('#feedbackComposeForm [type="submit"]').click()
    assert "отменённым" in page.locator("#noticeMessage").inner_text()
    assert page.locator("#feedbackText").input_value() == ""


def test_corrupt_schedule_recovers_and_old_drafts_are_not_restored(feedback_page):
    page = feedback_page
    page.evaluate("""() => {
      feedbackPersist();
      const raw=JSON.parse(localStorage.getItem(feedbackStorageKey));
      raw.schedules[feedbackState.group].course='missing';
      raw.drafts=[{text:'Старое сообщение'},null];
      localStorage.setItem(feedbackStorageKey,JSON.stringify(raw));
    }""")
    page.reload(wait_until="networkidle")
    assert page.locator("#feedbackComposeForm").is_visible()
    assert page.locator("#feedbackText").input_value() == ""
    assert page.evaluate(
        '!Object.hasOwn(JSON.parse(localStorage.getItem(feedbackStorageKey)),"drafts")'
    )


def test_message_download_and_drafts_controls_are_removed(feedback_page):
    page = feedback_page
    page.locator('#feedbackComposeForm [type="submit"]').click()
    text = page.locator("#feedbackText").input_value()
    with page.expect_download() as download:
        page.locator("[data-feedback-download]").click()
    assert Path(download.value.path()).read_text(encoding="utf-8") == text
    assert page.locator('[data-feedback-tab="history"], [data-feedback-save]').count() == 0
    assert page.locator('[data-feedback-copy]').is_enabled()
    assert "Черновик" not in page.locator("#feedbackWorkspace").inner_text()


def test_mobile_layout_and_keyboard_tab_navigation(feedback_page):
    page = feedback_page
    page.set_viewport_size({"width": 390, "height": 844})
    page.locator(".feedback-schedule-settings > summary").click()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
    page.locator('[data-feedback-tab="groups"]').focus()
    page.keyboard.press("ArrowRight")
    page.wait_for_function("feedbackState.tab==='manual'")
    assert page.locator('[data-feedback-tab="manual"]').evaluate("e=>e===document.activeElement")


def test_absent_name_normalization_and_profile_isolation(feedback_page):
    page = feedback_page
    actual = page.evaluate(
        "feedbackUniqueNames([' Маша ','маша','Маша','Иван  Иванов','Иван Иванов'])"
    )
    assert actual == ["Маша", "Иван Иванов"]
    page.locator('#feedbackComposeForm [type="submit"]').click()
    base = urlsplit(page.url)
    page.goto(
        f"{base.scheme}://{base.netloc}/miniapp"
        "?demo=1&demo_role=admin&feedback_preview=1&view=feedback",
        wait_until="networkidle",
    )
    assert page.locator("#feedbackText").input_value() == ""
    page.goto(
        f"{base.scheme}://{base.netloc}/miniapp?demo=1&demo_role=parent&feedback_preview=1",
        wait_until="networkidle",
    )
    assert not page.locator('[data-view="feedback"]').first.is_visible()


def test_course_change_preserves_incomplete_date(feedback_page):
    page = feedback_page
    page.locator('#feedbackComposeForm [name="date"]').fill("")
    course = page.locator("#feedbackCourse option").nth(1).get_attribute("value")
    page.locator("#feedbackCourse").select_option(course)
    assert page.locator('#feedbackComposeForm [name="date"]').input_value() == ""
    assert page.locator("#feedbackCourse").input_value() == course


def test_duplicate_schedule_numbers_are_rejected(feedback_page):
    page = feedback_page
    page.locator(".feedback-schedule-settings > summary").click()
    page.locator('[data-feedback-schedule-row] [name="number"]').nth(1).fill("1")
    page.locator('#feedbackScheduleForm [type="submit"]').click()
    assert "повторяется" in page.locator("#noticeMessage").inner_text()
    assert page.evaluate("feedbackSchedule(feedbackState.group).rows[1].number") == 2


def test_bulk_schedule_intervals_validate_and_require_confirmation(feedback_page):
    page = feedback_page
    page.locator(".feedback-schedule-settings > summary").click()
    page.locator(".feedback-series-settings > summary").click()
    page.locator('#feedbackSeriesForm [name="startDate"]').fill("2026-10-03")
    page.locator('#feedbackSeriesForm [name="count"]').fill("3")
    page.locator('#feedbackSeriesForm [name="interval"]').fill("14")
    page.locator('#feedbackSeriesForm [type="submit"]').click()
    page.locator("#confirmConfirmationButton").click()
    assert page.locator("[data-feedback-schedule-row]").count() == 3
    actual = page.locator('[data-feedback-schedule-row] [name="date"]').nth(2).input_value()
    assert actual == "2026-10-31"
    page.locator('#feedbackScheduleForm [type="submit"]').click()
    page.reload(wait_until="networkidle")
    assert page.locator("[data-feedback-row]").count() == 3


def test_catalog_failure_is_retryable(feedback_page):
    page = feedback_page
    requests = []

    def once(route):
        requests.append(True)
        if len(requests) == 1:
            route.fulfill(status=503, body="Unavailable")
        else:
            route.continue_()

    page.route("**/miniapp/feedback/catalog", once)
    page.reload(wait_until="networkidle")
    page.locator("[data-feedback-retry]").click()
    page.wait_for_selector("#feedbackComposeForm")
    assert page.locator("#feedbackCourse option").count() == 20


def test_malformed_storage_variants_are_safe_and_ignore_old_drafts(feedback_page):
    results = feedback_page.evaluate("""() => {
      const catalog=feedbackState.catalog, groups=feedbackGroups();
      const bad=[null,undefined,[],0,true,'bad',{}, {drafts:[null]},
        {schedules:[]}, {schedules:true}, {drafts:{}},
        {drafts:[{id:'old',text:'Старое сообщение'}]}];
      return bad.map(raw=>{try {const value=feedbackRestore(raw,catalog,groups);
        return !Object.hasOwn(value,'drafts') && typeof value.schedules==='object';
      }catch{return false;}});
    }""")
    assert all(results)


def test_edits_keep_generated_metadata_until_message_is_regenerated(feedback_page):
    page = feedback_page
    page.locator('#feedbackComposeForm [type="submit"]').click()
    original_date = page.evaluate("feedbackState.generated.date")
    page.locator('#feedbackComposeForm [name="date"]').fill("2026-11-01")
    page.locator("#feedbackText").fill("Редакция для прежнего занятия")
    assert page.evaluate("feedbackState.generated.date") == original_date
    assert page.locator(".feedback-stale-note").is_visible()


def test_invalid_advanced_control_is_revealed_before_validation(feedback_page):
    page = feedback_page
    page.locator(".feedback-advanced > summary").click()
    page.locator('#feedbackComposeForm [name="offset"]').fill("1000")
    page.locator(".feedback-advanced > summary").click()
    # Explicit validation opens the collapsed container before focusing its invalid input.
    page.locator('#feedbackComposeForm [type="submit"]').click()
    assert page.locator(".feedback-advanced").evaluate("element => element.open")


def test_astrocoin_balance_info_is_always_present_and_accrual_is_optional(feedback_page):
    page = feedback_page
    submit = page.locator('#feedbackComposeForm [type="submit"]')
    submit.click()
    text = page.locator("#feedbackText").input_value()
    assert "Баланс астрокоинов" in text
    assert "https://max.ru/id525601030904_3_bot" in text
    assert "Начислены астрокоины" not in text
    page.locator('#feedbackComposeForm [name="coins"]').check()
    submit.click()
    text = page.locator("#feedbackText").input_value()
    assert "Начислены астрокоины за урок №01" in text
    assert text.count("https://max.ru/id525601030904_3_bot") == 1
    row_id = page.evaluate("feedbackState.rowId")
    page.locator(f'.feedback-weeks button:not([data-feedback-row="{row_id}"])').first.click()
    assert not page.locator('#feedbackComposeForm [name="coins"]').is_checked()
    submit.click()
    assert "Начислены астрокоины" not in page.locator("#feedbackText").input_value()
