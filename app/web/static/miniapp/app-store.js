function renderStudents() {
  const list = qs("#studentList");
  const roleStudents = studentsForCurrentRole();
  if (roleStudents.length === 0) {
    list.innerHTML = '<div class="empty-state">Пока нет связанных учеников</div>';
    return;
  }

  const visibleStudents = studentsForGroup();
  if (visibleStudents.length === 0) {
    list.innerHTML = '<div class="empty-state">В этой группе пока нет учеников</div>';
    return;
  }

  const grouped = studentGroups()
    .filter((group) => state.studentGroupFilter === "all" || group === state.studentGroupFilter)
    .map((group) => {
      const rows = visibleStudents.filter((student) => studentGroupName(student) === group);
      if (rows.length === 0) return "";
      return `
        <div class="student-group">
          <div class="student-group-title">${escapeHtml(group)}</div>
          ${rows
            .map((student) => {
              return `
                <div class="student-row">
                  <div>
                    <strong>${escapeHtml(student.name)}</strong>
                    ${
                      state.role === "teacher"
                        ? ""
                        : `<div class="student-meta">${escapeHtml(student.teacher)}</div>`
                    }
                  </div>
                  <span class="student-balance-badge">
                    <small>Остаток на счете</small>
                    <strong>${student.balance} AC</strong>
                  </span>
                </div>
              `;
            })
            .join("")}
        </div>
      `;
    })
    .join("");

  list.innerHTML = grouped;
}

function renderParentInvitations() {
  const panel = qs("#parentInvitesPanel");
  const list = qs("#parentInviteList");
  const description = qs("#parentInvitesDescription");
  if (!panel || !list) return;

  const visible = state.role === "parent" && state.hasAccess;
  panel.hidden = !visible;
  if (!visible) return;
  if (description) {
    description.textContent =
      "Покажите ребенку его QR-код. Он привяжет только выбранный профиль.";
  }

  const linkedStudents = parentStudents();
  if (state.studentInvitationsLoading) {
    list.innerHTML = '<div class="empty-state">Создаем персональные QR-коды...</div>';
    return;
  }
  if (linkedStudents.length === 0) {
    list.innerHTML = '<div class="empty-state">Связанные дети не найдены</div>';
    return;
  }

  list.innerHTML = linkedStudents
    .map((student) => {
      const invitation = state.studentInvitations.get(student.id);
      if (!invitation) {
        return `
          <article class="parent-invite-card">
            <div class="empty-state">QR-код загружается</div>
          </article>
        `;
      }
      if (invitation.error || !invitation.data) {
        return `
          <article class="parent-invite-card">
            <div class="parent-invite-copy">
              <strong>${escapeHtml(student.name)}</strong>
              <span>${escapeHtml(invitation.error || "QR-код недоступен")}</span>
            </div>
          </article>
        `;
      }
      return `
        <details class="parent-invite-card" ${student.id === state.activeStudentId ? "open" : ""}>
          <summary>
            <span class="parent-invite-initial">${escapeHtml(student.name.slice(0, 1))}</span>
            <span class="parent-invite-copy">
              <strong>${escapeHtml(student.name)}</strong>
              <span>${escapeHtml(student.group)}</span>
            </span>
            <span class="link-status is-active"><i data-lucide="link"></i> Доступ активен</span>
            <i class="parent-invite-chevron" data-lucide="chevron-down"></i>
          </summary>
          <div class="parent-invite-details">
            <button
              class="parent-invite-qr-button"
              type="button"
              data-open-student-qr="${escapeHtml(student.id)}"
              aria-label="Увеличить QR-код для ${escapeHtml(student.name)}"
            >
              <img
                src="${escapeHtml(invitation.data.qr_data_url)}"
                alt="QR-код для входа: ${escapeHtml(student.name)}"
              />
              <span><i data-lucide="maximize-2"></i> Увеличить</span>
            </button>
            <div class="parent-invite-help">
              <strong>Вход ребенка</strong>
              <span>Покажите QR-код ребенку или сохраните его как изображение.</span>
              <div class="parent-invite-actions">
                <button class="secondary-action parent-invite-save" type="button" data-save-student-qr="${escapeHtml(student.id)}"><i data-lucide="download"></i> Сохранить картинку</button>
              </div>
            </div>
          </div>
        </details>
      `;
    })
    .join("");
  refreshIcons();
}
function studentInvitationData(studentId) {
  return state.teacherInvitations.get(studentId)?.data || state.studentInvitations.get(studentId)?.data;
}

function openStudentQrPreview(studentId) {
  const student = students.find((item) => item.id === studentId);
  const invitation = studentInvitationData(studentId);
  const dialog = qs("#studentQrDialog");
  if (!student || !invitation || !dialog) return;
  state.qrPreviewStudentId = studentId;
  qs("#studentQrDialogTitle").textContent = student.name;
  qs("#studentQrDialogGroup").textContent = student.group || "";
  const image = qs("#studentQrPreviewImage");
  image.src = invitation.qr_data_url;
  image.alt = `QR-код для входа: ${student.name}`;
  qs("#saveStudentQrPreviewButton").dataset.saveStudentQr = studentId;
  qs("#openStudentQrFileButton").dataset.openStudentQrFile = studentId;
  dialog.hidden = false;
  document.body.classList.add("dialog-open");
  if (window.WebApp?.requestScreenMaxBrightness) {
    state.qrBrightnessRequested = true;
    Promise.resolve(window.WebApp.requestScreenMaxBrightness()).catch((error) => {
      console.warn("MAX brightness request failed", error);
    });
  }
  qs("#closeStudentQrDialogButton")?.focus();
}

function closeStudentQrPreview() {
  const dialog = qs("#studentQrDialog");
  if (!dialog || dialog.hidden) return;
  dialog.hidden = true;
  state.qrPreviewStudentId = "";
  qs("#saveStudentQrPreviewButton").dataset.saveStudentQr = "";
  qs("#openStudentQrFileButton").dataset.openStudentQrFile = "";
  if (state.qrBrightnessRequested && window.WebApp?.restoreScreenBrightness) {
    Promise.resolve(window.WebApp.restoreScreenBrightness()).catch((error) => {
      console.warn("MAX brightness restore failed", error);
    });
  }
  state.qrBrightnessRequested = false;
  syncDialogBodyClass();
}

function studentQrDownload(studentId) {
  const student = students.find((item) => item.id === studentId);
  const invitation = studentInvitationData(studentId);
  if (!student || !invitation) return null;
  const safeId = String(student.id || "student").replace(/[^a-z0-9_-]/gi, "").slice(0, 24);
  const filename = `algo-max-qr-${safeId || "student"}.png`;
  const source = invitation.qr_download_url || invitation.qr_data_url;
  const downloadUrl = new URL(source, window.location.origin).href;
  return { downloadUrl, filename };
}

function openStudentQrFile(studentId) {
  const download = studentQrDownload(studentId);
  if (!download) return;
  if (window.WebApp?.openLink && download.downloadUrl.startsWith("https://")) {
    window.WebApp.openLink(download.downloadUrl);
    return;
  }
  window.open(download.downloadUrl, "_blank", "noopener");
}

async function saveStudentQrImage(studentId, button = null) {
  const download = studentQrDownload(studentId);
  if (!download) return;
  const originalHtml = button?.innerHTML || "";
  if (button) {
    button.disabled = true;
    button.innerHTML = '<span class="button-spinner" aria-hidden="true"></span> Сохраняем...';
  }

  if (window.WebApp?.downloadFile && download.downloadUrl.startsWith("https://")) {
    try {
      const result = await window.WebApp.downloadFile(download.downloadUrl, download.filename);
      if (result?.error) {
        throw result.error;
      }
      showNotice("QR-код сохранен в загрузки");
      return;
    } catch (error) {
      console.warn("MAX download failed", error);
      if (qs("#studentQrDialog")?.hidden) openStudentQrPreview(studentId);
      showNotice("MAX не смог сохранить файл. Нажмите «Открыть файл»", "danger");
      qs("#openStudentQrFileButton")?.focus();
      return;
    } finally {
      if (button) {
        button.disabled = false;
        button.innerHTML = originalHtml;
        refreshIcons();
      }
    }
  }

  try {
    const link = document.createElement("a");
    link.href = download.downloadUrl;
    link.download = download.filename;
    link.rel = "noopener";
    document.body.append(link);
    link.click();
    link.remove();
    showNotice("QR-код сохранен");
  } catch (error) {
    console.warn(error);
    showNotice("Не удалось сохранить QR-код", "danger");
  } finally {
    if (button) {
      button.disabled = false;
      button.innerHTML = originalHtml;
      refreshIcons();
    }
  }
}

