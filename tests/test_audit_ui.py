# ruff: noqa: F811
import pytest

from tests.test_binding_ui import binding_browser  # noqa: F401


@pytest.mark.parametrize("width", [320, 390, 1440])
def test_general_history_global_scope_is_visible_and_superadmin_only(binding_browser, width):
    browser, base = binding_browser
    page = browser.new_page(viewport={"width": width, "height": 950})
    page.route("https://st.max.ru/**", lambda route: route.abort())
    page.goto(base + "/miniapp?demo=1", wait_until="networkidle")
    page.evaluate("""async () => {
      apiContext.demoMode = false; apiContext.maxUserId = 1; state.hasAccess = true;
      state.role = 'admin'; state.staffRoles = ['superadmin']; state.adminTab = 'history';
      resetAuditFeeds(); window.historyScopeCalls = [];
      apiFetch = async url => {
        const params = Object.fromEntries(new URL(url, location.href).searchParams);
        window.historyScopeCalls.push(params);
        return new Response(JSON.stringify({total: 1, has_more: false, entries: [{
          id: 'connection', action: 'student_qr_access_link.created', title: 'Ученик подключился',
          tenant_name: 'Бор', tenant_slug: 'bor', created_at: '2026-10-10T06:40:00Z',
          payload: {binding_subject: {confirmed: true}}
        }]}), {status: 200});
      };
      setView('admin'); await loadAuditFeed('actions', true);
    }""")
    scope = page.locator('.audit-school-scope select')
    assert scope.is_visible() and scope.input_value() == "true"
    assert page.evaluate("historyScopeCalls[0].all_tenants") == "true"
    assert "Бор" in page.locator('.audit-tags').inner_text()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    scope.select_option("false")
    page.wait_for_function("historyScopeCalls.length === 2 && !auditFeed('actions').loading")
    assert page.evaluate("historyScopeCalls[1].all_tenants || null") is None
    assert scope.input_value() == "false"
    assert "Бор" not in page.locator('.audit-tags').inner_text()
    result = page.evaluate("""async () => {
      state.staffRoles = ['admin']; resetAuditFeeds();
      const defaultScope = auditFeed('actions').filters.allTenants;
      auditFeed('actions').filters.allTenants = true;
      await loadAuditFeed('actions', true);
      const adminScope = historyScopeCalls.at(-1).all_tenants || null;
      const adminControl = !!document.querySelector('.audit-school-scope');
      state.staffRoles = ['superadmin'];
      await loadAuditFeed('student:pupil', true);
      return {defaultScope, adminScope, adminControl,
        studentScope: historyScopeCalls.at(-1).all_tenants || null};
    }""")
    assert result == {"defaultScope": False, "adminScope": None, "adminControl": False,
                      "studentScope": None}
    page.close()


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
    page.wait_for_function("typeof state !== 'undefined' && typeof renderAdminPanel === 'function'")
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


def test_audit_groups_preserve_identity_time_boundaries_and_every_event(binding_browser):
    browser, base = binding_browser
    page = browser.new_page()
    page.route("https://st.max.ru/**", lambda route: route.abort())
    page.goto(base + "/miniapp?demo=1", wait_until="networkidle")
    result = page.evaluate("""() => {
      const event = (id, actor, at) => normalizeAdminHistoryEntry({id,
        actor_name: 'Одинаковое имя', actor_max_user_id: actor, created_at: at});
      const rows = [event('a', 1, '2026-10-07T10:10:00Z'),
        event('other', 2, '2026-10-07T10:09:00Z'),
        event('b', 1, '2026-10-07T10:08:00Z'),
        event('edge', 1, '2026-10-07T10:05:00Z'),
        event('outside', 1, '2026-10-07T10:04:59Z'),
        event('unknown1', null, '2026-10-07T10:04:00Z'),
        event('unknown2', null, '2026-10-07T10:03:59Z'),
        event('afterMidnight', 3, '2026-10-06T21:00:01Z'),
        event('beforeMidnight', 3, '2026-10-06T20:59:59Z')];
      const groups = auditGroups([...rows].reverse(), 5);
      return {groups: groups.map(group => group.rows.map(entry => entry.id)),
        span: groups[0].newest - groups[0].oldest,
        count: groups.flatMap(group => group.rows).length,
        longer: auditGroups(rows, 15)[0].rows.length};
    }""")
    assert result == {
        "groups": [["a", "b", "edge"], ["other"], ["outside"], ["unknown1"],
                   ["unknown2"], ["afterMidnight"], ["beforeMidnight"]],
        "span": 300000, "count": 9, "longer": 4,
    }
    page.close()


