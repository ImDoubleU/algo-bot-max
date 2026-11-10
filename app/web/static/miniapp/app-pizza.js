/* A collection is not a cart item: one fixed share, one student, automatic refund. */
const pizzaState = {board: null, loading: false, busy: false, disabled: false, error: "", offset: 0, focus: null, context: ""};
const PIZZA_STATES = {
  open: "Собираем", funded: "Сумма собрана", paid: "Деньги переданы",
  ordered: "Пицца заказана", delivered: "Пицца приехала", cancelled: "Сбор отменён", expired: "Срок истёк",
};
const pizzaNumber = (value) => Number(value || 0).toLocaleString("ru-RU");
const pizzaEscape = (value) => escapeHtml(String(value ?? ""));
const pizzaContextKey = () => [window.pizzaPreview?.tenant || apiContext.tenantSlug,
  state.role, ["student", "parent"].includes(state.role) ? selectedStudent()?.id : "staff"].join(":");
const pizzaOfferIcon = (c) => c.kind === "other" ? "piggy-bank" : "pizza";
const pizzaStatus = (c) => c.kind === "other" && c.status === "ordered" ? "Заказ оформлен" :
  c.kind === "other" && c.status === "delivered" ? "Заказ получен" : PIZZA_STATES[c.status];

function pizzaIllustration() {
  return `<svg class="pizza-art" viewBox="0 0 320 280" role="img" aria-label="Пицца для всей группы">
    <defs><filter id="pizzaShadow" x="-40%" y="-40%" width="180%" height="180%"><feDropShadow dx="0" dy="9" stdDeviation="9" flood-color="#903e15" flood-opacity=".14"/></filter>
    <radialGradient id="pizzaCheese"><stop stop-color="#ffe594"/><stop offset="1" stop-color="#f9bd52"/></radialGradient></defs>
    <g filter="url(#pizzaShadow)"><g transform="translate(160 134) rotate(-12)">
    <circle r="117" fill="#fff9ef" stroke="#f2debf" stroke-width="2"/>
    <circle r="101" fill="#df8a37"/><circle r="94" fill="#f6b95b"/>
    <circle r="86" fill="#d75c36"/><circle r="81" fill="url(#pizzaCheese)"/>
    ${[[0,-50],[50,-15],[32,49],[-26,47],[-50,-14],[0,8]].map(([x,y])=>`<circle cx="${x}" cy="${y}" r="15" fill="#d55b43" stroke="#bd4835" stroke-width="2"/><circle cx="${x-3}" cy="${y-3}" r="3" fill="#eb9675" opacity=".8"/>`).join("")}
    ${[[-23,-52],[50,28],[-52,25],[19,-24],[-9,61],[62,-44]].map(([x,y])=>`<path d="M${x} ${y}q-14 -17 -18 2q15 14 18 -2" fill="#518355"/>`).join("")}
    ${[0,45,90,135].map(a=>`<path d="M0 -97V97" stroke="#ba742d" stroke-width="2" opacity=".45" transform="rotate(${a})"/>`).join("")}
    <circle r="107" fill="none" stroke="#fff" stroke-width="2" opacity=".3"/>
    </g></g><path d="M44 38l5 -9m222 23l9 -5M29 178l-11 2m255 43l8 8" stroke="#dc784b" stroke-width="4" stroke-linecap="round"/>
    <circle cx="271" cy="118" r="6" fill="#93ac78"/><circle cx="52" cy="232" r="4" fill="#e6a94d"/>
  </svg>`;
}