function renderDashboardOrders() {
  const list = qs("#dashboardOrders");
  if (!list) return;

  const teacherView = primaryStaffRole() === "teacher";
  const roleOrders = ordersForCurrentRole();
  const visible = (teacherView
    ? roleOrders.filter((order) => order.rawStatus === "transferred_to_teacher")
    : roleOrders
  ).slice(0, 4);
  if (visible.length === 0) {
    list.innerHTML = '<div class="empty-state compact-empty">Заказов пока нет</div>';
    return;
  }

  list.innerHTML = visible
    .map(
      (order) => `
        <button
          class="compact-order"
          type="button"
          data-open-order="${escapeHtml(order.backendId || order.id)}"
          aria-label="Открыть заказ №${escapeHtml(order.id)}"
        >
          <div>
            <strong>${escapeHtml(order.student)}</strong>
            <div class="student-meta">${escapeHtml(order.item)}</div>
            ${teacherView && order.warehouse ? `<div class="compact-order-warehouse"><i data-lucide="warehouse"></i> Забрать: ${escapeHtml(order.warehouse)}</div>` : ""}
          </div>
          <span class="status-badge ${order.tone}">${escapeHtml(order.status)}</span>
        </button>
      `,
    )
    .join("");
}

function renderCategories() {
  const filter = qs("#categoryFilter");
  const selected = state.productCategory || filter.value || "all";
  const categories = [...new Set(activeProducts().map((product) => product.category))]
    .filter(Boolean)
    .sort((left, right) => left.localeCompare(right, "ru"));
  filter.innerHTML = [
    '<option value="all">Все категории</option>',
    ...categories.map(
      (category) => `<option value="${escapeHtml(category)}">${escapeHtml(category)}</option>`,
    ),
  ].join("");
  state.productCategory = categories.includes(selected) ? selected : "all";
  filter.value = state.productCategory;
  const chips = qs("#categoryChips");
  if (chips) {
    chips.innerHTML = [
      ["all", "Все"],
      ...categories.map((category) => [category, category]),
    ]
      .map(
        ([value, label]) => `
          <button
            class="category-chip ${state.productCategory === value ? "is-active" : ""}"
            type="button"
            data-product-category="${escapeHtml(value)}"
            aria-pressed="${state.productCategory === value}"
            title="${escapeHtml(label)}"
          ><span>${escapeHtml(label)}</span></button>
        `,
      )
      .join("");
  }
}

function renderProducts() {
  const search = qs("#productSearch").value.trim().toLowerCase();
  const category = qs("#categoryFilter").value;
  const sort = qs("#productSort").value;
  const grid = qs("#productGrid");
  state.productSort = sort;
  state.productCategory = category;
  const stockCheckbox = qs("#inStockOnly");
  state.inStockOnly = stockCheckbox.checked;
  stockCheckbox.closest(".stock-filter")?.classList.toggle("is-active", state.inStockOnly);
  const visible = activeProducts()
    .filter((product) => {
      const matchesSearch = productMatchesSearch(product, search);
      const matchesCategory = category === "all" || product.category === category;
      const matchesFavorite = !state.favoritesOnly || state.favorites.has(product.id);
      const matchesStock = !state.inStockOnly || productAvailable(product) > 0;
      return matchesSearch && matchesCategory && matchesFavorite && matchesStock;
    })
    .sort((left, right) => {
      const stockDifference = Number(productAvailable(right) > 0) - Number(productAvailable(left) > 0);
      if (stockDifference) return stockDifference;
      if (sort === "price-asc") return left.price - right.price;
      if (sort === "price-desc") return right.price - left.price;
      if (sort === "newest") return Number(left.catalogIndex || 0) - Number(right.catalogIndex || 0);
      return 0;
    });

  const favoritesCount = activeProducts().filter((product) =>
    state.favorites.has(product.id),
  ).length;
  const favoritesFilter = qs("#favoritesFilter");
  favoritesFilter.setAttribute("aria-pressed", String(state.favoritesOnly));
  qs(".store-sort-filter")?.classList.toggle("is-active", sort !== "recommended");
  const clearSearchButton = qs("#clearProductSearch");
  if (clearSearchButton) clearSearchButton.hidden = !search;
  const filterButton = qs("#mobileStoreFiltersButton");
  const activeFilterCount = Number(state.inStockOnly) + Number(state.favoritesOnly) + Number(category !== "all") + Number(sort !== "recommended");
  if (filterButton) {
    filterButton.setAttribute("aria-expanded", String(state.storeFiltersOpen));
    filterButton.classList.toggle("is-active", state.storeFiltersOpen);
  }
  const filterCount = qs("#storeFilterCount");
  if (filterCount) {
    filterCount.textContent = String(activeFilterCount);
    filterCount.hidden = activeFilterCount === 0;
  }
  qs(".store-filter-actions")?.classList.toggle("is-open", state.storeFiltersOpen);
  const filterBackdrop = qs("#storeFilterBackdrop");
  if (filterBackdrop) filterBackdrop.hidden = !state.storeFiltersOpen;
  document.body.classList.toggle("store-filters-open", state.storeFiltersOpen);
  qs("#favoritesCount").textContent = favoritesCount;
  qs("#catalogResultCount").textContent = productCountLabel(visible.length);
  renderRecentProductSearches();

  grid.classList.toggle("is-empty", visible.length === 0);
  if (visible.length === 0) {
    grid.innerHTML = state.favoritesOnly
      ? '<div class="empty-state"><div>В избранном пока ничего нет</div><button class="secondary-action" type="button" data-show-all-products>Показать все товары</button></div>'
      : '<div class="empty-state">Товары не найдены</div>';
    return;
  }

  grid.innerHTML = visible
    .map((product) => {
      const available = productAvailable(product);
      const availableLeft = canUseStoreCart()
        ? Math.max(available - cartQuantityFor(product.id), 0)
        : available;
      const disabled = availableLeft <= 0;
      const favorite = state.favorites.has(product.id);
      const stockText =
        availableLeft <= 0
          ? "Нет в наличии"
          : availableLeft <= 5
            ? `Осталось ${availableLeft}`
            : "В наличии";
      const fulfillmentLabel =
        product.fulfillmentType === "digital_code"
          ? '<span class="product-auto-issue"><i data-lucide="zap"></i> Цифровой товар</span>'
          : "";
      return `
        <article class="product-card" data-product-card="${escapeHtml(product.id)}" tabindex="0" role="button" aria-label="Открыть ${escapeHtml(product.name)}">
          <div class="product-visual ${product.photoUrl ? "has-photo" : ""}">
            ${
              product.photoUrl
                ? `<img src="${escapeHtml(product.photoUrl)}" alt="${escapeHtml(product.name)}" loading="lazy" />`
                : `<div class="product-visual-fallback" aria-hidden="true">
                    <i data-lucide="${productFallbackIcon(product)}"></i>
                  </div>`
            }
            <button
              class="product-visual-open"
              type="button"
              data-product-details="${escapeHtml(product.id)}"
              aria-label="Открыть ${escapeHtml(product.name)}"
            ></button>
            <button
              class="product-favorite ${favorite ? "is-active" : ""}"
              type="button"
              title="${favorite ? "Убрать из избранного" : "Добавить в избранное"}"
              aria-label="${favorite ? "Убрать из избранного" : "Добавить в избранное"}"
              data-favorite="${escapeHtml(product.id)}"
            ><i data-lucide="heart"></i></button>
          </div>
          <div class="product-body">
            <span class="product-category">${escapeHtml(product.category)}</span>
            <button
              class="product-title-button"
              type="button"
              data-product-details="${escapeHtml(product.id)}"
            >${escapeHtml(product.name)}</button>
            <div class="product-availability ${disabled ? "is-empty" : ""}">
              <span aria-hidden="true"></span>
              ${stockText}
            </div>
            ${fulfillmentLabel}
          </div>
          <div class="product-card-footer">
            <strong>${product.price} <span>AC</span></strong>
            ${
              canUseStoreCart()
                ? `<button
                    class="primary-action"
                    type="button"
                    data-add="${escapeHtml(product.id)}"
                    ${disabled ? "disabled" : ""}
                  >
                    <i data-lucide="shopping-bag"></i>
                    <span>${disabled ? "Недоступно" : "В корзину"}</span>
                  </button>`
                : `<button
                    class="secondary-action"
                    type="button"
                    data-product-details="${escapeHtml(product.id)}"
                  >
                    <i data-lucide="eye"></i>
                    <span>Подробнее</span>
                  </button>`
            }
          </div>
        </article>
      `;
    })
    .join("");
  refreshIcons();
}

