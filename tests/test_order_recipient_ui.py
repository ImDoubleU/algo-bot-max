from pathlib import Path

import pytest
from test_feedback_workspace_ui import feedback_browser as _browser

feedback_browser = _browser


@pytest.mark.parametrize("width", [390, 1440])
def test_checkout_collects_only_configured_recipient(feedback_browser, width):
    browser, base = feedback_browser
    context = browser.new_context(viewport={"width": width, "height": 844})
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route("https://st.max.ru/**", lambda route: route.abort())
    page.goto(base + "/miniapp?demo=1&demo_role=student&view=store", wait_until="networkidle")
    for field, value in [("steam_login", "player_one"), ("roblox_username", "Child_2026"),
                         ("phone", "+7 (999) 123-45-67")]:
        page.evaluate("""field => {
          products.push({id: 'demo-recipient-' + field, name: 'Электронный товар',
            price: 50, fulfillmentType: 'digital_manual', recipientField: field, status: 'active'});
          state.cart.clear(); state.cart.set('demo-recipient-' + field,
            {productId: 'demo-recipient-' + field, quantity: 1});
          selectedStudent().balance = 1000; setView('store'); renderCart(); openCheckoutDialog();
        }""", field)
        input = page.locator("[data-checkout-recipient]")
        assert input.count() == 1
        assert page.locator("#checkoutDialog .checkout-guidance").count() == 0
        assert input.get_attribute("type") == ("tel" if field == "phone" else None)
        before = page.evaluate("orders.length")
        page.locator("#confirmOrderButton").click()
        assert page.evaluate("orders.length") == before
        assert page.locator("#checkoutDialog").is_visible()
        input.fill(value)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        if field == "phone":
            folder = Path(".deploy_tmp/product-recipient-release")
            folder.mkdir(parents=True, exist_ok=True)
            page.locator("#checkoutDialog").screenshot(path=str(folder / f"checkout-{width}.png"))
        page.locator("#confirmOrderButton").click()
        assert page.locator("#checkoutDialog").is_hidden()
        item = page.evaluate("orders[0].items[0]")
        assert item["recipientField"] == field
        assert item["recipientValue"] == ("+79991234567" if field == "phone" else value)
        page.evaluate("openOrderDetails(orders[0].backendId)")
        assert item["recipientValue"] in page.locator("#orderDialogContent").inner_text()
        page.locator("#closeOrderDialogButton").click()
    assert not errors
    context.close()