function collectionPigIllustration() {
  return `<svg class="pizza-art piggy-art" viewBox="0 0 320 280" role="img" aria-label="Копилка в виде свиньи">
    <defs>
      <filter id="pigShadow" x="-40%" y="-40%" width="180%" height="180%"><feDropShadow dx="0" dy="8" stdDeviation="8" flood-color="#9b5c45" flood-opacity=".13"/></filter>
      <radialGradient id="pigBody" cx="35%" cy="25%" r="80%"><stop stop-color="#ffe1d5"/><stop offset=".55" stop-color="#f7b8aa"/><stop offset="1" stop-color="#e89a90"/></radialGradient>
      <linearGradient id="pigFace" x1="15%" y1="10%" x2="80%" y2="100%"><stop stop-color="#ffd2c1"/><stop offset="1" stop-color="#efa498"/></linearGradient>
      <linearGradient id="pigSnout" x2="0" y2="1"><stop stop-color="#ffd6c7"/><stop offset="1" stop-color="#f1a79a"/></linearGradient>
    </defs>
    <g filter="url(#pigShadow)">
      <path d="M77 155c-21 3 -34 -7 -28 -17 7 -11 22 -2 16 7" fill="none" stroke="#d28f85" stroke-width="6" stroke-linecap="round"/>
      <path d="M123 196h20l-2 31q-1 6 -8 6h-7q-7 0 -7 -7zM210 189h18l-1 35q0 7 -7 7h-5q-7 0 -7 -7z" fill="#d88c83"/>
      <g transform="translate(151 67) rotate(-9)"><circle r="25" fill="#dda33b"/><circle r="21" fill="#ffdf84" stroke="#f4c65b" stroke-width="2"/><text text-anchor="middle" y="5" fill="#a77128" font-size="15" font-family="Arial" font-weight="700">AC</text></g>
      <ellipse cx="151" cy="153" rx="88" ry="64" fill="url(#pigBody)"/>
      <path d="M231 112q1 -21 16 -25 6 15 -1 34" fill="#dc978d"/>
      <circle cx="211" cy="145" r="44" fill="url(#pigFace)"/>
      <path d="M185 117q-10 -16 -7 -30 19 0 32 18" fill="#f5b7a8" stroke="#e6a297" stroke-width="1.5"/>
      <path d="M187 106q-5 -8 -5 -14 11 1 20 11" fill="#de9289"/>
      <path d="M100 192q12 5 25 5l-3 32q-1 8 -9 8h-9q-8 0 -8 -8zM189 193q12 3 26 -2l-1 37q0 8 -8 8h-10q-8 0 -8 -8z" fill="url(#pigFace)"/>
      <path d="M97 226q12 4 25 0v5q-1 7 -9 7h-9q-8 0 -8 -8zM189 225q12 4 25 0v5q0 7 -8 7h-10q-8 0 -8 -8z" fill="#cc827b"/>
      <path d="M109 231v6m93 -6v5" stroke="#ae6c67" stroke-width="2" stroke-linecap="round"/>
      <path d="M132 99q17 -6 35 -2" fill="none" stroke="#a8685e" stroke-width="5" stroke-linecap="round"/>
      <path d="M133 96q16 -5 33 -2" fill="none" stroke="#fff0df" stroke-width="2" stroke-linecap="round" opacity=".8"/>
      <ellipse cx="241" cy="155" rx="25" ry="20" fill="url(#pigSnout)" stroke="#df978b" stroke-width="1.5"/>
      <ellipse cx="233" cy="155" rx="3.5" ry="5" fill="#b8766f"/><ellipse cx="249" cy="155" rx="3.5" ry="5" fill="#b8766f"/>
      <circle cx="210" cy="132" r="4.5" fill="#62403a"/><circle cx="211" cy="130" r="1.5" fill="white"/>
      <ellipse cx="205" cy="157" rx="9" ry="6" fill="#e68d87" opacity=".5"/>
      <path d="M216 177q10 5 16 -2" fill="none" stroke="#bf8177" stroke-width="2" stroke-linecap="round"/>
      <path d="M83 139q9 -21 30 -25" fill="none" stroke="#fff0e6" stroke-width="7" stroke-linecap="round" opacity=".7"/>
      <ellipse cx="91" cy="155" rx="3" ry="5" fill="#fff3e9" opacity=".65"/>
    </g>
    <path d="M72 83l4 -7m181 -1l8 -3" stroke="#d8a17f" stroke-width="3" stroke-linecap="round"/>
    <circle cx="64" cy="213" r="4" fill="#a1b88b"/>
  </svg>`;
}

function pizzaEndpoint(path = "", student = true) {
  const url = new URL(`/api/v1/miniapp/pizza${path}`, location.origin);
  url.searchParams.set("tenant_slug", window.pizzaPreview?.tenant || apiContext.tenantSlug || state.currentTenant?.tenant_slug || "");
  if (student && ["student", "parent"].includes(state.role) && selectedStudent()?.id) {
    url.searchParams.set("student_id", selectedStudent().id);
  }
  return url.pathname + url.search;
}

async function pizzaRequest(path = "", body = null, method = "POST") {
  const options = {headers: {}};
  if (window.pizzaPreview?.token) options.headers["X-Miniapp-Token"] = window.pizzaPreview.token;
  if (body !== null) {
    options.method = method;
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  const response = await apiFetch(pizzaEndpoint(path, body === null), options);
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw Object.assign(new Error(typeof data.detail === "string" ? data.detail : "Не получилось выполнить действие. Попробуйте ещё раз"), {status: response.status});
  }
  return response.json();
}

