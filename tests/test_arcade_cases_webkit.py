"""MAX iframe storage can be unavailable on Safari; the server owns the collection."""

import pytest

from app.services.arcade_cases import CaseStore
from tests.test_arcade_server import arcade as arcade
from tests.test_arcade_webkit import browser as browser


@pytest.mark.parametrize("blocked_storage", [False, True])
def test_cases_open_on_webkit_and_keep_saved_items_without_browser_storage(arcade, blocked_storage):
    page, store = arcade
    page.set_viewport_size(dict(width=390, height=600))
    page.emulate_media(reduced_motion="reduce")
    if blocked_storage:
        page.add_init_script("""Object.defineProperty(window,'localStorage',{
          configurable:true,get(){throw new DOMException('Storage blocked','SecurityError');}
        });""")
        page.reload()
    page.locator("[data-cases]").click()
    page.locator("[data-case-open]").click()
    page.locator(".case-result:not([hidden])").wait_for()
    assert page.locator("#casesDialog").evaluate("d=>d.scrollWidth<=d.clientWidth")
    page.locator("[data-case-close]").click()
    page.locator("[data-cases]").click()
    page.locator(".case-toolbar [data-case-tab=collection]").click()
    assert page.locator(".case-inventory-item.is-owned").count() == 1
    assert CaseStore(store).get("p1")["opens"] == 1
    page.locator("[data-case-close]").click()
