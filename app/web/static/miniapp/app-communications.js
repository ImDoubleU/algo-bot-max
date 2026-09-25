function renderTeacherInvitations() {
  const panel = qs("#teacherQrPanel");
  const list = qs("#teacherQrList");
  const groupSelect = qs("#teacherQrGroupFilter");
  const tabs = qs("#dashboardModeTabs");
  const overview = qs("#dashboardOverviewContent");
  if (!panel || !list || !groupSelect || !tabs || !overview) return;

  const available = hasStudentQrCapabilities();
  if (!available) state.dashboardMode = "overview";
  const qrSelected = available && state.dashboardMode === "qr";
  tabs.hidden = !available;
  overview.hidden = qrSelected;
  panel.hidden = !qrSelected;
  qsa("[data-dashboard-mode]").forEach((button) => {
    const selected = button.dataset.dashboardMode === state.dashboardMode;
    button.classList.toggle("is-active", selected);
    button.setAttribute("aria-selected", String(selected));
    button.tabIndex = selected ? 0 : -1;
  });
  if (!qrSelected) return;

  const qrStudents = studentsForStudentQrCapabilities();
  const groups = [...new Set(qrStudents.map(studentGroupName))].sort((a, b) =>
    a.localeCompare(b, "ru"),
  );
  if (state.teacherInvitationGroup !== "all" && !groups.includes(state.teacherInvitationGroup)) {
    state.teacherInvitationGroup = "all";
  }
  groupSelect.innerHTML = `
    <option value="all">Все группы</option>
    ${groups.map((group) => `<option value="${escapeHtml(group)}">${escapeHtml(group)}</option>`).join("")}
  `;
  groupSelect.value = state.teacherInvitationGroup;

  if (state.teacherInvitationsLoading) {
    list.innerHTML = '<div class="empty-state compact-empty">Загружаем QR-коды...</div>';
    return;
  }
  if (!state.teacherInvitationsLoaded) {
    list.innerHTML = `
      <button class="secondary-action teacher-qr-load" type="button" data-load-teacher-qr>
        <i data-lucide="qr-code"></i><span>Показать QR-коды</span>
      </button>
    `;
    refreshIcons();
    return;
  }

  const visibleStudents = qrStudents.filter(
    (student) => state.teacherInvitationGroup === "all" || studentGroupName(student) === state.teacherInvitationGroup,
  );
  list.innerHTML = visibleStudents.length
    ? visibleStudents.map((student) => {
        const invitation = state.teacherInvitations.get(student.id);
        const data = invitation?.data;
        if (data?.available && data.qr_data_url) {
          const parentConnected = data.parent_connected !== false;
          return `
            <article class="teacher-qr-card ${parentConnected ? "is-connected" : "is-awaiting-parent"}">
              <button type="button" class="teacher-qr-preview" data-open-student-qr="${escapeHtml(student.id)}" aria-label="Показать QR-код ${escapeHtml(student.name)}">
                <img src="${escapeHtml(data.qr_data_url)}" alt="QR-код: ${escapeHtml(student.name)}" />
                ${data.demo ? '<small class="safe-qr-label">Пример, не сканировать</small>' : ""}
              </button>
              <span class="teacher-qr-copy">
                <strong>${escapeHtml(student.name)}</strong>
                <small>${escapeHtml(student.group)}</small>
                <span class="link-status ${parentConnected ? "is-active" : "is-pending"}">
                  <i data-lucide="${parentConnected ? "link" : "mail"}"></i>
                  ${parentConnected ? "Родитель подключен" : "Ожидается вход родителя"}
                </span>
                ${parentConnected || !data.message ? "" : `<span class="teacher-qr-note">${escapeHtml(data.message)}</span>`}
              </span>
              <button type="button" class="secondary-action" data-open-student-qr="${escapeHtml(student.id)}">Показать</button>
            </article>
          `;
        }
        return `
          <article class="teacher-qr-card is-unavailable">
            <span class="teacher-qr-placeholder"><i data-lucide="qr-code"></i></span>
            <span class="teacher-qr-copy">
              <strong>${escapeHtml(student.name)}</strong>
              <small>${escapeHtml(student.group)}</small>
              <span>${escapeHtml(data?.message || invitation?.error || "QR-код недоступен")}</span>
            </span>
          </article>
        `;
      }).join("")
    : '<div class="empty-state compact-empty">В этой группе учеников нет</div>';
  refreshIcons();
}