async function pizzaLoad(force = false) {
  if (force === true) pizzaState.disabled = false;
  if ((!apiContext.maxUserId && !window.pizzaPreview) || pizzaState.loading || pizzaState.disabled) return;
  pizzaState.loading = true;
  const context = pizzaContextKey();
  try {
    const board = await pizzaRequest();
    if (context !== pizzaContextKey()) return;
    pizzaState.board = board;
    pizzaState.context = context;
    pizzaState.offset = Date.parse(board.server_time) - Date.now();
    pizzaState.error = "";
    if (board.balance !== null && selectedStudent()) {
      selectedStudent().balance = board.balance;
      renderStatus();
    }
    renderPizza();
    if (["student", "parent"].includes(state.role)) {
      renderOrders();
      renderLedger();
    }
  } catch (error) {
    if (error.status === 404) {
      pizzaState.disabled = true;
      pizzaState.board = null;
      renderPizza();
    }
    if (error.status !== 404) {
      pizzaState.error = error.message;
      renderPizza();
      if (force === true) throw error;
    }
  } finally {
    pizzaState.loading = false;
    if (context !== pizzaContextKey()) void pizzaLoad();
  }
}

function pizzaCountdown(deadline) {
  const seconds = Math.max(0, Math.floor((Date.parse(deadline) - Date.now() - pizzaState.offset) / 1000));
  const d = Math.floor(seconds / 86400), h = Math.floor(seconds % 86400 / 3600);
  const m = Math.floor(seconds % 3600 / 60), s = seconds % 60;
  return `${d ? `${d} д · ` : ""}${String(h).padStart(2,"0")}:${String(m).padStart(2,"0")}:${String(s).padStart(2,"0")}`;
}

function pizzaActions(c) {
  if (c.status === "open") {
    if (c.contributed) return `<div class="pizza-personal is-done"><i data-lucide="circle-check"></i><span>Ваш взнос — ${pizzaNumber(c.share)} AC<strong>Вы участвуете</strong></span></div>`;
    if (c.can_contribute) {
      const enough = pizzaState.board.balance >= c.share;
      return `<button class="pizza-primary" data-pizza-contribute="${c.id}" ${!enough ? "disabled" : ""}><i data-lucide="${pizzaOfferIcon(c)}"></i>${enough ? `Внести ${pizzaNumber(c.share)} AC` : `Не хватает ${pizzaNumber(c.share - pizzaState.board.balance)} AC`}<i data-lucide="arrow-up-right"></i></button>`;
    }
    if (state.role === "parent") return '<p class="pizza-personal">Внести астрокоины можно из кабинета ребёнка.</p>';
  }
  if (c.refunded) return `<div class="pizza-personal is-done"><i data-lucide="undo-2"></i><span>${pizzaNumber(c.share)} AC вернулись на баланс</span></div>`;
  const action = c.status === "funded" && c.can_pay ? ["paid", "Деньги переданы преподавателю"] :
    c.status === "paid" && c.is_teacher ? ["ordered", c.kind === "other" ? "Заказ оформлен" : "Пицца заказана"] :
    c.status === "ordered" && c.is_teacher ? ["delivered", c.kind === "other" ? "Заказ получен" : "Пицца приехала"] : null;
  return action ? `<button class="pizza-primary" data-pizza-action="${action[0]}" data-pizza-id="${c.id}"><i data-lucide="check"></i>${action[1]}</button>` : "";
}

