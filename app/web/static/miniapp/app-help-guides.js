let helpGuideId = "";
const HELP_GUIDE_ASSET_VERSION = "0.91.66";

function helpMediaRecord(question) {
  return typeof HELP_MEDIA_CATALOG === "undefined" ? null : HELP_MEDIA_CATALOG[question] || null;
}

function availableHelpGuides() {
  if (typeof HELP_TOP_GUIDES === "undefined") return [];
  return HELP_TOP_GUIDES.filter((guide) => {
    const item = HELP_FAQ_ITEMS.find((entry) => entry.question === guide.question);
    return item && helpItemVisible(item) && (helpAudience() === "staff"
      || guide.audiences?.includes(helpAudience()));
  });
}

function helpMediaMarkup(record, question) {
  const base = `/miniapp/static/assets/help/guides/${encodeURIComponent(record.id)}`;
  return `<div class="help-guide-media"><video controls playsinline preload="none" tabindex="0"
      poster="${base}.png?v=${HELP_GUIDE_ASSET_VERSION}" aria-label="${escapeHtml(record.title || question)}">
      <source src="${base}.mp4?v=${HELP_GUIDE_ASSET_VERSION}" type="video/mp4" />
      <track kind="captions" src="${base}.vtt?v=${HELP_GUIDE_ASSET_VERSION}" srclang="ru" label="Русский" />
      <a href="${base}.mp4?v=${HELP_GUIDE_ASSET_VERSION}">Скачать видео</a></video>
      <div class="help-guide-video-error" role="alert" hidden><p>Видео не загрузилось. Продолжите по шагам из ответа. Если проблема повторяется, сообщите в поддержку.</p>
        <button type="button" class="secondary-action" data-help-support="${escapeHtml(question)}"><i data-lucide="message-circle" aria-hidden="true"></i>Сообщить о проблеме</button></div></div>`;
}

function bindHelpVideo(container) {
  const video = container.querySelector("video");
  if (!video || video.dataset.helpBound) return;
  video.dataset.helpBound = "1";
  const showError = () => {
    if (!video.isConnected || !container.contains(video)) return;
    const fallback = container.querySelector(".help-guide-video-error");
    if (fallback && container.isConnected) fallback.hidden = false;
  };
  video.addEventListener("error", showError);
  video.querySelector("source")?.addEventListener("error", showError);
  video.addEventListener("loadedmetadata", () => {
    if (video.dataset.pendingTime == null) return;
    video.currentTime = Math.min(Number(video.dataset.pendingTime), Math.max(0, video.duration - .1));
    delete video.dataset.pendingTime;
  });
}

function pauseHelpVideos(except = null) {
  qsa("#helpView video").forEach((video) => { if (video !== except) video.pause(); });
}

function renderHelpGuides() {
  const root = qs("#helpGuides");
  if (!root) return;
  const guides = availableHelpGuides().filter((guide) => helpMediaRecord(guide.question));
  const key = `${helpAudience()}:${guides.map((guide) => guide.id).join(",")}`;
  if (root.dataset.renderKey === key) return;
  root.querySelector("video")?.pause();
  root.dataset.renderKey = key;
  root.hidden = !guides.length;
  if (!guides.length) { root.innerHTML = ""; return; }
  if (!guides.some((guide) => guide.id === helpGuideId)) {
    const preferred = helpAudience() === "staff" ? "import-students" : helpAudience();
    const staffStart = helpAudience() === "staff"
      ? guides.find((guide) => guide.question === "Как загрузить учеников из Excel?") : null;
    helpGuideId = (staffStart || guides.find((guide) => guide.id === preferred) || guides[0]).id;
  }
  root.innerHTML = `<header class="help-guides-heading"><h2>Пошаговые видео</h2></header>
    <div class="help-guide-picker"><label for="helpGuideSelect" class="sr-only">Выберите видеоинструкцию</label>
      <select id="helpGuideSelect" aria-controls="helpGuidePanel">${guides.map((guide) => `<option value="${escapeHtml(guide.id)}" ${guide.id === helpGuideId ? "selected" : ""}>${escapeHtml(guide.label)}</option>`).join("")}</select>
      <button type="button" class="icon-button" data-help-guide-prev aria-label="Предыдущее видео" title="Предыдущее видео"><i data-lucide="chevron-left" aria-hidden="true"></i></button>
      <button type="button" class="icon-button" data-help-guide-next aria-label="Следующее видео" title="Следующее видео"><i data-lucide="chevron-right" aria-hidden="true"></i></button></div>
    <div id="helpGuidePanel" class="help-guide-panel" role="region" aria-label="Видеоинструкция"></div>`;
  selectHelpGuide(helpGuideId);
}

