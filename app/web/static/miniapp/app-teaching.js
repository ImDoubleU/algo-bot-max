function teachingWorkspace() {
  return state.teachingWorkspace || { courses: [], groups: [], schedules: [], feedback_outputs: [] };
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
  renderScheduleEditor();
  renderScheduleList();
  renderFeedbackHistory();
  renderAttendanceJournal();
}

function formatJournalDate(value) {
  if (!value) return "";
  return new Intl.DateTimeFormat("ru-RU", { day: "2-digit", month: "2-digit" }).format(
    new Date(`${value}T12:00:00`),
  );
}

function formatJournalMonth(value) {
  if (!value) return "";
  return new Intl.DateTimeFormat("ru-RU", { month: "long" }).format(new Date(`${value}T12:00:00`));
}

function dateAfterWeeks(value, weekOffset) {
  const dateValue = new Date(`${value}T12:00:00`);
  dateValue.setDate(dateValue.getDate() + weekOffset * 7);
  return dateValue.toISOString().slice(0, 10);
}

function attendanceMark(student, lessonDate) {
  return student.marks.find((mark) => mark.lesson_date === lessonDate) || null;
}

function attendanceDirtyKey(studentId, lessonDate) {
  return `${studentId}:${lessonDate}`;
}

function attendanceMarkSnapshot(mark) {
  if (!mark) return null;
  return {
    present: mark.present ?? null,
    makeup_completed: Boolean(mark.makeup_completed),
    comment: mark.comment || null,
  };
}

function sameAttendanceMark(left, right) {
  return (
    left?.present === right?.present &&
    Boolean(left?.makeup_completed) === Boolean(right?.makeup_completed) &&
    (left?.comment || null) === (right?.comment || null)
  );
}

function rememberAttendanceChange(student, lessonDate, originalMark) {
  const key = attendanceDirtyKey(student.student_id, lessonDate);
  const mark = attendanceMark(student, lessonDate);
  const pending = state.attendanceDirty.get(key);
  const original = pending ? pending._original : originalMark;
  const current = attendanceMarkSnapshot(mark);
  if (sameAttendanceMark(current, original)) {
    state.attendanceDirty.delete(key);
    return;
  }
  state.attendanceDirty.set(key, {
    student_id: student.student_id,
    lesson_date: lessonDate,
    present: mark?.present ?? null,
    makeup_completed: Boolean(mark?.makeup_completed),
    comment: mark?.comment || null,
    _original: original,
  });
}

function cycleAttendanceStatus(studentId, lessonDate) {
  const student = state.attendanceJournal?.students.find((item) => item.student_id === studentId);
  if (!student) return;
  let mark = attendanceMark(student, lessonDate);
  const originalMark = attendanceMarkSnapshot(mark);
  if (!mark) {
    mark = {
      lesson_date: lessonDate,
      present: true,
      makeup_completed: false,
      comment: null,
    };
    student.marks.push(mark);
  } else if (mark.present === true) {
    mark.present = false;
    mark.makeup_completed = false;
  } else if (!mark.makeup_completed) {
    mark.makeup_completed = true;
  } else {
    student.marks = student.marks.filter((item) => item.lesson_date !== lessonDate);
  }
  rememberAttendanceChange(student, lessonDate, originalMark);
  renderAttendanceJournal();
}

function attendanceChangesCount() {
  return state.attendanceDirty.size + state.attendanceLessonDirty.size;
}

function hasAttendanceChanges() {
  return attendanceChangesCount() > 0;
}

function discardAttendanceJournalChanges() {
  state.attendanceScheduleId = "";
  state.attendanceJournal = null;
  state.attendanceDirty = new Map();
  state.attendanceLessonDirty = new Map();
  state.attendanceAutoScroll = false;
}

function confirmDiscardAttendanceChanges(onDiscard) {
  requestConfirmation({
    eyebrow: "Несохраненные изменения",
    title: "Выйти из журнала?",
    message: "Поставленные отметки и изменения занятий не сохранятся.",
    confirmLabel: "Выйти без сохранения",
    cancelLabel: "Остаться в журнале",
    destructive: true,
  }).then((confirmed) => {
    if (!confirmed) return;
    discardAttendanceJournalChanges();
    onDiscard?.();
  });
}