function pizzaCard(c) {
  const percent = c.target ? c.collected / c.target * 100 : 0;
  const open = c.status === "open", ended = ["cancelled", "expired"].includes(c.status);
  const customer = ["student", "parent"].includes(state.role);
  const date = new Intl.DateTimeFormat("ru-RU", {timeZone:"Europe/Moscow", day:"numeric", month:"long", hour:"2-digit", minute:"2-digit"}).format(new Date(c.deadline));
  return `<article class="pizza-campaign is-${c.status}" data-pizza-card="${c.id}">
    <div class="pizza-card-top"><span class="pizza-badge"><i data-lucide="${ended ? "undo-2" : open ? "sparkles" : "circle-check"}"></i>${open ? "Групповой сбор" : pizzaStatus(c)}</span>
      ${open ? `<div class="pizza-clock" title="До ${pizzaEscape(date)} МСК"><i data-lucide="timer"></i><span data-pizza-timer="${pizzaEscape(c.deadline)}">${pizzaCountdown(c.deadline)}</span></div>` : `<span class="pizza-small">${c.joined} из ${c.members} участников</span>`}</div>
    <div class="pizza-card-body"><div class="pizza-copy"><p class="pizza-group">${pizzaEscape(c.group_name)}</p>
      <h2>${c.status === "cancelled" ? "Сбор отменён" : ended ? "В этот раз не собрались" : c.kind === "other" ? pizzaEscape(c.title) : customer && !open ? "На пиццу собрали!" : c.status === "delivered" ? "Пицца приехала!" : "На пиццу всей группой"}</h2>
      <div class="pizza-progress-caption"><strong>${pizzaNumber(c.collected)} <span>из ${pizzaNumber(c.target)} AC</span></strong><span>${c.joined} из ${c.members} внесли</span></div>
      <div class="pizza-segments" role="progressbar" aria-label="Собрано астрокоинов" aria-valuenow="${c.collected}" aria-valuemin="0" aria-valuemax="${c.target}">${Array.from({length: Math.min(c.members,30)},(_,i)=>`<span aria-hidden="true" class="${i < c.joined ? "is-filled" : ""}"></span>`).join("")}</div>
      ${pizzaActions(c)}
      <div class="pizza-card-foot"><span><i data-lucide="${ended ? "wallet" : "shield-check"}"></i>${ended ? "Внесённые астрокоины возвращены" : open ? "Не соберём к сроку — вернём взносы" : customer ? "Сумма собрана. Спасибо за участие!" : c.status === "funded" ? "Преподаватель и директор уведомлены" : pizzaStatus(c)}</span><button class="pizza-text-button" data-pizza-details="${c.id}">Подробнее<i data-lucide="chevron-right"></i></button></div>
    </div><div class="pizza-visual"><div class="pizza-illustration">${c.kind === "other" ? collectionPigIllustration() : pizzaIllustration()}<span class="pizza-percent"><i data-lucide="check"></i><span>${Math.round(percent)}% собрано</span></span></div></div></div>
    ${c.can_manage && !["cancelled","expired","delivered"].includes(c.status) ? `<div class="pizza-workflow">${["funded","paid","ordered","delivered"].map((status,i)=>`<span class="${["open","funded","paid","ordered","delivered"].indexOf(c.status) >= i+1 ? "is-complete" : ""}"><i data-lucide="${["circle-check","banknote",c.kind === "other" ? "shopping-bag" : "pizza","party-popper"][i]}"></i>${["Собрали","Деньги переданы","Заказали","Получили"][i]}</span>`).join("")}${["open","funded"].includes(c.status) ? `<button class="pizza-text-button" data-pizza-action="cancel" data-pizza-id="${c.id}">Отменить сбор</button>` : ""}</div>` : ""}
  </article>`;
}

function renderPizza() {
  const root = qs("#pizzaCollections");
  if (!root) return;
  if (pizzaState.board && pizzaState.context !== pizzaContextKey()) {
    pizzaState.board = null;
    pizzaState.error = "";
    void pizzaLoad();
  }
  const board = pizzaState.board;
  root.hidden = !board && !pizzaState.error;
  if (root.hidden) return;
  if (!board) {
    root.innerHTML = `<div class="pizza-load-error" role="status">${pizzaEscape(pizzaState.error)} <button class="secondary-action" data-pizza-retry>Повторить</button></div>`;
    return;
  }
  const staff = board.teacher || board.director;
  const live = board.campaigns.filter(c=>staff ? !c.finished : c.status === "open");
  const past = staff ? board.campaigns.filter(c=>c.finished) : [];
  root.hidden = !staff && !live.length;
  root.innerHTML = `${staff ? `<div class="pizza-section-head"><h2>Групповые сборы</h2><div class="pizza-staff-actions">${board.notices.length ? `<button class="secondary-action" data-pizza-notices><i data-lucide="bell"></i><span>${board.notices.length}</span></button>` : ""}${board.director ? '<button class="secondary-action" data-pizza-offers><i data-lucide="sliders-horizontal"></i>Варианты сбора</button>' : ""}${board.teacher ? '<button class="pizza-primary" data-pizza-launch><i data-lucide="plus"></i>Открыть сбор</button>' : ""}</div></div>` : ""}
    ${pizzaState.error ? `<p class="pizza-inline-error" role="alert">${pizzaEscape(pizzaState.error)}</p>` : ""}
    ${live.map(pizzaCard).join("")}
    ${!live.length && staff ? `<div class="pizza-empty"><i data-lucide="pizza"></i><div><strong>Открытых сборов пока нет</strong><p>${board.teacher ? "Выберите вариант сбора и откройте сбор для своей группы." : "Добавьте вариант сбора для преподавателей."}</p></div></div>` : ""}
    ${past.length ? `<details class="pizza-past" ${!live.length ? "open" : ""}><summary>Завершённые сборы <span>${past.length}</span></summary>${past.map(pizzaCard).join("")}</details>` : ""}`;
  refreshIcons();
}

