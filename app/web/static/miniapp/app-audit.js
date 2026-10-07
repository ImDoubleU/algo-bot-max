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
    groupMinutes: 5, openGroups: new Set(),
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
    feed.openGroups.clear();
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
  const staffLabels = {curator: "Куратор", partner_director: "Директор", warehouse_manager: "Сотрудник склада"};
  if (typeof value === "string" && staffLabels[value]) return staffLabels[value];
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

function isAuditAccrual(entry) {
  return ["miniapp_astrocoins.accrued", "miniapp_astrocoins.undone", "astrocoins.birthday_rewarded"].includes(entry.action);
}

function auditPeople(entry) {
  const p = entry.payload || {};
  const accrual = isAuditAccrual(entry);
  const students = Array.isArray(p.students) ? p.students : [];
  const role = String(p.actor_role || p.role || "").split(", ").filter(Boolean).map(auditReadable).join(", ");
  const actor = {
    role: role || "Автор", name: entry.actorName === `Аккаунт MAX ${entry.actorMaxUserId}` ? "Имя не указано" : entry.actorName,
    ids: entry.actorMaxUserId ? [entry.actorMaxUserId] : [], actor: true, current: false,
  };
  const people = [actor];
  const representedIds = new Set(actor.ids.map(String));
  const contexts = new Map();
  const additional = [];
  students.forEach((student) => {
    const accounts = Array.isArray(student.accounts) ? student.accounts : [];
    const childIds = [...new Set(accounts.filter((account) => account.role === "student" && (!account.status || account.status === "active")).map((account) => account.max_user_id).filter(Boolean).map(String))];
    const isActor = p.actor_role === "student" && (students.length === 1 || childIds.some((id) => String(id) === String(entry.actorMaxUserId)));
    const person = isActor ? actor : {role: "Ученик", ids: childIds, current: childIds.length > 0};
    Object.assign(person, {name: student.name, studentId: student.id, lmsId: student.lms_id, crmId: student.crm_id, studentTenantSlug: student.tenant_slug});
    if (!isActor) people.push(person);
    if (isActor) {
      person.currentIds = childIds.filter((id) => !person.ids.some((known) => String(known) === String(id)));
      person.ids.push(...person.currentIds);
    }
    person.ids.forEach((id) => representedIds.add(String(id)));
    if (!accrual) accounts.filter((account) => account.role !== "student").forEach((account) => additional.push(account));
    const teacherShown = student.teacher_max_user_id && representedIds.has(String(student.teacher_max_user_id));
    const context = {group: student.group, teacher: teacherShown || accrual ? "" : student.teacher, teacherId: teacherShown || accrual ? null : student.teacher_max_user_id};
    if (context.group || context.teacher) contexts.set(JSON.stringify(context), context);
  });
  additional.forEach((account) => {
    const key = String(account.max_user_id);
    if (representedIds.has(key)) return;
    representedIds.add(key);
    people.push({role: auditReadable(account.role), name: account.name || "Имя не указано", ids: [account.max_user_id], current: true});
  });
  return {people, contexts: [...contexts.values()]};
}

function auditPersonNameMarkup(person, entry) {
  return person.studentId ? `<button type="button" class="audit-student-link" data-audit-student="${escapeHtml(person.studentId)}" data-audit-tenant="${escapeHtml(person.studentTenantSlug || entry.tenantSlug || "")}">${escapeHtml(person.name)}<i data-lucide="arrow-up-right"></i></button>` : `<strong>${escapeHtml(person.name)}</strong>`;
}

function auditPersonMarkup(person, entry) {
  const name = auditPersonNameMarkup(person, entry);
  return `<div class="audit-person" ${person.actor ? 'data-audit-actor' : ""}>
    <span class="audit-person-role">${escapeHtml(person.role)}</span>
    <div class="audit-person-name">${name}${person.current ? '<small class="audit-current" title="Текущая привязка; состояние на момент события может отличаться">сейчас</small>' : ""}</div>
    <div class="audit-person-ids">${person.ids.map((id) => `<code>MAX ID ${escapeHtml(id)}${person.currentIds?.includes(id) ? ' <small class="audit-current">сейчас</small>' : ""}</code>`).join("")}${person.lmsId ? `<code>LMS ID ${escapeHtml(person.lmsId)}</code>` : ""}</div>
  </div>`;
}

