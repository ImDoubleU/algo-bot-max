const apiContext = {
  maxUserId: queryParam("max_user_id"),
  tenantSlug: queryParam("tenant_slug") || "",
  demoMode: queryParam("demo") === "1",
};

const state = {
  role: "student",
  view: "dashboard",
  adminTab: "summary",
  studentGroupFilter: "all",
  orderStatusFilter: "open",
  orderSearch: "",
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
  productSaving: false,
  editingProductId: "",
  staffSaving: false,
  inventorySavingKey: "",
  warehouseSaving: false,
  editingWarehouseId: "",
  opsSummary: null,
  opsSummaryLoaded: false,
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

let accessLinks = [
  {
    id: "demo-link-alisa",
    maxUserId: "53364725",
    username: "parent_user",
    displayName: "Родитель",
    studentId: "demo-alisa",
    studentName: "Алиса",
    group: "Союзный 45, вс 10:00",
    role: "parent",
    status: "active",
  },
  {
    id: "demo-link-ivan",
    maxUserId: "53364725",
    username: "parent_user",
    displayName: "Родитель",
    studentId: "demo-ivan",
    studentName: "Иван",
    group: "Гагарина 64, сб 18:00",
    role: "parent",
    status: "active",
  },
];

let staffAssignments = [
  {
    id: "demo-staff-admin",
    maxUserId: "53364725",
    username: "admin_user",
    displayName: "Администратор",
    role: "admin",
    status: "active",
  },
  {
    id: "demo-staff-teacher",
    maxUserId: "53364726",
    username: "teacher_user",
    displayName: "Педагог",
    role: "teacher",
    status: "active",
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
          stock_quantity: 3,
          reserved_quantity: 0,
          available_quantity: 3,
        },
        {
          warehouse_id: "demo-warehouse-soyuznyy",
          warehouse_name: "Союзный 45",
          stock_quantity: 1,
          reserved_quantity: 0,
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
          stock_quantity: 12,
          reserved_quantity: 0,
          available_quantity: 12,
        },
        {
          warehouse_id: "demo-warehouse-common",
          warehouse_name: "Общий склад",
          stock_quantity: 6,
          reserved_quantity: 0,
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
          stock_quantity: 2,
          reserved_quantity: 0,
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
          stock_quantity: 0,
          reserved_quantity: 0,
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
          stock_quantity: 24,
          reserved_quantity: 0,
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
          stock_quantity: 3,
          reserved_quantity: 0,
          available_quantity: 3,
        },
      ],
  },
];

let orders = [
  {
    id: "1357",
    backendId: "demo-order-1357",
    rawStatus: "reserved",
    student: "Алиса",
    item: "Ручка металл с лого",
    warehouse: "Союзный 45",
    status: "Зарезервирован",
    tone: "ok",
  },
  {
    id: "1358",
    backendId: "demo-order-1358",
    rawStatus: "transferred_to_teacher",
    student: "Иван",
    item: "Кружка Python",
    warehouse: "Общий склад",
    status: "Передан педагогу",
    tone: "warn",
  },
  {
    id: "1359",
    backendId: "demo-order-1359",
    rawStatus: "problem",
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

let catalogWarehouses = [
  { id: "demo-warehouse-common", name: "Общий склад", type: "common", address: "Нижний Новгород" },
  { id: "demo-warehouse-soyuznyy", name: "Союзный 45", type: "venue", address: "Союзный 45" },
  { id: "demo-warehouse-gagarina", name: "Гагарина 64", type: "venue", address: "Гагарина 64" },
  { id: "demo-warehouse-external", name: "Внешний склад", type: "external", address: "Поставщик" },
  { id: "demo-warehouse-partner", name: "Партнерский склад", type: "partner", address: "Партнер" },
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

function slugify(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replaceAll("ё", "е")
    .replace(/[^a-z0-9а-я]+/gi, "-")
    .replace(/^-+|-+$/g, "") || "warehouse";
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
      type: warehouse.warehouse_type || warehouse.type || "",
      stock: Number(warehouse.stock_quantity ?? warehouse.stock ?? warehouse.available_quantity ?? 0),
      reserved: Number(warehouse.reserved_quantity || warehouse.reserved || 0),
      available: Number(warehouse.available_quantity || warehouse.available || 0),
    }));
  }

  return [
    {
      id: product.warehouse || "default",
      name: product.warehouse || "Склад будет выбран",
      type: "",
      stock: Number(product.stock || 0),
      reserved: 0,
      available: Number(product.stock || 0),
    },
  ];
}

function allCatalogWarehouses() {
  const byId = new Map();
  catalogWarehouses.forEach((warehouse) => {
    byId.set(String(warehouse.id), {
      id: String(warehouse.id),
      slug: warehouse.slug || "",
      name: warehouse.name || "Склад",
      type: warehouse.warehouse_type || warehouse.type || "",
      address: warehouse.address || "",
    });
  });
  products.forEach((product) => {
    productWarehouses(product).forEach((warehouse) => {
      if (!byId.has(warehouse.id)) {
        byId.set(warehouse.id, {
          id: warehouse.id,
          slug: "",
          name: warehouse.name,
          type: "",
          address: "",
        });
      }
    });
  });
  return Array.from(byId.values()).sort((left, right) => left.name.localeCompare(right.name, "ru"));
}

