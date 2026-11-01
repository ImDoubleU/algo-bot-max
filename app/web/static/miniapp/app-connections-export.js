const connectionExportState = {
  rows: [], tenant: "", tenantName: "", selected: {}, searches: {}, includeInactive: false,
  loading: false, exporting: false, error: "", sequence: 0, controller: null, returnFocus: null,
};
const connectionExportDimensions = [
  ["teachers", "teacher_name", "Преподаватели"],
  ["venues", "venue_name", "Площадки"],
  ["groups", "group_name", "Группы"],
];

function connectionExportBaseRows() {
  return connectionExportState.rows.filter((row) => connectionExportState.includeInactive
    || row.status === "active");
}

function connectionExportOptions(key, field) {
  const counts = new Map();
  connectionExportBaseRows().forEach((row) => counts.set(row[field], (counts.get(row[field]) || 0) + 1));
  return [...counts.entries()].sort(([a], [b]) => a.localeCompare(b, "ru"));
}

function connectionExportSelectedRows() {
  return connectionExportBaseRows().filter((row) => connectionExportDimensions.every(
    ([key, field]) => connectionExportState.selected[key]?.has(row[field]),
  ));
}

function ensureConnectionExportDialog() {
  let dialog = qs("#connectionExportDialog");
  if (dialog) return dialog;
  dialog = document.createElement("div");
  dialog.id = "connectionExportDialog";
  dialog.className = "dialog-backdrop";
  dialog.hidden = true;
  dialog.innerHTML = `<section class="checkout-dialog connection-export-dialog" role="dialog" aria-modal="true" aria-labelledby="connectionExportTitle">
    <div class="dialog-head"><div><p class="eyebrow">Связи доступа</p><h2 id="connectionExportTitle">Экспорт в Excel</h2><p class="connection-export-city"></p></div><button type="button" class="icon-button" data-close-connection-export title="Закрыть" aria-label="Закрыть"><i data-lucide="x"></i></button></div>
    <div id="connectionExportContent" class="connection-export-content"></div>
    <div class="connection-export-footer"><span id="connectionExportCount" role="status"></span><button type="button" class="primary-action" data-download-connection-export><i data-lucide="download"></i><span>Скачать Excel</span></button></div>
  </section>`;
  document.body.append(dialog);
  dialog.addEventListener("click", (event) => { if (event.target === dialog) closeConnectionExportDialog(); });
  return dialog;
}

function closeConnectionExportDialog() {
  const dialog = qs("#connectionExportDialog");
  if (!dialog || dialog.hidden) return;
  connectionExportState.controller?.abort();
  connectionExportState.sequence += 1;
  dialog.hidden = true;
  syncDialogBodyClass();
  connectionExportState.returnFocus?.focus();
}

async function openConnectionExportDialog() {
  if (!["superadmin", "admin", "partner_director"].includes(primaryStaffRole())) return;
  const dialog = ensureConnectionExportDialog();
  connectionExportState.controller?.abort();
  const controller = new AbortController();
  const sequence = ++connectionExportState.sequence;
  Object.assign(connectionExportState, {rows: [], tenant: apiContext.tenantSlug, tenantName: "",
    selected: {}, searches: {}, includeInactive: false, loading: true, exporting: false, error: "",
    controller, returnFocus: document.activeElement});
  dialog.hidden = false;
  syncDialogBodyClass();
  renderConnectionExport();
  dialog.querySelector("[data-close-connection-export]").focus();
  try {
    let report;
    if (apiContext.demoMode) {
      report = {tenant_name: "Демонстрационные данные", students: students.map((student) => ({
        student_id: student.id, lms_student_id: student.lmsId || "", display_name: student.name,
        group_name: student.group || "Без группы", teacher_name: student.teacher || "Преподаватель не указан",
        venue_name: student.venue || "Площадка не указана", status: student.status || "active",
        student_connected: accessLinks.some((link) => link.studentId === student.id && link.role === "student" && link.status === "active"),
        parent_connected: accessLinks.some((link) => link.studentId === student.id && link.role === "parent" && link.status === "active"),
      }))};
    } else {
      const url = new URL("/api/v1/miniapp/access-links/export-options", location.origin);
      url.searchParams.set("max_user_id", apiContext.maxUserId);
      url.searchParams.set("tenant_slug", connectionExportState.tenant || "");
      const response = await apiFetch(url.toString(), {signal: controller.signal});
      if (!response.ok) throw new Error(await parseApiError(response));
      report = await response.json();
    }
    if (sequence !== connectionExportState.sequence || apiContext.tenantSlug !== connectionExportState.tenant) return;
    connectionExportState.rows = report.students;
    connectionExportState.tenantName = report.tenant_name;
    connectionExportDimensions.forEach(([key, field]) => {
      connectionExportState.selected[key] = new Set(connectionExportOptions(key, field).map(([value]) => value));
    });
  } catch (error) {
    if (error.name !== "AbortError" && sequence === connectionExportState.sequence) {
      connectionExportState.error = error.message || "Не удалось загрузить данные для экспорта";
    }
  } finally {
    if (sequence === connectionExportState.sequence) {
      connectionExportState.loading = false;
      renderConnectionExport();
    }
  }
}