function auditParticipantsMarkup(model, entry, showActor = true) {
  if (!isAuditAccrual(entry)) {
    const people = model.people.filter((person) => showActor || !person.actor);
    return people.length ? `<div class="audit-people">${people.map((person) => auditPersonMarkup(person, entry)).join("")}</div>` : "";
  }
  const actor = model.people.find((person) => person.actor);
  const authorLabel = entry.action === "miniapp_astrocoins.undone" ? "Отменил" : entry.action === "astrocoins.birthday_rewarded" ? "Автор" : "Начислил";
  const author = actor && showActor ? `<div class="audit-accrual-author" data-audit-actor><span>${authorLabel}</span>${auditPersonNameMarkup(actor, entry)}${actor.ids.length ? `<code>MAX ID ${escapeHtml(actor.ids.join(", "))}</code>` : ""}</div>` : "";
  const pupils = model.people.filter((person) => person.studentId);
  const table = pupils.length ? `<table class="audit-accrual-table" aria-label="Ученики начисления">
    <colgroup><col /><col class="audit-accrual-max-column" /><col class="audit-accrual-lms-column" /></colgroup>
    <thead><tr><th scope="col">Ученик</th><th scope="col" title="Текущая привязка ученика">MAX ID</th><th scope="col">LMS ID</th></tr></thead>
    <tbody>${pupils.map((person) => `<tr><th scope="row">${auditPersonNameMarkup(person, entry)}</th><td>${person.ids.length ? person.ids.map((id) => `<code>${escapeHtml(id)}</code>`).join("") : "—"}</td><td>${escapeHtml(String(person.lmsId || "—"))}</td></tr>`).join("")}</tbody>
  </table>` : "";
  return `${author}${table}`;
}

function auditEventTitle(entry) {
  if (entry.action === "student_qr_access_link.created") return entry.payload.created === false ? "Повторный вход по QR-коду" : "Подключение по QR-коду";
  if (entry.action === "contact_access_links.created") return entry.payload.created_links || entry.payload.reactivated_links ? "Подключение по ссылке" : "Повторный вход по ссылке";
  return entry.title;
}

function auditGroups(rows, minutes = 5) {
  const groups = [];
  const latestByActor = new Map();
  const interval = minutes * 60 * 1000;
  [...rows].sort((left, right) => new Date(right.createdAt) - new Date(left.createdAt)).forEach((entry) => {
    const stamp = new Date(entry.createdAt).getTime();
    // Unknown actors remain separate: an IP or the name "Система" is not an identity.
    const key = entry.actorMaxUserId ? `${entry.actorMaxUserId}:${auditDay(entry.createdAt)}` : null;
    let group = key ? latestByActor.get(key) : null;
    if (!group || group.newest - stamp > interval) {
      group = {id: entry.id, newest: stamp, oldest: stamp, rows: []};
      groups.push(group);
      if (key) latestByActor.set(key, group);
    }
    group.rows.push(entry); group.oldest = stamp;
  });
  return groups;
}

