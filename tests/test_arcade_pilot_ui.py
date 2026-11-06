"""Exercise the production lazy loader and advanced spatial layouts in real browsers."""

from pathlib import Path

import pytest

from tests.test_arcade_server import arcade as arcade
from tests.test_arcade_server import browser as browser


def pilot_page(page, allowed=True):
    account = 910001 if allowed else 910003
    source = """<!doctype html><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <link rel="stylesheet" href="/miniapp/static/styles.css"><div id="gamesRoot"></div><script>
      const localDemoHost=false;
      const apiContext={demoMode:false,maxUserId:ACCOUNT,maxWebAppData:'test-launch'};
      const state={hasAccess:true,account:{max_user_id:ACCOUNT,display_name:'Staff'},view:'games'};
      function apiFetch(url,options={}){
        const u=new URL(url,location.origin);
        u.pathname=u.pathname.replace('/api/v1/miniapp/arcade','/preview/arcade');
        return fetch(u,{...options,headers:{...options.headers,'X-Miniapp-Token':'p1'}});
      }
      window.ALGO_ARCADE_PILOT={ids:[910001]};
    </script><script src="/miniapp/static/app-arcade-pilot.js"></script>
    <script>void AlgoArcadePilot.render();</script>""".replace("ACCOUNT", str(account))
    page.route(
        "**/pilot", lambda route: route.fulfill(status=200, content_type="text/html", body=source)
    )
    page.goto("http://127.0.0.1:8779/pilot")


def test_private_pilot_does_not_load_games_for_unlisted_accounts(arcade):
    page, _ = arcade
    pilot_page(page, False)
    assert not page.evaluate("AlgoArcadePilot.canOpen()")
    assert page.evaluate("window.algoGames===undefined")
    assert page.locator("[data-arcade-asset]").count() == 0


def test_private_loader_can_retry_after_one_script_fails(arcade):
    page, _ = arcade
    attempts = []

    def fail_once(route):
        attempts.append(route.request.url)
        if len(attempts) == 1:
            route.abort()
        else:
            route.fallback()

    page.route("**/games-world.js?*", fail_once)
    pilot_page(page)
    page.locator("#gamesRoot>button").wait_for()
    page.locator("#gamesRoot>button").click()
    page.locator(".game-card").first.wait_for()
    assert len(attempts) == 2
    assert page.locator(".game-card").count() == 16


@pytest.mark.parametrize("width", [320, 390, 844, 1440])
def test_private_loader_and_eight_spatial_options_fit_and_timer_does_not_replace_buttons(
    arcade, width
):
    page, _ = arcade
    height = 568 if width == 320 else 600 if width == 390 else 390 if width == 844 else 900
    page.set_viewport_size(dict(width=width, height=height))
    pilot_page(page)
    page.locator(".game-card").first.wait_for()
    assert page.locator(".game-card").count() == 16
    assert page.locator("#gamesPlayer").count() == 0
    assert page.locator(".arcade-pilot-note").is_visible()
    page.locator('.game-card[data-game="react"]').click()
    page.locator('[data-benchmark="spatial"]').click()
    # Render a late-stage state without submitting a synthetic result to the server.
    page.evaluate("""()=>{
      const original=ArcadeBenchmarks.create;
      ArcadeBenchmarks.create=setup=>{
        const w=original(setup);
        for(let i=0;i<21;i++){
          ArcadeBenchmarks.advance(w,12);ArcadeBenchmarks.input(w,{type:'choice',i:w.correct});
        }
        w.tick=w.time=w.since=0;w.until=w.difficulty.seconds*60;return w;
      };
    }""")
    page.locator("[data-bench-start]").click()
    page.locator(".benchmark-spatial-clock").wait_for()
    assert page.locator("[data-bench-choice]").count() == 8
    assert "Этап 4" in page.locator(".benchmark-spatial-clock").inner_text()
    page.locator("[data-bench-choice]").first.evaluate("n=>window.firstSpatialChoice=n")
    page.wait_for_function("document.querySelector('[data-bench-round-time]').textContent==='5 с'")
    assert page.locator("[data-bench-choice]").first.evaluate("n=>n===window.firstSpatialChoice")
    assert page.locator(".benchmark-dialog").evaluate("n=>n.scrollWidth<=n.clientWidth")
    for choice in page.locator("[data-bench-choice]").all():
        box = choice.bounding_box()
        assert box and box["y"] >= 0 and box["y"] + box["height"] <= height
    captures = Path(__file__).parents[1] / ".deploy_tmp/spatial-pilot-screens"
    captures.mkdir(exist_ok=True)
    page.locator(".benchmark-dialog").screenshot(path=str(captures / f"spatial-eight-{width}.png"))
    page.locator("[data-bench-close]").click()