function selectHelpGuide(id) {
  const guide = availableHelpGuides().find((item) => item.id === id);
  const panel = qs("#helpGuidePanel");
  const record = guide && helpMediaRecord(guide.question);
  if (!record || !panel) return;
  panel.querySelector("video")?.pause();
  helpGuideId = id;
  qs("#helpGuideSelect").value = id;
  const steps = record.steps || [];
  const base = `/miniapp/static/assets/help/guides/${encodeURIComponent(record.id)}`;
  panel.innerHTML = `${helpMediaMarkup(record, guide.question)}
    <div class="help-guide-transcript"><h3>${escapeHtml(record.title || guide.label)}</h3><ol>${steps.map(([time, title, text], index) => `<li><button type="button" class="help-guide-step" data-help-video-time="${Number(time)}" title="Перейти к шагу ${index + 1} в видео"><span>${index + 1}</span><strong>${escapeHtml(title)}</strong><i data-lucide="play" aria-hidden="true"></i></button>${text ? `<p>${escapeHtml(text)}</p>` : ""}</li>`).join("")}</ol>
      <div class="help-guide-actions"><a class="help-guide-download" href="${base}.mp4?v=${HELP_GUIDE_ASSET_VERSION}" download><i data-lucide="download" aria-hidden="true"></i>Скачать видео</a>
      <button type="button" class="text-action" data-help-open-question="${escapeHtml(guide.question)}">Открыть полный ответ<i data-lucide="arrow-down" aria-hidden="true"></i></button></div></div>`;
  bindHelpVideo(panel);
  refreshIcons();
}

function mountHelpFaqVideo(details, item) {
  const container = details.querySelector(".help-faq-video");
  const record = helpMediaRecord(item.question);
  if (!container || container.querySelector("video") || !record || !helpItemVisible(item)) return;
  container.innerHTML = helpMediaMarkup(record, item.question);
  bindHelpVideo(container);
}

function helpOpenSupport(question) {
  const item = HELP_FAQ_ITEMS.find((entry) => entry.question === question);
  if (!item || !helpItemVisible(item) || typeof supportOpenForm !== "function") return;
  pauseHelpVideos();
  supportOpenForm();
  const form = qs("#supportForm");
  if (!form) return;
  if (!form.elements.role.value) supportSetRole(helpAudience() === "staff" ? "staff" : helpAudience());
  if (!form.elements.message.value.trim()) {
    form.elements.message.value = `Вопрос из справки: ${question}\n\nЧто я пытался сделать:\nНа каком шаге остановился:\nТекст ошибки и время:\n`;
    supportSaveDraft();
  }
  window.setTimeout(() => {
    if (qs("#supportDialog").hidden) return;
    const field = form.elements.first_name.value.trim() ? form.elements.message : form.elements.first_name;
    field.focus();
  }, 0);
}

document.addEventListener("change", (event) => {
  if (event.target.id === "helpGuideSelect") selectHelpGuide(event.target.value);
});
document.addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (!button) return;
  if (button.hasAttribute("data-help-support")) helpOpenSupport(button.dataset.helpSupport);
  if (button.hasAttribute("data-help-guide-prev") || button.hasAttribute("data-help-guide-next")) {
    const guides = availableHelpGuides().filter((guide) => helpMediaRecord(guide.question));
    const index = guides.findIndex((guide) => guide.id === helpGuideId);
    const offset = button.hasAttribute("data-help-guide-prev") ? -1 : 1;
    if (guides.length) selectHelpGuide(guides[(index + offset + guides.length) % guides.length].id);
  }
  if (button.hasAttribute("data-help-video-time")) {
    const video = button.closest(".help-guide-panel")?.querySelector("video");
    if (!video) return;
    video.pause();
    if (video.readyState) video.currentTime = Math.min(Number(button.dataset.helpVideoTime), Math.max(0, video.duration - .1));
    else { video.dataset.pendingTime = button.dataset.helpVideoTime; video.load(); }
    video.focus();
  }
  if (button.hasAttribute("data-help-open-question")) {
    const question = button.dataset.helpOpenQuestion;
    helpFaqState.query = "";
    helpFaqState.renderKey = "";
    renderHelpFaq();
    const details = qsa(".help-faq-item").find((item) => item.dataset.helpQuestion === question);
    if (details) {
      details.open = true;
      details.scrollIntoView({behavior: "auto", block: "start"});
      details.querySelector("summary").focus({preventScroll: true});
    }
  }
  if (button.matches("[data-view], [data-view-jump], [data-support-tab='inbox'], [data-support-open]")) pauseHelpVideos();
});
document.addEventListener("play", (event) => {
  if (event.target.matches("#helpView video")) pauseHelpVideos(event.target);
}, true);
document.addEventListener("visibilitychange", () => { if (document.hidden) pauseHelpVideos(); });
