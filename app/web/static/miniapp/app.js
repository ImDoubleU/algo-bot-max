const maxWebAppLaunch = resolveMaxWebAppLaunch();
const launchMaxUserId =
  maxWebAppLaunch.userId || positiveIntegerParam("max_user_id");
const launchTenantSlug = queryParam("tenant_slug") || "";
const localDemoHost = ["127.0.0.1", "localhost"].includes(window.location.hostname);
const apiContext = {
  maxUserId: launchMaxUserId,
  tenantSlug: launchTenantSlug,
  maxWebAppData: maxWebAppLaunch.initData,
  demoMode: localDemoHost && queryParam("demo") === "1",
  demoRole: queryParam("demo_role") || "",
  productId: queryParam("product") || "",
};
if (queryParam("miniapp_token")) {
  const cleanUrl = new URL(window.location.href);
  cleanUrl.searchParams.delete("miniapp_token");
  window.history.replaceState(null, "", cleanUrl);
}
const sessionStartedAt = new Date();

const ROLE_VIEWS = Object.freeze({
  student: ["dashboard", "store", "cart", "orders", "wallet"],
  parent: ["dashboard", "store", "cart", "orders", "wallet"],
  teacher: ["dashboard", "store", "orders", "wallet", "report", "accrual", "teaching", "broadcasts"],
  admin: ["dashboard", "store", "orders", "wallet", "report", "accrual", "teaching", "broadcasts", "admin"],
});

const VIEW_META = Object.freeze({
  dashboard: { label: "Главная", icon: "layout-dashboard" },
  store: { label: "Магазин", icon: "store" },
  cart: { label: "Корзина", icon: "shopping-bag" },
  orders: { label: "Заказы", icon: "package-check" },
  wallet: { label: "История AC", icon: "wallet-cards" },
  report: { label: "Отчет AC", icon: "file-chart-column" },
  accrual: { label: "Начисления", icon: "circle-plus" },
  teaching: { label: "Журнал", icon: "calendar-days" },
  broadcasts: { label: "Рассылки", icon: "megaphone" },
  admin: { label: "Управление", icon: "settings-2" },
});

const ROLE_MOBILE_PRIMARY = Object.freeze({
  student: ["dashboard", "store", "cart", "orders"],
  parent: ["dashboard", "store", "cart", "orders"],
  teacher: ["dashboard", "accrual", "teaching", "orders"],
  admin: ["dashboard", "orders", "admin", "store"],
});

const state = {
  hasAccess: apiContext.demoMode,
  role: "student",
  account: null,
  staffRoles: [],
  currentTenant: null,
  defaultWarehouseId: "",
  availableTenants: [],
  canManageTenants: false,
  tenantSaving: false,
  tenantSearch: "",
  availableRoles: ["student", "parent", "teacher", "admin"],
  view: ["dashboard", "store", "cart", "orders", "wallet", "report", "accrual", "teaching", "broadcasts", "admin"].includes(
    queryParam("view"),
  )
    ? queryParam("view")
    : "dashboard",
  adminTab: "summary",
  studentGroupFilter: "all",
  orderStatusFilter: "action",
  orderSearch: "",
  accrualGroup: "",
  accrualNameFilter: "",
  selectedAccrualStudents: new Set(),
  balance: 1240,
  activeStudentId: "demo-alisa",
  carts: new Map(),
  loadedCartStudentIds: new Set(),
  cartVersions: new Map(),
  get cart() {
    const scope = this.activeStudentId || "unassigned";
    if (!this.carts.has(scope)) this.carts.set(scope, new Map());
    return this.carts.get(scope);
  },
  set cart(value) {
    const scope = this.activeStudentId || "unassigned";
    this.carts.set(scope, value);
  },
  favorites: new Set(["demo-pen"]),
  favoritesOnly: false,
  inStockOnly: false,
  productSort: "recommended",
  productCategory: "all",
  recentProductSearches: [],
  storeFiltersOpen: false,
  railCollapsed: false,
  refreshing: false,
  lastSyncAt: null,
  catalogLoaded: false,
  sessionLoaded: false,
  studentInvitations: new Map(),
  studentInvitationsLoading: false,
  studentInvitationsLoaded: false,
  qrPreviewStudentId: "",
  qrBrightnessRequested: false,
  productImporting: false,
  productImportFile: null,
  productImportFileName: "",
  productPhotoFile: null,
  productPhotoFileName: "",
  productPhotoPreviewUrl: "",
  productPhotoRemoved: false,
  crmImporting: false,
  crmImportFile: null,
  crmImportFileName: "",
  crmImportPreview: null,
  crmStudentStatus: "active",
  accrualSaving: false,
  accrualRequestKey: "",
  accrualRequestSignature: "",
  orderSaving: false,
  orderRequestKey: "",
  orderRequestSignature: "",
  productSaving: false,
  productEditorOpen: false,
  editingProductId: "",
  staffSaving: false,
  staffEditorOpen: false,
  staffStatusFilter: "active",
  staffRoleFilter: "all",
  staffNotificationSettings: null,
  staffNotificationTargetAccountId: "",
  staffNotificationsLoading: false,
  staffNotificationsSaving: false,
  accessStatusFilter: "all",
  accessRoleFilter: "all",
  inventorySavingKey: "",
  warehouseSaving: false,
  warehousePreferenceSaving: false,
  warehouseEditorOpen: false,
  editingWarehouseId: "",
  opsSummary: null,
  opsSummaryLoaded: false,
  teachingWorkspace: null,
  teachingLoaded: false,
  teachingLoading: false,
  scheduleEditorOpen: false,
  editingScheduleId: "",
  scheduleDraftGroup: "",
  generatedFeedback: "",
  generatedFeedbackId: "",
  attendanceScheduleId: "",
  attendanceJournal: null,
  attendanceLoading: false,
  attendanceSaving: false,
  attendanceDirty: new Map(),
  attendanceLessonDirty: new Map(),
  attendanceAutoScroll: false,
  accrualReport: null,
  accrualReportLoading: false,
  accrualReportPeriod: "month",
  accrualReportTeacherFilter: "all",
  accrualReportGroupFilter: "all",
  inventoryWarehouseFilter: "all",
  inventoryStockFilter: "all",
  adminEntitySearch: "",
  adminStudents: [],
  adminStudentsLoaded: false,
  adminStudentsLoading: false,
  adminStudentsError: "",
  studentRegistryStatusFilter: "all",
  studentRegistryGroupFilter: "all",
  productStatusFilter: "all",
  productCategoryFilter: "all",
  broadcastHistory: [],
  broadcastHistoryLoaded: false,
  broadcastHistoryLoading: false,
  broadcastSaving: false,
  broadcastPreviewLoading: false,
  broadcastPreview: null,
  broadcastPreviewSignature: "",
  broadcastSelectedGroups: new Set(),
  broadcastAllGroups: true,
  broadcastPhotoFile: null,
  broadcastPhotoPreviewUrl: "",
  broadcastStep: 1,
  broadcastDraftSavedAt: null,
};

let accrualSearchTimer = null;
let adminSearchTimer = null;
let noticeTimer = null;
let noticeActionHandler = null;
let broadcastDraftTimer = null;
const cartSyncChains = new Map();

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
    venue: "Союзный 45",
    teacher: "Олейник Д",
    balance: 1240,
    contact: "681",
  },
  {
    id: "demo-ivan",
    lmsId: "2417",
    name: "Петров Иван",
    group: "Гагарина 64, сб 18:00",
    venue: "Гагарина 64",
    teacher: "Олейник Д",
    balance: 860,
    contact: "681",
  },
  {
    id: "demo-mark",
    lmsId: "1930",
    name: "Соколов Марк",
    group: "Октября 13, пн 16:00",
    venue: "Октября 13",
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
    accountId: "demo-account-admin",
    maxUserId: "53364725",
    username: "admin_user",
    displayName: "Администратор",
    role: "admin",
    status: "active",
  },
  {
    id: "demo-staff-teacher",
    accountId: "demo-account-teacher",
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
const PRODUCT_IMAGE_MAX_BYTES = 10 * 1024 * 1024;
const PRODUCT_IMAGE_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

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

function resolveMaxWebAppLaunch() {
  const hashParams = new URLSearchParams(window.location.hash.replace(/^#/, ""));
  const initData = String(
    window.WebApp?.initData || hashParams.get("WebAppData") || "",
  ).trim();
  let userId = String(window.WebApp?.initDataUnsafe?.user?.id || "");
  if (!userId && initData) {
    const encodedUser = new URLSearchParams(initData).get("user");
    if (encodedUser) {
      try {
        userId = String(JSON.parse(encodedUser)?.id || "");
      } catch {
        userId = "";
      }
    }
  }
  if (!/^[1-9]\d*$/.test(userId)) userId = "";
  return { initData, userId };
}

function clearLegacyMiniappToken() {
  try {
    Object.keys(window.sessionStorage)
      .filter((key) => key.startsWith("algo-max:miniapp-token:"))
      .forEach((key) => window.sessionStorage.removeItem(key));
  } catch {
    // Storage can be unavailable in a restricted MAX webview.
  }
}

clearLegacyMiniappToken();

function positiveIntegerParam(name) {
  const value = queryParam(name)?.trim() || "";
  return /^[1-9]\d*$/.test(value) ? value : "";
}

function tenantTitle() {
  if (state.currentTenant && !apiContext.demoMode) {
    return `${state.currentTenant.city_name} · ${state.currentTenant.partner_name}`;
  }
  if (apiContext.demoMode) return "Algo MAX";
  if (!apiContext.tenantSlug) return "Не выбран";
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

function formatRegistryDate(value) {
  if (!value) return "Не указана";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Не указана";
  return date.toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function todayShort() {
  return new Date().toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit" });
}

function createRequestKey() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return `request-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 14)}`;
}

function studentWelcome(firstName) {
  const hour = sessionStartedAt.getHours();
  const greeting =
    hour >= 5 && hour < 12
      ? "Доброе утро"
      : hour < 18
        ? "Добрый день"
        : hour < 23
          ? "Добрый вечер"
          : "Доброй ночи";
  return {
    title: `${greeting}${firstName ? `, ${firstName}` : ""}`,
    text: "Баланс, заказы и история начисления астрокоинов.",
  };
}

function studentsForCurrentRole() {
  if (state.role === "admin") return students;
  if (state.role === "teacher") {
    if (apiContext.demoMode && primaryStaffRole() === "curator") return students;
    if (!apiContext.demoMode) return students.filter((student) => student.staffVisible);
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

function legacyCartStorageKey() {
  const tenant = apiContext.tenantSlug || (apiContext.demoMode ? "demo" : "default");
  const user = apiContext.maxUserId || "guest";
  return `algo-max-cart:${tenant}:${user}`;
}

function cartStorageKey(studentId = state.activeStudentId) {
  const student = studentId || "unassigned";
  return `${legacyCartStorageKey()}:${student}`;
}

function cartServerMarkerKey(studentId = state.activeStudentId) {
  return `${cartStorageKey(studentId)}:server`;
}

function canUseServerCart(studentId = state.activeStudentId) {
  return Boolean(
    !apiContext.demoMode &&
      apiContext.maxUserId &&
      state.hasAccess &&
      canUseStoreCart() &&
      studentId &&
      !String(studentId).startsWith("demo-"),
  );
}

function buildCartMap(storedItems) {
  const cart = new Map();
  if (!Array.isArray(storedItems)) return cart;
  storedItems.forEach((item) => {
    const productId = String(item.productId || item.product_id || "");
    const product = productById(productId);
    const available = product ? productAvailable(product) : 0;
    if (!product || available <= 0) return;
    const key = cartKey(product.id);
    const current = cart.get(key)?.quantity || 0;
    const quantity = clampQuantity(current + Number(item.quantity || 0), available);
    cart.set(key, {
      productId: product.id,
      quantity,
    });
  });
  return cart;
}

function queueCartSync(studentId = state.activeStudentId) {
  const scope = String(studentId || "");
  if (!canUseServerCart(scope)) return Promise.resolve();
  const tenantSlug = apiContext.tenantSlug || undefined;
  const maxUserId = Number(apiContext.maxUserId);
  const markerKey = cartServerMarkerKey(scope);
  const syncKey = `${tenantSlug || "default"}:${scope}`;
  const cart = state.carts.get(scope) || new Map();
  const items = Array.from(cart.values()).map((item) => ({
    product_id: item.productId,
    quantity: item.quantity,
  }));
  const previous = cartSyncChains.get(syncKey) || Promise.resolve();
  const request = previous
    .catch(() => undefined)
    .then(async () => {
      const response = await apiFetch(
        apiUrl(`/api/v1/miniapp/students/${encodeURIComponent(scope)}/cart`),
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            max_user_id: maxUserId,
            tenant_slug: tenantSlug,
            items,
          }),
        },
      );
      if (!response.ok) throw new Error(await parseApiError(response));
      try {
        localStorage.setItem(markerKey, "1");
      } catch (error) {
        console.warn("Не удалось отметить синхронизацию корзины", error);
      }
    });
  cartSyncChains.set(syncKey, request);
  const handledRequest = request.catch((error) => {
    console.warn("Не удалось синхронизировать корзину", error);
  });
  handledRequest.finally(() => {
    if (cartSyncChains.get(syncKey) === request) cartSyncChains.delete(syncKey);
  });
  return handledRequest;
}

function saveCart(
  studentId = state.activeStudentId,
  { sync = true, bumpVersion = true } = {},
) {
  const scope = studentId || "unassigned";
  const cart = state.carts.get(scope);
  if (!cart && !state.loadedCartStudentIds.has(scope)) return Promise.resolve();
  try {
    localStorage.setItem(
      cartStorageKey(studentId),
      JSON.stringify(Array.from((cart || new Map()).values())),
    );
    state.loadedCartStudentIds.add(scope);
    if (bumpVersion) {
      state.cartVersions.set(scope, (state.cartVersions.get(scope) || 0) + 1);
    }
  } catch (error) {
    console.warn("Не удалось сохранить корзину", error);
  }
  return sync ? queueCartSync(studentId) : Promise.resolve();
}

function restoreCart(studentId = state.activeStudentId) {
  const scope = studentId || "unassigned";
  let serialized = null;
  const storageKey = cartStorageKey(studentId);
  let storedItems = [];
  try {
    serialized = localStorage.getItem(storageKey);
    if (serialized === null) {
      const legacyKey = legacyCartStorageKey();
      serialized = localStorage.getItem(legacyKey);
      if (serialized !== null) {
        localStorage.setItem(storageKey, serialized);
        localStorage.removeItem(legacyKey);
      }
    }
    storedItems = JSON.parse(serialized || "[]");
  } catch (error) {
    console.warn("Не удалось восстановить корзину", error);
    return;
  }
  if (!Array.isArray(storedItems)) return;

  state.carts.set(scope, buildCartMap(storedItems));
  state.loadedCartStudentIds.add(scope);
}

async function loadServerCart(studentId = state.activeStudentId) {
  const scope = String(studentId || "");
  if (!canUseServerCart(scope) || !state.catalogLoaded) return;
  const syncKey = `${apiContext.tenantSlug || "default"}:${scope}`;
  const pendingSync = cartSyncChains.get(syncKey);
  if (pendingSync) await pendingSync.catch(() => undefined);

  const versionBeforeLoad = state.cartVersions.get(scope) || 0;
  const localCart = state.carts.get(scope) || new Map();
  try {
    const response = await apiFetch(
      apiUrl(`/api/v1/miniapp/students/${encodeURIComponent(scope)}/cart`, {
        max_user_id: apiContext.maxUserId,
        tenant_slug: apiContext.tenantSlug,
      }),
    );
    if (!response.ok) throw new Error(await parseApiError(response));
    const result = await response.json();
    if ((state.cartVersions.get(scope) || 0) !== versionBeforeLoad) return;

    let serverKnown = false;
    try {
      serverKnown = localStorage.getItem(cartServerMarkerKey(scope)) === "1";
    } catch (error) {
      console.warn("Не удалось проверить синхронизацию корзины", error);
    }
    const serverItems = Array.isArray(result.items) ? result.items : [];
    if (serverItems.length === 0 && localCart.size > 0 && !serverKnown) {
      await queueCartSync(scope);
      return;
    }

    state.carts.set(scope, buildCartMap(serverItems));
    state.loadedCartStudentIds.add(scope);
    saveCart(scope, { sync: false, bumpVersion: false });
    try {
      localStorage.setItem(cartServerMarkerKey(scope), "1");
    } catch (error) {
      console.warn("Не удалось отметить загрузку корзины", error);
    }
    if (state.activeStudentId === scope) {
      renderProducts();
      renderCart();
    }
  } catch (error) {
    console.warn("Не удалось загрузить корзину ученика", error);
  }
}

function changeActiveStudent(studentId, { restore = true } = {}) {
  const nextStudentId = String(studentId || "");
  const previousStudentId = state.activeStudentId;
  if (previousStudentId === nextStudentId) {
    if (
      restore &&
      nextStudentId &&
      !state.loadedCartStudentIds.has(nextStudentId)
    ) {
      restoreCart(nextStudentId);
    }
    return;
  }
  if (previousStudentId) saveCart(previousStudentId);
  state.activeStudentId = nextStudentId;
  if (restore && nextStudentId && (apiContext.demoMode || state.catalogLoaded)) {
    restoreCart(nextStudentId);
  }
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
        recentProductSearches: state.recentProductSearches.slice(0, 5),
        railCollapsed: state.railCollapsed,
      }),
    );
  } catch (error) {
    console.warn("Не удалось сохранить настройки приложения", error);
  }
}

