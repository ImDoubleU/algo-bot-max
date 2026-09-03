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
    birthDate: item.birth_date || "",
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
    parentContactIds: Array.isArray(item.parent_contact_ids) ? item.parent_contact_ids : [],
    parentNames: Array.isArray(item.parent_names) ? item.parent_names : [],
    parentMaxUserIds: Array.isArray(item.parent_max_user_ids) ? item.parent_max_user_ids : [],
    history: Array.isArray(item.history)
      ? item.history.map((event) => ({
          id: event.id ? String(event.id) : "",
          eventType: event.event_type || "updated",
          fromStatus: event.from_status || "",
          toStatus: event.to_status || "active",
          fromGroupName: event.from_group_name || "",
          toGroupName: event.to_group_name || "",
          changedFields: Array.isArray(event.changed_fields) ? event.changed_fields : [],
          source: event.source || "",
          actorName: event.actor_name || "",
          occurredAt: event.occurred_at || "",
        }))
      : [],
  };
}

function demoAdminStudentRegistry() {
  const now = new Date().toISOString();
  return {
    students: students.map((student) => ({
      student_id: student.id,
      lms_student_id: student.lmsId || null,
      display_name: student.name,
      birth_date: student.birthDate || null,
      group_name: student.group || null,
      course_name: student.course || null,
      venue_name: student.venue || null,
      teacher_name: student.teacher || null,
      status: student.status || "active",
      balance: Number(student.balance || 0),
      imported_at: student.importedAt || now,
      updated_at: student.updatedAt || now,
      status_updated_at: student.statusUpdatedAt || now,
      departed_at: student.departedAt || null,
      parent_contact_ids: student.parentContactIds || [],
      parent_names: student.parentNames || [],
      parent_max_user_ids: student.parentMaxUserIds || [],
      history: [
        {
          event_type: "imported",
          to_status: student.status || "active",
          to_group_name: student.group || null,
          changed_fields: ["student"],
          source: "demo",
          occurred_at: student.importedAt || now,
        },
      ],
    })),
  };
}

function applyAdminStudentRegistry(result) {
  state.adminStudents = Array.isArray(result?.students)
    ? result.students.map(normalizeRegistryStudent)
    : [];
  state.adminStudentsLoaded = true;
  state.adminStudentsError = "";
}

function normalizeStudentLedgerEntry(item) {
  const amount = Number(item.amount || 0);
  const direction = item.direction === "debit" ? "debit" : "credit";
  return {
    id: String(item.id || ""),
    studentId: String(item.student_id || ""),
    direction,
    amount,
    amountLabel: `${direction === "debit" ? "-" : "+"}${amount} AC`,
    reason: item.reason || "Операция с балансом",
    comment: item.comment || "",
    createdAt: item.created_at || "",
  };
}

function demoStudentLedger(studentId) {
  return ledger
    .filter(([, , , entryStudentId]) => !entryStudentId || entryStudentId === studentId)
    .map(([date, reason, amount], index) => {
      const numericAmount = Number(String(amount).replace(/[^\d,.-]/g, "").replace(",", ".")) || 0;
      return {
        id: `demo-${studentId}-${index}`,
        studentId,
        direction: numericAmount < 0 ? "debit" : "credit",
        amount: Math.abs(numericAmount),
        amountLabel: amount,
        reason,
        comment: "",
        createdAt: date,
      };
    });
}

async function loadStudentLedger(studentId, force = false) {
  const normalizedStudentId = String(studentId || "");
  if (!normalizedStudentId) return;
  if (
    state.studentLedgerLoading.has(normalizedStudentId) ||
    (state.studentLedgerById.has(normalizedStudentId) && !force)
  ) return;

  state.studentLedgerLoading.add(normalizedStudentId);
  state.studentLedgerErrors.delete(normalizedStudentId);
  if (typeof renderStudentLedgerPanel === "function") {
    renderStudentLedgerPanel(normalizedStudentId);
  }
  try {
    if (apiContext.demoMode) {
      state.studentLedgerById.set(normalizedStudentId, demoStudentLedger(normalizedStudentId));
      return;
    }
    const response = await apiFetch(
      apiUrl(`/api/v1/miniapp/students/${encodeURIComponent(normalizedStudentId)}/ledger`, {
        max_user_id: apiContext.maxUserId,
        tenant_slug: apiContext.tenantSlug,
        limit: 100,
      }),
    );
    if (!response.ok) throw new Error(await parseApiError(response));
    const result = await response.json();
    state.studentLedgerById.set(
      normalizedStudentId,
      Array.isArray(result) ? result.map(normalizeStudentLedgerEntry) : [],
    );
  } catch (error) {
    state.studentLedgerErrors.set(
      normalizedStudentId,
      error.message || "Не удалось загрузить операции",
    );
  } finally {
    state.studentLedgerLoading.delete(normalizedStudentId);
    if (typeof renderStudentLedgerPanel === "function") {
      renderStudentLedgerPanel(normalizedStudentId);
    }
  }
}