function broadcastAudienceSignature() {
  return JSON.stringify(broadcastAudiencePayload());
}

function invalidateBroadcastPreview() {
  state.broadcastPreview = null;
  state.broadcastPreviewSignature = "";
  renderBroadcastAudiencePreview();
}

const BROADCAST_LESSON_MODE_LABELS = {
  offline: "очные",
  online: "онлайн",
  individual: "индивидуальные",
};

function normalizeBroadcastTargetText(value) {
  return String(value || "")
    .trim()
    .toLocaleLowerCase("ru-RU")
    .replaceAll("ё", "е")
    .replace(/\s+/g, " ");
}

function broadcastGroupLessonMode(groupName) {
  const normalized = normalizeBroadcastTargetText(groupName);
  if (normalized.includes("индивид")) return "individual";
  if (normalized.includes("общ")) return "online";
  return "offline";
}

function broadcastTargetGroups() {
  const configuredGroups = state.broadcastTargetOptions?.groups || [];
  const source = configuredGroups.length
    ? configuredGroups
    : students.map((student) => String(student.group || "").trim()).filter(Boolean);
  return [...new Set(source)].sort((left, right) => left.localeCompare(right, "ru"));
}

function broadcastTargetVenues() {
  return state.broadcastTargetOptions?.venues || [];
}

function broadcastExplicitGroupOwners() {
  const owners = new Map();
  broadcastTargetVenues().forEach((venue) => {
    (venue.group_names || []).forEach((groupName) => {
      const key = normalizeBroadcastTargetText(groupName);
      if (!key) return;
      if (!owners.has(key)) owners.set(key, new Set());
      owners.get(key).add(normalizeBroadcastTargetText(venue.name));
    });
  });
  return owners;
}

function broadcastVenueMatchesGroup(groupName, venue, explicitOwners = null) {
  const normalizedGroup = normalizeBroadcastTargetText(groupName);
  const normalizedVenue = normalizeBroadcastTargetText(venue?.name);
  const owners = (explicitOwners || broadcastExplicitGroupOwners()).get(normalizedGroup);
  if (owners?.size) return owners.has(normalizedVenue);
  const importedVenueMatch = students.some(
    (student) =>
      normalizeBroadcastTargetText(student.group) === normalizedGroup &&
      normalizeBroadcastTargetText(student.venue) === normalizedVenue,
  );
  if (importedVenueMatch) return true;
  return (venue?.keywords || []).some((keyword) => {
    const normalizedKeyword = normalizeBroadcastTargetText(keyword);
    return normalizedKeyword && normalizedGroup.includes(normalizedKeyword);
  });
}

function selectedBroadcastVenues() {
  const availableNames = new Set(broadcastTargetVenues().map((venue) => venue.name));
  return [...state.broadcastSelectedVenues]
    .filter((name) => availableNames.has(name))
    .sort((left, right) => left.localeCompare(right, "ru"));
}

function selectedBroadcastLessonModes() {
  return [...state.broadcastSelectedLessonModes].filter(
    (mode) => mode in BROADCAST_LESSON_MODE_LABELS,
  );
}

function availableBroadcastGroups() {
  const selectedModes = new Set(selectedBroadcastLessonModes());
  const selectedVenueNames = new Set(
    selectedBroadcastVenues().map(normalizeBroadcastTargetText),
  );
  const selectedVenues = broadcastTargetVenues().filter((venue) =>
    selectedVenueNames.has(normalizeBroadcastTargetText(venue.name)),
  );
  const explicitOwners = broadcastExplicitGroupOwners();
  return broadcastTargetGroups().filter((groupName) => {
    if (selectedModes.size && !selectedModes.has(broadcastGroupLessonMode(groupName))) {
      return false;
    }
    if (
      selectedVenues.length &&
      !selectedVenues.some((venue) =>
        broadcastVenueMatchesGroup(groupName, venue, explicitOwners),
      )
    ) {
      return false;
    }
    return true;
  });
}

