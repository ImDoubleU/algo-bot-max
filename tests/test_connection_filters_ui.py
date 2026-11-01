import pytest
from test_feedback_workspace_ui import feedback_browser as _browser

feedback_browser = _browser


@pytest.mark.parametrize("width", [320, 390, 768, 1440])
def test_missing_connection_filters_include_students_without_any_links(
    feedback_browser, width, tmp_path,
):
    browser, base = feedback_browser
    context = browser.new_context(viewport={"width": width, "height": 1000})
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route("https://st.max.ru/**", lambda route: route.abort())
    try:
        page.goto(base + "/miniapp?demo=1&demo_role=admin&view=admin", wait_until="networkidle")
        page.evaluate("""() => {
          state.adminTab = 'contacts';
          students = ['both', 'parent', 'student', 'none', 'revoked', 'multiple']
            .map((id, index) => ({id, name: `Ученик ${index}`, group: 'Python',
              lmsId: `LMS-${id}`, staffVisible: true, status: 'active'}));
          const link = (studentId, role, status = 'active') => ({
            id: `${studentId}-${role}-${status}`, studentId, role, status,
            studentName: students.find(s => s.id === studentId).name,
            group: 'Python', maxUserId: `${studentId}-${role}`, displayName: '', username: '',
          });
          accessLinks = [link('both', 'parent'), link('both', 'student'),
            link('parent', 'parent'), link('student', 'student'),
            link('revoked', 'parent', 'revoked'),
            link('multiple', 'parent', 'revoked'), link('multiple', 'parent')];
          renderAdminPanel();
        }""")

        def ids():
            return set(page.locator("[data-access-child]").evaluate_all(
                "rows => rows.map(row => row.dataset.accessChild)",
            ))

        assert page.locator("#accessStatusFilter").count() == 0
        assert page.locator("#accessRoleFilter").count() == 0
        assert ids() == {"both", "parent", "student", "none", "revoked", "multiple"}
        page.locator('[data-access-connection-filter="parent"]').click()
        assert ids() == {"student", "none", "revoked"}
        assert page.locator('[data-access-connection-filter="parent"]').get_attribute(
            "aria-pressed"
        ) == "true"
        page.locator('[data-access-child="none"] > summary').click()
        assert page.locator('[data-access-child="none"] .empty-state').inner_text() == (
            "Подключений пока нет"
        )
        page.locator('[data-access-connection-filter="student"]').click()
        assert ids() == {"parent", "none", "revoked", "multiple"}
        assert page.locator('[data-access-child="none"]').evaluate("row => row.open")
        page.screenshot(path=str(tmp_path / f"connections-filter-{width}.png"), full_page=True)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.locator("#adminEntitySearch").fill("LMS-none")
        page.wait_for_function("document.querySelectorAll('[data-access-child]').length === 1")
        assert ids() == {"none"}
        page.locator("#adminEntitySearch").fill("Несуществующий")
        page.wait_for_function("document.querySelectorAll('[data-access-child]').length === 0")
        assert not ids()
        page.locator("#adminPanel .empty-state [data-clear-admin-search]").click()
        assert len(ids()) == 6
        assert page.evaluate("state.accessConnectionFilter") == "all"
        # Session may include family-linked pupils outside the employee's scope.
        page.evaluate("""() => {
          apiContext.demoMode = false;
          students.push({id: 'foreign', name: 'Чужой ученик', staffVisible: false});
          renderAdminPanel();
        }""")
        assert "foreign" not in ids()
        assert not errors, errors
    finally:
        context.close()
