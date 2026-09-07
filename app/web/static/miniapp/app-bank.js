const BANK_DEPOSIT_STATUS = Object.freeze({
  active: "Действует",
  matured: "Завершен",
  early_closed: "Закрыт досрочно",
  student_inactive_closed: "Закрыт после завершения обучения",
});

const BANK_OPERATION_ICON = Object.freeze({
  opened: "landmark",
  topped_up: "circle-plus",
  interest_capitalized: "badge-percent",
  rate_changed: "percent",
  matured: "circle-check",
  early_closed: "lock-open",
  student_inactive_closed: "user-minus",
});

function bankRateLabel(rateBps) {
  return `${(Number(rateBps || 0) / 100).toLocaleString("ru-RU", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}%`;
}

function bankDateLabel(value) {
  if (!value) return "Не указана";
  const date = new Date(`${value}T12:00:00`);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function bankDateInputValue(offsetDays) {
  const date = new Date();
  date.setHours(12, 0, 0, 0);
  date.setDate(date.getDate() + offsetDays);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function bankExactInterestLabel(value) {
  const amount = Number(value || 0);
  return `${amount.toLocaleString("ru-RU", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 4,
  })} AC`;
}

function normalizeBankProjection(item) {
  return {
    openedOn: item.opened_on || "",
    maturityOn: item.maturity_on || "",
    amount: Number(item.amount || 0),
    annualRateBps: Number(item.annual_rate_bps || 0),
    accrualDays: Number(item.accrual_days || 0),
    projectedInterest: Number(item.projected_interest || 0),
    projectedBalance: Number(item.projected_balance || 0),
  };
}

function projectDemoBankDeposit({ amount, annualRateBps, openedOn, maturityOn }) {
  const opened = new Date(`${openedOn}T12:00:00Z`);
  const maturity = new Date(`${maturityOn}T12:00:00Z`);
  let cursor = new Date(opened);
  cursor.setUTCDate(cursor.getUTCDate() + 1);
  let capitalizedInterest = 0;
  let pendingInterest = 0;
  let accrualDays = 0;
  const roundHalfUp = (value) => (
    value >= 0 ? Math.floor(value + 0.5) : Math.ceil(value - 0.5)
  );
  while (cursor < maturity) {
    const balance = amount + capitalizedInterest;
    pendingInterest += balance * annualRateBps / 10000 / 365;
    pendingInterest = Math.round(pendingInterest * 1e12) / 1e12;
    const nextDay = new Date(cursor);
    nextDay.setUTCDate(nextDay.getUTCDate() + 1);
    if (nextDay.getUTCMonth() !== cursor.getUTCMonth()) {
      const postedInterest = Math.max(0, roundHalfUp(pendingInterest));
      capitalizedInterest += postedInterest;
      pendingInterest = Math.round((pendingInterest - postedInterest) * 1e12) / 1e12;
    }
    accrualDays += 1;
    cursor.setUTCDate(cursor.getUTCDate() + 1);
  }
  const projectedInterest = capitalizedInterest + Math.max(0, roundHalfUp(pendingInterest));
  return normalizeBankProjection({
    opened_on: openedOn,
    maturity_on: maturityOn,
    amount,
    annual_rate_bps: annualRateBps,
    accrual_days: accrualDays,
    projected_interest: projectedInterest,
    projected_balance: amount + projectedInterest,
  });
}

function normalizeBankDeposit(item) {
  if (!item) return null;
  return {
    id: String(item.id || ""),
    status: item.status || "active",
    openedOn: item.opened_on || "",
    maturityOn: item.maturity_on || "",
    closedAt: item.closed_at || "",
    closeReason: item.close_reason || "",
    principalAmount: Number(item.principal_amount || 0),
    capitalizedInterest: Number(item.capitalized_interest || 0),
    pendingInterest: String(item.pending_interest || "0"),
    pendingInterestRounded: Number(item.pending_interest_rounded || 0),
    bankBalance: Number(item.bank_balance || 0),
    returnedAmount: Number(item.returned_amount || 0),
    forfeitedInterest: Number(item.forfeited_interest || 0),
    daysRemaining: Number(item.days_remaining || 0),
  };
}

function normalizeBankHistoryEntry(item) {
  return {
    id: String(item.id || ""),
    operationType: item.operation_type || "",
    title: item.title || "Операция по вкладу",
    amount: Number(item.amount || 0),
    direction: item.direction || "neutral",
    principalAfter: Number(item.principal_after || 0),
    interestAfter: Number(item.interest_after || 0),
    bankBalanceAfter: Number(item.bank_balance_after || 0),
    walletAfter: item.wallet_after === null || item.wallet_after === undefined
      ? null
      : Number(item.wallet_after),
    annualRateBps: item.annual_rate_bps === null || item.annual_rate_bps === undefined
      ? null
      : Number(item.annual_rate_bps),
    effectiveOn: item.effective_on || "",
    comment: item.comment || "",
    createdAt: item.created_at || "",
  };
}

function normalizeBankSummary(item) {
  return {
    tenantSlug: item.tenant_slug || "",
    studentId: String(item.student_id || ""),
    studentName: item.student_name || "Ученик",
    studentStatus: item.student_status || "active",
    personalBalance: Number(item.personal_balance || 0),
    bankBalance: Number(item.bank_balance || 0),
    totalBalance: Number(item.total_balance || 0),
    annualRateBps: Number(item.annual_rate_bps || 0),
    canOpen: Boolean(item.can_open),
    canTopUp: Boolean(item.can_top_up),
    canCloseEarly: Boolean(item.can_close_early),
    deposit: normalizeBankDeposit(item.deposit),
    history: Array.isArray(item.history)
      ? item.history.map(normalizeBankHistoryEntry)
      : [],
  };
}

function normalizeBankSettings(item) {
  return {
    tenantSlug: item.tenant_slug || "",
    annualRateBps: Number(item.annual_rate_bps || 0),
    effectiveOn: item.effective_on || "",
    updatedAt: item.updated_at || "",
  };
}

function normalizeBankReport(item) {
  return {
    tenantSlug: item.tenant_slug || "",
    annualRateBps: Number(item.annual_rate_bps || 0),
    activeDeposits: Number(item.active_deposits || 0),
    totalPrincipal: Number(item.total_principal || 0),
    totalCapitalizedInterest: Number(item.total_capitalized_interest || 0),
    totalBankBalance: Number(item.total_bank_balance || 0),
    entries: Array.isArray(item.entries)
      ? item.entries.map((entry) => ({
          studentId: String(entry.student_id || ""),
          studentName: entry.student_name || "Ученик",
          groupName: entry.group_name || "",
          teacherName: entry.teacher_name || "",
          personalBalance: Number(entry.personal_balance || 0),
          principalAmount: Number(entry.principal_amount || 0),
          capitalizedInterest: Number(entry.capitalized_interest || 0),
          pendingInterest: String(entry.pending_interest || "0"),
          bankBalance: Number(entry.bank_balance || 0),
          totalBalance: Number(entry.total_balance || 0),
          annualRateBps: Number(entry.annual_rate_bps || 0),
          openedOn: entry.opened_on || "",
          maturityOn: entry.maturity_on || "",
          status: entry.status || "active",
        }))
      : [],
  };
}

function demoBankSummary(studentId) {
  const student = students.find((item) => item.id === studentId) || students[0];
  const hasDeposit = student?.id === "demo-alisa";
  const today = new Date();
  const opened = new Date(today);
  opened.setDate(opened.getDate() - 24);
  const maturity = new Date(today);
  maturity.setDate(maturity.getDate() + 90);
  const dateValue = (date) => {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  };
  const deposit = hasDeposit
    ? {
        id: `demo-bank-${student.id}`,
        status: "active",
        opened_on: dateValue(opened),
        maturity_on: dateValue(maturity),
        principal_amount: 600,
        capitalized_interest: 18,
        pending_interest: "3.428493150685",
        pending_interest_rounded: 3,
        bank_balance: 618,
        returned_amount: 0,
        forfeited_interest: 0,
        days_remaining: 90,
      }
    : null;
  const history = hasDeposit
    ? [
        {
          id: `demo-bank-interest-${student.id}`,
          operation_type: "interest_capitalized",
          title: "Начисление процентов",
          amount: 18,
          direction: "credit",
          principal_after: 600,
          interest_after: 18,
          bank_balance_after: 618,
          wallet_after: null,
          annual_rate_bps: 3650,
          effective_on: dateValue(opened),
          comment: "Проценты за прошлый месяц",
          created_at: new Date(today.getTime() - 7 * 86400000).toISOString(),
        },
        {
          id: `demo-bank-open-${student.id}`,
          operation_type: "opened",
          title: "Открытие вклада",
          amount: 600,
          direction: "debit",
          principal_after: 600,
          interest_after: 0,
          bank_balance_after: 600,
          wallet_after: Number(student?.balance || 0),
          annual_rate_bps: 3650,
          effective_on: dateValue(opened),
          comment: `Срок до ${bankDateLabel(dateValue(maturity))}`,
          created_at: opened.toISOString(),
        },
      ]
    : [];
  return normalizeBankSummary({
    tenant_slug: apiContext.tenantSlug || "demo",
    student_id: student?.id || studentId,
    student_name: student?.name || "Ученик",
    student_status: student?.status || "active",
    personal_balance: Number(student?.balance || 0),
    bank_balance: deposit?.bank_balance || 0,
    total_balance: Number(student?.balance || 0) + (deposit?.bank_balance || 0),
    annual_rate_bps: 3650,
    can_open: state.role === "student" && !deposit,
    can_top_up: state.role === "student" && Boolean(deposit),
    can_close_early: state.role === "student" && Boolean(deposit),
    deposit,
    history,
  });
}

function demoBankManagement() {
  const summaries = students.slice(0, 3).map((student, index) => {
    const summary = demoBankSummary(index === 0 ? "demo-alisa" : student.id);
    const principal = index === 0 ? 600 : 300 + index * 100;
    const interest = index === 0 ? 18 : 7 + index;
    return {
      student_id: student.id,
      student_name: student.name,
      group_name: student.group,
      teacher_name: student.teacher,
      personal_balance: student.balance,
      principal_amount: principal,
      capitalized_interest: interest,
      pending_interest: summary.deposit?.pendingInterest || "1.274",
      bank_balance: principal + interest,
      total_balance: student.balance + principal + interest,
      annual_rate_bps: 3650,
      opened_on: summary.deposit?.openedOn || bankDateInputValue(-14 - index),
      maturity_on: summary.deposit?.maturityOn || bankDateInputValue(60 + index * 30),
      status: "active",
    };
  });
  return {
    settings: normalizeBankSettings({
      tenant_slug: apiContext.tenantSlug || "demo",
      annual_rate_bps: 3650,
      effective_on: bankDateInputValue(0),
      updated_at: new Date().toISOString(),
    }),
    report: normalizeBankReport({
      tenant_slug: apiContext.tenantSlug || "demo",
      annual_rate_bps: 3650,
      active_deposits: summaries.length,
      total_principal: summaries.reduce((sum, item) => sum + item.principal_amount, 0),
      total_capitalized_interest: summaries.reduce(
        (sum, item) => sum + item.capitalized_interest,
        0,
      ),
      total_bank_balance: summaries.reduce((sum, item) => sum + item.bank_balance, 0),
      entries: summaries,
    }),
  };
}

function resetBankData() {
  state.bankSummary = null;
  state.bankLoadedStudentId = "";
  state.bankLoading = false;
  state.bankError = "";
  state.bankSettings = null;
  state.bankReport = null;
  state.bankManagementLoading = false;
  state.bankManagementError = "";
  state.studentBankById = new Map();
  state.studentBankLoading = new Set();
  state.studentBankErrors = new Map();
  state.bankRequestKeys = new Map();
}

async function fetchBankSummary(studentId) {
  const response = await apiFetch(
    apiUrl("/api/v1/miniapp/bank", {
      max_user_id: apiContext.maxUserId,
      tenant_slug: apiContext.tenantSlug,
      student_id: studentId,
      history_limit: 100,
    }),
  );
  if (!response.ok) throw new Error(await parseApiError(response));
  return normalizeBankSummary(await response.json());
}

async function loadBankData(force = false) {
  if (!roleViews(state.role).includes("bank") || !state.hasAccess) return;
  if (state.role === "admin") {
    if (state.bankManagementLoading || (state.bankSettings && state.bankReport && !force)) return;
    state.bankManagementLoading = true;
    state.bankManagementError = "";
    renderBankView();
    try {
      if (apiContext.demoMode) {
        const demo = demoBankManagement();
        state.bankSettings = demo.settings;
        state.bankReport = demo.report;
      } else {
        const params = {
          max_user_id: apiContext.maxUserId,
          tenant_slug: apiContext.tenantSlug,
        };
        const [settingsResponse, reportResponse] = await Promise.all([
          apiFetch(apiUrl("/api/v1/miniapp/bank/settings", params)),
          apiFetch(apiUrl("/api/v1/miniapp/bank/report", params)),
        ]);
        if (!settingsResponse.ok) throw new Error(await parseApiError(settingsResponse));
        if (!reportResponse.ok) throw new Error(await parseApiError(reportResponse));
        state.bankSettings = normalizeBankSettings(await settingsResponse.json());
        state.bankReport = normalizeBankReport(await reportResponse.json());
      }
    } catch (error) {
      state.bankManagementError = error.message || "Не удалось загрузить данные банка";
      if (force) throw error;
    } finally {
      state.bankManagementLoading = false;
      renderBankView();
    }
    return;
  }

  const studentId = String(state.activeStudentId || "");
  if (!studentId) {
    state.bankError = "Нет доступного профиля ученика";
    renderBankView();
    return;
  }
  if (
    state.bankLoading ||
    (!force && state.bankSummary && state.bankLoadedStudentId === studentId)
  ) return;
  state.bankLoading = true;
  state.bankError = "";
  if (state.bankLoadedStudentId !== studentId) state.bankSummary = null;
  state.bankLoadedStudentId = studentId;
  renderBankView();
  try {
    if (apiContext.demoMode) {
      state.bankSummary = state.bankSummary && state.bankSummary.studentId === studentId
        ? state.bankSummary
        : demoBankSummary(studentId);
    } else {
      state.bankSummary = await fetchBankSummary(studentId);
    }
    syncBankPersonalBalance(state.bankSummary);
  } catch (error) {
    state.bankError = error.message || "Не удалось загрузить вклад";
    if (force) throw error;
  } finally {
    state.bankLoading = false;
    renderBankView();
  }
}

async function loadStudentBank(studentId, force = false) {
  const normalizedId = String(studentId || "");
  if (!normalizedId || !["teacher", "admin"].includes(state.role)) return;
  if (
    state.studentBankLoading.has(normalizedId) ||
    (state.studentBankById.has(normalizedId) && !force)
  ) return;
  state.studentBankLoading.add(normalizedId);
  state.studentBankErrors.delete(normalizedId);
  renderStudentBankPanel(normalizedId);
  try {
    let summary;
    if (apiContext.demoMode) {
      summary = demoBankSummary(normalizedId);
      summary.canOpen = false;
      summary.canTopUp = false;
      summary.canCloseEarly = false;
    } else {
      const response = await apiFetch(
        apiUrl(`/api/v1/miniapp/students/${encodeURIComponent(normalizedId)}/bank`, {
          max_user_id: apiContext.maxUserId,
          tenant_slug: apiContext.tenantSlug,
          history_limit: 100,
        }),
      );
      if (!response.ok) throw new Error(await parseApiError(response));
      summary = normalizeBankSummary(await response.json());
    }
    state.studentBankById.set(normalizedId, summary);
  } catch (error) {
    state.studentBankErrors.set(
      normalizedId,
      error.message || "Не удалось загрузить банковские данные",
    );
  } finally {
    state.studentBankLoading.delete(normalizedId);
    renderStudentBankPanel(normalizedId);
  }
}

function syncBankPersonalBalance(summary) {
  if (!summary) return;
  const student = students.find((item) => item.id === summary.studentId);
  if (student) student.balance = summary.personalBalance;
  if (state.activeStudentId === summary.studentId) state.balance = summary.personalBalance;
  renderStatus();
  renderProducts();
  renderCart();
}

function bankBalanceMarkup(summary, compact = false) {
  const items = [
    ["Личный счет", summary.personalBalance, "wallet-cards"],
    ["В банке", summary.bankBalance, "landmark"],
    ["Всего AC", summary.totalBalance, "coins"],
  ];
  return `
    <div class="bank-balances ${compact ? "is-compact" : ""}">
      ${items.map(([label, amount, icon]) => `
        <div class="bank-balance-item">
          <i data-lucide="${icon}" aria-hidden="true"></i>
          <span>${label}</span>
          <strong>${Number(amount).toLocaleString("ru-RU")} AC</strong>
        </div>
      `).join("")}
    </div>
  `;
}

function bankDepositDetailsMarkup(summary, compact = false) {
  const deposit = summary.deposit;
  if (!deposit || deposit.status !== "active") return "";
  const fields = [
    ["Внесенная сумма", `${deposit.principalAmount.toLocaleString("ru-RU")} AC`],
    ["Причисленные проценты", `${deposit.capitalizedInterest.toLocaleString("ru-RU")} AC`],
    ["Ставка", `${bankRateLabel(summary.annualRateBps)} годовых`],
    ["Открыт", bankDateLabel(deposit.openedOn)],
    ["Завершится", bankDateLabel(deposit.maturityOn)],
    ["Осталось", `${deposit.daysRemaining} дн.`],
  ];
  if (!compact) {
    fields.push(["Предварительный доход", bankExactInterestLabel(deposit.pendingInterest)]);
  }
  return `
    <div class="bank-deposit-details ${compact ? "is-compact" : ""}">
      ${fields.map(([label, value]) => `
        <span><small>${label}</small><strong>${escapeHtml(value)}</strong></span>
      `).join("")}
    </div>
    ${compact ? "" : `
      <p class="bank-calculation-note">
        Предварительный доход еще не причислен, не входит в доступный баланс и может измениться при досрочном закрытии.
      </p>
    `}
  `;
}

function bankHistoryMarkup(history) {
  if (!history.length) {
    return '<div class="empty-state bank-empty-history">Операций по вкладу пока нет.</div>';
  }
  return `
    <div class="bank-history-list">
      ${history.map((entry) => {
        const sign = entry.direction === "debit" ? "−" : entry.direction === "credit" ? "+" : "";
        const amount = entry.direction === "neutral"
          ? (entry.annualRateBps === null ? "" : bankRateLabel(entry.annualRateBps))
          : `${sign}${entry.amount.toLocaleString("ru-RU")} AC`;
        return `
          <article class="bank-history-entry is-${escapeHtml(entry.direction)}">
            <span class="bank-history-icon" aria-hidden="true">
              <i data-lucide="${BANK_OPERATION_ICON[entry.operationType] || "landmark"}"></i>
            </span>
            <span class="bank-history-copy">
              <strong>${escapeHtml(entry.title)}</strong>
              ${entry.comment ? `<span>${escapeHtml(entry.comment)}</span>` : ""}
              <time datetime="${escapeHtml(entry.createdAt)}">${escapeHtml(studentLedgerDate(entry.createdAt))}</time>
            </span>
            <strong class="bank-history-amount">${escapeHtml(amount)}</strong>
          </article>
        `;
      }).join("")}
    </div>
  `;
}

function bankOpenFormMarkup(summary) {
  if (!summary.canOpen) {
    const message = state.role === "parent"
      ? "Вклад пока не открыт. Операции выполняет ребенок."
      : summary.studentStatus !== "active"
        ? "После завершения обучения открыть новый вклад нельзя."
        : "Открытие вклада сейчас недоступно.";
    return `<div class="bank-readonly-message"><i data-lucide="info"></i><span>${message}</span></div>`;
  }
  return `
    <form id="bankOpenForm" class="bank-action-form">
      <div class="bank-action-copy">
        <h3>Открыть вклад</h3>
        <p>Ставка ${bankRateLabel(summary.annualRateBps)} годовых. Выберите сумму и дату завершения.</p>
      </div>
      <label>
        <span>Сумма, AC</span>
        <input name="amount" type="number" min="1" max="${summary.personalBalance}" inputmode="numeric" required />
      </label>
      <label>
        <span>Конечная дата</span>
        <input name="maturity_on" type="date" min="${bankDateInputValue(1)}" max="${bankDateInputValue(365)}" required />
      </label>
      <button class="primary-action" type="submit" ${summary.personalBalance < 1 ? "disabled" : ""}>
        <i data-lucide="landmark"></i><span>Открыть вклад</span>
      </button>
    </form>
  `;
}

function bankActiveActionsMarkup(summary) {
  if (!summary.deposit) return "";
  if (!summary.canTopUp && !summary.canCloseEarly) {
    return '<div class="bank-readonly-message"><i data-lucide="eye"></i><span>Операции выполняет ребенок.</span></div>';
  }
  return `
    <div class="bank-active-actions">
      <form id="bankTopUpForm" class="bank-action-form is-inline">
        <div class="bank-action-copy">
          <h3>Пополнить вклад</h3>
          <p>Пополнение начнет увеличивать процентную базу со следующего дня.</p>
        </div>
        <label>
          <span>Сумма, AC</span>
          <input name="amount" type="number" min="1" max="${summary.personalBalance}" inputmode="numeric" required />
        </label>
        <button class="primary-action" type="submit" ${summary.personalBalance < 1 ? "disabled" : ""}>
          <i data-lucide="circle-plus"></i><span>Пополнить</span>
        </button>
      </form>
      <button class="secondary-action bank-early-close-button" type="button" data-bank-early-close>
        <i data-lucide="lock-open"></i><span>Закрыть досрочно</span>
      </button>
    </div>
  `;
}

function renderCustomerBank(summary) {
  const active = summary.deposit?.status === "active";
  const previousDeposit = summary.deposit && !active ? summary.deposit : null;
  return `
    <div class="section-heading bank-heading">
      <div>
        <p class="eyebrow">Астрокоины</p>
        <h2>Банк</h2>
        <span>${escapeHtml(summary.studentName)}</span>
      </div>
      <button class="secondary-action" type="button" data-bank-refresh aria-label="Обновить банк" title="Обновить банк">
        <i data-lucide="refresh-cw"></i><span>Обновить</span>
      </button>
    </div>
    ${bankBalanceMarkup(summary)}
    <section class="bank-account-section">
      ${active ? `
        <div class="bank-section-head">
          <div><p class="eyebrow">Вклад</p><h3>Действующий вклад</h3></div>
          <span class="status-badge ok">${BANK_DEPOSIT_STATUS.active}</span>
        </div>
        ${bankDepositDetailsMarkup(summary)}
        ${bankActiveActionsMarkup(summary)}
      ` : `
        ${previousDeposit ? `
          <div class="bank-closed-summary">
            <span class="status-badge warn">${escapeHtml(BANK_DEPOSIT_STATUS[previousDeposit.status] || "Закрыт")}</span>
            <strong>Последний вклад закрыт</strong>
            <span>Возвращено на личный счет: ${previousDeposit.returnedAmount.toLocaleString("ru-RU")} AC</span>
          </div>
        ` : ""}
        ${bankOpenFormMarkup(summary)}
      `}
    </section>
    <section class="bank-history-section">
      <div class="bank-section-head">
        <div><p class="eyebrow">Операции</p><h3>История вклада</h3></div>
        <span>${summary.history.length} записей</span>
      </div>
      ${bankHistoryMarkup(summary.history)}
    </section>
  `;
}

function bankReportFilteredEntries() {
  const entries = state.bankReport?.entries || [];
  const query = state.bankReportSearch.trim().toLocaleLowerCase("ru-RU");
  return entries.filter((entry) => {
    const matchesSearch = !query || [entry.studentName, entry.groupName, entry.teacherName]
      .join(" ")
      .toLocaleLowerCase("ru-RU")
      .includes(query);
    const matchesGroup = state.bankReportGroupFilter === "all"
      || entry.groupName === state.bankReportGroupFilter;
    const matchesStatus = state.bankReportStatusFilter === "all"
      || entry.status === state.bankReportStatusFilter;
    return matchesSearch && matchesGroup && matchesStatus;
  });
}

function renderBankManagement() {
  const settings = state.bankSettings;
  const report = state.bankReport;
  const groups = [...new Set((report?.entries || []).map((entry) => entry.groupName).filter(Boolean))]
    .sort((left, right) => left.localeCompare(right, "ru"));
  const entries = bankReportFilteredEntries();
  return `
    <div class="section-heading bank-heading">
      <div>
        <p class="eyebrow">Управление</p>
        <h2>Банк</h2>
        <span>Ставка и остатки по выбранному городу</span>
      </div>
      <button class="secondary-action" type="button" data-bank-refresh aria-label="Обновить банк" title="Обновить банк">
        <i data-lucide="refresh-cw"></i><span>Обновить</span>
      </button>
    </div>
    <section class="bank-rate-section">
      <div class="bank-section-head">
        <div><p class="eyebrow">Настройка города</p><h3>Процентная ставка</h3></div>
        <span>Действует с ${bankDateLabel(settings.effectiveOn)}</span>
      </div>
      <form id="bankRateForm" class="bank-rate-form">
        <label>
          <span>Процент годовых</span>
          <span class="bank-rate-input"><input name="annual_rate" type="number" min="0" max="100" step="0.01" value="${(settings.annualRateBps / 100).toFixed(2)}" required /><b>%</b></span>
        </label>
        <button class="primary-action" type="submit">
          <i data-lucide="save"></i><span>Сохранить</span>
        </button>
      </form>
    </section>
    <section class="bank-report-section">
      <div class="bank-section-head">
        <div><p class="eyebrow">Контроль</p><h3>Остатки по вкладам</h3></div>
        <span>${entries.length} из ${(report?.entries || []).length}</span>
      </div>
      <div class="bank-report-metrics">
        <span><small>Активных вкладов</small><strong>${report.activeDeposits}</strong></span>
        <span><small>Внесено</small><strong>${report.totalPrincipal.toLocaleString("ru-RU")} AC</strong></span>
        <span><small>Проценты</small><strong>${report.totalCapitalizedInterest.toLocaleString("ru-RU")} AC</strong></span>
        <span><small>Всего в банке</small><strong>${report.totalBankBalance.toLocaleString("ru-RU")} AC</strong></span>
      </div>
      <div class="bank-report-filters">
        <label class="search-field">
          <i data-lucide="search"></i>
          <input id="bankReportSearch" type="search" value="${escapeHtml(state.bankReportSearch)}" placeholder="ФИО, группа или преподаватель" />
        </label>
        <select id="bankReportGroupFilter" aria-label="Группа">
          <option value="all">Все группы</option>
          ${groups.map((group) => `<option value="${escapeHtml(group)}" ${state.bankReportGroupFilter === group ? "selected" : ""}>${escapeHtml(group)}</option>`).join("")}
        </select>
        <select id="bankReportStatusFilter" aria-label="Статус вклада">
          <option value="all">Все статусы</option>
          ${Object.entries(BANK_DEPOSIT_STATUS).map(([value, label]) => `<option value="${value}" ${state.bankReportStatusFilter === value ? "selected" : ""}>${label}</option>`).join("")}
        </select>
      </div>
      <div class="bank-report-list">
        ${entries.length ? entries.map((entry) => `
          <article class="bank-report-row">
            <span class="bank-report-student">
              <strong>${escapeHtml(entry.studentName)}</strong>
              <small>${escapeHtml([entry.groupName, entry.teacherName].filter(Boolean).join(" · ") || "Группа не указана")}</small>
            </span>
            <span><small>Личный счет</small><strong>${entry.personalBalance.toLocaleString("ru-RU")} AC</strong></span>
            <span><small>В банке</small><strong>${entry.bankBalance.toLocaleString("ru-RU")} AC</strong></span>
            <span><small>Внесено</small><strong>${entry.principalAmount.toLocaleString("ru-RU")} AC</strong></span>
            <span><small>Проценты</small><strong>${entry.capitalizedInterest.toLocaleString("ru-RU")} AC</strong></span>
            <span><small>Всего AC</small><strong>${entry.totalBalance.toLocaleString("ru-RU")} AC</strong></span>
            <span><small>Ставка</small><strong>${bankRateLabel(entry.annualRateBps)}</strong></span>
            <span><small>Срок</small><strong>${bankDateLabel(entry.openedOn)} – ${bankDateLabel(entry.maturityOn)}</strong></span>
            <span class="status-badge ${entry.status === "active" ? "ok" : "warn"}">${escapeHtml(BANK_DEPOSIT_STATUS[entry.status] || entry.status)}</span>
          </article>
        `).join("") : '<div class="empty-state bank-report-empty">Вклады по выбранным фильтрам не найдены.</div>'}
      </div>
    </section>
  `;
}

function renderBankView() {
  const content = qs("#bankContent");
  if (!content) return;
  if (!roleViews(state.role).includes("bank")) {
    content.innerHTML = "";
    return;
  }
  const loading = state.role === "admin" ? state.bankManagementLoading : state.bankLoading;
  const error = state.role === "admin" ? state.bankManagementError : state.bankError;
  if (loading && !(state.bankSummary || (state.bankSettings && state.bankReport))) {
    content.innerHTML = `
      <div class="bank-loading" role="status">
        <span class="button-spinner" aria-hidden="true"></span>
        <strong>Загружаем банк</strong>
      </div>
    `;
    return;
  }
  if (error) {
    content.innerHTML = `
      <div class="empty-state bank-error-state">
        <i data-lucide="circle-alert"></i>
        <strong>Не удалось загрузить банк</strong>
        <span>${escapeHtml(error)}</span>
        <button class="secondary-action" type="button" data-bank-refresh aria-label="Повторить загрузку банка" title="Повторить загрузку банка"><i data-lucide="refresh-cw"></i><span>Повторить</span></button>
      </div>
    `;
    refreshIcons();
    return;
  }
  if (state.role === "admin" && state.bankSettings && state.bankReport) {
    content.innerHTML = renderBankManagement();
  } else if (state.bankSummary && state.bankLoadedStudentId === state.activeStudentId) {
    content.innerHTML = renderCustomerBank(state.bankSummary);
  } else {
    content.innerHTML = `
      <div class="bank-loading" role="status">
        <span class="button-spinner" aria-hidden="true"></span>
        <strong>Загружаем банк</strong>
      </div>
    `;
  }
  refreshIcons();
}

function studentBankCardMarkup(studentId) {
  const normalizedId = String(studentId || "");
  if (state.studentBankLoading.has(normalizedId)) {
    return '<div class="student-ledger-state"><span class="button-spinner" aria-hidden="true"></span><span>Загружаем банк</span></div>';
  }
  const error = state.studentBankErrors.get(normalizedId);
  if (error) {
    return `
      <div class="student-ledger-state is-error">
        <span>${escapeHtml(error)}</span>
        <button class="text-action" type="button" data-retry-student-bank="${escapeHtml(normalizedId)}">Повторить</button>
      </div>
    `;
  }
  if (!state.studentBankById.has(normalizedId)) {
    return '<div class="student-ledger-state">Данные загрузятся после открытия карточки.</div>';
  }
  const summary = state.studentBankById.get(normalizedId);
  const active = summary.deposit?.status === "active";
  return `
    ${bankBalanceMarkup(summary, true)}
    ${active
      ? bankDepositDetailsMarkup(summary, true)
      : `<div class="bank-readonly-message"><i data-lucide="landmark"></i><span>${summary.deposit ? BANK_DEPOSIT_STATUS[summary.deposit.status] || "Вклад закрыт" : "Вклад не открыт"}</span></div>`}
  `;
}

function renderStudentBankPanel(studentId) {
  const panel = qsa("[data-student-bank-panel]").find(
    (item) => item.dataset.studentBankPanel === String(studentId || ""),
  );
  if (!panel) return;
  panel.innerHTML = studentBankCardMarkup(studentId);
  refreshIcons();
}

function bankRequestKey(action, payload) {
  const signature = `${action}:${JSON.stringify(payload)}`;
  if (!state.bankRequestKeys.has(signature)) {
    state.bankRequestKeys.set(signature, createRequestKey());
  }
  return { signature, requestKey: state.bankRequestKeys.get(signature) };
}

function applyDemoBankMutation(action, payload) {
  const summary = state.bankSummary || demoBankSummary(state.activeStudentId);
  const now = new Date().toISOString();
  if (action === "open") {
    summary.personalBalance -= payload.amount;
    summary.bankBalance = payload.amount;
    summary.totalBalance = summary.personalBalance + summary.bankBalance;
    summary.deposit = normalizeBankDeposit({
      id: `demo-bank-${summary.studentId}-${Date.now()}`,
      status: "active",
      opened_on: bankDateInputValue(0),
      maturity_on: payload.maturity_on,
      principal_amount: payload.amount,
      capitalized_interest: 0,
      pending_interest: "0",
      pending_interest_rounded: 0,
      bank_balance: payload.amount,
      days_remaining: Math.max(
        0,
        Math.round(
          (new Date(`${payload.maturity_on}T12:00:00`) - new Date(`${bankDateInputValue(0)}T12:00:00`))
            / 86400000,
        ),
      ),
    });
    summary.history.unshift(normalizeBankHistoryEntry({
      id: `demo-open-${Date.now()}`,
      operation_type: "opened",
      title: "Открытие вклада",
      amount: payload.amount,
      direction: "debit",
      principal_after: payload.amount,
      interest_after: 0,
      bank_balance_after: payload.amount,
      wallet_after: summary.personalBalance,
      annual_rate_bps: summary.annualRateBps,
      effective_on: bankDateInputValue(0),
      created_at: now,
    }));
  } else if (action === "topup" && summary.deposit) {
    summary.personalBalance -= payload.amount;
    summary.deposit.principalAmount += payload.amount;
    summary.deposit.bankBalance += payload.amount;
    summary.bankBalance = summary.deposit.bankBalance;
    summary.totalBalance = summary.personalBalance + summary.bankBalance;
    summary.history.unshift(normalizeBankHistoryEntry({
      id: `demo-topup-${Date.now()}`,
      operation_type: "topped_up",
      title: "Пополнение вклада",
      amount: payload.amount,
      direction: "debit",
      principal_after: summary.deposit.principalAmount,
      interest_after: summary.deposit.capitalizedInterest,
      bank_balance_after: summary.deposit.bankBalance,
      wallet_after: summary.personalBalance,
      annual_rate_bps: summary.annualRateBps,
      effective_on: bankDateInputValue(0),
      created_at: now,
    }));
  } else if (action === "close" && summary.deposit) {
    const returned = summary.deposit.principalAmount;
    const forfeited = summary.deposit.capitalizedInterest;
    summary.personalBalance += returned;
    summary.deposit.status = "early_closed";
    summary.deposit.closedAt = now;
    summary.deposit.returnedAmount = returned;
    summary.deposit.forfeitedInterest = forfeited;
    summary.deposit.pendingInterest = "0";
    summary.deposit.pendingInterestRounded = 0;
    summary.deposit.bankBalance = 0;
    summary.deposit.daysRemaining = 0;
    summary.bankBalance = 0;
    summary.totalBalance = summary.personalBalance;
    summary.history.unshift(normalizeBankHistoryEntry({
      id: `demo-close-${Date.now()}`,
      operation_type: "early_closed",
      title: "Досрочное закрытие вклада",
      amount: returned,
      direction: "credit",
      principal_after: 0,
      interest_after: 0,
      bank_balance_after: 0,
      wallet_after: summary.personalBalance,
      annual_rate_bps: summary.annualRateBps,
      effective_on: bankDateInputValue(0),
      comment: `Аннулировано процентов: ${forfeited} AC`,
      created_at: now,
    }));
  }
  summary.canOpen = state.role === "student" && summary.deposit?.status !== "active";
  summary.canTopUp = state.role === "student" && summary.deposit?.status === "active";
  summary.canCloseEarly = summary.canTopUp;
  return summary;
}

function openBankConfirmation(confirmation, trigger) {
  const dialog = qs("#bankConfirmationDialog");
  if (!dialog || state.bankMutationSaving || state.bankRateSaving) return;
  state.bankConfirmation = confirmation;
  state.bankConfirmationReturnFocus = trigger instanceof HTMLElement ? trigger : null;
  qs("#bankConfirmationTitle").textContent = confirmation.title;
  qs("#bankConfirmationDescription").innerHTML = confirmation.content;
  const confirmButton = qs("#confirmBankActionButton");
  confirmButton.disabled = false;
  confirmButton.textContent = confirmation.confirmLabel || "Подтвердить";
  confirmButton.classList.toggle("is-danger", confirmation.tone === "danger");
  dialog.hidden = false;
  document.body.classList.add("dialog-open");
  refreshIcons();
  window.setTimeout(() => confirmButton.focus(), 40);
}

function closeBankConfirmation({ restoreFocus = true } = {}) {
  const dialog = qs("#bankConfirmationDialog");
  if (dialog) dialog.hidden = true;
  document.body.classList.remove("dialog-open");
  const returnFocus = state.bankConfirmationReturnFocus;
  const confirmButton = qs("#confirmBankActionButton");
  if (confirmButton) confirmButton.disabled = false;
  state.bankConfirmation = null;
  state.bankConfirmationReturnFocus = null;
  if (restoreFocus) returnFocus?.focus();
}

async function executeBankMutation(action, payload, endpoint) {
  if (state.bankMutationSaving) return;
  const key = bankRequestKey(action, payload);
  state.bankMutationSaving = true;
  const confirmButton = qs("#confirmBankActionButton");
  if (confirmButton) confirmButton.disabled = true;
  try {
    let summary;
    if (apiContext.demoMode) {
      await new Promise((resolve) => window.setTimeout(resolve, 120));
      summary = applyDemoBankMutation(action, payload);
    } else {
      const response = await apiFetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          max_user_id: Number(apiContext.maxUserId),
          tenant_slug: apiContext.tenantSlug || undefined,
          ...payload,
          request_key: key.requestKey,
        }),
      });
      if (!response.ok) throw new Error(await parseApiError(response));
      summary = normalizeBankSummary(await response.json());
    }
    state.bankRequestKeys.delete(key.signature);
    state.bankSummary = summary;
    state.bankLoadedStudentId = summary.studentId;
    state.bankError = "";
    syncBankPersonalBalance(summary);
    if (state.bankConfirmation?.action === action) {
      closeBankConfirmation({ restoreFocus: false });
    }
    renderBankView();
    showNotice({
      open: "Вклад открыт",
      topup: "Вклад пополнен",
      close: "Вклад закрыт досрочно",
    }[action] || "Операция выполнена");
  } catch (error) {
    showNotice(error.message || "Не удалось выполнить операцию", "danger");
  } finally {
    state.bankMutationSaving = false;
    if (confirmButton?.isConnected) confirmButton.disabled = false;
  }
}