function setBroadcastFilterChipState(chip, selected) {
  if (!chip) return;
  chip.classList.toggle("is-active", selected);
  chip.classList.toggle("is-selected", selected);
  if (chip instanceof HTMLButtonElement) {
    chip.setAttribute("aria-pressed", String(selected));
  }
}

function renderBroadcastVenueSelectionSummary() {
  const summary = qs("#broadcastVenueSelectedCount");
  if (!summary) return;
  summary.textContent = `Выбрано: ${state.broadcastVenueDraft?.groups.size || 0}`;
}

function renderBroadcastVenueEditorGroups() {
  const list = qs("#broadcastVenueGroupList");
  if (!list || !state.broadcastVenueDraft) return;
  const search = normalizeBroadcastTargetText(qs("#broadcastVenueGroupSearch")?.value);
  const visibleGroups = broadcastTargetGroups().filter(
    (groupName) => !search || normalizeBroadcastTargetText(groupName).includes(search),
  );
  list.innerHTML = visibleGroups.length
    ? visibleGroups
        .map((groupName) => {
          const selected = state.broadcastVenueDraft.groups.has(groupName);
          return `
            <label class="broadcast-venue-group-option ${selected ? "is-selected" : ""}">
              <input
                type="checkbox"
                data-broadcast-venue-group="${escapeHtml(groupName)}"
                ${selected ? "checked" : ""}
              />
              <span>${escapeHtml(groupName)}</span>
            </label>`;
        })
        .join("")
    : '<div class="empty-state compact-empty">Подходящих групп нет</div>';
  renderBroadcastVenueSelectionSummary();
}

function renderBroadcastVenueEditor() {
  const editor = qs("#broadcastVenueEditor");
  if (!editor) return;
  const draft = state.broadcastVenueDraft;
  editor.hidden = !state.broadcastVenueEditorOpen || !draft;
  if (editor.hidden) return;
  const title = qs("#broadcastVenueEditorTitle");
  const nameInput = qs("#broadcastVenueName");
  const keywordsInput = qs("#broadcastVenueKeywords");
  const saveButton = qs("#saveBroadcastVenueButton");
  if (title) title.textContent = draft.id ? "Редактирование площадки" : "Новая площадка";
  if (nameInput && nameInput.value !== draft.name) nameInput.value = draft.name;
  if (keywordsInput && keywordsInput.value !== draft.keywords) keywordsInput.value = draft.keywords;
  if (saveButton) {
    saveButton.disabled = state.broadcastVenueSaving;
    const label = saveButton.querySelector("span");
    if (label) label.textContent = state.broadcastVenueSaving ? "Сохраняем..." : "Сохранить площадку";
  }
  renderBroadcastVenueEditorGroups();
}

