"""WebKit/Safari pilot boot must not require browser storage in MAX's iframe."""

import pytest

from tests.test_arcade_pilot_ui import pilot_page
from tests.test_arcade_server import arcade as arcade


@pytest.fixture
def browser():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        b = p.webkit.launch()
        yield b
        b.close()


@pytest.mark.parametrize("blocked_storage", [False, True])
def test_pilot_loads_on_webkit_when_iframe_storage_is_unavailable(arcade, blocked_storage):
    page, _ = arcade
    if blocked_storage:
        page.add_init_script("""Object.defineProperty(window,'localStorage',{
          configurable:true,get(){throw new DOMException('Storage is blocked','SecurityError');}
        });""")
    pilot_page(page)
    page.locator(".game-card").first.wait_for()
    assert page.locator(".game-card").count() == 16
    page.locator('.game-card[data-game="sort"]').click()
    page.locator('[data-mode="practice"]').click()
    page.locator(".sort-tubes").wait_for()
