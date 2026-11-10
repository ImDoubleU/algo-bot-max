"""Refresh orchestration, failure reporting and preservation of unsaved work."""

import pytest
from test_feedback_workspace_ui import feedback_browser as _browser

from app.web.arcade_pilot import inject_pilot

feedback_browser = _browser


def test_refresh_assets_keep_their_version_with_the_pilot_enabled():
    from pathlib import Path

    source = (Path(__file__).parents[1] / "app/web/static/miniapp/index.html").read_text(
        encoding="utf-8"
    )
    injected = inject_pilot(source, [53364725])
    assert 'app-core.js?rev=0.92.7"' in injected
    assert 'app-shell.js?rev=0.92.7"' in injected


@pytest.fixture
def refresh_page(feedback_browser):
    browser, base = feedback_browser
    context = browser.new_context()
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route("https://st.max.ru/**", lambda route: route.abort())
    page.goto(base + "/miniapp?demo=1&demo_role=partner_director&view=admin",
              wait_until="networkidle")
    page.evaluate("""() => {
      window.refreshCalls = []; window.notices = [];
      showNotice = (message, tone) => notices.push({message, tone});
      for (const name of ['loadSession', 'loadCatalog', 'loadOpsSummary', 'loadBankData',
          'loadAdminStudents', 'loadTeacherInvitations', 'loadParentInvitations',
          'loadBroadcastHistory', 'loadBroadcastTargetOptions', 'loadAccrualReport',
          'pizzaLoad', 'supportLoadContext', 'supportLoadInbox', 'refreshFeedbackData',
          'loadStudentLedger', 'loadStudentBank', 'loadServerCart']) {
        window[name] = async (...args) => refreshCalls.push({name, args});
      }
      loadAuditFeed = async (kind, force) =>
        refreshCalls.push({name: 'history:' + kind, args: [force]});
      state.hasAccess = true;
      state.lastSyncAt = null;
      state.role = 'admin'; state.staffRoles = ['superadmin', 'teacher'];
      supportState.owner = true;
      apiContext.demoMode = false; apiContext.maxUserId = 53364725;
      state.availableRoles = ['admin', 'teacher', 'parent'];
      state.adminTab = 'products'; renderAdminPanel();
    }""")
    yield page
    context.close()
    assert not errors, errors


def test_refresh_all_accessible_data_and_preserve_product_draft(refresh_page):
    page = refresh_page
    page.evaluate("""() => {
      state.productEditorOpen = true; renderAdminPanel();
      auditFeed('audit').loaded = true;
      auditFeed('student:old-card').loaded = true;
    }""")
    editor_input = page.locator("#productName")
    editor_input.fill("Несохранённый товар")
    page.locator("#refreshDataButton").click()
    page.wait_for_function("!state.refreshing")
    names = page.evaluate("refreshCalls.map(x => x.name)")
    assert set(names) >= {
        "loadSession", "loadCatalog", "loadOpsSummary", "loadBankData", "loadAdminStudents",
        "loadTeacherInvitations", "loadParentInvitations", "history:actions", "history:audit",
        "loadBroadcastHistory", "loadBroadcastTargetOptions", "loadAccrualReport", "pizzaLoad",
        "supportLoadContext", "supportLoadInbox", "refreshFeedbackData",
    }
    assert names[0] == "loadSession"
    assert editor_input.input_value() == "Несохранённый товар"
    assert page.evaluate("state.lastSyncAt !== null")
    assert page.evaluate("notices.at(-1).message") == "Все данные обновлены"
    assert page.locator("#refreshDataButton").is_enabled()
    assert page.evaluate("auditFeed('student:old-card').loaded") is False


def test_partial_failure_is_not_reported_as_success(refresh_page):
    page = refresh_page
    page.evaluate("""async () => {
      loadTeacherInvitations = async () => { throw new Error('offline'); };
      supportLoadContext = async () => { throw new Error('offline'); };
      await refreshAllData();
    }""")
    assert page.evaluate("state.lastSyncAt") is None
    assert page.evaluate("state.refreshing") is False
    notice = page.evaluate("notices.at(-1)")
    assert notice["tone"] == "danger"
    assert "QR-коды" in notice["message"] and "Поддержка" in notice["message"]
    assert "loadCatalog" in page.evaluate("refreshCalls.map(x => x.name)")


def test_session_failure_stops_fanout_and_always_releases_button(refresh_page):
    page = refresh_page
    page.evaluate("""async () => {
      loadSession = async () => { state.hasAccess = false; throw new Error('offline'); };
      await refreshAllData();
    }""")
    assert page.evaluate("refreshCalls") == []
    assert page.locator("#refreshDataButton").is_enabled()
    assert page.evaluate("notices.at(-1).tone") == "danger"


def test_refresh_waits_for_inflight_load_and_ignores_double_click(refresh_page):
    page = refresh_page
    page.evaluate("""async () => {
      state.adminStudentsLoading = true;
      setTimeout(() => { state.adminStudentsLoading = false; }, 100);
      await Promise.all([refreshAllData(), refreshAllData()]);
    }""")
    names = page.evaluate("refreshCalls.map(x => x.name)")
    assert names.count("loadSession") == 1
    assert names.count("loadAdminStudents") == 1