function renderRecentProductSearches() {
  const container = qs("#recentProductSearches");
  const searchInput = qs("#productSearch");
  if (!container || !searchInput) return;
  const query = searchInput.value.trim().toLowerCase();
  const values = query
    ? Array.from(new Set(activeProducts().flatMap((product) => [product.name, product.category])))
        .filter((value) => value.toLowerCase().includes(query) && value.toLowerCase() !== query)
        .slice(0, 5)
    : state.recentProductSearches;
  const visible = document.activeElement === searchInput && values.length > 0;
  container.hidden = !visible;
  container.innerHTML = visible
    ? `<span>${query ? "Подсказки:" : "Недавние:"}</span>${values
        .map(
          (value) => `<button type="button" data-recent-product-search="${escapeHtml(value)}">${escapeHtml(value)}</button>`,
        )
        .join("")}`
    : "";
}

function rememberProductSearch() {
  const query = qs("#productSearch")?.value.trim() || "";
  if (query.length < 2) return;
  state.recentProductSearches = [
    query,
    ...state.recentProductSearches.filter((item) => item.toLowerCase() !== query.toLowerCase()),
  ].slice(0, 5);
  savePreferences();
}

function productCountLabel(count) {
  const lastTwo = count % 100;
  const last = count % 10;
  if (lastTwo >= 11 && lastTwo <= 14) return `${count} товаров`;
  if (last === 1) return `${count} товар`;
  if (last >= 2 && last <= 4) return `${count} товара`;
  return `${count} товаров`;
}

function cartCount() {
  return Array.from(state.cart.values()).reduce((sum, item) => sum + item.quantity, 0);
}

function cartTotal() {
  return Array.from(state.cart.values()).reduce((sum, item) => {
    const product = productById(item.productId);
    return sum + (product ? product.price * item.quantity : 0);
  }, 0);
}

function renderCart() {
  const list = qs("#cartList");
  if (state.cart.size === 0) {
    const budget = Number(selectedStudent()?.balance || 0);
    const suggestions = activeProducts()
      .filter((product) => productAvailable(product) > 0 && product.price <= budget)
      .sort((left, right) => left.price - right.price)
      .slice(0, 3);
    list.innerHTML = `
      <div class="empty-state cart-empty-state">
        <i data-lucide="shopping-bag"></i>
        <strong>Корзина пока пустая</strong>
        <span>Добавьте награду из магазина.</span>
        <button class="primary-action" type="button" data-view-jump="store">Перейти в магазин</button>
      </div>
      ${
        suggestions.length
          ? `<section class="cart-suggestions"><h3>Хватит баланса</h3><div>${suggestions
              .map(
                (product) => `<button type="button" data-product-details="${escapeHtml(product.id)}">
                    <span>${escapeHtml(product.name)}</span><strong>${product.price} AC</strong>
                  </button>`,
              )
              .join("")}</div></section>`
          : ""
      }
    `;
  } else {
    list.innerHTML = Array.from(state.cart.entries())
      .map(([key, item]) => {
        const product = productById(item.productId);
        if (!product) return "";
        const maxQuantity = Math.max(productAvailable(product), item.quantity);
        return `
          <div class="cart-row ${product.fulfillmentType === "digital_code" ? "is-digital" : ""}">
            <div class="cart-product">
              <div class="cart-product-visual">
                ${
                  product.photoUrl
                    ? `<img src="${escapeHtml(product.photoUrl)}" alt="" />`
                    : `<i data-lucide="${productFallbackIcon(product)}"></i>`
                }
              </div>
              <div>
                <span>${escapeHtml(product.category)}</span>
                <strong>${escapeHtml(product.name)}</strong>
                <small class="cart-mobile-price">${product.price} AC за шт.</small>
              </div>
            </div>
            <div class="cart-unit-price">
              <span>Цена</span>
              <strong>${product.price} AC</strong>
            </div>
            <div class="quantity-control">
              <span>Количество</span>
              <div class="quantity-stepper">
                <button type="button" data-cart-step="-1" data-cart-key="${escapeHtml(key)}" aria-label="Уменьшить количество"><i data-lucide="minus"></i></button>
                <input type="number" min="1" max="${maxQuantity}" value="${item.quantity}" data-cart-quantity="${escapeHtml(key)}" aria-label="Количество ${escapeHtml(product.name)}" />
                <button type="button" data-cart-step="1" data-cart-key="${escapeHtml(key)}" aria-label="Увеличить количество" ${item.quantity >= maxQuantity ? "disabled" : ""}><i data-lucide="plus"></i></button>
              </div>
            </div>
            <div class="cart-line-total">
              <span>Сумма</span>
              <strong>${product.price * item.quantity} AC</strong>
            </div>
            <button class="icon-button cart-remove" type="button" title="Удалить" aria-label="Удалить ${escapeHtml(
              product.name,
            )}" data-remove="${escapeHtml(key)}">
              <i data-lucide="trash-2"></i>
            </button>
          </div>
        `;
      })
      .join("");
  }

  const total = cartTotal();
  const count = cartCount();
  const student = selectedStudent();
  const studentFirstName = student?.name?.trim().split(/\s+/).at(-1) || "";
  qs("#cartTitle").textContent =
    state.role === "parent" && studentFirstName
      ? `Корзина: ${studentFirstName}`
      : "Корзина";
  qs("#storeCartAction").textContent =
    state.role === "parent" && studentFirstName
      ? `Корзина ${studentFirstName}`
      : "Открыть корзину";
  const balance = Number(student?.balance || 0);
  const remaining = balance - total;
  const canCheckout = state.cart.size > 0 && Boolean(student) && remaining >= 0;
  qs("#cartCounter").textContent = count;
  qsa("[data-cart-count]").forEach((counter) => {
    counter.textContent = count;
    counter.hidden = count === 0;
  });
  qs("#cartTotal").textContent = total;
  qs("#cartSummary").hidden = state.cart.size === 0;
  qs("#cartStudentName").textContent = student?.name || "Ученик не выбран";
  qs("#cartBalance").textContent = balance;
  qs("#cartAffordabilityLabel").textContent = remaining >= 0 ? "После покупки" : "Не хватает";
  qs("#cartAffordabilityValue").textContent = Math.abs(remaining);
  qs("#cartAffordability").classList.toggle("is-danger", remaining < 0);
  qs("#placeOrderButton").disabled = !canCheckout;
  qs("#placeOrderButton").textContent = canCheckout
    ? `Оформить за ${total} AC`
    : remaining < 0
    ? `Не хватает ${Math.abs(remaining)} AC`
    : "Оформить заказ";
  qs("#storeCartBar").hidden = count === 0;
  qs("#storeCartCount").textContent = productCountLabel(count);
  qs("#storeCartTotal").textContent = total;
  qs("#storeView").classList.toggle("has-cart-dock", count > 0);
  renderChildSwitcher();
  renderMobileNavigation();
  refreshIcons();
}

function renderCheckoutSummary() {
  const student = selectedStudent();
  const total = cartTotal();
  const summary = qs("#checkoutSummary");
  if (!student || state.cart.size === 0) {
    summary.innerHTML = '<div class="empty-state">Корзина пока пустая</div>';
    return;
  }

  const cartProducts = Array.from(state.cart.values())
    .map((item) => productById(item.productId))
    .filter(Boolean);
  const isDigitalCheckout =
    cartProducts.length > 0 &&
    cartProducts.every((product) => product.fulfillmentType === "digital_code");
  const items = Array.from(state.cart.values())
    .map((item) => {
      const product = productById(item.productId);
      if (!product) return "";
      return `
        <div class="checkout-item">
          <div>
            <strong>${escapeHtml(product.name)}</strong>
            <div class="student-meta">${item.quantity} шт.</div>
          </div>
          <span class="checkout-item-total">${product.price * item.quantity} AC</span>
        </div>
      `;
    })
    .filter(Boolean)
    .join("");

  summary.innerHTML = `
    <div class="checkout-student">
      <div>
        <span class="label">Получатель</span>
        <strong>${escapeHtml(student.name)}</strong>
        <div class="student-meta">${escapeHtml(student.group)}</div>
      </div>
      <div class="checkout-balance">
        Баланс ${student.balance} AC<br />
        После заказа ${student.balance - total} AC
      </div>
    </div>
    <div class="checkout-items">${items}</div>
    <div class="checkout-guidance ${isDigitalCheckout ? "is-digital" : ""}">
      <i data-lucide="${isDigitalCheckout ? "key-round" : "package-check"}"></i>
      <div>
        <strong>${isDigitalCheckout ? "Где найти код после покупки" : "Что будет после оформления"}</strong>
        <span>${
          isDigitalCheckout
            ? "Откройте «Заказы» → «Выполненные» и нажмите на заказ. Код и кнопка копирования будут внутри."
            : "Заказ появится в разделе «В работе». Администратор выберет склад и подтвердит дальнейшую выдачу."
        }</span>
      </div>
    </div>
    <div class="checkout-total">
      <span>К списанию</span>
      <strong>${total} AC</strong>
    </div>
  `;
  qs("#checkoutDialogTitle").textContent = isDigitalCheckout
    ? "Получить цифровой товар?"
    : "Все верно?";
  qs("#confirmOrderButton").textContent = isDigitalCheckout
    ? `Оплатить ${total} AC`
    : "Подтвердить заказ";
  refreshIcons();
}

