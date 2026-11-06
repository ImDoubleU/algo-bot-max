"""Phone playfields and their controls must fit the visible browser viewport."""

import json
from pathlib import Path

import pytest

from app.services.arcade import GAMES
from tests.test_arcade_pilot_ui import pilot_page
from tests.test_arcade_server import arcade as arcade


@pytest.fixture(params=["webkit", "chromium"])
def browser(request):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        b = p.webkit.launch() if request.param == "webkit" else p.chromium.launch(channel="msedge")
        yield b
        b.close()


@pytest.mark.parametrize("arcade", ["touch"], indirect=True)
@pytest.mark.parametrize("size", [(320, 568), (390, 600), (844, 390)])
def test_phone_menus_and_playfields_stay_inside_visible_window(arcade, size, request):
    page, _ = arcade
    page.set_viewport_size(dict(zip(("width", "height"), size, strict=True)))
    pilot_page(page)
    page.locator(".game-card").first.wait_for()
    page.on("dialog", lambda d: d.accept())
    captures = Path(__file__).parents[1] / ".deploy_tmp/mobile-games"
    captures.mkdir(exist_ok=True)
    metrics = {}
    for game in GAMES:
        page.locator(f'.game-card[data-game="{game}"]').click()
        if game == "react":
            page.locator("[data-benchmark-react]").click()
        if game == "kopatych":
            page.locator("[data-menu-levels]").click()
            page.locator("[data-farm-sprint]").first.click()
        name = f"{request.node.callspec.id}-{game}"
        page.locator(".game-dialog").screenshot(path=str(captures / f"{name}-menu.png"))
        for action in page.locator(".arcade-menu-action").all():
            box = action.bounding_box()
            assert box and box["y"] >= 0 and box["y"] + box["height"] <= size[1], (game, box)
        page.locator('[data-mode="practice"]').click()
        if page.locator("[data-practice-start]").count():
            page.locator("[data-practice-start]").first.click()
        if game == "typing":
            page.locator(".typing-input").press_sequentially("a")
        page.wait_for_function("document.querySelector('#gameClock b')?.textContent.length>0")
        assert page.locator("#gameClock").is_visible(), game
        page.wait_for_timeout(120)
        m = page.locator(".game-dialog").evaluate("""d=>{
          const s=d.querySelector('.game-stage'), f=s.querySelector('.arcade-canvas-frame');
          const box=n=>{const r=n.getBoundingClientRect();
            return {x:r.x,y:r.y,w:r.width,h:r.height}};
          return {dialog:box(d),stage:box(s),canvas:f&&box(f),
            overflow:d.scrollWidth>d.clientWidth,scroll:s.scrollHeight-s.clientHeight};
        }""")
        metrics[game] = m
        assert not m["overflow"], (game, m)
        assert m["dialog"]["y"] >= 0, (game, m)
        assert m["dialog"]["y"] + m["dialog"]["h"] <= size[1] + 1, (game, m)
        assert m["stage"]["h"] >= 120, (game, m)
        if m["canvas"]:
            f, s = m["canvas"], m["stage"]
            assert f["y"] >= s["y"] - 1 and f["y"] + f["h"] <= s["y"] + s["h"] + 1, (game, m)
            assert m["scroll"] <= 1, (game, m)
        page.locator(".game-dialog").screenshot(path=str(captures / f"{name}.png"))
        page.locator(".game-close").click()
        page.locator(".game-dialog").wait_for(state="detached")
    (captures / f"{request.node.callspec.id}.json").write_text(
        json.dumps(metrics, indent=2), encoding="utf-8"
    )


@pytest.mark.parametrize("arcade", ["touch"], indirect=True)
def test_late_memory_and_sort_boards_fit_small_phone(arcade):
    page, _ = arcade
    page.set_viewport_size({"width": 320, "height": 568})
    pilot_page(page)
    page.locator(".game-card").first.wait_for()
    page.on("dialog", lambda d: d.accept())
    # Layout-only late boards in an isolated store; never submit synthetic scores.
    page.evaluate("""()=>{
      const create=ArcadeWorld.create;
      ArcadeWorld.create=s=>{
        const w=create(s);
        if(s.game==='memory')w.cards=Array.from({length:24},(_,i)=>i%12);
        if(s.game==='sort')w.tubes=Array.from({length:10},(_,i)=>i<8?[i,i,i,i]:[]);
        return w;
      };
    }""")
    for game, board in [("memory", ".memory-grid"), ("sort", ".sort-tubes")]:
        page.locator(f'.game-card[data-game="{game}"]').click()
        page.locator('[data-mode="practice"]').click()
        page.locator(board).wait_for()
        page.wait_for_timeout(150)
        assert page.locator(".game-stage").evaluate("s=>s.scrollHeight<=s.clientHeight+1"), game
        page.locator(".game-close").click()
        page.locator(".game-dialog").wait_for(state="detached")
