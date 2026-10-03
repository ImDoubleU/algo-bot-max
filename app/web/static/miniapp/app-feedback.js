// Review-only workspace. No production data writes or parent delivery.
const feedbackStorageKey = `algo-max-feedback-preview-v2:${apiContext.tenantSlug || "demo"}:${apiContext.maxUserId || apiContext.demoRole || "teacher"}`;
const feedbackState = {
  tab: "groups", catalog: null, loading: false, error: "", restored: false,
  group: "", rowId: "", course: "", lesson: 1, date: feedbackToday(), offset: 0,
  mode: "group", repeat: false, coins: false, absent: [], extraAbsent: "",
  text: "", draftId: "", generated: null, edited: false, stale: false,
  schedules: Object.create(null), drafts: [], editor: null, editorDirty: false,
  editorUndo: null, historySearch: "", groupSearch: "", autosaveTimer: null,
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

function feedbackGroups() {
  return [...new Set(studentsForCurrentRole().map(studentGroupName).filter(Boolean))];
}

function feedbackPersist() {
  try {
    localStorage.setItem(feedbackStorageKey, JSON.stringify({ schedules: feedbackState.schedules, drafts: feedbackState.drafts }));
    return true;
  } catch {
    showNotice("Не удалось сохранить данные на этом устройстве. Скопируйте текст или скачайте файл.", "danger");
    return false;
  }
}

function feedbackSchedule(group) {
  if (!Object.hasOwn(feedbackState.schedules, group)) {
    const student = studentsForCurrentRole().find((item) => studentGroupName(item) === group);
    const names = Object.keys(feedbackState.catalog);
    const course = names.find((name) => name.startsWith(student?.course || "Python Start")) || names[0];
    const today = feedbackToday();
    const weekday = /сб/i.test(group) ? 6 : /вс/i.test(group) ? 0 : new Date(`${today}T12:00:00Z`).getUTCDay();
    const lastDate = feedbackShiftDate(today, -((new Date(`${today}T12:00:00Z`).getUTCDay() - weekday + 7) % 7));
    feedbackState.schedules[group] = { course, mode: "group", rows: feedbackSeries(course,
      feedbackShiftDate(lastDate, -28), 1, 1, feedbackState.catalog[course].length, 7, feedbackState.catalog) };
  }
  return feedbackState.schedules[group];
}

function feedbackSaveDraft(notify = false) {
  window.clearTimeout(feedbackState.autosaveTimer);
  if (!feedbackState.generated || !feedbackState.text.trim()) return false;
  if (feedbackState.text.length > 20000) { showNotice("Текст слишком длинный: максимум 20 000 символов", "danger"); return false; }
  const meta = feedbackState.generated;
  const existing = feedbackState.drafts.find((draft) => meta.rowId
    ? draft.group === meta.group && draft.rowId === meta.rowId
    : !draft.group && draft.course === meta.course && draft.lesson === meta.lesson && draft.date === meta.date && draft.offset === meta.offset);
  const id = feedbackState.draftId || existing?.id || crypto.randomUUID();
  if (!feedbackState.drafts.some((draft) => draft.id === id) && feedbackState.drafts.length >= 100) {
    showNotice("Сохранено 100 черновиков. Удалите ненужный или скачайте текущий текст — старые записи не удаляем.", "danger");
    return false;
  }
  const draft = { ...structuredClone(meta), id, text: feedbackState.text, updatedAt: new Date().toISOString() };
  feedbackState.drafts = [draft, ...feedbackState.drafts.filter((item) => item.id !== id)].slice(0, 100);
  feedbackState.draftId = id;
  const persisted = feedbackPersist();
  const label = qs("#feedbackSaveState");
  if (label) label.textContent = persisted ? "Сохранено на этом устройстве" : "Пока сохранено только в открытой вкладке";
  if (notify && persisted) showNotice("Черновик сохранён на этом устройстве");
  return persisted;
}

function feedbackLoadDraft(draft) {
  Object.assign(feedbackState, structuredClone(draft), {
    generated: structuredClone(draft), draftId: draft.id, edited: true, stale: false,
  });
}

function feedbackSelectGroup(group, rowId = "") {
  feedbackSaveDraft();
  const schedule = feedbackSchedule(group);
  const rows = [...schedule.rows].sort((a, b) => a.date.localeCompare(b.date) || a.number - b.number);
  const row = rows.find((item) => item.id === rowId)
    || [...rows].reverse().find((item) => item.date <= feedbackToday() && !item.skipped)
    || rows.find((item) => !item.skipped) || rows[0];
  Object.assign(feedbackState, {
    group, rowId: row.id, course: schedule.course, lesson: Number(row.lesson), date: row.date,
    offset: Number(row.number) - Number(row.lesson), mode: schedule.mode, absent: [], extraAbsent: "",
    repeat: row.repeat, text: "", draftId: "", generated: null, edited: false, stale: false,
    editor: structuredClone(schedule), editorDirty: false, editorUndo: null,
  });
  const draft = feedbackState.drafts.find((item) => item.group === group && item.rowId === row.id);
  if (draft) {
    // Keep moved lesson settings distinct from the date in an older draft.
    const current = { course: schedule.course, lesson: row.lesson, date: row.date, offset: row.number - row.lesson, repeat: row.repeat, mode: schedule.mode };
    feedbackLoadDraft(draft);
    Object.assign(feedbackState, current);
    feedbackState.stale = Object.keys(current).some((key) => current[key] !== draft[key]);
  }
}

async function renderFeedback() {
  if (!apiContext.feedbackPreview || !["teacher", "admin"].includes(state.role)) return;
  const root = qs("#feedbackWorkspace");
  if (!root) return;
  if (!feedbackState.catalog) {
    if (feedbackState.loading) return;
    feedbackState.loading = true;
    root.innerHTML = '<div class="empty-state compact-empty">Загружаем материалы курсов…</div>';
    try {
      const response = await fetch("/miniapp/static/assets/feedback/courses.json");
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
        const current = localStorage.getItem(feedbackStorageKey);
        const legacy = !current && apiContext.demoRole === "teacher" ? localStorage.getItem("algo-max-feedback-preview-v1") : null;
        saved = JSON.parse(current || legacy || "{}");
      } catch { recovered = true; }
      const restored = feedbackRestore(saved, feedbackState.catalog, feedbackGroups());
      feedbackState.schedules = restored.schedules; feedbackState.drafts = restored.drafts;
      feedbackState.restored = true; feedbackState.error = "";
      if (recovered || restored.recovered) showNotice("Повреждённые записи пропущены. Остальные черновики и настройки сохранены.", "danger");
    } catch (error) {
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
      ${[["groups", "По группам", "users"], ["manual", "Создать вручную", "square-pen"], ["history", "Черновики", "files"]]
        .map(([tab, label, icon]) => `<button id="feedbackTab-${tab}" type="button" role="tab" aria-controls="feedbackTabPanel" aria-selected="${feedbackState.tab === tab}" tabindex="${feedbackState.tab === tab ? 0 : -1}"
          class="${feedbackState.tab === tab ? "is-active" : ""}" data-feedback-tab="${tab}">
          <i data-lucide="${icon}"></i>${label}${tab === "history" ? `<span>${feedbackState.drafts.filter((draft) => !draft.group || groups.includes(draft.group)).length}</span>` : ""}</button>`).join("")}
    </div>
    <div id="feedbackTabPanel" role="tabpanel" aria-labelledby="feedbackTab-${feedbackState.tab}">
    ${feedbackState.tab === "history" ? feedbackHistoryMarkup() : `
      ${feedbackState.tab === "groups" ? feedbackGroupMarkup(groups) : ""}
      <div class="feedback-workspace-grid">
        <form id="feedbackComposeForm" class="feedback-compose-card" novalidate>
          <div class="feedback-card-heading"><span class="feedback-step">1</span><div><h2>Что было на занятии</h2><p>Выберите материал и добавьте детали группы.</p></div></div>
          ${feedbackFormMarkup()}
          <button class="primary-action feedback-generate" type="submit"><i data-lucide="sparkles"></i>Подготовить сообщение</button>
        </form>
        <section class="feedback-output-card" aria-label="Сообщение родителям">
          <div class="feedback-card-heading"><span class="feedback-step">2</span><div><h2>Сообщение родителям</h2><p>Текст можно редактировать; правки сохраняются автоматически.</p></div></div>
          <div class="feedback-output-meta" id="feedbackOutputMeta">${feedbackOutputMeta()}</div>
          <p class="feedback-stale-note" ${feedbackState.stale ? "" : "hidden"}>Параметры изменены. Текст ниже относится к прежнему занятию — подготовьте сообщение заново.</p>
          <label class="feedback-editor-label" for="feedbackText">Текст сообщения</label>
          <textarea id="feedbackText" class="feedback-text" maxlength="20000" placeholder="Здесь появится сообщение о занятии. Его можно отредактировать перед копированием." ${feedbackState.generated ? "" : "disabled"}>${escapeHtml(feedbackState.text)}</textarea>
          <div class="feedback-output-actions"><button class="primary-action" data-feedback-copy type="button" ${feedbackState.text.trim() ? "" : "disabled"}><i data-lucide="copy"></i>Скопировать</button>
            <button class="secondary-action" data-feedback-save type="button" ${feedbackState.text.trim() ? "" : "disabled"}><i data-lucide="bookmark"></i>Сохранить</button>
            <button class="secondary-action" data-feedback-download type="button" ${feedbackState.text.trim() ? "" : "disabled"} aria-label="Скачать сообщение текстовым файлом"><i data-lucide="download"></i></button></div>
          <p id="feedbackSaveState" class="feedback-save-state" role="status" aria-live="polite">${feedbackState.draftId ? "Черновик доступен в истории" : ""}</p>
          <p class="feedback-delivery-note"><i data-lucide="shield-check"></i>Сообщения не отправляются. Вы сами решаете, когда поделиться текстом.</p>
        </section>
      </div>`}
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
  const rows = [...schedule.rows].sort((a, b) => a.date.localeCompare(b.date) || a.number - b.number);
  return `<div class="feedback-group-grid">${groups.map((group) => {
    const config = feedbackSchedule(group);
    const count = studentsForCurrentRole().filter((item) => studentGroupName(item) === group).length;
    return `<button type="button" class="feedback-group-card ${group === feedbackState.group ? "is-active" : ""}" data-feedback-group="${escapeHtml(group)}">
      <span class="feedback-group-icon"><i data-lucide="users"></i></span><span><strong>${escapeHtml(group)}</strong><small>${escapeHtml(config.course)} · учеников: ${count}</small></span><i data-lucide="chevron-right"></i></button>`;
  }).join("")}</div>
    <div class="feedback-week-heading"><h2>Занятия группы</h2><span>${rows.length} занятий · свои даты и материалы</span></div>
    <div class="feedback-weeks">${rows.map((row) => {
      const saved = feedbackState.drafts.some((draft) => draft.group === feedbackState.group && draft.rowId === row.id);
      return `<button type="button" data-feedback-row="${escapeHtml(row.id)}" class="${row.id === feedbackState.rowId ? "is-active" : ""} ${row.skipped ? "is-skipped" : ""}">
        <small>${feedbackDateLabel(row.date)}</small><strong>Занятие ${row.number}</strong>
        <span>${row.skipped ? "Отменено" : saved ? "Черновик сохранён" : row.repeat ? "Повторение" : row.date > feedbackToday() ? "Впереди" : "Можно подготовить"}</span></button>`;
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
  return `${invalid ? '<option value="" selected>Выберите материал</option>' : ""}${lessons.map((lesson, index) => `<option value="${index + 1}" ${index + 1 === Number(selected) ? "selected" : ""}>${escapeHtml(lesson.title)}</option>`).join("")}`;
}

function feedbackScheduleEditorMarkup() {
  const editor = feedbackState.editor || structuredClone(feedbackSchedule(feedbackState.group));
  feedbackState.editor = editor;
  return `<form id="feedbackScheduleForm">
      <div class="feedback-fields-two"><label>Курс группы<select name="course">${feedbackCourseOptions(editor.course)}</select></label>
        <label>Формат<select name="mode"><option value="group" ${editor.mode === "group" ? "selected" : ""}>Группа</option><option value="online" ${editor.mode === "online" ? "selected" : ""}>Онлайн / индивидуально</option></select></label></div>
      <p>Каждая строка — отдельное занятие. Номер в сообщении и материал курса можно выбирать независимо.</p>
      <div class="feedback-schedule-table-wrap"><table class="feedback-schedule-table"><thead><tr><th scope="col">№ занятия</th><th scope="col">Дата</th><th scope="col">Материал курса</th><th scope="col">Повторение</th><th scope="col">Отменено</th><th scope="col"><span class="feedback-editor-label">Действия</span></th></tr></thead>
      <tbody>${editor.rows.map((row) => `<tr data-feedback-schedule-row="${escapeHtml(row.id)}">
        <td><input name="number" type="number" min="1" max="999" step="1" value="${escapeHtml(row.number)}" required aria-label="Номер занятия"></td>
        <td><input name="date" type="date" min="2000-01-01" max="2100-12-31" value="${escapeHtml(row.date)}" required aria-label="Дата занятия ${escapeHtml(row.number)}"></td>
        <td><select name="lesson" required aria-label="Материал занятия ${escapeHtml(row.number)}">${feedbackLessonOptions(editor.course, row.lesson)}</select></td>
        <td><input name="repeat" type="checkbox" ${row.repeat ? "checked" : ""} aria-label="Повторение на занятии ${escapeHtml(row.number)}"></td>
        <td><input name="skipped" type="checkbox" ${row.skipped ? "checked" : ""} aria-label="Отменить занятие ${escapeHtml(row.number)}"></td>
        <td><button class="icon-button" type="button" data-feedback-remove-row="${escapeHtml(row.id)}" aria-label="Удалить занятие ${escapeHtml(row.number)}"><i data-lucide="trash-2"></i></button></td></tr>`).join("")}</tbody></table></div>
      <div class="feedback-schedule-actions"><button class="secondary-action" type="button" data-feedback-add-row><i data-lucide="plus"></i>Добавить занятие</button>
        <button class="secondary-action" type="button" data-feedback-undo ${feedbackState.editorUndo ? "" : "disabled"}><i data-lucide="undo-2"></i>Отменить изменение</button>
        <button class="primary-action" type="submit">Сохранить расписание</button></div>
    </form>
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
  return { course: form.elements.course.value, mode: form.elements.mode.value,
    rows: [...form.querySelectorAll("[data-feedback-schedule-row]")].map((row) => ({
      id: row.dataset.feedbackScheduleRow, number: Number(row.querySelector('[name="number"]').value),
      date: row.querySelector('[name="date"]').value, lesson: Number(row.querySelector('[name="lesson"]').value),
      repeat: row.querySelector('[name="repeat"]').checked, skipped: row.querySelector('[name="skipped"]').checked,
    })) };
}

function feedbackRedrawEditor() {
  qs("#feedbackScheduleEditor").innerHTML = feedbackScheduleEditorMarkup();
  refreshIcons();
}

function feedbackFormMarkup() {
  const lesson = feedbackState.catalog[feedbackState.course]?.[feedbackState.lesson - 1];
  const groupStudents = feedbackState.group ? studentsForCurrentRole().filter((item) => studentGroupName(item) === feedbackState.group) : [];
  return `<label>Курс<select name="course" id="feedbackCourse">${feedbackCourseOptions(feedbackState.course)}</select></label>
    <div class="feedback-fields-two"><label>Материал курса<select name="lesson" id="feedbackLesson">${feedbackLessonOptions(feedbackState.course, feedbackState.lesson)}</select></label>
      <label>Дата занятия<input type="date" name="date" min="2000-01-01" max="2100-12-31" value="${feedbackState.date}" required></label></div>
    <div class="feedback-material"><span><i data-lucide="book-open"></i>Из материалов курса</span><p>${escapeHtml((lesson?.educational_results || "").slice(0, 200))}${(lesson?.educational_results || "").length > 200 ? "…" : ""}</p></div>
    <div class="feedback-attendance"><h3>Кого не было на занятии?</h3><p>Отметьте учеников, которым нужно напомнить об отработке.</p>
      <div class="feedback-student-chips">${groupStudents.map((student) => `<label><input type="checkbox" name="absent" value="${escapeHtml(student.name)}" ${feedbackState.absent.includes(student.name) ? "checked" : ""}><span>${escapeHtml(student.name)}<i data-lucide="check"></i></span></label>`).join("")}</div>
      <label class="feedback-add-names">${groupStudents.length ? "Другие имена" : "Отсутствующие ученики"}<input name="extraAbsent" maxlength="2000" value="${escapeHtml(feedbackState.extraAbsent)}" placeholder="Имена через запятую"></label></div>
    <label class="feedback-checkbox"><input type="checkbox" name="repeat" ${feedbackState.repeat ? "checked" : ""}><span><strong>Повторяли прошлую тему</strong><small>Заменить описание нового материала на текст о повторении.</small></span></label>
    <details class="feedback-advanced"><summary>Дополнительные параметры<i data-lucide="chevron-down"></i></summary>
      <div class="feedback-fields-two"><label>Формат<select name="mode"><option value="group" ${feedbackState.mode === "group" ? "selected" : ""}>Группа</option><option value="online" ${feedbackState.mode === "online" ? "selected" : ""}>Онлайн / индивидуально</option></select></label>
        <label>Смещение номера<input name="offset" type="number" min="-99" max="999" step="1" value="${feedbackState.offset}" required></label></div>
      <p>Меняет номер в сообщении, сохраняя материал курса.</p>
      <label class="feedback-checkbox"><input type="checkbox" name="coins" ${feedbackState.coins ? "checked" : ""}><span><strong>Астрокоины за урок уже начислены</strong><small>Добавить информацию о начислении. Само начисление выполняется в разделе «Начисления».</small></span></label>
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
    offset: Number(values.get("offset")), mode: values.get("mode"), repeat: values.has("repeat"), coins: values.has("coins"),
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
    feedbackState.coins ? `Начислены астрокоины за урок №${String(number).padStart(2, "0")} от ${formattedDate}\nКоличество астрокоинов, а также куда их потратить, можно посмотреть в боте Max\nhttps://max.ru/id525601030904_3_bot` : "",
    "На онлайн-платформе «Алгоритмика» предоставлен весь материал, пройденный на уроках, и прогресс ребенка.", "Удачной недели!"].filter(Boolean).join("\n\n");
}

function feedbackHistoryMarkup() {
  const groups = feedbackGroups();
  const query = feedbackState.historySearch.trim().toLocaleLowerCase("ru-RU");
  const drafts = feedbackState.drafts.filter((draft) => (!draft.group || groups.includes(draft.group))
    && `${draft.group} ${draft.course} ${draft.date} ${draft.text}`.toLocaleLowerCase("ru-RU").includes(query));
  return `<label class="feedback-history-search">Поиск черновика<input id="feedbackHistorySearch" type="search" value="${escapeHtml(feedbackState.historySearch)}" placeholder="Группа, курс, дата или текст"></label>
    <div id="feedbackHistoryList">${drafts.length ? `<div class="feedback-history">${drafts.map((draft) => `
    <article class="feedback-draft-card"><button type="button" class="feedback-draft-open" data-feedback-draft="${escapeHtml(draft.id)}"><span class="feedback-group-icon"><i data-lucide="file-text"></i></span>
      <span><strong>${escapeHtml(draft.group || draft.course)}</strong><small>Урок ${Number(draft.lesson) + Number(draft.offset)} · ${feedbackDateLabel(draft.date)}</small><p>${escapeHtml(draft.text.slice(0, 100))}…</p></span>
      <i data-lucide="chevron-right"></i></button><button class="icon-button" type="button" data-feedback-delete-draft="${escapeHtml(draft.id)}" aria-label="Удалить черновик занятия ${Number(draft.lesson) + Number(draft.offset)}"><i data-lucide="trash-2"></i></button></article>`).join("")}</div>`
    : `<div class="feedback-history-empty"><i data-lucide="files"></i><h2>${query ? "Ничего не найдено" : "Здесь будут ваши черновики"}</h2><p>${query ? "Попробуйте другую группу, дату или слово." : "Подготовьте сообщение — черновик сохранится автоматически."}</p><button class="primary-action" data-feedback-tab="manual">Создать сообщение</button></div>`}</div>`;
}

async function feedbackCanLeaveEditor() {
  if (!feedbackState.editorDirty) return true;
  return requestConfirmation({ title: "Выйти без сохранения расписания?", message: "Изменения дат и уроков ещё не сохранены.", confirmLabel: "Выйти без сохранения", cancelLabel: "Продолжить настройку", destructive: true });
}

document.addEventListener("submit", async (event) => {
  if (!apiContext.feedbackPreview || !event.target.id.startsWith("feedback")) return;
  event.preventDefault();
  try {
    if (event.target.id === "feedbackComposeForm") {
      if (!feedbackReadForm(true)) return;
      const row = feedbackState.group && feedbackSchedule(feedbackState.group).rows.find((item) => item.id === feedbackState.rowId);
      if (row?.skipped) throw new Error("Занятие отмечено отменённым. Сначала измените отметку в расписании.");
      const text = feedbackBuildText();
      if (feedbackState.edited && !await requestConfirmation({ title: "Подготовить текст заново?", message: "Ручные правки в текущем сообщении будут заменены текстом по материалам урока.", confirmLabel: "Подготовить заново", cancelLabel: "Оставить правки" })) return;
      feedbackSaveDraft();
      const keys = ["group", "rowId", "course", "lesson", "date", "offset", "mode", "repeat", "coins", "absent", "extraAbsent"];
      feedbackState.generated = structuredClone(Object.fromEntries(keys.map((key) => [key, feedbackState[key]])));
      feedbackState.text = text; feedbackState.draftId = ""; feedbackState.edited = false; feedbackState.stale = false;
      feedbackSaveDraft(); await renderFeedback();
      if (window.matchMedia("(max-width: 900px)").matches) qs(".feedback-output-card")?.scrollIntoView({ behavior: "smooth", block: "start" });
      showNotice("Сообщение подготовлено. Проверьте текст перед копированием.");
    } else if (event.target.id === "feedbackScheduleForm") {
      if (!event.target.reportValidity()) return;
      const schedule = feedbackCaptureSchedule();
      feedbackValidateSchedule(schedule, feedbackState.catalog);
      feedbackState.schedules[feedbackState.group] = structuredClone(schedule);
      feedbackState.editorDirty = false;
      const rowId = feedbackState.rowId;
      const persisted = feedbackPersist();
      feedbackSelectGroup(feedbackState.group, rowId); await renderFeedback();
      if (persisted) showNotice("Уроки и даты сохранены на этом устройстве");
    } else if (event.target.id === "feedbackSeriesForm") {
      if (!event.target.reportValidity()) return;
      const values = new FormData(event.target);
      const editor = feedbackCaptureSchedule();
      const rows = feedbackSeries(editor.course, values.get("startDate"), values.get("firstLesson"), values.get("firstNumber"), values.get("count"), values.get("interval"), feedbackState.catalog);
      if (!await requestConfirmation({ title: "Заменить таблицу занятий?", message: "Индивидуальные даты и выбранные материалы в таблице будут заменены. Сохранённое расписание изменится только после нажатия «Сохранить расписание».", confirmLabel: "Заполнить таблицу", cancelLabel: "Оставить таблицу" })) return;
      feedbackState.editorUndo = structuredClone(editor); feedbackState.editor = { ...editor, rows }; feedbackState.editorDirty = true; feedbackRedrawEditor();
    }
  } catch (error) { showNotice(error.message, "danger"); }
});

document.addEventListener("change", (event) => {
  if (!apiContext.feedbackPreview) return;
  if (event.target.closest("#feedbackScheduleForm")) {
    feedbackState.editorDirty = true;
    feedbackState.editor = feedbackCaptureSchedule();
    if (event.target.name === "course") {
      feedbackState.editor = feedbackCaptureSchedule(); feedbackRedrawEditor();
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
  if (!apiContext.feedbackPreview) return;
  if (event.target.closest("#feedbackScheduleForm")) {
    feedbackState.editorDirty = true; feedbackState.editor = feedbackCaptureSchedule();
  }
  if (event.target.id === "feedbackText") {
    feedbackState.text = event.target.value; feedbackState.edited = true;
    qsa("[data-feedback-copy], [data-feedback-save], [data-feedback-download]").forEach((button) => { button.disabled = !feedbackState.text.trim(); });
    window.clearTimeout(feedbackState.autosaveTimer);
    feedbackState.autosaveTimer = window.setTimeout(() => feedbackSaveDraft(), 600);
    const label = qs("#feedbackSaveState"); if (label) label.textContent = feedbackState.text.trim() ? "Сохраняем…" : "Пустой текст не сохранён. Предыдущий черновик остался в истории.";
  }
  if (event.target.id === "feedbackHistorySearch") {
    feedbackState.historySearch = event.target.value;
    const markup = document.createElement("div"); markup.innerHTML = feedbackHistoryMarkup();
    qs("#feedbackHistoryList").innerHTML = markup.querySelector("#feedbackHistoryList").innerHTML; refreshIcons();
  }
});

document.addEventListener("click", async (event) => {
  if (!apiContext.feedbackPreview) return;
  const button = event.target.closest("button"); if (!button) return;
  const data = button.dataset;
  try {
    if (data.feedbackTab || data.feedbackGroup || data.feedbackRow || data.feedbackDraft) {
      if (!await feedbackCanLeaveEditor()) return;
      if (feedbackState.editorDirty) {
        feedbackState.editor = feedbackState.group ? structuredClone(feedbackSchedule(feedbackState.group)) : null;
        feedbackState.editorDirty = false;
      }
      feedbackReadForm(); feedbackSaveDraft();
      if (data.feedbackTab) {
        feedbackState.tab = data.feedbackTab;
        if (data.feedbackTab === "manual") {
          feedbackState.group = ""; feedbackState.rowId = ""; feedbackState.editorDirty = false;
          if (feedbackState.generated?.group) { feedbackState.text = ""; feedbackState.generated = null; feedbackState.draftId = ""; feedbackState.edited = false; }
        }
      } else if (data.feedbackGroup) feedbackSelectGroup(data.feedbackGroup);
      else if (data.feedbackRow) feedbackSelectGroup(feedbackState.group, data.feedbackRow);
      else {
        const draft = feedbackState.drafts.find((item) => item.id === data.feedbackDraft);
        if (!draft || (draft.group && !feedbackGroups().includes(draft.group))) return;
        feedbackLoadDraft(draft); feedbackState.tab = "manual"; feedbackState.editorDirty = false;
      }
      await renderFeedback();
    } else if ("feedbackRetry" in data) await renderFeedback();
    else if ("feedbackSave" in data) feedbackSaveDraft(true);
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
      const last = editor.rows.at(-1);
      const number = Math.max(...editor.rows.map((row) => row.number)) + 1;
      if (number > 999) throw new Error("Максимальный номер занятия — 999");
      const date = feedbackShiftDate(last.date, 7);
      const lesson = Math.min(last.lesson + 1, feedbackState.catalog[editor.course].length);
      feedbackState.editorUndo = structuredClone(editor);
      const added = feedbackNewRow(date, lesson, number);
      added.repeat = lesson === last.lesson;
      editor.rows.push(added);
      feedbackState.editor = editor; feedbackState.editorDirty = true; feedbackRedrawEditor();
      const lastInput = qs("#feedbackScheduleForm tbody tr:last-child input"); lastInput?.focus();
    } else if (data.feedbackRemoveRow) {
      const editor = feedbackCaptureSchedule();
      if (editor.rows.length === 1) throw new Error("Оставьте хотя бы одно занятие");
      if (!await requestConfirmation({ title: "Удалить занятие из расписания?", message: "Черновик сообщения сохранится в истории. Вместо удаления можно отметить занятие отменённым.", confirmLabel: "Удалить занятие", cancelLabel: "Оставить", destructive: true })) return;
      feedbackState.editorUndo = structuredClone(editor);
      editor.rows = editor.rows.filter((row) => row.id !== data.feedbackRemoveRow);
      feedbackState.editor = editor; feedbackState.editorDirty = true; feedbackRedrawEditor();
    } else if ("feedbackUndo" in data && feedbackState.editorUndo) {
      const current = feedbackCaptureSchedule(); feedbackState.editor = feedbackState.editorUndo; feedbackState.editorUndo = current;
      feedbackState.editorDirty = true; feedbackRedrawEditor();
    } else if (data.feedbackDeleteDraft) {
      if (!await requestConfirmation({ title: "Удалить черновик?", message: "Сохранённый текст будет удалён с этого устройства.", confirmLabel: "Удалить черновик", cancelLabel: "Оставить", destructive: true })) return;
      feedbackState.drafts = feedbackState.drafts.filter((draft) => draft.id !== data.feedbackDeleteDraft);
      if (feedbackState.draftId === data.feedbackDeleteDraft) { feedbackState.text = ""; feedbackState.generated = null; feedbackState.draftId = ""; }
      if (feedbackPersist()) showNotice("Черновик удалён"); await renderFeedback();
    }
  } catch (error) { showNotice(error.message, "danger"); }
});

document.addEventListener("keydown", (event) => {
  if (!apiContext.feedbackPreview || !event.target.matches("[data-feedback-tab]") || !["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
  event.preventDefault();
  const tabs = qsa("[data-feedback-tab]"); const index = tabs.indexOf(event.target);
  const next = event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
  const tab = tabs[next].dataset.feedbackTab; tabs[next].click();
  window.setTimeout(() => qs(`[data-feedback-tab="${tab}"]`)?.focus(), 0);
});

window.addEventListener("pagehide", () => { if (apiContext.feedbackPreview) feedbackSaveDraft(); });
