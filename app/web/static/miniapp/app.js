const apiContext = {
  maxUserId: queryParam("max_user_id"),
  tenantSlug: queryParam("tenant_slug") || "",
  demoMode: queryParam("demo") === "1",
};

const state = {
  role: "student",
  view: "dashboard",
  adminTab: "products",
  studentGroupFilter: "all",
  accrualGroup: "all",
  accrualNameFilter: "",
  balance: 1240,
  activeStudentId: "demo-alisa",
  cart: new Map(),
  favorites: new Set(["demo-pen"]),
  catalogLoaded: false,
  sessionLoaded: false,
  productImporting: false,
  productImportFile: null,
  productImportFileName: "",
};

let students = [
  {
    id: "demo-alisa",
    lmsId: "1841",
    name: "Алиса",
    group: "Союзный 45, вс 10:00",
    teacher: "Олейник Д",
    balance: 1240,
    contact: "681",
  },
  {
    id: "demo-ivan",
    lmsId: "2417",
    name: "Иван",
    group: "Гагарина 64, сб 18:00",
    teacher: "Мыленкова СН",
    balance: 860,
    contact: "681",
  },
  {
    id: "demo-mark",
    lmsId: "1930",
    name: "Марк",
    group: "Октября 13, пн 16:00",
    teacher: "Сучкина Е",
    balance: 1510,
    contact: "681",
  },
];

let products = [
  {
    id: "demo-game",
    name: "Игра Кибертаун",
    category: "Игры",
    price: 900,
    stock: 4,
    warehouse: "Общий склад",
    mark: "K",
    warehouses: [
      {
        warehouse_id: "demo-warehouse-common",
        warehouse_name: "Общий склад",
        available_quantity: 3,
      },
      {
        warehouse_id: "demo-warehouse-soyuznyy",
        warehouse_name: "Союзный 45",
        available_quantity: 1,
      },
    ],
  },
  {
    id: "demo-pen",
    name: "Ручка металл с лого",
    category: "Канцелярия",
    price: 120,
    stock: 18,
    warehouse: "Союзный 45",
    mark: "Р",
    warehouses: [
      {
        warehouse_id: "demo-warehouse-soyuznyy",
        warehouse_name: "Союзный 45",
        available_quantity: 12,
      },
      {
        warehouse_id: "demo-warehouse-common",
        warehouse_name: "Общий склад",
        available_quantity: 6,
      },
    ],
  },
  {
    id: "demo-bracelet",
    name: "Силиконовый браслет",
    category: "Браслеты",
    price: 160,
    stock: 2,
    warehouse: "Гагарина 64",
    mark: "Б",
    warehouses: [
      {
        warehouse_id: "demo-warehouse-gagarina",
        warehouse_name: "Гагарина 64",
        available_quantity: 2,
      },
    ],
  },
  {
    id: "demo-mug",
    name: "Кружка Python. Be the best",
    category: "Кружки",
    price: 520,
    stock: 0,
    warehouse: "Внешний склад",
    mark: "P",
    warehouses: [
      {
        warehouse_id: "demo-warehouse-external",
        warehouse_name: "Внешний склад",
        available_quantity: 0,
      },
    ],
  },
  {
    id: "demo-magnet",
    name: "Магнит Roblox",
    category: "Магниты",
    price: 90,
    stock: 24,
    warehouse: "Общий склад",
    mark: "M",
    warehouses: [
      {
        warehouse_id: "demo-warehouse-common",
        warehouse_name: "Общий склад",
        available_quantity: 24,
      },
    ],
  },
  {
    id: "demo-pad",
    name: "Коврик для мышки",
    category: "Аксессуары",
    price: 700,
    stock: 3,
    warehouse: "Партнерский склад",
    mark: "A",
    warehouses: [
      {
        warehouse_id: "demo-warehouse-partner",
        warehouse_name: "Партнерский склад",
        available_quantity: 3,
      },
    ],
  },
];

let orders = [
  {
    id: "1357",
    student: "Алиса",
    item: "Ручка металл с лого",
    warehouse: "Союзный 45",
    status: "Выдать ученику",
    tone: "ok",
  },
  {
    id: "1358",
    student: "Иван",
    item: "Кружка Python",
    warehouse: "Общий склад",
    status: "Передан педагогу",
    tone: "warn",
  },
  {
    id: "1359",
    student: "Марк",
    item: "Игра Кибертаун",
    warehouse: "Не выбран",
    status: "Проблема",
    tone: "danger",
  },
];

let ledger = [
  ["16.06", "Начисление за проект на уроке", "+120 AC"],
  ["14.06", "Покупка: ручка металл с лого", "-120 AC"],
  ["12.06", "Бонус за домашнее задание", "+80 AC"],
  ["10.06", "Корректировка администратора", "+40 AC"],
];

const warehouses = [
  ["Общий склад", "common", "Нижний Новгород", "148 позиций", "Активен"],
  ["Союзный 45", "venue", "Союзный 45", "32 позиции", "Активен"],
  ["Гагарина 64", "venue", "Гагарина 64", "21 позиция", "Активен"],
  ["Внешний склад", "external", "Поставщик", "9 позиций", "Проверить"],
];

const accrualReasons = [
  "Активность на уроке",
  "Домашнее задание",
  "Проект",
  "Помощь группе",
  "Бонус",
];

const accrualAmounts = [10, 20, 30, 50, 100];

function qs(selector) {
  return document.querySelector(selector);
}

function qsa(selector) {
  return Array.from(document.querySelectorAll(selector));
}

