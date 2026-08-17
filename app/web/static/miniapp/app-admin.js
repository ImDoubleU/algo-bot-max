function studentRegistryStatus(status) {
  const statuses = {
    active: { label: "Обучается", tone: "active" },
    departed: { label: "Выбыл", tone: "departed" },
    archived: { label: "Архив", tone: "archived" },
  };
  return statuses[status] || statuses.active;
}

function formatStudentBirthDate(value) {
  const parts = String(value || "").split("-");
  return parts.length === 3 ? `${parts[2]}.${parts[1]}.${parts[0]}` : "Не указана";
}

function studentHistoryChangedFields(fields) {
  const labels = {
    crm_deal_id: "данные CRM",
    crm_uuid: "данные CRM",
    lms_student_id: "ID ученика",
    first_name: "имя",
    last_name: "фамилия",
    birth_date: "дата рождения",
    group_name: "группа",
    course_name: "курс",
    venue_name: "площадка",
    teacher_name: "преподаватель",
  };
  return [...new Set((fields || []).map((field) => labels[field] || field))];
}

function studentHistoryCopy(event) {
  if (event.eventType === "created") {
    return {
      title: "Добавлен вручную",
      detail: "Карточка ученика создана сотрудником школы.",
    };
  }
  if (event.eventType === "imported") {
    return {
      title: "Добавлен в систему",
      detail: "Данные ученика загружены из файла.",
    };
  }
  if (event.eventType === "status_changed") {
    const from = studentRegistryStatus(event.fromStatus || "active").label;
    const to = studentRegistryStatus(event.toStatus).label;
    return {
      title: `Статус изменен: ${to}`,
      detail: `${from} → ${to}`,
    };
  }
  if (event.eventType === "group_changed") {
    return {
      title: "Переведен в другую группу",
      detail: `${event.fromGroupName || "Без группы"} → ${event.toGroupName || "Без группы"}`,
    };
  }
  const changedFields = studentHistoryChangedFields(event.changedFields);
  return {
    title: "Данные обновлены",
    detail: changedFields.length
      ? `Изменено: ${changedFields.join(", ")}.`
      : "Файл загружен повторно, данные не изменились.",
  };
}

function studentCreateEditor() {
  if (!state.studentCreateOpen) return "";
  return `
    <section class="student-create-editor">
      <div class="student-create-heading">
        <span><i data-lucide="user-plus"></i></span>
        <div>
          <strong>Новый ученик</strong>
          <small>Карточка ученика, родитель и доступ создаются одной операцией.</small>
        </div>
        <button class="icon-button" type="button" data-close-student-create title="Закрыть" aria-label="Закрыть">×</button>
      </div>
      <form id="studentCreateForm" class="student-create-form">
        <fieldset class="student-create-section">
          <legend>Ученик</legend>
          <div class="student-create-fields">
            <label><span>Фамилия</span><input name="last_name" maxlength="120" autocomplete="family-name" required /></label>
            <label><span>Имя</span><input name="first_name" maxlength="120" autocomplete="given-name" required /></label>
            <label><span>Дата рождения</span><input name="birth_date" type="date" /></label>
            <label><span>Состояние</span><select name="status"><option value="active">Обучается</option><option value="departed">Выбыл</option><option value="archived">Архив</option></select></label>
          </div>
        </fieldset>
        <fieldset class="student-create-section">
          <legend>Обучение и CRM</legend>
          <div class="student-create-fields">
            <label><span>ID ученика</span><input name="lms_student_id" maxlength="120" /></label>
            <label><span>ID сделки amoCRM</span><input name="crm_deal_id" maxlength="120" inputmode="numeric" /></label>
            <label><span>UUID CRM</span><input name="crm_uuid" maxlength="180" /></label>
            <label><span>Группа</span><input name="group_name" maxlength="160" /></label>
            <label><span>Курс</span><input name="course_name" maxlength="160" /></label>
            <label><span>Площадка</span><input name="venue_name" maxlength="160" /></label>
            <label><span>Преподаватель</span><input name="teacher_name" maxlength="160" /></label>
          </div>
        </fieldset>
        <fieldset class="student-create-section">
          <legend>Родитель</legend>
          <div class="student-create-fields">
            <label><span>ФИО родителя</span><input name="parent_name" maxlength="160" autocomplete="name" /></label>
            <label><span>Contact ID из CRM</span><input name="parent_contact_id" maxlength="120" inputmode="numeric" /></label>
            <label><span>MAX ID, необязательно</span><input name="parent_max_user_id" type="number" min="1" inputmode="numeric" /></label>
            <label><span>Имя в MAX, необязательно</span><input name="parent_max_username" maxlength="120" placeholder="без @" /></label>
          </div>
        </fieldset>
        <fieldset class="student-create-section student-create-balance">
          <legend>Астрокоины</legend>
          <div class="student-create-fields">
            <label><span>Начальный баланс</span><input name="initial_balance" type="number" min="0" max="10000000" inputmode="numeric" value="0" required /></label>
          </div>
        </fieldset>
        <div class="student-create-actions">
          <button class="secondary-action" type="button" data-close-student-create>Отмена</button>
          <button class="primary-action" type="submit"><i data-lucide="user-plus"></i><span>Добавить ученика</span></button>
        </div>
      </form>
    </section>
  `;
}

function studentAccessPolicyEditor() {
  if (!["superadmin", "partner_director"].includes(primaryStaffRole())) return "";
  const policy = state.studentAccessPolicy || {};
  return `
    <section class="student-access-policy">
      <div class="student-access-policy-heading">
        <span class="student-access-policy-icon"><i data-lucide="calendar-clock"></i></span>
        <span>
          <strong>Доступ после выбытия</strong>
          <small>Баланс, заказы и привязки сохраняются. При возвращении ученик продолжит с прежними данными.</small>
        </span>
      </div>
      <form id="studentAccessPolicyForm" class="student-access-policy-form">
        <label>
          <span>Срок доступа, дней</span>
          <input id="departedAccessDays" type="number" min="1" max="365" inputmode="numeric" value="${Number(policy.departedAccessDays || 30)}" required />
        </label>
        <label>
          <span>Пауза с</span>
          <input id="studentAccessFreezeFrom" type="date" value="${escapeHtml(policy.freezeFrom || "")}" />
        </label>
        <label>
          <span>Пауза до</span>
          <input id="studentAccessFreezeUntil" type="date" value="${escapeHtml(policy.freezeUntil || "")}" />
        </label>
        <div class="student-access-policy-actions">
          <button class="text-action" type="button" data-clear-access-freeze ${policy.freezeFrom || policy.freezeUntil ? "" : "disabled"}>Очистить даты</button>
          <button class="primary-action" type="submit" ${state.studentAccessPolicySaving ? "disabled" : ""}>
            ${state.studentAccessPolicySaving ? '<span class="button-spinner" aria-hidden="true"></span> Сохраняем' : "Сохранить"}
          </button>
        </div>
      </form>
      <p>Дни внутри указанного периода не расходуют срок доступа. Например, пауза до 31 августа переносит оставшиеся дни на сентябрь.</p>
    </section>
  `;
}

async function saveStudentAccessPolicy(event) {
  event.preventDefault();
  if (state.studentAccessPolicySaving || !apiContext.maxUserId) return;
  const departedAccessDays = Number(qs("#departedAccessDays")?.value || 0);
  const freezeFrom = qs("#studentAccessFreezeFrom")?.value || "";
  const freezeUntil = qs("#studentAccessFreezeUntil")?.value || "";
  if (!Number.isInteger(departedAccessDays) || departedAccessDays < 1 || departedAccessDays > 365) {
    showNotice("Укажите срок от 1 до 365 дней", "danger");
    return;
  }
  if (Boolean(freezeFrom) !== Boolean(freezeUntil)) {
    showNotice("Укажите обе даты паузы или очистите обе", "danger");
    return;
  }
  if (freezeFrom && freezeUntil && freezeFrom > freezeUntil) {
    showNotice("Дата начала паузы должна быть раньше даты окончания", "danger");
    return;
  }

  state.studentAccessPolicySaving = true;
  renderStudentRegistry();
  try {
    const response = await apiFetch("/api/v1/miniapp/students/access-policy", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        max_user_id: Number(apiContext.maxUserId),
        tenant_slug: apiContext.tenantSlug || undefined,
        departed_access_days: departedAccessDays,
        freeze_from: freezeFrom || null,
        freeze_until: freezeUntil || null,
      }),
    });
    if (!response.ok) throw new Error(await parseApiError(response));
    const result = await response.json();
    state.studentAccessPolicy = {
      departedAccessDays: Number(result.departed_access_days || 30),
      freezeFrom: result.freeze_from || "",
      freezeUntil: result.freeze_until || "",
    };
    showNotice("Настройки доступа сохранены");
  } catch (error) {
    showNotice(error.message || "Не удалось сохранить настройки доступа", "danger");
  } finally {
    state.studentAccessPolicySaving = false;
    renderStudentRegistry();
  }
}