async function loadAdminStudents(force = false) {
  if (apiContext.demoMode) {
    applyAdminStudentRegistry(demoAdminStudentRegistry());
    if (force) {
      state.studentLedgerById = new Map();
      state.studentLedgerErrors = new Map();
    }
    if (isStaffStudentHistoryView()) renderStudentRegistry();
    return;
  }
  if (
    !["teacher", "admin"].includes(state.role) ||
    !state.hasAccess ||
    !apiContext.maxUserId
  ) return;
  if (
    state.adminStudentsLoading ||
    (state.adminStudentsLoaded && !force)
  ) return;

  state.adminStudentsLoading = true;
  state.adminStudentsError = "";
  if (isStaffStudentHistoryView()) renderStudentRegistry();
  try {
    const response = await apiFetch(
      apiUrl("/api/v1/miniapp/students/registry", {
        max_user_id: apiContext.maxUserId,
        tenant_slug: apiContext.tenantSlug,
      }),
    );
    if (!response.ok) throw new Error(await parseApiError(response));
    const result = await response.json();
    applyAdminStudentRegistry(result);
    if (force) {
      state.studentLedgerById = new Map();
      state.studentLedgerErrors = new Map();
    }
  } catch (error) {
    state.adminStudentsError = error.message || "Не удалось загрузить учеников";
    showNotice(state.adminStudentsError, "danger");
  } finally {
    state.adminStudentsLoading = false;
    if (isStaffStudentHistoryView()) renderStudentRegistry();
  }
}

function normalizeAdminHistoryEntry(item) {
  return {
    id: String(item.id || ""),
    action: item.action || "",
    title: item.title || "Системное действие",
    category: item.category || "Система",
    status: item.status || "success",
    actorName: item.actor_name || "Система",
    actorMaxUserId: item.actor_max_user_id || null,
    entityType: item.entity_type || "",
    entityId: item.entity_id || "",
    payload: item.payload && typeof item.payload === "object" ? item.payload : {},
    createdAt: item.created_at || "",
  };
}

