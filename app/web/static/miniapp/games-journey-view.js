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

  function countWord(n, forms) {
    return forms[n % 100 >= 11 && n % 100 <= 14 ? 2 : n % 10 === 1 ? 0 : n % 10 >= 2 && n % 10 <= 4 ? 1 : 2];
  }

  function labels(m) {
    if(m.game==='sort'&&m.routeVersion===2)return m.goal+' '+countWord(m.goal,['задача','задачи','задач'])+' · '+(m.boss&&m.goal>1&&m.colors<7?m.colors+'–'+(m.colors+1)+' цветов':m.colors+' '+countWord(m.colors,['цвет','цвета','цветов']));
    if(m.game==='hill') return 'Проедь '+m.goal+' м';
    if(m.game==='evolve') return m.goal+' очков · спаси '+Math.ceil(m.stage/4)+' '+countWord(Math.ceil(m.stage/4),['зверя','зверей','зверей']);
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
    return m.goal + ' ' + countWord(m.goal, forms[m.game]|| (m.game==='plane'?['метр','метра','метров']:['очко','очка','очков']));
  }

  function starGoals(m) {
    const g = m.game,
      n = m.goal;
    if(g==='sort'&&m.routeVersion===2)return [labels(m),
      'До '+m.silverMoves+' ходов','До '+m.goldMoves+' ходов без запасной колбы'];
    const extra = {
      orbit: ['Посадок по центру: ' + Math.ceil(n * .5), 'Посадок по центру: ' + Math.ceil(n * .8)],
      tower: ['Укладок по центру: ' + Math.ceil(n / 4), 'Укладок по центру: ' + Math.ceil(n / 2)],
      typing: ['Точность от 93%', 'Точность от 98%'],
      react: ['Не больше одной ошибки', 'Без ошибок, реакция до 350 мс'],
      memory: ['Не больше трёх ходов на пару', 'Не больше двух ходов на пару'],
      '2048': ['Не больше ' + Math.floor(m.moves * .9) + ' ходов', 'Не больше ' + Math.floor(m.moves * .7) + ' ходов'],
      evolve: ['Сохрани 8 единиц воздуха', 'Спаси '+Math.ceil(n/24)+' зверей без помощи'],
      drop: ['Не больше ' + (Math.ceil(n / 8) + 10) + ' бросков', 'Не больше ' + (Math.ceil(n / 12) + 8) + ' бросков'],
      blocks: ['Очищенных линий: ' + Math.ceil(n / 200), 'Серия из двух очищений'],
      runner: ['Не больше ' + (n + 2) + ' прыжков', 'Не больше ' + n + ' прыжков'],
      hill: ['Сохрани 20 литров топлива','Сохрани 40 литров без запасной канистры'],
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
    b.textContent = w.id==='sort'&&w.sortRules>=4&&w.sortPowerUsed?'Колба добавлена':j.swapSelecting ? 'Отменить обмен' : j.used >= j.charges ? 'Использовано' : 'Применить · ' + (j.charges - j.used);
    const blocked = w.id === 'blocks' && !J.rotatable(w) || w.id === 'bugs' && !w.targets.some(t => !t.good) || w.id === 'tower' && j.magnet || w.id === 'orbit' && j.correction || w.id === 'memory' && j.revealUntil > w.time || w.id === 'debug' && (w.answered || j.hintAt === w.index) || w.id === 'bubbles' && w.projectile || w.id === 'sort' && (w.sortWon||(w.sortRules>=4&&w.sortPowerUsed)) || w.id === 'words' && w.wordHint || ['typing', 'react', 'runner'].includes(w.id) && j.powerUntil > w.time;
    b.disabled = j.used >= j.charges || run.phase !== 'playing' || !!blocked;
    run.dialog.dataset.journeyPower = j.powerUntil > w.time || j.correction || j.magnet ? 'on' : 'off';
  }

  function collection(saved) {
    const entries = Object.entries(saved || {}).filter(([, s]) => s.cleared > 0);
    if (!entries.length) return '';
    return `<section class="journey-shelf"><h3>Коллекция приключений</h3><div>${entries.map(([game,s])=>`<button data-game="${game}"><span>${AlgoGameArt.render(game)}</span><div><b>${esc(J.specs[game].name)}</b><small>${s.cleared}/${s.maximum||24} заданий · ${s.stars}/${(s.maximum||24)*3} ★</small><em>${Array.from({length:Math.ceil((s.maximum||24)/(s.chapterSize||4))},(_,i)=>`<i class="${s.keepsakes.includes(i+1)?'is-earned':''}">✦</i>`).join('')}</em></div><strong>→</strong></button>`).join('')}</div></section>`;
  }
  window.ArcadeJourneyView = {
    collection,
    tools,
    labels,
    starGoals
  };
})();
