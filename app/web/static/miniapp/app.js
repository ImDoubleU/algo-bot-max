const apiContext = {
  maxUserId: positiveIntegerParam("max_user_id"),
  tenantSlug: queryParam("tenant_slug") || "",
  demoMode: queryParam("demo") === "1",
};
const sessionStartedAt = new Date();

const ROLE_VIEWS = Object.freeze({
  student: ["dashboard", "store", "cart", "orders", "wallet"],
  parent: ["dashboard", "store", "cart", "orders", "wallet"],
  teacher: ["dashboard", "orders", "wallet", "accrual", "teaching"],
  admin: ["dashboard", "orders", "wallet", "accrual", "teaching", "admin"],
});

const ROLE_DASHBOARD_ACTION = Object.freeze({
  student: { view: "store", label: "Открыть магазин" },
  parent: { view: "store", label: "Открыть магазин" },
  teacher: { view: "teaching", label: "Открыть расписание" },
  admin: { view: "admin", label: "Открыть операции" },
});

const state = {
  role: "student",
  account: null,
  staffRoles: [],
  availableRoles: ["student", "parent", "teacher", "admin"],
  view: ["dashboard", "store", "cart", "orders", "wallet", "accrual", "teaching", "admin"].includes(
    queryParam("view"),
  )
    ? queryParam("view")
    : "dashboard",
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
  favoritesOnly: false,
  inStockOnly: false,
  productSort: "recommended",
  productCategory: "all",
  refreshing: false,
  lastSyncAt: null,
  catalogLoaded: false,
  sessionLoaded: false,
  productImporting: false,
  productImportFile: null,
  productImportFileName: "",
  crmImporting: false,
  crmImportFile: null,
  crmImportFileName: "",
  crmImportPreview: null,
  productSaving: false,
  productEditorOpen: false,
  editingProductId: "",
  staffSaving: false,
  staffEditorOpen: false,
  inventorySavingKey: "",
  warehouseSaving: false,
  warehouseEditorOpen: false,
  editingWarehouseId: "",
  opsSummary: null,
  opsSummaryLoaded: false,
  teachingWorkspace: null,
  teachingLoaded: false,
  teachingLoading: false,
  scheduleEditorOpen: false,
  editingScheduleId: "",
  scheduleDayFilter: "all",
  feedbackScheduleId: "",
  generatedFeedback: "",
  generatedFeedbackId: "",
};

const demoTeachingWorkspace = {
  tenant_slug: "demo",
  courses: [
    { id: "demo-python-start", name: "Python Start 1 год", lesson_count: 32 },
    { id: "demo-game-design", name: "Геймдизайн NEW", lesson_count: 32 },
    { id: "demo-sites", name: "Создание сайтов", lesson_count: 32 },
  ],
  groups: [
    { name: "Союзный 45, вс 10:00", course_name: "Python Start 1 год", student_count: 8 },
    { name: "Гагарина 64, сб 18:00", course_name: "Геймдизайн NEW", student_count: 7 },
  ],
  schedules: [
    {
      id: "demo-schedule-1",
      group_name: "Союзный 45, вс 10:00",
      course_id: "demo-python-start",
      course_name: "Python Start 1 год",
      lesson_count: 32,
      first_lesson_date: "2026-01-11",
      weekday: 6,
      lesson_time: "10:00:00",
      duration_minutes: 90,
      lesson_mode: "group",
      lesson_place: "Союзный 45",
      current_lesson_number: 18,
      lesson_offset: 0,
      auto_feedback_enabled: true,
      parent_delivery_enabled: false,
      is_active: true,
      next_lesson_date: "2026-05-10",
      next_lesson_title: "Работа со списками",
    },
  ],
  feedback_outputs: [],
};

let students = [
  {
    id: "demo-alisa",
    lmsId: "1841",
    name: "Васильева Алиса",
    group: "Союзный 45, вс 10:00",
    teacher: "Олейник Д",
    balance: 1240,
    contact: "681",
  },
  {
    id: "demo-ivan",
    lmsId: "2417",
    name: "Петров Иван",
    group: "Гагарина 64, сб 18:00",
    teacher: "Олейник Д",
    balance: 860,
    contact: "681",
  },
  {
    id: "demo-mark",
    lmsId: "1930",
    name: "Соколов Марк",
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
    studentName: "Васильева Алиса",
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
    studentName: "Петров Иван",
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
    description: "Настольная игра о цифровом городе, логике и командной работе.",
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
    description: "Металлическая ручка Алгоритмики в подарочной упаковке.",
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
    description: "Фирменный мягкий браслет для учеников Алгоритмики.",
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
    description: "Керамическая кружка с принтом Python для будущих разработчиков.",
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
    description: "Яркий сувенир для поклонников Roblox и игровой разработки.",
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
    description: "Большой нескользящий коврик для учебы, игр и домашних проектов.",
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
    studentId: "demo-alisa",
    rawStatus: "reserved",
    student: "Васильева Алиса",
    item: "Ручка металл с лого",
    warehouse: "Назначается администратором",
    status: "Зарезервировано",
    tone: "ok",
    total: 120,
    createdAt: "2026-06-16T12:30:00Z",
    items: [
      {
        productId: "demo-pen",
        productName: "Ручка металл с лого",
        quantity: 1,
        totalPrice: 120,
        warehouseId: "",
        warehouseName: "",
      },
    ],
    statusHistory: [
      { fromStatus: "created", toStatus: "reserved", comment: "Ожидается назначение склада", createdAt: "2026-06-16T12:30:00Z" },
    ],
  },
  {
    id: "1358",
    backendId: "demo-order-1358",
    studentId: "demo-ivan",
    rawStatus: "transferred_to_teacher",
    student: "Петров Иван",
    item: "Кружка Python",
    warehouse: "Общий склад",
    status: "Передан педагогу",
    tone: "warn",
    total: 520,
    createdAt: "2026-06-15T16:10:00Z",
    items: [
      {
        productId: "demo-mug",
        productName: "Кружка Python",
        quantity: 1,
        totalPrice: 520,
        warehouseId: "demo-warehouse-common",
        warehouseName: "Общий склад",
      },
    ],
    statusHistory: [
      { fromStatus: "reserved", toStatus: "transferred_to_teacher", comment: "Передано педагогу", createdAt: "2026-06-16T09:00:00Z" },
    ],
  },
  {
    id: "1359",
    backendId: "demo-order-1359",
    studentId: "demo-mark",
    rawStatus: "problem",
    student: "Соколов Марк",
    item: "Игра Кибертаун",
    warehouse: "Не выбран",
    status: "Проблема",
    tone: "danger",
    total: 900,
    createdAt: "2026-06-14T18:45:00Z",
    items: [
      {
        productId: "demo-game",
        productName: "Игра Кибертаун",
        quantity: 1,
        totalPrice: 900,
        warehouseName: "Не выбран",
      },
    ],
    statusHistory: [
      { fromStatus: "created", toStatus: "problem", comment: "Требуется выбрать склад", createdAt: "2026-06-14T18:46:00Z" },
    ],
  },
];

