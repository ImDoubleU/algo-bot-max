const AUDIT_CATEGORY_LABELS = ["Привязки", "Доступ", "Ученики", "Сотрудники", "Заказы", "Астрокоины", "Банк", "Товары", "Склады", "Обратная связь", "Поддержка", "Рассылки", "Запросы", "Бот", "Система"];
const auditFeeds = new Map();
let auditSearchTimer;

function fullAuditEnabled() {
  return primaryStaffRole() === "superadmin" || (apiContext.demoMode && state.role === "admin");
}

function auditFeed(kind) {
  if (!auditFeeds.has(kind)) auditFeeds.set(kind, {
    rows: apiContext.demoMode ? [...state.adminHistory] : [], total: apiContext.demoMode ? state.adminHistory.length : 0,
    loading: false, loaded: apiContext.demoMode, error: "", more: false, snapshot: "", generation: 0,
    filters: { q: "", category: "", outcome: "", actor: "", days: "30", from: "", to: "", allTenants: kind === "audit" },
  });
  return auditFeeds.get(kind);
}

function resetAuditFeeds() {
  auditFeeds.forEach((feed) => feed.abort?.abort());
  auditFeeds.clear();
}

async function loadAuditFeed(kind, reset = false) {
  if (apiContext.demoMode || !state.hasAccess || !apiContext.maxUserId) return;
  if (kind === "audit" && !fullAuditEnabled()) return;
  const feed = auditFeed(kind);
  if (!reset && (feed.loading || (feed.loaded && !feed.more))) return;
  if (reset) {
    feed.abort?.abort(); feed.loading = false; feed.rows = []; feed.snapshot = ""; feed.loaded = false;
  }
  const generation = ++feed.generation;
  const tenant = apiContext.tenantSlug;
  const filters = { ...feed.filters };
  if (filters.from && filters.to && filters.from > filters.to) {
    showNotice("Начало периода должно быть раньше окончания", "danger"); return;
  }
  if (filters.actor && !/^[1-9]\d{0,17}$/.test(filters.actor)) {
    showNotice("Укажите MAX ID цифрами", "danger"); return;
  }
  feed.loading = true; feed.error = ""; feed.abort = new AbortController();
  renderAuditCurrent(kind);
  try {
    const studentId = kind.startsWith("student:") ? kind.slice(8) : "";
    const path = studentId ? `/api/v1/miniapp/students/${encodeURIComponent(studentId)}/actions` : "/api/v1/miniapp/admin/history";
    const response = await apiFetch(apiUrl(path, {
      max_user_id: apiContext.maxUserId, tenant_slug: tenant, kind: studentId ? undefined : kind,
      limit: 100, offset: feed.rows.length, snapshot_at: feed.snapshot || undefined,
      q: filters.q || undefined, category: filters.category || undefined,
      outcome: filters.outcome || undefined, actor_max_user_id: filters.actor || undefined,
      period_days: filters.days, date_from: filters.from || undefined, date_to: filters.to || undefined,
      all_tenants: kind === "audit" && filters.allTenants ? "true" : undefined,
    }), { signal: feed.abort.signal });
    if (!response.ok) throw new Error(await parseApiError(response));
    const result = await response.json();
    if (generation !== feed.generation || tenant !== apiContext.tenantSlug) return;
    const unique = new Map(feed.rows.map((row) => [row.id, row]));
    (result.entries || []).map(normalizeAdminHistoryEntry).forEach((row) => unique.set(row.id, row));
    feed.rows = [...unique.values()]; feed.total = result.total || 0;
    feed.snapshot = result.snapshot_at || ""; feed.more = Boolean(result.has_more); feed.loaded = true;
  } catch (error) {
    if (error.name !== "AbortError" && generation === feed.generation) feed.error = error.message || "Не удалось загрузить события";
  } finally {
    if (generation === feed.generation && tenant === apiContext.tenantSlug) {
      feed.loading = false; renderAuditCurrent(kind);
    }
  }
}

function auditTime(value, withDay = false) {
  if (!value || Number.isNaN(new Date(value).getTime())) return "";
  return new Intl.DateTimeFormat("ru-RU", {
    timeZone: "Europe/Moscow", ...(withDay ? { day: "numeric", month: "long", year: "numeric" } : {}),
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  }).format(new Date(value));
}

function auditDay(value) {
  return new Intl.DateTimeFormat("ru-RU", { timeZone: "Europe/Moscow", day: "numeric", month: "long", year: "numeric" }).format(new Date(value));
}