function ensureProductWarehouse(product, warehouse) {
  product.warehouses = product.warehouses || [];
  let raw = product.warehouses.find(
    (item) => String(item.warehouse_id || item.id || item.warehouse_name) === warehouse.id,
  );
  if (!raw) {
    raw = {
      warehouse_id: warehouse.id,
      warehouse_name: warehouse.name,
      warehouse_type: warehouse.type || "common",
      stock_quantity: 0,
      reserved_quantity: 0,
      available_quantity: 0,
    };
    product.warehouses.push(raw);
  }
  return raw;
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

function activeProducts() {
  return products.filter((product) => (product.status || "active") === "active");
}

function productSearchText(product) {
  return [
    product.name,
    product.sku,
    product.category,
    product.categorySlug,
    product.description,
    product.warehouse,
    ...productWarehouses(product).flatMap((warehouse) => [
      warehouse.id,
      warehouse.name,
      warehouse.type,
    ]),
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function productMatchesSearch(product, query) {
  if (!query) return true;
  const searchText = productSearchText(product);
  return query.split(/\s+/).every((token) => searchText.includes(token));
}

function pruneInactiveCartItems() {
  const activeIds = new Set(activeProducts().map((product) => product.id));
  Array.from(state.cart.keys()).forEach((key) => {
    const productId = state.cart.get(key)?.productId;
    if (!activeIds.has(productId)) state.cart.delete(key);
  });
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

function staffRoleToUiRole(staffRoles = []) {
  if (staffRoles.some((role) => ["superadmin", "partner_director", "admin"].includes(role))) {
    return "admin";
  }
  if (staffRoles.some((role) => ["curator", "teacher"].includes(role))) {
    return "teacher";
  }
  return null;
}

function canUseAdminCatalog() {
  return Boolean(apiContext.maxUserId && ["teacher", "admin"].includes(state.role));
}

function buildLocalOpsSummary() {
  const orderStatuses = new Map();
  orders.forEach((order) => {
    const status = order.rawStatus || "created";
    orderStatuses.set(status, (orderStatuses.get(status) || 0) + 1);
  });

  const lowStock = [];
  let totalStock = 0;
  let totalReserved = 0;
  products.forEach((product) => {
    productWarehouses(product).forEach((warehouse) => {
      totalStock += warehouse.stock;
      totalReserved += warehouse.reserved;
      if ((product.status || "active") !== "archived" && warehouse.available <= 5) {
        lowStock.push({
          product_name: product.name,
          sku: product.sku,
          warehouse_name: warehouse.name,
          stock_quantity: warehouse.stock,
          reserved_quantity: warehouse.reserved,
          available_quantity: warehouse.available,
        });
      }
    });
  });

  return {
    tenant_slug: apiContext.tenantSlug || "demo",
    staff_role: state.role === "admin" ? "admin" : "teacher",
    total_orders: orders.length,
    open_orders: orders.filter((order) => isOpenOrderStatus(order.rawStatus)).length,
    pending_issue_orders: orders.filter((order) =>
      ["reserved", "transferred_to_teacher"].includes(order.rawStatus),
    ).length,
    order_statuses: Array.from(orderStatuses.entries()).map(([status, count]) => ({
      status,
      count,
    })),
    recent_open_orders: orders
      .filter((order) => isOpenOrderStatus(order.rawStatus))
      .slice(0, 8)
      .map((order) => ({
        order_number: order.id,
        student_name: order.student,
        status: order.rawStatus,
        total_astrocoins: order.total_astrocoins || 0,
      })),
    low_stock: lowStock.sort((left, right) => left.available_quantity - right.available_quantity),
    low_stock_threshold: 5,
    active_products: activeProducts().length,
    warehouses: allCatalogWarehouses().length,
    total_stock_quantity: totalStock,
    total_reserved_quantity: totalReserved,
  };
}

function applyOpsSummary(summary) {
  state.opsSummary = summary || null;
  state.opsSummaryLoaded = Boolean(summary);
}

function staffRoleLabel(role) {
  return {
    superadmin: "Суперадмин",
    partner_director: "Директор партнера",
    admin: "Админ",
    curator: "Куратор",
    teacher: "Педагог",
  }[role] || role;
}

function assignmentStatusLabel(status) {
  return status === "active" ? "Активна" : "Отозвана";
}

function ledgerAmount(entry) {
  const sign = entry.direction === "debit" ? "-" : "+";
  return `${sign}${entry.amount} AC`;
}

function normalizeOrderItems(order) {
  return (order.items || []).map((item) => ({
    productId: String(item.product_id || ""),
    productName: item.product_name || item.name || "Товар",
    quantity: Number(item.quantity || 0),
    unitPrice: Number(item.unit_price_astrocoins || item.unit_price || 0),
    totalPrice: Number(item.total_price_astrocoins || item.total_price || 0),
    warehouseId: item.warehouse_id ? String(item.warehouse_id) : "",
    warehouseName: item.warehouse_name || "",
  }));
}

function orderItemsSummary(items, fallback = "") {
  if (!Array.isArray(items) || items.length === 0) return fallback;
  const rows = items.slice(0, 3).map((item) => {
    const quantity = item.quantity ? ` x${item.quantity}` : "";
    const total = item.totalPrice ? `, ${item.totalPrice} AC` : "";
    return `${item.productName}${quantity}${total}`;
  });
  if (items.length > 3) rows.push(`еще ${items.length - 3}`);
  return rows.join("; ");
}

function orderWarehouseSummary(items, fallback = "") {
  const names = [
    ...new Set(
      (items || [])
        .map((item) => item.warehouseName)
        .filter((value) => value && value.trim()),
    ),
  ];
  if (names.length === 0) return fallback;
  if (names.length <= 2) return names.join(", ");
  return `${names.slice(0, 2).join(", ")} и еще ${names.length - 2}`;
}

function normalizeOrderStatusHistory(order) {
  return (order.status_history || []).map((event) => ({
    fromStatus: event.from_status || "start",
    toStatus: event.to_status || "unknown",
    comment: event.comment || "",
    createdAt: event.created_at || "",
  }));
}

function orderStatusHistoryDetails(order) {
  if (!Array.isArray(order.statusHistory) || order.statusHistory.length === 0) return "";
  return order.statusHistory
    .slice(-5)
    .map((event) => {
      const date = event.createdAt ? formatDate(event.createdAt) : "";
      const comment = event.comment ? ` - ${event.comment}` : "";
      return `${date}: ${event.fromStatus} -> ${event.toStatus}${comment}`;
    })
    .join("\n");
}

function applySession(session) {
  if (!session || !Array.isArray(session.students) || session.students.length === 0) {
    return;
  }

  students = session.students.map((student) => ({
    id: String(student.student_id),
    lmsId: student.lms_student_id || "",
    role: student.role,
    accessStatus: student.access_status || "active",
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
    backendId: String(order.id),
    rawStatus: order.status,
    student: order.student_name,
    item: `Заказ на ${order.total_astrocoins} AC`,
    warehouse: order.venue_name || "Склад будет выбран",
    status: orderStatusLabel(order.status),
    tone: orderStatusTone(order.status),
  }));

  orders = orders.map((order, index) => {
    const sourceOrder = (session.orders || [])[index] || {};
    const items = normalizeOrderItems(sourceOrder);
    const statusHistory = normalizeOrderStatusHistory(sourceOrder);
    if (items.length === 0) return { ...order, statusHistory };
    return {
      ...order,
      item: orderItemsSummary(items, order.item),
      items,
      statusHistory,
      total: Number(sourceOrder.total_astrocoins || 0),
      warehouse: orderWarehouseSummary(items, order.warehouse),
    };
  });

  accessLinks = (session.access_links || []).map((link) => ({
    id: String(link.id),
    maxUserId: String(link.max_user_id),
    username: link.username || "",
    displayName: link.display_name || "",
    studentId: String(link.student_id),
    studentName: link.student_name,
    group: link.group_name || "Группа не указана",
    role: link.role,
    status: link.status,
  }));

  staffAssignments = (session.staff_assignments || []).map((assignment) => ({
    id: String(assignment.id),
    maxUserId: String(assignment.max_user_id),
    username: assignment.username || "",
    displayName: assignment.display_name || "",
    role: assignment.role,
    status: assignment.status,
  }));

  ledger = (session.ledger || []).map((entry) => [
    formatDate(entry.created_at),
    entry.reason,
    ledgerAmount(entry),
  ]);

  const staffRole = staffRoleToUiRole(session.staff_roles || []);
  const hasParentRole = session.student_roles?.includes("parent");
  state.role = staffRole || (hasParentRole ? "parent" : "student");
  state.sessionLoaded = true;
}

function applyCatalog(catalog) {
  if (!catalog) {
    return;
  }

  if (Array.isArray(catalog.warehouses)) {
    catalogWarehouses = catalog.warehouses.map((warehouse) => ({
      id: String(warehouse.id),
      slug: warehouse.slug || "",
      name: warehouse.name || "Склад",
      type: warehouse.warehouse_type || "",
      address: warehouse.address || "",
    }));
  }

  if (!Array.isArray(catalog.products)) {
    products = [];
    pruneInactiveCartItems();
    state.catalogLoaded = true;
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
      photoUrl: product.photo_url || "",
      status: product.status || "active",
      category: product.category_name || "Без категории",
      categorySlug: product.category_slug || "",
      price: product.price_astrocoins,
      stock: product.available_quantity,
      warehouse: primaryWarehouse?.warehouse_name || "Склад будет выбран",
      mark: name.trim().slice(0, 1).toUpperCase() || "A",
      warehouses: product.warehouses || [],
    };
  });
  pruneInactiveCartItems();
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

  const params = { tenant_slug: apiContext.tenantSlug };
  if (canUseAdminCatalog()) {
    params.max_user_id = apiContext.maxUserId;
    params.include_inactive = "true";
  }
  const response = await fetch(
    apiUrl("/api/v1/miniapp/catalog", params),
  );
  if (!response.ok) throw new Error(await parseApiError(response));
  applyCatalog(await response.json());
}

async function loadOpsSummary() {
  if (apiContext.demoMode || !apiContext.maxUserId || !["teacher", "admin"].includes(state.role)) {
    applyOpsSummary(null);
    return;
  }

  const response = await fetch(
    apiUrl("/api/v1/miniapp/ops/summary", {
      max_user_id: apiContext.maxUserId,
      tenant_slug: apiContext.tenantSlug,
      low_stock_threshold: 5,
    }),
  );
  if (!response.ok) throw new Error(await parseApiError(response));
  applyOpsSummary(await response.json());
}

async function refreshOrderAndInventoryState() {
  await loadSession();
  await loadCatalog();
  await loadOpsSummary();
}

async function refreshCatalogAndOpsSummary() {
  await loadCatalog();
  await loadOpsSummary();
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
  qs("#openOrdersCount").textContent = orders.filter((order) =>
    isOpenOrderStatus(order.rawStatus),
  ).length;
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
  const categories = [...new Set(activeProducts().map((product) => product.category))];
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
  const visible = activeProducts().filter((product) => {
    const matchesSearch = productMatchesSearch(product, search);
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
              ${product.sku ? `<span>${escapeHtml(product.sku)}</span>` : ""}
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

function isOpenOrderStatus(status) {
  return ["created", "reserved", "transferred_to_teacher"].includes(status);
}

function canIssueOrder(order) {
  return (
    ["teacher", "admin"].includes(state.role) &&
    ["reserved", "transferred_to_teacher"].includes(order.rawStatus)
  );
}

function canCancelOrder(order) {
  return ["reserved", "transferred_to_teacher"].includes(order.rawStatus);
}

function canReturnOrder(order) {
  return ["teacher", "admin"].includes(state.role) && order.rawStatus === "issued_to_student";
}

function orderMatchesStatusFilter(order) {
  if (state.orderStatusFilter === "all") return true;
  if (state.orderStatusFilter === "open") return isOpenOrderStatus(order.rawStatus);
  return order.rawStatus === state.orderStatusFilter;
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
  return orders.filter((order) => {
    if (!orderMatchesStatusFilter(order)) return false;
    return !query || orderSearchText(order).includes(query);
  });
}

function orderActionButtons(order) {
  const buttons = [
    `<button class="secondary-action" type="button" data-open-order="${escapeHtml(
      order.backendId || order.id,
    )}">Открыть</button>`,
  ];

  if (canIssueOrder(order)) {
    buttons.push(
      `<button class="secondary-action" type="button" data-order-action="issue" data-order-action-id="${escapeHtml(
        order.backendId || order.id,
      )}">Выдать</button>`,
    );
  }
  if (canCancelOrder(order)) {
    buttons.push(
      `<button class="secondary-action danger-action" type="button" data-order-action="cancel" data-order-action-id="${escapeHtml(
        order.backendId || order.id,
      )}">Отменить</button>`,
    );
  }
  if (canReturnOrder(order)) {
    buttons.push(
      `<button class="secondary-action" type="button" data-order-action="return" data-order-action-id="${escapeHtml(
        order.backendId || order.id,
      )}">Возврат</button>`,
    );
  }
  return `<div class="order-actions">${buttons.join("")}</div>`;
}

function renderOrders() {
  const searchInput = qs("#orderSearch");
  const statusFilter = qs("#orderStatusFilter");
  if (searchInput) searchInput.value = state.orderSearch;
  if (statusFilter) statusFilter.value = state.orderStatusFilter;

  if (orders.length === 0) {
    qs("#ordersTable").innerHTML = '<div class="empty-state">Заказов пока нет</div>';
    return;
  }

  const visibleOrders = filteredOrders();
  if (visibleOrders.length === 0) {
    qs("#ordersTable").innerHTML =
      '<div class="empty-state">Заказов по выбранному фильтру не найдено</div>';
    return;
  }

  qs("#ordersTable").innerHTML = [
    '<div class="table-row table-head"><span>№</span><span>Ученик и позиция</span><span>Склад</span><span>Статус</span><span></span></div>',
    ...visibleOrders.map(
      (order) => `
        <div class="table-row">
          <span>${escapeHtml(order.id)}</span>
          <div>
            <strong class="order-title">${escapeHtml(order.student)}</strong>
            <div class="student-meta">${escapeHtml(order.item)}</div>
          </div>
          <span>${escapeHtml(order.warehouse)}</span>
          <span class="status-badge ${order.tone}">${escapeHtml(order.status)}</span>
          ${orderActionButtons(order)}
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

  if (state.adminTab === "summary") {
    const summary = state.opsSummary || buildLocalOpsSummary();
    const statuses = summary.order_statuses || [];
    const openOrders = summary.recent_open_orders || [];
    const lowStock = summary.low_stock || [];
    qs("#adminPanel").innerHTML = `
      <div class="ops-summary-grid">
        <article>
          <span>${Number(summary.open_orders || 0)}</span>
          <strong>Открытых заказов</strong>
        </article>
        <article>
          <span>${Number(summary.pending_issue_orders || 0)}</span>
          <strong>Ожидают выдачи</strong>
        </article>
        <article>
          <span>${Number(summary.active_products || 0)}</span>
          <strong>Активных товаров</strong>
        </article>
        <article>
          <span>${Number(summary.total_reserved_quantity || 0)}</span>
          <strong>В резерве</strong>
        </article>
      </div>
      <div class="ops-summary-meta">
        <span>Tenant: ${escapeHtml(summary.tenant_slug || apiContext.tenantSlug || "demo")}</span>
        <span>Роль: ${escapeHtml(staffRoleLabel(summary.staff_role || state.role))}</span>
        <span>Складов: ${Number(summary.warehouses || 0)}</span>
        <span>Факт: ${Number(summary.total_stock_quantity || 0)} шт.</span>
      </div>
      <div class="ops-summary-columns">
        <section>
          <h3>Статусы заказов</h3>
          ${
            statuses.length
              ? statuses
                  .map(
                    (item) => `
                      <div class="ops-row">
                        <span>${escapeHtml(orderStatusLabel(item.status))}</span>
                        <strong>${Number(item.count || 0)}</strong>
                      </div>
                    `,
                  )
                  .join("")
              : '<div class="empty-state">Заказов пока нет</div>'
          }
        </section>
        <section>
          <h3>Ближайшие открытые</h3>
          ${
            openOrders.length
              ? openOrders
                  .slice(0, 6)
                  .map(
                    (order) => `
                      <div class="ops-row">
                        <span>#${escapeHtml(order.order_number || order.id || "")} ${escapeHtml(
                          order.student_name || "ученик",
                        )}</span>
                        <strong>${escapeHtml(orderStatusLabel(order.status))}</strong>
                      </div>
                    `,
                  )
                  .join("")
              : '<div class="empty-state">Открытых заказов нет</div>'
          }
        </section>
        <section>
          <h3>Остатки ниже порога</h3>
          ${
            lowStock.length
              ? lowStock
                  .slice(0, 8)
                  .map(
                    (item) => `
                      <div class="ops-row">
                        <span>${escapeHtml(
                          item.product_name || item.sku || "товар",
                        )} / ${escapeHtml(item.warehouse_name || "склад")}</span>
                        <strong>${Number(item.available_quantity || 0)} шт.</strong>
                      </div>
                    `,
                  )
                  .join("")
              : '<div class="empty-state">Проблемных остатков нет</div>'
          }
        </section>
      </div>
    `;
    return;
  }

  if (state.adminTab === "products") {
    const importingDisabled = state.productImporting ? "disabled" : "";
    const savingDisabled = state.productSaving ? "disabled" : "";
    const editing = products.find((product) => product.id === state.editingProductId);
    qs("#adminPanel").innerHTML = `
      <div class="product-form">
        <label>
          <span>SKU</span>
          <input id="productSku" value="${escapeHtml(editing?.sku || "")}" placeholder="PEN-LOGO" />
        </label>
        <label>
          <span>Название</span>
          <input id="productName" value="${escapeHtml(editing?.name || "")}" placeholder="Название товара" />
        </label>
        <label>
          <span>Категория</span>
          <input id="productCategory" value="${escapeHtml(editing?.category || "Без категории")}" />
        </label>
        <label>
          <span>Цена AC</span>
          <input id="productPrice" type="number" min="0" value="${editing?.price ?? 0}" />
        </label>
        <label>
          <span>Статус</span>
          <select id="productStatus">
            ${["active", "hidden", "archived"]
              .map(
                (status) => `<option value="${status}" ${
                  (editing?.status || "active") === status ? "selected" : ""
                }>${status}</option>`,
              )
              .join("")}
          </select>
        </label>
        <label>
          <span>Фото URL</span>
          <input id="productPhotoUrl" value="${escapeHtml(editing?.photoUrl || "")}" />
        </label>
        <label class="product-form-wide">
          <span>Описание</span>
          <input id="productDescription" value="${escapeHtml(editing?.description || "")}" />
        </label>
        <button id="productSaveButton" class="primary-action" type="button" ${savingDisabled}>
          ${state.productSaving ? "Сохранение..." : editing ? "Сохранить" : "Создать"}
        </button>
        ${
          editing
            ? '<button id="productCancelEditButton" class="secondary-action" type="button">Отмена</button>'
            : ""
        }
      </div>
      <div class="import-panel">
        <div>
          <h3>Загрузка товаров</h3>
        </div>
        <label class="file-picker">
          <input id="productImportFile" type="file" accept=".xlsx,.csv,text/csv" />
          <span>${escapeHtml(state.productImportFileName || "Выбрать файл")}</span>
        </label>
        <button id="productImportButton" class="primary-action" type="button" ${importingDisabled}>
          ${state.productImporting ? "Загрузка..." : "Загрузить"}
        </button>
      </div>
      <div class="product-admin-row table-head">
        <span>Товар</span><span>Категория</span><span>Статус</span><span>Склад</span><span>Остаток</span><span>Цена</span>
      </div>
      ${products
        .map(
          (product) => `
            <div class="product-admin-row">
              <strong>${escapeHtml(product.name)}</strong>
              <span>${escapeHtml(product.category)}</span>
              <span>${escapeHtml(product.status || "active")}</span>
              <span>${escapeHtml(product.warehouse)}</span>
              <span>${product.stock} шт.</span>
              <button class="secondary-action" type="button" data-edit-product="${escapeHtml(
                product.id,
              )}">${product.price} AC</button>
            </div>
          `,
        )
        .join("")}
    `;
    return;
  }

  if (state.adminTab === "warehouses") {
    const editing = catalogWarehouses.find((item) => item.id === state.editingWarehouseId);
    const disabled = state.warehouseSaving ? "disabled" : "";
    const rows = allCatalogWarehouses()
      .map(
        (warehouse) => `
          <div class="warehouse-row">
            <strong>${escapeHtml(warehouse.name)}</strong>
            <span>${escapeHtml(warehouse.type || "common")}</span>
            <span>${escapeHtml(warehouse.address || "Адрес не указан")}</span>
            <span>${escapeHtml(warehouse.id)}</span>
            <button class="secondary-action" type="button" data-edit-warehouse="${escapeHtml(
              warehouse.id,
            )}">Править</button>
          </div>
        `,
      )
      .join("");

    qs("#adminPanel").innerHTML = `
      <div class="warehouse-form">
        <label>
          <span>Название</span>
          <input id="warehouseName" value="${escapeHtml(editing?.name || "")}" placeholder="Склад на площадке" />
        </label>
        <label>
          <span>Slug</span>
          <input id="warehouseSlug" value="${escapeHtml(editing?.slug || "")}" placeholder="auto" />
        </label>
        <label>
          <span>Тип</span>
          <select id="warehouseType">
            ${["common", "venue", "partner", "external"]
              .map(
                (type) => `<option value="${type}" ${
                  (editing?.type || editing?.warehouse_type || "common") === type ? "selected" : ""
                }>${type}</option>`,
              )
              .join("")}
          </select>
        </label>
        <label>
          <span>Адрес</span>
          <input id="warehouseAddress" value="${escapeHtml(editing?.address || "")}" placeholder="Адрес или примечание" />
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
      <div class="warehouse-row table-head">
        <span>Склад</span><span>Тип</span><span>Адрес</span><span>ID</span><span></span>
      </div>
      ${rows || '<div class="empty-state">Складов пока нет</div>'}
    `;
    return;
  }

  if (state.adminTab === "inventory") {
    const allWarehouses = allCatalogWarehouses();
    const rows = products.flatMap((product) =>
      productWarehouses(product).map((warehouse) => {
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
            <strong>${escapeHtml(product.name)}</strong>
            <span>${escapeHtml(warehouse.name)}</span>
            <span>${warehouse.reserved} в резерве</span>
            <span>${warehouse.available} свободно</span>
            <input
              data-inventory-quantity="${escapeHtml(key)}"
              inputmode="numeric"
              min="${warehouse.reserved}"
              type="number"
              value="${warehouse.stock}"
            />
            <button
              class="secondary-action"
              type="button"
              data-adjust-inventory="${escapeHtml(key)}"
              ${saving ? "disabled" : ""}
            >${saving ? "Сохранение..." : "Сохранить"}</button>
            <select data-transfer-target="${escapeHtml(key)}">
              ${targetOptions}
            </select>
            <input
              data-transfer-quantity="${escapeHtml(key)}"
              inputmode="numeric"
              min="1"
              max="${warehouse.available}"
              type="number"
              value="${warehouse.available > 0 ? 1 : 0}"
            />
            <button
              class="secondary-action"
              type="button"
              data-transfer-inventory="${escapeHtml(key)}"
              ${saving || warehouse.available <= 0 || !targetOptions ? "disabled" : ""}
            >Перенести</button>
          </div>
        `;
      }),
    );

    qs("#adminPanel").innerHTML = `
      <div class="inventory-row table-head">
        <span>Товар</span><span>Склад</span><span>Резерв</span><span>Свободно</span><span>Факт</span><span></span><span>Куда</span><span>Кол-во</span><span></span>
      </div>
      ${rows.join("") || '<div class="empty-state">Остатков пока нет</div>'}
    `;
    return;
  }

  if (state.adminTab === "contacts") {
    if (accessLinks.length === 0) {
      qs("#adminPanel").innerHTML = '<div class="empty-state">Связей доступа пока нет</div>';
      return;
    }

    qs("#adminPanel").innerHTML = accessLinks
      .map(
        (link) => `
          <div class="contact-row">
            <strong>${escapeHtml(link.maxUserId)}</strong>
            <span>${escapeHtml(link.studentName)}</span>
            <span>${escapeHtml(link.group)}</span>
            <button class="secondary-action" type="button" data-toggle-contact="${escapeHtml(
              link.id,
            )}">${link.status === "revoked" ? "Вернуть" : "Отозвать"}</button>
          </div>
        `,
      )
      .join("");
    return;
  }

  const disabled = state.staffSaving ? "disabled" : "";
  const rows =
    staffAssignments.length === 0
      ? '<div class="empty-state">Сотрудников пока нет</div>'
      : staffAssignments
          .map(
            (assignment) => `
              <div class="staff-row">
                <strong>${escapeHtml(assignment.maxUserId)}</strong>
                <span>${escapeHtml(
                  assignment.displayName || assignment.username || "Без имени",
                )}</span>
                <span>${escapeHtml(staffRoleLabel(assignment.role))}</span>
                <span>${escapeHtml(assignmentStatusLabel(assignment.status))}</span>
                <button class="secondary-action" type="button" data-toggle-staff="${escapeHtml(
                  assignment.maxUserId,
                )}" data-staff-role="${escapeHtml(assignment.role)}">
                  ${assignment.status === "revoked" ? "Вернуть" : "Отозвать"}
                </button>
              </div>
            `,
          )
          .join("");

  qs("#adminPanel").innerHTML = `
    <div class="staff-form">
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
          <option value="teacher">Педагог</option>
          <option value="curator">Куратор</option>
          <option value="admin">Админ</option>
          <option value="partner_director">Директор партнера</option>
          <option value="superadmin">Суперадмин</option>
        </select>
      </label>
      <button id="staffSaveButton" class="primary-action" type="button" ${disabled}>
        ${state.staffSaving ? "Сохранение..." : "Выдать роль"}
      </button>
    </div>
    <div class="staff-row table-head">
      <span>MAX ID</span><span>Сотрудник</span><span>Роль</span><span>Статус</span><span></span>
    </div>
    ${rows}
  `;
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

async function saveProductFromForm() {
  const sku = qs("#productSku")?.value.trim().toUpperCase() || "";
  const name = qs("#productName")?.value.trim() || "";
  const category = qs("#productCategory")?.value.trim() || "Без категории";
  const price = Number.parseInt(qs("#productPrice")?.value || "0", 10);
  const status = qs("#productStatus")?.value || "active";
  const photoUrl = qs("#productPhotoUrl")?.value.trim() || "";
  const description = qs("#productDescription")?.value.trim() || "";
  if (sku.length < 2 || name.length < 2) {
    showNotice("Укажите SKU и название товара", "danger");
    return;
  }
  if (Number.isNaN(price) || price < 0) {
    showNotice("Цена должна быть неотрицательным числом", "danger");
    return;
  }

  const editing = products.find((product) => product.id === state.editingProductId);
  const payload = {
    sku,
    name,
    category_name: category,
    category_slug: slugify(category),
    price_astrocoins: price,
    status,
    photo_url: photoUrl || undefined,
    description: description || undefined,
  };

  if (apiContext.demoMode || !apiContext.maxUserId || state.editingProductId.startsWith("demo-")) {
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
    showNotice(`Товар "${name}" сохранен`);
    renderAll();
    return;
  }

  state.productSaving = true;
  renderAdminPanel();
  try {
    const response = await fetch("/api/v1/miniapp/products", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        max_user_id: Number(apiContext.maxUserId),
        tenant_slug: apiContext.tenantSlug || undefined,
        product_id: state.editingProductId || undefined,
        ...payload,
      }),
    });
    if (!response.ok) throw new Error(await parseApiError(response));

    const result = await response.json();
    state.editingProductId = "";
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

function addToCart(productId) {
  const product = productById(productId);
  if (!product) return;
  if ((product.status || "active") !== "active") return;
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
    backendId: `demo-order-${orderNumber}`,
    rawStatus: "reserved",
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
  const order = orders.find((item) => item.id === orderId || item.backendId === orderId);
  if (!order) return;
  setView("orders");
  const historyDetails = orderStatusHistoryDetails(order);
  const historyText = historyDetails ? `\nИстория:\n${historyDetails}` : "";
  if (historyText) {
    const itemDetails =
      Array.isArray(order.items) && order.items.length > 0
        ? order.items
            .map((item) => {
              const warehouse = item.warehouseName ? `, ${item.warehouseName}` : "";
              return `${item.productName} x${item.quantity}: ${item.totalPrice} AC${warehouse}`;
            })
            .join("\n")
        : order.item;
    showNotice(
      `Заказ №${order.id}: ${order.student}\n${itemDetails}\nСклад: ${order.warehouse}\nСтатус: ${order.status}${historyText}`,
    );
    return;
  }
  if (Array.isArray(order.items) && order.items.length > 0) {
    const itemDetails = order.items
      .map((item) => {
        const warehouse = item.warehouseName ? `, ${item.warehouseName}` : "";
        return `${item.productName} x${item.quantity}: ${item.totalPrice} AC${warehouse}`;
      })
      .join("\n");
    showNotice(
      `Заказ №${order.id}: ${order.student}\n${itemDetails}\nСклад: ${order.warehouse}\nСтатус: ${order.status}`,
    );
    return;
  }
  showNotice(
    `Заказ №${order.id}: ${order.student}, ${order.item}, склад: ${order.warehouse}, статус: ${order.status}`,
  );
}

async function updateOrderAction(orderId, action) {
  const order = orders.find((item) => item.backendId === orderId || item.id === orderId);
  if (!order) return;

  if (orderId.startsWith("demo-") || apiContext.demoMode || !apiContext.maxUserId) {
    if (action === "issue") order.rawStatus = "issued_to_student";
    else if (action === "return") order.rawStatus = "returned";
    else order.rawStatus = "cancelled";
    order.status = orderStatusLabel(order.rawStatus);
    order.tone = orderStatusTone(order.rawStatus);
    showNotice(
      {
        issue: `Заказ №${order.id} отмечен как выданный`,
        return: `Заказ №${order.id} возвращен в демо-режиме`,
        cancel: `Заказ №${order.id} отменен в демо-режиме`,
      }[action],
    );
    renderAll();
    return;
  }

  const endpoint = action === "issue" ? "issue" : action === "return" ? "return" : "cancel";
  try {
    const response = await fetch(
      `/api/v1/miniapp/orders/${encodeURIComponent(order.backendId)}/${endpoint}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          max_user_id: Number(apiContext.maxUserId),
          tenant_slug: apiContext.tenantSlug || undefined,
          comment: {
            issue: "Выдано из MAX mini app",
            return: "Возврат из MAX mini app",
            cancel: "Отменено из MAX mini app",
          }[action],
        }),
      },
    );
    if (!response.ok) throw new Error(await parseApiError(response));

    const result = await response.json();
    showNotice(
      {
        issue: `Заказ №${result.order.order_number} выдан ученику`,
        return: `Заказ №${result.order.order_number} возвращен, астрокоины зачислены`,
        cancel: `Заказ №${result.order.order_number} отменен, астрокоины возвращены`,
      }[action],
    );
    await refreshOrderAndInventoryState();
    renderAll();
  } catch (error) {
    showNotice(error.message || "Не удалось обновить заказ", "danger");
  }
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

async function saveWarehouseFromForm() {
  const name = qs("#warehouseName")?.value.trim() || "";
  const slug = qs("#warehouseSlug")?.value.trim() || "";
  const type = qs("#warehouseType")?.value || "common";
  const address = qs("#warehouseAddress")?.value.trim() || "";
  if (name.length < 2) {
    showNotice("Укажите название склада", "danger");
    return;
  }

  const payload = {
    name,
    slug: slug || slugify(name),
    warehouse_type: type,
    address: address || undefined,
  };

  if (apiContext.demoMode || !apiContext.maxUserId || state.editingWarehouseId.startsWith("demo-")) {
    const id = state.editingWarehouseId || `demo-warehouse-${payload.slug}`;
    const existingIndex = catalogWarehouses.findIndex((warehouse) => warehouse.id === id);
    const nextWarehouse = {
      id,
      slug: payload.slug,
      name: payload.name,
      type: payload.warehouse_type,
      address: payload.address || "",
    };
    if (existingIndex >= 0) catalogWarehouses[existingIndex] = nextWarehouse;
    else catalogWarehouses.push(nextWarehouse);
    state.editingWarehouseId = "";
    showNotice(`Склад "${payload.name}" сохранен`);
    renderAdminPanel();
    return;
  }

  state.warehouseSaving = true;
  renderAdminPanel();
  try {
    const response = await fetch("/api/v1/miniapp/warehouses", {
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
    const response = await fetch("/api/v1/miniapp/inventory/adjust", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        max_user_id: Number(apiContext.maxUserId),
        tenant_slug: apiContext.tenantSlug || undefined,
        product_id: product.id,
        warehouse_id: warehouse.id,
        available_quantity: nextQuantity,
        comment: "Корректировка из MAX mini app",
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
    const response = await fetch("/api/v1/miniapp/inventory/transfer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        max_user_id: Number(apiContext.maxUserId),
        tenant_slug: apiContext.tenantSlug || undefined,
        product_id: product.id,
        from_warehouse_id: source.id,
        to_warehouse_id: target.id,
        quantity,
        comment: "Перемещение из MAX mini app",
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
    const response = await fetch(`/api/v1/miniapp/access-links/${encodeURIComponent(link.id)}`, {
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

async function updateStaffAssignment({ targetMaxUserId, role, status, displayName = "" }) {
  const maxUserId = String(targetMaxUserId || "").trim();
  if (!/^\d+$/.test(maxUserId)) {
    showNotice("Укажите числовой MAX user_id сотрудника", "danger");
    return;
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
    return;
  }

  state.staffSaving = true;
  renderAdminPanel();
  try {
    const response = await fetch("/api/v1/miniapp/staff/assignments", {
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
  } catch (error) {
    showNotice(error.message || "Не удалось обновить роль сотрудника", "danger");
  } finally {
    state.staffSaving = false;
    renderAdminPanel();
  }
}

async function saveStaffAssignmentFromForm() {
  const targetMaxUserId = qs("#staffMaxUserId")?.value || "";
  const displayName = qs("#staffDisplayName")?.value.trim() || "";
  const role = qs("#staffRoleSelect")?.value || "teacher";
  await updateStaffAssignment({
    targetMaxUserId,
    role,
    status: "active",
    displayName,
  });
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
    await refreshOrderAndInventoryState();
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

  const orderActionId = target.dataset.orderActionId;
  const orderAction = target.dataset.orderAction;
  if (orderActionId && orderAction) {
    updateOrderAction(orderActionId, orderAction);
  }

  if ("groupAccrual" in target.dataset) {
    accrueGroupCoins();
  }

  const warehouseName = target.dataset.warehouseAction;
  if (warehouseName) showWarehouseAction(warehouseName);

  const editWarehouseId = target.dataset.editWarehouse;
  if (editWarehouseId) {
    state.editingWarehouseId = editWarehouseId;
    renderAdminPanel();
  }

  if (target.id === "warehouseCancelEditButton") {
    state.editingWarehouseId = "";
    renderAdminPanel();
  }

  if (target.id === "warehouseSaveButton") {
    saveWarehouseFromForm();
  }

  const transferProductId = target.dataset.transferProduct;
  if (transferProductId) cycleProductWarehouse(transferProductId);

  const inventoryKey = target.dataset.adjustInventory;
  if (inventoryKey) adjustInventory(inventoryKey);

  const transferInventoryKey = target.dataset.transferInventory;
  if (transferInventoryKey) transferInventory(transferInventoryKey);

  const contactStudentId = target.dataset.toggleContact;
  if (contactStudentId) toggleContactLink(contactStudentId);

  const staffMaxUserId = target.dataset.toggleStaff;
  const staffRole = target.dataset.staffRole;
  if (staffMaxUserId && staffRole) {
    toggleStaffAssignment(staffMaxUserId, staffRole);
  }

  if (target.id === "productImportButton") {
    importProductsFromFile();
  }

  const editProductId = target.dataset.editProduct;
  if (editProductId) {
    state.editingProductId = editProductId;
    renderAdminPanel();
  }

  if (target.id === "productCancelEditButton") {
    state.editingProductId = "";
    renderAdminPanel();
  }

  if (target.id === "productSaveButton") {
    saveProductFromForm();
  }

  if (target.id === "staffSaveButton") {
    saveStaffAssignmentFromForm();
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

  if (target.id === "orderStatusFilter") {
    state.orderStatusFilter = target.value;
    renderOrders();
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

  if (target.id === "orderSearch") {
    state.orderSearch = target.value;
    renderOrders();
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
  const results = [];
  results.push(
    await Promise.resolve(loadSession()).then(
      () => ({ status: "fulfilled" }),
      (reason) => ({ status: "rejected", reason }),
    ),
  );
  results.push(
    await Promise.resolve(loadCatalog()).then(
      () => ({ status: "fulfilled" }),
      (reason) => ({ status: "rejected", reason }),
    ),
  );
  results.push(
    await Promise.resolve(loadOpsSummary()).then(
      () => ({ status: "fulfilled" }),
      (reason) => ({ status: "rejected", reason }),
    ),
  );
  results
    .filter((result) => result.status === "rejected")
    .forEach((result) => console.warn(result.reason));

  setRole(state.role);
  setView(state.view);
  renderAll();
}

init();
