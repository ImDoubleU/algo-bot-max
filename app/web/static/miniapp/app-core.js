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
  teacher: ["dashboard", "store", "orders", "wallet", "report", "accrual", "broadcasts"],
  admin: ["dashboard", "store", "orders", "wallet", "report", "accrual", "broadcasts", "admin"],
});

const VIEW_META = Object.freeze({
  dashboard: { label: "Главная", icon: "layout-dashboard" },
  store: { label: "Магазин", icon: "store" },
  cart: { label: "Корзина", icon: "shopping-bag" },
  orders: { label: "Заказы", icon: "package-check" },
  wallet: { label: "История AC", icon: "wallet-cards" },
  report: { label: "Отчет AC", icon: "file-chart-column" },
  accrual: { label: "Начисления", icon: "circle-plus" },
  broadcasts: { label: "Рассылки", icon: "megaphone" },
  admin: { label: "Управление", icon: "settings-2" },
});

const ROLE_MOBILE_PRIMARY = Object.freeze({
  student: ["dashboard", "store", "cart", "orders"],
  parent: ["dashboard", "store", "cart", "orders"],
  teacher: ["dashboard", "store", "accrual", "orders"],
  admin: ["dashboard", "orders", "admin", "store"],
});

const DEFAULT_ACCRUAL_RULES = Object.freeze([
  { reason: "Активность на уроке", amount: 10, isActive: true },
  { reason: "Домашнее задание", amount: 20, isActive: true },
  { reason: "Проект", amount: 30, isActive: true },
  { reason: "Помощь группе", amount: 10, isActive: true },
  { reason: "Бонус", amount: 50, isActive: true },
]);

