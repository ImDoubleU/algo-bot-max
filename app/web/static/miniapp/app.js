function renderAll() {
  renderTenantControl();
  applyRailState();
  renderMobileNavigation();
  renderStatus();
  renderStudents();
  renderParentInvitations();
  renderDashboardOrders();
  renderCategories();
  renderProducts();
  renderCart();
  renderOrders();
  renderLedger();
  renderAccrualReport();
  renderAccrual();
  renderTeacherInvitations();
  renderBroadcasts();
  renderAdminPanel();
  refreshIcons();
}

async function importProductsFromFile() {
  const input = qs("#productImportFile");
  const file = state.productImportFile || input?.files?.[0] || null;
  if (!file) {
    showNotice("Выберите Excel или CSV с товарами", "danger");
    return;
  }

  if (apiContext.demoMode || !apiContext.maxUserId) {
    await importDemoProductsFromFile(file);
    return;
  }

  const formData = new FormData();
  formData.set("max_user_id", apiContext.maxUserId);
  if (apiContext.tenantSlug) formData.set("tenant_slug", apiContext.tenantSlug);
  formData.set("file", file);

  state.productImporting = true;
  renderAdminPanel();

  try {
    const response = await apiFetch("/api/v1/miniapp/products/import", {
      method: "POST",
      body: formData,
    });
    if (!response.ok) throw new Error(await parseApiError(response));

    const result = await response.json();
    await refreshCatalogAndOpsSummary();
    state.productImportFile = null;
    state.productImportFileName = "";
    showNotice(
      `Товары загружены: новых ${result.created_products}, обновлено ${result.updated_products}, остатков ${result.updated_inventory}`,
    );
  } catch (error) {
    showNotice(error.message || "Не удалось загрузить товары", "danger");
  } finally {
    state.productImporting = false;
    renderAll();
  }
}

async function importCrmStudents(dryRun) {
  const input = qs("#crmImportFile");
  const file = state.crmImportFile || input?.files?.[0] || null;
  if (!file) {
    showNotice("Выберите файл XLSX", "danger");
    return;
  }
  if (apiContext.demoMode || !apiContext.maxUserId) {
    showNotice("Импорт доступен после входа администратора", "danger");
    return;
  }
  if (!dryRun && !state.crmImportPreview) {
    showNotice("Сначала проверьте выбранный файл", "danger");
    return;
  }

  const formData = new FormData();
  formData.set("max_user_id", apiContext.maxUserId);
  if (apiContext.tenantSlug) formData.set("tenant_slug", apiContext.tenantSlug);
  formData.set("sheet_name", "Шаблон");
  formData.set("dry_run", String(dryRun));
  formData.set("student_status", state.crmStudentStatus);
  formData.set("file", file);

  state.crmImporting = true;
  renderAdminPanel();
  try {
    const response = await apiFetch("/api/v1/miniapp/students/import", {
      method: "POST",
      body: formData,
    });
    if (!response.ok) throw new Error(await parseApiError(response));
    const result = await response.json();
    state.crmImportPreview = result;
    if (dryRun) {
      showNotice(
        `Файл проверен: ${result.parsed_rows} строк, ${result.distinct_groups} групп, ${result.distinct_cities} городов`,
      );
    } else {
      await loadSession();
      state.adminStudents = [];
      state.adminStudentsLoaded = false;
      state.adminStudentsError = "";
      state.adminHistoryLoaded = false;
      showNotice(
        `Импорт завершен: новых ${result.created_students}, обновлено ${result.updated_students}, городов ${result.distinct_cities}`,
      );
    }
  } catch (error) {
    showNotice(error.message || "Не удалось импортировать файл", "danger");
  } finally {
    state.crmImporting = false;
    renderAll();
  }
}

async function importDemoProductsFromFile(file) {
  if (/\.xlsx$/i.test(file.name)) {
    showNotice("Для локальной проверки используйте CSV. Excel обработает backend при запуске из MAX", "danger");
    return;
  }

  try {
    const imported = parseDemoImport(await file.text());
    let created = 0;
    let updated = 0;

    imported.forEach((item) => {
      const existingIndex = products.findIndex(
        (product) => product.sku === item.sku || product.id === item.id,
      );
      if (existingIndex >= 0) {
        products[existingIndex] = { ...products[existingIndex], ...item };
        updated += 1;
      } else {
        products.push(item);
        created += 1;
      }
    });

    state.productImportFile = null;
    state.productImportFileName = "";
    renderCategories();
    renderProducts();
    renderAdminPanel();
    showNotice(`CSV загружен локально: новых ${created}, обновлено ${updated}`);
  } catch (error) {
    showNotice(error.message || "Не удалось прочитать CSV", "danger");
  }
}

function resetProductPhotoSelection() {
  if (state.productPhotoPreviewUrl.startsWith("blob:")) {
    URL.revokeObjectURL(state.productPhotoPreviewUrl);
  }
  state.productPhotoFile = null;
  state.productPhotoFileName = "";
  state.productPhotoPreviewUrl = "";
  state.productPhotoRemoved = false;
}

function selectProductPhoto(file) {
  if (!file) return false;
  const supportedByName = /\.(jpe?g|png|webp)$/i.test(file.name);
  if (!PRODUCT_IMAGE_TYPES.has(file.type) && !supportedByName) {
    showNotice("Выберите фото JPEG, PNG или WebP", "danger");
    return false;
  }
  if (file.size > PRODUCT_IMAGE_MAX_BYTES) {
    showNotice("Фото товара должно быть не больше 10 МБ", "danger");
    return false;
  }

  resetProductPhotoSelection();
  state.productPhotoFile = file;
  state.productPhotoFileName = file.name;
  state.productPhotoPreviewUrl = URL.createObjectURL(file);
  return true;
}

function fileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.addEventListener("load", () => resolve(String(reader.result || "")));
    reader.addEventListener("error", () => reject(new Error("Не удалось прочитать фото")));
    reader.readAsDataURL(file);
  });
}

function readProductInventoriesFromForm() {
  return qsa("[data-product-warehouse-select]:checked").map((checkbox) => {
    const warehouseId = checkbox.dataset.productWarehouseSelect || "";
    const quantityInput = qsa("[data-product-warehouse-quantity]").find(
      (input) => input.dataset.productWarehouseQuantity === warehouseId,
    );
    return {
      warehouse_id: warehouseId,
      stock_quantity: Number.parseInt(quantityInput?.value || "", 10),
      minimum_quantity: Number.parseInt(quantityInput?.min || "0", 10),
    };
  });
}

function syncProductInventoryEditor() {
  qsa("[data-product-inventory-row]").forEach((row) => {
    const warehouseId = row.dataset.productInventoryRow || "";
    const checkbox = row.querySelector("[data-product-warehouse-select]");
    const quantityInput = row.querySelector("[data-product-warehouse-quantity]");
    if (!(checkbox instanceof HTMLInputElement) || !(quantityInput instanceof HTMLInputElement)) {
      return;
    }
    const selected = checkbox.checked;
    row.classList.toggle("is-selected", selected);
    quantityInput.disabled = !selected;
    const freeLabel = row.querySelector("[data-product-warehouse-free]");
    if (freeLabel) {
      const reserved = Number.parseInt(freeLabel.dataset.reservedQuantity || "0", 10);
      const stock = Number.parseInt(quantityInput.value || "0", 10);
      const freeText = freeLabel.querySelector("span:last-child");
      if (freeText) {
        freeText.textContent = selected
          ? `Свободно ${Math.max((Number.isNaN(stock) ? 0 : stock) - reserved, 0)} шт.`
          : "Не используется";
      }
    }
    if (quantityInput.dataset.productWarehouseQuantity !== warehouseId) {
      quantityInput.dataset.productWarehouseQuantity = warehouseId;
    }
  });

  const total = readProductInventoriesFromForm().reduce(
    (sum, inventory) =>
      sum + (Number.isNaN(inventory.stock_quantity) ? 0 : inventory.stock_quantity),
    0,
  );
  const totalElement = qs("[data-product-inventory-total]");
  if (totalElement) totalElement.textContent = `${total} шт.`;
}

async function saveProductFromForm() {
  const name = qs("#productName")?.value.trim() || "";
  const category = qs("#productCategory")?.value.trim() || "Без категории";
  const price = Number.parseInt(qs("#productPrice")?.value || "0", 10);
  const status = qs("#productStatus")?.value || "active";
  const fulfillmentType = qs("#productFulfillmentType")?.value || "warehouse";
  const newCodes = qs("#productNewCodes")?.value.trim() || "";
  const description = qs("#productDescription")?.value.trim() || "";
  const photoFile = state.productPhotoFile;
  const editing = products.find((product) => product.id === state.editingProductId);
  const existingPhotoUrl = state.productPhotoRemoved ? "" : editing?.photoUrl || "";
  const inventoryDraft = fulfillmentType === "warehouse" ? readProductInventoriesFromForm() : [];
  if (name.length < 2) {
    showNotice("Укажите название товара", "danger");
    return;
  }
  if (Number.isNaN(price) || price < 0) {
    showNotice("Цена должна быть неотрицательным числом", "danger");
    return;
  }
  if (!photoFile && !existingPhotoUrl) {
    showNotice("Добавьте фото товара", "danger");
    return;
  }
  if (fulfillmentType === "digital_code" && !editing && !newCodes) {
    showNotice("Добавьте хотя бы один код для автовыдачи", "danger");
    return;
  }
  if (fulfillmentType === "warehouse" && inventoryDraft.length === 0) {
    showNotice(
      allCatalogWarehouses().length
        ? "Выберите хотя бы один склад для товара"
        : "Сначала добавьте склад",
      "danger",
    );
    return;
  }
  const invalidInventory = inventoryDraft.find(
    (inventory) =>
      !inventory.warehouse_id ||
      Number.isNaN(inventory.stock_quantity) ||
      inventory.stock_quantity < inventory.minimum_quantity ||
      inventory.stock_quantity > 1000000,
  );
  if (invalidInventory) {
    showNotice("Проверьте количество товара на выбранных складах", "danger");
    return;
  }
  const inventories = inventoryDraft.map(({ warehouse_id, stock_quantity }) => ({
    warehouse_id,
    stock_quantity,
  }));
  const payload = {
    sku: editing?.sku || undefined,
    name,
    category_name: category,
    category_slug: slugify(category),
    price_astrocoins: price,
    status,
    fulfillment_type: fulfillmentType,
    new_codes: newCodes,
    description: description || undefined,
    inventories,
  };

  if (apiContext.demoMode || !apiContext.maxUserId || state.editingProductId.startsWith("demo-")) {
    let photoUrl = existingPhotoUrl;
    if (photoFile) {
      try {
        photoUrl = await fileAsDataUrl(photoFile);
      } catch (error) {
        showNotice(error.message || "Не удалось прочитать фото", "danger");
        return;
      }
    }
    const demoSku = editing?.sku || `PRD-${Date.now().toString(36).toUpperCase()}`;
    const id = editing?.id || `demo-product-${slugify(demoSku)}`;
    const previousInventories = new Map(
      (editing ? productWarehouses(editing) : []).map((warehouse) => [warehouse.id, warehouse]),
    );
    const demoWarehouses = fulfillmentType === "warehouse"
      ? inventories.map((inventory) => {
          const warehouse = allCatalogWarehouses().find(
            (item) => item.id === inventory.warehouse_id,
          );
          const previous = previousInventories.get(inventory.warehouse_id);
          const reserved = Number(previous?.reserved || 0);
          return {
            warehouse_id: inventory.warehouse_id,
            warehouse_name: warehouse?.name || previous?.name || "Склад",
            warehouse_type: warehouse?.type || previous?.type || "common",
            stock_quantity: inventory.stock_quantity,
            reserved_quantity: reserved,
            available_quantity: Math.max(inventory.stock_quantity - reserved, 0),
          };
        })
      : [];
    const availableQuantity = demoWarehouses.reduce(
      (total, warehouse) => total + Number(warehouse.available_quantity || 0),
      0,
    );
    const nextProduct = {
      ...(editing || {}),
      id,
      sku: demoSku,
      name,
      category,
      categorySlug: payload.category_slug,
      price,
      status,
      fulfillmentType,
      totalCodeCount:
        Number(editing?.totalCodeCount || 0) +
        (newCodes ? newCodes.split(/\r?\n/).filter((code) => code.trim()).length : 0),
      issuedCodeCount: Number(editing?.issuedCodeCount || 0),
      photoUrl,
      description,
      stock:
        fulfillmentType === "digital_code"
          ? Number(editing?.stock || 0)
          : availableQuantity,
      warehouse:
        fulfillmentType === "digital_code"
          ? "Автовыдача кода"
          : demoWarehouses[0]?.warehouse_name || "Склад не выбран",
      warehouses: demoWarehouses,
      mark: name.trim().slice(0, 1).toUpperCase() || "A",
    };
    const existingIndex = products.findIndex((product) => product.id === id);
    if (existingIndex >= 0) products[existingIndex] = nextProduct;
    else products.unshift(nextProduct);
    state.editingProductId = "";
    state.productEditorOpen = false;
    resetProductPhotoSelection();
    showNotice(`Товар "${name}" сохранен`);
    renderAll();
    return;
  }

  state.productSaving = true;
  renderAdminPanel();
  try {
    const formData = new FormData();
    formData.set("max_user_id", apiContext.maxUserId);
    if (apiContext.tenantSlug) formData.set("tenant_slug", apiContext.tenantSlug);
    if (state.editingProductId) formData.set("product_id", state.editingProductId);
    if (payload.sku) formData.set("sku", payload.sku);
    formData.set("name", payload.name);
    formData.set("category_name", payload.category_name);
    formData.set("category_slug", payload.category_slug);
    formData.set("price_astrocoins", String(payload.price_astrocoins));
    formData.set("status", payload.status);
    formData.set("fulfillment_type", payload.fulfillment_type);
    formData.set("inventories", JSON.stringify(payload.inventories));
    if (payload.new_codes) formData.set("new_codes", payload.new_codes);
    if (payload.description) formData.set("description", payload.description);
    if (existingPhotoUrl) formData.set("existing_photo_url", existingPhotoUrl);
    if (photoFile) formData.set("photo", photoFile);

    const response = await apiFetch("/api/v1/miniapp/products/save", {
      method: "POST",
      body: formData,
    });
    if (!response.ok) throw new Error(await parseApiError(response));

    const result = await response.json();
    state.editingProductId = "";
    state.productEditorOpen = false;
    resetProductPhotoSelection();
    showNotice(`Товар "${result.name}" сохранен`);
    await refreshCatalogAndOpsSummary();
    renderAll();
  } catch (error) {
    showNotice(error.message || "Не удалось сохранить товар", "danger");
  } finally {
    state.productSaving = false;
    renderAdminPanel();
  }
}