function restorePreferences() {
  try {
    const preferences = JSON.parse(localStorage.getItem(preferencesStorageKey()) || "null");
    if (!preferences || typeof preferences !== "object") return;
    if (preferences.activeStudentId) state.activeStudentId = String(preferences.activeStudentId);
    const storedProductSort = preferences.productSort === "name"
      ? "recommended"
      : preferences.productSort;
    if (["recommended", "price-asc", "price-desc", "newest"].includes(storedProductSort)) {
      state.productSort = storedProductSort;
    }
    state.productCategory = String(preferences.productCategory || "all");
    state.inStockOnly = Boolean(preferences.inStockOnly);
    state.favoritesOnly = Boolean(preferences.favoritesOnly);
    state.recentProductSearches = Array.isArray(preferences.recentProductSearches)
      ? preferences.recentProductSearches.map(String).filter(Boolean).slice(0, 5)
      : [];
    state.railCollapsed = Boolean(preferences.railCollapsed);
    const storedOrderFilter = preferences.orderStatusFilter === "open"
      ? "action"
      : preferences.orderStatusFilter;
    if (
      [
        "action",
        "work",
        "issued",
        "cancelled",
        "all",
        "created",
        "reserved",
        "transferred_to_teacher",
        "issued_to_student",
        "returned",
        "problem",
      ].includes(storedOrderFilter)
    ) {
      state.orderStatusFilter = storedOrderFilter;
    }
  } catch (error) {
    console.warn("Не удалось восстановить настройки приложения", error);
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

function apiFetch(input, options = {}) {
  const headers = new Headers(options.headers || {});
  if (apiContext.maxWebAppData) {
    headers.set("X-Max-WebApp-Data", apiContext.maxWebAppData);
  }
  return window.fetch(input, { ...options, headers });
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

function showNotice(message, tone = "ok", options = {}) {
  const notice = qs("#noticeBar");
  const messageNode = qs("#noticeMessage");
  const actionButton = qs("#noticeAction");
  if (!notice || !messageNode || !actionButton) return;
  window.clearTimeout(noticeTimer);
  noticeActionHandler = typeof options.onAction === "function" ? options.onAction : null;
  messageNode.textContent = apiErrorMessage(message);
  actionButton.hidden = !noticeActionHandler;
  actionButton.textContent = noticeActionHandler ? String(options.actionLabel || "Открыть") : "";
  notice.hidden = false;
  notice.className = `notice-bar ${tone}`;
  refreshIcons();
  const duration = Number(options.duration ?? (tone === "danger" ? 8000 : 4500));
  if (duration > 0) noticeTimer = window.setTimeout(hideNotice, duration);
}

function hideNotice() {
  const notice = qs("#noticeBar");
  const messageNode = qs("#noticeMessage");
  const actionButton = qs("#noticeAction");
  window.clearTimeout(noticeTimer);
  noticeActionHandler = null;
  if (!notice) return;
  notice.hidden = true;
  if (messageNode) messageNode.textContent = "";
  if (actionButton) {
    actionButton.hidden = true;
    actionButton.textContent = "";
  }
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

function applyDemoRole() {
  if (!apiContext.demoMode) return;
  const requestedRole = apiContext.demoRole.trim().toLowerCase();
  const staffRoleMap = {
    superadmin: "admin",
    partner_director: "admin",
    admin: "admin",
    curator: "teacher",
    teacher: "teacher",
  };
  if (staffRoleMap[requestedRole]) {
    state.staffRoles = [requestedRole];
    state.role = staffRoleMap[requestedRole];
    state.availableRoles = [state.role];
    return;
  }
  if (["student", "parent"].includes(requestedRole)) {
    state.staffRoles = [];
    state.role = requestedRole;
    state.availableRoles = [requestedRole];
  }
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

function staffRoleProfileLabel(role) {
  return {
    superadmin: "суперадминистратор",
    partner_director: "директор",
    admin: "администратор",
    curator: "куратор",
    teacher: "преподаватель",
  }[role] || "сотрудник";
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
    suggestedWarehouseId: item.suggested_warehouse_id
      ? String(item.suggested_warehouse_id)
      : "",
    suggestedWarehouseName: item.suggested_warehouse_name || "",
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

  state.hasAccess = apiContext.demoMode || Boolean(session.has_access);
  apiContext.tenantSlug = session.tenant_slug || apiContext.tenantSlug;
  state.currentTenant = session.tenant || null;
  state.availableTenants = Array.isArray(session.available_tenants)
    ? session.available_tenants
    : [];
  state.canManageTenants = Boolean(session.can_manage_tenants);
  state.defaultWarehouseId = String(session.default_warehouse_id || "");
  state.account = session.account || null;
  state.staffRoles = Array.isArray(session.staff_roles) ? session.staff_roles : [];
  if (!state.hasAccess) {
    students = [];
    orders = [];
    ledger = [];
    accessLinks = [];
    staffAssignments = [];
    products = [];
    catalogWarehouses = [];
    state.availableRoles = [];
    state.activeStudentId = "";
    state.catalogLoaded = false;
    state.adminStudents = [];
    state.adminStudentsLoaded = false;
    state.adminStudentsError = "";
    state.sessionLoaded = true;
    return;
  }

  students = session.students.map((student) => ({
    id: String(student.student_id),
    lmsId: student.lms_student_id || "",
    role: student.role,
    staffVisible: Boolean(student.staff_visible),
    accessStatus: student.access_status || "active",
    name: student.display_name,
    group: student.group_name || student.course_name || "Группа не указана",
    course: student.course_name || "",
    venue: student.venue_name || "",
    teacher: student.teacher_name || "Педагог не указан",
    balance: student.balance,
    contact: session.account?.max_user_id || "",
  }));

  const previousStudentExists = students.some((student) => student.id === state.activeStudentId);
  const nextStudentId = previousStudentExists ? state.activeStudentId : students[0]?.id || "";
  changeActiveStudent(nextStudentId, { restore: state.catalogLoaded });

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
    accountId: String(assignment.account_id),
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
  state.availableRoles = Array.from(availableRoles).filter((role) =>
    ["student", "parent", "teacher", "admin"].includes(role),
  );
  state.role = staffRole || (hasParentRole ? "parent" : "student");
  state.sessionLoaded = true;
}

function applyAccessGate(message = "") {
  const locked = !apiContext.demoMode && !state.hasAccess;
  const gate = qs("#accessGate");
  const shell = qs(".app-shell");
  if (gate) gate.hidden = !locked;
  if (shell) shell.hidden = locked;
  if (locked && message) {
    const label = qs("#accessGateMessage");
    if (label) label.textContent = message;
  }
  document.body.dataset.access = locked ? "locked" : "granted";
  refreshIcons();
  return locked;
}

function parentStudents() {
  if (apiContext.demoMode) return [...students];
  const unique = new Map();
  students
    .filter((student) => student.role === "parent")
    .forEach((student) => unique.set(student.id, student));
  return Array.from(unique.values());
}

async function loadParentInvitations() {
  if (apiContext.demoMode) {
    state.studentInvitations = new Map(
      parentStudents().map((student) => [
        student.id,
        {
          data: {
            qr_data_url: `/miniapp/static/assets/${student.id}-qr.svg`,
            qr_download_url: `/miniapp/static/assets/${student.id}-qr.svg`,
            bot_url: "",
          },
          demo: true,
          error: "",
        },
      ]),
    );
    state.studentInvitationsLoaded = true;
    renderParentInvitations();
    return;
  }
  if (
    !state.hasAccess ||
    !apiContext.maxUserId ||
    !state.availableRoles.includes("parent") ||
    state.studentInvitationsLoading
  ) {
    return;
  }
  const linkedStudents = parentStudents();
  if (linkedStudents.length === 0) {
    state.studentInvitationsLoaded = true;
    return;
  }

  state.studentInvitationsLoading = true;
  renderParentInvitations();
  const invitations = new Map();
  await Promise.all(
    linkedStudents.map(async (student) => {
      try {
        const response = await apiFetch(
          apiUrl(`/api/v1/miniapp/students/${encodeURIComponent(student.id)}/invitation`, {
            max_user_id: apiContext.maxUserId,
            tenant_slug: apiContext.tenantSlug,
          }),
        );
        if (!response.ok) throw new Error(await parseApiError(response));
        invitations.set(student.id, { data: await response.json(), error: "" });
      } catch (error) {
        invitations.set(student.id, {
          data: null,
          error: error.message || "Не удалось создать QR-код",
        });
      }
    }),
  );
  state.studentInvitations = invitations;
  state.studentInvitationsLoading = false;
  state.studentInvitationsLoaded = true;
  renderParentInvitations();
}

async function loadTeachingWorkspace() {
  if (apiContext.demoMode || !apiContext.maxUserId) {
    state.teachingWorkspace = structuredClone(demoTeachingWorkspace);
    state.teachingLoaded = true;
    return;
  }

  const response = await apiFetch(
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

  products = catalog.products.map((product, catalogIndex) => {
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
      catalogIndex,
    };
  });
  pruneInactiveCartItems();
  state.catalogLoaded = true;
}

async function loadSession() {
  if (apiContext.demoMode) return;
  if (!apiContext.maxUserId) return;

  const response = await apiFetch(
    apiUrl("/api/v1/miniapp/session", {
      max_user_id: apiContext.maxUserId,
      tenant_slug: apiContext.tenantSlug,
    }),
  );
  if (!response.ok) throw new Error(await parseApiError(response));
  applySession(await response.json());
  syncTenantToUrl();
}

async function loadCatalog() {
  if (apiContext.demoMode) return;
  if (!state.hasAccess) return;

  const params = { tenant_slug: apiContext.tenantSlug };
  if (apiContext.maxUserId) params.max_user_id = apiContext.maxUserId;
  if (canUseAdminCatalog()) {
    params.include_inactive = "true";
  }
  const response = await apiFetch(
    apiUrl("/api/v1/miniapp/catalog", params),
  );
  if (!response.ok) throw new Error(await parseApiError(response));
  applyCatalog(await response.json());
}

async function loadOpsSummary() {
  if (
    apiContext.demoMode ||
    !state.hasAccess ||
    !apiContext.maxUserId ||
    !["teacher", "admin"].includes(state.role)
  ) {
    applyOpsSummary(null);
    return;
  }

  const response = await apiFetch(
    apiUrl("/api/v1/miniapp/ops/summary", {
      max_user_id: apiContext.maxUserId,
      tenant_slug: apiContext.tenantSlug,
      low_stock_threshold: 5,
    }),
  );
  if (!response.ok) throw new Error(await parseApiError(response));
  applyOpsSummary(await response.json());
}

function normalizeRegistryStudent(item) {
  return {
    id: String(item.student_id || ""),
    lmsId: item.lms_student_id || "",
    name: item.display_name || "Без имени",
    group: item.group_name || "",
    course: item.course_name || "",
    venue: item.venue_name || "",
    teacher: item.teacher_name || "",
    status: item.status || "active",
    balance: Number(item.balance || 0),
    importedAt: item.imported_at || "",
    updatedAt: item.updated_at || "",
    statusUpdatedAt: item.status_updated_at || "",
    departedAt: item.departed_at || "",
    history: Array.isArray(item.history)
      ? item.history.map((event) => ({
          id: event.id ? String(event.id) : "",
          eventType: event.event_type || "updated",
          fromStatus: event.from_status || "",
          toStatus: event.to_status || "active",
          changedFields: Array.isArray(event.changed_fields) ? event.changed_fields : [],
          source: event.source || "",
          actorName: event.actor_name || "",
          occurredAt: event.occurred_at || "",
        }))
      : [],
  };
}

async function loadAdminStudents(force = false) {
  if (
    state.role !== "admin" ||
    !state.hasAccess ||
    !apiContext.maxUserId ||
    apiContext.demoMode
  ) return;
  if (
    state.adminStudentsLoading ||
    (state.adminStudentsLoaded && !force)
  ) return;

  state.adminStudentsLoading = true;
  state.adminStudentsError = "";
  if (state.adminTab === "students") renderAdminPanel();
  try {
    const response = await apiFetch(
      apiUrl("/api/v1/miniapp/students/registry", {
        max_user_id: apiContext.maxUserId,
        tenant_slug: apiContext.tenantSlug,
      }),
    );
    if (!response.ok) throw new Error(await parseApiError(response));
    const result = await response.json();
    state.adminStudents = Array.isArray(result.students)
      ? result.students.map(normalizeRegistryStudent)
      : [];
    state.adminStudentsLoaded = true;
  } catch (error) {
    state.adminStudentsError = error.message || "Не удалось загрузить учеников";
    showNotice(state.adminStudentsError, "danger");
  } finally {
    state.adminStudentsLoading = false;
    if (state.adminTab === "students") renderAdminPanel();
  }
}

async function refreshOrderAndInventoryState() {
  await loadSession();
  if (applyAccessGate()) return;
  await loadCatalog();
  await loadOpsSummary();
}

async function refreshCatalogAndOpsSummary() {
  if (!state.hasAccess) return;
  await loadCatalog();
  await loadOpsSummary();
}

function syncTenantToUrl() {
  if (apiContext.demoMode || !apiContext.tenantSlug) return;
  const url = new URL(window.location.href);
  url.searchParams.set("tenant_slug", apiContext.tenantSlug);
  window.history.replaceState(null, "", url);
}

function renderTenantControl() {
  const button = qs("#tenantSwitcherButton");
  const title = qs("#tenantTitle");
  const canSwitch = !apiContext.demoMode && state.canManageTenants;
  document.body.dataset.canSwitchTenants = canSwitch ? "true" : "false";
  if (button) button.hidden = !canSwitch;
  if (title) title.textContent = tenantTitle();
}

function renderTenantDialog() {
  const list = qs("#tenantList");
  if (!list) return;
  const currentSlug = apiContext.tenantSlug;
  const query = state.tenantSearch.trim().toLowerCase();
  const visibleTenants = state.availableTenants.filter((tenant) =>
    !query || `${tenant.city_name} ${tenant.partner_name} ${tenant.tenant_name} ${tenant.tenant_slug}`.toLowerCase().includes(query),
  );
  list.innerHTML = visibleTenants
    .map((tenant) => {
      const isCurrent = tenant.tenant_slug === currentSlug;
      return `
        <button class="tenant-option ${isCurrent ? "is-current" : ""}" type="button" data-tenant-switch="${escapeHtml(tenant.tenant_slug)}" ${isCurrent ? "disabled" : ""}>
          <span>${escapeHtml(tenant.city_name)}</span>
          <strong>${escapeHtml(tenant.partner_name)}</strong>
          <small>${escapeHtml(tenant.tenant_name)}</small>
        </button>
      `;
    })
    .join("") || '<div class="empty-state compact-empty"><strong>Партнеры не найдены</strong></div>';
  Array.from(list.querySelectorAll("[data-tenant-switch]")).forEach((button) => {
    button.addEventListener("click", () => switchTenant(button.dataset.tenantSwitch || ""));
  });
}

function setTenantCreateMode(enabled) {
  const form = qs("#tenantCreateForm");
  const list = qs("#tenantList");
  const hint = qs("#tenantDialogHint");
  const showButton = qs("#showTenantCreateButton");
  const cancelButton = qs("#cancelTenantCreateButton");
  const saveButton = qs("#saveTenantButton");
  if (form) form.hidden = !enabled;
  if (list) list.hidden = enabled;
  const searchField = qs("#tenantSearchField");
  if (searchField) searchField.hidden = enabled;
  if (hint) hint.textContent = enabled
    ? "Добавьте нового партнера. Его данные будут храниться отдельно."
    : "Выберите город и партнера.";
  if (showButton) showButton.hidden = enabled;
  if (cancelButton) cancelButton.hidden = !enabled;
  if (saveButton) saveButton.hidden = !enabled;
}

function openTenantDialog() {
  if (!state.canManageTenants) return;
  state.tenantSearch = "";
  const search = qs("#tenantSearch");
  if (search) search.value = "";
  renderTenantDialog();
  setTenantCreateMode(false);
  const dialog = qs("#tenantDialog");
  if (dialog) dialog.hidden = false;
}

function closeTenantDialog() {
  const dialog = qs("#tenantDialog");
  if (dialog) dialog.hidden = true;
}

async function switchTenant(tenantSlug) {
  if (!state.canManageTenants || !tenantSlug || tenantSlug === apiContext.tenantSlug) {
    closeTenantDialog();
    return;
  }
  const previousTenantSlug = apiContext.tenantSlug;
  saveCart();
  apiContext.tenantSlug = tenantSlug;
  state.carts = new Map();
  state.loadedCartStudentIds = new Set();
  state.cartVersions = new Map();
  state.adminStudents = [];
  state.adminStudentsLoaded = false;
  state.adminStudentsError = "";
  state.studentRegistryStatusFilter = "all";
  state.studentRegistryGroupFilter = "all";
  syncTenantToUrl();
  closeTenantDialog();
  try {
    await loadSession();
    if (applyAccessGate()) return;
    await loadCatalog();
    await loadOpsSummary();
    if (state.adminTab === "students") await loadAdminStudents();
    state.studentInvitations = new Map();
    state.studentInvitationsLoaded = false;
    state.favorites = new Set();
    state.teachingWorkspace = null;
    state.teachingLoaded = false;
    state.attendanceScheduleId = "";
    state.attendanceJournal = null;
    state.attendanceDirty = new Map();
    state.attendanceLessonDirty = new Map();
    state.accrualReport = null;
    state.accrualReportTeacherFilter = "all";
    state.accrualReportGroupFilter = "all";
    state.broadcastHistory = [];
    state.broadcastHistoryLoaded = false;
    state.broadcastPreview = null;
    state.broadcastPreviewSignature = "";
    state.broadcastSelectedGroups = new Set();
    state.broadcastAllGroups = true;
    qs("#broadcastForm")?.reset();
    clearBroadcastPhoto();
    restoreBroadcastDraft();
    restoreCart();
    await loadServerCart(state.activeStudentId);
    restoreFavorites();
    setRole(state.role);
    state.lastSyncAt = new Date();
    renderAll();
    renderSyncStatus();
    showNotice("Партнер выбран");
  } catch (error) {
    apiContext.tenantSlug = previousTenantSlug;
    syncTenantToUrl();
    showNotice(error.message || "Не удалось выбрать партнера", "danger");
  }
}

async function createTenantFromForm(event) {
  event.preventDefault();
  if (!state.canManageTenants || !apiContext.maxUserId) return;
  const cityName = qs("#tenantCityName")?.value.trim() || "";
  const partnerName = qs("#tenantPartnerName")?.value.trim() || "";
  const directorId = qs("#tenantDirectorMaxUserId")?.value.trim() || "";
  const directorName = qs("#tenantDirectorName")?.value.trim() || "";
  if (!cityName || !partnerName) {
    showNotice("Укажите город и партнера", "danger");
    return;
  }
  const payload = {
    max_user_id: Number(apiContext.maxUserId),
    tenant_slug: apiContext.tenantSlug || undefined,
    city_name: cityName,
    partner_name: partnerName,
  };
  if (directorId) payload.partner_director_max_user_id = Number(directorId);
  if (directorName) payload.partner_director_display_name = directorName;

  state.tenantSaving = true;
  const saveButton = qs("#saveTenantButton");
  if (saveButton) saveButton.disabled = true;
  try {
    const response = await apiFetch("/api/v1/miniapp/tenants", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(await parseApiError(response));
    const result = await response.json();
    qs("#tenantCreateForm")?.reset();
    await switchTenant(result.tenant.tenant_slug);
    showNotice(result.created ? "Партнер создан" : "Партнер уже существует и открыт");
  } catch (error) {
    showNotice(error.message || "Не удалось создать партнера", "danger");
  } finally {
    state.tenantSaving = false;
    if (saveButton) saveButton.disabled = false;
  }
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
    label.textContent = "Данные не обновлялись";
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
  try {
    await loadSession();
  } catch (error) {
    errors.push(error);
  }
  if (applyAccessGate()) {
    state.refreshing = false;
    return;
  }
  const refreshTasks = [loadCatalog(), loadOpsSummary()];
  if (state.adminStudentsLoaded || state.adminTab === "students") {
    refreshTasks.push(loadAdminStudents(true));
  }
  const results = await Promise.allSettled(refreshTasks);
  results.forEach((result) => {
    if (result.status === "rejected") errors.push(result.reason);
  });
  state.studentInvitations = new Map();
  state.studentInvitationsLoaded = false;
  await loadParentInvitations();
  if (["teacher", "admin"].includes(state.role)) {
    try {
      await loadTeachingWorkspace();
    } catch (error) {
      errors.push(error);
    }
  }
  if (roleViews(state.role).includes("broadcasts")) {
    state.broadcastHistoryLoaded = false;
    try {
      await loadBroadcastHistory();
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
    showNotice("Данные обновлены");
  }
}

function setView(view) {
  const allowedViews = roleViews(state.role);
  const nextView = allowedViews.includes(view) ? view : "dashboard";
  const previousView = state.view;
  if (
    previousView === "teaching" &&
    nextView !== "teaching" &&
    hasAttendanceChanges() &&
    !window.confirm("В журнале есть несохраненные изменения. Выйти без сохранения?")
  ) {
    return;
  }
  if (previousView !== nextView) hideNotice();
  if (nextView !== "store") state.storeFiltersOpen = false;
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
    ["wallet", "report", "accrual", "teaching", "broadcasts", "admin"].includes(nextView),
  );
  closeMobileMorePanel();
  renderMobileNavigation();
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
  if (nextView === "broadcasts" && !state.teachingLoaded && !state.teachingLoading) {
    state.teachingLoading = true;
    loadTeachingWorkspace()
      .then(renderBroadcasts)
      .catch((error) =>
        showNotice(error.message || "Не удалось загрузить форматы занятий", "danger"),
      )
      .finally(() => {
        state.teachingLoading = false;
        renderBroadcasts();
      });
  }
  if (
    nextView === "broadcasts" &&
    !state.broadcastHistoryLoaded &&
    !state.broadcastHistoryLoading
  ) {
    loadBroadcastHistory().catch((error) => {
      showNotice(error.message || "Не удалось загрузить историю рассылок", "danger");
    });
  }
  renderStatus();
  if (nextView === "report") renderAccrualReport();
  if (nextView === "broadcasts") renderBroadcasts();
}

function roleViews(role) {
  const views = [...(ROLE_VIEWS[role] || ROLE_VIEWS.student)];
  if (role === "teacher" && primaryStaffRole() === "teacher") {
    return views.filter((view) => !["report", "broadcasts"].includes(view));
  }
  return views;
}

function cartCountForStudent(studentId) {
  const cart = state.carts.get(studentId || "unassigned");
  if (!cart) return 0;
  return [...cart.values()].reduce((total, item) => total + Number(item.quantity || 0), 0);
}

function renderChildSwitcher() {
  const bar = qs("#childSwitcherBar");
  if (!bar) return;
  const roleStudents = sortedStudents();
  const visible = state.role === "parent" && roleStudents.length > 1;
  bar.hidden = !visible;
  if (!visible) {
    bar.innerHTML = "";
    return;
  }
  bar.innerHTML = `
    <span class="child-switcher-label">Ребенок</span>
    <div class="child-switcher-scroll">
      ${roleStudents
        .map((student) => {
          const count = cartCountForStudent(student.id);
          return `
            <button
              class="child-switcher-button ${student.id === state.activeStudentId ? "is-active" : ""}"
              type="button"
              data-active-student="${escapeHtml(student.id)}"
              aria-pressed="${student.id === state.activeStudentId}"
            >
              <span>${escapeHtml(student.name)}</span>
              ${count ? `<b title="Товаров в корзине">${count}</b>` : ""}
            </button>`;
        })
        .join("")}
    </div>`;
  const scroller = bar.querySelector(".child-switcher-scroll");
  const activeButton = scroller?.querySelector(".child-switcher-button.is-active");
  if (scroller && activeButton) {
    const left = activeButton.offsetLeft - (scroller.clientWidth - activeButton.offsetWidth) / 2;
    scroller.scrollLeft = Math.max(left, 0);
  }
}

function mobilePrimaryViews() {
  const allowed = roleViews(state.role);
  return (ROLE_MOBILE_PRIMARY[state.role] || ROLE_MOBILE_PRIMARY.student).filter((view) =>
    allowed.includes(view),
  );
}

function navButtonMarkup(view, className = "") {
  const meta = VIEW_META[view];
  if (!meta) return "";
  const count = view === "cart" ? cartCount() : 0;
  return `
    <button class="nav-button ${className} ${state.view === view ? "is-active" : ""}" type="button" data-view="${view}">
      <span class="mobile-nav-icon" aria-hidden="true"><i data-lucide="${meta.icon}"></i></span>
      <span>${meta.label}</span>
      ${view === "cart" ? `<span class="mobile-nav-count" data-cart-count ${count ? "" : "hidden"}>${count}</span>` : ""}
    </button>`;
}

function renderMobileNavigation() {
  const nav = qs("#mobileBottomNav");
  const actions = qs("#mobileMoreActions");
  const tenant = qs("#mobileMoreTenant");
  if (!nav || !actions) return;
  const primary = mobilePrimaryViews();
  const allowed = roleViews(state.role);
  const secondary = [...new Set(allowed.filter((view) => !primary.includes(view)))];
  nav.innerHTML = `${primary.map((view) => navButtonMarkup(view)).join("")}
    <button id="mobileMoreButton" class="nav-button ${secondary.includes(state.view) ? "is-active" : ""}" type="button" data-mobile-more>
      <span class="mobile-nav-icon" aria-hidden="true"><i data-lucide="menu"></i></span>
      <span>Ещё</span>
    </button>`;
  actions.innerHTML = secondary
    .map((view) => {
      const meta = VIEW_META[view];
      if (!meta) return "";
      return `
        <button class="mobile-more-action ${state.view === view ? "is-active" : ""}" type="button" data-view="${view}">
          <span class="mobile-more-action-icon" aria-hidden="true"><i data-lucide="${meta.icon}"></i></span>
          <span class="mobile-more-action-label">${meta.label}</span>
          <i class="mobile-more-action-chevron" data-lucide="chevron-right" aria-hidden="true"></i>
        </button>`;
    })
    .join("");
  if (tenant) tenant.textContent = ["teacher", "admin"].includes(state.role) ? tenantTitle() : "";
  refreshIcons();
}

function applyRailState() {
  document.body.classList.toggle("rail-collapsed", state.railCollapsed);
  const button = qs("#railCollapseButton");
  if (!button) return;
  button.setAttribute("aria-expanded", String(!state.railCollapsed));
  button.setAttribute("aria-label", state.railCollapsed ? "Развернуть меню" : "Свернуть меню");
  button.title = state.railCollapsed ? "Развернуть меню" : "Свернуть меню";
  const icon = button.querySelector("i");
  if (icon) icon.setAttribute("data-lucide", state.railCollapsed ? "panel-left-open" : "panel-left-close");
  const label = button.querySelector("span");
  if (label) label.textContent = state.railCollapsed ? "Развернуть" : "Свернуть";
  refreshIcons();
}

function canUseStoreCart() {
  return ["student", "parent"].includes(state.role);
}

function setRole(role) {
  if (!state.availableRoles.includes(role)) return;
  const roleChanged = state.role !== role;
  state.role = role;
  if (roleChanged) {
    state.studentGroupFilter = "all";
    state.accrualGroup = "";
    state.accrualNameFilter = "";
  }
  const roleStudents = studentsForCurrentRole();
  const nextStudentId = roleStudents.some(
    (student) => student.id === state.activeStudentId,
  )
    ? state.activeStudentId
    : roleStudents[0]?.id || "";
  changeActiveStudent(nextStudentId);
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

  const allowedViews = roleViews(role);
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

  const cartButton = qs("#openCartButton");
  if (cartButton) cartButton.hidden = !allowedViews.includes("cart");
  renderMobileNavigation();

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
  if (
    role === "parent" &&
    !state.studentInvitationsLoaded &&
    !state.studentInvitationsLoading
  ) {
    loadParentInvitations().catch((error) => console.warn(error));
  }
}

function closeMobileMorePanel() {
  const panel = qs("#mobileMorePanel");
  const backdrop = qs("#mobileMoreBackdrop");
  if (panel) panel.hidden = true;
  if (backdrop) backdrop.hidden = true;
  document.body.classList.remove("mobile-more-open");
}

function toggleMobileMorePanel() {
  const panel = qs("#mobileMorePanel");
  const backdrop = qs("#mobileMoreBackdrop");
  if (!panel) return;
  const willOpen = panel.hidden;
  panel.hidden = !willOpen;
  if (backdrop) backdrop.hidden = !willOpen;
  document.body.classList.toggle("mobile-more-open", willOpen);
  if (willOpen) qs("#closeMobileMoreButton")?.focus();
}

function setActiveStudent(studentId) {
  if (!studentsForCurrentRole().some((student) => student.id === studentId)) return;
  changeActiveStudent(studentId);
  savePreferences();
  renderAll();
  void loadServerCart(studentId);
}

function renderStatus() {
  const student = selectedStudent();
  const isStaff = ["teacher", "admin"].includes(state.role);
  const accountName = state.account?.display_name?.trim() || "";
  const primaryRole =
    primaryStaffRole() || (state.role === "admin" ? "admin" : "teacher");
  const profileRole = staffRoleProfileLabel(primaryRole);
  const roleStudents = studentsForCurrentRole();
  const linkedCount = roleStudents.length;
  const statusStrip = qs(".status-strip");
  const studentContext = qs("#studentContext");
  if (studentContext) {
    studentContext.hidden = linkedCount === 0 || (isStaff && state.view !== "wallet");
  }
  if (statusStrip) statusStrip.classList.toggle("has-no-students", linkedCount === 0);
  if (statusStrip) statusStrip.classList.toggle("is-staff-profile", isStaff);
  if (statusStrip) {
    statusStrip.classList.toggle(
      "has-student-context",
      Boolean(studentContext && !studentContext.hidden),
    );
  }
  const balancePanel = qs(".status-balance");
  if (balancePanel) balancePanel.hidden = isStaff;
  const profileLabel = qs(".status-profile-label");
  if (profileLabel) profileLabel.textContent = isStaff ? "Рабочий профиль" : "Личный профиль";
  const statusTenant = qs("#statusTenantTitle");
  if (statusTenant) {
    statusTenant.hidden = !isStaff;
    statusTenant.textContent = isStaff ? tenantTitle() : "";
  }
  const labels = {
    student: student ? `${student.name}, ученик` : "Ученик",
    parent: accountName
      ? `${accountName}, родитель`
      : linkedCount > 0
        ? `Родитель, ${linkedCount} учен.`
        : "Родитель",
    teacher: accountName ? `${accountName}, ${profileRole}` : staffRoleLabel(primaryRole),
    admin: accountName ? `${accountName}, ${profileRole}` : staffRoleLabel(primaryRole),
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
  qsa('.nav-button[data-view="wallet"] span').forEach((walletNavLabel) => {
    walletNavLabel.textContent = isStaff ? "История учеников" : "История AC";
  });
  const storeAudience = qs("#storeAudience");
  if (storeAudience) {
    storeAudience.textContent = isStaff
      ? ""
      : student
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
      title: primaryRole === "curator" ? "Группы и занятия" : "Мои группы и занятия",
      text:
        primaryRole === "curator"
          ? "Ученики, расписание и обратная связь по филиалу."
          : "Ученики, расписание и обратная связь по вашим группам.",
    },
    admin: {
      kicker: "Управление филиалом",
      title: "Сводка по филиалу",
      text: "Импорт, сотрудники, склады и заказы.",
    },
  };
  const spotlight = spotlightByRole[state.role] || spotlightByRole.student;
  if (state.role === "admin" && primaryRole === "partner_director") {
    spotlight.kicker = "Кабинет директора";
  } else if (state.role === "admin" && primaryRole === "superadmin") {
    spotlight.kicker = "Кабинет суперадминистратора";
  }
  qs("#dashboardTitle").textContent = dashboardTitle;
  qs("#dashboardRoleKicker").textContent = spotlight.kicker;
  qs("#dashboardSpotlightTitle").textContent = spotlight.title;
  qs("#dashboardSpotlightText").textContent = spotlight.text;
  const taskActions = qs("#dashboardTaskActions");
  if (taskActions) {
    const actions = state.role === "teacher"
      ? [
          ["teaching", "calendar-check", "Открыть журнал"],
          ["accrual", "circle-plus", "Начислить AC"],
        ]
      : state.role === "admin"
        ? [
            ["orders", "package-check", "Заказы к выдаче"],
            ["inventory", "boxes", "Проверить остатки", "ops"],
          ]
        : [];
    taskActions.hidden = actions.length === 0;
    taskActions.innerHTML = actions
      .map(
        ([view, icon, label, actionType], index) => `
          <button class="${index === 0 ? "primary-action" : "secondary-action"}" type="button" ${actionType === "ops" ? `data-ops-jump="${view}"` : `data-view-jump="${view}"`}>
            <i data-lucide="${icon}"></i><span>${label}</span>
          </button>`,
      )
      .join("");
  }
  qs("#dashboardOrdersTitle").textContent = {
    student: "Мои заказы",
    parent: "Заказы детей",
    teacher: "Заказы к выдаче",
    admin: "Заказы к выдаче",
  }[state.role] || "Заказы";
  qs("#studentPanelTitle").textContent = {
    student: "Мой профиль",
    parent: "Мои дети",
    teacher: primaryRole === "curator" ? "Ученики филиала" : "Мои ученики",
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
  renderChildSwitcher();
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
                  <span class="soft-badge">${student.balance} AC</span>
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
                <button class="icon-button" type="button" data-share-student-invite="${escapeHtml(student.id)}" title="Поделиться" aria-label="Поделиться"><i data-lucide="share-2"></i></button>
                <button class="icon-button" type="button" data-print-student-invite="${escapeHtml(student.id)}" title="Печать" aria-label="Печать"><i data-lucide="printer"></i></button>
              </div>
            </div>
          </div>
        </details>
      `;
    })
    .join("");
  refreshIcons();
}

function openStudentQrPreview(studentId) {
  const student = students.find((item) => item.id === studentId);
  const invitation = state.studentInvitations.get(studentId)?.data;
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
  const invitation = state.studentInvitations.get(studentId)?.data;
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

async function shareStudentInvitation(studentId) {
  const student = students.find((item) => item.id === studentId);
  const invitation = state.studentInvitations.get(studentId)?.data;
  if (!student || !invitation) return;
  const shareData = {
    title: `Вход в Algo MAX: ${student.name}`,
    text: `Персональная ссылка для входа ребенка ${student.name}`,
    url: invitation.bot_url || window.location.href,
  };
  try {
    if (navigator.share && invitation.bot_url) await navigator.share(shareData);
    else {
      await navigator.clipboard.writeText(invitation.bot_url || invitation.qr_data_url);
      showNotice("Ссылка скопирована");
    }
  } catch (error) {
    if (error?.name !== "AbortError") showNotice("Не удалось поделиться ссылкой", "danger");
  }
}

function printStudentInvitation(studentId) {
  const student = students.find((item) => item.id === studentId);
  const invitation = state.studentInvitations.get(studentId)?.data;
  if (!student || !invitation) return;
  const printWindow = window.open("", "_blank", "width=520,height=680");
  if (!printWindow) return showNotice("Разрешите всплывающие окна для печати", "danger");
  const heading = printWindow.document.createElement("h1");
  const group = printWindow.document.createElement("p");
  const image = printWindow.document.createElement("img");
  heading.textContent = student.name;
  group.textContent = student.group;
  image.src = invitation.qr_data_url;
  image.alt = `QR-код: ${student.name}`;
  image.style.width = "360px";
  image.style.maxWidth = "100%";
  printWindow.document.title = `QR-код ${student.name}`;
  printWindow.document.body.style.cssText = "font-family:Arial,sans-serif;text-align:center;padding:32px;color:#171326";
  printWindow.document.body.append(heading, group, image);
  image.addEventListener("load", () => printWindow.print(), { once: true });
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

function canTransferOrder(order) {
  return (
    state.role === "admin" &&
    order.rawStatus === "reserved" &&
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
  } else if (canIssueOrder(order)) {
    descriptors.push({ action: "issue", label: "Выдать заказ", icon: "package-check" });
  } else if (canTransferOrder(order)) {
    descriptors.push({ action: "transfer", label: "Передать педагогу", icon: "send" });
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
  const roleOrders = ordersForCurrentRole();
  const tabs = [
    ["action", "К действию"],
    ["work", "В работе"],
    ["issued", "Выданы"],
    ["cancelled", "Отменены"],
    ["all", "Все"],
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

function renderOrders() {
  const searchInput = qs("#orderSearch");
  const statusFilter = qs("#orderStatusFilter");
  if (searchInput) searchInput.value = state.orderSearch;
  if (statusFilter) statusFilter.value = state.orderStatusFilter;
  const clearSearchButton = qs("#clearOrderSearch");
  if (clearSearchButton) clearSearchButton.hidden = !state.orderSearch;
  renderOrderStatusTabs();

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
      return `
        <article class="order-card" data-tone="${escapeHtml(order.tone)}">
          <button class="order-card-visual" type="button" data-open-order="${escapeHtml(order.backendId || order.id)}" aria-label="Открыть заказ №${escapeHtml(order.id)}">
            ${product?.photoUrl ? `<img src="${escapeHtml(product.photoUrl)}" alt="" loading="lazy" />` : `<i data-lucide="${product ? productFallbackIcon(product) : "package"}"></i>`}
          </button>
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
    qs("#exportAcReportButton").disabled = true;
    return;
  }
  const report = state.accrualReport;
  if (!report) {
    summary.textContent = "Выберите период и нажмите «Показать».";
    list.innerHTML = "";
    qs("#exportAcReportButton").disabled = true;
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
  qs("#exportAcReportButton").disabled = entries.length === 0;
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

function exportAccrualReport() {
  const entries = filteredAccrualReportEntries();
  if (!entries.length) return;
  const csvRows = [
    ["Дата", "Преподаватель", "Ученик", "Группа", "Сумма AC", "Причина"],
    ...entries.map((entry) => [
      new Date(entry.created_at).toLocaleString("ru-RU"),
      entry.teacher_name,
      entry.student_name,
      entry.group_name || "",
      Number(entry.amount),
      entry.reason,
    ]),
  ];
  const csv = csvRows
    .map((row) => row.map((value) => `"${String(value ?? "").replaceAll('"', '""')}"`).join(";"))
    .join("\r\n");
  const url = URL.createObjectURL(new Blob([`\ufeff${csv}`], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `ac-report-${qs("#acReportDateFrom").value}-${qs("#acReportDateTo").value}.csv`;
  link.click();
  URL.revokeObjectURL(url);
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
    '<option value="">Сумма</option>',
    ...accrualAmounts.map((amount) => `<option value="${amount}">+${amount} AC</option>`),
  ].join("");
  groupReason.value = selectedGroupReason;
  groupAmount.value = selectedGroupAmount;
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
  const canSubmitAccrual = selectedCount > 0 && Boolean(selectedGroupReason) && Boolean(selectedGroupAmount);
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
    stickyDetails.textContent = selectedGroupReason && selectedGroupAmount
      ? `${selectedGroupReason} · +${selectedGroupAmount} AC каждому`
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
                  <span>${product.stock} шт.</span>
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
    <div><i data-lucide="users"></i><strong>${active.length}</strong><span>групп</span></div>
    <div class="teaching-next"><i data-lucide="calendar-clock"></i><span>Ближайшее занятие</span><strong>${nearest ? `${escapeHtml(formatTeachingDate(nearest.next_lesson_date))}, ${escapeHtml(nearest.lesson_time.slice(0, 5))}` : "Не запланировано"}</strong></div>`;
  renderScheduleEditor();
  renderScheduleList();
  renderFeedbackHistory();
  renderAttendanceJournal();
}

function formatJournalDate(value) {
  if (!value) return "";
  return new Intl.DateTimeFormat("ru-RU", { day: "2-digit", month: "2-digit" }).format(
    new Date(`${value}T12:00:00`),
  );
}

function formatJournalMonth(value) {
  if (!value) return "";
  return new Intl.DateTimeFormat("ru-RU", { month: "long" }).format(new Date(`${value}T12:00:00`));
}

function dateAfterWeeks(value, weekOffset) {
  const dateValue = new Date(`${value}T12:00:00`);
  dateValue.setDate(dateValue.getDate() + weekOffset * 7);
  return dateValue.toISOString().slice(0, 10);
}

function attendanceMark(student, lessonDate) {
  return student.marks.find((mark) => mark.lesson_date === lessonDate) || null;
}

function attendanceDirtyKey(studentId, lessonDate) {
  return `${studentId}:${lessonDate}`;
}

function attendanceMarkSnapshot(mark) {
  if (!mark) return null;
  return {
    present: mark.present ?? null,
    makeup_completed: Boolean(mark.makeup_completed),
    comment: mark.comment || null,
  };
}

function sameAttendanceMark(left, right) {
  return (
    left?.present === right?.present &&
    Boolean(left?.makeup_completed) === Boolean(right?.makeup_completed) &&
    (left?.comment || null) === (right?.comment || null)
  );
}

function rememberAttendanceChange(student, lessonDate, originalMark) {
  const key = attendanceDirtyKey(student.student_id, lessonDate);
  const mark = attendanceMark(student, lessonDate);
  const pending = state.attendanceDirty.get(key);
  const original = pending ? pending._original : originalMark;
  const current = attendanceMarkSnapshot(mark);
  if (sameAttendanceMark(current, original)) {
    state.attendanceDirty.delete(key);
    return;
  }
  state.attendanceDirty.set(key, {
    student_id: student.student_id,
    lesson_date: lessonDate,
    present: mark?.present ?? null,
    makeup_completed: Boolean(mark?.makeup_completed),
    comment: mark?.comment || null,
    _original: original,
  });
}

function cycleAttendanceStatus(studentId, lessonDate) {
  const student = state.attendanceJournal?.students.find((item) => item.student_id === studentId);
  if (!student) return;
  let mark = attendanceMark(student, lessonDate);
  const originalMark = attendanceMarkSnapshot(mark);
  if (!mark) {
    mark = {
      lesson_date: lessonDate,
      present: true,
      makeup_completed: false,
      comment: null,
    };
    student.marks.push(mark);
  } else if (mark.present === true) {
    mark.present = false;
    mark.makeup_completed = false;
  } else if (!mark.makeup_completed) {
    mark.makeup_completed = true;
  } else {
    student.marks = student.marks.filter((item) => item.lesson_date !== lessonDate);
  }
  rememberAttendanceChange(student, lessonDate, originalMark);
  renderAttendanceJournal();
}

function attendanceChangesCount() {
  return state.attendanceDirty.size + state.attendanceLessonDirty.size;
}

function hasAttendanceChanges() {
  return attendanceChangesCount() > 0;
}

function openAttendanceLessonEditor(position) {
  const lesson = state.attendanceJournal?.lessons.find(
    (item) => Number(item.position) === Number(position),
  );
  const dialog = qs("#attendanceLessonDialog");
  if (!lesson || !dialog) return;
  dialog.dataset.position = String(lesson.position);
  qs("#attendanceLessonDate").value = lesson.lesson_date;
  qs("#attendanceLessonNumber").value = String(lesson.lesson_number);
  qs("#attendanceLessonDialogTitle").textContent = `Занятие ${lesson.position}`;
  dialog.hidden = false;
  document.body.classList.add("dialog-open");
  qs("#attendanceLessonDate").focus();
}

function closeAttendanceLessonEditor() {
  const dialog = qs("#attendanceLessonDialog");
  if (!dialog || dialog.hidden) return;
  dialog.hidden = true;
  dialog.dataset.position = "";
  syncDialogBodyClass();
}

function applyAttendanceLessonEditor() {
  const dialog = qs("#attendanceLessonDialog");
  const journal = state.attendanceJournal;
  const position = Number(dialog?.dataset.position || 0);
  const lesson = journal?.lessons.find((item) => Number(item.position) === position);
  const lessonDate = qs("#attendanceLessonDate")?.value || "";
  const lessonNumber = Number(qs("#attendanceLessonNumber")?.value || 0);
  if (!dialog || !journal || !lesson) return;
  if (!lessonDate || lessonNumber < 1) {
    showNotice("Укажите дату и номер урока", "danger");
    return;
  }
  const duplicateDate = journal.lessons.some(
    (item) => Number(item.position) !== position && item.lesson_date === lessonDate,
  );
  if (duplicateDate) {
    showNotice("На эту дату уже назначено занятие группы", "danger");
    return;
  }

  const previousDate = lesson.lesson_date;
  const previousNumber = lesson.lesson_number;
  if (previousDate !== lessonDate) {
    journal.students.forEach((student) => {
      const mark = attendanceMark(student, previousDate);
      if (mark) mark.lesson_date = lessonDate;
    });
    [...state.attendanceDirty.entries()].forEach(([key, item]) => {
      if (item.lesson_date !== previousDate) return;
      state.attendanceDirty.delete(key);
      item.lesson_date = lessonDate;
      state.attendanceDirty.set(
        attendanceDirtyKey(item.student_id, lessonDate),
        item,
      );
    });
  }
  lesson.lesson_date = lessonDate;
  lesson.lesson_number = lessonNumber;
  lesson.lesson_title = null;
  lesson.is_future = lessonDate > reportDateValue(new Date());
  journal.lessons.sort((left, right) =>
    `${left.lesson_date}:${left.position}`.localeCompare(`${right.lesson_date}:${right.position}`),
  );
  const pendingLesson = state.attendanceLessonDirty.get(position);
  const originalLessonDate = pendingLesson?._original_lesson_date || previousDate;
  const originalLessonNumber =
    pendingLesson?._original_lesson_number ?? previousNumber;
  if (
    lessonDate === originalLessonDate &&
    lessonNumber === originalLessonNumber
  ) {
    state.attendanceLessonDirty.delete(position);
  } else {
    state.attendanceLessonDirty.set(position, {
      position,
      lesson_date: lessonDate,
      lesson_number: lessonNumber,
      _original_lesson_date: originalLessonDate,
      _original_lesson_number: originalLessonNumber,
    });
  }
  closeAttendanceLessonEditor();
  renderAttendanceJournal();
}

function syncJournalScrollControls(scroll) {
  if (!scroll) return;
  const controls = scroll.previousElementSibling;
  const range = controls?.querySelector("[data-journal-scroll-range]");
  const previousButton = controls?.querySelector('[data-journal-scroll="-1"]');
  const nextButton = controls?.querySelector('[data-journal-scroll="1"]');
  if (!range || !previousButton || !nextButton) return;
  const maximum = Math.max(scroll.scrollWidth - scroll.clientWidth, 0);
  range.disabled = maximum === 0;
  range.value = maximum ? String(Math.round((scroll.scrollLeft / maximum) * 1000)) : "0";
  previousButton.disabled = maximum === 0 || scroll.scrollLeft <= 1;
  nextButton.disabled = maximum === 0 || scroll.scrollLeft >= maximum - 1;
}

function scrollAttendanceJournal(direction) {
  const scroll = qs("#attendanceJournalList .school-journal-scroll");
  if (!scroll) return;
  const distance = Math.max(Math.round(scroll.clientWidth * 0.72), 280);
  scroll.scrollBy({ left: direction * distance, behavior: "smooth" });
}

function attendanceJournalFocusLesson(journal) {
  const lessons = Array.isArray(journal?.lessons) ? journal.lessons : [];
  const configured = lessons.find((lesson) => lesson.is_current)
    || lessons.find(
      (lesson) => Number(lesson.position) === Number(journal?.current_lesson_number),
    );
  if (configured) return configured;
  const ordered = [...lessons].sort((left, right) =>
    `${left.lesson_date}:${left.position}`.localeCompare(`${right.lesson_date}:${right.position}`),
  );
  const today = reportDateValue(new Date());
  return ordered.find((lesson) => lesson.lesson_date >= today)
    || ordered[ordered.length - 1]
    || null;
}

function attendanceJournalFocusLeft(scroll, lessonHeader) {
  const studentHeader = scroll.querySelector("thead .journal-student");
  const studentWidth = studentHeader?.offsetWidth || 0;
  const scrollRect = scroll.getBoundingClientRect();
  const lessonRect = lessonHeader.getBoundingClientRect();
  const desiredLeft = scrollRect.left + studentWidth + 8;
  return Math.max(scroll.scrollLeft + lessonRect.left - desiredLeft, 0);
}

function renderAttendanceJournal() {
  const list = qs("#attendanceJournalList");
  const title = qs("#attendanceJournalTitle");
  const meta = qs("#attendanceJournalMeta");
  const saveButton = qs("#saveAttendanceButton");
  const saveHint = qs("#attendanceSaveHint");
  const closeButton = qs("#closeAttendanceJournalButton");
  const panel = qs("#attendanceJournalPanel");
  if (!list || !title || !meta || !saveButton || !saveHint || !closeButton || !panel) return;
  panel.hidden = !state.attendanceLoading && !state.attendanceJournal;
  list.classList.toggle(
    "is-empty",
    state.attendanceLoading ||
      !state.attendanceJournal ||
      state.attendanceJournal.students.length === 0,
  );
  const previousScroll = list.querySelector(".school-journal-scroll")?.scrollLeft || 0;
  if (state.attendanceLoading) {
    title.textContent = "Открываем журнал";
    meta.textContent = "Загружаем учеников и даты занятий";
    list.innerHTML = '<div class="empty-state">Загружаем журнал...</div>';
    saveButton.hidden = true;
    closeButton.hidden = false;
    return;
  }
  const journal = state.attendanceJournal;
  if (!journal) {
    title.textContent = "Выберите группу";
    meta.textContent = "Посещаемость и отработки";
    list.innerHTML = '<div class="empty-state">Откройте журнал нужной группы.</div>';
    saveButton.hidden = true;
    saveHint.textContent = "";
    closeButton.hidden = true;
    return;
  }
  title.textContent = journal.group_name;
  meta.textContent = `${journal.course_name} · ${journal.lesson_time.slice(0, 5)}`;
  closeButton.hidden = false;
  if (!journal.students.length) {
    list.innerHTML = '<div class="empty-state">В этой группе нет активных учеников.</div>';
    saveButton.hidden = true;
    saveHint.textContent = "";
    return;
  }
  const targetLesson = attendanceJournalFocusLesson(journal);
  const targetPosition = Number(targetLesson?.position || 0);
  const lessonHeaders = journal.lessons
    .map(
      (lesson, index) => {
        const previousLesson = journal.lessons[index - 1];
        const monthChanged = !previousLesson || formatJournalMonth(previousLesson.lesson_date) !== formatJournalMonth(lesson.lesson_date);
        const isTargetLesson = Number(lesson.position) === targetPosition;
        return `
        <th class="journal-date ${isTargetLesson ? "is-current" : ""} ${lesson.is_future ? "is-future" : ""}" data-current-lesson="${isTargetLesson ? "true" : "false"}">
          ${monthChanged ? `<span class="journal-month">${escapeHtml(formatJournalMonth(lesson.lesson_date))}</span>` : ""}
          <button
            class="journal-lesson-edit"
            type="button"
            data-edit-attendance-lesson="${lesson.position}"
            title="Изменить дату и номер урока"
            aria-label="Изменить занятие ${lesson.lesson_number} от ${formatJournalDate(lesson.lesson_date)}"
          >
            <span>${formatJournalDate(lesson.lesson_date)}</span>
            <small>Урок ${lesson.lesson_number}</small>
            <i data-lucide="pencil"></i>
          </button>
        </th>`;
      },
    )
    .join("");
  const studentRows = journal.students
    .map((student) => {
      const cells = journal.lessons
        .map((lesson) => {
          const mark = attendanceMark(student, lesson.lesson_date);
          const disabled = lesson.is_future ? "disabled" : "";
          const status = mark?.present === true
            ? "present"
            : mark?.present === false && mark?.makeup_completed
              ? "makeup"
              : mark?.present === false
                ? "absent"
                : "empty";
          const statusLabel = status === "present"
            ? "Был на уроке"
            : status === "makeup"
              ? "Пропуск отработан"
              : status === "absent"
                ? "Не был на уроке"
                : "Отметка не поставлена";
          return `
            <td class="journal-mark ${mark?.present === true ? "is-present" : ""} ${mark?.present === false ? "is-absent" : ""} ${mark?.makeup_completed ? "has-makeup" : ""}">
              <button
                type="button"
                class="journal-attendance-box is-${status}"
                data-attendance-cycle="true"
                data-student-id="${escapeHtml(student.student_id)}"
                data-lesson-date="${lesson.lesson_date}"
                aria-label="${escapeHtml(student.student_name)}, ${formatJournalDate(lesson.lesson_date)}: ${statusLabel}"
                title="${statusLabel}"
                ${disabled}
              >${status === "makeup" ? '<span aria-hidden="true">✓</span>' : ""}</button>
            </td>`;
        })
        .join("");
      return `<tr><th class="journal-student" scope="row">${escapeHtml(student.student_name)}</th>${cells}</tr>`;
    })
    .join("");
  list.innerHTML = `
    <div class="journal-toolbar">
      <div class="journal-legend">
        <span><b class="legend-present"></b> был</span>
        <span><b class="legend-absent"></b> не был</span>
        <span><b class="legend-makeup">✓</b> отработано</span>
      </div>
      <div class="journal-quick-actions">
        <button type="button" class="secondary-action" data-journal-current><i data-lucide="locate-fixed"></i><span>Текущий урок</span></button>
        ${targetLesson ? `<button type="button" class="secondary-action" data-mark-all-present="${targetLesson.lesson_date}"><i data-lucide="check-check"></i><span>Все были</span></button>` : ""}
      </div>
    </div>
    <div class="journal-swipe-hint"><i data-lucide="move-horizontal"></i><span>Листайте журнал пальцем</span></div>
    <div class="journal-scroll-controls" aria-label="Прокрутка уроков">
      <button type="button" data-journal-scroll="-1" title="Предыдущие уроки" aria-label="Предыдущие уроки">
        <i data-lucide="chevron-left"></i>
      </button>
      <input
        type="range"
        min="0"
        max="1000"
        value="0"
        step="1"
        data-journal-scroll-range="true"
        aria-label="Прокрутить список уроков"
      />
      <button type="button" data-journal-scroll="1" title="Следующие уроки" aria-label="Следующие уроки">
        <i data-lucide="chevron-right"></i>
      </button>
    </div>
    <div class="school-journal-scroll" tabindex="0">
      <table class="school-journal-table">
        <thead><tr><th class="journal-student">Ученик</th>${lessonHeaders}</tr></thead>
        <tbody>${studentRows}</tbody>
      </table>
    </div>`;
  refreshIcons();
  const changeCount = attendanceChangesCount();
  saveButton.hidden = false;
  saveButton.disabled = state.attendanceSaving || changeCount === 0;
  saveButton.textContent = state.attendanceSaving ? "Сохраняем..." : "Сохранить журнал";
  saveHint.textContent = changeCount
    ? `Изменений: ${changeCount}`
    : "Все изменения сохранены";
  requestAnimationFrame(() => {
    const scroll = list.querySelector(".school-journal-scroll");
    if (!scroll) return;
    if (state.attendanceAutoScroll) {
      const current = scroll.querySelector('[data-current-lesson="true"]');
      if (current) {
        scroll.scrollLeft = attendanceJournalFocusLeft(scroll, current);
      }
      state.attendanceAutoScroll = false;
    } else {
      scroll.scrollLeft = previousScroll;
    }
    syncJournalScrollControls(scroll);
    scroll.addEventListener("scroll", () => syncJournalScrollControls(scroll), { passive: true });
  });
}

function scrollJournalToCurrent() {
  const scroll = qs("#attendanceJournalList .school-journal-scroll");
  const current = scroll?.querySelector('[data-current-lesson="true"]');
  if (!scroll || !current) return;
  scroll.scrollTo({
    left: attendanceJournalFocusLeft(scroll, current),
    behavior: "smooth",
  });
}

function markGroupPresent(lessonDate) {
  const journal = state.attendanceJournal;
  if (!journal || !lessonDate) return;
  journal.students.forEach((student) => {
    let mark = attendanceMark(student, lessonDate);
    if (!mark) {
      mark = { lesson_date: lessonDate, present: true, makeup_completed: false, comment: null };
      student.marks.push(mark);
    } else {
      mark.present = true;
      mark.makeup_completed = false;
    }
    rememberAttendanceChange(student, lessonDate);
  });
  renderAttendanceJournal();
  showNotice(`Отмечено присутствие: ${journal.students.length} учен.`, "ok", { duration: 3200 });
}

function demoGroupAttendanceJournal(schedule) {
  const today = reportDateValue(new Date());
  const lessons = Array.from({ length: Math.max(schedule.lesson_count || 1, 1) }, (_, index) => {
    const lessonDate = dateAfterWeeks(schedule.first_lesson_date, index);
    return {
      position: index + 1,
      lesson_date: lessonDate,
      lesson_number: index + 1,
      lesson_title: `Урок ${index + 1}`,
      is_current: index + 1 === schedule.current_lesson_number,
      is_future: lessonDate > today,
    };
  });
  return {
    schedule_id: schedule.id,
    group_name: schedule.group_name,
    course_name: schedule.course_name,
    lesson_time: schedule.lesson_time,
    current_lesson_number: schedule.current_lesson_number,
    lessons,
    students: studentsForGroup(schedule.group_name).map((student) => ({
      student_id: student.id,
      student_name: student.name,
      group_name: schedule.group_name,
      marks: [],
    })),
  };
}

async function loadAttendanceJournal(scheduleId) {
  const schedule = teachingWorkspace().schedules.find((item) => item.id === scheduleId);
  if (!schedule) return;
  if (hasAttendanceChanges() && scheduleId !== state.attendanceScheduleId) {
    showNotice("Сначала сохраните изменения в открытом журнале", "danger");
    return;
  }
  state.attendanceScheduleId = scheduleId;
  state.attendanceJournal = null;
  state.attendanceDirty = new Map();
  state.attendanceLessonDirty = new Map();
  state.attendanceLoading = true;
  state.attendanceAutoScroll = true;
  renderTeaching();
  try {
    if (apiContext.demoMode || !apiContext.maxUserId) {
      state.attendanceJournal = demoGroupAttendanceJournal(schedule);
    } else {
      const params = new URLSearchParams({
        max_user_id: String(apiContext.maxUserId),
        tenant_slug: apiContext.tenantSlug || "",
      });
      const response = await apiFetch(
        `/api/v1/teaching/schedules/${encodeURIComponent(scheduleId)}/journal?${params}`,
      );
      if (!response.ok) throw new Error(await parseApiError(response));
      state.attendanceJournal = await response.json();
    }
  } catch (error) {
    state.attendanceScheduleId = "";
    showNotice(error.message || "Не удалось открыть журнал", "danger");
  } finally {
    state.attendanceLoading = false;
    renderTeaching();
    if (window.matchMedia("(max-width: 960px)").matches) {
      qs("#attendanceJournalPanel")?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }
}

function closeAttendanceJournal() {
  if (hasAttendanceChanges()) {
    showNotice("Сначала сохраните изменения в журнале", "danger");
    return;
  }
  state.attendanceScheduleId = "";
  state.attendanceJournal = null;
  state.attendanceDirty = new Map();
  state.attendanceLessonDirty = new Map();
  renderTeaching();
  qs(".journal-groups-panel")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function saveAttendanceJournal() {
  const journal = state.attendanceJournal;
  const items = [...state.attendanceDirty.values()].map(
    ({ _original, ...item }) => item,
  );
  const lessons = [...state.attendanceLessonDirty.values()].map(
    ({ _original_lesson_date, _original_lesson_number, ...lesson }) => lesson,
  );
  if (!journal || (!items.length && !lessons.length) || state.attendanceSaving) return;
  state.attendanceSaving = true;
  renderAttendanceJournal();
  try {
    if (!apiContext.demoMode && apiContext.maxUserId) {
      const response = await apiFetch(
        `/api/v1/teaching/schedules/${encodeURIComponent(journal.schedule_id)}/journal`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            max_user_id: Number(apiContext.maxUserId),
            tenant_slug: apiContext.tenantSlug || undefined,
            items,
            lessons,
          }),
        },
      );
      if (!response.ok) throw new Error(await parseApiError(response));
      state.attendanceJournal = await response.json();
    }
    state.attendanceDirty = new Map();
    state.attendanceLessonDirty = new Map();
    showNotice("Журнал сохранен");
  } catch (error) {
    showNotice(error.message || "Не удалось сохранить журнал", "danger");
  } finally {
    state.attendanceSaving = false;
    renderAttendanceJournal();
  }
}

function renderScheduleEditor() {
  const editor = qs("#scheduleEditor");
  if (!editor) return;
  editor.hidden = !state.scheduleEditorOpen;
  if (!state.scheduleEditorOpen) return;
  const workspace = teachingWorkspace();
  const item = workspace.schedules.find((schedule) => schedule.id === state.editingScheduleId);
  const selectedGroup = item?.group_name || state.scheduleDraftGroup;
  const today = new Date().toISOString().slice(0, 10);
  const scheduledGroups = new Set(
    workspace.schedules
      .filter((schedule) => schedule.id !== item?.id)
      .map((schedule) => schedule.group_name),
  );
  const groupNames = [...new Set([
    ...(selectedGroup ? [selectedGroup] : []),
    ...workspace.groups
      .map((group) => group.name)
      .filter((groupName) => !scheduledGroups.has(groupName)),
  ])];
  const groupField = groupNames.length
    ? `<select id="scheduleGroupName"><option value="">Выберите группу</option>${groupNames
        .map(
          (groupName) =>
            `<option value="${escapeHtml(groupName)}" ${groupName === selectedGroup ? "selected" : ""}>${escapeHtml(groupName)}</option>`,
        )
        .join("")}</select>`
    : '<input id="scheduleGroupName" value="" placeholder="Название группы" />';
  editor.innerHTML = `
    <div class="schedule-editor-head"><div><p class="eyebrow">${item ? "Редактирование" : "Новая группа"}</p><h3>${escapeHtml(selectedGroup || "Добавить занятие")}</h3></div><button class="icon-button" type="button" data-close-schedule title="Закрыть">×</button></div>
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
    </div>
    <div class="schedule-editor-actions"><button class="secondary-action" type="button" data-close-schedule>Отмена</button><button id="scheduleSaveButton" class="primary-action" type="button">Сохранить расписание</button></div>`;
}

function renderScheduleList() {
  const list = qs("#scheduleList");
  if (!list) return;
  const workspace = teachingWorkspace();
  const items = workspace.schedules;
  if (state.teachingLoading) return void (list.innerHTML = '<div class="empty-state">Загружаем расписание...</div>');
  const groupsByName = new Map();
  workspace.groups.forEach((group) => {
    const existing = groupsByName.get(group.name);
    groupsByName.set(group.name, {
      ...group,
      student_count: (existing?.student_count || 0) + group.student_count,
      course_name: existing?.course_name || group.course_name,
    });
  });
  const scheduledNames = new Set(items.map((item) => item.group_name));
  const unscheduledGroups = [...groupsByName.values()].filter(
    (group) => !scheduledNames.has(group.name),
  );
  if (!items.length && !unscheduledGroups.length) {
    list.innerHTML = '<div class="empty-state">Доступных групп пока нет.</div>';
    return;
  }
  const scheduledRows = items
    .map((item) => {
      const group = groupsByName.get(item.group_name);
      return `
        <article class="schedule-card ${item.is_active ? "" : "is-paused"} ${state.attendanceScheduleId === item.id ? "is-selected" : ""}">
          <div class="schedule-time">
            <strong>${escapeHtml(item.lesson_time.slice(0, 5))}</strong>
            <span>${escapeHtml(weekdayNames[item.weekday] || "")}</span>
          </div>
          <div class="schedule-main">
            <div class="schedule-card-title">
              <h3>${escapeHtml(item.group_name)}</h3>
              <span class="soft-badge">${group?.student_count || 0} учеников</span>
            </div>
            <p>${escapeHtml(item.course_name)}</p>
            <div class="schedule-next">
              <strong>${formatTeachingDate(item.next_lesson_date)}</strong>
              <span>Урок ${item.next_lesson_number || item.current_lesson_number} из ${item.lesson_count}</span>
            </div>
          </div>
          <div class="schedule-actions">
            <button class="primary-action" type="button" data-open-attendance="${escapeHtml(item.id)}">Журнал</button>
            <button class="secondary-action" type="button" data-edit-schedule="${escapeHtml(item.id)}">Изменить</button>
          </div>
        </article>`;
    })
    .join("");
  const unscheduledRows = unscheduledGroups
    .map(
      (group) => `
        <article class="schedule-card is-unconfigured">
          <div class="schedule-time">
            <strong>--:--</strong>
            <span>Не настроено</span>
          </div>
          <div class="schedule-main">
            <div class="schedule-card-title">
              <h3>${escapeHtml(group.name)}</h3>
              <span class="soft-badge">${group.student_count} учеников</span>
            </div>
            <p>${escapeHtml(group.course_name || "Курс не указан")}</p>
            <div class="schedule-next"><strong>Добавьте день и время занятия</strong></div>
          </div>
          <div class="schedule-actions">
            <button class="primary-action" type="button" data-configure-schedule="${escapeHtml(group.name)}">Настроить</button>
          </div>
        </article>`,
    )
    .join("");
  list.innerHTML = scheduledRows + unscheduledRows;
}

function renderFeedbackHistory() {
  const list = qs("#feedbackHistory");
  if (!list) return;
  const outputs = teachingWorkspace().feedback_outputs;
  if (outputs.length === 0) return void (list.innerHTML = '<div class="empty-state">Сформированные обратные связи появятся здесь.</div>');
  list.innerHTML = outputs.slice(0, 10).map((item) => `<button class="feedback-history-row" type="button" data-open-feedback="${escapeHtml(item.id)}"><span><strong>${escapeHtml(item.group_name)}</strong><small>${formatTeachingDate(item.lesson_date)} · урок ${item.lesson_number}</small></span><span>›</span></button>`).join("");
}

function openScheduleEditor(scheduleId = "", groupName = "") {
  state.editingScheduleId = scheduleId;
  state.scheduleDraftGroup = groupName;
  state.scheduleEditorOpen = true;
  renderTeaching();
  qs("#scheduleEditor")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function closeScheduleEditor() {
  state.scheduleEditorOpen = false;
  state.editingScheduleId = "";
  state.scheduleDraftGroup = "";
  renderTeaching();
}

async function saveTeachingSchedule() {
  const groupName = qs("#scheduleGroupName")?.value.trim();
  const courseId = qs("#scheduleCourseId")?.value;
  if (!groupName || !courseId) return showNotice("Укажите группу и курс", "danger");
  const payload = { max_user_id: Number(apiContext.maxUserId || 1), tenant_slug: apiContext.tenantSlug || null, schedule_id: state.editingScheduleId || null, group_name: groupName, course_id: courseId, first_lesson_date: qs("#scheduleFirstDate").value, lesson_time: qs("#scheduleTime").value, duration_minutes: Number(qs("#scheduleDuration").value), lesson_mode: qs("#scheduleMode").value, lesson_place: qs("#schedulePlace").value.trim() || "offline", current_lesson_number: Number(qs("#scheduleLessonNumber").value || 1), lesson_offset: 0, auto_feedback_enabled: qs("#scheduleAutoFeedback").checked, parent_delivery_enabled: false, is_active: true };
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
      const response = await apiFetch("/api/v1/teaching/schedules", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
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

function openFeedbackDialog(outputId) {
  const output = teachingWorkspace().feedback_outputs.find((item) => item.id === outputId);
  if (!output) return;
  state.generatedFeedback = output.feedback_text || "";
  state.generatedFeedbackId = output.id || "";
  qs("#feedbackDialogTitle").textContent = output.group_name;
  qs("#feedbackDialogContent").innerHTML = `<textarea id="feedbackResult" class="feedback-result" readonly>${escapeHtml(output.feedback_text)}</textarea>`;
  qs("#copyFeedbackButton").hidden = false;
  qs("#feedbackDialog").hidden = false;
}

function closeFeedbackDialog() {
  qs("#feedbackDialog").hidden = true;
  state.generatedFeedback = "";
  state.generatedFeedbackId = "";
}

async function copyGeneratedFeedback() {
  if (!state.generatedFeedback) return;
  await navigator.clipboard.writeText(state.generatedFeedback);
  showNotice("Текст ОС скопирован");
}

function availableBroadcastVenues() {
  return [...new Set(
    students
      .map((student) => String(student.venue || "").trim())
      .filter(Boolean),
  )].sort((left, right) => left.localeCompare(right, "ru"));
}

function broadcastVenueFilterValue() {
  return qs("#broadcastVenueFilter")?.value || "all";
}

function broadcastLessonModeFilterValue() {
  return qs("#broadcastLessonModeFilter")?.value || "all";
}

function broadcastScheduleForGroup(groupName) {
  return teachingWorkspace().schedules.find(
    (schedule) => schedule.is_active !== false && schedule.group_name === groupName,
  );
}

function availableBroadcastGroups() {
  const venueFilter = broadcastVenueFilterValue();
  const lessonModeFilter = broadcastLessonModeFilterValue();
  return [...new Set(
    students
      .filter((student) => {
        if (venueFilter !== "all" && String(student.venue || "") !== venueFilter) return false;
        if (lessonModeFilter === "all") return true;
        return broadcastScheduleForGroup(student.group)?.lesson_mode === lessonModeFilter;
      })
      .map((student) => String(student.group || "").trim())
      .filter(Boolean),
  )].sort((left, right) => left.localeCompare(right, "ru"));
}

function renderBroadcastTargetFilters() {
  const venueSelect = qs("#broadcastVenueFilter");
  if (!venueSelect) return;
  const currentVenue = venueSelect.value || "all";
  const venues = availableBroadcastVenues();
  venueSelect.innerHTML = [
    '<option value="all">Все площадки</option>',
    ...venues.map(
      (venueName) => `<option value="${escapeHtml(venueName)}">${escapeHtml(venueName)}</option>`,
    ),
  ].join("");
  venueSelect.value = venues.includes(currentVenue) ? currentVenue : "all";
}

function selectedBroadcastGroups() {
  const available = new Set(availableBroadcastGroups());
  return [...state.broadcastSelectedGroups]
    .filter((groupName) => available.has(groupName))
    .sort((left, right) => left.localeCompare(right, "ru"));
}

function broadcastAudiencePayload() {
  return {
    max_user_id: Number(apiContext.maxUserId || 1),
    tenant_slug: apiContext.tenantSlug || undefined,
    recipient_category: qs("#broadcastRecipientCategory")?.value || "all",
    audience_filter: qs("#broadcastAudienceFilter")?.value || "all",
    group_names: state.broadcastAllGroups ? [] : selectedBroadcastGroups(),
    venue_names:
      broadcastVenueFilterValue() === "all" ? [] : [broadcastVenueFilterValue()],
    lesson_modes:
      broadcastLessonModeFilterValue() === "all" ? [] : [broadcastLessonModeFilterValue()],
    balance_threshold:
      qs("#broadcastAudienceFilter")?.value === "low_balance"
        ? Number(qs("#broadcastBalanceThreshold")?.value || 300)
        : null,
  };
}

function broadcastAudienceSignature() {
  return JSON.stringify(broadcastAudiencePayload());
}

function invalidateBroadcastPreview() {
  state.broadcastPreview = null;
  state.broadcastPreviewSignature = "";
  renderBroadcastAudiencePreview();
}

function renderBroadcastGroups() {
  const list = qs("#broadcastGroupList");
  const hint = qs("#broadcastGroupHint");
  if (!list || !hint) return;
  const groups = availableBroadcastGroups();
  if (groups.length === 0) {
    list.innerHTML = '<div class="empty-state">Подходящих групп нет.</div>';
    hint.textContent =
      broadcastVenueFilterValue() !== "all" || broadcastLessonModeFilterValue() !== "all"
        ? "Измените площадку или формат занятий."
        : "После импорта учеников группы появятся здесь.";
    return;
  }
  hint.textContent = state.broadcastAllGroups
    ? `Выбраны все группы: ${groups.length}`
    : selectedBroadcastGroups().length
      ? `Выбрано групп: ${selectedBroadcastGroups().length}`
      : "Выберите хотя бы одну группу.";
  list.innerHTML = groups
    .map(
      (groupName) => `
        <label class="broadcast-group-option">
          <input
            type="checkbox"
            data-broadcast-group="${escapeHtml(groupName)}"
            ${state.broadcastAllGroups || state.broadcastSelectedGroups.has(groupName) ? "checked" : ""}
          />
          <span>${escapeHtml(groupName)}</span>
        </label>
      `,
    )
    .join("");
}

function renderBroadcastPhoto() {
  const preview = qs("#broadcastPhotoPreview");
  const pickerLabel = qs(".broadcast-photo-picker span");
  if (!preview) return;
  if (!state.broadcastPhotoPreviewUrl) {
    preview.hidden = true;
    preview.innerHTML = "";
    if (pickerLabel) pickerLabel.textContent = "Добавить фото";
    return;
  }
  preview.hidden = false;
  preview.innerHTML = `
    <img src="${escapeHtml(state.broadcastPhotoPreviewUrl)}" alt="Фото к новости" />
    <button type="button" data-remove-broadcast-photo title="Убрать фото" aria-label="Убрать фото">
      <i data-lucide="x"></i>
    </button>
  `;
  if (pickerLabel) pickerLabel.textContent = state.broadcastPhotoFile?.name || "Заменить фото";
}

function broadcastStatusLabel(status) {
  return {
    sending: "Отправляется",
    sent: "Отправлено",
    partial: "Частично",
    failed: "Ошибка",
  }[status] || status;
}

function broadcastAudienceLabel(item) {
  const recipients = {
    all: "родители и ученики",
    parents: "родители",
    students: "ученики",
  }[item.recipient_category] || "получатели";
  const groups = item.group_names?.length
    ? `${item.group_names.length} гр.`
    : "все группы";
  const venues = item.venue_names?.length ? item.venue_names.join(", ") : "все площадки";
  const lessonModes = item.lesson_modes?.length
    ? item.lesson_modes
        .map((mode) => (mode === "individual" ? "индивидуально" : "в группах"))
        .join(", ")
    : "любой формат";
  return `${recipients} · ${venues} · ${lessonModes} · ${groups}`;
}

function formatBroadcastDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function renderBroadcastHistory() {
  const list = qs("#broadcastHistory");
  if (!list) return;
  if (state.broadcastHistoryLoading) {
    list.innerHTML = '<div class="empty-state">Загружаем историю...</div>';
    return;
  }
  if (state.broadcastHistory.length === 0) {
    list.innerHTML = '<div class="empty-state">Отправленных новостей пока нет.</div>';
    return;
  }
  list.innerHTML = state.broadcastHistory
    .map(
      (item) => `
        <article class="broadcast-history-item">
          ${item.image_url ? `<img class="broadcast-history-image" src="${escapeHtml(item.image_url)}" alt="" loading="lazy" />` : ""}
          <div class="broadcast-history-head">
            <strong>${escapeHtml(item.title || "Без заголовка")}</strong>
            <span class="broadcast-status is-${escapeHtml(item.status)}">${escapeHtml(broadcastStatusLabel(item.status))}</span>
          </div>
          <p>${escapeHtml(item.message)}</p>
          <div class="broadcast-history-meta">
            <span>${escapeHtml(broadcastAudienceLabel(item))}</span>
            <span>${Number(item.delivered_count || 0)} из ${Number(item.recipient_count || 0)}</span>
          </div>
          <div class="broadcast-history-meta">
            <span>${escapeHtml(item.creator_name || "Сотрудник")}</span>
            <time>${escapeHtml(formatBroadcastDate(item.sent_at || item.created_at))}</time>
          </div>
          <div class="broadcast-history-actions">
            <button type="button" class="text-action" data-duplicate-broadcast="${escapeHtml(item.id || "")}"><i data-lucide="copy"></i>Повторить</button>
            ${item.status === "failed" || item.status === "partial" ? `<button type="button" class="text-action" data-retry-broadcast="${escapeHtml(item.id || "")}"><i data-lucide="refresh-cw"></i>Отправить снова</button>` : ""}
          </div>
        </article>
      `,
    )
    .join("");
}

function broadcastDraftStorageKey() {
  return `algo-max-broadcast-draft:${apiContext.tenantSlug || "default"}:${apiContext.maxUserId || "demo"}`;
}

function broadcastDraftPayload() {
  return {
    title: qs("#broadcastTitle")?.value || "",
    message: qs("#broadcastMessage")?.value || "",
    recipientCategory: qs("#broadcastRecipientCategory")?.value || "all",
    audienceFilter: qs("#broadcastAudienceFilter")?.value || "all",
    venueFilter: broadcastVenueFilterValue(),
    lessonModeFilter: broadcastLessonModeFilterValue(),
    balanceThreshold: qs("#broadcastBalanceThreshold")?.value || "300",
    allGroups: state.broadcastAllGroups,
    groups: selectedBroadcastGroups(),
    savedAt: new Date().toISOString(),
  };
}

function saveBroadcastDraft({ quiet = false } = {}) {
  try {
    const draft = broadcastDraftPayload();
    localStorage.setItem(broadcastDraftStorageKey(), JSON.stringify(draft));
    state.broadcastDraftSavedAt = new Date(draft.savedAt);
    const label = qs("#broadcastDraftState");
    if (label) label.textContent = `Черновик сохранен в ${state.broadcastDraftSavedAt.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}`;
    if (!quiet) showNotice("Черновик новости сохранен");
  } catch (error) {
    console.warn("Не удалось сохранить черновик рассылки", error);
  }
}

function scheduleBroadcastDraftSave() {
  window.clearTimeout(broadcastDraftTimer);
  const label = qs("#broadcastDraftState");
  if (label) label.textContent = "Сохраняем черновик...";
  broadcastDraftTimer = window.setTimeout(() => saveBroadcastDraft({ quiet: true }), 500);
}

function restoreBroadcastDraft() {
  try {
    const draft = JSON.parse(localStorage.getItem(broadcastDraftStorageKey()) || "null");
    if (!draft || typeof draft !== "object") return;
    qs("#broadcastTitle").value = draft.title || "";
    qs("#broadcastMessage").value = draft.message || "";
    qs("#broadcastRecipientCategory").value = draft.recipientCategory || "all";
    qs("#broadcastAudienceFilter").value = draft.audienceFilter || "all";
    renderBroadcastTargetFilters();
    qs("#broadcastVenueFilter").value = draft.venueFilter || "all";
    qs("#broadcastLessonModeFilter").value = draft.lessonModeFilter || "all";
    qs("#broadcastBalanceThreshold").value = draft.balanceThreshold || "300";
    state.broadcastAllGroups = draft.allGroups !== false;
    state.broadcastSelectedGroups = new Set(Array.isArray(draft.groups) ? draft.groups : []);
    state.broadcastDraftSavedAt = draft.savedAt ? new Date(draft.savedAt) : null;
  } catch (error) {
    console.warn("Не удалось восстановить черновик рассылки", error);
  }
}

function clearBroadcastDraft() {
  try {
    localStorage.removeItem(broadcastDraftStorageKey());
  } catch (error) {
    console.warn("Не удалось удалить черновик рассылки", error);
  }
  state.broadcastDraftSavedAt = null;
}

function setBroadcastStep(step) {
  state.broadcastStep = Math.min(Math.max(Number(step) || 1, 1), 3);
  if (state.broadcastStep === 3) previewBroadcastAudience();
  renderBroadcasts();
}

function moveBroadcastStep(direction) {
  if (direction === "back") {
    setBroadcastStep(state.broadcastStep - 1);
    return;
  }
  if (state.broadcastStep === 1 && !state.broadcastAllGroups && selectedBroadcastGroups().length === 0) {
    showNotice("Выберите хотя бы одну группу", "danger");
    return;
  }
  if (state.broadcastStep === 2 && !qs("#broadcastMessage")?.value.trim()) {
    showNotice("Введите текст новости", "danger");
    qs("#broadcastMessage")?.focus();
    return;
  }
  setBroadcastStep(state.broadcastStep + 1);
}

function renderBroadcastLivePreview() {
  const preview = qs("#broadcastLivePreview");
  if (!preview) return;
  const title = qs("#broadcastTitle")?.value.trim() || "Новость школы";
  const message = qs("#broadcastMessage")?.value.trim() || "Введите текст новости, чтобы увидеть сообщение.";
  preview.innerHTML = `
    ${state.broadcastPhotoPreviewUrl ? `<img src="${escapeHtml(state.broadcastPhotoPreviewUrl)}" alt="" />` : ""}
    <div class="broadcast-preview-bubble">
      <strong>${escapeHtml(title)}</strong>
      <p>${escapeHtml(message)}</p>
      <span>Открыть в Algo MAX</span>
    </div>`;
}

function duplicateBroadcast(itemId) {
  const item = state.broadcastHistory.find((entry) => String(entry.id || "") === String(itemId));
  if (!item) return;
  qs("#broadcastTitle").value = item.title || "";
  qs("#broadcastMessage").value = item.message || "";
  qs("#broadcastRecipientCategory").value = item.recipient_category || "all";
  qs("#broadcastAudienceFilter").value = item.audience_filter || "all";
  renderBroadcastTargetFilters();
  qs("#broadcastVenueFilter").value = item.venue_names?.[0] || "all";
  qs("#broadcastLessonModeFilter").value = item.lesson_modes?.[0] || "all";
  state.broadcastAllGroups = !(item.group_names || []).length;
  state.broadcastSelectedGroups = new Set(item.group_names || []);
  invalidateBroadcastPreview();
  state.broadcastStep = 1;
  scheduleBroadcastDraftSave();
  renderBroadcasts();
  qs("#broadcastForm")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderBroadcastAudiencePreview() {
  const preview = qs("#broadcastAudiencePreview");
  const previewButton = qs("#previewBroadcastButton");
  const sendButton = qs("#sendBroadcastButton");
  if (!preview || !previewButton || !sendButton) return;
  preview.classList.remove("is-empty");
  if (state.broadcastPreviewLoading) {
    preview.innerHTML = '<i data-lucide="loader-circle"></i><span>Считаем получателей...</span>';
  } else if (!state.broadcastAllGroups && selectedBroadcastGroups().length === 0) {
    preview.classList.add("is-empty");
    preview.innerHTML = '<i data-lucide="users"></i><span>Выберите хотя бы одну группу</span>';
  } else if (!state.broadcastPreview) {
    preview.innerHTML = '<i data-lucide="users"></i><span>Сначала проверьте количество получателей</span>';
  } else if (state.broadcastPreview.recipient_count === 0) {
    preview.classList.add("is-empty");
    preview.innerHTML = '<i data-lucide="user-round-x"></i><span>По выбранным условиям получателей нет</span>';
  } else {
    const unavailable = Number(state.broadcastPreview.unavailable_students || 0);
    preview.innerHTML = `
      <i data-lucide="users-round"></i>
      <span><strong>${Number(state.broadcastPreview.recipient_count)}</strong> получателей · ${Number(state.broadcastPreview.matched_students)} учеников${unavailable ? `<small>${unavailable} учен. без доступного контакта</small>` : ""}</span>
    `;
  }
  const previewIsCurrent =
    state.broadcastPreviewSignature === broadcastAudienceSignature();
  previewButton.disabled = state.broadcastPreviewLoading || state.broadcastSaving;
  sendButton.disabled =
    state.broadcastSaving ||
    state.broadcastPreviewLoading ||
    !previewIsCurrent ||
    !state.broadcastPreview?.recipient_count;
  const sendLabel = sendButton.querySelector("span");
  if (sendLabel) {
    sendLabel.textContent = state.broadcastSaving
      ? "Отправляем..."
      : "Отправить новость";
  }
  refreshIcons();
}

function renderBroadcasts() {
  const form = qs("#broadcastForm");
  if (form) form.dataset.currentStep = String(state.broadcastStep);
  qsa("[data-broadcast-step]").forEach((button) => {
    const active = Number(button.dataset.broadcastStep) === state.broadcastStep;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-selected", String(active));
  });
  const backButton = qs("#broadcastBackButton");
  const nextButton = qs("#broadcastNextButton");
  if (backButton) backButton.hidden = state.broadcastStep === 1;
  if (nextButton) nextButton.hidden = state.broadcastStep === 3;
  const tenantLabel = qs("#broadcastTenantLabel");
  if (tenantLabel) tenantLabel.textContent = tenantTitle();
  const filter = qs("#broadcastAudienceFilter")?.value || "all";
  const thresholdField = qs("#broadcastBalanceThresholdField");
  if (thresholdField) thresholdField.hidden = filter !== "low_balance";
  const message = qs("#broadcastMessage")?.value || "";
  const count = qs("#broadcastMessageCount");
  if (count) count.textContent = String(message.length);
  const draftLabel = qs("#broadcastDraftState");
  if (draftLabel && state.broadcastDraftSavedAt) {
    draftLabel.textContent = `Черновик сохранен в ${state.broadcastDraftSavedAt.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}`;
  }
  renderBroadcastTargetFilters();
  renderBroadcastGroups();
  renderBroadcastPhoto();
  renderBroadcastLivePreview();
  renderBroadcastAudiencePreview();
  renderBroadcastHistory();
}

function demoBroadcastPreview(payload) {
  let matched = [...students];
  if (payload.group_names.length) {
    const groupNames = new Set(payload.group_names);
    matched = matched.filter((student) => groupNames.has(student.group));
  }
  if (payload.venue_names.length) {
    const venueNames = new Set(payload.venue_names);
    matched = matched.filter((student) => venueNames.has(student.venue));
  }
  if (payload.lesson_modes.length) {
    const lessonModes = new Set(payload.lesson_modes);
    matched = matched.filter((student) =>
      lessonModes.has(broadcastScheduleForGroup(student.group)?.lesson_mode),
    );
  }
  if (payload.audience_filter === "low_balance") {
    const threshold = Number(payload.balance_threshold ?? 300);
    matched = matched.filter((student) => Number(student.balance || 0) <= threshold);
  } else if (payload.audience_filter === "active_orders") {
    const studentIds = new Set(
      orders
        .filter((order) => ["created", "reserved", "transferred_to_teacher", "problem"].includes(order.status))
        .map((order) => order.studentId),
    );
    matched = matched.filter((student) => studentIds.has(student.id));
  } else if (payload.audience_filter === "no_orders") {
    const studentIds = new Set(orders.map((order) => order.studentId));
    matched = matched.filter((student) => !studentIds.has(student.id));
  }
  const multiplier = payload.recipient_category === "all" ? 2 : 1;
  return {
    recipient_count: matched.length * multiplier,
    matched_students: matched.length,
    unavailable_students: 0,
    selected_groups: payload.group_names,
    selected_venues: payload.venue_names,
    selected_lesson_modes: payload.lesson_modes,
  };
}

async function loadBroadcastHistory() {
  if (!roleViews(state.role).includes("broadcasts")) return;
  state.broadcastHistoryLoading = true;
  renderBroadcastHistory();
  try {
    if (apiContext.demoMode || !apiContext.maxUserId) {
      state.broadcastHistoryLoaded = true;
      return;
    }
    const params = new URLSearchParams({
      max_user_id: String(apiContext.maxUserId),
      tenant_slug: apiContext.tenantSlug || "",
    });
    const response = await apiFetch(`/api/v1/miniapp/broadcasts?${params}`);
    if (!response.ok) throw new Error(await parseApiError(response));
    state.broadcastHistory = await response.json();
    state.broadcastHistoryLoaded = true;
  } finally {
    state.broadcastHistoryLoading = false;
    renderBroadcastHistory();
  }
}

async function previewBroadcastAudience() {
  if (!state.broadcastAllGroups && selectedBroadcastGroups().length === 0) {
    invalidateBroadcastPreview();
    return null;
  }
  const payload = broadcastAudiencePayload();
  const signature = JSON.stringify(payload);
  state.broadcastPreviewLoading = true;
  state.broadcastPreview = null;
  state.broadcastPreviewSignature = "";
  renderBroadcastAudiencePreview();
  try {
    if (apiContext.demoMode || !apiContext.maxUserId) {
      await new Promise((resolve) => setTimeout(resolve, 180));
      state.broadcastPreview = demoBroadcastPreview(payload);
    } else {
      const response = await apiFetch("/api/v1/miniapp/broadcasts/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error(await parseApiError(response));
      state.broadcastPreview = await response.json();
    }
    state.broadcastPreviewSignature = signature;
    return state.broadcastPreview;
  } catch (error) {
    showNotice(error.message || "Не удалось проверить аудиторию", "danger");
    return null;
  } finally {
    state.broadcastPreviewLoading = false;
    renderBroadcastAudiencePreview();
  }
}

function clearBroadcastPhoto() {
  if (state.broadcastPhotoPreviewUrl) {
    URL.revokeObjectURL(state.broadcastPhotoPreviewUrl);
  }
  state.broadcastPhotoFile = null;
  state.broadcastPhotoPreviewUrl = "";
  const input = qs("#broadcastPhotoFile");
  if (input) input.value = "";
  renderBroadcastPhoto();
}

function selectBroadcastPhoto(file) {
  const supportedTypes = new Set(["image/jpeg", "image/png", "image/webp"]);
  if (!supportedTypes.has(file.type)) {
    showNotice("Выберите изображение JPEG, PNG или WebP", "danger");
    return false;
  }
  if (file.size > 10 * 1024 * 1024) {
    showNotice("Изображение должно быть не больше 10 МБ", "danger");
    return false;
  }
  clearBroadcastPhoto();
  state.broadcastPhotoFile = file;
  state.broadcastPhotoPreviewUrl = URL.createObjectURL(file);
  renderBroadcastPhoto();
  refreshIcons();
  return true;
}

async function sendSchoolBroadcast(event) {
  event?.preventDefault();
  if (state.broadcastSaving) return;
  const title = qs("#broadcastTitle")?.value.trim() || "";
  const message = qs("#broadcastMessage")?.value.trim() || "";
  if (!message) {
    showNotice("Введите текст новости", "danger");
    qs("#broadcastMessage")?.focus();
    return;
  }

  let preview = state.broadcastPreview;
  if (
    !preview ||
    state.broadcastPreviewSignature !== broadcastAudienceSignature()
  ) {
    preview = await previewBroadcastAudience();
  }
  if (!preview?.recipient_count) return;
  if (!window.confirm(`Отправить новость ${preview.recipient_count} получателям?`)) {
    return;
  }

  const payload = broadcastAudiencePayload();
  state.broadcastSaving = true;
  renderBroadcastAudiencePreview();
  try {
    let result;
    if (apiContext.demoMode || !apiContext.maxUserId) {
      await new Promise((resolve) => setTimeout(resolve, 300));
      result = {
        id: `demo-broadcast-${Date.now()}`,
        title: title || null,
        message,
        image_url: state.broadcastPhotoPreviewUrl || null,
        recipient_category: payload.recipient_category,
        audience_filter: payload.audience_filter,
        group_names: payload.group_names,
        venue_names: payload.venue_names,
        lesson_modes: payload.lesson_modes,
        balance_threshold: payload.balance_threshold,
        status: "sent",
        recipient_count: preview.recipient_count,
        delivered_count: preview.recipient_count,
        failed_count: 0,
        creator_name: state.account?.display_name || "Сотрудник",
        sent_at: new Date().toISOString(),
        created_at: new Date().toISOString(),
      };
    } else {
      const formData = new FormData();
      formData.set("max_user_id", String(apiContext.maxUserId));
      if (apiContext.tenantSlug) formData.set("tenant_slug", apiContext.tenantSlug);
      if (title) formData.set("title", title);
      formData.set("message", message);
      formData.set("recipient_category", payload.recipient_category);
      formData.set("audience_filter", payload.audience_filter);
      if (payload.balance_threshold !== null) {
        formData.set("balance_threshold", String(payload.balance_threshold));
      }
      payload.group_names.forEach((groupName) => {
        formData.append("group_names", groupName);
      });
      payload.venue_names.forEach((venueName) => {
        formData.append("venue_names", venueName);
      });
      payload.lesson_modes.forEach((lessonMode) => {
        formData.append("lesson_modes", lessonMode);
      });
      if (state.broadcastPhotoFile) {
        formData.set("photo", state.broadcastPhotoFile);
      }
      const response = await apiFetch("/api/v1/miniapp/broadcasts", {
        method: "POST",
        body: formData,
      });
      if (!response.ok) throw new Error(await parseApiError(response));
      result = await response.json();
    }

    state.broadcastHistory.unshift(result);
    state.broadcastHistoryLoaded = true;
    qs("#broadcastForm")?.reset();
    state.broadcastSelectedGroups = new Set();
    state.broadcastAllGroups = true;
    state.broadcastPreview = null;
    state.broadcastPreviewSignature = "";
    state.broadcastStep = 1;
    clearBroadcastDraft();
    clearBroadcastPhoto();
    showNotice(
      result.failed_count
        ? `Доставлено ${result.delivered_count} из ${result.recipient_count}`
        : `Новость отправлена: ${result.delivered_count} получ.`,
      result.failed_count ? "danger" : "ok",
    );
  } catch (error) {
    showNotice(error.message || "Не удалось отправить новость", "danger");
  } finally {
    state.broadcastSaving = false;
    renderBroadcasts();
  }
}

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
  const payload = {
    sku,
    name,
    category_name: category,
    category_slug: slugify(category),
    price_astrocoins: price,
    status,
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
            return `
              <div class="order-detail-item ${needsWarehouseAssignment ? "needs-warehouse" : ""}">
                <span class="order-detail-thumb">
                  ${product?.photoUrl ? `<img src="${escapeHtml(product.photoUrl)}" alt="" />` : `<i data-lucide="${product ? productFallbackIcon(product) : "package"}"></i>`}
                </span>
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
      <label>
        <span>Причина отмены</span>
        <select id="orderCancelReason">
          ${canMarkOutOfStock ? '<option value="Товар закончился">Товар закончился</option>' : ""}
          <option value="Ошибка в заказе">Ошибка в заказе</option>
          <option value="По просьбе родителя">По просьбе родителя</option>
          <option value="Заказ не актуален">Заказ не актуален</option>
          <option value="Другое">Другое</option>
        </select>
      </label>
      ${
        canMarkOutOfStock
          ? `<label>
               <span>Товар</span>
               <select id="orderCancelProduct">${productOptions}</select>
             </label>`
          : ""
      }
      <label>
        <span>Своя причина</span>
        <input id="orderCancelCustomReason" type="text" maxlength="500" placeholder="Заполняется для варианта «Другое»" />
      </label>
      <div class="order-cancel-actions">
        <button class="secondary-action" type="button" data-cancel-order-back="${escapeHtml(orderId)}">Назад</button>
        <button class="secondary-action danger-action" type="button" data-confirm-order-cancel="${escapeHtml(orderId)}">Отменить заказ</button>
      </div>
    </div>
  `;
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
    showNotice(`Заказ №${result.order.order_number} оформлен и зарезервирован`);
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
    if (reason === "Другое" && !customReason) {
      showNotice("Укажите свою причину отмены", "danger");
      return;
    }
    updateOrderAction(confirmCancelOrderId, "cancel", { reason, customReason, productId });
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
  if (target.id === "exportAcReportButton") exportAccrualReport();
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
    const label = target.closest(".file-picker")?.querySelector("span");
    if (label) label.textContent = state.crmImportFileName || "Выбрать XLSX";
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