function renderConnectionExportOptions(key) {
  const dimension = connectionExportDimensions.find(([value]) => value === key);
  const list = qs(`[data-connection-export-list="${key}"]`);
  if (!dimension || !list) return;
  const query = (connectionExportState.searches[key] || "").trim().toLocaleLowerCase("ru");
  const entries = connectionExportOptions(...dimension).filter(([value]) => !query || value.toLocaleLowerCase("ru").includes(query));
  list.innerHTML = entries.map(([value, count]) => `<label class="connection-export-option"><input type="checkbox" data-connection-export-key="${key}" value="${escapeHtml(value)}" ${connectionExportState.selected[key]?.has(value) ? "checked" : ""} ${connectionExportState.exporting ? "disabled" : ""}/><span>${escapeHtml(value)}</span><small>${count}</small></label>`).join("")
    || '<div class="connection-export-empty">Ничего не найдено</div>';
  const counter = qs(`[data-connection-export-counter="${key}"]`);
  if (counter) counter.textContent = `${connectionExportState.selected[key]?.size || 0} / ${connectionExportOptions(...dimension).length}`;
}

function renderConnectionExportPreview() {
  const rows = connectionExportSelectedRows();
  const preview = qs("#connectionExportPreview");
  const count = qs("#connectionExportCount");
  const download = qs("[data-download-connection-export]");
  if (download) {
    download.disabled = connectionExportState.loading || connectionExportState.exporting || !rows.length;
    download.querySelector("span").textContent = connectionExportState.exporting ? "Подготовка..." : "Скачать Excel";
  }
  if (count) count.textContent = connectionExportState.loading ? "Загружаем данные..." : `Учеников в файле: ${rows.length}`;
  if (!preview) return;
  const child = rows.filter((row) => row.student_connected).length;
  const parent = rows.filter((row) => row.parent_connected).length;
  const groups = new Map();
  rows.forEach((row) => {
    const key = JSON.stringify([row.group_name, row.venue_name, row.teacher_name]);
    if (!groups.has(key)) groups.set(key, {row, total: 0, children: 0, parents: 0});
    const group = groups.get(key);
    group.total += 1; group.children += Number(row.student_connected); group.parents += Number(row.parent_connected);
  });
  preview.innerHTML = `<div class="connection-export-totals"><div><span>Учеников</span><strong>${rows.length}</strong></div><div><span>Дети подключены</span><strong>${child}<small> / ${rows.length}</small></strong></div><div><span>Родители подключены</span><strong>${parent}<small> / ${rows.length}</small></strong></div></div>
    ${rows.length ? `<div class="connection-export-table-wrap"><table><thead><tr><th>Группа</th><th>Учеников</th><th>Дети: есть / нет</th><th>Родители: есть / нет</th></tr></thead><tbody>${[...groups.values()].sort((a, b) => a.row.group_name.localeCompare(b.row.group_name, "ru")).map((group) => `<tr><th>${escapeHtml(group.row.group_name)}<small>${escapeHtml(group.row.venue_name)} · ${escapeHtml(group.row.teacher_name)}</small></th><td>${group.total}</td><td>${group.children} / ${group.total - group.children}</td><td>${group.parents} / ${group.total - group.parents}</td></tr>`).join("")}</tbody></table></div>` : '<div class="connection-export-empty">В выбранных фильтрах нет учеников</div>'}`;
}

function renderConnectionExport() {
  const dialog = qs("#connectionExportDialog");
  if (!dialog || dialog.hidden) return;
  dialog.querySelector(".connection-export-city").textContent = connectionExportState.tenantName;
  const content = qs("#connectionExportContent");
  if (connectionExportState.loading) content.innerHTML = '<div class="loading-state" role="status">Загружаем учеников...</div>';
  else if (connectionExportState.error) content.innerHTML = `<div class="connection-export-error" role="alert">${escapeHtml(connectionExportState.error)}<button type="button" class="secondary-action" data-retry-connection-export><i data-lucide="refresh-cw"></i>Повторить</button></div>`;
  else {
    content.innerHTML = `<label class="connection-export-inactive"><input type="checkbox" data-connection-export-inactive ${connectionExportState.includeInactive ? "checked" : ""} ${connectionExportState.exporting ? "disabled" : ""}/>Включить выбывших и архивных учеников</label>
      <div class="connection-export-filters">${connectionExportDimensions.map(([key, field, label]) => `<section class="connection-export-filter" aria-label="${label}"><div class="connection-export-filter-heading"><h3>${label}</h3><small data-connection-export-counter="${key}"></small></div><input type="search" data-connection-export-search="${key}" value="${escapeHtml(connectionExportState.searches[key] || "")}" aria-label="Поиск: ${label.toLocaleLowerCase("ru")}" placeholder="Поиск" ${connectionExportState.exporting ? "disabled" : ""}/><div class="connection-export-filter-actions"><button type="button" data-connection-export-select="${key}" data-select-mode="all" ${connectionExportState.exporting ? "disabled" : ""}>Выбрать все</button><button type="button" data-connection-export-select="${key}" data-select-mode="none" ${connectionExportState.exporting ? "disabled" : ""}>Снять выбор</button></div><div class="connection-export-options" data-connection-export-list="${key}"></div></section>`).join("")}</div><div id="connectionExportPreview"></div>`;
    connectionExportDimensions.forEach(([key]) => renderConnectionExportOptions(key));
  }
  renderConnectionExportPreview();
  refreshIcons();
}