function openAttendanceLessonEditor(position) {
  const lesson = state.attendanceJournal?.lessons.find(
    (item) => Number(item.position) === Number(position),
  );
  const dialog = qs("#attendanceLessonDialog");
  if (!lesson || !dialog) return;
  dialog.dataset.position = String(lesson.position);
  qs("#attendanceLessonDate").value = lesson.lesson_date;
  qs("#attendanceLessonNumber").value = String(lesson.lesson_number);
  qs("#attendanceLessonDialogTitle").textContent = `Занятие ${lesson.position}`;
  dialog.hidden = false;
  document.body.classList.add("dialog-open");
  qs("#attendanceLessonDate").focus();
}

function closeAttendanceLessonEditor() {
  const dialog = qs("#attendanceLessonDialog");
  if (!dialog || dialog.hidden) return;
  dialog.hidden = true;
  dialog.dataset.position = "";
  syncDialogBodyClass();
}

function applyAttendanceLessonEditor() {
  const dialog = qs("#attendanceLessonDialog");
  const journal = state.attendanceJournal;
  const position = Number(dialog?.dataset.position || 0);
  const lesson = journal?.lessons.find((item) => Number(item.position) === position);
  const lessonDate = qs("#attendanceLessonDate")?.value || "";
  const lessonNumber = Number(qs("#attendanceLessonNumber")?.value || 0);
  if (!dialog || !journal || !lesson) return;
  if (!lessonDate || lessonNumber < 1) {
    showNotice("Укажите дату и номер урока", "danger");
    return;
  }
  const duplicateDate = journal.lessons.some(
    (item) => Number(item.position) !== position && item.lesson_date === lessonDate,
  );
  if (duplicateDate) {
    showNotice("На эту дату уже назначено занятие группы", "danger");
    return;
  }

  const previousDate = lesson.lesson_date;
  const previousNumber = lesson.lesson_number;
  if (previousDate !== lessonDate) {
    journal.students.forEach((student) => {
      const mark = attendanceMark(student, previousDate);
      if (mark) mark.lesson_date = lessonDate;
    });
    [...state.attendanceDirty.entries()].forEach(([key, item]) => {
      if (item.lesson_date !== previousDate) return;
      state.attendanceDirty.delete(key);
      item.lesson_date = lessonDate;
      state.attendanceDirty.set(
        attendanceDirtyKey(item.student_id, lessonDate),
        item,
      );
    });
  }
  lesson.lesson_date = lessonDate;
  lesson.lesson_number = lessonNumber;
  lesson.lesson_title = null;
  lesson.is_future = lessonDate > reportDateValue(new Date());
  journal.lessons.sort((left, right) =>
    `${left.lesson_date}:${left.position}`.localeCompare(`${right.lesson_date}:${right.position}`),
  );
  const pendingLesson = state.attendanceLessonDirty.get(position);
  const originalLessonDate = pendingLesson?._original_lesson_date || previousDate;
  const originalLessonNumber =
    pendingLesson?._original_lesson_number ?? previousNumber;
  if (
    lessonDate === originalLessonDate &&
    lessonNumber === originalLessonNumber
  ) {
    state.attendanceLessonDirty.delete(position);
  } else {
    state.attendanceLessonDirty.set(position, {
      position,
      lesson_date: lessonDate,
      lesson_number: lessonNumber,
      _original_lesson_date: originalLessonDate,
      _original_lesson_number: originalLessonNumber,
    });
  }
  closeAttendanceLessonEditor();
  renderAttendanceJournal();
}

function syncJournalScrollControls(scroll) {
  if (!scroll) return;
  const controls = scroll.previousElementSibling;
  const range = controls?.querySelector("[data-journal-scroll-range]");
  const previousButton = controls?.querySelector('[data-journal-scroll="-1"]');
  const nextButton = controls?.querySelector('[data-journal-scroll="1"]');
  if (!range || !previousButton || !nextButton) return;
  const maximum = Math.max(scroll.scrollWidth - scroll.clientWidth, 0);
  range.disabled = maximum === 0;
  range.value = maximum ? String(Math.round((scroll.scrollLeft / maximum) * 1000)) : "0";
  previousButton.disabled = maximum === 0 || scroll.scrollLeft <= 1;
  nextButton.disabled = maximum === 0 || scroll.scrollLeft >= maximum - 1;
}

