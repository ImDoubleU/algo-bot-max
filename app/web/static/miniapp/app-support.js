const supportState = {
  owner: false, tab: "faq", files: [], photoIds: [], requestId: "", saving: false,
  items: [], total: 0, offset: 0, filter: "", search: "", sequence: 0,
  imageUrls: new Map(), openTickets: new Set(), loaded: false,
  focusBefore: null, unsaved: new Map(),
  replyDrafts: new Map(), replyKeys: new Map(),
  deleting: new Set(), counts: {},
};
const SUPPORT_ROLES = { parent: "Родитель", student: "Ученик", staff: "Сотрудник" };
const SUPPORT_STATUSES = { new: "Новые", in_progress: "В работе", resolved: "Решённые" };

async function supportApi(path, options = {}) {
  const response = await apiFetch(`/api/v1/support${path}`, options);
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(apiErrorMessage(error.detail, response.status) || "Не удалось загрузить данные");
  }
  return response.status === 204 ? null : response.json();
}

function supportDraftKey() { return `algo-max-support:${apiContext.maxUserId || "demo"}`; }

function supportSaveDraft() {
  const form = qs("#supportForm");
  if (!form || supportState.saving) return;
  const fields = Object.fromEntries(new FormData(form));
  delete fields.photos;
  try { localStorage.setItem(supportDraftKey(), JSON.stringify(fields)); } catch (_) { /* WebView */ }
}

function supportSetRole(role) {
  qs("#supportRole").value = SUPPORT_ROLES[role] ? role : "";
  qs("#supportFormFields").hidden = !SUPPORT_ROLES[role];
  qsa("[data-support-role]").forEach((b) => {
    const selected = b.dataset.supportRole === role;
    b.classList.toggle("is-selected", selected);
    b.setAttribute("aria-pressed", String(selected));
  });
}

function supportOpenForm() {
  const form = qs("#supportForm");
  if (!supportState.requestId) supportState.requestId = crypto.randomUUID();
  if (!form.elements.first_name.value && !form.elements.message.value) {
    try {
      const draft = JSON.parse(localStorage.getItem(supportDraftKey()) || "{}");
      for (const name of ["first_name", "last_name", "message"]) form.elements[name].value = String(draft[name] || "");
      supportSetRole(draft.role || "");
    } catch (_) { /* No saved form */ }
  }
  qs("#supportDialog").hidden = false;
  supportState.focusBefore = document.activeElement;
  qs(".app-shell").inert = true; qs("#accessGate").inert = true;
  const focus = qs("#supportFormFields").hidden ? qs("[data-support-role]") : form.elements.first_name;
  window.setTimeout(() => focus?.focus(), 0);
}

function supportCloseForm() {
  if (supportState.saving) return;
  supportSaveDraft();
  qs("#supportDialog").hidden = true;
  qs(".app-shell").inert = false; qs("#accessGate").inert = false;
  supportState.focusBefore?.focus();
}

function supportRenderPhotos() {
  qs("#supportPhotos").innerHTML = supportState.files.map((item, index) => `
    <div class="support-photo"><img src="${escapeHtml(item.url)}" alt="Фото ${index + 1}" />
      <button type="button" class="icon-button" data-support-remove-photo="${index}" aria-label="Удалить фото ${index + 1}">×</button>
    </div>`).join("");
  qs("#supportPhotoCount").textContent = `${supportState.files.length}/5`;
}

function supportAddPhotos(files) {
  if (supportState.saving) return;
  const selected = [...files];
  const error = selected.some((f) => !["image/jpeg", "image/png", "image/webp"].includes(f.type))
    ? "Выберите фотографии JPEG, PNG или WebP"
    : selected.some((f) => f.size > 10 * 1024 * 1024) ? "Фото должно быть не больше 10 МБ"
    : selected.length + supportState.files.length > 5 ? "Можно прикрепить до 5 фотографий" : "";
  if (error) { qs("#supportFormStatus").textContent = error; return; }
  supportState.files.push(...selected.map((file) => ({ file, url: URL.createObjectURL(file), id: null })));
  qs("#supportFormStatus").textContent = "";
  supportRenderPhotos();
}