function renderBroadcastTargetFilters() {
  const modeAllButton = qs('[data-broadcast-modes="all"]');
  if (modeAllButton) {
    setBroadcastFilterChipState(modeAllButton, state.broadcastSelectedLessonModes.size === 0);
  }
  qsa("[data-broadcast-lesson-mode]").forEach((input) => {
    input.checked = state.broadcastSelectedLessonModes.has(input.value);
    setBroadcastFilterChipState(input.closest(".broadcast-filter-chip"), input.checked);
  });

  const container = qs("#broadcastVenueOptions");
  const addButton = qs("#addBroadcastVenueButton");
  if (!container) return;
  if (addButton) {
    addButton.hidden = !state.broadcastTargetOptions?.can_manage_venues;
  }
  if (state.broadcastTargetOptionsLoading) {
    container.innerHTML = '<div class="broadcast-target-loading"><i data-lucide="loader-circle"></i>Загружаем площадки...</div>';
    refreshIcons();
    return;
  }
  if (state.broadcastTargetOptionsError) {
    container.innerHTML = `
      <div class="broadcast-target-error">
        <span>${escapeHtml(state.broadcastTargetOptionsError)}</span>
        <button class="text-action" type="button" data-reload-broadcast-targets>Повторить</button>
      </div>`;
    return;
  }
  const venues = broadcastTargetVenues();
  const selected = new Set(selectedBroadcastVenues());
  container.innerHTML = `
    <button class="broadcast-filter-chip ${selected.size ? "" : "is-active is-selected"}" type="button" data-broadcast-venues="all" aria-pressed="${String(!selected.size)}">
      Все площадки
    </button>
    ${venues
      .map(
        (venue) => `
          <div class="broadcast-venue-option">
            <label class="broadcast-filter-chip ${selected.has(venue.name) ? "is-active is-selected" : ""}">
              <input type="checkbox" value="${escapeHtml(venue.name)}" data-broadcast-venue ${selected.has(venue.name) ? "checked" : ""} />
              <span>${escapeHtml(venue.name)}</span>
              <small>${Number(venue.matched_group_count || 0)} гр.</small>
            </label>
            ${state.broadcastTargetOptions?.can_manage_venues ? `
              <button class="icon-action" type="button" data-edit-broadcast-venue="${escapeHtml(venue.id)}" title="Настроить ${escapeHtml(venue.name)}" aria-label="Настроить ${escapeHtml(venue.name)}">
                <i data-lucide="pencil"></i>
              </button>` : ""}
          </div>
        `,
      )
      .join("")}
    ${!venues.length ? '<p class="broadcast-target-empty">Площадки еще не настроены. Добавьте название и слова из названий групп.</p>' : ""}
  `;
  renderBroadcastVenueEditor();
  refreshIcons();
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
    venue_names: selectedBroadcastVenues(),
    lesson_modes: selectedBroadcastLessonModes(),
    balance_threshold:
      qs("#broadcastAudienceFilter")?.value === "low_balance"
        ? Number(qs("#broadcastBalanceThreshold")?.value || 300)
        : null,
  };
}

