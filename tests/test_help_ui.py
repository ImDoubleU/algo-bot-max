"""Help regressions use a local static fixture, never production or real MAX links."""

import json
import re
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

import pytest
from PIL import Image, ImageChops
from test_feedback_workspace_ui import feedback_browser as _browser
from test_help_media_coverage import (
    BOT_SUPPORT_QUESTION,
    assert_bot_support_step_order,
    mp4_duration,
)

feedback_browser = _browser
ASSETS = Path(__file__).parents[1] / "app/web/static/miniapp/assets/help/guides"
FAMILY = ("parent", "student")
STAFF = ("teacher", "curator", "admin", "partner_director", "superadmin")
PARENT_QUESTION = "Как родителю подключить ребёнка?"
SAVE_QUESTION = "Почему в окне не видно кнопку сохранения?"
SHARED_QUESTION = "Как открыть приложение?"
STAFF_QUESTION = "Как добавить физический товар?"


@pytest.fixture
def help_session(feedback_browser):
    browser, base = feedback_browser
    context = browser.new_context(viewport={"width": 1440, "height": 1000}, reduced_motion="reduce")
    page = context.new_page()
    page.set_default_timeout(10_000)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    # All tests remain offline, including SDK, invitation and support traffic.
    context.route(
        "**/*",
        lambda route: (
            route.continue_()
            if urlsplit(route.request.url).netloc == urlsplit(base).netloc
            else route.abort()
        ),
    )
    try:
        yield page, base
    finally:
        context.close()
        assert not errors, errors


@pytest.fixture
def runtime_media_session(help_session):
    """Network fixtures exercise runtime, never substitute for real catalog acceptance."""
    page, base = help_session
    catalog = {}
    for question, stem in ((SHARED_QUESTION, "parent"), (STAFF_QUESTION, "connections")):
        duration = mp4_duration(ASSETS / f"{stem}.mp4")
        catalog[question] = {
            "id": stem,
            "title": question,
            "duration": duration,
            "steps": [
                [0, "Start", "First demo scene"],
                [duration / 2, "Next", "Second demo scene"],
            ],
        }
    guides = [
        {
            "id": "family",
            "label": "Family",
            "icon": "circle-help",
            "audiences": ["parent", "student"],
            "question": SHARED_QUESTION,
        },
        # A broad guide audience must never override the linked FAQ's staff scope.
        {
            "id": "staff",
            "label": "Staff",
            "icon": "settings",
            "audiences": ["parent", "student", "staff"],
            "question": STAFF_QUESTION,
        },
    ]
    script = (
        f"const HELP_MEDIA_CATALOG = {json.dumps(catalog)};\n"
        f"const HELP_TOP_GUIDES = {json.dumps(guides)};"
    )
    page.route(
        "**/app-help-media-catalog.js*",
        lambda route: route.fulfill(
            status=200,
            content_type="application/javascript",
            body=script,
        ),
    )
    install_video_ranges(page)
    return page, base


def open_help(page, base, role="parent"):
    demo_role = role if role in (*FAMILY, "teacher", "admin") else "admin"
    page.goto(
        base + f"/miniapp?demo=1&demo_role={demo_role}&view=help",
        wait_until="networkidle",
    )
    if role in STAFF:
        page.evaluate(
            """role => {
              state.staffRoles = [role];
              setRole(role === 'teacher' ? 'teacher' : 'admin');
              setView('help');
            }""",
            role,
        )
    page.locator("details.help-faq-item").first.wait_for()


def contract(page):
    return page.evaluate(
        """() => ({items: HELP_FAQ_ITEMS, catalog: HELP_MEDIA_CATALOG,
                     guides: HELP_TOP_GUIDES})"""
    )


def faq_contract(page):
    return page.evaluate("() => ({items: HELP_FAQ_ITEMS})")


def questions(page):
    return page.locator("details.help-faq-item").evaluate_all(
        "items => items.map(item => item.dataset.helpQuestion)"
    )


def faq(page, question):
    return page.locator("details.help-faq-item").filter(has=page.get_by_text(question, exact=True))


def allowed(item, role):
    return role in STAFF or role in item["audiences"]


def visible_guides(data, role):
    items = {item["question"]: item for item in data["items"]}
    return [
        guide
        for guide in data["guides"]
        if guide["question"] in data["catalog"]
        and guide["question"] in items
        and allowed(guide, role)
        and allowed(items[guide["question"]], role)
    ]


