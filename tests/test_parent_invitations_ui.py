# ruff: noqa: F811
import pytest

from tests.test_binding_ui import binding_browser  # noqa: F401


@pytest.mark.parametrize("width", [320, 390, 1440])
def test_parent_link_dialog_copies_correct_parent_and_keeps_child_qr_separate(
    binding_browser, width,
):
    browser, base = binding_browser
    page = browser.new_page(viewport={"width": width, "height": 900})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route("https://st.max.ru/**", lambda route: route.abort())
    page.goto(base + "/miniapp?demo=1&demo_role=admin", wait_until="networkidle")
    pupil = page.evaluate("""async () => {
      state.role = 'admin'; state.staffRoles = ['superadmin']; state.dashboardMode = 'qr';
      await loadTeacherInvitations();
      const pupil = studentsForStudentQrCapabilities()[1];
      const data = state.teacherInvitations.get(pupil.id).data;
      data.demo = false;
      data.bot_url = 'https://example.invalid/student/child';
      data.parent_invitations = [
        {parent_name: 'Иванова Мария', bot_url: 'https://example.invalid/parent/mother'},
        {parent_name: 'Иванов Сергей', bot_url: 'https://example.invalid/parent/father'}
      ];
      window.copiedParentLinks = [];
      Object.defineProperty(navigator, 'clipboard', {configurable: true,
        value: {writeText: async value => { copiedParentLinks.push(value); }}});
      setView('dashboard'); renderTeacherInvitations();
      return {id:pupil.id,name:pupil.name};
    }""")
    trigger = page.locator(f'[data-open-parent-invitation="{pupil["id"]}"]')
    assert trigger.is_visible()
    trigger.click()
    dialog = page.locator("#parentInvitationDialog")
    assert dialog.is_visible() and page.locator("#studentQrDialog").is_hidden()
    assert page.locator("#parentInvitationDialogTitle").inner_text() == pupil["name"]
    assert dialog.locator(".parent-invitation-item").count() == 2
    assert dialog.locator("input").nth(0).input_value() == "https://example.invalid/parent/mother"
    assert dialog.locator("input").nth(1).input_value() == "https://example.invalid/parent/father"
    dialog.locator('[data-parent-invitation-index="1"]').click()
    page.wait_for_function("copiedParentLinks.length === 1")
    assert page.evaluate("copiedParentLinks") == ["https://example.invalid/parent/father"]
    page.locator("#closeParentInvitationDialogButton").focus()
    page.keyboard.press("Shift+Tab")
    assert dialog.locator('[data-parent-invitation-index="1"]').evaluate(
        "element => element === document.activeElement"
    )
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert dialog.locator(".parent-invitation-dialog").evaluate(
        "element => element.scrollWidth <= element.clientWidth"
    )
    page.keyboard.press("Escape")
    assert dialog.is_hidden() and not dialog.locator("input").count()
    assert trigger.evaluate("element => element === document.activeElement")
    page.locator(f'[data-open-student-qr="{pupil["id"]}"]').last.click()
    assert page.locator("#studentQrDialog").is_visible() and dialog.is_hidden()
    copy_student = page.locator("#copyStudentQrLinkButton")
    assert copy_student.get_attribute("data-copy-student-link") == pupil["id"]
    page.keyboard.press("Escape")
    page.evaluate("""id => {
      state.teacherInvitations.get(id).data.parent_invitations = [];
      renderTeacherInvitations();
    }""", pupil["id"])
    trigger.click()
    assert "Контакт родителя ещё не загружен" in dialog.inner_text()
    assert not dialog.locator("[data-copy-parent-link]").count()
    page.locator("#closeParentInvitationDialogButton").click()
    assert not page.locator('.teacher-qr-card.is-connected [data-open-parent-invitation]').count()
    assert not errors, errors
    page.close()