async function cropProductPhoto() {
  const editing = products.find((product) => product.id === state.editingProductId);
  const source = state.productPhotoPreviewUrl || editing?.photoUrl || "";
  if (!source) return;
  try {
    const image = new Image();
    image.crossOrigin = "anonymous";
    await new Promise((resolve, reject) => {
      image.addEventListener("load", resolve, { once: true });
      image.addEventListener("error", () => reject(new Error("Не удалось открыть фото")), { once: true });
      image.src = source;
    });
    const side = Math.min(image.naturalWidth, image.naturalHeight);
    const outputSize = Math.min(side, 1200);
    const canvas = document.createElement("canvas");
    canvas.width = outputSize;
    canvas.height = outputSize;
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Кадрирование недоступно");
    context.drawImage(
      image,
      (image.naturalWidth - side) / 2,
      (image.naturalHeight - side) / 2,
      side,
      side,
      0,
      0,
      outputSize,
      outputSize,
    );
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/webp", 0.9));
    if (!blob) throw new Error("Не удалось подготовить фото");
    resetProductPhotoSelection();
    state.productPhotoFile = new File([blob], `product-${Date.now()}.webp`, { type: "image/webp" });
    state.productPhotoFileName = state.productPhotoFile.name;
    state.productPhotoPreviewUrl = URL.createObjectURL(blob);
    renderAdminPanel();
    showNotice("Фото обрезано по центру");
  } catch (error) {
    showNotice(error.message || "Не удалось кадрировать фото", "danger");
  }
}

async function toggleProductStatus(productId) {
  const product = productById(productId);
  if (!product || state.productSaving) return;
  const nextStatus = (product.status || "active") === "active" ? "hidden" : "active";
  if (apiContext.demoMode || !apiContext.maxUserId || product.id.startsWith("demo-")) {
    product.status = nextStatus;
    renderAll();
    showNotice(nextStatus === "active" ? "Товар опубликован" : "Товар скрыт");
    return;
  }
  state.productSaving = true;
  renderAdminPanel();
  try {
    const formData = new FormData();
    formData.set("max_user_id", String(apiContext.maxUserId));
    if (apiContext.tenantSlug) formData.set("tenant_slug", apiContext.tenantSlug);
    formData.set("product_id", product.id);
    formData.set("sku", product.sku || product.id);
    formData.set("name", product.name);
    formData.set("category_name", product.category || "Без категории");
    formData.set("category_slug", product.categorySlug || slugify(product.category || "Без категории"));
    formData.set("price_astrocoins", String(product.price || 0));
    formData.set("status", nextStatus);
    formData.set("fulfillment_type", product.fulfillmentType || "warehouse");
    if (product.description) formData.set("description", product.description);
    if (product.photoUrl) formData.set("existing_photo_url", product.photoUrl);
    const response = await apiFetch("/api/v1/miniapp/products/save", { method: "POST", body: formData });
    if (!response.ok) throw new Error(await parseApiError(response));
    await refreshCatalogAndOpsSummary();
    showNotice(nextStatus === "active" ? "Товар опубликован" : "Товар скрыт");
  } catch (error) {
    showNotice(error.message || "Не удалось изменить статус товара", "danger");
  } finally {
    state.productSaving = false;
    renderAdminPanel();
  }
}

function addCartItem(product, quantityValue) {
  if (!canUseStoreCart()) return false;
  const existingType = Array.from(state.cart.values())
    .map((item) => productById(item.productId)?.fulfillmentType || "warehouse")
    .find(Boolean);
  if (existingType && existingType !== (product.fulfillmentType || "warehouse")) {
    showNotice("Коды и товары со склада оформляются отдельными заказами", "danger");
    return false;
  }
  const current = cartQuantityFor(product.id);
  const availableLeft = cartAddableQuantity(product);
  const quantity = clampQuantity(quantityValue || "1", availableLeft);
  if (availableLeft <= 0) return false;

  const key = cartKey(product.id);
  state.cart.set(key, {
    productId: product.id,
    quantity: current + quantity,
  });
  saveCart();
  renderProducts();
  renderCart();
  return true;
}

function addToCart(productId) {
  if (!canUseStoreCart()) return;
  const product = productById(productId);
  if (!product || (product.status || "active") !== "active") return;
  addCartItem(product, "1");
}

function addProductDialogItemToCart() {
  const dialog = qs("#productDialog");
  const product = productById(dialog.dataset.productId || "");
  if (!product) return;
  const added = addCartItem(product, qs("#productDialogQuantity").value);
  if (!added) return;
  closeProductDialog();
  showNotice(`${product.name}: добавлено в корзину`);
}

function createDemoOrder() {
  const student = selectedStudent();
  const total = cartTotal();
  if (!student || state.cart.size === 0) return;
  if (total > student.balance) {
    showNotice("Недостаточно астрокоинов для заказа", "danger");
    return;
  }

  const orderNumber = String(1400 + orders.length + 1);
  const createdAt = new Date().toISOString();
  const orderItems = Array.from(state.cart.values())
    .map((item, index) => {
      const product = productById(item.productId);
      if (!product) return null;
      return {
        id: `demo-order-item-${orderNumber}-${index + 1}`,
        productId: product.id,
        productName: product.name,
        quantity: item.quantity,
        totalPrice: product.price * item.quantity,
        warehouseId: "",
        warehouseName: "",
        fulfillmentType: product.fulfillmentType || "warehouse",
        isPicked: false,
      };
    })
    .filter(Boolean);
  const orderSummary = orderItems
    .map((item) => `${item.productName} × ${item.quantity}`)
    .join("; ");
  student.balance -= total;
  orders.unshift({
    id: orderNumber,
    backendId: `demo-order-${orderNumber}`,
    studentId: student.id,
    rawStatus: "reserved",
    student: student.name,
    item: orderSummary || `Заказ на ${total} AC`,
    warehouse: "Назначается администратором",
    status: orderStatusLabel("reserved"),
    tone: orderStatusTone("reserved"),
    total,
    createdAt,
    items: orderItems,
    statusHistory: [
      {
        fromStatus: "created",
        toStatus: "reserved",
        comment: "Заказ оформлен, ожидается назначение склада",
        createdAt,
      },
    ],
  });
  ledger.unshift([
    todayShort(),
    `Покупка в магазине, заказ №${orderNumber}`,
    `-${total} AC`,
    student.id,
  ]);
  state.cart.clear();
  saveCart();
  setView("orders");
  showNotice(`Заказ №${orderNumber} оформлен и зарезервирован`);
  renderAll();
}

function orderWarehouseOptions(item) {
  const product = productById(item.productId || "");
  if (!product) return [];
  return productWarehouses(product).filter(
    (warehouse) =>
      warehouse.id === item.suggestedWarehouseId ||
      warehouse.id === item.warehouseId ||
      warehouse.available >= Number(item.quantity || 0),
  );
}

function renderOrderDialog(order) {
  const needsWarehouseAssignment = canAssignOrderWarehouses(order);
  const isDigitalOrder = orderIsDigital(order);
  const items = Array.isArray(order.items) && order.items.length > 0
    ? order.items
        .map(
          (item) => {
            const product = productById(item.productId || "");
            const isDigitalItem = item.fulfillmentType === "digital_code";
            const warehouseOptions = needsWarehouseAssignment
              ? orderWarehouseOptions(item)
              : [];
            const preferredWarehouseId = warehouseOptions.some(
              (warehouse) => warehouse.id === state.defaultWarehouseId,
            )
              ? state.defaultWarehouseId
              : item.suggestedWarehouseId;
            const warehouseControl = needsWarehouseAssignment
              ? `
                  <label class="order-warehouse-field">
                    <span>Склад для списания</span>
                    <select data-order-warehouse="${escapeHtml(item.productId || "")}">
                      <option value="">Выберите склад</option>
                      ${warehouseOptions
                        .map(
                          (warehouse) => `
                            <option
                              value="${escapeHtml(warehouse.id)}"
                              ${warehouse.id === preferredWarehouseId ? "selected" : ""}
                            >
                              ${escapeHtml(warehouse.name)} · доступно ${warehouse.available}
                            </option>
                          `,
                        )
                        .join("")}
                    </select>
                  </label>
                `
              : ["teacher", "admin"].includes(state.role) && item.warehouseName
                ? `<div class="student-meta">${escapeHtml(item.warehouseName)}</div>`
                : "";
            const issuedCodes = (item.issuedCodes || []).length
              ? `<section class="digital-delivery">
                  <div class="digital-delivery-head">
                    <span><i data-lucide="key-round"></i></span>
                    <div>
                      <strong>Цифровой товар готов</strong>
                      <small>Скопируйте код и используйте его на сайте или в приложении сервиса.</small>
                    </div>
                  </div>
                  <div class="issued-code-list">${item.issuedCodes
                  .map(
                    (code, index) => `<div class="issued-code-card">
                      <span>${item.issuedCodes.length > 1 ? `Код ${index + 1}` : "Код товара"}</span>
                      <code>${escapeHtml(code)}</code>
                      <button class="primary-action" type="button" data-copy-code="${escapeHtml(code)}" aria-label="Копировать код">
                        <i data-lucide="copy"></i><span>Копировать</span>
                      </button>
                    </div>`,
                  )
                  .join("")}</div>
                </section>`
              : "";
            return `
              <div class="order-detail-item ${needsWarehouseAssignment ? "needs-warehouse" : ""} ${isDigitalItem ? "is-digital" : ""}">
                <span class="order-detail-thumb">
                  ${product?.photoUrl ? `<img src="${escapeHtml(product.photoUrl)}" alt="" />` : `<i data-lucide="${product ? productFallbackIcon(product) : "package"}"></i>`}
                </span>
                <div class="order-detail-copy">
                  <div class="order-detail-product-head">
                    <div>
                      <strong>${escapeHtml(item.productName || "Товар")}</strong>
                      <div class="student-meta">${Number(item.quantity || 0)} шт.</div>
                    </div>
                    ${isDigitalItem ? `<strong class="order-detail-price">${Number(item.totalPrice || 0)} AC</strong>` : ""}
                  </div>
                  ${warehouseControl}
                  ${isDigitalItem ? "" : issuedCodes}
                </div>
                ${isDigitalItem ? "" : `<strong class="order-detail-price">${Number(item.totalPrice || 0)} AC</strong>`}
                ${isDigitalItem ? issuedCodes : ""}
              </div>
            `;
          },
        )
        .join("")
    : `
        <div class="order-detail-item">
          <div><strong>${escapeHtml(order.item)}</strong></div>
          ${orderTotalValue(order) ? `<strong>${orderTotalValue(order)} AC</strong>` : ""}
        </div>
      `;

  const history = Array.isArray(order.statusHistory) && order.statusHistory.length > 0
    ? order.statusHistory
        .slice()
        .reverse()
        .map((event, index) => {
          const comment = orderHistoryComment(event.comment);
          return `
            <div class="order-history-row ${index === 0 ? "is-current" : "is-complete"}">
              <span class="order-history-marker"><i data-lucide="${index === 0 ? "circle-dot" : "check"}"></i></span>
              <div>
                <strong>${escapeHtml(
                  isDigitalOrder && event.toStatus === "issued_to_student"
                    ? "Заказ выполнен"
                    : orderStatusLabel(event.toStatus),
                )}</strong>
                <span>${escapeHtml(formatOrderDate(event.createdAt))}</span>
                ${comment ? `<div>${escapeHtml(comment)}</div>` : ""}
              </div>
            </div>
          `;
        })
        .join("")
    : `
        <div class="order-history-row">
          <span class="order-history-marker"><i data-lucide="circle-dot"></i></span>
          <div><strong>${escapeHtml(orderStatusLabel(order.rawStatus))}</strong><span>Текущий статус</span></div>
        </div>
      `;

  qs("#orderDialogTitle").textContent = `Заказ №${order.id}`;
  qs("#orderDialogContent").innerHTML = `
    <div class="order-dialog-summary ${isDigitalOrder ? "is-digital" : ""}">
      <div>
        <span class="status-badge ${escapeHtml(orderStatusTone(order.rawStatus))}">${escapeHtml(orderStatusLabel(order.rawStatus))}</span>
        <h3>${escapeHtml(order.student)}</h3>
        <div class="student-meta">
          ${
            isDigitalOrder
              ? "Код хранится в этом заказе"
              : ["teacher", "admin"].includes(state.role)
              ? orderHasAssignedWarehouses(order)
                ? "Склад назначен"
                : "Ожидает назначения склада"
              : "Заказ зарезервирован"
          }
          ${order.createdAt ? ` · ${escapeHtml(formatOrderDate(order.createdAt))}` : ""}
        </div>
      </div>
      <div class="order-dialog-total">${orderTotalValue(order)} AC</div>
    </div>
    <section class="order-detail-section">
      <h3>Состав заказа</h3>
      ${items}
    </section>
    <section class="order-detail-section">
      <h3>История статусов</h3>
      <div class="order-history">${history}</div>
    </section>
  `;
  qs("#orderDialogActions").innerHTML = needsWarehouseAssignment
    ? `
        <button
          id="assignOrderWarehousesButton"
          class="primary-action"
          type="button"
          data-order-id="${escapeHtml(order.backendId || order.id)}"
        >Подтвердить склады</button>
      `
    : orderActionButtons(order, false);
  refreshIcons();
}