def requires_action_ending(item):
    read_only = item.get("video") is False and not item.get("steps")
    return bool(
        item.get("video")
        or item.get("steps")
        or (item["category"] == "problems" and not read_only)
        or item["question"] == SAVE_QUESTION
    )


def install_video_ranges(page):
    def video_range(route):
        name = Path(unquote(urlsplit(route.request.url).path)).name
        target = ASSETS / name
        assert target.is_file(), f"Missing help video: {name}"
        data = target.read_bytes()
        requested = route.request.headers.get("range")
        headers = {"Accept-Ranges": "bytes", "Content-Type": "video/mp4"}
        start, end = 0, len(data) - 1
        if requested:
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", requested)
            assert match and any(match.groups()), requested
            lower, upper = match.groups()
            if lower:
                start = int(lower)
                end = min(int(upper), end) if upper else end
            else:
                start = max(0, len(data) - int(upper))
            if start > end or start >= len(data):
                route.fulfill(status=416, headers={"Content-Range": f"bytes */{len(data)}"})
                return
            headers["Content-Range"] = f"bytes {start}-{end}/{len(data)}"
        body = data[start : end + 1]
        headers["Content-Length"] = str(len(body))
        route.fulfill(status=206 if requested else 200, body=body, headers=headers)

    # SimpleHTTPRequestHandler does not implement the native MP4 seek contract.
    page.route("**/assets/help/guides/*.mp4*", video_range)


def assert_loaded_video(video, clip):
    assert video.get_attribute("controls") is not None
    assert video.get_attribute("playsinline") is not None
    assert video.get_attribute("preload") == "none"
    assert video.get_attribute("autoplay") is None
    base = f"/miniapp/static/assets/help/guides/{clip['id']}"
    poster = video.get_attribute("poster")
    assert poster and urlsplit(poster).path == f"{base}.png"
    assert video.locator('track[kind="captions"][srclang="ru"]').count() == 1
    captions = video.locator("track").get_attribute("src")
    assert captions and urlsplit(captions).path == f"{base}.vtt"
    urls = video.evaluate(
        "v => [v.getAttribute('src'), ...[...v.querySelectorAll('source')].map(s => s.src)]"
    )
    sources = [url for url in urls if url and urlsplit(url).path == f"{base}.mp4"]
    assert sources
    for url in [poster, captions, *sources]:
        assert parse_qs(urlsplit(url).query).get("v") == ["0.91.66"], url


def test_media_markup_has_versioned_paths_without_a_catalog(help_session):
    page, base = help_session
    open_help(page, base)
    page.evaluate(
        """() => {
          document.querySelector('#helpGuides').innerHTML =
            helpMediaMarkup({id: 'parent', title: 'Demo'}, 'Demo question');
        }"""
    )
    assert_loaded_video(page.locator("#helpGuides video"), {"id": "parent"})


def test_runtime_stale_source_error_does_not_mark_new_guide_failed(runtime_media_session):
    page, base = runtime_media_session
    open_help(page, base, "admin")
    page.locator("#helpGuideSelect").select_option("family")
    old_source = page.locator("#helpGuidePanel source").element_handle()
    page.locator("#helpGuideSelect").select_option("staff")
    fallback = page.locator("#helpGuidePanel .help-guide-video-error")
    assert not fallback.is_visible()
    old_source.dispatch_event("error")
    assert not fallback.is_visible(), "A detached source must not fail the replacement guide"


@pytest.mark.parametrize("role", FAMILY)
def test_runtime_role_switch_purges_staff_media_and_checks_linked_faq(runtime_media_session, role):
    page, base = runtime_media_session
    open_help(page, base, "admin")
    page.locator("#helpGuideSelect").select_option("staff")
    detail = faq(page, STAFF_QUESTION)
    detail.locator("summary").click()
    video = detail.locator("video")
    video.evaluate("v => v.play()")
    old_video = video.element_handle()
    old_guide = page.locator("#helpGuidePanel video").element_handle()
    page.evaluate("state.availableRoles = ['admin', 'parent', 'student']")
    page.evaluate("role => setRole(role)", role)
    assert page.evaluate("state.role") == role
    for previous in (old_video, old_guide):
        assert previous.evaluate("v => v.paused && !v.isConnected")
    assert STAFF_QUESTION not in questions(page)
    assert page.locator("#helpGuideSelect option").evaluate_all(
        "options => options.map(option => option.value)"
    ) == ["family"]
    assert page.locator("#helpGuideSelect").input_value() == "family"