function pizzaPersonalBoard() {
  return ["student", "parent"].includes(state.role) &&
    pizzaState.context === pizzaContextKey() ? pizzaState.board : null;
}

function pizzaMergedLedger(rows) {
  const board = pizzaPersonalBoard();
  if (!board) return rows;
  const items = (board.ledger || []).map(entry => [
    formatDate(entry.created_at),
    `${entry.reason}${entry.comment ? ` · ${entry.comment}` : ""}`,
    `${entry.direction === "debit" ? "-" : "+"}${pizzaNumber(entry.amount)} AC`,
    entry.student_id, "purchase", entry.id, entry.created_at,
  ]);
  const ids = new Set(items.map(row=>row[5]));
  return [...rows.filter(row=>!ids.has(row[5])), ...items]
    .sort((a,b)=>(Date.parse(b[6] || b[0]) || 0)-(Date.parse(a[6] || a[0]) || 0));
}

function renderPizzaOrderHistory() {
  const root = qs("#pizzaOrdersHistory");
  if (!root) return 0;
  const board = pizzaPersonalBoard();
  const query = String(state.orderSearch || "").toLocaleLowerCase("ru-RU").replaceAll("ё","е").trim();
  const history = (board?.history || []).filter(c=>
    `${c.title} ${c.group_name}`.toLocaleLowerCase("ru-RU").replaceAll("ё","е").includes(query));
  root.hidden = !history.length;
  root.innerHTML = history.length ? `<h3>Групповые сборы</h3>${history.map(c=>{
    const refunded = c.refunded;
    const status = refunded ? "Взнос возвращён" : c.status === "open" ? "Взнос внесён" : "Сумма собрана";
    const date = new Intl.DateTimeFormat("ru-RU", {timeZone:"Europe/Moscow", dateStyle:"medium", timeStyle:"short"}).format(new Date(c.refunded_at || c.contributed_at));
    return `<article class="pizza-history-card" data-pizza-history="${c.id}"><span class="pizza-history-icon"><i data-lucide="${refunded ? "undo-2" : pizzaOfferIcon(c)}"></i></span><div><strong>${pizzaEscape(c.title)}</strong><span>${pizzaEscape(c.group_name)}</span><small>${pizzaEscape(date)} МСК</small></div><div class="pizza-history-outcome"><span class="${refunded ? "is-refunded" : ""}">${status}</span><strong>${pizzaNumber(c.share)} AC</strong></div><button class="pizza-text-button" data-pizza-details="${c.id}">Подробнее<i data-lucide="chevron-right"></i></button></article>`;
  }).join("")}` : "";
  refreshIcons();
  return history.length;
}

function pizzaOpenDialog(title, body, footer = "") {
  pizzaCloseDialog();
  pizzaState.focus = document.activeElement;
  const dialog = document.createElement("dialog");
  dialog.id = "pizzaDialog"; dialog.className = "pizza-dialog";
  dialog.setAttribute("aria-labelledby", "pizzaDialogTitle");
  dialog.innerHTML = `<div class="pizza-dialog-head"><h2 id="pizzaDialogTitle">${pizzaEscape(title)}</h2><button class="pizza-close" type="button" data-pizza-close aria-label="Закрыть"><i data-lucide="x"></i></button></div><div class="pizza-dialog-body">${body}</div>${footer ? `<div class="pizza-dialog-footer">${footer}</div>` : ""}`;
  dialog.addEventListener("cancel", event=>{ if (pizzaState.busy) event.preventDefault(); });
  dialog.addEventListener("click", event=>{
    const box=dialog.getBoundingClientRect();
    if (!pizzaState.busy && event.target===dialog &&
        (event.clientX<box.left || event.clientX>box.right || event.clientY<box.top || event.clientY>box.bottom)) pizzaCloseDialog();
  });
  dialog.addEventListener("close", ()=>{ dialog.remove(); pizzaState.focus?.focus(); });
  document.body.append(dialog); dialog.showModal(); refreshIcons();
}

function pizzaCloseDialog() {
  const dialog = qs("#pizzaDialog");
  if (dialog) { dialog.close(); dialog.remove(); }
}

