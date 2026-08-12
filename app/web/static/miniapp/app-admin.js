function studentRegistryStatus(status) {
  const statuses = {
    active: { label: "Обучается", tone: "active" },
    departed: { label: "Выбыл", tone: "departed" },
    archived: { label: "Архив", tone: "archived" },
  };
  return statuses[status] || statuses.active;
}

function studentHistoryChangedFields(fields) {
  const labels = {
    crm_deal_id: "данные CRM",
    crm_uuid: "данные CRM",
    lms_student_id: "ID ученика",
    first_name: "имя",
    last_name: "фамилия",
    group_name: "группа",
    course_name: "курс",
    venue_name: "площадка",
    teacher_name: "преподаватель",
  };
  return [...new Set((fields || []).map((field) => labels[field] || field))];
}

function studentHistoryCopy(event) {
  if (event.eventType === "imported") {
    return {
      title: "Добавлен в систему",
      detail: "Данные ученика загружены из файла.",
    };
  }
  if (event.eventType === "status_changed") {
    const from = studentRegistryStatus(event.fromStatus || "active").label;
    const to = studentRegistryStatus(event.toStatus).label;
    return {
      title: `Статус изменен: ${to}`,
      detail: `${from} → ${to}`,
    };
  }
  const changedFields = studentHistoryChangedFields(event.changedFields);
  return {
    title: "Данные обновлены",
    detail: changedFields.length
      ? `Изменено: ${changedFields.join(", ")}.`
      : "Файл загружен повторно, данные не изменились.",
  };
}

function renderStudentRegistry() {
  const panel = qs("#adminPanel");
  if (!panel) return;

  if (state.adminStudentsLoading || (!state.adminStudentsLoaded && !state.adminStudentsError)) {
    panel.innerHTML = `
      <div class="student-registry-loading" role="status">
        <span class="button-spinner" aria-hidden="true"></span>
        <strong>Загружаем учеников</strong>
      </div>
    `;
    return;
  }

  if (state.adminStudentsError) {
    panel.innerHTML = `
      <div class="empty-state student-registry-error">
        <i data-lucide="circle-alert"></i>
        <strong>Не удалось загрузить учеников</strong>
        <span>${escapeHtml(state.adminStudentsError)}</span>
        <button class="secondary-action" type="button" data-retry-student-registry>
          <i data-lucide="refresh-cw"></i><span>Повторить</span>
        </button>
      </div>
    `;
    refreshIcons();
    return;
  }

  const allStudents = state.adminStudents;
  const statusCounts = allStudents.reduce(
    (counts, student) => {
      counts.all += 1;
      counts[student.status] = (counts[student.status] || 0) + 1;
      return counts;
    },
    { all: 0, active: 0, departed: 0, archived: 0 },
  );
  const groups = [...new Set(allStudents.map((student) => student.group).filter(Boolean))]
    .sort((left, right) => left.localeCompare(right, "ru"));
  const query = state.adminEntitySearch.trim().toLowerCase();
  const visibleStudents = allStudents
    .filter((student) => {
      const matchesStatus =
        state.studentRegistryStatusFilter === "all" ||
        student.status === state.studentRegistryStatusFilter;
      const matchesGroup =
        state.studentRegistryGroupFilter === "all" ||
        student.group === state.studentRegistryGroupFilter;
      const searchText = [
        student.name,
        student.lmsId,
        student.group,
        student.course,
        student.venue,
        student.teacher,
      ].join(" ").toLowerCase();
      return matchesStatus && matchesGroup && (!query || searchText.includes(query));
    })
    .sort((left, right) => {
      const statusOrder = { active: 0, departed: 1, archived: 2 };
      const statusCompare = (statusOrder[left.status] ?? 3) - (statusOrder[right.status] ?? 3);
      if (statusCompare !== 0) return statusCompare;
      const groupCompare = (left.group || "").localeCompare(right.group || "", "ru");
      return groupCompare || left.name.localeCompare(right.name, "ru");
    });
  const statusFilters = [
    ["all", "Все ученики", "users"],
    ["active", "Обучаются", "user-check"],
    ["departed", "Выбыли", "user-minus"],
    ["archived", "В архиве", "archive"],
  ];

  panel.innerHTML = `
    <div class="admin-section-toolbar student-registry-heading">
      <div>
        <h3>Все ученики</h3>
        <span>Состояние и история изменений с момента первого импорта</span>
      </div>
      <button class="secondary-action" type="button" data-retry-student-registry>
        <i data-lucide="refresh-cw"></i><span>Обновить</span>
      </button>
    </div>
    <div class="student-registry-metrics" aria-label="Фильтр по состоянию">
      ${statusFilters.map(([status, label, icon]) => `
        <button
          class="student-registry-metric ${state.studentRegistryStatusFilter === status ? "is-active" : ""}"
          type="button"
          data-student-registry-status="${status}"
        >
          <i data-lucide="${icon}"></i>
          <span><strong>${statusCounts[status] || 0}</strong><small>${label}</small></span>
        </button>
      `).join("")}
    </div>
    <div class="admin-filter-toolbar student-registry-filters">
      <label class="search-field">
        <i data-lucide="search"></i>
        <input id="adminEntitySearch" type="search" value="${escapeHtml(state.adminEntitySearch)}" placeholder="ФИО, группа, ID или преподаватель" />
        <button class="search-clear" type="button" data-clear-admin-search ${state.adminEntitySearch ? "" : "hidden"}><i data-lucide="x"></i></button>
      </label>
      <select id="studentRegistryGroupFilter" aria-label="Группа">
        <option value="all">Все группы</option>
        ${groups.map((group) => `<option value="${escapeHtml(group)}" ${state.studentRegistryGroupFilter === group ? "selected" : ""}>${escapeHtml(group)}</option>`).join("")}
      </select>
      <span>Показано: ${visibleStudents.length} из ${allStudents.length}</span>
    </div>
    <div class="student-registry-list">
      ${visibleStudents.length ? visibleStudents.map((student) => {
        const status = studentRegistryStatus(student.status);
        const history = [...student.history].sort(
          (left, right) => new Date(right.occurredAt) - new Date(left.occurredAt),
        );
        const meta = [student.group, student.course, student.venue, student.teacher]
          .filter(Boolean);
        return `
          <details class="student-registry-card">
            <summary>
              <span class="student-registry-mark">${escapeHtml(student.name.trim().slice(0, 1).toUpperCase() || "У")}</span>
              <span class="student-registry-main">
                <span class="student-registry-name-row">
                  <strong>${escapeHtml(student.name)}</strong>
                  <span class="student-registry-status is-${status.tone}">${status.label}</span>
                </span>
                <span class="student-registry-meta">${meta.map((item) => `<span>${escapeHtml(item)}</span>`).join("") || "Данные группы не указаны"}</span>
              </span>
              <span class="student-registry-balance">${student.balance} AC</span>
              <span class="student-registry-chevron"><i data-lucide="chevron-down"></i></span>
            </summary>
            <div class="student-registry-details">
              <div class="student-registry-dates">
                <span><small>Импортирован</small><strong>${formatRegistryDate(student.importedAt)}</strong></span>
                <span><small>Данные обновлены</small><strong>${formatRegistryDate(student.updatedAt)}</strong></span>
                <span><small>Статус обновлен</small><strong>${formatRegistryDate(student.statusUpdatedAt)}</strong></span>
                <span class="${student.departedAt ? "is-departed" : ""}"><small>Дата выбытия</small><strong>${student.departedAt ? formatRegistryDate(student.departedAt) : "Нет"}</strong></span>
              </div>
              <div class="student-registry-identifiers">
                <span><small>ID ученика</small><strong>${escapeHtml(student.lmsId || "Не указан")}</strong></span>
                <span><small>Группа</small><strong>${escapeHtml(student.group || "Не указана")}</strong></span>
              </div>
              <section class="student-history">
                <div class="student-history-head">
                  <h4>История ученика</h4>
                  <span>${history.length} ${history.length === 1 ? "событие" : "событий"}</span>
                </div>
                <div class="student-history-list">
                  ${history.length ? history.map((event) => {
                    const copy = studentHistoryCopy(event);
                    return `
                      <article class="student-history-item is-${escapeHtml(event.eventType)}">
                        <span class="student-history-dot" aria-hidden="true"></span>
                        <span class="student-history-copy">
                          <strong>${escapeHtml(copy.title)}</strong>
                          <span>${escapeHtml(copy.detail)}</span>
                          ${event.actorName ? `<small>Ответственный: ${escapeHtml(event.actorName)}</small>` : ""}
                        </span>
                        <time datetime="${escapeHtml(event.occurredAt)}">${formatRegistryDate(event.occurredAt)}</time>
                      </article>
                    `;
                  }).join("") : '<div class="empty-state compact-empty">История пока пуста</div>'}
                </div>
              </section>
            </div>
          </details>
        `;
      }).join("") : `
        <div class="empty-state student-registry-empty">
          <i data-lucide="users"></i>
          <strong>Ученики не найдены</strong>
          <span>Измените поиск или фильтр.</span>
          <button class="secondary-action" type="button" data-reset-student-registry>Сбросить фильтры</button>
        </div>
      `}
    </div>
  `;
  refreshIcons();
}