def test_runtime_faq_lazy_reopen_and_single_playback(runtime_media_session):
    page, base = runtime_media_session
    open_help(page, base)
    assert page.locator("#helpFaqContent video[src], #helpFaqContent source[src]").count() == 0
    detail = faq(page, SHARED_QUESTION)
    detail.locator("summary").click()
    video = detail.locator("video")
    video.evaluate("v => v.play()")
    detail.locator("summary").click()
    page.wait_for_function("v => v.paused", arg=video.element_handle())
    detail.locator("summary").click()
    assert detail.locator("video").count() == 1
    video.evaluate("v => v.play()")
    guide = page.locator("#helpGuidePanel video")
    guide.evaluate("v => v.play()")
    page.wait_for_function("v => v.paused", arg=video.element_handle())
    page.evaluate("() => setView('store')")
    assert guide.evaluate("v => v.paused")


def test_runtime_search_removes_and_pauses_playing_faq(runtime_media_session):
    page, base = runtime_media_session
    open_help(page, base)
    detail = faq(page, SHARED_QUESTION)
    detail.locator("summary").click()
    old = detail.locator("video").element_handle()
    old.evaluate("v => v.play()")
    page.locator("#helpSearchInput").fill("несуществующий-вопрос-xyz")
    assert old.evaluate("v => v.paused && !v.isConnected")


def test_runtime_full_answer_resets_search_and_opens_its_lazy_player(runtime_media_session):
    page, base = runtime_media_session
    open_help(page, base)
    page.locator("#helpSearchInput").fill("вклад")
    assert SHARED_QUESTION not in questions(page)
    page.locator("#helpGuidePanel [data-help-open-question]").click()
    assert page.locator("#helpSearchInput").input_value() == ""
    detail = faq(page, SHARED_QUESTION)
    detail.locator("video").wait_for(state="attached")
    assert detail.evaluate("e => e.open")
    assert detail.locator("summary").evaluate("e => e === document.activeElement")


def test_runtime_seek_before_metadata_loads_the_requested_step_without_playing(
    runtime_media_session,
):
    page, base = runtime_media_session
    open_help(page, base)
    video = page.locator("#helpGuidePanel video")
    assert video.evaluate("v => v.readyState") == 0
    step = page.locator("#helpGuidePanel [data-help-video-time]").last
    time = float(step.get_attribute("data-help-video-time"))
    step.click()
    page.wait_for_function(
        "([v, time]) => v.readyState >= 2 && !v.seeking && Math.abs(v.currentTime - time) < .15",
        arg=[video.element_handle(), time],
    )
    assert video.evaluate("v => v.paused")


def test_runtime_opening_support_pauses_the_playing_faq(runtime_media_session):
    page, base = runtime_media_session
    open_help(page, base)
    detail = faq(page, SHARED_QUESTION)
    detail.locator("summary").click()
    video = detail.locator("video")
    video.evaluate("v => v.play()")
    detail.locator(".help-faq-support [data-help-support]").click()
    assert page.locator("#supportDialog").is_visible()
    assert video.evaluate("v => v.paused")


def test_hidden_staff_support_cannot_open_form_or_overwrite_a_family_draft(help_session):
    page, base = help_session
    open_help(page, base)
    detail = faq(page, SAVE_QUESTION)
    detail.locator("summary").click()
    detail.locator(".help-faq-support [data-help-support]").click()
    message = page.locator('#supportForm [name="message"]')
    message.fill("Unsent family report")
    page.locator("[data-support-close]").click()
    page.evaluate("question => helpOpenSupport(question)", STAFF_QUESTION)
    assert not page.locator("#supportDialog").is_visible()
    assert message.input_value() == "Unsent family report"
    assert page.locator("#supportRole").input_value() == "parent"


def test_support_draft_survives_reload_and_keeps_explicit_role(help_session):
    page, base = help_session
    open_help(page, base)
    detail = faq(page, SAVE_QUESTION)
    detail.locator("summary").click()
    detail.locator(".help-faq-support [data-help-support]").click()
    page.locator('[data-support-role="student"]').click()
    page.locator('#supportForm [name="first_name"]').fill("Demo")
    page.locator('#supportForm [name="last_name"]').fill("Student")
    page.locator('#supportForm [name="message"]').fill("Keep this existing draft")
    page.locator("[data-support-close]").click()
    page.reload(wait_until="networkidle")
    other = faq(page, SHARED_QUESTION)
    other.locator("summary").click()
    other.locator(".help-faq-support [data-help-support]").click()
    assert page.locator('#supportForm [name="message"]').input_value() == "Keep this existing draft"
    assert page.locator('#supportForm [name="first_name"]').input_value() == "Demo"
    assert page.locator('#supportForm [name="last_name"]').input_value() == "Student"
    assert page.locator("#supportRole").input_value() == "student"


