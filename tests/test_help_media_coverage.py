"""Executable catalog contracts and local help-media integrity, without a backend."""

import base64
import math
import re
import runpy
import struct
from pathlib import Path

import pytest
from PIL import Image
from test_feedback_workspace_ui import feedback_browser as _browser

feedback_browser = _browser
MINIAPP = Path(__file__).parents[1] / "app/web/static/miniapp"
ASSETS = MINIAPP / "assets/help/guides"
FAMILY = {"parent", "student"}
AUDIENCES = FAMILY | {"staff"}
BOT_SUPPORT_QUESTION = "Как сообщить о проблеме через бота?"


def assert_bot_support_step_order(steps):
    normalized = [step.lower().replace("ё", "е") for step in steps]

    def position(label, predicate):
        found = [index for index, step in enumerate(normalized) if predicate(step)]
        assert found, f"Bot support flow is missing: {label}"
        return found[0]

    city = position("city request", lambda step: "отправьте" in step and "город" in step)
    child = position(
        "parent's child name request",
        lambda step: "родител" in step and "имя и фамилию ребенка" in step,
    )
    description = position("description request", lambda step: "отправьте описание" in step)
    photos = position(
        "photo attachment", lambda step: re.search(r"(?:прилож|прикреп)\w*\s+фото", step)
    )
    assert city < child < description <= photos
    assert "ученики и сотрудники" in normalized[child] and "пропускают" in normalized[child]
    assert "предыдущих шагах фотографии не принимаются" in normalized[description]


@pytest.fixture(scope="module")
def help_data_page(feedback_browser):
    browser, base = feedback_browser
    context = browser.new_context()
    try:
        context.route("https://st.max.ru/**", lambda route: route.abort())
        page = context.new_page()
        page.goto(base + "/miniapp?demo=1&demo_role=teacher&view=help", wait_until="networkidle")
        yield page
    finally:
        context.close()


@pytest.fixture(scope="module")
def help_contract(help_data_page):
    return help_data_page.evaluate(
        """() => ({items: HELP_FAQ_ITEMS, catalog: HELP_MEDIA_CATALOG,
                    guides: HELP_TOP_GUIDES})"""
    )


@pytest.fixture(scope="module")
def help_faq_items(help_data_page):
    return help_data_page.evaluate("HELP_FAQ_ITEMS")


@pytest.fixture(scope="module")
def family_capture_plan(help_faq_items):
    tooling = MINIAPP.parents[3] / "tools/help_media"
    assert (tooling / "build.py").is_file(), "Capture provenance tooling is missing"
    # Compile declarations only: no capture, server, encoding or asset writes.
    with pytest.MonkeyPatch.context() as environment:
        environment.syspath_prepend(str(tooling))
        builder = runpy.run_path(str(tooling / "build.py"))
        family = runpy.run_path(str(tooling / "scenario_family.py"))
        external = runpy.run_path(str(tooling / "external.py"))
        definitions = builder["definitions"]()
        definitions.update(family["family_definitions"](help_faq_items))
        review = runpy.run_path(str(tooling / "review.py"))
        definitions = review["apply_reviews"](help_faq_items, definitions)
        result = {}
        for item in help_faq_items:
            if not item.get("video") or not FAMILY.intersection(item["audiences"]):
                continue
            question = item["question"]
            compiled = builder["compile_item"](item, definitions[question])
            sources = []
            for step in compiled["timeline"]:
                name = step["shot"].split("@", 1)[0]
                screen = builder["SCREENS"].get(name)
                if screen:
                    sources.append(
                        {
                            "role": screen.role,
                            "view": screen.view,
                            "screen": name,
                            "reconstructed": screen.reconstructed,
                        }
                    )
                else:
                    assert name in external["MOCKS"], f"Unknown capture source: {question}: {name}"
                    sources.append(
                        {
                            "role": "public",
                            "view": "external",
                            "screen": name,
                            "reconstructed": True,
                        }
                    )
            result[question] = {"compiled": compiled, "sources": sources}
        return result


def mp4_duration(path):
    data = path.read_bytes()

    def boxes(start, end):
        while start + 8 <= end:
            size, kind = struct.unpack_from(">I4s", data, start)
            header = 8
            if size == 1:
                size = struct.unpack_from(">Q", data, start + 8)[0]
                header = 16
            elif size == 0:
                size = end - start
            assert size >= header and start + size <= end, f"Invalid MP4 box in {path.name}"
            yield kind, start + header, start + size
            start += size

    for kind, start, end in boxes(0, len(data)):
        if kind != b"moov":
            continue
        for child, payload, _ in boxes(start, end):
            if child == b"mvhd":
                if data[payload] == 1:
                    scale, duration = struct.unpack_from(">IQ", data, payload + 20)
                else:
                    scale, duration = struct.unpack_from(">II", data, payload + 12)
                assert scale > 0
                return duration / scale
    pytest.fail(f"No movie duration in {path.name}")