function adminHistoryStatus(status) {
  return {
    success: { label: "Выполнено", icon: "check" },
    partial: { label: "Требует внимания", icon: "triangle-alert" },
    error: { label: "Ошибка", icon: "x" },
  }[status] || { label: "Выполнено", icon: "check" };
}

function adminHistoryFacts(entry) {
  const payload = entry.payload || {};
  const facts = [];
  const add = (label, value) => {
    if (value === undefined || value === null || value === "") return;
    facts.push([label, String(value)]);
  };
  if (entry.action === "amocrm.students_synced") {
    add("Получено сделок", Array.isArray(payload.lead_ids) ? payload.lead_ids.length : 0);
    add("Создано учеников", Number(payload.created_students || 0));
    add("Уже были в системе", Number(payload.existing_students || 0));
    add("Не хватает данных", Object.keys(payload.incomplete_leads || {}).length);
  } else if (entry.action === "amocrm.student_status_updated") {
    add("Найдено учеников", Number(payload.matched_students || 0));
    add("Статус изменен", Number(payload.updated_students || 0));
    add("Не найдены", Array.isArray(payload.unmatched_lead_ids) ? payload.unmatched_lead_ids.length : 0);
  } else if (entry.action === "amocrm.sync_failed") {
    add("Причина", payload.error || "Синхронизация не выполнена");
  } else {
    add("Файл", payload.filename);
    add("Товар", payload.name || payload.sku);
    add("Заказ", payload.order_number ? `№${payload.order_number}` : "");
    add("Создано", payload.created_students ?? payload.created_products);
    add("Обновлено", payload.updated_students ?? payload.updated_products);
    add("Количество", payload.quantity ?? payload.credited_students);
    add("Сумма", payload.total_astrocoins ? `${payload.total_astrocoins} AC` : "");
    add("Роль", payload.role || payload.staff_role);
  }
  return facts.slice(0, 5);
}

function renderAdminHistory() {
  const panel = qs("#adminPanel");
  if (!panel) return;
  const query = state.adminEntitySearch.trim().toLowerCase();
  const entries = state.adminHistory.filter((entry) => {
    const isAmoCrmEvent = entry.action.startsWith("amocrm.");
    if (apiContext.demoMode && (state.adminHistoryKind === "amocrm") !== isAmoCrmEvent) {
      return false;
    }
    const text = [
      entry.title,
      entry.category,
      entry.actorName,
      entry.action,
      JSON.stringify(entry.payload || {}),
    ].join(" ").toLowerCase();
    return !query || text.includes(query);
  });
  const issueCount = entries.filter((entry) => entry.status !== "success").length;
  const title = state.adminHistoryKind === "amocrm"
    ? "Синхронизация amoCRM"
    : "Действия сотрудников";
  const description = state.adminHistoryKind === "amocrm"
    ? "Создание учеников, смена статусов и ошибки входящих данных"
    : "Изменения товаров, заказов, складов, доступов и настроек";

  panel.innerHTML = `
    <div class="admin-section-toolbar admin-history-heading">
      <div><h3>${title}</h3><span>${description}</span></div>
      <button class="secondary-action" type="button" data-retry-admin-history ${state.adminHistoryLoading ? "disabled" : ""}>
        <i data-lucide="refresh-cw"></i><span>Обновить</span>
      </button>
    </div>
    <div class="admin-history-controls">
      <div class="segmented-control" aria-label="Вид истории">
        <button type="button" class="${state.adminHistoryKind === "actions" ? "is-active" : ""}" data-admin-history-kind="actions">Действия</button>
        <button type="button" class="${state.adminHistoryKind === "amocrm" ? "is-active" : ""}" data-admin-history-kind="amocrm">amoCRM</button>
      </div>
      <label class="search-field"><i data-lucide="search"></i><input id="adminEntitySearch" type="search" value="${escapeHtml(state.adminEntitySearch)}" placeholder="Событие или сотрудник" /><button class="search-clear" type="button" data-clear-admin-search ${state.adminEntitySearch ? "" : "hidden"}><i data-lucide="x"></i></button></label>
      <select id="adminHistoryPeriod" aria-label="Период истории">
        ${[[7, "7 дней"], [30, "30 дней"], [90, "3 месяца"], [365, "Год"]].map(([days, label]) => `<option value="${days}" ${state.adminHistoryPeriod === days ? "selected" : ""}>${label}</option>`).join("")}
      </select>
    </div>
    <div class="admin-history-summary">
      <span><strong>${entries.length}</strong> событий</span>
      <span class="${issueCount ? "has-issues" : ""}"><strong>${issueCount}</strong> требуют внимания</span>
    </div>
    ${state.adminHistoryLoading ? `
      <div class="admin-history-loading"><span class="loading-spinner"></span><strong>Загружаем историю</strong></div>
    ` : state.adminHistoryError ? `
      <div class="empty-state admin-history-empty"><i data-lucide="circle-alert"></i><strong>${escapeHtml(state.adminHistoryError)}</strong><button class="secondary-action" type="button" data-retry-admin-history>Повторить</button></div>
    ` : `
      <div class="admin-history-list">
        ${entries.length ? entries.map((entry) => {
          const status = adminHistoryStatus(entry.status);
          const facts = adminHistoryFacts(entry);
          return `<article class="admin-history-entry is-${escapeHtml(entry.status)}">
            <span class="admin-history-mark"><i data-lucide="${status.icon}"></i></span>
            <div class="admin-history-main">
              <div class="admin-history-title"><strong>${escapeHtml(entry.title)}</strong><span>${escapeHtml(entry.category)}</span></div>
              ${facts.length ? `<div class="admin-history-facts">${facts.map(([label, value]) => `<span><small>${escapeHtml(label)}</small><strong>${escapeHtml(value)}</strong></span>`).join("")}</div>` : ""}
              <div class="admin-history-meta"><span>${escapeHtml(entry.actorName)}</span>${entry.actorMaxUserId ? `<span>MAX ID ${entry.actorMaxUserId}</span>` : ""}<span>${escapeHtml(status.label)}</span></div>
            </div>
            <time datetime="${escapeHtml(entry.createdAt)}">${formatRegistryDate(entry.createdAt)}</time>
          </article>`;
        }).join("") : `<div class="empty-state admin-history-empty"><i data-lucide="history"></i><strong>Событий за этот период нет</strong><span>Новые действия появятся здесь автоматически.</span></div>`}
      </div>
    `}
  `;
  refreshIcons();
}