def test_search_includes_visible_support_instructions(help_session):
    page, base = help_session
    open_help(page, base)
    item = next(item for item in faq_contract(page)["items"] if item["question"] == SAVE_QUESTION)
    query = " ".join(item["support"].split()[:7])
    page.locator("#helpSearchInput").fill(query)
    assert SAVE_QUESTION in questions(page), f"Visible support text was not searchable: {query}"


@pytest.mark.parametrize("role", ["parent", "student", "teacher"])
def test_answers_and_guides_omit_redundant_result_blocks(help_session, role):
    page, base = help_session
    open_help(page, base, role)
    assert page.locator(".help-faq-outcome, .help-guide-outcome").count() == 0
    assert page.evaluate(
        """() => {
          const item = {...HELP_FAQ_ITEMS[0], outcome: 'hiddenresulttoken'};
          return !helpAnswerMarkup(item).includes('hiddenresulttoken')
            && !helpItemSearchText(item).includes('hiddenresulttoken');
        }"""
    )


def test_visibility_helper_classifies_family_and_every_staff_role(help_session):
    page, base = help_session
    page.goto(base + "/miniapp?demo=1&demo_role=teacher&view=help", wait_until="networkidle")
    for role in (*FAMILY, *STAFF):
        result = page.evaluate(
            """role => {
              state.role = ['parent', 'student', 'teacher'].includes(role) ? role : 'admin';
              state.staffRoles = ['parent', 'student'].includes(role) ? ['superadmin'] : [role];
              const cases = [['staff'], ['parent'], ['student'], [],
                             ['parent', 'student', 'staff']];
              return {audience: helpAudience(), visible: cases.map(audiences =>
                Boolean(helpItemVisible({audiences})))};
            }""",
            role,
        )
        assert result["audience"] == (role if role in FAMILY else "staff")
        expected = [
            role in STAFF or role in audience
            for audience in (["staff"], ["parent"], ["student"], [], ["parent", "student", "staff"])
        ]
        assert result["visible"] == expected, role


def test_help_faq_defaults_do_not_add_action_clutter_to_concepts(help_session):
    page, base = help_session
    open_help(page, base)
    result = page.evaluate(
        """() => ({
          concept: helpFaq('coins', 'Что такое AC?', 'Описание понятия'),
          staff: helpFaq('management', 'Системное понятие', 'Описание'),
          procedure: helpFaq('start', 'Как открыть?', 'Описание', {steps: ['Откройте']}),
          readOnly: HELP_FAQ_ITEMS.filter(item => !item.video && !item.steps.length
                                               && item.category !== 'problems')
            .map(item => ({question: item.question, visible: helpItemVisible(item)}))
        })"""
    )
    concept = result["concept"]
    assert set(concept["audiences"]) == {"parent", "student"}
    assert not concept["outcome"] and not concept["support"] and not concept["video"]
    assert result["staff"]["audiences"] == ["staff"]
    assert result["procedure"]["video"] is True
    assert result["readOnly"] and any(item["visible"] for item in result["readOnly"])


@pytest.mark.parametrize("requested", ["bytes=0-31", "bytes=-32", "bytes=8-", "bytes=999999999-"])
def test_local_mp4_range_mock_matches_native_contract(help_session, requested):
    page, base = help_session
    install_video_ranges(page)
    page.goto(base + "/miniapp?demo=1", wait_until="networkidle")
    result = page.evaluate(
        """async range => {
          const response = await fetch('/miniapp/static/assets/help/guides/parent.mp4?v=0.91.66',
                                       {headers: {Range: range}});
          return {status: response.status, range: response.headers.get('Content-Range'),
                  length: (await response.arrayBuffer()).byteLength};
        }""",
        requested,
    )
    size = (ASSETS / "parent.mp4").stat().st_size
    if requested == "bytes=999999999-":
        assert result["status"] == 416
        assert result["range"] == f"bytes */{size}"
    else:
        start = size - 32 if requested == "bytes=-32" else 8 if requested == "bytes=8-" else 0
        end = 31 if requested == "bytes=0-31" else size - 1
        assert result == {
            "status": 206,
            "range": f"bytes {start}-{end}/{size}",
            "length": end - start + 1,
        }


