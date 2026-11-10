"""Illustrations load from local assets and preserve the common library layout."""

import pytest

from tests.test_arcade_server import arcade as arcade
from tests.test_arcade_server import browser as browser


@pytest.mark.parametrize("width", [320, 768, 1440])
def test_all_game_covers_load_and_cards_match_the_case_format(arcade, width):
    page, _ = arcade
    page.set_viewport_size(dict(width=width, height=900))
    images = page.locator(".game-card-art > .arcade-cover")
    assert images.count() == 16
    sources = images.evaluate_all("nodes=>nodes.map(n=>n.src)")
    assert len(set(sources)) == 16
    assert page.locator('.game-card-bottom,.game-reward,.case-library-card>span>span').count() == 0
    for title in page.locator('.game-card h3,.case-library-card h3').all():
        assert title.evaluate('n=>parseFloat(getComputedStyle(n).fontSize)') >= 28
    for image in images.all():
        image.scroll_into_view_if_needed()
        image.evaluate("n=>n.decode()")
        assert image.evaluate("n=>n.complete&&n.naturalWidth>0")
    heights = page.locator(".game-card-shell,.case-library-card").evaluate_all(
        "nodes=>nodes.map(n=>n.getBoundingClientRect().height)"
    )
    assert max(heights)-min(heights) <= 2
    page.locator('.game-card[data-game="drop"]').click()
    cover = page.locator(".arcade-menu-art .arcade-cover")
    cover.evaluate("n=>n.decode()")
    assert "/covers/drop-" in cover.get_attribute("src")
    background = page.locator(".game-stage").evaluate("n=>getComputedStyle(n).backgroundColor")
    assert background == "rgb(14, 31, 46)"
    assert page.locator(".arcade-menu-action").count() == 4
    page.locator(".game-close").click()