function openOrderDetails(orderId) {
  const order = orders.find((item) => item.id === orderId || item.backendId === orderId);
  if (!order) return;
  setView("orders");
  const dialog = qs("#orderDialog");
  dialog.dataset.orderId = order.backendId || order.id;
  renderOrderDialog(order);
  dialog.hidden = false;
  syncDialogBodyClass();
  qs("#closeOrderDialogButton").focus();
}

function closeOrderDialog() {
  const dialog = qs("#orderDialog");
  if (dialog.hidden) return;
  dialog.hidden = true;
  dialog.dataset.orderId = "";
  syncDialogBodyClass();
}

function showCancelOrderForm(orderId) {
  const order = orders.find((item) => item.backendId === orderId || item.id === orderId);
  if (!order) return;
  const canMarkOutOfStock = state.role === "admin";
  const productOptions = (order.items || [])
    .map(
      (item) =>
        `<option value="${escapeHtml(item.productId)}">${escapeHtml(item.productName)}</option>`,
    )
    .join("");
  qs("#orderDialogActions").innerHTML = `
    <div class="order-cancel-form">
      <div class="order-cancel-head">
        <span class="order-cancel-icon"><i data-lucide="circle-x"></i></span>
        <div>
          <strong>Отмена заказа</strong>
          <p>Выберите причину. Ученик получит ее вместе с уведомлением.</p>
        </div>
      </div>
      <label>
        <span>Причина отмены</span>
        <select id="orderCancelReason">
          <option value="" selected disabled>Выберите причину</option>
          ${canMarkOutOfStock ? '<option value="Товар закончился">Товар закончился</option>' : ""}
          <option value="Ошибка в заказе">Ошибка в заказе</option>
          <option value="По просьбе родителя">По просьбе родителя</option>
          <option value="Заказ не актуален">Заказ не актуален</option>
          <option value="Другое">Другое</option>
        </select>
      </label>
      ${
        canMarkOutOfStock
          ? `<label id="orderCancelProductField" hidden>
               <span>Товар</span>
               <select id="orderCancelProduct">${productOptions}</select>
             </label>`
          : ""
      }
      <label id="orderCancelCustomReasonField" class="order-cancel-wide" hidden>
        <span>Своя причина</span>
        <input id="orderCancelCustomReason" type="text" maxlength="500" placeholder="Коротко объясните причину отмены" />
      </label>
      ${
        canMarkOutOfStock
          ? `<div id="orderCancelStockWarning" class="order-cancel-warning" hidden>
               <i data-lucide="triangle-alert"></i>
               <span>Остаток выбранного товара будет обнулен на всех складах.</span>
             </div>`
          : ""
      }
      <div class="order-cancel-actions">
        <button class="secondary-action" type="button" data-cancel-order-back="${escapeHtml(orderId)}">Назад</button>
        <button class="secondary-action danger-action" type="button" data-confirm-order-cancel="${escapeHtml(orderId)}">Отменить заказ</button>
      </div>
    </div>
  `;
  syncCancelOrderForm();
  refreshIcons();
  qs("#orderCancelReason")?.focus();
}

function syncCancelOrderForm() {
  const reason = qs("#orderCancelReason")?.value || "";
  const isCustom = reason === "Другое";
  const isOutOfStock = reason === "Товар закончился";
  const customField = qs("#orderCancelCustomReasonField");
  const productField = qs("#orderCancelProductField");
  const warning = qs("#orderCancelStockWarning");
  if (customField) customField.hidden = !isCustom;
  if (productField) productField.hidden = !isOutOfStock;
  if (warning) warning.hidden = !isOutOfStock;
}

async function assignOrderWarehouses(orderId) {
  const order = orders.find((item) => item.backendId === orderId || item.id === orderId);
  if (!order || !canAssignOrderWarehouses(order)) return;

  const assignments = (order.items || []).map((item) => {
    const select = qsa("[data-order-warehouse]").find(
      (field) => field.dataset.orderWarehouse === item.productId,
    );
    return {
      item,
      warehouseId: select?.value || "",
    };
  });
  if (assignments.some((assignment) => !assignment.warehouseId)) {
    showNotice("Выберите склад для каждой позиции заказа", "danger");
    return;
  }

  const button = qs("#assignOrderWarehousesButton");
  if (button) button.disabled = true;

  if (orderId.startsWith("demo-") || apiContext.demoMode || !apiContext.maxUserId) {
    const previousStatus = order.rawStatus;
    assignments.forEach(({ item, warehouseId }) => {
      const product = productById(item.productId);
      const warehouse = product ? warehouseById(product, warehouseId) : null;
      if (!warehouse) return;
      item.warehouseId = warehouse.id;
      item.warehouseName = warehouse.name;
      const raw = ensureProductWarehouse(product, warehouse);
      raw.reserved_quantity = Number(raw.reserved_quantity || 0) + Number(item.quantity || 0);
      raw.available_quantity = Math.max(
        Number(raw.available_quantity || warehouse.available) - Number(item.quantity || 0),
        0,
      );
    });
    order.rawStatus = "awaiting_delivery";
    order.status = orderStatusLabel(order.rawStatus);
    order.tone = orderStatusTone(order.rawStatus);
    order.warehouse = orderWarehouseSummary(order.items, "Склад назначен");
    order.statusHistory = order.statusHistory || [];
    order.statusHistory.push({
      fromStatus: previousStatus,
      toStatus: order.rawStatus,
      comment: previousStatus === "problem"
        ? "Проблема устранена, заказ ожидает доставки"
        : "Склад назначен, заказ ожидает доставки",
      createdAt: new Date().toISOString(),
    });
    showNotice(`Заказ №${order.id}: склады назначены`);
    renderAll();
    renderOrderDialog(order);
    return;
  }

  try {
    const response = await apiFetch(
      `/api/v1/miniapp/orders/${encodeURIComponent(order.backendId)}/assign-warehouses`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          max_user_id: Number(apiContext.maxUserId),
          tenant_slug: apiContext.tenantSlug || undefined,
          items: assignments.map(({ item, warehouseId }) => ({
            product_id: item.productId,
            warehouse_id: warehouseId,
          })),
          comment: "Склад назначен в приложении",
        }),
      },
    );
    if (!response.ok) throw new Error(await parseApiError(response));

    showNotice(`Заказ №${order.id}: склады назначены`);
    await refreshOrderAndInventoryState();
    renderAll();
    const refreshedOrder = orders.find(
      (item) => item.backendId === orderId || item.id === orderId,
    );
    if (refreshedOrder) renderOrderDialog(refreshedOrder);
  } catch (error) {
    showNotice(error.message || "Не удалось назначить склады", "danger");
    if (button) button.disabled = false;
  }
}

async function assignSummaryOrderWarehouses(rawOrderIds, button = null) {
  const orderIds = String(rawOrderIds || "")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
  const targets = orderIds
    .map((orderId) => orders.find((order) => fulfillmentOrderId(order) === orderId))
    .filter(
      (order) =>
        order &&
        canAssignOrderWarehouses(order) &&
        (order.items || []).every((item) => Boolean(orderPreferredWarehouseId(item))),
    );
  if (!targets.length) {
    showNotice("Нет заказов с готовым выбором склада", "danger");
    return;
  }

  const confirmed = await requestConfirmation({
    eyebrow: "Комплектация",
    title: "Подтвердить склады",
    message: `Для заказов: ${targets.length}. Будут выбраны ваш главный склад или склад текущего резерва.`,
    confirmLabel: "Подтвердить",
    cancelLabel: "Отмена",
  });
  if (!confirmed) return;

  if (button) button.disabled = true;
  let completed = 0;
  try {
    if (apiContext.demoMode || !apiContext.maxUserId) {
      targets.forEach((order) => {
        (order.items || []).forEach((item) => {
          const warehouseId = orderPreferredWarehouseId(item);
          const product = productById(item.productId);
          const warehouse = product ? warehouseById(product, warehouseId) : null;
          if (!warehouse) return;
          item.warehouseId = warehouse.id;
          item.warehouseName = warehouse.name;
        });
        order.rawStatus = "awaiting_delivery";
        order.status = orderStatusLabel(order.rawStatus);
        order.tone = orderStatusTone(order.rawStatus);
        order.warehouse = orderWarehouseSummary(order.items, "Склад назначен");
        completed += 1;
      });
    } else {
      for (const order of targets) {
        const response = await apiFetch(
          `/api/v1/miniapp/orders/${encodeURIComponent(order.backendId)}/assign-warehouses`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              max_user_id: Number(apiContext.maxUserId),
              tenant_slug: apiContext.tenantSlug || undefined,
              items: (order.items || []).map((item) => ({
                product_id: item.productId,
                warehouse_id: orderPreferredWarehouseId(item),
              })),
              comment: "Склад выбран",
            }),
          },
        );
        if (!response.ok) throw new Error(await parseApiError(response));
        completed += 1;
      }
      await refreshOrderAndInventoryState();
    }
    targets.forEach((order) => {
      state.selectedFulfillmentOrders.delete(String(order.backendId || order.id));
    });
    renderAll();
    showNotice(`Склады подтверждены для заказов: ${completed}`);
  } catch (error) {
    if (completed > 0 && !apiContext.demoMode) {
      await refreshOrderAndInventoryState();
      renderAll();
    }
    showNotice(
      `${completed ? `Подтверждено: ${completed}. ` : ""}${error.message || "Не удалось подтвердить склады"}`,
      "danger",
    );
  } finally {
    if (button) button.disabled = false;
  }
}

async function deliverSummaryOrders(rawOrderIds, button = null) {
  const orderIds = String(rawOrderIds || "")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
  const targets = orderIds
    .map((orderId) => orders.find((order) => fulfillmentOrderId(order) === orderId))
    .filter((order) => order && canMarkOrderDelivered(order));
  if (!targets.length) {
    showNotice("Нет полностью собранных заказов для доставки", "danger");
    return;
  }

  const confirmed = await requestConfirmation({
    eyebrow: "Распределение",
    title: "Подтвердить доставку",
    message: `Заказы будут отмечены как доставленные на площадку: ${targets.length}.`,
    confirmLabel: "Подтвердить доставку",
    cancelLabel: "Отмена",
  });
  if (!confirmed) return;

  if (button) {
    button.disabled = true;
    button.classList.add("is-loading");
  }
  state.fulfillmentSaving = true;
  let completed = 0;
  try {
    if (apiContext.demoMode || !apiContext.maxUserId) {
      targets.forEach((order) => {
        const previousStatus = order.rawStatus;
        order.rawStatus = "delivered_to_venue";
        order.status = orderStatusLabel(order.rawStatus);
        order.tone = orderStatusTone(order.rawStatus);
        order.statusHistory = order.statusHistory || [];
        order.statusHistory.push({
          fromStatus: previousStatus,
          toStatus: order.rawStatus,
          comment: "Заказ доставлен на площадку",
          createdAt: new Date().toISOString(),
        });
        completed += 1;
      });
    } else {
      for (const order of targets) {
        const response = await apiFetch(
          `/api/v1/miniapp/orders/${encodeURIComponent(order.backendId)}/delivered-to-venue`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              max_user_id: Number(apiContext.maxUserId),
              tenant_slug: apiContext.tenantSlug || undefined,
              comment: "",
            }),
          },
        );
        if (!response.ok) throw new Error(await parseApiError(response));
        completed += 1;
      }
      await refreshOrderAndInventoryState();
    }
    targets.forEach((order) => {
      state.selectedFulfillmentOrders.delete(fulfillmentOrderId(order));
    });
    renderAll();
    showNotice(`Доставлено на площадку: ${completed}`);
  } catch (error) {
    if (completed > 0 && !apiContext.demoMode) {
      await refreshOrderAndInventoryState();
      renderAll();
    }
    showNotice(
      `${completed ? `Обновлено: ${completed}. ` : ""}${error.message || "Не удалось обновить доставку"}`,
      "danger",
    );
  } finally {
    state.fulfillmentSaving = false;
    if (button?.isConnected) {
      button.disabled = false;
      button.classList.remove("is-loading");
    }
  }
}