async function downloadConnectionExport() {
  if (connectionExportState.exporting || !connectionExportSelectedRows().length) return;
  if (apiContext.tenantSlug !== connectionExportState.tenant) {
    showNotice("Город изменился. Откройте экспорт заново", "danger"); return;
  }
  connectionExportState.exporting = true;
  const sequence = connectionExportState.sequence;
  renderConnectionExport();
  try {
    const payload = {max_user_id: Number(apiContext.maxUserId) || 53364725,
      tenant_slug: connectionExportState.tenant || undefined,
      include_inactive: connectionExportState.includeInactive};
    connectionExportDimensions.forEach(([key]) => { payload[key] = [...connectionExportState.selected[key]]; });
    const response = await apiFetch("/api/v1/miniapp/access-links/export", {
      method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload),
      signal: connectionExportState.controller?.signal,
    });
    if (!response.ok) throw new Error(await parseApiError(response));
    const blob = await response.blob();
    if (sequence !== connectionExportState.sequence || apiContext.tenantSlug !== connectionExportState.tenant) return;
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url; anchor.download = "algo-max-connections.xlsx";
    document.body.append(anchor); anchor.click(); anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 60000);
  } catch (error) {
    if (error.name !== "AbortError") showNotice(error.message || "Не удалось скачать Excel", "danger");
  } finally {
    if (sequence === connectionExportState.sequence) {
      connectionExportState.exporting = false; renderConnectionExport();
    }
  }
}

document.addEventListener("click", (event) => {
  const target = event.target.closest("button");
  if (!target) return;
  if (target.hasAttribute("data-open-connection-export") || target.hasAttribute("data-retry-connection-export")) void openConnectionExportDialog();
  if (target.hasAttribute("data-close-connection-export")) closeConnectionExportDialog();
  if (target.hasAttribute("data-download-connection-export")) void downloadConnectionExport();
  if (target.dataset.connectionExportSelect) {
    const key = target.dataset.connectionExportSelect;
    qsa(`[data-connection-export-list="${key}"] input`).forEach((input) => {
      if (target.dataset.selectMode === "all") connectionExportState.selected[key].add(input.value);
      else connectionExportState.selected[key].delete(input.value);
    });
    renderConnectionExportOptions(key); renderConnectionExportPreview();
  }
});
document.addEventListener("input", (event) => {
  const key = event.target.dataset.connectionExportSearch;
  if (!key) return;
  connectionExportState.searches[key] = event.target.value;
  renderConnectionExportOptions(key);
});
document.addEventListener("change", (event) => {
  const key = event.target.dataset.connectionExportKey;
  if (key) {
    if (event.target.checked) connectionExportState.selected[key].add(event.target.value);
    else connectionExportState.selected[key].delete(event.target.value);
    renderConnectionExportOptions(key); renderConnectionExportPreview();
  }
  if (event.target.hasAttribute("data-connection-export-inactive")) {
    const allSelected = Object.fromEntries(connectionExportDimensions.map(([key, field]) => [key,
      connectionExportOptions(key, field).every(([value]) => connectionExportState.selected[key].has(value))]));
    connectionExportState.includeInactive = event.target.checked;
    connectionExportDimensions.forEach(([key, field]) => {
      const options = connectionExportOptions(key, field).map(([value]) => value);
      connectionExportState.selected[key] = new Set(options.filter((value) => allSelected[key] || connectionExportState.selected[key].has(value)));
    });
    renderConnectionExport();
  }
});
document.addEventListener("keydown", (event) => {
  const dialog = qs("#connectionExportDialog");
  if (!dialog || dialog.hidden) return;
  if (event.key === "Escape") {
    event.preventDefault(); event.stopImmediatePropagation(); closeConnectionExportDialog();
  }
  if (event.key === "Tab") {
    const controls = [...dialog.querySelectorAll("button:not(:disabled), input:not(:disabled)")].filter((element) => element.getClientRects().length);
    const first = controls[0], last = controls[controls.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
    if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
  }
});
