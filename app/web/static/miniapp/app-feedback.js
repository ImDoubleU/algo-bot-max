// Review-only workspace: available on localhost with feedback_preview=1 and demo=1.
const feedbackStorageKey = "algo-max-feedback-preview-v1";
let feedbackStored;
try { feedbackStored = JSON.parse(localStorage.getItem(feedbackStorageKey) || "{}"); }
catch { feedbackStored = {}; }
const feedbackState = {
  tab: "groups", catalog: null, loading: false, error: "", group: "", week: 0,
  course: "", lesson: 1, date: feedbackToday(), offset: 0, mode: "group",
  repeat: false, coins: false, absent: [], extraAbsent: "", text: "", draftId: "",
  schedules: feedbackStored?.schedules || {},
  drafts: Array.isArray(feedbackStored?.drafts) ? feedbackStored.drafts : [],
};

function feedbackToday() {
  return new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Moscow" }).format(new Date());
}

function feedbackShiftDate(value, days) {
  const date = new Date(`${value}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

function feedbackDateLabel(value) {
  return new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long", timeZone: "UTC" })
    .format(new Date(`${value}T12:00:00Z`));
}

function feedbackGroups() {
  return [...new Set(studentsForCurrentRole().map(studentGroupName).filter(Boolean))];
}

function feedbackPersist() {
  try {
    localStorage.setItem(feedbackStorageKey, JSON.stringify({
      schedules: feedbackState.schedules, drafts: feedbackState.drafts,
    }));
    return true;
  } catch {
    showNotice("Не удалось сохранить черновик на этом устройстве. Скопируйте текст.", "danger");
    return false;
  }
}

function feedbackSchedule(group) {
  if (!feedbackState.schedules[group]) {
    const student = studentsForCurrentRole().find((item) => studentGroupName(item) === group);
    const names = Object.keys(feedbackState.catalog || {});
    const course = names.find((name) => name.startsWith(student?.course || "Python Start")) || names[0];
    const today = feedbackToday();
    const weekday = /сб/i.test(group) ? 6 : /вс/i.test(group) ? 0 : new Date(`${today}T12:00:00Z`).getUTCDay();
    const lastDate = feedbackShiftDate(today, -((new Date(`${today}T12:00:00Z`).getUTCDay() - weekday + 7) % 7));
    feedbackState.schedules[group] = { course, anchorDate: lastDate, anchorLesson: 5, offset: 0, mode: "group" };
  }
  return feedbackState.schedules[group];
}

function feedbackSelectGroup(group, week = 0) {
  const schedule = feedbackSchedule(group);
  Object.assign(feedbackState, {
    group, week, course: schedule.course, lesson: Number(schedule.anchorLesson) + week,
    date: feedbackShiftDate(schedule.anchorDate, week * 7), offset: Number(schedule.offset),
    mode: schedule.mode, absent: [], extraAbsent: "", repeat: false, text: "", draftId: "",
  });
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
      feedbackState.catalog = await response.json();
      feedbackState.error = "";
      feedbackState.course = Object.keys(feedbackState.catalog)[0];
    } catch (error) {
      feedbackState.error = error.message;
      root.innerHTML = `<div class="empty-state compact-empty"><span>${escapeHtml(error.message)}</span>
        <button class="secondary-action" data-feedback-retry>Попробовать ещё раз</button></div>`;
      return;
    } finally { feedbackState.loading = false; }
  }
  const groups = feedbackGroups();
  if (feedbackState.tab === "groups" && !groups.includes(feedbackState.group)) {
    if (groups[0]) feedbackSelectGroup(groups[0]);
    else feedbackState.tab = "manual";
  }
  root.innerHTML = `
    <div class="feedback-tabs" role="tablist" aria-label="Обратная связь">
      ${[["groups", "По группам", "users"], ["manual", "Создать вручную", "square-pen"], ["history", "Черновики", "files"]]
        .map(([tab, label, icon]) => `<button type="button" role="tab" aria-selected="${feedbackState.tab === tab}"
          class="${feedbackState.tab === tab ? "is-active" : ""}" data-feedback-tab="${tab}">
          <i data-lucide="${icon}"></i>${label}${tab === "history" ? `<span>${feedbackState.drafts.length}</span>` : ""}</button>`).join("")}
    </div>
    ${feedbackState.tab === "history" ? feedbackHistoryMarkup() : `
      ${feedbackState.tab === "groups" ? feedbackGroupMarkup(groups) : ""}
      <div class="feedback-workspace-grid">
        <form id="feedbackComposeForm" class="feedback-compose-card">
          <div class="feedback-card-heading"><span class="feedback-step">1</span><div><h2>Что было на занятии</h2><p>Выберите материал и добавьте детали группы.</p></div></div>
          ${feedbackFormMarkup()}
          <button class="primary-action feedback-generate" type="submit"><i data-lucide="sparkles"></i>Подготовить сообщение</button>
        </form>
        <section class="feedback-output-card" aria-label="Сообщение родителям">
          <div class="feedback-card-heading"><span class="feedback-step">2</span><div><h2>Сообщение родителям</h2><p>Проверьте текст и добавьте свои наблюдения.</p></div></div>
          <div class="feedback-output-meta" id="feedbackOutputMeta">${feedbackOutputMeta()}</div>
          <label class="feedback-editor-label" for="feedbackText">Текст сообщения</label>
          <textarea id="feedbackText" class="feedback-text" placeholder="Здесь появится сообщение о занятии. Его можно отредактировать перед копированием." ${feedbackState.text ? "" : "disabled"}>${escapeHtml(feedbackState.text)}</textarea>
          <div class="feedback-output-actions"><button class="primary-action" data-feedback-copy type="button" ${feedbackState.text ? "" : "disabled"}><i data-lucide="copy"></i>Скопировать</button>
            <button class="secondary-action" data-feedback-save type="button" ${feedbackState.text ? "" : "disabled"}><i data-lucide="bookmark"></i>Сохранить черновик</button></div>
          <p class="feedback-delivery-note"><i data-lucide="shield-check"></i>Сообщения не отправляются. Вы сами решаете, когда поделиться текстом.</p>
        </section>
      </div>`}
  `;
  refreshIcons();
  const weeks = qs(".feedback-weeks");
  const selectedWeek = weeks?.querySelector(".is-active");
  if (weeks && selectedWeek && weeks.scrollWidth > weeks.clientWidth) {
    weeks.scrollLeft = selectedWeek.offsetLeft - weeks.offsetLeft
      - (weeks.clientWidth - selectedWeek.offsetWidth) / 2;
  }
}

function feedbackOutputMeta() {
  return feedbackState.text
    ? `<span class="feedback-ready-dot"></span>Урок ${Number(feedbackState.lesson) + Number(feedbackState.offset)} · ${feedbackDateLabel(feedbackState.date)}`
    : '<span class="feedback-empty-dot"></span>Текст ещё не подготовлен';
}

function feedbackGroupMarkup(groups) {
  const schedule = feedbackSchedule(feedbackState.group);
  return `<div class="feedback-group-grid">${groups.map((group) => {
    const config = feedbackSchedule(group);
    const count = studentsForCurrentRole().filter((item) => studentGroupName(item) === group).length;
    return `<button type="button" class="feedback-group-card ${group === feedbackState.group ? "is-active" : ""}" data-feedback-group="${escapeHtml(group)}">
      <span class="feedback-group-icon"><i data-lucide="users"></i></span><span><strong>${escapeHtml(group)}</strong><small>${escapeHtml(config.course)} · учеников: ${count}</small></span>
      <i data-lucide="chevron-right"></i></button>`;
  }).join("")}</div>
    <div class="feedback-week-heading"><h2>Занятия группы</h2><span>Выберите неделю</span></div>
    <div class="feedback-weeks">${[-2, -1, 0, 1, 2].map((week) => {
      const number = Number(schedule.anchorLesson) + week;
      const date = feedbackShiftDate(schedule.anchorDate, week * 7);
      const valid = number >= 1 && number <= (feedbackState.catalog[schedule.course]?.length || 0);
      const saved = feedbackState.drafts.some((draft) => draft.group === feedbackState.group && draft.date === date);
      return `<button type="button" data-feedback-week="${week}" class="${week === feedbackState.week ? "is-active" : ""}" ${valid ? "" : "disabled"}>
        <small>${week === 0 ? "Опорное занятие" : feedbackDateLabel(date)}</small><strong>Урок ${number + Number(schedule.offset)}</strong>
        <span>${saved ? "Черновик сохранён" : date > feedbackToday() ? "Впереди" : "Можно подготовить"}</span></button>`;
    }).join("")}</div>
    <details class="feedback-schedule-settings"><summary><i data-lucide="sliders-horizontal"></i>Настроить последовательность занятий</summary>
      <form id="feedbackScheduleForm"><label>Курс<select name="course">${feedbackCourseOptions(schedule.course)}</select></label>
        <label>Опорная дата<input name="anchorDate" type="date" value="${schedule.anchorDate}" required></label>
        <label>Урок в эту дату<input name="anchorLesson" type="number" min="1" max="${feedbackState.catalog[schedule.course].length}" value="${schedule.anchorLesson}" required></label>
        <label>Смещение номера<input name="offset" type="number" min="-99" max="99" value="${schedule.offset}" required></label>
        <label>Формат<select name="mode"><option value="group" ${schedule.mode === "group" ? "selected" : ""}>Группа</option><option value="online" ${schedule.mode === "online" ? "selected" : ""}>Онлайн / индивидуально</option></select></label>
        <button class="secondary-action" type="submit">Сохранить настройки</button>
      </form><p>Номер урока меняется на один каждую неделю от опорной даты. Настройки сохраняются на этом устройстве.</p>
    </details>`;
}

function feedbackCourseOptions(selected) {
  return Object.keys(feedbackState.catalog).map((course) => `<option value="${escapeHtml(course)}" ${course === selected ? "selected" : ""}>${escapeHtml(course)}</option>`).join("");
}

function feedbackFormMarkup() {
  const lessons = feedbackState.catalog[feedbackState.course] || [];
  const lesson = lessons[feedbackState.lesson - 1];
  const groupStudents = feedbackState.group
    ? studentsForCurrentRole().filter((item) => studentGroupName(item) === feedbackState.group) : [];
  return `<label>Курс<select name="course" id="feedbackCourse">${feedbackCourseOptions(feedbackState.course)}</select></label>
    <div class="feedback-fields-two"><label>Урок<select name="lesson" id="feedbackLesson">${lessons.map((item, index) => `<option value="${index + 1}" ${index + 1 === Number(feedbackState.lesson) ? "selected" : ""}>${escapeHtml(item.title)}</option>`).join("")}</select></label>
      <label>Дата занятия<input type="date" name="date" value="${feedbackState.date}" required></label></div>
    <div class="feedback-material"><span><i data-lucide="book-open"></i>Из материалов курса</span><p>${escapeHtml((lesson?.educational_results || "").slice(0, 200))}${(lesson?.educational_results || "").length > 200 ? "…" : ""}</p></div>
    <div class="feedback-attendance"><h3>Кого не было на занятии?</h3><p>Отметьте учеников, которым нужно напомнить об отработке.</p>
      <div class="feedback-student-chips">${groupStudents.map((student) => `<label><input type="checkbox" name="absent" value="${escapeHtml(student.name)}" ${feedbackState.absent.includes(student.name) ? "checked" : ""}><span>${escapeHtml(student.name)}<i data-lucide="check"></i></span></label>`).join("")}</div>
      <label class="feedback-add-names">${groupStudents.length ? "Другие имена" : "Отсутствующие ученики"}<input name="extraAbsent" value="${escapeHtml(feedbackState.extraAbsent)}" placeholder="Имена через запятую"></label></div>
    <label class="feedback-checkbox"><input type="checkbox" name="repeat" ${feedbackState.repeat ? "checked" : ""}><span><strong>Повторяли прошлую тему</strong><small>Заменить описание нового материала на текст о повторении.</small></span></label>
    <details class="feedback-advanced"><summary>Дополнительные параметры<i data-lucide="chevron-down"></i></summary>
      <div class="feedback-fields-two"><label>Формат<select name="mode"><option value="group" ${feedbackState.mode === "group" ? "selected" : ""}>Группа</option><option value="online" ${feedbackState.mode === "online" ? "selected" : ""}>Онлайн / индивидуально</option></select></label>
        <label>Смещение номера<input name="offset" type="number" min="-99" max="99" value="${feedbackState.offset}" required></label></div>
      <p>Меняет номер в сообщении, но сохраняет выбранный материал урока.</p>
      <label class="feedback-checkbox"><input type="checkbox" name="coins" ${feedbackState.coins ? "checked" : ""}><span><strong>Астрокоины за урок уже начислены</strong><small>Добавить информацию о начислении. Само начисление выполняется в разделе «Начисления».</small></span></label>
    </details>`;
}

function feedbackReadForm() {
  const form = qs("#feedbackComposeForm");
  if (!form || !form.reportValidity()) return false;
  const values = new FormData(form);
  Object.assign(feedbackState, {
    course: values.get("course"), lesson: Number(values.get("lesson")), date: values.get("date"),
    offset: Number(values.get("offset")), mode: values.get("mode"), repeat: values.has("repeat"),
    coins: values.has("coins"), absent: values.getAll("absent"), extraAbsent: values.get("extraAbsent").trim(),
  });
  return true;
}

function feedbackBuildText() {
  const lesson = feedbackState.catalog[feedbackState.course]?.[feedbackState.lesson - 1];
  const number = feedbackState.lesson + feedbackState.offset;
  if (!lesson || number < 1) throw new Error("Номер урока в сообщении должен быть больше нуля");
  const formattedDate = feedbackState.date.split("-").reverse().join(".");
  const hour = Number(new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/Moscow", hour: "2-digit", hourCycle: "h23" }).format(new Date()));
  const greeting = hour >= 6 && hour < 12 ? "Доброе утро" : hour >= 12 && hour < 18 ? "Добрый день" : "Добрый вечер";
  const names = [...new Set([...feedbackState.absent, ...feedbackState.extraAbsent.split(",").map((name) => name.trim()).filter(Boolean)])];
  const absentNames = names.length < 2 ? names.join("") : `${names.slice(0, -1).join(", ")} и ${names.at(-1)}`;
  const educational = feedbackState.repeat
    ? "Сегодня мы с ребятами повторяли тему предыдущего занятия, чтобы укрепить знания по ней."
    : lesson.educational_results;
  const absentText = names.length
    ? feedbackState.mode === "online"
      ? `${absentNames}, свяжитесь с преподавателем, чтобы договориться об отработке пропущенного занятия.`
      : `${absentNames}, ждем на отработке за 30 минут до начала следующего занятия.`
    : "";
  return [
    `Обратная связь урок №${String(number).padStart(2, "0")} от ${formattedDate}`,
    `${greeting}, уважаемые родители!`, educational, absentText,
    feedbackState.coins ? `Начислены астрокоины за урок №${String(number).padStart(2, "0")} от ${formattedDate}\nКоличество астрокоинов, а также куда их потратить, можно посмотреть в боте Max\nhttps://max.ru/id525601030904_3_bot` : "",
    "На онлайн-платформе «Алгоритмика» предоставлен весь материал, пройденный на уроках, и прогресс ребенка.",
    "Удачной недели!",
  ].filter(Boolean).join("\n\n");
}