async function updateOrderAction(orderId, action, cancelData = null) {
  const order = orders.find((item) => item.backendId === orderId || item.id === orderId);
  if (!order) return;

  if (orderId.startsWith("demo-") || apiContext.demoMode || !apiContext.maxUserId) {
    const previousStatus = order.rawStatus;
    if (action === "issue") order.rawStatus = "issued_to_student";
    else if (action === "deliver") order.rawStatus = "delivered_to_venue";
    else if (action === "transfer") order.rawStatus = "transferred_to_teacher";
    else order.rawStatus = "cancelled";
    order.status = orderStatusLabel(order.rawStatus);
    order.tone = orderStatusTone(order.rawStatus);
    order.statusHistory = order.statusHistory || [];
    order.statusHistory.push({
      fromStatus: previousStatus,
      toStatus: order.rawStatus,
      comment: {
        issue: "Заказ передан ученику",
        deliver: "Заказ доставлен на площадку",
        transfer: "Учитель получил заказ",
        cancel: cancelData?.customReason || cancelData?.reason || "Заказ отменен",
      }[action],
      createdAt: new Date().toISOString(),
    });
    showNotice(
      {
        issue: `Заказ №${order.id} передан ученику`,
        deliver: `Заказ №${order.id} доставлен на площадку`,
        transfer: `Учитель получил заказ №${order.id}`,
        cancel: `Заказ №${order.id} отменен`,
      }[action],
    );
    renderAll();
    if (!qs("#orderDialog").hidden) renderOrderDialog(order);
    return;
  }

  const endpoint = {
    issue: "issue",
    deliver: "delivered-to-venue",
    transfer: "transfer-to-teacher",
    cancel: "cancel",
  }[action];
  if (!endpoint) return;
  try {
    const response = await apiFetch(
      `/api/v1/miniapp/orders/${encodeURIComponent(order.backendId)}/${endpoint}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          action === "cancel"
            ? {
                max_user_id: Number(apiContext.maxUserId),
                tenant_slug: apiContext.tenantSlug || undefined,
                reason: cancelData?.reason || "Другое",
                custom_reason: cancelData?.customReason || undefined,
                out_of_stock_product_id: cancelData?.productId || undefined,
              }
            : {
                max_user_id: Number(apiContext.maxUserId),
                tenant_slug: apiContext.tenantSlug || undefined,
                comment: {
                  issue: "Выдано в приложении",
                  deliver: "Доставлено на площадку",
                  transfer: "Учитель получил заказ",
                }[action],
              },
        ),
      },
    );
    if (!response.ok) throw new Error(await parseApiError(response));

    const result = await response.json();
    showNotice(
      {
        issue: `Заказ №${result.order.order_number} выдан ученику`,
        deliver: `Заказ №${result.order.order_number} доставлен на площадку`,
        transfer: `Учитель получил заказ №${result.order.order_number}`,
        cancel: `Заказ №${result.order.order_number} отменен, астрокоины возвращены`,
      }[action],
    );
    await refreshOrderAndInventoryState();
    renderAll();
    if (!qs("#orderDialog").hidden) {
      const refreshedOrder = orders.find((item) => item.backendId === orderId || item.id === orderId);
      if (refreshedOrder) renderOrderDialog(refreshedOrder);
    }
  } catch (error) {
    showNotice(error.message || "Не удалось обновить заказ", "danger");
  }
}

async function confirmFulfillmentPickDraft() {
  if (state.fulfillmentSaving) return;
  const updates = [...state.fulfillmentPickDraft.values()];
  if (updates.length === 0) return;

  const invalid = updates.some(
    ({ order, item, itemId }) =>
      !order ||
      !item ||
      !itemId ||
      !canPickOrderItem(order) ||
      !(order.items || []).includes(item),
  );
  if (invalid) {
    showNotice("Заказы изменились. Обновите список и повторите сборку", "danger");
    return;
  }

  state.fulfillmentSaving = true;
  renderOrderFulfillmentSummary();
  refreshIcons();
  try {
    if (!apiContext.demoMode && apiContext.maxUserId) {
      const response = await apiFetch("/api/v1/miniapp/orders/picks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          max_user_id: Number(apiContext.maxUserId),
          tenant_slug: apiContext.tenantSlug || undefined,
          items: updates.map(({ order, itemId, isPicked }) => ({
            order_id: order.backendId,
            order_item_id: itemId,
            is_picked: isPicked,
          })),
        }),
      });
      if (!response.ok) throw new Error(await parseApiError(response));
    }
    updates.forEach(({ item, isPicked }) => {
      item.isPicked = isPicked;
    });
    state.fulfillmentPickDraft.clear();
    showNotice("Сборка подтверждена");
  } catch (error) {
    try {
      await refreshOrderAndInventoryState();
      refreshFulfillmentStageSnapshot();
    } catch {
      state.fulfillmentPickDraft.clear();
    }
    showNotice(error.message || "Не удалось подтвердить сборку", "danger");
  } finally {
    state.fulfillmentSaving = false;
    renderOrderFulfillmentSummary();
    refreshIcons();
  }
}

async function accrueSelectedStudents() {
  const selectedReason = qs("#groupAccrualReason")?.value || "";
  const customReason = selectedReason === "__custom__";
  const rule = state.accrualRules.find((item) => item.reason === selectedReason);
  const reason = customReason ? qs("#customAccrualReason")?.value.trim() || "" : selectedReason;
  const amount = customReason
    ? Number.parseInt(qs("#customAccrualAmount")?.value || "0", 10)
    : Number(rule?.amount || 0);
  if (!reason) {
    showNotice("Выберите причину начисления", "danger");
    return;
  }
  if (!amount || amount <= 0) {
    showNotice("Выберите сумму начисления", "danger");
    return;
  }
  const targets = students.filter((student) => state.selectedAccrualStudents.has(student.id));
  if (targets.length === 0) {
    showNotice("Отметьте хотя бы одного ученика", "danger");
    return;
  }
  await accrueStudents(targets, amount, reason, "", customReason);
}

async function saveWarehouseFromForm() {
  const name = qs("#warehouseName")?.value.trim() || "";
  const address = qs("#warehouseAddress")?.value.trim() || "";
  if (name.length < 2) {
    showNotice("Укажите название склада", "danger");
    return;
  }

  const payload = {
    name,
    address: address || undefined,
  };

  if (apiContext.demoMode || !apiContext.maxUserId || state.editingWarehouseId.startsWith("demo-")) {
    const existing = catalogWarehouses.find(
      (warehouse) => warehouse.id === state.editingWarehouseId,
    );
    const generatedSlug = existing?.slug || slugify(name);
    const id = state.editingWarehouseId || `demo-warehouse-${generatedSlug}`;
    const existingIndex = catalogWarehouses.findIndex((warehouse) => warehouse.id === id);
    const nextWarehouse = {
      id,
      slug: generatedSlug,
      name: payload.name,
      type: existing?.type || "common",
      address: payload.address || "",
    };
    if (existingIndex >= 0) catalogWarehouses[existingIndex] = nextWarehouse;
    else catalogWarehouses.push(nextWarehouse);
    state.editingWarehouseId = "";
    state.warehouseEditorOpen = false;
    showNotice(`Склад "${payload.name}" сохранен`);
    renderAdminPanel();
    return;
  }

  state.warehouseSaving = true;
  renderAdminPanel();
  try {
    const response = await apiFetch("/api/v1/miniapp/warehouses", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        max_user_id: Number(apiContext.maxUserId),
        tenant_slug: apiContext.tenantSlug || undefined,
        warehouse_id: state.editingWarehouseId || undefined,
        ...payload,
      }),
    });
    if (!response.ok) throw new Error(await parseApiError(response));

    const result = await response.json();
    state.editingWarehouseId = "";
    state.warehouseEditorOpen = false;
    showNotice(`Склад "${result.name}" сохранен`);
    await refreshCatalogAndOpsSummary();
    renderAll();
  } catch (error) {
    showNotice(error.message || "Не удалось сохранить склад", "danger");
  } finally {
    state.warehouseSaving = false;
    renderAdminPanel();
  }
}

async function saveWarehousePreference() {
  const warehouseId = qs("#defaultWarehouseSelect")?.value || "";
  if (!warehouseId) {
    showNotice("Выберите основной склад", "danger");
    return;
  }
  state.warehousePreferenceSaving = true;
  renderAdminPanel();
  try {
    const response = await apiFetch("/api/v1/miniapp/warehouse-preference", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        max_user_id: Number(apiContext.maxUserId),
        tenant_slug: apiContext.tenantSlug || undefined,
        warehouse_id: warehouseId,
      }),
    });
    if (!response.ok) throw new Error(await parseApiError(response));
    const result = await response.json();
    state.defaultWarehouseId = String(result.warehouse_id);
    showNotice(`Основной склад: ${result.warehouse_name}`);
  } catch (error) {
    showNotice(error.message || "Не удалось сохранить основной склад", "danger");
  } finally {
    state.warehousePreferenceSaving = false;
    renderAdminPanel();
  }
}

async function toggleContactLink(linkId) {
  const link = accessLinks.find((item) => item.id === linkId);
  if (!link) return;
  const nextStatus = link.status === "revoked" ? "active" : "revoked";

  if (apiContext.demoMode || !apiContext.maxUserId || link.id.startsWith("demo-")) {
    link.status = nextStatus;
    showNotice(
      nextStatus === "revoked"
        ? `Связь с учеником ${link.studentName} помечена к отзыву`
        : `Связь с учеником ${link.studentName} восстановлена`,
    );
    renderAdminPanel();
    return;
  }

  try {
    const response = await apiFetch(`/api/v1/miniapp/access-links/${encodeURIComponent(link.id)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        max_user_id: Number(apiContext.maxUserId),
        tenant_slug: apiContext.tenantSlug || undefined,
        status: nextStatus,
      }),
    });
    if (!response.ok) throw new Error(await parseApiError(response));

    link.status = nextStatus;
    showNotice(
      nextStatus === "revoked"
        ? `Связь с учеником ${link.studentName} отозвана`
        : `Связь с учеником ${link.studentName} восстановлена`,
    );
    await loadSession();
    renderAll();
  } catch (error) {
    showNotice(error.message || "Не удалось обновить связь доступа", "danger");
  }
}

function closeStaffNotificationSettings() {
  const dialog = qs("#staffNotificationDialog");
  if (!dialog || dialog.hidden) return;
  dialog.hidden = true;
  state.staffNotificationSettings = null;
  state.staffNotificationTargetAccountId = "";
  state.staffNotificationsLoading = false;
  state.staffNotificationsSaving = false;
  syncDialogBodyClass();
}

function renderStaffNotificationSettings() {
  const content = qs("#staffNotificationDialogContent");
  const saveButton = qs("#saveStaffNotificationsButton");
  const resetButton = qs("#resetStaffNotificationsButton");
  if (!content || !saveButton || !resetButton) return;

  saveButton.disabled = state.staffNotificationsLoading || state.staffNotificationsSaving;
  resetButton.disabled = state.staffNotificationsLoading || state.staffNotificationsSaving;
  saveButton.textContent = state.staffNotificationsSaving ? "Сохранение..." : "Сохранить";
  if (state.staffNotificationsLoading) {
    content.innerHTML = '<div class="loading-state">Загружаем настройки...</div>';
    return;
  }

  const settings = state.staffNotificationSettings;
  if (!settings) {
    content.innerHTML = '<div class="empty-state">Не удалось загрузить настройки</div>';
    return;
  }
  qs("#staffNotificationDialogTitle").textContent = settings.display_name || "Уведомления";
  qs("#staffNotificationDialogMeta").textContent = `${(settings.roles || []).map(staffRoleLabel).join(", ")} · MAX ID ${settings.max_user_id}`;

  const groups = new Map();
  (settings.items || []).forEach((item) => {
    if (!groups.has(item.category)) {
      groups.set(item.category, { label: item.category_label, items: [] });
    }
    groups.get(item.category).items.push(item);
  });
  content.innerHTML = [...groups.values()]
    .map(
      (group) => `
        <section class="staff-notification-group">
          <div class="staff-notification-group-head">
            <h3>${escapeHtml(group.label)}</h3>
            <span>${group.items.filter((item) => item.enabled).length} из ${group.items.length}</span>
          </div>
          <div class="staff-notification-list">
            ${group.items.map((item) => `
              <label class="staff-notification-row">
                <input
                  type="checkbox"
                  data-staff-notification-key="${escapeHtml(item.event_key)}"
                  data-default-enabled="${item.default_enabled ? "1" : "0"}"
                  ${item.enabled ? "checked" : ""}
                />
                <span class="staff-notification-check" aria-hidden="true"></span>
                <span class="staff-notification-copy">
                  <strong>${escapeHtml(item.label)}</strong>
                  <small>${escapeHtml(item.description)}</small>
                </span>
                ${item.customized ? '<span class="staff-notification-custom">Изменено</span>' : ""}
              </label>
            `).join("")}
          </div>
        </section>
      `,
    )
    .join("");
}

