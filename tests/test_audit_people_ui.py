# ruff: noqa: F811
import pytest

from tests.test_binding_ui import binding_browser  # noqa: F401


@pytest.mark.parametrize(
    "actor_role,actor_id,actor_name",
    [
        ("student", 177, "Орлов Денис"),
        ("parent", 45, "Орлова Елена"),
    ],
)
def test_binding_people_and_ids_appear_once(binding_browser, actor_role, actor_id, actor_name):
    browser, base = binding_browser
    page = browser.new_page(viewport={"width": 390, "height": 850})
    page.route("https://st.max.ru/**", lambda route: route.abort())
    page.goto(base + "/miniapp?demo=1", wait_until="networkidle")
    result = page.evaluate(
        """({role, id, name}) => {
      state.role = 'admin'; state.adminTab = 'history';
      const student = {id: 'student-1', name: 'Орлов Денис', lms_id: 'ST-1',
        crm_id: 'CRM-1', group: 'Python, сб 18:00', teacher: 'Стрежнев Александр',
        teacher_max_user_id: 418,
        accounts: [{role: 'student', name: 'Орлов Денис', max_user_id: 177},
          {role: 'parent', name: 'Орлова Елена', max_user_id: 45}]};
      auditFeed('actions').rows = [normalizeAdminHistoryEntry({id: 'event-1',
        action: role === 'student' ? 'student_qr_access_link.created'
          : 'contact_access_links.created',
        status: 'success', actor_name: name, actor_max_user_id: id,
        created_at: '2026-10-07T10:30:00Z',
        payload: {actor_role: role, created: true, created_links: 1,
          source: 'parent_qr', students: [student]}})];
      renderAdminPanel();
      const card = document.querySelector('.audit-event');
      return {detailsOpen: card.querySelector('details').open,
        people: card.querySelector('.audit-people').innerText,
        actorCount: card.querySelectorAll('[data-audit-actor]').length,
        links: card.querySelectorAll('[data-audit-student]').length,
        context: card.querySelector('.audit-context').innerText,
        ids: card.querySelectorAll('.audit-person-ids code').length,
        overflow: document.documentElement.scrollWidth > innerWidth};
    }""",
        {"role": actor_role, "id": actor_id, "name": actor_name},
    )
    assert result["people"].count("Орлов Денис") == 1
    assert result["people"].count("Орлова Елена") == 1
    assert result["people"].count("MAX ID 177") == 1
    assert result["people"].count("MAX ID 45") == 1
    assert result["people"].count("LMS ID ST-1") == 1
    assert result["context"].count("Стрежнев Александр") == 1
    assert result["actorCount"] == result["links"] == 1
    assert not result["overflow"]
    assert not result["detailsOpen"]
    page.close()


def test_same_parent_of_two_students_is_shown_once(binding_browser):
    browser, base = binding_browser
    page = browser.new_page()
    page.route("https://st.max.ru/**", lambda route: route.abort())
    page.goto(base + "/miniapp?demo=1", wait_until="networkidle")
    model = page.evaluate("""() => auditPeople({actorName: 'Администратор', actorMaxUserId: 1,
      payload: {actor_role: 'admin', students: ['a', 'b'].map((id) => ({id, name: id,
        group: 'Python', teacher: 'Преподаватель', accounts: [
          {role: 'parent', name: 'Мама', max_user_id: 45},
          {role: 'parent', name: 'Мама', max_user_id: 45}]}))}})""")
    assert len(model["people"]) == 4
    assert sum(45 in person["ids"] for person in model["people"]) == 1
    assert len(model["contexts"]) == 1
    page.close()


def test_rebound_student_keeps_event_and_current_ids_in_one_person(binding_browser):
    browser, base = binding_browser
    page = browser.new_page()
    page.route("https://st.max.ru/**", lambda route: route.abort())
    page.goto(base + "/miniapp?demo=1", wait_until="networkidle")
    model = page.evaluate("""() => auditPeople({actorName: 'Ученик', actorMaxUserId: 10,
      payload: {actor_role: 'student', students: [{id: 'student', name: 'Ученик',
        accounts: [{role: 'student', max_user_id: 20}]}]}})""")
    assert len(model["people"]) == 1
    assert [str(value) for value in model["people"][0]["ids"]] == ["10", "20"]
    assert [str(value) for value in model["people"][0]["currentIds"]] == ["20"]
    page.close()