function pizzaLaunchDialog() {
  const board = pizzaState.board;
  const date = new Intl.DateTimeFormat("sv-SE", {timeZone:"Europe/Moscow", year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit"}).format(new Date(Date.now()+7*86400000)).replace(" ","T");
  const groups = board.groups.filter(g=>g.count >= 2 && !board.campaigns.some(c=>c.group_name===g.name && ["open","funded","paid","ordered"].includes(c.status)));
  if (!board.offers.length || !groups.length) {
    pizzaOpenDialog("Открыть сбор", `<p>${!board.offers.length ? "Директор ещё не добавил варианты сбора." : "Нет свободной группы с двумя или более учениками. Для группы может быть открыт только один сбор."}</p>`);
    return;
  }
  pizzaOpenDialog("Открыть сбор", `<form id="pizzaLaunchForm">
    <label>Группа<select name="group_name" required>${groups.map(g=>`<option value="${pizzaEscape(g.name)}">${pizzaEscape(g.name)} · ${g.count} учеников</option>`).join("")}</select></label>
    <fieldset class="pizza-offer-options"><legend>Вариант сбора</legend>${board.offers.map((o,i)=>`<label><input type="radio" name="offer_id" value="${o.id}" ${!i ? "checked" : ""} required><span><strong>${pizzaEscape(o.title)}</strong><small>${pizzaEscape(o.description)}</small></span><b>${pizzaNumber(o.share)} AC<small>с ученика</small></b></label>`).join("")}</fieldset>
    <label>Собрать до · МСК<input type="datetime-local" name="deadline" value="${date}" required></label>
    <div id="pizzaLaunchSummary" class="pizza-calculation"></div><p class="pizza-form-note">Если к сроку не соберётся вся сумма, астрокоины вернутся участникам.</p>
    <p class="pizza-form-error" role="alert" hidden></p><button class="pizza-primary" type="submit">Открыть сбор<i data-lucide="arrow-right"></i></button></form>`);
  pizzaUpdateLaunchSummary();
}

function pizzaUpdateLaunchSummary() {
  const form = qs("#pizzaLaunchForm"); if (!form) return;
  const values = new FormData(form), b=pizzaState.board;
  const group = b.groups.find(g=>g.name===values.get("group_name"));
  const offer = b.offers.find(o=>o.id===values.get("offer_id"));
  if (group && offer) qs("#pizzaLaunchSummary").innerHTML = `<span>${group.count} учеников × ${pizzaNumber(offer.share)} AC</span><strong>Цель ${pizzaNumber(group.count*offer.share)} AC</strong>`;
}

function pizzaOfferForm(offer = null) {
  const kind = offer?.kind || "pizza";
  return `<form id="pizzaOfferForm" data-offer-id="${offer?.id || ""}">
    ${offer ? `<input type="hidden" name="revision" value="${offer.revision}">` : "<h3>Новый вариант</h3>"}
    <fieldset class="collection-kind-options"><legend>Тип сбора</legend>
      <label><input type="radio" name="kind" value="pizza" ${kind === "pizza" ? "checked" : ""}><i data-lucide="pizza"></i><span>Пицца</span></label>
      <label><input type="radio" name="kind" value="other" ${kind === "other" ? "checked" : ""}><i data-lucide="piggy-bank"></i><span>Другое</span></label>
    </fieldset>
    <label>Название<input name="title" maxlength="120" minlength="2" value="${pizzaEscape(offer?.title || "")}" placeholder="Например, общий подарок" required></label>
    <label>Описание<input name="description" maxlength="500" value="${pizzaEscape(offer?.description || "")}" placeholder="Что планируем для группы"></label>
    <label>Взнос с ученика · AC<input name="share" type="number" min="1" max="100000" step="1" value="${offer?.share || 200}" required></label>
    <p class="pizza-form-error" role="alert" hidden></p><div class="collection-form-actions">${offer ? '<button class="secondary-action" type="button" data-pizza-offers>К списку</button>' : ""}<button class="pizza-primary" type="submit">${offer ? "Сохранить изменения" : "Добавить вариант"}</button></div></form>`;
}

function pizzaOffersDialog() {
  const offers = pizzaState.board.offers;
  pizzaOpenDialog("Варианты сбора", `<div class="pizza-offer-list">${offers.map(o=>`<article class="collection-offer-row" data-offer-row="${o.id}"><i data-lucide="${pizzaOfferIcon(o)}"></i><div><strong>${pizzaEscape(o.title)}</strong><span>${pizzaEscape(o.description)}</span></div><b>${pizzaNumber(o.share)} AC<small>с ученика</small></b><div class="collection-offer-actions"><button class="secondary-action" type="button" data-pizza-edit-offer="${o.id}"><i data-lucide="pencil"></i>Редактировать</button><button class="secondary-action collection-delete" type="button" data-pizza-delete-offer="${o.id}"><i data-lucide="trash-2"></i>Удалить</button></div></article>`).join("") || '<p class="pizza-form-note">Пока нет вариантов</p>'}</div>${pizzaOfferForm()}`);
}

function pizzaConfirmContribution(c) {
  pizzaOpenDialog("Участвуем в сборе?", `<div class="pizza-confirm-hero"><i data-lucide="${pizzaOfferIcon(c)}"></i><strong>${pizzaEscape(c.title)}</strong><span>${pizzaEscape(selectedStudent()?.name || "")}</span></div><div class="pizza-confirm-amount"><span>Ваш взнос</span><strong>${pizzaNumber(c.share)} AC</strong></div><div class="pizza-calculation"><span>Баланс после взноса</span><strong>${pizzaNumber(pizzaState.board.balance-c.share)} AC</strong></div><p class="pizza-form-note">Если сбор отменят или не соберётся вся сумма, ${pizzaNumber(c.share)} AC вернутся на баланс.</p><p class="pizza-form-error" role="alert" hidden></p>`, `<button class="secondary-action" data-pizza-close>Пока нет</button><button class="pizza-primary" data-pizza-confirm="${c.id}">Внести ${pizzaNumber(c.share)} AC</button>`);
}

function pizzaShowDetails(c) {
  const date = new Intl.DateTimeFormat("ru-RU", {timeZone:"Europe/Moscow",dateStyle:"long",timeStyle:"short"}).format(new Date(c.deadline));
  pizzaOpenDialog(c.title, `<p class="pizza-detail-status">${pizzaStatus(c)}</p><dl class="pizza-facts"><div><dt>Группа</dt><dd>${pizzaEscape(c.group_name)}</dd></div><div><dt>Взнос каждого</dt><dd>${pizzaNumber(c.share)} AC</dd></div><div><dt>Цель</dt><dd>${pizzaNumber(c.target)} AC · ${c.members} учеников</dd></div><div><dt>Срок</dt><dd>${pizzaEscape(date)} МСК</dd></div></dl><div class="pizza-rules"><p><i data-lucide="equal"></i>Один одинаковый взнос с ученика.</p><p><i data-lucide="undo-2"></i>Если не соберём всю сумму, взносы вернутся автоматически.</p><p><i data-lucide="users"></i>Для всей группы.</p></div>`);
}

async function pizzaMutate(path, payload, success, method = "POST") {
  if (pizzaState.busy) return;
  pizzaState.busy = true;
  const dialog=qs("#pizzaDialog");
  const controls = [...(dialog?.querySelectorAll("button,input,select") || [])];
  controls.forEach(e=>e.disabled=true);
  try {
    await pizzaRequest(path, payload, method);
    pizzaCloseDialog();
    await pizzaLoad();
    showNotice(success, "success");
  } catch (error) {
    if (error.status === 409 || error.status === 404) await pizzaLoad();
    const output = dialog?.querySelector(".pizza-form-error");
    if (output) {output.textContent=error.message; output.hidden=false;}
    else showNotice(error.message,"danger");
  } finally {
    pizzaState.busy=false;
    controls.forEach(e=>e.disabled=false);
  }
}

document.addEventListener("click", event=>{
  const target = event.target.closest("button"); if (!target) return;
  if (target.hasAttribute("data-pizza-close") && !pizzaState.busy) pizzaCloseDialog();
  if (target.hasAttribute("data-pizza-retry")) void pizzaLoad();
  if (target.hasAttribute("data-pizza-launch")) pizzaLaunchDialog();
  if (target.hasAttribute("data-pizza-offers")) pizzaOffersDialog();
  const offer = pizzaState.board?.offers.find(o=>o.id === (target.dataset.pizzaEditOffer || target.dataset.pizzaDeleteOffer || target.dataset.pizzaConfirmDeleteOffer));
  if (target.dataset.pizzaEditOffer && offer) pizzaOpenDialog("Редактировать вариант", pizzaOfferForm(offer));
  if (target.dataset.pizzaDeleteOffer && offer) pizzaOpenDialog("Удалить вариант?", `<p>«${pizzaEscape(offer.title)}» исчезнет из списка для новых сборов. Уже открытые сборы и их история сохранятся.</p><p class="pizza-form-error" role="alert" hidden></p>`, `<button class="secondary-action" type="button" data-pizza-offers>Назад</button><button class="pizza-primary is-danger" type="button" data-pizza-confirm-delete-offer="${offer.id}">Удалить вариант</button>`);
  if (target.dataset.pizzaConfirmDeleteOffer && offer) void pizzaMutate(`/offers/${offer.id}`, {revision:offer.revision}, "Вариант удалён", "DELETE");
  if (target.hasAttribute("data-pizza-notices")) pizzaOpenDialog("Уведомления по сборам", `<div class="pizza-notices">${pizzaState.board.notices.map(n=>`<article><i data-lucide="${n.event==="refund" ? "undo-2" : "bell"}"></i><p>${pizzaEscape(n.message)}</p></article>`).join("")}</div><p class="pizza-form-note">В локальной демке сообщения в MAX не отправляются.</p>`);
  const c=[...(pizzaState.board?.campaigns || []),...(pizzaState.board?.history || [])].find(c=>c.id===(target.dataset.pizzaContribute || target.dataset.pizzaDetails || target.dataset.pizzaId));
  if (target.dataset.pizzaContribute && c) pizzaConfirmContribution(c);
  if (target.dataset.pizzaDetails && c) pizzaShowDetails(c);
  if (target.dataset.pizzaConfirm) void pizzaMutate(`/campaigns/${target.dataset.pizzaConfirm}/contribute`, {student_id: selectedStudent().id}, "Взнос внесён. Вы участвуете!");
  if (target.dataset.pizzaAction && c) {
    const cancel=target.dataset.pizzaAction==="cancel";
    const text = cancel ? `Каждый участник получит обратно свои ${pizzaNumber(c.share)} AC. Отмену нельзя откатить.` :
      target.dataset.pizzaAction==="paid" ? "Подтвердите, что вы уже передали деньги преподавателю. После этого автоматическая отмена сбора будет недоступна." :
      target.dataset.pizzaAction==="ordered" ? `Подтвердите, что вы оформили заказ для группы «${pizzaEscape(c.group_name)}».` :
      `Подтвердите, что группа «${pizzaEscape(c.group_name)}» получила заказ.`;
    pizzaOpenDialog(cancel ? "Отменить сбор?" : pizzaStatus({...c,status:target.dataset.pizzaAction}), `<p>${text}</p><p class="pizza-form-error" role="alert" hidden></p>`, `<button class="secondary-action" data-pizza-close>Назад</button><button class="pizza-primary ${cancel ? "is-danger" : ""}" data-pizza-confirm-action="${target.dataset.pizzaAction}" data-pizza-campaign="${c.id}">${cancel ? "Отменить и вернуть взносы" : "Подтвердить"}</button>`);
  }
  if (target.dataset.pizzaConfirmAction) void pizzaMutate(`/campaigns/${target.dataset.pizzaCampaign}/action`, {action:target.dataset.pizzaConfirmAction}, "Состояние сбора обновлено");
});

document.addEventListener("submit", event=>{
  const form=event.target;
  if (!["pizzaOfferForm","pizzaLaunchForm"].includes(form.id)) return;
  event.preventDefault();
  const data=Object.fromEntries(new FormData(form));
  if (form.id==="pizzaOfferForm") {
    data.share=Number(data.share);
    if (form.dataset.offerId) {
      data.revision=Number(data.revision);
      void pizzaMutate(`/offers/${form.dataset.offerId}`, data, "Вариант обновлён", "PATCH");
    } else void pizzaMutate("/offers", data, "Вариант добавлен");
  } else {
    data.deadline=new Date(data.deadline+":00+03:00").toISOString();
    void pizzaMutate("/campaigns", data, "Сбор открыт для группы");
  }
});
document.addEventListener("change", event=>{if(event.target.closest("#pizzaLaunchForm")) pizzaUpdateLaunchSummary();});
setInterval(()=>{
  qsa("[data-pizza-timer]").forEach(el=>el.textContent=pizzaCountdown(el.dataset.pizzaTimer));
  if (pizzaState.board?.campaigns.some(c=>c.status==="open" && Date.parse(c.deadline)<=Date.now()+pizzaState.offset) &&
      !pizzaState.busy && !qs("#pizzaDialog")) void pizzaLoad();
},1000);
setInterval(()=>{if(["store","orders","wallet"].includes(state.view) && !qs("#pizzaDialog") && !pizzaState.busy) void pizzaLoad();},15000);