def test_student_refresh_does_not_request_staff_data(refresh_page):
    page = refresh_page
    page.evaluate("""async () => {
      state.role = 'student'; state.availableRoles = ['student']; state.staffRoles = [];
      supportState.owner = false; state.adminTab = 'summary';
      await refreshAllData();
    }""")
    names = page.evaluate("refreshCalls.map(x => x.name)")
    assert "loadServerCart" in names
    assert not set(names) & {
        "loadAdminStudents", "loadTeacherInvitations", "loadBroadcastHistory",
        "loadAccrualReport", "history:actions", "history:audit", "supportLoadInbox",
    }


def test_feedback_refresh_is_read_only_and_keeps_draft_and_dirty_revision(feedback_browser):
    browser, base = feedback_browser
    context = browser.new_context()
    page = context.new_page()
    page.route("https://st.max.ru/**", lambda route: route.abort())
    page.goto(base + "/miniapp?demo=1&demo_role=teacher&feedback_preview=1&view=feedback",
              wait_until="networkidle")
    page.wait_for_selector("#feedbackComposeForm")
    result = page.evaluate("""async () => {
      apiContext.demoMode = false; apiContext.maxUserId = 53364725;
      state.staffRoles = ['superadmin', 'teacher'];
      students.forEach(student => { student.teacherVisible = true; student.staffVisible = true; });
      feedbackState.contextKey = feedbackContextStorageKey();
      const group = feedbackState.group, saved = structuredClone(feedbackState.schedules[group]);
      feedbackState.editorDirty = true; feedbackState.serverVersions[group] = 1;
      feedbackState.text = 'Мой исправленный текст'; feedbackState.edited = true;
      const editor = JSON.stringify(feedbackState.editor), requests = [];
      apiFetch = async (url, options) => {
        requests.push({url, method: options?.method || 'GET'});
        return new Response(JSON.stringify(String(url).includes('/catalog')
          ? feedbackState.catalog :
          {schedules: {[group]: {schedule: saved, revision: 2},
            'Индивидуальная новая': {schedule: {...saved, custom_group: true}, revision: 1}}}),
          {status: 200, headers: {'Content-Type': 'application/json'}});
      };
      await refreshFeedbackData();
      return {requests, text: feedbackState.text, revision: feedbackState.serverVersions[group],
        sameEditor: editor === JSON.stringify(feedbackState.editor),
        newGroup: Boolean(feedbackState.schedules['Индивидуальная новая'])};
    }""")
    assert len(result["requests"]) == 2
    assert all(request["method"] == "GET" for request in result["requests"])
    assert result["text"] == "Мой исправленный текст"
    assert result["revision"] == 1 and result["sameEditor"] and result["newGroup"]
    context.close()


def test_strict_loaders_report_errors_and_collections_can_recover(feedback_browser):
    browser, base = feedback_browser
    context = browser.new_context()
    page = context.new_page()
    page.route("https://st.max.ru/**", lambda route: route.abort())
    page.goto(base + "/miniapp?demo=1&demo_role=partner_director", wait_until="networkidle")
    result = page.evaluate("""async () => {
      apiContext.demoMode = false; apiContext.maxUserId = 53364725;
      apiFetch = async () => { throw new Error('network unavailable'); };
      supportState.owner = true;
      const rejected = await Promise.allSettled([supportLoadContext(true), supportLoadInbox(true),
        loadTeacherInvitations(true, true), loadAccrualReport(true)]);
      pizzaState.disabled = true;
      let called = false;
      pizzaRequest = async () => { called = true; throw new Error('network unavailable'); };
      const pizza = await Promise.allSettled([pizzaLoad(true)]);
      return {rejected: rejected.map(x => x.status), called,
        pizza: pizza[0].status, loading: pizzaState.loading};
    }""")
    assert result["rejected"] == ["rejected"] * 4
    assert result["called"] and result["pizza"] == "rejected" and not result["loading"]
    context.close()


def test_cart_refresh_does_not_upload_a_legacy_local_cart(feedback_browser):
    browser, base = feedback_browser
    context = browser.new_context()
    page = context.new_page()
    page.route("https://st.max.ru/**", lambda route: route.abort())
    page.goto(base + "/miniapp?demo=1&demo_role=student", wait_until="networkidle")
    result = page.evaluate("""async () => {
      const id = 'refresh-cart-test', requests = [];
      canUseServerCart = () => true; state.catalogLoaded = true;
      state.carts.set(id, new Map([['local-product', {quantity: 2}]]));
      apiFetch = async (url, options) => {
        requests.push(options?.method || 'GET');
        return new Response(JSON.stringify({items: []}), {status: 200});
      };
      queueCartSync = async () => { throw new Error('Refresh must not upload the cart'); };
      await loadServerCart(id, {strict: true, readOnly: true});
      return {requests, quantity: state.carts.get(id).get('local-product').quantity};
    }""")
    assert result == {"requests": ["GET"], "quantity": 2}
    context.close()
