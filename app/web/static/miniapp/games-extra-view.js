/* Original vector art and responsive controls for the six added arcade games. */
(() => {
  "use strict";
  const X = ArcadeExtras,
    M = AlgoGameMotion,
    colors = X.colors;
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  } [c]));
  const bear = (gold = false) => `<svg viewBox="0 0 240 240" aria-hidden="true"><ellipse cx="120" cy="219" rx="74" ry="10" fill="#203b272a"/><path d="M65 191q-17-51 55-57 71 6 54 57l-10 25H77Z" fill="#a96931" stroke="#643d2e" stroke-width="4"/><circle cx="63" cy="89" r="26" fill="#9d5d2e" stroke="#643d2e" stroke-width="4"/><circle cx="177" cy="89" r="26" fill="#9d5d2e" stroke="#643d2e" stroke-width="4"/><circle cx="63" cy="89" r="14" fill="#d6985c"/><circle cx="177" cy="89" r="14" fill="#d6985c"/><circle cx="120" cy="123" r="73" fill="#b97a3b" stroke="#643d2e" stroke-width="4"/><ellipse cx="120" cy="148" rx="44" ry="32" fill="#edc783"/><ellipse cx="98" cy="114" rx="15" ry="21" fill="#fff8da"/><ellipse cx="142" cy="114" rx="15" ry="21" fill="#fff8da"/><ellipse cx="101" cy="119" rx="5" ry="8" fill="#34303a"/><ellipse cx="139" cy="119" rx="5" ry="8" fill="#34303a"/><path d="M111 139q9-9 18 0l-3 10h-12Z" fill="#633e2b"/><path d="M120 150v9m-16-1q16 15 32 0" fill="none" stroke="#633e2b" stroke-width="4" stroke-linecap="round"/><path d="m84 87 24 3m24 0 24-3" stroke="#633e2b" stroke-width="6" stroke-linecap="round"/><path d="M58 78q64-30 125 0l-6 16q-57-13-114 0Z" fill="${gold?'#ffe58a':'#edd179'}" stroke="#a08337" stroke-width="3"/><path d="m82 73 9-35q28-19 58 0l9 35Z" fill="#e7c76a" stroke="#a08337" stroke-width="3"/><path d="M87 57q35-12 66 0" fill="none" stroke="#a08337" stroke-width="3"/><path d="m177 180 14-14 15 16-14 14Z" fill="#90b862" stroke="#527443" stroke-width="3"/><path d="m189 181-14 33" stroke="#80552e" stroke-width="5" stroke-linecap="round"/></svg>`;
  const carrot = () => '<svg viewBox="0 0 40 40" aria-hidden="true"><path d="M13 12q13-9 17 4L8 36Z" fill="#ed9e52" stroke="#a56835" stroke-width="2"/><path d="m23 11 1-9m3 10 9-5m-15 2-6-6" stroke="#8cbb62" stroke-width="4" stroke-linecap="round"/><path d="m17 19 5 2m-9 5 5 2" stroke="#d5823e" stroke-width="2"/></svg>';
  const shapeSvg = (p, color = "#b8a1ed", scale = 25) => {
    const width = Math.max(...p.map(v => v[0])) + 1,
      height = Math.max(...p.map(v => v[1])) + 1;
    return `<svg viewBox="0 0 ${width*scale} ${height*scale}" aria-hidden="true">${p.map(([x,y])=>`<rect x="${x*scale+1}" y="${y*scale+1}" width="${scale-2}" height="${scale-2}" rx="4" fill="${color}"/><path d="M${x*scale+5} ${y*scale+5}h${scale-10}" stroke="#ffffff55" stroke-width="2" stroke-linecap="round"/>`).join('')}</svg>`;
  };

  function art(id) {
    let body = '';
    if (id === 'kopatych') body = `<g transform="translate(38 -9) scale(.74)">${bear().replace(/<\/?svg[^>]*>/g,'')}</g><g transform="translate(25 109) scale(.8)">${carrot().replace(/<\/?svg[^>]*>/g,'')}</g>`;
    if (id === 'blocks') body = `<g transform="translate(45 32)">${shapeSvg([[0,0],[0,1],[1,1],[2,1]],'#9c85d2',36).replace(/<\/?svg[^>]*>/g,'')}</g><g transform="translate(131 79)">${shapeSvg([[0,0],[1,0],[0,1],[1,1]],'#ecc36e',33).replace(/<\/?svg[^>]*>/g,'')}</g><path d="M41 145h171" stroke="#b5a6cd" stroke-width="3" stroke-dasharray="5 7"/>`;
    if (id === 'runner') body = '<path d="M28 142h200" stroke="#a296cb" stroke-width="3"/><g transform="rotate(-17 99 84)"><rect x="61" y="45" width="76" height="76" rx="15" fill="#b9a4f1" stroke="#77629f" stroke-width="3"/><rect x="78" y="66" width="10" height="14" rx="4" fill="#433954"/><rect x="111" y="66" width="10" height="14" rx="4" fill="#433954"/><path d="M85 97h29" stroke="#433954" stroke-width="5" stroke-linecap="round"/></g><path d="m157 140 22-44 22 44Z" fill="#efad91" stroke="#b98677" stroke-width="3"/><path d="m36 78-14 9m17 14H18m28 19-17 8" stroke="#d0bee8" stroke-width="4" stroke-linecap="round"/>';
    if (id === 'bubbles') body = `${[[84,50,0],[124,50,1],[164,50,0],[64,85,2],[104,85,0],[144,85,3],[184,85,2],[84,120,1],[164,120,0]].map(([x,y,i])=>`<circle cx="${x}" cy="${y}" r="19" fill="${colors[i]}" stroke="#8e7fa2" stroke-width="2"/><path d="M${x-9} ${y-6}q4-7 11-6" stroke="#ffffff99" stroke-width="3" stroke-linecap="round"/>`).join('')}<path d="m124 153 0-33m-6 6 6-8 6 8" stroke="#a68fbe" stroke-width="3" stroke-linecap="round"/>`;
    if (id === 'sort') body = `${[0,1,2].map((n)=>`<g transform="rotate(${n===0?-8:n===2?8:0} ${75+n*55} 90)"><path d="M${57+n*55} 40v91q0 19 18 19t18-19V40" fill="#ffffff44" stroke="#9c91b0" stroke-width="3"/>${[0,1,2].map((j)=>`<circle cx="${75+n*55}" cy="${129-j*29}" r="13" fill="${colors[(n+j)%3]}"/><circle cx="${71+n*55}" cy="${125-j*29}" r="3" fill="#ffffff88"/>`).join('')}</g>`).join('')}`;
    if (id === 'words') body = `${[['С',64,54,0],['Л',109,45,1],['О',154,56,2],['В',91,104,3],['А',139,108,4]].map(([t,x,y,i])=>`<g transform="rotate(${i%2?8:-7} ${x+18} ${y+18})"><rect x="${x}" y="${y}" width="39" height="43" rx="10" fill="${colors[i]}" stroke="#a394a5" stroke-width="2"/><text x="${x+20}" y="${y+29}" text-anchor="middle" fill="#66566f" font-family="system-ui" font-size="25" font-weight="800">${t}</text></g>`).join('')}`;
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 176" aria-hidden="true" data-arcade-mark="${id}">${body}</svg>`;
  }
  const $ = (s, r) => r.querySelector(s);

  function mount(id, stage, send, options) {
    stage.dataset.game = id;
    const on = (el, type, fn, extra = {}) => el.addEventListener(type, fn, {
      ...extra,
      signal: options.signal
    });
    const source = e => e?.pointerType ? (e.pointerType === 'touch' ? 'touch' : 'keyboard') : e?.type === 'keydown' ? 'keyboard' : options.device;
    const input = (a, e) => {
      if (!options.paused() && !options.readOnly) send({
        ...a,
        source: source(e)
      });
    };
    let world = null,
      lastCue = 0,
      update = () => {};
    if (id === 'kopatych') {
      stage.innerHTML = `<div class="kopatych-game"><div class="garden-cloud cloud-one"></div><div class="garden-cloud cloud-two"></div><div class="garden-summary"><div><small>В корзинке</small><strong data-bank>0</strong></div><div><small>Серия</small><strong data-combo>×1</strong></div><div><small>В секунду</small><strong data-auto>0</strong></div></div><div class="garden-sun" aria-hidden="true">✦</div><p class="garden-gold" role="status"></p><button class="kopatych-tap" aria-label="Собрать морковку">${window.KopatychArt?.character(false,1)||bear()}</button><div class="garden-bed" aria-hidden="true">${Array.from({length:7},()=>carrot()).join('')}</div><div class="garden-upgrades">${[['Лопата','+2 за нажатие'],['Грядка','Растёт сама'],['Теплица','Ускоряет грядки']].map(([t,d],i)=>`<button data-buy="${i}"><span class="garden-tool">${window.KopatychArt?.item(['shovel','bed','greenhouse'][i])||['↗','≋','⌂'][i]}</span><b>${t}</b><small>${d}</small><strong></strong></button>`).join('')}</div></div>`;
      const tap = $('.kopatych-tap', stage),
        pop = $('.kopatych-game', stage);
      on(tap, 'pointerdown', e => {
        e.preventDefault();
        input({
          type: 'tap'
        }, e);
      });
      on(tap, 'click', e => {
        if (e.detail === 0) input({
          type: 'tap'
        }, e);
      });
      on(document, 'keydown', e => {
        if (e.code === 'Space' && !e.repeat && !e.target.closest('[data-buy]')) {
          e.preventDefault();
          input({
            type: 'tap'
          }, e);
        }
      });
      on(stage, 'click', e => {
        const b = e.target.closest('[data-buy]');
        if (b) input({
          type: 'buy',
          i: +b.dataset.buy
        }, e);
      });
      update = (w, dt) => {
        world = w;
        const bank = Math.floor(w.harvest - w.spent);
        $('[data-bank]', stage).textContent = bank;
        $('[data-combo]', stage).textContent = '×' + (1 + Math.floor(w.combo / 10));
        $('[data-auto]', stage).textContent = (w.upgrades[1] * (1 + w.upgrades[2]) * .8).toFixed(1);
        const gold = w.time < w.goldUntil;
        pop.classList.toggle('is-gold', gold);
        $('.garden-gold', stage).textContent = gold ? 'Золотой урожай ×3' : '';
        for (const b of stage.querySelectorAll('[data-buy]')) {
          const i = +b.dataset.buy,
            cost = X.cost(w, i),
            max = w.upgrades[i] >= 6;
          b.disabled = options.readOnly || max || bank < cost;
          $('strong', b).textContent = max ? 'Максимум' : cost + ' морковок';
          b.setAttribute('aria-label', `${['Лопата','Грядка','Теплица'][i]}, уровень ${w.upgrades[i]}, ${cost} морковок`);
        }
        for (const cue of w.cues.filter(c => c.n > lastCue)) {
          if (cue.type === 'harvest') {
            M.pop(tap);
            const f = document.createElement('span');
            f.className = 'garden-float';
            f.textContent = '+' + cue.gain;
            f.style.left = (39 + Math.random() * 22) + '%';
            pop.append(f);
            setTimeout(() => f.remove(), 750);
          }
          if (cue.type === 'upgrade') M.pop($('.garden-upgrades', stage));
          lastCue = cue.n;
        }
      };
    }
    if (id === 'blocks') {
      stage.innerHTML = '<div class="blocks-game"><div class="blocks-meta"><span data-lines></span><b data-block-combo></b></div><div class="blocks-board" role="grid" aria-label="Поле 8 на 8">' + Array.from({
        length: 64
      }, (_, i) => `<button class="block-cell" data-block-cell="${i}" role="gridcell" aria-label="Ряд ${Math.floor(i/8)+1}, столбец ${i%8+1}"></button>`).join('') + '</div><div class="blocks-hand"></div><p class="blocks-instruction">Выбери фигуру · нажми на клетку или перетащи</p></div>';
      const board = $('.blocks-board', stage),
        hand = $('.blocks-hand', stage);
      let signature = '',
        drag = null,
        hover = null;
      const cellAt = (x, y) => {
        const r = board.getBoundingClientRect();
        if (x < r.left || x >= r.right || y < r.top || y >= r.bottom) return null;
        return {
          x: Math.min(7, Math.floor((x - r.left) / r.width * 8)),
          y: Math.min(7, Math.floor((y - r.top) / r.height * 8))
        };
      };

      function preview(at, piece) {
        for (const b of board.children) b.classList.remove('is-preview', 'is-invalid');
        if (!world || !at) return;
        const p = world.pieces[piece];
        if (!p) return;
        const valid = X.fitsBlock(world, p, at.x, at.y);
        for (const [dx, dy] of p) {
          const x = at.x + dx,
            y = at.y + dy;
          if (x < 8 && y < 8) {
            board.children[y * 8 + x].classList.add(valid ? 'is-preview' : 'is-invalid');
          }
        }
      }
      on(board, 'pointermove', e => {
        hover = cellAt(e.clientX, e.clientY);
        preview(hover, world?.selectedPiece);
      });
      on(board, 'pointerleave', () => preview(null, 0));
      on(board, 'click', e => {
        const b = e.target.closest('[data-block-cell]');
        if (b && world) input({
          type: 'place',
          piece: world.selectedPiece,
          x: +b.dataset.blockCell % 8,
          y: Math.floor(+b.dataset.blockCell / 8)
        }, e);
      });
      on(hand, 'pointerdown', e => {
        const b = e.target.closest('[data-piece]');
        if (!b || !world) return;
        e.preventDefault();
        drag = {
          piece: +b.dataset.piece,
          x: e.clientX,
          y: e.clientY,
          moved: false
        };
        input({
          type: 'piece',
          i: drag.piece
        }, e);
      });
      on(hand, 'click', e => {
        const b = e.target.closest('[data-piece]');
        if (b && e.detail === 0) input({
          type: 'piece',
          i: +b.dataset.piece
        }, e);
      });
      on(document, 'pointermove', e => {
        if (!drag) return;
        drag.moved ||= Math.hypot(e.clientX - drag.x, e.clientY - drag.y) > 7;
        preview(cellAt(e.clientX, e.clientY), drag.piece);
      });
      on(document, 'pointerup', e => {
        if (!drag) return;
        const d = drag;
        drag = null;
        const at = cellAt(e.clientX, e.clientY);
        if (at && d.moved) input({
          type: 'place',
          piece: d.piece,
          ...at
        }, e);
        preview(null, 0);
      });
      update = w => {
        world = w;
        [...board.children].forEach((b, i) => {
          b.style.setProperty('--cell', w.blockBoard[i] ? colors[w.blockBoard[i] - 1] : '');
          b.classList.toggle('is-filled', !!w.blockBoard[i]);
          b.setAttribute('aria-label', `Ряд ${Math.floor(i/8)+1}, столбец ${i%8+1}${w.blockBoard[i]?', занято':''}`);
        });
        const key = JSON.stringify([w.pieces, w.selectedPiece]);
        if (key !== signature) {
          signature = key;
          hand.innerHTML = w.pieces.map((p, i) => p ? `<button data-piece="${i}" aria-label="Фигура ${i+1}, ${p.length} клеток" aria-pressed="${w.selectedPiece===i}">${shapeSvg(p,colors[w.pieceColors[i]-1])}</button>` : '<div class="blocks-used" aria-label="Фигура использована">✓</div>').join('');
        }
        $('[data-lines]', stage).textContent = `Линий: ${w.lines}`;
        $('[data-block-combo]', stage).textContent = w.blockCombo > 1 ? 'Комбо ×' + w.blockCombo : '';
        for (const cue of w.cues.filter(c => c.n > lastCue)) {
          if (cue.type === 'clearLines')
            for (let i = 0; i < 64; i++)
              if (cue.rows.includes(Math.floor(i / 8)) || cue.cols.includes(i % 8)) M.pop(board.children[i]);
          lastCue = cue.n;
        }
      };
    }
    if (id === 'sort') return ArcadeSortView.mount(stage,send,options);
    if (id === 'words') {
      stage.innerHTML = '<div class="words-game"><div class="words-round"><b></b><span></span></div><div class="words-source"></div><form class="words-form"><label class="sr-only" for="arcadeWordInput">Новое слово</label><input id="arcadeWordInput" maxlength="32" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" placeholder="Составь слово"><button aria-label="Стереть букву" data-word-back type="button">⌫</button><button class="games-main" type="submit">Проверить</button></form><p class="words-message" role="status"></p><div class="words-found"></div><small class="words-rule">Существительные от 3 букв · словарь игры</small>' + (options.mode === 'practice' ? '<button class="arcade-subtle" data-word-hint>Подсказка</button>' : '') + '</div>';
      const field = $('input', stage);
      let root = '',
        signature = '',
        cue = 0;
      on($('.words-form', stage), 'submit', e => {
        e.preventDefault();
        input({
          type: 'word',
          value: field.value
        }, e);
      });
      on(stage, 'click', e => {
        const b = e.target.closest('button');
        if (!b) return;
        if (b.dataset.letter !== undefined && world) {
          const letter = world.wordPack.root[+b.dataset.letter].toLowerCase(),
            used = field.value.toLowerCase().split(letter).length - 1,
            available = world.wordPack.root.toLowerCase().split(letter).length - 1;
          if (used < available) {
            field.value += letter;
            markUsed();
          }
        }
        if (b.hasAttribute('data-word-back')) {
          field.value = field.value.slice(0, -1);
          markUsed();
        }
        if (b.hasAttribute('data-word-hint')) input({
          type: 'hint'
        }, e);
      });
      on(field, 'input', () => markUsed());

      function markUsed() {
        const letters = field.value.toLowerCase().replace(/ё/g, 'е').split('');
        for (const b of stage.querySelectorAll('[data-letter]')) {
          const letter = b.textContent.toLowerCase().replace(/ё/g, 'е'),
            i = letters.indexOf(letter);
          b.classList.toggle('is-used', i >= 0);
          if (i >= 0) letters.splice(i, 1);
        }
      }
      update = w => {
        world = w;
        if (root !== w.wordPack.root) {
          root = w.wordPack.root;
          field.value = '';
          $('.words-source', stage).innerHTML = [...root].map((t, i) => `<button type="button" data-letter="${i}">${esc(t)}</button>`).join('');
        }
        const key = w.roundWords.join();
        if (signature !== key) {
          signature = key;
          $('.words-found', stage).innerHTML = w.roundWords.map(t => `<span>${esc(t)}</span>`).join('');
        }
        $('.words-round b', stage).textContent = `Подборка ${Math.min(5,w.wordRound+1)} / 5`;
        $('.words-round span', stage).textContent = `${w.roundWords.length} / 8 слов`;
        $('.words-message', stage).textContent = w.wordHint ? 'Подсказка: ' + w.wordHint : w.wordFeedback;
        for (const c of w.cues.filter(c => c.n > cue)) {
          if (c.type === 'wordFound') {
            field.value = '';
            markUsed();
            M.pop($('.words-found', stage));
          }
          cue = c.n;
        }
      };
    }
    if (id === 'runner' || id === 'bubbles') {
      const canvas = document.createElement('canvas');
      canvas.width = 720;
      canvas.height = 860;
      canvas.tabIndex = 0;
      canvas.setAttribute('aria-label', X.games.find(g => g.id === id).hint);
      stage.append(canvas);
      const c = canvas.getContext('2d');
      let aim = {
          x: 180,
          y: 80
        },
        debris = [],
        trail = [],
        previous = null;
      const point = e => {
        const r = canvas.getBoundingClientRect(),
          s = Math.min(r.width / 360, r.height / 430);
        return {
          x: (e.clientX - r.left - (r.width - 360 * s) / 2) / s,
          y: (e.clientY - r.top - (r.height - 430 * s) / 2) / s
        };
      };
      on(canvas, 'pointermove', e => {
        aim = point(e);
      });
      on(canvas, 'pointerdown', e => {
        e.preventDefault();
        const p = point(e);
        input(id === 'runner' ? {
          type: 'tap'
        } : {
          type: 'shoot',
          ...p
        }, e);
      });
      on(document, 'keydown', e => {
        if (['Space', 'ArrowUp'].includes(e.code) && !e.repeat) {
          e.preventDefault();
          input(id === 'runner' ? {
            type: 'tap'
          } : {
            type: 'shoot',
            ...aim
          }, e);
        }
        if (id === 'bubbles' && ['ArrowLeft', 'ArrowRight'].includes(e.code)) {
          e.preventDefault();
          aim.x = Math.max(0, Math.min(360, aim.x + (e.code === 'ArrowLeft' ? -15 : 15)));
        }
      });
      const ball = (x, y, color, r = 17, alpha = 1) => {
        if(window.ArcadeWorldArt){ArcadeWorldArt.ball(c,x,y,color,r,alpha);return;}
        c.save();
        c.globalAlpha = alpha;
        c.fillStyle = colors[color % colors.length];
        c.beginPath();
        c.arc(x, y, r, 0, Math.PI * 2);
        c.fill();
        c.fillStyle = '#ffffff77';
        c.beginPath();
        c.arc(x - r * .3, y - r * .3, r * .2, 0, Math.PI * 2);
        c.fill();
        c.fillStyle = '#382e5466';
        c.font = '700 10px system-ui';
        c.textAlign = 'center';
        c.fillText(String(color + 1), x, y + 4);
        c.restore();
      };
      update = (w, dt = 0) => {
        world = w;
        const low = options.quality() === 'low' || matchMedia('(prefers-reduced-motion: reduce)').matches;
        c.setTransform(2, 0, 0, 2, 0, 0);
        c.fillStyle = id === 'runner' ? '#18162d' : '#19182d';
        c.fillRect(0, 0, 360, 430);
        window.ArcadeWorldArt?.backdrop(c,id,w,360,430,options.theme);
        if (id === 'runner') {
          c.strokeStyle = '#a99ad015';
          c.lineWidth = 1;
          for (let x = -(w.distance * .25 % 48); x < 360; x += 48) {
            c.beginPath();
            c.moveTo(x, 0);
            c.lineTo(x, 380);
            c.stroke();
          }
          for (let y = 26; y < 380; y += 48) {
            c.beginPath();
            c.moveTo(0, y);
            c.lineTo(360, y);
            c.stroke();
          }
          c.fillStyle = '#b6a0e922';
          for (let i = 0; i < 8; i++) {
            const x = ((i * 93 - w.distance * .15) % 750 + 750) % 750 - 50;
            c.fillRect(x, 250 - i % 3 * 35, 42, 130 + i % 3 * 35);
          }
          c.fillStyle = '#24203a';
          c.fillRect(0, 380, 360, 50);
          c.strokeStyle = '#c9ee92';
          c.lineWidth = 3;
          c.beginPath();
          c.moveTo(0, 380);
          c.lineTo(360, 380);
          c.stroke();
          if (!low && !options.readOnly) {
            trail.push({
              x: 80,
              y: w.runnerY + 13,
              age: 0
            });
            if (trail.length > 16) trail.shift();
          }
          for (const t of trail) {
            t.x -= dt * (155 + w.score * 4.5);
            t.age += dt;
            c.fillStyle = `rgba(185,161,237,${Math.max(0,.24-t.age*.7)})`;
            c.fillRect(t.x - 9, t.y - 9, 18, 18);
          }
          trail = trail.filter(t => t.age < .4);
          for (const o of w.obstacles) {
            c.fillStyle = '#eea8b0';
            c.strokeStyle = '#fff0df66';
            c.lineWidth = 2;
            const n = o.width > 40 ? 2 : 1;
            for (let i = 0; i < n; i++) {
              const x = o.x + i * o.width / n;
              c.beginPath();
              c.moveTo(x, 379);
              c.lineTo(x + o.width / n / 2, 380 - o.height);
              c.lineTo(x + o.width / n, 379);
              c.closePath();
              c.fill();
              c.stroke();
            }
          }
          c.save();
          c.translate(80, w.runnerY + 14);
          c.rotate(w.runnerAngle);
          c.shadowColor = '#b6a0ec';
          c.shadowBlur = low ? 0 : 16;
          c.fillStyle = '#b6a0ec';
          c.beginPath();
          c.roundRect(-14, -14, 28, 28, 6);
          c.fill();
          c.shadowBlur = 0;
          c.fillStyle = '#3f3459';
          c.fillRect(-7, -5, 4, 6);
          c.fillRect(5, -5, 4, 6);
          c.fillRect(-6, 5, 13, 3);
          c.restore();
          c.fillStyle = '#b5a4ce';
          c.font = '600 14px system-ui';
          c.textAlign = 'left';
          c.fillText(`${Math.floor(w.distance/10)} м`, 20, 28);
          c.textAlign = 'right';
          c.fillText(`Скорость ${Math.round(155+Math.min(160,w.score*4.5))}`, 340, 28);
        } else {
          const angle = Math.max(-1.18, Math.min(1.18, Math.atan2(aim.x - 180, 402 - Math.max(0, Math.min(370, aim.y)))));
          if (!w.projectile && !options.readOnly) {
            let x = 180,
              y = 402,
              vx = Math.sin(angle) * 7,
              vy = -Math.cos(angle) * 7;
            for (let i = 0; i < 35; i++) {
              x += vx;
              y += vy;
              if (x < 18 || x > 342) vx *= -1;
              if (i % 3 === 0) {
                c.fillStyle = '#cfbce850';
                c.beginPath();
                c.arc(x, y, 2, 0, Math.PI * 2);
                c.fill();
              }
            }
          }
          c.strokeStyle = '#e8a1b344';
          c.setLineDash([5, 6]);
          c.beginPath();
          c.moveTo(10, 335);
          c.lineTo(350, 335);
          c.stroke();
          c.setLineDash([]);
          w.bubbleBoard.forEach((v, i) => {
            if (v >= 0) {
              const p = X.bubblePoint(i);
              ball(p.x, p.y, v);
            }
          });
          if (previous && previous.tick <= w.tick && previous.seed === w.seed) previous.bubbleBoard.forEach((v, i) => {
            if (v >= 0 && w.bubbleBoard[i] < 0) {
              const p = X.bubblePoint(i);
              if (debris.length < (low ? 16 : 55)) debris.push({
                ...p,
                color: v,
                vx: (Math.random() - .5) * 130,
                vy: -80 - Math.random() * 80,
                age: 0
              });
            }
          });
          for (const b of debris) {
            b.age += dt;
            b.vy += 600 * dt;
            b.x += b.vx * dt;
            b.y += b.vy * dt;
            ball(b.x, b.y, b.color, 14, Math.max(0, 1 - b.age));
          }
          debris = debris.filter(b => b.age < 1);
          c.save();
          c.translate(180, 402);
          c.rotate(angle);
          c.fillStyle = '#827099';
          c.beginPath();
          c.roundRect(-11, -31, 22, 37, 7);
          c.fill();
          c.restore();
          window.ArcadeWorldArt?.cannon(c,angle);
          if (w.projectile) ball(w.projectile.x, w.projectile.y, w.currentBubble);
          else ball(180, 402, w.currentBubble);
          ball(322, 402, w.nextBubble, 17);
          c.fillStyle = '#9b8cae';
          c.font = '700 22px system-ui';
          c.textAlign = 'center';
          c.fillText('↗', 322, 377);
          for (let i = 0; i < 5; i++) {
            c.fillStyle = i < w.bubbleMisses ? '#e3ab9d' : '#42344f';
            c.beginPath();
            c.arc(26 + i * 15, 402, 4, 0, Math.PI * 2);
            c.fill();
          }
          previous = {
            bubbleBoard: w.bubbleBoard.slice(),
            seed: w.seed,
            tick: w.tick
          };
        }
      };
      return {
        update,
        canvas
      };
    }
    return {
      update
    };
  }
  window.ArcadeExtraArt = {
    has: X.has,
    render: art,
    bear,
    carrot
  };
  window.ArcadeExtraView = {
    has: X.has,
    mount
  };
})();