def vtt_cues(path):
    text = path.read_text(encoding="utf-8-sig")
    assert text.startswith("WEBVTT"), path.name
    stamp = r"(?:(\d{2}):)?(\d{2}):(\d{2})\.(\d{3})"

    def seconds(parts):
        hours, minutes, secs, millis = parts
        assert int(minutes) < 60 and int(secs) < 60, path.name
        return int(hours or 0) * 3600 + int(minutes) * 60 + int(secs) + int(millis) / 1000

    cues = []
    for block in re.split(r"\r?\n\s*\r?\n", text):
        if "-->" not in block:
            continue
        lines = block.splitlines()
        index = next(index for index, line in enumerate(lines) if "-->" in line)
        match = re.fullmatch(stamp + r"\s+-->\s+" + stamp + r"(?:\s+.*)?", lines[index])
        assert match, f"Invalid VTT timestamp in {path.name}: {lines[index]}"
        start, end = seconds(match.groups()[:4]), seconds(match.groups()[4:])
        assert start < end
        assert "\n".join(lines[index + 1 :]).strip(), f"Empty caption in {path.name}"
        cues.append((start, end))
    assert cues, f"No captions in {path.name}"
    assert "https://max.ru/" not in text, f"Real invitation in {path.name}"
    return cues


def test_procedural_faq_catalog_is_keyed_by_exact_question(help_contract):
    items, catalog = help_contract["items"], help_contract["catalog"]
    questions = [item["question"] for item in items]
    assert len(items) >= 195
    assert len(questions) == len(set(questions))
    assert catalog and set(catalog).issubset(questions), "Orphan or renamed media question"
    procedural = [item for item in items if item["steps"]]
    assert procedural
    missing = [
        item["question"]
        for item in procedural
        if not item.get("video") or item["question"] not in catalog
    ]
    assert not missing, f"Procedural FAQs missing video: {missing}"
    for item in items:
        assert bool(item.get("video")) == (item["question"] in catalog), item["question"]
    required = {
        "Как родителю подключить ребёнка?",
        "Как ученику зарегистрироваться после родителя?",
        "Как добавить физический товар?",
        "Как загрузить учеников из Excel?",
        "Как загрузить сразу несколько товаров?",
        "Как посмотреть историю подключений и открыть карточку ученика?",
        "Где посмотреть, кто изменил товар, заказ или доступ?",
        "Почему в окне не видно кнопку сохранения?",
    }
    assert required <= catalog.keys(), "Core procedural workflows require clips even without steps"


def test_faq_audiences_and_actionable_answer_endings(help_faq_items):
    for item in help_faq_items:
        question = item["question"]
        assert item["audiences"] and set(item["audiences"]) <= AUDIENCES, question
        assert len(item["audiences"]) == len(set(item["audiences"])), question
        read_only = item.get("video") is False and not item.get("steps")
        actionable = (
            item.get("video")
            or item.get("steps")
            or (item["category"] == "problems" and not read_only)
            or question == "Почему в окне не видно кнопку сохранения?"
        )
        if actionable:
            assert isinstance(item.get("outcome"), str) and item["outcome"].strip(), question
            assert item.get("support"), question
        if item["category"] in {"staff", "management", "messages", "feedback"}:
            assert not FAMILY.intersection(item["audiences"]), question
    for question in ("Как добавить физический товар?", "Как ответить автору и завершить тикет?"):
        item = next(item for item in help_faq_items if item["question"] == question)
        assert set(item["audiences"]) == {"staff"}, question


def test_common_problem_clips_remain_available_to_both_family_roles(help_faq_items):
    common = {
        "Что делать, если раздел долго загружается?",
        "Почему в окне не видно кнопку сохранения?",
        "Что делать, если операция завершилась сообщением о сбое?",
        "Почему после выхода новой версии приложение выглядит по-старому?",
        "Что делать, если данные не принимаются?",
        "Что делать, если вход не подтверждён или нет доступа?",
        "Что делать, если сервис временно недоступен?",
    }
    items = {item["question"]: item for item in help_faq_items}
    assert common <= items.keys()
    for question in common:
        item = items[question]
        assert FAMILY <= set(item["audiences"]), f"Common error hidden from family: {question}"
        assert item.get("video"), question