async function supportSubmit(event) {
  event.preventDefault();
  if (supportState.saving) return;
  const form = event.currentTarget;
  if (!form.reportValidity()) return;
  const fields = Object.fromEntries(new FormData(form));
  if (!SUPPORT_ROLES[fields.role]) { qs("#supportFormStatus").textContent = "Выберите роль"; return; }
  if (![fields.first_name, fields.last_name, fields.message].every((v) => String(v).trim())) {
    qs("#supportFormStatus").textContent = "Заполните имя, фамилию и описание"; return;
  }
  supportState.saving = true;
  const controls = [...form.querySelectorAll("input, textarea, button")];
  controls.forEach((e) => { e.disabled = true; });
  qs("#supportFormStatus").textContent = "Отправляем…";
  try {
    for (const item of supportState.files) {
      if (item.id) continue;
      const body = new FormData(); body.append("photo", item.file);
      item.id = (await supportApi("/photos", { method: "POST", body })).id;
    }
    const result = await supportApi("/tickets", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ request_id: supportState.requestId, role: fields.role,
        first_name: fields.first_name.trim(), last_name: fields.last_name.trim(),
        message: fields.message.trim(), photo_ids: supportState.files.map((f) => f.id) }) });
    form.reset(); supportSetRole("");
    supportState.files.forEach((f) => URL.revokeObjectURL(f.url)); supportState.files = [];
    supportState.requestId = ""; supportRenderPhotos();
    try { localStorage.removeItem(supportDraftKey()); } catch (_) { /* WebView */ }
    qs("#supportFormStatus").textContent = `Заявка №${result.id} отправлена.`;
    if (supportState.owner) { supportState.loaded = false; if (supportState.tab === "inbox") void supportLoadInbox(); }
  } catch (error) { qs("#supportFormStatus").textContent = error.message; }
  finally { supportState.saving = false; controls.forEach((e) => { e.disabled = false; }); }
}

function supportSetTab(tab) {
  if (tab === "inbox" && !supportState.owner) return;
  supportState.tab = tab;
  qs("#supportInbox").hidden = tab !== "inbox";
  qs("#helpFaqPanel").hidden = tab !== "faq";
  qsa("[data-support-tab]").forEach((b) => {
    b.classList.toggle("is-active", b.dataset.supportTab === tab);
    b.setAttribute("aria-selected", String(b.dataset.supportTab === tab));
  });
  if (tab === "inbox") void supportLoadInbox();
}

function supportReleaseImages() {
  supportState.imageUrls.forEach((url) => URL.revokeObjectURL(url)); supportState.imageUrls.clear();
}

async function supportLoadImages(ticket, container) {
  for (const id of ticket.photo_ids) {
    if (!container.isConnected) return;
    const img = document.createElement("img"); img.alt = "Фото к заявке";
    const button = document.createElement("button"); button.type = "button"; button.className = "support-ticket-photo";
    try {
      let url = supportState.imageUrls.get(id);
      if (!url) {
        const response = await apiFetch(`/api/v1/support/photos/${encodeURIComponent(id)}`);
        if (!response.ok) throw new Error("Фото не загрузилось");
        url = URL.createObjectURL(await response.blob());
        if (!container.isConnected) { URL.revokeObjectURL(url); return; }
        supportState.imageUrls.set(id, url);
      }
      img.src = url; button.append(img);
      button.addEventListener("click", () => {
        qs("#supportImageFull").src = url; qs("#supportImageDialog").hidden = false;
      });
      container.append(button);
    } catch (_) { const text = document.createElement("span"); text.textContent = "Фото не загрузилось"; container.append(text); }
  }
}

function supportUserFacts(items) {
  const visible = items.filter(([, value]) => value !== null && value !== undefined && value !== "");
  return visible.length ? `<dl class="support-user-facts">${visible.map(([name, value]) => `<div><dt>${escapeHtml(name)}</dt><dd>${escapeHtml(String(value))}</dd></div>`).join("")}</dl>` : "";
}

function supportUserDate(value) {
  if (!value || Number.isNaN(new Date(value).getTime())) return "";
  return new Date(value).toLocaleString("ru-RU", {timeZone: "Europe/Moscow"});
}

function supportUserSchool(school) {
  return school ? [school.city, school.partner].filter(Boolean).join(" · ") || school.name || school.slug : "";
}