function scrollAttendanceJournal(direction) {
  const scroll = qs("#attendanceJournalList .school-journal-scroll");
  if (!scroll) return;
  const distance = Math.max(Math.round(scroll.clientWidth * 0.72), 280);
  scroll.scrollBy({ left: direction * distance, behavior: "smooth" });
}

function attendanceJournalFocusLesson(journal) {
  const lessons = Array.isArray(journal?.lessons) ? journal.lessons : [];
  const configured = lessons.find((lesson) => lesson.is_current)
    || lessons.find(
      (lesson) => Number(lesson.position) === Number(journal?.current_lesson_number),
    );
  if (configured) return configured;
  const ordered = [...lessons].sort((left, right) =>
    `${left.lesson_date}:${left.position}`.localeCompare(`${right.lesson_date}:${right.position}`),
  );
  const today = reportDateValue(new Date());
  return ordered.find((lesson) => lesson.lesson_date >= today)
    || ordered[ordered.length - 1]
    || null;
}

function attendanceJournalFocusLeft(scroll, lessonHeader) {
  const studentHeader = scroll.querySelector("thead .journal-student");
  const studentWidth = studentHeader?.offsetWidth || 0;
  const scrollRect = scroll.getBoundingClientRect();
  const lessonRect = lessonHeader.getBoundingClientRect();
  const desiredLeft = scrollRect.left + studentWidth + 8;
  return Math.max(scroll.scrollLeft + lessonRect.left - desiredLeft, 0);
}

