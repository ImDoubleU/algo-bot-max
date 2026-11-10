import pytest
from test_feedback_workspace_ui import feedback_browser as _browser

feedback_browser = _browser

ORDER = """() => ({id: '9998', backendId: 'demo-account-order',
  studentId: students[0].id, student: students[0].name, rawStatus: 'created', total: 200,
  managementVisible: true, createdAt: new Date().toISOString(),
  items: [{id: 'account-item', productId: 'demo-account-product', productName: '80 Robux',
    quantity: 1, totalPrice: 200, fulfillmentType: 'digital_manual',
    recipientField: 'roblox_username', recipientValue: 'Child_2026', issuedCodes: []}],
  statusHistory: []})"""


@pytest.mark.parametrize("width", [390, 1440])
def test_confirm_account_fulfillment_and_customer_receipt(feedback_browser, width):
    browser, base = feedback_browser
    context = browser.new_context(viewport={"width": width, "height": 900})
    page = context.new_page()
    page.route("https://st.max.ru/**", lambda route: route.abort())
    page.goto(base + "/miniapp?demo=1&demo_role=partner_director&view=orders",
              wait_until="networkidle")
    page.evaluate("orders.unshift((" + ORDER + ")());"
                  " state.orderStatusFilter='electronic'; renderAll()")
    assert "Ожидает выполнения" in page.locator("#ordersTable").inner_text()
    page.locator('#ordersTable [data-open-order="demo-account-order"]').first.click()
    assert page.locator("[data-digital-issue-item]").count() == 0
    assert page.locator("[data-issue-digital-order]").inner_text() == "Подтвердить выполнение"
    page.locator("[data-issue-digital-order]").click()
    assert "Child_2026" in page.locator("#confirmationDialogMessage").inner_text()
    page.locator("#cancelConfirmationButton").click()
    assert page.evaluate("orders[0].rawStatus") == "created"
    page.locator("[data-issue-digital-order]").click()
    page.locator("#confirmConfirmationButton").click()
    page.wait_for_function("orders[0].rawStatus === 'issued_to_student'")
    assert page.locator("[data-issue-digital-order]").count() == 0
    assert "Заказ выполнен" in page.locator("#orderDialogContent").inner_text()
    assert page.locator(".digital-delivery").count() == 0
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    context.close()

    context = browser.new_context(viewport={"width": width, "height": 900})
    page = context.new_page()
    page.route("https://st.max.ru/**", lambda route: route.abort())
    page.goto(base + "/miniapp?demo=1&demo_role=student&view=orders", wait_until="networkidle")
    page.evaluate("const receipt=(" + ORDER + ")(); receipt.rawStatus='issued_to_student';"
                  " orders.unshift(receipt); openOrderDetails(receipt.backendId)")
    assert "Заказ выполнен" in page.locator("#orderDialogContent").inner_text()
    assert "Child_2026" in page.locator("#orderDialogContent").inner_text()
    assert "Код" not in page.locator("#orderDialogContent").inner_text()
    assert page.locator("[data-issue-digital-order]").count() == 0
    context.close()


def test_manager_can_open_order_from_other_city(feedback_browser):
    browser, base = feedback_browser
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    page.route("https://st.max.ru/**", lambda route: route.abort())
    page.goto(base + "/miniapp?demo=1&demo_role=partner_director&view=orders",
              wait_until="networkidle")
    page.evaluate("""() => {
      apiContext.tenantSlug='n-novgorod'; apiContext.demoMode=false;
      state.availableTenants=[{tenant_slug:'n-novgorod'}, {tenant_slug:'bor'}];
      state.canManageTenants=true; state.orderViewMode='management';
      switchTenant=async slug => {window.switchedOrderCity=slug; apiContext.tenantSlug=slug;};
    }""")
    page.evaluate("const foreign=(" + ORDER + ")(); foreign.studentId='foreign-student';"
                  " foreign.tenantSlug='bor'; foreign.schoolName='Бор';"
                  " orders.unshift(foreign); state.orderStatusFilter='electronic'; renderAll()")
    assert page.evaluate("ordersForCurrentRole().some(o => o.backendId==='demo-account-order')")
    card = page.locator('#ordersTable [data-open-order="demo-account-order"]').first
    assert "Бор" in card.locator("xpath=ancestor::article").inner_text()
    card.click()
    page.wait_for_function("window.switchedOrderCity==='bor'")
    assert page.locator("#orderDialog").is_visible()
    assert "Бор" in page.locator("#orderDialogContent").inner_text()
    assert page.locator("[data-issue-digital-order]").is_visible()
    context.close()
