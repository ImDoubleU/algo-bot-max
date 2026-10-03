// Pure validation and schedule helpers for the local feedback workspace.
function feedbackValidDate(value) {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  if (value < "2000-01-01" || value > "2100-12-31") return false;
  const date = new Date(`${value}T12:00:00Z`);
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value;
}

function feedbackInteger(value, min, max, label) {
  const number = Number(value);
  if (!["number", "string"].includes(typeof value) || String(value).trim() === ""
    || !Number.isSafeInteger(number) || number < min || number > max) {
    throw new Error(`Проверьте поле «${label}»`);
  }
  return number;
}

function feedbackValidateMessage(input, catalog) {
  if (!input || typeof input !== "object" || !Object.hasOwn(catalog, input.course)) {
    throw new Error("Выберите курс из списка");
  }
  const lesson = feedbackInteger(input.lesson, 1, catalog[input.course].length, "Материал урока");
  const offset = feedbackInteger(input.offset, -99, 999, "Смещение номера");
  const number = lesson + offset;
  if (!Number.isSafeInteger(number) || number < 1 || number > 999) throw new Error("Номер занятия должен быть от 1 до 999");
  if (!feedbackValidDate(input.date)) throw new Error("Укажите существующую дату занятия с 2000 по 2100 год");
  if (!["group", "online"].includes(input.mode)) throw new Error("Выберите формат занятия");
  return { lesson, offset, number };
}

function feedbackUniqueNames(values) {
  const names = new Map();
  for (const value of values) {
    if (typeof value !== "string") continue;
    const name = value.normalize("NFC").trim().replace(/\s+/g, " ").slice(0, 120);
    if (name) names.set(name.toLocaleLowerCase("ru-RU"), names.get(name.toLocaleLowerCase("ru-RU")) || name);
  }
  return [...names.values()].slice(0, 100);
}

function feedbackNewRow(date, lesson, number = lesson) {
  return { id: crypto.randomUUID(), date, lesson, number, repeat: false, skipped: false };
}

function feedbackGroupOrder(group) {
  const day = /(?:^|[\s,])(пн|вт|ср|чт|пт|сб|вс)(?:[\s,]|$)/i.exec(group);
  const time = /(?:^|\s)(\d{1,2})[:\-](\d{2})(?:\s|$)/.exec(group);
  return [(day ? ["пн", "вт", "ср", "чт", "пт", "сб", "вс"].indexOf(day[1].toLowerCase()) : 7),
    time ? Number(time[1]) * 60 + Number(time[2]) : 1440];
}

function feedbackRenumber(rows, firstNumber = 1) {
  let number = firstNumber;
  for (const row of rows) if (!row.skipped) row.number = number++;
  if (number > 1000) throw new Error("Максимальный номер занятия — 999");
}

function feedbackRebaseSchedule(schedule, date) {
  if (!feedbackValidDate(date)) throw new Error("Укажите дату первого занятия");
  const result = structuredClone(schedule);
  const first = result.rows.find((row) => !row.skipped);
  const days = Math.round((new Date(`${date}T12:00:00Z`) - new Date(`${first.date}T12:00:00Z`)) / 86400000);
  result.rows.forEach((row) => { row.date = feedbackShiftDate(row.date, days); });
  return result;
}

function feedbackInsertRepeat(schedule, rowId) {
  const result = structuredClone(schedule);
  if (result.rows.length >= 100) throw new Error("Максимум 100 занятий в расписании");
  const index = result.rows.findIndex((row) => row.id === rowId && !row.skipped);
  if (index < 0) throw new Error("Выберите включённое занятие для повторения");
  const firstNumber = result.rows.find((row) => !row.skipped).number;
  const source = result.rows[index];
  const added = feedbackNewRow(feedbackShiftDate(source.date, 7), source.lesson);
  added.repeat = true;
  result.rows.slice(index + 1).forEach((row) => { row.date = feedbackShiftDate(row.date, 7); });
  result.rows.splice(index + 1, 0, added);
  feedbackRenumber(result.rows, firstNumber);
  return result;
}

function feedbackToggleLesson(schedule, rowId, skipped) {
  const result = structuredClone(schedule);
  const index = result.rows.findIndex((row) => row.id === rowId);
  if (index < 0) throw new Error("Занятие не найдено");
  if (result.rows[index].skipped === skipped) return result;
  const firstNumber = result.rows.find((row) => !row.skipped)?.number || 1;
  result.rows[index].skipped = skipped;
  if (result.rows.every((row) => row.skipped)) throw new Error("Оставьте включённым хотя бы одно занятие");
  result.rows.slice(index + 1).forEach((row) => { row.date = feedbackShiftDate(row.date, skipped ? -7 : 7); });
  feedbackRenumber(result.rows, firstNumber);
  return result;
}