if (apiContext.demoMode && !state.adminHistory.length) {
  const now = new Date();
  state.adminHistory = [
    normalizeAdminHistoryEntry({
      id: "demo-history-product",
      action: "product.updated",
      title: "Товар изменен",
      category: "Товары",
      status: "success",
      actor_name: "Администратор",
      actor_max_user_id: 53364725,
      payload: { name: "Набор для творчества", sku: "CREATIVE-01" },
      created_at: now.toISOString(),
    }),
    normalizeAdminHistoryEntry({
      id: "demo-history-order",
      action: "miniapp_order.cancelled",
      title: "Заказ отменен",
      category: "Заказы",
      status: "success",
      actor_name: "Директор",
      payload: { order_number: 184 },
      created_at: new Date(now.getTime() - 45 * 60 * 1000).toISOString(),
    }),
    normalizeAdminHistoryEntry({
      id: "demo-history-amocrm-sync",
      action: "amocrm.students_synced",
      title: "Ученики синхронизированы",
      category: "amoCRM",
      status: "partial",
      actor_name: "amoCRM",
      payload: {
        lead_ids: [41001, 41002, 41003],
        created_students: 2,
        existing_students: 0,
        incomplete_leads: { 41003: ["Группа"] },
      },
      created_at: new Date(now.getTime() - 12 * 60 * 1000).toISOString(),
    }),
    normalizeAdminHistoryEntry({
      id: "demo-history-amocrm-status",
      action: "amocrm.student_status_updated",
      title: "Статус ученика обновлен",
      category: "amoCRM",
      status: "success",
      actor_name: "amoCRM",
      payload: { matched_students: 1, updated_students: 1, unmatched_lead_ids: [] },
      created_at: new Date(now.getTime() - 70 * 60 * 1000).toISOString(),
    }),
  ];
  state.adminHistoryLoaded = true;
}

