# ruff: noqa: F811
import pytest

from tests.test_binding_ui import binding_browser  # noqa: F401


def test_superadmin_audit_and_mobile_cards(binding_browser):
    browser, base = binding_browser
    page = browser.new_page(viewport={"width": 390, "height": 850})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route("https://st.max.ru/**", lambda route: route.abort())
    page.goto(base + "/miniapp?demo=1", wait_until="networkidle")
    result = page.evaluate("""() => {
      apiContext.demoMode = false; state.role = 'admin';
      state.staffRoles = ['superadmin']; state.hasAccess = true;
      state.adminTab = 'audit';
      auditFeed('audit').rows = [normalizeAdminHistoryEntry({
        id: 'event1', action: 'contact_access_link.failed', title: 'Родитель не смог подключиться',
        category: 'Привязки', status: 'denied', actor_name: '<img src=x onerror=alert(1)>',
        actor_max_user_id: 12345, created_at: '2026-10-07T10:30:00Z', request_id: 'request1',
        payload: {reason: 'parent_required', student_name: 'Ученик', source: 'teacher_qr'}
      })];
      auditFeed('audit').total = 215; auditFeed('audit').more = true;
      renderAdminPanel(); document.querySelector('#adminView').hidden = false;
      const auditTab = document.querySelector('[data-admin-tab="audit"]');
      return {enabled: fullAuditEnabled(), visible: !auditTab.hidden,
        cards: document.querySelectorAll('.audit-event').length,
        escaped: !document.querySelector('.audit-event img'),
        more: !!document.querySelector('[data-audit-more]'),
        time: document.querySelector('.audit-event time').textContent};
    }""")
    assert result == {
        "enabled": True,
        "visible": True,
        "cards": 1,
        "escaped": True,
        "more": True,
        "time": "13:30:00",
    }
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert not errors, errors
    page.evaluate("state.staffRoles = ['admin']; state.adminTab = 'audit'; renderAdminPanel()")
    assert page.evaluate("state.adminTab") == "history"
    assert page.locator('[data-admin-tab="audit"]').is_hidden()
    assert page.locator(".audit-details").count() == 0
    page.close()


def test_student_context_is_compact_and_opens_profile(binding_browser):
    browser, base = binding_browser
    page = browser.new_page(viewport={"width": 390, "height": 850})
    page.route("https://st.max.ru/**", lambda route: route.abort())
    page.goto(base + "/miniapp?demo=1", wait_until="networkidle")
    page.evaluate("""() => {
      state.role = 'admin'; state.adminTab = 'history'; state.staffRoles = ['admin'];
      auditFeed('actions').rows = [normalizeAdminHistoryEntry({id: 'event',
        title: 'Ученик подключился', actor_name: 'Иванов Иван', actor_max_user_id: 123,
        created_at: '2026-10-07T10:00:00Z', tenant_slug: apiContext.tenantSlug,
        payload: {actor_role: 'student', students: [{id: 'student-id', name: 'Иванов Иван',
          group: 'Python, суббота 12:00', teacher: 'Олейник Дмитрий', lms_id: 'ST-1',
          accounts: [{role: 'parent', name: 'Иванова Мария', max_user_id: 456}]}]}})];
      renderAdminPanel();
      openAdminStudentProfile = async (id) => { window.openedStudent = id; };
      document.querySelector('[data-audit-student]').click();
    }""")
    assert page.evaluate("window.openedStudent") == "student-id"
    assert "MAX ID 456" in page.locator(".audit-people").inner_text()
    assert page.locator(".audit-people").inner_text().count("Иванов Иван") == 1
    assert (
        page.evaluate("getComputedStyle(document.querySelector('.audit-filter-extra')).display")
        == "none"
    )
    page.evaluate("document.querySelector('[data-audit-toggle]').click()")
    assert (
        page.evaluate("getComputedStyle(document.querySelector('.audit-filter-extra')).display")
        == "grid"
    )
    assert (
        page.evaluate("parseInt(getComputedStyle(document.querySelector('.audit-panel')).padding)")
        > 0
    )
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.close()