function feedbackHistoryMarkup() {
  const groups = feedbackGroups();
  const drafts = feedbackState.drafts.filter((draft) => !draft.group || groups.includes(draft.group));
  return drafts.length ? `<div class="feedback-history">${drafts.map((draft) => `
    <button type="button" class="feedback-draft-card" data-feedback-draft="${escapeHtml(draft.id)}"><span class="feedback-group-icon"><i data-lucide="file-text"></i></span>
      <span><strong>${escapeHtml(draft.group || draft.course)}</strong><small>Урок ${draft.lesson + draft.offset} · ${feedbackDateLabel(draft.date)}</small><p>${escapeHtml(draft.text.slice(0, 100))}…</p></span>
      <span class="feedback-draft-label">Черновик<i data-lucide="chevron-right"></i></span></button>`).join("")}</div>`
    : '<div class="feedback-history-empty"><i data-lucide="files"></i><h2>Здесь будут ваши черновики</h2><p>Подготовьте сообщение и сохраните его, чтобы вернуться к тексту позже.</p><button class="primary-action" data-feedback-tab="manual">Создать сообщение</button></div>';
}

document.addEventListener("submit", (event) => {
  if (!apiContext.feedbackPreview) return;
  if (event.target.id === "feedbackComposeForm") {
    event.preventDefault();
    if (!feedbackReadForm()) return;
    try {
      feedbackState.text = feedbackBuildText(); feedbackState.draftId = "";
      void renderFeedback();
      if (window.matchMedia("(max-width: 900px)").matches) {
        qs(".feedback-output-card")?.scrollIntoView({ behavior: "smooth", block: "start" });
      }
      showNotice("Сообщение подготовлено. Проверьте текст перед копированием.");
    } catch (error) { showNotice(error.message, "danger"); }
  }
  if (event.target.id === "feedbackScheduleForm") {
    event.preventDefault();
    const form = event.target;
    if (!form.reportValidity()) return;
    const values = new FormData(form);
    const number = Number(values.get("anchorLesson"));
    const course = values.get("course");
    const offset = Number(values.get("offset"));
    if (number > feedbackState.catalog[course].length || number + offset < 1) {
      showNotice("Проверьте номер урока и смещение для выбранного курса", "danger"); return;
    }
    feedbackState.schedules[feedbackState.group] = {
      course, anchorLesson: number, anchorDate: values.get("anchorDate"), offset, mode: values.get("mode"),
    };
    feedbackSelectGroup(feedbackState.group);
    if (feedbackPersist()) showNotice("Последовательность занятий сохранена на этом устройстве");
    void renderFeedback();
  }
});