async function openStaffNotificationSettings(accountId) {
  if (!accountId) return;
  if (apiContext.demoMode || !apiContext.maxUserId) {
    showNotice("Настройки уведомлений доступны после входа в рабочий кабинет", "danger");
    return;
  }
  const assignment = staffAssignments.find((item) => item.accountId === accountId);
  state.staffNotificationTargetAccountId = accountId;
  state.staffNotificationSettings = null;
  state.staffNotificationsLoading = true;
  qs("#staffNotificationDialogTitle").textContent = assignment?.displayName || "Уведомления";
  qs("#staffNotificationDialogMeta").textContent = assignment
    ? `${staffRoleLabel(assignment.role)} · MAX ID ${assignment.maxUserId}`
    : "";
  qs("#staffNotificationDialog").hidden = false;
  document.body.classList.add("dialog-open");
  renderStaffNotificationSettings();
  refreshIcons();

  const params = new URLSearchParams({ max_user_id: String(apiContext.maxUserId) });
  if (apiContext.tenantSlug) params.set("tenant_slug", apiContext.tenantSlug);
  try {
    const response = await apiFetch(
      `/api/v1/miniapp/staff/${encodeURIComponent(accountId)}/notifications?${params}`,
    );
    if (!response.ok) throw new Error(await parseApiError(response));
    state.staffNotificationSettings = await response.json();
  } catch (error) {
    showNotice(error.message || "Не удалось загрузить настройки уведомлений", "danger");
  } finally {
    state.staffNotificationsLoading = false;
    renderStaffNotificationSettings();
    refreshIcons();
  }
}

function syncStaffNotificationGroupCounts() {
  qsa(".staff-notification-group").forEach((group) => {
    const inputs = Array.from(group.querySelectorAll("[data-staff-notification-key]"));
    const counter = group.querySelector(".staff-notification-group-head span");
    if (counter) counter.textContent = `${inputs.filter((input) => input.checked).length} из ${inputs.length}`;
  });
}

function resetStaffNotificationSettings() {
  qsa("[data-staff-notification-key]").forEach((input) => {
    input.checked = input.dataset.defaultEnabled === "1";
  });
  qsa(".staff-notification-custom").forEach((badge) => badge.remove());
  syncStaffNotificationGroupCounts();
}

async function saveStaffNotificationSettings() {
  const accountId = state.staffNotificationTargetAccountId;
  if (!accountId || state.staffNotificationsSaving) return;
  const preferences = qsa("[data-staff-notification-key]").map((input) => ({
    event_key: input.dataset.staffNotificationKey,
    enabled: input.checked,
  }));
  if (!preferences.length) return;

  state.staffNotificationsSaving = true;
  renderStaffNotificationSettings();
  try {
    const response = await apiFetch(
      `/api/v1/miniapp/staff/${encodeURIComponent(accountId)}/notifications`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          max_user_id: Number(apiContext.maxUserId),
          tenant_slug: apiContext.tenantSlug || undefined,
          preferences,
        }),
      },
    );
    if (!response.ok) throw new Error(await parseApiError(response));
    state.staffNotificationSettings = await response.json();
    showNotice("Настройки уведомлений сохранены");
    closeStaffNotificationSettings();
  } catch (error) {
    showNotice(error.message || "Не удалось сохранить настройки уведомлений", "danger");
  } finally {
    state.staffNotificationsSaving = false;
    if (!qs("#staffNotificationDialog").hidden) renderStaffNotificationSettings();
  }
}

async function updateStaffAssignment({ targetMaxUserId, role, status, displayName = "" }) {
  const maxUserId = String(targetMaxUserId || "").trim();
  if (!/^\d+$/.test(maxUserId)) {
    showNotice("Укажите числовой MAX user_id сотрудника", "danger");
    return false;
  }

  if (apiContext.demoMode || !apiContext.maxUserId || maxUserId.startsWith("demo-")) {
    const existing = staffAssignments.find(
      (assignment) => assignment.maxUserId === maxUserId && assignment.role === role,
    );
    if (existing) {
      existing.status = status;
      if (displayName) existing.displayName = displayName;
    } else {
      staffAssignments.push({
        id: `demo-staff-${maxUserId}-${role}`,
        accountId: `demo-account-${maxUserId}`,
        maxUserId,
        username: "",
        displayName,
        role,
        status,
      });
    }
    showNotice(
      status === "active"
        ? `Роль ${staffRoleLabel(role)} выдана пользователю ${maxUserId}`
        : `Роль ${staffRoleLabel(role)} отозвана у пользователя ${maxUserId}`,
    );
    renderAdminPanel();
    return true;
  }

  state.staffSaving = true;
  renderAdminPanel();
  try {
    const response = await apiFetch("/api/v1/miniapp/staff/assignments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        max_user_id: Number(apiContext.maxUserId),
        tenant_slug: apiContext.tenantSlug || undefined,
        target_max_user_id: Number(maxUserId),
        role,
        status,
        display_name: displayName || undefined,
      }),
    });
    if (!response.ok) throw new Error(await parseApiError(response));

    const result = await response.json();
    showNotice(
      result.status === "active"
        ? `Роль ${staffRoleLabel(result.role)} выдана пользователю ${result.max_user_id}`
        : `Роль ${staffRoleLabel(result.role)} отозвана у пользователя ${result.max_user_id}`,
    );
    await loadSession();
    renderAll();
    return true;
  } catch (error) {
    showNotice(error.message || "Не удалось обновить роль сотрудника", "danger");
    return false;
  } finally {
    state.staffSaving = false;
    renderAdminPanel();
  }
}

async function saveStaffAssignmentFromForm() {
  const targetMaxUserId = qs("#staffMaxUserId")?.value || "";
  const displayName = qs("#staffDisplayName")?.value.trim() || "";
  const role = qs("#staffRoleSelect")?.value || "teacher";
  const saved = await updateStaffAssignment({
    targetMaxUserId,
    role,
    status: "active",
    displayName,
  });
  if (saved) {
    state.staffEditorOpen = false;
    renderAdminPanel();
  }
}

async function createStaffInvitation() {
  const role = qs("#staffInvitationRoleSelect")?.value || state.staffInvitationRole || "teacher";
  state.staffInvitationRole = role;
  if (apiContext.demoMode || !apiContext.maxUserId) {
    showNotice("Создание приглашений доступно после входа через MAX", "danger");
    return;
  }

  state.staffInvitationSaving = true;
  renderAdminPanel();
  try {
    const response = await apiFetch("/api/v1/miniapp/staff/invitations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        max_user_id: Number(apiContext.maxUserId),
        tenant_slug: apiContext.tenantSlug || undefined,
        role,
        expires_in_days: 7,
      }),
    });
    if (!response.ok) throw new Error(await parseApiError(response));
    const result = await response.json();
    state.staffInvitationRole = result.role || role;
    state.staffInvitationLink = result.invite_url || "";
    state.staffInvitationExpiresAt = result.expires_at || "";
    showNotice("Ссылка приглашения создана");
  } catch (error) {
    showNotice(error.message || "Не удалось создать приглашение", "danger");
  } finally {
    state.staffInvitationSaving = false;
    renderAdminPanel();
  }
}

async function copyStaffInvitation() {
  const copied = await copyTextToClipboard(state.staffInvitationLink);
  showNotice(copied ? "Ссылка скопирована" : "Не удалось скопировать ссылку", copied ? "ok" : "danger");
}

async function toggleStaffAssignment(maxUserId, role) {
  const assignment = staffAssignments.find(
    (item) => item.maxUserId === maxUserId && item.role === role,
  );
  if (!assignment) return;
  await updateStaffAssignment({
    targetMaxUserId: assignment.maxUserId,
    role: assignment.role,
    status: assignment.status === "revoked" ? "active" : "revoked",
    displayName: assignment.displayName,
  });
}

function updateCartQuantity(key, value) {
  if (!canUseStoreCart()) return;
  const item = state.cart.get(key);
  if (!item) return;
  const product = productById(item.productId);
  if (!product) return;

  const maxQuantity = Math.min(
    Math.max(productAvailable(product), item.quantity),
    MAX_CART_PRODUCT_QUANTITY,
  );
  item.quantity = clampQuantity(value, maxQuantity);
  state.cart.set(key, item);
  saveCart();
  renderProducts();
  renderCart();
}

async function undoAccrualBatch({ requestKey = "", targets = [], amount = 0, reason = "" }) {
  if (!targets.length || !amount) return;
  try {
    if (apiContext.demoMode || !apiContext.maxUserId || targets.some((student) => student.id.startsWith("demo-"))) {
      targets.forEach((student) => {
        student.balance = Math.max(Number(student.balance || 0) - amount, 0);
        ledger.unshift([todayShort(), `Отмена: ${reason}`, `-${amount} AC`, student.id]);
      });
    } else {
      const response = await apiFetch("/api/v1/miniapp/coins/accrue/undo", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          max_user_id: Number(apiContext.maxUserId),
          tenant_slug: apiContext.tenantSlug || undefined,
          request_key: requestKey,
        }),
      });
      if (!response.ok) throw new Error(await parseApiError(response));
      await loadSession();
    }
    renderAll();
    showNotice(`Начисление отменено: ${targets.length} учен.`);
  } catch (error) {
    showNotice(error.message || "Не удалось отменить начисление", "danger");
  }
}

async function accrueStudents(targets, amount, reason, groupLabel = "", customReason = false) {
  if (targets.length === 0) {
    showNotice("Выберите учеников для начисления", "danger");
    return;
  }
  if (state.accrualSaving) return;

  if (apiContext.demoMode || !apiContext.maxUserId || targets.some((student) => student.id.startsWith("demo-"))) {
    targets.forEach((student) => {
      student.balance += amount;
      ledger.unshift([
        todayShort(),
        groupLabel ? `${reason}: ${groupLabel}` : `${reason}: ${student.name}`,
        `+${amount} AC`,
        student.id,
      ]);
    });
    showNotice(`Начислено ${targets.length} учен.: по ${amount} AC · ${reason}`, "ok", {
      actionLabel: "Отменить",
      onAction: () => undoAccrualBatch({ targets, amount, reason }),
      duration: 5000,
    });
    state.selectedAccrualStudents.clear();
    renderAll();
    return;
  }

  state.accrualSaving = true;
  renderAccrual();
  try {
    const requestSignature = JSON.stringify({
      studentIds: targets.map((student) => student.id).sort(),
      amount,
      reason,
      groupLabel,
    });
    if (state.accrualRequestSignature !== requestSignature) {
      state.accrualRequestSignature = requestSignature;
      state.accrualRequestKey = createRequestKey();
    }
    const response = await apiFetch("/api/v1/miniapp/coins/accrue", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        max_user_id: Number(apiContext.maxUserId),
        tenant_slug: apiContext.tenantSlug || undefined,
        student_ids: targets.map((student) => student.id),
        amount,
        reason,
        custom_reason: customReason,
        comment: "Algo MAX",
        request_key: state.accrualRequestKey,
      }),
    });
    if (!response.ok) throw new Error(await parseApiError(response));

    const result = await response.json();
    const completedRequestKey = state.accrualRequestKey;
    await loadSession();
    state.selectedAccrualStudents.clear();
    state.accrualRequestKey = "";
    state.accrualRequestSignature = "";
    renderAll();
    showNotice(`Начислено ${result.credited_students} учен.: по ${amount} AC · ${reason}`, "ok", {
      actionLabel: "Отменить",
      onAction: () => undoAccrualBatch({ requestKey: completedRequestKey, targets, amount, reason }),
      duration: 5000,
    });
  } catch (error) {
    showNotice(error.message || "Не удалось начислить астрокоины", "danger");
  } finally {
    state.accrualSaving = false;
    renderAccrual();
  }
}