@pytest.mark.parametrize("role", ["parent", "student", "teacher", "admin"])
@pytest.mark.parametrize("width", [320, 390, 768, 1440])
def test_help_responsive_audiences_and_anchor_topics(help_session, role, width, tmp_path):
    page, base = help_session
    page.set_viewport_size({"width": width, "height": 1000})
    open_help(page, base, role)
    data = faq_contract(page)
    expected = {item["question"] for item in data["items"] if allowed(item, role)}
    actual = questions(page)
    assert actual and None not in actual
    assert len(actual) == len(set(actual))
    assert set(actual) == expected
    assert "Без звука, с подписями" not in page.locator("#helpView").inner_text()
    categories = page.locator("[data-help-category]").evaluate_all(
        "buttons => buttons.map(button => button.dataset.helpCategory)"
    )
    if role in FAMILY:
        assert not {"staff", "management", "messages", "feedback"}.intersection(categories)
    for category in categories:
        button = page.locator(f'[data-help-category="{category}"]')
        button.click()
        assert set(questions(page)) == expected, "Topic navigation must not filter FAQ"
        assert button.get_attribute("aria-pressed") == "true"
        if category != "all":
            destination = page.locator(f"#help-topic-{category}")
            assert destination.count() == 1
            box = destination.bounding_box()
            assert box and 0 <= box["y"] < 1000

    page.locator("#helpSearchInput").fill("несуществующий-вопрос-xyz")
    assert page.locator("#helpEmptyState").is_visible()
    assert page.locator(".help-faq-item").count() == 0
    page.locator("[data-reset-help-search]").click()
    assert set(questions(page)) == expected
    page.locator("[data-help-category=all]").click()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.screenshot(path=str(tmp_path / f"help-faq-{role}-{width}.png"))


@pytest.mark.parametrize("role", ["parent", "student", "teacher", "admin"])
@pytest.mark.parametrize("width", [320, 390, 768, 1440])
def test_help_media_responsive_guides_and_expanded_player(help_session, role, width, tmp_path):
    page, base = help_session
    page.set_viewport_size({"width": width, "height": 1000})
    open_help(page, base, role)
    data = contract(page)
    assert page.locator("#helpGuideSelect option").evaluate_all(
        "options => options.map(option => option.value)"
    ) == [guide["id"] for guide in visible_guides(data, role)]
    assert page.locator("#helpGuideSelect").evaluate(
        "e => e.getBoundingClientRect().right <= innerWidth"
    )
    with_video = next(item for item in data["items"] if allowed(item, role) and item["video"])
    detail = faq(page, with_video["question"])
    detail.locator("summary").focus()
    detail.locator("summary").press("Enter")
    video = detail.locator(".help-faq-video video")
    video.wait_for(state="attached")
    for control in (video, detail.locator(".help-faq-support [data-help-support]")):
        assert control.evaluate(
            "e => { const box = e.getBoundingClientRect();"
            " return box.left >= 0 && box.right <= innerWidth; }"
        )
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.screenshot(path=str(tmp_path / f"help-{role}-{width}.png"))


@pytest.mark.parametrize("role", STAFF)
def test_every_staff_role_sees_all_questions_and_actionable_endings(help_session, role):
    page, base = help_session
    open_help(page, base, role)
    data = faq_contract(page)
    assert len(data["items"]) >= 195
    assert set(questions(page)) == {item["question"] for item in data["items"]}
    assert page.evaluate("HELP_FAQ_ITEMS.every(helpItemVisible)")
    answers = page.locator("details.help-faq-item").evaluate_all(
        """items => items.map(item => ({question: item.dataset.helpQuestion,
          support: item.querySelector('.help-faq-support [data-help-support]')
                       ?.dataset.helpSupport}))"""
    )
    actionable = {item["question"] for item in data["items"] if requires_action_ending(item)}
    for answer in answers:
        if answer["question"] in actionable:
            assert answer["support"] == answer["question"], answer["question"]


@pytest.mark.parametrize("role", STAFF)
def test_every_staff_role_sees_all_available_guides(help_session, role):
    page, base = help_session
    open_help(page, base, role)
    data = contract(page)
    assert page.locator("#helpGuideSelect option").evaluate_all(
        "options => options.map(option => option.value)"
    ) == [guide["id"] for guide in visible_guides(data, role)]


