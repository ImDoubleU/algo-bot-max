/* Illustrated route pages and active tools; all progression comes from the server. */
(() => {
  'use strict';
  const J = ArcadeJourney,
    esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;'
    } [c]));
  const stars = n => '★'.repeat(n) + '☆'.repeat(3 - n);

  function countWord(n, forms) {
    return forms[n % 100 >= 11 && n % 100 <= 14 ? 2 : n % 10 === 1 ? 0 : n % 10 >= 2 && n % 10 <= 4 ? 1 : 2];
  }

  function labels(m) {
    if (m.game === '2048') return 'Собери плитку ' + m.goal + (m.corner ? ' в левом верхнем углу' : '');
    const forms = {
      orbit: ['прыжок', 'прыжка', 'прыжков'],
      evolve: ['очко', 'очка', 'очков'],
      bugs: ['баг', 'бага', 'багов'],
      tower: ['этаж', 'этажа', 'этажей'],
      typing: ['верный символ', 'верных символа', 'верных символов'],
      debug: ['раскрытая ошибка', 'раскрытые ошибки', 'раскрытых ошибок'],
      drop: ['очко', 'очка', 'очков'],
      memory: ['пара', 'пары', 'пар'],
      react: ['сигнал', 'сигнала', 'сигналов'],
      blocks: ['очко', 'очка', 'очков'],
      runner: ['преграда', 'преграды', 'преград'],
      bubbles: ['очко', 'очка', 'очков'],
      sort: ['опыт', 'опыта', 'опытов'],
      words: ['слово', 'слова', 'слов']
    };
    return m.goal + ' ' + countWord(m.goal, forms[m.game]);
  }

  function starGoals(m) {
    const g = m.game,
      n = m.goal;
    const extra = {
      orbit: ['Посадок по центру: ' + Math.ceil(n * .5), 'Посадок по центру: ' + Math.ceil(n * .8)],
      tower: ['Укладок по центру: ' + Math.ceil(n / 4), 'Укладок по центру: ' + Math.ceil(n / 2)],
      typing: ['Точность от 93%', 'Точность от 98%'],
      react: ['Не больше одной ошибки', 'Без ошибок, реакция до 350 мс'],
      memory: ['Не больше трёх ходов на пару', 'Не больше двух ходов на пару'],
      '2048': ['Не больше ' + Math.floor(m.moves * .9) + ' ходов', 'Не больше ' + Math.floor(m.moves * .7) + ' ходов'],
      evolve: ['Не больше ' + Math.ceil(n / 4) + ' объединений', 'Открой зверя ' + (m.species + 1) + ' уровня'],
      drop: ['Не больше ' + (Math.ceil(n / 8) + 10) + ' бросков', 'Не больше ' + (Math.ceil(n / 12) + 8) + ' бросков'],
      blocks: ['Очищенных линий: ' + Math.ceil(n / 200), 'Серия из двух очищений'],
      runner: ['Не больше ' + (n + 2) + ' прыжков', 'Не больше ' + n + ' прыжков'],
      bubbles: ['Не больше ' + (Math.ceil(n / 18) + 10) + ' выстрелов', 'Не больше ' + (Math.ceil(n / 30) + 5) + ' выстрелов'],
      sort: ['Не больше ' + n * 110 + ' переливаний', 'Не больше ' + n * 65 + ' переливаний'],
      words: ['Не больше двух ошибок', 'Слов от пяти букв: ' + Math.ceil(n / 3) + ' · без ошибок']
    } [g] || ['Не больше двух ошибок', 'Без ошибок за ' + Math.floor(m.seconds * .75) + ' с'];
    return [labels(m), ...extra];
  }

  function tools(run) {
    const w = run.world,
      j = w.journey,
      host = run.dialog.querySelector('.journey-tools');
    if (!j) {
      host.hidden = true;
      return;
    }
    host.hidden = false;
    host.querySelector('b').textContent = j.power;
    host.querySelector('small').textContent = j.notes || (j.powerUntil > w.time ? 'Действует ещё ' + Math.ceil(j.powerUntil - w.time) + ' с' : j.action);
    const b = host.querySelector('button');
    b.textContent = j.swapSelecting ? 'Отменить обмен' : j.used >= j.charges ? 'Использовано' : 'Применить · ' + (j.charges - j.used);
    const blocked = w.id === 'blocks' && !J.rotatable(w) || w.id === 'bugs' && !w.targets.some(t => !t.good) || w.id === 'tower' && j.magnet || w.id === 'orbit' && j.correction || w.id === 'memory' && j.revealUntil > w.time || w.id === 'debug' && (w.answered || j.hintAt === w.index) || w.id === 'bubbles' && w.projectile || w.id === 'sort' && w.sortWon || w.id === 'words' && w.wordHint || ['typing', 'react', 'runner'].includes(w.id) && j.powerUntil > w.time;
    b.disabled = j.used >= j.charges || run.phase !== 'playing' || !!blocked;
    run.dialog.dataset.journeyPower = j.powerUntil > w.time || j.correction || j.magnet ? 'on' : 'off';
  }

  function result(run, report, saved) {
    const j = report.journey,
      m = J.mission(run.g.id, j.stage),
      record = saved.records.find(r => r.stage === j.stage);
    return `<div class="journey-result-head"><small>УРОВЕНЬ ${j.stage} · ${esc(m.title)}</small><div class="journey-result-stars" aria-label="${j.stars} из 3 звёзд">${stars(j.stars)}</div><h3>${j.success?'Готово!':'Попробуем ещё?'}</h3><p>${j.success?`${report.score} / ${j.goal} · лучший результат: ${record?.stars||j.stars} ★`:esc(report.reason)}</p></div><ul class="journey-result-goals">${starGoals(m).map((g,i)=>`<li class="${j.stars>i?'is-done':''}"><span>${j.stars>i?'✓':'○'}</span>${esc(g)}</li>`).join('')}</ul>${j.success&&j.stage%4===0?`<div class="journey-keepsake">✦ Глава пройдена · ${esc(J.specs[run.g.id].reward)}</div>`:''}<button class="games-main" data-journey-next>${!j.success?'Повторить уровень':j.stage<24?'Следующий уровень →':'К уровням'}</button>${j.success?'<button class="game-back" data-journey-retry>Повторить уровень</button>':''}${!j.success||j.stage<24?'<button class="game-back" data-journey-map>К уровням</button>':''}`;
  }

  function collection(saved) {
    const entries = Object.entries(saved || {}).filter(([, s]) => s.cleared > 0);
    if (!entries.length) return '';
    return `<section class="journey-shelf"><h3>Коллекция приключений</h3><div>${entries.map(([game,s])=>`<button data-game="${game}"><span>${AlgoGameArt.render(game)}</span><div><b>${esc(J.specs[game].name)}</b><small>${s.cleared}/24 заданий · ${s.stars}/72 ★</small><em>${Array.from({length:6},(_,i)=>`<i class="${s.keepsakes.includes(i+1)?'is-earned':''}">✦</i>`).join('')}</em></div><strong>→</strong></button>`).join('')}</div></section>`;
  }
  window.ArcadeJourneyView = {
    collection,
    tools,
    result,
    labels,
    starGoals
  };
})();