function renderAttendanceJournal() {
  const list = qs("#attendanceJournalList");
  const title = qs("#attendanceJournalTitle");
  const meta = qs("#attendanceJournalMeta");
  const saveButton = qs("#saveAttendanceButton");
  const saveHint = qs("#attendanceSaveHint");
  const closeButton = qs("#closeAttendanceJournalButton");
  const panel = qs("#attendanceJournalPanel");
  if (!list || !title || !meta || !saveButton || !saveHint || !closeButton || !panel) return;
  panel.hidden = !state.attendanceLoading && !state.attendanceJournal;
  list.classList.toggle(
    "is-empty",
    state.attendanceLoading ||
      !state.attendanceJournal ||
      state.attendanceJournal.students.length === 0,
  );
  const previousScroll = list.querySelector(".school-journal-scroll")?.scrollLeft || 0;
  if (state.attendanceLoading) {
    title.textContent = "Открываем журнал";
    meta.textContent = "Загружаем учеников и даты занятий";
    list.innerHTML = '<div class="empty-state">Загружаем журнал...</div>';
    saveButton.hidden = true;
    closeButton.hidden = false;
    return;
  }
  const journal = state.attendanceJournal;
  if (!journal) {
    title.textContent = "Выберите группу";
    meta.textContent = "Посещаемость и отработки";
    list.innerHTML = '<div class="empty-state">Откройте журнал нужной группы.</div>';
    saveButton.hidden = true;
    saveHint.textContent = "";
    closeButton.hidden = true;
    return;
  }
  title.textContent = journal.group_name;
  meta.textContent = `${journal.course_name} · ${journal.lesson_time.slice(0, 5)}`;
  closeButton.hidden = false;
  if (!journal.students.length) {
    list.innerHTML = '<div class="empty-state">В этой группе нет активных учеников.</div>';
    saveButton.hidden = true;
    saveHint.textContent = "";
    return;
  }
  const targetLesson = attendanceJournalFocusLesson(journal);
  const targetPosition = Number(targetLesson?.position || 0);
  const lessonHeaders = journal.lessons
    .map(
      (lesson, index) => {
        const previousLesson = journal.lessons[index - 1];
        const monthChanged = !previousLesson || formatJournalMonth(previousLesson.lesson_date) !== formatJournalMonth(lesson.lesson_date);
        const isTargetLesson = Number(lesson.position) === targetPosition;
        return `
        <th class="journal-date ${isTargetLesson ? "is-current" : ""} ${lesson.is_future ? "is-future" : ""}" data-current-lesson="${isTargetLesson ? "true" : "false"}">
          ${monthChanged ? `<span class="journal-month">${escapeHtml(formatJournalMonth(lesson.lesson_date))}</span>` : ""}
          <button
            class="journal-lesson-edit"
            type="button"
            data-edit-attendance-lesson="${lesson.position}"
            title="Изменить дату и номер урока"
            aria-label="Изменить занятие ${lesson.lesson_number} от ${formatJournalDate(lesson.lesson_date)}"
          >
            <span>${formatJournalDate(lesson.lesson_date)}</span>
            <small>Урок ${lesson.lesson_number}</small>
            <i data-lucide="pencil"></i>
          </button>
        </th>`;
      },
    )
    .join("");
  const studentRows = journal.students
    .map((student) => {
      const cells = journal.lessons
        .map((lesson) => {
          const mark = attendanceMark(student, lesson.lesson_date);
          const disabled = lesson.is_future ? "disabled" : "";
          const status = mark?.present === true
            ? "present"
            : mark?.present === false && mark?.makeup_completed
              ? "makeup"
              : mark?.present === false
                ? "absent"
                : "empty";
          const statusLabel = status === "present"
            ? "Был на уроке"
            : status === "makeup"
              ? "Пропуск отработан"
              : status === "absent"
                ? "Не был на уроке"
                : "Отметка не поставлена";
          return `
            <td class="journal-mark ${mark?.present === true ? "is-present" : ""} ${mark?.present === false ? "is-absent" : ""} ${mark?.makeup_completed ? "has-makeup" : ""}">
              <button
                type="button"
                class="journal-attendance-box is-${status}"
                data-attendance-cycle="true"
                data-student-id="${escapeHtml(student.student_id)}"
                data-lesson-date="${lesson.lesson_date}"
                aria-label="${escapeHtml(student.student_name)}, ${formatJournalDate(lesson.lesson_date)}: ${statusLabel}"
                title="${statusLabel}"
                ${disabled}
              >${status === "makeup" ? '<span aria-hidden="true">✓</span>' : ""}</button>
            </td>`;
        })
        .join("");
      return `<tr><th class="journal-student" scope="row">${escapeHtml(student.student_name)}</th>${cells}</tr>`;
    })
    .join("");
  list.innerHTML = `
    <div class="journal-toolbar">
      <div class="journal-legend">
        <span><b class="legend-present"></b> был</span>
        <span><b class="legend-absent"></b> не был</span>
        <span><b class="legend-makeup">✓</b> отработано</span>
      </div>
      <div class="journal-quick-actions">
        <button type="button" class="secondary-action" data-journal-current><i data-lucide="locate-fixed"></i><span>Текущий урок</span></button>
        ${targetLesson ? `<button type="button" class="secondary-action" data-mark-all-present="${targetLesson.lesson_date}"><i data-lucide="check-check"></i><span>Все были</span></button>` : ""}
      </div>
    </div>
    <div class="journal-swipe-hint"><i data-lucide="move-horizontal"></i><span>Листайте журнал пальцем</span></div>
    <div class="journal-scroll-controls" aria-label="Прокрутка уроков">
      <button type="button" data-journal-scroll="-1" title="Предыдущие уроки" aria-label="Предыдущие уроки">
        <i data-lucide="chevron-left"></i>
      </button>
      <input
        type="range"
        min="0"
        max="1000"
        value="0"
        step="1"
        data-journal-scroll-range="true"
        aria-label="Прокрутить список уроков"
      />
      <button type="button" data-journal-scroll="1" title="Следующие уроки" aria-label="Следующие уроки">
        <i data-lucide="chevron-right"></i>
      </button>
    </div>
    <div class="school-journal-scroll" tabindex="0">
      <table class="school-journal-table">
        <thead><tr><th class="journal-student">Ученик</th>${lessonHeaders}</tr></thead>
        <tbody>${studentRows}</tbody>
      </table>
    </div>`;
  refreshIcons();
  const changeCount = attendanceChangesCount();
  saveButton.hidden = false;
  saveButton.disabled = state.attendanceSaving || changeCount === 0;
  saveButton.textContent = state.attendanceSaving ? "Сохраняем..." : "Сохранить журнал";
  saveHint.textContent = changeCount
    ? `Изменений: ${changeCount}`
    : "Все изменения сохранены";
  requestAnimationFrame(() => {
    const scroll = list.querySelector(".school-journal-scroll");
    if (!scroll) return;
    if (state.attendanceAutoScroll) {
      const current = scroll.querySelector('[data-current-lesson="true"]');
      if (current) {
        scroll.scrollLeft = attendanceJournalFocusLeft(scroll, current);
      }
      state.attendanceAutoScroll = false;
    } else {
      scroll.scrollLeft = previousScroll;
    }
    syncJournalScrollControls(scroll);
    scroll.addEventListener("scroll", () => syncJournalScrollControls(scroll), { passive: true });
  });
}