async function submitBankTopUp(form) {
  if (!state.bankSummary?.deposit || state.bankMutationSaving || !form.reportValidity()) return;
  const amount = Number.parseInt(new FormData(form).get("amount"), 10);
  if (!Number.isInteger(amount) || amount < 1 || amount > state.bankSummary.personalBalance) {
    showNotice("Укажите сумму не больше личного баланса", "danger");
    return;
  }
  const submitButton = form.querySelector("button[type='submit']");
  const earlyCloseButton = qs("[data-bank-early-close]");
  if (submitButton) submitButton.disabled = true;
  if (earlyCloseButton) earlyCloseButton.disabled = true;
  await executeBankMutation(
    "topup",
    { amount },
    `/api/v1/miniapp/bank/deposits/${encodeURIComponent(state.bankSummary.deposit.id)}/top-ups`,
  );
  if (submitButton?.isConnected) submitButton.disabled = false;
  if (earlyCloseButton?.isConnected) earlyCloseButton.disabled = false;
}

async function loadBankDepositProjection({ amount, maturityOn }) {
  if (!state.bankSummary) throw new Error("Данные банка еще не загружены");
  if (apiContext.demoMode) {
    return projectDemoBankDeposit({
      amount,
      annualRateBps: state.bankSummary.annualRateBps,
      openedOn: bankDateInputValue(0),
      maturityOn,
    });
  }
  const response = await apiFetch("/api/v1/miniapp/bank/deposits/preview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      max_user_id: Number(apiContext.maxUserId),
      tenant_slug: apiContext.tenantSlug || undefined,
      student_id: state.bankSummary.studentId,
      amount,
      maturity_on: maturityOn,
    }),
  });
  if (!response.ok) throw new Error(await parseApiError(response));
  return normalizeBankProjection(await response.json());
}

