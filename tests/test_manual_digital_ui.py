import pytest
from test_feedback_workspace_ui import feedback_browser as _browser

feedback_browser = _browser


@pytest.mark.parametrize("width", [390, 1440])
def test_electronic_tab_pending_code_and_editor_modes(feedback_browser, width):
    browser, base = feedback_browser
    context = browser.new_context(viewport={"width": width, "height": 1000})
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route("https://st.max.ru/**", lambda route: route.abort())
    page.goto(base + "/miniapp?demo=1&demo_role=partner_director&view=orders",
              wait_until="networkidle")
    page.evaluate("""() => {
      products.unshift({id: 'demo-manual', name: 'Код под заказ', category: 'Игры',
        fulfillmentType: 'digital_manual', price: 200, status: 'active', warehouses: []});
      orders.unshift({id: '9999', backendId: 'demo-manual-order', studentId: students[0].id,
        student: students[0].name, item: 'Код под заказ', rawStatus: 'created', total: 200,
        createdAt: new Date().toISOString(), items: [{id: 'manual-item', productId: 'demo-manual',
          productName: 'Код под заказ', quantity: 1, totalPrice: 200,
          fulfillmentType: 'digital_manual', issuedCodes: []}], statusHistory: []});
      state.orderStatusFilter = 'all'; renderAll();
    }""")
    page.locator('[data-order-status="electronic"]').click()
    assert "Ожидает кода" in page.locator("#ordersTable").inner_text()
    assert page.evaluate(
        "orderMatchesNamedFilter("
        "orders.find(o => o.backendId === 'demo-manual-order'), 'reserved')",
    ) is False
    assert page.evaluate("fulfillmentOrdersForStage('assign').every(o => !orderIsDigital(o))")
    page.locator('#ordersTable [data-open-order="demo-manual-order"]').first.click()
    assert page.locator("[data-digital-issue-item]").is_visible()
    assert page.locator("[data-order-warehouse]").count() == 0
    page.locator("[data-digital-issue-item]").fill("LOCAL-CODE-ONE")
    page.locator("[data-issue-digital-order]").click()
    page.locator("#confirmConfirmationButton").click()
    page.wait_for_function(
        "orders.find(o => o.backendId === 'demo-manual-order').rawStatus === 'issued_to_student'",
    )
    assert "LOCAL-CODE-ONE" in page.locator("#orderDialogContent").inner_text()
    assert page.locator("[data-issue-digital-order]").count() == 0
    page.locator("#closeOrderDialogButton").click()
    page.evaluate("""() => {
      state.adminTab = 'products'; state.productEditorOpen = true;
      state.editingProductId = ''; setView('admin'); renderAll();
    }""")
    page.locator("#productFulfillmentType").select_option("digital_manual")
    assert not page.locator("#productInstantDelivery").is_checked()
    assert page.locator(".product-code-editor").is_hidden()
    assert page.locator(".product-inventory-editor").is_hidden()
    page.locator("#productInstantDelivery").check()
    assert page.locator("#productNewCodes").is_visible()
    page.locator("#productInstantDelivery").uncheck()
    assert page.locator("#productNewCodes").is_hidden()
    assert not errors
    context.close()
