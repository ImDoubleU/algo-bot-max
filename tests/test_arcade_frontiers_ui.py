"""Actual menus, pointer/keyboard controls and case filters on small viewports."""

# ruff: noqa: E501 -- embedded browser geometry probes.
import os
from pathlib import Path

import pytest

from tests.test_arcade_server import arcade as arcade

CAPTURES = Path(__file__).resolve().parents[1] / ".deploy_tmp/frontiers-20261114"


@pytest.fixture(params=["chromium", "webkit"])
def browser(request):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        b = getattr(p, request.param).launch(
            **({"channel": "msedge"} if os.name == "nt" and request.param == "chromium" else {})
        )
        yield b
        b.close()


@pytest.mark.parametrize("arcade", ["touch"], indirect=True)
@pytest.mark.parametrize("size", [(320, 568), (390, 844), (844, 390), (1440, 1000)])
def test_new_games_have_levels_and_readable_playfields(arcade, size):
    page, _ = arcade
    page.set_viewport_size(dict(width=size[0], height=size[1]))
    CAPTURES.mkdir(exist_ok=True)
    for game in ["ocean", "slap", "plane", "menagerie", "evolve"]:
        page.locator(f'.game-card[data-game="{game}"]').click()
        page.locator("[data-menu-levels]").click()
        assert page.locator("[data-journey-stage]").count() == 24
        page.locator(".game-menu-back").click()
        page.locator('[data-mode="practice"]').click()
        page.wait_for_selector(".arcade-countdown", state="detached")
        page.locator(".frontier-field canvas").wait_for()
        if game == "plane":
            page.locator("[data-launch]").click()
        canvas = page.locator(".frontier-field canvas")
        r = canvas.bounding_box()
        assert r and r["width"] > 140 and r["height"] > 100
        ratio = canvas.evaluate("c=>c.width/c.height")
        assert abs(r["width"] / r["height"] - ratio) < 0.02, (
            game,
            canvas.evaluate(
                "c=>[c,c.parentElement,c.closest('.game-stage')].map(n=>{const r=n.getBoundingClientRect(),s=getComputedStyle(n);return {w:r.width,h:r.height,style:n.style.cssText,max:s.maxHeight,min:s.minHeight,display:s.display}})"
            ),
        )
        assert page.locator("#gameDialog").evaluate("d=>d.scrollWidth<=d.clientWidth")
        assert page.locator(".arcade-live-goal").is_hidden()
        if game == "evolve":
            canvas.click(position=dict(x=r["width"] * 50 / 360, y=r["height"] * 305 / 430))
        else:
            canvas.focus()
            page.keyboard.down("ArrowUp")
            page.wait_for_timeout(80)
            page.keyboard.up("ArrowUp")
        if size[0] == 390:
            page.locator("#gameDialog").screenshot(path=str(CAPTURES / f"{game}-mobile.png"))
        page.locator(".game-close").click()


def test_case_collection_filtering_pagination_and_prices(arcade):
    page, store = arcade
    page.emulate_media(reduced_motion="reduce")
    page.locator("[data-cases]").click()
    assert "300" in page.locator(".case-wallet").inner_text()
    assert page.locator("[data-case-select]").count() == 20
    page.locator("[data-case-open]").click()
    page.locator(".case-result:not([hidden])").wait_for()
    assert "250" in page.locator(".case-wallet").inner_text()
    page.locator(".case-toolbar [data-case-tab=collection]").click()
    assert page.locator(".case-inventory-item").count() == 24
    page.locator("[data-case-filter=collection]").select_option("neon")
    assert page.locator(".case-inventory-item").count() == 20
    contrast = page.locator("[data-case-filter=collection]").evaluate("""n=>{
      const s=getComputedStyle(n),lum=value=>{const c=value.match(/[\\d.]+/g).slice(0,3).map(v=>{
        v=Number(v)/255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4;
      });return c[0]*.2126+c[1]*.7152+c[2]*.0722;};
      const a=lum(s.color),b=lum(s.backgroundColor);return (Math.max(a,b)+.05)/(Math.min(a,b)+.05);
    }""")
    assert contrast >= 4.5
    page.locator("[data-case-filter=rarity]").select_option("legendary")
    assert page.locator(".case-inventory-item").count() == 4
    page.locator("[data-case-filter=search]").fill("not-an-item")
    assert page.locator(".case-inventory-item").count() == 0
    assert page.locator(".case-empty").is_visible()
    assert page.locator("#casesDialog").evaluate("d=>d.scrollWidth<=d.clientWidth")
    page.locator("[data-case-close]").click()


@pytest.mark.parametrize("arcade", ["touch"], indirect=True)
def test_joystick_release_records_stop_and_boost_is_real(arcade):
    page, store = arcade
    events = []
    page.on(
        "request", lambda r: events.append(r.post_data_json) if r.url.endswith("/finish") else None
    )
    page.locator('.game-card[data-game="ocean"]').click()
    page.locator('[data-mode="practice"]').click()
    page.wait_for_selector(".arcade-countdown", state="detached")
    stick = page.locator(".frontier-stick")
    r = stick.bounding_box()
    page.mouse.move(r["x"] + r["width"] / 2, r["y"] + r["height"] / 2)
    page.mouse.down()
    page.mouse.move(r["x"] + r["width"] / 2, r["y"] + 8, steps=4)
    page.wait_for_timeout(80)
    page.mouse.up()
    page.locator(".frontier-action").tap()
    page.wait_for_timeout(80)
    assert page.locator(".frontier-action").is_disabled()
    # Navigation submits the trace through the same pagehide recovery path used in MAX.
    page.evaluate("window.dispatchEvent(new Event('pagehide'))")
    page.wait_for_timeout(250)
    assert events
    actions = events[-1]["actions"]
    assert any(a["type"] == "steer" and a["y"] < 0 for a in actions)
    assert any(a["type"] == "steer" and a["x"] == a["y"] == 0 for a in actions)
    assert any(a["type"] == "ability" for a in actions)