function supportUserStudentMarkup(student, ticket) {
  const links = student.links || [];
  const active = links.filter((link) => link.status === "active");
  const badge = !active.length ? links.some((link) => link.status === "disputed") ? "Требует проверки" : "Связь отключена" : active.some((link) => link.role === "student") && !student.parent_connected ? "Нужен родитель" : "Связь активна";
  const reasons = {parent_required: "Родитель не подключён", parent_required_hotfix: "Отключено до подключения родителя", bot_stopped: "Бот остановлен пользователем", registration_reset: "Регистрация сброшена", sponsor_revoked: "Связь родителя отключена", sponsor_bot_stopped: "Родитель остановил бота", admin: "Отключено администратором"};
  const maxIds = [...new Set((student.accounts || []).filter((account) => account.role === "student").map((account) => account.max_id))];
  const parents = (student.accounts || []).filter((account) => account.role === "parent" && String(account.max_id) !== String(ticket.max_user_id));
  return `<article class="support-user-student">
    <header><button type="button" class="audit-student-link" data-audit-student="${escapeHtml(student.id)}" data-audit-tenant="${escapeHtml(student.school?.slug || "")}">${escapeHtml(student.name)}<i data-lucide="arrow-up-right"></i></button><span class="support-user-link-state ${!active.length ? "is-inactive" : ""}">${badge}</span></header>
    ${supportUserFacts([["Связь автора", [...new Set(links.map((link) => auditReadable(link.role)))].join(", ")],
      ["MAX ID ученика", maxIds.join(", ") || "—"], ["LMS ID", student.lms_id || "—"],
      ["Школа", supportUserSchool(student.school)], ["Группа", student.group], ["Курс", student.course],
      ["Площадка", student.venue], ["Преподаватель", [student.teacher, student.teacher_max_id ? `MAX ID ${student.teacher_max_id}` : ""].filter(Boolean).join(" · ")],
      ["Статус ученика", {active: "Обучается", departed: "Выбыл", archived: "В архиве"}[student.status]],
      ["Баланс", student.balance !== undefined ? `${student.balance} AC` : null]])}
    ${parents.length ? `<div class="support-user-parents"><h5>Родители в MAX</h5>${parents.map((parent) => `<div><strong>${escapeHtml(parent.name || "Имя не указано")}</strong>${supportUserFacts([["MAX ID", parent.max_id], ["Логин", parent.username ? `@${parent.username.replace(/^@/, "")}` : ""], ["Телефон", parent.phone]])}</div>`).join("")}</div>` : ""}
    <details class="support-user-extra"><summary>Связи и другие ID</summary>
      ${supportUserFacts([["ID ученика", student.id], ["CRM ID", student.crm_id], ["CRM UUID", student.crm_uuid],
        ["Дата рождения", student.birth_date ? new Date(student.birth_date).toLocaleDateString("ru-RU", {timeZone: "Europe/Moscow"}) : ""],
        ["Родитель подключён", student.parent_connected ? "Да" : "Нет"]])}
      ${links.map((link) => `<div class="support-user-binding">${supportUserFacts([
        ["Роль", auditReadable(link.role)], ["Статус связи", {active: "Активна", revoked: "Отключена", disputed: "Требует проверки"}[link.status] || link.status],
        ["Способ подключения", link.source === "import" ? "Импорт" : auditReadable(link.source)], ["Подключён", supportUserDate(link.connected_at)],
        ["Отключён", supportUserDate(link.revoked_at)], ["Причина отключения", reasons[link.revoked_reason] || link.revoked_reason], ["ID связи", link.id]])}</div>`).join("")}
      ${(student.contacts || []).length ? `<h5>Контакты из импорта</h5>${student.contacts.map((contact) => supportUserFacts([["Имя", contact.name], ["ID контакта", contact.id]])).join("")}` : ""}
    </details>
  </article>`;
}