def test_parent_registration_uses_supplied_email_without_personal_qr(family_capture_plan):
    question = "Как родителю подключить ребёнка?"
    plan = family_capture_plan[question]
    assert [step["shot"] for step in plan["compiled"]["timeline"][:2]] == [
        "parentmailoverview@#subject",
        "parentmaillink@#invite",
    ]
    assert all(not scene["reconstructed"] for scene in plan["sources"][:2])
    assert not any(step["shot"].startswith("account@") for step in plan["compiled"]["timeline"])
    source = MINIAPP.parents[3] / "tools/help_media/assets/parent-invitation.png"
    with Image.open(source) as screenshot:
        assert screenshot.size == (1247, 1280)
        assert screenshot.crop((534, 345, 873, 567)).convert("RGB").getextrema() == (
            (255, 255),
            (255, 255),
            (255, 255),
        )
        assert (
            max(
                high
                for _, high in screenshot.crop((370, 731, 597, 957)).convert("RGB").getextrema()
            )
            <= 170
        )


def test_bot_support_clip_requests_city_and_child_before_description_and_photos(help_contract):
    clip = help_contract["catalog"][BOT_SUPPORT_QUESTION]
    assert_bot_support_step_order([text for _, _, text in clip["steps"]])
    captions = (ASSETS / f"{clip['id']}.vtt").read_text(encoding="utf-8-sig")
    assert_bot_support_step_order(re.split(r"\r?\n\s*\r?\n", captions))


def test_all_videos_have_explicit_focused_reviews(help_faq_items):
    tooling = MINIAPP.parents[3] / "tools/help_media"
    with pytest.MonkeyPatch.context() as environment:
        environment.syspath_prepend(str(tooling))
        builder = runpy.run_path(str(tooling / "build.py"))
        review = runpy.run_path(str(tooling / "review.py"))
        plans = review["apply_reviews"](help_faq_items, builder["definitions"]())
        for item in help_faq_items:
            if not item.get("video"):
                continue
            question = item["question"]
            plan = plans[question]
            clip = builder["compile_item"](item, plan)
            assert plan["review_note"].strip(), question
            assert len(clip["timeline"]) == len(plan["video_steps"]), question
            assert not any(step.get("result") for step in clip["timeline"]), question
            assert not any(step["shot"].startswith("account@") for step in clip["timeline"])
            for step in clip["timeline"]:
                assert step["title"] != "Проверьте результат", question
                assert step["action"] in {"click", "observe"}, question
                assert len(step["text"]) <= 360, question


@pytest.mark.parametrize("action", ["observe", "click"])
def test_video_scene_only_animates_reviewed_clicks(feedback_browser, action):
    browser, _ = feedback_browser
    context = browser.new_context(viewport={"width": 960, "height": 720})
    try:
        page = context.new_page()
        tooling = MINIAPP.parents[3] / "tools/help_media"
        page.goto((tooling / "templates/scene.html").as_uri())
        screenshot = base64.b64encode((MINIAPP / "assets/help/start-navigation.png").read_bytes())
        caption = "Проверьте выбранного ученика и сумму операции."
        page.evaluate("setScene", {
            "name": "Проверка операции", "index": 1, "total": 1,
            "title": "Проверьте выбранного ученика", "text": caption,
            "image": "data:image/png;base64," + screenshot.decode(),
            "width": 1060, "height": 430,
            "rect": {"x": 300, "y": 100, "width": 300, "height": 40},
            "action": action,
        })
        page.evaluate("setPhase(3)")
        assert page.locator("#pointer").is_visible() == (action == "click")
        assert page.locator("#press").is_visible() == (action == "click")
        assert page.locator("#title").is_hidden()
        assert page.locator("#text").inner_text() == caption
        assert page.evaluate("textFits()")
    finally:
        context.close()


def test_family_clip_capture_sources_never_use_staff_screens(help_contract, family_capture_plan):
    catalog = help_contract["catalog"]
    staff_views = {"admin", "report", "accrual", "broadcasts", "feedback"}
    staff_screens = ("admin", "management", "producteditor", "profile", "staffrole")
    stale = []
    for item in help_contract["items"]:
        if not item.get("video") or not FAMILY.intersection(item["audiences"]):
            continue
        question = item["question"]
        clip = catalog[question]
        # Capture metadata describes every scene, not just the clip's intended audience.
        plan = family_capture_plan[question]
        assert clip["id"] == plan["compiled"]["id"], question
        expected_steps = [[step["time"], step["text"]] for step in plan["compiled"]["timeline"]]
        if (
            clip["duration"] != plan["compiled"]["duration"]
            or [[time, text] for time, _, text in clip["steps"]] != expected_steps
        ):
            stale.append(question)
        sources = clip.get("sources", plan["sources"])
        assert isinstance(sources, list) and sources, f"Missing family capture sources: {question}"
        for source in sources:
            assert isinstance(source, dict), question
            assert source.get("role") in FAMILY or (
                source.get("role") == "public" and source.get("reconstructed") is True
            ), f"Staff capture in family clip: {question}: {source}"
            assert source.get("view") not in staff_views, f"Staff view: {question}: {source}"
            assert source.get("view") or source.get("screen"), f"Unknown screen: {question}"
            screen = re.sub(r"[^a-z0-9]", "", str(source.get("screen", "")).lower())
            assert not any(name in screen for name in staff_screens), (
                f"Staff editor in family clip: {question}: {source}"
            )
    assert not stale, f"Capture plan and catalog are out of sync ({len(stale)}): {stale}"