function queryParam(name) {
  return new URLSearchParams(window.location.search).get(name);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit" });
}

function todayShort() {
  return new Date().toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit" });
}

function selectedStudent() {
  return students.find((student) => student.id === state.activeStudentId) || students[0] || null;
}

function studentGroupName(student) {
  return student.group || "Группа не указана";
}

function sortedStudents() {
  return [...students].sort((left, right) => {
    const groupCompare = studentGroupName(left).localeCompare(studentGroupName(right), "ru");
    if (groupCompare !== 0) return groupCompare;
    return left.name.localeCompare(right.name, "ru");
  });
}

function studentGroups() {
  return [...new Set(sortedStudents().map(studentGroupName))];
}

function studentDisplayId(student, index = 0) {
  if (student.lmsId) return student.lmsId;
  const numeric = Number.parseInt(String(student.contact || "").replace(/\D/g, ""), 10);
  if (!Number.isNaN(numeric) && numeric > 0) return String(numeric);
  return String(1800 + index);
}

function studentsForGroup(groupName = state.studentGroupFilter) {
  const sorted = sortedStudents();
  if (!groupName || groupName === "all") return sorted;
  return sorted.filter((student) => studentGroupName(student) === groupName);
}

function productWarehouses(product) {
  if (Array.isArray(product.warehouses) && product.warehouses.length > 0) {
    return product.warehouses.map((warehouse) => ({
      id: String(warehouse.warehouse_id || warehouse.id || warehouse.warehouse_name),
      name: warehouse.warehouse_name || warehouse.name || "Склад",
      available: Number(warehouse.available_quantity || warehouse.available || 0),
    }));
  }

  return [
    {
      id: product.warehouse || "default",
      name: product.warehouse || "Склад будет выбран",
      available: Number(product.stock || 0),
    },
  ];
}

function warehouseCountLabel(count) {
  if (count === 1) return "1 склад";
  if (count >= 2 && count <= 4) return `${count} склада`;
  return `${count} складов`;
}

function selectedProductWarehouse(product, card) {
  const warehouses = productWarehouses(product);
  const selectedId = card?.querySelector("[data-warehouse-select]")?.value || warehouses[0]?.id;
  return warehouses.find((warehouse) => warehouse.id === selectedId) || warehouses[0] || null;
}

function cartKey(productId, warehouseId) {
  return `${productId}::${warehouseId || "auto"}`;
}

function cartQuantityFor(productId, warehouseId) {
  return state.cart.get(cartKey(productId, warehouseId))?.quantity || 0;
}

function productById(productId) {
  return products.find((product) => product.id === productId) || null;
}

function warehouseById(product, warehouseId) {
  return productWarehouses(product).find((warehouse) => warehouse.id === warehouseId) || null;
}

function clampQuantity(value, max) {
  const parsed = Number.parseInt(value, 10);
  if (Number.isNaN(parsed)) return 1;
  return Math.min(Math.max(parsed, 1), Math.max(max, 1));
}

function syncProductCardControls(card) {
  const productId = card?.dataset.productCard;
  const product = productById(productId);
  if (!product) return;

  const warehouse = selectedProductWarehouse(product, card);
  const input = card.querySelector("[data-quantity]");
  const button = card.querySelector("[data-add]");
  if (!warehouse || !input || !button) return;

  const availableLeft = Math.max(warehouse.available - cartQuantityFor(product.id, warehouse.id), 0);
  input.max = String(availableLeft);
  input.disabled = availableLeft <= 0;
  input.value = availableLeft <= 0 ? "0" : String(clampQuantity(input.value, availableLeft));
  button.disabled = availableLeft <= 0;
  button.textContent = availableLeft <= 0 ? "Недоступно" : "В корзину";
}

function apiUrl(path, params = {}) {
  const url = new URL(path, window.location.origin);
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, value);
    }
  });
  return url.toString();
}

async function parseApiError(response) {
  try {
    const data = await response.json();
    return data.detail || `Ошибка API: ${response.status}`;
  } catch {
    return `Ошибка API: ${response.status}`;
  }
}

function showNotice(message, tone = "ok") {
  const notice = qs("#noticeBar");
  notice.textContent = message;
  notice.hidden = false;
  notice.className = `notice-bar ${tone}`;
}

function normalizeHeader(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replaceAll("ё", "е")
    .replaceAll(" ", "_");
}

function splitSeparatedLine(line, separator) {
  const values = [];
  let current = "";
  let quoted = false;

  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];
    const next = line[index + 1];

    if (char === '"' && next === '"') {
      current += '"';
      index += 1;
      continue;
    }

    if (char === '"') {
      quoted = !quoted;
      continue;
    }

    if (char === separator && !quoted) {
      values.push(current.trim());
      current = "";
      continue;
    }

    current += char;
  }

  values.push(current.trim());
  return values;
}

function detectSeparator(headerLine) {
  const separators = [",", ";", "\t"];
  return separators
    .map((separator) => ({
      separator,
      count: splitSeparatedLine(headerLine, separator).length,
    }))
    .sort((left, right) => right.count - left.count)[0].separator;
}

function canonicalImportField(header) {
  const aliases = {
    sku: ["sku", "артикул"],
    name: ["name", "название", "товар", "product"],
    category: ["category", "категория"],
    price: ["price", "price_astrocoins", "цена", "астрокоины"],
    quantity: ["quantity", "stock", "остаток", "количество"],
    warehouse: ["warehouse", "склад"],
    description: ["description", "описание"],
    photoUrl: ["photo_url", "фото", "изображение"],
    status: ["status", "статус"],
  };
  const normalized = normalizeHeader(header);
  return Object.entries(aliases).find(([, values]) => values.includes(normalized))?.[0] || "";
}

