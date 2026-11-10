"""Readable, operable Ball Sort route: real controls, mobile sizes and replay verification."""

from pathlib import Path

import pytest

from tests.test_arcade_mobile import browser as browser
from tests.test_arcade_server import arcade as arcade

CAPTURES = Path(__file__).parents[1] / ".deploy_tmp/sort-route-20261110"


def open_route(page, store):
    # Layout fixture only; generated runs still go through the real verifier.
    with store.db() as db:
        for stage in range(1, 48):
            db.execute(
                "INSERT INTO arcade_journeys VALUES(?,?,?,?,?,?,?)",
                ("p1", "sort", stage, 1, 1, store.clock(), '{"routeVersion":2}'),
            )
    page.reload()
    page.locator('.game-card[data-game="sort"]').click()
    page.locator("[data-menu-levels]").click()
    page.locator('[data-journey-play="48"]').wait_for()


@pytest.mark.parametrize("size", [(320, 568), (390, 844), (844, 390), (1440, 900)])
def test_each_chapter_is_readable_on_phone_and_desktop(arcade, size, request):
    page, store = arcade
    page.set_viewport_size(dict(zip(("width", "height"), size, strict=True)))
    page.emulate_media(reduced_motion="reduce")
    open_route(page, store)
    assert page.locator(".journey-stop").count() == 48
    assert page.locator(".arcade-level-topic").count() == 6
    for stage in (1, 9, 17, 25, 33, 41, 48):
        page.locator(f'[data-journey-stage="{stage}"]').click()
        if stage < 41:
            assert page.locator(".sort-next-feature").is_visible()
        page.locator(f'[data-journey-play="{stage}"]').click()
        page.wait_for_function("document.querySelector('#gameClock b')?.textContent.length>0")
        page.evaluate(
            "async()=>{await new Promise(requestAnimationFrame);"
            "await new Promise(requestAnimationFrame);}"
        )
        assert page.locator(".sort-rule").is_visible()
        assert page.locator(".game-dialog").evaluate("n=>n.scrollWidth<=n.clientWidth")
        assert page.locator(".sort-tubes").evaluate("n=>n.scrollWidth<=n.clientWidth")
        assert page.locator("[data-sort-route-clock]").is_visible()
        metrics = page.locator(".game-stage").evaluate("""stage=>{
          const box=n=>n.getBoundingClientRect(),s=box(stage),
            grid=box(stage.querySelector('.sort-tubes')),rule=box(stage.querySelector('.sort-rule')),
            tools=box(stage.querySelector('.sort-tools'));
          return {bottom:tools.bottom<=s.bottom+1,
            overlap:!(grid.top>=rule.bottom-1||grid.right<=rule.left+1)};
        }""")
        assert metrics["bottom"] and not metrics["overlap"], (stage, size, metrics)
        assert page.locator(".sort-rule").evaluate(
            "n=>parseFloat(getComputedStyle(n).fontSize)>=18"
        )
        if stage == 9:
            assert page.locator('.sort-tube[data-capacity="3"]').count() == 1
        if stage == 17:
            assert page.locator(".sort-tube.is-sealed:disabled").count() == 1
        if stage in (25, 41, 48):
            assert page.locator(".sort-unknown").count() > 0
            assert page.locator('.sort-unknown[style*="marble"]').count() == 0
        CAPTURES.mkdir(parents=True, exist_ok=True)
        page.locator(".game-dialog").screenshot(
            path=str(CAPTURES / f"{request.node.name}-{stage}.png")
        )
        page.locator(".game-close").click()
        if stage != 48:
            page.locator('.game-card[data-game="sort"]').click()
            page.locator("[data-menu-levels]").click()