async function prepareBankOpenConfirmation(form) {
  if (state.bankMutationSaving || form.dataset.bankPreviewLoading === "true") return;
  if (!form.reportValidity() || !state.bankSummary) return;
  const data = new FormData(form);
  const amount = Number.parseInt(data.get("amount"), 10);
  const maturityOn = String(data.get("maturity_on") || "");
  if (!Number.isInteger(amount) || amount < 1 || amount > state.bankSummary.personalBalance) {
    showNotice("Укажите сумму не больше личного баланса", "danger");
    return;
  }

  const submitButton = form.querySelector("button[type='submit']");
  form.dataset.bankPreviewLoading = "true";
  if (submitButton) submitButton.disabled = true;
  try {
    const projection = await loadBankDepositProjection({ amount, maturityOn });
    openBankConfirmation({
      type: "mutation",
      action: "open",
      title: "Открыть вклад?",
      confirmLabel: "Открыть вклад",
      payload: {
        student_id: state.bankSummary.studentId,
        amount,
        maturity_on: maturityOn,
      },
      endpoint: "/api/v1/miniapp/bank/deposits",
      content: `
        <div class="bank-confirmation-summary has-projection">
          <span><small>С личного счета</small><strong>−${amount.toLocaleString("ru-RU")} AC</strong></span>
          <span><small>Дата завершения</small><strong>${bankDateLabel(maturityOn)}</strong></span>
          <span><small>Ставка</small><strong>${bankRateLabel(projection.annualRateBps)} годовых</strong></span>
          <span class="bank-confirmation-projection">
            <small>Расчетный доход</small>
            <strong>+${projection.projectedInterest.toLocaleString("ru-RU")} AC</strong>
            <em>Итого ${projection.projectedBalance.toLocaleString("ru-RU")} AC</em>
          </span>
        </div>
        <p>Доход рассчитан при условии, что текущая сумма и ставка не изменятся до даты завершения.</p>
        <p>Частично снять деньги нельзя. Доступно только полное досрочное закрытие с потерей всех процентов.</p>
      `,
    }, submitButton);
  } catch (error) {
    showNotice(error.message || "Не удалось рассчитать доход", "danger");
  } finally {
    delete form.dataset.bankPreviewLoading;
    if (submitButton?.isConnected) submitButton.disabled = false;
  }
}