function auditGroupedCards(rows) {
  const feed = auditFeed("audit");
  let previousDay = "";
  return auditGroups(rows, feed.groupMinutes).map((group) => {
    const first = group.rows[0];
    const day = auditDay(first.createdAt);
    const heading = day !== previousDay ? `<h4 class="audit-day">${escapeHtml(day)}</h4>` : "";
    previousDay = day;
    if (group.rows.length === 1) return heading + auditCards(group.rows, true, {grouped: true});
    const named = group.rows.find((entry) => entry.actorName && !entry.actorName.startsWith("Аккаунт MAX ")) || first;
    const actor = auditPeople(named).people.find((person) => person.actor);
    const roles = [...new Set(group.rows.flatMap((entry) => String(entry.payload.actor_role || entry.payload.staff_role || "").split(", ").filter(Boolean)))].map(auditReadable).join(", ");
    const status = ["error", "denied", "partial", "pending"].find((value) => group.rows.some((entry) => entry.status === value)) || "success";
    const attention = group.rows.filter((entry) => entry.status !== "success").length;
    const meaningful = group.rows.filter((entry) => entry.action !== "activity.request");
    const titles = [...new Set((meaningful.length ? meaningful : group.rows).map(auditEventTitle))];
    const range = `${auditTime(new Date(group.oldest).toISOString())} — ${auditTime(first.createdAt)}`;
    return `${heading}<details class="audit-session is-${status}" data-audit-group="${escapeHtml(group.id)}" ${feed.openGroups.has(group.id) ? "open" : ""}>
      <summary class="audit-session-summary">
        <span class="audit-session-avatar"><i data-lucide="user-round"></i></span>
        <span class="audit-session-person">${auditPersonNameMarkup(actor, named)}<span>${roles ? escapeHtml(roles) + " · " : ""}MAX ID ${escapeHtml(String(first.actorMaxUserId))}</span></span>
        <span class="audit-session-range"><time datetime="${escapeHtml(first.createdAt)}" title="Время Москвы">${escapeHtml(range)}</time><span>${group.rows.length} ${auditActionCount(group.rows.length)}</span></span>
        <i class="audit-session-chevron" data-lucide="chevron-down"></i>
        <span class="audit-session-preview">${escapeHtml(titles.slice(0, 3).join(" · "))}${titles.length > 3 ? ` · ещё ${titles.length - 3}` : ""}</span>
        ${attention ? `<span class="audit-session-warning">Требуют внимания: ${attention}</span>` : ""}
      </summary>
      <div class="audit-session-events">${auditCards([...group.rows].reverse(), true, {grouped: true, hideActor: true})}</div>
    </details>`;
  }).join("");
}

function auditActionCount(count) {
  if (count % 100 >= 11 && count % 100 <= 14) return "действий";
  return count % 10 === 1 ? "действие" : count % 10 >= 2 && count % 10 <= 4 ? "действия" : "действий";
}

function auditLinkTargetMarkup(entry) {
  const target = entry.payload?.link_target;
  if (!target) return "";
  const label = target.kind === "contact" ? "ID родителя из ссылки" : "ID ученика из ссылки";
  const description = target.state === "historical_id_missing"
    ? "ID ссылки в старом событии не сохранился"
    : "ID ссылки при входе не был передан";
  const students = entry.payload.students || [];
  return `<div class="audit-link-target"><span>${escapeHtml(target.id ? label : description)}</span>
    ${target.id ? `<code>${escapeHtml(target.id)}</code>` : ""}
    ${!students.length ? '<code>LMS ID —</code>' : ""}</div>`;
}