function renderBroadcastGroups() {
  const list = qs("#broadcastGroupList");
  const hint = qs("#broadcastGroupHint");
  if (!list || !hint) return;
  const groups = availableBroadcastGroups();
  if (!groups.length) {
    list.innerHTML = '<div class="empty-state compact-empty">По выбранным условиям групп нет</div>';
    hint.textContent = "Измените формат или площадку.";
    return;
  }
  hint.textContent = state.broadcastAllGroups
    ? `Подойдут все группы: ${groups.length}`
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

function demoBroadcastTargetOptions() {
  const venueNames = [...new Set(students.map((student) => String(student.venue || "").trim()).filter(Boolean))];
  return {
    groups: broadcastTargetGroups(),
    venues: venueNames.map((name, index) => ({
      id: `demo-venue-${index + 1}`,
      name,
      keywords: [],
      group_names: [],
      matched_group_count: new Set(
        students.filter((student) => String(student.venue || "").trim() === name).map((student) => student.group),
      ).size,
    })),
    can_manage_venues: ["admin", "partner_director", "superadmin"].includes(
      primaryStaffRole(),
    ),
  };
}

async function loadBroadcastTargetOptions(force = false) {
  if (state.broadcastTargetOptionsLoading) return;
  if (state.broadcastTargetOptionsLoaded && !force) return;
  state.broadcastTargetOptionsLoading = true;
  state.broadcastTargetOptionsError = "";
  renderBroadcastTargetFilters();
  try {
    if (apiContext.demoMode || !apiContext.maxUserId) {
      state.broadcastTargetOptions = demoBroadcastTargetOptions();
    } else {
      const params = new URLSearchParams({
        max_user_id: String(apiContext.maxUserId),
        tenant_slug: apiContext.tenantSlug || "",
      });
      const response = await apiFetch(`/api/v1/miniapp/broadcasts/options?${params}`);
      if (!response.ok) throw new Error(await parseApiError(response));
      state.broadcastTargetOptions = await response.json();
    }
    state.broadcastTargetOptionsLoaded = true;
  } catch (error) {
    state.broadcastTargetOptionsError = error.message || "Не удалось загрузить площадки";
  } finally {
    state.broadcastTargetOptionsLoading = false;
    renderBroadcasts();
  }
}

function openBroadcastVenueEditor(venueId = "") {
  const venue = broadcastTargetVenues().find((item) => String(item.id) === String(venueId));
  state.broadcastVenueDraft = {
    id: venue?.id || "",
    originalName: venue?.name || "",
    name: venue?.name || "",
    keywords: (venue?.keywords || []).join(", "),
    groups: new Set(venue?.group_names || []),
  };
  state.broadcastVenueEditorOpen = true;
  renderBroadcastTargetFilters();
  qs("#broadcastVenueName")?.focus();
}

function closeBroadcastVenueEditor() {
  state.broadcastVenueEditorOpen = false;
  state.broadcastVenueDraft = null;
  renderBroadcastTargetFilters();
}

async function saveBroadcastVenue() {
  if (state.broadcastVenueSaving || !state.broadcastVenueDraft) return;
  const name = qs("#broadcastVenueName")?.value.trim() || "";
  if (!name) {
    showNotice("Введите название площадки", "danger");
    qs("#broadcastVenueName")?.focus();
    return;
  }
  const keywords = (qs("#broadcastVenueKeywords")?.value || "")
    .split(/[,;\n]+/)
    .map((value) => value.trim())
    .filter(Boolean);
  const body = {
    max_user_id: Number(apiContext.maxUserId || 1),
    tenant_slug: apiContext.tenantSlug || undefined,
    name,
    keywords,
    group_names: [...state.broadcastVenueDraft.groups],
  };
  state.broadcastVenueSaving = true;
  renderBroadcastVenueEditor();
  try {
    let saved;
    if (apiContext.demoMode || !apiContext.maxUserId) {
      saved = {
        id: state.broadcastVenueDraft.id || `demo-venue-${Date.now()}`,
        name,
        keywords,
        group_names: body.group_names,
        matched_group_count: body.group_names.length,
      };
    } else {
      const path = state.broadcastVenueDraft.id
        ? `/api/v1/miniapp/broadcasts/venues/${encodeURIComponent(state.broadcastVenueDraft.id)}`
        : "/api/v1/miniapp/broadcasts/venues";
      const response = await apiFetch(path, {
        method: state.broadcastVenueDraft.id ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!response.ok) throw new Error(await parseApiError(response));
      saved = await response.json();
    }
    const venues = [...broadcastTargetVenues()];
    const index = venues.findIndex((venue) => String(venue.id) === String(saved.id));
    if (index >= 0) venues[index] = saved;
    else venues.push(saved);
    state.broadcastTargetOptions = {
      ...(state.broadcastTargetOptions || { groups: broadcastTargetGroups(), can_manage_venues: true }),
      venues: venues.sort((left, right) => left.name.localeCompare(right.name, "ru")),
    };
    if (state.broadcastSelectedVenues.delete(state.broadcastVenueDraft.originalName)) {
      state.broadcastSelectedVenues.add(saved.name);
    }
    state.broadcastVenueEditorOpen = false;
    state.broadcastVenueDraft = null;
    invalidateBroadcastPreview();
    queueBroadcastDraftSave();
    showNotice("Площадка сохранена", "ok");
  } catch (error) {
    showNotice(error.message || "Не удалось сохранить площадку", "danger");
  } finally {
    state.broadcastVenueSaving = false;
    renderBroadcasts();
  }
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
  const modes = item.lesson_modes?.length
    ? item.lesson_modes.map((mode) => BROADCAST_LESSON_MODE_LABELS[mode] || mode).join(", ")
    : "все форматы";
  return `${recipients} · ${modes} · ${venues} · ${groups}`;
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
    venues: selectedBroadcastVenues(),
    lessonModes: selectedBroadcastLessonModes(),
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

function queueBroadcastDraftSave() {
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
    state.broadcastSelectedVenues = new Set(
      Array.isArray(draft.venues)
        ? draft.venues
        : draft.venueFilter && draft.venueFilter !== "all"
          ? [draft.venueFilter]
          : [],
    );
    state.broadcastSelectedLessonModes = new Set(
      Array.isArray(draft.lessonModes) ? draft.lessonModes : [],
    );
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

function closeBroadcastEmojiPicker() {
  const picker = qs("#broadcastEmojiPicker");
  const button = qs("#broadcastEmojiButton");
  if (picker) picker.hidden = true;
  if (button) button.setAttribute("aria-expanded", "false");
}

function toggleBroadcastEmojiPicker() {
  const picker = qs("#broadcastEmojiPicker");
  const button = qs("#broadcastEmojiButton");
  if (!picker || !button) return;
  const willOpen = picker.hidden;
  picker.hidden = !willOpen;
  button.setAttribute("aria-expanded", String(willOpen));
  if (willOpen) picker.querySelector("button")?.focus();
}

function insertBroadcastEmoji(emoji) {
  const message = qs("#broadcastMessage");
  if (!message || !emoji) return;
  const start = message.selectionStart ?? message.value.length;
  const end = message.selectionEnd ?? start;
  message.setRangeText(emoji, start, end, "end");
  message.dispatchEvent(new Event("input", { bubbles: true }));
  closeBroadcastEmojiPicker();
  message.focus();
}

function duplicateBroadcast(itemId) {
  const item = state.broadcastHistory.find((entry) => String(entry.id || "") === String(itemId));
  if (!item) return;
  qs("#broadcastTitle").value = item.title || "";
  qs("#broadcastMessage").value = item.message || "";
  qs("#broadcastRecipientCategory").value = item.recipient_category || "all";
  qs("#broadcastAudienceFilter").value = item.audience_filter || "all";
  state.broadcastSelectedVenues = new Set(item.venue_names || []);
  state.broadcastSelectedLessonModes = new Set(item.lesson_modes || []);
  state.broadcastAllGroups = !(item.group_names || []).length;
  state.broadcastSelectedGroups = new Set(item.group_names || []);
  invalidateBroadcastPreview();
  state.broadcastStep = 1;
  queueBroadcastDraftSave();
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
  if (
    roleViews(state.role).includes("broadcasts") &&
    !state.broadcastTargetOptionsLoaded &&
    !state.broadcastTargetOptionsLoading
  ) {
    void loadBroadcastTargetOptions();
  }
  const form = qs("#broadcastForm");
  if (form) form.dataset.currentStep = String(state.broadcastStep);
  if (state.broadcastStep !== 2) closeBroadcastEmojiPicker();
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
  if (payload.lesson_modes.length) {
    const modes = new Set(payload.lesson_modes);
    matched = matched.filter((student) => modes.has(broadcastGroupLessonMode(student.group)));
  }
  if (payload.venue_names.length) {
    const venueNames = new Set(payload.venue_names.map(normalizeBroadcastTargetText));
    const venues = broadcastTargetVenues().filter((venue) =>
      venueNames.has(normalizeBroadcastTargetText(venue.name)),
    );
    const explicitOwners = broadcastExplicitGroupOwners();
    matched = matched.filter((student) =>
      venues.some((venue) => broadcastVenueMatchesGroup(student.group, venue, explicitOwners)),
    );
  }
  if (payload.audience_filter === "low_balance") {
    const threshold = Number(payload.balance_threshold ?? 300);
    matched = matched.filter((student) => Number(student.balance || 0) <= threshold);
  } else if (payload.audience_filter === "active_orders") {
    const studentIds = new Set(
      orders
        .filter((order) => ["created", "reserved", "awaiting_delivery", "delivered_to_venue", "transferred_to_teacher", "problem"].includes(order.status))
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
  if (state.broadcastTargetOptionsLoading) {
    showNotice("Подождите, площадки еще загружаются");
    return null;
  }
  if (!state.broadcastTargetOptionsLoaded) {
    await loadBroadcastTargetOptions();
  }
  if (state.broadcastTargetOptionsError) {
    showNotice(state.broadcastTargetOptionsError, "danger");
    return null;
  }
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
  const confirmed = await requestConfirmation({
    eyebrow: "Проверка рассылки",
    title: "Отправить новость?",
    message: `Получателей: ${preview.recipient_count}. После отправки изменить сообщение нельзя.`,
    confirmLabel: "Отправить",
    cancelLabel: "Вернуться к редактированию",
  });
  if (!confirmed) {
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
    state.broadcastSelectedVenues = new Set();
    state.broadcastSelectedLessonModes = new Set();
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