function parseDemoImport(text) {
  const lines = text
    .replace(/^\uFEFF/, "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  if (lines.length < 2) {
    throw new Error("В файле нет строк с товарами");
  }

  const separator = detectSeparator(lines[0]);
  const headers = splitSeparatedLine(lines[0], separator).map(canonicalImportField);
  const required = ["sku", "name", "category", "price", "quantity", "warehouse"];
  const missed = required.filter((field) => !headers.includes(field));
  if (missed.length > 0) {
    throw new Error("Не хватает колонок: sku, name, category, price_astrocoins, quantity, warehouse");
  }

  return lines.slice(1).map((line, rowIndex) => {
    const values = splitSeparatedLine(line, separator);
    const row = {};
    headers.forEach((field, index) => {
      if (field) row[field] = values[index] || "";
    });

    const price = Number.parseInt(String(row.price).replace(/\D/g, ""), 10);
    const stock = Number.parseInt(String(row.quantity).replace(/\D/g, ""), 10);
    if (!row.sku || !row.name || Number.isNaN(price) || Number.isNaN(stock)) {
      throw new Error(`Проверьте строку ${rowIndex + 2}: нужен артикул, название, цена и остаток`);
    }

    return {
      id: `demo-import-${row.sku}`,
      sku: row.sku,
      name: row.name,
      description: row.description || "",
      category: row.category || "Без категории",
      price,
      stock,
      warehouse: row.warehouse || "Общий склад",
      mark: row.name.trim().slice(0, 1).toUpperCase() || "A",
      photoUrl: row.photoUrl || "",
      status: row.status || "active",
      warehouses: [
        {
          warehouse_id: `demo-import-warehouse-${row.warehouse || "default"}`,
          warehouse_name: row.warehouse || "Общий склад",
          available_quantity: stock,
        },
      ],
    };
  });
}

function orderStatusLabel(status) {
  return {
    created: "Оформлен",
    reserved: "Зарезервирован",
    transferred_to_teacher: "Передан педагогу",
    issued_to_student: "Выдан ученику",
    cancelled: "Отменен",
    returned: "Возвращен",
    coins_refunded: "Монеты возвращены",
    problem: "Проблема",
  }[status] || status;
}

function orderStatusTone(status) {
  if (["issued_to_student", "reserved"].includes(status)) return "ok";
  if (["transferred_to_teacher", "created"].includes(status)) return "warn";
  return "danger";
}

function ledgerAmount(entry) {
  const sign = entry.direction === "debit" ? "-" : "+";
  return `${sign}${entry.amount} AC`;
}

function applySession(session) {
  if (!session || !Array.isArray(session.students) || session.students.length === 0) {
    return;
  }

  students = session.students.map((student) => ({
    id: String(student.student_id),
    lmsId: student.lms_student_id || "",
    role: student.role,
    name: student.display_name,
    group: student.group_name || student.course_name || "Группа не указана",
    teacher: student.teacher_name || "Педагог не указан",
    balance: student.balance,
    contact: session.account?.max_user_id || "",
  }));

  const previousStudentExists = students.some((student) => student.id === state.activeStudentId);
  if (!previousStudentExists) {
    state.activeStudentId = students[0].id;
  }

  orders = (session.orders || []).map((order) => ({
    id: String(order.order_number),
    student: order.student_name,
    item: `Заказ на ${order.total_astrocoins} AC`,
    warehouse: order.venue_name || "Склад будет выбран",
    status: orderStatusLabel(order.status),
    tone: orderStatusTone(order.status),
  }));

  ledger = (session.ledger || []).map((entry) => [
    formatDate(entry.created_at),
    entry.reason,
    ledgerAmount(entry),
  ]);

  const hasParentRole = session.student_roles?.includes("parent");
  state.role = hasParentRole ? "parent" : "student";
  state.sessionLoaded = true;
}

function applyCatalog(catalog) {
  if (!catalog || !Array.isArray(catalog.products) || catalog.products.length === 0) {
    return;
  }

  products = catalog.products.map((product) => {
    const primaryWarehouse = product.warehouses?.[0];
    const name = product.name || "Товар";
    return {
      id: String(product.id),
      sku: product.sku,
      name,
      description: product.description || "",
      category: product.category_name || "Без категории",
      price: product.price_astrocoins,
      stock: product.available_quantity,
      warehouse: primaryWarehouse?.warehouse_name || "Склад будет выбран",
      mark: name.trim().slice(0, 1).toUpperCase() || "A",
      warehouses: product.warehouses || [],
    };
  });
  state.catalogLoaded = true;
}

async function loadSession() {
  if (apiContext.demoMode) return;
  if (!apiContext.maxUserId) return;

  const response = await fetch(
    apiUrl("/api/v1/miniapp/session", {
      max_user_id: apiContext.maxUserId,
      tenant_slug: apiContext.tenantSlug,
    }),
  );
  if (!response.ok) throw new Error(await parseApiError(response));
  applySession(await response.json());
}

async function loadCatalog() {
  if (apiContext.demoMode) return;

  const response = await fetch(
    apiUrl("/api/v1/miniapp/catalog", { tenant_slug: apiContext.tenantSlug }),
  );
  if (!response.ok) throw new Error(await parseApiError(response));
  applyCatalog(await response.json());
}