async function loadAdminHistory(force = false) {
  if (
    state.role !== "admin" ||
    !state.hasAccess ||
    !apiContext.maxUserId ||
    apiContext.demoMode
  ) return;
  if (state.adminHistoryLoading || (state.adminHistoryLoaded && !force)) return;

  state.adminHistoryLoading = true;
  state.adminHistoryError = "";
  if (state.adminTab === "history") renderAdminPanel();
  try {
    const response = await apiFetch(
      apiUrl("/api/v1/miniapp/admin/history", {
        max_user_id: apiContext.maxUserId,
        tenant_slug: apiContext.tenantSlug,
        kind: "actions",
        period_days: state.adminHistoryPeriod,
        limit: 150,
      }),
    );
    if (!response.ok) throw new Error(await parseApiError(response));
    const result = await response.json();
    state.adminHistory = Array.isArray(result.entries)
      ? result.entries.map(normalizeAdminHistoryEntry)
      : [];
    state.adminHistoryLoaded = true;
  } catch (error) {
    state.adminHistoryError = error.message || "Не удалось загрузить историю";
    showNotice(state.adminHistoryError, "danger");
  } finally {
    state.adminHistoryLoading = false;
    if (state.adminTab === "history") renderAdminPanel();
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
  if (showButton) showButton.hidden = enabled || !state.canCreateTenants;
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
  state.studentLedgerById = new Map();
  state.studentLedgerLoading = new Set();
  state.studentLedgerErrors = new Map();
  state.studentCreateOpen = false;
  state.studentMutationSaving = "";
  state.adminHistory = [];
  state.adminHistoryLoaded = false;
  state.adminHistoryError = "";
  state.studentRegistrySearch = "";
  state.studentRegistryStatusFilter = "all";
  state.studentRegistryGroupFilter = "all";
  state.studentRegistryVisibleCount = STUDENT_REGISTRY_PAGE_SIZE;
  state.teacherInvitations = new Map();
  state.teacherInvitationsLoaded = false;
  state.teacherInvitationGroup = "all";
  syncTenantToUrl();
  closeTenantDialog();
  try {
    await loadSession();
    if (applyAccessGate()) return;
    await loadCatalog();
    await loadOpsSummary();
    if (isStaffStudentHistoryView()) await loadAdminStudents();
    if (state.adminTab === "history") await loadAdminHistory();
    state.studentInvitations = new Map();
    state.studentInvitationsLoaded = false;
    state.favorites = new Set();
    state.accrualReport = null;
    state.accrualReportTeacherFilter = "all";
    state.accrualReportGroupFilter = "all";
    state.broadcastHistory = [];
    state.broadcastHistoryLoaded = false;
    state.broadcastPreview = null;
    state.broadcastPreviewSignature = "";
    state.broadcastSelectedGroups = new Set();
    state.broadcastAllGroups = true;
    state.broadcastTargetOptions = null;
    state.broadcastTargetOptionsLoaded = false;
    state.broadcastTargetOptionsLoading = false;
    state.broadcastTargetOptionsError = "";
    state.broadcastSelectedVenues = new Set();
    state.broadcastSelectedLessonModes = new Set();
    state.broadcastVenueEditorOpen = false;
    state.broadcastVenueDraft = null;
    state.broadcastVenueSaving = false;
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
  const buttons = qsa("#refreshDataButton, [data-refresh-fulfillment]");
  if (!label || buttons.length === 0) return;
  const refreshLabel = qs("#refreshDataButton span");
  if (state.refreshing) {
    label.textContent = "Обновление";
    if (refreshLabel) refreshLabel.textContent = "Обновление...";
  } else if (state.lastSyncAt) {
    label.textContent = `Обновлено ${state.lastSyncAt.toLocaleTimeString("ru-RU", {
      hour: "2-digit",
      minute: "2-digit",
    })}`;
    if (refreshLabel) refreshLabel.textContent = "Обновить";
  } else {
    label.textContent = "Данные не обновлялись";
    if (refreshLabel) refreshLabel.textContent = "Обновить";
  }
  buttons.forEach((button) => {
    button.disabled = state.refreshing;
    button.classList.toggle("is-loading", state.refreshing);
    button.setAttribute("aria-busy", String(state.refreshing));
  });
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
    renderSyncStatus();
    return;
  }
  const refreshTasks = [loadCatalog(), loadOpsSummary()];
  if (state.adminStudentsLoaded || isStaffStudentHistoryView()) {
    refreshTasks.push(loadAdminStudents(true));
  }
  if (state.adminHistoryLoaded || state.adminTab === "history") {
    refreshTasks.push(loadAdminHistory(true));
  }
  const results = await Promise.allSettled(refreshTasks);
  results.forEach((result) => {
    if (result.status === "rejected") errors.push(result.reason);
  });
  state.studentInvitations = new Map();
  state.studentInvitationsLoaded = false;
  state.teacherInvitations = new Map();
  state.teacherInvitationsLoaded = false;
  await loadParentInvitations();
  if (hasTeacherCapabilities()) {
    try {
      await loadTeacherInvitations(true);
    } catch (error) {
      errors.push(error);
    }
  }
  if (roleViews(state.role).includes("broadcasts")) {
    state.broadcastHistoryLoaded = false;
    state.broadcastTargetOptionsLoaded = false;
    try {
      await Promise.all([loadBroadcastHistory(), loadBroadcastTargetOptions(true)]);
    } catch (error) {
      errors.push(error);
    }
  }

  state.lastSyncAt = new Date();
  state.refreshing = false;
  refreshFulfillmentStageSnapshot();
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
    ["wallet", "report", "accrual", "broadcasts", "admin", "help"].includes(nextView),
  );
  closeMobileMorePanel();
  renderMobileNavigation();
  if (previousView !== nextView && window.matchMedia("(max-width: 640px)").matches) {
    window.scrollTo({ top: 0, behavior: "auto" });
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
  if (nextView === "wallet") {
    renderLedger();
    if (isStaffStudentHistoryView()) void loadAdminStudents();
  }
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
    state.fulfillmentStageSnapshot = null;
    state.selectedFulfillmentOrders.clear();
    state.fulfillmentPickDraft.clear();
  }
  const roleStudents = studentsForCurrentRole();
  const nextStudentId = roleStudents.some(
    (student) => student.id === state.activeStudentId,
  )
    ? state.activeStudentId
    : roleStudents[0]?.id || "";
  changeActiveStudent(nextStudentId);
  document.body.dataset.activeRole = role;
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
  if (
    hasTeacherCapabilities() &&
    !state.teacherInvitationsLoaded &&
    !state.teacherInvitationsLoading
  ) {
    loadTeacherInvitations().catch((error) => console.warn(error));
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
  const primaryRole =
    primaryStaffRole() || (state.role === "admin" ? "admin" : "teacher");
  const accountName =
    staffProfileDisplayName() ||
    state.account?.display_name?.trim() ||
    "";
  const profileRole = state.staffRoles.length
    ? state.staffRoles.map(staffRoleProfileLabel).join(", ")
    : staffRoleProfileLabel(primaryRole);
  const roleStudents = studentsForCurrentRole();
  const linkedCount = roleStudents.length;
  const statusStrip = qs(".status-strip");
  const studentContext = qs("#studentContext");
  if (studentContext) {
    studentContext.hidden = true;
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
  if (profileLabel) {
    profileLabel.textContent = {
      student: "Профиль ученика",
      parent: "Профиль родителя",
      teacher: "Рабочий профиль",
      admin: "Рабочий профиль",
    }[state.role] || "Профиль";
  }
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

  const nameParts = student?.name?.trim().split(/\s+/).filter(Boolean) || [];
  const firstName = student?.firstName || (nameParts.length > 1 ? nameParts[1] : nameParts[0] || "");
  const welcome = studentWelcome(firstName);
  const dashboardSpotlight = qs("#dashboardSpotlight");
  if (dashboardSpotlight) dashboardSpotlight.hidden = state.role === "admin";
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
      kicker: "",
      title: primaryRole === "curator" ? "Ученики филиала" : "Мои ученики",
      text:
        primaryRole === "curator"
          ? "Ученики, начисления, заказы и рассылки по филиалу."
          : "Ученики, начисления, заказы и QR-коды ваших групп.",
    },
  };
  const spotlight = spotlightByRole[state.role];
  const dashboardRoleKicker = qs("#dashboardRoleKicker");
  if (dashboardRoleKicker && spotlight) {
    dashboardRoleKicker.textContent = spotlight.kicker;
    dashboardRoleKicker.hidden = !spotlight.kicker;
  }
  if (spotlight) {
    qs("#dashboardSpotlightTitle").textContent = spotlight.title;
    qs("#dashboardSpotlightText").textContent = spotlight.text;
  }
  const accessNotice = qs("#studentAccessNotice");
  if (accessNotice) {
    const showAccessNotice = !isStaff && student?.status === "departed" && student.accessUntil;
    accessNotice.hidden = !showAccessNotice;
    if (showAccessNotice) {
      const accessDate = new Intl.DateTimeFormat("ru-RU", {
        day: "numeric",
        month: "long",
        year: "numeric",
      }).format(new Date(`${student.accessUntil}T12:00:00`));
      accessNotice.innerHTML = `
        <i data-lucide="clock-3"></i>
        <span>
          <strong>Доступ сохранен до ${escapeHtml(accessDate)}</strong>
          <small>${student.accessPaused ? "Отсчет сейчас приостановлен школой." : "До этой даты доступны баланс, магазин и история заказов."}</small>
        </span>
      `;
    } else {
      accessNotice.innerHTML = "";
    }
  }
  const taskActions = qs("#dashboardTaskActions");
  if (taskActions) {
    const actions = state.role === "teacher"
      ? [
          ["accrual", "circle-plus", "Начислить AC"],
          ["orders", "package-check", "Заказы учеников"],
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
    teacher: primaryRole === "teacher" ? "Передано вам к выдаче" : "Заказы к выдаче",
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
  refreshIcons();
}