function auditReadable(value) {
  const labels = { parent: "Родитель", student: "Ученик", teacher: "Преподаватель", admin: "Администратор", superadmin: "Суперадминистратор", active: "Активен", revoked: "Отключён", departed: "Завершил обучение", archived: "В архиве", id_entry: "Ссылка из письма", parent_qr: "QR родителя", teacher_qr: "QR преподавателя", success: "Выполнено", denied: "Отказ", error: "Не выполнено", partial: "Требует внимания", pending: "В обработке" };
  if (Array.isArray(value)) return value.map(auditReadable).join(", ");
  if (value && typeof value === "object") return JSON.stringify(value);
  return labels[value] || String(value ?? "—");
}

function auditFacts(entry) {
  const p = entry.payload || {};
  const facts = adminHistoryFacts(entry).filter(([name]) => name !== "Роль" || !p.actor_role).map(([name, value]) => [name, auditReadable(value)]);
  const add = (label, value) => { if (value !== undefined && value !== null && value !== "" && !facts.some(([key]) => key === label)) facts.push([label, auditReadable(value)]); };
  add("Ученик", p.student_name); add("Группа", p.group_name); add("Способ входа", p.source);
  if (p.from_status || p.to_status) add("Изменение", `${auditReadable(p.from_status)} → ${auditReadable(p.to_status)}`);
  if (p.previous_balance !== undefined) add("Баланс", `${p.previous_balance} → ${p.new_balance} AC`);
  if (p.from_quantity !== undefined) add("Остаток", `${p.from_quantity} → ${p.to_quantity}`);
  add("Начислено", p.amount ? `${p.amount} AC` : ""); add("Возвращено", p.refund_astrocoins ? `${p.refund_astrocoins} AC` : "");
  add("Детей в семье", p.total_links > 1 ? p.total_links : ""); add("Привязок создано", p.created_links || ""); add("Привязок восстановлено", p.reactivated_links || "");
  add("MAX ID получателя", p.target_max_user_id); add("Повторных попыток", p.attempts);
  if (p.before && p.after) {
    const names = { first_name: "Имя", last_name: "Фамилия", group_name: "Группа", course_name: "Курс", teacher_name: "Преподаватель", venue_name: "Площадка", birth_date: "Дата рождения" };
    Object.keys(p.after).filter((key) => JSON.stringify(p.before[key]) !== JSON.stringify(p.after[key])).forEach((key) => add(names[key] || key, `${auditReadable(p.before[key])} → ${auditReadable(p.after[key])}`));
  }
  return facts.slice(0, 12);
}

function auditStudents(entry) {
  const students = Array.isArray(entry.payload?.students) ? entry.payload.students : [];
  return students.map((student) => `<div class="audit-student">
    <div class="audit-student-main"><span class="audit-person-role">Ученик</span>
      <button type="button" class="audit-student-link" data-audit-student="${escapeHtml(student.id)}" data-audit-tenant="${escapeHtml(entry.tenantSlug || "")}" title="Открыть карточку ученика · ${escapeHtml(student.id)}">${escapeHtml(student.name)}<i data-lucide="arrow-up-right"></i></button>
      <span class="audit-student-ids">${[student.lms_id ? `LMS ID ${escapeHtml(student.lms_id)}` : "", student.crm_id ? `CRM ID ${escapeHtml(student.crm_id)}` : ""].filter(Boolean).join(" · ")}</span>
    </div>
    <div class="audit-student-context"><span><small>Группа</small>${escapeHtml(student.group || "Не указана")}</span><span><small>Преподаватель</small>${escapeHtml(student.teacher || "Не указан")}${student.teacher_max_user_id ? ` · MAX ID ${escapeHtml(student.teacher_max_user_id)}` : ""}</span></div>
    ${(student.accounts || []).length ? `<div class="audit-linked-people"><small>Связи сейчас</small>${student.accounts.map((account) => `<span><b>${escapeHtml(auditReadable(account.role))}:</b> ${escapeHtml(account.name || "Имя не указано")} <code>MAX ID ${escapeHtml(account.max_user_id)}</code></span>`).join("")}</div>` : ""}
  </div>`).join("");
}