function supportUserMarkup(ticket) {
  const context = ticket.user_context || {};
  const account = context.account;
  const staff = context.staff || [];
  const students = context.students || [];
  const roles = [...new Set([...staff.filter((item) => item.status === "active").map((item) => item.role),
    ...students.flatMap((student) => (student.links || []).filter((link) => link.status === "active").map((link) => link.role))])];
  const statedName = `${ticket.last_name} ${ticket.first_name}`.trim();
  return `<section class="support-user-panel"><div class="support-user-panel-heading"><h4>Пользователь</h4>${supportState.owner && fullAuditEnabled() ? `<button type="button" class="text-action" data-support-user-history="${escapeHtml(ticket.max_user_id)}">Действия пользователя</button>` : ""}</div>
    ${supportUserFacts([["MAX ID автора", ticket.max_user_id], ["Роли в системе", roles.map(auditReadable).join(", ")],
      ["Имя в MAX", account?.name && account.name !== statedName ? account.name : ""],
      ["ФИО сотрудника", account?.staff_name && ![statedName, account.name].includes(account.staff_name) ? account.staff_name : ""],
      ["Логин", account?.username ? `@${account.username.replace(/^@/, "")}` : ""], ["Телефон", account?.phone],
      ["Школа отправки", supportUserSchool(context.origin_school) || ticket.tenant_slug],
      ["Источник", ticket.source === "bot" ? "Бот" : "Миниприложение"]])}
    ${account ? `<details class="support-user-extra"><summary>Данные аккаунта</summary>${supportUserFacts([
      ["ID аккаунта", account.id], ["В системе с", supportUserDate(account.created_at)],
      ["Профиль обновлён", supportUserDate(account.updated_at)], ["Последнее действие", supportUserDate(account.last_activity_at)]])}</details>` : ""}
    ${students.length ? `<h5 class="support-user-section-title">Связанные ученики</h5>${students.map((student) => supportUserStudentMarkup(student, ticket)).join("")}` : ""}
    ${staff.length ? `<h5 class="support-user-section-title">Доступ сотрудника</h5>${staff.map((item) => `<article class="support-user-staff ${item.status !== "active" ? "is-inactive" : ""}"><header><strong>${escapeHtml(auditReadable(item.role))}</strong>${item.status !== "active" ? "<span>Отключён</span>" : ""}</header>
      ${supportUserFacts([["Школа", supportUserSchool(item.school)], ["Площадки", (item.venues || []).join(", ")], ["Назначен", supportUserDate(item.since)]])}
      ${(item.groups || []).length ? `<div class="support-user-groups">${item.groups.map((group) => `<div><strong>${escapeHtml(group.name || "Без группы")}</strong><span>${escapeHtml([group.course, group.venue, `Учеников: ${group.students}`].filter(Boolean).join(" · "))}</span></div>`).join("")}</div>` : ""}</article>`).join("")}` : ""}
    ${ticket.user_context && !students.length && !staff.length ? '<span class="support-user-unlinked">Нет привязок в системе</span>' : ""}
  </section>`;
}

