"""Local game rules and UI. Uses static files, no database or outgoing MAX requests."""

import os
from pathlib import Path

import pytest

from app.cli.games_preview import inject_games

STATIC = Path(__file__).parents[1] / "app/web/static/miniapp"


@pytest.fixture(scope="module")
def games_browser():
    pw = pytest.importorskip("playwright.sync_api")
    with pw.sync_playwright() as runtime:
        try:
            browser = runtime.chromium.launch(channel="msedge" if os.name == "nt" else None)
        except pw.Error as error:
            if "Executable doesn't exist" in str(error) or "distribution 'msedge'" in str(error):
                pytest.skip("Install Playwright Chromium for game UI checks")
            raise
        yield browser
        browser.close()


@pytest.fixture
def engine(games_browser):
    page = games_browser.new_page()
    page.add_script_tag(path=str(STATIC / "games-engine.js"))
    yield page
    page.close()


@pytest.mark.parametrize(
    ("row", "expected", "score"),
    [
        ([2, 2, 2, 2], [4, 4, 0, 0], 8),
        ([2, 2, 4, 0], [4, 4, 0, 0], 4),
        ([4, 0, 4, 4], [8, 4, 0, 0], 8),
        ([2, 4, 8, 16], [2, 4, 8, 16], 0),
    ],
)
def test_2048_merges_once_per_move(engine, row, expected, score):
    result = engine.evaluate("r=>AlgoGameEngine.slide([...r,...Array(12).fill(0)],'left')", row)
    assert result["board"][:4] == expected
    assert result["score"] == score


def test_2048_vertical_reverse_and_game_over(engine):
    assert (
        engine.evaluate(
            "AlgoGameEngine.slide([2,0,0,0,2,0,0,0,...Array(8).fill(0)],'down').board[12]"
        )
        == 4
    )
    assert engine.evaluate(
        "AlgoGameEngine.slide([2,2,4,0,...Array(12).fill(0)],'right').board.slice(0,4)"
    ) == [0, 0, 4, 4]
    assert engine.evaluate("AlgoGameEngine.canMove([2,4,2,4,4,2,4,2,2,4,2,4,4,2,4,2])") is False
    assert engine.evaluate("AlgoGameEngine.canMove([2,4,2,4,4,2,4,2,2,4,2,4,4,2,4,4])") is True


@pytest.mark.parametrize(
    ("stamp", "week"),
    [
        ("2026-11-01T20:59:59Z", "2026-10-26"),
        ("2026-11-01T21:00:00Z", "2026-11-02"),
        ("2027-01-01T00:00:00Z", "2026-12-28"),
    ],
)
def test_week_starts_on_monday_in_moscow(engine, stamp, week):
    assert engine.evaluate("s=>AlgoGameEngine.weekKey(new Date(s))", stamp) == week


def test_weekly_rewards_cannot_repeat_or_use_old_best(engine):
    result = engine.evaluate("""() => {
      const e=AlgoGameEngine,s=e.blank(),now=new Date('2026-10-31T12:00:00Z');
      e.finish(s,'orbit',7,now);
      const below=e.claim(s,'week','orbit',now);
      e.finish(s,'orbit',8,now);
      const first=e.claim(s,'week','orbit',now),duplicate=e.claim(s,'week','orbit',now);
      const next=new Date('2026-11-02T00:00:00Z');
      const oldBest=e.claim(s,'week','orbit',next);
      e.finish(s,'orbit',8,next);
      return [below,first,duplicate,oldBest,e.claim(s,'week','orbit',next),s.transactions.length];
    }""")
    assert result == [0, 10, 0, 0, 10, 2]


def test_achievements_one_time_and_restore(engine):
    assert (
        engine.evaluate("""() => {
      const e=AlgoGameEngine,s=e.blank();
      if(e.claim(s,'achievement','first')!==0)return false;
      e.finish(s,'debug',8);
      if(e.claim(s,'achievement','debug')!==25)return false;
      const restored=e.normalize(JSON.parse(JSON.stringify(s)));
      if(e.claim(restored,'achievement','debug')!==0)return false;
      return restored.best.debug===8 && e.claim(restored,'achievement','first')===15;
    }""")
        is True
    )