def test_audit_pagination_uses_snapshot_and_keeps_all_pages(binding_browser):
    browser, base = binding_browser
    page = browser.new_page()
    page.route("https://st.max.ru/**", lambda route: route.abort())
    page.goto(base + "/miniapp?demo=1", wait_until="networkidle")
    result = page.evaluate("""async () => {
      apiContext.demoMode = false; apiContext.maxUserId = 1; state.hasAccess = true;
      state.role = 'admin'; state.staffRoles = ['superadmin']; state.adminTab = 'audit';
      resetAuditFeeds(); const calls = [];
      apiFetch = async (url) => {
        const parsed = new URL(url, location.href);
        calls.push(Object.fromEntries(parsed.searchParams));
        const offset = Number(parsed.searchParams.get('offset'));
        return new Response(JSON.stringify({total: 3, has_more: offset === 0,
          snapshot_at: '2026-10-07T10:00:00Z',
          entries: (offset ? ['c'] : ['a', 'b']).map(id => ({id, title: 'Событие',
            created_at: '2026-10-07T09:00:00Z', payload: {}}))}), {status: 200});
      };
      await loadAuditFeed('audit', true); await loadAuditFeed('audit');
      return {count: auditFeed('audit').rows.length, more: auditFeed('audit').more,
        secondOffset: calls[1].offset, snapshot: calls[1].snapshot_at,
        fullScope: calls[0].all_tenants};
    }""")
    assert result == {
        "count": 3,
        "more": False,
        "secondOffset": "2",
        "snapshot": "2026-10-07T10:00:00Z",
        "fullScope": "true",
    }
    page.close()


@pytest.mark.parametrize("width", [320, 390, 1440])
@pytest.mark.parametrize("action", [
    "miniapp_astrocoins.accrued", "miniapp_astrocoins.undone", "astrocoins.birthday_rewarded",
])
def test_coin_history_shows_author_and_only_pupils_with_two_id_columns(
    binding_browser, width, action,
):
    browser, base = binding_browser
    page = browser.new_page(viewport={"width": width, "height": 950})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route("https://st.max.ru/**", lambda route: route.abort())
    page.goto(base + "/miniapp?demo=1", wait_until="networkidle")
    page.evaluate("""action => {
      state.role = 'admin'; state.adminTab = 'history'; state.staffRoles = ['admin'];
      auditFeed('actions').rows = [normalizeAdminHistoryEntry({id: 'coin-event', action,
        title: 'Астрокоины начислены', actor_name: 'Победов Никита', actor_max_user_id: 100,
        tenant_slug: apiContext.tenantSlug, created_at: '2026-10-07T10:00:00Z',
        payload: {actor_role: 'teacher', amount: 50, total_astrocoins: 150, students: [
          {id: 'child-one', name: 'Иванов Александр', lms_id: 'ST-001', group: 'Python',
            teacher: 'Другой преподаватель', teacher_max_user_id: 987,
            accounts: [{role: 'student', max_user_id: 111},
              {role: 'student', max_user_id: 111},
              {role: 'student', max_user_id: 333, status: 'revoked'},
              {role: 'parent', max_user_id: 222, name: 'Иванова Мария'}]},
          {id: 'child-two', name: 'Петров Дмитрий', lms_id: 'ST-002', group: 'Python',
            accounts: [{role: 'parent', max_user_id: 222, name: 'Иванова Мария'}]},
          {id: 'child-three', name: '<img src=x onerror=alert(1)>', accounts: []},
        ]}})];
      renderAdminPanel(); setView('admin');
      openAdminStudentProfile = async (id) => { window.openedStudent = id; };
    }""", action)
    event = page.locator(".audit-event")
    author = event.locator(".audit-accrual-author")
    assert author.is_visible()
    assert author.inner_text().count("Победов Никита") == 1
    assert "MAX ID 100" in author.inner_text()
    if action.endswith("undone"):
        assert "Отменил" in author.inner_text()
    table = event.locator(".audit-accrual-table")
    assert table.locator("thead th").all_text_contents() == ["Ученик", "MAX ID", "LMS ID"]
    rows = table.locator("tbody tr")
    assert rows.count() == 3
    assert rows.nth(0).locator("td").all_text_contents() == ["111", "ST-001"]
    assert rows.nth(1).locator("td").all_text_contents() == ["—", "ST-002"]
    assert rows.nth(2).locator("td").all_text_contents() == ["—", "—"]
    text = event.inner_text()
    assert "Иванова Мария" not in text and "222" not in text and "333" not in text
    assert "Другой преподаватель" not in text
    assert not event.locator("img").count()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    table.locator('[data-audit-student="child-two"]').click()
    assert page.evaluate("window.openedStudent") == "child-two"
    if action.endswith("accrued") and width in (390, 1440):
        event.scroll_into_view_if_needed()
        page.screenshot(path=f".deploy_tmp/coin-history-{width}.png")
    assert not errors, errors
    page.close()
