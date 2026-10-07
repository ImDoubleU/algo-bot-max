const pendingBindingsState = {tenant: "", items: [], total: 0, offset: 0, search: "", filter: "open", loading: false, loaded: false, error: "", sequence: 0};
const PENDING_BINDING_LABELS = {pending: "Ожидает профиля", ready: "Ждёт подтверждения", review: "Нужна проверка", completed: "Подключён", expired: "Срок закончился", cancelled: "Отменён"};

function pendingBindingsEnabled() {
  return primaryStaffRole() === "superadmin" || (apiContext.demoMode && state.role === "admin");
}

function pendingBindingDate(value) {
  return value ? new Date(value).toLocaleString("ru-RU", {timeZone: "Europe/Moscow", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit"}) : "";
}

function pendingBindingReason(value) {
  if (value === "account_already_connected") return "У аккаунта уже есть действующий доступ";
  return {contact_not_found: "Семья ещё не найдена", contact_id_not_found: "Семья ещё не найдена", contact_has_no_students: "У контакта пока нет учеников", student_not_found: "Ученик ещё не найден", ready: "Профиль найден", account_role_conflict: "Аккаунт уже используется с другой ролью", student_already_bound: "Аккаунт подключён к другому ученику", access_revoked: "Связь отключена школой", student_access_closed: "Доступ ученика закрыт", parent_link_inactive: "Нужна действующая связь родителя", school_inactive: "Школа отключена", pending_expired: "Нужна свежая ссылка школы", bot_stopped: "Пользователь остановил бота", cancelled: "Ожидание отменено", connected: "Подключение завершено"}[value] || "Требует проверки школы";
}

function pendingBindingRows() {
  return pendingBindingsState.items.map(item => `<article class="pending-binding-row">
    <div class="pending-binding-heading"><strong>${escapeHtml(item.name || (item.username ? `@${item.username}` : "Имя в MAX не указано"))}</strong><span class="pending-binding-status is-${escapeHtml(item.status)}">${escapeHtml(PENDING_BINDING_LABELS[item.status] || "Нужна проверка")}</span></div>
    <div class="pending-binding-identity"><span>${escapeHtml(auditReadable(item.role))}</span><span>MAX ID ${escapeHtml(item.max_user_id)}</span>${item.name && item.name_source === "ticket" ? "<span>Имя из заявки</span>" : ""}${item.username && item.name ? `<span>@${escapeHtml(item.username.replace(/^@/, ""))}</span>` : ""}<span>${item.target_id ? `${item.kind === "contact" ? "ID контакта" : "ID ученика"}: ${escapeHtml(item.target_id)}` : "ID из старой попытки сохранён по хешу"}</span></div>
    ${(item.students || []).length ? `<div class="pending-binding-students">${item.students.map(student => `<div><button type="button" class="audit-student-link" data-audit-student="${escapeHtml(student.id)}" data-audit-tenant="${escapeHtml(item.tenant_slug)}">${escapeHtml(student.name)}<i data-lucide="arrow-up-right"></i></button><span>${escapeHtml([student.group, student.lms_id ? `LMS ID ${student.lms_id}` : ""].filter(Boolean).join(" · "))}</span></div>`).join("")}</div>` : ""}
    <div class="pending-binding-details"><span>${escapeHtml(pendingBindingReason(item.reason))}</span><span>Попыток: ${item.attempts}</span><span>Последняя: ${pendingBindingDate(item.last_attempt_at)}</span>${item.notified_at ? `<span>Уведомление: ${pendingBindingDate(item.notified_at)}</span>` : item.notification_error ? `<span class="pending-binding-error">${escapeHtml(item.notification_error)}</span>` : item.status === "ready" ? "<span>Уведомление в очереди</span>" : ""}<span>Ожидание до ${pendingBindingDate(item.expires_at)}</span></div>
    ${["pending", "ready", "review"].includes(item.status) ? `<button type="button" class="text-action pending-binding-cancel" data-pending-cancel="${escapeHtml(item.id)}">Отменить ожидание</button>` : ""}
  </article>`).join("");
}

function pendingBindingPanel() {
  if (!pendingBindingsEnabled()) return "";
  if (pendingBindingsState.tenant !== apiContext.tenantSlug) {
    ++pendingBindingsState.sequence;
    Object.assign(pendingBindingsState, {tenant: apiContext.tenantSlug, items: [], total: 0, offset: 0, loaded: false, loading: false, error: ""});
  }
  return `<section class="pending-bindings-panel" aria-labelledby="pendingBindingsTitle">
    <div class="pending-bindings-title"><h3 id="pendingBindingsTitle">Ожидают подключения</h3><button type="button" class="secondary-action" data-pending-refresh><i data-lucide="refresh-cw"></i>Обновить</button></div>
    <div class="pending-bindings-filters"><input class="support-control" type="search" data-pending-search aria-label="Поиск ожидающих подключений" placeholder="Имя, MAX ID или ID из ссылки" value="${escapeHtml(pendingBindingsState.search)}"><select class="support-control" data-pending-filter aria-label="Статус ожидающего подключения">${[["open", "Ожидающие"], ["ready", "Ждут подтверждения"], ["review", "Нужна проверка"], ["completed", "Подключённые"], ["expired", "Срок закончился"], ["cancelled", "Отменённые"]].map(([value, label]) => `<option value="${value}" ${pendingBindingsState.filter === value ? "selected" : ""}>${label}</option>`).join("")}</select></div>
    <div class="pending-bindings-content" role="status">${pendingBindingsContent()}</div>
  </section>`;
}

function pendingBindingsContent() {
  if (pendingBindingsState.error) return `<p class="pending-binding-error">${escapeHtml(pendingBindingsState.error)}</p>`;
  if (pendingBindingsState.loading && !pendingBindingsState.loaded) return "<p>Загрузка…</p>";
  return `${pendingBindingRows() || '<p class="pending-bindings-empty">Ожидающих подключений нет</p>'}${pendingBindingsState.total > 30 ? `<div class="support-pagination"><button type="button" class="secondary-action" data-pending-page="-1" ${pendingBindingsState.offset === 0 ? "disabled" : ""}>Назад</button><span>${pendingBindingsState.offset + 1}–${pendingBindingsState.offset + pendingBindingsState.items.length} из ${pendingBindingsState.total}</span><button type="button" class="secondary-action" data-pending-page="1" ${pendingBindingsState.offset + pendingBindingsState.items.length >= pendingBindingsState.total ? "disabled" : ""}>Далее</button></div>` : ""}`;
}

function pendingBindingsRenderContent() {
  const node = qs(".pending-bindings-content");
  if (!node || state.adminTab !== "contacts" || !pendingBindingsEnabled()) return;
  node.innerHTML = pendingBindingsContent(); refreshIcons();
}

async function loadPendingBindings(force = false) {
  if (!pendingBindingsEnabled() || state.adminTab !== "contacts") return;
  if (pendingBindingsState.tenant !== apiContext.tenantSlug) pendingBindingPanel();
  if (!force && (pendingBindingsState.loaded || pendingBindingsState.loading)) return;
  const sequence = ++pendingBindingsState.sequence;
  const tenant = apiContext.tenantSlug;
  pendingBindingsState.loading = true; pendingBindingsState.error = ""; pendingBindingsRenderContent();
  try {
    if (apiContext.demoMode) {
      pendingBindingsState.items = []; pendingBindingsState.total = 0;
    } else {
      const response = await apiFetch(apiUrl("/api/v1/access/pending", {tenant_slug: tenant, offset: pendingBindingsState.offset, search: pendingBindingsState.search, filter_status: pendingBindingsState.filter}));
      if (!response.ok) throw new Error(await parseApiError(response));
      const result = await response.json();
      if (sequence !== pendingBindingsState.sequence || tenant !== apiContext.tenantSlug) return;
      pendingBindingsState.items = result.items; pendingBindingsState.total = result.total;
    }
    pendingBindingsState.loaded = true;
  } catch (error) {
    if (sequence === pendingBindingsState.sequence) pendingBindingsState.error = error.message;
  } finally {
    if (sequence === pendingBindingsState.sequence) { pendingBindingsState.loading = false; pendingBindingsRenderContent(); }
  }
}

document.addEventListener("click", async event => {
  const target = event.target.closest("[data-pending-refresh], [data-pending-page], [data-pending-cancel]");
  if (!target || !pendingBindingsEnabled()) return;
  if (target.hasAttribute("data-pending-refresh")) { void loadPendingBindings(true); return; }
  if (target.dataset.pendingPage) {
    pendingBindingsState.offset = Math.max(0, pendingBindingsState.offset + 30 * Number(target.dataset.pendingPage));
    void loadPendingBindings(true); return;
  }
  if (target.dataset.pendingCancel) {
    const confirmed = await requestConfirmation({title: "Отменить ожидание подключения?", message: "Уведомление о появлении профиля отправляться не будет.", confirmLabel: "Отменить ожидание", cancelLabel: "Назад"});
    if (!confirmed) return;
    target.disabled = true;
    try {
      const response = await apiFetch(apiUrl(`/api/v1/access/pending/${encodeURIComponent(target.dataset.pendingCancel)}/cancel`), {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({tenant_slug: apiContext.tenantSlug, max_user_id: apiContext.maxUserId})});
      if (!response.ok) throw new Error(await parseApiError(response));
      if (pendingBindingsState.items.length === 1 && pendingBindingsState.offset > 0) pendingBindingsState.offset -= 30;
      await loadPendingBindings(true);
    } catch (error) { showNotice(error.message, "danger"); }
    finally { target.disabled = false; }
  }
});
let pendingBindingsSearchTimer;
document.addEventListener("input", event => {
  if (!event.target.hasAttribute("data-pending-search")) return;
  pendingBindingsState.search = event.target.value; pendingBindingsState.offset = 0;
  clearTimeout(pendingBindingsSearchTimer);
  pendingBindingsSearchTimer = setTimeout(() => void loadPendingBindings(true), 300);
});
document.addEventListener("change", event => {
  if (!event.target.hasAttribute("data-pending-filter")) return;
  pendingBindingsState.filter = event.target.value; pendingBindingsState.offset = 0; void loadPendingBindings(true);
});