def test_final_level_uses_real_ui_and_verified_result_shows_actual_star_limits(arcade, request):
    page, store = arcade
    page.emulate_media(reduced_motion="reduce")
    open_route(page, store)
    page.evaluate("""()=>{
      const create=ArcadeWorld.create,now=performance.now.bind(performance);
      window.routeOffset=0;performance.now=()=>now()+routeOffset;
      ArcadeWorld.create=s=>{const w=create(s);if(s.game==='sort')window.routeProbe=w;return w;};
    }""")
    offset = [0]
    previous_clock = store.clock
    store.clock = lambda: previous_clock() + offset[0]
    page.locator('[data-journey-play="48"]').click()
    page.wait_for_function("document.querySelector('#gameClock b')?.textContent.length>0")
    assert page.locator(".sort-meta b").inner_text() == "Задача 1 из 3"
    for round_ in range(3):
        for move in page.evaluate("routeProbe.sortSolution"):
            offset[0] += 1
            page.evaluate("routeOffset+=1000")
            page.evaluate(
                """a=>{
              document.querySelector(`[data-tube="${a.from}"]`).click();
              document.querySelector(`[data-tube="${a.to}"]`).click();
            }""",
                move,
            )
        if round_ < 2:
            page.locator("[data-sort-next]").click()
    page.locator(".journey-result").wait_for()
    page.locator("[data-journey-next]").wait_for()
    assert "Уровень пройден!" in page.locator(".journey-result").inner_text()
    assert page.locator(".journey-result-stars").inner_text() == "★★★"
    page.locator(".arcade-result-details summary").click()
    assert "undefined" not in page.locator(".journey-result").inner_text()
    assert "без запасной колбы" in page.locator(".journey-result").inner_text()
    assert store.profile("p1")["journeys"]["sort"]["cleared"] == 48
    assert store.profile("p1")["balance"] == 5
    assert not store.board("sort", viewer="p1")["rows"]
    CAPTURES.mkdir(parents=True, exist_ok=True)
    page.locator(".game-dialog").screenshot(path=str(CAPTURES / f"{request.node.name}-win.png"))
    page.locator("[data-journey-next]").click()
    assert page.locator(".journey-stop.is-complete").count() == 48
    page.locator(".game-close").click()


def test_separate_local_viewer_opens_all_levels_without_creating_sessions_or_rewards(arcade):
    page, store = arcade
    page.emulate_media(reduced_motion="reduce")
    source = Path(__file__).parents[1] / "app/cli/sort_levels_preview.html"
    static = Path(__file__).parents[1] / "app/web/static/miniapp"
    page.route(
        "http://127.0.0.1:8779/preview/sort-levels*",
        lambda r: r.fulfill(path=str(source), content_type="text/html"),
    )
    page.route(
        "**/games-world.js*",
        lambda r: r.fulfill(
            body=(static / "games-world.js").read_text(encoding="utf-8")
            + """
        (()=>{const create=ArcadeWorld.create;ArcadeWorld.create=s=>{
          const w=create(s);window.labProbe=w;return w;};})();
        """,
            content_type="application/javascript",
        ),
    )
    requests = []
    page.on("request", lambda r: requests.append(r.url) if "/preview/arcade" in r.url else None)
    page.goto("http://127.0.0.1:8779/preview/sort-levels?level=48")
    page.locator(".sort-tubes").wait_for()
    assert page.locator("#level option").count() == 48
    assert page.locator(".sort-unknown").count() > 0
    for round_ in range(3):
        for move in page.evaluate("labProbe.sortSolution"):
            page.evaluate(
                """a=>{
              document.querySelector(`[data-tube="${a.from}"]`).click();
              document.querySelector(`[data-tube="${a.to}"]`).click();
            }""",
                move,
            )
        if round_ < 2:
            page.locator("[data-sort-next]").click()
    page.locator(".journey-result").wait_for()
    assert page.locator(".journey-result-stars").inner_text() == "★★★"
    assert not requests
    with store.db() as db:
        assert db.execute("SELECT COUNT(*) FROM arcade_sessions").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM arcade_journeys").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM arcade_awards").fetchone()[0] == 0