def test_invalid_results_and_corrupted_storage(engine):
    assert (
        engine.evaluate("""() => {
      const e=AlgoGameEngine,s=e.blank();
      e.finish(s,'unknown',100);e.finish(s,'orbit',NaN);e.finish(s,'orbit',-1);
      const clean=e.normalize({version:1,best:{orbit:'hello'},
        weeks:{'bad':{scores:{}}},transactions:'bad'});
      return s.runs===0 && !Object.keys(clean.best).length && !Object.keys(clean.weeks).length;
    }""")
        is True
    )


@pytest.fixture
def arcade(games_browser):
    context = games_browser.new_context(viewport={"width": 390, "height": 844})
    page = context.new_page()
    errors = []
    writes = []
    source = inject_games((STATIC / "index.html").read_text(encoding="utf-8"))

    def route(request):
        path = request.request.url.split("?", 1)[0].removeprefix("http://127.0.0.1:8779")
        if request.request.method not in ("GET", "HEAD"):
            writes.append(path)
            request.fulfill(status=403)
        elif path == "/miniapp":
            request.fulfill(body=source, content_type="text/html")
        elif path.startswith("/miniapp/static/"):
            target = (STATIC / path.removeprefix("/miniapp/static/")).resolve()
            if target.is_relative_to(STATIC.resolve()) and target.is_file():
                request.fulfill(path=str(target))
            else:
                request.fulfill(status=404)
        else:
            request.fulfill(status=404)

    page.route("http://127.0.0.1:8779/**", route)
    page.route("https://st.max.ru/**", lambda r: r.abort())
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(
        "http://127.0.0.1:8779/miniapp?demo=1&demo_role=student&view=games",
        wait_until="networkidle",
    )
    yield page
    context.close()
    assert not errors, errors
    assert not writes, writes


@pytest.mark.parametrize("width", [320, 390, 768, 1440])
def test_every_game_opens_starts_and_exits_without_overflow(arcade, width):
    page = arcade
    page.set_viewport_size({"width": width, "height": 900})
    assert page.locator(".game-card").count() == 10
    assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
    for game in [
        "orbit",
        "evolve",
        "bugs",
        "tower",
        "typing",
        "debug",
        "2048",
        "drop",
        "memory",
        "react",
    ]:
        page.locator(f'.game-card[data-game="{game}"]').click()
        page.locator("#gameStart").click()
        page.wait_for_timeout(50)
        assert page.locator("#gameDialog[open]").count() == 1
        assert page.evaluate(
            "document.querySelector('#gameDialog').scrollWidth<=document.querySelector('#gameDialog').clientWidth"
        )
        page.locator("#gameFinish").click()
        assert page.locator(".game-result").is_visible()
        page.locator(".game-back").click()
    page.locator('[data-games-tab="achievements"]').first.click()
    assert page.locator(".game-achievement").count() == 10
    page.locator('[data-games-tab="rewards"]').first.click()
    assert page.locator(".games-reward-summary").is_visible()


def test_python_real_completion_claim_and_reload(arcade):
    page = arcade
    original = page.evaluate("students.map(s=>s.balance)")
    page.locator('.game-card[data-game="debug"]').click()
    page.locator("#gameStart").click()
    for _ in range(8):
        intro = page.locator(".debug-game h3").inner_text()
        task = page.evaluate("intro=>AlgoGameEngine.tasks.find(t=>t.intro===intro)", intro)
        page.locator(f'[data-line="{task["line"]}"]').click()
        page.locator(f'[data-option="{task["answer"]}"]').click()
        assert page.locator(".debug-feedback").inner_text().startswith("✓ Верно!")
        page.locator("[data-next]").click()
    assert "8 задач" in page.locator(".game-result h3").inner_text()
    page.locator(".game-claim-result").click()
    assert page.locator(".game-claim-result").is_disabled()
    page.locator(".game-back").click()
    page.locator('[data-games-tab="achievements"]').first.click()
    page.locator('[data-claim="achievement"][data-id="debug"]').click()
    page.reload(wait_until="networkidle")
    page.locator('[data-games-tab="rewards"]').first.click()
    assert page.locator(".games-reward-summary strong").inner_text() == "35 AC"
    assert page.locator('[data-claim="week"][data-id="debug"]').is_disabled()
    assert page.evaluate("students.map(s=>s.balance)") == original


