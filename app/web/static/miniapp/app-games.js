/* Games are enabled only by the loopback preview CLI. Rewards stay in this browser. */
(() => {
  "use strict";
  if (!window.ALGO_GAMES_PROTOTYPE || !localDemoHost || !apiContext.demoMode) return;
  const E = window.AlgoGameEngine,
    $ = (s, r = document) => r.querySelector(s);
  const esc = s => String(s).replace(/[&<>"']/g, c => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  } [c]));
  let profile = "",
    data = E.blank(),
    filter = "all",
    tab = "games",
    session = null,
    storageError = false;
  const root = $("#gamesRoot"),
    symbols = ["🪨", "🌱", "🍄", "🐣", "🐱", "🦊", "🐲", "🪐", "🌞", "🌌"];
  const icon = (id) => {
    const common = '<svg viewBox="0 0 240 150" fill="none" aria-hidden="true">';
    const arts = {
      orbit: '<ellipse cx="120" cy="78" rx="84" ry="34" stroke="currentColor" stroke-width="2" stroke-dasharray="5 7" transform="rotate(-22 120 78)"/><circle cx="112" cy="83" r="34" fill="currentColor" opacity=".25"/><circle cx="112" cy="83" r="24" fill="currentColor"/><path d="m164 33 2-15 12 10 12-6 1 16q-3 19-20 15-11-3-7-20Z" fill="#fff9eb"/><path d="M173 36h1m10-1h1" stroke="#25223d" stroke-width="3" stroke-linecap="round"/><path d="m58 38 3-8 3 8 8 3-8 3-3 8-3-8-8-3Z" fill="currentColor"/>',
      evolve: '<rect x="44" y="49" width="48" height="50" rx="16" fill="currentColor" opacity=".4"/><rect x="101" y="49" width="48" height="50" rx="16" fill="currentColor" opacity=".4"/><path d="m165 55 3-18 14 12 15-12 3 18v36q-18 18-35 0Z" fill="currentColor"/><path d="M62 71h1m13 0h1m41 0h1m13 0h1m43 0h1m13 0h1" stroke="#153f36" stroke-width="4" stroke-linecap="round"/><path d="m74 118 31 6m29 0 31-6" stroke="currentColor" stroke-width="3"/>',
      bugs: '<rect x="78" y="38" width="80" height="78" rx="28" fill="currentColor"/><path d="m95 35-8-13m52 13 8-13M74 62H58m16 24H51m27 18-15 12m99-54h16m-16 24h23m-27 18 15 12" stroke="currentColor" stroke-width="6" stroke-linecap="round"/><path d="M102 63v10m31-10v10m-30 20h27" stroke="#66381f" stroke-width="6" stroke-linecap="round"/>',
      tower: '<rect x="44" y="105" width="143" height="25" rx="5" fill="currentColor" opacity=".4"/><rect x="58" y="72" width="115" height="25" rx="5" fill="currentColor" opacity=".65"/><rect x="69" y="39" width="89" height="25" rx="5" fill="currentColor"/><path d="m180 38 19-5m-17 17h22" stroke="currentColor" stroke-width="3" stroke-linecap="round"/>',
      typing: '<rect x="37" y="48" width="169" height="74" rx="15" stroke="currentColor" stroke-width="4"/><path d="M56 67h10m10 0h10m10 0h10m10 0h10m10 0h10m10 0h10m10 0h10M61 85h10m10 0h10m10 0h10m10 0h10m10 0h10m10 0h10M82 104h76" stroke="currentColor" stroke-width="6" stroke-linecap="round"/><path d="m169 16-9 16h11l-9 16" stroke="currentColor" stroke-width="3"/>',
      debug: '<rect x="47" y="25" width="146" height="107" rx="15" fill="currentColor" opacity=".15"/><path d="m88 53-17 17 17 17m64-34 17 17-17 17m-35 11 14-55" stroke="currentColor" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/><circle cx="177" cy="116" r="20" fill="currentColor"/><path d="m170 116 5 5 10-11" stroke="white" stroke-width="4" stroke-linecap="round"/>',
      '2048': '<rect x="45" y="25" width="68" height="53" rx="10" fill="currentColor" opacity=".25"/><rect x="122" y="25" width="68" height="53" rx="10" fill="currentColor" opacity=".4"/><rect x="45" y="87" width="68" height="53" rx="10" fill="currentColor" opacity=".6"/><rect x="122" y="87" width="68" height="53" rx="10" fill="currentColor"/><text x="79" y="62" text-anchor="middle" fill="#7e422c" font-size="25" font-weight="800">2</text><text x="156" y="62" text-anchor="middle" fill="#7e422c" font-size="25" font-weight="800">4</text><text x="79" y="124" text-anchor="middle" fill="#7e422c" font-size="25" font-weight="800">8</text><text x="156" y="122" text-anchor="middle" fill="white" font-size="22" font-weight="800">16</text>',
      drop: '<path d="M48 62v63q0 12 12 12h120q12 0 12-12V62" stroke="currentColor" stroke-width="3"/><circle cx="83" cy="109" r="26" fill="currentColor" opacity=".6"/><circle cx="140" cy="100" r="34" fill="currentColor"/><circle cx="115" cy="30" r="14" fill="currentColor" opacity=".5"/><path d="M115 50v13m-6-5 6 6 6-6" stroke="currentColor" stroke-width="2"/><path d="M130 94v3m20-3v3" stroke="white" stroke-width="4" stroke-linecap="round"/>',
      memory: '<rect x="47" y="32" width="69" height="90" rx="14" fill="currentColor" opacity=".4" transform="rotate(-10 47 32)"/><rect x="130" y="24" width="69" height="90" rx="14" fill="currentColor" transform="rotate(12 130 24)"/><path d="m76 65 3-11 9 7 10-4 1 12q0 17-13 15T76 65Z" fill="white"/><path d="m151 60 3-11 9 7 10-4 1 12q0 17-13 15t-10-15Z" fill="white"/>',
      react: '<circle cx="119" cy="78" r="51" stroke="currentColor" stroke-width="2" stroke-dasharray="3 7"/><path d="m125 30-28 52h24l-9 43 35-59h-26Z" fill="currentColor"/><path d="m57 29 4 6m122 77 7 4m-13-90-6 7" stroke="currentColor" stroke-width="3" stroke-linecap="round"/>',
    };
    return common + (arts[id] || arts.orbit) + '</svg>';
  };

  const target = g => g.id === "2048" ? `плитка ${g.goal}` : `${g.goal} ${g.unit}`;
  function load() {
    const key = "algo-games-prototype:v1:" + (state.activeStudentId || "preview");
    if (profile === key) return;
    profile = key;
    storageError = false;
    try {
      data = E.normalize(JSON.parse(localStorage.getItem(key) || "null"));
    } catch {
      data = E.blank();
      storageError = true;
    }
  }

  function save() {
    try {
      localStorage.setItem(profile, JSON.stringify(data));
    } catch {
      storageError = true;
    }
  }

  function refreshStored() {
    try {
      const raw = localStorage.getItem(profile);
      if (raw) data = E.normalize(JSON.parse(raw));
    } catch {
      storageError = true;
    }
  }

  function render() {
    if (!root) return;
    load();
    const w = E.week(data),
      available = E.games.filter(g => (w.scores[g.id] || 0) >= g.goal && !w.claimed[g.id]).length;
    const balance = Object.values(data.weeks).reduce((n, w) => n + Object.keys(w.claimed).length * 10, 0) +
      E.achievements.reduce((n, a) => n + (data.claimed[a.id] ? a.reward : 0), 0),
      done = E.games.filter(g => w.claimed[g.id]).length;
    const next = new Date(E.weekKey() + "T00:00:00+03:00");
    next.setTime(next.getTime() + 7 * 86400000);
    root.innerHTML = `<div class="games-heading"><div><span class="games-eyebrow">ALGO ARCADE</span><h1>Игры</h1></div><span class="games-demo">Локальный прототип</span></div>
      <section class="games-hero"><div class="games-hero-copy"><span class="games-season">СЕЗОН 01 · КОСМИЧЕСКИЙ ХАОС</span><h2>Маленький перерыв.<br><em>Большой рекорд.</em></h2><p>10 игр. Твои рекорды. Новые достижения.</p><button data-game="orbit" class="games-main">Полетели <span>↗</span></button></div><div class="games-hero-art">${icon("orbit")}<span class="games-sticker">ЕЩЁ ОДНУ<br>И ВСЁ!</span></div></section>
      <div class="games-weekbar"><div><span class="games-week-icon">✦</span><span><b>Награды недели</b><small>Обновятся ${next.toLocaleDateString("ru-RU",{timeZone:"Europe/Moscow",day:"numeric",month:"long"})} в 00:00 МСК</small></span></div><div class="games-week-pips" aria-label="Получено ${done} из 10 наград">${E.games.map(g=>`<i class="${w.claimed[g.id]?"claimed":(w.scores[g.id]||0)>=g.goal?"ready":""}"></i>`).join("")}</div><b>${done}<span> / 10</span></b><button data-games-tab="rewards">${available?`Забрать ${available*10} AC`:'Мои награды'} →</button></div>
      <nav class="games-tabs" aria-label="Игры и достижения">${[["games","Все игры"],["achievements","Достижения"],["rewards","Награды"]].map(([id,label])=>`<button data-games-tab="${id}" aria-pressed="${tab===id}" class="${tab===id?"active":""}">${label}${id==="achievements"?`<span>${Object.keys(data.unlocked).length}/${E.achievements.length}</span>`:""}</button>`).join("")}</nav>
      ${storageError?'<p class="games-warning" role="alert">Браузер не сохраняет прогресс. Не закрывай вкладку, пока проверяешь демку.</p>':""}
      ${tab==="games"?`<div class="games-filters" aria-label="Тип игры">${[["all","Все"],["fun","Залипательные"],["skill","С пользой"],["puzzle","Подумать"]].map(([id,label])=>`<button data-games-filter="${id}" aria-pressed="${filter===id}" class="${filter===id?"active":""}">${label}</button>`).join("")}</div><div class="games-grid">${E.games.filter(g=>filter==="all"||g.kind===filter).map(g=>{
        const ready=(w.scores[g.id]||0)>=g.goal;return `<button data-game="${g.id}" class="game-card ${g.color}"><div class="game-card-art">${icon(g.icon)}<span class="game-reward ${w.claimed[g.id]?"claimed":""}">${w.claimed[g.id]?"✓ Получено":ready?"✦ Награда ждёт":"✦ 10 AC"}</span></div><div class="game-card-body"><small>${g.tag}</small><h3>${g.name}</h3><div class="game-card-bottom"><span>${data.best[g.id]!==undefined?`Рекорд <b>${data.best[g.id]}</b>`:`Цель: ${target(g)}`}</span><span class="game-play" aria-hidden="true">↗</span></div></div></button>`;
      }).join("")}</div>`:""}
      ${tab==="achievements"?`<div class="games-achievement-grid">${E.achievements.map(a=>{
        const unlocked=!!data.unlocked[a.id],count=Math.min(a.target,a.metric(data));return `<article class="game-achievement ${unlocked?"unlocked":""}"><span class="achievement-medal">${unlocked?"✦":"◇"}</span><div><h3>${a.title}</h3><p>${a.detail}</p><progress value="${count}" max="${a.target}"></progress><small>${count} / ${a.target}</small></div><button data-claim="achievement" data-id="${a.id}" ${!unlocked||data.claimed[a.id]?"disabled":""}>${data.claimed[a.id]?"✓ Получено":`+${a.reward} AC`}</button></article>`;
      }).join("")}</div>`:""}
      ${tab==="rewards"?`<section class="games-reward-summary"><div><small>Тестовые астрокоины</small><strong>${balance} <span>AC</span></strong><p>Баланс ученика не меняется.</p></div><div><b>10 AC за цель в каждой игре</b><p>Один раз за неделю, с понедельника по Москве.<br>Награды за достижения — один раз за всё время.</p></div></section><div class="games-reward-list">${E.games.map(g=>{
        const score=w.scores[g.id]||0;return `<div><span class="reward-dot ${g.color}">✦</span><span><b>${g.name}</b><small>${Math.min(score,g.goal)} / ${target(g)}</small></span><button data-claim="week" data-id="${g.id}" ${score<g.goal||w.claimed[g.id]?"disabled":""}>${w.claimed[g.id]?"✓ Получено":"Забрать 10 AC"}</button></div>`;
      }).join("")}</div>${data.transactions.length?`<h3 class="games-history-title">История наград</h3><div class="games-reward-list">${data.transactions.slice(0,30).map(t=>`<div><span><b>${esc(t.label)}</b><small>${new Date(t.at).toLocaleString("ru-RU",{timeZone:"Europe/Moscow",day:"numeric",month:"long",hour:"2-digit",minute:"2-digit"})}</small></span><strong>+${t.amount} AC</strong></div>`).join("")}</div>`:""}`:""}
      <div class="games-toast" role="status" aria-live="polite"></div>`;
    root.onclick = event => {
      const b = event.target.closest("button");
      if (!b || b.disabled) return;
      if (b.dataset.game) open(b.dataset.game);
      if (b.dataset.gamesTab) {
        tab = b.dataset.gamesTab;
        render();
      }
      if (b.dataset.gamesFilter) {
        filter = b.dataset.gamesFilter;
        render();
      }
      if (b.dataset.claim) {
        refreshStored();
        const amount = E.claim(data, b.dataset.claim, b.dataset.id);
        save();
        render();
        toast(amount ? `+${amount} тестовых AC` : "Награда уже получена");
      }
    };
  }

  function toast(text) {
    const el = $(".games-toast", root);
    if (el) {
      el.textContent = text;
      el.classList.add("visible");
      setTimeout(() => el.isConnected && el.classList.remove("visible"), 2600);
    }
  }

  function close() {
    if (session) {
      session.destroy();
      session = null;
    }
    $("#gameDialog")?.remove();
  }

  function open(id) {
    close();
    load();
    const g = E.games.find(g => g.id === id);
    if (!g) return;
    const d = document.createElement("dialog");
    d.id = "gameDialog";
    d.className = "game-dialog";
    d.innerHTML =
      `<header><div><small>ALGO ARCADE</small><h2>${g.name}</h2></div><button class="game-close" aria-label="Закрыть игру">×</button></header><div class="game-hud"><span>Счёт <b id="gameScore">0</b></span><span id="gameClock"></span><span>Рекорд <b>${data.best[id]||0}</b></span></div><div class="game-stage"><div class="game-intro ${g.color}">${icon(g.icon)}<h3>${g.tag}</h3><p>${g.hint}</p><button class="games-main" id="gameStart">Начать игру →</button><small>Цель недели: ${target(g)} · 10 AC</small></div></div><footer><span id="gameHint">${["typing","debug"].includes(id)?"Короткая тренировка — большой навык":"Телефон или компьютер — играй как удобно"}</span><button id="gameFinish" hidden>Завершить</button></footer>`;
    document.body.append(d);
    d.showModal();
    $(".game-close", d).onclick = () => {
      close();
      render();
    };
    d.addEventListener("cancel", e => {
      e.preventDefault();
      close();
      render();
    });
    $("#gameStart", d).onclick = () => start(g, d);
    d.addEventListener("click", e => {
      if (e.target === d) {
        const r = d.getBoundingClientRect();
        if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) {
          close();
          render();
        }
      }
    });
  }

  function start(g, dialog) {
    const stage = $(".game-stage", dialog);
    stage.innerHTML = "";
    const abort = new AbortController();
    let raf = 0,
      last = performance.now(),
      time = 0,
      score = 0,
      done = false,
      recorded = false,
      paused = false,
      loop = () => {},
      paint = () => {};
    const on = (el, type, handler, opts = {}) => el.addEventListener(type, handler, {
      ...opts,
      signal: abort.signal
    });
    const scoreEl = $("#gameScore", dialog),
      clock = $("#gameClock", dialog),
      finishButton = $("#gameFinish", dialog);
    finishButton.hidden = false;
    const s = {
      g,
      stage,
      dialog,
      on,
      get time() {
        return time;
      },
      get score() {
        return score;
      },
      get paused() {
        return paused || done;
      },
      setScore(v) {
        score = Math.max(0, Math.floor(v));
        scoreEl.textContent = score;
      },
      add(v) {
        this.setScore(score + v);
      },
      clock(text) {
        clock.textContent = text;
      },
      hint(text) {
        $("#gameHint", dialog).textContent = text;
      },
      tick(fn) {
        loop = fn;
      },
      paint(fn) {
        paint = fn;
      },
      end(reason = "Партия завершена") {
        end(reason);
      }
    };

    function pause() {
      if (done || paused) return;
      paused = true;
      const cover = document.createElement("div");
      cover.className = "game-pause";
      cover.innerHTML = '<span>Ⅱ</span><h3>Пауза</h3><button class="games-main">Продолжить →</button>';
      stage.append(cover);
      $("button", cover).onclick = () => {
        cover.remove();
        paused = false;
        last = performance.now();
      };
    }

    function end(reason) {
      if (done) return;
      done = true;
      cancelAnimationFrame(raf);
      abort.abort();
      finishButton.hidden = true;
      refreshStored();
      const unlocked = E.finish(data, g.id, score);
      recorded = true;
      save();
      const w = E.week(data),
        eligible = (w.scores[g.id] || 0) >= g.goal && !w.claimed[g.id];
      const result = document.createElement("div");
      result.className = "game-result";
      result.innerHTML =
        `<span class="result-star">${score>=g.goal?"✦":"↗"}</span><small>${esc(reason)}</small><h3>${score} <span>${g.unit}</span></h3><p>${score>=g.goal?"Цель недели выполнена":`Цель недели: ${target(g)}`}</p>${unlocked.length?`<div class="game-new-achievement">◇ ${unlocked.map(id=>E.achievements.find(a=>a.id===id).title).join(" · ")}</div>`:""}<button class="games-main" id="gameAgain">Ещё раз ↻</button>${eligible?'<button class="game-claim-result">Забрать 10 AC</button>':""}<button class="game-back">К играм</button>`;
      stage.append(result);
      $("#gameAgain", result).onclick = () => {
        session?.destroy();
        start(g, dialog);
      };
      $(".game-back", result).onclick = () => {
        close();
        render();
      };
      $(".game-claim-result", result)?.addEventListener("click", e => {
        refreshStored();
        const amount = E.claim(data, "week", g.id);
        save();
        e.currentTarget.textContent = amount ? "✓ +10 тестовых AC" : "✓ Получено";
        e.currentTarget.disabled = true;
      });
      $("#gameAgain", result).focus();
    }
    session = {
      destroy() {
        if (!recorded && score > 0) {
          refreshStored();
          E.finish(data, g.id, score);
          recorded = true;
          save();
        }
        done = true;
        abort.abort();
        cancelAnimationFrame(raf);
      }
    };
    finishButton.onclick = () => end("Результат сохранён");
    on(document, "visibilitychange", () => {
      if (document.hidden) pause();
    });
    const init = {
      orbit: orbit,
      evolve: evolve,
      bugs: bugs,
      tower: tower,
      typing: typing,
      debug: debug,
      "2048": numberGame,
      drop: drop,
      memory: memory,
      react: react
    } [g.id];
    init(s);

    function frame(now) {
      if (done) return;
      const dt = Math.min(.04, (now - last) / 1000);
      last = now;
      if (!paused) {
        time += dt;
        loop(dt);
      }
      if (!done) paint();
      if (!done) raf = requestAnimationFrame(frame);
    }
    raf = requestAnimationFrame(frame);
  }
  const random = (a, b) => a + Math.random() * (b - a),
    pick = a => a[Math.floor(Math.random() * a.length)];

  function canvas(s) {
    const c = document.createElement("canvas");
    c.width = 720;
    c.height = 860;
    c.setAttribute("aria-label", s.g.name + ". " + s.g.hint);
    c.tabIndex = 0;
    s.stage.append(c);
    const x = c.getContext("2d");
    x.scale(2, 2);
    c.focus();
    const point = e => {
      const r = c.getBoundingClientRect(),
        scale = Math.min(r.width / 360, r.height / 430);
      return {
        x: (e.clientX - r.left - (r.width - 360 * scale) / 2) / scale,
        y: (e.clientY - r.top - (r.height - 430 * scale) / 2) / scale
      };
    };
    return {
      c,
      x,
      point
    };
  }

  function bg(x) {
    x.fillStyle = "#17182c";
    x.fillRect(0, 0, 360, 430);
    x.fillStyle = "#777790";
    for (let i = 0; i < 32; i++) {
      const a = (i * 83 + 23) % 350,
        b = (i * 59 + 31) % 420;
      x.fillRect(a, b, i % 3 ? 1 : 2, i % 3 ? 1 : 2);
    }
  }

  function text(x, t, a, b, size = 22, color = "#fff") {
    x.fillStyle = color;
    x.font = `700 ${size}px system-ui`;
    x.textAlign = "center";
    x.fillText(t, a, b);
  }

  function circle(x, a, b, r, color) {
    x.fillStyle = color;
    x.beginPath();
    x.arc(a, b, r, 0, Math.PI * 2);
    x.fill();
  }

  function action(s, c, handler) {
    s.on(c, "pointerdown", e => {
      e.preventDefault();
      if (!s.paused) handler(e);
    });
    s.on(document, "keydown", e => {
      if (["Space", "ArrowUp"].includes(e.code) && !e.repeat && !s.paused) {
        e.preventDefault();
        handler(e);
      }
    });
  }

  function orbit(s) {
    const {
      c,
      x
    } = canvas(s);
    let angle = -Math.PI / 2,
      flight = 0,
      from = {
        x: 0,
        y: 0
      },
      targetAngle = random(-2.3, -.8),
      hops = 0;
    s.hint("Тап / пробел — прыгнуть к планете");
    action(s, c, () => {
      if (flight) return;
      const delta = Math.atan2(Math.sin(angle - targetAngle), Math.cos(angle - targetAngle));
      if (Math.abs(delta) > .37) {
        s.end("Кот улетел исследовать космос");
        return;
      }
      from = {
        x: 180 + Math.cos(angle) * 69,
        y: 281 + Math.sin(angle) * 69
      };
      flight = .001;
    });
    s.tick(dt => {
      if (flight) {
        flight += dt * 2.8;
        if (flight >= 1) {
          flight = 0;
          hops++;
          s.setScore(hops);
          angle = Math.PI / 2;
          targetAngle = random(-2.5, -.65);
        }
      } else angle += dt * (1.4 + Math.min(hops, 25) * .075);
      s.clock(`${Math.floor(s.time)} с`);
    });
    s.paint(() => {
      bg(x);
      const target = {
        x: 180 + Math.cos(targetAngle) * 105,
        y: 281 + Math.sin(targetAngle) * 160
      };
      x.strokeStyle = "#c5ef78";
      x.lineWidth = 14;
      x.globalAlpha = .15;
      x.beginPath();
      x.arc(180, 281, 69, targetAngle - .37, targetAngle + .37);
      x.stroke();
      x.globalAlpha = 1;
      x.strokeStyle = "#45465e";
      x.lineWidth = 1;
      x.beginPath();
      x.arc(180, 281, 69, 0, Math.PI * 2);
      x.stroke();
      x.setLineDash([4, 7]);
      x.beginPath();
      x.moveTo(180, 281);
      x.lineTo(target.x, target.y);
      x.stroke();
      x.setLineDash([]);
      circle(x, 180, 281, 43, "#9b87f5");
      circle(x, 168, 270, 13, "#b7a6ff");
      circle(x, target.x, target.y, 28, "#bfec7f");
      circle(x, target.x - 7, target.y - 7, 8, "#d9f7ad");
      const a = flight ? from.x + (target.x - from.x) * flight : 180 + Math.cos(angle) * 69,
        b = flight ? from.y + (target.y - from.y) * flight : 281 + Math.sin(angle) * 69;
      text(x, "🐱", a, b + 10, 29);
      text(x, flight ? "Есть контакт!" : "Поймай зелёную дугу", 180, 47, 16, "#c5ef78");
    });
  }

  function evolve(s) {
    let cells = Array.from({
        length: 16
      }, () => Math.random() < .3 ? 1 : 0),
      selected = -1,
      turn = 0;
    s.stage.innerHTML =
      '<div class="evolve-game"><div class="evolve-chain">🪨 → 🌱 → 🍄 → 🐣 → 🐱 → 🦊 → 🐲</div><div class="evolve-grid"></div><p>Два одинаковых → новый зверь</p></div>';
    const grid = $(".evolve-grid", s.stage);

    function draw() {
      grid.innerHTML = cells.map((v, i) =>
        `<button data-cell="${i}" aria-label="${2**(v+1)}" aria-pressed="${i===selected}" class="${selected===i?"selected":""}"><span>${symbols[v]}</span><small>${2**(v+1)}</small></button>`
        ).join("");
    }
    s.on(grid, "click", e => {
      if (s.paused) return;
      const b = e.target.closest("[data-cell]");
      if (!b) return;
      const i = +b.dataset.cell;
      if (selected === i) {
        selected = -1;
        draw();
        return;
      }
      if (selected < 0 || cells[selected] !== cells[i]) {
        selected = i;
        draw();
        return;
      }
      cells[i]++;
      s.add(2 ** (cells[i] + 1));
      cells[selected] = Math.random() < .2 ? 1 : 0;
      selected = -1;
      turn++;
      draw();
      if (cells[i] >= 9) s.end("Открыта целая вселенная!");
      else if (!cells.some((v, i) => cells.indexOf(v) !== i)) s.end("Все звери стали разными");
    });
    draw();
    s.tick(() => s.clock(`${turn} слияний`));
  }

  function bugs(s) {
    const {
      c,
      x,
      point
    } = canvas(s);
    let targets = [],
      spawn = 0,
      life = 3;
    s.hint("Лови багов 🐛 · береги роботов 🤖");
    s.on(c, "pointerdown", e => {
      e.preventDefault();
      if (s.paused) return;
      const p = point(e),
        t = targets.findLast(t => Math.hypot(t.x - p.x, t.y - p.y) < 30);
      if (!t) return;
      targets = targets.filter(a => a !== t);
      if (t.good) {
        life--;
        if (!life) s.end("Роботы попросили перерыв");
      } else s.add(1);
    });
    s.tick(dt => {
      spawn -= dt;
      if (spawn <= 0) {
        spawn = random(.35, .7);
        targets.push({
          x: random(34, 326),
          y: random(70, 370),
          left: 1.6,
          good: Math.random() < .23
        });
      }
      targets.forEach(t => t.left -= dt);
      for (const t of targets.filter(t => t.left <= 0)) {
        if (!t.good) life--;
      }
      targets = targets.filter(t => t.left > 0);
      s.clock(`${Math.ceil(45-s.time)} с · ${"♥".repeat(Math.max(0,life))}`);
      if (life <= 0) s.end("Баги разбежались");
      else if (s.time >= 45) s.end("Охота окончена");
    });
    s.paint(() => {
      bg(x);
      for (const t of targets) {
        circle(x, t.x, t.y, 27, t.good ? "#3e6c5d" : "#65538a");
        x.strokeStyle = t.good ? "#bce98b" : "#c5afff";
        x.lineWidth = 3;
        x.beginPath();
        x.arc(t.x, t.y, 29, -Math.PI / 2, -Math.PI / 2 + t.left / 1.6 * 2 * Math.PI);
        x.stroke();
        text(x, t.good ? "🤖" : "🐛", t.x, t.y + 10, 29);
      }
      text(x, "Баги — да. Роботы — нет.", 180, 35, 15, "#b5b1ca");
    });
  }

  function tower(s) {
    const {
      c,
      x
    } = canvas(s);
    let blocks = [{
        left: 65,
        width: 230
      }],
      left = 0,
      width = 230,
      dir = 1,
      moving = true,
      flashes = 0;
    action(s, c, () => {
      if (!moving) return;
      const prev = blocks.at(-1),
        a = Math.max(left, prev.left),
        b = Math.min(left + width, prev.left + prev.width);
      if (b - a < 5) {
        s.end("Башня ушла в свободный полёт");
        return;
      }
      const perfect = Math.abs(left - prev.left) < 7;
      width = perfect ? prev.width : b - a;
      left = perfect ? prev.left : a;
      blocks.push({
        left,
        width
      });
      s.setScore(blocks.length - 1);
      flashes = perfect ? .5 : 0;
      left = dir > 0 ? 360 - width : 0;
      dir *= -1;
    });
    s.hint("Тап / пробел — поставить этаж");
    s.tick(dt => {
      left += dir * (100 + Math.min(s.score, 25) * 9) * dt;
      if (left < 0) {
        left = 0;
        dir = 1;
      }
      if (left + width > 360) {
        left = 360 - width;
        dir = -1;
      }
      flashes = Math.max(0, flashes - dt);
      s.clock(`${s.score} этажей`);
    });
    s.paint(() => {
      bg(x);
      const visible = blocks.slice(-11),
        base = 390;
      visible.forEach((b, i) => {
        x.fillStyle = `hsl(${250+i*9+s.score*8} 65% 73%)`;
        x.fillRect(b.left, base - i * 25, b.width, 21);
      });
      x.fillStyle = "#c9ed81";
      x.fillRect(left, base - visible.length * 25, width, 21);
      if (flashes) text(x, "ИДЕАЛЬНО", 180, 57, 19, "#c5ef78");
    });
  }
  const typingTexts = [
    "Космический кот нашёл на орбите пиццу. Теперь его миссия стала гораздо интереснее. ",
    "Робот умеет считать звёзды, но всё ещё путает сахар и соль. Ошибки помогают ему учиться. ",
    "Самая высокая башня начинается с одного блока. Самая крутая программа начинается с идеи. "
  ];

  function typing(s) {
    const source = pick(typingTexts) + pick(typingTexts) + pick(typingTexts);
    let mistakes = 0,
      typed = 0,
      previous = "";
    s.stage.innerHTML =
      '<div class="typing-game"><div class="typing-stats"><span id="typingAccuracy">Точность 100%</span><span id="typingSpeed">0 зн/мин</span></div><div class="typing-passage" aria-label="Текст для печати"></div><label>Печатай здесь<textarea class="typing-input" rows="3" autocomplete="off" autocapitalize="off" spellcheck="false" inputmode="text" aria-label="Введи текст по образцу"></textarea></label><small>Русская раскладка · 60 секунд</small></div>';
    const input = $("textarea", s.stage),
      passage = $(".typing-passage", s.stage);
    let committed = 0;

    function draw() {
      passage.innerHTML = [...source.slice(committed, committed + 105)].map((ch, i) =>
        `<span class="${i<input.value.length?(ch===input.value[i]?"correct":"wrong"):i===input.value.length?"cursor":""}">${esc(ch)}</span>`
        ).join("");
    }
    s.on(input, "paste", e => e.preventDefault());
    s.on(input, "drop", e => e.preventDefault());
    s.on(input, "beforeinput", e => {
      if (s.paused || e.inputType === "insertFromPaste" || e.inputType === "insertFromDrop") e
        .preventDefault();
    });
    s.on(input, "input", () => {
      const value = input.value;
      let correct = 0;
      for (let i = 0; i < value.length; i++)
        if (value[i] === source[committed + i]) correct++;
      if (value.length > previous.length) {
        for (let i = previous.length; i < value.length; i++) {
          typed++;
          if (value[i] !== source[committed + i]) mistakes++;
        }
      }
      previous = value;
      s.setScore(committed + correct);
      if (value.length >= source.slice(committed).length) {
        s.end("Весь текст напечатан");
        return;
      }
      if (value.length > 50 && value.endsWith(" ") && correct === value.length) {
        committed += value.length;
        input.value = "";
        previous = "";
      }
      draw();
    });
    s.tick(() => {
      s.clock(`${Math.ceil(60-s.time)} с`);
      $("#typingAccuracy", s.stage).textContent =
        `Точность ${typed?Math.round((typed-mistakes)/typed*100):100}%`;
      $("#typingSpeed", s.stage).textContent = `${Math.round(s.score/Math.max(1,s.time)*60)} зн/мин`;
      if (s.time >= 60) s.end("Минута пролетела");
    });
    draw();
    input.focus();
    s.hint("Пробелы тоже считаются · ошибки можно исправлять");
  }

  function debug(s) {
    let index = 0,
      line = -1,
      answered = false;
    const tasks = E.tasks.slice().sort(() => Math.random() - .5);

    function draw() {
      const t = tasks[index];
      s.stage.innerHTML =
        `<div class="debug-game"><div class="debug-progress">Задача ${index+1} / ${tasks.length}<span>PYTHON</span></div><h3>${esc(t.intro)}</h3><div class="debug-code" aria-label="Выбери ошибочную строку">${t.lines.map((text,i)=>`<button data-line="${i}" class="${line===i?"selected":""}"><span>${i+1}</span><code>${esc(text)}</code></button>`).join("")}</div><p class="debug-instruction">${line<0?"Нажми на строку с ошибкой":"Чем заменим эту строку?"}</p>${line>=0?`<div class="debug-options">${t.options.map((text,i)=>`<button data-option="${i}"><code>${esc(text.trim())}</code></button>`).join("")}</div>`:""}<div class="debug-feedback" role="status"></div></div>`;
    }
    s.on(s.stage, "click", e => {
      if (s.paused) return;
      const b = e.target.closest("button");
      if (!b) return;
      const t = tasks[index];
      if (b.dataset.line !== undefined && !answered) {
        line = +b.dataset.line;
        draw();
      }
      if (b.dataset.option !== undefined && !answered) {
        answered = true;
        const ok = line === t.line && +b.dataset.option === t.answer;
        if (ok) s.add(1);
        $(".debug-feedback", s.stage).innerHTML =
          `<b>${ok?"✓ Верно!":"Разберёмся"}</b><p>${esc(t.why)}</p><code>${esc(t.options[t.answer])}</code><button class="games-main" data-next>${index===tasks.length-1?"Результат":"Дальше →"}</button>`;
        $(".debug-options", s.stage).querySelectorAll("button").forEach(b => b.disabled = true);
        $("[data-next]", s.stage).focus();
      }
      if (b.hasAttribute("data-next")) {
        index++;
        if (index >= tasks.length) {
          s.end("Дело раскрыто");
          return;
        }
        line = -1;
        answered = false;
        draw();
      }
    });
    draw();
    s.tick(() => s.clock(`${index+1} / 8`));
    s.hint("Найди строку · выбери исправление");
  }

  function numberGame(s) {
    let board = Array(16).fill(0),
      points = 0;
    s.stage.innerHTML =
      '<div class="number-game"><div class="number-points">Очки <b>0</b></div><div class="number-grid" role="grid" aria-label="Поле 2048"></div><div class="number-controls"><button data-dir="up" aria-label="Вверх">↑</button><div><button data-dir="left" aria-label="Влево">←</button><button data-dir="down" aria-label="Вниз">↓</button><button data-dir="right" aria-label="Вправо">→</button></div></div></div>';
    const grid = $(".number-grid", s.stage);

    function add() {
      const empty = board.map((v, i) => v ? null : i).filter(v => v !== null);
      if (empty.length) board[pick(empty)] = Math.random() < .9 ? 2 : 4;
    }

    function draw() {
      grid.innerHTML = board.map(v =>
        `<div role="gridcell" class="number-cell n${Math.min(v,2048)}">${v||""}</div>`).join("");
      $(".number-points b", s.stage).textContent = points;
    }

    function move(dir) {
      if (s.paused) return;
      const r = E.slide(board, dir);
      if (!r.changed) return;
      board = r.board;
      points += r.score;
      add();
      s.setScore(Math.max(...board));
      draw();
      if (!E.canMove(board)) s.end("Ходов больше нет");
    }
    s.on(document, "keydown", e => {
      const dir = {
        ArrowLeft: "left",
        ArrowRight: "right",
        ArrowUp: "up",
        ArrowDown: "down"
      } [e.key];
      if (dir) {
        e.preventDefault();
        move(dir);
      }
    });
    let touch = null;
    s.on(grid, "pointerdown", e => {
      touch = {
        x: e.clientX,
        y: e.clientY
      };
      grid.setPointerCapture(e.pointerId);
    });
    s.on(grid, "pointerup", e => {
      if (!touch) return;
      const dx = e.clientX - touch.x,
        dy = e.clientY - touch.y;
      touch = null;
      if (Math.max(Math.abs(dx), Math.abs(dy)) > 15) move(Math.abs(dx) > Math.abs(dy) ? (dx > 0 ?
        "right" : "left") : (dy > 0 ? "down" : "up"));
    });
    s.on(s.stage, "click", e => {
      const b = e.target.closest("[data-dir]");
      if (b) move(b.dataset.dir);
    });
    add();
    add();
    draw();
    s.setScore(Math.max(...board));
    s.hint("Свайп / стрелки — сдвинуть плитки");
  }

  function drop(s) {
    const {
      c,
      x,
      point
    } = canvas(s);
    let balls = [],
      aim = 180,
      next = 0,
      cool = 0,
      danger = 0;
    const radii = [13, 18, 24, 31, 39, 48, 59, 72],
      colors = ["#b3b0ff", "#bbea7a", "#ffc27a", "#ff8a95", "#9ccfff", "#f2e48a", "#b9a0fc", "#fac27d"];

    function release() {
      if (s.paused || cool > 0) return;
      const r = radii[next];
      balls.push({
        x: Math.max(r + 12, Math.min(348 - r, aim)),
        y: 50,
        r,
        level: next,
        vx: 0,
        vy: 0,
        age: 0
      });
      next = Math.floor(random(0, 3));
      cool = .55;
    }
    s.on(c, "pointermove", e => {
      aim = point(e).x;
    });
    s.on(c, "pointerdown", e => {
      e.preventDefault();
      aim = point(e).x;
      release();
    });
    s.on(document, "keydown", e => {
      if (s.paused) return;
      if (e.code === "ArrowLeft") {
        e.preventDefault();
        aim = Math.max(30, aim - 15);
      }
      if (e.code === "ArrowRight") {
        e.preventDefault();
        aim = Math.min(330, aim + 15);
      }
      if (e.code === "Space" && !e.repeat) {
        e.preventDefault();
        release();
      }
    });

    function physics(dt) {
      cool = Math.max(0, cool - dt);
      for (const b of balls) {
        b.age += dt;
        b.vy += 520 * dt;
        b.vx *= .996;
        b.x += b.vx * dt;
        b.y += b.vy * dt;
        if (b.x - b.r < 12) {
          b.x = 12 + b.r;
          b.vx = Math.abs(b.vx) * .3;
        }
        if (b.x + b.r > 348) {
          b.x = 348 - b.r;
          b.vx = -Math.abs(b.vx) * .3;
        }
        if (b.y + b.r > 416) {
          b.y = 416 - b.r;
          b.vy = -Math.abs(b.vy) * .15;
          if (Math.abs(b.vy) < 8) b.vy = 0;
        }
      }
      let merges = 0;
      for (let pass = 0; pass < 4; pass++)
        for (let i = 0; i < balls.length; i++)
          for (let j = i + 1; j < balls.length; j++) {
            const a = balls[i],
              b = balls[j],
              dx = b.x - a.x,
              dy = b.y - a.y,
              d = Math.hypot(dx, dy),
              sum = a.r + b.r;
            if (d >= sum) continue;
            if (a.level === b.level && a.level < 7) {
              const level = a.level + 1;
              balls[i] = {
                x: (a.x + b.x) / 2,
                y: (a.y + b.y) / 2,
                r: radii[level],
                level,
                vx: (a.vx + b.vx) / 2,
                vy: -40,
                age: 0
              };
              balls.splice(j, 1);
              s.add(2 ** (level + 1));
              merges++;
              break;
            }
            const nx = d > .001 ? dx / d : 1,
              ny = d > .001 ? dy / d : 0,
              overlap = sum - Math.max(d, .001);
            a.x -= nx * overlap * .5;
            a.y -= ny * overlap * .5;
            b.x += nx * overlap * .5;
            b.y += ny * overlap * .5;
            const rel = (b.vx - a.vx) * nx + (b.vy - a.vy) * ny;
            if (rel < 0) {
              const impulse = -rel * .55;
              a.vx -= impulse * nx;
              a.vy -= impulse * ny;
              b.vx += impulse * nx;
              b.vy += impulse * ny;
            }
          }
      const tooHigh = balls.some(b => b.age > 2 && b.y - b.r < 78 && Math.abs(b.vy) < 45);
      danger = tooHigh ? danger + dt : Math.max(0, danger - dt * 2);
      if (danger > 2) s.end("Космос закончился");
    }
    s.tick(dt => {
      const steps = Math.max(1, Math.ceil(dt / .008));
      for (let i = 0; i < steps; i++) physics(dt / steps);
      s.clock(`Следующий ${symbols[next]}`);
    });
    s.paint(() => {
      bg(x);
      x.strokeStyle = danger ? "#ff8696" : "#65627c";
      x.lineWidth = 1;
      x.setLineDash([4, 5]);
      x.beginPath();
      x.moveTo(12, 78);
      x.lineTo(348, 78);
      x.stroke();
      x.setLineDash([]);
      x.strokeStyle = "#4b4962";
      x.lineWidth = 3;
      x.strokeRect(11, 79, 338, 338);
      if (cool <= 0) {
        const a = Math.max(radii[next] + 12, Math.min(348 - radii[next], aim));
        x.globalAlpha = .7;
        circle(x, a, 41, radii[next], colors[next]);
        x.globalAlpha = 1;
        x.strokeStyle = "#6c658c";
        x.setLineDash([2, 5]);
        x.beginPath();
        x.moveTo(a, 62);
        x.lineTo(a, 390);
        x.stroke();
        x.setLineDash([]);
      }
      for (const b of balls) {
        circle(x, b.x, b.y, b.r, colors[b.level]);
        text(x, symbols[b.level], b.x, b.y + b.r * .35, Math.max(16, b.r * 1.1));
      }
      if (danger) text(x, "ОСТОРОЖНО", 180, 104, 14, "#ff8696");
    });
    s.hint("Выбери место и нажми · стрелки и пробел на ПК");
  }

  function memory(s) {
    const values = ["🐱", "🪐", "🍕", "🐲", "🚀", "🍄", "⚡", "💎"],
      cards = [...values, ...values];
    for (let i = cards.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [cards[i], cards[j]] = [cards[j], cards[i]];
    }
    let opened = [],
      matched = new Set(),
      moves = 0,
      wait = 0;
    s.stage.innerHTML =
      '<div class="memory-game"><div class="memory-top">Найди пары <b id="memoryMoves">0 ходов</b></div><div class="memory-grid"></div></div>';
    const grid = $(".memory-grid", s.stage);

    function draw() {
      grid.innerHTML = cards.map((v, i) =>
        `<button data-card="${i}" class="${matched.has(i)?"matched":opened.includes(i)?"flipped":""}" ${matched.has(i)?"disabled":""} aria-label="${matched.has(i)||opened.includes(i)?v:`Карточка ${i+1}`}">${matched.has(i)||opened.includes(i)?v:"✦"}</button>`
        ).join("");
      $("#memoryMoves", s.stage).textContent = `${moves} ходов`;
    }
    s.on(grid, "click", e => {
      if (s.paused || wait > 0) return;
      const b = e.target.closest("[data-card]");
      if (!b) return;
      const i = +b.dataset.card;
      if (matched.has(i) || opened.includes(i)) return;
      opened.push(i);
      if (opened.length === 2) {
        moves++;
        if (cards[opened[0]] === cards[opened[1]]) {
          opened.forEach(i => matched.add(i));
          opened = [];
          s.setScore(matched.size / 2);
          if (matched.size === 16) {
            draw();
            s.end(`Все пары найдены за ${moves} ходов`);
            return;
          }
        } else wait = .75;
      }
      draw();
    });
    s.tick(dt => {
      if (wait > 0) {
        wait -= dt;
        if (wait <= 0) {
          opened = [];
          draw();
        }
      }
      s.clock(`${Math.ceil(90-s.time)} с`);
      if (s.time >= 90) s.end("Время вышло");
    });
    draw();
  }

  function react(s) {
    let state = "wait",
      at = random(1.2, 3.5),
      since = 0,
      hits = [],
      early = 0,
      feedback = "";
    s.stage.innerHTML =
      '<button class="reaction-pad waiting"><span class="reaction-symbol">•••</span><b>Подожди зелёный</b><small>Не нажимай заранее</small></button><div class="reaction-attempts"></div>';
    const pad = $(".reaction-pad", s.stage),
      list = $(".reaction-attempts", s.stage);

    function draw() {
      pad.className = `reaction-pad ${state}`;
      $(".reaction-symbol", pad).textContent = state === "go" ? "⚡" : state === "feedback" ? "✓" : "•••";
      $("b", pad).textContent = state === "go" ? "ЖМИ!" : state === "feedback" ? feedback :
        "Подожди зелёный";
      $("small", pad).textContent = state === "go" ? "Сейчас!" : state === "feedback" ?
        "Готовься к следующей попытке" : "Не нажимай заранее";
      list.innerHTML = Array.from({
        length: 5
      }, (_, i) => `<span class="${hits[i]?"done":""}">${hits[i]?hits[i]+" мс":i+1}</span>`).join("");
    }

    function hit() {
      if (s.paused || state === "feedback") return;
      if (state === "wait") {
        early++;
        feedback = "Рановато!";
      } else {
        const ms = Math.round((s.time - since) * 1000);
        hits.push(ms);
        s.setScore(hits.length);
        feedback = `${ms} мс`;
        if (hits.length === 5) {
          s.end(`Средняя реакция ${Math.round(hits.reduce((a,b)=>a+b,0)/5)} мс`);
          return;
        }
      }
      state = "feedback";
      at = s.time + 1.1;
      draw();
    }
    s.on(pad, "click", () => hit());
    s.on(document, "keydown", e => {
      if (e.code === "Space" && !e.repeat) {
        e.preventDefault();
        hit();
      }
    });
    s.tick(() => {
      s.clock(`${hits.length} / 5`);
      if (s.time >= at) {
        if (state === "wait") {
          state = "go";
          since = s.time;
          at = Infinity;
        } else if (state === "feedback") {
          state = "wait";
          at = s.time + random(1.2, 3.5);
        }
        draw();
      }
    });
    draw();
    s.hint("Тап / пробел · только на зелёный");
  }
  window.algoGames = {
    render,
    close
  };
  window.addEventListener("pagehide", () => session?.destroy());
  window.addEventListener("storage", event => {
    if (event.key === profile && !session) {
      refreshStored();
      render();
    }
  });
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", render, {
    once: true
  });
  else render();
})();