function auditCards(rows, full = false, {grouped = false, hideActor = false} = {}) {
  if (full && !grouped) return auditGroupedCards(rows);
  let previousDay = "";
  return rows.map((entry) => {
    const day = auditDay(entry.createdAt);
    const heading = !grouped && day !== previousDay ? `<h4 class="audit-day">${escapeHtml(day)}</h4>` : "";
    previousDay = day;
    const status = {success: ["check", "Выполнено"], denied: ["shield-alert", "Отказ"], error: ["circle-x", "Не выполнено"], partial: ["triangle-alert", "Требует внимания"], pending: ["clock", "В обработке"]}[entry.status] || ["info", "Событие"];
    const model = auditPeople(entry);
    const facts = auditFacts(entry).filter(([key]) => !["Роль", "Способ входа", "Детей в семье", "Привязок создано", "Привязок восстановлено"].includes(key) && !(key === "Ученик" && model.people.some((person) => person.studentId)) && !(key === "Группа" && model.contexts.length));
    const studentDetails = model.people.filter((person) => person.studentId).map((person) => `<div><dt>${escapeHtml(person.name)}</dt><dd>ID ${escapeHtml(person.studentId)}${person.crmId ? ` · CRM ID ${escapeHtml(person.crmId)}` : ""}</dd></div>`).join("");
    const diagnostics = full ? `<div><dt>Событие</dt><dd>${escapeHtml(entry.action)}</dd></div><div><dt>Запись</dt><dd>${escapeHtml(entry.id)}</dd></div>${entry.requestId ? `<div><dt>Запрос</dt><dd>${escapeHtml(entry.requestId)}</dd></div>` : ""}${entry.ipAddress ? `<div><dt>IP</dt><dd>${escapeHtml(entry.ipAddress)}</dd></div>` : ""}<div><dt>Объект</dt><dd>${escapeHtml([entry.entityType, entry.entityId].filter(Boolean).join(" · "))}</dd></div>` : "";
    return `${heading}<article class="audit-event is-${escapeHtml(entry.status)}" data-audit-entry="${escapeHtml(entry.id)}">
      <span class="audit-icon" role="img" aria-label="${status[1]}"><i data-lucide="${status[0]}" aria-hidden="true"></i></span>
      <div class="audit-copy">
        <div class="audit-heading"><div class="audit-title"><strong>${escapeHtml(auditEventTitle(entry))}</strong>${entry.status !== "success" ? `<span class="audit-badge">${status[1]}</span>` : ""}</div><time datetime="${escapeHtml(entry.createdAt)}" title="Время Москвы">${escapeHtml(auditTime(entry.createdAt))}</time></div>
        ${full ? auditLinkTargetMarkup(entry) : ""}
        ${auditParticipantsMarkup(model, entry, !hideActor)}
        ${model.contexts.length ? `<div class="audit-context">${model.contexts.map((context) => `<div>${context.group ? `<span><small>Группа</small>${escapeHtml(context.group)}</span>` : ""}${context.teacher ? `<span><small>Преподаватель</small>${escapeHtml(context.teacher)}${context.teacherId ? ` <code>MAX ID ${escapeHtml(context.teacherId)}</code>` : ""}</span>` : ""}</div>`).join("")}</div>` : ""}
        ${entry.explanation ? `<p class="audit-explanation">${escapeHtml(entry.explanation)}</p>` : ""}
        ${facts.length ? `<dl class="audit-facts">${facts.map(([key, value]) => `<div><dt>${escapeHtml(key)}</dt><dd>${escapeHtml(value)}</dd></div>`).join("")}</dl>` : ""}
        <div class="audit-footer"><div class="audit-tags">${entry.payload.source ? `<span>${escapeHtml(auditReadable(entry.payload.source))}</span>` : `<span>${escapeHtml(entry.category)}</span>`}${full && entry.tenantName ? `<span>${escapeHtml(entry.tenantName)}</span>` : ""}</div>
          ${studentDetails || full ? `<details class="audit-details ${full ? "audit-technical" : ""}"><summary>${full ? "Детали аудита" : "ID ученика"}</summary><div class="audit-detail-content"><dl class="audit-facts">${studentDetails}${diagnostics}</dl>${full ? `<pre>${escapeHtml(JSON.stringify(entry.payload, null, 2))}</pre>` : ""}</div></details>` : ""}
        </div>
      </div>
    </article>`;
  }).join("");
}

function auditPanel(kind, compact = false) {
  const feed = auditFeed(kind); const f = feed.filters; const full = kind === "audit";
  const attrs = (field) => `data-audit-field="${field}" data-audit-kind="${escapeHtml(kind)}"`;
  const title = full ? "Аудит действий" : kind === "bindings" ? "История подключений" : "История действий";
  return `<section class="audit-panel" data-audit-panel="${escapeHtml(kind)}">
    <div class="audit-toolbar">${full ? `<label class="audit-group-control"><span>Интервал</span><select data-audit-group-minutes>${[1, 5, 15, 30].map((minutes) => `<option value="${minutes}" ${feed.groupMinutes === minutes ? "selected" : ""}>${minutes} мин</option>`).join("")}</select></label>` : `<h3>${title}</h3>`}<button class="secondary-action" type="button" data-audit-refresh="${escapeHtml(kind)}" ${feed.loading ? "disabled" : ""}><i data-lucide="refresh-cw"></i>Обновить</button></div>
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
  if (event.target.matches("[data-audit-group-minutes]")) {
    const minutes = Number(event.target.value);
    if (![1, 5, 15, 30].includes(minutes)) return;
    auditFeed("audit").groupMinutes = minutes;
    auditFeed("audit").openGroups.clear(); renderAuditCurrent("audit"); return;
  }
  const { auditKind: kind, auditField: field } = event.target.dataset;
  if (!kind || ["q", "actor"].includes(field)) return;
  auditFeed(kind).filters[field] = field === "allTenants" ? event.target.checked : event.target.value;
  void loadAuditFeed(kind, true);
});

document.addEventListener("toggle", (event) => {
  const groupId = event.target.dataset?.auditGroup;
  if (!groupId || !event.target.isConnected) return;
  const openGroups = auditFeed("audit").openGroups;
  if (event.target.open) openGroups.add(groupId); else openGroups.delete(groupId);
}, true);