async function confirmBankAction() {
  const confirmation = state.bankConfirmation;
  if (!confirmation) return;
  if (confirmation.type === "rate") {
    await saveBankRate(confirmation.annualRateBps);
    return;
  }
  await executeBankMutation(confirmation.action, confirmation.payload, confirmation.endpoint);
}

async function saveBankRate(annualRateBps) {
  if (state.bankRateSaving) return;
  state.bankRateSaving = true;
  const button = qs("#confirmBankActionButton");
  if (button) button.disabled = true;
  try {
    if (apiContext.demoMode) {
      state.bankSettings.annualRateBps = annualRateBps;
      state.bankSettings.effectiveOn = bankDateInputValue(0);
      state.bankReport.annualRateBps = annualRateBps;
      state.bankReport.entries.forEach((entry) => { entry.annualRateBps = annualRateBps; });
    } else {
      const response = await apiFetch("/api/v1/miniapp/bank/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          max_user_id: Number(apiContext.maxUserId),
          tenant_slug: apiContext.tenantSlug || undefined,
          annual_rate_bps: annualRateBps,
        }),
      });
      if (!response.ok) throw new Error(await parseApiError(response));
      state.bankSettings = normalizeBankSettings(await response.json());
      const reportResponse = await apiFetch(
        apiUrl("/api/v1/miniapp/bank/report", {
          max_user_id: apiContext.maxUserId,
          tenant_slug: apiContext.tenantSlug,
        }),
      );
      if (!reportResponse.ok) throw new Error(await parseApiError(reportResponse));
      state.bankReport = normalizeBankReport(await reportResponse.json());
    }
    closeBankConfirmation({ restoreFocus: false });
    renderBankView();
    showNotice(`Ставка ${bankRateLabel(annualRateBps)} действует с сегодняшнего дня`);
  } catch (error) {
    showNotice(error.message || "Не удалось изменить ставку", "danger");
  } finally {
    state.bankRateSaving = false;
    if (button?.isConnected) button.disabled = false;
  }
}