function setView(view) {
  state.view = view;
  qsa(".nav-button").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.view === view);
  });
  qsa("[data-view-panel]").forEach((panel) => {
    panel.classList.toggle("is-active", panel.dataset.viewPanel === view);
  });
}

function setRole(role) {
  state.role = role;
  qsa(".role-button").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.role === role);
  });

  const adminButton = qs('[data-view="admin"]');
  adminButton.disabled = !["teacher", "admin"].includes(role);
  if (adminButton.disabled && state.view === "admin") {
    setView("dashboard");
  }
  renderStatus();
}

function setActiveStudent(studentId) {
  if (!students.some((student) => student.id === studentId)) return;
  state.activeStudentId = studentId;
  renderAll();
}

function renderStatus() {
  const student = selectedStudent();
  const linkedCount = students.length;
  const labels = {
    student: student ? `${student.name}, ученик` : "Ученик",
    parent: linkedCount > 0 ? `Родитель, ${linkedCount} учен.` : "Родитель",
    teacher: "Олейник Д, педагог",
    admin: "Администратор tenant",
  };

  state.balance = student?.balance || 0;
  qs("#profileTitle").textContent = labels[state.role] || "Профиль";
  qs("#balanceValue").textContent = state.balance;
  qs("#linkedStudentsCount").textContent = linkedCount;
  qs("#openOrdersCount").textContent = orders.filter((order) => order.tone !== "danger").length;
  qs("#stockProblemCount").textContent = orders.filter((order) => order.tone === "danger").length;

  const select = qs("#studentSelect");
  select.innerHTML = sortedStudents()
    .map(
      (item) =>
        `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name)} - ${escapeHtml(
          item.group,
        )}</option>`,
    )
    .join("");
  select.value = state.activeStudentId || "";
  select.disabled = students.length <= 1;

  const groupFilter = qs("#studentGroupFilter");
  if (groupFilter) {
    const groups = studentGroups();
    if (state.studentGroupFilter !== "all" && !groups.includes(state.studentGroupFilter)) {
      state.studentGroupFilter = "all";
    }
    groupFilter.innerHTML = [
      '<option value="all">Все группы</option>',
      ...groups.map((group) => `<option value="${escapeHtml(group)}">${escapeHtml(group)}</option>`),
    ].join("");
    groupFilter.value = state.studentGroupFilter;
  }
}