@pytest.mark.parametrize("role", FAMILY)
def test_family_search_never_discloses_staff_answers_or_keywords(help_session, role):
    page, base = help_session
    open_help(page, base, role)
    data = faq_contract(page)
    hidden = {item["question"] for item in data["items"] if not allowed(item, role)}
    assert "Как добавить физический товар?" in hidden
    assert "Как ответить автору и завершить тикет?" in hidden
    queries = [
        "Как добавить физический товар?",
        "Как ответить автору и завершить тикет?",
        "импорт",
        "суперадминистратор",
        "LMS ID",
        "staff",
        "управление",
        "тикет",
    ]
    for query in queries:
        page.locator("#helpSearchInput").fill(query)
        assert not hidden.intersection(questions(page)), query
        rendered = page.locator("#helpFaqContent").text_content()
        assert all(question not in rendered for question in hidden), query
    for question in ("Как добавить физический товар?", "Как ответить автору и завершить тикет?"):
        page.locator("#helpSearchInput").fill(question)
        assert page.locator("#helpEmptyState").is_visible()
    page.locator("#helpSearchInput").fill("переписка")
    assert page.locator(".help-faq-item").count() > 0
    assert "Найдено ответов:" in page.locator("#helpSearchStatus").inner_text()
    page.locator('[data-help-category="access"]').click()
    assert page.locator("#helpSearchInput").input_value() == ""
    assert set(questions(page)) == {
        item["question"] for item in data["items"] if allowed(item, role)
    }


def test_parent_registration_answer_retains_complete_workflow(help_session):
    page, base = help_session
    open_help(page, base)
    item = faq(page, PARENT_QUESTION)
    item.locator("summary").click()
    for label in ("Регистрация по ссылке", "Начать", "Открыть", "разные MAX-аккаунты"):
        assert label in item.inner_text()


def test_bot_support_answer_requests_city_and_child_before_description_and_photos(help_session):
    page, base = help_session
    open_help(page, base)
    detail = faq(page, BOT_SUPPORT_QUESTION)
    detail.locator("summary").click()
    steps = detail.locator(".help-faq-answer > ol > li").all_text_contents()
    assert len(steps) == 7
    assert_bot_support_step_order(steps)
    assert "Отправить заявку" in steps[-1]
    assert "номера заявки" in steps[-1]


def test_every_procedural_faq_mounts_only_its_video_when_expanded(help_session):
    page, base = help_session
    requests = []
    page.on("request", lambda request: requests.append(request.url))
    open_help(page, base, "teacher")
    data = contract(page)
    content = page.locator("#helpFaqContent")
    assert content.locator("video[src], source[src], track[src]").count() == 0
    assert not any(urlsplit(url).path.endswith(".mp4") for url in requests)
    media_items = [item for item in data["items"] if item.get("video")]
    assert media_items
    expanded = set()
    last = None
    for item in data["items"]:
        detail = faq(page, item["question"])
        placeholder = detail.locator(".help-faq-video[data-help-video-question]")
        assert placeholder.count() == bool(item.get("video")), item["question"]
        if not item.get("video"):
            continue
        assert placeholder.get_attribute("data-help-video-question") == item["question"]
        assert placeholder.locator("video[src], source[src]").count() == 0
        detail.locator("summary").click()
        video = placeholder.locator("video")
        video.wait_for(state="attached")
        assert_loaded_video(video, data["catalog"][item["question"]])
        expanded.add(item["question"])
        last = detail
        assert content.locator("details[open]").count() == 1
        mounted = content.locator(".help-faq-video").evaluate_all(
            """nodes => nodes.filter(n => n.querySelector('video[src], source[src]'))
              .map(n => n.dataset.helpVideoQuestion)"""
        )
        assert set(mounted).issubset(expanded), item["question"]
    last.locator("summary").click()
    last.locator("summary").click()
    assert last.locator("video").count() == 1, "Reopening must not duplicate a player"


@pytest.mark.parametrize("role", ["parent", "student", "teacher"])
def test_top_guide_catalog_select_and_previous_next_are_accessible(help_session, role):
    page, base = help_session
    open_help(page, base, role)
    data = contract(page)
    guides = visible_guides(data, role)
    select = page.locator("#helpGuideSelect")
    assert select.evaluate("e => e.tagName") == "SELECT"
    assert (
        select.get_attribute("aria-label") or page.locator('label[for="helpGuideSelect"]').count()
    )
    previous = page.locator("[data-help-guide-prev]")
    following = page.locator("[data-help-guide-next]")
    for button in (previous, following):
        assert button.get_attribute("title") or button.get_attribute("aria-label")
    assert len(guides) >= 2
    select.focus()
    select.press("Home")
    select.press("ArrowDown")
    select.press("Enter")
    assert select.input_value() == guides[1]["id"]
    select.select_option(guides[0]["id"])
    following.click()
    assert select.input_value() == guides[1]["id"]
    previous.click()
    assert select.input_value() == guides[0]["id"]
    for guide in guides:
        select.select_option(guide["id"])
        clip = data["catalog"][guide["question"]]
        panel = page.locator("#helpGuidePanel")
        assert_loaded_video(panel.locator("video"), clip)
        assert panel.locator("[data-help-video-time]").count() == len(clip["steps"])
        assert clip["title"] in panel.inner_text()
        assert all(
            title in panel.inner_text() and text in panel.inner_text()
            for _, title, text in clip["steps"]
        )