function scrollJournalToCurrent() {
  const scroll = qs("#attendanceJournalList .school-journal-scroll");
  const current = scroll?.querySelector('[data-current-lesson="true"]');
  if (!scroll || !current) return;
  scroll.scrollTo({
    left: attendanceJournalFocusLeft(scroll, current),
    behavior: "smooth",
  });
}

function markGroupPresent(lessonDate) {
  const journal = state.attendanceJournal;
  if (!journal || !lessonDate) return;
  journal.students.forEach((student) => {
    let mark = attendanceMark(student, lessonDate);
    if (!mark) {
      mark = { lesson_date: lessonDate, present: true, makeup_completed: false, comment: null };
      student.marks.push(mark);
    } else {
      mark.present = true;
      mark.makeup_completed = false;
    }
    rememberAttendanceChange(student, lessonDate);
  });
  renderAttendanceJournal();
  showNotice(`Отмечено присутствие: ${journal.students.length} учен.`, "ok", { duration: 3200 });
}

function demoGroupAttendanceJournal(schedule) {
  const today = reportDateValue(new Date());
  const lessons = Array.from({ length: Math.max(schedule.lesson_count || 1, 1) }, (_, index) => {
    const lessonDate = dateAfterWeeks(schedule.first_lesson_date, index);
    return {
      position: index + 1,
      lesson_date: lessonDate,
      lesson_number: index + 1,
      lesson_title: `Урок ${index + 1}`,
      is_current: index + 1 === schedule.current_lesson_number,
      is_future: lessonDate > today,
    };
  });
  return {
    schedule_id: schedule.id,
    group_name: schedule.group_name,
    course_name: schedule.course_name,
    lesson_time: schedule.lesson_time,
    current_lesson_number: schedule.current_lesson_number,
    lessons,
    students: studentsForGroup(schedule.group_name).map((student) => ({
      student_id: student.id,
      student_name: student.name,
      group_name: schedule.group_name,
      marks: [],
    })),
  };
}

