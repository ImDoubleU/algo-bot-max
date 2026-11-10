from pathlib import Path

import pytest
from test_feedback_workspace_ui import feedback_browser as _browser

feedback_browser = _browser


@pytest.mark.parametrize("width", [320, 390, 1440])
def test_newest_sort_hover_and_uncropped_product_images(feedback_browser, width):
    browser, base = feedback_browser
    context = browser.new_context(viewport={"width": width, "height": 900})
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route("https://st.max.ru/**", lambda route: route.abort())
    image = ('<svg xmlns="http://www.w3.org/2000/svg" width="600" height="900">'
             '<rect width="600" height="900" fill="#f9eedb"/>'
             '<text x="300" y="850" text-anchor="middle" font-size="80">80 ROBUX</text></svg>')
    page.route("https://catalog.test/**", lambda route: route.fulfill(
        body=image, content_type="image/svg+xml",
    ))
    page.goto(base + "/miniapp?demo=1&demo_role=student&view=store", wait_until="networkidle")
    page.evaluate("""() => {
      const p = (id, created, stock) => ({id, name: id, category_name: 'Электронные товары',
        price_astrocoins: 100, status: 'active', fulfillment_type: 'digital_code',
        available_quantity: stock, created_at: created, updated_at: '2026-11-10T15:00:00Z',
        photo_url: 'https://catalog.test/full.svg',
        photo_thumbnail_url: 'https://catalog.test/cropped.svg'});
      applyCatalog({products: [p('old-edited', '2026-09-01T12:00:00Z', 20),
        p('recent-available', '2026-11-01T12:00:00Z', 20),
        p('newest-unavailable', '2026-11-10T12:00:00Z', 0),
        p('unknown-date', null, 20)], warehouses: []});
      state.productCategory = 'all'; state.productSort = 'newest';
      state.favoritesOnly = false; qs('#inStockOnly').checked = false;
      qs('#productSearch').value = ''; renderCategories(); renderProducts();
    }""")
    assert page.locator("[data-product-card]").evaluate_all(
        "cards => cards.map(card => card.dataset.productCard)",
    ) == ["newest-unavailable", "recent-available", "old-edited", "unknown-date"]
    chip = page.locator(".category-chip.is-active")
    chip.hover()
    colors = chip.evaluate(
        "e => ({text: getComputedStyle(e).color, bg: getComputedStyle(e).backgroundColor})",
    )
    assert colors["text"] == "rgb(255, 255, 255)"
    assert colors["text"] != colors["bg"]
    first = page.locator("[data-product-card]").first
    img = first.locator("[data-product-image]")
    assert img.get_attribute("src") == "https://catalog.test/full.svg"
    assert img.evaluate("e => getComputedStyle(e).objectFit") == "contain"
    box = first.locator(".product-visual").bounding_box()
    assert abs(box["width"] - box["height"]) <= 1
    first.click()
    assert page.locator(".product-dialog-visual img").evaluate(
        "e => getComputedStyle(e).objectFit",
    ) == "contain"
    page.locator("#closeProductDialogButton").click()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    folder = Path(".deploy_tmp/store-catalog-release")
    folder.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(folder / f"store-{width}.png"), full_page=True)
    assert not errors
    context.close()
