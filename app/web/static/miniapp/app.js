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
  renderTeaching();
  renderAttendanceJournal();
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
    showNotice("Выберите CRM-файл XLSX", "danger");
    return;
  }
  if (apiContext.demoMode || !apiContext.maxUserId) {
    showNotice("Импорт CRM доступен после входа администратора", "danger");
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
        `Файл проверен: ${result.parsed_rows} строк, ${result.distinct_groups} групп`,
      );
    } else {
      await loadSession();
      state.teachingLoaded = false;
      state.adminStudents = [];
      state.adminStudentsLoaded = false;
      state.adminStudentsError = "";
      state.adminHistoryLoaded = false;
      showNotice(
        `Импорт завершен: новых ${result.created_students}, обновлено ${result.updated_students}`,
      );
    }
  } catch (error) {
    showNotice(error.message || "Не удалось импортировать CRM", "danger");
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

async function saveProductFromForm() {
  const sku = qs("#productSku")?.value.trim().toUpperCase() || "";
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
  if (sku.length < 2 || name.length < 2) {
    showNotice("Укажите SKU и название товара", "danger");
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
  const payload = {
    sku,
    name,
    category_name: category,
    category_slug: slugify(category),
    price_astrocoins: price,
    status,
    fulfillment_type: fulfillmentType,
    new_codes: newCodes,
    description: description || undefined,
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
    const id = editing?.id || `demo-product-${slugify(sku)}`;
    const nextProduct = {
      ...(editing || {}),
      id,
      sku,
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
      stock: editing?.stock || 0,
      warehouse: editing?.warehouse || "Склад будет выбран",
      warehouses: editing?.warehouses || [],
      mark: name.trim().slice(0, 1).toUpperCase() || "A",
    };
    const existingIndex = products.findIndex((product) => product.id === id || product.sku === sku);
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
    formData.set("sku", payload.sku);
    formData.set("name", payload.name);
    formData.set("category_name", payload.category_name);
    formData.set("category_slug", payload.category_slug);
    formData.set("price_astrocoins", String(payload.price_astrocoins));
    formData.set("status", payload.status);
    formData.set("fulfillment_type", payload.fulfillment_type);
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
  const existingType = Array.from(state.cart.values())
    .map((item) => productById(item.productId)?.fulfillmentType || "warehouse")
    .find(Boolean);
  if (existingType && existingType !== (product.fulfillmentType || "warehouse")) {
    showNotice("Коды и товары со склада оформляются отдельными заказами", "danger");
    return false;
  }
  const current = cartQuantityFor(product.id);
  const availableLeft = Math.max(productAvailable(product) - current, 0);
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
    .map((item) => {
      const product = productById(item.productId);
      if (!product) return null;
      return {
        productId: product.id,
        productName: product.name,
        quantity: item.quantity,
        totalPrice: product.price * item.quantity,
        warehouseId: "",
        warehouseName: "",
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
    status: "Зарезервировано",
    tone: "ok",
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
  const items = Array.isArray(order.items) && order.items.length > 0
    ? order.items
        .map(
          (item) => {
            const product = productById(item.productId || "");
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
              ? `<div class="issued-code-list">${item.issuedCodes
                  .map(
                    (code) => `<div><span>Код</span><code>${escapeHtml(code)}</code><button class="icon-button" type="button" data-copy-code="${escapeHtml(code)}" title="Копировать код" aria-label="Копировать код"><i data-lucide="copy"></i></button></div>`,
                  )
                  .join("")}</div>`
              : "";
            return `
              <div class="order-detail-item ${needsWarehouseAssignment ? "needs-warehouse" : ""}">
                <span class="order-detail-thumb">
                  ${product?.photoUrl ? `<img src="${escapeHtml(product.photoUrl)}" alt="" />` : `<i data-lucide="${product ? productFallbackIcon(product) : "package"}"></i>`}
                </span>
                <div>
                  <strong>${escapeHtml(item.productName || "Товар")}</strong>
                  <div class="student-meta">${Number(item.quantity || 0)} шт.</div>
                  ${warehouseControl}
                  ${issuedCodes}
                </div>
                <strong>${Number(item.totalPrice || 0)} AC</strong>
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
        .map(
          (event, index) => `
            <div class="order-history-row ${index === 0 ? "is-current" : "is-complete"}">
              <span class="order-history-marker"><i data-lucide="${index === 0 ? "circle-dot" : "check"}"></i></span>
              <div>
                <strong>${escapeHtml(orderStatusLabel(event.toStatus))}</strong>
                <span>${escapeHtml(formatOrderDate(event.createdAt))}</span>
                ${event.comment ? `<div>${escapeHtml(event.comment)}</div>` : ""}
              </div>
            </div>
          `,
        )
        .join("")
    : `
        <div class="order-history-row">
          <span class="order-history-marker"><i data-lucide="circle-dot"></i></span>
          <div><strong>${escapeHtml(order.status)}</strong><span>Текущий статус</span></div>
        </div>
      `;

  qs("#orderDialogTitle").textContent = `Заказ №${order.id}`;
  qs("#orderDialogContent").innerHTML = `
    <div class="order-dialog-summary">
      <div>
        <span class="status-badge ${escapeHtml(order.tone)}">${escapeHtml(order.status)}</span>
        <h3>${escapeHtml(order.student)}</h3>
        <div class="student-meta">
          ${
            orderIsDigital(order)
              ? "Код выдан автоматически"
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
    if (previousStatus === "problem") {
      order.rawStatus = "reserved";
      order.status = orderStatusLabel(order.rawStatus);
      order.tone = orderStatusTone(order.rawStatus);
    }
    order.warehouse = orderWarehouseSummary(order.items, "Склад назначен");
    order.statusHistory = order.statusHistory || [];
    order.statusHistory.push({
      fromStatus: previousStatus,
      toStatus: order.rawStatus,
      comment: previousStatus === "problem"
        ? "Проблема устранена, склад назначен администратором"
        : "Склад назначен администратором",
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

async function updateOrderAction(orderId, action, cancelData = null) {
  const order = orders.find((item) => item.backendId === orderId || item.id === orderId);
  if (!order) return;

  if (orderId.startsWith("demo-") || apiContext.demoMode || !apiContext.maxUserId) {
    const previousStatus = order.rawStatus;
    if (action === "issue") order.rawStatus = "issued_to_student";
    else if (action === "transfer") order.rawStatus = "transferred_to_teacher";
    else if (action === "return") order.rawStatus = "returned";
    else order.rawStatus = "cancelled";
    order.status = orderStatusLabel(order.rawStatus);
    order.tone = orderStatusTone(order.rawStatus);
    order.statusHistory = order.statusHistory || [];
    order.statusHistory.push({
      fromStatus: previousStatus,
      toStatus: order.rawStatus,
      comment: {
        issue: "Заказ выдан ученику",
        transfer: "Заказ передан учителю",
        return: "Заказ возвращен",
        cancel: cancelData?.customReason || cancelData?.reason || "Заказ отменен",
      }[action],
      createdAt: new Date().toISOString(),
    });
    showNotice(
      {
        issue: `Заказ №${order.id} отмечен как выданный`,
        transfer: `Заказ №${order.id} передан учителю`,
        return: `Заказ №${order.id} возвращен`,
        cancel: `Заказ №${order.id} отменен`,
      }[action],
    );
    renderAll();
    if (!qs("#orderDialog").hidden) renderOrderDialog(order);
    return;
  }

  const endpoint =
    action === "issue"
      ? "issue"
      : action === "transfer"
        ? "transfer-to-teacher"
        : action === "return"
          ? "return"
          : "cancel";
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
                  transfer: "Передано учителю в приложении",
                  return: "Возврат оформлен в приложении",
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
        transfer: `Заказ №${result.order.order_number} передан учителю`,
        return: `Заказ №${result.order.order_number} возвращен, астрокоины зачислены`,
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

async function accrueSelectedStudents() {
  const reason = qs("#groupAccrualReason")?.value || "";
  const amount = Number.parseInt(qs("#groupAccrualAmount")?.value || "0", 10);
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
  await accrueStudents(targets, amount, reason);
}

function cycleProductWarehouse(productId) {
  const product = products.find((item) => item.id === productId);
  if (!product) return;
  const currentIndex = warehouses.findIndex(([name]) => name === product.warehouse);
  const nextWarehouse = warehouses[(currentIndex + 1 + warehouses.length) % warehouses.length][0];
  product.warehouse = nextWarehouse;
  showNotice(`${product.name}: выбран склад "${nextWarehouse}"`);
  renderProducts();
  renderAdminPanel();
}

function showWarehouseAction(warehouseName) {
  const warehouse = warehouses.find(([name]) => name === warehouseName);
  if (!warehouse) return;
  showNotice(`Склад "${warehouse[0]}": ${warehouse[3]}, статус "${warehouse[4]}"`);
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

async function adjustInventory(inventoryKey) {
  const [productId, warehouseId] = inventoryKey.split("::");
  const product = productById(productId);
  const warehouse = product ? warehouseById(product, warehouseId) : null;
  const input = qsa("[data-inventory-quantity]").find(
    (item) => item.dataset.inventoryQuantity === inventoryKey,
  );
  const nextQuantity = Number.parseInt(input?.value || "", 10);
  if (!product || !warehouse || Number.isNaN(nextQuantity)) return;
  if (nextQuantity < warehouse.reserved) {
    showNotice("Фактический остаток не может быть меньше резерва", "danger");
    return;
  }

  if (apiContext.demoMode || !apiContext.maxUserId || product.id.startsWith("demo-")) {
    const rawWarehouse = product.warehouses.find(
      (item) => String(item.warehouse_id || item.id || item.warehouse_name) === warehouse.id,
    );
    if (rawWarehouse) {
      rawWarehouse.stock_quantity = nextQuantity;
      rawWarehouse.available_quantity = Math.max(nextQuantity - warehouse.reserved, 0);
    }
    product.stock = productWarehouses(product).reduce((total, item) => total + item.available, 0);
    showNotice(`${product.name}: остаток на складе "${warehouse.name}" обновлен`);
    renderAll();
    return;
  }

  state.inventorySavingKey = inventoryKey;
  renderAdminPanel();
  try {
    const response = await apiFetch("/api/v1/miniapp/inventory/adjust", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        max_user_id: Number(apiContext.maxUserId),
        tenant_slug: apiContext.tenantSlug || undefined,
        product_id: product.id,
        warehouse_id: warehouse.id,
        available_quantity: nextQuantity,
        comment: "Корректировка в приложении",
      }),
    });
    if (!response.ok) throw new Error(await parseApiError(response));

    const result = await response.json();
    showNotice(
      `${product.name}: склад "${result.warehouse_name}", факт ${result.stock_quantity} шт.`,
    );
    await refreshCatalogAndOpsSummary();
    renderAll();
  } catch (error) {
    showNotice(error.message || "Не удалось обновить остаток", "danger");
  } finally {
    state.inventorySavingKey = "";
    renderAdminPanel();
  }
}

async function transferInventory(inventoryKey) {
  const [productId, warehouseId] = inventoryKey.split("::");
  const product = productById(productId);
  const source = product ? warehouseById(product, warehouseId) : null;
  const targetId =
    qsa("[data-transfer-target]").find((item) => item.dataset.transferTarget === inventoryKey)
      ?.value || "";
  const target = allCatalogWarehouses().find((warehouse) => warehouse.id === targetId);
  const quantityValue =
    qsa("[data-transfer-quantity]").find((item) => item.dataset.transferQuantity === inventoryKey)
      ?.value || "";
  const quantity = Number.parseInt(quantityValue, 10);
  if (!product || !source || !target || Number.isNaN(quantity)) return;
  if (quantity <= 0) {
    showNotice("Укажите количество для перемещения", "danger");
    return;
  }
  if (quantity > source.available) {
    showNotice("Нельзя переместить больше свободного остатка", "danger");
    return;
  }

  if (apiContext.demoMode || !apiContext.maxUserId || product.id.startsWith("demo-")) {
    const rawSource = ensureProductWarehouse(product, source);
    const rawTarget = ensureProductWarehouse(product, target);
    rawSource.stock_quantity = Math.max(Number(rawSource.stock_quantity || source.stock) - quantity, 0);
    rawSource.available_quantity = Math.max(
      Number(rawSource.available_quantity || source.available) - quantity,
      0,
    );
    rawTarget.stock_quantity = Number(rawTarget.stock_quantity || 0) + quantity;
    rawTarget.available_quantity = Number(rawTarget.available_quantity || 0) + quantity;
    product.stock = productWarehouses(product).reduce((total, item) => total + item.available, 0);
    showNotice(`${product.name}: ${quantity} шт. перемещено в "${target.name}"`);
    renderAll();
    return;
  }

  state.inventorySavingKey = inventoryKey;
  renderAdminPanel();
  try {
    const response = await apiFetch("/api/v1/miniapp/inventory/transfer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        max_user_id: Number(apiContext.maxUserId),
        tenant_slug: apiContext.tenantSlug || undefined,
        product_id: product.id,
        from_warehouse_id: source.id,
        to_warehouse_id: target.id,
        quantity,
        comment: "Перемещение в приложении",
      }),
    });
    if (!response.ok) throw new Error(await parseApiError(response));

    const result = await response.json();
    showNotice(
      `${product.name}: ${result.quantity} шт. перемещено в "${result.to_warehouse_name}"`,
    );
    await refreshCatalogAndOpsSummary();
    renderAll();
  } catch (error) {
    showNotice(error.message || "Не удалось переместить остаток", "danger");
  } finally {
    state.inventorySavingKey = "";
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
  const item = state.cart.get(key);
  if (!item) return;
  const product = productById(item.productId);
  if (!product) return;

  const maxQuantity = Math.max(productAvailable(product), item.quantity);
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

async function accrueStudents(targets, amount, reason, groupLabel = "") {
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
  if (state.cart.size === 0 || state.orderSaving) return;

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
    state.cart.clear();
    state.orderRequestKey = "";
    state.orderRequestSignature = "";
    await saveCart();
    closeCheckoutDialog();
    await refreshOrderAndInventoryState();
    setView("orders");
    showNotice(
      result.order.status === "issued_to_student"
        ? `Заказ №${result.order.order_number} оплачен, код уже доступен в заказе`
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

  const openedQrFileStudentId = target.dataset.openStudentQrFile;
  if (openedQrFileStudentId) {
    openStudentQrFile(openedQrFileStudentId);
    return;
  }

  const sharedStudentId = target.dataset.shareStudentInvite;
  if (sharedStudentId) shareStudentInvitation(sharedStudentId);

  const printedStudentId = target.dataset.printStudentInvite;
  if (printedStudentId) printStudentInvitation(printedStudentId);

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

  if (target.id === "scheduleCreateButton") openScheduleEditor();
  if ("closeSchedule" in target.dataset) closeScheduleEditor();
  if (target.id === "scheduleSaveButton") saveTeachingSchedule();

  const editScheduleId = target.dataset.editSchedule;
  if (editScheduleId) openScheduleEditor(editScheduleId);

  const configureScheduleGroup = target.dataset.configureSchedule;
  if (configureScheduleGroup) openScheduleEditor("", configureScheduleGroup);

  const attendanceScheduleId = target.dataset.openAttendance;
  if (attendanceScheduleId) loadAttendanceJournal(attendanceScheduleId);

  const attendanceLessonPosition = target.dataset.editAttendanceLesson;
  if (attendanceLessonPosition) openAttendanceLessonEditor(attendanceLessonPosition);

  if (target.dataset.attendanceCycle) {
    cycleAttendanceStatus(
      target.dataset.studentId || "",
      target.dataset.lessonDate || "",
    );
  }

  const journalScrollDirection = Number(target.dataset.journalScroll || 0);
  if (journalScrollDirection) scrollAttendanceJournal(journalScrollDirection);
  if ("journalCurrent" in target.dataset) scrollJournalToCurrent();
  const markAllPresentDate = target.dataset.markAllPresent;
  if (markAllPresentDate) markGroupPresent(markAllPresentDate);

  if (target.id === "closeAttendanceJournalButton") closeAttendanceJournal();
  if (
    target.id === "closeAttendanceLessonDialogButton"
    || target.id === "cancelAttendanceLessonButton"
  ) {
    closeAttendanceLessonEditor();
  }
  if (target.id === "applyAttendanceLessonButton") applyAttendanceLessonEditor();

  const feedbackOutputId = target.dataset.openFeedback;
  if (feedbackOutputId) openFeedbackDialog(feedbackOutputId);

  if (target.id === "closeFeedbackDialogButton") closeFeedbackDialog();
  if (target.id === "copyFeedbackButton") copyGeneratedFeedback();

  if (target.id === "previewBroadcastButton") {
    previewBroadcastAudience();
  }
  if (target.id === "saveBroadcastDraftButton") saveBroadcastDraft();
  const broadcastStep = target.dataset.broadcastStep;
  if (broadcastStep) setBroadcastStep(broadcastStep);
  const broadcastStepDirection = target.dataset.broadcastStepNav;
  if (broadcastStepDirection) moveBroadcastStep(broadcastStepDirection);
  const duplicateBroadcastId = target.dataset.duplicateBroadcast || target.dataset.retryBroadcast;
  if (duplicateBroadcastId) duplicateBroadcast(duplicateBroadcastId);

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
    if (adminTab === "students") void loadAdminStudents();
    if (adminTab === "history") void loadAdminHistory();
  }

  const adminHistoryKind = target.dataset.adminHistoryKind;
  if (["actions", "amocrm"].includes(adminHistoryKind)) {
    state.adminHistoryKind = adminHistoryKind;
    state.adminHistoryLoaded = false;
    state.adminEntitySearch = "";
    renderAdminPanel();
    void loadAdminHistory(true);
  }

  if ("retryAdminHistory" in target.dataset) {
    void loadAdminHistory(true);
  }

  const studentRegistryStatusFilter = target.dataset.studentRegistryStatus;
  if (["all", "active", "departed", "archived"].includes(studentRegistryStatusFilter)) {
    state.studentRegistryStatusFilter = studentRegistryStatusFilter;
    renderAdminPanel();
  }

  if ("retryStudentRegistry" in target.dataset) {
    void loadAdminStudents(true);
  }

  if ("resetStudentRegistry" in target.dataset) {
    state.adminEntitySearch = "";
    state.studentRegistryStatusFilter = "all";
    state.studentRegistryGroupFilter = "all";
    renderAdminPanel();
  }

  const orderStatus = target.dataset.orderStatus;
  if (orderStatus) {
    state.orderStatusFilter = orderStatus;
    const select = qs("#orderStatusFilter");
    if (select && [...select.options].some((option) => option.value === orderStatus)) select.value = orderStatus;
    if (state.view !== "orders") setView("orders");
    renderOrders();
    savePreferences();
  }

  const staffStatusFilter = target.dataset.staffStatusFilter;
  if (["active", "revoked", "all"].includes(staffStatusFilter)) {
    state.staffStatusFilter = staffStatusFilter;
    renderAdminPanel();
  }

  const opsJump = target.dataset.opsJump;
  if (opsJump === "orders") {
    state.orderStatusFilter = "action";
    setView("orders");
    renderOrders();
  } else if (["inventory", "products", "warehouses"].includes(opsJump)) {
    state.adminTab = opsJump;
    if ("inventoryLowStock" in target.dataset) state.inventoryStockFilter = "low";
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

  if (target.id === "saveAttendanceButton") {
    saveAttendanceJournal();
  }

  if ("selectedAccrual" in target.dataset) {
    accrueSelectedStudents();
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
  const warehouseName = target.dataset.warehouseAction;
  if (warehouseName) showWarehouseAction(warehouseName);

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

  const transferProductId = target.dataset.transferProduct;
  if (transferProductId) cycleProductWarehouse(transferProductId);

  const inventoryKey = target.dataset.adjustInventory;
  if (inventoryKey) adjustInventory(inventoryKey);

  const transferInventoryKey = target.dataset.transferInventory;
  if (transferInventoryKey) transferInventory(transferInventoryKey);

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
    state.editingProductId = editProductId;
    state.productEditorOpen = true;
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
    state.studentRegistryStatusFilter = "all";
    state.studentRegistryGroupFilter = "all";
    state.productStatusFilter = "all";
    state.productCategoryFilter = "all";
    state.accessStatusFilter = "all";
    state.accessRoleFilter = "all";
    state.staffRoleFilter = "all";
    renderAdminPanel();
  }
  if ("clearInventoryFilters" in target.dataset) {
    state.adminEntitySearch = "";
    state.inventoryWarehouseFilter = "all";
    state.inventoryStockFilter = "all";
    renderAdminPanel();
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
    state.staffEditorOpen = true;
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

qs("#feedbackDialog").addEventListener("click", (event) => {
  if (event.target === event.currentTarget) closeFeedbackDialog();
});

qs("#attendanceLessonDialog").addEventListener("click", (event) => {
  if (event.target === event.currentTarget) closeAttendanceLessonEditor();
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
  if (!qs("#attendanceLessonDialog").hidden) {
    closeAttendanceLessonEditor();
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
  if (!qs("#feedbackDialog").hidden) {
    closeFeedbackDialog();
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
    if (codeEditor) codeEditor.hidden = target.value !== "digital_code";
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

  if (target.id === "groupAccrualReason" || target.id === "groupAccrualAmount") {
    renderAccrual();
  }

  const accrualStudentId = target.dataset.accrualStudentCheck;
  if (accrualStudentId) {
    if (target.checked) state.selectedAccrualStudents.add(accrualStudentId);
    else state.selectedAccrualStudents.delete(accrualStudentId);
    renderAccrual();
  }

  if (target.id === "orderStatusFilter") {
    state.orderStatusFilter = target.value;
    renderOrders();
    savePreferences();
  }

  if (target.id === "productStatusFilter") {
    state.productStatusFilter = target.value;
    renderAdminPanel();
  }
  if (target.id === "studentRegistryGroupFilter") {
    state.studentRegistryGroupFilter = target.value;
    renderAdminPanel();
  }
  if (target.id === "productCategoryFilter") {
    state.productCategoryFilter = target.value;
    renderAdminPanel();
  }
  if (target.id === "inventoryWarehouseFilter") {
    state.inventoryWarehouseFilter = target.value;
    renderAdminPanel();
  }
  if (target.id === "inventoryStockFilter") {
    state.inventoryStockFilter = target.value;
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
  if (target.id === "adminHistoryPeriod") {
    state.adminHistoryPeriod = Number(target.value) || 30;
    state.adminHistoryLoaded = false;
    renderAdminPanel();
    void loadAdminHistory(true);
  }

  if (
    target.id === "broadcastRecipientCategory" ||
    target.id === "broadcastAudienceFilter" ||
    target.id === "broadcastVenueFilter" ||
    target.id === "broadcastLessonModeFilter"
  ) {
    invalidateBroadcastPreview();
    scheduleBroadcastDraftSave();
    renderBroadcasts();
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
    scheduleBroadcastDraftSave();
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
  if (!(target instanceof HTMLInputElement) || !target.dataset.journalScrollRange) return;
  const scroll = qs("#attendanceJournalList .school-journal-scroll");
  if (!scroll) return;
  const maximum = Math.max(scroll.scrollWidth - scroll.clientWidth, 0);
  scroll.scrollLeft = maximum * (Number(target.value) / 1000);
});

document.addEventListener("input", (event) => {
  const target = event.target;
  if (target instanceof HTMLTextAreaElement && target.id === "broadcastMessage") {
    const count = qs("#broadcastMessageCount");
    if (count) count.textContent = String(target.value.length);
    scheduleBroadcastDraftSave();
    renderBroadcastLivePreview();
    return;
  }
  if (!(target instanceof HTMLInputElement)) return;

  if (target.id === "broadcastTitle") {
    scheduleBroadcastDraftSave();
    renderBroadcastLivePreview();
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

  if (target.id === "accrualNameFilter") {
    state.accrualNameFilter = target.value;
    window.clearTimeout(accrualSearchTimer);
    accrualSearchTimer = window.setTimeout(renderAccrual, 140);
  }

  if (target.id === "broadcastBalanceThreshold") {
    invalidateBroadcastPreview();
    scheduleBroadcastDraftSave();
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
qs("#closeTenantDialogButton")?.addEventListener("click", closeTenantDialog);
qs("#showTenantCreateButton")?.addEventListener("click", () => setTenantCreateMode(true));
qs("#cancelTenantCreateButton")?.addEventListener("click", () => setTenantCreateMode(false));
qs("#tenantCreateForm")?.addEventListener("submit", createTenantFromForm);
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
window.addEventListener("beforeunload", (event) => {
  if (!hasAttendanceChanges()) return;
  event.preventDefault();
  event.returnValue = "";
});

async function init() {
  qs("#tenantTitle").textContent = tenantTitle();
  restorePreferences();
  applyDemoRole();
  if (
    apiContext.demoMode &&
    !apiContext.demoRole &&
    state.view === "teaching"
  ) {
    state.role = "teacher";
    state.staffRoles = ["teacher"];
    state.availableRoles = ["teacher"];
  }
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
        : "",
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