async function placeOrder() {
  if (!canUseStoreCart() || state.cart.size === 0 || state.orderSaving) return;

  const student = selectedStudent();
  const canUseBackend =
    apiContext.maxUserId && student && !student.id.startsWith("demo-") && state.catalogLoaded;
  if (!canUseBackend) {
    closeCheckoutDialog();
    createDemoOrder();
    return;
  }

  const orderItems = Array.from(state.cart.values()).map((item) => ({
    product_id: item.productId,
    quantity: item.quantity,
  }));
  const requestSignature = JSON.stringify({
    studentId: student.id,
    items: [...orderItems].sort((left, right) =>
      left.product_id.localeCompare(right.product_id),
    ),
  });
  if (state.orderRequestSignature !== requestSignature) {
    state.orderRequestSignature = requestSignature;
    state.orderRequestKey = createRequestKey();
  }

  const payload = {
    max_user_id: Number(apiContext.maxUserId),
    tenant_slug: apiContext.tenantSlug || undefined,
    student_id: student.id,
    items: orderItems,
    comment: "Algo MAX",
    request_key: state.orderRequestKey,
  };

  const button = qs("#confirmOrderButton");
  state.orderSaving = true;
  if (button) button.disabled = true;
  try {
    const response = await apiFetch("/api/v1/miniapp/orders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(await parseApiError(response));

    const result = await response.json();
    const isDigitalOrder = result.order.status === "issued_to_student";
    state.cart.clear();
    state.orderRequestKey = "";
    state.orderRequestSignature = "";
    await saveCart();
    closeCheckoutDialog();
    await refreshOrderAndInventoryState();
    if (isDigitalOrder) {
      state.orderStatusFilter = "issued";
      savePreferences();
    }
    setView("orders");
    showNotice(
      isDigitalOrder
        ? `Покупка готова. Откройте заказ №${result.order.order_number}, чтобы посмотреть и скопировать код.`
        : `Заказ №${result.order.order_number} оформлен и зарезервирован`,
    );
    renderAll();
  } catch (error) {
    closeCheckoutDialog();
    showNotice(error.message || "Не удалось оформить заказ", "danger");
    renderCart();
  } finally {
    state.orderSaving = false;
    if (button) button.disabled = false;
  }
}

document.addEventListener("click", (event) => {
  const clickedElement = event.target instanceof Element ? event.target : null;
  if (!clickedElement?.closest(".broadcast-message-control")) {
    closeBroadcastEmojiPicker();
  }
  const target = clickedElement?.closest("button") || null;
  if (!target) {
    const productCard = clickedElement?.closest("[data-product-card]");
    if (productCard) openProductDialog(productCard.dataset.productCard || "");
    return;
  }

  const codeToCopy = target.dataset.copyCode;
  if (codeToCopy) {
    copyTextToClipboard(codeToCopy)
      .then((copied) => showNotice(copied ? "Код скопирован" : "Не удалось скопировать код", copied ? "ok" : "danger"));
    return;
  }

  if (target.id === "cancelConfirmationButton") {
    settleConfirmation(false);
    return;
  }
  if (target.id === "confirmConfirmationButton") {
    settleConfirmation(true);
    return;
  }

  if (target.id === "noticeClose") {
    hideNotice();
    return;
  }
  if (target.id === "noticeAction" && noticeActionHandler) {
    const handler = noticeActionHandler;
    hideNotice();
    handler();
    return;
  }

  if (target.id === "railCollapseButton") {
    state.railCollapsed = !state.railCollapsed;
    savePreferences();
    applyRailState();
    return;
  }

  const activeStudentId = target.dataset.activeStudent;
  if (activeStudentId) {
    setActiveStudent(activeStudentId);
    return;
  }

  const summaryWarehouseOrders = target.dataset.confirmSummaryWarehouses;
  if (summaryWarehouseOrders) {
    void assignSummaryOrderWarehouses(summaryWarehouseOrders, target);
    return;
  }

  const previewStudentId = target.dataset.openStudentQr;
  if (previewStudentId) {
    openStudentQrPreview(previewStudentId);
    return;
  }

  const savedQrStudentId = target.dataset.saveStudentQr;
  if (savedQrStudentId) {
    void saveStudentQrImage(savedQrStudentId, target);
    return;
  }

  const copiedStudentLinkId = target.dataset.copyStudentLink;
  if (copiedStudentLinkId) {
    void copyStudentInvitationLink(copiedStudentLinkId);
    return;
  }

  const openedQrFileStudentId = target.dataset.openStudentQrFile;
  if (openedQrFileStudentId) {
    openStudentQrFile(openedQrFileStudentId);
    return;
  }

  if ("loadTeacherQr" in target.dataset) {
    void loadTeacherInvitations(true);
  }

  if (target.id === "closeStudentQrDialogButton") {
    closeStudentQrPreview();
    return;
  }

  if ("mobileMore" in target.dataset) {
    toggleMobileMorePanel();
    return;
  }
  if (target.id === "closeMobileMoreButton") {
    closeMobileMorePanel();
    return;
  }

  const role = target.dataset.role;
  if (role) setRole(role);

  const view = target.dataset.view || target.dataset.viewJump;
  if (view) setView(view);

  if (target.id === "previewBroadcastButton") {
    previewBroadcastAudience();
  }
  if (target.id === "broadcastEmojiButton") {
    toggleBroadcastEmojiPicker();
    return;
  }
  const broadcastEmoji = target.dataset.broadcastEmoji;
  if (broadcastEmoji) {
    insertBroadcastEmoji(broadcastEmoji);
    return;
  }
  if (target.id === "saveBroadcastDraftButton") saveBroadcastDraft();
  const broadcastStep = target.dataset.broadcastStep;
  if (broadcastStep) setBroadcastStep(broadcastStep);
  const broadcastStepDirection = target.dataset.broadcastStepNav;
  if (broadcastStepDirection) moveBroadcastStep(broadcastStepDirection);
  const duplicateBroadcastId = target.dataset.duplicateBroadcast || target.dataset.retryBroadcast;
  if (duplicateBroadcastId) duplicateBroadcast(duplicateBroadcastId);

  if ("reloadBroadcastTargets" in target.dataset) {
    void loadBroadcastTargetOptions(true);
  }
  if (target.id === "addBroadcastVenueButton") openBroadcastVenueEditor();
  const broadcastVenueId = target.dataset.editBroadcastVenue;
  if (broadcastVenueId) openBroadcastVenueEditor(broadcastVenueId);
  if (
    target.id === "closeBroadcastVenueEditor" ||
    target.id === "cancelBroadcastVenueButton"
  ) {
    closeBroadcastVenueEditor();
  }
  if (target.id === "saveBroadcastVenueButton") void saveBroadcastVenue();
  if (target.dataset.broadcastModes === "all") {
    state.broadcastSelectedLessonModes.clear();
    invalidateBroadcastPreview();
    queueBroadcastDraftSave();
    renderBroadcasts();
  }
  if (target.dataset.broadcastVenues === "all") {
    state.broadcastSelectedVenues.clear();
    invalidateBroadcastPreview();
    queueBroadcastDraftSave();
    renderBroadcasts();
  }

  const broadcastGroupAction = target.dataset.broadcastGroups;
  if (broadcastGroupAction === "all") {
    state.broadcastAllGroups = true;
    state.broadcastSelectedGroups.clear();
    invalidateBroadcastPreview();
    renderBroadcastGroups();
  } else if (broadcastGroupAction === "none") {
    state.broadcastAllGroups = false;
    state.broadcastSelectedGroups.clear();
    invalidateBroadcastPreview();
    renderBroadcastGroups();
  }

  if ("removeBroadcastPhoto" in target.dataset) {
    clearBroadcastPhoto();
    refreshIcons();
  }

  const addId = target.dataset.add;
  if (addId) addToCart(addId);

  if (target.id === "clearProductSearch") {
    qs("#productSearch").value = "";
    renderProducts();
    qs("#productSearch").focus();
  }
  if (target.id === "clearOrderSearch") {
    state.orderSearch = "";
    renderOrders();
    qs("#orderSearch")?.focus();
  }
  if ("clearFulfillmentSearch" in target.dataset) {
    state.orderSearch = "";
    renderOrders();
    qs("#fulfillmentOrderSearch")?.focus();
    return;
  }

  if (target.id === "mobileStoreFiltersButton") {
    state.storeFiltersOpen = !state.storeFiltersOpen;
    renderProducts();
  }
  if (target.id === "closeStoreFiltersButton" || target.id === "storeFilterBackdrop") {
    state.storeFiltersOpen = false;
    renderProducts();
  }

  const recentProductSearch = target.dataset.recentProductSearch;
  if (recentProductSearch) {
    qs("#productSearch").value = recentProductSearch;
    renderProducts();
  }

  const productDetailsId = target.dataset.productDetails;
  if (productDetailsId) openProductDialog(productDetailsId);

  const favoriteId = target.dataset.favorite;
  if (favoriteId) {
    const wasFavorite = state.favorites.has(favoriteId);
    if (wasFavorite) state.favorites.delete(favoriteId);
    else state.favorites.add(favoriteId);
    saveFavorites();
    renderProducts();
    showNotice(wasFavorite ? "Убрано из избранного" : "Добавлено в избранное", "ok", { duration: 2200 });
  }

  const productCategory = target.dataset.productCategory;
  if (productCategory) {
    state.productCategory = productCategory;
    qs("#categoryFilter").value = productCategory;
    renderCategories();
    renderProducts();
    savePreferences();
  }

  if ("showAllProducts" in target.dataset) {
    state.favoritesOnly = false;
    renderProducts();
    savePreferences();
  }

  const removeId = target.dataset.remove;
  if (removeId) {
    state.cart.delete(removeId);
    saveCart();
    renderProducts();
    renderCart();
  }

  const cartStep = Number(target.dataset.cartStep || 0);
  const cartStepKey = target.dataset.cartKey;
  if (cartStep && cartStepKey) {
    const item = state.cart.get(cartStepKey);
    if (item) updateCartQuantity(cartStepKey, Number(item.quantity || 1) + cartStep);
  }

  const adminTab = target.dataset.adminTab;
  if (adminTab) {
    state.adminTab = adminTab;
    state.adminEntitySearch = "";
    renderAdminPanel();
    if (adminTab === "history") void loadAdminHistory();
  }

  if ("retryAdminHistory" in target.dataset) {
    void loadAdminHistory(true);
  }

  const studentRegistryStatusFilter = target.dataset.studentRegistryStatus;
  if (["all", "active", "departed", "archived"].includes(studentRegistryStatusFilter)) {
    state.studentRegistryStatusFilter = studentRegistryStatusFilter;
    state.studentRegistryVisibleCount = STUDENT_REGISTRY_PAGE_SIZE;
    renderStudentRegistry();
  }

  if ("showMoreStudents" in target.dataset) {
    state.studentRegistryVisibleCount += STUDENT_REGISTRY_PAGE_SIZE;
    renderStudentRegistry();
  }

  if ("retryStudentRegistry" in target.dataset) {
    void loadAdminStudents(true);
  }

  const studentLedgerId = target.dataset.retryStudentLedger;
  if (studentLedgerId) {
    void loadStudentLedger(studentLedgerId, true);
  }

  if ("toggleStudentCreate" in target.dataset) {
    state.studentCreateOpen = !state.studentCreateOpen;
    renderStudentRegistry();
    if (state.studentCreateOpen) qs('#studentCreateForm input[name="last_name"]')?.focus();
  }

  if ("closeStudentCreate" in target.dataset) {
    state.studentCreateOpen = false;
    renderStudentRegistry();
  }

  if ("clearAccessFreeze" in target.dataset) {
    const from = qs("#studentAccessFreezeFrom");
    const until = qs("#studentAccessFreezeUntil");
    if (from) from.value = "";
    if (until) until.value = "";
    target.disabled = true;
  }

  if ("resetStudentRegistry" in target.dataset) {
    state.studentRegistrySearch = "";
    state.studentRegistryStatusFilter = "all";
    state.studentRegistryGroupFilter = "all";
    state.studentRegistryVisibleCount = STUDENT_REGISTRY_PAGE_SIZE;
    renderStudentRegistry();
  }

  const orderStatus = target.dataset.orderStatus;
  if (orderStatus) {
    state.orderStatusFilter = orderStatus;
    if (state.view !== "orders") setView("orders");
    renderOrders();
    savePreferences();
  }

  const fulfillmentVenuesAction = target.dataset.fulfillmentVenues;
  if (["open", "close"].includes(fulfillmentVenuesAction)) {
    const shouldOpen = fulfillmentVenuesAction === "open";
    qsa("#orderFulfillmentSummary .fulfillment-venue").forEach((venue) => {
      venue.open = shouldOpen;
    });
  }

  if ("fulfillmentAssignSelected" in target.dataset) {
    void assignSummaryOrderWarehouses(
      [...state.selectedFulfillmentOrders].join(","),
      target,
    );
    return;
  }

  if ("fulfillmentConfirmPicks" in target.dataset) {
    void confirmFulfillmentPickDraft();
    return;
  }

  if ("fulfillmentDeliverSelected" in target.dataset) {
    void deliverSummaryOrders(
      [...state.selectedFulfillmentOrders].join(","),
      target,
    );
    return;
  }

  if ("refreshFulfillment" in target.dataset) {
    void refreshAllData();
    return;
  }

  const staffStatusFilter = target.dataset.staffStatusFilter;
  if (["active", "revoked", "all"].includes(staffStatusFilter)) {
    state.staffStatusFilter = staffStatusFilter;
    renderAdminPanel();
  }

  const opsJump = target.dataset.opsJump;
  if (opsJump === "orders") {
    state.orderStatusFilter = "all";
    setView("orders");
    renderOrders();
  } else if (["inventory", "products", "warehouses"].includes(opsJump)) {
    state.adminTab = opsJump === "inventory" ? "products" : opsJump;
    setView("admin");
    renderAdminPanel();
  }

  const orderId = target.dataset.openOrder;
  if (orderId) openOrderDetails(orderId);

  const orderActionId = target.dataset.orderActionId;
  const orderAction = target.dataset.orderAction;
  if (orderActionId && orderAction) {
    if (orderAction === "cancel") {
      openOrderDetails(orderActionId);
      showCancelOrderForm(orderActionId);
    } else {
      updateOrderAction(orderActionId, orderAction);
    }
  }

  const confirmCancelOrderId = target.dataset.confirmOrderCancel;
  if (confirmCancelOrderId) {
    const reason = qs("#orderCancelReason")?.value || "";
    const customReason = qs("#orderCancelCustomReason")?.value.trim() || "";
    const productId = qs("#orderCancelProduct")?.value || "";
    if (!reason) {
      showNotice("Выберите причину отмены", "danger");
      qs("#orderCancelReason")?.focus();
      return;
    }
    if (reason === "Другое" && !customReason) {
      showNotice("Укажите свою причину отмены", "danger");
      qs("#orderCancelCustomReason")?.focus();
      return;
    }
    if (reason === "Товар закончился" && !productId) {
      showNotice("Выберите закончившийся товар", "danger");
      qs("#orderCancelProduct")?.focus();
      return;
    }
    updateOrderAction(confirmCancelOrderId, "cancel", {
      reason,
      customReason,
      productId: reason === "Товар закончился" ? productId : "",
    });
  }

  const cancelOrderBackId = target.dataset.cancelOrderBack;
  if (cancelOrderBackId) {
    const order = orders.find(
      (item) => item.backendId === cancelOrderBackId || item.id === cancelOrderBackId,
    );
    if (order) renderOrderDialog(order);
  }

  if (target.id === "assignOrderWarehousesButton") {
    assignOrderWarehouses(target.dataset.orderId || "");
  }

  if (target.id === "loadAcReportButton") {
    loadAccrualReport();
  }

  const reportPeriod = target.dataset.reportPeriod;
  if (reportPeriod) setAccrualReportPeriod(reportPeriod);
  if (target.id === "resetAcReportFiltersButton") {
    state.accrualReportTeacherFilter = "all";
    state.accrualReportGroupFilter = "all";
    renderAccrualReport();
  }

  if ("selectedAccrual" in target.dataset) {
    accrueSelectedStudents();
  }

  const removeAccrualRule = target.closest("[data-remove-accrual-rule]");
  if (removeAccrualRule) {
    state.accrualRulesDraft = readAccrualRulesEditor();
    state.accrualRulesDraft.splice(Number(removeAccrualRule.dataset.removeAccrualRule), 1);
    renderAccrualRulesEditor();
  }

  if (target.id === "addAccrualRuleButton") {
    state.accrualRulesDraft = readAccrualRulesEditor();
    state.accrualRulesDraft.push({ reason: "", amount: 10, isActive: true });
    renderAccrualRulesEditor();
    qs("[data-accrual-rule-row]:last-child [data-accrual-rule-reason]")?.focus();
  }

  const accrualSelection = target.dataset.accrualSelect;
  if (accrualSelection === "visible") {
    const query = state.accrualNameFilter.trim().toLowerCase();
    studentsForGroup(state.accrualGroup).filter((student) => student.name.toLowerCase().includes(query)).forEach((student) => state.selectedAccrualStudents.add(student.id));
    renderAccrual();
  } else if (accrualSelection === "none") {
    state.selectedAccrualStudents.clear();
    renderAccrual();
  }
  if ("clearAccrualSearch" in target.dataset || target.id === "clearAccrualSearch") {
    state.accrualNameFilter = "";
    renderAccrual();
    qs("#accrualNameFilter")?.focus();
  }
  const editWarehouseId = target.dataset.editWarehouse;
  if (editWarehouseId) {
    state.editingWarehouseId = editWarehouseId;
    state.warehouseEditorOpen = true;
    renderAdminPanel();
  }

  if (target.id === "warehouseCreateButton") {
    state.editingWarehouseId = "";
    state.warehouseEditorOpen = true;
    renderAdminPanel();
  }

  if (target.id === "warehouseCancelEditButton") {
    state.editingWarehouseId = "";
    state.warehouseEditorOpen = false;
    renderAdminPanel();
  }

  if (target.id === "warehouseSaveButton") {
    saveWarehouseFromForm();
  }

  if (target.id === "saveWarehousePreferenceButton") {
    saveWarehousePreference();
  }

  const contactStudentId = target.dataset.toggleContact;
  if (contactStudentId) toggleContactLink(contactStudentId);

  const staffNotificationAccountId = target.dataset.staffNotifications;
  if (staffNotificationAccountId) {
    void openStaffNotificationSettings(staffNotificationAccountId);
    return;
  }

  if (target.id === "closeStaffNotificationDialogButton") {
    closeStaffNotificationSettings();
    return;
  }
  if (target.id === "resetStaffNotificationsButton") {
    resetStaffNotificationSettings();
    return;
  }
  if (target.id === "saveStaffNotificationsButton") {
    void saveStaffNotificationSettings();
    return;
  }

  const staffMaxUserId = target.dataset.toggleStaff;
  const staffRole = target.dataset.staffRole;
  if (staffMaxUserId && staffRole) {
    toggleStaffAssignment(staffMaxUserId, staffRole);
  }

  if (target.id === "productImportButton") {
    importProductsFromFile();
  }

  if (target.id === "crmPreviewButton") {
    importCrmStudents(true);
  }

  if (target.id === "crmImportButton") {
    importCrmStudents(false);
  }

  const editProductId = target.dataset.editProduct;
  if (editProductId) {
    resetProductPhotoSelection();
    state.adminTab = "products";
    state.editingProductId = editProductId;
    state.productEditorOpen = true;
    if (state.view !== "admin") setView("admin");
    renderAdminPanel();
  }

  if ("openProductWarehouses" in target.dataset) {
    resetProductPhotoSelection();
    state.editingProductId = "";
    state.productEditorOpen = false;
    state.adminTab = "warehouses";
    renderAdminPanel();
  }

  if (target.id === "productCreateButton") {
    resetProductPhotoSelection();
    state.editingProductId = "";
    state.productEditorOpen = true;
    renderAdminPanel();
  }

  if (
    target.id === "productCancelEditButton" ||
    target.id === "productCancelEditButtonBottom"
  ) {
    resetProductPhotoSelection();
    state.editingProductId = "";
    state.productEditorOpen = false;
    renderAdminPanel();
  }

  if (target.id === "productSaveButton") {
    saveProductFromForm();
  }

  if ("clearAdminSearch" in target.dataset) {
    state.adminEntitySearch = "";
    state.productStatusFilter = "all";
    state.productCategoryFilter = "all";
    state.accessStatusFilter = "all";
    state.accessRoleFilter = "all";
    state.staffRoleFilter = "all";
    renderAdminPanel();
  }
  if ("clearStudentRegistrySearch" in target.dataset) {
    state.studentRegistrySearch = "";
    state.studentRegistryVisibleCount = STUDENT_REGISTRY_PAGE_SIZE;
    renderStudentRegistry();
  }
  const productStatusId = target.dataset.toggleProductStatus;
  if (productStatusId) toggleProductStatus(productStatusId);
  if ("removeProductPhoto" in target.dataset) {
    resetProductPhotoSelection();
    state.productPhotoRemoved = true;
    renderAdminPanel();
  }
  if ("cropProductPhoto" in target.dataset) cropProductPhoto();

  if (target.id === "staffSaveButton") {
    saveStaffAssignmentFromForm();
  }

  if (target.id === "staffCreateButton") {
    state.staffInvitationOpen = false;
    state.staffEditorOpen = true;
    renderAdminPanel();
  }

  if (target.id === "staffInviteButton") {
    state.staffEditorOpen = false;
    state.staffInvitationOpen = true;
    state.staffInvitationRole = "teacher";
    state.staffInvitationLink = "";
    state.staffInvitationExpiresAt = "";
    renderAdminPanel();
  }

  if (target.id === "staffInvitationCreateButton") {
    void createStaffInvitation();
  }

  if (target.id === "staffInvitationCopyButton") {
    void copyStaffInvitation();
  }

  if (target.id === "staffInvitationCancelButton") {
    state.staffInvitationOpen = false;
    state.staffInvitationLink = "";
    state.staffInvitationExpiresAt = "";
    renderAdminPanel();
  }

  if (target.id === "staffCancelButton") {
    state.staffEditorOpen = false;
    renderAdminPanel();
  }

  if (target.id === "closeCheckoutButton" || target.id === "cancelCheckoutButton") {
    closeCheckoutDialog();
  }

  if (target.id === "confirmOrderButton") {
    placeOrder();
  }

  if (target.id === "closeProductDialogButton" || target.id === "productDialogBackButton") {
    closeProductDialog();
  }

  if (target.id === "productDialogAddButton") {
    addProductDialogItemToCart();
  }

  if (target.id === "closeOrderDialogButton") {
    closeOrderDialog();
  }
});

qs("#checkoutDialog").addEventListener("click", (event) => {
  if (event.target === event.currentTarget) closeCheckoutDialog();
});

qs("#productDialog").addEventListener("click", (event) => {
  if (event.target === event.currentTarget) closeProductDialog();
});

qs("#orderDialog").addEventListener("click", (event) => {
  if (event.target === event.currentTarget) closeOrderDialog();
});

qs("#studentQrDialog").addEventListener("click", (event) => {
  if (event.target === event.currentTarget) closeStudentQrPreview();
});

qs("#confirmationDialog").addEventListener("click", (event) => {
  if (event.target === event.currentTarget) settleConfirmation(false);
});

qs("#staffNotificationDialog").addEventListener("click", (event) => {
  if (event.target === event.currentTarget) closeStaffNotificationSettings();
});

document.addEventListener("keydown", (event) => {
  const productCard = event.target instanceof Element ? event.target.closest("[data-product-card]") : null;
  if (productCard && !event.target.closest("button, input, select, textarea, a") && ["Enter", " "].includes(event.key)) {
    event.preventDefault();
    openProductDialog(productCard.dataset.productCard || "");
    return;
  }
  if (event.key !== "Escape") return;
  if (!qs("#broadcastEmojiPicker")?.hidden) {
    closeBroadcastEmojiPicker();
    qs("#broadcastEmojiButton")?.focus();
    return;
  }
  if (!qs("#confirmationDialog").hidden) {
    settleConfirmation(false);
    return;
  }
  if (!qs("#staffNotificationDialog").hidden) {
    closeStaffNotificationSettings();
    return;
  }
  if (!qs("#studentQrDialog").hidden) {
    closeStudentQrPreview();
    return;
  }
  if (!qs("#mobileMorePanel").hidden) {
    closeMobileMorePanel();
    return;
  }
  if (!qs("#productDialog").hidden) {
    closeProductDialog();
    return;
  }
  if (!qs("#orderDialog").hidden) {
    closeOrderDialog();
    return;
  }
  if (!qs("#checkoutDialog").hidden) closeCheckoutDialog();
});

document.addEventListener("change", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLInputElement) && !(target instanceof HTMLSelectElement)) return;

  if (target.id === "orderCancelReason") {
    syncCancelOrderForm();
    if (target.value === "Другое") qs("#orderCancelCustomReason")?.focus();
    return;
  }

  const orderPickGroup = target.dataset.orderPickGroup;
  if (orderPickGroup) {
    stageFulfillmentPickRows(
      fulfillmentPickGroups.get(orderPickGroup) || [],
      target.checked,
    );
    return;
  }

  const fulfillmentOrderIdValue = target.dataset.fulfillmentOrderSelect;
  if (fulfillmentOrderIdValue) {
    if (target.checked) state.selectedFulfillmentOrders.add(fulfillmentOrderIdValue);
    else state.selectedFulfillmentOrders.delete(fulfillmentOrderIdValue);
    renderOrderFulfillmentSummary();
    refreshIcons();
    return;
  }

  const fulfillmentSelectAll = target.dataset.fulfillmentSelectAll;
  if (fulfillmentSelectAll) {
    const orderIds = String(target.dataset.orderIds || "").split(",").filter(Boolean);
    orderIds.forEach((orderId) => {
      if (target.checked) state.selectedFulfillmentOrders.add(orderId);
      else state.selectedFulfillmentOrders.delete(orderId);
    });
    renderOrderFulfillmentSummary();
    refreshIcons();
    return;
  }

  if (target.dataset.staffNotificationKey) {
    syncStaffNotificationGroupCounts();
    return;
  }

  if (target.id === "productImportFile") {
    const file = target.files?.[0] || null;
    state.productImportFile = file;
    state.productImportFileName = file?.name || "";
    const label = target.closest(".file-picker")?.querySelector("span");
    if (label) label.textContent = state.productImportFileName || "Выбрать файл";
  }

  if (target.id === "productPhotoFile") {
    const file = target.files?.[0] || null;
    if (file && selectProductPhoto(file)) {
      renderAdminPanel();
    } else {
      target.value = "";
    }
  }

  if (target.id === "productFulfillmentType") {
    const codeEditor = qs(".product-code-editor");
    const inventoryEditor = qs(".product-inventory-editor");
    if (codeEditor) codeEditor.hidden = target.value !== "digital_code";
    if (inventoryEditor) inventoryEditor.hidden = target.value !== "warehouse";
  }

  const productWarehouseId = target.dataset.productWarehouseSelect;
  if (productWarehouseId) {
    syncProductInventoryEditor();
  }

  if (target.id === "broadcastPhotoFile") {
    const file = target.files?.[0] || null;
    if (file && !selectBroadcastPhoto(file)) {
      target.value = "";
    }
  }

  if (target.id === "crmImportFile") {
    const file = target.files?.[0] || null;
    state.crmImportFile = file;
    state.crmImportFileName = file?.name || "";
    state.crmImportPreview = null;
    renderAdminPanel();
  }

  if (target.id === "crmStudentStatus") {
    state.crmStudentStatus = target.value;
    state.crmImportPreview = null;
    renderAdminPanel();
  }

  if (target.id === "studentGroupFilter") {
    state.studentGroupFilter = target.value;
    renderStudents();
  }

  if (target.id === "accrualGroupSelect") {
    state.accrualGroup = target.value;
    state.selectedAccrualStudents.clear();
    renderAccrual();
  }

  if (target.id === "groupAccrualReason") {
    renderAccrual();
  }

  const accrualStudentId = target.dataset.accrualStudentCheck;
  if (accrualStudentId) {
    if (target.checked) state.selectedAccrualStudents.add(accrualStudentId);
    else state.selectedAccrualStudents.delete(accrualStudentId);
    renderAccrual();
  }

  if (target.id === "productStatusFilter") {
    state.productStatusFilter = target.value;
    renderAdminPanel();
  }
  if (target.id === "studentRegistryGroupFilter") {
    state.studentRegistryGroupFilter = target.value;
    state.studentRegistryVisibleCount = STUDENT_REGISTRY_PAGE_SIZE;
    renderStudentRegistry();
  }
  if (target.id === "teacherQrGroupFilter") {
    state.teacherInvitationGroup = target.value;
    renderTeacherInvitations();
  }
  if (target.id === "productCategoryFilter") {
    state.productCategoryFilter = target.value;
    renderAdminPanel();
  }
  if (target.id === "accessStatusFilter") {
    state.accessStatusFilter = target.value;
    renderAdminPanel();
  }
  if (target.id === "accessRoleFilter") {
    state.accessRoleFilter = target.value;
    renderAdminPanel();
  }
  if (target.id === "staffRoleFilter") {
    state.staffRoleFilter = target.value;
    renderAdminPanel();
  }
  if (target.id === "staffInvitationRoleSelect") {
    state.staffInvitationRole = target.value;
    state.staffInvitationLink = "";
    state.staffInvitationExpiresAt = "";
    renderAdminPanel();
  }
  if (target.id === "adminHistoryPeriod") {
    state.adminHistoryPeriod = Number(target.value) || 30;
    state.adminHistoryLoaded = false;
    renderAdminPanel();
    void loadAdminHistory(true);
  }

  if (
    target.id === "broadcastRecipientCategory" ||
    target.id === "broadcastAudienceFilter"
  ) {
    invalidateBroadcastPreview();
    queueBroadcastDraftSave();
    renderBroadcasts();
  }

  if ("broadcastLessonMode" in target.dataset) {
    if (target.checked) state.broadcastSelectedLessonModes.add(target.value);
    else state.broadcastSelectedLessonModes.delete(target.value);
    setBroadcastFilterChipState(target.closest(".broadcast-filter-chip"), target.checked);
    invalidateBroadcastPreview();
    queueBroadcastDraftSave();
    renderBroadcasts();
  }

  if ("broadcastVenue" in target.dataset) {
    if (target.checked) state.broadcastSelectedVenues.add(target.value);
    else state.broadcastSelectedVenues.delete(target.value);
    setBroadcastFilterChipState(target.closest(".broadcast-filter-chip"), target.checked);
    invalidateBroadcastPreview();
    queueBroadcastDraftSave();
    renderBroadcasts();
  }

  const broadcastVenueGroup = target.dataset.broadcastVenueGroup;
  if (broadcastVenueGroup && state.broadcastVenueDraft) {
    if (target.checked) state.broadcastVenueDraft.groups.add(broadcastVenueGroup);
    else state.broadcastVenueDraft.groups.delete(broadcastVenueGroup);
    target
      .closest(".broadcast-venue-group-option")
      ?.classList.toggle("is-selected", target.checked);
    renderBroadcastVenueSelectionSummary();
  }

  const broadcastGroupName = target.dataset.broadcastGroup;
  if (broadcastGroupName) {
    if (state.broadcastAllGroups) {
      state.broadcastAllGroups = false;
      state.broadcastSelectedGroups = new Set(availableBroadcastGroups());
    }
    if (target.checked) state.broadcastSelectedGroups.add(broadcastGroupName);
    else state.broadcastSelectedGroups.delete(broadcastGroupName);
    invalidateBroadcastPreview();
    queueBroadcastDraftSave();
    renderBroadcastGroups();
  }

  if (target.id === "productDialogQuantity") {
    syncProductDialogControls();
  }

  if (target.id === "acReportDateFrom" || target.id === "acReportDateTo") {
    state.accrualReportPeriod = "custom";
    qsa("[data-report-period]").forEach((button) => button.classList.remove("is-active"));
  }

  if (target.id === "acReportTeacherFilter") {
    state.accrualReportTeacherFilter = target.value;
    renderAccrualReport();
  }
  if (target.id === "acReportGroupFilter") {
    state.accrualReportGroupFilter = target.value;
    renderAccrualReport();
  }

  const cartQuantityKey = target.dataset.cartQuantity;
  if (cartQuantityKey) {
    updateCartQuantity(cartQuantityKey, target.value);
  }

});

