// Pure validation and schedule helpers for the local feedback workspace.
function feedbackResolveCourse(value, catalog) {
  const aliases = {
    "Python Start 1 год": "Питон Старт 1-й год",
    "Python Start 2 год": "Питон Старт 2-й год",
    "Питон Старт 2й год": "Питон Старт 2-й год",
    "Python Pro 1 год": "Питон Профессиональный 1-й год",
    "Python Pro 2 год": "Питон Профессиональный 2-й год",
    "Геймдизайн NEW": "Геймдизайн",
    "Геймдизайн OLD": "Геймдизайн",
    "Создание сайтов": "Создание веб-сайтов",
    "ОЛИП": "Основы логики и программирования",
    "Визуальное программирование 1 год": "Визуальное программирование",
  };
  const normalize = (name) => String(name || "").normalize("NFC").trim().replace(/\s+/g, " ").toLocaleLowerCase("ru-RU");
  const name = normalize(value);
  const alias = Object.keys(aliases).find((item) => normalize(item) === name);
  return Object.keys(catalog).find((item) => normalize(item) === normalize(alias ? aliases[alias] : value)) || "";
}

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
  if (input?.customTopic) throw new Error("Для занятия со своей темой сообщение вводится вручную");
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

function feedbackMarkRepeats(schedule) {
  const seen = new Set();
  for (const row of schedule.rows) {
    row.repeat = row.lesson != null && seen.has(row.lesson);
    if (row.lesson != null) seen.add(row.lesson);
  }
  return schedule;
}

function feedbackChangeCourse(schedule, course, catalog) {
  if (!Object.hasOwn(catalog, course)) throw new Error("Выберите курс из списка");
  const result = structuredClone(schedule);
  result.course = course;
  const count = catalog[course].length;
  result.rows = result.rows.filter((row) => row.lesson == null || (Number.isInteger(row.lesson) && row.lesson >= 1 && row.lesson <= count));
  const custom = result.rows.filter((row) => row.lesson == null);
  result.rows = result.rows.filter((row) => row.lesson != null);
  const present = new Set(result.rows.map((row) => row.lesson));
  let date = result.rows.at(-1)?.date || schedule.rows.find((row) => !row.skipped)?.date || feedbackToday();
  for (let lesson = 1; lesson <= count; lesson++) {
    if (present.has(lesson)) continue;
    if (result.rows.length) date = feedbackShiftDate(date, 7);
    result.rows.push(feedbackNewRow(date, lesson));
  }
  for (const row of custom) { row.date = feedbackShiftDate(result.rows.at(-1).date, 7); result.rows.push(row); }
  if (result.rows.every((row) => row.skipped)) result.rows[0].skipped = false;
  feedbackRenumber(result.rows, schedule.rows.find((row) => !row.skipped)?.number || 1);
  feedbackMarkRepeats(result);
  feedbackValidateSchedule(result, catalog);
  return result;
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
  const index = result.rows.findIndex((row) => row.id === rowId && !row.skipped && row.lesson != null);
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

function feedbackAppendLesson(schedule) {
  if (schedule.rows.length >= 100) throw new Error("Максимум 100 занятий в расписании");
  const result = structuredClone(schedule);
  const last = result.rows.at(-1);
  const number = Math.max(...result.rows.filter((row) => !row.skipped).map((row) => row.number)) + 1;
  feedbackInteger(number, 1, 999, "Номер занятия");
  result.rows.push({ ...feedbackNewRow(feedbackShiftDate(last.date, 7), null, number), topic: "Новое занятие" });
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

function feedbackSeries(course, startDate, firstLesson, firstNumber, count, interval, catalog, weekdays = null) {
  if (!Object.hasOwn(catalog, course)) throw new Error("Выберите курс из списка");
  if (!feedbackValidDate(startDate)) throw new Error("Укажите существующую дату первого занятия");
  const first = feedbackInteger(firstLesson, 1, catalog[course].length, "Первый материал");
  const number = feedbackInteger(firstNumber, 1, 999, "Первый номер");
  const total = feedbackInteger(count, 1, 100, "Количество занятий");
  const days = weekdays === null ? null : [...new Set(weekdays.map((day) => feedbackInteger(day, 0, 6, "День недели")))];
  if (days && !days.length) throw new Error("Выберите хотя бы один день недели");
  const step = days ? 1 : feedbackInteger(interval, 1, 60, "Интервал в днях");
  if (first + total - 1 > catalog[course].length || number + total - 1 > 999) {
    throw new Error("Количество занятий выходит за пределы курса или нумерации");
  }
  let cursor = startDate;
  return Array.from({ length: total }, (_, index) => {
    if (days) {
      while (!days.includes(new Date(`${cursor}T12:00:00Z`).getUTCDay())) cursor = feedbackShiftDate(cursor, 1);
    }
    const value = days ? cursor : feedbackShiftDate(startDate, index * step);
    if (!feedbackValidDate(value)) throw new Error("Последняя дата выходит за допустимый диапазон");
    if (days && index < total - 1) cursor = feedbackShiftDate(cursor, 1);
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
    if (row.lesson == null) {
      if (typeof row.topic !== "string" || !row.topic.trim() || row.topic.length > 200 || row.repeat) throw new Error("Укажите тему своего занятия");
    } else feedbackInteger(row.lesson, 1, catalog[schedule.course].length, "Материал урока");
    if (!row.skipped && numbers.has(number)) throw new Error(`Номер занятия ${number} повторяется. Укажите разные номера.`);
    if (!row.skipped) numbers.add(number);
    if (!feedbackValidDate(row.date)) throw new Error(`Проверьте дату занятия №${number}`);
    if (typeof row.repeat !== "boolean" || typeof row.skipped !== "boolean") throw new Error("Проверьте отметки повторения и отмены");
  }
  if (schedule.rows.every((row) => row.skipped)) throw new Error("Оставьте включённым хотя бы одно занятие");
  return true;
}

function feedbackRestore(raw, catalog, groups) {
  const restored = { schedules: Object.create(null), recovered: 0 };
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) { restored.recovered += 1; return restored; }
  const schedules = raw.schedules && typeof raw.schedules === "object" && !Array.isArray(raw.schedules) ? raw.schedules : {};
  if (raw.schedules && schedules !== raw.schedules) restored.recovered += 1;
  for (const group of groups) {
    if (!Object.hasOwn(schedules, group)) continue;
    const saved = { ...schedules[group], course: feedbackResolveCourse(schedules[group]?.course, catalog) };
    try {
      let schedule;
      if (Array.isArray(saved?.rows)) {
        schedule = { course: saved.course, mode: saved.mode, rows: saved.rows.map((row) => ({
          id: row.id, date: row.date, lesson: row.lesson == null ? null : Number(row.lesson), number: Number(row.number),
          ...(row.lesson == null ? { topic: row.topic } : {}),
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
  return restored;
}