function supportRenderInbox(counts = {}) {
  supportState.counts = counts;
  const badge = qs("#supportNewCount"); badge.textContent = String(counts.new || 0); badge.hidden = !counts.new;
  qs("#supportFilters").innerHTML = [["", "Все"], ...Object.entries(SUPPORT_STATUSES)].map(([status, label]) => `
    <button type="button" class="support-filter ${supportState.filter === status ? "is-active" : ""}"
      data-support-filter="${status}" aria-pressed="${supportState.filter === status}">${label}
      <span>${status ? counts[status] || 0 : Object.values(counts).reduce((s, v) => s + v, 0)}</span></button>`).join("");
  qs("#supportTicketList").innerHTML = supportState.items.length ? supportState.items.map((ticket) => `
    <details class="support-ticket" data-ticket="${ticket.id}" ${supportState.openTickets.has(ticket.id) ? "open" : ""}>
      <summary><span class="support-ticket-number">#${ticket.id}</span><span class="support-ticket-title">
        <strong>${escapeHtml(ticket.last_name)} ${escapeHtml(ticket.first_name)}</strong>
        <small>${escapeHtml(SUPPORT_ROLES[ticket.role])} · ${new Date(ticket.created_at).toLocaleString("ru-RU", {timeZone: "Europe/Moscow", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit"})}</small></span>
        <span class="support-badge support-badge-${ticket.status}">${escapeHtml(SUPPORT_STATUSES[ticket.status])}</span>
      </summary>
      <div class="support-ticket-body"><p class="support-ticket-message">${escapeHtml(ticket.message)}</p>
        ${supportUserMarkup(ticket)}
        <div class="support-ticket-photos" data-ticket-photos="${ticket.id}"></div>
        <form data-support-update="${ticket.id}" class="support-ticket-update">
          <label>Статус<select name="status" class="support-control">${Object.entries(SUPPORT_STATUSES).map(([s,l]) => `<option value="${s}" ${s === ticket.status ? "selected" : ""}>${l}</option>`).join("")}</select></label>
          <label>Заметка<textarea name="private_note" class="support-control" rows="2" maxlength="4000">${escapeHtml(ticket.private_note)}</textarea></label>
          <button class="secondary-action" type="submit">Сохранить</button><span data-update-result role="status"></span>
        </form>
        <div class="support-reply-history">${(ticket.replies || []).map((reply) => `
          <article class="support-reply"><small>${reply.status === "sent" ? "Отправлен в MAX" : reply.status === "retry" ? "Повторная отправка" : "Ожидает отправки"}</small>
            <p>${escapeHtml(reply.message)}</p></article>`).join("")}</div>
        <form data-support-reply="${ticket.id}" class="support-ticket-update">
          <label>Ответ автору в MAX<textarea name="reply_message" class="support-control" rows="3" maxlength="3500" required ${
            (ticket.replies || []).some((r) => r.status !== "sent") ? "disabled" : ""}></textarea></label>
          <button class="primary-action" type="submit" ${(ticket.replies || []).some((r) => r.status !== "sent") ? "disabled" : ""}>Ответить и решить</button>
          <span data-reply-result role="status"></span>
        </form>
        ${supportState.owner ? `<div class="support-ticket-danger"><button type="button" class="secondary-action is-danger" data-support-delete="${ticket.id}"><i data-lucide="trash-2"></i>Удалить тикет</button></div>` : ""}
      </div>
    </details>`).join("") : '<div class="support-empty">Заявок пока нет</div>';
  qs("#supportPrevious").disabled = supportState.offset === 0;
  qs("#supportNext").disabled = supportState.offset + supportState.items.length >= supportState.total;
  qs("#supportPagination").hidden = supportState.total <= 30;
  qs("#supportPageLabel").textContent = `${supportState.offset + 1}–${supportState.offset + supportState.items.length} из ${supportState.total}`;
  qsa(".support-ticket").forEach((details) => {
    const ticket = supportState.items.find((t) => t.id === Number(details.dataset.ticket));
    const photos = details.querySelector("[data-ticket-photos]");
    function opened() {
      if (details.open) {
        supportState.openTickets.add(ticket.id);
        if (!photos.dataset.loaded) { photos.dataset.loaded = "1"; void supportLoadImages(ticket, photos); }
      } else supportState.openTickets.delete(ticket.id);
    }
    details.addEventListener("toggle", opened); if (details.open) opened();
    const form = details.querySelector("form");
    const saved = supportState.unsaved.get(ticket.id);
    if (saved) { form.elements.status.value = saved.status; form.elements.private_note.value = saved.private_note; }
    form.addEventListener("input", () => { supportState.unsaved.set(ticket.id, Object.fromEntries(new FormData(form))); });
    const replyForm = details.querySelector("[data-support-reply]");
    replyForm.elements.reply_message.value = supportState.replyDrafts.get(ticket.id) || "";
    replyForm.addEventListener("input", () => {
      const text = replyForm.elements.reply_message.value;
      if (text) supportState.replyDrafts.set(ticket.id, text); else supportState.replyDrafts.delete(ticket.id);
    });
  });
  refreshIcons();
}

async function supportLoadInbox() {
  if (!supportState.owner || supportState.deleting.size) return;
  const sequence = ++supportState.sequence;
  qs("#supportInboxStatus").textContent = "Загрузка…";
  try {
    const query = new URLSearchParams({ offset: supportState.offset, search: supportState.search });
    if (supportState.filter) query.set("status", supportState.filter);
    const result = await supportApi(`/tickets?${query}`);
    if (sequence !== supportState.sequence) return;
    supportReleaseImages();
    supportState.items = result.items; supportState.total = result.total; supportState.loaded = true;
    supportRenderInbox(result.counts); qs("#supportInboxStatus").textContent = "";
  } catch (error) { if (sequence === supportState.sequence) qs("#supportInboxStatus").textContent = error.message; }
}