async function loadAttendanceJournal(scheduleId) {
  const schedule = teachingWorkspace().schedules.find((item) => item.id === scheduleId);
  if (!schedule) return;
  if (hasAttendanceChanges() && scheduleId !== state.attendanceScheduleId) {
    showNotice("Сначала сохраните изменения в открытом журнале", "danger");
    return;
  }
  state.attendanceScheduleId = scheduleId;
  state.attendanceJournal = null;
  state.attendanceDirty = new Map();
  state.attendanceLessonDirty = new Map();
  state.attendanceLoading = true;
  state.attendanceAutoScroll = true;
  renderTeaching();
  try {
    if (apiContext.demoMode || !apiContext.maxUserId) {
      state.attendanceJournal = demoGroupAttendanceJournal(schedule);
    } else {
      const params = new URLSearchParams({
        max_user_id: String(apiContext.maxUserId),
        tenant_slug: apiContext.tenantSlug || "",
      });
      const response = await apiFetch(
        `/api/v1/teaching/schedules/${encodeURIComponent(scheduleId)}/journal?${params}`,
      );
      if (!response.ok) throw new Error(await parseApiError(response));
      state.attendanceJournal = await response.json();
    }
  } catch (error) {
    state.attendanceScheduleId = "";
    showNotice(error.message || "Не удалось открыть журнал", "danger");
  } finally {
    state.attendanceLoading = false;
    renderTeaching();
    if (window.matchMedia("(max-width: 960px)").matches) {
      qs("#attendanceJournalPanel")?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }
}

function closeAttendanceJournal() {
  if (hasAttendanceChanges()) {
    confirmDiscardAttendanceChanges(() => {
      renderTeaching();
      qs(".journal-groups-panel")?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
    return;
  }
  discardAttendanceJournalChanges();
  renderTeaching();
  qs(".journal-groups-panel")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function saveAttendanceJournal() {
  const journal = state.attendanceJournal;
  const items = [...state.attendanceDirty.values()].map(
    ({ _original, ...item }) => item,
  );
  const lessons = [...state.attendanceLessonDirty.values()].map(
    ({ _original_lesson_date, _original_lesson_number, ...lesson }) => lesson,
  );
  if (!journal || (!items.length && !lessons.length) || state.attendanceSaving) return;
  state.attendanceSaving = true;
  renderAttendanceJournal();
  try {
    if (!apiContext.demoMode && apiContext.maxUserId) {
      const response = await apiFetch(
        `/api/v1/teaching/schedules/${encodeURIComponent(journal.schedule_id)}/journal`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            max_user_id: Number(apiContext.maxUserId),
            tenant_slug: apiContext.tenantSlug || undefined,
            items,
            lessons,
          }),
        },
      );
      if (!response.ok) throw new Error(await parseApiError(response));
      state.attendanceJournal = await response.json();
    }
    state.attendanceDirty = new Map();
    state.attendanceLessonDirty = new Map();
    showNotice("Журнал сохранен");
  } catch (error) {
    showNotice(error.message || "Не удалось сохранить журнал", "danger");
  } finally {
    state.attendanceSaving = false;
    renderAttendanceJournal();
  }
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
    <div class="schedule-toggle-list">
      <label class="schedule-toggle"><input id="scheduleAutoFeedback" type="checkbox" ${item?.auto_feedback_enabled === false ? "" : "checked"} /><span>Автоматически готовить ОС после занятия</span></label>
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
        <article class="schedule-card ${item.is_active ? "" : "is-paused"} ${state.attendanceScheduleId === item.id ? "is-selected" : ""}">
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
            <button class="primary-action" type="button" data-open-attendance="${escapeHtml(item.id)}">Журнал</button>
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

function renderFeedbackHistory() {
  const list = qs("#feedbackHistory");
  if (!list) return;
  const outputs = teachingWorkspace().feedback_outputs;
  if (outputs.length === 0) return void (list.innerHTML = '<div class="empty-state">Сформированные обратные связи появятся здесь.</div>');
  list.innerHTML = outputs.slice(0, 10).map((item) => `<button class="feedback-history-row" type="button" data-open-feedback="${escapeHtml(item.id)}"><span><strong>${escapeHtml(item.group_name)}</strong><small>${formatTeachingDate(item.lesson_date)} · урок ${item.lesson_number}</small></span><span>›</span></button>`).join("");
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
  const payload = { max_user_id: Number(apiContext.maxUserId || 1), tenant_slug: apiContext.tenantSlug || null, schedule_id: state.editingScheduleId || null, group_name: groupName, course_id: courseId, first_lesson_date: qs("#scheduleFirstDate").value, lesson_time: qs("#scheduleTime").value, duration_minutes: Number(qs("#scheduleDuration").value), lesson_mode: qs("#scheduleMode").value, lesson_place: qs("#schedulePlace").value.trim() || "offline", current_lesson_number: Number(qs("#scheduleLessonNumber").value || 1), lesson_offset: 0, auto_feedback_enabled: qs("#scheduleAutoFeedback").checked, parent_delivery_enabled: false, is_active: true };
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

function openFeedbackDialog(outputId) {
  const output = teachingWorkspace().feedback_outputs.find((item) => item.id === outputId);
  if (!output) return;
  state.generatedFeedback = output.feedback_text || "";
  state.generatedFeedbackId = output.id || "";
  qs("#feedbackDialogTitle").textContent = output.group_name;
  qs("#feedbackDialogContent").innerHTML = `<textarea id="feedbackResult" class="feedback-result" readonly>${escapeHtml(output.feedback_text)}</textarea>`;
  qs("#copyFeedbackButton").hidden = false;
  qs("#feedbackDialog").hidden = false;
}

function closeFeedbackDialog() {
  qs("#feedbackDialog").hidden = true;
  state.generatedFeedback = "";
  state.generatedFeedbackId = "";
}

async function copyGeneratedFeedback() {
  if (!state.generatedFeedback) return;
  const copied = await copyTextToClipboard(state.generatedFeedback);
  showNotice(copied ? "Текст ОС скопирован" : "Не удалось скопировать текст", copied ? "ok" : "danger");
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