const state = {
  hasAccess: apiContext.demoMode,
  accessMessage: "",
  role: "student",
  account: null,
  staffRoles: [],
  currentTenant: null,
  defaultWarehouseId: "",
  availableTenants: [],
  canManageTenants: false,
  canCreateTenants: false,
  tenantSaving: false,
  tenantSearch: "",
  availableRoles: ["student", "parent", "teacher", "admin"],
  view: ["dashboard", "store", "cart", "orders", "wallet", "report", "accrual", "broadcasts", "admin"].includes(
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
  accrualRules: DEFAULT_ACCRUAL_RULES.map((rule) => ({ ...rule })),
  accrualRulesDraft: [],
  accrualRulesSaving: false,
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
  teacherInvitations: new Map(),
  teacherInvitationsLoading: false,
  teacherInvitationsLoaded: false,
  teacherInvitationGroup: "all",
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
  warehouseSaving: false,
  warehousePreferenceSaving: false,
  warehouseEditorOpen: false,
  editingWarehouseId: "",
  opsSummary: null,
  opsSummaryLoaded: false,
  accrualReport: null,
  accrualReportLoading: false,
  accrualReportPeriod: "month",
  accrualReportTeacherFilter: "all",
  accrualReportGroupFilter: "all",
  adminEntitySearch: "",
  adminStudents: [],
  adminStudentsLoaded: false,
  adminStudentsLoading: false,
  adminStudentsError: "",
  studentLedgerById: new Map(),
  studentLedgerLoading: new Set(),
  studentLedgerErrors: new Map(),
  studentCreateOpen: false,
  studentMutationSaving: "",
  studentAccessPolicy: {
    departedAccessDays: 30,
    freezeFrom: "",
    freezeUntil: "",
  },
  studentAccessPolicySaving: false,
  adminHistory: [],
  adminHistoryKind: "actions",
  adminHistoryPeriod: 30,
  adminHistoryLoaded: false,
  adminHistoryLoading: false,
  adminHistoryError: "",
  studentRegistrySearch: "",
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
  broadcastTargetOptions: null,
  broadcastTargetOptionsLoaded: false,
  broadcastTargetOptionsLoading: false,
  broadcastTargetOptionsError: "",
  broadcastSelectedVenues: new Set(),
  broadcastSelectedLessonModes: new Set(),
  broadcastVenueEditorOpen: false,
  broadcastVenueDraft: null,
  broadcastVenueSaving: false,
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
let confirmationResolver = null;
let confirmationReturnFocus = null;
const cartSyncChains = new Map();

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

async function copyTextToClipboard(value) {
  const text = String(value ?? "");
  if (!text) return false;
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // MAX WebView can deny Clipboard API access; use the selection fallback below.
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.readOnly = true;
  textarea.style.position = "fixed";
  textarea.style.inset = "-9999px auto auto -9999px";
  document.body.appendChild(textarea);
  textarea.select();
  textarea.setSelectionRange(0, text.length);
  let copied = false;
  try {
    copied = document.execCommand("copy");
  } catch {
    copied = false;
  } finally {
    textarea.remove();
  }
  return copied;
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
  if (Array.isArray(product.warehouses)) {
    return product.warehouses.map((warehouse) => ({
      id: String(warehouse.warehouse_id || warehouse.id || warehouse.warehouse_name),
      name: warehouse.warehouse_name || warehouse.name || "Склад",
      type: warehouse.warehouse_type || warehouse.type || "",
      stock: Number(warehouse.stock_quantity ?? warehouse.stock ?? warehouse.available_quantity ?? 0),
      reserved: Number(warehouse.reserved_quantity || warehouse.reserved || 0),
      available: Number(warehouse.available_quantity || warehouse.available || 0),
    }));
  }

  if (product.fulfillmentType === "digital_code") return [];

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
    if (!Array.isArray(product.warehouses) || product.warehouses.length === 0) return;
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
  if (product.fulfillmentType === "digital_code") {
    return Math.max(Number(product.stock || 0), 0);
  }
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

function isStaffStudentHistoryView() {
  return ["teacher", "admin"].includes(state.role) && state.view === "wallet";
}

function canManageStudentRecords() {
  return ["superadmin", "partner_director", "admin"].includes(primaryStaffRole());
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
    fulfillmentType: item.fulfillment_type || "warehouse",
    issuedCodes: Array.isArray(item.issued_codes) ? item.issued_codes : [],
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
  state.accessMessage = session.access_message || "";
  apiContext.tenantSlug = session.tenant_slug || apiContext.tenantSlug;
  state.currentTenant = session.tenant || null;
  state.availableTenants = Array.isArray(session.available_tenants)
    ? session.available_tenants
    : [];
  state.canManageTenants = Boolean(session.can_manage_tenants);
  state.canCreateTenants = Boolean(session.can_create_tenants);
  state.defaultWarehouseId = String(session.default_warehouse_id || "");
  state.studentAccessPolicy = {
    departedAccessDays: Number(session.student_access_policy?.departed_access_days || 30),
    freezeFrom: session.student_access_policy?.freeze_from || "",
    freezeUntil: session.student_access_policy?.freeze_until || "",
  };
  state.accrualRules = Array.isArray(session.accrual_rules) && session.accrual_rules.length
    ? session.accrual_rules.map((rule) => ({
        id: rule.id ? String(rule.id) : "",
        reason: rule.reason || "",
        amount: Number(rule.amount || 0),
        isActive: rule.is_active !== false,
      })).filter((rule) => rule.reason && rule.amount > 0)
    : DEFAULT_ACCRUAL_RULES.map((rule) => ({ ...rule }));
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
    state.studentLedgerById = new Map();
    state.studentLedgerLoading = new Set();
    state.studentLedgerErrors = new Map();
    state.studentRegistrySearch = "";
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
    status: student.student_status || "active",
    accessUntil: student.access_until || "",
    accessPaused: Boolean(student.access_paused),
    accessDaysRemaining: student.access_days_remaining,
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

function applyAccessGate(message = state.accessMessage || "") {
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

async function loadTeacherInvitations(force = false) {
  if (apiContext.demoMode) {
    const teacherStudents = studentsForCurrentRole();
    state.teacherInvitations = new Map(
      teacherStudents.map((student, index) => [
        student.id,
        {
          data: index === 0
            ? {
                student_id: student.id,
                student_name: student.name,
                group_name: student.group,
                available: true,
                parent_connected: true,
                qr_data_url: `/miniapp/static/assets/${student.id}-qr.svg`,
                qr_download_url: `/miniapp/static/assets/${student.id}-qr.svg`,
                bot_url: "",
              }
            : {
                student_id: student.id,
                student_name: student.name,
                group_name: student.group,
                available: false,
                parent_connected: false,
                message: "Родитель еще не подключен. Попросите его открыть письмо школы и перейти по персональной ссылке.",
              },
          error: "",
        },
      ]),
    );
    state.teacherInvitationsLoaded = true;
    renderTeacherInvitations();
    return;
  }
  if (
    !state.hasAccess ||
    !apiContext.maxUserId ||
    primaryStaffRole() !== "teacher" ||
    state.teacherInvitationsLoading ||
    (state.teacherInvitationsLoaded && !force)
  ) return;

  state.teacherInvitationsLoading = true;
  renderTeacherInvitations();
  try {
    const response = await apiFetch(
      apiUrl("/api/v1/miniapp/students/invitations", {
        max_user_id: apiContext.maxUserId,
        tenant_slug: apiContext.tenantSlug,
      }),
    );
    if (!response.ok) throw new Error(await parseApiError(response));
    const invitations = await response.json();
    state.teacherInvitations = new Map(
      invitations.map((item) => [String(item.student_id), { data: item, error: "" }]),
    );
    state.teacherInvitationsLoaded = true;
  } catch (error) {
    showNotice(error.message || "Не удалось загрузить QR-коды", "danger");
  } finally {
    state.teacherInvitationsLoading = false;
    renderTeacherInvitations();
  }
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
      fulfillmentType: product.fulfillment_type || "warehouse",
      category: product.category_name || "Без категории",
      categorySlug: product.category_slug || "",
      price: product.price_astrocoins,
      stock: product.available_quantity,
      totalCodeCount: Number(product.total_code_count || 0),
      issuedCodeCount: Number(product.issued_code_count || 0),
      codes: Array.isArray(product.codes) ? product.codes : [],
      warehouse:
        product.fulfillment_type === "digital_code"
          ? "Автовыдача кода"
          : primaryWarehouse?.warehouse_name || "Склад будет выбран",
      mark: name.trim().slice(0, 1).toUpperCase() || "A",
      warehouses: product.warehouses || [],
      catalogIndex,
    };
  });
  pruneInactiveCartItems();
  state.catalogLoaded = true;
}
