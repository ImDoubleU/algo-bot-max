import pytest
from test_feedback_workspace_ui import feedback_browser as _browser

feedback_browser = _browser


@pytest.mark.parametrize("width", [320, 390, 1440])
def test_grouped_connections_confirm_full_detach_and_preserve_expansion(feedback_browser, width):
    browser, base = feedback_browser
    context = browser.new_context(viewport={"width": width, "height": 1000})
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route("https://st.max.ru/**", lambda route: route.abort())
    page.goto(base + "/miniapp?demo=1&demo_role=admin&view=admin", wait_until="networkidle")
    page.evaluate("""() => {
      window.loadedAuditKinds = [];
      const originalLoad = loadAuditFeed;
      loadAuditFeed = (kind, ...args) => {
        loadedAuditKinds.push(kind); return originalLoad(kind, ...args);
      };
      accessLinks.push({...accessLinks[0], id: 'demo-child-link', role: 'student',
        maxUserId: '777777', displayName: 'Аккаунт ученика'});
    }""")
    page.locator('[data-admin-tab="contacts"]').click()
    assert page.locator("#bindingHistoryPanel, [data-audit-panel='bindings']").count() == 0
    assert "История подключений" not in page.locator("#adminPanel").inner_text()
    assert page.evaluate("loadedAuditKinds") == []
    assert page.locator("[data-access-child]").count() == 2
    child = page.locator('[data-access-child="demo-alisa"]')
    child.locator("summary").click()
    assert child.locator(".access-account-row").count() == 2
    assert "Родитель: подключён" in child.locator("summary").inner_text()
    assert "Ученик: подключён" in child.locator("summary").inner_text()
    page.evaluate("renderAdminPanel()")
    assert child.get_attribute("open") is not None
    child.locator('[data-toggle-contact="demo-link-alisa"]').click()
    assert page.locator("#confirmationDialog").is_visible()
    assert "Петров Иван" in page.locator("#confirmationDialogMessage").inner_text()
    page.locator("#cancelConfirmationButton").click()
    assert page.evaluate("accessLinks.filter(l => l.status === 'active').length") == 3
    child.locator('[data-toggle-contact="demo-link-alisa"]').click()
    page.locator("#confirmConfirmationButton").click()
    assert page.evaluate(
        "accessLinks.filter(l => l.maxUserId === '53364725').every(l => l.status === 'revoked')",
    )
    assert child.get_attribute("open") is not None
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.locator('[data-admin-tab="history"]').click()
    assert page.locator('[data-audit-panel="actions"]').is_visible()
    assert not errors
    context.close()


@pytest.mark.parametrize("width", [320, 701, 1024, 1440])
def test_warehouse_assignment_columns_align_for_different_statuses(feedback_browser, width):
    browser, base = feedback_browser
    context = browser.new_context(viewport={"width": width, "height": 1000})
    page = context.new_page()
    page.route("https://st.max.ru/**", lambda route: route.abort())
    page.goto(base + "/miniapp?demo=1&demo_role=admin&view=orders", wait_until="networkidle")
    page.evaluate("""() => {
      const p = products[0];
      orders = ['reserved', 'problem', 'reserved'].map((rawStatus, index) => ({
        id: String(900 + index), backendId: 'demo-assignment-' + index,
        studentId: students[0].id, student: students[0].name, rawStatus,
        items: [{id: 'assign-item-' + index, productId: p.id, productName: p.name,
          fulfillmentType: 'warehouse', quantity: 1}],
      }));
      state.orderViewMode = 'management'; state.orderStatusFilter = 'fulfillment_assign';
      refreshFulfillmentStageSnapshot(); renderOrders();
    }""")
    assert page.locator(".fulfillment-work-row").count() == 3
    positions = page.locator(".fulfillment-work-row .fulfillment-work-warehouse").evaluate_all(
        "elements => elements.map(e => e.getBoundingClientRect().left)",
    )
    assert max(positions) - min(positions) < 1
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    context.close()


@pytest.mark.parametrize("width", [320, 390, 1440])
def test_order_actions_thumbnails_and_digital_dialog_layout(feedback_browser, width):
    browser, base = feedback_browser
    context = browser.new_context(viewport={"width": width, "height": 1000})
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route("https://st.max.ru/**", lambda route: route.abort())
    page.goto(base + "/miniapp?demo=1&demo_role=admin&view=orders", wait_until="networkidle")
    page.evaluate("""() => {
      const p = products[0];
      p.photoThumbnailUrl = 'data:image/png;base64,' +
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/' +
        'x8AAwMCAO+j8ioAAAAASUVORK5CYII=';
      orders = [{id: '900', backendId: 'demo-test-order', studentId: students[0].id,
        teacherVisible: true, rawStatus: 'delivered_to_venue', student: students[0].name,
        total: 200, item: p.name, items: [{id: 'test-item', productId: p.id,
          productName: p.name, quantity: 1, fulfillmentType: 'warehouse',
          warehouseId: p.warehouses[0].warehouse_id,
          warehouseName: p.warehouses[0].warehouse_name,
          totalPrice: 200, isPicked: false}]}];
      state.orderViewMode = 'management'; state.orderStatusFilter = 'all'; renderOrders();
    }""")
    transfer = page.locator('#ordersTable [data-order-action="transfer"]')
    assert transfer.inner_text() == "Принять заказ"
    assert page.locator("#ordersTable .order-more-menu").count() == 0
    assert page.locator('#ordersTable [data-order-action="cancel"]').get_attribute("title")
    page.wait_for_function("""() => [...document.querySelectorAll('.order-actions button')]
      .every(b => b.querySelector('svg'))""")
    assert page.evaluate("""() => [...document.querySelectorAll('.order-actions button')]
      .every(b => Math.abs(b.getBoundingClientRect().height - 44) < 1)""")
    page.evaluate("""() => {
      orders[0].rawStatus = 'awaiting_delivery';
      state.orderStatusFilter = 'fulfillment_collect';
      refreshFulfillmentStageSnapshot(); renderOrders();
    }""")
    assert page.locator(".fulfillment-quick-row .fulfillment-product-thumb img").count() == 1
    page.wait_for_function(
        "document.querySelector('.fulfillment-product-thumb img').naturalWidth > 0",
    )
    page.evaluate("""() => {
      orders[0].items[0].isPicked = true;
      state.orderStatusFilter = 'fulfillment_route';
      refreshFulfillmentStageSnapshot(); renderOrders();
    }""")
    assert page.locator(".fulfillment-route-order .fulfillment-product-thumb img").count() == 1
    page.evaluate("""() => {
      orders[0].rawStatus = 'issued_to_student';
      orders[0].items[0].fulfillmentType = 'digital_manual';
      state.orderStatusFilter = 'electronic'; renderOrders();
    }""")
    page.locator('#ordersTable .order-actions [data-open-order="demo-test-order"]').click()
    assert "Код выдан ученику" in page.locator("#orderDialogContent").inner_text()
    assert page.evaluate("""() => {
      const thumb = document.querySelector('.order-detail-thumb').getBoundingClientRect();
      const copy = document.querySelector('.order-detail-copy').getBoundingClientRect();
      const item = document.querySelector('.order-detail-item').getBoundingClientRect();
      return thumb.right + 8 <= copy.left && thumb.bottom + 8 <= item.bottom;
    }""")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert not errors
    context.close()