let ledger = [
  ["16.06", "Начисление за проект на уроке", "+120 AC", "demo-alisa"],
  ["14.06", "Покупка: ручка металл с лого", "-120 AC", "demo-alisa"],
  ["12.06", "Бонус за домашнее задание", "+80 AC", "demo-ivan"],
  ["10.06", "Корректировка администратора", "+40 AC", "demo-mark"],
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

if (!apiContext.demoMode) {
  state.activeStudentId = "";
  state.balance = 0;
  state.favorites.clear();
  students = [];
  accessLinks = [];
  staffAssignments = [];
  products = [];
  orders = [];
  ledger = [];
  catalogWarehouses = [];
}

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

function refreshIcons() {
  if (!window.lucide?.createIcons) return;
  window.lucide.createIcons({
    attrs: {
      "aria-hidden": "true",
      "stroke-width": 2,
    },
  });
}

function queryParam(name) {
  return new URLSearchParams(window.location.search).get(name);
}

function positiveIntegerParam(name) {
  const value = queryParam(name)?.trim() || "";
  return /^[1-9]\d*$/.test(value) ? value : "";
}

function tenantTitle() {
  if (apiContext.demoMode) return "Демо-магазин";
  if (!apiContext.tenantSlug) return "Контур по умолчанию";
  return apiContext.tenantSlug
    .split(/[-_]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
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

function studentWelcome(firstName) {
  const hour = sessionStartedAt.getHours();
  const period =
    hour >= 5 && hour < 12
      ? "morning"
      : hour >= 12 && hour < 18
        ? "day"
        : hour >= 18 && hour < 23
          ? "evening"
          : "night";
  const greetings = {
    morning: "Доброе утро",
    day: "Добрый день",
    evening: "Добрый вечер",
    night: "Доброй ночи",
  };
  const messages = {
    morning: [
      "Пусть день начнется с любопытства, а продолжится маленькой победой.",
      "Утренняя новость: сегодня у тебя уже есть отличный шанс узнать что-то новое.",
      "Мини-шутка: почему компьютер утром бодрый? Он хорошо перезагрузился.",
    ],
    day: [
      "Хорошая новость: любопытство уже включено, осталось выбрать следующую цель.",
      "Пусть сегодня найдется задача, которая сначала удивит, а потом обязательно получится.",
      "Мини-шутка: почему компьютер не устал? Он вовремя перешел в спящий режим.",
    ],
    evening: [
      "Самое время похвалить себя хотя бы за одну вещь, которая сегодня получилась.",
      "Вечерняя новость: маленькие победы тоже считаются большими, если они твои.",
      "Пусть вечер будет спокойным, а новые идеи дождутся тебя до завтра.",
    ],
    night: [
      "Поздний режим: сохраняем прогресс и бережем силы для новых идей.",
      "Даже самым любопытным исследователям нужен отдых. Продолжим с новыми силами.",
      "Ночная новость: все важные открытия отлично подождут до завтра.",
    ],
  };
  const dayNumber = Math.floor(
    new Date(
      sessionStartedAt.getFullYear(),
      sessionStartedAt.getMonth(),
      sessionStartedAt.getDate(),
    ).getTime() / 86400000,
  );
  const periodMessages = messages[period];
  const message = periodMessages[(dayNumber + firstName.length) % periodMessages.length];
  return {
    title: `${greetings[period]}${firstName ? `, ${firstName}` : ""}!`,
    text: message,
  };
}

function studentsForCurrentRole() {
  if (state.role === "admin") return students;
  if (state.role === "teacher") {
    if (!apiContext.demoMode) return students;
    const teacherName = students[0]?.teacher;
    return students.filter((student) => student.teacher === teacherName);
  }
  if (apiContext.demoMode) {
    return state.role === "student" ? students.slice(0, 1) : students;
  }
  const accountMaxUserId = String(state.account?.max_user_id || apiContext.maxUserId || "");
  const linkedStudentIds = new Set(
    accessLinks
      .filter(
        (link) =>
          link.status === "active" &&
          link.role === state.role &&
          link.maxUserId === accountMaxUserId,
      )
      .map((link) => link.studentId),
  );
  if (linkedStudentIds.size > 0) {
    return students.filter((student) => linkedStudentIds.has(student.id));
  }
  return students.filter((student) => student.role === state.role);
}

function selectedStudent() {
  const roleStudents = studentsForCurrentRole();
  return (
    roleStudents.find((student) => student.id === state.activeStudentId) ||
    roleStudents[0] ||
    null
  );
}

function studentGroupName(student) {
  return student.group || "Группа не указана";
}

function sortedStudents() {
  return [...studentsForCurrentRole()].sort((left, right) => {
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

function cartKey(productId) {
  return `${productId}::auto`;
}

function cartStorageKey() {
  const tenant = apiContext.tenantSlug || (apiContext.demoMode ? "demo" : "default");
  const user = apiContext.maxUserId || "guest";
  return `algo-max-cart:${tenant}:${user}`;
}

function saveCart() {
  try {
    localStorage.setItem(cartStorageKey(), JSON.stringify(Array.from(state.cart.values())));
  } catch (error) {
    console.warn("Не удалось сохранить корзину", error);
  }
}

function restoreCart() {
  let storedItems = [];
  try {
    storedItems = JSON.parse(localStorage.getItem(cartStorageKey()) || "[]");
  } catch (error) {
    console.warn("Не удалось восстановить корзину", error);
    return;
  }
  if (!Array.isArray(storedItems)) return;

  storedItems.forEach((item) => {
    const product = productById(String(item.productId || ""));
    const available = product ? productAvailable(product) : 0;
    if (!product || available <= 0) return;
    const key = cartKey(product.id);
    const current = state.cart.get(key)?.quantity || 0;
    const quantity = clampQuantity(current + Number(item.quantity || 0), available);
    state.cart.set(key, {
      productId: product.id,
      quantity,
    });
  });
}

function favoritesStorageKey() {
  const tenant = apiContext.tenantSlug || (apiContext.demoMode ? "demo" : "default");
  const user = apiContext.maxUserId || "guest";
  return `algo-max-favorites:${tenant}:${user}`;
}

function preferencesStorageKey() {
  const tenant = apiContext.tenantSlug || (apiContext.demoMode ? "demo" : "default");
  const user = apiContext.maxUserId || "guest";
  return `algo-max-preferences:${tenant}:${user}`;
}

function savePreferences() {
  try {
    localStorage.setItem(
      preferencesStorageKey(),
      JSON.stringify({
        activeStudentId: state.activeStudentId,
        productCategory: state.productCategory,
        productSort: state.productSort,
        inStockOnly: state.inStockOnly,
        favoritesOnly: state.favoritesOnly,
        orderStatusFilter: state.orderStatusFilter,
      }),
    );
  } catch (error) {
    console.warn("Не удалось сохранить настройки mini-app", error);
  }
}

function restorePreferences() {
  try {
    const preferences = JSON.parse(localStorage.getItem(preferencesStorageKey()) || "null");
    if (!preferences || typeof preferences !== "object") return;
    if (preferences.activeStudentId) state.activeStudentId = String(preferences.activeStudentId);
    if (["recommended", "price-asc", "price-desc", "name"].includes(preferences.productSort)) {
      state.productSort = preferences.productSort;
    }
    state.productCategory = String(preferences.productCategory || "all");
    state.inStockOnly = Boolean(preferences.inStockOnly);
    state.favoritesOnly = Boolean(preferences.favoritesOnly);
    if (
      [
        "open",
        "all",
        "reserved",
        "transferred_to_teacher",
        "issued_to_student",
        "cancelled",
        "returned",
        "problem",
      ].includes(preferences.orderStatusFilter)
    ) {
      state.orderStatusFilter = preferences.orderStatusFilter;
    }
  } catch (error) {
    console.warn("Не удалось восстановить настройки mini-app", error);
  }
}

function saveFavorites() {
  try {
    localStorage.setItem(favoritesStorageKey(), JSON.stringify(Array.from(state.favorites)));
  } catch (error) {
    console.warn("Не удалось сохранить избранное", error);
  }
}

function restoreFavorites() {
  try {
    const value = localStorage.getItem(favoritesStorageKey());
    if (value === null) return;
    const productIds = JSON.parse(value);
    if (Array.isArray(productIds)) state.favorites = new Set(productIds.map(String));
  } catch (error) {
    console.warn("Не удалось восстановить избранное", error);
  }
}

function cartQuantityFor(productId) {
  return state.cart.get(cartKey(productId))?.quantity || 0;
}

function productById(productId) {
  return products.find((product) => product.id === productId) || null;
}

function activeProducts() {
  return products.filter((product) => (product.status || "active") === "active");
}

function productStatusLabel(status) {
  return {
    active: "Активен",
    hidden: "Скрыт",
    archived: "В архиве",
  }[status || "active"] || status;
}

function productAvailable(product) {
  return productWarehouses(product).reduce(
    (total, warehouse) => total + Number(warehouse.available || 0),
    0,
  );
}

function productFallbackIcon(product) {
  const text = `${product.category || ""} ${product.name || ""}`.toLowerCase();
  if (/игр|game|кибер/.test(text)) return "gamepad-2";
  if (/руч|карандаш|канцел|блокнот/.test(text)) return "pencil";
  if (/круж|бутыл|термос/.test(text)) return "cup-soda";
  if (/браслет|значок|аксессуар/.test(text)) return "sparkles";
  if (/коврик|техник|мыш/.test(text)) return "mouse";
  if (/одеж|футбол|худи/.test(text)) return "shirt";
  return "gift";
}

function productSearchText(product) {
  return [
    product.name,
    product.sku,
    product.category,
    product.categorySlug,
    product.description,
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
  const button = card.querySelector("[data-add]");
  if (!button) return;
  const availableLeft = Math.max(productAvailable(product) - cartQuantityFor(product.id), 0);
  button.disabled = availableLeft <= 0;
  const label = button.querySelector("span");
  if (label) label.textContent = availableLeft <= 0 ? "Недоступно" : "В корзину";
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

function apiErrorMessage(detail, status) {
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => apiErrorMessage(item, status))
      .filter(Boolean);
    if (messages.length > 0) return messages.join("; ");
  }
  if (detail && typeof detail === "object") {
    for (const key of ["message", "msg", "error", "detail"]) {
      if (detail[key]) return apiErrorMessage(detail[key], status);
    }
  }
  return status ? `Ошибка API: ${status}` : "Не удалось выполнить запрос";
}

async function parseApiError(response) {
  try {
    const data = await response.json();
    return apiErrorMessage(data.detail ?? data, response.status);
  } catch {
    return `Ошибка API: ${response.status}`;
  }
}

function showNotice(message, tone = "ok") {
  const notice = qs("#noticeBar");
  notice.textContent = apiErrorMessage(message);
  notice.hidden = false;
  notice.className = `notice-bar ${tone}`;
}

function hideNotice() {
  const notice = qs("#noticeBar");
  notice.hidden = true;
  notice.textContent = "";
  notice.className = "notice-bar";
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
    reserved: "Зарезервировано",
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

function primaryStaffRole(staffRoles = state.staffRoles) {
  return ["superadmin", "partner_director", "admin", "curator", "teacher"].find((role) =>
    staffRoles.includes(role),
  ) || "";
}

function canUseAdminCatalog() {
  return Boolean(apiContext.maxUserId && state.role === "admin");
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
        id: order.backendId || order.id,
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

function accessRoleLabel(role) {
  return { parent: "Родитель", student: "Ученик" }[role] || role;
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
  if (!session || !Array.isArray(session.students)) return;

  state.account = session.account || null;
  state.staffRoles = Array.isArray(session.staff_roles) ? session.staff_roles : [];

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
  if (!previousStudentExists && students.length > 0) {
    state.activeStudentId = students[0].id;
  } else if (students.length === 0) {
    state.activeStudentId = "";
  }

  orders = (session.orders || []).map((order) => ({
    id: String(order.order_number),
    backendId: String(order.id),
    studentId: String(order.student_id),
    rawStatus: order.status,
    student: order.student_name,
    item: `Заказ на ${order.total_astrocoins} AC`,
    warehouse: "Назначается администратором",
    status: orderStatusLabel(order.status),
    tone: orderStatusTone(order.status),
    total: Number(order.total_astrocoins || 0),
    createdAt: order.created_at || "",
    teacherName: order.teacher_name || "",
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
    String(entry.student_id),
  ]);

  const staffRole = staffRoleToUiRole(session.staff_roles || []);
  const hasParentRole = session.student_roles?.includes("parent");
  const availableRoles = new Set(session.student_roles || []);
  if (staffRole) availableRoles.add(staffRole);
  if (availableRoles.size === 0) availableRoles.add("student");
  state.availableRoles = Array.from(availableRoles).filter((role) =>
    ["student", "parent", "teacher", "admin"].includes(role),
  );
  state.role = staffRole || (hasParentRole ? "parent" : "student");
  state.sessionLoaded = true;
}

async function loadTeachingWorkspace() {
  if (apiContext.demoMode || !apiContext.maxUserId) {
    state.teachingWorkspace = structuredClone(demoTeachingWorkspace);
    state.teachingLoaded = true;
    return;
  }

  const response = await fetch(
    apiUrl("/api/v1/teaching/workspace", {
      max_user_id: apiContext.maxUserId,
      tenant_slug: apiContext.tenantSlug,
    }),
  );
  if (!response.ok) throw new Error(await parseApiError(response));
  state.teachingWorkspace = await response.json();
  state.teachingLoaded = true;
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

function renderSyncStatus() {
  const label = qs("#lastSyncTime");
  const button = qs("#refreshDataButton");
  if (!label || !button) return;
  if (state.refreshing) {
    label.textContent = "Обновление";
  } else if (state.lastSyncAt) {
    label.textContent = `Обновлено ${state.lastSyncAt.toLocaleTimeString("ru-RU", {
      hour: "2-digit",
      minute: "2-digit",
    })}`;
  } else {
    label.textContent = apiContext.demoMode ? "Демо-данные" : "Данные не обновлялись";
  }
  button.disabled = state.refreshing;
  button.classList.toggle("is-loading", state.refreshing);
  button.setAttribute("aria-busy", String(state.refreshing));
}

async function refreshAllData() {
  if (state.refreshing) return;
  state.refreshing = true;
  renderSyncStatus();

  const errors = [];
  const results = await Promise.allSettled([loadSession(), loadCatalog()]);
  results.forEach((result) => {
    if (result.status === "rejected") errors.push(result.reason);
  });
  try {
    await loadOpsSummary();
  } catch (error) {
    errors.push(error);
  }
  if (["teacher", "admin"].includes(state.role)) {
    try {
      await loadTeachingWorkspace();
    } catch (error) {
      errors.push(error);
    }
  }

  state.lastSyncAt = new Date();
  state.refreshing = false;
  renderAll();
  renderSyncStatus();
  if (errors.length > 0) {
    showNotice(
      errors[0]?.message || "Часть данных не удалось обновить",
      "danger",
    );
  } else {
    showNotice(apiContext.demoMode ? "Демо-данные обновлены" : "Данные обновлены");
  }
}

function setView(view) {
  const allowedViews = ROLE_VIEWS[state.role] || ROLE_VIEWS.student;
  const nextView = allowedViews.includes(view) ? view : "dashboard";
  const previousView = state.view;
  if (previousView !== nextView) hideNotice();
  state.view = nextView;
  const url = new URL(window.location.href);
  url.searchParams.set("view", nextView);
  window.history.replaceState(null, "", url);
  document.body.dataset.activeView = nextView;
  qsa(".nav-button").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.view === nextView);
  });
  qsa("[data-view-panel]").forEach((panel) => {
    panel.classList.toggle("is-active", panel.dataset.viewPanel === nextView);
  });
  const mobileMoreButton = qs("#mobileMoreButton");
  mobileMoreButton?.classList.toggle(
    "is-active",
    ["wallet", "accrual", "teaching", "admin"].includes(nextView),
  );
  closeMobileMorePanel();
  if (previousView !== nextView && window.matchMedia("(max-width: 640px)").matches) {
    window.scrollTo({ top: 0, behavior: "auto" });
  }
  if (nextView === "teaching" && !state.teachingLoaded && !state.teachingLoading) {
    state.teachingLoading = true;
    renderTeaching();
    loadTeachingWorkspace()
      .then(renderTeaching)
      .catch((error) => showNotice(error.message || "Не удалось загрузить расписание", "danger"))
      .finally(() => {
        state.teachingLoading = false;
        renderTeaching();
      });
  }
  renderStatus();
}

function setRole(role) {
  if (!state.availableRoles.includes(role)) return;
  const roleChanged = state.role !== role;
  state.role = role;
  if (roleChanged) {
    state.studentGroupFilter = "all";
    state.accrualGroup = "all";
    state.accrualNameFilter = "";
  }
  const roleStudents = studentsForCurrentRole();
  if (!roleStudents.some((student) => student.id === state.activeStudentId)) {
    state.activeStudentId = roleStudents[0]?.id || "";
  }
  document.body.dataset.activeRole = role;
  qsa(".role-button").forEach((button) => {
    if (button.dataset.role === "admin") {
      button.textContent = primaryStaffRole() === "partner_director" ? "Директор" : "Админ";
    }
    button.hidden = !state.availableRoles.includes(button.dataset.role);
    button.classList.toggle("is-active", button.dataset.role === role);
  });
  const roleSwitch = qs(".role-switch");
  if (roleSwitch) roleSwitch.hidden = state.availableRoles.length <= 1;

  const allowedViews = ROLE_VIEWS[role] || ROLE_VIEWS.student;
  qsa(".nav-button[data-view]").forEach((button) => {
    const allowed = allowedViews.includes(button.dataset.view);
    button.disabled = !allowed;
    button.hidden = !allowed;
  });
  qsa("[data-view-jump]").forEach((button) => {
    const allowed = allowedViews.includes(button.dataset.viewJump);
    button.disabled = !allowed;
    button.hidden = !allowed;
  });

  const dashboardAction = qs("#dashboardPrimaryAction");
  const dashboardActionConfig = ROLE_DASHBOARD_ACTION[role] || ROLE_DASHBOARD_ACTION.student;
  if (dashboardAction) {
    dashboardAction.dataset.viewJump = dashboardActionConfig.view;
    dashboardAction.textContent = dashboardActionConfig.label;
    dashboardAction.hidden = false;
    dashboardAction.disabled = false;
  }

  const cartButton = qs("#openCartButton");
  if (cartButton) cartButton.hidden = !allowedViews.includes("cart");
  const moreViews = ["wallet", "accrual", "teaching", "admin"];
  const mobileMoreButton = qs("#mobileMoreButton");
  if (mobileMoreButton) {
    mobileMoreButton.hidden = !moreViews.some((view) => allowedViews.includes(view));
  }

  if (!allowedViews.includes(state.view)) {
    setView("dashboard");
  }
  renderAll();
  if (
    !apiContext.demoMode &&
    !state.opsSummaryLoaded &&
    role === "admin"
  ) {
    loadOpsSummary()
      .then(renderAdminPanel)
      .catch((error) => console.warn(error));
  }
}

function closeMobileMorePanel() {
  const panel = qs("#mobileMorePanel");
  if (panel) panel.hidden = true;
}

function toggleMobileMorePanel() {
  const panel = qs("#mobileMorePanel");
  if (!panel) return;
  panel.hidden = !panel.hidden;
}

function setActiveStudent(studentId) {
  if (!studentsForCurrentRole().some((student) => student.id === studentId)) return;
  state.activeStudentId = studentId;
  savePreferences();
  renderAll();
}

function renderStatus() {
  const student = selectedStudent();
  const accountName = state.account?.display_name?.trim() || "";
  const roleStudents = studentsForCurrentRole();
  const linkedCount = roleStudents.length;
  const statusStrip = qs(".status-strip");
  const studentContext = qs("#studentContext");
  if (studentContext) studentContext.hidden = linkedCount === 0;
  if (statusStrip) statusStrip.classList.toggle("has-no-students", linkedCount === 0);
  const labels = {
    student: student ? `${student.name}, ученик` : "Ученик",
    parent: accountName
      ? `${accountName}, родитель`
      : linkedCount > 0
        ? `Родитель, ${linkedCount} учен.`
        : "Родитель",
    teacher: accountName ? `${accountName}, педагог` : "Педагог",
    admin:
      primaryStaffRole() === "partner_director"
        ? accountName
          ? `${accountName}, директор`
          : "Директор"
        : accountName
          ? `${accountName}, администратор`
          : "Администратор",
  };

  state.balance = student?.balance || 0;
  qs("#profileTitle").textContent = labels[state.role] || "Профиль";
  const profileInitial = qs("#profileInitial");
  if (profileInitial) {
    const profileName = student?.name || accountName || labels[state.role] || "А";
    profileInitial.textContent = profileName.trim().charAt(0).toUpperCase() || "А";
  }
  const contextLabel = qs("#studentContextLabel");
  if (contextLabel) {
    contextLabel.textContent = {
      store: "Получатель заказа",
      cart: "Получатель",
      wallet: "История ученика",
    }[state.view] || "Ученик";
  }
  qs("#balanceValue").textContent = state.balance;
  const storeAudience = qs("#storeAudience");
  if (storeAudience) {
    storeAudience.textContent = student
      ? `${student.name} · ${state.balance} AC доступно`
      : "Выберите ученика, чтобы оформить заказ";
  }

  const dashboardTitle = {
    student: "Мои результаты",
    parent: "Дети и заказы",
    teacher: "Рабочий день",
    admin: "Филиал сегодня",
  }[state.role] || "Мои результаты";
  const nameParts = student?.name?.trim().split(/\s+/).filter(Boolean) || [];
  const firstName = nameParts.length > 1 ? nameParts[1] : nameParts[0] || "";
  const welcome = studentWelcome(firstName);
  const spotlightByRole = {
    student: {
      kicker: "Личный кабинет",
      title: welcome.title,
      text: welcome.text,
    },
    parent: {
      kicker: "Семейный кабинет",
      title: firstName ? `Результаты и награды: ${firstName}` : "Результаты детей",
      text: "Переключайтесь между детьми и следите за заказами.",
    },
    teacher: {
      kicker: "Рабочий день",
      title: "Группы и начисления под рукой",
      text: "Только ваши ученики, расписание и обратная связь.",
    },
    admin: {
      kicker: "Управление филиалом",
      title: "Данные филиала в одном контуре",
      text: "Импорт, сотрудники, склад и заказы без лишних переходов.",
    },
  };
  const spotlight = spotlightByRole[state.role] || spotlightByRole.student;
  if (state.role === "admin" && primaryStaffRole() === "partner_director") {
    spotlight.kicker = "Кабинет директора";
  }
  qs("#dashboardTitle").textContent = dashboardTitle;
  qs("#dashboardRoleKicker").textContent = spotlight.kicker;
  qs("#dashboardSpotlightTitle").textContent = spotlight.title;
  qs("#dashboardSpotlightText").textContent = spotlight.text;
  qs("#dashboardOrdersTitle").textContent = {
    student: "Мои заказы",
    parent: "Заказы детей",
    teacher: "Заказы к выдаче",
    admin: "Заказы к выдаче",
  }[state.role] || "Заказы";
  qs("#studentPanelTitle").textContent = {
    student: "Мой профиль",
    parent: "Мои дети",
    teacher: "Мои ученики",
    admin: "Ученики и группы",
  }[state.role] || "Ученики";
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
  select.disabled = roleStudents.length <= 1;

  const groupFilter = qs("#studentGroupFilter");
  if (groupFilter) {
    groupFilter.hidden = state.role === "student";
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
              const active = student.id === state.activeStudentId;
              return `
                <div class="student-row ${active ? "is-active" : ""}">
                  <div>
                    <strong>${escapeHtml(student.name)}</strong>
                    ${
                      state.role === "teacher"
                        ? ""
                        : `<div class="student-meta">${escapeHtml(student.teacher)}</div>`
                    }
                  </div>
                  <span class="soft-badge">${student.balance} AC</span>
                  ${
                    roleStudents.length > 1
                      ? `<button class="secondary-action compact" type="button" data-select-student="${escapeHtml(
                          student.id,
                        )}">${active ? "Выбран" : "Выбрать"}</button>`
                      : ""
                  }
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

  const visible = ordersForCurrentRole().slice(0, 4);
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
  const categories = [...new Set(activeProducts().map((product) => product.category))];
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
          >${escapeHtml(label)}</button>
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
  state.inStockOnly = qs("#inStockOnly").checked;
  const visible = activeProducts()
    .filter((product) => {
      const matchesSearch = productMatchesSearch(product, search);
      const matchesCategory = category === "all" || product.category === category;
      const matchesFavorite = !state.favoritesOnly || state.favorites.has(product.id);
      const matchesStock = !state.inStockOnly || productAvailable(product) > 0;
      return matchesSearch && matchesCategory && matchesFavorite && matchesStock;
    })
    .sort((left, right) => {
      if (sort === "price-asc") return left.price - right.price;
      if (sort === "price-desc") return right.price - left.price;
      if (sort === "name") return left.name.localeCompare(right.name, "ru");
      return 0;
    });

  const favoritesCount = activeProducts().filter((product) =>
    state.favorites.has(product.id),
  ).length;
  const favoritesFilter = qs("#favoritesFilter");
  favoritesFilter.setAttribute("aria-pressed", String(state.favoritesOnly));
  qs("#favoritesCount").textContent = favoritesCount;
  qs("#catalogResultCount").textContent = productCountLabel(visible.length);

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
      const availableLeft = Math.max(available - cartQuantityFor(product.id), 0);
      const disabled = availableLeft <= 0;
      const favorite = state.favorites.has(product.id);
      const stockText =
        availableLeft <= 0
          ? "Нет в наличии"
          : availableLeft <= 5
            ? `Осталось ${availableLeft}`
            : "В наличии";
      return `
        <article class="product-card" data-product-card="${escapeHtml(product.id)}">
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
          </div>
          <div class="product-card-footer">
            <strong>${product.price} <span>AC</span></strong>
            <button
              class="primary-action"
              type="button"
              data-add="${escapeHtml(product.id)}"
              ${disabled ? "disabled" : ""}
            >
              <i data-lucide="shopping-bag"></i>
              <span>${disabled ? "Недоступно" : "В корзину"}</span>
            </button>
          </div>
        </article>
      `;
    })
    .join("");
  refreshIcons();
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
    list.innerHTML = `
      <div class="empty-state cart-empty-state">
        <strong>Корзина пока пустая</strong>
        <button class="primary-action" type="button" data-view-jump="store">Перейти в магазин</button>
      </div>
    `;
  } else {
    list.innerHTML = Array.from(state.cart.entries())
      .map(([key, item]) => {
        const product = productById(item.productId);
        if (!product) return "";
        const maxQuantity = Math.max(productAvailable(product), item.quantity);
        return `
          <div class="cart-row">
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
              </div>
            </div>
            <div class="cart-unit-price">
              <span>Цена</span>
              <strong>${product.price} AC</strong>
            </div>
            <div class="quantity-control">
              <span>Количество</span>
              <input
                type="number"
                min="1"
                max="${maxQuantity}"
                value="${item.quantity}"
                data-cart-quantity="${escapeHtml(key)}"
              />
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
  qs("#cartAffordabilityLabel").textContent = remaining >= 0 ? "Останется" : "Не хватает";
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
    <p class="checkout-reservation-note">
      После оформления администратор назначит склад. До этого заказ будет отмечен как
      «Зарезервировано».
    </p>
    <div class="checkout-total">
      <span>К списанию</span>
      <strong>${total} AC</strong>
    </div>
  `;
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

function syncProductDialogControls() {
  const dialog = qs("#productDialog");
  const product = productById(dialog.dataset.productId || "");
  if (!product) return;

  const quantityInput = qs("#productDialogQuantity");
  const addButton = qs("#productDialogAddButton");
  const stock = qs("#productDialogStock");
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
      <div class="product-dialog-controls">
        <label>
          <span>Количество</span>
          <input id="productDialogQuantity" type="number" min="1" value="1" />
        </label>
      </div>
      <div id="productDialogStock" class="product-dialog-stock"></div>
    </div>
  `;
  dialog.hidden = false;
  syncDialogBodyClass();
  syncProductDialogControls();
  refreshIcons();
  qs("#productDialogAddButton").focus();
}

function closeProductDialog() {
  const dialog = qs("#productDialog");
  if (dialog.hidden) return;
  dialog.hidden = true;
  dialog.dataset.productId = "";
  syncDialogBodyClass();
}

function isOpenOrderStatus(status) {
  return ["created", "reserved", "transferred_to_teacher"].includes(status);
}

function orderHasAssignedWarehouses(order) {
  return (
    Array.isArray(order.items) &&
    order.items.length > 0 &&
    order.items.every((item) => Boolean(item.warehouseId))
  );
}

function canAssignOrderWarehouses(order) {
  return state.role === "admin" && order.rawStatus === "reserved" && !orderHasAssignedWarehouses(order);
}

function canIssueOrder(order) {
  return (
    ["teacher", "admin"].includes(state.role) &&
    ["reserved", "transferred_to_teacher"].includes(order.rawStatus) &&
    orderHasAssignedWarehouses(order)
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

function orderActionButtons(order, includeOpen = true) {
  const buttons = [];

  if (includeOpen) {
    const label = canAssignOrderWarehouses(order) ? "Назначить склад" : "Подробнее";
    buttons.push(
      `<button class="secondary-action" type="button" data-open-order="${escapeHtml(
        order.backendId || order.id,
      )}">${label}</button>`,
    );
  }

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
  return buttons.length ? `<div class="order-actions">${buttons.join("")}</div>` : "";
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

function renderOrders() {
  const searchInput = qs("#orderSearch");
  const statusFilter = qs("#orderStatusFilter");
  if (searchInput) searchInput.value = state.orderSearch;
  if (statusFilter) statusFilter.value = state.orderStatusFilter;

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
      const total = orderTotalValue(order);
      return `
        <article class="order-card" data-tone="${escapeHtml(order.tone)}">
          <div class="order-card-main">
            <div class="order-card-head">
              <strong class="order-number">Заказ №${escapeHtml(order.id)}</strong>
              <span class="status-badge ${order.tone}">${escapeHtml(order.status)}</span>
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
              ${date ? `<span>${escapeHtml(date)}</span>` : ""}
            </div>
          </div>
          ${orderActionButtons(order)}
        </article>
      `;
    })
    .join("");
}

function renderLedger() {
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

  const groupReason = qs("#groupAccrualReason");
  const groupAmount = qs("#groupAccrualAmount");
  const selectedGroupReason = groupReason.value;
  const selectedGroupAmount = groupAmount.value;
  groupReason.innerHTML = [
    '<option value="">Выберите причину</option>',
    ...accrualReasons.map(
      (reason) => `<option value="${escapeHtml(reason)}">${escapeHtml(reason)}</option>`,
    ),
  ].join("");
  groupAmount.innerHTML = [
    '<option value="">Выберите сумму</option>',
    ...accrualAmounts.map((amount) => `<option value="${amount}">+${amount} AC</option>`),
  ].join("");
  groupReason.value = selectedGroupReason;
  groupAmount.value = selectedGroupAmount;

  const normalizedName = state.accrualNameFilter.trim().toLowerCase();
  const visibleStudents = studentsForGroup(state.accrualGroup).filter((student) =>
    student.name.toLowerCase().includes(normalizedName),
  );
  const groupFilterActive = state.accrualGroup !== "all";
  const bulkHint = qs(".accrual-bulk p");
  if (bulkHint) {
    bulkHint.textContent = groupFilterActive
      ? `${visibleStudents.length} учен. в выбранной группе`
      : "Сначала выберите конкретную группу в фильтре.";
  }

  if (visibleStudents.length === 0) {
    studentList.innerHTML = '<div class="empty-state">Ученики не найдены</div>';
    return;
  }

  studentList.innerHTML = visibleStudents
    .map(
      (student) => `
        <article class="accrual-card ${groupFilterActive ? "is-group-filtered" : ""}">
          <div class="accrual-student-head">
            <div class="accrual-student-mark">${escapeHtml(student.name.slice(0, 1))}</div>
            <div>
              <strong>${escapeHtml(student.name)}</strong>
            </div>
            <span class="soft-badge">${student.balance} AC</span>
          </div>
          ${
            groupFilterActive
              ? ""
              : `<div class="accrual-student-meta"><span>${escapeHtml(
                  studentGroupName(student),
                )}</span>${
                  state.role === "teacher"
                    ? ""
                    : `<span>${escapeHtml(student.teacher)}</span>`
                }</div>`
          }
          <div class="accrual-card-controls">
            <label>
              <span>Причина</span>
              <select data-accrual-reason="${escapeHtml(student.id)}">
                <option value="">Выберите причину</option>
                ${accrualReasons
                  .map(
                    (reason) => `<option value="${escapeHtml(reason)}">${escapeHtml(reason)}</option>`,
                  )
                  .join("")}
              </select>
            </label>
            <label>
              <span>Сумма</span>
              <select data-accrual-amount="${escapeHtml(student.id)}">
                <option value="">Сумма</option>
                ${accrualAmounts
                  .map((amount) => `<option value="${amount}">+${amount} AC</option>`)
                  .join("")}
              </select>
            </label>
            <button
              class="primary-action"
              type="button"
              data-accrue-student="${escapeHtml(student.id)}"
            >Начислить</button>
          </div>
        </article>
      `,
    )
    .join("");
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

  if (state.adminTab === "summary") {
    const summary = state.opsSummary || buildLocalOpsSummary();
    const statuses = summary.order_statuses || [];
    const openOrders = summary.recent_open_orders || [];
    const lowStock = summary.low_stock || [];
    qs("#adminPanel").innerHTML = `
      <div class="ops-quick-actions">
        <button class="primary-action" type="button" data-ops-jump="orders">
          Заказы к выдаче
        </button>
        <button class="secondary-action" type="button" data-ops-jump="inventory">
          Проверить остатки
        </button>
        <button class="secondary-action" type="button" data-ops-jump="products">
          Управление товарами
        </button>
      </div>
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
          <h3>Остатки ниже порога</h3>
          ${
            lowStock.length
              ? lowStock
                  .slice(0, 8)
                  .map(
                    (item) => `
                      <button class="ops-row ops-row-action" type="button" data-ops-jump="inventory">
                        <span>${escapeHtml(
                          item.product_name || item.sku || "товар",
                        )} / ${escapeHtml(item.warehouse_name || "склад")}</span>
                        <strong>${Number(item.available_quantity || 0)} шт.</strong>
                      </button>
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
    const editorOpen = state.productEditorOpen || Boolean(editing);
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
      ${editorOpen ? `
      <div class="product-form admin-editor">
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
          <textarea id="productDescription" rows="3">${escapeHtml(
            editing?.description || "",
          )}</textarea>
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
      ` : ""}
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
      <div class="admin-card-list">
      ${products
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
                  <span>${product.stock} шт.</span>
                  <span>${escapeHtml(product.warehouse)}</span>
                </div>
              </div>
              <div class="admin-entity-actions">
                <strong>${product.price} AC</strong>
                <button class="secondary-action" type="button" data-edit-product="${escapeHtml(
                  product.id,
                )}">Редактировать</button>
              </div>
            </article>
          `,
        )
        .join("")}
      </div>
    `;
    return;
  }

  if (state.adminTab === "crm") {
    const preview = state.crmImportPreview;
    const busy = state.crmImporting ? "disabled" : "";
    qs("#adminPanel").innerHTML = `
      <div class="admin-section-toolbar">
        <div>
          <h3>Данные CRM</h3>
          <span>${escapeHtml(apiContext.tenantSlug || "Текущий филиал")}</span>
        </div>
      </div>
      <div class="import-panel crm-import-panel">
        <div>
          <h3>Ученики и группы</h3>
        </div>
        <label class="file-picker">
          <input id="crmImportFile" type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" />
          <span>${escapeHtml(state.crmImportFileName || "Выбрать XLSX")}</span>
        </label>
        <button id="crmPreviewButton" class="secondary-action" type="button" ${busy}>
          ${state.crmImporting ? "Обработка..." : "Проверить файл"}
        </button>
      </div>
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
                  <span>Без имени: ${Number(preview.rows_without_student_name || 0)}</span>
                </div>
                <button id="crmImportButton" class="primary-action" type="button" ${busy}>
                  ${state.crmImporting ? "Импорт..." : "Импортировать"}
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
            <div class="warehouse-type-mark">${escapeHtml(
              String(warehouse.type || "common").slice(0, 1).toUpperCase(),
            )}</div>
            <div class="admin-entity-main">
              <div class="admin-entity-title">
                <strong>${escapeHtml(warehouse.name)}</strong>
                <span class="soft-badge">${escapeHtml(warehouse.type || "common")}</span>
              </div>
              <div class="admin-entity-meta">
                <span>${escapeHtml(warehouse.address || "Адрес не указан")}</span>
                <span>${escapeHtml(warehouse.slug || warehouse.id)}</span>
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
          <span>${allCatalogWarehouses().length} складов в текущем контуре</span>
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
      ` : ""}
      <div class="admin-card-list">
        ${rows || '<div class="empty-state">Складов пока нет</div>'}
      </div>
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
      }),
    );

    qs("#adminPanel").innerHTML = `
      <div class="inventory-list">
        ${rows.join("") || '<div class="empty-state">Остатков пока нет</div>'}
      </div>
    `;
    return;
  }

  if (state.adminTab === "contacts") {
    const activeLinks = accessLinks.filter((link) => link.status === "active").length;
    const rows = accessLinks
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
              <button
                class="secondary-action ${link.status === "active" ? "danger-action" : ""}"
                type="button"
                data-toggle-contact="${escapeHtml(link.id)}"
              >${link.status === "revoked" ? "Восстановить" : "Отозвать"}</button>
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
      <div class="admin-card-list">
        ${rows || '<div class="empty-state">Связей доступа пока нет</div>'}
      </div>
    `;
    return;
  }

  const disabled = state.staffSaving ? "disabled" : "";
  const activeStaff = staffAssignments.filter((item) => item.status === "active").length;
  const rows =
    staffAssignments.length === 0
      ? '<div class="empty-state">Сотрудников пока нет</div>'
      : staffAssignments
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
                  <button
                    class="secondary-action ${
                      assignment.status === "active" ? "danger-action" : ""
                    }"
                    type="button"
                    data-toggle-staff="${escapeHtml(assignment.maxUserId)}"
                    data-staff-role="${escapeHtml(assignment.role)}"
                  >${assignment.status === "revoked" ? "Восстановить" : "Отозвать"}</button>
                </div>
              </article>
            `,
          )
          .join("");

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
      <button id="staffCancelButton" class="secondary-action" type="button">Отмена</button>
    </div>
    ` : ""}
    <div class="admin-card-list">
      ${rows}
    </div>
  `;
}