def test_typing_input_and_memory_match_are_real(arcade):
    page = arcade
    page.locator('.game-card[data-game="typing"]').click()
    page.locator("#gameStart").click()
    passage = page.locator(".typing-passage").inner_text()
    page.locator(".typing-input").press_sequentially(passage[:20])
    assert page.locator("#gameScore").inner_text() == "20"
    page.locator(".typing-input").press("Backspace")
    assert page.locator("#gameScore").inner_text() == "19"
    page.locator(".game-close").click()
    assert page.locator('.game-card[data-game="typing"]').inner_text().find("19") >= 0
    page.locator('.game-card[data-game="memory"]').click()
    page.locator("#gameStart").click()
    page.locator('[data-card="0"]').click()
    assert page.locator(".memory-grid .flipped").count() == 1
    page.locator('[data-card="1"]').click()
    assert page.locator(".memory-grid .flipped,.memory-grid .matched").count() == 2
    page.locator(".game-close").click()


def test_dropping_identical_objects_really_merges_with_physics(arcade):
    page = arcade
    page.evaluate("Math.random=()=>0.1")
    page.locator('.game-card[data-game="drop"]').click()
    page.locator("#gameStart").click()
    canvas = page.locator("#gameDialog canvas")
    canvas.click(position={"x": canvas.bounding_box()["width"] / 2, "y": 50})
    page.wait_for_timeout(1400)
    canvas.click(position={"x": canvas.bounding_box()["width"] / 2, "y": 50})
    page.wait_for_function("Number(document.querySelector('#gameScore').textContent)>=4")
    assert page.locator(".game-result").count() == 0
    page.locator(".game-close").click()
    assert "Рекорд" in page.locator('.game-card[data-game="drop"]').inner_text()


def test_merging_creatures_and_keyboard_2048(arcade):
    page = arcade
    page.evaluate("Math.random=()=>0.1")
    page.locator('.game-card[data-game="evolve"]').click()
    page.locator("#gameStart").click()
    page.locator('[data-cell="0"]').click()
    page.locator('[data-cell="1"]').click()
    assert page.locator("#gameScore").inner_text() == "8"
    page.locator(".game-close").click()
    page.locator('.game-card[data-game="2048"]').click()
    page.locator("#gameStart").click()
    assert page.locator(".number-cell.n2").count() == 2
    page.keyboard.press("ArrowLeft")
    assert page.locator(".number-cell.n4").count() == 1
    assert page.locator("#gameScore").inner_text() == "4"
    page.locator(".game-close").click()


def test_reaction_false_start_then_green_signal(arcade):
    page = arcade
    page.locator('.game-card[data-game="react"]').click()
    page.locator("#gameStart").click()
    page.locator(".reaction-pad").click()
    assert "Рановато" in page.locator(".reaction-pad").inner_text()
    assert page.locator("#gameScore").inner_text() == "0"
    page.wait_for_selector(".reaction-pad.go")
    page.keyboard.press("Space")
    assert page.locator("#gameScore").inner_text() == "1"
    assert page.locator(".reaction-attempts .done").count() == 1
    page.locator(".game-close").click()


def test_arcade_requires_explicit_local_preview_flag(arcade):
    assert arcade.evaluate("roleViews(state.role).includes('games')")
    arcade.evaluate("window.ALGO_GAMES_PROTOTYPE=false;setView('games')")
    assert arcade.evaluate("state.view") == "dashboard"