function auditCards(rows, full = false) {
  let previousDay = "";
  return rows.map((entry) => {
    const day = auditDay(entry.createdAt);
    const heading = day !== previousDay ? `<h4 class="audit-day">${escapeHtml(day)}</h4>` : "";
    previousDay = day;
    const status = { success: ["check", "Выполнено"], denied: ["shield-alert", "Отказ"], error: ["circle-x", "Не выполнено"], partial: ["triangle-alert", "Требует внимания"], pending: ["clock", "В обработке"] }[entry.status] || ["info", "Событие"];
    const facts = auditFacts(entry);
    const actorName = entry.actorName === `Аккаунт MAX ${entry.actorMaxUserId}` ? "Имя не указано" : entry.actorName;
    const actorRole = String(entry.payload?.actor_role || entry.payload?.role || "").split(", ").filter(Boolean).map(auditReadable).join(", ");
    return `${heading}<article class="audit-event is-${escapeHtml(entry.status)}">
      <span class="audit-icon"><i data-lucide="${status[0]}"></i></span>
      <div class="audit-copy"><div class="audit-title"><strong>${escapeHtml(entry.title)}</strong><span class="audit-badge">${status[1]}</span></div>
        <div class="audit-who">${actorRole ? `<span class="audit-person-role">${escapeHtml(actorRole)}</span>` : ""}<strong>${escapeHtml(actorName)}</strong>${entry.actorMaxUserId ? `<code>MAX ID ${escapeHtml(entry.actorMaxUserId)}</code>` : ""}</div>
        ${auditStudents(entry)}
        ${entry.explanation ? `<p class="audit-explanation">${escapeHtml(entry.explanation)}</p>` : ""}
        ${facts.length ? `<dl class="audit-facts">${facts.map(([key, value]) => `<div><dt>${escapeHtml(key)}</dt><dd>${escapeHtml(value)}</dd></div>`).join("")}</dl>` : ""}
        <div class="audit-tags"><span>${escapeHtml(entry.category)}</span>${full && entry.tenantName ? `<span>${escapeHtml(entry.tenantName)}</span>` : ""}</div>
        ${full ? `<details class="audit-details"><summary>Подробности события</summary><dl class="audit-facts"><div><dt>Событие</dt><dd>${escapeHtml(entry.action)}</dd></div><div><dt>Запись</dt><dd>${escapeHtml(entry.id)}</dd></div>${entry.requestId ? `<div><dt>Запрос</dt><dd>${escapeHtml(entry.requestId)}</dd></div>` : ""}${entry.ipAddress ? `<div><dt>IP</dt><dd>${escapeHtml(entry.ipAddress)}</dd></div>` : ""}<div><dt>Объект</dt><dd>${escapeHtml([entry.entityType, entry.entityId].filter(Boolean).join(" · "))}</dd></div></dl><pre>${escapeHtml(JSON.stringify(entry.payload, null, 2))}</pre></details>` : ""}
      </div><time datetime="${escapeHtml(entry.createdAt)}" title="Время Москвы">${escapeHtml(auditTime(entry.createdAt))}</time>
    </article>`;
  }).join("");
}

function auditPanel(kind, compact = false) {
  const feed = auditFeed(kind); const f = feed.filters; const full = kind === "audit";
  const attrs = (field) => `data-audit-field="${field}" data-audit-kind="${escapeHtml(kind)}"`;
  const title = full ? "Аудит действий" : kind === "bindings" ? "История подключений" : "История действий";
  return `<section class="audit-panel" data-audit-panel="${escapeHtml(kind)}">
    <div class="audit-toolbar"><h3>${title}</h3><button class="secondary-action" type="button" data-audit-refresh="${escapeHtml(kind)}" ${feed.loading ? "disabled" : ""}><i data-lucide="refresh-cw"></i>Обновить</button></div>
    ${!compact ? `<div class="audit-filters">
      <label class="audit-search"><span>Поиск</span><input type="search" maxlength="120" ${attrs("q")} value="${escapeHtml(f.q)}" placeholder="Имя, событие, MAX ID" /></label>
      <button type="button" class="audit-filter-toggle secondary-action" data-audit-toggle="${escapeHtml(kind)}" aria-expanded="${Boolean(feed.filtersOpen)}"><i data-lucide="sliders-horizontal"></i>Фильтры</button>
      <div class="audit-filter-extra ${feed.filtersOpen ? "is-open" : ""}">
      <label><span>Результат</span><select ${attrs("outcome")}><option value="">Все результаты</option>${["success", "denied", "error", "partial", "pending"].map((value) => `<option value="${value}" ${f.outcome === value ? "selected" : ""}>${auditReadable(value)}</option>`).join("")}</select></label>
      <label><span>Раздел</span><select ${attrs("category")}><option value="">Все разделы</option>${AUDIT_CATEGORY_LABELS.map((value) => `<option ${f.category === value ? "selected" : ""}>${escapeHtml(value)}</option>`).join("")}</select></label>
      <label><span>Период</span><select ${attrs("days")}>${[[1, "24 часа"], [7, "7 дней"], [30, "30 дней"], [90, "3 месяца"], [365, "Год"], [3650, "Вся история"]].map(([value, label]) => `<option value="${value}" ${String(value) === f.days ? "selected" : ""}>${label}</option>`).join("")}</select></label>
      <label><span>С даты</span><input type="date" ${attrs("from")} value="${escapeHtml(f.from)}" /></label><label><span>По дату</span><input type="date" ${attrs("to")} value="${escapeHtml(f.to)}" /></label>
      ${full ? `<label><span>MAX ID</span><input inputmode="numeric" maxlength="18" ${attrs("actor")} value="${escapeHtml(f.actor)}" /></label><label class="audit-checkbox"><input type="checkbox" ${attrs("allTenants")} ${f.allTenants ? "checked" : ""} /><span>Все школы и события без школы</span></label>` : ""}
      </div>
    </div>` : ""}
    <div class="audit-count">Показано ${feed.rows.length} из ${feed.total} · время Москвы</div>
    ${feed.error ? `<div class="audit-error" role="alert">${escapeHtml(feed.error)}<button type="button" class="secondary-action" data-audit-refresh="${escapeHtml(kind)}">Повторить</button></div>` : ""}
    <div class="audit-timeline">${auditCards(feed.rows, full)}</div>
    ${feed.loading ? '<div class="audit-loading" role="status">Загружаем события…</div>' : !feed.rows.length && !feed.error ? '<div class="empty-state compact-empty">Событий за этот период нет</div>' : ""}
    ${feed.more ? `<button type="button" class="secondary-action audit-more" data-audit-more="${escapeHtml(kind)}" ${feed.loading ? "disabled" : ""}>Показать ещё 100</button>` : ""}
  </section>`;
}