const weekdayNames = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"];

function teachingWorkspace() {
  return state.teachingWorkspace || { courses: [], groups: [], schedules: [], feedback_outputs: [] };
}

function formatTeachingDate(value) {
  if (!value) return "Дата не задана";
  return new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long" }).format(
    new Date(`${value}T12:00:00`),
  );
}

function renderTeaching() {
  const workspace = teachingWorkspace();
  const summary = qs("#teachingSummary");
  if (!summary) return;
  const active = workspace.schedules.filter((item) => item.is_active);
  const nearest = [...active].sort((a, b) =>
    `${a.next_lesson_date}${a.lesson_time}`.localeCompare(`${b.next_lesson_date}${b.lesson_time}`),
  )[0];
  summary.innerHTML = `
    <article><strong>${active.length}</strong><span>активных групп</span></article>
    <article><strong>${active.filter((item) => item.auto_feedback_enabled).length}</strong><span>автоматических ОС</span></article>
    <article><strong>${nearest ? escapeHtml(nearest.lesson_time.slice(0, 5)) : "--:--"}</strong><span>${nearest ? escapeHtml(nearest.group_name) : "занятий пока нет"}</span></article>`;
  renderScheduleEditor();
  renderScheduleList();
  renderFeedbackHistory();
}

function renderScheduleEditor() {
  const editor = qs("#scheduleEditor");
  if (!editor) return;
  editor.hidden = !state.scheduleEditorOpen;
  if (!state.scheduleEditorOpen) return;
  const workspace = teachingWorkspace();
  const item = workspace.schedules.find((schedule) => schedule.id === state.editingScheduleId);
  const today = new Date().toISOString().slice(0, 10);
  const scheduledGroups = new Set(
    workspace.schedules
      .filter((schedule) => schedule.id !== item?.id)
      .map((schedule) => schedule.group_name),
  );
  const groupNames = [...new Set([
    ...(item?.group_name ? [item.group_name] : []),
    ...workspace.groups
      .map((group) => group.name)
      .filter((groupName) => !scheduledGroups.has(groupName)),
  ])];
  const groupField = groupNames.length
    ? `<select id="scheduleGroupName"><option value="">Выберите группу</option>${groupNames
        .map(
          (groupName) =>
            `<option value="${escapeHtml(groupName)}" ${groupName === item?.group_name ? "selected" : ""}>${escapeHtml(groupName)}</option>`,
        )
        .join("")}</select>`
    : '<input id="scheduleGroupName" value="" placeholder="Название группы" />';
  editor.innerHTML = `
    <div class="schedule-editor-head"><div><p class="eyebrow">${item ? "Редактирование" : "Новая группа"}</p><h3>${item ? escapeHtml(item.group_name) : "Добавить занятие"}</h3></div><button class="icon-button" type="button" data-close-schedule title="Закрыть">×</button></div>
    <div class="schedule-form-grid">
      <label class="schedule-field-wide"><span>Группа</span>${groupField}</label>
      <label class="schedule-field-wide"><span>Курс</span><select id="scheduleCourseId">${workspace.courses.map((course) => `<option value="${escapeHtml(course.id)}" ${course.id === item?.course_id ? "selected" : ""}>${escapeHtml(course.name)} · ${course.lesson_count} уроков</option>`).join("")}</select></label>
      <label><span>Первое занятие</span><input id="scheduleFirstDate" type="date" value="${item?.first_lesson_date || today}" /></label>
      <label><span>Время</span><input id="scheduleTime" type="time" value="${item?.lesson_time?.slice(0, 5) || "10:00"}" /></label>
      <label><span>Формат</span><select id="scheduleMode"><option value="group">Группа</option><option value="individual" ${item?.lesson_mode === "individual" ? "selected" : ""}>Индивидуально</option></select></label>
      <label><span>Место</span><input id="schedulePlace" value="${escapeHtml(item?.lesson_place || "offline")}" placeholder="Адрес или online" /></label>
      <label><span>Текущий урок</span><input id="scheduleLessonNumber" type="number" min="1" value="${item?.current_lesson_number || 1}" /></label>
      <label><span>Длительность</span><select id="scheduleDuration"><option value="90">90 минут</option><option value="60" ${item?.duration_minutes === 60 ? "selected" : ""}>60 минут</option><option value="120" ${item?.duration_minutes === 120 ? "selected" : ""}>120 минут</option></select></label>
    </div>
    <div class="schedule-toggle-list">
      <label class="schedule-toggle"><input id="scheduleAutoFeedback" type="checkbox" ${item?.auto_feedback_enabled === false ? "" : "checked"} /><span>Автоматически готовить ОС после занятия</span></label>
      <label class="schedule-toggle"><input id="scheduleParentDelivery" type="checkbox" ${item?.parent_delivery_enabled ? "checked" : ""} /><span>Отправлять готовую ОС связанным родителям</span></label>
    </div>
    <div class="schedule-editor-actions"><button class="secondary-action" type="button" data-close-schedule>Отмена</button><button id="scheduleSaveButton" class="primary-action" type="button">Сохранить расписание</button></div>`;
}

