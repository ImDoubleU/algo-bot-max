function teachingWorkspace() {
  return state.teachingWorkspace || { courses: [], groups: [], schedules: [] };
}

function formatTeachingDate(value) {
  if (!value) return "Дата не задана";
  return new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long" }).format(
    new Date(`${value}T12:00:00`),
  );
}

function renderTeaching() {
  const workspace = teachingWorkspace();
  const summary = qs("#teachingSummary");
  if (!summary) return;
  const active = workspace.schedules.filter((item) => item.is_active);
  const nearest = [...active].sort((a, b) =>
    `${a.next_lesson_date}${a.lesson_time}`.localeCompare(`${b.next_lesson_date}${b.lesson_time}`),
  )[0];
  summary.innerHTML = `
    <div><i data-lucide="users"></i><strong>${active.length}</strong><span>групп</span></div>
    <div class="teaching-next"><i data-lucide="calendar-clock"></i><span>Ближайшее занятие</span><strong>${nearest ? `${escapeHtml(formatTeachingDate(nearest.next_lesson_date))}, ${escapeHtml(nearest.lesson_time.slice(0, 5))}` : "Не запланировано"}</strong></div>`;
  renderTeacherInvitations();
  renderScheduleEditor();
  renderScheduleList();
}

function renderTeacherInvitations() {
  const panel = qs("#teacherQrPanel");
  const list = qs("#teacherQrList");
  const groupSelect = qs("#teacherQrGroupFilter");
  if (!panel || !list || !groupSelect) return;

  const visible = state.role === "teacher" && primaryStaffRole() === "teacher";
  panel.hidden = !visible;
  if (!visible) return;

  const teacherStudents = studentsForCurrentRole();
  const groups = [...new Set(teacherStudents.map(studentGroupName))].sort((a, b) =>
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

  const visibleStudents = teacherStudents.filter(
    (student) => state.teacherInvitationGroup === "all" || studentGroupName(student) === state.teacherInvitationGroup,
  );
  list.innerHTML = visibleStudents.length
    ? visibleStudents.map((student) => {
        const invitation = state.teacherInvitations.get(student.id);
        const data = invitation?.data;
        if (data?.available && data.qr_data_url) {
          return `
            <article class="teacher-qr-card is-connected">
              <button type="button" class="teacher-qr-preview" data-open-student-qr="${escapeHtml(student.id)}" aria-label="Показать QR-код ${escapeHtml(student.name)}">
                <img src="${escapeHtml(data.qr_data_url)}" alt="QR-код: ${escapeHtml(student.name)}" />
              </button>
              <span class="teacher-qr-copy">
                <strong>${escapeHtml(student.name)}</strong>
                <small>${escapeHtml(student.group)}</small>
                <span class="link-status is-active"><i data-lucide="link"></i> Родитель подключен</span>
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

function renderScheduleEditor() {
  const editor = qs("#scheduleEditor");
  if (!editor) return;
  editor.hidden = !state.scheduleEditorOpen;
  if (!state.scheduleEditorOpen) return;
  const workspace = teachingWorkspace();
  const item = workspace.schedules.find((schedule) => schedule.id === state.editingScheduleId);
  const selectedGroup = item?.group_name || state.scheduleDraftGroup;
  const today = new Date().toISOString().slice(0, 10);
  const scheduledGroups = new Set(
    workspace.schedules
      .filter((schedule) => schedule.id !== item?.id)
      .map((schedule) => schedule.group_name),
  );
  const groupNames = [...new Set([
    ...(selectedGroup ? [selectedGroup] : []),
    ...workspace.groups
      .map((group) => group.name)
      .filter((groupName) => !scheduledGroups.has(groupName)),
  ])];
  const groupField = groupNames.length
    ? `<select id="scheduleGroupName"><option value="">Выберите группу</option>${groupNames
        .map(
          (groupName) =>
            `<option value="${escapeHtml(groupName)}" ${groupName === selectedGroup ? "selected" : ""}>${escapeHtml(groupName)}</option>`,
        )
        .join("")}</select>`
    : '<input id="scheduleGroupName" value="" placeholder="Название группы" />';
  editor.innerHTML = `
    <div class="schedule-editor-head"><div><p class="eyebrow">${item ? "Редактирование" : "Новая группа"}</p><h3>${escapeHtml(selectedGroup || "Добавить занятие")}</h3></div><button class="icon-button" type="button" data-close-schedule title="Закрыть">×</button></div>
    <div class="schedule-form-grid">
      <label class="schedule-field-wide"><span>Группа</span>${groupField}</label>
      <label class="schedule-field-wide"><span>Курс</span><select id="scheduleCourseId">${workspace.courses.map((course) => `<option value="${escapeHtml(course.id)}" ${course.id === item?.course_id ? "selected" : ""}>${escapeHtml(course.name)} · ${course.lesson_count} уроков</option>`).join("")}</select></label>
      <label><span>Первое занятие</span><input id="scheduleFirstDate" type="date" value="${item?.first_lesson_date || today}" /></label>
      <label><span>Время</span><input id="scheduleTime" type="time" value="${item?.lesson_time?.slice(0, 5) || "10:00"}" /></label>
      <label><span>Формат</span><select id="scheduleMode"><option value="group">Группа</option><option value="individual" ${item?.lesson_mode === "individual" ? "selected" : ""}>Индивидуально</option></select></label>
      <label><span>Место</span><input id="schedulePlace" value="${escapeHtml(item?.lesson_place || "offline")}" placeholder="Адрес или online" /></label>
      <label><span>Текущий урок</span><input id="scheduleLessonNumber" type="number" min="1" value="${item?.current_lesson_number || 1}" /></label>
      <label><span>Длительность</span><select id="scheduleDuration"><option value="90">90 минут</option><option value="60" ${item?.duration_minutes === 60 ? "selected" : ""}>60 минут</option><option value="120" ${item?.duration_minutes === 120 ? "selected" : ""}>120 минут</option></select></label>
    </div>
    <div class="schedule-editor-actions"><button class="secondary-action" type="button" data-close-schedule>Отмена</button><button id="scheduleSaveButton" class="primary-action" type="button">Сохранить расписание</button></div>`;
}

function renderScheduleList() {
  const list = qs("#scheduleList");
  if (!list) return;
  const workspace = teachingWorkspace();
  const items = workspace.schedules;
  if (state.teachingLoading) return void (list.innerHTML = '<div class="empty-state">Загружаем расписание...</div>');
  const groupsByName = new Map();
  workspace.groups.forEach((group) => {
    const existing = groupsByName.get(group.name);
    groupsByName.set(group.name, {
      ...group,
      student_count: (existing?.student_count || 0) + group.student_count,
      course_name: existing?.course_name || group.course_name,
    });
  });
  const scheduledNames = new Set(items.map((item) => item.group_name));
  const unscheduledGroups = [...groupsByName.values()].filter(
    (group) => !scheduledNames.has(group.name),
  );
  if (!items.length && !unscheduledGroups.length) {
    list.innerHTML = '<div class="empty-state">Доступных групп пока нет.</div>';
    return;
  }
  const scheduledRows = items
    .map((item) => {
      const group = groupsByName.get(item.group_name);
      return `
        <article class="schedule-card ${item.is_active ? "" : "is-paused"}">
          <div class="schedule-time">
            <strong>${escapeHtml(item.lesson_time.slice(0, 5))}</strong>
            <span>${escapeHtml(weekdayNames[item.weekday] || "")}</span>
          </div>
          <div class="schedule-main">
            <div class="schedule-card-title">
              <h3>${escapeHtml(item.group_name)}</h3>
              <span class="soft-badge">${group?.student_count || 0} учеников</span>
            </div>
            <p>${escapeHtml(item.course_name)}</p>
            <div class="schedule-next">
              <strong>${formatTeachingDate(item.next_lesson_date)}</strong>
              <span>Урок ${item.next_lesson_number || item.current_lesson_number} из ${item.lesson_count}</span>
            </div>
          </div>
          <div class="schedule-actions">
            <button class="secondary-action" type="button" data-edit-schedule="${escapeHtml(item.id)}">Изменить</button>
          </div>
        </article>`;
    })
    .join("");
  const unscheduledRows = unscheduledGroups
    .map(
      (group) => `
        <article class="schedule-card is-unconfigured">
          <div class="schedule-time">
            <strong>--:--</strong>
            <span>Не настроено</span>
          </div>
          <div class="schedule-main">
            <div class="schedule-card-title">
              <h3>${escapeHtml(group.name)}</h3>
              <span class="soft-badge">${group.student_count} учеников</span>
            </div>
            <p>${escapeHtml(group.course_name || "Курс не указан")}</p>
            <div class="schedule-next"><strong>Добавьте день и время занятия</strong></div>
          </div>
          <div class="schedule-actions">
            <button class="primary-action" type="button" data-configure-schedule="${escapeHtml(group.name)}">Настроить</button>
          </div>
        </article>`,
    )
    .join("");
  list.innerHTML = scheduledRows + unscheduledRows;
}

function openScheduleEditor(scheduleId = "", groupName = "") {
  state.editingScheduleId = scheduleId;
  state.scheduleDraftGroup = groupName;
  state.scheduleEditorOpen = true;
  renderTeaching();
  qs("#scheduleEditor")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function closeScheduleEditor() {
  state.scheduleEditorOpen = false;
  state.editingScheduleId = "";
  state.scheduleDraftGroup = "";
  renderTeaching();
}

async function saveTeachingSchedule() {
  const groupName = qs("#scheduleGroupName")?.value.trim();
  const courseId = qs("#scheduleCourseId")?.value;
  if (!groupName || !courseId) return showNotice("Укажите группу и курс", "danger");
  const payload = { max_user_id: Number(apiContext.maxUserId || 1), tenant_slug: apiContext.tenantSlug || null, schedule_id: state.editingScheduleId || null, group_name: groupName, course_id: courseId, first_lesson_date: qs("#scheduleFirstDate").value, lesson_time: qs("#scheduleTime").value, duration_minutes: Number(qs("#scheduleDuration").value), lesson_mode: qs("#scheduleMode").value, lesson_place: qs("#schedulePlace").value.trim() || "offline", current_lesson_number: Number(qs("#scheduleLessonNumber").value || 1), lesson_offset: 0, is_active: true };
  const button = qs("#scheduleSaveButton");
  button.disabled = true;
  button.textContent = "Сохраняем...";
  try {
    if (apiContext.demoMode || !apiContext.maxUserId) {
      const index = teachingWorkspace().schedules.findIndex((item) => item.id === payload.schedule_id);
      const course = teachingWorkspace().courses.find((item) => item.id === courseId);
      const firstDate = new Date(`${payload.first_lesson_date}T12:00:00`);
      const saved = { ...payload, id: payload.schedule_id || `demo-schedule-${Date.now()}`, course_name: course.name, lesson_count: course.lesson_count, weekday: (firstDate.getDay() + 6) % 7, next_lesson_date: payload.first_lesson_date, next_lesson_title: "Следующая тема курса" };
      if (index >= 0) teachingWorkspace().schedules[index] = saved;
      else teachingWorkspace().schedules.push(saved);
    } else {
      const response = await apiFetch("/api/v1/teaching/schedules", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      if (!response.ok) throw new Error(await parseApiError(response));
      await loadTeachingWorkspace();
    }
    closeScheduleEditor();
    showNotice("Расписание сохранено");
  } catch (error) {
    showNotice(error.message || "Не удалось сохранить расписание", "danger");
    button.disabled = false;
    button.textContent = "Сохранить расписание";
  }
}

function availableBroadcastVenues() {
  return [...new Set(
    students
      .map((student) => String(student.venue || "").trim())
      .filter(Boolean),
  )].sort((left, right) => left.localeCompare(right, "ru"));
}

function broadcastVenueFilterValue() {
  return qs("#broadcastVenueFilter")?.value || "all";
}

function broadcastLessonModeFilterValue() {
  return qs("#broadcastLessonModeFilter")?.value || "all";
}

function broadcastScheduleForGroup(groupName) {
  return teachingWorkspace().schedules.find(
    (schedule) => schedule.is_active !== false && schedule.group_name === groupName,
  );
}

function availableBroadcastGroups() {
  const venueFilter = broadcastVenueFilterValue();
  const lessonModeFilter = broadcastLessonModeFilterValue();
  return [...new Set(
    students
      .filter((student) => {
        if (venueFilter !== "all" && String(student.venue || "") !== venueFilter) return false;
        if (lessonModeFilter === "all") return true;
        return broadcastScheduleForGroup(student.group)?.lesson_mode === lessonModeFilter;
      })
      .map((student) => String(student.group || "").trim())
      .filter(Boolean),
  )].sort((left, right) => left.localeCompare(right, "ru"));
}

function renderBroadcastTargetFilters() {
  const venueSelect = qs("#broadcastVenueFilter");
  if (!venueSelect) return;
  const currentVenue = venueSelect.value || "all";
  const venues = availableBroadcastVenues();
  venueSelect.innerHTML = [
    '<option value="all">Все площадки</option>',
    ...venues.map(
      (venueName) => `<option value="${escapeHtml(venueName)}">${escapeHtml(venueName)}</option>`,
    ),
  ].join("");
  venueSelect.value = venues.includes(currentVenue) ? currentVenue : "all";
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
    venue_names:
      broadcastVenueFilterValue() === "all" ? [] : [broadcastVenueFilterValue()],
    lesson_modes:
      broadcastLessonModeFilterValue() === "all" ? [] : [broadcastLessonModeFilterValue()],
    balance_threshold:
      qs("#broadcastAudienceFilter")?.value === "low_balance"
        ? Number(qs("#broadcastBalanceThreshold")?.value || 300)
        : null,
  };
}

function broadcastAudienceSignature() {
  return JSON.stringify(broadcastAudiencePayload());
}

function invalidateBroadcastPreview() {
  state.broadcastPreview = null;
  state.broadcastPreviewSignature = "";
  renderBroadcastAudiencePreview();
}

function renderBroadcastGroups() {
  const list = qs("#broadcastGroupList");
  const hint = qs("#broadcastGroupHint");
  if (!list || !hint) return;
  const groups = availableBroadcastGroups();
  if (groups.length === 0) {
    list.innerHTML = '<div class="empty-state">Подходящих групп нет.</div>';
    hint.textContent =
      broadcastVenueFilterValue() !== "all" || broadcastLessonModeFilterValue() !== "all"
        ? "Измените площадку или формат занятий."
        : "После импорта учеников группы появятся здесь.";
    return;
  }
  hint.textContent = state.broadcastAllGroups
    ? `Выбраны все группы: ${groups.length}`
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
  const lessonModes = item.lesson_modes?.length
    ? item.lesson_modes
        .map((mode) => (mode === "individual" ? "индивидуально" : "в группах"))
        .join(", ")
    : "любой формат";
  return `${recipients} · ${venues} · ${lessonModes} · ${groups}`;
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
    venueFilter: broadcastVenueFilterValue(),
    lessonModeFilter: broadcastLessonModeFilterValue(),
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

function scheduleBroadcastDraftSave() {
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
    renderBroadcastTargetFilters();
    qs("#broadcastVenueFilter").value = draft.venueFilter || "all";
    qs("#broadcastLessonModeFilter").value = draft.lessonModeFilter || "all";
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

function duplicateBroadcast(itemId) {
  const item = state.broadcastHistory.find((entry) => String(entry.id || "") === String(itemId));
  if (!item) return;
  qs("#broadcastTitle").value = item.title || "";
  qs("#broadcastMessage").value = item.message || "";
  qs("#broadcastRecipientCategory").value = item.recipient_category || "all";
  qs("#broadcastAudienceFilter").value = item.audience_filter || "all";
  renderBroadcastTargetFilters();
  qs("#broadcastVenueFilter").value = item.venue_names?.[0] || "all";
  qs("#broadcastLessonModeFilter").value = item.lesson_modes?.[0] || "all";
  state.broadcastAllGroups = !(item.group_names || []).length;
  state.broadcastSelectedGroups = new Set(item.group_names || []);
  invalidateBroadcastPreview();
  state.broadcastStep = 1;
  scheduleBroadcastDraftSave();
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
  const form = qs("#broadcastForm");
  if (form) form.dataset.currentStep = String(state.broadcastStep);
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
  if (payload.venue_names.length) {
    const venueNames = new Set(payload.venue_names);
    matched = matched.filter((student) => venueNames.has(student.venue));
  }
  if (payload.lesson_modes.length) {
    const lessonModes = new Set(payload.lesson_modes);
    matched = matched.filter((student) =>
      lessonModes.has(broadcastScheduleForGroup(student.group)?.lesson_mode),
    );
  }
  if (payload.audience_filter === "low_balance") {
    const threshold = Number(payload.balance_threshold ?? 300);
    matched = matched.filter((student) => Number(student.balance || 0) <= threshold);
  } else if (payload.audience_filter === "active_orders") {
    const studentIds = new Set(
      orders
        .filter((order) => ["created", "reserved", "transferred_to_teacher", "problem"].includes(order.status))
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
