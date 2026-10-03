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
                catalog = {
                    course: [
                        {"title": title, "educational_results": lesson["educational_results"]}
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
    assert len(results) == 736
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
    row = page.locator("[data-feedback-schedule-row]").first
    row_id = row.get_attribute("data-feedback-schedule-row")
    row.locator('[name="date"]').fill("2026-10-07")
    row.locator('[name="number"]').fill("101")
    row.locator('[name="lesson"]').select_option("8")
    row.locator('[name="repeat"]').check()
    page.locator('#feedbackScheduleForm [type="submit"]').click()
    page.locator(f'[data-feedback-row="{row_id}"]').click()
    page.locator('#feedbackComposeForm [type="submit"]').click()
    text = page.locator("#feedbackText").input_value()
    assert "урок №101 от 07.10.2026" in text
    assert "повторяли тему предыдущего занятия" in text
    page.reload(wait_until="networkidle")
    row = page.locator(f'[data-feedback-schedule-row="{row_id}"]')
    assert row.locator('[name="date"]').input_value() == "2026-10-07"
    assert row.locator('[name="number"]').input_value() == "101"
    assert row.locator('[name="lesson"]').input_value() == "8"
    assert row.locator('[name="repeat"]').is_checked()


def test_autosave_preserves_edits_and_regeneration_needs_confirmation(feedback_page):
    page = feedback_page
    row_id = page.evaluate("feedbackState.rowId")
    submit = page.locator('#feedbackComposeForm [type="submit"]')
    submit.click()
    submit.click()
    assert page.evaluate("feedbackState.drafts.length") == 1
    text = page.locator("#feedbackText").input_value() + "\n\nМоя ручная правка"
    page.locator("#feedbackText").fill(text)
    next_row = page.locator(f'.feedback-weeks button:not([data-feedback-row="{row_id}"])').first
    next_row.click()
    page.locator(f'[data-feedback-row="{row_id}"]').click()
    assert page.locator("#feedbackText").input_value() == text
    submit.click()
    assert page.locator("#confirmationDialog").is_visible()
    page.locator("#cancelConfirmationButton").click()
    assert page.locator("#feedbackText").input_value() == text
    page.reload(wait_until="networkidle")
    assert page.locator("#feedbackText").input_value() == text
    page.locator("#feedbackText").fill("")
    assert not page.locator("#feedbackText").is_disabled()
    page.locator("#feedbackText").fill("Текст снова доступен")
    page.locator("[data-feedback-save]").click()
    assert page.evaluate("feedbackState.drafts[0].text") == "Текст снова доступен"


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
    page.locator('[data-feedback-tab="history"]').click()
    assert page.locator("#confirmationDialog").is_visible()
    page.locator("#cancelConfirmationButton").click()
    assert page.locator("#feedbackScheduleForm").is_visible()
    page.locator('[data-feedback-tab="history"]').click()
    page.locator("#confirmConfirmationButton").click()
    assert page.locator("#feedbackHistorySearch").is_visible()
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


def test_corrupt_storage_recovers_without_losing_valid_draft(feedback_page):
    page = feedback_page
    page.locator('#feedbackComposeForm [type="submit"]').click()
    original = page.locator("#feedbackText").input_value()
    page.evaluate("""() => {
      const raw=JSON.parse(localStorage.getItem(feedbackStorageKey));
      raw.schedules[feedbackState.group].course='missing';
      raw.drafts.push(null, {id:'missing-text',group:'',date:'2026-02-31'});
      localStorage.setItem(feedbackStorageKey,JSON.stringify(raw));
      // Disable pagehide save to preserve the corruption for the reload test.
      feedbackState.generated=null;
    }""")
    page.reload(wait_until="networkidle")
    page.locator('[data-feedback-tab="history"]').click()
    assert page.locator("[data-feedback-draft]").count() == 1
    page.locator("[data-feedback-draft]").click()
    assert page.locator("#feedbackText").input_value() == original


def test_history_search_delete_and_text_download(feedback_page):
    page = feedback_page
    page.locator('#feedbackComposeForm [type="submit"]').click()
    text = page.locator("#feedbackText").input_value()
    with page.expect_download() as download:
        page.locator("[data-feedback-download]").click()
    assert Path(download.value.path()).read_text(encoding="utf-8") == text
    page.locator('[data-feedback-tab="history"]').click()
    page.locator("#feedbackHistorySearch").fill("нет такого текста")
    assert page.locator("[data-feedback-draft]").count() == 0
    page.locator("#feedbackHistorySearch").fill("")
    assert page.locator("[data-feedback-draft]").count() == 1
    page.locator("[data-feedback-delete-draft]").click()
    page.locator("#confirmConfirmationButton").click()
    assert page.locator("[data-feedback-draft]").count() == 0


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
    assert page.evaluate("feedbackState.drafts.length") == 0
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
    assert page.locator("#feedbackCourse option").count() == 21


def test_malformed_storage_variants_are_safe_and_valid_drafts_survive(feedback_page):
    page = feedback_page
    page.locator('#feedbackComposeForm [type="submit"]').click()
    results = page.evaluate("""() => {
      const catalog=feedbackState.catalog, groups=feedbackGroups(), good=feedbackState.drafts[0];
      const bad=[null,undefined,[],0,true,'bad',{}, {drafts:[null]},
        {drafts:[{...good,text:null}]}, {drafts:[{...good,offset:Infinity}]},
        {drafts:[{...good,date:'2026-02-31'}]}, {drafts:[{...good,course:'missing'}]},
        {schedules:[]}, {schedules:true}, {drafts:{}},
        {drafts:[{...good,id:''}]}, {drafts:[{...good,group:'other school'}]}];
      const results=bad.map(raw=>{try {const value=feedbackRestore(raw,catalog,groups);
        return Array.isArray(value.drafts) && typeof value.schedules==='object';
      }catch{return false;}});
      for(let number=0;number<100;number++) {
        const raw={drafts:[null,{...good,date:'invalid-'+number},good]};
        const restored=feedbackRestore(raw,catalog,groups);
        results.push(restored.drafts.length===1 && restored.drafts[0].text===good.text);
      }
      return results;
    }""")
    assert all(results)


def test_autosave_uses_generated_metadata_until_message_is_regenerated(feedback_page):
    page = feedback_page
    page.locator('#feedbackComposeForm [type="submit"]').click()
    original_date = page.evaluate("feedbackState.generated.date")
    page.locator('#feedbackComposeForm [name="date"]').fill("2026-11-01")
    page.locator("#feedbackText").fill("Редакция для прежнего занятия")
    page.locator("[data-feedback-save]").click()
    assert page.evaluate("feedbackState.drafts[0].date") == original_date
    assert page.locator(".feedback-stale-note").is_visible()


def test_invalid_advanced_control_is_revealed_before_validation(feedback_page):
    page = feedback_page
    page.locator(".feedback-advanced > summary").click()
    page.locator('#feedbackComposeForm [name="offset"]').fill("1000")
    page.locator(".feedback-advanced > summary").click()
    # Explicit validation opens the collapsed container before focusing its invalid input.
    page.locator('#feedbackComposeForm [type="submit"]').click()
    assert page.locator(".feedback-advanced").evaluate("element => element.open")