function renderScheduleList() {
  const list = qs("#scheduleList");
  if (!list) return;
  const items = teachingWorkspace().schedules.filter(
    (item) => state.scheduleDayFilter === "all" || String(item.weekday) === state.scheduleDayFilter,
  );
  if (state.teachingLoading) return void (list.innerHTML = '<div class="empty-state">Загружаем расписание...</div>');
  if (items.length === 0) return void (list.innerHTML = '<div class="empty-state">Добавьте первую группу и выберите курс.</div>');
  list.innerHTML = items.map((item) => `
    <article class="schedule-card ${item.is_active ? "" : "is-paused"}">
      <div class="schedule-time"><strong>${escapeHtml(item.lesson_time.slice(0, 5))}</strong><span>${escapeHtml(weekdayNames[item.weekday] || "")}</span></div>
      <div class="schedule-main"><div class="schedule-card-title"><h3>${escapeHtml(item.group_name)}</h3><span class="soft-badge">Урок ${item.current_lesson_number}/${item.lesson_count}</span></div><p>${escapeHtml(item.course_name)}</p><div class="schedule-next"><strong>${formatTeachingDate(item.next_lesson_date)}</strong><span>${escapeHtml(item.next_lesson_title || "Тема будет определена курсом")}</span></div><div class="schedule-flags"><span>${escapeHtml(item.lesson_place)}</span><span>${item.auto_feedback_enabled ? "Авто-ОС включена" : "ОС вручную"}</span><span>${item.parent_delivery_enabled ? "Доставка родителям" : "Без автоотправки"}</span></div></div>
      <div class="schedule-actions"><button class="primary-action" type="button" data-feedback-schedule="${escapeHtml(item.id)}">Подготовить ОС</button><button class="secondary-action" type="button" data-edit-schedule="${escapeHtml(item.id)}">Изменить</button></div>
    </article>`).join("");
}

