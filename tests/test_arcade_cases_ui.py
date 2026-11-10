"""Case opening, storage recovery and phone layout through the actual miniapp."""

from pathlib import Path

import pytest

from app.services.arcade_cases import CaseStore
from tests.test_arcade_server import arcade as arcade
from tests.test_arcade_server import browser as browser


@pytest.mark.parametrize("width", [320, 390, 1440])
def test_case_open_and_collection_survive_reopen_without_ac(arcade, width):
    page, store = arcade
    page.set_viewport_size(dict(width=width, height=850))
    page.emulate_media(reduced_motion="reduce")
    page.locator("[data-cases]").click()
    page.locator("[data-case-open]").click()
    page.locator(".case-result:not([hidden])").wait_for()
    assert CaseStore(store).get("p1")["opens"] == 1
    winner = CaseStore(store).get("p1")["history"][0]["item"]
    pointed = page.locator(".case-roll-window").evaluate("""viewport=>{
      const center=viewport.getBoundingClientRect().left+viewport.clientWidth/2;
      return [...viewport.querySelectorAll('[data-case-loot]')].sort((a,b)=>{
        const distance=n=>Math.abs(n.getBoundingClientRect().left+n.offsetWidth/2-center);
        return distance(a)-distance(b);
      })[0].dataset.caseLoot;
    }""")
    assert pointed == winner
    assert store.profile("p1")["balance"] == 0
    assert page.locator("#casesDialog").evaluate("n=>n.scrollWidth<=n.clientWidth")
    assert page.locator(".case-result").inner_text().find("НОВАЯ НАХОДКА") >= 0
    page.locator(".case-result").scroll_into_view_if_needed()
    page.wait_for_function(
        "[...document.querySelectorAll('.case-result img')].every(n=>n.complete&&n.naturalWidth>0)"
    )
    page.locator(".case-result [data-case-tab=collection]").click()
    page.locator(".case-inventory-item.is-owned button").click()
    page.locator(".case-showcase").wait_for()
    captures = Path(__file__).parents[1] / ".deploy_tmp/arcade-audit-20261110"
    page.locator("#casesDialog").screenshot(path=str(captures / f"cases-collection-{width}.png"))
    page.locator("[data-case-close]").click()
    page.locator("[data-cases]").click()
    page.locator(".case-toolbar [data-case-tab=collection]").click()
    assert page.locator(".case-inventory-item.is-owned").count() == 1
    assert page.locator(".case-showcase").is_visible()
    page.locator("[data-case-close]").click()


def test_lost_case_response_retries_the_same_draw_once(arcade):
    page, store = arcade
    page.emulate_media(reduced_motion="reduce")
    page.locator("[data-cases]").click()

    def lose_response(route):
        body = route.request.post_data_json
        CaseStore(store).act("p1", body["id"], body["action"], body["item"])
        route.abort("failed")

    page.route("**/cases/actions", lose_response, times=1)
    page.locator("[data-case-open]").click()
    page.locator("[data-case-retry]").wait_for()
    assert CaseStore(store).get("p1")["opens"] == 1
    page.locator("[data-case-retry]").click()
    page.locator(".case-result:not([hidden])").wait_for()
    assert CaseStore(store).get("p1")["opens"] == 1
    assert page.evaluate("localStorage.getItem('arcade-cases-pending:p1')") is None
    page.locator("[data-case-close]").click()


def test_cases_and_other_auxiliary_windows_close_when_leaving_games(arcade):
    page, _ = arcade
    page.locator("[data-cases]").click()
    page.locator("[data-case-open]").wait_for()
    page.evaluate("algoGames.close()")
    assert page.locator("#casesDialog").count() == 0
    page.locator('.game-card[data-game="hill"]').click()
    page.locator("[data-menu-levels]").click()
    page.locator(".hill-garage-dialog").wait_for()
    page.evaluate("algoGames.close()")
    assert page.locator(".hill-garage-dialog").count() == 0