document.addEventListener("change", (event) => {
  if (!apiContext.feedbackPreview) return;
  if (event.target.matches('#feedbackScheduleForm [name="course"]')) {
    const lessonInput = qs('#feedbackScheduleForm [name="anchorLesson"]');
    lessonInput.max = feedbackState.catalog[event.target.value].length;
  }
  if (["feedbackCourse", "feedbackLesson"].includes(event.target.id)) {
    feedbackReadForm();
    if (event.target.id === "feedbackCourse") feedbackState.lesson = 1;
    feedbackState.text = ""; feedbackState.draftId = "";
    void renderFeedback();
  }
});

document.addEventListener("input", (event) => {
  if (event.target.id === "feedbackText" && apiContext.feedbackPreview) feedbackState.text = event.target.value;
});

document.addEventListener("click", async (event) => {
  if (!apiContext.feedbackPreview) return;
  const button = event.target.closest("button");
  if (!button) return;
  const data = button.dataset;
  if (data.feedbackTab) {
    feedbackReadForm(); feedbackState.tab = data.feedbackTab;
    if (data.feedbackTab === "manual") feedbackState.group = "";
    await renderFeedback();
  } else if (data.feedbackGroup) {
    feedbackSelectGroup(data.feedbackGroup); await renderFeedback();
  } else if ("feedbackWeek" in data) {
    feedbackSelectGroup(feedbackState.group, Number(data.feedbackWeek)); await renderFeedback();
  } else if (data.feedbackDraft) {
    const draft = feedbackState.drafts.find((item) => item.id === data.feedbackDraft);
    if (!draft) return;
    Object.assign(feedbackState, draft, { tab: "manual", draftId: draft.id });
    await renderFeedback();
  } else if ("feedbackRetry" in data) {
    await renderFeedback();
  } else if ("feedbackSave" in data) {
    if (!feedbackState.text.trim()) { showNotice("Черновик не может быть пустым", "danger"); return; }
    const id = feedbackState.draftId || crypto.randomUUID();
    const draft = Object.fromEntries(["group", "course", "lesson", "date", "offset", "mode", "repeat", "coins", "absent", "extraAbsent", "text"].map((key) => [key, feedbackState[key]]));
    Object.assign(draft, { id, updatedAt: new Date().toISOString() });
    feedbackState.drafts = [draft, ...feedbackState.drafts.filter((item) => item.id !== id)].slice(0, 100);
    feedbackState.draftId = id;
    if (feedbackPersist()) showNotice("Черновик сохранён на этом устройстве");
    await renderFeedback();
  } else if ("feedbackCopy" in data) {
    if (!feedbackState.text.trim()) return;
    try { await navigator.clipboard.writeText(feedbackState.text); showNotice("Сообщение скопировано"); }
    catch { qs("#feedbackText")?.focus(); qs("#feedbackText")?.select(); showNotice("Выделили текст — скопируйте его вручную"); }
  }
});