@pytest.mark.parametrize("width", [320, 390, 1440])
def test_grouped_audit_keeps_errors_details_and_open_state_without_grouping_history(
    binding_browser, width,
):
    browser, base = binding_browser
    page = browser.new_page(viewport={"width": width, "height": 1000})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route("https://st.max.ru/**", lambda route: route.abort())
    page.goto(base + "/miniapp?demo=1", wait_until="networkidle")
    page.wait_for_function("typeof state !== 'undefined' && typeof renderAdminPanel === 'function'")
    page.evaluate("""() => {
      state.role = 'admin'; state.adminTab = 'audit'; state.staffRoles = ['superadmin'];
      const event = (id, actor, at, status = 'success') => normalizeAdminHistoryEntry({
        id, actor_name: actor === 100 ? 'Победов Никита' : 'Другой пользователь',
        actor_max_user_id: actor, created_at: '2026-10-07T' + at + 'Z', status,
        action: 'miniapp_astrocoins.accrued', title: 'Астрокоины начислены',
        tenant_slug: apiContext.tenantSlug, request_id: 'request-' + id,
        payload: {actor_role: 'teacher', students: [{id: 'child-' + id, name: 'Ученик ' + id,
          lms_id: 'ST-' + id, accounts: [{role: 'parent', max_user_id: 300}]}]}});
      const rows = [event('a', 100, '10:10:00'), event('other', 200, '10:09:00'),
        event('b', 100, '10:08:00', 'denied'), event('c', 100, '10:06:00'),
        event('old', 100, '10:04:00')];
      auditFeed('audit').rows = rows; auditFeed('audit').total = rows.length;
      auditFeed('actions').rows = rows; auditFeed('actions').total = rows.length;
      renderAdminPanel(); setView('admin');
    }""")
    group = page.locator(".audit-session")
    assert group.count() == 1
    assert "Требуют внимания: 1" in group.locator(".audit-session-summary").inner_text()
    assert group.locator(".audit-session-summary").inner_text().count("Победов Никита") == 1
    assert group.locator(".audit-session-summary").inner_text().count("MAX ID 100") == 1
    assert group.locator(".audit-session-events").is_hidden()
    group.locator(".audit-session-summary").click()
    assert group.locator(".audit-event").count() == 3
    assert "Победов Никита" not in group.locator(".audit-session-events").inner_text()
    assert group.locator(".audit-event.is-denied").is_visible()
    group.locator(".audit-details summary").first.click()
    assert "request-c" in group.locator(".audit-detail-content").first.inner_text()
    page.wait_for_function("auditFeed('audit').openGroups.has('a')")
    page.evaluate("renderAuditCurrent('audit')")
    assert page.locator('.audit-session[open]').count() == 1
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    if width in (390, 1440):
        page.screenshot(path=f".deploy_tmp/audit-grouped-{width}.png")
    page.locator("[data-audit-group-minutes]").select_option("15")
    assert page.locator(".audit-session").first.locator(".audit-event").count() == 4
    page.locator('[data-admin-tab="history"]').click()
    assert page.locator(".audit-session").count() == 0
    assert page.locator(".audit-event").count() == 5
    assert page.locator("[data-audit-group-minutes]").count() == 0
    assert not errors, errors
    page.close()