def test_top_guides_are_complete_unique_and_reference_faq_catalog(help_contract):
    guides, catalog = help_contract["guides"], help_contract["catalog"]
    assert len(guides) > 3
    assert len({guide["id"] for guide in guides}) == len(guides)
    assert len({guide["question"] for guide in guides}) == len(guides)
    for guide in guides:
        assert {"id", "label", "icon", "audiences", "question"} <= guide.keys()
        assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", guide["id"])
        assert guide["label"].strip() and guide["icon"].strip()
        assert guide["audiences"] and set(guide["audiences"]) <= AUDIENCES
        assert guide["question"] in catalog, guide["question"]
        item = next(
            item for item in help_contract["items"] if item["question"] == guide["question"]
        )
        assert item.get("video"), guide["question"]
    questions = {guide["question"] for guide in guides}
    assert "Как загрузить учеников из Excel?" in questions
    assert "Как добавить физический товар?" in questions
    assert questions.intersection(
        {
            "Как посмотреть историю подключений и открыть карточку ученика?",
            "Где посмотреть, кто изменил товар, заказ или доступ?",
        }
    ), "Missing history top guide"
    assert any(
        item["category"] == "access" and item["question"] in questions
        for item in help_contract["items"]
    ), "Missing access top guide"


def test_catalog_metadata_and_step_times_match_real_mp4s(help_contract):
    for question, clip in help_contract["catalog"].items():
        assert {"id", "title", "duration", "steps"} <= clip.keys(), question
        assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", clip["id"]), question
        assert isinstance(clip["title"], str) and clip["title"].strip(), question
        duration = clip["duration"]
        assert isinstance(duration, (int, float)) and not isinstance(duration, bool)
        assert math.isfinite(duration) and 0 < duration <= 180, question
        assert clip["steps"], question
        times = []
        for step in clip["steps"]:
            assert isinstance(step, list) and len(step) == 3, question
            time, title, text = step
            assert isinstance(time, (int, float)) and not isinstance(time, bool), question
            assert math.isfinite(time) and 0 <= time < duration, question
            assert isinstance(title, str) and title.strip(), question
            assert isinstance(text, str) and text.strip(), question
            times.append(time)
        assert times[0] == 0 and times == sorted(set(times)), question
        path = ASSETS / f"{clip['id']}.mp4"
        assert path.is_file(), f"{question}: {path.name}"
        assert abs(mp4_duration(path) - duration) < 0.6, question
        cues = vtt_cues(path.with_suffix(".vtt"))
        assert all(0 <= start < end <= duration + 0.1 for start, end in cues), question
        assert [start for start, _ in cues] == sorted(start for start, _ in cues), question
        assert all(any(start <= time < end for start, end in cues) for time in times), question


def test_every_shipped_clip_has_a_decodable_poster_and_caption_track():
    clips = list(ASSETS.glob("*.mp4"))
    assert clips
    for path in clips:
        assert 10_000 < path.stat().st_size < 3_000_000, path.name
        poster = path.with_suffix(".png")
        assert poster.is_file(), path.name
        with Image.open(poster) as image:
            assert image.width >= 320 and image.height >= 180, poster.name
            image.verify()
        cues = vtt_cues(path.with_suffix(".vtt"))
        assert max(end for _, end in cues) <= mp4_duration(path) + 0.1, path.name


def test_help_assets_use_fresh_cache_versions_and_catalog_load_order():
    source = (MINIAPP / "index.html").read_text(encoding="utf-8")
    assets = re.findall(r'(?:src|href)="(/miniapp/static/[^"?]+\.(?:js|css))\?v=([0-9.]+)"', source)
    assert assets
    for path, version in assets:
        if "/assets/" not in path:
            assert version == "0.92.1", path
    scripts = re.findall(r'<script\b[^>]*\bsrc="([^"?]+)', source)
    assert scripts.index("/miniapp/static/app-help-media-catalog.js") < scripts.index(
        "/miniapp/static/app-help.js"
    )
    assert scripts.index("/miniapp/static/app-help-guides.js") < scripts.index(
        "/miniapp/static/app-help.js"
    )
