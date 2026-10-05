// Teacher-owned server schedules. Message text exists only in the current editor.
let feedbackStorageKey = `algo-max-feedback-preview-v2:${apiContext.tenantSlug || "demo"}:${apiContext.maxUserId || apiContext.demoRole || "teacher"}`;
const feedbackState = {
  tab: "groups", contextKey: "", legacyStorageKey: "", catalog: null, loading: false, scheduleSaving: false, error: "", restored: false,
  group: "", rowId: "", course: "", lesson: 1, date: feedbackToday(), offset: 0,
  mode: "group", repeat: false, coins: false, absent: [], extraAbsent: "",
  text: "", generated: null, edited: false, stale: false,
  schedules: Object.create(null), serverVersions: Object.create(null), editor: null, editorDirty: false,
  editorUndo: null, groupSearch: "",
};

function feedbackToday() {
  return new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Moscow" }).format(new Date());
}

function feedbackShiftDate(value, days) {
  if (!feedbackValidDate(value) || !Number.isSafeInteger(days)) throw new Error("Проверьте дату занятия");
  const date = new Date(`${value}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  const result = date.toISOString().slice(0, 10);
  if (!feedbackValidDate(result)) throw new Error("Дата выходит за допустимый диапазон");
  return result;
}

function feedbackDateLabel(value) {
  if (!feedbackValidDate(value)) return "Дата не указана";
  return new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long", timeZone: "UTC" })
    .format(new Date(`${value}T12:00:00Z`));
}

function feedbackStudents() {
  const visible = studentsForCurrentRole();
  if (apiContext.demoMode) return visible;
  return visible.filter((student) => student.teacherVisible);
}

function feedbackGroups() {
  return [...new Set(feedbackStudents().map(studentGroupName).filter(Boolean))].sort((a, b) => {
    const left = feedbackGroupOrder(a), right = feedbackGroupOrder(b);
    return left[0] - right[0] || left[1] - right[1] || a.localeCompare(b, "ru");
  });
}

function feedbackPersist() {
  try {
    localStorage.setItem(feedbackStorageKey, JSON.stringify({ schedules: feedbackState.schedules }));
    return true;
  } catch {
    showNotice("Не удалось сохранить данные на этом устройстве. Скопируйте текст или скачайте файл.", "danger");
    return false;
  }
}

async function feedbackScheduleRequest(payload = null, tenantSlug = apiContext.tenantSlug) {
  const response = await apiFetch(apiUrl("/api/v1/miniapp/feedback/schedules", {
    tenant_slug: tenantSlug,
  }), payload ? { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) } : {});
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(typeof data.detail === "string" ? data.detail : "Не удалось сохранить расписание на сервере");
    error.status = response.status; throw error;
  }
  return data;
}

async function feedbackLoadServerSchedules() {
  if (apiContext.demoMode) return;
  const tenant = apiContext.tenantSlug;
  const groups = feedbackGroups();
  const local = Object.fromEntries(groups.map((group) => [group, structuredClone(feedbackSchedule(group))]));
  let remote = await feedbackScheduleRequest(null, tenant);
  if (tenant !== apiContext.tenantSlug) throw new Error("Школа изменилась. Откройте вкладку заново.");
  for (const group of groups) {
    if (!Object.hasOwn(remote.schedules, group)) {
      const schedule = local[group];
      try {
        const saved = await feedbackScheduleRequest({ group_name: group, revision: 0, schedule }, tenant);
        remote.schedules[group] = saved;
      } catch (error) {
        if (error.status !== 409) throw error;
        remote = await feedbackScheduleRequest(null, tenant);
        if (!Object.hasOwn(remote.schedules, group)) throw error;
      }
    }
    if (tenant !== apiContext.tenantSlug) throw new Error("Школа изменилась. Откройте вкладку заново.");
  }
  for (const [group, entry] of Object.entries(remote.schedules)) {
    feedbackValidateSchedule(entry.schedule, feedbackState.catalog);
    feedbackState.schedules[group] = entry.schedule;
    feedbackState.serverVersions[group] = entry.revision;
  }
  feedbackPersist();
}

async function feedbackSaveSchedule(group, schedule) {
  if (apiContext.demoMode) return schedule;
  const context = feedbackState.contextKey;
  const tenant = apiContext.tenantSlug;
  const saved = await feedbackScheduleRequest({ group_name: group,
    revision: feedbackState.serverVersions[group] || 0, schedule }, tenant);
  if (context !== feedbackState.contextKey || tenant !== apiContext.tenantSlug) {
    throw new Error("Расписание сохранено в прежней школе. Откройте вкладку выбранной школы заново.");
  }
  feedbackState.serverVersions[group] = saved.revision;
  return saved.schedule;
}

function feedbackSchedule(group) {
  if (!Object.hasOwn(feedbackState.schedules, group)) {
    const student = feedbackStudents().find((item) => studentGroupName(item) === group);
    const course = feedbackResolveCourse(student?.course || (apiContext.demoMode ? "Питон Старт 1-й год" : ""), feedbackState.catalog);
    if (!course) throw new Error(`Для группы «${group}» нет соответствия курсу «${student?.course || "не указан"}». Выберите материалы курса после уточнения названия.`);
    const today = feedbackToday();
    const day = feedbackGroupOrder(group)[0];
    const weekday = day < 7 ? (day + 1) % 7 : new Date(`${today}T12:00:00Z`).getUTCDay();
    const lastDate = feedbackShiftDate(today, -((new Date(`${today}T12:00:00Z`).getUTCDay() - weekday + 7) % 7));
    feedbackState.schedules[group] = { course, mode: "group", rows: feedbackSeries(course,
      lastDate, 1, 1, feedbackState.catalog[course].length, 7, feedbackState.catalog) };
  }
  return feedbackState.schedules[group];
}

function feedbackSelectGroup(group, rowId = "") {
  const schedule = feedbackSchedule(group);
  const rows = schedule.rows;
  const row = rows.find((item) => item.id === rowId)
    || rows.find((item) => !item.skipped) || rows[0];
  Object.assign(feedbackState, {
    group, rowId: row.id, course: schedule.course, lesson: Number(row.lesson), date: row.date,
    offset: Number(row.number) - Number(row.lesson), mode: schedule.mode, absent: [], extraAbsent: "",
    repeat: row.repeat, coins: false, text: "", generated: null, edited: false, stale: false,
    editor: structuredClone(schedule), editorDirty: false, editorUndo: null,
  });
}

async function renderFeedback() {
  if (!canAccessFeedback()) return;
  const key = `algo-max-feedback-preview-v2:${apiContext.tenantSlug || "demo"}:${apiContext.maxUserId || apiContext.demoRole || "teacher"}`;
  if (feedbackState.contextKey !== key) {
    const legacy = feedbackState.contextKey ? "" : feedbackStorageKey;
    feedbackStorageKey = key;
    Object.assign(feedbackState, { contextKey: key, legacyStorageKey: legacy, catalog: null,
      schedules: Object.create(null), serverVersions: Object.create(null),
      group: "", rowId: "", text: "", generated: null, edited: false,
      editor: null, editorDirty: false, editorUndo: null, restored: false });
  }
  const root = qs("#feedbackWorkspace");
  if (!root) return;
  if (!feedbackState.catalog) {
    if (feedbackState.loading) return;
    feedbackState.loading = true;
    root.innerHTML = '<div class="empty-state compact-empty">Загружаем материалы курсов…</div>';
    try {
      const response = await apiFetch(apiUrl("/api/v1/miniapp/feedback/catalog"));
      if (!response.ok) throw new Error("Не удалось загрузить материалы курсов");
      const raw = await response.json();
      if (!raw || typeof raw !== "object" || Array.isArray(raw)) throw new Error("Материалы курсов повреждены");
      const courses = Object.entries(raw).filter(([, lessons]) => Array.isArray(lessons) && lessons.length
        && lessons.every((item) => item && typeof item.title === "string" && typeof item.educational_results === "string"));
      if (!courses.length) throw new Error("В каталоге нет доступных уроков");
      feedbackState.catalog = Object.fromEntries(courses);
      feedbackState.course = courses[0][0];
      let saved = {};
      let recovered = false;
      try {
        const current = localStorage.getItem(feedbackStorageKey) || (feedbackState.legacyStorageKey ? localStorage.getItem(feedbackState.legacyStorageKey) : null);
        const legacy = !current && apiContext.demoRole === "teacher" ? localStorage.getItem("algo-max-feedback-preview-v1") : null;
        saved = JSON.parse(current || legacy || "{}");
      } catch { recovered = true; }
      const storedGroups = [...new Set(studentsForCurrentRole().map(studentGroupName).filter(Boolean))];
      const restored = feedbackRestore(saved, feedbackState.catalog, storedGroups);
      feedbackState.schedules = restored.schedules;
      await feedbackLoadServerSchedules();
      if (apiContext.demoMode) feedbackPersist();
      feedbackState.restored = true; feedbackState.error = "";
      if (recovered || restored.recovered) showNotice("Повреждённые записи пропущены. Остальные настройки расписания сохранены.", "danger");
    } catch (error) {
      feedbackState.catalog = null;
      feedbackState.error = error.message;
      root.innerHTML = `<div class="empty-state compact-empty"><span>${escapeHtml(error.message)}</span>
        <button class="secondary-action" data-feedback-retry>Попробовать ещё раз</button></div>`;
      return;
    } finally { feedbackState.loading = false; }
  }
  if (!["teacher", "admin"].includes(state.role)) return;
  const groups = feedbackGroups();
  const scheduleOpen = qs(".feedback-schedule-settings")?.open;
  const advancedOpen = qs(".feedback-advanced")?.open;
  if (feedbackState.tab === "groups" && !groups.includes(feedbackState.group)) {
    if (groups[0]) feedbackSelectGroup(groups[0]); else feedbackState.tab = "manual";
  }
  root.innerHTML = `
    <div class="feedback-tabs" role="tablist" aria-label="Обратная связь">
      ${[["groups", "По группам", "users"], ["manual", "Создать вручную", "square-pen"]]
        .map(([tab, label, icon]) => `<button id="feedbackTab-${tab}" type="button" role="tab" aria-controls="feedbackTabPanel" aria-selected="${feedbackState.tab === tab}" tabindex="${feedbackState.tab === tab ? 0 : -1}"
          class="${feedbackState.tab === tab ? "is-active" : ""}" data-feedback-tab="${tab}">
          <i data-lucide="${icon}"></i>${label}</button>`).join("")}
    </div>
    <div id="feedbackTabPanel" role="tabpanel" aria-labelledby="feedbackTab-${feedbackState.tab}">
      ${feedbackState.tab === "groups" ? feedbackGroupMarkup(groups) : ""}
      <div class="feedback-workspace-grid">
        <form id="feedbackComposeForm" class="feedback-compose-card" novalidate>
          <div class="feedback-card-heading"><span class="feedback-step">1</span><div><h2>Что было на занятии</h2><p>Выберите материал и добавьте детали группы.</p></div></div>
          ${feedbackFormMarkup()}
          <button class="primary-action feedback-generate" type="submit"><i data-lucide="sparkles"></i>Подготовить сообщение</button>
        </form>
        <section class="feedback-output-card" aria-label="Сообщение родителям">
          <div class="feedback-card-heading"><span class="feedback-step">2</span><div><h2>Сообщение родителям</h2><p>Отредактируйте текст и скопируйте его или скачайте файл.</p></div></div>
          <div class="feedback-output-meta" id="feedbackOutputMeta">${feedbackOutputMeta()}</div>
          <p class="feedback-stale-note" ${feedbackState.stale ? "" : "hidden"}>Параметры изменены. Текст ниже относится к прежнему занятию — подготовьте сообщение заново.</p>
          <label class="feedback-editor-label" for="feedbackText">Текст сообщения</label>
          <textarea id="feedbackText" class="feedback-text" maxlength="20000" placeholder="Здесь появится сообщение о занятии. Его можно отредактировать перед копированием." ${feedbackState.generated ? "" : "disabled"}>${escapeHtml(feedbackState.text)}</textarea>
          <div class="feedback-output-actions"><button class="primary-action" data-feedback-copy type="button" ${feedbackState.text.trim() ? "" : "disabled"}><i data-lucide="copy"></i>Скопировать</button>
            <button class="secondary-action" data-feedback-download type="button" ${feedbackState.text.trim() ? "" : "disabled"} aria-label="Скачать сообщение текстовым файлом"><i data-lucide="download"></i></button></div>
          <p class="feedback-delivery-note"><i data-lucide="shield-check"></i>Сообщения не отправляются. Вы сами решаете, когда поделиться текстом.</p>
        </section>
      </div>
    </div>`;
  refreshIcons();
  if (scheduleOpen && qs(".feedback-schedule-settings")) qs(".feedback-schedule-settings").open = true;
  if (advancedOpen && qs(".feedback-advanced")) qs(".feedback-advanced").open = true;
  const weeks = qs(".feedback-weeks");
  const selected = weeks?.querySelector(".is-active");
  if (weeks && selected) weeks.scrollLeft = selected.offsetLeft - weeks.offsetLeft - (weeks.clientWidth - selected.offsetWidth) / 2;
}

function feedbackOutputMeta() {
  const meta = feedbackState.generated;
  return meta ? `<span class="feedback-ready-dot"></span>Урок ${meta.lesson + meta.offset} · ${feedbackDateLabel(meta.date)}`
    : '<span class="feedback-empty-dot"></span>Текст ещё не подготовлен';
}

function feedbackGroupMarkup(groups) {
  const schedule = feedbackSchedule(feedbackState.group);
  const rows = schedule.rows.filter((row) => !row.skipped);
  return `<div class="feedback-group-grid">${groups.map((group) => {
    const config = feedbackSchedule(group);
    const count = feedbackStudents().filter((item) => studentGroupName(item) === group).length;
    return `<button type="button" class="feedback-group-card ${group === feedbackState.group ? "is-active" : ""}" data-feedback-group="${escapeHtml(group)}">
      <span class="feedback-group-icon"><i data-lucide="users"></i></span><span><strong>${escapeHtml(group)}</strong><small>${escapeHtml(config.course)} · учеников: ${count}</small></span><i data-lucide="chevron-right"></i></button>`;
  }).join("")}</div>
    <div class="feedback-week-heading"><h2>Занятия группы</h2><span>${rows.length} занятий · свои даты и материалы</span></div>
    <div class="feedback-weeks">${rows.map((row) => {
      return `<button type="button" data-feedback-row="${escapeHtml(row.id)}" class="${row.id === feedbackState.rowId ? "is-active" : ""} ${row.skipped ? "is-skipped" : ""}">
        <small>${feedbackDateLabel(row.date)}</small><strong>Занятие ${row.number}</strong>
        <span class="feedback-lesson-topic">${escapeHtml(feedbackLessonTopic(schedule.course, row.lesson))}</span>
        ${row.repeat ? '<span class="feedback-repeat-badge">Повторение</span>' : ""}
        <span>${row.skipped ? "Отменено" : row.date > feedbackToday() ? "Впереди" : "Можно подготовить"}</span></button>`;
    }).join("")}</div>
    <details class="feedback-schedule-settings"><summary><i data-lucide="calendar-days"></i>Расписание: уроки и даты</summary>
      <div id="feedbackScheduleEditor">${feedbackScheduleEditorMarkup()}</div>
    </details>`;
}

function feedbackCourseOptions(selected) {
  return Object.keys(feedbackState.catalog).map((course) => `<option value="${escapeHtml(course)}" ${course === selected ? "selected" : ""}>${escapeHtml(course)}</option>`).join("");
}

function feedbackLessonOptions(course, selected) {
  const lessons = feedbackState.catalog[course] || [];
  const invalid = !Number.isInteger(Number(selected)) || Number(selected) < 1 || Number(selected) > lessons.length;
  return `${invalid ? '<option value="" selected>Выберите материал</option>' : ""}${lessons.map((lesson, index) => `<option value="${index + 1}" ${index + 1 === Number(selected) ? "selected" : ""}>${escapeHtml(lesson.title)}${lesson.topic ? ` — ${escapeHtml(lesson.topic)}` : ""}</option>`).join("")}`;
}

function feedbackLessonTopic(course, lesson) {
  const material = feedbackState.catalog[course]?.[Number(lesson) - 1];
  return material?.topic || material?.title || "Материал занятия";
}

function feedbackScheduleEditorMarkup() {
  const editor = feedbackState.editor || structuredClone(feedbackSchedule(feedbackState.group));
  feedbackState.editor = editor;
  return `<form id="feedbackScheduleForm">
      <div class="feedback-fields-two"><label>Курс группы<select name="course">${feedbackCourseOptions(editor.course)}</select></label>
        <label>Формат<select name="mode"><option value="group" ${editor.mode === "group" ? "selected" : ""}>Группа</option><option value="online" ${editor.mode === "online" ? "selected" : ""}>Онлайн / индивидуально</option></select></label></div>
      <label class="feedback-first-date">Дата первого занятия<input name="firstDate" type="date" min="2000-01-01" max="2100-12-31" value="${editor.rows.find((row) => !row.skipped)?.date || feedbackToday()}" required><small>От этой даты отсчитываются остальные недели. Изменение сдвинет весь календарь; отдельные даты ниже можно поправить вручную.</small></label>
      <p>Выключение урока убирает его неделю из календаря: следующие занятия сдвигаются на неделю раньше и перенумеровываются. Их темы сохраняются.</p>
      <div class="feedback-schedule-table-wrap"><table class="feedback-schedule-table"><thead><tr><th scope="col">№ занятия</th><th scope="col">Дата</th><th scope="col">Материал курса</th><th scope="col">Повторение</th><th scope="col">Выключено</th><th scope="col"><span class="feedback-editor-label">Действия</span></th></tr></thead>
      <tbody>${editor.rows.map((row) => `<tr class="${row.skipped ? "feedback-disabled-row" : ""}" data-feedback-schedule-row="${escapeHtml(row.id)}">
        <td><input name="number" type="number" min="1" max="999" step="1" value="${escapeHtml(row.number)}" ${row.skipped ? 'disabled title="Выключенное занятие не имеет номера в календаре"' : ""} required aria-label="Номер занятия">${row.skipped ? '<small>Выключен</small>' : ""}</td>
        <td><input name="date" type="date" min="2000-01-01" max="2100-12-31" value="${escapeHtml(row.date)}" required aria-label="Дата занятия ${escapeHtml(row.number)}"></td>
        <td><select name="lesson" required aria-label="Материал занятия ${escapeHtml(row.number)}">${feedbackLessonOptions(editor.course, row.lesson)}</select></td>
        <td>${row.repeat ? '<span class="feedback-repeat-badge">Повторение</span>' : '<span class="feedback-new-material">Новая тема</span>'}</td>
        <td><input name="skipped" type="checkbox" ${row.skipped ? "checked" : ""} aria-label="Выключить занятие ${escapeHtml(row.number)}"></td>
        <td><button class="icon-button" type="button" data-feedback-remove-row="${escapeHtml(row.id)}" aria-label="Удалить занятие ${escapeHtml(row.number)}"><i data-lucide="trash-2"></i></button></td></tr>`).join("")}</tbody></table></div>
      <div class="feedback-schedule-actions"><button class="secondary-action" type="button" data-feedback-add-row><i data-lucide="plus"></i>Добавить занятие</button>
        <button class="secondary-action" type="button" data-feedback-undo ${feedbackState.editorUndo ? "" : "disabled"}><i data-lucide="undo-2"></i>Отменить изменение</button>
        <button class="primary-action" type="submit">Сохранить расписание</button></div>
    </form>
    <dialog id="feedbackRepeatDialog" class="feedback-repeat-dialog">
      <form id="feedbackRepeatForm"><h3>Добавить повторение</h3>
        <label>Номер повторяемого занятия<select name="repeatRow" required>${editor.rows.filter((row) => !row.skipped).map((row) => `<option value="${escapeHtml(row.id)}">№${row.number} — ${escapeHtml(feedbackLessonTopic(editor.course, row.lesson))}</option>`).join("")}</select></label>
        <p>Повторение появится сразу после выбранного занятия с той же темой. Следующие занятия сдвинутся на неделю позже.</p>
        <div class="feedback-schedule-actions"><button type="button" class="secondary-action" data-feedback-close-repeat>Отмена</button><button type="submit" class="primary-action">Добавить повторение</button></div>
      </form>
    </dialog>
    <details class="feedback-series-settings"><summary>Заполнить даты по интервалу</summary>
      <form id="feedbackSeriesForm"><label>Первая дата<input name="startDate" type="date" min="2000-01-01" max="2100-12-31" value="${editor.rows[0]?.date || feedbackToday()}" required></label>
        <label>Первый материал<input name="firstLesson" type="number" min="1" max="${feedbackState.catalog[editor.course].length}" value="1" required></label>
        <label>Первый номер<input name="firstNumber" type="number" min="1" max="999" value="1" required></label>
        <label>Количество занятий<input name="count" type="number" min="1" max="${feedbackState.catalog[editor.course].length}" value="${feedbackState.catalog[editor.course].length}" required></label>
        <label>Интервал, дней<input name="interval" type="number" min="1" max="60" value="7" required></label>
        <button class="secondary-action" type="submit">Заполнить таблицу</button></form>
      <p>После заполнения проверьте индивидуальные переносы и сохраните расписание.</p>
    </details>`;
}

function feedbackCaptureSchedule() {
  const form = qs("#feedbackScheduleForm");
  if (!form) return feedbackState.editor;
  return feedbackMarkRepeats({ course: form.elements.course.value, mode: form.elements.mode.value,
    rows: [...form.querySelectorAll("[data-feedback-schedule-row]")].map((row) => ({
      id: row.dataset.feedbackScheduleRow, number: Number(row.querySelector('[name="number"]').value),
      date: row.querySelector('[name="date"]').value, lesson: Number(row.querySelector('[name="lesson"]').value),
      repeat: false, skipped: row.querySelector('[name="skipped"]').checked,
    })) });
}

function feedbackRedrawEditor() {
  qs("#feedbackScheduleEditor").innerHTML = feedbackScheduleEditorMarkup();
  refreshIcons();
}

function feedbackFormMarkup() {
  const lesson = feedbackState.catalog[feedbackState.course]?.[feedbackState.lesson - 1];
  const groupStudents = feedbackState.group ? feedbackStudents().filter((item) => studentGroupName(item) === feedbackState.group) : [];
  return `<label>Курс<select name="course" id="feedbackCourse">${feedbackCourseOptions(feedbackState.course)}</select></label>
    <div class="feedback-fields-two"><label>Материал курса<select name="lesson" id="feedbackLesson">${feedbackLessonOptions(feedbackState.course, feedbackState.lesson)}</select></label>
      <label>Дата занятия<input type="date" name="date" min="2000-01-01" max="2100-12-31" value="${feedbackState.date}" required></label></div>
    <div class="feedback-material"><span><i data-lucide="book-open"></i>Из материалов курса</span><p>${escapeHtml((lesson?.educational_results || "").slice(0, 200))}${(lesson?.educational_results || "").length > 200 ? "…" : ""}</p></div>
    <div class="feedback-attendance"><h3>Кого не было на занятии?</h3><p>Отметьте учеников, которым нужно напомнить об отработке.</p>
      <div class="feedback-student-chips">${groupStudents.map((student) => `<label><input type="checkbox" name="absent" value="${escapeHtml(student.name)}" ${feedbackState.absent.includes(student.name) ? "checked" : ""}><span>${escapeHtml(student.name)}<i data-lucide="check"></i></span></label>`).join("")}</div>
      <label class="feedback-add-names">${groupStudents.length ? "Другие имена" : "Отсутствующие ученики"}<input name="extraAbsent" maxlength="2000" value="${escapeHtml(feedbackState.extraAbsent)}" placeholder="Имена через запятую"></label></div>
    ${feedbackState.repeat ? '<p class="feedback-repeat-note"><span class="feedback-repeat-badge">Повторение</span> Закрепляем выбранную тему.</p>' : ""}
    <label class="feedback-checkbox"><input type="checkbox" name="coins" ${feedbackState.coins ? "checked" : ""}><span><strong>Астрокоины за урок уже начислены</strong><small>Отметьте после начисления в разделе «Начисления». Информация о балансе и магазине добавляется в сообщение всегда.</small></span></label>
    <details class="feedback-advanced"><summary>Дополнительные параметры<i data-lucide="chevron-down"></i></summary>
      <div class="feedback-fields-two"><label>Формат<select name="mode"><option value="group" ${feedbackState.mode === "group" ? "selected" : ""}>Группа</option><option value="online" ${feedbackState.mode === "online" ? "selected" : ""}>Онлайн / индивидуально</option></select></label>
        <label>Смещение номера<input name="offset" type="number" min="-99" max="999" step="1" value="${feedbackState.offset}" required></label></div>
      <p>Меняет номер в сообщении, сохраняя материал курса.</p>
    </details>`;
}

function feedbackReadForm(validate = false) {
  const form = qs("#feedbackComposeForm");
  if (!form) return false;
  if (validate && !form.checkValidity()) {
    // Reveal invalid controls inside the collapsed advanced section before focus.
    if (form.querySelector(".feedback-advanced :invalid")) form.querySelector(".feedback-advanced").open = true;
    form.reportValidity(); return false;
  }
  const values = new FormData(form);
  Object.assign(feedbackState, { course: values.get("course"), lesson: Number(values.get("lesson")), date: values.get("date"),
    offset: Number(values.get("offset")), mode: values.get("mode"), repeat: Boolean(feedbackState.group && feedbackSchedule(feedbackState.group).rows.find((row) => row.id === feedbackState.rowId)?.repeat), coins: values.has("coins"),
    absent: values.getAll("absent"), extraAbsent: values.get("extraAbsent").trim() });
  return true;
}

function feedbackBuildText() {
  const { number } = feedbackValidateMessage(feedbackState, feedbackState.catalog);
  const lesson = feedbackState.catalog[feedbackState.course][feedbackState.lesson - 1];
  const formattedDate = feedbackState.date.split("-").reverse().join(".");
  const hour = Number(new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/Moscow", hour: "2-digit", hourCycle: "h23" }).format(new Date()));
  const greeting = hour >= 6 && hour < 12 ? "Доброе утро" : hour >= 12 && hour < 18 ? "Добрый день" : "Добрый вечер";
  const names = feedbackUniqueNames([...feedbackState.absent, ...feedbackState.extraAbsent.split(/[,;\n]/)]);
  const absentNames = names.length < 2 ? names.join("") : `${names.slice(0, -1).join(", ")} и ${names.at(-1)}`;
  const educational = feedbackState.repeat ? "Сегодня мы с ребятами повторяли тему предыдущего занятия, чтобы укрепить знания по ней." : lesson.educational_results;
  const absentText = names.length ? feedbackState.mode === "online"
    ? `${absentNames}, свяжитесь с преподавателем, чтобы договориться об отработке пропущенного занятия.`
    : `${absentNames}, ждем на отработке за 30 минут до начала следующего занятия.` : "";
  return [`Обратная связь урок №${String(number).padStart(2, "0")} от ${formattedDate}`,
    `${greeting}, уважаемые родители!`, educational, absentText,
    feedbackState.coins ? `Начислены астрокоины за урок №${String(number).padStart(2, "0")} от ${formattedDate}.` : "",
    "Баланс астрокоинов и товары, на которые их можно потратить, доступны в миниприложении Алгобота в MAX:\nhttps://max.ru/id525601030904_3_bot",
    "На онлайн-платформе «Алгоритмика» предоставлен весь материал, пройденный на уроках, и прогресс ребенка.", "Удачной недели!"].filter(Boolean).join("\n\n");
}

async function feedbackCanLeaveEditor() {
  if (!feedbackState.editorDirty) return true;
  return requestConfirmation({ title: "Выйти без сохранения расписания?", message: "Изменения дат и уроков ещё не сохранены.", confirmLabel: "Выйти без сохранения", cancelLabel: "Продолжить настройку", destructive: true });
}

document.addEventListener("submit", async (event) => {
  if (!canAccessFeedback() || !event.target.id.startsWith("feedback")) return;
  event.preventDefault();
  if (feedbackState.scheduleSaving) return;
  try {
    if (event.target.id === "feedbackComposeForm") {
      if (!feedbackReadForm(true)) return;
      const row = feedbackState.group && feedbackSchedule(feedbackState.group).rows.find((item) => item.id === feedbackState.rowId);
      if (row?.skipped) throw new Error("Занятие отмечено отменённым. Сначала измените отметку в расписании.");
      const text = feedbackBuildText();
      if (feedbackState.edited && !await requestConfirmation({ title: "Подготовить текст заново?", message: "Ручные правки в текущем сообщении будут заменены текстом по материалам урока.", confirmLabel: "Подготовить заново", cancelLabel: "Оставить правки" })) return;
      const keys = ["group", "rowId", "course", "lesson", "date", "offset", "mode", "repeat", "coins", "absent", "extraAbsent"];
      feedbackState.generated = structuredClone(Object.fromEntries(keys.map((key) => [key, feedbackState[key]])));
      feedbackState.text = text; feedbackState.edited = false; feedbackState.stale = false;
      await renderFeedback();
      if (window.matchMedia("(max-width: 900px)").matches) qs(".feedback-output-card")?.scrollIntoView({ behavior: "smooth", block: "start" });
      showNotice("Сообщение подготовлено. Проверьте текст перед копированием.");
    } else if (event.target.id === "feedbackScheduleForm") {
      if (!event.target.reportValidity()) return;
      const schedule = feedbackCaptureSchedule();
      feedbackValidateSchedule(schedule, feedbackState.catalog);
      const group = feedbackState.group;
      const first = schedule.rows.find((row) => !row.skipped);
      const anchorChanged = first.date !== feedbackSchedule(group).rows.find((row) => !row.skipped).date;
      const controls = [...event.target.elements].map((element) => [element, element.disabled]);
      feedbackState.scheduleSaving = true;
      controls.forEach(([element]) => { element.disabled = true; });
      let saved;
      try { saved = await feedbackSaveSchedule(group, schedule); }
      finally { controls.forEach(([element, disabled]) => { element.disabled = disabled; }); feedbackState.scheduleSaving = false; }
      feedbackState.schedules[group] = structuredClone(saved);
      feedbackState.editorDirty = false;
      const rowId = anchorChanged ? first.id : feedbackState.rowId;
      const persisted = feedbackPersist();
      feedbackSelectGroup(feedbackState.group, rowId); await renderFeedback();
      if (!apiContext.demoMode || persisted) showNotice(apiContext.demoMode ? "Уроки и даты сохранены на этом устройстве" : "Расписание сохранено на сервере и привязано к вашему аккаунту преподавателя");
    } else if (event.target.id === "feedbackSeriesForm") {
      if (!event.target.reportValidity()) return;
      const values = new FormData(event.target);
      const editor = feedbackCaptureSchedule();
      const rows = feedbackSeries(editor.course, values.get("startDate"), values.get("firstLesson"), values.get("firstNumber"), values.get("count"), values.get("interval"), feedbackState.catalog);
      if (!await requestConfirmation({ title: "Заменить таблицу занятий?", message: "Индивидуальные даты и выбранные материалы в таблице будут заменены. Сохранённое расписание изменится только после нажатия «Сохранить расписание».", confirmLabel: "Заполнить таблицу", cancelLabel: "Оставить таблицу" })) return;
      feedbackState.editorUndo = structuredClone(editor); feedbackState.editor = { ...editor, rows }; feedbackState.editorDirty = true; feedbackRedrawEditor();
    } else if (event.target.id === "feedbackRepeatForm") {
      const editor = feedbackCaptureSchedule();
      feedbackValidateSchedule(editor, feedbackState.catalog);
      const next = feedbackInsertRepeat(editor, new FormData(event.target).get("repeatRow"));
      feedbackValidateSchedule(next, feedbackState.catalog);
      qs("#feedbackRepeatDialog").close();
      feedbackState.editorUndo = structuredClone(editor);
      feedbackState.editor = next; feedbackState.editorDirty = true; feedbackRedrawEditor();
    }
  } catch (error) { showNotice(error.message, "danger"); }
});

document.addEventListener("change", (event) => {
  if (!canAccessFeedback() || feedbackState.scheduleSaving) return;
  if (event.target.closest("#feedbackScheduleForm")) {
    if (event.target.name === "course") {
      try {
        const before = structuredClone(feedbackState.editor);
        const next = feedbackChangeCourse(before, event.target.value, feedbackState.catalog);
        feedbackState.editorUndo = before;
        feedbackState.editor = next; feedbackState.editorDirty = true; feedbackRedrawEditor();
        showNotice(`Курс изменён: ${feedbackState.catalog[next.course].length} тем, ${next.rows.length} занятий. Сохраните расписание.`);
      } catch (error) { showNotice(error.message, "danger"); feedbackRedrawEditor(); }
      return;
    }
    if (["firstDate", "skipped"].includes(event.target.name)) {
      try {
        const before = structuredClone(feedbackState.editor);
        const next = event.target.name === "firstDate"
          ? feedbackRebaseSchedule(before, event.target.value)
          : feedbackToggleLesson(before, event.target.closest("[data-feedback-schedule-row]").dataset.feedbackScheduleRow, event.target.checked);
        feedbackValidateSchedule(next, feedbackState.catalog);
        feedbackState.editorUndo = before;
        feedbackState.editor = next; feedbackState.editorDirty = true; feedbackRedrawEditor();
      } catch (error) { showNotice(error.message, "danger"); feedbackRedrawEditor(); }
      return;
    }
    if (event.target.name === "date" && event.target.closest("[data-feedback-schedule-row]").dataset.feedbackScheduleRow === feedbackState.editor.rows.find((row) => !row.skipped)?.id) {
      try {
        const before = structuredClone(feedbackState.editor);
        feedbackState.editor = feedbackRebaseSchedule(before, event.target.value);
        feedbackState.editorUndo = before; feedbackState.editorDirty = true; feedbackRedrawEditor();
      } catch (error) { showNotice(error.message, "danger"); feedbackRedrawEditor(); }
      return;
    }
    feedbackState.editorDirty = true;
    feedbackState.editor = feedbackCaptureSchedule();
    if (event.target.name === "lesson") feedbackRedrawEditor();
    if (event.target.name === "date") {
      qs('#feedbackScheduleForm [name="firstDate"]').value = feedbackState.editor.rows.find((row) => !row.skipped).date;
    }
  }
  if (event.target.closest("#feedbackComposeForm")) {
    feedbackReadForm(); feedbackState.stale = Boolean(feedbackState.generated);
    if (event.target.id === "feedbackCourse") feedbackState.lesson = 1;
    if (["feedbackCourse", "feedbackLesson"].includes(event.target.id)) void renderFeedback();
    else { const note = qs(".feedback-stale-note"); if (note) note.hidden = !feedbackState.stale; }
  }
});

document.addEventListener("input", (event) => {
  if (!canAccessFeedback() || feedbackState.scheduleSaving) return;
  if (event.target.closest("#feedbackScheduleForm")) {
    if (["firstDate", "skipped", "course"].includes(event.target.name)) return;
    if (event.target.name === "date" && event.target.closest("[data-feedback-schedule-row]").dataset.feedbackScheduleRow === feedbackState.editor.rows.find((row) => !row.skipped)?.id) return;
    feedbackState.editorDirty = true; feedbackState.editor = feedbackCaptureSchedule();
  }
  if (event.target.id === "feedbackText") {
    feedbackState.text = event.target.value; feedbackState.edited = true;
    qsa("[data-feedback-copy], [data-feedback-download]").forEach((button) => { button.disabled = !feedbackState.text.trim(); });
  }
});

document.addEventListener("click", async (event) => {
  if (!canAccessFeedback() || feedbackState.scheduleSaving) return;
  const button = event.target.closest("button"); if (!button) return;
  const data = button.dataset;
  try {
    if (data.feedbackTab || data.feedbackGroup || data.feedbackRow) {
      if (!await feedbackCanLeaveEditor()) return;
      const changingMessage = (data.feedbackTab && data.feedbackTab !== feedbackState.tab)
        || (data.feedbackGroup && data.feedbackGroup !== feedbackState.group)
        || (data.feedbackRow && data.feedbackRow !== feedbackState.rowId);
      if (changingMessage && feedbackState.edited && feedbackState.text.trim()
        && !await requestConfirmation({ title: "Закрыть отредактированное сообщение?", message: "Скопируйте текст или скачайте файл, чтобы сохранить правки. При переходе сообщение будет закрыто.", confirmLabel: "Перейти", cancelLabel: "Остаться" })) return;
      if (feedbackState.editorDirty) {
        feedbackState.editor = feedbackState.group ? structuredClone(feedbackSchedule(feedbackState.group)) : null;
        feedbackState.editorDirty = false;
      }
      feedbackReadForm();
      if (data.feedbackTab) {
        feedbackState.tab = data.feedbackTab;
        if (data.feedbackTab === "manual") {
          feedbackState.group = ""; feedbackState.rowId = ""; feedbackState.editorDirty = false;
          if (feedbackState.generated?.group) { feedbackState.text = ""; feedbackState.generated = null; feedbackState.edited = false; }
        }
      } else if (data.feedbackGroup) feedbackSelectGroup(data.feedbackGroup);
      else if (data.feedbackRow) feedbackSelectGroup(feedbackState.group, data.feedbackRow);

      await renderFeedback();
    } else if ("feedbackRetry" in data) await renderFeedback();
    else if ("feedbackCopy" in data) {
      if (!feedbackState.text.trim()) return;
      try { await navigator.clipboard.writeText(feedbackState.text); showNotice("Сообщение скопировано"); }
      catch { qs("#feedbackText")?.focus(); qs("#feedbackText")?.select(); showNotice("Выделили текст — скопируйте его вручную"); }
    } else if ("feedbackDownload" in data) {
      if (!feedbackState.generated || !feedbackState.text.trim()) return;
      const url = URL.createObjectURL(new Blob([feedbackState.text], { type: "text/plain;charset=utf-8" }));
      const link = document.createElement("a"); link.href = url; link.download = `Обратная связь ${feedbackState.generated.date}.txt`; link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } else if ("feedbackAddRow" in data) {
      const editor = feedbackCaptureSchedule();
      feedbackValidateSchedule(editor, feedbackState.catalog);
      if (editor.rows.length >= 100) throw new Error("Максимум 100 занятий в расписании");
      const dialog = qs("#feedbackRepeatDialog");
      dialog.showModal(); dialog.querySelector("select")?.focus();
    } else if ("feedbackCloseRepeat" in data) {
      qs("#feedbackRepeatDialog")?.close();
    } else if (data.feedbackRemoveRow) {
      const editor = feedbackCaptureSchedule();
      if (editor.rows.length === 1) throw new Error("Оставьте хотя бы одно занятие");
      if (!await requestConfirmation({ title: "Удалить занятие из расписания?", message: "Занятие будет удалено после сохранения расписания. Вместо удаления можно выключить его из расписания.", confirmLabel: "Удалить занятие", cancelLabel: "Оставить", destructive: true })) return;
      feedbackState.editorUndo = structuredClone(editor);
      editor.rows = editor.rows.filter((row) => row.id !== data.feedbackRemoveRow);
      feedbackState.editor = editor; feedbackState.editorDirty = true; feedbackRedrawEditor();
    } else if ("feedbackUndo" in data && feedbackState.editorUndo) {
      const current = feedbackCaptureSchedule(); feedbackState.editor = feedbackState.editorUndo; feedbackState.editorUndo = current;
      feedbackState.editorDirty = true; feedbackRedrawEditor();
    }
  } catch (error) { showNotice(error.message, "danger"); }
});

document.addEventListener("keydown", (event) => {
  if (!canAccessFeedback() || !event.target.matches("[data-feedback-tab]") || !["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
  event.preventDefault();
  const tabs = qsa("[data-feedback-tab]"); const index = tabs.indexOf(event.target);
  const next = event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
  const tab = tabs[next].dataset.feedbackTab; tabs[next].click();
  window.setTimeout(() => qs(`[data-feedback-tab="${tab}"]`)?.focus(), 0);
});