function openCheckoutDialog() {
  const student = selectedStudent();
  const total = cartTotal();
  if (!student || state.cart.size === 0) return;
  if (total > student.balance) {
    showNotice("Недостаточно астрокоинов для заказа", "danger");
    return;
  }

  renderCheckoutSummary();
  const dialog = qs("#checkoutDialog");
  dialog.hidden = false;
  document.body.classList.add("dialog-open");
  qs("#confirmOrderButton").focus();
}

function closeCheckoutDialog() {
  const dialog = qs("#checkoutDialog");
  if (dialog.hidden) return;
  dialog.hidden = true;
  syncDialogBodyClass();
  qs("#placeOrderButton").focus();
}

function syncDialogBodyClass() {
  const hasOpenDialog = qsa(".dialog-backdrop").some((dialog) => !dialog.hidden);
  document.body.classList.toggle("dialog-open", hasOpenDialog);
}

function settleConfirmation(result) {
  const dialog = qs("#confirmationDialog");
  if (!dialog || dialog.hidden) return;
  dialog.hidden = true;
  syncDialogBodyClass();
  const resolve = confirmationResolver;
  const returnFocus = confirmationReturnFocus;
  confirmationResolver = null;
  confirmationReturnFocus = null;
  resolve?.(result);
  if (!result && returnFocus instanceof HTMLElement) returnFocus.focus();
}

function requestConfirmation({
  eyebrow = "Подтверждение",
  title,
  message,
  confirmLabel = "Продолжить",
  cancelLabel = "Вернуться",
  destructive = false,
}) {
  if (confirmationResolver) settleConfirmation(false);
  const dialog = qs("#confirmationDialog");
  const confirmButton = qs("#confirmConfirmationButton");
  if (!dialog || !confirmButton) return Promise.resolve(false);
  qs("#confirmationDialogEyebrow").textContent = eyebrow;
  qs("#confirmationDialogTitle").textContent = title;
  qs("#confirmationDialogMessage").textContent = message;
  qs("#cancelConfirmationButton").textContent = cancelLabel;
  confirmButton.textContent = confirmLabel;
  confirmButton.classList.toggle("is-danger", destructive);
  dialog.querySelector(".confirmation-dialog")?.classList.toggle("is-danger", destructive);
  confirmationReturnFocus = document.activeElement;
  dialog.hidden = false;
  syncDialogBodyClass();
  refreshIcons();
  return new Promise((resolve) => {
    confirmationResolver = resolve;
    window.setTimeout(() => confirmButton.focus(), 0);
  });
}

function syncProductDialogControls() {
  const dialog = qs("#productDialog");
  const product = productById(dialog.dataset.productId || "");
  if (!product) return;

  const quantityInput = qs("#productDialogQuantity");
  const addButton = qs("#productDialogAddButton");
  const stock = qs("#productDialogStock");
  const shopper = canUseStoreCart();
  addButton.hidden = !shopper;
  if (!shopper) {
    const available = productAvailable(product);
    stock.textContent = available > 0 ? `В наличии: ${available} шт.` : "Нет в наличии";
    stock.classList.toggle("is-empty", available <= 0);
    return;
  }
  const availableLeft = Math.max(productAvailable(product) - cartQuantityFor(product.id), 0);
  quantityInput.max = String(availableLeft);
  quantityInput.disabled = availableLeft <= 0;
  quantityInput.value = availableLeft <= 0
    ? "0"
    : String(clampQuantity(quantityInput.value || "1", availableLeft));
  addButton.disabled = availableLeft <= 0;
  stock.textContent = availableLeft > 0
    ? availableLeft <= 5
      ? `Осталось ${availableLeft} шт.`
      : "В наличии"
    : "Нет в наличии";
  stock.classList.toggle("is-empty", availableLeft <= 0);
}

function openProductDialog(productId) {
  const product = productById(productId);
  if (!product || (product.status || "active") !== "active") return;
  const dialog = qs("#productDialog");
  dialog.dataset.productId = product.id;
  qs("#productDialogTitle").textContent = product.name;
  qs("#productDialogContent").innerHTML = `
    <div class="product-dialog-visual">
      ${
        product.photoUrl
          ? `<img src="${escapeHtml(product.photoUrl)}" alt="${escapeHtml(product.name)}" />`
          : `<div class="product-visual-fallback" aria-hidden="true">
              <i data-lucide="${productFallbackIcon(product)}"></i>
            </div>`
      }
    </div>
    <div class="product-dialog-info">
      <div class="product-dialog-price">${product.price} AC</div>
      <div class="product-dialog-meta">
        <span>${escapeHtml(product.category)}</span>
      </div>
      ${
        product.description
          ? `<p class="product-dialog-description">${escapeHtml(product.description)}</p>`
          : ""
      }
      ${
        canUseStoreCart()
          ? `<div class="product-dialog-controls">
              <label>
                <span>Количество</span>
                <input id="productDialogQuantity" type="number" min="1" value="1" />
              </label>
            </div>`
          : ""
      }
      <div id="productDialogStock" class="product-dialog-stock"></div>
    </div>
  `;
  dialog.hidden = false;
  syncDialogBodyClass();
  syncProductDialogControls();
  refreshIcons();
  const backButton = qs("#productDialogBackButton");
  backButton.textContent = canUseStoreCart() ? "Продолжить выбор" : "Закрыть";
  (canUseStoreCart() ? qs("#productDialogAddButton") : backButton).focus();
}

function closeProductDialog() {
  const dialog = qs("#productDialog");
  if (dialog.hidden) return;
  dialog.hidden = true;
  dialog.dataset.productId = "";
  syncDialogBodyClass();
}

function isOpenOrderStatus(status) {
  return ["created", "reserved", "transferred_to_teacher", "problem"].includes(status);
}

function orderHasAssignedWarehouses(order) {
  if (orderIsDigital(order)) return true;
  return (
    Array.isArray(order.items) &&
    order.items.length > 0 &&
    order.items.every((item) => Boolean(item.warehouseId))
  );
}

function orderIsDigital(order) {
  return (
    Array.isArray(order.items) &&
    order.items.length > 0 &&
    order.items.every((item) => item.fulfillmentType === "digital_code")
  );
}

function canAssignOrderWarehouses(order) {
  return (
    state.role === "admin" &&
    ["reserved", "problem"].includes(order.rawStatus) &&
    !orderHasAssignedWarehouses(order)
  );
}

function canIssueOrder(order) {
  return (
    ["teacher", "admin"].includes(state.role) &&
    ["reserved", "transferred_to_teacher"].includes(order.rawStatus) &&
    orderHasAssignedWarehouses(order)
  );
}

function canTransferOrder(order) {
  return (
    state.role === "admin" &&
    order.rawStatus === "reserved" &&
    orderHasAssignedWarehouses(order)
  );
}

function canCancelOrder(order) {
  if (["teacher", "admin"].includes(state.role)) {
    return ["reserved", "transferred_to_teacher"].includes(order.rawStatus);
  }
  return order.rawStatus === "reserved" && !orderHasAssignedWarehouses(order);
}

function canReturnOrder(order) {
  return (
    ["teacher", "admin"].includes(state.role) &&
    order.rawStatus === "issued_to_student" &&
    !(order.items || []).some((item) => item.fulfillmentType === "digital_code")
  );
}

function orderMatchesStatusFilter(order) {
  return orderMatchesNamedFilter(order, state.orderStatusFilter);
}

