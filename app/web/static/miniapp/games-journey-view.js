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
  const palettes = {
    orbit: ['#7074a6', '#d9deed'],
    evolve: ['#738c72', '#e0e7d8'],
    bugs: ['#a27e52', '#eee0cc'],
    tower: ['#758a9c', '#dce5e9'],
    typing: ['#8c8060', '#e9e4d4'],
    debug: ['#687e9c', '#dbe3ec'],
    '2048': ['#a17b56', '#efdfc9'],
    drop: ['#8575a4', '#e4deed'],
    memory: ['#678976', '#dce8df'],
    react: ['#9c8c52', '#ece5cc'],
    blocks: ['#687f94', '#dde4e8'],
    runner: ['#89729b', '#e7ddeb'],
    bubbles: ['#5e8d94', '#d9e8e7'],
    sort: ['#789174', '#e0e8d9'],
    words: ['#998253', '#ece3cc']
  };
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

  function scenery(game, chapter, ink, wash) {
    const n = chapter + 3;
    if (['orbit', 'drop'].includes(game)) return Array.from({
      length: n
    }, (_, i) => `<g transform="translate(${45+i*560/n} ${48+i%2*30})"><circle r="${9+i*2}" fill="${wash}" stroke="${ink}" stroke-width="1"/><ellipse rx="${16+i*2}" ry="5" transform="rotate(-25)" fill="none" stroke="${ink}"/></g>`).join('');
    if (['tower', '2048', 'runner'].includes(game)) return Array.from({
      length: n + 3
    }, (_, i) => {
      const h = 20 + (i * 23 + chapter * 11) % 62,
        x = 20 + i * 600 / (n + 3);
      return `<g><path d="M${x} 133v-${h}h38v${h}" fill="${wash}" stroke="${ink}"/>${Array.from({length:3},(_,k)=>`<path d="M${x+8} ${140-h+k*12}h5m9 0h5" stroke="${ink}" stroke-width="3"/>`).join('')}</g>`;
    }).join('');
    if (game === 'bubbles') return Array.from({
      length: n + 2
    }, (_, i) => `<path d="M${25+i*590/(n+2)} 145q-20-30 0-58m0 58q20-25 10-42" fill="none" stroke="${ink}" stroke-width="3"/><circle cx="${45+i*540/(n+2)}" cy="${45+i%3*20}" r="${5+i%3*3}" fill="none" stroke="${ink}"/>`).join('');
    if (game === 'bugs') return `<path d="M25 115h70V52h80v40h80V35h80v70h90V54h90v55h100" fill="none" stroke="${ink}" stroke-width="3"/>${Array.from({length:n},(_,i)=>`<rect x="${45+i*550/n}" y="${i%2?48:95}" width="21" height="21" rx="4" fill="${wash}" stroke="${ink}"/>`).join('')}`;
    if (['words', 'typing', 'debug'].includes(game)) return Array.from({
      length: n + 2
    }, (_, i) => `<g transform="translate(${25+i*590/(n+2)} 78) rotate(${i%2?-8:5})"><path d="M0 0h40v52H0Z" fill="${wash}" stroke="${ink}"/><path d="M7 10h24m-24 9h19m-19 9h24m-24 9h14" stroke="${ink}"/></g>`).join('');
    if (game === 'sort') return Array.from({
      length: n
    }, (_, i) => `<g transform="translate(${45+i*550/n} 70)"><path d="M0 0v43q0 18 15 18t15-18V0" fill="none" stroke="${ink}" stroke-width="2"/><path d="M2 29h26v16q-2 14-13 14T2 45Z" fill="${wash}"/><path d="m8 35 7-7 7 7-7 12Z" fill="${ink}"/></g>`).join('');
    if (game === 'react') return `<path d="M210 150 290 15h60l80 135" fill="${wash}" stroke="${ink}"/><path d="M320 35v20m0 17v20m0 17v20" stroke="${ink}" stroke-width="4"/>`;
    if (game === 'memory') return Array.from({
      length: n
    }, (_, i) => `<g transform="translate(${35+i*570/n} 84) rotate(${i%2?7:-7})"><rect width="43" height="43" rx="5" fill="${wash}" stroke="${ink}"/><path d="M10 11h23v22H10Z" fill="none" stroke="${ink}"/></g>`).join('');
    if (game === 'blocks') return Array.from({
      length: 16
    }, (_, i) => `<rect x="${70+i%8*66}" y="${85+Math.floor(i/8)*24}" width="20" height="20" rx="3" fill="${(i+chapter)%3?wash:ink}"/>`).join('');
    return Array.from({
      length: n
    }, (_, i) => `<path d="M${45+i*540/n} 133v-30q-28-21-16-42 36 1 16 42 32-19 24-40-32 0-24 40" fill="${wash}" stroke="${ink}"/>`).join('');
  }

  function landscape(game, chapter) {
    const [ink, wash] = palettes[game], shift = chapter * 4;
    return `<svg class="journey-landscape" viewBox="0 0 640 150" aria-hidden="true"><path d="M0 130Q90 ${40+shift} 180 107T400 90T640 110V150H0Z" fill="${wash}"/><path d="M0 141Q100 70 230 126T460 113T640 126" fill="none" stroke="${ink}" stroke-width="1" opacity=".25"/><g opacity=".26">${scenery(game,chapter,ink,wash)}</g><path d="M35 115C130 145 160 50 270 85S440 135 595 52" fill="none" stroke="${ink}" stroke-width="2" stroke-dasharray="4 7" opacity=".4"/>${Array.from({length:5},(_,i)=>`<circle cx="${40+i*143}" cy="${i%2?50:35}" r="${3+chapter%3}" fill="${ink}" opacity="${.08+i*.03}"/>`).join('')}<circle cx="${510-shift}" cy="35" r="23" fill="${ink}" opacity=".1"/></svg>`;
  }

  function hub(game, saved, selected) {
    const spec = J.specs[game];
    if (!spec) return '';
    saved = saved || {
      unlocked: 1,
      stars: 0,
      cleared: 0,
      charges: 1,
      records: [],
      keepsakes: []
    };
    const stage = selected || saved.unlocked,
      m = J.mission(game, stage),
      [ink, wash] = palettes[game],
      goals = starGoals(m);
    return `<section class="journey-hub" style="--journey-ink:${ink};--journey-wash:${wash}" data-journey-game="${game}"><div class="journey-cover"><div><span class="journey-eyebrow">${String(m.chapter+1).padStart(2,'0')} / 06</span><h3>${esc(spec.name)}</h3><p>${saved.cleared}/24 заданий <span>·</span> ${saved.stars}/72 ★</p></div><div class="journey-cover-art">${AlgoGameArt.render(game)}</div></div><nav class="journey-chapters" aria-label="Главы">${spec.chapters.map((name,i)=>`<button data-journey-chapter="${i}" aria-pressed="${i===m.chapter}" ${i*4+1>saved.unlocked?'disabled':''}><span>${saved.keepsakes.includes(i+1)?'✓':String(i+1).padStart(2,'0')}</span><b>${esc(name)}</b></button>`).join('')}</nav><div class="journey-route">${landscape(game,m.chapter)}${Array.from({length:4},(_,i)=>{const number=m.chapter*4+i+1,r=saved.records.find(r=>r.stage===number),locked=number>saved.unlocked;return `<button data-journey-stage="${number}" ${locked?'disabled':''} class="journey-stop ${number===stage?'is-selected':''} ${r?'is-complete':''}"><span>${r?'✓':number}</span><b>${number===stage?'Сейчас':locked?'Закрыто':r?'Пройдено':'Задание '+number}</b><small aria-label="${r?.stars||0} из 3 звёзд">${stars(r?.stars||0)}</small></button>`;}).join('')}</div><div class="journey-mission"><div class="journey-mission-head"><small>ЗАДАНИЕ ${stage}</small><span>${Math.ceil(m.seconds/60)} мин${m.moves?' · '+Math.ceil(m.moves)+' ходов':''}</span></div><h4>${esc(m.title)}</h4><p>${game==='drop'?esc(ArcadeDrop.get(ArcadeDrop.chapter(stage)).name)+' · ':''}${esc(m.rule)}${m.minimumWord===4?' · слова от четырёх букв':''}</p><ul class="journey-star-goals">${goals.map((g,i)=>`<li><span>${'★'.repeat(i+1)}</span>${esc(g)}</li>`).join('')}</ul><button class="games-main journey-start" data-journey-play="${stage}">${saved.records.some(r=>r.stage===stage)?'Улучшить результат':'Начать задание'} <span>→</span></button></div><div class="journey-kit"><span class="journey-kit-symbol">${game==='debug'?'⌕':game==='typing'?'Aa':game==='words'?'Б':game==='2048'?'⇄':'◇'}</span><div><b>${esc(spec.power)} <span>×${saved.charges}</span></b><p>${esc(spec.action)}</p><small>${saved.charges===1?'Второе применение — после главы 2':saved.charges===2?'Третье применение — после главы 4':'Все улучшения инструмента открыты'}</small></div></div><div class="journey-collection"><div><small>${esc(spec.reward)}</small><span>${saved.keepsakes.length}/6</span></div><ol>${spec.chapters.map((title,i)=>`<li title="${esc(title)}" class="${saved.keepsakes.includes(i+1)?'is-earned':''}"><span>${saved.keepsakes.includes(i+1)?'✦':'◇'}</span><small>${i+1}</small></li>`).join('')}</ol></div></section>`;
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
    return `<div class="journey-result-head"><small>ЗАДАНИЕ ${j.stage} · ${esc(m.title)}</small><div class="journey-result-stars" aria-label="${j.stars} из 3 звёзд">${stars(j.stars)}</div><h3>${j.success?'Готово!':'Попробуем ещё?'}</h3><p>${j.success?`${report.score} / ${j.goal} · лучший результат: ${record?.stars||j.stars} ★`:esc(report.reason)}</p></div><ul class="journey-result-goals">${starGoals(m).map((g,i)=>`<li class="${j.stars>i?'is-done':''}"><span>${j.stars>i?'✓':'○'}</span>${esc(g)}</li>`).join('')}</ul>${j.success&&j.stage%4===0?`<div class="journey-keepsake">✦ Глава пройдена · ${esc(J.specs[run.g.id].reward)}</div>`:''}<button class="games-main" data-journey-next>${!j.success?'Повторить задание':j.stage<24?'Следующее задание →':'К маршруту'}</button>${j.success?'<button class="game-back" data-journey-retry>Повторить задание</button>':''}${!j.success||j.stage<24?'<button class="game-back" data-journey-map>К маршруту</button>':''}`;
  }

  function collection(saved) {
    const entries = Object.entries(saved || {}).filter(([, s]) => s.cleared > 0);
    if (!entries.length) return '';
    return `<section class="journey-shelf"><h3>Коллекция приключений</h3><div>${entries.map(([game,s])=>`<button data-game="${game}"><span>${AlgoGameArt.render(game)}</span><div><b>${esc(J.specs[game].name)}</b><small>${s.cleared}/24 заданий · ${s.stars}/72 ★</small><em>${Array.from({length:6},(_,i)=>`<i class="${s.keepsakes.includes(i+1)?'is-earned':''}">✦</i>`).join('')}</em></div><strong>→</strong></button>`).join('')}</div></section>`;
  }
  window.ArcadeJourneyView = {
    hub,
    collection,
    tools,
    result,
    labels,
    starGoals
  };
})();