async function supportUpdate(event) {
  event.preventDefault(); const form = event.target; const button = form.querySelector("button");
  if (button.disabled || supportState.deleting.has(Number(form.dataset.supportUpdate))) return; button.disabled = true;
  try {
    const values = Object.fromEntries(new FormData(form));
    await supportApi(`/tickets/${form.dataset.supportUpdate}`, { method: "PATCH",
      headers: {"Content-Type": "application/json"}, body: JSON.stringify(values) });
    supportState.unsaved.delete(Number(form.dataset.supportUpdate));
    await supportLoadInbox();
  } catch (error) { form.querySelector("[data-update-result]").textContent = error.message; }
  finally { button.disabled = false; }
}

async function supportReply(event) {
  event.preventDefault(); const form = event.target; const button = form.querySelector("button");
  const id = Number(form.dataset.supportReply);
  if (button.disabled || supportState.deleting.has(id)) return;
  const message = form.elements.reply_message.value.trim();
  if (!message) { form.querySelector("[data-reply-result]").textContent = "Напишите ответ"; return; }
  if (!supportState.replyKeys.has(id)) supportState.replyKeys.set(id, crypto.randomUUID());
  button.disabled = true; form.elements.reply_message.disabled = true;
  try {
    await supportApi(`/tickets/${id}/replies`, { method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({request_id: supportState.replyKeys.get(id), message}) });
    supportState.replyKeys.delete(id); supportState.replyDrafts.delete(id);
    await supportLoadInbox();
  } catch (error) { form.querySelector("[data-reply-result]").textContent = error.message; }
  finally { button.disabled = false; form.elements.reply_message.disabled = false; }
}

async function supportDeleteTicket(id) {
  if (!supportState.owner || supportState.deleting.size) return;
  const ticket = supportState.items.find((item) => item.id === id);
  if (!ticket) return;
  supportState.deleting.add(id);
  let controls = [];
  try {
    const confirmed = await requestConfirmation({
      title: `Удалить тикет №${id}?`,
      message: "Тикет, ответы, фотографии и связанная история будут удалены. Восстановить их нельзя.",
      confirmLabel: "Удалить полностью", cancelLabel: "Отмена", destructive: true,
    });
    if (!confirmed) return;
    ++supportState.sequence;
    const row = qs(`[data-ticket="${id}"]`);
    controls = [...(row?.querySelectorAll("button, input, select, textarea") || [])].map((node) => [node, node.disabled]);
    controls.forEach(([node]) => { node.disabled = true; });
    qs("#supportInboxStatus").textContent = "Удаление…";
    await supportApi(`/tickets/${id}`, {method: "DELETE"});
    supportState.items = supportState.items.filter((item) => item.id !== id);
    supportState.total = Math.max(0, supportState.total - 1);
    supportState.openTickets.delete(id); supportState.unsaved.delete(id);
    supportState.replyDrafts.delete(id); supportState.replyKeys.delete(id);
    for (const photoId of ticket.photo_ids || []) {
      const url = supportState.imageUrls.get(photoId);
      if (url) {
        if (qs("#supportImageFull").getAttribute("src") === url) {
          qs("#supportImageDialog").hidden = true; qs("#supportImageFull").removeAttribute("src");
        }
        URL.revokeObjectURL(url); supportState.imageUrls.delete(photoId);
      }
    }
    const counts = {...supportState.counts};
    counts[ticket.status] = Math.max(0, (counts[ticket.status] || 0) - 1);
    supportRenderInbox(counts);
    if (supportState.offset >= supportState.total) supportState.offset = Math.max(0, supportState.offset - 30);
    if (typeof resetAuditFeeds === "function") resetAuditFeeds();
    supportState.deleting.delete(id);
    await supportLoadInbox();
    qs("#supportRefresh").focus();
  } catch (error) { qs("#supportInboxStatus").textContent = error.message; }
  finally {
    supportState.deleting.delete(id);
    controls.forEach(([node, disabled]) => { if (node.isConnected) node.disabled = disabled; });
  }
}