async function createAdminStudent(event) {
  event.preventDefault();
  if (state.studentMutationSaving || !apiContext.maxUserId) return;
  const form = event.target;
  const data = new FormData(form);
  const firstName = String(data.get("first_name") || "").trim();
  const lastName = String(data.get("last_name") || "").trim();
  if (!firstName || !lastName) {
    showNotice("Укажите имя и фамилию ученика", "danger");
    return;
  }
  const parentContactId = String(data.get("parent_contact_id") || "").trim();
  const parentName = String(data.get("parent_name") || "").trim();
  const parentMaxIdRaw = String(data.get("parent_max_user_id") || "").trim();
  const parentMaxUserId = parentMaxIdRaw ? Number(parentMaxIdRaw) : null;
  if ((parentName || parentMaxUserId) && !parentContactId) {
    showNotice("Для связи с родителем укажите Contact ID из CRM", "danger");
    return;
  }
  if (parentMaxIdRaw && (!Number.isInteger(parentMaxUserId) || parentMaxUserId <= 0)) {
    showNotice("Проверьте MAX ID родителя", "danger");
    return;
  }
  const submitButton = form.querySelector('button[type="submit"]');
  state.studentMutationSaving = "create";
  if (submitButton) submitButton.disabled = true;
  try {
    const response = await apiFetch("/api/v1/miniapp/students", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        max_user_id: Number(apiContext.maxUserId),
        tenant_slug: apiContext.tenantSlug || undefined,
        first_name: firstName,
        last_name: lastName,
        birth_date: String(data.get("birth_date") || "") || null,
        lms_student_id: String(data.get("lms_student_id") || "").trim() || null,
        crm_deal_id: String(data.get("crm_deal_id") || "").trim() || null,
        crm_uuid: String(data.get("crm_uuid") || "").trim() || null,
        group_name: String(data.get("group_name") || "").trim() || null,
        course_name: String(data.get("course_name") || "").trim() || null,
        venue_name: String(data.get("venue_name") || "").trim() || null,
        teacher_name: String(data.get("teacher_name") || "").trim() || null,
        status: String(data.get("status") || "active"),
        parent_contact_id: parentContactId || null,
        parent_name: parentName || null,
        parent_max_user_id: parentMaxUserId,
        parent_max_username: String(data.get("parent_max_username") || "").trim() || null,
        initial_balance: Number(data.get("initial_balance") || 0),
      }),
    });
    if (!response.ok) throw new Error(await parseApiError(response));
    applyAdminStudentRegistry(await response.json());
    state.studentCreateOpen = false;
    showNotice("Ученик добавлен");
    renderStudentRegistry();
  } catch (error) {
    showNotice(error.message || "Не удалось добавить ученика", "danger");
  } finally {
    state.studentMutationSaving = "";
    if (submitButton?.isConnected) submitButton.disabled = false;
  }
}

async function updateAdminStudentBirthDate(event) {
  event.preventDefault();
  if (state.studentMutationSaving || !apiContext.maxUserId) return;
  const form = event.target;
  const studentId = form.dataset.studentBirthDateForm || "";
  const birthDate = String(new FormData(form).get("birth_date") || "");
  const submitButton = form.querySelector('button[type="submit"]');
  state.studentMutationSaving = studentId;
  if (submitButton) submitButton.disabled = true;
  try {
    const response = await apiFetch(`/api/v1/miniapp/students/${encodeURIComponent(studentId)}/birth-date`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        max_user_id: Number(apiContext.maxUserId),
        tenant_slug: apiContext.tenantSlug || undefined,
        birth_date: birthDate || null,
      }),
    });
    if (!response.ok) throw new Error(await parseApiError(response));
    applyAdminStudentRegistry(await response.json());
    showNotice("Дата рождения сохранена");
    renderStudentRegistry();
  } catch (error) {
    showNotice(error.message || "Не удалось сохранить дату рождения", "danger");
  } finally {
    state.studentMutationSaving = "";
    if (submitButton?.isConnected) submitButton.disabled = false;
  }
}

