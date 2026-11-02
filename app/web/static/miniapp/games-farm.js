/* Persistent farm client. Prices, energy, gifts and offline production come from the server. */
(() => {
  'use strict';
  const $ = (s, r = document) => r.querySelector(s),
    A = () => window.ArcadeExtraArt,
    M = () => window.AlgoGameMotion;
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  } [c]));
  const fmt = n => Math.max(0, Math.floor(n || 0)).toLocaleString('ru-RU');
  const compact = n => n >= 1000000 ? (n / 1000000).toLocaleString('ru-RU', {
    maximumFractionDigits: 1
  }) + ' млн' : n >= 100000 ? (n / 1000).toLocaleString('ru-RU', {
    maximumFractionDigits: 1
  }) + ' тыс.' : fmt(n);
  const clock = n => {
    n = Math.max(0, Math.ceil(n));
    return n >= 3600 ? Math.floor(n / 3600) + ':' + String(Math.floor(n % 3600 / 60)).padStart(2, '0') + ':' + String(n % 60).padStart(2, '0') : Math.floor(n / 60) + ':' + String(n % 60).padStart(2, '0');
  };
  const paths = {
    shovel: 'M5 21 16 10m-2-6 3-3 6 6-3 3-5-5m-8 9-4 1v5h5l2-4',
    gloves: 'M6 12V6a2 2 0 0 1 4 0v4V4a2 2 0 0 1 4 0v6-4a2 2 0 0 1 4 0v8l2-2q3-1 2 3l-4 7H8l-5-7q-1-3 3-2Z',
    energy: 'm13 2-8 12h6l-1 8 9-13h-6Z',
    water: 'M12 2C8 8 4 11 4 15a8 8 0 0 0 16 0c0-4-4-7-8-13ZM7 15q0 5 5 5',
    beds: 'M3 11h18M4 17h16M6 22h12M7 8V3m-3 1 3 2 3-2m7 4V3m-3 1 3 2 3-2',
    helper: 'M6 21v-5q0-5 6-5t6 5v5M8 5a4 4 0 1 0 8 0 4 4 0 0 0-8 0M3 16h4m10 0h4',
    bee: 'M7 9q-7-5-2-7 5-1 7 7m5 0q7-5 2-7-5-1-7 7M5 14a7 7 0 1 0 14 0 7 7 0 0 0-14 0m4-6v12m6-12v12m-4-13 1-3',
    greenhouse: 'm3 10 9-8 9 8v12H3Zm9-8v20M3 10h18M3 16h18',
    tree: 'M12 22v-9m0 4-4-3m4 0 5-3M4 10a5 5 0 0 1 4-7 5 5 0 0 1 9 2 5 5 0 1 1 3 8q-3 4-8 1-7 3-8-4Z',
    market: 'M3 9h18l-2-6H5Zm1 1v12h16V10M9 22v-8h6v8M2 9q2 5 5 0 3 5 5 0 3 5 5 0 3 5 5 0',
    barn: 'm2 10 10-8 10 8v12H2Zm6 12V12h8v10m-8-9 8 8m0-8-8 8M9 6h6',
    sun: 'M12 5v-3m0 23v-3M5 12H2m23 0h-3M5 5 3 3m20 20-2-2M5 21l-2 2M23 3l-2 2M7 12a5 5 0 1 0 10 0 5 5 0 0 0-10 0',
    cup: 'M7 3h10v9q0 6-5 6t-5-6ZM7 6H3v3q0 5 5 5m9-8h4v3q0 5-5 5m-4 4v4m-5 0h10',
    gift: 'M3 10h18v12H3Zm-1-5h20v5H2Zm10 0v17m0-17Q2 6 5 1q4-4 7 4Zm0 0q10 1 7-4-4-4-7 4Z',
    leaf: 'M4 20Q1 5 21 3q0 19-14 16m-3 3L18 7',
    arrow: 'm7 4 8 8-8 8',
    check: 'm4 12 5 5L21 5',
    close: 'm6 6 12 12M18 6 6 18'
  };
  const icon = id => `<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="${paths[id]||paths.leaf}"/></svg>`;
  const carrot = () => A().carrot();
  const money = n => `<span class="farm-money">${carrot()}<b>${fmt(n)}</b></span>`;
  let current = null;

  function structure(s) {
    return JSON.stringify([s.items.map(i => i.level), s.level, s.daily.day, s.daily.claimed, s.daily.combo_claimed, s.quests.map(q => [q.ready, q.claimed]), s.badges.map(b => [b.ready, b.claimed])]);
  }

  function pending(f) {
    return f.taps + (f.request?.action === 'tap' ? f.request.count : 0);
  }

  function live(f) {
    const s = f.snapshot;
    if (!s) return null;
    const seconds = Math.max(0, (performance.now() - f.received) / 1000),
      p = pending(f),
      boost = Math.max(0, s.stats.boost_seconds - seconds),
      perTap = s.stats.boost && boost <= 0 ? s.stats.base_tap : s.stats.per_tap;
    return {
      balance: s.balance + Math.floor(Math.min(seconds, s.stats.offline_hours * 3600) * s.stats.per_hour / 3600) + p * perTap,
      energy: Math.min(s.stats.energy_max, Math.max(0, s.energy + Math.floor(seconds * s.stats.energy_per_second) - p)),
      boost,
      perTap
    };
  }

  function status(f, message, error = false) {
    if (current !== f) return;
    const node = $('.farm-status', f.dialog);
    node.textContent = message;
    node.classList.toggle('is-error', error);
    node.hidden = !message;
  }
  async function open(api, options) {
    if (current) return;
    const dialog = document.createElement('dialog');
    dialog.id = 'kopatychFarm';
    dialog.className = 'farm-dialog';
    dialog.innerHTML = `<header class="farm-header"><div class="farm-brand">${carrot()}<div><small>КОПАТЫЧ</small><h2>Моя ферма</h2></div></div><button class="farm-tournament" data-farm-sprint>${icon('cup')}<span>Турнир · 90 с</span></button><button class="farm-close" data-farm-close aria-label="Закрыть ферму">${icon('close')}</button></header><div class="farm-loading">Готовим огород…</div><div class="farm-app" hidden><div class="farm-wallet"><div><span>Морковки</span><strong data-farm-bank>0</strong></div><div class="farm-income"><span>Доход в час</span><strong data-farm-income>0</strong></div><div class="farm-level-chip"><span>Уровень</span><strong data-farm-level>1</strong></div></div><div class="farm-offline" hidden></div><nav class="farm-tabs" aria-label="Разделы фермы">${[['home','leaf','Ферма'],['upgrades','barn','Улучшения'],['tasks','gift','Задания'],['valley','cup','Долина']].map(([tab,i,t])=>`<button data-farm-tab="${tab}">${icon(i)}<span>${t}</span><i></i></button>`).join('')}</nav><p class="farm-status" role="status" hidden></p><div class="farm-content"></div><footer class="farm-save-line"><span class="farm-save-dot"></span><span data-save-label>Прогресс сохраняется</span><span class="farm-offline-rule">Растёт даже с закрытым приложением</span></footer></div>`;
    document.body.append(dialog);
    dialog.showModal();
    const f = {
      api,
      options,
      player: options.player,
      dialog,
      snapshot: null,
      received: 0,
      taps: 0,
      request: null,
      inflight: null,
      busy: false,
      failed: false,
      lastTap: 0,
      tab: 'home',
      category: 'garden',
      abort: new AbortController(),
      timer: 0,
      pollAt: 0,
      signature: '',
      returning: null,
      board: null
    };
    current = f;
    try {
      const saved = JSON.parse(localStorage.getItem('kopatych-ui:' + f.player) || '{}');
      if (['home', 'upgrades', 'tasks', 'valley'].includes(saved.tab)) f.tab = saved.tab;
      if (['garden', 'tools', 'business'].includes(saved.category)) f.category = saved.category;
    } catch {}
    const on = (el, type, fn, extra = {}) => el.addEventListener(type, fn, {
      ...extra,
      signal: f.abort.signal
    });
    on(dialog, 'click', e => void handle(f, e));
    on(dialog, 'cancel', e => {
      e.preventDefault();
      close();
    });
    on(document, 'keydown', e => {
      if (current === f && f.tab === 'home' && e.code === 'Space' && !e.repeat && !['INPUT', 'TEXTAREA'].includes(e.target.tagName) && !e.target.closest('button:not(.farm-bear)')) {
        e.preventDefault();
        tap(f, e);
      }
    });
    on(document, 'visibilitychange', () => {
      if (document.hidden) void flush(f).catch(() => {});
      else void refresh(f, true).catch(error => status(f, error.message, true));
    });
    try {
      await refresh(f, true);
      if (current !== f) return;
      $('.farm-loading', dialog).remove();
      $('.farm-app', dialog).hidden = false;
      render(f);
      f.timer = setInterval(() => tick(f), 250);
    } catch (error) {
      const loading = $('.farm-loading', dialog);
      if (loading) loading.innerHTML = `<p>${esc(error.status ? error.message : 'Не удалось открыть ферму. Проверь соединение и попробуй снова.')}</p><button class="farm-button" data-retry-open>Попробовать снова</button>`;
    }
  }

  function accept(f, s, showOffline = false) {
    if (s.player !== f.player) throw Error('Открой ферму заново под своим аккаунтом.');
    f.snapshot = s;
    f.received = performance.now();
    f.failed = false;
    f.pollAt = performance.now() + 15000;
    if (showOffline && s.offline?.amount > 0 && s.offline.seconds >= 60) f.returning = s.offline;
    if (current !== f) return;
    const changed = structure(s) !== f.signature;
    if (changed && $('.farm-content', f.dialog).children.length) render(f);
    else update(f);
  }
  async function refresh(f, showOffline = false) {
    if (current !== f || f.busy || f.inflight) return;
    await flush(f);
    if (f.failed) return;
    const s = await f.api('/farm');
    if (current !== f) return;
    accept(f, s, showOffline);
    status(f, '');
  }

  function persistUi(f) {
    try {
      localStorage.setItem('kopatych-ui:' + f.player, JSON.stringify({
        tab: f.tab,
        category: f.category
      }));
    } catch {}
  }

  function render(f) {
    if (current !== f || !f.snapshot) return;
    f.signature = structure(f.snapshot);
    const host = $('.farm-content', f.dialog);
    for (const b of f.dialog.querySelectorAll('[data-farm-tab]')) {
      const yes = b.dataset.farmTab === f.tab;
      b.classList.toggle('is-active', yes);
      b.setAttribute('aria-pressed', String(yes));
    }
    host.innerHTML = f.tab === 'home' ? home(f) : f.tab === 'upgrades' ? shop(f) : f.tab === 'tasks' ? tasks(f) : valley(f);
    const bear = $('.farm-bear', host);
    if (bear) {
      bear.addEventListener('pointerdown', e => {
        e.preventDefault();
        tap(f, e);
      }, {
        signal: f.abort.signal
      });
      bear.addEventListener('click', e => {
        if (e.detail === 0) tap(f, e);
      }, {
        signal: f.abort.signal
      });
    }
    if (bear) bear.focus({
      preventScroll: true
    });
    update(f);
    if (f.tab === 'valley') void loadBoard(f);
  }

  function home(f) {
    const s = f.snapshot,
      buildings = s.items.filter(i => ['beds', 'greenhouse', 'orchard', 'beehives'].includes(i.id));
    const quick = s.items.filter(i => !i.locked && !i.maxed).sort((a, b) => Number(b.affordable) - Number(a.affordable) || a.cost - b.cost).slice(0, 3);
    return `<div class="farm-home-grid"><section class="farm-scene"><div class="farm-scene-top"><span>${icon('leaf')}${esc(s.league.name)}</span><span class="farm-storage-tag">${icon('barn')}<b>${s.stats.offline_hours} ч</b> запаса</span></div><div class="farm-sun" aria-hidden="true">${icon('sun')}</div><div class="farm-scene-cloud c1"></div><div class="farm-scene-cloud c2"></div><div class="farm-hills" aria-hidden="true"></div><div class="farm-buildings">${buildings.map(i=>`<div class="farm-building ${i.level?'is-built':''}">${icon(i.icon)}<span>${i.id==='beds'?i.level+1:i.level}</span></div>`).join('')}</div><button class="farm-bear" aria-label="Собрать морковки">${A().bear(s.stats.boost)}</button><div class="farm-carrot-row" aria-hidden="true">${Array.from({length:8},carrot).join('')}</div><div class="farm-tap-value">+<b data-per-tap>${s.stats.per_tap}</b> за нажатие</div><div class="farm-energy"><span>${icon('energy')}<b data-energy>${s.energy}</b><small>/ ${s.stats.energy_max}</small></span><span>+${s.stats.energy_per_second.toLocaleString('ru-RU')} в секунду</span><progress data-energy-bar max="${s.stats.energy_max}" value="${s.energy}"></progress></div><div class="farm-boosts"><button data-farm-action="boost">${icon('sun')}<span><b>Нажатия ×2</b><small data-boost-label>30 секунд · ${s.daily.boosts_left}/2</small></span></button><button data-farm-action="refill">${icon('water')}<span><b>Восстановить силы</b><small data-refill-label>${s.daily.refills_left}/2 на сегодня</small></span></button></div></section><aside class="farm-side"><button class="farm-daily-shortcut" data-farm-tab="tasks">${icon('gift')}<span><b>${s.daily.claimed?'Задания дня':'Подарок за вход'}</b><small>${s.daily.claimed?s.quests.filter(q=>q.claimed).length+'/3 задания выполнено':`День ${s.daily.streak} · +${fmt(s.daily.reward)} морковок`}</small></span>${icon('arrow')}</button><section class="farm-level-card"><div><span>Уровень ${s.level}</span><b data-level-total>${s.level_next?fmt(s.earned)+' / '+fmt(s.level_next):'Вершина долины'}</b></div><progress data-level-progress max="${s.level_next?s.level_next-s.level_start:1}" value="${s.level_next?s.earned-s.level_start:1}"></progress><small data-level-remaining>${s.level_next?'До следующего уровня '+fmt(Math.max(0,s.level_next-s.earned))+' морковок':'Все уровни открыты'}</small></section><div class="farm-section-title"><h3>Быстрый рост</h3><button data-farm-tab="upgrades">Все улучшения ${icon('arrow')}</button></div><div class="farm-quick-upgrades">${quick.map(i=>upgrade(f,i,true)).join('')}</div><div class="farm-next-unlock">${icon('leaf')}<span><b>${nextUnlock(s)}</b><small>Собрано за всё время: <span data-total-earned>${fmt(s.earned)}</span></small></span></div></aside></div>`;
  }

  function nextUnlock(s) {
    const next = s.items.find(i => i.locked);
    return next ? `${next.name} · с ${next.unlock} уровня` : 'Все постройки открыты';
  }

  function upgrade(f, i, small = false) {
    const effect = i.per_hour_gain ? `+${fmt(i.per_hour_gain)} в час` : i.id === 'shovel' || i.id === 'gloves' ? `+${fmt(i.per_tap_gain)} за нажатие` : i.id === 'silo' ? '+2 часа без захода' : i.id === 'battery' ? '+200 энергии' : '+0,2 энергии в секунду';
    return `<button class="farm-upgrade ${small?'is-compact':''} ${i.locked?'is-locked':''}" data-farm-action="buy" data-item="${i.id}" ${i.locked||i.maxed?'disabled':''}><span class="farm-upgrade-icon">${icon(i.icon)}</span><span class="farm-upgrade-info"><b>${esc(i.name)}<em>${i.level?`Ур. ${i.level}`:'Новый'}</em></b><small>${esc(i.locked?'Откроется на '+i.unlock+' уровне':effect)}</small>${!small?`<span>${esc(i.text)}</span>`:''}</span><strong class="farm-upgrade-price">${i.maxed?'Максимум':money(i.cost)}</strong></button>`;
  }

  function shop(f) {
    return `<div class="farm-shop-head"><div><h3>Улучшения фермы</h3></div><div class="farm-shop-filters">${[['garden','Огород'],['tools','Инструменты'],['business','Хозяйство']].map(([key,name])=>`<button data-farm-category="${key}" aria-pressed="${key===f.category}">${name}</button>`).join('')}</div></div><div class="farm-shop-grid">${f.snapshot.items.filter(i=>i.category===f.category).map(i=>upgrade(f,i)).join('')}</div>`;
  }

  function tasks(f) {
    const s = f.snapshot,
      d = s.daily,
      cycle = (d.streak - 1) % 7;
    const dailyCards = d.rewards.map((reward, i) => `<div class="farm-day ${i===cycle?'is-today':''} ${i<cycle||i===cycle&&d.claimed?'is-done':''}"><small>День ${i+1}</small>${i<cycle||i===cycle&&d.claimed?icon('check'):carrot()}<b>${fmt(reward)}</b></div>`).join('');
    const combo = d.combo.map(id => {
      const i = s.items.find(i => i.id === id),
        done = d.bought.includes(id);
      return `<div class="farm-combo-item ${done?'is-done':''}">${icon(i.icon)}<b>${esc(i.name)}</b><small>${done?'Готово':'Улучши сегодня'}</small></div>`;
    }).join('');
    return `<div class="farm-tasks-grid"><section class="farm-panel farm-daily-panel"><div class="farm-panel-title"><h3>Заходи за подарком</h3><span>${d.streak} ${d.streak%10===1&&d.streak%100!==11?'день':[2,3,4].includes(d.streak%10)&&![12,13,14].includes(d.streak%100)?'дня':'дней'} подряд</span></div><div class="farm-days">${dailyCards}</div><button class="farm-button" data-farm-action="claim_daily" ${d.claimed?'disabled':''}>${d.claimed?'Сегодня получено':`Забрать ${fmt(d.reward)} морковок`}</button></section><section class="farm-panel"><div class="farm-panel-title"><h3>Задания дня</h3><span data-farm-reset></span></div><div class="farm-quests">${s.quests.map(q=>`<div class="farm-quest" data-quest="${q.id}"><div><b>${esc(q.name)}</b><small>${fmt(Math.min(q.value,q.goal))} / ${fmt(q.goal)} ${esc(q.unit)}</small><progress max="${q.goal}" value="${q.value}"></progress></div><button class="farm-small-button" data-farm-action="claim_quest" data-item="${q.id}" ${q.ready&&!q.claimed?'':'disabled'}>${q.claimed?'✓':money(q.reward)}</button></div>`).join('')}</div></section><section class="farm-panel farm-combo-panel"><div class="farm-panel-title"><h3>Комбо дня</h3><span>+${fmt(d.combo_reward)} морковок</span></div><div class="farm-combo">${combo||'<p>Все постройки уже прокачаны.</p>'}</div><button class="farm-button" data-farm-action="claim_quest" data-item="combo" ${d.combo_ready&&!d.combo_claimed?'':'disabled'}>${d.combo_claimed?'Комбо собрано':'Забрать награду'}</button></section><section class="farm-panel"><div class="farm-panel-title"><h3>Достижения фермы</h3><span>${s.badges.filter(b=>b.claimed).length}/${s.badges.length}</span></div><div class="farm-badges">${s.badges.map(b=>`<div data-badge="${b.id}" class="farm-badge ${b.ready?'is-ready':''}">${icon(b.ready?'cup':'leaf')}<div><b>${esc(b.name)}</b><small>${fmt(Math.min(b.value,b.target))} / ${fmt(b.target)}</small></div><button class="farm-small-button" data-farm-action="claim_badge" data-item="${b.id}" ${b.ready&&!b.claimed?'':'disabled'}>${b.claimed?'✓':money(b.reward)}</button></div>`).join('')}</div></section></div>`;
  }

  function valley(f) {
    const s = f.snapshot,
      leagues = ['Росток', 'Огородник', 'Фермер', 'Агроном', 'Мастер урожая', 'Хозяин долины'];
    return `<div class="farm-valley-grid"><section class="farm-panel"><div class="farm-panel-title"><h3>Твоя долина</h3><span>${icon('leaf')}${esc(s.league.name)}</span></div><div class="farm-leagues">${leagues.map((name,i)=>`<div class="farm-league ${i===s.league.index?'is-current':''} ${i<s.league.index?'is-passed':''}">${icon(i<=s.league.index?'cup':'leaf')}<span>${name}</span><small>${i===s.league.index?'Ты здесь':i<s.league.index?'Пройдено':''}</small></div>`).join('')}</div><div class="farm-total-stats"><div><small>Урожай за всё время</small><b>${fmt(s.earned)}</b></div><div><small>Собрано вручную</small><b>${fmt(s.manual)}</b></div><div><small>Выросло само</small><b>${fmt(s.passive)}</b></div><div><small>Нажатий</small><b>${fmt(s.taps)}</b></div></div></section><section class="farm-panel"><div class="farm-panel-title"><h3>Фермеры</h3><span>Общий урожай</span></div><div class="farm-leaderboard" aria-live="polite">Загружаем долину…</div><button class="farm-tour-card" data-farm-sprint>${icon('cup')}<span><b>Аркадный турнир</b><small>90 секунд · рейтинг и награды AC</small></span>${icon('arrow')}</button></section></div>`;
  }
  async function loadBoard(f) {
    try {
      const data = await f.api('/farm/board');
      if (current !== f || f.tab !== 'valley') return;
      const host = $('.farm-leaderboard', f.dialog);
      host.innerHTML = data.rows.length ? data.rows.map(r => `<div class="farm-rank-row ${r.player===f.player?'is-me':''}"><b>${r.rank}</b><span><strong>${esc(r.name)}${r.player===f.player?' · Ты':''}</strong><small>${esc(r.league)} · ${fmt(r.per_hour)} в час</small></span><em>${fmt(r.earned)}</em></div>`).join('') : 'Начни собирать урожай — твоё имя появится здесь.';
    } catch (error) {
      const host = $('.farm-leaderboard', f.dialog);
      if (host) host.textContent = error.message;
    }
  }

  function update(f) {
    if (current !== f || !f.snapshot) return;
    const s = f.snapshot,
      v = live(f),
      d = f.dialog,
      age = (performance.now() - f.received) / 1000;
    $('[data-farm-bank]', d).textContent = compact(v.balance);
    $('[data-farm-bank]', d).title = fmt(v.balance) + ' морковок';
    $('[data-farm-income]', d).textContent = '+' + compact(s.stats.per_hour);
    $('[data-farm-level]', d).textContent = s.level;
    $('[data-energy]', d) && ($('[data-energy]', d).textContent = fmt(v.energy));
    $('[data-energy-bar]', d) && ($('[data-energy-bar]', d).value = v.energy);
    const perTap = s.stats.boost && v.boost <= 0 ? s.stats.base_tap : s.stats.per_tap;
    if ($('[data-per-tap]', d)) $('[data-per-tap]', d).textContent = perTap;
    $('.farm-scene', d)?.classList.toggle('is-boosted', v.boost > 0);
    for (const b of d.querySelectorAll('[data-farm-action="buy"]')) {
      const i = s.items.find(i => i.id === b.dataset.item);
      b.disabled = f.busy || f.failed || i.locked || i.maxed || v.balance < i.cost;
    }
    const boost = $('[data-farm-action="boost"]', d),
      refill = $('[data-farm-action="refill"]', d);
    if (boost) {
      boost.disabled = f.busy || f.failed || v.boost > 0 || !s.daily.boosts_left;
      $('[data-boost-label]', d).textContent = v.boost > 0 ? 'Ещё ' + clock(v.boost) : `30 секунд · ${s.daily.boosts_left}/2`;
    }
    if (refill) {
      const wait = Math.max(0, s.daily.refill_seconds - age);
      refill.disabled = f.busy || f.failed || wait > 0 || !s.daily.refills_left || v.energy >= s.stats.energy_max;
      $('[data-refill-label]', d).textContent = wait > 0 ? 'Через ' + clock(wait) : `${s.daily.refills_left}/2 на сегодня`;
    }
    const earned = s.earned + Math.floor(Math.min(age, s.stats.offline_hours * 3600) * s.stats.per_hour / 3600) + pending(f) * v.perTap;
    if ($('[data-total-earned]', d)) $('[data-total-earned]', d).textContent = fmt(earned);
    if ($('[data-level-total]', d)) $('[data-level-total]', d).textContent = s.level_next ? fmt(earned) + ' / ' + fmt(s.level_next) : 'Вершина долины';
    if ($('[data-level-progress]', d)) $('[data-level-progress]', d).value = s.level_next ? Math.max(0, earned - s.level_start) : 1;
    if ($('[data-level-remaining]', d)) $('[data-level-remaining]', d).textContent = s.level_next ? 'До следующего уровня ' + fmt(Math.max(0, s.level_next - earned)) + ' морковок' : 'Все уровни открыты';
    for (const q of s.quests) {
      const node = d.querySelector('[data-quest="' + q.id + '"]');
      if (node) {
        $('small', node).textContent = fmt(Math.min(q.value, q.goal)) + ' / ' + fmt(q.goal) + ' ' + q.unit;
        $('progress', node).value = q.value;
      }
    }
    for (const b of s.badges) {
      const node = d.querySelector('[data-badge="' + b.id + '"]');
      if (node) $('small', node).textContent = fmt(Math.min(b.value, b.target)) + ' / ' + fmt(b.target);
    }
    const reset = $('[data-farm-reset]', d);
    if (reset) reset.textContent = 'Обновление через ' + clock((s.daily.reset_at - s.server_ms) / 1000 - age);
    for (const b of d.querySelectorAll('[data-farm-tab="tasks"] i')) {
      const count = s.quests.filter(q => q.ready && !q.claimed).length + s.badges.filter(b => b.ready && !b.claimed).length + Number(!s.daily.claimed) + Number(s.daily.combo_ready && !s.daily.combo_claimed);
      b.textContent = count || '';
    }
    const offline = $('.farm-offline', d);
    if (f.returning) {
      offline.hidden = false;
      const key = JSON.stringify(f.returning);
      if (offline.dataset.key !== key) {
        offline.dataset.key = key;
        offline.innerHTML = `<span class="farm-offline-icon">${icon('barn')}</span><div><b>Пока тебя не было: +${fmt(f.returning.amount)} морковок</b><small>${f.returning.capped?`Амбар вместил ${f.returning.limit_hours} ч урожая`:'Урожай уже в корзинке'}</small></div><button data-dismiss-offline aria-label="Скрыть уведомление">${icon('close')}</button>`;
      }
    } else {
      offline.hidden = true;
      delete offline.dataset.key;
    }
    $('.farm-save-dot', d).classList.toggle('is-busy', !!f.inflight || f.taps > 0);
    $('.farm-save-dot', d).classList.toggle('is-error', f.failed);
    $('[data-save-label]', d).textContent = f.failed ? 'Ожидаем соединения' : f.inflight || f.taps ? 'Сохраняем…' : 'Сохранено';
  }

  function tap(f, e) {
    if (current !== f || !f.snapshot || f.failed || f.busy || document.hidden) return;
    const now = performance.now();
    if (now - f.lastTap < 120) return;
    f.lastTap = now;
    const v = live(f);
    if (v.energy < 1) {
      status(f, 'Копатыч отдыхает. Энергия восстанавливается сама.');
      return;
    }
    if (pending(f) >= 30) return;
    f.taps++;
    const button = $('.farm-bear', f.dialog);
    if (button) {
      M().pop(button);
      const n = document.createElement('span');
      n.className = 'farm-floating';
      n.textContent = '+' + (f.snapshot.stats.boost && v.boost <= 0 ? f.snapshot.stats.base_tap : f.snapshot.stats.per_tap);
      n.style.left = (43 + Math.random() * 14) + '%';
      $('.farm-scene', f.dialog).append(n);
      setTimeout(() => n.remove(), 750);
    }
    if (f.options.settings?.vibration && navigator.vibrate) navigator.vibrate(10);
    update(f);
  }
  async function flush(f) {
    if (f.inflight) return f.inflight;
    if (!f.request) {
      if (!f.taps) return;
      const count = Math.min(20, f.taps);
      f.taps -= count;
      f.request = {
        id: crypto.randomUUID(),
        action: 'tap',
        count
      };
    }
    const request = f.request;
    f.inflight = f.api('/farm/actions', {
      method: 'POST',
      body: request
    }).then(value => {
      if (f.request === request) f.request = null;
      if (current !== f) return;
      accept(f, value.farm);
      status(f, '');
    }).catch(async error => {
      f.failed = true;
      if (error.status === 400 || error.status === 422) {
        f.request = null;
        try {
          const s = await f.api('/farm');
          if (current === f) accept(f, s);
          f.failed = false;
        } catch {}
        status(f, error.message, true);
      } else status(f, 'Связь прервалась. Нажми «Повторить», чтобы сохранить действие.', true);
      if (current === f && f.failed) {
        const node = $('.farm-status', f.dialog);
        if (!$('.farm-retry', f.dialog)) {
          const b = document.createElement('button');
          b.className = 'farm-retry';
          b.dataset.farmRetry = '';
          b.textContent = 'Повторить';
          node.append(b);
        }
      }
      throw error;
    }).finally(() => {
      f.inflight = null;
      if (current === f) update(f);
    });
    update(f);
    return f.inflight;
  }
  async function action(f, kind, item) {
    if (!f.snapshot || f.busy || f.failed) return;
    f.busy = true;
    update(f);
    try {
      await flush(f);
      if (f.taps) await flush(f);
      f.request = {
        id: crypto.randomUUID(),
        action: kind,
        ...(item ? {
          item
        } : {})
      };
      await flush(f);
      if (current === f) {
        render(f);
        if (kind === 'buy') status(f, 'Улучшение куплено');
        else if (kind === 'claim_daily' || kind === 'claim_quest' || kind === 'claim_badge') status(f, 'Морковки уже в корзинке');
      }
    } catch {} finally {
      f.busy = false;
      if (current === f) update(f);
    }
  }
  async function handle(f, e) {
    const b = e.target.closest('button');
    if (!b || b.disabled) return;
    if (b.hasAttribute('data-farm-close')) {
      close();
      return;
    }
    if (b.hasAttribute('data-farm-sprint')) {
      close();
      f.options.onSprint?.();
      return;
    }
    if (b.dataset.farmTab) {
      f.tab = b.dataset.farmTab;
      persistUi(f);
      render(f);
      return;
    }
    if (b.dataset.farmCategory) {
      f.category = b.dataset.farmCategory;
      persistUi(f);
      render(f);
      return;
    }
    if (b.dataset.farmAction) {
      await action(f, b.dataset.farmAction, b.dataset.item);
      return;
    }
    if (b.hasAttribute('data-dismiss-offline')) {
      f.returning = null;
      update(f);
      return;
    }
    if (b.hasAttribute('data-farm-retry')) {
      f.failed = false;
      status(f, 'Проверяем соединение…');
      try {
        await flush(f);
        await refresh(f, true);
      } catch {}
      return;
    }
    if (b.hasAttribute('data-retry-open')) {
      const {
        api,
        options
      } = f;
      close();
      void open(api, options);
    }
  }

  function tick(f) {
    if (current !== f || document.hidden || !f.snapshot) return;
    update(f);
    if (!f.busy && !f.failed && !f.inflight && (f.taps || f.request)) void flush(f).catch(() => {});
    else if (!f.busy && !f.failed && !f.inflight && performance.now() > f.pollAt) {
      f.pollAt = performance.now() + 15000;
      void refresh(f).catch(error => status(f, error.message, true));
    }
  }

  function close() {
    const f = current;
    if (!f) return;
    clearInterval(f.timer);
    persistUi(f);
    f.abort.abort();
    if (f.request) void f.api('/farm/actions', {
      method: 'POST',
      body: f.request,
      keepalive: true
    }).catch(() => {});
    if (f.taps) void f.api('/farm/actions', {
      method: 'POST',
      body: {
        id: crypto.randomUUID(),
        action: 'tap',
        count: Math.min(20, f.taps)
      },
      keepalive: true
    }).catch(() => {});
    f.dialog.remove();
    current = null;
    f.options.onClose?.();
  }
  window.addEventListener('pagehide', close);
  window.KopatychFarm = {
    open,
    close,
    get isOpen() {
      return !!current;
    }
  };
})();