document.addEventListener("input", (event) => {
  const target = event.target;
  if (target instanceof HTMLTextAreaElement && target.id === "broadcastMessage") {
    const count = qs("#broadcastMessageCount");
    if (count) count.textContent = String(target.value.length);
    queueBroadcastDraftSave();
    renderBroadcastLivePreview();
    return;
  }
  if (!(target instanceof HTMLInputElement)) return;

  if (target.dataset.productWarehouseQuantity) {
    syncProductInventoryEditor();
    return;
  }

  if (target.id === "broadcastTitle") {
    queueBroadcastDraftSave();
    renderBroadcastLivePreview();
  }

  if (target.id === "broadcastVenueName" && state.broadcastVenueDraft) {
    state.broadcastVenueDraft.name = target.value;
  }
  if (target.id === "broadcastVenueKeywords" && state.broadcastVenueDraft) {
    state.broadcastVenueDraft.keywords = target.value;
  }
  if (target.id === "broadcastVenueGroupSearch") {
    renderBroadcastVenueEditorGroups();
  }

  if (target.id === "tenantSearch") {
    state.tenantSearch = target.value;
    renderTenantDialog();
  }

  if (target.id === "productDialogQuantity") {
    syncProductDialogControls();
  }

  if (target.id === "orderSearch") {
    state.orderSearch = target.value;
    renderOrders();
  }

  if (target.id === "fulfillmentOrderSearch") {
    state.orderSearch = target.value;
    const cursor = target.selectionStart ?? target.value.length;
    window.clearTimeout(orderSearchTimer);
    orderSearchTimer = window.setTimeout(() => {
      renderOrders();
      const input = qs("#fulfillmentOrderSearch");
      input?.focus();
      input?.setSelectionRange(cursor, cursor);
    }, 120);
  }

  if (target.id === "adminEntitySearch") {
    state.adminEntitySearch = target.value;
    const cursor = target.selectionStart ?? target.value.length;
    window.clearTimeout(adminSearchTimer);
    adminSearchTimer = window.setTimeout(() => {
      renderAdminPanel();
      const input = qs("#adminEntitySearch");
      input?.focus();
      input?.setSelectionRange(cursor, cursor);
    }, 120);
  }

  if (target.id === "studentRegistrySearch") {
    state.studentRegistrySearch = target.value;
    state.studentRegistryVisibleCount = STUDENT_REGISTRY_PAGE_SIZE;
    const cursor = target.selectionStart ?? target.value.length;
    window.clearTimeout(adminSearchTimer);
    adminSearchTimer = window.setTimeout(() => {
      renderStudentRegistry();
      const input = qs("#studentRegistrySearch");
      input?.focus();
      input?.setSelectionRange(cursor, cursor);
    }, 120);
  }

  if (target.id === "accrualNameFilter") {
    state.accrualNameFilter = target.value;
    window.clearTimeout(accrualSearchTimer);
    accrualSearchTimer = window.setTimeout(renderAccrual, 140);
  }
  if (target.id === "customAccrualReason" || target.id === "customAccrualAmount") {
    renderAccrual();
  }

  if (target.id === "broadcastBalanceThreshold") {
    invalidateBroadcastPreview();
    queueBroadcastDraftSave();
  }
});

