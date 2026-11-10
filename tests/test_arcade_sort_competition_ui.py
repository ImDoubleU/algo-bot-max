"""Ball Sort transitions must own pointer, drag, keyboard and focus on phones too."""

from pathlib import Path

import pytest

from tests.test_arcade_mobile import browser as browser
from tests.test_arcade_server import arcade as arcade
from tests.test_arcade_server import finish_naturally

CAPTURES = Path(__file__).parents[1] / ".deploy_tmp/sort-race-20261110"


@pytest.mark.parametrize("size", [(320, 568), (844, 390), (1440, 900)])
def test_race_rules_are_readable_and_only_start_creates_a_session(arcade, size, request):
    page, store = arcade
    page.set_viewport_size(dict(zip(("width", "height"), size, strict=True)))
    page.locator('.game-card[data-game="sort"]').click()
    page.locator('[data-mode="ranked"]').click()
    page.locator("[data-sort-race-start]").wait_for()
    with store.db() as db:
        assert db.execute("SELECT COUNT(*) FROM arcade_sessions").fetchone()[0] == 0
    assert page.locator(".sort-race-intro h3").inner_text() == "5 задач"
    assert page.locator(".sort-race-route>span").count() == 5
    assert page.locator(".game-dialog").evaluate("d=>d.scrollWidth<=d.clientWidth")
    box = page.locator("[data-sort-race-start]").bounding_box()
    assert box and box["y"] + box["height"] <= size[1]
    CAPTURES.mkdir(parents=True, exist_ok=True)
    page.locator(".game-dialog").screenshot(path=str(CAPTURES / f"{request.node.name}-rules.png"))
    page.locator(".game-menu-back").click()
    page.locator('[data-mode="ranked"]').click()
    page.locator("[data-sort-race-start]").click()
    page.locator(".sort-tubes").wait_for()
    page.wait_for_function("document.querySelector('#gameClock b')?.textContent.length>0")
    assert page.locator(".sort-meta b").inner_text() == "Задача 1 из 5"
    assert page.locator(".arcade-live-goal>span").inner_text() == "Решено 0 из 5 задач"
    with store.db() as db:
        assert db.execute("SELECT COUNT(*) FROM arcade_sessions").fetchone()[0] == 1
    page.locator(".game-close").click()


@pytest.mark.parametrize("arcade", ["touch"], indirect=True)
def test_completed_board_cannot_be_selected_or_dragged_and_next_has_focus(arcade, request):
    page, _ = arcade
    page.set_viewport_size({"width": 390, "height": 600})
    # An isolated layout fixture uses the actual game loop and controls; no ranked submission.
    page.evaluate("""()=>{
      const create=ArcadeWorld.create;ArcadeWorld.create=setup=>{
        const w=create(setup);if(setup.game==='sort'){
          w.tubes=[[0,0,0],[1,1,1,1],[0],[]];
          w.sortStart=w.tubes.map(t=>t.slice());window.sortProbe=w;
        }return w;
      };
    }""")
    page.locator('.game-card[data-game="sort"]').click()
    page.locator('[data-mode="practice"]').click()
    page.locator('[data-tube="2"]').click()
    page.locator('[data-tube="0"]').click()
    page.locator("[data-sort-next]").wait_for()
    before = page.evaluate("JSON.stringify(sortProbe.tubes)")
    assert page.locator(".sort-tubes").get_attribute("inert") is not None
    assert page.locator(".sort-tubes button:disabled").count() == 4
    assert page.locator("[data-sort-next]").evaluate("n=>n===document.activeElement")
    page.keyboard.press("Digit1")
    page.evaluate("""()=>{
      const tube=document.querySelector('[data-tube="0"]');tube.click();
      tube.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,pointerId:1}));
      tube.dispatchEvent(new PointerEvent('pointermove',{bubbles:true,pointerId:1,clientX:100}));
      tube.dispatchEvent(new PointerEvent('pointerup',{bubbles:true,pointerId:1,clientX:100}));
    }""")
    assert page.evaluate("sortProbe.selectedTube") == -1
    assert page.evaluate("JSON.stringify(sortProbe.tubes)") == before
    CAPTURES.mkdir(parents=True, exist_ok=True)
    page.locator(".game-dialog").screenshot(path=str(CAPTURES / f"{request.node.name}-win.png"))
    page.keyboard.press("Enter")
    page.wait_for_function("sortProbe.tubes.length===6&&!sortProbe.sortWon")
    assert page.locator(".sort-tubes button:disabled").count() == 0
    assert page.locator(".sort-meta b").inner_text() == "Уровень 2"
    page.locator(".game-close").click()


def test_timeout_reaches_real_results_and_can_start_another_race(arcade):
    page, store = arcade
    page.locator('.game-card[data-game="sort"]').click()
    page.locator('[data-mode="ranked"]').click()
    page.locator("[data-sort-race-start]").click()
    page.wait_for_function("document.querySelector('#gameClock b')?.textContent.length>0")
    finish_naturally(page, store, seconds=601)
    assert page.locator(".sort-race-result>p").first.inner_text() == "Время вышло"
    assert page.locator(".sort-race-result h3").inner_text() == "0\nиз 5"
    assert page.locator("[data-analysis]").count() == 1
    page.locator("[data-again]").click()
    page.locator(".sort-tubes").wait_for()
    page.locator(".game-close").click()


def test_five_real_puzzles_finish_in_ui_and_server_accepts_identical_result(arcade, request):
    page, store = arcade
    page.emulate_media(reduced_motion="reduce")
    page.evaluate("""()=>{
      const create=ArcadeWorld.create,now=performance.now.bind(performance);
      window.sortTimeOffset=0;performance.now=()=>now()+sortTimeOffset;
      ArcadeWorld.create=s=>{const w=create(s);if(s.game==='sort')window.sortProbe=w;return w;};
    }""")
    offset = [0]
    previous_clock = store.clock
    store.clock = lambda: previous_clock() + offset[0]
    page.locator('.game-card[data-game="sort"]').click()
    page.locator('[data-mode="ranked"]').click()
    page.locator("[data-sort-race-start]").click()
    page.wait_for_function("document.querySelector('#gameClock b')?.textContent.length>0")

    def advance():
        offset[0] += 1
        page.evaluate("sortTimeOffset+=1000")

    for level in range(5):
        moves = page.evaluate("sortProbe.sortSolution")
        for move in moves:
            advance()
            page.wait_for_function("!!document.querySelector('.sort-tubes button:not(:disabled)')")
            page.evaluate(
                """a=>{
              document.querySelector(`[data-tube="${a.from}"]`).click();
              document.querySelector(`[data-tube="${a.to}"]`).click();
            }""",
                move,
            )
        if level < 4:
            advance()
            page.locator("[data-sort-next]").click()
    page.locator(".sort-race-result").wait_for()
    page.locator("[data-again]").wait_for()
    assert page.locator(".sort-race-result>p").first.inner_text() == "Все задачи решены!"
    assert page.locator(".sort-race-result h3").inner_text() == "5\nиз 5"
    assert page.locator(".arcade-reward-receipt").is_visible()
    assert store.profile("p1")["runs"][0]["accepted"]
    assert store.board("sort", viewer="p1")["rows"][0]["result"] == 5
    CAPTURES.mkdir(parents=True, exist_ok=True)
    page.locator(".game-dialog").screenshot(path=str(CAPTURES / f"{request.node.name}-result.png"))
    page.locator("[data-back]").click()