function orderMatchesNamedFilter(order, filter) {
  if (filter === "all") return true;
  if (filter === "action") return ["created", "problem"].includes(order.rawStatus);
  if (filter === "work") return ["reserved", "transferred_to_teacher"].includes(order.rawStatus);
  if (filter === "issued") return order.rawStatus === "issued_to_student";
  if (filter === "cancelled") return ["cancelled", "returned"].includes(order.rawStatus);
  if (filter === "open") return isOpenOrderStatus(order.rawStatus);
  return order.rawStatus === filter;
}

function orderSearchText(order) {
  return [
    order.id,
    order.backendId,
    order.student,
    order.item,
    order.warehouse,
    order.rawStatus,
    order.status,
    ...(order.items || []).flatMap((item) => [
      item.productName,
      item.warehouseName,
      item.productId,
    ]),
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function filteredOrders() {
  const query = state.orderSearch.trim().toLowerCase();
  return ordersForCurrentRole().filter((order) => {
    if (!orderMatchesStatusFilter(order)) return false;
    return !query || orderSearchText(order).includes(query);
  });
}

function ordersForCurrentRole() {
  if (state.role === "admin") return orders;
  const roleStudentIds = new Set(studentsForCurrentRole().map((student) => student.id));
  return orders.filter((order) => roleStudentIds.has(order.studentId));
}

function orderActionDescriptors(order) {
  const descriptors = [];
  if (canAssignOrderWarehouses(order)) {
    descriptors.push({ action: "open", label: "Назначить склад", icon: "warehouse" });
  } else if (canTransferOrder(order)) {
    descriptors.push({ action: "transfer", label: "Передать педагогу", icon: "send" });
    if (canIssueOrder(order)) {
      descriptors.push({ action: "issue", label: "Выдать заказ", icon: "package-check" });
    }
  } else if (canIssueOrder(order)) {
    descriptors.push({ action: "issue", label: "Выдать заказ", icon: "package-check" });
  } else {
    descriptors.push({ action: "open", label: "Подробнее", icon: "eye" });
  }
  if (descriptors[0].action !== "open") {
    descriptors.push({ action: "open", label: "Открыть заказ", icon: "eye" });
  }
  if (canReturnOrder(order)) {
    descriptors.push({ action: "return", label: "Оформить возврат", icon: "undo-2" });
  }
  if (canCancelOrder(order)) {
    descriptors.push({ action: "cancel", label: "Отменить заказ", icon: "circle-x", danger: true });
  }
  return descriptors;
}

function orderActionMarkup(order, descriptor, primary = false) {
  const orderId = escapeHtml(order.backendId || order.id);
  const attributes = descriptor.action === "open"
    ? `data-open-order="${orderId}"`
    : `data-order-action="${descriptor.action}" data-order-action-id="${orderId}"`;
  return `<button class="${primary ? "primary-action" : "order-menu-action"} ${descriptor.danger ? "danger-action" : ""}" type="button" ${attributes}>
      <i data-lucide="${descriptor.icon}"></i><span>${descriptor.label}</span>
    </button>`;
}

function orderActionButtons(order, includeOpen = true) {
  let descriptors = orderActionDescriptors(order);
  if (!includeOpen) descriptors = descriptors.filter((item) => item.action !== "open");
  if (!descriptors.length) return "";
  const [primary, ...secondary] = descriptors;
  return `<div class="order-actions">
      ${orderActionMarkup(order, primary, true)}
      ${secondary.length ? `<details class="order-more-menu">
        <summary title="Другие действия" aria-label="Другие действия"><i data-lucide="ellipsis"></i></summary>
        <div>${secondary.map((item) => orderActionMarkup(order, item)).join("")}</div>
      </details>` : ""}
    </div>`;
}

function formatOrderDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString("ru-RU", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function orderTotalValue(order) {
  if (Number(order.total || 0) > 0) return Number(order.total);
  return (order.items || []).reduce((sum, item) => sum + Number(item.totalPrice || 0), 0);
}

function orderAgeLabel(value) {
  const created = new Date(value);
  if (Number.isNaN(created.getTime())) return "";
  const minutes = Math.max(Math.floor((Date.now() - created.getTime()) / 60000), 0);
  if (minutes < 60) return `${minutes || 1} мин. назад`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} ч. назад`;
  const days = Math.floor(hours / 24);
  return `${days} дн. назад`;
}

function renderOrderStatusTabs() {
  const container = qs("#orderStatusTabs");
  if (!container) return;
  if (state.orderStatusFilter === "action") state.orderStatusFilter = "all";
  const roleOrders = ordersForCurrentRole();
  const tabs = [
    ["all", "Все"],
    ["work", "В работе"],
    ["issued", "Выполненные"],
    ["cancelled", "Отменены"],
  ];
  container.innerHTML = tabs
    .map(([value, label]) => {
      const count = value === "all"
        ? roleOrders.length
        : roleOrders.filter((order) => orderMatchesNamedFilter(order, value)).length;
      return `<button class="${state.orderStatusFilter === value ? "is-active" : ""}" type="button" data-order-status="${value}" role="tab" aria-selected="${state.orderStatusFilter === value}">
          <span>${label}</span><b>${count}</b>
        </button>`;
    })
    .join("");
}

function orderStudentContext(order) {
  return students.find((student) => student.id === order.studentId) || null;
}

function orderVenueName(order) {
  const student = orderStudentContext(order);
  return order.venueName || student?.venue || "Площадка не указана";
}

function orderTeacherName(order) {
  const student = orderStudentContext(order);
  return order.teacherName || student?.teacher || "Преподаватель не указан";
}

function orderPreferredWarehouseId(item) {
  const product = productById(item.productId || "");
  if (!product) return item.suggestedWarehouseId || "";
  const options = productWarehouses(product).filter(
    (warehouse) =>
      warehouse.id === item.suggestedWarehouseId ||
      warehouse.id === item.warehouseId ||
      warehouse.available >= Number(item.quantity || 0),
  );
  if (options.some((warehouse) => warehouse.id === state.defaultWarehouseId)) {
    return state.defaultWarehouseId;
  }
  return item.suggestedWarehouseId || "";
}

function summaryWarehouseLabel(item) {
  if (item.warehouseName) return item.warehouseName;
  if (item.suggestedWarehouseName) return `${item.suggestedWarehouseName} · в резерве`;
  return "Склад не назначен";
}

function orderFulfillmentSummaryOrders() {
  const staffRole = primaryStaffRole();
  const physicalOrders = ordersForCurrentRole().filter(
    (order) => !orderIsDigital(order) && Array.isArray(order.items) && order.items.length > 0,
  );
  if (["superadmin", "partner_director", "admin"].includes(staffRole)) {
    return physicalOrders.filter((order) =>
      ["created", "reserved", "transferred_to_teacher", "problem"].includes(order.rawStatus),
    );
  }
  if (staffRole === "teacher") {
    return physicalOrders.filter((order) => order.rawStatus === "transferred_to_teacher");
  }
  return [];
}

function renderOrderFulfillmentSummary() {
  const container = qs("#orderFulfillmentSummary");
  if (!container) return;
  const staffRole = primaryStaffRole();
  const isManager = ["superadmin", "partner_director", "admin"].includes(staffRole);
  const isTeacher = staffRole === "teacher";
  const summaryOrders = orderFulfillmentSummaryOrders();
  const visible = (isManager || isTeacher) && summaryOrders.length > 0;
  container.hidden = !visible;
  if (!visible) {
    container.innerHTML = "";
    return;
  }

  const venues = new Map();
  summaryOrders.forEach((order) => {
    const venueName = orderVenueName(order);
    const teacherName = orderTeacherName(order);
    if (!venues.has(venueName)) venues.set(venueName, new Map());
    const teachers = venues.get(venueName);
    if (!teachers.has(teacherName)) teachers.set(teacherName, []);
    teachers.get(teacherName).push(order);
  });

  const venueMarkup = [...venues.entries()]
    .sort(([left], [right]) => left.localeCompare(right, "ru"))
    .map(([venueName, teachers]) => {
      const venueOrderCount = [...teachers.values()].reduce((sum, rows) => sum + rows.length, 0);
      const teacherMarkup = [...teachers.entries()]
        .sort(([left], [right]) => left.localeCompare(right, "ru"))
        .map(([teacherName, teacherOrders]) => {
          const productsByWarehouse = new Map();
          teacherOrders.forEach((order) => {
            (order.items || []).forEach((item) => {
              if (item.fulfillmentType === "digital_code") return;
              const warehouse = summaryWarehouseLabel(item);
              const key = `${item.productId || item.productName}|${warehouse}`;
              if (!productsByWarehouse.has(key)) {
                productsByWarehouse.set(key, {
                  name: item.productName || "Товар",
                  quantity: 0,
                  warehouse,
                });
              }
              productsByWarehouse.get(key).quantity += Number(item.quantity || 0);
            });
          });
          const assignableOrders = isManager
            ? teacherOrders.filter(
                (order) =>
                  canAssignOrderWarehouses(order) &&
                  (order.items || []).every((item) => Boolean(orderPreferredWarehouseId(item))),
              )
            : [];
          const orderButtons = teacherOrders
            .map((order) => {
              const needsWarehouse = canAssignOrderWarehouses(order);
              const label = isTeacher
                ? `№${order.id} · ${order.student}`
                : `№${order.id} · ${needsWarehouse ? "назначить склад" : order.student}`;
              return `<button class="fulfillment-order-link" type="button" data-open-order="${escapeHtml(order.backendId || order.id)}">${escapeHtml(label)}</button>`;
            })
            .join("");
          return `
            <article class="fulfillment-teacher-group">
              <div class="fulfillment-teacher-head">
                <div><i data-lucide="user-round"></i><strong>${escapeHtml(teacherName)}</strong></div>
                <span>Заказов: ${teacherOrders.length}</span>
              </div>
              <div class="fulfillment-product-list">
                ${[...productsByWarehouse.values()]
                  .sort((left, right) => left.name.localeCompare(right.name, "ru"))
                  .map(
                    (item) => `
                      <div class="fulfillment-product-row">
                        <strong>${escapeHtml(item.name)}</strong>
                        <b>${item.quantity} шт.</b>
                        <span><i data-lucide="warehouse"></i>${escapeHtml(item.warehouse)}</span>
                      </div>`,
                  )
                  .join("")}
              </div>
              <div class="fulfillment-group-actions">
                <div class="fulfillment-order-links">${orderButtons}</div>
                ${assignableOrders.length
                  ? `<button class="secondary-action" type="button" data-confirm-summary-warehouses="${escapeHtml(assignableOrders.map((order) => order.backendId || order.id).join(","))}"><i data-lucide="warehouse"></i>Подтвердить склады (${assignableOrders.length})</button>`
                  : ""}
              </div>
            </article>`;
        })
        .join("");
      return `
        <details class="fulfillment-venue" open>
          <summary>
            <span><i data-lucide="map-pin"></i><strong>${escapeHtml(venueName)}</strong></span>
            <b>Заказов: ${venueOrderCount}</b>
          </summary>
          <div class="fulfillment-teachers">${teacherMarkup}</div>
        </details>`;
    })
    .join("");

  container.innerHTML = `
    <div class="fulfillment-summary-head">
      <div>
        <span>${isTeacher ? "К выдаче" : "Комплектация"}</span>
        <h3>${isTeacher ? "Передано вам" : "Заказы по площадкам"}</h3>
        <p>${isTeacher ? "Проверьте товары и склады перед выдачей ученикам." : "Сначала площадка, затем преподаватель, товары и склады."}</p>
      </div>
      <strong>${summaryOrders.length}</strong>
    </div>
    <div class="fulfillment-venue-list">${venueMarkup}</div>`;
}

function renderOrders() {
  if (state.orderStatusFilter === "action") state.orderStatusFilter = "all";
  const searchInput = qs("#orderSearch");
  const statusFilter = qs("#orderStatusFilter");
  if (searchInput) searchInput.value = state.orderSearch;
  if (statusFilter) statusFilter.value = state.orderStatusFilter;
  const clearSearchButton = qs("#clearOrderSearch");
  if (clearSearchButton) clearSearchButton.hidden = !state.orderSearch;
  renderOrderStatusTabs();
  renderOrderFulfillmentSummary();

  if (ordersForCurrentRole().length === 0) {
    qs("#ordersTable").innerHTML = '<div class="empty-state">Заказов пока нет</div>';
    return;
  }

  const visibleOrders = filteredOrders();
  if (visibleOrders.length === 0) {
    qs("#ordersTable").innerHTML =
      '<div class="empty-state">Заказов по выбранному фильтру не найдено</div>';
    return;
  }

  qs("#ordersTable").innerHTML = visibleOrders
    .map((order) => {
      const date = formatOrderDate(order.createdAt);
      const age = orderAgeLabel(order.createdAt);
      const total = orderTotalValue(order);
      const product = productById(order.items?.[0]?.productId || "");
      const displayStatus = orderIsDigital(order) ? "Выполнен" : order.status;
      return `
        <article class="order-card" data-tone="${escapeHtml(order.tone)}">
          <button class="order-card-visual" type="button" data-open-order="${escapeHtml(order.backendId || order.id)}" aria-label="Открыть заказ №${escapeHtml(order.id)}">
            ${product?.photoUrl ? `<img src="${escapeHtml(product.photoUrl)}" alt="" loading="lazy" />` : `<i data-lucide="${product ? productFallbackIcon(product) : "package"}"></i>`}
          </button>
          <div class="order-card-main">
            <div class="order-card-head">
              <strong class="order-number">Заказ №${escapeHtml(order.id)}</strong>
              <span class="status-badge ${order.tone}">${escapeHtml(displayStatus)}</span>
            </div>
            <strong class="order-card-student">${escapeHtml(order.student)}</strong>
            <div class="order-card-items">${escapeHtml(order.item)}</div>
            <div class="order-card-meta">
              ${
                ["teacher", "admin"].includes(state.role)
                  ? `<span>${
                      orderHasAssignedWarehouses(order)
                        ? `Склад назначен`
                        : `Ожидает назначения склада`
                    }</span>`
                  : ""
              }
              ${total ? `<span>Сумма: ${total} AC</span>` : ""}
              ${age ? `<span>${escapeHtml(age)}</span>` : date ? `<span>${escapeHtml(date)}</span>` : ""}
            </div>
          </div>
          ${orderActionButtons(order)}
        </article>
      `;
    })
    .join("");
}

function renderLedger() {
  const personalWalletContent = qs("#personalWalletContent");
  const staffStudentHistory = qs("#staffStudentHistory");
  const showStudentRegistry = ["teacher", "admin"].includes(state.role);
  if (personalWalletContent) personalWalletContent.hidden = showStudentRegistry;
  if (staffStudentHistory) staffStudentHistory.hidden = !showStudentRegistry;
  if (showStudentRegistry) {
    renderStudentRegistry();
    return;
  }

  const student = selectedStudent();
  const visibleLedger = ledger.filter(
    ([, , , studentId]) => !studentId || !student || studentId === student.id,
  );
  const amounts = visibleLedger.map(([, , amount]) => ledgerAmountValue(amount));
  const credited = amounts.filter((amount) => amount > 0).reduce((total, amount) => total + amount, 0);
  const spent = Math.abs(
    amounts.filter((amount) => amount < 0).reduce((total, amount) => total + amount, 0),
  );
  qs("#walletSummary").innerHTML = `
    <div class="wallet-stat wallet-stat-balance">
      <span>Доступно</span>
      <strong>${state.balance} AC</strong>
    </div>
    <div class="wallet-stat wallet-stat-credit">
      <span>Начислено</span>
      <strong>+${credited} AC</strong>
    </div>
    <div class="wallet-stat wallet-stat-debit">
      <span>Потрачено</span>
      <strong>${spent > 0 ? `-${spent}` : "0"} AC</strong>
    </div>
    <div class="wallet-stat">
      <span>Операций</span>
      <strong>${visibleLedger.length}</strong>
    </div>
  `;

  qs("#walletTitle").textContent = student ? `История: ${student.name}` : "История операций";

  if (visibleLedger.length === 0) {
    qs("#ledgerList").innerHTML = '<div class="empty-state">У выбранного ученика операций пока нет</div>';
    return;
  }

  qs("#ledgerList").innerHTML = visibleLedger
    .map(
      ([date, reason, amount]) => {
        const value = ledgerAmountValue(amount);
        const tone = value < 0 ? "debit" : "credit";
        return `
        <article class="ledger-entry ${tone}">
          <div class="ledger-entry-mark" aria-hidden="true">${value < 0 ? "−" : "+"}</div>
          <div class="ledger-entry-content">
            <strong>${escapeHtml(reason)}</strong>
            <span>${escapeHtml(date)}</span>
          </div>
          <strong class="ledger-entry-amount">${escapeHtml(amount)}</strong>
        </article>
      `;
    })
    .join("");
}

function ledgerAmountValue(amount) {
  const value = Number(String(amount).replace(/[^\d,.-]/g, "").replace(",", "."));
  return Number.isFinite(value) ? value : 0;
}

function reportDateValue(date) {
  const offset = date.getTimezoneOffset();
  return new Date(date.getTime() - offset * 60000).toISOString().slice(0, 10);
}

function accrualReportTeacherKey(entry) {
  return String(entry.teacher_id || entry.teacher_name || "");
}

function accrualReportGroupKey(entry) {
  return String(entry.group_name || "__without_group__");
}

function filteredAccrualReportEntries() {
  const entries = state.accrualReport?.entries || [];
  return entries.filter((entry) => {
    const teacherMatches =
      state.accrualReportTeacherFilter === "all" ||
      accrualReportTeacherKey(entry) === state.accrualReportTeacherFilter;
    const groupMatches =
      state.accrualReportGroupFilter === "all" ||
      accrualReportGroupKey(entry) === state.accrualReportGroupFilter;
    return teacherMatches && groupMatches;
  });
}

function renderAccrualReportFilters(entries) {
  const teacherSelect = qs("#acReportTeacherFilter");
  const groupSelect = qs("#acReportGroupFilter");
  if (!teacherSelect || !groupSelect) return;

  const teachers = new Map();
  entries.forEach((entry) => {
    const key = accrualReportTeacherKey(entry);
    if (key) teachers.set(key, entry.teacher_name || "Преподаватель не указан");
  });
  const teacherOptions = [...teachers.entries()].sort((left, right) =>
    left[1].localeCompare(right[1], "ru"),
  );
  if (
    state.accrualReportTeacherFilter !== "all" &&
    !teachers.has(state.accrualReportTeacherFilter)
  ) {
    state.accrualReportTeacherFilter = "all";
  }
  teacherSelect.innerHTML = [
    '<option value="all">Все преподаватели</option>',
    ...teacherOptions.map(
      ([value, label]) => `<option value="${escapeHtml(value)}">${escapeHtml(label)}</option>`,
    ),
  ].join("");
  teacherSelect.value = state.accrualReportTeacherFilter;

  const groupLabels = new Map();
  entries.forEach((entry) => {
    const key = accrualReportGroupKey(entry);
    groupLabels.set(key, entry.group_name || "Без группы");
  });
  const groupOptions = [...groupLabels.entries()].sort((left, right) =>
    left[1].localeCompare(right[1], "ru"),
  );
  if (
    state.accrualReportGroupFilter !== "all" &&
    !groupLabels.has(state.accrualReportGroupFilter)
  ) {
    state.accrualReportGroupFilter = "all";
  }
  groupSelect.innerHTML = [
    '<option value="all">Все группы</option>',
    ...groupOptions.map(
      ([value, label]) => `<option value="${escapeHtml(value)}">${escapeHtml(label)}</option>`,
    ),
  ].join("");
  groupSelect.value = state.accrualReportGroupFilter;
}

function renderAccrualReport() {
  const fromInput = qs("#acReportDateFrom");
  const toInput = qs("#acReportDateTo");
  const summary = qs("#acReportSummary");
  const list = qs("#acReportList");
  if (!fromInput || !toInput || !summary || !list) return;
  const today = new Date();
  if (!toInput.value) toInput.value = reportDateValue(today);
  if (!fromInput.value) {
    fromInput.value = reportDateValue(new Date(today.getFullYear(), today.getMonth(), 1));
  }
  if (state.accrualReportLoading) {
    summary.innerHTML = '<div class="skeleton-row"></div><div class="skeleton-row"></div>';
    list.innerHTML = '<div class="report-skeleton"><div></div><div></div><div></div></div>';
    return;
  }
  const report = state.accrualReport;
  if (!report) {
    summary.textContent = "Выберите период и нажмите «Показать».";
    list.innerHTML = "";
    return;
  }
  renderAccrualReportFilters(report.entries);
  const entries = filteredAccrualReportEntries();
  const totalAstrocoins = entries.reduce((total, entry) => total + Number(entry.amount || 0), 0);
  const teacherCount = new Set(entries.map(accrualReportTeacherKey)).size;
  const studentCount = new Set(entries.map((entry) => String(entry.student_id))).size;
  const average = entries.length
    ? Math.round(totalAstrocoins / entries.length)
    : 0;
  summary.innerHTML = `
    <article><span>Начислено</span><strong>${totalAstrocoins} AC</strong></article>
    <article><span>Операций</span><strong>${entries.length}</strong></article>
    <article><span>Преподавателей</span><strong>${teacherCount}</strong></article>
    <article><span>Учеников</span><strong>${studentCount}</strong></article>
    <article><span>Среднее начисление</span><strong>${average} AC</strong></article>`;
  list.innerHTML = entries.length
    ? entries
        .map(
          (entry) => `
            <details class="report-row">
              <summary>
              <div>
                <strong>${escapeHtml(entry.teacher_name)}</strong>
                <span>${escapeHtml(new Date(entry.created_at).toLocaleString("ru-RU"))}</span>
              </div>
              <div>
                <strong>${escapeHtml(entry.student_name)}</strong>
                <span>${escapeHtml(entry.group_name || "Без группы")}</span>
              </div>
              <div>
                <strong>+${Number(entry.amount)} AC</strong>
                <span>${escapeHtml(entry.reason)}</span>
              </div>
              <i data-lucide="chevron-down"></i>
              </summary>
              <div class="report-row-details">
                <span>Группа: ${escapeHtml(entry.group_name || "Без группы")}</span>
                <span>Дата: ${escapeHtml(new Date(entry.created_at).toLocaleString("ru-RU"))}</span>
              </div>
            </details>
          `,
        )
        .join("")
    : `<div class="empty-state compact-empty"><i data-lucide="calendar-x"></i><strong>Начислений нет</strong><span>${report.entries.length ? "Измените преподавателя или группу." : "Попробуйте выбрать другой период."}</span></div>`;
  refreshIcons();
}

function setAccrualReportPeriod(period) {
  const today = new Date();
  const from = new Date(today);
  if (period === "week") from.setDate(today.getDate() - 6);
  if (period === "month") from.setDate(1);
  qs("#acReportDateFrom").value = reportDateValue(from);
  qs("#acReportDateTo").value = reportDateValue(today);
  state.accrualReportPeriod = period;
  qsa("[data-report-period]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.reportPeriod === period);
  });
  loadAccrualReport();
}

async function loadAccrualReport() {
  const dateFrom = qs("#acReportDateFrom")?.value || "";
  const dateTo = qs("#acReportDateTo")?.value || "";
  if (!dateFrom || !dateTo) {
    showNotice("Выберите начало и конец периода", "danger");
    return;
  }
  state.accrualReportLoading = true;
  renderAccrualReport();
  try {
    const params = new URLSearchParams({
      max_user_id: String(apiContext.maxUserId),
      tenant_slug: apiContext.tenantSlug || "",
      date_from: dateFrom,
      date_to: dateTo,
    });
    const response = await apiFetch(`/api/v1/miniapp/coins/report?${params}`);
    if (!response.ok) throw new Error(await parseApiError(response));
    state.accrualReport = await response.json();
  } catch (error) {
    showNotice(error.message || "Не удалось загрузить отчет", "danger");
  } finally {
    state.accrualReportLoading = false;
    renderAccrualReport();
  }
}

function renderAccrual() {
  const groupSelect = qs("#accrualGroupSelect");
  const studentList = qs("#accrualStudentList");
  const nameFilter = qs("#accrualNameFilter");
  if (!groupSelect || !studentList || !nameFilter) return;
  const rulesButton = qs("#openAccrualRulesButton");
  if (rulesButton) {
    rulesButton.hidden = !["superadmin", "partner_director", "admin"].includes(
      primaryStaffRole(),
    );
  }

  const groups = studentGroups();
  if (state.accrualGroup && state.accrualGroup !== "all" && !groups.includes(state.accrualGroup)) {
    state.accrualGroup = "";
  }
  groupSelect.innerHTML = [
    '<option value="">Сначала выберите группу</option>',
    '<option value="all">Все группы</option>',
    ...groups.map((group) => `<option value="${escapeHtml(group)}">${escapeHtml(group)}</option>`),
  ].join("");
  groupSelect.disabled = groups.length === 0;
  groupSelect.value = state.accrualGroup;
  nameFilter.value = state.accrualNameFilter;

  const groupReason = qs("#groupAccrualReason");
  const selectedGroupReason = groupReason.value;
  const selectedRule = state.accrualRules.find((rule) => rule.reason === selectedGroupReason);
  const customSelected = selectedGroupReason === "__custom__";
  const customReason = qs("#customAccrualReason")?.value.trim() || "";
  const customAmount = Number.parseInt(qs("#customAccrualAmount")?.value || "0", 10);
  const selectedGroupAmount = customSelected ? customAmount : Number(selectedRule?.amount || 0);
  const effectiveReason = customSelected ? customReason : selectedGroupReason;
  groupReason.innerHTML = [
    '<option value="">Выберите причину</option>',
    ...state.accrualRules.filter((rule) => rule.isActive).map(
      (rule) => `<option value="${escapeHtml(rule.reason)}">${escapeHtml(rule.reason)} · +${rule.amount} AC</option>`,
    ),
    '<option value="__custom__">Своя причина и сумма</option>',
  ].join("");
  groupReason.value = selectedGroupReason;
  const customReasonField = qs("#customAccrualReasonField");
  const customAmountField = qs("#customAccrualAmountField");
  if (customReasonField) customReasonField.hidden = !customSelected;
  if (customAmountField) customAmountField.hidden = !customSelected;
  const normalizedName = state.accrualNameFilter.trim().toLowerCase();
  const groupStudents = state.accrualGroup ? studentsForGroup(state.accrualGroup) : [];
  const visibleStudents = groupStudents.filter((student) =>
    student.name.toLowerCase().includes(normalizedName),
  );
  const resultCount = qs("#accrualResultCount");
  if (resultCount) resultCount.textContent = state.accrualGroup ? `Найдено: ${visibleStudents.length}` : "";
  const clearSearchButton = qs("#clearAccrualSearch");
  if (clearSearchButton) clearSearchButton.hidden = !state.accrualNameFilter;
  const selectedCount = state.selectedAccrualStudents.size;
  const selectedCountLabel = qs("#accrualSelectedCount");
  if (selectedCountLabel) {
    selectedCountLabel.textContent = selectedCount ? `Выбрано: ${selectedCount}` : "Никто не выбран";
  }
  const canSubmitAccrual = selectedCount > 0 && Boolean(effectiveReason) && selectedGroupAmount > 0;
  qsa("[data-selected-accrual]").forEach((selectedButton) => {
    selectedButton.disabled = state.accrualSaving || !canSubmitAccrual;
    selectedButton.textContent = state.accrualSaving
      ? "Начисление..."
      : selectedButton.closest("#accrualStickyAction")
        ? `Начислить ${selectedCount}`
        : `Начислить выбранным (${selectedCount})`;
  });
  const stickyAction = qs("#accrualStickyAction");
  if (stickyAction) stickyAction.hidden = selectedCount === 0;
  const stickyCount = qs("#accrualStickyCount");
  if (stickyCount) stickyCount.textContent = `Выбрано: ${selectedCount}`;
  const stickyDetails = qs("#accrualStickyDetails");
  if (stickyDetails) {
    stickyDetails.textContent = effectiveReason && selectedGroupAmount
      ? `${effectiveReason} · +${selectedGroupAmount} AC каждому`
      : "Выберите причину и сумму";
  }
  const bulkHint = qs(".accrual-bulk p");
  if (bulkHint) {
    bulkHint.textContent = selectedCount
      ? `Выбрано учеников: ${selectedCount}`
      : "Отметьте учеников в списке ниже.";
  }

  if (!state.accrualGroup) {
    studentList.innerHTML = '<div class="empty-state compact-empty"><i data-lucide="users"></i><strong>Выберите группу</strong><span>После выбора появится список учеников.</span></div>';
    refreshIcons();
    return;
  }
  if (visibleStudents.length === 0) {
    studentList.innerHTML = '<div class="empty-state compact-empty"><strong>Ученики не найдены</strong><button type="button" class="secondary-action" data-clear-accrual-search>Сбросить поиск</button></div>';
    return;
  }

  studentList.innerHTML = visibleStudents
    .map((student) => {
      const checked = state.selectedAccrualStudents.has(student.id);
      return `
        <label class="accrual-card accrual-select-card ${checked ? "is-selected" : ""}">
          <input
            type="checkbox"
            data-accrual-student-check="${escapeHtml(student.id)}"
            ${checked ? "checked" : ""}
          />
          <span class="accrual-student-head">
            <span class="accrual-student-mark">${escapeHtml(student.name.slice(0, 1))}</span>
              <span class="accrual-student-copy">
              <strong>${escapeHtml(student.name)}</strong>
              <span class="accrual-student-meta">
                ${state.accrualGroup === "all" ? `<span>${escapeHtml(studentGroupName(student))}</span>` : ""}
                ${state.role === "teacher" ? "" : `<span>${escapeHtml(student.teacher)}</span>`}
              </span>
            </span>
            <span class="accrual-student-actions">
              <span class="soft-badge">${student.balance} AC</span>
            </span>
          </span>
        </label>
      `;
    })
    .join("");
  refreshIcons();
}

function readAccrualRulesEditor() {
  return qsa("[data-accrual-rule-row]").map((row) => ({
    reason: row.querySelector("[data-accrual-rule-reason]")?.value.trim() || "",
    amount: Number.parseInt(
      row.querySelector("[data-accrual-rule-amount]")?.value || "0",
      10,
    ),
    isActive: true,
  }));
}

function renderAccrualRulesEditor() {
  const editor = qs("#accrualRulesEditor");
  if (!editor) return;
  editor.innerHTML = state.accrualRulesDraft.map((rule, index) => `
    <div class="accrual-rule-row" data-accrual-rule-row="${index}">
      <input data-accrual-rule-reason type="text" maxlength="160" value="${escapeHtml(rule.reason || "")}" placeholder="Причина начисления" aria-label="Причина начисления" />
      <input data-accrual-rule-amount type="number" min="1" max="10000" inputmode="numeric" value="${Number(rule.amount || 0) || ""}" placeholder="Сумма AC" aria-label="Сумма астрокоинов" />
      <button class="icon-button danger-action" type="button" data-remove-accrual-rule="${index}" title="Удалить причину" aria-label="Удалить причину"><i data-lucide="trash-2"></i></button>
    </div>
  `).join("");
  refreshIcons();
}

function openAccrualRulesDialog() {
  if (!["superadmin", "partner_director", "admin"].includes(primaryStaffRole())) return;
  state.accrualRulesDraft = state.accrualRules.map((rule) => ({ ...rule }));
  renderAccrualRulesEditor();
  const dialog = qs("#accrualRulesDialog");
  if (dialog) dialog.hidden = false;
}

function closeAccrualRulesDialog() {
  const dialog = qs("#accrualRulesDialog");
  if (dialog) dialog.hidden = true;
  state.accrualRulesDraft = [];
}

async function saveAccrualRules() {
  if (state.accrualRulesSaving) return;
  const rules = readAccrualRulesEditor();
  if (!rules.length) {
    showNotice("Добавьте хотя бы одну причину начисления", "danger");
    return;
  }
  if (rules.some((rule) => rule.reason.length < 2 || !rule.amount || rule.amount < 1)) {
    showNotice("Заполните причину и положительную сумму в каждой строке", "danger");
    return;
  }
  const normalized = rules.map((rule) => rule.reason.toLowerCase());
  if (new Set(normalized).size !== normalized.length) {
    showNotice("Причины начислений не должны повторяться", "danger");
    return;
  }
  state.accrualRulesSaving = true;
  const saveButton = qs("#saveAccrualRulesButton");
  if (saveButton) saveButton.disabled = true;
  try {
    const response = await apiFetch("/api/v1/miniapp/coins/rules", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        max_user_id: Number(apiContext.maxUserId),
        tenant_slug: apiContext.tenantSlug || undefined,
        rules: rules.map((rule) => ({
          reason: rule.reason,
          amount: rule.amount,
          is_active: true,
        })),
      }),
    });
    if (!response.ok) throw new Error(await parseApiError(response));
    const result = await response.json();
    state.accrualRules = result.map((rule) => ({
      id: rule.id ? String(rule.id) : "",
      reason: rule.reason,
      amount: Number(rule.amount),
      isActive: rule.is_active !== false,
    }));
    closeAccrualRulesDialog();
    renderAccrual();
    showNotice("Причины начислений сохранены");
  } catch (error) {
    showNotice(error.message || "Не удалось сохранить причины", "danger");
  } finally {
    state.accrualRulesSaving = false;
    if (saveButton) saveButton.disabled = false;
  }
}
