import pytest
from test_feedback_workspace_ui import feedback_browser as _browser

feedback_browser = _browser


@pytest.mark.parametrize("width", [320, 390, 768, 1440])
def test_connection_export_filters_summary_download_and_alignment(feedback_browser, width):
    browser, base = feedback_browser
    context = browser.new_context(viewport={"width": width, "height": 1000})
    page = context.new_page()
    errors, exports = [], []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route("https://st.max.ru/**", lambda route: route.abort())

    def export(route):
        exports.append(route.request.post_data_json)
        route.fulfill(status=200, body=b"PK-local-xlsx-test",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    page.route("**/api/v1/miniapp/access-links/export", export)
    page.goto(base + "/miniapp?demo=1&demo_role=admin&view=admin", wait_until="networkidle")
    page.evaluate("""() => {
      state.adminTab = 'contacts';
      students = [
        {id: 'first', name: 'Первый ученик', group: 'Python', teacher: 'Первый педагог',
          venue: 'Центр', status: 'active'},
        {id: 'second', name: 'Второй ученик', group: 'Scratch', teacher: 'Второй педагог',
          venue: 'Филиал', status: 'active'},
        {id: 'third', name: 'Третий ученик', group: 'Python', teacher: 'Первый педагог',
          venue: 'Центр', status: 'active'},
      ];
      accessLinks = [
        {id:'demo-first', studentId:'first', studentName:'Первый ученик', group:'Python',
          role:'parent', status:'active', maxUserId:'777'},
        {id:'demo-second', studentId:'second', studentName:'Второй ученик', group:'Scratch',
          role:'student', status:'active', maxUserId:'778'},
      ];
      renderAdminPanel();
    }""")
    if width > 700:
        for index in [0, 1]:
            positions = page.locator(".access-child-statuses").evaluate_all(
                "(rows, i) => rows.map(r => r.children[i].getBoundingClientRect().left)", index,
            )
            assert max(positions) - min(positions) < 1
    page.locator("[data-open-connection-export]").click()
    assert page.locator("#connectionExportDialog").is_visible()
    assert page.locator("#connectionExportCount").inner_text() == "Учеников в файле: 3"
    assert page.locator(".connection-export-totals strong").all_text_contents() == [
        "3", "1 / 3", "1 / 3",
    ]
    page.locator('[data-connection-export-select="teachers"][data-select-mode="none"]').click()
    assert page.locator("[data-download-connection-export]").is_disabled()
    page.locator('[data-connection-export-key="teachers"][value="Первый педагог"]').check()
    assert page.locator("#connectionExportCount").inner_text() == "Учеников в файле: 2"
    page.locator('[data-connection-export-search="groups"]').fill("Python")
    assert page.locator('[data-connection-export-list="groups"] input').count() == 1
    page.locator('[data-connection-export-key="groups"]').uncheck()
    assert page.locator("[data-download-connection-export]").is_disabled()
    page.locator('[data-connection-export-key="groups"]').check()
    with page.expect_download() as received:
        page.locator("[data-download-connection-export]").click()
    assert received.value.suggested_filename == "algo-max-connections.xlsx"
    assert exports[0]["teachers"] == ["Первый педагог"]
    assert set(exports[0]["venues"]) == {"Центр", "Филиал"}
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.keyboard.press("Escape")
    assert page.locator("#connectionExportDialog").is_hidden()
    assert page.locator("[data-open-connection-export]").evaluate(
        "e => e === document.activeElement",
    )
    assert not errors, errors
    context.close()