function feedbackSeries(course, startDate, firstLesson, firstNumber, count, interval, catalog) {
  if (!Object.hasOwn(catalog, course)) throw new Error("Выберите курс из списка");
  if (!feedbackValidDate(startDate)) throw new Error("Укажите существующую дату первого занятия");
  const first = feedbackInteger(firstLesson, 1, catalog[course].length, "Первый материал");
  const number = feedbackInteger(firstNumber, 1, 999, "Первый номер");
  const total = feedbackInteger(count, 1, 100, "Количество занятий");
  const step = feedbackInteger(interval, 1, 60, "Интервал в днях");
  if (first + total - 1 > catalog[course].length || number + total - 1 > 999) {
    throw new Error("Количество занятий выходит за пределы курса или нумерации");
  }
  return Array.from({ length: total }, (_, index) => {
    const date = new Date(`${startDate}T12:00:00Z`);
    date.setUTCDate(date.getUTCDate() + index * step);
    const value = date.toISOString().slice(0, 10);
    if (!feedbackValidDate(value)) throw new Error("Последняя дата выходит за допустимый диапазон");
    return feedbackNewRow(value, first + index, number + index);
  });
}

function feedbackValidateSchedule(schedule, catalog) {
  if (!schedule || !Object.hasOwn(catalog, schedule.course)) throw new Error("Выберите курс расписания");
  if (!["group", "online"].includes(schedule.mode)) throw new Error("Выберите формат группы");
  if (!Array.isArray(schedule.rows) || !schedule.rows.length || schedule.rows.length > 100) {
    throw new Error("В расписании должно быть от 1 до 100 занятий");
  }
  const ids = new Set();
  const numbers = new Set();
  for (const row of schedule.rows) {
    if (!row || typeof row.id !== "string" || !row.id || ids.has(row.id)) throw new Error("Занятия должны иметь разные идентификаторы");
    ids.add(row.id);
    const number = feedbackInteger(row.number, 1, 999, "Номер занятия");
    feedbackInteger(row.lesson, 1, catalog[schedule.course].length, "Материал урока");
    if (!row.skipped && numbers.has(number)) throw new Error(`Номер занятия ${number} повторяется. Укажите разные номера.`);
    if (!row.skipped) numbers.add(number);
    if (!feedbackValidDate(row.date)) throw new Error(`Проверьте дату занятия №${number}`);
    if (typeof row.repeat !== "boolean" || typeof row.skipped !== "boolean") throw new Error("Проверьте отметки повторения и отмены");
  }
  if (schedule.rows.every((row) => row.skipped)) throw new Error("Оставьте включённым хотя бы одно занятие");
  return true;
}

function feedbackRestore(raw, catalog, groups) {
  const restored = { schedules: Object.create(null), drafts: [], recovered: 0 };
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) { restored.recovered += 1; return restored; }
  const schedules = raw.schedules && typeof raw.schedules === "object" && !Array.isArray(raw.schedules) ? raw.schedules : {};
  if (raw.schedules && schedules !== raw.schedules) restored.recovered += 1;
  if (raw.drafts && !Array.isArray(raw.drafts)) restored.recovered += 1;
  for (const group of groups) {
    if (!Object.hasOwn(schedules, group)) continue;
    const saved = schedules[group];
    try {
      let schedule;
      if (Array.isArray(saved?.rows)) {
        schedule = { course: saved.course, mode: saved.mode, rows: saved.rows.map((row) => ({
          id: row.id, date: row.date, lesson: Number(row.lesson), number: Number(row.number),
          repeat: row.repeat, skipped: row.skipped,
        })) };
      } else {
        // Preserve valid settings from the first preview when migrating.
        const anchor = feedbackInteger(saved.anchorLesson, 1, catalog[saved.course]?.length || 0, "Опорный урок");
        const offset = feedbackInteger(saved.offset, -99, 99, "Смещение");
        const first = Math.max(1, 1 - offset);
        const date = new Date(`${saved.anchorDate}T12:00:00Z`);
        if (!feedbackValidDate(saved.anchorDate)) throw new Error("Некорректная дата");
        date.setUTCDate(date.getUTCDate() - (anchor - first) * 7);
        schedule = { course: saved.course, mode: saved.mode, rows: feedbackSeries(saved.course,
          date.toISOString().slice(0, 10), first, first + offset, catalog[saved.course].length - first + 1, 7, catalog) };
      }
      feedbackValidateSchedule(schedule, catalog);
      restored.schedules[group] = schedule;
    } catch { restored.recovered += 1; }
  }
  const seen = new Set();
  for (const value of (Array.isArray(raw.drafts) ? raw.drafts : []).slice(0, 100)) {
    try {
      const validated = feedbackValidateMessage(value, catalog);
      if (typeof value.id !== "string" || !value.id || seen.has(value.id)) throw new Error();
      if (typeof value.text !== "string" || !value.text.trim() || value.text.length > 20000) throw new Error();
      if (typeof value.group !== "string" || (value.group && !groups.includes(value.group))) continue;
      const draft = { id: value.id, group: value.group, course: value.course, lesson: validated.lesson,
        offset: validated.offset, date: value.date, mode: value.mode, text: value.text,
        repeat: value.repeat === true, coins: value.coins === true,
        absent: feedbackUniqueNames(Array.isArray(value.absent) ? value.absent : []),
        extraAbsent: typeof value.extraAbsent === "string" ? value.extraAbsent.slice(0, 2000) : "",
        rowId: typeof value.rowId === "string" ? value.rowId : "",
        updatedAt: feedbackValidDate(String(value.updatedAt).slice(0, 10)) ? value.updatedAt : new Date().toISOString() };
      restored.drafts.push(draft); seen.add(value.id);
    } catch { restored.recovered += 1; }
  }
  return restored;
}