async function supportLoadContext() {
  if (apiContext.demoMode) return;
  try {
    const context = await supportApi("/context"); supportState.owner = context.inbox_enabled;
    qs("#supportInboxTab").hidden = !supportState.owner;
  } catch (_) { /* Report form remains available when profile/session is unavailable. */ }
}

document.addEventListener("click", (event) => {
  const target = event.target.closest("[data-support-open], [data-support-close], [data-support-role], [data-support-remove-photo], [data-support-tab], [data-support-filter], [data-support-delete], [data-support-user-history]");
  if (!target) return;
  if (target.hasAttribute("data-support-open")) supportOpenForm();
  if (target.dataset.supportDelete) void supportDeleteTicket(Number(target.dataset.supportDelete));
  if (target.dataset.supportUserHistory && supportState.owner && fullAuditEnabled()) {
    const feed = auditFeed("audit");
    feed.filters = {q: "", category: "", outcome: "", actor: target.dataset.supportUserHistory,
      days: "3650", from: "", to: "", allTenants: true};
    state.adminTab = "audit"; renderAdminPanel(); setView("admin"); void loadAuditFeed("audit", true);
  }
  if (target.hasAttribute("data-support-close")) supportCloseForm();
  if (target.dataset.supportRole && !supportState.saving) { supportSetRole(target.dataset.supportRole); qs("#supportFormStatus").textContent = ""; supportSaveDraft(); }
  if (target.dataset.supportTab) supportSetTab(target.dataset.supportTab);
  if (target.hasAttribute("data-support-filter")) { supportState.filter = target.dataset.supportFilter; supportState.offset = 0; void supportLoadInbox(); }
  if (target.hasAttribute("data-support-remove-photo") && !supportState.saving) {
    const [item] = supportState.files.splice(Number(target.dataset.supportRemovePhoto), 1);
    if (item) { URL.revokeObjectURL(item.url); if (item.id) void supportApi(`/photos/${item.id}`, {method: "DELETE"}).catch(() => {}); }
    supportRenderPhotos();
  }
});
document.addEventListener("submit", (event) => {
  if (event.target.matches("[data-support-update]")) void supportUpdate(event);
  if (event.target.matches("[data-support-reply]")) void supportReply(event);
});
qs("#supportForm").addEventListener("submit", supportSubmit);
qs("#supportForm").addEventListener("input", supportSaveDraft);
qs("#supportFileInput").addEventListener("change", (event) => { supportAddPhotos(event.target.files); event.target.value = ""; });
qs("#supportDialog").addEventListener("click", (event) => { if (event.target.id === "supportDialog") supportCloseForm(); });
qs("#supportRefresh").addEventListener("click", () => { void supportLoadInbox(); });
qs("#supportPrevious").addEventListener("click", () => { supportState.offset = Math.max(0, supportState.offset - 30); void supportLoadInbox(); });
qs("#supportNext").addEventListener("click", () => { supportState.offset += 30; void supportLoadInbox(); });
let supportSearchTimer;
qs("#supportSearch").addEventListener("input", (event) => {
  supportState.search = event.target.value; supportState.offset = 0;
  window.clearTimeout(supportSearchTimer); supportSearchTimer = window.setTimeout(supportLoadInbox, 300);
});
qs("#supportImageClose").addEventListener("click", () => { qs("#supportImageDialog").hidden = true; qs("#supportImageFull").removeAttribute("src"); });
document.addEventListener("keydown", (event) => {
  if (event.key === "Tab" && !qs("#supportDialog").hidden) {
    const controls = [...qs("#supportDialog").querySelectorAll("button, input, textarea")]
      .filter((e) => !e.disabled && e.type !== "hidden" && e.getClientRects().length);
    const first = controls[0]; const last = controls[controls.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
    if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
  }
  if (event.key !== "Escape") return;
  if (!qs("#supportImageDialog").hidden) qs("#supportImageClose").click();
  else if (!qs("#supportDialog").hidden) supportCloseForm();
});
window.setInterval(() => {
  if (supportState.owner && supportState.tab === "inbox" && state.view === "help" && !document.hidden
    && !supportState.unsaved.size && !supportState.replyDrafts.size && !qs("#supportInbox").contains(document.activeElement)) void supportLoadInbox();
}, 30000);
void supportLoadContext();