@pytest.mark.parametrize("surface", ["guide", "faq"])
def test_native_video_plays_seeks_changes_frames_and_pauses(help_session, surface):
    page, base = help_session
    install_video_ranges(page)
    open_help(page, base)
    data = contract(page)
    if surface == "guide":
        guide_id = page.locator("#helpGuideSelect").input_value()
        question = next(guide["question"] for guide in data["guides"] if guide["id"] == guide_id)
        container = page.locator("#helpGuidePanel")
    else:
        question = PARENT_QUESTION
        detail = faq(page, question)
        detail.locator("summary").click()
        container = detail.locator(".help-faq-video")
    clip = data["catalog"][question]
    video = container.locator("video")
    video.evaluate("v => v.play()")
    page.wait_for_function("v => v.currentTime > .2", arg=video.element_handle())
    video.evaluate("v => v.pause()")
    first = Image.open(BytesIO(video.screenshot())).convert("RGB")
    seek_time = clip["steps"][len(clip["steps"]) // 2][0]
    assert seek_time > 0
    if surface == "guide":
        container.locator(f'[data-help-video-time="{seek_time}"]').click()
    else:
        video.evaluate("(v, time) => { v.currentTime = time; }", seek_time)
    page.wait_for_function(
        "([v, time]) => Math.abs(v.currentTime - time) < .15 && !v.seeking && v.readyState >= 2",
        arg=[video.element_handle(), seek_time],
    )
    later = Image.open(BytesIO(video.screenshot())).convert("RGB")
    # Exclude native controls, whose seek progress can change over a static picture.
    first = first.crop((0, 0, first.width, max(1, first.height - 60)))
    later = later.crop((0, 0, later.width, max(1, later.height - 60)))
    assert ImageChops.difference(first, later).getbbox(), "Seeking must change the rendered frame"
    assert abs(video.evaluate("v => v.duration") - clip["duration"]) < 0.6
    assert video.evaluate("v => v.videoWidth > 0 && v.videoHeight > 0")
    assert video.evaluate("v => v.paused")
    video.evaluate("v => v.play()")
    if surface == "faq":
        faq(page, question).locator("summary").click()
        page.wait_for_function("v => v.paused", arg=video.element_handle())
        faq(page, question).locator("summary").click()
        video.evaluate("v => v.play()")
    page.locator('[data-view="store"]').first.click()
    assert video.evaluate("v => v.paused"), "Hidden help must not continue playback"


@pytest.mark.parametrize("surface", ["guide", "faq"])
@pytest.mark.parametrize("failure", ["network", "source"])
def test_video_error_keeps_transcript_and_support(help_session, surface, failure):
    page, base = help_session
    page.route("**/assets/help/guides/*.mp4*", lambda route: route.abort())
    open_help(page, base)
    data = contract(page)
    if surface == "guide":
        guide_id = page.locator("#helpGuideSelect").input_value()
        question = next(guide["question"] for guide in data["guides"] if guide["id"] == guide_id)
        container = page.locator("#helpGuidePanel")
    else:
        question = PARENT_QUESTION
        faq(page, question).locator("summary").click()
        container = faq(page, question).locator(".help-faq-video")
    if failure == "network":
        container.locator("video").evaluate("v => { v.load(); void v.play().catch(() => {}); }")
    else:
        container.locator("source").dispatch_event("error")
    error = container.locator(".help-guide-video-error")
    error.wait_for(state="visible")
    assert "не загрузилось" in error.inner_text().lower()
    clip = data["catalog"][question]
    if surface == "guide":
        assert all(text in container.inner_text() for _, _, text in clip["steps"])
        download = container.locator("a[download]")
        assert download.is_visible()
        href = download.get_attribute("href")
        assert urlsplit(href).path == f"/miniapp/static/assets/help/guides/{clip['id']}.mp4"
        assert parse_qs(urlsplit(href).query).get("v") == ["0.91.66"]
    else:
        item = next(item for item in data["items"] if item["question"] == question)
        assert all(step in faq(page, question).inner_text() for step in item["steps"])
        assert faq(page, question).locator(".help-faq-outcome").count() == 0
    error.locator("[data-help-support]").click()
    assert page.locator("#supportDialog").is_visible()


@pytest.mark.parametrize("role", ["parent", "student", "teacher"])
def test_missing_save_answer_has_screenshot_instructions_and_working_cta(help_session, role):
    page, base = help_session
    open_help(page, base, role)
    detail = faq(page, SAVE_QUESTION)
    detail.locator("summary").click()
    text = detail.inner_text().lower()
    assert "скриншот" in text or "снимок экрана" in text
    assert "сообщить о проблеме" in text
    assert "прикреп" in text
    assert "отправ" in text
    assert detail.locator(".help-faq-outcome").count() == 0
    button = detail.locator(".help-faq-support [data-help-support]")
    assert button.get_attribute("data-help-support") == SAVE_QUESTION
    button.click()
    assert page.locator("#supportDialog").is_visible()
    assert page.locator("#supportRole").input_value() == (role if role in FAMILY else "staff")
    page.locator('#supportForm [name="first_name"]').fill("Demo")
    page.locator('#supportForm [name="last_name"]').fill("Tester")
    page.locator('#supportForm [name="message"]').fill("Keep my unsent screenshot report")
    page.locator("#supportFileInput").set_input_files(
        {
            "name": "demo-screenshot.png",
            "mimeType": "image/png",
            "buffer": (ASSETS / "parent.png").read_bytes(),
        }
    )
    page.locator("[data-support-close]").click()
    # A different FAQ must not replace the draft with its own question/context.
    other = faq(page, "Как открыть приложение?")
    other.locator("summary").click()
    other.locator(".help-faq-support [data-help-support]").focus()
    other.locator(".help-faq-support [data-help-support]").press("Enter")
    assert page.locator("#supportDialog").is_visible()
    assert (
        page.locator('#supportForm [name="message"]').input_value()
        == "Keep my unsent screenshot report"
    )
    assert page.locator('#supportForm [name="first_name"]').input_value() == "Demo"
    assert page.locator('#supportForm [name="last_name"]').input_value() == "Tester"
    assert page.locator("#supportRole").input_value() == (role if role in FAMILY else "staff")
    assert page.locator("#supportPhotoCount").inner_text() == "1/5"


@pytest.mark.parametrize("role", FAMILY)
def test_role_switch_removes_staff_answers_guides_and_loaded_media(help_session, role):
    page, base = help_session
    install_video_ranges(page)
    open_help(page, base, "admin")
    data = contract(page)
    family_guides = {guide["id"] for guide in visible_guides(data, role)}
    staff_guide = next(
        guide for guide in visible_guides(data, "admin") if guide["id"] not in family_guides
    )
    question = staff_guide["question"]
    page.locator("#helpGuideSelect").select_option(staff_guide["id"])
    detail = faq(page, question)
    detail.locator("summary").click()
    page.evaluate("""() => {
      window.oldHelpVideos = [...document.querySelectorAll('#helpView video')];
    }""")
    detail.locator("video").evaluate("v => v.play()")
    page.evaluate("state.availableRoles = ['admin', 'parent', 'student']")
    page.evaluate("role => setRole(role)", role)
    assert page.evaluate("state.role") == role
    assert page.evaluate("window.oldHelpVideos.every(v => v.paused && !v.isConnected)")
    assert question not in page.locator("#helpView").text_content()
    assert staff_guide["id"] not in page.locator("#helpGuideSelect option").evaluate_all(
        "options => options.map(option => option.value)"
    )
    clip_id = data["catalog"][question]["id"]
    guide_sources = page.locator("#helpGuides source[src], #helpGuides video[src]").evaluate_all(
        "nodes => nodes.map(node => node.src)"
    )
    assert all(
        urlsplit(url).path != f"/miniapp/static/assets/help/guides/{clip_id}.mp4"
        for url in guide_sources
    )
    page.locator("#helpSearchInput").fill("")
    assert set(questions(page)) == {
        item["question"] for item in data["items"] if allowed(item, role)
    }
    page.evaluate("() => setRole('admin')")
    assert set(questions(page)) == {item["question"] for item in data["items"]}