function renderFeedbackHistory() {
  const list = qs("#feedbackHistory");
  if (!list) return;
  const outputs = teachingWorkspace().feedback_outputs;
  if (outputs.length === 0) return void (list.innerHTML = '<div class="empty-state">Сформированные обратные связи появятся здесь.</div>');
  list.innerHTML = outputs.slice(0, 10).map((item) => `<button class="feedback-history-row" type="button" data-open-feedback="${escapeHtml(item.id)}"><span><strong>${escapeHtml(item.group_name)}</strong><small>${formatTeachingDate(item.lesson_date)} · урок ${item.lesson_number}</small></span><span>›</span></button>`).join("");
}

function openScheduleEditor(scheduleId = "") {
  state.editingScheduleId = scheduleId;
  state.scheduleEditorOpen = true;
  renderTeaching();
  qs("#scheduleEditor")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function closeScheduleEditor() {
  state.scheduleEditorOpen = false;
  state.editingScheduleId = "";
  renderTeaching();
}

async function saveTeachingSchedule() {
  const groupName = qs("#scheduleGroupName")?.value.trim();
  const courseId = qs("#scheduleCourseId")?.value;
  if (!groupName || !courseId) return showNotice("Укажите группу и курс", "danger");
  const payload = { max_user_id: Number(apiContext.maxUserId || 1), tenant_slug: apiContext.tenantSlug || null, schedule_id: state.editingScheduleId || null, group_name: groupName, course_id: courseId, first_lesson_date: qs("#scheduleFirstDate").value, lesson_time: qs("#scheduleTime").value, duration_minutes: Number(qs("#scheduleDuration").value), lesson_mode: qs("#scheduleMode").value, lesson_place: qs("#schedulePlace").value.trim() || "offline", current_lesson_number: Number(qs("#scheduleLessonNumber").value || 1), lesson_offset: 0, auto_feedback_enabled: qs("#scheduleAutoFeedback").checked, parent_delivery_enabled: qs("#scheduleParentDelivery").checked, is_active: true };
  const button = qs("#scheduleSaveButton");
  button.disabled = true;
  button.textContent = "Сохраняем...";
  try {
    if (apiContext.demoMode || !apiContext.maxUserId) {
      const index = teachingWorkspace().schedules.findIndex((item) => item.id === payload.schedule_id);
      const course = teachingWorkspace().courses.find((item) => item.id === courseId);
      const firstDate = new Date(`${payload.first_lesson_date}T12:00:00`);
      const saved = { ...payload, id: payload.schedule_id || `demo-schedule-${Date.now()}`, course_name: course.name, lesson_count: course.lesson_count, weekday: (firstDate.getDay() + 6) % 7, next_lesson_date: payload.first_lesson_date, next_lesson_title: "Следующая тема курса" };
      if (index >= 0) teachingWorkspace().schedules[index] = saved;
      else teachingWorkspace().schedules.push(saved);
    } else {
      const response = await fetch("/api/v1/teaching/schedules", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      if (!response.ok) throw new Error(await parseApiError(response));
      await loadTeachingWorkspace();
    }
    closeScheduleEditor();
    showNotice("Расписание сохранено");
  } catch (error) {
    showNotice(error.message || "Не удалось сохранить расписание", "danger");
    button.disabled = false;
    button.textContent = "Сохранить расписание";
  }
}

function openFeedbackDialog(scheduleId = "", outputId = "") {
  const output = teachingWorkspace().feedback_outputs.find((item) => item.id === outputId);
  const schedule = teachingWorkspace().schedules.find((item) => item.id === (scheduleId || output?.schedule_id));
  if (!schedule && !output) return;
  state.feedbackScheduleId = schedule?.id || output.schedule_id;
  state.generatedFeedback = output?.feedback_text || "";
  state.generatedFeedbackId = output?.id || "";
  qs("#feedbackDialogTitle").textContent = output ? output.group_name : schedule.group_name;
  qs("#feedbackDialogContent").innerHTML = output ? `<textarea id="feedbackResult" class="feedback-result" readonly>${escapeHtml(output.feedback_text)}</textarea>` : `<div class="feedback-options"><label><span>Кто отсутствовал</span><input id="feedbackAbsent" placeholder="Имена через запятую" /></label><label class="schedule-toggle"><input id="feedbackRepetition" type="checkbox" /><span>Повторяли прошлую тему</span></label><p>Урок ${schedule.current_lesson_number}: ${escapeHtml(schedule.next_lesson_title || schedule.course_name)}</p></div>`;
  qs("#copyFeedbackButton").hidden = !state.generatedFeedback;
  qs("#sendFeedbackButton").hidden = !state.generatedFeedback;
  qs("#generateFeedbackButton").hidden = Boolean(output);
  qs("#generateFeedbackButton").disabled = false;
  qs("#generateFeedbackButton").textContent = "Сформировать ОС";
  qs("#feedbackDialog").hidden = false;
}

function closeFeedbackDialog() {
  qs("#feedbackDialog").hidden = true;
  state.feedbackScheduleId = "";
  state.generatedFeedback = "";
  state.generatedFeedbackId = "";
}

async function generateTeachingFeedback() {
  const schedule = teachingWorkspace().schedules.find((item) => item.id === state.feedbackScheduleId);
  if (!schedule) return;
  const payload = { max_user_id: Number(apiContext.maxUserId || 1), tenant_slug: apiContext.tenantSlug || null, absent_students: (qs("#feedbackAbsent")?.value || "").split(",").map((name) => name.trim()).filter(Boolean), is_repetition: Boolean(qs("#feedbackRepetition")?.checked), advance_lesson: false };
  const button = qs("#generateFeedbackButton");
  button.disabled = true;
  button.textContent = "Формируем...";
  try {
    let output;
    if (apiContext.demoMode || !apiContext.maxUserId) {
      output = { id: `demo-feedback-${Date.now()}`, schedule_id: schedule.id, group_name: schedule.group_name, course_name: schedule.course_name, lesson_date: schedule.next_lesson_date, lesson_number: schedule.current_lesson_number, feedback_text: `Обратная связь урок №${String(schedule.current_lesson_number).padStart(2, "0")}\n\nДобрый день, уважаемые родители!\n\nСегодня ученики изучили тему «${schedule.next_lesson_title || schedule.course_name}».\n\nНа платформе доступен материал урока и прогресс ребенка.` };
      teachingWorkspace().feedback_outputs.unshift(output);
    } else {
      const response = await fetch(`/api/v1/teaching/schedules/${encodeURIComponent(schedule.id)}/feedback`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      if (!response.ok) throw new Error(await parseApiError(response));
      output = await response.json();
      await loadTeachingWorkspace();
    }
    state.generatedFeedback = output.feedback_text;
    state.generatedFeedbackId = output.id;
    qs("#feedbackDialogContent").innerHTML = `<textarea id="feedbackResult" class="feedback-result" readonly>${escapeHtml(output.feedback_text)}</textarea>`;
    qs("#copyFeedbackButton").hidden = false;
    qs("#sendFeedbackButton").hidden = false;
    button.hidden = true;
    renderFeedbackHistory();
  } catch (error) {
    showNotice(error.message || "Не удалось сформировать ОС", "danger");
    button.disabled = false;
    button.textContent = "Сформировать ОС";
  }
}

async function copyGeneratedFeedback() {
  if (!state.generatedFeedback) return;
  await navigator.clipboard.writeText(state.generatedFeedback);
  showNotice("Текст ОС скопирован");
}

async function sendGeneratedFeedback() {
  if (!state.generatedFeedbackId) return;
  const button = qs("#sendFeedbackButton");
  button.disabled = true;
  button.textContent = "Отправляем...";
  try {
    if (apiContext.demoMode || !apiContext.maxUserId) {
      await new Promise((resolve) => setTimeout(resolve, 250));
      showNotice("Демо: ОС отправлена 3 родителям");
      button.textContent = "Отправлено";
      return;
    }
    const response = await fetch(`/api/v1/teaching/feedback/${encodeURIComponent(state.generatedFeedbackId)}/send`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ max_user_id: Number(apiContext.maxUserId), tenant_slug: apiContext.tenantSlug || null }),
    });
    if (!response.ok) throw new Error(await parseApiError(response));
    const result = await response.json();
    if (result.status === "sent") {
      showNotice(`ОС отправлена: ${result.sent_recipients} получ.`);
      button.textContent = "Отправлено";
    } else if (result.status === "delivery_unavailable") {
      showNotice(`Найдено родителей: ${result.parent_recipients}. Проверьте MAX-токен.`, "danger");
      button.disabled = false;
      button.textContent = "Отправить родителям";
    } else {
      showNotice("У группы нет связанных MAX-аккаунтов родителей", "danger");
      button.disabled = false;
      button.textContent = "Отправить родителям";
    }
  } catch (error) {
    showNotice(error.message || "Не удалось отправить ОС", "danger");
    button.disabled = false;
    button.textContent = "Отправить родителям";
  }
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
  renderTeaching();
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

  const formData = new FormData();
  formData.set("max_user_id", apiContext.maxUserId);
  if (apiContext.tenantSlug) formData.set("tenant_slug", apiContext.tenantSlug);
  formData.set("sheet_name", "Сделки");
  formData.set("dry_run", String(dryRun));
  formData.set("file", file);

  state.crmImporting = true;
  renderAdminPanel();
  try {
    const response = await fetch("/api/v1/miniapp/students/import", {
      method: "POST",
      body: formData,
    });
    if (!response.ok) throw new Error(await parseApiError(response));
    const result = await response.json();
    state.crmImportPreview = result;
    if (dryRun) {
      showNotice(`Файл проверен: ${result.parsed_rows} строк, ${result.distinct_groups} групп`);
    } else {
      await loadSession();
      state.teachingLoaded = false;
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
    state.productEditorOpen = false;
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
    state.productEditorOpen = false;
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

function addCartItem(product, quantityValue) {
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
  showNotice(`Заказ №${orderNumber} оформлен в демо-режиме`);
  setView("orders");
  renderAll();
}

function orderWarehouseOptions(item) {
  const product = productById(item.productId || "");
  if (!product) return [];
  return productWarehouses(product).filter(
    (warehouse) => warehouse.available >= Number(item.quantity || 0),
  );
}

function renderOrderDialog(order) {
  const needsWarehouseAssignment = canAssignOrderWarehouses(order);
  const items = Array.isArray(order.items) && order.items.length > 0
    ? order.items
        .map(
          (item) => {
            const warehouseOptions = needsWarehouseAssignment
              ? orderWarehouseOptions(item)
              : [];
            const warehouseControl = needsWarehouseAssignment
              ? `
                  <label class="order-warehouse-field">
                    <span>Склад для списания</span>
                    <select data-order-warehouse="${escapeHtml(item.productId || "")}">
                      <option value="">Выберите склад</option>
                      ${warehouseOptions
                        .map(
                          (warehouse) => `
                            <option value="${escapeHtml(warehouse.id)}">
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
            return `
              <div class="order-detail-item ${needsWarehouseAssignment ? "needs-warehouse" : ""}">
                <div>
                  <strong>${escapeHtml(item.productName || "Товар")}</strong>
                  <div class="student-meta">${Number(item.quantity || 0)} шт.</div>
                  ${warehouseControl}
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
          (event) => `
            <div class="order-history-row">
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
            ["teacher", "admin"].includes(state.role)
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
    order.warehouse = orderWarehouseSummary(order.items, "Склад назначен");
    order.statusHistory = order.statusHistory || [];
    order.statusHistory.push({
      fromStatus: order.rawStatus,
      toStatus: order.rawStatus,
      comment: "Склад назначен администратором",
      createdAt: new Date().toISOString(),
    });
    showNotice(`Заказ №${order.id}: склады назначены`);
    renderAll();
    renderOrderDialog(order);
    return;
  }

  try {
    const response = await fetch(
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
          comment: "Склад назначен из MAX mini app",
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

async function updateOrderAction(orderId, action) {
  const order = orders.find((item) => item.backendId === orderId || item.id === orderId);
  if (!order) return;

  if (orderId.startsWith("demo-") || apiContext.demoMode || !apiContext.maxUserId) {
    const previousStatus = order.rawStatus;
    if (action === "issue") order.rawStatus = "issued_to_student";
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
        return: "Заказ возвращен",
        cancel: "Заказ отменен",
      }[action],
      createdAt: new Date().toISOString(),
    });
    showNotice(
      {
        issue: `Заказ №${order.id} отмечен как выданный`,
        return: `Заказ №${order.id} возвращен в демо-режиме`,
        cancel: `Заказ №${order.id} отменен в демо-режиме`,
      }[action],
    );
    renderAll();
    if (!qs("#orderDialog").hidden) renderOrderDialog(order);
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
    if (!qs("#orderDialog").hidden) {
      const refreshedOrder = orders.find((item) => item.backendId === orderId || item.id === orderId);
      if (refreshedOrder) renderOrderDialog(refreshedOrder);
    }
  } catch (error) {
    showNotice(error.message || "Не удалось обновить заказ", "danger");
  }
}

async function accrueGroupCoins() {
  const group = qs("#accrualGroupSelect")?.value || "all";
  const reason = qs("#groupAccrualReason")?.value || "";
  const amount = Number.parseInt(qs("#groupAccrualAmount")?.value || "0", 10);
  if (group === "all") {
    showNotice("Выберите конкретную группу для группового начисления", "danger");
    return;
  }
  if (!reason) {
    showNotice("Выберите причину группового начисления", "danger");
    return;
  }
  if (!amount || amount <= 0) {
    showNotice("Выберите сумму группового начисления", "danger");
    return;
  }

  state.accrualGroup = group;
  await accrueStudents(studentsForGroup(group), amount, reason, group);
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
    state.warehouseEditorOpen = false;
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

async function accrueStudents(targets, amount, reason, groupLabel = "") {
  if (targets.length === 0) {
    showNotice("Выберите учеников для начисления", "danger");
    return;
  }

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
    showNotice(
      groupLabel
        ? `Группе «${groupLabel}» начислено по ${amount} AC`
        : targets.length === 1
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
      groupLabel
        ? `Группе «${groupLabel}» начислено по ${amount} AC: ${result.credited_students} учен.`
        : targets.length === 1
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
    closeCheckoutDialog();
    createDemoOrder();
    return;
  }

  const payload = {
    max_user_id: Number(apiContext.maxUserId),
    tenant_slug: apiContext.tenantSlug || undefined,
    student_id: student.id,
    items: Array.from(state.cart.values()).map((item) => ({
      product_id: item.productId,
      quantity: item.quantity,
    })),
    comment: "MAX mini app",
  };

  const button = qs("#confirmOrderButton");
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
    saveCart();
    closeCheckoutDialog();
    showNotice(`Заказ №${result.order.order_number} оформлен и зарезервирован`);
    await refreshOrderAndInventoryState();
    setView("orders");
    renderAll();
  } catch (error) {
    closeCheckoutDialog();
    showNotice(error.message || "Не удалось оформить заказ", "danger");
    renderCart();
  } finally {
    button.disabled = false;
  }
}

document.addEventListener("click", (event) => {
  const target = event.target instanceof HTMLElement ? event.target.closest("button") : null;
  if (!target) return;

  if ("mobileMore" in target.dataset) {
    toggleMobileMorePanel();
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

  const feedbackScheduleId = target.dataset.feedbackSchedule;
  if (feedbackScheduleId) openFeedbackDialog(feedbackScheduleId);

  const feedbackOutputId = target.dataset.openFeedback;
  if (feedbackOutputId) openFeedbackDialog("", feedbackOutputId);

  if (target.id === "closeFeedbackDialogButton") closeFeedbackDialog();
  if (target.id === "generateFeedbackButton") generateTeachingFeedback();
  if (target.id === "copyFeedbackButton") copyGeneratedFeedback();
  if (target.id === "sendFeedbackButton") sendGeneratedFeedback();

  const studentId = target.dataset.selectStudent;
  if (studentId) setActiveStudent(studentId);

  const addId = target.dataset.add;
  if (addId) addToCart(addId);

  const productDetailsId = target.dataset.productDetails;
  if (productDetailsId) openProductDialog(productDetailsId);

  const favoriteId = target.dataset.favorite;
  if (favoriteId) {
    if (state.favorites.has(favoriteId)) state.favorites.delete(favoriteId);
    else state.favorites.add(favoriteId);
    saveFavorites();
    renderProducts();
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

  const adminTab = target.dataset.adminTab;
  if (adminTab) {
    state.adminTab = adminTab;
    renderAdminPanel();
  }

  const opsJump = target.dataset.opsJump;
  if (opsJump === "orders") {
    state.orderStatusFilter = "open";
    setView("orders");
    renderOrders();
  } else if (["inventory", "products"].includes(opsJump)) {
    state.adminTab = opsJump;
    renderAdminPanel();
  }

  const orderId = target.dataset.openOrder;
  if (orderId) openOrderDetails(orderId);

  const orderActionId = target.dataset.orderActionId;
  const orderAction = target.dataset.orderAction;
  if (orderActionId && orderAction) {
    updateOrderAction(orderActionId, orderAction);
  }

  if (target.id === "assignOrderWarehousesButton") {
    assignOrderWarehouses(target.dataset.orderId || "");
  }

  if ("groupAccrual" in target.dataset) {
    accrueGroupCoins();
  }

  const accrueStudentId = target.dataset.accrueStudent;
  if (accrueStudentId) {
    accrueStudentFromRow(accrueStudentId);
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

  if (target.id === "crmPreviewButton") {
    importCrmStudents(true);
  }

  if (target.id === "crmImportButton") {
    importCrmStudents(false);
  }

  const editProductId = target.dataset.editProduct;
  if (editProductId) {
    state.editingProductId = editProductId;
    state.productEditorOpen = true;
    renderAdminPanel();
  }

  if (target.id === "productCreateButton") {
    state.editingProductId = "";
    state.productEditorOpen = true;
    renderAdminPanel();
  }

  if (target.id === "productCancelEditButton") {
    state.editingProductId = "";
    state.productEditorOpen = false;
    renderAdminPanel();
  }

  if (target.id === "productSaveButton") {
    saveProductFromForm();
  }

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

  if (target.id === "applyAccrualFilter") {
    state.accrualNameFilter = qs("#accrualNameFilter")?.value.trim() || "";
    state.accrualGroup = qs("#accrualGroupSelect")?.value || "all";
    renderAccrual();
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

qs("#feedbackDialog").addEventListener("click", (event) => {
  if (event.target === event.currentTarget) closeFeedbackDialog();
});

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
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

  if (target.id === "productImportFile") {
    const file = target.files?.[0] || null;
    state.productImportFile = file;
    state.productImportFileName = file?.name || "";
    const label = target.closest(".file-picker")?.querySelector("span");
    if (label) label.textContent = state.productImportFileName || "Выбрать файл";
  }

  if (target.id === "crmImportFile") {
    const file = target.files?.[0] || null;
    state.crmImportFile = file;
    state.crmImportFileName = file?.name || "";
    state.crmImportPreview = null;
    const label = target.closest(".file-picker")?.querySelector("span");
    if (label) label.textContent = state.crmImportFileName || "Выбрать XLSX";
  }

  if (target.id === "studentGroupFilter") {
    state.studentGroupFilter = target.value;
    renderStudents();
  }

  if (target.id === "orderStatusFilter") {
    state.orderStatusFilter = target.value;
    renderOrders();
    savePreferences();
  }

  if (target.id === "scheduleDayFilter") {
    state.scheduleDayFilter = target.value;
    renderScheduleList();
  }

  if (target.id === "productDialogQuantity") {
    syncProductDialogControls();
  }

  const cartQuantityKey = target.dataset.cartQuantity;
  if (cartQuantityKey) {
    updateCartQuantity(cartQuantityKey, target.value);
  }

});

document.addEventListener("input", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLInputElement)) return;

  if (target.id === "productDialogQuantity") {
    syncProductDialogControls();
  }

  if (target.id === "orderSearch") {
    state.orderSearch = target.value;
    renderOrders();
  }
});

document.addEventListener(
  "error",
  (event) => {
    const image = event.target;
    if (
      !(image instanceof HTMLImageElement) ||
      !image.closest(".product-visual, .product-dialog-visual, .admin-product-thumb")
    ) return;
    image.remove();
  },
  true,
);

qs("#studentSelect").addEventListener("change", (event) => {
  setActiveStudent(event.target.value);
});
qs("#openCartButton").addEventListener("click", () => setView("cart"));
qs("#refreshDataButton").addEventListener("click", refreshAllData);
qs("#productSearch").addEventListener("input", renderProducts);
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

async function init() {
  qs("#tenantTitle").textContent = tenantTitle();
  restorePreferences();
  if (apiContext.demoMode && state.view === "teaching") state.role = "teacher";
  qs("#productSort").value = state.productSort;
  qs("#inStockOnly").checked = state.inStockOnly;
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

  if (apiContext.demoMode || state.catalogLoaded) restoreCart();
  restoreFavorites();

  setRole(state.role);
  setView(state.view);
  state.lastSyncAt = new Date();
  renderAll();
  renderSyncStatus();
  refreshIcons();
}

init();