function renderAdminPanel() {
  const adminTitles = {
    summary: "Операционная сводка",
    products: "Товары",
    inventory: "Остатки",
    warehouses: "Склады",
    crm: "Импорт учеников и групп",
    contacts: "Связи доступа",
    staff: "Сотрудники",
    students: "Ученики",
    history: "История изменений",
  };
  qs("#adminViewTitle").textContent = adminTitles[state.adminTab] || "Операции";
  const adminRoleEyebrow = qs("#adminRoleEyebrow");
  if (adminRoleEyebrow) {
    adminRoleEyebrow.textContent =
      primaryStaffRole() === "partner_director" ? "Директор" : "Админ";
  }
  qsa(".admin-tab").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.adminTab === state.adminTab);
  });

  if (state.adminTab === "students") {
    renderStudentRegistry();
    return;
  }

  if (state.adminTab === "history") {
    renderAdminHistory();
    return;
  }

  if (state.adminTab === "summary") {
    const summary = state.opsSummary || buildLocalOpsSummary();
    const statuses = summary.order_statuses || [];
    const openOrders = summary.recent_open_orders || [];
    const lowStock = summary.low_stock || [];
    const warehouseCount = Number(summary.warehouses || 0);
    const activeProductCount = Number(summary.active_products || 0);
    const totalStockQuantity = Number(summary.total_stock_quantity || 0);
    const statusOrderCount = statuses.reduce(
      (total, item) => total + Number(item.count || 0),
      0,
    );
    const hasOperationalRows = Boolean(statuses.length || openOrders.length || lowStock.length);
    const needsInitialSetup = warehouseCount === 0 || activeProductCount === 0;
    const setupTarget = activeProductCount === 0 ? "products" : "warehouses";
    const setupAction = activeProductCount === 0 ? "Добавить товары" : "Настроить склад";
    qs("#adminPanel").innerHTML = `
      <div class="ops-quick-actions">
        <strong>Быстрые действия</strong>
        <div class="ops-quick-action-list">
          <button class="primary-action" type="button" data-ops-jump="orders">
            <i data-lucide="package-check"></i>
            <span>Заказы к выдаче</span>
          </button>
          <button class="secondary-action" type="button" data-ops-jump="inventory">
            <i data-lucide="boxes"></i>
            <span>Остатки</span>
          </button>
          <button class="secondary-action" type="button" data-ops-jump="products">
            <i data-lucide="package-plus"></i>
            <span>Товары</span>
          </button>
        </div>
      </div>
      <div class="ops-summary-grid">
        <button class="ops-metric ops-metric-orders" type="button" data-ops-jump="orders">
          <span class="ops-metric-icon"><i data-lucide="shopping-bag"></i></span>
          <span class="ops-metric-copy">
            <strong class="ops-metric-value">${Number(summary.open_orders || 0)}</strong>
            <small>Заказы в работе</small>
          </span>
        </button>
        <button class="ops-metric ops-metric-issue" type="button" data-ops-jump="orders" data-order-filter="open">
          <span class="ops-metric-icon"><i data-lucide="hand-platter"></i></span>
          <span class="ops-metric-copy">
            <strong class="ops-metric-value">${Number(summary.pending_issue_orders || 0)}</strong>
            <small>Ожидают выдачи</small>
          </span>
        </button>
        <button class="ops-metric ops-metric-products" type="button" data-ops-jump="products">
          <span class="ops-metric-icon"><i data-lucide="package-open"></i></span>
          <span class="ops-metric-copy">
            <strong class="ops-metric-value">${activeProductCount}</strong>
            <small>Активные товары</small>
          </span>
        </button>
        <button class="ops-metric ops-metric-reserved" type="button" data-ops-jump="inventory">
          <span class="ops-metric-icon"><i data-lucide="archive"></i></span>
          <span class="ops-metric-copy">
            <strong class="ops-metric-value">${Number(summary.total_reserved_quantity || 0)}</strong>
            <small>Товаров в резерве</small>
          </span>
        </button>
      </div>
      <div class="ops-summary-meta">
        <span><i data-lucide="warehouse"></i>${warehouseCountLabel(warehouseCount)}</span>
        <span><i data-lucide="package"></i>${totalStockQuantity} шт. на складах</span>
      </div>
      ${
        hasOperationalRows
          ? `
            <div class="ops-summary-columns">
              <section>
                <div class="ops-column-head">
                  <h3>Статусы заказов</h3>
                  <span>${statusOrderCount}</span>
                </div>
                ${
                  statuses.length
                    ? statuses
                        .map(
                          (item) => `
                            <button class="ops-row ops-row-action" type="button" data-order-status="${escapeHtml(item.status)}" data-view-jump="orders">
                              <span>${escapeHtml(orderStatusLabel(item.status))}</span>
                              <strong>${Number(item.count || 0)}</strong>
                            </button>
                          `,
                        )
                        .join("")
                    : '<div class="empty-state">Заказов пока нет</div>'
                }
              </section>
              <section>
                <div class="ops-column-head">
                  <h3>Ближайшие к выдаче</h3>
                  <span>${openOrders.length}</span>
                </div>
                ${
                  openOrders.length
                    ? openOrders
                        .slice(0, 6)
                        .map(
                          (order) => `
                            <button
                              class="ops-row ops-row-action"
                              type="button"
                              data-open-order="${escapeHtml(order.id || order.order_number || "")}"
                            >
                              <span>#${escapeHtml(order.order_number || order.id || "")} ${escapeHtml(
                                order.student_name || "ученик",
                              )}</span>
                              <strong>${escapeHtml(orderStatusLabel(order.status))}</strong>
                            </button>
                          `,
                        )
                        .join("")
                    : '<div class="empty-state">Открытых заказов нет</div>'
                }
              </section>
              <section>
                <div class="ops-column-head">
                  <h3>Низкие остатки</h3>
                  <span>${lowStock.length}</span>
                </div>
                ${
                  lowStock.length
                    ? lowStock
                        .slice(0, 8)
                        .map(
                          (item) => `
                            <button class="ops-row ops-row-action" type="button" data-ops-jump="inventory" data-inventory-low-stock>
                              <span>${escapeHtml(
                                item.product_name || item.sku || "товар",
                              )} / ${escapeHtml(item.warehouse_name || "склад")}</span>
                              <strong>${Number(item.available_quantity || 0)} шт.</strong>
                            </button>
                          `,
                        )
                        .join("")
                    : '<div class="empty-state">Низких остатков нет</div>'
                }
              </section>
            </div>
          `
          : `
            <div class="ops-empty-overview">
              <span class="ops-empty-icon">
                <i data-lucide="${needsInitialSetup ? "package-plus" : "clipboard-check"}"></i>
              </span>
              <div>
                <h3>${needsInitialSetup ? "Подготовьте каталог к работе" : "Нет задач, требующих внимания"}</h3>
                <p>${
                  needsInitialSetup
                    ? "Добавьте товары и настройте склад. После первых заказов здесь появятся выдача, резервы и контроль остатков."
                    : "Новые заказы и позиции с низким остатком появятся в этом разделе."
                }</p>
              </div>
              ${
                needsInitialSetup
                  ? `<button class="secondary-action" type="button" data-ops-jump="${setupTarget}">
                      <span>${setupAction}</span>
                      <i data-lucide="arrow-right"></i>
                    </button>`
                  : ""
              }
            </div>
          `
      }
    `;
    refreshIcons();
    return;
  }

  if (state.adminTab === "products") {
    const importingDisabled = state.productImporting ? "disabled" : "";
    const savingDisabled = state.productSaving ? "disabled" : "";
    const editing = products.find((product) => product.id === state.editingProductId);
    const editorOpen = state.productEditorOpen || Boolean(editing);
    const photoPreviewUrl = state.productPhotoPreviewUrl || (state.productPhotoRemoved ? "" : editing?.photoUrl || "");
    const productQuery = state.adminEntitySearch.trim().toLowerCase();
    const productCategories = Array.from(new Set(products.map((product) => product.category).filter(Boolean))).sort((left, right) => left.localeCompare(right, "ru"));
    const visibleProducts = products.filter((product) => {
      const matchesQuery = !productQuery || productSearchText(product).includes(productQuery);
      const matchesStatus = state.productStatusFilter === "all" || (product.status || "active") === state.productStatusFilter;
      const matchesCategory = state.productCategoryFilter === "all" || product.category === state.productCategoryFilter;
      return matchesQuery && matchesStatus && matchesCategory;
    });
    qs("#adminPanel").innerHTML = `
      <div class="admin-section-toolbar">
        <div>
          <h3>Каталог товаров</h3>
          <span>${activeProducts().length} активных из ${products.length}</span>
        </div>
        ${
          editorOpen
            ? ""
            : '<button id="productCreateButton" class="primary-action" type="button">Добавить товар</button>'
        }
      </div>
      ${editorOpen ? "" : `<div class="admin-filter-toolbar">
        <label class="search-field"><i data-lucide="search"></i><input id="adminEntitySearch" type="search" value="${escapeHtml(state.adminEntitySearch)}" placeholder="Название, SKU или категория" /><button class="search-clear" type="button" data-clear-admin-search ${state.adminEntitySearch ? "" : "hidden"}><i data-lucide="x"></i></button></label>
        <select id="productStatusFilter" aria-label="Статус товара">
          <option value="all">Все статусы</option>
          <option value="active" ${state.productStatusFilter === "active" ? "selected" : ""}>Активные</option>
          <option value="hidden" ${state.productStatusFilter === "hidden" ? "selected" : ""}>Скрытые</option>
          <option value="archived" ${state.productStatusFilter === "archived" ? "selected" : ""}>В архиве</option>
        </select>
        <select id="productCategoryFilter" aria-label="Категория товара">
          <option value="all">Все категории</option>
          ${productCategories.map((category) => `<option value="${escapeHtml(category)}" ${state.productCategoryFilter === category ? "selected" : ""}>${escapeHtml(category)}</option>`).join("")}
        </select>
        <span>${visibleProducts.length} из ${products.length}</span>
      </div>`}
      ${editorOpen ? `
      <div class="product-editor admin-editor">
        <div class="product-editor-heading">
          <div>
            <h3>${editing ? "Редактирование товара" : "Новый товар"}</h3>
            <span>${editing ? escapeHtml(editing.sku) : "Заполните карточку целиком"}</span>
          </div>
          <button
            id="productCancelEditButton"
            class="icon-button"
            type="button"
            title="Закрыть редактор"
            aria-label="Закрыть редактор"
            ${savingDisabled}
          ><i data-lucide="x"></i></button>
        </div>

        <div class="product-editor-main">
          <div class="product-photo-field">
            <span>Фото товара</span>
            <label class="product-photo-picker ${photoPreviewUrl ? "has-preview" : ""}">
              <input
                id="productPhotoFile"
                type="file"
                accept="image/jpeg,image/png,image/webp"
                ${savingDisabled}
              />
              ${
                photoPreviewUrl
                  ? `<img src="${escapeHtml(photoPreviewUrl)}" alt="Фото товара" />`
                  : `<span class="product-photo-placeholder">
                      <i data-lucide="image-plus"></i>
                      <strong>Добавить фото</strong>
                      <small>JPEG, PNG или WebP до 10 МБ</small>
                    </span>`
              }
              <span class="product-photo-action">
                <i data-lucide="camera"></i>
                ${photoPreviewUrl ? "Заменить фото" : "Выбрать фото"}
              </span>
            </label>
            ${
              state.productPhotoFileName
                ? `<small class="product-photo-name">${escapeHtml(
                    state.productPhotoFileName,
                  )}</small>`
                : ""
            }
            ${photoPreviewUrl ? `<div class="product-photo-tools">
              <button type="button" class="secondary-action" data-crop-product-photo><i data-lucide="crop"></i><span>Кадрировать</span></button>
              <button type="button" class="secondary-action danger-action" data-remove-product-photo><i data-lucide="trash-2"></i><span>Удалить</span></button>
            </div>` : ""}
          </div>

          <div class="product-form-grid">
            <label>
              <span>SKU</span>
              <input id="productSku" value="${escapeHtml(editing?.sku || "")}" placeholder="PEN-LOGO" />
            </label>
            <label>
              <span>Статус</span>
              <select id="productStatus">
                ${["active", "hidden", "archived"]
                  .map(
                    (status) => `<option value="${status}" ${
                      (editing?.status || "active") === status ? "selected" : ""
                    }>${escapeHtml(productStatusLabel(status))}</option>`,
                  )
                  .join("")}
              </select>
            </label>
            <label class="product-field-wide">
              <span>Способ выдачи</span>
              <select id="productFulfillmentType">
                <option value="warehouse" ${(editing?.fulfillmentType || "warehouse") === "warehouse" ? "selected" : ""}>Со склада</option>
                <option value="digital_code" ${editing?.fulfillmentType === "digital_code" ? "selected" : ""}>Код сразу после покупки</option>
              </select>
            </label>
            <label class="product-field-wide">
              <span>Название</span>
              <input id="productName" value="${escapeHtml(editing?.name || "")}" placeholder="Название товара" />
            </label>
            <label>
              <span>Категория</span>
              <input id="productCategory" value="${escapeHtml(editing?.category || "Без категории")}" />
            </label>
            <label>
              <span>Цена, AC</span>
              <input id="productPrice" type="number" min="0" value="${editing?.price ?? 0}" />
            </label>
            <label class="product-field-wide">
              <span>Описание</span>
              <textarea id="productDescription" rows="4" placeholder="Краткое описание товара">${escapeHtml(
                editing?.description || "",
              )}</textarea>
            </label>
            <div class="product-field-wide product-code-editor" ${editing?.fulfillmentType === "digital_code" ? "" : "hidden"}>
              <div class="product-code-editor-head">
                <div>
                  <strong>Коды для автовыдачи</strong>
                  <span>По одному коду в строке. Уже сохраненные коды не заменяются.</span>
                </div>
                <span>${Number(editing?.stock || 0)} доступно · ${Number(editing?.issuedCodeCount || 0)} выдано</span>
              </div>
              <textarea id="productNewCodes" rows="6" placeholder="ROBLOX-XXXX-XXXX&#10;ROBLOX-YYYY-YYYY"></textarea>
              ${
                Array.isArray(editing?.codes) && editing.codes.length
                  ? `<details class="product-code-history"><summary>История кодов (${editing.codes.length})</summary><div>${editing.codes
                      .map(
                        (code) => `<div><code>${escapeHtml(code.code)}</code><span class="status-badge ${code.status === "available" ? "ok" : code.status === "issued" ? "info" : "danger"}">${code.status === "available" ? "Доступен" : code.status === "issued" ? "Выдан" : "Отключен"}</span>${code.student_name ? `<small>${escapeHtml(code.student_name)}</small>` : ""}${code.order_number ? `<small>Заказ №${Number(code.order_number)}</small>` : ""}${code.issued_at ? `<small>${escapeHtml(new Date(code.issued_at).toLocaleString("ru-RU"))}</small>` : ""}</div>`,
                      )
                      .join("")}</div></details>`
                  : ""
              }
            </div>
          </div>
        </div>

        <div class="product-editor-actions">
          <button id="productSaveButton" class="primary-action" type="button" ${savingDisabled}>
            <i data-lucide="save"></i>
            ${state.productSaving ? "Сохранение..." : "Сохранить товар"}
          </button>
          <button id="productCancelEditButtonBottom" class="secondary-action" type="button" ${savingDisabled}>
            Отмена
          </button>
        </div>
      </div>
      ` : ""}
      <details class="product-import-panel" ${state.productImportFileName ? "open" : ""}>
        <summary>
          <span class="product-import-icon"><i data-lucide="file-spreadsheet"></i></span>
          <span>
            <strong>Массовый импорт</strong>
            <small>Загрузка каталога из CSV или XLSX</small>
          </span>
          <i class="product-import-chevron" data-lucide="chevron-down"></i>
        </summary>
        <div class="product-import-controls">
          <label class="file-picker">
            <input id="productImportFile" type="file" accept=".xlsx,.csv,text/csv" />
            <span>${escapeHtml(state.productImportFileName || "Выбрать CSV или XLSX")}</span>
          </label>
          <button id="productImportButton" class="primary-action" type="button" ${importingDisabled}>
            ${state.productImporting ? "Импорт..." : "Импортировать"}
          </button>
        </div>
      </details>
      <div class="admin-card-list">
      ${
        products.length === 0
          ? '<div class="empty-state compact-empty"><i data-lucide="package-plus"></i><strong>Товаров пока нет</strong><span>Добавьте первый товар целиком: фото, название, цену и описание.</span></div>'
          : visibleProducts.length === 0
            ? '<div class="empty-state compact-empty"><strong>Товары не найдены</strong><button class="secondary-action" type="button" data-clear-admin-search>Сбросить фильтры</button></div>'
          : visibleProducts
              .map(
                (product) => `
            <article class="admin-entity-card">
              <div class="admin-product-thumb">
                <span>${escapeHtml(product.mark)}</span>
                ${
                  product.photoUrl
                    ? `<img src="${escapeHtml(product.photoUrl)}" alt="" loading="lazy" />`
                    : ""
                }
              </div>
              <div class="admin-entity-main">
                <div class="admin-entity-title">
                  <strong>${escapeHtml(product.name)}</strong>
                  <span class="status-badge ${
                    (product.status || "active") === "active"
                      ? "ok"
                      : (product.status || "active") === "hidden"
                        ? "warn"
                        : "danger"
                  }">${escapeHtml(productStatusLabel(product.status))}</span>
                </div>
                <div class="admin-entity-meta">
                  ${product.sku ? `<span>${escapeHtml(product.sku)}</span>` : ""}
                  <span>${escapeHtml(product.category)}</span>
                  <span>${product.fulfillmentType === "digital_code" ? `${product.stock} кодов доступно` : `${product.stock} шт.`}</span>
                  <span>${escapeHtml(product.warehouse)}</span>
                </div>
              </div>
              <div class="admin-entity-actions">
                <strong>${product.price} AC</strong>
                <button class="icon-button product-status-toggle" type="button" data-toggle-product-status="${escapeHtml(product.id)}" title="${(product.status || "active") === "active" ? "Скрыть товар" : "Опубликовать товар"}" aria-label="${(product.status || "active") === "active" ? "Скрыть товар" : "Опубликовать товар"}"><i data-lucide="${(product.status || "active") === "active" ? "eye-off" : "eye"}"></i></button>
                <button class="secondary-action" type="button" data-edit-product="${escapeHtml(
                  product.id,
                )}">Редактировать</button>
              </div>
            </article>
          `,
              )
              .join("")
      }
      </div>
    `;
    refreshIcons();
    return;
  }

  if (state.adminTab === "crm") {
    const preview = state.crmImportPreview;
    const busy = state.crmImporting ? "disabled" : "";
    const importStep = preview ? 3 : state.crmImportFile ? 2 : 1;
    qs("#adminPanel").innerHTML = `
      <div class="admin-section-toolbar">
        <div>
          <h3>Данные CRM</h3>
          <span>${escapeHtml(apiContext.tenantSlug || "Текущий филиал")}</span>
        </div>
        <a
          class="secondary-action"
          href="/miniapp/import-template.xlsx"
          download="algo-max-students-import-template.xlsx"
        ><i data-lucide="file-down"></i> Скачать шаблон</a>
      </div>
      <div class="import-stepper" aria-label="Этапы импорта">
        <span class="${importStep >= 1 ? "is-complete" : ""}"><b>1</b> Файл</span>
        <span class="${importStep >= 2 ? "is-complete" : ""}"><b>2</b> Проверка</span>
        <span class="${importStep >= 3 ? "is-complete" : ""}"><b>3</b> Подтверждение</span>
      </div>
      <div class="import-panel crm-import-panel">
        <div>
          <h3>Ученики и группы</h3>
        </div>
        <label>
          <span>Состав выгрузки</span>
          <select id="crmStudentStatus" ${busy}>
            <option value="active" ${state.crmStudentStatus === "active" ? "selected" : ""}>Активные ученики</option>
            <option value="departed" ${state.crmStudentStatus === "departed" ? "selected" : ""}>Выбывшие ученики</option>
          </select>
        </label>
        <label class="file-picker">
          <input id="crmImportFile" type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" />
          <span>${escapeHtml(state.crmImportFileName || "Выбрать XLSX")}</span>
        </label>
        <button id="crmPreviewButton" class="secondary-action" type="button" ${busy}>
          ${state.crmImporting ? "Обработка..." : "Проверить файл"}
        </button>
      </div>
      ${state.crmImportFile ? `<div class="import-mapping-note"><i data-lucide="table-properties"></i><div><strong>Читаем только лист «Шаблон»</strong><span>Дополнительные листы и колонки не попадут в импорт.</span></div></div>` : ""}
      ${
        preview
          ? `
            <div class="crm-import-result">
              <div class="ops-summary-grid crm-summary-grid">
                <article><span>${Number(preview.parsed_rows || 0)}</span><strong>Строк</strong></article>
                <article><span>${Number(preview.distinct_groups || 0)}</span><strong>Групп</strong></article>
                <article><span>${Number(preview.distinct_courses || 0)}</span><strong>Курсов</strong></article>
                <article><span>${Number(preview.distinct_teachers || 0)}</span><strong>Преподавателей</strong></article>
                <article><span>${Number(preview.rows_with_contacts || 0)}</span><strong>С Contact ID</strong></article>
                <article><span>${Number(preview.rows_without_group || 0)}</span><strong>Без группы</strong></article>
              </div>
              <div class="crm-import-actions">
                <div>
                  <strong>${escapeHtml(preview.filename || state.crmImportFileName)}</strong>
                  <span>${
                    preview.student_status === "departed"
                      ? "Статус: выбывшие"
                      : "Статус: активные"
                  } · без имени: ${Number(preview.rows_without_student_name || 0)}</span>
                </div>
                <button id="crmImportButton" class="primary-action" type="button" ${busy}>
                  ${state.crmImporting ? "Импорт..." : `Импортировать ${Number(preview.parsed_rows || 0)} строк`}
                </button>
              </div>
            </div>
          `
          : ""
      }
    `;
    return;
  }

  if (state.adminTab === "warehouses") {
    const editing = catalogWarehouses.find((item) => item.id === state.editingWarehouseId);
    const editorOpen = state.warehouseEditorOpen || Boolean(editing);
    const disabled = state.warehouseSaving ? "disabled" : "";
    const rows = allCatalogWarehouses()
      .map(
        (warehouse) => `
          <article class="admin-entity-card warehouse-entity-card">
            <div class="warehouse-name-mark">${escapeHtml(
              String(warehouse.name || "С").slice(0, 1).toUpperCase(),
            )}</div>
            <div class="admin-entity-main">
              <div class="admin-entity-title">
                <strong>${escapeHtml(warehouse.name)}</strong>
              </div>
              <div class="admin-entity-meta">
                <span>${escapeHtml(warehouse.address || "Адрес или примечание не указаны")}</span>
              </div>
            </div>
            <div class="admin-entity-actions">
              <button class="secondary-action" type="button" data-edit-warehouse="${escapeHtml(
                warehouse.id,
              )}">Редактировать</button>
            </div>
          </article>
        `,
      )
      .join("");

    qs("#adminPanel").innerHTML = `
      <div class="admin-section-toolbar">
        <div>
          <h3>Склады</h3>
          <span>${allCatalogWarehouses().length} складов у выбранного партнера</span>
        </div>
        ${
          editorOpen
            ? ""
            : '<button id="warehouseCreateButton" class="primary-action" type="button">Добавить склад</button>'
        }
      </div>
      ${editorOpen ? `
      <div class="warehouse-form admin-editor">
        <label>
          <span>Название</span>
          <input id="warehouseName" value="${escapeHtml(editing?.name || "")}" placeholder="Например, Центральный склад" />
        </label>
        <label>
          <span>Адрес или примечание</span>
          <input id="warehouseAddress" value="${escapeHtml(editing?.address || "")}" placeholder="Например, ул. Большая Покровская, 10" />
        </label>
        <button id="warehouseSaveButton" class="primary-action" type="button" ${disabled}>
          ${state.warehouseSaving ? "Сохранение..." : editing ? "Сохранить" : "Создать"}
        </button>
        ${
          editing
            ? '<button id="warehouseCancelEditButton" class="secondary-action" type="button">Отмена</button>'
            : ""
        }
      </div>
      ` : ""}
      <div class="warehouse-preference">
        <div>
          <strong>Мой основной склад</strong>
          <span>Будет выбран заранее в новых зарезервированных заказах.</span>
        </div>
        <select id="defaultWarehouseSelect">
          <option value="">Выберите склад</option>
          ${allCatalogWarehouses()
            .map(
              (warehouse) => `<option value="${escapeHtml(warehouse.id)}" ${
                warehouse.id === state.defaultWarehouseId ? "selected" : ""
              }>${escapeHtml(warehouse.name)}</option>`,
            )
            .join("")}
        </select>
        <button
          id="saveWarehousePreferenceButton"
          class="secondary-action"
          type="button"
          ${state.warehousePreferenceSaving ? "disabled" : ""}
        >${state.warehousePreferenceSaving ? "Сохранение..." : "Сохранить"}</button>
      </div>
      <div class="admin-card-list">
        ${rows || '<div class="empty-state">Складов пока нет</div>'}
      </div>
    `;
    return;
  }

  if (state.adminTab === "inventory") {
    const allWarehouses = allCatalogWarehouses();
    const inventoryQuery = state.adminEntitySearch.trim().toLowerCase();
    const inventoryItems = products.flatMap((product) =>
      productWarehouses(product).map((warehouse) => ({ product, warehouse })),
    ).filter(({ product, warehouse }) => {
      const matchesQuery = !inventoryQuery || `${product.name} ${product.sku || ""} ${warehouse.name}`.toLowerCase().includes(inventoryQuery);
      const matchesWarehouse = state.inventoryWarehouseFilter === "all" || warehouse.id === state.inventoryWarehouseFilter;
      const matchesStock = state.inventoryStockFilter === "all"
        || (state.inventoryStockFilter === "low" && warehouse.available > 0 && warehouse.available <= 5)
        || (state.inventoryStockFilter === "empty" && warehouse.available <= 0)
        || (state.inventoryStockFilter === "available" && warehouse.available > 5);
      return matchesQuery && matchesWarehouse && matchesStock;
    }).sort((left, right) => left.warehouse.available - right.warehouse.available);
    const rows = inventoryItems.map(({ product, warehouse }) => {
        const key = `${product.id}::${warehouse.id}`;
        const saving = state.inventorySavingKey === key;
        const targetOptions = allWarehouses
          .filter((item) => item.id !== warehouse.id)
          .map(
            (item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name)}</option>`,
          )
          .join("");
        return `
          <div class="inventory-row">
            <div class="inventory-item-heading">
              <strong>${escapeHtml(product.name)}</strong>
              <span>${escapeHtml(warehouse.name)}</span>
              <div class="inventory-badges">
                <span>${warehouse.stock} факт</span>
                <span>${warehouse.reserved} резерв</span>
                <span>${warehouse.available} свободно</span>
              </div>
            </div>
            <div class="inventory-action-group">
              <label>
                <span>Фактический остаток</span>
                <input
                  data-inventory-quantity="${escapeHtml(key)}"
                  inputmode="numeric"
                  min="${warehouse.reserved}"
                  type="number"
                  value="${warehouse.stock}"
                />
              </label>
              <button
                class="secondary-action"
                type="button"
                data-adjust-inventory="${escapeHtml(key)}"
                ${saving ? "disabled" : ""}
              >${saving ? "Сохранение..." : "Обновить"}</button>
            </div>
            <div class="inventory-action-group inventory-transfer-group">
              <label>
                <span>Перенести на склад</span>
                <select data-transfer-target="${escapeHtml(key)}">${targetOptions}</select>
              </label>
              <label class="inventory-quantity-field">
                <span>Количество</span>
                <input
                  data-transfer-quantity="${escapeHtml(key)}"
                  inputmode="numeric"
                  min="1"
                  max="${warehouse.available}"
                  type="number"
                  value="${warehouse.available > 0 ? 1 : 0}"
                />
              </label>
              <button
                class="secondary-action"
                type="button"
                data-transfer-inventory="${escapeHtml(key)}"
                ${saving || warehouse.available <= 0 || !targetOptions ? "disabled" : ""}
              >Перенести</button>
            </div>
          </div>
        `;
      });

    qs("#adminPanel").innerHTML = `
      <div class="admin-section-toolbar">
        <div><h3>Остатки по складам</h3><span>${inventoryItems.length} позиций</span></div>
      </div>
      <div class="admin-filter-toolbar inventory-filter-toolbar">
        <label class="search-field"><i data-lucide="search"></i><input id="adminEntitySearch" type="search" value="${escapeHtml(state.adminEntitySearch)}" placeholder="Товар, SKU или склад" /><button class="search-clear" type="button" data-clear-admin-search ${state.adminEntitySearch ? "" : "hidden"}><i data-lucide="x"></i></button></label>
        <select id="inventoryWarehouseFilter" aria-label="Склад"><option value="all">Все склады</option>${allWarehouses.map((warehouse) => `<option value="${escapeHtml(warehouse.id)}" ${state.inventoryWarehouseFilter === warehouse.id ? "selected" : ""}>${escapeHtml(warehouse.name)}</option>`).join("")}</select>
        <select id="inventoryStockFilter" aria-label="Остаток">
          <option value="all">Любой остаток</option>
          <option value="low" ${state.inventoryStockFilter === "low" ? "selected" : ""}>Мало товара</option>
          <option value="empty" ${state.inventoryStockFilter === "empty" ? "selected" : ""}>Нет в наличии</option>
          <option value="available" ${state.inventoryStockFilter === "available" ? "selected" : ""}>В наличии</option>
        </select>
      </div>
      <div class="inventory-list">
        ${rows.join("") || '<div class="empty-state compact-empty"><strong>Позиции не найдены</strong><button class="secondary-action" type="button" data-clear-inventory-filters>Сбросить фильтры</button></div>'}
      </div>
    `;
    refreshIcons();
    return;
  }

  if (state.adminTab === "contacts") {
    const activeLinks = accessLinks.filter((link) => link.status === "active").length;
    const accessQuery = state.adminEntitySearch.trim().toLowerCase();
    const visibleLinks = accessLinks.filter((link) => {
      const matchesQuery = !accessQuery || `${link.studentName} ${link.group} ${link.maxUserId} ${link.displayName} ${link.username}`.toLowerCase().includes(accessQuery);
      const matchesStatus = state.accessStatusFilter === "all" || link.status === state.accessStatusFilter;
      const matchesRole = state.accessRoleFilter === "all" || link.role === state.accessRoleFilter;
      return matchesQuery && matchesStatus && matchesRole;
    });
    const rows = visibleLinks
      .map(
        (link) => `
          <article class="admin-entity-card access-entity-card">
            <div class="access-role-mark">${escapeHtml(
              accessRoleLabel(link.role).slice(0, 1),
            )}</div>
            <div class="admin-entity-main">
              <div class="admin-entity-title">
                <strong>${escapeHtml(link.studentName)}</strong>
                <span class="status-badge ${link.status === "active" ? "ok" : "danger"}">
                  ${link.status === "active" ? "Активна" : "Отозвана"}
                </span>
              </div>
              <div class="admin-entity-meta">
                <span>${escapeHtml(accessRoleLabel(link.role))}</span>
                <span>${escapeHtml(link.group)}</span>
                <span>MAX ID ${escapeHtml(link.maxUserId)}</span>
                ${
                  (link.displayName && link.displayName !== accessRoleLabel(link.role)) ||
                  link.username
                    ? `<span>${escapeHtml(
                        link.displayName && link.displayName !== accessRoleLabel(link.role)
                          ? link.displayName
                          : `@${link.username}`,
                      )}</span>`
                    : ""
                }
              </div>
            </div>
            <div class="admin-entity-actions">
              <details class="admin-row-menu">
                <summary class="icon-button" title="Действия" aria-label="Действия со связью"><i data-lucide="ellipsis-vertical"></i></summary>
                <div class="admin-row-menu-popover">
                  <button
                    class="${link.status === "active" ? "danger-action" : ""}"
                    type="button"
                    data-toggle-contact="${escapeHtml(link.id)}"
                  >${link.status === "revoked" ? "Восстановить связь" : "Отозвать связь"}</button>
                </div>
              </details>
            </div>
          </article>
        `,
      )
      .join("");

    qs("#adminPanel").innerHTML = `
      <div class="admin-section-toolbar">
        <div>
          <h3>Связи доступа</h3>
          <span>${activeLinks} активных из ${accessLinks.length}</span>
        </div>
      </div>
      <div class="admin-filter-toolbar">
        <label class="search-field"><i data-lucide="search"></i><input id="adminEntitySearch" type="search" value="${escapeHtml(state.adminEntitySearch)}" placeholder="Ученик, группа или MAX ID" /><button class="search-clear" type="button" data-clear-admin-search ${state.adminEntitySearch ? "" : "hidden"}><i data-lucide="x"></i></button></label>
        <select id="accessStatusFilter" aria-label="Статус связи"><option value="all">Все статусы</option><option value="active" ${state.accessStatusFilter === "active" ? "selected" : ""}>Активные</option><option value="revoked" ${state.accessStatusFilter === "revoked" ? "selected" : ""}>Отозванные</option></select>
        <select id="accessRoleFilter" aria-label="Роль связи"><option value="all">Все роли</option><option value="parent" ${state.accessRoleFilter === "parent" ? "selected" : ""}>Родители</option><option value="student" ${state.accessRoleFilter === "student" ? "selected" : ""}>Ученики</option></select>
      </div>
      <div class="admin-card-list">
        ${rows || '<div class="empty-state compact-empty"><strong>Связи не найдены</strong><button class="secondary-action" type="button" data-clear-admin-search>Сбросить фильтры</button></div>'}
      </div>
    `;
    refreshIcons();
    return;
  }

  const disabled = state.staffSaving ? "disabled" : "";
  const activeStaff = staffAssignments.filter((item) => item.status === "active").length;
  const revokedStaff = staffAssignments.length - activeStaff;
  const staffQuery = state.adminEntitySearch.trim().toLowerCase();
  const visibleStaffAssignments = staffAssignments.filter((item) => {
    const matchesStatus = state.staffStatusFilter === "all" || item.status === state.staffStatusFilter;
    const matchesRole = state.staffRoleFilter === "all" || item.role === state.staffRoleFilter;
    const matchesQuery = !staffQuery || `${item.displayName} ${item.username} ${item.maxUserId} ${staffRoleLabel(item.role)}`.toLowerCase().includes(staffQuery);
    return matchesStatus && matchesRole && matchesQuery;
  });
  const canManageStaffNotifications = ["superadmin", "partner_director"].includes(
    primaryStaffRole(),
  );
  const rows =
    visibleStaffAssignments.length === 0
      ? `<div class="empty-state">${
          staffAssignments.length === 0
            ? "Сотрудников пока нет"
            : state.staffStatusFilter === "revoked"
              ? "Отозванных назначений нет"
              : "Активных назначений нет"
        }</div>`
      : visibleStaffAssignments
          .map(
            (assignment) => `
              <article class="admin-entity-card staff-entity-card">
                <div class="staff-role-mark">${escapeHtml(
                  staffRoleLabel(assignment.role).slice(0, 1),
                )}</div>
                <div class="admin-entity-main">
                  <div class="admin-entity-title">
                    <strong>${escapeHtml(
                      assignment.displayName || assignment.username || "Без имени",
                    )}</strong>
                    <span class="status-badge ${
                      assignment.status === "active" ? "ok" : "danger"
                    }">${escapeHtml(assignmentStatusLabel(assignment.status))}</span>
                  </div>
                  <div class="admin-entity-meta">
                    <span>${escapeHtml(staffRoleLabel(assignment.role))}</span>
                    <span>MAX ID ${escapeHtml(assignment.maxUserId)}</span>
                    ${assignment.username ? `<span>@${escapeHtml(assignment.username)}</span>` : ""}
                  </div>
                </div>
                <div class="admin-entity-actions">
                  ${
                    canManageStaffNotifications
                    && assignment.status === "active"
                    && ["admin", "curator"].includes(assignment.role)
                      ? `<button
                          class="secondary-action staff-notification-button"
                          type="button"
                          data-staff-notifications="${escapeHtml(assignment.accountId)}"
                        ><i data-lucide="bell-ring"></i><span>Уведомления</span></button>`
                      : ""
                  }
                  ${
                    assignment.role !== "superadmin" &&
                    (primaryStaffRole() === "superadmin" ||
                      ["teacher", "curator"].includes(assignment.role))
                      ? `<details class="admin-row-menu">
                          <summary class="icon-button" title="Действия" aria-label="Действия с сотрудником"><i data-lucide="ellipsis-vertical"></i></summary>
                          <div class="admin-row-menu-popover">
                            <button
                              class="${assignment.status === "active" ? "danger-action" : ""}"
                              type="button"
                              data-toggle-staff="${escapeHtml(assignment.maxUserId)}"
                              data-staff-role="${escapeHtml(assignment.role)}"
                            >${assignment.status === "revoked" ? "Восстановить роль" : "Отозвать роль"}</button>
                          </div>
                        </details>`
                      : ""
                  }
                </div>
              </article>
            `,
          )
          .join("");

  const elevatedRoleOptions = primaryStaffRole() === "superadmin"
    ? `
          <option value="admin">Администратор</option>
          <option value="partner_director">Директор партнера</option>
        `
    : "";

  qs("#adminPanel").innerHTML = `
    <div class="admin-section-toolbar">
      <div>
        <h3>Сотрудники</h3>
        <span>${activeStaff} активных назначений из ${staffAssignments.length}</span>
      </div>
      ${
        state.staffEditorOpen
          ? ""
          : '<button id="staffCreateButton" class="primary-action" type="button">Выдать роль</button>'
      }
    </div>
    <div class="staff-status-filter" role="group" aria-label="Фильтр сотрудников">
      <button
        class="staff-filter-button ${state.staffStatusFilter === "active" ? "is-active" : ""}"
        type="button"
        data-staff-status-filter="active"
      >Активные <span>${activeStaff}</span></button>
      <button
        class="staff-filter-button ${state.staffStatusFilter === "revoked" ? "is-active" : ""}"
        type="button"
        data-staff-status-filter="revoked"
      >Отозванные <span>${revokedStaff}</span></button>
      <button
        class="staff-filter-button ${state.staffStatusFilter === "all" ? "is-active" : ""}"
        type="button"
        data-staff-status-filter="all"
      >Все <span>${staffAssignments.length}</span></button>
    </div>
    <div class="admin-filter-toolbar">
      <label class="search-field"><i data-lucide="search"></i><input id="adminEntitySearch" type="search" value="${escapeHtml(state.adminEntitySearch)}" placeholder="Имя, MAX ID или роль" /><button class="search-clear" type="button" data-clear-admin-search ${state.adminEntitySearch ? "" : "hidden"}><i data-lucide="x"></i></button></label>
      <select id="staffRoleFilter" aria-label="Роль сотрудника">
        <option value="all">Все роли</option>
        ${["teacher", "curator", "admin", "partner_director", "superadmin"].map((role) => `<option value="${role}" ${state.staffRoleFilter === role ? "selected" : ""}>${escapeHtml(staffRoleLabel(role))}</option>`).join("")}
      </select>
    </div>
    ${state.staffEditorOpen ? `
    <div class="staff-form admin-editor">
      <label>
        <span>MAX user_id</span>
        <input id="staffMaxUserId" inputmode="numeric" placeholder="53364725" />
      </label>
      <label>
        <span>Имя</span>
        <input id="staffDisplayName" placeholder="ФИО или ник" />
      </label>
      <label>
        <span>Роль</span>
        <select id="staffRoleSelect">
          <option value="teacher">Преподаватель</option>
          <option value="curator">Куратор</option>
          ${elevatedRoleOptions}
        </select>
      </label>
      <button id="staffSaveButton" class="primary-action" type="button" ${disabled}>
        ${state.staffSaving ? "Сохранение..." : "Выдать роль"}
      </button>
      <button id="staffCancelButton" class="secondary-action" type="button">Отмена</button>
    </div>
    ` : ""}
    <div class="admin-card-list">
      ${rows}
    </div>
  `;
}

const weekdayNames = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"];
