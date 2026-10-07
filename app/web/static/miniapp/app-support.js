const supportState = {
  owner: false, tab: "faq", files: [], photoIds: [], requestId: "", saving: false,
  items: [], total: 0, offset: 0, filter: "", search: "", sequence: 0,
  imageUrls: new Map(), openTickets: new Set(), loaded: false,
  focusBefore: null, unsaved: new Map(),
  replyDrafts: new Map(), replyKeys: new Map(),
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

function supportRenderInbox(counts = {}) {
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
        <div class="support-ticket-meta">MAX ID: ${escapeHtml(ticket.max_user_id)} · ${ticket.source === "bot" ? "Бот" : "Миниприложение"}${ticket.tenant_slug ? ` · ${escapeHtml(ticket.tenant_slug)}` : ""}</div>
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
}

async function supportLoadInbox() {
  if (!supportState.owner) return;
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
    const badge = qs("#supportNewCount"); badge.textContent = String(result.counts.new || 0); badge.hidden = !result.counts.new;
  } catch (error) { if (sequence === supportState.sequence) qs("#supportInboxStatus").textContent = error.message; }
}

async function supportUpdate(event) {
  event.preventDefault(); const form = event.target; const button = form.querySelector("button");
  if (button.disabled) return; button.disabled = true;
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
  if (button.disabled) return;
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

async function supportLoadContext() {
  if (apiContext.demoMode) return;
  try {
    const context = await supportApi("/context"); supportState.owner = context.inbox_enabled;
    qs("#supportInboxTab").hidden = !supportState.owner;
  } catch (_) { /* Report form remains available when profile/session is unavailable. */ }
}

document.addEventListener("click", (event) => {
  const target = event.target.closest("[data-support-open], [data-support-close], [data-support-role], [data-support-remove-photo], [data-support-tab], [data-support-filter]");
  if (!target) return;
  if (target.hasAttribute("data-support-open")) supportOpenForm();
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