document.addEventListener(
  "error",
  (event) => {
    const image = event.target;
    if (
      !(image instanceof HTMLImageElement) ||
      !image.closest(
        ".product-visual, .product-dialog-visual, .admin-product-thumb, .product-photo-picker",
      )
    ) return;
    image.remove();
  },
  true,
);

qs("#studentSelect").addEventListener("change", (event) => {
  setActiveStudent(event.target.value);
});
qs("#openCartButton").addEventListener("click", () => setView("cart"));
qs("#openWalletButton")?.addEventListener("click", () => setView("wallet"));
qs("#refreshDataButton").addEventListener("click", refreshAllData);
qs("#tenantSwitcherButton")?.addEventListener("click", openTenantDialog);
qs("#openAccrualRulesButton")?.addEventListener("click", openAccrualRulesDialog);
qs("#closeAccrualRulesButton")?.addEventListener("click", closeAccrualRulesDialog);
qs("#cancelAccrualRulesButton")?.addEventListener("click", closeAccrualRulesDialog);
qs("#saveAccrualRulesButton")?.addEventListener("click", saveAccrualRules);
qs("#accrualRulesDialog")?.addEventListener("click", (event) => {
  if (event.target === event.currentTarget) closeAccrualRulesDialog();
});
qs("#closeTenantDialogButton")?.addEventListener("click", closeTenantDialog);
qs("#showTenantCreateButton")?.addEventListener("click", () => setTenantCreateMode(true));
qs("#cancelTenantCreateButton")?.addEventListener("click", () => setTenantCreateMode(false));
qs("#tenantCreateForm")?.addEventListener("submit", createTenantFromForm);
document.addEventListener("submit", (event) => {
  if (event.target?.id === "studentAccessPolicyForm") {
    void saveStudentAccessPolicy(event);
  } else if (event.target?.id === "studentCreateForm") {
    void createAdminStudent(event);
  } else if (event.target?.dataset?.studentBirthDateForm) {
    void updateAdminStudentBirthDate(event);
  } else if (event.target?.dataset?.studentStatusForm) {
    void updateAdminStudentStatus(event);
  } else if (event.target?.dataset?.studentBalanceForm) {
    void updateAdminStudentBalance(event);
  }
});
document.addEventListener(
  "toggle",
  (event) => {
    const card = event.target;
    if (!(card instanceof HTMLDetailsElement) || !card.open || !card.dataset.studentCard) return;
    void loadStudentLedger(card.dataset.studentCard);
  },
  true,
);
qs("#tenantDialog")?.addEventListener("click", (event) => {
  if (event.target === event.currentTarget) closeTenantDialog();
});
qs("#productSearch").addEventListener("input", renderProducts);
qs("#productSearch").addEventListener("focus", renderRecentProductSearches);
qs("#productSearch").addEventListener("blur", () => {
  rememberProductSearch();
  window.setTimeout(renderRecentProductSearches, 120);
});
qs("#productSearch").addEventListener("keydown", (event) => {
  if (event.key === "Enter") rememberProductSearch();
});
qs("#categoryFilter").addEventListener("change", () => {
  renderProducts();
  savePreferences();
});
qs("#productSort").addEventListener("change", () => {
  renderProducts();
  savePreferences();
});
qs("#inStockOnly").addEventListener("change", () => {
  renderProducts();
  savePreferences();
});
qs("#favoritesFilter").addEventListener("click", () => {
  state.favoritesOnly = !state.favoritesOnly;
  renderProducts();
  savePreferences();
});
qs("#placeOrderButton").addEventListener("click", openCheckoutDialog);
qs("#storeCartBar").addEventListener("click", () => setView("cart"));
qs("#broadcastForm")?.addEventListener("submit", sendSchoolBroadcast);
qs("#mobileMoreBackdrop")?.addEventListener("click", closeMobileMorePanel);
async function init() {
  qs("#tenantTitle").textContent = tenantTitle();
  restorePreferences();
  applyDemoRole();
  qs("#productSort").value = state.productSort;
  qs("#inStockOnly").checked = state.inStockOnly;
  const results = [];
  results.push(
    await Promise.resolve(loadSession()).then(
      () => ({ status: "fulfilled" }),
      (reason) => ({ status: "rejected", reason }),
    ),
  );
  const sessionError = results.find((result) => result.status === "rejected");
  if (sessionError && !apiContext.demoMode) {
    state.hasAccess = false;
  }
  if (
    applyAccessGate(
      sessionError
        ? "Не удалось проверить привязку профиля. Откройте бота и попробуйте войти снова."
        : state.accessMessage || "",
    )
  ) {
    document.body.classList.remove("is-booting");
    return;
  }
  results.push(
    ...(await Promise.all([
      Promise.resolve(loadCatalog()).then(
        () => ({ status: "fulfilled" }),
        (reason) => ({ status: "rejected", reason }),
      ),
      Promise.resolve(loadOpsSummary()).then(
        () => ({ status: "fulfilled" }),
        (reason) => ({ status: "rejected", reason }),
      ),
    ])),
  );
  results
    .filter((result) => result.status === "rejected")
    .forEach((result) => console.warn(result.reason));

  restoreFavorites();
  restoreBroadcastDraft();

  setRole(state.role);
  if (apiContext.demoMode || state.catalogLoaded) restoreCart();
  await loadServerCart(state.activeStudentId);
  await loadParentInvitations();
  if (primaryStaffRole() === "teacher") await loadTeacherInvitations();
  setView(state.view);
  state.lastSyncAt = new Date();
  renderAll();
  renderSyncStatus();
  refreshIcons();
  document.body.classList.remove("is-booting");
  if (queryParam("focus") === "qr" && state.role === "parent") {
    window.setTimeout(() => {
      qs("#parentInvitesPanel")?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    }, 80);
  }
  if (
    apiContext.productId &&
    ["student", "parent"].includes(state.role) &&
    productById(apiContext.productId)
  ) {
    setView("store");
    openProductDialog(apiContext.productId);
  }
}

init();