function renderStudents() {
  const list = qs("#studentList");
  if (students.length === 0) {
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
              const active = student.id === state.activeStudentId;
              return `
                <div class="student-row ${active ? "is-active" : ""}">
                  <div>
                    <strong>${escapeHtml(student.name)}</strong>
                    <div class="student-meta">${escapeHtml(student.teacher)}</div>
                  </div>
                  <span class="soft-badge">${student.balance} AC</span>
                  <button class="secondary-action compact" type="button" data-select-student="${escapeHtml(
                    student.id,
                  )}">${active ? "Выбран" : "Выбрать"}</button>
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

function renderDashboardOrders() {
  const list = qs("#dashboardOrders");
  if (!list) return;

  const visible = orders.slice(0, 4);
  if (visible.length === 0) {
    list.innerHTML = '<div class="empty-state compact-empty">Заказов пока нет</div>';
    return;
  }

  list.innerHTML = visible
    .map(
      (order) => `
        <div class="compact-order">
          <div>
            <strong>${escapeHtml(order.student)}</strong>
            <div class="student-meta">${escapeHtml(order.item)}</div>
          </div>
          <span class="status-badge ${order.tone}">${escapeHtml(order.status)}</span>
        </div>
      `,
    )
    .join("");
}

function renderCategories() {
  const filter = qs("#categoryFilter");
  const selected = filter.value || "all";
  const categories = [...new Set(products.map((product) => product.category))];
  filter.innerHTML = [
    '<option value="all">Все категории</option>',
    ...categories.map(
      (category) => `<option value="${escapeHtml(category)}">${escapeHtml(category)}</option>`,
    ),
  ].join("");
  filter.value = categories.includes(selected) ? selected : "all";
}

function renderProducts() {
  const search = qs("#productSearch").value.trim().toLowerCase();
  const category = qs("#categoryFilter").value;
  const grid = qs("#productGrid");
  const visible = products.filter((product) => {
    const matchesSearch = product.name.toLowerCase().includes(search);
    const matchesCategory = category === "all" || product.category === category;
    return matchesSearch && matchesCategory;
  });

  grid.classList.toggle("is-empty", visible.length === 0);
  if (visible.length === 0) {
    grid.innerHTML = '<div class="empty-state">Товары не найдены</div>';
    return;
  }

  grid.innerHTML = visible
    .map((product) => {
      const warehouses = productWarehouses(product);
      const selectedWarehouse = warehouses[0];
      const inCart = selectedWarehouse ? cartQuantityFor(product.id, selectedWarehouse.id) : 0;
      const availableLeft = selectedWarehouse ? Math.max(selectedWarehouse.available - inCart, 0) : 0;
      const disabled = availableLeft <= 0;
      const favorite = state.favorites.has(product.id);
      const stockText = product.stock > 0 ? `Остаток ${product.stock}` : "Нет в наличии";
      return `
        <article class="product-card" data-product-card="${escapeHtml(product.id)}">
          <div class="product-visual">${escapeHtml(product.mark)}</div>
          <div class="product-body">
            <h3>${escapeHtml(product.name)}</h3>
            <div class="product-meta">
              <span>${escapeHtml(product.category)}</span>
              <span>${product.price} AC</span>
              <span>${stockText}</span>
              <span>${warehouseCountLabel(warehouses.length)}</span>
            </div>
            <div class="product-pickers">
              <label>
                <span>Склад</span>
                <select data-warehouse-select="${escapeHtml(product.id)}">
                  ${warehouses
                    .map(
                      (warehouse) => `
                        <option value="${escapeHtml(warehouse.id)}">
                          ${escapeHtml(warehouse.name)} · ${warehouse.available} шт.
                        </option>
                      `,
                    )
                    .join("")}
                </select>
              </label>
              <label>
                <span>Кол-во</span>
                <input
                  data-quantity="${escapeHtml(product.id)}"
                  type="number"
                  min="1"
                  max="${availableLeft}"
                  value="${disabled ? 0 : 1}"
                  ${disabled ? "disabled" : ""}
                />
              </label>
            </div>
          </div>
          <div class="product-actions">
            <button
              class="icon-button ${favorite ? "is-active" : ""}"
              type="button"
              title="Избранное"
              data-favorite="${escapeHtml(product.id)}"
            >★</button>
            <button
              class="primary-action"
              type="button"
              data-add="${escapeHtml(product.id)}"
              ${disabled ? "disabled" : ""}
            >${disabled ? "Недоступно" : "В корзину"}</button>
          </div>
        </article>
      `;
    })
    .join("");
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
    list.innerHTML = '<div class="empty-state">Корзина пока пустая</div>';
  } else {
    list.innerHTML = Array.from(state.cart.entries())
      .map(([key, item]) => {
        const product = productById(item.productId);
        if (!product) return "";
        const warehouses = productWarehouses(product);
        const selectedWarehouse = warehouseById(product, item.warehouseId) || warehouses[0];
        const selectedAvailable = selectedWarehouse?.available || item.quantity;
        const maxQuantity = selectedAvailable + item.quantity - cartQuantityFor(product.id, item.warehouseId);
        return `
          <div class="cart-row">
            <div>
              <strong>${escapeHtml(product.name)}</strong>
              <div class="student-meta">${item.quantity} шт. · ${product.price * item.quantity} AC</div>
            </div>
            <div>${product.price} AC</div>
            <select class="cart-warehouse-select" data-cart-warehouse="${escapeHtml(key)}">
              ${warehouses
                .map(
                  (warehouse) => `
                    <option value="${escapeHtml(warehouse.id)}" ${
                      warehouse.id === item.warehouseId ? "selected" : ""
                    }>
                      ${escapeHtml(warehouse.name)}
                    </option>
                  `,
                )
                .join("")}
            </select>
            <div class="quantity-control">
              <input
                type="number"
                min="1"
                max="${maxQuantity}"
                value="${item.quantity}"
                data-cart-quantity="${escapeHtml(key)}"
              />
            </div>
            <button class="icon-button" type="button" title="Удалить" data-remove="${escapeHtml(
              key,
            )}">×</button>
          </div>
        `;
      })
      .join("");
  }

  const total = cartTotal();
  qs("#cartCounter").textContent = cartCount();
  qs("#cartTotal").textContent = total;
  qs("#placeOrderButton").disabled = state.cart.size === 0 || total > state.balance;
}

function renderOrders() {
  if (orders.length === 0) {
    qs("#ordersTable").innerHTML = '<div class="empty-state">Заказов пока нет</div>';
    return;
  }

  qs("#ordersTable").innerHTML = [
    '<div class="table-row table-head"><span>№</span><span>Ученик и позиция</span><span>Склад</span><span>Статус</span><span></span></div>',
    ...orders.map(
      (order) => `
        <div class="table-row">
          <span>${escapeHtml(order.id)}</span>
          <div>
            <strong class="order-title">${escapeHtml(order.student)}</strong>
            <div class="student-meta">${escapeHtml(order.item)}</div>
          </div>
          <span>${escapeHtml(order.warehouse)}</span>
          <span class="status-badge ${order.tone}">${escapeHtml(order.status)}</span>
          <button class="secondary-action" type="button" data-open-order="${escapeHtml(
            order.id,
          )}">Открыть</button>
        </div>
      `,
    ),
  ].join("");
}

function renderLedger() {
  if (ledger.length === 0) {
    qs("#ledgerList").innerHTML = '<div class="empty-state">Операций пока нет</div>';
    return;
  }

  qs("#ledgerList").innerHTML = ledger
    .map(
      ([date, reason, amount]) => `
        <div class="ledger-row">
          <span>${escapeHtml(date)}</span>
          <strong>${escapeHtml(reason)}</strong>
          <span>${escapeHtml(amount)}</span>
        </div>
      `,
    )
    .join("");
}

function renderAccrual() {
  const groupSelect = qs("#accrualGroupSelect");
  const studentList = qs("#accrualStudentList");
  const nameFilter = qs("#accrualNameFilter");
  if (!groupSelect || !studentList || !nameFilter) return;

  const groups = studentGroups();
  if (state.accrualGroup !== "all" && !groups.includes(state.accrualGroup)) {
    state.accrualGroup = "all";
  }
  groupSelect.innerHTML = [
    '<option value="all">Все группы</option>',
    ...groups.map((group) => `<option value="${escapeHtml(group)}">${escapeHtml(group)}</option>`),
  ].join("");
  groupSelect.disabled = groups.length === 0;
  groupSelect.value = state.accrualGroup;
  nameFilter.value = state.accrualNameFilter;

  const normalizedName = state.accrualNameFilter.trim().toLowerCase();
  const visibleStudents = studentsForGroup(state.accrualGroup).filter((student) =>
    student.name.toLowerCase().includes(normalizedName),
  );

  const header = `
    <div class="accrual-table-row accrual-table-head">
      <span>ID</span>
      <span>ФИО</span>
      <span>ГРУППЫ</span>
      <span>НАЧИСЛИТЬ АСТРОКОИНЫ</span>
      <span>НАЧИСЛИТЬ АСТРОКОИНЫ</span>
    </div>
  `;

  if (visibleStudents.length === 0) {
    studentList.innerHTML = `${header}<div class="empty-state">Ученики не найдены</div>`;
    return;
  }

  studentList.innerHTML =
    header +
    visibleStudents
      .map(
        (student, index) => `
          <div class="accrual-table-row">
            <span>${escapeHtml(studentDisplayId(student, index))}</span>
            <strong>${escapeHtml(student.name)}</strong>
            <span>${escapeHtml(studentGroupName(student))}</span>
            <select data-accrual-reason="${escapeHtml(student.id)}">
              <option value=""></option>
              ${accrualReasons
                .map((reason) => `<option value="${escapeHtml(reason)}">${escapeHtml(reason)}</option>`)
                .join("")}
            </select>
            <select data-accrual-amount="${escapeHtml(student.id)}">
              <option value=""></option>
              ${accrualAmounts
                .map((amount) => `<option value="${amount}">+${amount} AC</option>`)
                .join("")}
            </select>
          </div>
        `,
      )
      .join("");
}

function renderAdminPanel() {
  qsa(".admin-tab").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.adminTab === state.adminTab);
  });

  if (state.adminTab === "products") {
    const disabled = state.productImporting ? "disabled" : "";
    qs("#adminPanel").innerHTML = `
      <div class="import-panel">
        <div>
          <h3>Загрузка товаров</h3>
        </div>
        <label class="file-picker">
          <input id="productImportFile" type="file" accept=".xlsx,.csv,text/csv" />
          <span>${escapeHtml(state.productImportFileName || "Выбрать файл")}</span>
        </label>
        <button id="productImportButton" class="primary-action" type="button" ${disabled}>
          ${state.productImporting ? "Загрузка..." : "Загрузить"}
        </button>
      </div>
      <div class="warehouse-row table-head">
        <span>Товар</span><span>Категория</span><span>Склад</span><span>Остаток</span><span>Цена</span>
      </div>
      ${products
        .map(
          (product) => `
            <div class="warehouse-row">
              <strong>${escapeHtml(product.name)}</strong>
              <span>${escapeHtml(product.category)}</span>
              <span>${escapeHtml(product.warehouse)}</span>
              <span>${product.stock} шт.</span>
              <span>${product.price} AC</span>
            </div>
          `,
        )
        .join("")}
    `;
    return;
  }

  if (state.adminTab === "warehouses") {
    qs("#adminPanel").innerHTML = warehouses
      .map(
        ([name, type, place, stock, statusText]) => `
          <div class="warehouse-row">
            <strong>${escapeHtml(name)}</strong>
            <span>${escapeHtml(type)}</span>
            <span>${escapeHtml(place)}</span>
            <span>${escapeHtml(stock)}</span>
            <button class="secondary-action" type="button" data-warehouse-action="${escapeHtml(
              name,
            )}">${escapeHtml(statusText)}</button>
          </div>
        `,
      )
      .join("");
    return;
  }

  if (state.adminTab === "inventory") {
    qs("#adminPanel").innerHTML = products
      .map(
        (product) => `
          <div class="warehouse-row">
            <strong>${escapeHtml(product.name)}</strong>
            <span>${escapeHtml(product.category)}</span>
            <span>${escapeHtml(product.warehouse)}</span>
            <span>${product.stock} шт.</span>
            <button class="secondary-action" type="button" data-transfer-product="${escapeHtml(
              product.id,
            )}">Перенести</button>
          </div>
        `,
      )
      .join("");
    return;
  }

  qs("#adminPanel").innerHTML = students
    .map(
      (student) => `
        <div class="contact-row">
          <strong>${escapeHtml(student.contact)}</strong>
          <span>${escapeHtml(student.name)}</span>
          <span>${escapeHtml(student.group)}</span>
          <button class="secondary-action" type="button" data-toggle-contact="${escapeHtml(
            student.id,
          )}">${student.revoked ? "Вернуть" : "Отозвать"}</button>
        </div>
      `,
    )
    .join("");
}

function renderAll() {
  renderStatus();
  renderStudents();
  renderDashboardOrders();
  renderCategories();
  renderProducts();
  renderCart();
  renderOrders();
  renderLedger();
  renderAccrual();
  renderAdminPanel();
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
    const response = await fetch("/api/v1/miniapp/products/import", {
      method: "POST",
      body: formData,
    });
    if (!response.ok) throw new Error(await parseApiError(response));

    const result = await response.json();
    await loadCatalog();
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

function addToCart(productId) {
  const product = productById(productId);
  if (!product) return;
  const card = qsa("[data-product-card]").find((item) => item.dataset.productCard === productId);
  const warehouse = selectedProductWarehouse(product, card);
  if (!warehouse) return;

  const quantityInput = card?.querySelector("[data-quantity]");
  const current = cartQuantityFor(product.id, warehouse.id);
  const availableLeft = Math.max(warehouse.available - current, 0);
  const quantity = clampQuantity(quantityInput?.value || "1", availableLeft);
  if (availableLeft <= 0) return;

  const key = cartKey(product.id, warehouse.id);
  state.cart.set(key, {
    productId: product.id,
    warehouseId: warehouse.id,
    warehouseName: warehouse.name,
    quantity: current + quantity,
  });
  renderProducts();
  renderCart();
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
  const orderSummary = Array.from(state.cart.values())
    .map((item) => {
      const product = productById(item.productId);
      if (!product) return "";
      return `${product.name} x${item.quantity}, ${item.warehouseName}`;
    })
    .filter(Boolean)
    .join("; ");
  student.balance -= total;
  orders.unshift({
    id: orderNumber,
    student: student.name,
    item: orderSummary || `Заказ на ${total} AC`,
    warehouse: "Выбрано в корзине",
    status: "Зарезервирован",
    tone: "ok",
  });
  ledger.unshift([todayShort(), `Покупка в магазине, заказ №${orderNumber}`, `-${total} AC`]);
  state.cart.clear();
  showNotice(`Заказ №${orderNumber} оформлен в демо-режиме`);
  setView("orders");
  renderAll();
}

function openOrderDetails(orderId) {
  const order = orders.find((item) => item.id === orderId);
  if (!order) return;
  setView("orders");
  showNotice(
    `Заказ №${order.id}: ${order.student}, ${order.item}, склад: ${order.warehouse}, статус: ${order.status}`,
  );
}

function accrueGroupCoins() {
  const amount = 50;
  students.forEach((student) => {
    student.balance += amount;
  });
  ledger.unshift([todayShort(), `Начисление группе: ${students.length} учен.`, `+${amount} AC`]);
  showNotice(`Группе начислено по ${amount} AC`);
  renderAll();
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

function toggleContactLink(studentId) {
  const student = students.find((item) => item.id === studentId);
  if (!student) return;
  student.revoked = !student.revoked;
  showNotice(
    student.revoked
      ? `Связь с учеником ${student.name} помечена к отзыву`
      : `Связь с учеником ${student.name} восстановлена`,
  );
  renderStudents();
  renderAdminPanel();
}

function updateCartQuantity(key, value) {
  const item = state.cart.get(key);
  if (!item) return;
  const product = productById(item.productId);
  const warehouse = product ? warehouseById(product, item.warehouseId) : null;
  if (!product || !warehouse) return;

  const maxQuantity = warehouse.available + item.quantity - cartQuantityFor(product.id, item.warehouseId);
  item.quantity = clampQuantity(value, maxQuantity);
  state.cart.set(key, item);
  renderProducts();
  renderCart();
}

function updateCartWarehouse(key, warehouseId) {
  const item = state.cart.get(key);
  if (!item) return;
  const product = productById(item.productId);
  const warehouse = product ? warehouseById(product, warehouseId) : null;
  if (!product || !warehouse) return;

  if (warehouse.id === item.warehouseId) return;

  state.cart.delete(key);
  const nextKey = cartKey(product.id, warehouse.id);
  const existing = state.cart.get(nextKey);
  const availableLeft = Math.max(warehouse.available - (existing?.quantity || 0), 0);
  if (availableLeft <= 0) {
    state.cart.set(key, item);
    showNotice("На выбранном складе нет свободного остатка", "danger");
    renderCart();
    return;
  }

  state.cart.set(nextKey, {
    productId: product.id,
    warehouseId: warehouse.id,
    warehouseName: warehouse.name,
    quantity: (existing?.quantity || 0) + Math.min(item.quantity, availableLeft),
  });
  renderProducts();
  renderCart();
}

function selectedAccrualStudents() {
  return studentsForGroup(state.accrualGroup);
}

async function accrueStudents(targets, amount, reason) {
  if (targets.length === 0) {
    showNotice("Выберите учеников для начисления", "danger");
    return;
  }

  if (apiContext.demoMode || !apiContext.maxUserId || targets.some((student) => student.id.startsWith("demo-"))) {
    targets.forEach((student) => {
      student.balance += amount;
    });
    ledger.unshift([
      todayShort(),
      targets.length === 1
        ? `${reason}: ${targets[0].name}`
        : `${reason}: ${state.accrualGroup}, ${targets.length} учен.`,
      `+${amount} AC`,
    ]);
    showNotice(
      targets.length === 1
        ? `${targets[0].name}: начислено ${amount} AC`
        : `Группе «${state.accrualGroup}» начислено по ${amount} AC`,
    );
    renderAll();
    return;
  }

  try {
    const response = await fetch("/api/v1/miniapp/coins/accrue", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        max_user_id: Number(apiContext.maxUserId),
        tenant_slug: apiContext.tenantSlug || undefined,
        student_ids: targets.map((student) => student.id),
        amount,
        reason,
        comment: "MAX mini app",
      }),
    });
    if (!response.ok) throw new Error(await parseApiError(response));

    const result = await response.json();
    showNotice(
      targets.length === 1
        ? `${targets[0].name}: начислено ${amount} AC`
        : `Группе «${state.accrualGroup}» начислено по ${amount} AC: ${result.credited_students} учен.`,
    );
    await loadSession();
    renderAll();
  } catch (error) {
    showNotice(error.message || "Не удалось начислить астрокоины", "danger");
  }
}

async function accrueStudentFromRow(studentId) {
  const student = students.find((item) => item.id === studentId);
  const reason =
    qsa("[data-accrual-reason]").find((item) => item.dataset.accrualReason === studentId)
      ?.value || "";
  const amountValue =
    qsa("[data-accrual-amount]").find((item) => item.dataset.accrualAmount === studentId)
      ?.value || "";
  const amount = Number.parseInt(amountValue, 10);

  if (!student || !amountValue) return;
  if (!reason) {
    showNotice("Выберите причину начисления", "danger");
    return;
  }
  if (!amount || amount <= 0) {
    showNotice("Выберите количество астрокоинов", "danger");
    return;
  }

  await accrueStudents([student], amount, reason);
}

async function placeOrder() {
  if (state.cart.size === 0) return;

  const student = selectedStudent();
  const canUseBackend =
    apiContext.maxUserId && student && !student.id.startsWith("demo-") && state.catalogLoaded;
  if (!canUseBackend) {
    createDemoOrder();
    return;
  }

  const payload = {
    max_user_id: Number(apiContext.maxUserId),
    tenant_slug: apiContext.tenantSlug || undefined,
    student_id: student.id,
    items: Array.from(state.cart.values()).map((item) => ({
      product_id: item.productId,
      warehouse_id: item.warehouseId?.startsWith("demo-") ? undefined : item.warehouseId,
      quantity: item.quantity,
    })),
    comment: "MAX mini app",
  };

  const button = qs("#placeOrderButton");
  button.disabled = true;
  try {
    const response = await fetch("/api/v1/miniapp/orders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(await parseApiError(response));

    const result = await response.json();
    state.cart.clear();
    showNotice(`Заказ №${result.order.order_number} оформлен и зарезервирован`);
    await loadSession();
    setView("orders");
    renderAll();
  } catch (error) {
    showNotice(error.message || "Не удалось оформить заказ", "danger");
    renderCart();
  }
}

document.addEventListener("click", (event) => {
  const target = event.target instanceof HTMLElement ? event.target.closest("button") : null;
  if (!target) return;

  const role = target.dataset.role;
  if (role) setRole(role);

  const view = target.dataset.view || target.dataset.viewJump;
  if (view) setView(view);

  const studentId = target.dataset.selectStudent;
  if (studentId) setActiveStudent(studentId);

  const addId = target.dataset.add;
  if (addId) addToCart(addId);

  const favoriteId = target.dataset.favorite;
  if (favoriteId) {
    if (state.favorites.has(favoriteId)) state.favorites.delete(favoriteId);
    else state.favorites.add(favoriteId);
    renderProducts();
  }

  const removeId = target.dataset.remove;
  if (removeId) {
    state.cart.delete(removeId);
    renderProducts();
    renderCart();
  }

  const adminTab = target.dataset.adminTab;
  if (adminTab) {
    state.adminTab = adminTab;
    renderAdminPanel();
  }

  const orderId = target.dataset.openOrder;
  if (orderId) openOrderDetails(orderId);

  if ("groupAccrual" in target.dataset) {
    accrueGroupCoins();
  }

  const warehouseName = target.dataset.warehouseAction;
  if (warehouseName) showWarehouseAction(warehouseName);

  const transferProductId = target.dataset.transferProduct;
  if (transferProductId) cycleProductWarehouse(transferProductId);

  const contactStudentId = target.dataset.toggleContact;
  if (contactStudentId) toggleContactLink(contactStudentId);

  if (target.id === "productImportButton") {
    importProductsFromFile();
  }

  if (target.id === "applyAccrualFilter") {
    state.accrualNameFilter = qs("#accrualNameFilter")?.value.trim() || "";
    state.accrualGroup = qs("#accrualGroupSelect")?.value || "all";
    renderAccrual();
  }
});

document.addEventListener("change", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLInputElement) && !(target instanceof HTMLSelectElement)) return;

  if (target.id === "productImportFile") {
    const file = target.files?.[0] || null;
    state.productImportFile = file;
    state.productImportFileName = file?.name || "";
    const label = target.closest(".file-picker")?.querySelector("span");
    if (label) label.textContent = state.productImportFileName || "Выбрать файл";
  }

  if (target.id === "studentGroupFilter") {
    state.studentGroupFilter = target.value;
    renderStudents();
  }

  if (target.matches("[data-warehouse-select]")) {
    syncProductCardControls(target.closest("[data-product-card]"));
  }

  const accrualAmountStudentId = target.dataset.accrualAmount;
  if (accrualAmountStudentId) {
    accrueStudentFromRow(accrualAmountStudentId);
  }

  const accrualReasonStudentId = target.dataset.accrualReason;
  if (accrualReasonStudentId) {
    const amountSelected = qsa("[data-accrual-amount]").find(
      (item) => item.dataset.accrualAmount === accrualReasonStudentId && item.value,
    );
    if (amountSelected) accrueStudentFromRow(accrualReasonStudentId);
  }

  const cartQuantityKey = target.dataset.cartQuantity;
  if (cartQuantityKey) {
    updateCartQuantity(cartQuantityKey, target.value);
  }

  const cartWarehouseKey = target.dataset.cartWarehouse;
  if (cartWarehouseKey) {
    updateCartWarehouse(cartWarehouseKey, target.value);
  }
});

document.addEventListener("input", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLInputElement)) return;

  if (target.matches("[data-quantity]")) {
    syncProductCardControls(target.closest("[data-product-card]"));
  }
});

qs("#studentSelect").addEventListener("change", (event) => {
  setActiveStudent(event.target.value);
});
qs("#openCartButton").addEventListener("click", () => setView("cart"));
qs("#productSearch").addEventListener("input", renderProducts);
qs("#categoryFilter").addEventListener("change", renderProducts);
qs("#placeOrderButton").addEventListener("click", placeOrder);

async function init() {
  const results = await Promise.allSettled([loadSession(), loadCatalog()]);
  results
    .filter((result) => result.status === "rejected")
    .forEach((result) => console.warn(result.reason));

  setRole(state.role);
  setView(state.view);
  renderAll();
}

init();