document.addEventListener("submit", (event) => {
  const form = event.target;
  if (!(form instanceof HTMLFormElement)) return;
  if (form.id === "bankOpenForm") {
    event.preventDefault();
    void prepareBankOpenConfirmation(form);
  } else if (form.id === "bankTopUpForm") {
    event.preventDefault();
    void submitBankTopUp(form);
  } else if (form.id === "bankRateForm") {
    event.preventDefault();
    if (!form.reportValidity() || !state.bankSettings) return;
    const rate = Number(new FormData(form).get("annual_rate"));
    const rateBps = Math.round(rate * 100);
    if (!Number.isFinite(rate) || rateBps < 0 || rateBps > 10000) {
      showNotice("Укажите ставку от 0 до 100%", "danger");
      return;
    }
    if (rateBps === state.bankSettings.annualRateBps) {
      showNotice("Ставка не изменилась");
      return;
    }
    openBankConfirmation({
      type: "rate",
      title: "Изменить ставку?",
      confirmLabel: "Изменить ставку",
      annualRateBps: rateBps,
      content: `
        <div class="bank-confirmation-summary">
          <span><small>Текущая ставка</small><strong>${bankRateLabel(state.bankSettings.annualRateBps)}</strong></span>
          <span><small>Новая ставка</small><strong>${bankRateLabel(rateBps)}</strong></span>
        </div>
        <p>Новая ставка применяется ко всем действующим вкладам с сегодняшнего дня. Ранее начисленные проценты не пересчитываются.</p>
      `,
    }, form.querySelector("button[type='submit']"));
  }
});