function renderAuditCurrent(kind) {
  const active = document.activeElement;
  const field = active?.dataset?.auditField;
  const start = typeof active?.selectionStart === "number" ? active.selectionStart : null;
  if (["history", "audit"].includes(state.adminTab) && kind === (state.adminTab === "audit" ? "audit" : "actions")) renderAdminHistory();
  else if (kind === "bindings" && state.adminTab === "contacts") {
    const panel = qs("#bindingHistoryPanel"); if (panel) panel.innerHTML = auditPanel(kind);
  } else if (kind === `student:${state.studentProfileId}`) {
    const panel = qs("#studentActionTimeline"); if (panel) panel.innerHTML = auditPanel(kind, true);
  }
  if (field) {
    const replacement = qs(`[data-audit-field="${field}"][data-audit-kind="${kind}"]`);
    replacement?.focus(); if (start !== null && replacement?.type === "search") replacement.setSelectionRange(start, start);
  }
  refreshIcons();
}

function renderAdminHistory() {
  const panel = qs("#adminPanel"); if (!panel) return;
  const kind = state.adminTab === "audit" ? "audit" : "actions";
  if (kind === "audit" && !fullAuditEnabled()) { state.adminTab = "history"; renderAdminPanel(); return; }
  panel.innerHTML = auditPanel(kind); refreshIcons();
}

document.addEventListener("click", (event) => {
  const target = event.target.closest("button"); if (!target) return;
  if (target.dataset.auditRefresh) void loadAuditFeed(target.dataset.auditRefresh, true);
  if (target.dataset.auditMore) void loadAuditFeed(target.dataset.auditMore);
  if (target.dataset.auditToggle) {
    const kind = target.dataset.auditToggle;
    auditFeed(kind).filtersOpen = !auditFeed(kind).filtersOpen;
    renderAuditCurrent(kind);
  }
  if (target.dataset.auditStudent) void (async () => {
    const tenant = target.dataset.auditTenant;
    if (tenant && tenant !== apiContext.tenantSlug) await switchTenant(tenant);
    await openAdminStudentProfile(target.dataset.auditStudent);
  })();
});
document.addEventListener("input", (event) => {
  const { auditKind: kind, auditField: field } = event.target.dataset;
  if (!kind || !["q", "actor"].includes(field)) return;
  auditFeed(kind).filters[field] = event.target.value;
  window.clearTimeout(auditSearchTimer);
  auditSearchTimer = window.setTimeout(() => void loadAuditFeed(kind, true), 450);
});
document.addEventListener("change", (event) => {
  const { auditKind: kind, auditField: field } = event.target.dataset;
  if (!kind || ["q", "actor"].includes(field)) return;
  auditFeed(kind).filters[field] = field === "allTenants" ? event.target.checked : event.target.value;
  void loadAuditFeed(kind, true);
});