async function updateAdminStudentStatus(event) {
  event.preventDefault();
  if (state.studentMutationSaving || !apiContext.maxUserId) return;
  const form = event.target;
  const studentId = form.dataset.studentStatusForm || "";
  const status = new FormData(form).get("status");
  const submitButton = form.querySelector('button[type="submit"]');
  state.studentMutationSaving = studentId;
  if (submitButton) submitButton.disabled = true;
  try {
    const response = await apiFetch(`/api/v1/miniapp/students/${encodeURIComponent(studentId)}/status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        max_user_id: Number(apiContext.maxUserId),
        tenant_slug: apiContext.tenantSlug || undefined,
        status,
      }),
    });
    if (!response.ok) throw new Error(await parseApiError(response));
    applyAdminStudentRegistry(await response.json());
    showNotice("Состояние ученика обновлено");
    renderStudentRegistry();
  } catch (error) {
    showNotice(error.message || "Не удалось изменить состояние ученика", "danger");
  } finally {
    state.studentMutationSaving = "";
    if (submitButton?.isConnected) submitButton.disabled = false;
  }
}

async function updateAdminStudentBalance(event) {
  event.preventDefault();
  if (state.studentMutationSaving || !apiContext.maxUserId) return;
  const form = event.target;
  const studentId = form.dataset.studentBalanceForm || "";
  const data = new FormData(form);
  const balance = Number(data.get("balance"));
  if (!Number.isInteger(balance) || balance < 0 || balance > 10000000) {
    showNotice("Укажите итоговый баланс от 0 до 10 000 000 AC", "danger");
    return;
  }
  const submitButton = form.querySelector('button[type="submit"]');
  state.studentMutationSaving = studentId;
  if (submitButton) submitButton.disabled = true;
  try {
    const response = await apiFetch(`/api/v1/miniapp/students/${encodeURIComponent(studentId)}/balance`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        max_user_id: Number(apiContext.maxUserId),
        tenant_slug: apiContext.tenantSlug || undefined,
        balance,
        reason: "Ручная корректировка баланса",
        comment: String(data.get("comment") || "").trim() || null,
      }),
    });
    if (!response.ok) throw new Error(await parseApiError(response));
    applyAdminStudentRegistry(await response.json());
    state.studentLedgerById.delete(studentId);
    state.studentLedgerErrors.delete(studentId);
    showNotice("Баланс ученика обновлен");
    renderStudentRegistry();
  } catch (error) {
    showNotice(error.message || "Не удалось изменить баланс", "danger");
  } finally {
    state.studentMutationSaving = "";
    if (submitButton?.isConnected) submitButton.disabled = false;
  }
}

function studentLedgerDate(value) {
  const formatted = formatRegistryDate(value);
  return formatted === "Не указана" ? String(value || "Дата не указана") : formatted;
}

function studentLedgerMarkup(studentId) {
  const normalizedStudentId = String(studentId || "");
  if (state.studentLedgerLoading.has(normalizedStudentId)) {
    return `
      <div class="student-ledger-state" role="status">
        <span class="button-spinner" aria-hidden="true"></span>
        <span>Загружаем операции</span>
      </div>
    `;
  }
  const error = state.studentLedgerErrors.get(normalizedStudentId);
  if (error) {
    return `
      <div class="student-ledger-state is-error">
        <span>${escapeHtml(error)}</span>
        <button class="text-action" type="button" data-retry-student-ledger="${escapeHtml(normalizedStudentId)}">Повторить</button>
      </div>
    `;
  }
  if (!state.studentLedgerById.has(normalizedStudentId)) {
    return '<div class="student-ledger-state">Операции загрузятся после открытия карточки.</div>';
  }
  const entries = state.studentLedgerById.get(normalizedStudentId) || [];
  if (!entries.length) {
    return '<div class="student-ledger-state">Операций с астрокоинами пока нет.</div>';
  }
  return `
    <div class="student-ledger-list">
      ${entries.map((entry) => `
        <article class="student-ledger-entry is-${entry.direction}">
          <span class="student-ledger-sign" aria-hidden="true">${entry.direction === "debit" ? "−" : "+"}</span>
          <span class="student-ledger-copy">
            <strong>${escapeHtml(entry.reason)}</strong>
            ${entry.comment ? `<span>${escapeHtml(entry.comment)}</span>` : ""}
            <time datetime="${escapeHtml(entry.createdAt)}">${escapeHtml(studentLedgerDate(entry.createdAt))}</time>
          </span>
          <strong class="student-ledger-amount">${escapeHtml(entry.amountLabel)}</strong>
        </article>
      `).join("")}
    </div>
  `;
}

function renderStudentLedgerPanel(studentId) {
  const normalizedStudentId = String(studentId || "");
  const panel = qsa("[data-student-ledger-panel]").find(
    (item) => item.dataset.studentLedgerPanel === normalizedStudentId,
  );
  if (!panel) return;
  panel.innerHTML = studentLedgerMarkup(normalizedStudentId);
}

function studentCardManagement(student) {
  if (!canManageStudentRecords()) return "";
  return `
    <section class="student-card-management" aria-label="Управление учеником">
      <form class="student-card-action" data-student-birth-date-form="${escapeHtml(student.id)}">
        <div>
          <strong>Дата рождения</strong>
          <small>В этот день активному ученику автоматически начисляется 50 AC.</small>
        </div>
        <label>
          <span>Дата</span>
          <input name="birth_date" type="date" value="${escapeHtml(student.birthDate)}" />
        </label>
        <button class="secondary-action" type="submit">Сохранить дату</button>
      </form>
      <form class="student-card-action" data-student-status-form="${escapeHtml(student.id)}">
        <div>
          <strong>Состояние ученика</strong>
          <small>Возврат в обучение восстанавливает доступ с прежней историей и балансом.</small>
        </div>
        <label>
          <span>Новое состояние</span>
          <select name="status">
            <option value="active" ${student.status === "active" ? "selected" : ""}>Обучается</option>
            <option value="departed" ${student.status === "departed" ? "selected" : ""}>Выбыл</option>
            <option value="archived" ${student.status === "archived" ? "selected" : ""}>Архив</option>
          </select>
        </label>
        <button class="secondary-action" type="submit">Сохранить состояние</button>
      </form>
      <form class="student-card-action" data-student-balance-form="${escapeHtml(student.id)}">
        <div>
          <strong>Баланс астрокоинов</strong>
          <small>Введите итоговое количество. Разница сохранится отдельной операцией.</small>
        </div>
        <label>
          <span>Итоговый баланс</span>
          <input name="balance" type="number" min="0" max="10000000" inputmode="numeric" value="${student.balance}" required />
        </label>
        <label>
          <span>Комментарий</span>
          <input name="comment" maxlength="500" placeholder="Необязательно" />
        </label>
        <button class="primary-action" type="submit">Обновить баланс</button>
      </form>
    </section>
  `;
}

function renderStudentRegistry() {
  const panel = qs("#staffStudentHistory");
  if (!panel) return;

  if (state.adminStudentsLoading || (!state.adminStudentsLoaded && !state.adminStudentsError)) {
    panel.innerHTML = `
      <div class="student-registry-loading" role="status">
        <span class="button-spinner" aria-hidden="true"></span>
        <strong>Загружаем учеников</strong>
      </div>
    `;
    return;
  }

  if (state.adminStudentsError) {
    panel.innerHTML = `
      <div class="empty-state student-registry-error">
        <i data-lucide="circle-alert"></i>
        <strong>Не удалось загрузить учеников</strong>
        <span>${escapeHtml(state.adminStudentsError)}</span>
        <button class="secondary-action" type="button" data-retry-student-registry>
          <i data-lucide="refresh-cw"></i><span>Повторить</span>
        </button>
      </div>
    `;
    refreshIcons();
    return;
  }

  const allStudents = state.adminStudents;
  const statusCounts = allStudents.reduce(
    (counts, student) => {
      counts.all += 1;
      counts[student.status] = (counts[student.status] || 0) + 1;
      return counts;
    },
    { all: 0, active: 0, departed: 0, archived: 0 },
  );
  const groups = [...new Set(allStudents.map((student) => student.group).filter(Boolean))]
    .sort((left, right) => left.localeCompare(right, "ru"));
  const query = state.studentRegistrySearch.trim().toLowerCase();
  const visibleStudents = allStudents
    .filter((student) => {
      const matchesStatus =
        state.studentRegistryStatusFilter === "all" ||
        student.status === state.studentRegistryStatusFilter;
      const matchesGroup =
        state.studentRegistryGroupFilter === "all" ||
        student.group === state.studentRegistryGroupFilter;
      const searchText = [
        student.name,
        student.lmsId,
        student.group,
        student.course,
        student.venue,
        student.teacher,
      ].join(" ").toLowerCase();
      return matchesStatus && matchesGroup && (!query || searchText.includes(query));
    })
    .sort((left, right) => {
      const statusOrder = { active: 0, departed: 1, archived: 2 };
      const statusCompare = (statusOrder[left.status] ?? 3) - (statusOrder[right.status] ?? 3);
      if (statusCompare !== 0) return statusCompare;
      const groupCompare = (left.group || "").localeCompare(right.group || "", "ru");
      return groupCompare || left.name.localeCompare(right.name, "ru");
    });
  const statusFilters = [
    ["all", "Все ученики", "users"],
    ["active", "Обучаются", "user-check"],
    ["departed", "Выбыли", "user-minus"],
    ["archived", "В архиве", "archive"],
  ];
  const staffRole = primaryStaffRole();
  const canManage = canManageStudentRecords();
  const registryTitle = staffRole === "teacher"
    ? "Мои ученики"
    : staffRole === "curator"
      ? "Ученики филиала"
      : "Все ученики";
  const registryDescription = canManage
    ? "Состояние, баланс и полная история каждого ученика"
    : "Карточки учеников, группы и история астрокоинов";

  panel.innerHTML = `
    ${studentAccessPolicyEditor()}
    <div class="admin-section-toolbar student-registry-heading">
      <div>
        <h3>${registryTitle}</h3>
        <span>${registryDescription}</span>
      </div>
      <div class="student-registry-heading-actions">
        ${canManage ? `
          <button class="primary-action" type="button" data-toggle-student-create>
            <i data-lucide="user-plus"></i><span>Добавить</span>
          </button>
        ` : ""}
        <button class="secondary-action" type="button" data-retry-student-registry>
          <i data-lucide="refresh-cw"></i><span>Обновить</span>
        </button>
      </div>
    </div>
    ${canManage ? studentCreateEditor() : ""}
    <div class="student-registry-metrics" aria-label="Фильтр по состоянию">
      ${statusFilters.map(([status, label, icon]) => `
        <button
          class="student-registry-metric ${state.studentRegistryStatusFilter === status ? "is-active" : ""}"
          type="button"
          data-student-registry-status="${status}"
        >
          <i data-lucide="${icon}"></i>
          <span><strong>${statusCounts[status] || 0}</strong><small>${label}</small></span>
        </button>
      `).join("")}
    </div>
    <div class="admin-filter-toolbar student-registry-filters">
      <label class="search-field">
        <i data-lucide="search"></i>
        <input id="studentRegistrySearch" type="search" value="${escapeHtml(state.studentRegistrySearch)}" placeholder="ФИО, группа, ID или преподаватель" />
        <button class="search-clear" type="button" data-clear-student-registry-search ${state.studentRegistrySearch ? "" : "hidden"}><i data-lucide="x"></i></button>
      </label>
      <select id="studentRegistryGroupFilter" aria-label="Группа">
        <option value="all">Все группы</option>
        ${groups.map((group) => `<option value="${escapeHtml(group)}" ${state.studentRegistryGroupFilter === group ? "selected" : ""}>${escapeHtml(group)}</option>`).join("")}
      </select>
      <span>Показано: ${visibleStudents.length} из ${allStudents.length}</span>
    </div>
    <div class="student-registry-list">
      ${visibleStudents.length ? visibleStudents.map((student) => {
        const status = studentRegistryStatus(student.status);
        const history = [...student.history].sort(
          (left, right) => new Date(right.occurredAt) - new Date(left.occurredAt),
        );
        const meta = [student.group, student.course, student.venue, student.teacher]
          .filter(Boolean);
        return `
          <details class="student-registry-card" data-student-card="${escapeHtml(student.id)}">
            <summary>
              <span class="student-registry-mark">${escapeHtml(student.name.trim().slice(0, 1).toUpperCase() || "У")}</span>
              <span class="student-registry-main">
                <span class="student-registry-name-row">
                  <strong>${escapeHtml(student.name)}</strong>
                  <span class="student-registry-status is-${status.tone}">${status.label}</span>
                </span>
                <span class="student-registry-meta">${meta.map((item) => `<span>${escapeHtml(item)}</span>`).join("") || "Данные группы не указаны"}</span>
              </span>
              <span class="student-registry-balance">${student.balance} AC</span>
              <span class="student-registry-chevron"><i data-lucide="chevron-down"></i></span>
            </summary>
            <div class="student-registry-details">
              <div class="student-registry-dates">
                <span><small>Импортирован</small><strong>${formatRegistryDate(student.importedAt)}</strong></span>
                <span><small>Данные обновлены</small><strong>${formatRegistryDate(student.updatedAt)}</strong></span>
                <span><small>Статус обновлен</small><strong>${formatRegistryDate(student.statusUpdatedAt)}</strong></span>
                <span class="${student.departedAt ? "is-departed" : ""}"><small>Дата выбытия</small><strong>${student.departedAt ? formatRegistryDate(student.departedAt) : "Нет"}</strong></span>
              </div>
              <div class="student-registry-identifiers">
                <span><small>ID ученика</small><strong>${escapeHtml(student.lmsId || "Не указан")}</strong></span>
                <span><small>Группа</small><strong>${escapeHtml(student.group || "Не указана")}</strong></span>
                <span><small>Дата рождения</small><strong>${formatStudentBirthDate(student.birthDate)}</strong></span>
                <span><small>Родитель</small><strong>${escapeHtml(student.parentNames.join(", ") || "Не указан")}</strong></span>
                <span><small>Contact ID</small><strong>${escapeHtml(student.parentContactIds.join(", ") || "Не указан")}</strong></span>
                <span><small>Связь с MAX</small><strong>${student.parentMaxUserIds.length ? "Подключено: " + student.parentMaxUserIds.length : "Ожидает входа"}</strong></span>
              </div>
              ${studentCardManagement(student)}
              <section class="student-ledger-history">
                <div class="student-history-head">
                  <h4>История астрокоинов</h4>
                  <span>Последние 100 операций</span>
                </div>
                <div data-student-ledger-panel="${escapeHtml(student.id)}">
                  ${studentLedgerMarkup(student.id)}
                </div>
              </section>
              <section class="student-history">
                <div class="student-history-head">
                  <h4>История карточки</h4>
                  <span>${history.length} ${history.length === 1 ? "событие" : "событий"}</span>
                </div>
                <div class="student-history-list">
                  ${history.length ? history.map((event) => {
                    const copy = studentHistoryCopy(event);
                    return `
                      <article class="student-history-item is-${escapeHtml(event.eventType)}">
                        <span class="student-history-dot" aria-hidden="true"></span>
                        <span class="student-history-copy">
                          <strong>${escapeHtml(copy.title)}</strong>
                          <span>${escapeHtml(copy.detail)}</span>
                          ${event.actorName ? `<small>Ответственный: ${escapeHtml(event.actorName)}</small>` : ""}
                        </span>
                        <time datetime="${escapeHtml(event.occurredAt)}">${formatRegistryDate(event.occurredAt)}</time>
                      </article>
                    `;
                  }).join("") : '<div class="empty-state compact-empty">История пока пуста</div>'}
                </div>
              </section>
            </div>
          </details>
        `;
      }).join("") : `
        <div class="empty-state student-registry-empty">
          <i data-lucide="users"></i>
          <strong>Ученики не найдены</strong>
          <span>Измените поиск или фильтр.</span>
          <button class="secondary-action" type="button" data-reset-student-registry>Сбросить фильтры</button>
        </div>
      `}
    </div>
  `;
  refreshIcons();
}

function adminHistoryStatus(status) {
  return {
    success: { label: "Выполнено", icon: "check" },
    partial: { label: "Требует внимания", icon: "triangle-alert" },
    error: { label: "Ошибка", icon: "x" },
  }[status] || { label: "Выполнено", icon: "check" };
}

function adminHistoryFacts(entry) {
  const payload = entry.payload || {};
  const facts = [];
  const add = (label, value) => {
    if (value === undefined || value === null || value === "") return;
    facts.push([label, String(value)]);
  };
  if (entry.action === "amocrm.students_synced") {
    add("Получено сделок", Array.isArray(payload.lead_ids) ? payload.lead_ids.length : 0);
    add("Создано учеников", Number(payload.created_students || 0));
    add("Уже были в системе", Number(payload.existing_students || 0));
    add("Не хватает данных", Object.keys(payload.incomplete_leads || {}).length);
  } else if (entry.action === "amocrm.student_status_updated") {
    add("Найдено учеников", Number(payload.matched_students || 0));
    add("Статус изменен", Number(payload.updated_students || 0));
    add("Не найдены", Array.isArray(payload.unmatched_lead_ids) ? payload.unmatched_lead_ids.length : 0);
  } else if (entry.action === "amocrm.sync_failed") {
    add("Причина", payload.error || "Синхронизация не выполнена");
  } else {
    add("Файл", payload.filename);
    add("Товар", payload.name || payload.sku);
    add("Заказ", payload.order_number ? `№${payload.order_number}` : "");
    add("Создано", payload.created_students ?? payload.created_products);
    add("Обновлено", payload.updated_students ?? payload.updated_products);
    add("Количество", payload.quantity ?? payload.credited_students);
    add("Сумма", payload.total_astrocoins ? `${payload.total_astrocoins} AC` : "");
    add("Роль", payload.role || payload.staff_role);
  }
  return facts.slice(0, 5);
}

function renderAdminHistory() {
  const panel = qs("#adminPanel");
  if (!panel) return;
  const query = state.adminEntitySearch.trim().toLowerCase();
  const entries = state.adminHistory.filter((entry) => {
    const isAmoCrmEvent = entry.action.startsWith("amocrm.");
    if (apiContext.demoMode && (state.adminHistoryKind === "amocrm") !== isAmoCrmEvent) {
      return false;
    }
    const text = [
      entry.title,
      entry.category,
      entry.actorName,
      entry.action,
      JSON.stringify(entry.payload || {}),
    ].join(" ").toLowerCase();
    return !query || text.includes(query);
  });
  const issueCount = entries.filter((entry) => entry.status !== "success").length;
  const title = state.adminHistoryKind === "amocrm"
    ? "Синхронизация amoCRM"
    : "Действия сотрудников";
  const description = state.adminHistoryKind === "amocrm"
    ? "Создание учеников, смена статусов и ошибки входящих данных"
    : "Изменения товаров, заказов, складов, доступов и настроек";

  panel.innerHTML = `
    <div class="admin-section-toolbar admin-history-heading">
      <div><h3>${title}</h3><span>${description}</span></div>
      <button class="secondary-action" type="button" data-retry-admin-history ${state.adminHistoryLoading ? "disabled" : ""}>
        <i data-lucide="refresh-cw"></i><span>Обновить</span>
      </button>
    </div>
    <div class="admin-history-controls">
      <div class="segmented-control" aria-label="Вид истории">
        <button type="button" class="${state.adminHistoryKind === "actions" ? "is-active" : ""}" data-admin-history-kind="actions">Действия</button>
        <button type="button" class="${state.adminHistoryKind === "amocrm" ? "is-active" : ""}" data-admin-history-kind="amocrm">amoCRM</button>
      </div>
      <label class="search-field"><i data-lucide="search"></i><input id="adminEntitySearch" type="search" value="${escapeHtml(state.adminEntitySearch)}" placeholder="Событие или сотрудник" /><button class="search-clear" type="button" data-clear-admin-search ${state.adminEntitySearch ? "" : "hidden"}><i data-lucide="x"></i></button></label>
      <select id="adminHistoryPeriod" aria-label="Период истории">
        ${[[7, "7 дней"], [30, "30 дней"], [90, "3 месяца"], [365, "Год"]].map(([days, label]) => `<option value="${days}" ${state.adminHistoryPeriod === days ? "selected" : ""}>${label}</option>`).join("")}
      </select>
    </div>
    <div class="admin-history-summary">
      <span><strong>${entries.length}</strong> событий</span>
      <span class="${issueCount ? "has-issues" : ""}"><strong>${issueCount}</strong> требуют внимания</span>
    </div>
    ${state.adminHistoryLoading ? `
      <div class="admin-history-loading"><span class="loading-spinner"></span><strong>Загружаем историю</strong></div>
    ` : state.adminHistoryError ? `
      <div class="empty-state admin-history-empty"><i data-lucide="circle-alert"></i><strong>${escapeHtml(state.adminHistoryError)}</strong><button class="secondary-action" type="button" data-retry-admin-history>Повторить</button></div>
    ` : `
      <div class="admin-history-list">
        ${entries.length ? entries.map((entry) => {
          const status = adminHistoryStatus(entry.status);
          const facts = adminHistoryFacts(entry);
          return `<article class="admin-history-entry is-${escapeHtml(entry.status)}">
            <span class="admin-history-mark"><i data-lucide="${status.icon}"></i></span>
            <div class="admin-history-main">
              <div class="admin-history-title"><strong>${escapeHtml(entry.title)}</strong><span>${escapeHtml(entry.category)}</span></div>
              ${facts.length ? `<div class="admin-history-facts">${facts.map(([label, value]) => `<span><small>${escapeHtml(label)}</small><strong>${escapeHtml(value)}</strong></span>`).join("")}</div>` : ""}
              <div class="admin-history-meta"><span>${escapeHtml(entry.actorName)}</span>${entry.actorMaxUserId ? `<span>MAX ID ${entry.actorMaxUserId}</span>` : ""}<span>${escapeHtml(status.label)}</span></div>
            </div>
            <time datetime="${escapeHtml(entry.createdAt)}">${formatRegistryDate(entry.createdAt)}</time>
          </article>`;
        }).join("") : `<div class="empty-state admin-history-empty"><i data-lucide="history"></i><strong>Событий за этот период нет</strong><span>Новые действия появятся здесь автоматически.</span></div>`}
      </div>
    `}
  `;
  refreshIcons();
}

if (apiContext.demoMode && !state.adminHistory.length) {
  const now = new Date();
  state.adminHistory = [
    normalizeAdminHistoryEntry({
      id: "demo-history-product",
      action: "product.updated",
      title: "Товар изменен",
      category: "Товары",
      status: "success",
      actor_name: "Администратор",
      actor_max_user_id: 53364725,
      payload: { name: "Набор для творчества", sku: "CREATIVE-01" },
      created_at: now.toISOString(),
    }),
    normalizeAdminHistoryEntry({
      id: "demo-history-order",
      action: "miniapp_order.cancelled",
      title: "Заказ отменен",
      category: "Заказы",
      status: "success",
      actor_name: "Директор",
      payload: { order_number: 184 },
      created_at: new Date(now.getTime() - 45 * 60 * 1000).toISOString(),
    }),
    normalizeAdminHistoryEntry({
      id: "demo-history-amocrm-sync",
      action: "amocrm.students_synced",
      title: "Ученики синхронизированы",
      category: "amoCRM",
      status: "partial",
      actor_name: "amoCRM",
      payload: {
        lead_ids: [41001, 41002, 41003],
        created_students: 2,
        existing_students: 0,
        incomplete_leads: { 41003: ["Группа"] },
      },
      created_at: new Date(now.getTime() - 12 * 60 * 1000).toISOString(),
    }),
    normalizeAdminHistoryEntry({
      id: "demo-history-amocrm-status",
      action: "amocrm.student_status_updated",
      title: "Статус ученика обновлен",
      category: "amoCRM",
      status: "success",
      actor_name: "amoCRM",
      payload: { matched_students: 1, updated_students: 1, unmatched_lead_ids: [] },
      created_at: new Date(now.getTime() - 70 * 60 * 1000).toISOString(),
    }),
  ];
  state.adminHistoryLoaded = true;
}

function renderAdminPanel() {
  if (["inventory", "students"].includes(state.adminTab)) state.adminTab = "summary";
  const adminTitles = {
    summary: "Операционная сводка",
    products: "Товары и остатки",
    warehouses: "Склады",
    crm: "Импорт учеников и групп",
    contacts: "Связи доступа",
    staff: "Сотрудники",
    history: "История изменений",
  };
  qs("#adminViewTitle").textContent = adminTitles[state.adminTab] || "Операции";
  const adminRoleEyebrow = qs("#adminRoleEyebrow");
  if (adminRoleEyebrow) {
    adminRoleEyebrow.textContent =
      primaryStaffRole() === "partner_director" ? "Директор" : "Админ";
  }
  qsa(".admin-tab").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.adminTab === state.adminTab);
  });

  if (state.adminTab === "history") {
    renderAdminHistory();
    return;
  }

  if (state.adminTab === "summary") {
    const summary = state.opsSummary || buildLocalOpsSummary();
    const statuses = summary.order_statuses || [];
    const openOrders = summary.recent_open_orders || [];
    const lowStock = summary.low_stock || [];
    const warehouseCount = Number(summary.warehouses || 0);
    const activeProductCount = Number(summary.active_products || 0);
    const totalStockQuantity = Number(summary.total_stock_quantity || 0);
    const statusOrderCount = statuses.reduce(
      (total, item) => total + Number(item.count || 0),
      0,
    );
    const hasOperationalRows = Boolean(statuses.length || openOrders.length || lowStock.length);
    const needsInitialSetup = warehouseCount === 0 || activeProductCount === 0;
    const setupTarget = activeProductCount === 0 ? "products" : "warehouses";
    const setupAction = activeProductCount === 0 ? "Добавить товары" : "Настроить склад";
    qs("#adminPanel").innerHTML = `
      <div class="ops-quick-actions">
        <strong>Быстрые действия</strong>
        <div class="ops-quick-action-list">
          <button class="primary-action" type="button" data-ops-jump="orders">
            <i data-lucide="package-check"></i>
            <span>Заказы к выдаче</span>
          </button>
          <button class="secondary-action" type="button" data-ops-jump="products">
            <i data-lucide="boxes"></i>
            <span>Товары и остатки</span>
          </button>
        </div>
      </div>
      <div class="ops-summary-grid">
        <button class="ops-metric ops-metric-orders" type="button" data-ops-jump="orders">
          <span class="ops-metric-icon"><i data-lucide="shopping-bag"></i></span>
          <span class="ops-metric-copy">
            <strong class="ops-metric-value">${Number(summary.open_orders || 0)}</strong>
            <small>Заказы в работе</small>
          </span>
        </button>
        <button class="ops-metric ops-metric-issue" type="button" data-ops-jump="orders" data-order-filter="open">
          <span class="ops-metric-icon"><i data-lucide="hand-platter"></i></span>
          <span class="ops-metric-copy">
            <strong class="ops-metric-value">${Number(summary.pending_issue_orders || 0)}</strong>
            <small>Ожидают выдачи</small>
          </span>
        </button>
        <button class="ops-metric ops-metric-products" type="button" data-ops-jump="products">
          <span class="ops-metric-icon"><i data-lucide="package-open"></i></span>
          <span class="ops-metric-copy">
            <strong class="ops-metric-value">${activeProductCount}</strong>
            <small>Активные товары</small>
          </span>
        </button>
        <button class="ops-metric ops-metric-reserved" type="button" data-ops-jump="products">
          <span class="ops-metric-icon"><i data-lucide="archive"></i></span>
          <span class="ops-metric-copy">
            <strong class="ops-metric-value">${Number(summary.total_reserved_quantity || 0)}</strong>
            <small>Товаров в резерве</small>
          </span>
        </button>
      </div>
      <div class="ops-summary-meta">
        <span><i data-lucide="warehouse"></i>${warehouseCountLabel(warehouseCount)}</span>
        <span><i data-lucide="package"></i>${totalStockQuantity} шт. на складах</span>
      </div>
      ${
        hasOperationalRows
          ? `
            <div class="ops-summary-columns">
              <section>
                <div class="ops-column-head">
                  <h3>Статусы заказов</h3>
                  <span>${statusOrderCount}</span>
                </div>
                ${
                  statuses.length
                    ? statuses
                        .map(
                          (item) => `
                            <button class="ops-row ops-row-action" type="button" data-order-status="${escapeHtml(item.status)}" data-view-jump="orders">
                              <span>${escapeHtml(orderStatusLabel(item.status))}</span>
                              <strong>${Number(item.count || 0)}</strong>
                            </button>
                          `,
                        )
                        .join("")
                    : '<div class="empty-state">Заказов пока нет</div>'
                }
              </section>
              <section>
                <div class="ops-column-head">
                  <h3>Ближайшие к выдаче</h3>
                  <span>${openOrders.length}</span>
                </div>
                ${
                  openOrders.length
                    ? openOrders
                        .slice(0, 6)
                        .map(
                          (order) => `
                            <button
                              class="ops-row ops-row-action"
                              type="button"
                              data-open-order="${escapeHtml(order.id || order.order_number || "")}"
                            >
                              <span>#${escapeHtml(order.order_number || order.id || "")} ${escapeHtml(
                                order.student_name || "ученик",
                              )}</span>
                              <strong>${escapeHtml(orderStatusLabel(order.status))}</strong>
                            </button>
                          `,
                        )
                        .join("")
                    : '<div class="empty-state">Открытых заказов нет</div>'
                }
              </section>
              <section>
                <div class="ops-column-head">
                  <h3>Низкие остатки</h3>
                  <span>${lowStock.length}</span>
                </div>
                ${
                  lowStock.length
                    ? lowStock
                        .slice(0, 8)
                        .map(
                          (item) => `
                            <button class="ops-row ops-row-action" type="button" data-ops-jump="products" data-edit-product="${escapeHtml(item.product_id || "")}">
                              <span>${escapeHtml(
                                item.product_name || item.sku || "товар",
                              )} / ${escapeHtml(item.warehouse_name || "склад")}</span>
                              <strong>${Number(item.available_quantity || 0)} шт.</strong>
                            </button>
                          `,
                        )
                        .join("")
                    : '<div class="empty-state">Низких остатков нет</div>'
                }
              </section>
            </div>
          `
          : `
            <div class="ops-empty-overview">
              <span class="ops-empty-icon">
                <i data-lucide="${needsInitialSetup ? "package-plus" : "clipboard-check"}"></i>
              </span>
              <div>
                <h3>${needsInitialSetup ? "Подготовьте каталог к работе" : "Нет задач, требующих внимания"}</h3>
                <p>${
                  needsInitialSetup
                    ? "Добавьте товары и настройте склад. После первых заказов здесь появятся выдача, резервы и контроль остатков."
                    : "Новые заказы и позиции с низким остатком появятся в этом разделе."
                }</p>
              </div>
              ${
                needsInitialSetup
                  ? `<button class="secondary-action" type="button" data-ops-jump="${setupTarget}">
                      <span>${setupAction}</span>
                      <i data-lucide="arrow-right"></i>
                    </button>`
                  : ""
              }
            </div>
          `
      }
    `;
    refreshIcons();
    return;
  }

  if (state.adminTab === "products") {
    const importingDisabled = state.productImporting ? "disabled" : "";
    const savingDisabled = state.productSaving ? "disabled" : "";
    const editing = products.find((product) => product.id === state.editingProductId);
    const editorOpen = state.productEditorOpen || Boolean(editing);
    const photoPreviewUrl = state.productPhotoPreviewUrl || (state.productPhotoRemoved ? "" : editing?.photoUrl || "");
    const catalogWarehouseOptions = allCatalogWarehouses();
    const editingInventories = new Map(
      (editing ? productWarehouses(editing) : []).map((warehouse) => [warehouse.id, warehouse]),
    );
    const editingStockTotal = [...editingInventories.values()].reduce(
      (total, warehouse) => total + Number(warehouse.stock || 0),
      0,
    );
    const inventoryRows = catalogWarehouseOptions
      .map((warehouse, index) => {
        const current = editingInventories.get(warehouse.id);
        const selected = Boolean(current) || (
          !editing && (
            state.defaultWarehouseId
              ? warehouse.id === state.defaultWarehouseId
              : index === 0
          )
        );
        const reserved = Number(current?.reserved || 0);
        const stock = Number(current?.stock || 0);
        return `
          <div class="product-inventory-row ${selected ? "is-selected" : ""}" data-product-inventory-row="${escapeHtml(warehouse.id)}">
            <label class="product-warehouse-choice">
              <input
                type="checkbox"
                data-product-warehouse-select="${escapeHtml(warehouse.id)}"
                ${selected ? "checked" : ""}
                ${reserved > 0 ? "disabled" : ""}
              />
              <span class="product-warehouse-check"><i data-lucide="check"></i></span>
              <span class="product-warehouse-copy">
                <strong>${escapeHtml(warehouse.name)}</strong>
                <small>${escapeHtml(warehouse.address || "Без примечания")}</small>
              </span>
            </label>
            <label class="product-stock-field">
              <span>Количество</span>
              <input
                type="number"
                inputmode="numeric"
                min="${reserved}"
                max="1000000"
                value="${stock}"
                data-product-warehouse-quantity="${escapeHtml(warehouse.id)}"
                ${selected ? "" : "disabled"}
              />
            </label>
            <div
              class="product-stock-state"
              data-product-warehouse-free="${escapeHtml(warehouse.id)}"
              data-reserved-quantity="${reserved}"
            >
              ${reserved > 0 ? `<span class="status-badge warn">В резерве ${reserved}</span>` : ""}
              <span>${selected ? `Свободно ${Math.max(stock - reserved, 0)} шт.` : "Не используется"}</span>
            </div>
          </div>
        `;
      })
      .join("");
    const productQuery = state.adminEntitySearch.trim().toLowerCase();
    const productCategories = Array.from(new Set(products.map((product) => product.category).filter(Boolean))).sort((left, right) => left.localeCompare(right, "ru"));
    const visibleProducts = products.filter((product) => {
      const matchesQuery = !productQuery || productSearchText(product).includes(productQuery);
      const matchesStatus = state.productStatusFilter === "all" || (product.status || "active") === state.productStatusFilter;
      const matchesCategory = state.productCategoryFilter === "all" || product.category === state.productCategoryFilter;
      return matchesQuery && matchesStatus && matchesCategory;
    });
    qs("#adminPanel").innerHTML = `
      <div class="admin-section-toolbar">
        <div>
          <h3>Каталог товаров</h3>
          <span>${activeProducts().length} активных из ${products.length}</span>
        </div>
        ${
          editorOpen
            ? ""
            : '<button id="productCreateButton" class="primary-action" type="button">Добавить товар</button>'
        }
      </div>
      ${editorOpen ? "" : `<div class="admin-filter-toolbar">
        <label class="search-field"><i data-lucide="search"></i><input id="adminEntitySearch" type="search" value="${escapeHtml(state.adminEntitySearch)}" placeholder="Название или категория" /><button class="search-clear" type="button" data-clear-admin-search ${state.adminEntitySearch ? "" : "hidden"}><i data-lucide="x"></i></button></label>
        <select id="productStatusFilter" aria-label="Статус товара">
          <option value="all">Все статусы</option>
          <option value="active" ${state.productStatusFilter === "active" ? "selected" : ""}>Активные</option>
          <option value="hidden" ${state.productStatusFilter === "hidden" ? "selected" : ""}>Скрытые</option>
          <option value="archived" ${state.productStatusFilter === "archived" ? "selected" : ""}>В архиве</option>
        </select>
        <select id="productCategoryFilter" aria-label="Категория товара">
          <option value="all">Все категории</option>
          ${productCategories.map((category) => `<option value="${escapeHtml(category)}" ${state.productCategoryFilter === category ? "selected" : ""}>${escapeHtml(category)}</option>`).join("")}
        </select>
        <span>${visibleProducts.length} из ${products.length}</span>
      </div>`}
      ${editorOpen ? `
      <div class="product-editor admin-editor">
        <div class="product-editor-heading">
          <div>
            <h3>${editing ? "Редактирование товара" : "Новый товар"}</h3>
            <span>${editing ? "Измените данные и сохраните" : "Заполните карточку целиком"}</span>
          </div>
          <button
            id="productCancelEditButton"
            class="icon-button"
            type="button"
            title="Закрыть редактор"
            aria-label="Закрыть редактор"
            ${savingDisabled}
          ><i data-lucide="x"></i></button>
        </div>

        <div class="product-editor-main">
          <div class="product-photo-field">
            <span>Фото товара</span>
            <label class="product-photo-picker ${photoPreviewUrl ? "has-preview" : ""}">
              <input
                id="productPhotoFile"
                type="file"
                accept="image/jpeg,image/png,image/webp"
                ${savingDisabled}
              />
              ${
                photoPreviewUrl
                  ? `<img src="${escapeHtml(photoPreviewUrl)}" alt="Фото товара" />`
                  : `<span class="product-photo-placeholder">
                      <i data-lucide="image-plus"></i>
                      <strong>Добавить фото</strong>
                      <small>JPEG, PNG или WebP до 10 МБ</small>
                    </span>`
              }
              <span class="product-photo-action">
                <i data-lucide="camera"></i>
                ${photoPreviewUrl ? "Заменить фото" : "Выбрать фото"}
              </span>
            </label>
            ${
              state.productPhotoFileName
                ? `<small class="product-photo-name">${escapeHtml(
                    state.productPhotoFileName,
                  )}</small>`
                : ""
            }
            ${photoPreviewUrl ? `<div class="product-photo-tools">
              <button type="button" class="secondary-action" data-crop-product-photo><i data-lucide="crop"></i><span>Кадрировать</span></button>
              <button type="button" class="secondary-action danger-action" data-remove-product-photo><i data-lucide="trash-2"></i><span>Удалить</span></button>
            </div>` : ""}
          </div>

          <div class="product-form-grid">
            <label>
              <span>Статус</span>
              <select id="productStatus">
                ${["active", "hidden", "archived"]
                  .map(
                    (status) => `<option value="${status}" ${
                      (editing?.status || "active") === status ? "selected" : ""
                    }>${escapeHtml(productStatusLabel(status))}</option>`,
                  )
                  .join("")}
              </select>
            </label>
            <label class="product-field-wide">
              <span>Способ выдачи</span>
              <select id="productFulfillmentType">
                <option value="warehouse" ${(editing?.fulfillmentType || "warehouse") === "warehouse" ? "selected" : ""}>Со склада</option>
                <option value="digital_code" ${editing?.fulfillmentType === "digital_code" ? "selected" : ""}>Код сразу после покупки</option>
              </select>
            </label>
            <label class="product-field-wide">
              <span>Название</span>
              <input id="productName" value="${escapeHtml(editing?.name || "")}" placeholder="Название товара" />
            </label>
            <label>
              <span>Категория</span>
              <input id="productCategory" value="${escapeHtml(editing?.category || "Без категории")}" />
            </label>
            <label>
              <span>Цена, AC</span>
              <input id="productPrice" type="number" min="0" value="${editing?.price ?? 0}" />
            </label>
            <label class="product-field-wide">
              <span>Описание</span>
              <textarea id="productDescription" rows="4" placeholder="Краткое описание товара">${escapeHtml(
                editing?.description || "",
              )}</textarea>
            </label>
            <section class="product-field-wide product-inventory-editor" ${(editing?.fulfillmentType || "warehouse") === "warehouse" ? "" : "hidden"}>
              <div class="product-inventory-head">
                <div>
                  <strong>Склады и остатки</strong>
                  <span>Выберите, где хранится товар, и укажите фактическое количество.</span>
                </div>
                <strong data-product-inventory-total>${editingStockTotal} шт.</strong>
              </div>
              ${
                inventoryRows
                  ? `<div class="product-inventory-list">${inventoryRows}</div>`
                  : `<div class="product-inventory-empty">
                      <i data-lucide="warehouse"></i>
                      <div><strong>Сначала добавьте склад</strong><span>После этого здесь можно будет указать остаток товара.</span></div>
                      <button class="secondary-action" type="button" data-open-product-warehouses>Перейти к складам</button>
                    </div>`
              }
            </section>
            <div class="product-field-wide product-code-editor" ${editing?.fulfillmentType === "digital_code" ? "" : "hidden"}>
              <div class="product-code-editor-head">
                <div>
                  <strong>Коды для автовыдачи</strong>
                  <span>По одному коду в строке. Уже сохраненные коды не заменяются.</span>
                </div>
                <span>${Number(editing?.stock || 0)} доступно · ${Number(editing?.issuedCodeCount || 0)} выдано</span>
              </div>
              <textarea id="productNewCodes" rows="6" placeholder="ROBLOX-XXXX-XXXX&#10;ROBLOX-YYYY-YYYY"></textarea>
              ${
                Array.isArray(editing?.codes) && editing.codes.length
                  ? `<details class="product-code-history"><summary>История кодов (${editing.codes.length})</summary><div>${editing.codes
                      .map(
                        (code) => `<div><code>${escapeHtml(code.code)}</code><span class="status-badge ${code.status === "available" ? "ok" : code.status === "issued" ? "info" : "danger"}">${code.status === "available" ? "Доступен" : code.status === "issued" ? "Выдан" : "Отключен"}</span>${code.student_name ? `<small>${escapeHtml(code.student_name)}</small>` : ""}${code.order_number ? `<small>Заказ №${Number(code.order_number)}</small>` : ""}${code.issued_at ? `<small>${escapeHtml(new Date(code.issued_at).toLocaleString("ru-RU"))}</small>` : ""}</div>`,
                      )
                      .join("")}</div></details>`
                  : ""
              }
            </div>
          </div>
        </div>

        <div class="product-editor-actions">
          <button id="productSaveButton" class="primary-action" type="button" ${savingDisabled}>
            <i data-lucide="save"></i>
            ${state.productSaving ? "Сохранение..." : "Сохранить товар"}
          </button>
          <button id="productCancelEditButtonBottom" class="secondary-action" type="button" ${savingDisabled}>
            Отмена
          </button>
        </div>
      </div>
      ` : ""}
      <details class="product-import-panel" ${state.productImportFileName ? "open" : ""}>
        <summary>
          <span class="product-import-icon"><i data-lucide="file-spreadsheet"></i></span>
          <span>
            <strong>Массовый импорт</strong>
            <small>Загрузка каталога из CSV или XLSX</small>
          </span>
          <i class="product-import-chevron" data-lucide="chevron-down"></i>
        </summary>
        <div class="product-import-controls">
          <a class="secondary-action" href="${escapeHtml(apiUrl("/api/v1/miniapp/products/import-template", { max_user_id: apiContext.maxUserId, tenant_slug: apiContext.tenantSlug }))}" download>
            <i data-lucide="download"></i><span>Скачать шаблон XLSX</span>
          </a>
          <label class="file-picker">
            <input id="productImportFile" type="file" accept=".xlsx,.csv,text/csv" />
            <span>${escapeHtml(state.productImportFileName || "Выбрать CSV или XLSX")}</span>
          </label>
          <button id="productImportButton" class="primary-action" type="button" ${importingDisabled}>
            ${state.productImporting ? "Импорт..." : "Импортировать"}
          </button>
        </div>
      </details>
      <div class="admin-card-list">
      ${
        products.length === 0
          ? '<div class="empty-state compact-empty"><i data-lucide="package-plus"></i><strong>Товаров пока нет</strong><span>Добавьте первый товар целиком: фото, название, цену и описание.</span></div>'
          : visibleProducts.length === 0
            ? '<div class="empty-state compact-empty"><strong>Товары не найдены</strong><button class="secondary-action" type="button" data-clear-admin-search>Сбросить фильтры</button></div>'
          : visibleProducts
              .map(
                (product) => `
            <article class="admin-entity-card">
              <div class="admin-product-thumb">
                <span>${escapeHtml(product.mark)}</span>
                ${
                  product.photoUrl
                    ? `<img src="${escapeHtml(product.photoUrl)}" alt="" loading="lazy" />`
                    : ""
                }
              </div>
              <div class="admin-entity-main">
                <div class="admin-entity-title">
                  <strong>${escapeHtml(product.name)}</strong>
                  <span class="status-badge ${
                    (product.status || "active") === "active"
                      ? "ok"
                      : (product.status || "active") === "hidden"
                        ? "warn"
                        : "danger"
                  }">${escapeHtml(productStatusLabel(product.status))}</span>
                </div>
                <div class="admin-entity-meta">
                  <span>${escapeHtml(product.category)}</span>
                  <span>${
                    product.fulfillmentType === "digital_code"
                      ? `${product.stock} кодов доступно`
                      : `${productWarehouses(product).reduce((total, warehouse) => total + warehouse.stock, 0)} шт.${
                          productWarehouses(product).some((warehouse) => warehouse.reserved > 0)
                            ? ` · ${productWarehouses(product).reduce((total, warehouse) => total + warehouse.reserved, 0)} в резерве`
                            : ""
                        } · ${
                          productWarehouses(product).length
                            ? productWarehouses(product).map((warehouse) => escapeHtml(warehouse.name)).join(", ")
                            : "склад не выбран"
                        }`
                  }</span>
                </div>
              </div>
              <div class="admin-entity-actions">
                <strong>${product.price} AC</strong>
                <button class="icon-button product-status-toggle" type="button" data-toggle-product-status="${escapeHtml(product.id)}" title="${(product.status || "active") === "active" ? "Скрыть товар" : "Опубликовать товар"}" aria-label="${(product.status || "active") === "active" ? "Скрыть товар" : "Опубликовать товар"}"><i data-lucide="${(product.status || "active") === "active" ? "eye-off" : "eye"}"></i></button>
                <button class="secondary-action" type="button" data-edit-product="${escapeHtml(
                  product.id,
                )}">Редактировать</button>
              </div>
            </article>
          `,
              )
              .join("")
      }
      </div>
    `;
    refreshIcons();
    return;
  }

  if (state.adminTab === "crm") {
    const preview = state.crmImportPreview;
    const busy = state.crmImporting ? "disabled" : "";
    const importStep = preview ? 3 : state.crmImportFile ? 2 : 1;
    qs("#adminPanel").innerHTML = `
      <div class="admin-section-toolbar">
        <div>
          <h3>Данные CRM</h3>
          <span>${escapeHtml(apiContext.tenantSlug || "Текущий филиал")}</span>
        </div>
        <a
          class="secondary-action"
          href="/miniapp/import-template.xlsx"
          download="algo-max-students-import-template.xlsx"
        ><i data-lucide="file-down"></i> Скачать шаблон</a>
      </div>
      <div class="import-stepper" aria-label="Этапы импорта">
        <span class="${importStep >= 1 ? "is-complete" : ""}"><b>1</b> Файл</span>
        <span class="${importStep >= 2 ? "is-complete" : ""}"><b>2</b> Проверка</span>
        <span class="${importStep >= 3 ? "is-complete" : ""}"><b>3</b> Подтверждение</span>
      </div>
      <div class="import-panel crm-import-panel">
        <div>
          <h3>Ученики и группы</h3>
        </div>
        <label>
          <span>Состав выгрузки</span>
          <select id="crmStudentStatus" ${busy}>
            <option value="active" ${state.crmStudentStatus === "active" ? "selected" : ""}>Активные ученики</option>
            <option value="departed" ${state.crmStudentStatus === "departed" ? "selected" : ""}>Выбывшие ученики</option>
          </select>
        </label>
        <label class="file-picker">
          <input id="crmImportFile" type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" />
          <span>${escapeHtml(state.crmImportFileName || "Выбрать XLSX")}</span>
        </label>
        <button id="crmPreviewButton" class="secondary-action" type="button" ${busy}>
          ${state.crmImporting ? "Обработка..." : "Проверить файл"}
        </button>
      </div>
      ${state.crmImportFile ? `<div class="import-mapping-note"><i data-lucide="table-properties"></i><div><strong>Читаем только лист «Шаблон»</strong><span>Дополнительные листы и колонки не попадут в импорт.</span></div></div>` : ""}
      ${
        preview
          ? `
            <div class="crm-import-result">
              <div class="ops-summary-grid crm-summary-grid">
                <article><span>${Number(preview.parsed_rows || 0)}</span><strong>Строк</strong></article>
                <article><span>${Number(preview.distinct_groups || 0)}</span><strong>Групп</strong></article>
                <article><span>${Number(preview.distinct_courses || 0)}</span><strong>Курсов</strong></article>
                <article><span>${Number(preview.distinct_teachers || 0)}</span><strong>Преподавателей</strong></article>
                <article><span>${Number(preview.rows_with_contacts || 0)}</span><strong>С Contact ID</strong></article>
                <article><span>${Number(preview.rows_without_group || 0)}</span><strong>Без группы</strong></article>
              </div>
              <div class="crm-import-actions">
                <div>
                  <strong>${escapeHtml(preview.filename || state.crmImportFileName)}</strong>
                  <span>${
                    preview.student_status === "departed"
                      ? "Статус: выбывшие"
                      : "Статус: активные"
                  } · без имени: ${Number(preview.rows_without_student_name || 0)}</span>
                </div>
                <button id="crmImportButton" class="primary-action" type="button" ${busy}>
                  ${state.crmImporting ? "Импорт..." : `Импортировать ${Number(preview.parsed_rows || 0)} строк`}
                </button>
              </div>
            </div>
          `
          : ""
      }
    `;
    return;
  }

  if (state.adminTab === "warehouses") {
    const editing = catalogWarehouses.find((item) => item.id === state.editingWarehouseId);
    const editorOpen = state.warehouseEditorOpen || Boolean(editing);
    const disabled = state.warehouseSaving ? "disabled" : "";
    const rows = allCatalogWarehouses()
      .map(
        (warehouse) => `
          <article class="admin-entity-card warehouse-entity-card">
            <div class="warehouse-name-mark">${escapeHtml(
              String(warehouse.name || "С").slice(0, 1).toUpperCase(),
            )}</div>
            <div class="admin-entity-main">
              <div class="admin-entity-title">
                <strong>${escapeHtml(warehouse.name)}</strong>
              </div>
              <div class="admin-entity-meta">
                <span>${escapeHtml(warehouse.address || "Адрес или примечание не указаны")}</span>
              </div>
            </div>
            <div class="admin-entity-actions">
              <button class="secondary-action" type="button" data-edit-warehouse="${escapeHtml(
                warehouse.id,
              )}">Редактировать</button>
            </div>
          </article>
        `,
      )
      .join("");

    qs("#adminPanel").innerHTML = `
      <div class="admin-section-toolbar">
        <div>
          <h3>Склады</h3>
          <span>${allCatalogWarehouses().length} складов у выбранного партнера</span>
        </div>
        ${
          editorOpen
            ? ""
            : '<button id="warehouseCreateButton" class="primary-action" type="button">Добавить склад</button>'
        }
      </div>
      ${editorOpen ? `
      <div class="warehouse-form admin-editor">
        <label>
          <span>Название</span>
          <input id="warehouseName" value="${escapeHtml(editing?.name || "")}" placeholder="Например, Центральный склад" />
        </label>
        <label>
          <span>Адрес или примечание</span>
          <input id="warehouseAddress" value="${escapeHtml(editing?.address || "")}" placeholder="Например, ул. Большая Покровская, 10" />
        </label>
        <button id="warehouseSaveButton" class="primary-action" type="button" ${disabled}>
          ${state.warehouseSaving ? "Сохранение..." : editing ? "Сохранить" : "Создать"}
        </button>
        ${
          editing
            ? '<button id="warehouseCancelEditButton" class="secondary-action" type="button">Отмена</button>'
            : ""
        }
      </div>
      ` : ""}
      <div class="warehouse-preference">
        <div>
          <strong>Мой основной склад</strong>
          <span>Будет выбран заранее в новых зарезервированных заказах.</span>
        </div>
        <select id="defaultWarehouseSelect">
          <option value="">Выберите склад</option>
          ${allCatalogWarehouses()
            .map(
              (warehouse) => `<option value="${escapeHtml(warehouse.id)}" ${
                warehouse.id === state.defaultWarehouseId ? "selected" : ""
              }>${escapeHtml(warehouse.name)}</option>`,
            )
            .join("")}
        </select>
        <button
          id="saveWarehousePreferenceButton"
          class="secondary-action"
          type="button"
          ${state.warehousePreferenceSaving ? "disabled" : ""}
        >${state.warehousePreferenceSaving ? "Сохранение..." : "Сохранить"}</button>
      </div>
      <div class="admin-card-list">
        ${rows || '<div class="empty-state">Складов пока нет</div>'}
      </div>
    `;
    return;
  }

  if (state.adminTab === "contacts") {
    const activeLinks = accessLinks.filter((link) => link.status === "active").length;
    const accessQuery = state.adminEntitySearch.trim().toLowerCase();
    const visibleLinks = accessLinks.filter((link) => {
      const matchesQuery = !accessQuery || `${link.studentName} ${link.group} ${link.maxUserId} ${link.displayName} ${link.username}`.toLowerCase().includes(accessQuery);
      const matchesStatus = state.accessStatusFilter === "all" || link.status === state.accessStatusFilter;
      const matchesRole = state.accessRoleFilter === "all" || link.role === state.accessRoleFilter;
      return matchesQuery && matchesStatus && matchesRole;
    });
    const rows = visibleLinks
      .map(
        (link) => `
          <article class="admin-entity-card access-entity-card">
            <div class="access-role-mark">${escapeHtml(
              accessRoleLabel(link.role).slice(0, 1),
            )}</div>
            <div class="admin-entity-main">
              <div class="admin-entity-title">
                <strong>${escapeHtml(link.studentName)}</strong>
                <span class="status-badge ${link.status === "active" ? "ok" : "danger"}">
                  ${link.status === "active" ? "Активна" : "Отозвана"}
                </span>
              </div>
              <div class="admin-entity-meta">
                <span>${escapeHtml(accessRoleLabel(link.role))}</span>
                <span>${escapeHtml(link.group)}</span>
                <span>MAX ID ${escapeHtml(link.maxUserId)}</span>
                ${
                  (link.displayName && link.displayName !== accessRoleLabel(link.role)) ||
                  link.username
                    ? `<span>${escapeHtml(
                        link.displayName && link.displayName !== accessRoleLabel(link.role)
                          ? link.displayName
                          : `@${link.username}`,
                      )}</span>`
                    : ""
                }
              </div>
            </div>
            <div class="admin-entity-actions">
              <details class="admin-row-menu">
                <summary class="icon-button" title="Действия" aria-label="Действия со связью"><i data-lucide="ellipsis-vertical"></i></summary>
                <div class="admin-row-menu-popover">
                  <button
                    class="${link.status === "active" ? "danger-action" : ""}"
                    type="button"
                    data-toggle-contact="${escapeHtml(link.id)}"
                  >${link.status === "revoked" ? "Восстановить связь" : "Отозвать связь"}</button>
                </div>
              </details>
            </div>
          </article>
        `,
      )
      .join("");

    qs("#adminPanel").innerHTML = `
      <div class="admin-section-toolbar">
        <div>
          <h3>Связи доступа</h3>
          <span>${activeLinks} активных из ${accessLinks.length}</span>
        </div>
      </div>
      <div class="admin-filter-toolbar">
        <label class="search-field"><i data-lucide="search"></i><input id="adminEntitySearch" type="search" value="${escapeHtml(state.adminEntitySearch)}" placeholder="Ученик, группа или MAX ID" /><button class="search-clear" type="button" data-clear-admin-search ${state.adminEntitySearch ? "" : "hidden"}><i data-lucide="x"></i></button></label>
        <select id="accessStatusFilter" aria-label="Статус связи"><option value="all">Все статусы</option><option value="active" ${state.accessStatusFilter === "active" ? "selected" : ""}>Активные</option><option value="revoked" ${state.accessStatusFilter === "revoked" ? "selected" : ""}>Отозванные</option></select>
        <select id="accessRoleFilter" aria-label="Роль связи"><option value="all">Все роли</option><option value="parent" ${state.accessRoleFilter === "parent" ? "selected" : ""}>Родители</option><option value="student" ${state.accessRoleFilter === "student" ? "selected" : ""}>Ученики</option></select>
      </div>
      <div class="admin-card-list">
        ${rows || '<div class="empty-state compact-empty"><strong>Связи не найдены</strong><button class="secondary-action" type="button" data-clear-admin-search>Сбросить фильтры</button></div>'}
      </div>
    `;
    refreshIcons();
    return;
  }

  const disabled = state.staffSaving ? "disabled" : "";
  const activeStaff = staffAssignments.filter((item) => item.status === "active").length;
  const revokedStaff = staffAssignments.length - activeStaff;
  const staffQuery = state.adminEntitySearch.trim().toLowerCase();
  const visibleStaffAssignments = staffAssignments.filter((item) => {
    const matchesStatus = state.staffStatusFilter === "all" || item.status === state.staffStatusFilter;
    const matchesRole = state.staffRoleFilter === "all" || item.role === state.staffRoleFilter;
    const matchesQuery = !staffQuery || `${item.displayName} ${item.username} ${item.maxUserId} ${staffRoleLabel(item.role)}`.toLowerCase().includes(staffQuery);
    return matchesStatus && matchesRole && matchesQuery;
  });
  const canManageStaffNotifications = ["superadmin", "partner_director"].includes(
    primaryStaffRole(),
  );
  const rows =
    visibleStaffAssignments.length === 0
      ? `<div class="empty-state">${
          staffAssignments.length === 0
            ? "Сотрудников пока нет"
            : state.staffStatusFilter === "revoked"
              ? "Отозванных назначений нет"
              : "Активных назначений нет"
        }</div>`
      : visibleStaffAssignments
          .map(
            (assignment) => `
              <article class="admin-entity-card staff-entity-card">
                <div class="staff-role-mark">${escapeHtml(
                  staffRoleLabel(assignment.role).slice(0, 1),
                )}</div>
                <div class="admin-entity-main">
                  <div class="admin-entity-title">
                    <strong>${escapeHtml(
                      assignment.displayName || assignment.username || "Без имени",
                    )}</strong>
                    <span class="status-badge ${
                      assignment.status === "active" ? "ok" : "danger"
                    }">${escapeHtml(assignmentStatusLabel(assignment.status))}</span>
                  </div>
                  <div class="admin-entity-meta">
                    <span>${escapeHtml(staffRoleLabel(assignment.role))}</span>
                    <span>MAX ID ${escapeHtml(assignment.maxUserId)}</span>
                    ${assignment.username ? `<span>@${escapeHtml(assignment.username)}</span>` : ""}
                  </div>
                </div>
                <div class="admin-entity-actions">
                  ${
                    canManageStaffNotifications
                    && assignment.status === "active"
                    && ["admin", "curator"].includes(assignment.role)
                      ? `<button
                          class="secondary-action staff-notification-button"
                          type="button"
                          data-staff-notifications="${escapeHtml(assignment.accountId)}"
                        ><i data-lucide="bell-ring"></i><span>Уведомления</span></button>`
                      : ""
                  }
                  ${
                    assignment.role !== "superadmin" &&
                    (primaryStaffRole() === "superadmin" ||
                      ["teacher", "curator"].includes(assignment.role))
                      ? `<details class="admin-row-menu">
                          <summary class="icon-button" title="Действия" aria-label="Действия с сотрудником"><i data-lucide="ellipsis-vertical"></i></summary>
                          <div class="admin-row-menu-popover">
                            <button
                              class="${assignment.status === "active" ? "danger-action" : ""}"
                              type="button"
                              data-toggle-staff="${escapeHtml(assignment.maxUserId)}"
                              data-staff-role="${escapeHtml(assignment.role)}"
                            >${assignment.status === "revoked" ? "Восстановить роль" : "Отозвать роль"}</button>
                          </div>
                        </details>`
                      : ""
                  }
                </div>
              </article>
            `,
          )
          .join("");

  const elevatedRoleOptions = primaryStaffRole() === "superadmin"
    ? `
          <option value="admin">Администратор</option>
          <option value="partner_director">Директор партнера</option>
        `
    : "";

  qs("#adminPanel").innerHTML = `
    <div class="admin-section-toolbar">
      <div>
        <h3>Сотрудники</h3>
        <span>${activeStaff} активных назначений из ${staffAssignments.length}</span>
      </div>
      ${
        state.staffEditorOpen
          ? ""
          : '<button id="staffCreateButton" class="primary-action" type="button">Выдать роль</button>'
      }
    </div>
    <div class="staff-status-filter" role="group" aria-label="Фильтр сотрудников">
      <button
        class="staff-filter-button ${state.staffStatusFilter === "active" ? "is-active" : ""}"
        type="button"
        data-staff-status-filter="active"
      >Активные <span>${activeStaff}</span></button>
      <button
        class="staff-filter-button ${state.staffStatusFilter === "revoked" ? "is-active" : ""}"
        type="button"
        data-staff-status-filter="revoked"
      >Отозванные <span>${revokedStaff}</span></button>
      <button
        class="staff-filter-button ${state.staffStatusFilter === "all" ? "is-active" : ""}"
        type="button"
        data-staff-status-filter="all"
      >Все <span>${staffAssignments.length}</span></button>
    </div>
    <div class="admin-filter-toolbar">
      <label class="search-field"><i data-lucide="search"></i><input id="adminEntitySearch" type="search" value="${escapeHtml(state.adminEntitySearch)}" placeholder="Имя, MAX ID или роль" /><button class="search-clear" type="button" data-clear-admin-search ${state.adminEntitySearch ? "" : "hidden"}><i data-lucide="x"></i></button></label>
      <select id="staffRoleFilter" aria-label="Роль сотрудника">
        <option value="all">Все роли</option>
        ${["teacher", "curator", "admin", "partner_director", "superadmin"].map((role) => `<option value="${role}" ${state.staffRoleFilter === role ? "selected" : ""}>${escapeHtml(staffRoleLabel(role))}</option>`).join("")}
      </select>
    </div>
    ${state.staffEditorOpen ? `
    <div class="staff-form admin-editor">
      <label>
        <span>MAX user_id</span>
        <input id="staffMaxUserId" inputmode="numeric" placeholder="53364725" />
      </label>
      <label>
        <span>Имя</span>
        <input id="staffDisplayName" placeholder="ФИО или ник" />
      </label>
      <label>
        <span>Роль</span>
        <select id="staffRoleSelect">
          <option value="teacher">Преподаватель</option>
          <option value="curator">Куратор</option>
          ${elevatedRoleOptions}
        </select>
      </label>
      <button id="staffSaveButton" class="primary-action" type="button" ${disabled}>
        ${state.staffSaving ? "Сохранение..." : "Выдать роль"}
      </button>
      <button id="staffCancelButton" class="secondary-action" type="button">Отмена</button>
    </div>
    ` : ""}
    <div class="admin-card-list">
      ${rows}
    </div>
  `;
}
