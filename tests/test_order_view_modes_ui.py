import pytest
from test_feedback_workspace_ui import feedback_browser as _browser

feedback_browser = _browser


@pytest.mark.parametrize("width", [320, 390, 1440])
@pytest.mark.parametrize("manager", ["superadmin", "admin", "partner_director", "curator"])
def test_combined_roles_switch_order_views_without_losing_permissions(
    feedback_browser, width, manager,
):
    browser, base = feedback_browser
    context = browser.new_context(viewport={"width": width, "height": 1000})
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route("https://st.max.ru/**", lambda route: route.abort())
    page.goto(base + "/miniapp?demo=1&demo_role=admin&view=orders", wait_until="networkidle")
    page.evaluate("""(manager) => {
      state.staffRoles = [manager, 'teacher'];
      students.forEach(s => { s.staffOrderVisible = true; });
      orders = [
        { id: '101', backendId: 'own', studentId: students[0].id, teacherVisible: true,
          rawStatus: 'reserved', student: 'Свой ученик', item: 'Свой товар', items: [{
            id: 'item1', productId: products[0].id, quantity: 1, fulfillmentType: 'warehouse'}]},
        { id: '102', backendId: 'foreign', studentId: students[1].id, teacherVisible: false,
          rawStatus: 'awaiting_delivery', student: 'Чужой ученик', item: 'Чужой товар', items: [{
            id: 'item2', productId: products[0].id, quantity: 1, fulfillmentType: 'warehouse'}]},
        { id: '103', backendId: 'historical', studentId: students[1].id, teacherVisible: true,
          rawStatus: 'delivered_to_venue', student: 'Ранее свой ученик', item: 'Старый заказ',
          items: [{
            id: 'item3', productId: products[0].id, quantity: 1, fulfillmentType: 'warehouse',
            warehouseId: 'local-warehouse'}]},
      ];
      state.orderViewMode = 'management'; state.orderStatusFilter = 'fulfillment_assign';
      renderOrders(); refreshIcons();
    }""", manager)
    assert page.locator("#orderViewSwitcher").is_visible()
    page.locator('[data-order-view-mode="teacher"]').click()
    assert page.evaluate("state.orderStatusFilter") == "all"
    assert page.locator('[data-order-status="fulfillment_assign"]').count() == 0
    assert "Готовится для ваших учеников" in page.locator("#orderFulfillmentSummary").inner_text()
    assert page.evaluate("ordersForCurrentRole().map(o => o.backendId)") == ["own", "historical"]
    assert "Чужой ученик" not in page.locator("#ordersView").inner_text()
    assert page.locator('#ordersTable [data-order-id="own"]').count() == 0
    assert page.locator('[data-pending-order-id="own"]').count() == 1
    assert page.locator('#ordersTable [data-order-id="historical"]').count() == 1
    assert page.locator(".teacher-order-group-heading h3").all_text_contents() == ["К выдаче"]
    assert page.locator("#fulfillmentOrderSearch").count() == 0
    assert page.locator("#orderSearch").is_visible()
    page.locator("#orderSearch").fill("101")
    assert page.locator('[data-pending-order-id="own"]').count() == 1
    assert page.locator("#ordersTable .order-card").count() == 0
    assert page.locator("#ordersTable .empty-state").count() == 0
    page.locator("#orderSearch").fill("no-such-order")
    assert page.locator("#orderFulfillmentSummary").is_hidden()
    assert page.locator("#ordersTable .empty-state").count() == 1
    page.locator("#orderSearch").fill("")
    assert page.evaluate("state.staffRoles") == [manager, "teacher"]
    assert page.evaluate("canCancelOrder(orders[0])") is False
    assert page.evaluate("canTransferOrder(orders[2])") is True
    assert page.evaluate(
        "JSON.parse(localStorage.getItem(preferencesStorageKey())).orderViewMode",
    ) == "teacher"
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.evaluate("state.view = 'home'")
    assert page.evaluate("ordersForCurrentRole().length") == 3
    page.evaluate("state.view = 'orders'")
    page.locator('[data-order-view-mode="management"]').click()
    assert page.evaluate("ordersForCurrentRole().length") == 3
    assert page.locator('[data-order-status="fulfillment_assign"]').is_visible()
    assert page.locator("#orderFulfillmentSummary").is_hidden()
    page.evaluate("state.staffRoles = ['teacher']; renderOrders();")
    assert page.locator("#orderViewSwitcher").is_hidden()
    page.evaluate("state.staffRoles = ['admin']; state.orderViewMode = 'teacher'; renderOrders();")
    assert page.locator("#orderViewSwitcher").is_hidden()
    assert page.evaluate("orderScreenRole()") == "admin"
    assert not errors
    context.close()
