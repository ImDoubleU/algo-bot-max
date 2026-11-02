/* Persistent farm client. Prices, energy, gifts and offline production come from the server. */
(() => {
  'use strict';
  const $ = (s, r = document) => r.querySelector(s),
    A = () => window.ArcadeExtraArt,
    F = () => window.KopatychArt,
    M = () => window.AlgoGameMotion;
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  } [c]));
  const fmt = n => Math.max(0, Math.floor(n || 0)).toLocaleString('ru-RU');
  const decimal = n => Number(n || 0).toLocaleString('ru-RU', {
    maximumFractionDigits: 2
  });
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
    return JSON.stringify([s.items.map(i => i.level), s.level, s.daily.day, s.daily.claimed, s.daily.combo_claimed, s.quests.map(q => [q.ready, q.claimed]), s.badges.map(b => [b.ready, b.claimed]), s.chapters.map(c => [c.ready, c.claimed]), s.order, s.claimable]);
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
    dialog.innerHTML = `<header class="farm-header"><div class="farm-brand">${carrot()}<div><small>КОПАТЫЧ</small><h2>Моя ферма</h2></div></div><button class="farm-tournament" data-farm-sprint>${icon('cup')}<span>Турнир · 90 с</span></button><button class="farm-close" data-farm-close aria-label="Закрыть ферму">${icon('close')}</button></header><div class="farm-loading">Готовим огород…</div><div class="farm-app" hidden><div class="farm-wallet"><div class="farm-balance"><span>Морковки в корзинке</span><div class="farm-balance-number">${carrot()}<strong data-farm-bank>0</strong></div></div><div class="farm-income"><span>Растёт само</span><div><strong data-farm-income>0</strong><small>в час</small></div></div><div class="farm-level-chip"><span>Уровень</span><strong data-farm-level>1</strong></div></div><div class="farm-offline" hidden></div><nav class="farm-tabs" aria-label="Разделы фермы">${[['home','leaf','Ферма'],['upgrades','barn','Улучшения'],['tasks','gift','Задания'],['valley','cup','Долина']].map(([tab,i,t])=>`<button data-farm-tab="${tab}">${icon(i)}<span>${t}</span><i></i></button>`).join('')}</nav><div class="farm-collect-bar"><span data-collect-count></span><button class="farm-button" data-farm-action="claim_all">Забрать всё <span data-collect-amount></span></button></div><p class="farm-status" role="status" hidden></p><div class="farm-content"></div></div>`;
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
      taskView: 'daily',
      abort: new AbortController(),
      timer: 0,
      pollAt: 0,
      signature: '',
      returning: null,
      board: null,
      orderReadyChecked: null
    };
    current = f;
    try {
      const saved = JSON.parse(localStorage.getItem('kopatych-ui:' + f.player) || '{}');
      if (['home', 'upgrades', 'tasks', 'valley'].includes(saved.tab)) f.tab = saved.tab;
      if (['garden', 'tools', 'business'].includes(saved.category)) f.category = saved.category;
      if (['daily', 'story', 'orders', 'badges'].includes(saved.taskView)) f.taskView = saved.taskView;
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
        category: f.category,
        taskView: f.taskView
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
    const s = f.snapshot;
    const quick = s.items.filter(i => !i.locked && !i.maxed)
      .sort((a, b) => Number(b.affordable) - Number(a.affordable) || a.cost - b.cost).slice(0, 3);
    return `<div class="farm-home-grid">
      <section class="farm-scene" data-farm-stage="${F().stage(s.level).index}">
        <div class="farm-playground">
          <div class="farm-landscape">${F().scene(s.level,Object.fromEntries(s.items.map(i=>[i.id,i.level])))}</div>
          <div class="farm-scene-top">
            <span class="farm-league-label">${icon('leaf')}${esc(F().stage(s.level).name)}</span>
            <span class="farm-storage-tag">${icon('barn')}Амбар · <b>${s.stats.offline_hours} ч</b></span>
          </div>
          <button class="farm-bear" aria-label="Собрать морковки">${F().character(s.stats.boost,s.level)}</button>
          <div class="farm-tap-value">${carrot()}<span>+<b data-per-tap>${s.stats.per_tap}</b> за нажатие</span></div>
        </div>
        <div class="farm-scene-controls">
          <div class="farm-energy"><span>${icon('energy')}<b data-energy>${s.energy}</b><small>/ ${s.stats.energy_max}</small></span><span>+${s.stats.energy_per_second.toLocaleString('ru-RU')} в секунду</span><progress data-energy-bar max="${s.stats.energy_max}" value="${s.energy}"></progress></div>
          <div class="farm-boosts">
            <button data-farm-action="boost">${icon('sun')}<span><b>Нажатия ×2</b><small data-boost-label>30 секунд · ${s.daily.boosts_left}/2</small></span></button>
            <button data-farm-action="refill">${icon('water')}<span><b>Полить огород</b><small data-refill-label>${s.daily.refills_left}/2 на сегодня</small></span></button>
          </div>
        </div>
      </section>
      <aside class="farm-side">
        <button class="farm-daily-shortcut" data-farm-tab="tasks"><span class="farm-gift-art">${F().item('gift')}</span><span><b>${s.daily.claimed?'Задания дня':'Подарок дня'}</b><small>${s.daily.claimed?s.quests.filter(q=>q.claimed).length+' из '+s.quests.length+' выполнено':`+${fmt(s.daily.reward)} морковок уже ждут`}</small></span>${icon('arrow')}</button>
        <section class="farm-level-card"><div><span>Уровень ${s.level}</span><b data-level-total>${s.level_next?fmt(s.earned)+' / '+fmt(s.level_next):'Вершина долины'}</b></div><progress data-level-progress max="${s.level_next?s.level_next-s.level_start:1}" value="${s.level_next?s.earned-s.level_start:1}"></progress><small data-level-remaining>${s.level_next?'До следующего уровня '+fmt(Math.max(0,s.level_next-s.earned))+' морковок':'Все уровни открыты'}</small><span class="farm-appearance-next">${F().stage(s.level).next?'Новый облик · уровень '+F().stage(s.level).next:'Легендарный облик открыт'}</span></section>
        <div class="farm-section-title"><h3>Для огорода</h3><button data-farm-tab="upgrades">Все ${icon('arrow')}</button></div>
        <div class="farm-quick-upgrades">${quick.map(i=>upgrade(f,i,true)).join('')}</div>
        <div class="farm-next-unlock">${icon('leaf')}<span><b>${nextUnlock(s)}</b><small>Всего выращено: <span data-total-earned>${fmt(s.earned)}</span></small></span></div>
      </aside>
    </div><div class="farm-home-extras">${chapterPreview(s)}${orderPreview(s)}</div>`;
  }

  function nextUnlock(s) {
    const next = s.items.find(i => i.locked);
    return next ? `${next.name} · с ${next.unlock} уровня` : 'Все постройки открыты';
  }

  function upgrade(f, i, small = false) {
    const e = i.effect;
    const delta = `+${decimal(e.gain)} ${e.unit}`;
    const subtitle = i.locked ? 'С ' + i.unlock + ' уровня' : i.maxed ? 'Максимальный уровень' : delta;
    return `<button class="farm-upgrade ${small?'is-compact':''} ${i.locked?'is-locked':''}" data-farm-action="buy" data-item="${i.id}" ${i.locked||i.maxed?'disabled':''}>
      <span class="farm-upgrade-icon">${F().item(i.id)}</span>
      <span class="farm-upgrade-info"><b>${esc(i.name)}<em>${i.level} / ${i.maximum}</em></b><small>${esc(subtitle)}</small>
      ${!small?`<span class="farm-effect"><span>${esc(e.label)}</span><span><b>${decimal(e.current)}</b><i>→</i><strong>${decimal(e.next)}</strong> ${esc(e.unit)}</span></span><span class="farm-upgrade-note">${esc(i.text)}${i.payback_hours&&!i.maxed?` · Окупится за ${decimal(i.payback_hours)} ч`:''}</span>`:''}</span>
      <strong class="farm-upgrade-price">${i.maxed?'Максимум':money(i.cost)}${!small&&!i.maxed&&!i.locked?`<small data-missing="${i.id}"></small>`:''}</strong></button>`;
  }

  function production(s) {
    const p = s.production;
    return `<details class="farm-production"><summary><span>${icon('leaf')}Из чего складывается доход</span><b>${fmt(p.total)} / ч</b></summary><div class="farm-production-rows"><div><span>Огород Копатыча</span><b>${fmt(p.base)} / ч</b></div>${p.sources.map(r=>`<div><span>${esc(r.name)}</span><b>${fmt(r.amount)} / ч</b></div>`).join('')}<div class="farm-production-bonus"><span>Полив, лавка и компост · +${p.percent}%</span><b>+${fmt(p.bonus)} / ч</b></div><div><strong>Итого</strong><strong>${fmt(p.total)} / ч</strong></div></div></details>`;
  }

  function shop(f) {
    return `${production(f.snapshot)}<div class="farm-shop-head"><div><h3>Улучшения фермы</h3></div><div class="farm-shop-filters">${[['garden','Огород'],['tools','Инструменты'],['business','Хозяйство']].map(([key,name])=>`<button data-farm-category="${key}" aria-pressed="${key===f.category}">${name}</button>`).join('')}</div></div><div class="farm-shop-grid">${f.snapshot.items.filter(i=>i.category===f.category).map(i=>upgrade(f,i)).join('')}</div>`;
  }

  function chapterPreview(s) {
    const c = s.chapters.find(c => !c.claimed);
    return `<button class="farm-adventure-preview" data-task-view="story">${icon('leaf')}<span><small>История фермы · ${s.chapters.filter(c=>c.claimed).length} / ${s.chapters.length}</small><b>${c?esc(c.name):'Долина расцвела'}</b><span>${c?esc(c.text):'Все главы пройдены'}</span></span>${icon('arrow')}</button>`;
  }

  function orderPreview(s) {
    return `<button class="farm-adventure-preview" data-task-view="orders">${F().item('cart')}<span><small>Заказы соседей</small><b>${s.order?esc(s.order.name):'Доставка по долине'}</b><span>${s.order?'<em data-order-clock></em>':`${s.deliveries} выполнено · выбрать заказ`}</span></span>${icon('arrow')}</button>`;
  }

  function story(f) {
    return `<div class="farm-story-intro"><small>12 ГЛАВ · ОДНА БОЛЬШАЯ ФЕРМА</small><h3>Долина начинается с грядки</h3></div><div class="farm-chapters">${f.snapshot.chapters.map((c,n)=>`<section data-chapter="${c.id}" class="farm-chapter ${c.claimed?'is-done':c.locked?'is-locked':'is-current'}"><span class="farm-chapter-number">${c.claimed?icon('check'):String(n+1).padStart(2,'0')}</span><div><h4>${esc(c.name)}</h4><p>${esc(c.text)}</p><progress max="${c.goal}" value="${Math.min(c.value,c.goal)}"></progress><small>${fmt(Math.min(c.value,c.goal))} / ${fmt(c.goal)}</small></div><button class="farm-small-button" data-farm-action="claim_chapter" data-item="${c.id}" ${c.ready?'':'disabled'}>${c.claimed?'✓':money(c.reward)}</button></section>`).join('')}</div>`;
  }

  function orders(f) {
    const s = f.snapshot,
      o = s.order,
      n = s.neighbors;
    return `<div class="farm-orders-heading"><span>${F().item('cart')}</span><div><h3>Соседи ждут урожай</h3><p>Чем сильнее ферма, тем щедрее заказы.</p></div><b>${s.deliveries} выполнено</b></div>
      <div class="farm-neighbor-trust"><span>${icon('leaf')}</span><div><b>${esc(n.name)}</b><small>${n.next?`${n.deliveries} / ${n.next} доставок до следующего ранга`:'Высший ранг доверия'}</small><progress max="${n.next?n.next-n.start:1}" value="${n.next?n.deliveries-n.start:1}"></progress></div><strong>+${n.bonus||5}%<small>${n.bonus?'к прибыли':'за 5 доставок'}</small></strong></div>
      ${o?`<section class="farm-active-order"><span>${F().item('cart')}</span><div><small data-order-label>В ПУТИ</small><h3>${esc(o.name)}</h3><progress data-order-progress max="${o.seconds}" value="0"></progress><p data-order-clock></p></div><button class="farm-button" data-farm-action="claim_order" data-item="${o.id}">Забрать ${fmt(o.reward)}</button></section>`:''}
      <div class="farm-order-options">${s.orders.map(o=>`<section class="farm-order-option farm-contract ${o.portrait} ${s.level<o.unlock?'is-locked':''}"><div class="farm-contract-person"><span>${F().neighbor(o.portrait)}</span><div><small>${esc(o.person)}</small><h4>${esc(o.name)}</h4></div></div><p class="farm-order-request">«${esc(o.request)}»</p><span class="farm-contract-time">${icon('sun')}${o.seconds/60} минут${s.level<o.unlock?' · с уровня '+o.unlock:''}</span><div class="farm-contract-profit"><small>Чистая прибыль</small>${money(o.profit)}<span>Как ${fmt(o.income_minutes)} минут работы фермы${o.bonus?` · бонус +${o.bonus}%`:''}</span></div><div class="farm-order-economy"><div><small>Отправишь</small>${money(o.cost)}</div>${icon('arrow')}<div><small>Получишь</small>${money(o.reward)}</div></div><button class="farm-button" data-farm-action="start_order" data-item="${o.id}" ${s.level<o.unlock||s.order||s.balance<o.cost?'disabled':''}>${s.level<o.unlock?'С уровня '+o.unlock:s.order?'Доставка занята':'Отправить заказ'}</button></section>`).join('')}</div>`;
  }

  function dailyTasks(f) {
    const s = f.snapshot,
      d = s.daily,
      cycle = (d.streak - 1) % 7;
    const dailyCards = d.rewards.map((reward, i) => `<div class="farm-day ${i===cycle?'is-today':''} ${i<cycle||i===cycle&&d.claimed?'is-done':''}"><small>День ${i+1}</small>${i<cycle||i===cycle&&d.claimed?icon('check'):carrot()}<b>${fmt(reward)}</b></div>`).join('');
    const combo = d.combo.map(id => {
      const i = s.items.find(i => i.id === id),
        done = d.bought.includes(id);
      return `<div class="farm-combo-item ${done?'is-done':''}">${F().item(i.id)}<b>${esc(i.name)}</b><small>${done?'Готово':'Улучши сегодня'}</small></div>`;
    }).join('');
    return `<div class="farm-tasks-grid"><section class="farm-panel farm-daily-panel"><div class="farm-panel-title"><h3>Подарок дня</h3><span>${d.streak} ${d.streak%10===1&&d.streak%100!==11?'день':[2,3,4].includes(d.streak%10)&&![12,13,14].includes(d.streak%100)?'дня':'дней'} подряд</span></div><div class="farm-days">${dailyCards}</div><button class="farm-button" data-farm-action="claim_daily" ${d.claimed?'disabled':''}>${d.claimed?'Сегодня получено':`Забрать ${fmt(d.reward)} морковок`}</button></section><section class="farm-panel"><div class="farm-panel-title"><h3>Задания дня</h3><span data-farm-reset></span></div><div class="farm-quests">${s.quests.map(q=>`<div class="farm-quest" data-quest="${q.id}"><div><b>${esc(q.name)}</b><small>${fmt(Math.min(q.value,q.goal))} / ${fmt(q.goal)} ${esc(q.unit)}</small><progress max="${q.goal}" value="${q.value}"></progress></div><button class="farm-small-button" data-farm-action="claim_quest" data-item="${q.id}" ${q.ready&&!q.claimed?'':'disabled'}>${q.claimed?'✓':money(q.reward)}</button></div>`).join('')}</div></section><section class="farm-panel farm-combo-panel"><div class="farm-panel-title"><h3>Комбо дня</h3><span>+${fmt(d.combo_reward)} морковок</span></div><div class="farm-combo">${combo||'<p>Все постройки уже прокачаны.</p>'}</div><button class="farm-button" data-farm-action="claim_quest" data-item="combo" ${d.combo_ready&&!d.combo_claimed?'':'disabled'}>${d.combo_claimed?'Комбо собрано':'Забрать награду'}</button></section></div>`;
  }

  function tasks(f) {
    const s = f.snapshot;
    const nav = `<div class="farm-task-filters">${[['daily','На сегодня'],['story','История'],['orders','Заказы'],['badges','Достижения']].map(([key,name])=>`<button data-task-view="${key}" aria-pressed="${f.taskView===key}">${name}</button>`).join('')}</div>`;
    const badges = `<section class="farm-panel"><div class="farm-panel-title"><h3>Достижения фермы</h3><span>${s.badges.filter(b=>b.claimed).length}/${s.badges.length}</span></div><div class="farm-badges">${s.badges.map(b=>`<div data-badge="${b.id}" class="farm-badge ${b.ready&&!b.claimed?'is-ready':''} ${b.claimed?'is-claimed':''}">${icon(b.claimed?'check':b.ready?'cup':'leaf')}<div><b>${esc(b.name)}</b><small>${esc(b.description)} · ${fmt(Math.min(b.value,b.target))} / ${fmt(b.target)}</small></div><button class="farm-small-button" data-farm-action="claim_badge" data-item="${b.id}" ${b.ready&&!b.claimed?'':'disabled'}>${b.claimed?'✓':money(b.reward)}</button></div>`).join('')}</div></section>`;
    return nav + (f.taskView === 'daily' ? dailyTasks(f) : f.taskView === 'story' ? story(f) : f.taskView === 'orders' ? orders(f) : badges);
  }

  function valley(f) {
    const s = f.snapshot,
      leagues = ['Росток', 'Огородник', 'Фермер', 'Агроном', 'Мастер урожая', 'Хозяин долины'];
    return `<div class="farm-valley-grid"><section class="farm-panel"><div class="farm-panel-title"><h3>Твоя долина</h3><span>${icon('leaf')}${esc(s.league.name)}</span></div><div class="farm-leagues">${leagues.map((name,i)=>`<div class="farm-league ${i===s.league.index?'is-current':''} ${i<s.league.index?'is-passed':''}">${icon(i<=s.league.index?'cup':'leaf')}<span>${name}</span><small>${i===s.league.index?'Твоя лига':i<s.league.index?'Пройдено':''}</small></div>`).join('')}</div><div class="farm-total-stats"><div><small>Урожай за всё время</small><b>${fmt(s.earned)}</b></div><div><small>Собрано вручную</small><b>${fmt(s.manual)}</b></div><div><small>Выросло само</small><b>${fmt(s.passive)}</b></div><div><small>Нажатий</small><b>${fmt(s.taps)}</b></div></div></section><section class="farm-panel"><div class="farm-panel-title"><h3>Фермеры</h3><span>Общий урожай</span></div><div class="farm-leaderboard" aria-live="polite">Загружаем долину…</div><button class="farm-tour-card" data-farm-sprint>${icon('cup')}<span><b>Аркадный турнир</b><small>90 секунд · рейтинг и награды AC</small></span>${icon('arrow')}</button></section></div><section class="farm-roadmap"><h3>Путь фермера · ${s.roadmap.length} уровней</h3><div>${s.roadmap.map(r=>`<div class="${r.level===s.level?'is-current':r.level<s.level?'is-done':''}"><b>${r.level}</b><span>${r.unlocks.length?esc(r.unlocks.join(' · ')):fmt(r.earned)+' урожая'}</span></div>`).join('')}</div></section>`;
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
      b.classList.toggle('is-affordable', !b.disabled);
    }
    for (const node of d.querySelectorAll('[data-missing]')) {
      const i = s.items.find(i => i.id === node.dataset.missing);
      node.textContent = v.balance < i.cost ? 'Ещё ' + fmt(i.cost - v.balance) : 'Купить';
    }
    for (const button of d.querySelectorAll('[data-farm-action]:not([data-farm-action="buy"]):not([data-farm-action="boost"]):not([data-farm-action="refill"])')) {
      if (!button.dataset.initialDisabled) button.dataset.initialDisabled = button.disabled ? 'yes' : 'no';
      button.disabled = f.busy || f.failed || button.dataset.initialDisabled === 'yes';
    }
    const collect = $('[data-farm-action="claim_all"]', d);
    $('.farm-collect-bar', d).hidden = !s.claimable.count;
    collect.disabled = f.busy || f.failed || !s.claimable.count;
    $('[data-collect-count]', d).textContent = s.claimable.count ? 'Награды готовы · ' + s.claimable.count : 'Все награды собраны';
    $('[data-collect-amount]', d).textContent = s.claimable.amount ? '+' + fmt(s.claimable.amount) : '';
    const order = s.order,
      remaining = order ? Math.max(0, (order.finish_at - s.server_ms) / 1000 - age) : 0;
    for (const node of d.querySelectorAll('[data-order-clock]')) node.textContent = remaining ? 'Осталось ' + clock(remaining) : 'Доставка завершена';
    const orderLabel = $('[data-order-label]', d);
    if (orderLabel) orderLabel.textContent = remaining ? 'В ПУТИ' : 'ДОСТАВЛЕНО';
    $('.farm-active-order', d)?.classList.toggle('is-ready', remaining === 0);
    const orderProgress = $('[data-order-progress]', d);
    if (orderProgress) orderProgress.value = order.seconds - remaining;
    const orderClaim = $('[data-farm-action="claim_order"]', d);
    if (orderClaim) orderClaim.disabled = f.busy || f.failed || remaining > 0;
    const boost = $('[data-farm-action="boost"]', d),
      refill = $('[data-farm-action="refill"]', d);
    if (boost) {
      boost.disabled = f.busy || f.failed || v.boost > 0 || !s.daily.boosts_left;
      $('[data-boost-label]', d).textContent = v.boost > 0 ? 'Ещё ' + clock(v.boost) : `30 секунд · ${s.daily.boosts_left}/2`;
    }
    if (refill) {
      const wait = Math.max(0, s.daily.refill_seconds - age);
      refill.disabled = f.busy || f.failed || wait > 0 || !s.daily.refills_left || v.energy >= s.stats.energy_max;
      $('[data-refill-label]', d).textContent = wait > 0 ? 'Через ' + clock(wait) : v.energy >= s.stats.energy_max ? 'Энергия полная' : !s.daily.refills_left ? 'Снова завтра' : `${s.daily.refills_left}/2 на сегодня`;
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
    for (const c of s.chapters) {
      const node = d.querySelector('[data-chapter="' + c.id + '"]');
      if (node) {
        $('progress', node).value = Math.min(c.value, c.goal);
        $('small', node).textContent = fmt(Math.min(c.value, c.goal)) + ' / ' + fmt(c.goal);
      }
    }
    for (const button of d.querySelectorAll('[data-farm-action="start_order"]')) {
      const option = s.orders.find(o => o.id === button.dataset.item);
      button.disabled = f.busy || f.failed || !!s.order || s.level < option.unlock || v.balance < option.cost;
    }
    for (const b of s.badges) {
      const node = d.querySelector('[data-badge="' + b.id + '"]');
      if (node) $('small', node).textContent = b.description + ' · ' + fmt(Math.min(b.value, b.target)) + ' / ' + fmt(b.target);
    }
    const reset = $('[data-farm-reset]', d);
    if (reset) reset.textContent = 'Обновление через ' + clock((s.daily.reset_at - s.server_ms) / 1000 - age);
    for (const b of d.querySelectorAll('[data-farm-tab="tasks"] i')) {
      const count = s.claimable.count;
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
    d.dataset.saveState = f.failed ? 'error' : f.inflight || f.taps ? 'pending' : 'saved';
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
      f.lastResult = value.result;
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
        if (kind === 'claim_all') {
          f.returning = null;
          status(f, '');
        } else if (kind === 'start_order') status(f, 'Заказ отправлен');
        else if (kind === 'claim_order' || kind === 'claim_chapter') status(f, 'Награда в корзинке');
        else if (kind === 'buy') status(f, 'Улучшение куплено');
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
    if (b.dataset.taskView) {
      f.taskView = b.dataset.taskView;
      f.tab = 'tasks';
      persistUi(f);
      render(f);
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
    const order = f.snapshot.order;
    if (order && f.orderReadyChecked !== order.finish_at && f.snapshot.server_ms + (performance.now() - f.received) >= order.finish_at) {
      f.orderReadyChecked = order.finish_at;
      f.pollAt = 0;
    }
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