document.addEventListener("click", (event) => {
  const target = event.target instanceof Element ? event.target.closest("button") : null;
  if (!target) return;
  if ("bankRefresh" in target.dataset) {
    void loadBankData(true).catch((error) => {
      showNotice(error.message || "Не удалось обновить банк", "danger");
    });
    return;
  }
  const retryStudentId = target.dataset.retryStudentBank;
  if (retryStudentId) {
    void loadStudentBank(retryStudentId, true);
    return;
  }
  const ledgerFilter = target.dataset.studentLedgerFilter;
  const ledgerStudentId = target.dataset.studentId;
  if (ledgerFilter && ledgerStudentId) {
    state.studentLedgerFilterById.set(ledgerStudentId, ledgerFilter);
    renderStudentLedgerPanel(ledgerStudentId);
    return;
  }
  if ("bankEarlyClose" in target.dataset && state.bankSummary?.deposit) {
    if (state.bankMutationSaving) {
      showNotice("Дождитесь завершения текущей операции", "danger");
      return;
    }
    const deposit = state.bankSummary.deposit;
    openBankConfirmation({
      type: "mutation",
      action: "close",
      title: "Закрыть вклад досрочно?",
      confirmLabel: "Закрыть вклад",
      tone: "danger",
      payload: { expected_return_amount: deposit.principalAmount },
      endpoint: `/api/v1/miniapp/bank/deposits/${encodeURIComponent(deposit.id)}/early-close`,
      content: `
        <div class="bank-confirmation-summary is-danger">
          <span><small>Вернется на личный счет</small><strong>${deposit.principalAmount.toLocaleString("ru-RU")} AC</strong></span>
          <span><small>Будет аннулировано</small><strong>${deposit.capitalizedInterest.toLocaleString("ru-RU")} AC</strong></span>
          <span><small>Непричисленный доход</small><strong>${bankExactInterestLabel(deposit.pendingInterest)}</strong></span>
        </div>
        <p>Все проценты будут потеряны. Это действие необратимо.</p>
      `,
    }, target);
    return;
  }
  if (
    target.id === "closeBankConfirmationButton" ||
    target.id === "cancelBankConfirmationButton"
  ) {
    closeBankConfirmation();
    return;
  }
  if (target.id === "confirmBankActionButton") {
    void confirmBankAction();
  }
});

document.addEventListener("input", (event) => {
  if (!(event.target instanceof HTMLInputElement) || event.target.id !== "bankReportSearch") return;
  state.bankReportSearch = event.target.value;
  renderBankView();
  const input = qs("#bankReportSearch");
  input?.focus();
  input?.setSelectionRange(state.bankReportSearch.length, state.bankReportSearch.length);
});

document.addEventListener("change", (event) => {
  if (!(event.target instanceof HTMLSelectElement)) return;
  if (event.target.id === "bankReportGroupFilter") {
    state.bankReportGroupFilter = event.target.value;
    renderBankView();
  } else if (event.target.id === "bankReportStatusFilter") {
    state.bankReportStatusFilter = event.target.value;
    renderBankView();
  }
});

qs("#bankConfirmationDialog")?.addEventListener("click", (event) => {
  if (event.target === event.currentTarget) closeBankConfirmation();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !qs("#bankConfirmationDialog")?.hidden) {
    closeBankConfirmation();
  }
});
