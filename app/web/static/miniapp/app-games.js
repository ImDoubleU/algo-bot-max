/* Games are enabled only by the loopback preview CLI. Rewards stay in this browser. */
(() => {
  "use strict";
  if (!window.ALGO_GAMES_PROTOTYPE || !localDemoHost || !apiContext.demoMode) return;
  const E = window.AlgoGameEngine,
    M = window.AlgoGameMotion,
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
  let selectedPlayer = "",
    leaderGame = "orbit",
    leaderPeriod = "week";
  const boardKey = "algo-games-leaderboards:v2";
  try {
    selectedPlayer = localStorage.getItem("algo-games-demo-player") || "";
  } catch {}

  function players() {
    return (window.ALGO_GAME_PLAYERS?.length ? window.ALGO_GAME_PLAYERS : students)
      .filter(p => p.id && p.name);
  }

  function player() {
    return players().find(p => p.id === selectedPlayer) ||
      players().find(p => p.id === state.activeStudentId) || players()[0] || {
        id: "preview",
        name: "Игрок",
        group: "Демка"
      };
  }

  function readBoard() {
    try {
      const board = E.normalizeBoard(JSON.parse(localStorage.getItem(boardKey) || "null"));
      if (E.settleBoard(board).length) localStorage.setItem(boardKey, JSON.stringify(board));
      return board;
    } catch {
      return E.blankBoard();
    }
  }

  function writeRank(g, score, level, who, details) {
    if (!E.ranked.includes(g.id)) return;
    try {
      const board = readBoard();
      E.recordBoard(board, g.id, who, score, level, new Date(), details);
      localStorage.setItem(boardKey, JSON.stringify(board));
    } catch {
      storageError = true;
    }
  }

  function leaguePrizes(board) {
    const next = new Date(E.weekKey() + "T00:00:00+03:00");
    next.setTime(next.getTime() + 7 * 86400000);
    const past = Object.keys(board.settled).sort().at(-1),
      closed = past ? board.settled[past] : null;
    return `<div class="league-prizes"><div class="league-prize-heading"><b>Награды недели</b><small>Итоги ${next.toLocaleDateString("ru-RU",{timeZone:"Europe/Moscow",day:"numeric",month:"long"})} · 00:00 МСК</small></div><div class="league-prize-podium">${E.prizes.map((amount,i)=>`<div><span>${["🥇","🥈","🥉"][i]}</span><small>${i+1}-е место</small><b>${amount} <em>AC</em></b></div>`).join("")}</div><p>За общий топ‑3. Начисление после окончания недели.</p></div>
      ${closed?.winners.length?`<details class="league-last-week"><summary>Итоги недели ${esc(past)}</summary>${closed.winners.map(r=>`<div><span>${["🥇","🥈","🥉"][r.rank-1]} ${esc(r.name)}</span><b>+${r.amount} AC</b></div>`).join("")}</details>`:""}`;
  }

  function rankDetail(id, row) {
    if (id === "typing") return `Точность ${row.accuracy}%`;
    if (id === "debug") return `${(row.timeMs/1000).toFixed(1)} с`;
    if (id === "memory") return `${row.moves} ходов · ${(row.timeMs/1000).toFixed(0)} с`;
    if (id === "react") return `${row.reactionMs} мс · ошибок: ${row.mistakes}`;
    if (id === "2048") return row.result ? `Плитка ${row.result}` : `Уровень ${row.level}`;
    return `Уровень ${row.level}`;
  }

  function leaderMarkup(id = null) {
    const combined = !id,
      board = readBoard(),
      g = E.games.find(g => g.id === id),
      rows = combined ? E.overall(board, leaderPeriod) : E.leaders(board, id, leaderPeriod),
      mine = rows.find(r => r.player === player().id),
      shown = rows.slice(0, 20);
    if (mine && !shown.some(r => r.player === mine.player)) shown.push(mine);
    return `<section class="games-leaders ${combined?"games-overall":""}"><div class="games-leaders-top"><div><small>${combined?"ВСЕ 10 ИГР":"ТАБЛИЦА ЛИДЕРОВ"}</small><h3>${combined?"Общий рейтинг":g.name}</h3></div><span>Локальная демка</span></div>
      ${combined?leaguePrizes(board):""}
      <div class="games-leader-controls"><div class="games-leader-period">${[["week","Неделя"],["all","Всё время"]].map(([v,t])=>`<button data-leader-period="${v}" aria-pressed="${leaderPeriod===v}">${t}</button>`).join("")}</div><small>${combined?"Сумма очков за места в играх":`Лучший результат · ${E.rankUnit(id)}`}</small></div>
      ${mine?`<div class="games-my-rank"><span>Твоё место <b>#${mine.rank}</b></span><span>${mine.score.toLocaleString("ru-RU")} ${combined?"очков рейтинга":E.rankUnit(id)}<small>${combined?`${mine.games} из 10 игр`:rankDetail(id,mine)}</small></span></div>`:""}
      ${shown.length?`<div class="games-leader-scroll"><table><thead><tr><th>Место</th><th>Игрок</th><th>${combined?"Рейтинг":"Рекорд"}</th></tr></thead><tbody>${shown.map(r=>`<tr class="${r.player===player().id?"is-me":""}"><td><span class="rank-medal rank-${r.rank}">${r.rank<=3?["🥇","🥈","🥉"][r.rank-1]:r.rank}</span></td><td><b>${esc(r.name)}${r.player===player().id?' <em>Ты</em>':""}</b><small>${esc(r.group)}</small>${combined?`<details class="league-contributions"><summary>${r.games} из 10 игр</summary><ul>${r.contributions.map(c=>`<li><span>${E.games.find(g=>g.id===c.game).name} · #${c.rank}</span><strong>+${c.points}</strong></li>`).join("")}</ul></details>`:""}</td><td><strong>${r.score.toLocaleString("ru-RU")}</strong><small>${combined?`${r.wins} первых мест`:rankDetail(id,r)}</small></td></tr>`).join("")}</tbody></table></div>`:`<div class="games-leaders-empty"><span>🏆</span><h4>${combined?"Собери свой рейтинг":"Первый рекорд может быть твоим"}</h4><p>${combined?"Выполни цель недели хотя бы в одной игре.":"Заверши партию — результат появится здесь."}</p></div>`}
      ${combined?'<details class="league-rules"><summary>Как считаются очки</summary><p>В каждой игре: 100 очков за 1-е место, 80 за 2-е, 65 за 3-е; дальше 55, 45, 35, 25, 20, 15, 10 и по 5. В зачёт идут результаты с выполненной целью недели. Для печати нужна точность от 90%.</p><p>Складываются места во всех 10 играх. При равенстве: больше игр, затем первых мест, затем раньше достигнутый результат. Призы выдаются только за недельный общий рейтинг.</p></details>':'<p class="games-leader-note">Лучшая партия игрока. При равном результате учитываются точность, время или число ходов — в зависимости от игры.</p>'}
      <p class="games-leader-note">Результаты и награды этой демки хранятся в этом браузере.</p></section>`;
  }

  function wireLeaders(host, draw) {
    host.querySelectorAll("[data-leader-period]").forEach(el => el.onclick = () => {
      leaderPeriod = el.dataset.leaderPeriod;
      draw();
    });
  }

  function openLeaders(id) {
    if (id) leaderGame = id;
    session?.pause();
    $("#gamesLeaderDialog")?.remove();
    const d = document.createElement("dialog");
    d.id = "gamesLeaderDialog";
    d.className = "games-leader-dialog";
    const draw = () => {
      d.innerHTML =
        `<button class="games-leader-close" aria-label="Закрыть таблицу лидеров">×</button>${leaderMarkup(leaderGame)}`;
      $(".games-leader-close", d).onclick = () => d.close();
      wireLeaders(d, draw);
    };
    draw();
    document.body.append(d);
    d.addEventListener("close", () => d.remove());
    d.showModal();
  }
  const root = $("#gamesRoot"),
    symbols = ["🪨", "🌱", "🍄", "🐣", "🐱", "🦊", "🐲", "🪐", "🌞", "🌌"];
  const icon = id => window.AlgoGameArt.render(id);

  const target = g => g.id === "2048" ? `плитка ${g.goal}` : `${g.goal} ${g.unit}`;

  function load() {
    const key = "algo-games-prototype:v2:" + player().id;
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
    refreshStored();
    const received = E.collectPrizes(data, readBoard(), player().id);
    E.unlockAchievements(data);
    save();
    const w = E.week(data),
      available = E.games.filter(g => (w.scores[g.id] || 0) >= g.goal && !w.claimed[g.id]).length;
    const balance = E.balance(data),
      done = E.games.filter(g => w.claimed[g.id]).length;
    const next = new Date(E.weekKey() + "T00:00:00+03:00");
    next.setTime(next.getTime() + 7 * 86400000);
    root.innerHTML = `<div class="games-heading"><div><div class="games-wordmark">${icon("arcade")}<span class="games-eyebrow">ALGO ARCADE</span></div><h1>Игры</h1></div><label class="games-player-picker">Игрок демки<select id="gamesPlayer">${players().map(p=>`<option value="${esc(p.id)}" ${p.id===player().id?"selected":""}>${esc(p.name)}</option>`).join("")}</select></label></div>
      <section class="games-hero"><div class="games-hero-copy"><span class="games-season">СЕЗОН 01 · КОСМИЧЕСКИЙ ХАОС</span><h2>Маленький перерыв.<br><em>Большой рекорд.</em></h2><p>10 игр. Твои рекорды. Новые достижения.</p><button data-game="orbit" class="games-main">Полетели <span>↗</span></button></div><div class="games-hero-art">${icon("orbit")}<span class="games-sticker">ЕЩЁ ОДНУ<br>И ВСЁ!</span></div></section>
      <div class="games-weekbar"><div><span class="games-week-icon">✦</span><span><b>Награды недели</b><small>Обновятся ${next.toLocaleDateString("ru-RU",{timeZone:"Europe/Moscow",day:"numeric",month:"long"})} в 00:00 МСК</small></span></div><div class="games-week-pips" aria-label="Получено ${done} из 10 наград">${E.games.map(g=>`<i class="${w.claimed[g.id]?"claimed":(w.scores[g.id]||0)>=g.goal?"ready":""}"></i>`).join("")}</div><b>${done}<span> / 10</span></b><button data-games-tab="rewards">${available?`Забрать ${available*10} AC`:'Мои награды'} →</button></div>
      <nav class="games-tabs" aria-label="Игры и достижения">${[["games","Все игры"],["leaders","Общий рейтинг"],["achievements","Достижения"],["rewards","Награды"]].map(([id,label])=>`<button data-games-tab="${id}" aria-pressed="${tab===id}" class="${tab===id?"active":""}">${label}${id==="achievements"?`<span>${Object.keys(data.unlocked).length}/${E.achievements.length}</span>`:""}</button>`).join("")}</nav>
      ${tab==="leaders"?leaderMarkup():""}
      ${storageError?'<p class="games-warning" role="alert">Браузер не сохраняет прогресс. Не закрывай вкладку, пока проверяешь демку.</p>':""}
      ${tab==="games"?`<div class="games-filters" aria-label="Тип игры">${[["all","Все"],["fun","Залипательные"],["skill","С пользой"],["puzzle","Подумать"]].map(([id,label])=>`<button data-games-filter="${id}" aria-pressed="${filter===id}" class="${filter===id?"active":""}">${label}</button>`).join("")}</div><div class="games-grid">${E.games.filter(g=>filter==="all"||g.kind===filter).map(g=>{
        const ready=(w.scores[g.id]||0)>=g.goal;return `<div class="game-card-shell"><button data-game="${g.id}" class="game-card ${g.color}"><div class="game-card-art">${icon(g.icon)}<span class="game-reward ${w.claimed[g.id]?"claimed":""}">${w.claimed[g.id]?"✓ Получено":ready?"✦ Награда ждёт":"✦ 10 AC"}</span></div><div class="game-card-body"><small>${g.tag}</small><h3>${g.name}</h3><div class="game-card-bottom"><span>${data.best[g.id]!==undefined?`Рекорд <b>${data.best[g.id]}</b>`:`Цель: ${target(g)}`}</span><span class="game-play" aria-hidden="true">↗</span></div></div></button><button class="game-card-leader" data-game-board="${g.id}">🏆 Лидеры</button></div>`;
      }).join("")}</div>`:""}
      ${tab==="achievements"?`<div class="games-achievement-grid">${E.achievements.map(a=>{
        const unlocked=!!data.unlocked[a.id],count=Math.min(a.target,a.metric(data));return `<article class="game-achievement ${unlocked?"unlocked":""}"><span class="achievement-medal ${E.games.find(g=>g.id===a.game).color}">${icon(a.game)}<i>${unlocked?"✓":"◇"}</i></span><div><h3>${a.title}</h3><p>${a.detail}</p><progress value="${count}" max="${a.target}"></progress><small>${count} / ${a.target}</small></div><button data-claim="achievement" data-id="${a.id}" ${!unlocked||data.claimed[a.id]?"disabled":""}>${data.claimed[a.id]?"✓ Получено":`+${a.reward} AC`}</button></article>`;
      }).join("")}</div>`:""}
      ${tab==="rewards"?`<section class="games-reward-summary"><div><small>Тестовые астрокоины</small><strong>${balance} <span>AC</span></strong><p>Баланс ученика не меняется.</p></div><div><b>10 AC за цель в каждой игре</b><p>Один раз за неделю, с понедельника по Москве.<br>Награды за достижения — один раз за всё время.</p></div></section><div class="games-reward-list">${E.games.map(g=>{
        const score=w.scores[g.id]||0;return `<div><span class="reward-dot ${g.color}">✦</span><span><b>${g.name}</b><small>${Math.min(score,g.goal)} / ${target(g)}</small></span><button data-claim="week" data-id="${g.id}" ${score<g.goal||w.claimed[g.id]?"disabled":""}>${w.claimed[g.id]?"✓ Получено":"Забрать 10 AC"}</button></div>`;
      }).join("")}</div>${data.transactions.length?`<h3 class="games-history-title">История наград</h3><div class="games-reward-list">${data.transactions.slice(0,30).map(t=>`<div><span><b>${esc(t.label)}</b><small>${new Date(t.at).toLocaleString("ru-RU",{timeZone:"Europe/Moscow",day:"numeric",month:"long",hour:"2-digit",minute:"2-digit"})}</small></span><strong>+${t.amount} AC</strong></div>`).join("")}</div>`:""}`:""}
      <div class="games-toast" role="status" aria-live="polite"></div>`;
    root.onclick = event => {
      const b = event.target.closest("button");
      if (!b || b.disabled) return;
      if (b.dataset.game) open(b.dataset.game);
      if (b.dataset.gameBoard) openLeaders(b.dataset.gameBoard);
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
    $("#gamesPlayer", root).onchange = e => {
      selectedPlayer = e.target.value;
      try {
        localStorage.setItem("algo-games-demo-player", selectedPlayer);
      } catch {}
      profile = "";
      render();
    };
    if (tab === "leaders") wireLeaders(root, render);
    if (received) toast(`Награда за общий рейтинг: +${received} тестовых AC`);
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
    $("#gamesLeaderDialog")?.remove();
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
    if (E.ranked.includes(id)) {
      const b = document.createElement("button");
      b.className = "game-leaders-button";
      b.textContent = "🏆";
      b.setAttribute("aria-label", "Таблица лидеров");
      b.onclick = () => openLeaders(id);
      $("header", d).insertBefore(b, $(".game-close", d));
    }
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
    const who = {
        ...player()
      },
      sparks = new M.Sparks();
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
    let rankScore = 0,
      rankSet = false,
      highLevel = 1,
      progressHigh = 0,
      effectContext = null;
    const runDetails = {};
    const runSnapshot = () => ({
      timeMs: Math.round(time * 1000),
      ...runDetails,
      result: score
    });
    const on = (el, type, handler, opts = {}) => el.addEventListener(type, handler, {
      ...opts,
      signal: abort.signal
    });
    const scoreEl = $("#gameScore", dialog),
      clock = $("#gameClock", dialog),
      finishButton = $("#gameFinish", dialog);
    finishButton.hidden = false;
    $("#gameLevel", dialog)?.remove();
    const levelEl = document.createElement("span");
    levelEl.id = "gameLevel";
    levelEl.className = "game-level";
    levelEl.textContent = "Ур. 1";
    levelEl.setAttribute("aria-live", "polite");
    clock.after(levelEl);
    const s = {
      g,
      stage,
      dialog,
      on,
      details(values) {
        Object.assign(runDetails, values);
      },
      progress(value) {
        progressHigh = Math.max(progressHigh, value);
        const config = E.difficulty(g.id, progressHigh);
        if (config.level > highLevel) {
          highLevel = config.level;
          levelEl.textContent = `Ур. ${highLevel}`;
          M.pop(levelEl);
          const banner = document.createElement("div");
          banner.className = "game-level-up";
          banner.textContent = `Уровень ${highLevel}`;
          stage.append(banner);
          setTimeout(() => banner.remove(), 1600);
        }
        return config;
      },
      rank(value) {
        rankScore = Math.max(0, Math.floor(value));
        rankSet = true;
      },
      fx(x, y, color, count) {
        sparks.burst(x, y, color, count);
      },
      effects(ctx) {
        effectContext = ctx;
      },
      impact(strength = 3) {
        M.shake(stage, strength);
      },
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
      const unlocked = E.finish(data, g.id, score, new Date(), runSnapshot());
      writeRank(g, rankSet ? rankScore : score, highLevel, who, runSnapshot());
      recorded = true;
      save();
      const w = E.week(data),
        eligible = (w.scores[g.id] || 0) >= g.goal && !w.claimed[g.id];
      const result = document.createElement("div");
      result.className = "game-result";
      result.innerHTML =
        `<span class="result-star">${score>=g.goal?"✦":"↗"}</span><small>${esc(reason)}</small><h3>${score} <span>${g.unit}</span></h3><p>${score>=g.goal?"Цель недели выполнена":`Цель недели: ${target(g)}`}</p>${unlocked.length?`<div class="game-new-achievement">◇ ${unlocked.map(id=>E.achievements.find(a=>a.id===id).title).join(" · ")}</div>`:""}<button class="games-main" id="gameAgain">Ещё раз ↻</button>${eligible?'<button class="game-claim-result">Забрать 10 AC</button>':""}<button class="game-back">К играм</button>`;
      stage.append(result);
      if (E.ranked.includes(g.id)) {
        const b = document.createElement("button");
        b.className = "game-result-leaders";
        b.textContent = `🏆 Таблица лидеров · ${rankSet?rankScore:score} ${E.rankUnit(g.id)}`;
        b.onclick = () => openLeaders(g.id);
        $("#gameAgain", result).before(b);
      }
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
      pause,
      destroy() {
        if (!recorded && score > 0) {
          refreshStored();
          E.finish(data, g.id, score, new Date(), runSnapshot());
          writeRank(g, rankSet ? rankScore : score, highLevel, who, runSnapshot());
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
        sparks.tick(dt);
      }
      if (!done) paint();
      if (!done && effectContext) sparks.paint(effectContext);
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
    s.effects(x);
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
      baseTarget = random(-2.3, -.8),
      flightAngle = 0,
      from = {
        x: 0,
        y: 0
      },
      landed = 5,
      config = s.progress(0);
    const aim = () => baseTarget + Math.sin(s.time * .8) * config.orbitDrift;
    action(s, c, () => {
      if (flight) return;
      const delta = Math.atan2(Math.sin(angle - aim()), Math.cos(angle - aim()));
      if (Math.abs(delta) > config.orbitWindow) {
        s.impact(5);
        s.end("Кот улетел исследовать космос");
        return;
      }
      from = {
        x: 180 + Math.cos(angle) * 69,
        y: 281 + Math.sin(angle) * 69
      };
      flightAngle = aim();
      flight = .001;
    });
    s.tick(dt => {
      config = s.progress(s.score);
      landed += dt;
      if (flight) {
        flight += dt * 2.3;
        if (flight >= 1) {
          flight = 0;
          s.add(1);
          angle = Math.PI / 2;
          baseTarget = random(-2.5, -.65);
          landed = 0;
          s.fx(180, 350, "#d3f58b", 20);
        }
      } else angle += dt * config.orbitSpeed * (config.level >= 5 && Math.floor(s.score / 5) % 2 ? -1 :
        1);
      s.clock(`${Math.floor(s.time)} с`);
    });
    s.paint(() => {
      bg(x);
      const a = flight ? flightAngle : aim(),
        target = {
          x: 180 + Math.cos(a) * 105,
          y: 281 + Math.sin(a) * 160
        };
      const t = flight ? Math.min(1, flight) : 0,
        ease = t * t * (3 - 2 * t),
        cam = {
          x: (180 - target.x) * ease,
          y: (281 - target.y) * ease
        };
      x.save();
      x.translate(cam.x, cam.y);
      x.strokeStyle = "#c5ef78";
      x.lineWidth = 14;
      x.globalAlpha = .25 * (1 - ease);
      x.beginPath();
      x.arc(180, 281, 69, a - config.orbitWindow, a + config.orbitWindow);
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
      const squash = 1 + Math.sin(landed * 24) * Math.exp(-landed * 9) * .13;
      x.save();
      x.translate(180, 281);
      x.scale(1 / squash, squash);
      circle(x, 0, 0, 43, "#9b87f5");
      circle(x, -12, -11, 13, "#b7a6ff");
      x.restore();
      circle(x, target.x, target.y, 28 + 15 * ease, "#bfec7f");
      circle(x, target.x - 7, target.y - 7, 8, "#d9f7ad");
      const cx = flight ? from.x + (target.x - from.x) * ease : 180 + Math.cos(angle) * 69;
      const cy = flight ? from.y + (target.y + 69 - from.y) * ease - Math.sin(t * Math.PI) * 65 : 281 +
        Math.sin(angle) * 69;
      x.save();
      x.translate(cx, cy);
      x.rotate(flight ? Math.sin(t * Math.PI) * .65 : Math.sin(s.time * 3) * .08);
      const spring = 1 + Math.sin(landed * 22) * Math.exp(-landed * 8) * .2;
      x.scale(1 / spring, spring);
      text(x, "🐱", 0, 10, 29);
      x.restore();
      x.restore();
      text(x, flight ? "Есть контакт!" : "Поймай зелёную дугу", 180, 38, 16, "#c5ef78");
    });
    s.hint("Тап / пробел · дуга сужается, орбита ускоряется");
  }

  function evolve(s) {
    let cells = Array.from({
        length: 16
      }, () => Math.random() < .3 ? 1 : 0),
      selected = -1,
      turn = 0,
      config = s.progress(0),
      left = config.pairSeconds;
    s.stage.innerHTML =
      '<div class="evolve-game"><div class="evolve-chain">🪨 → 🌱 → 🍄 → 🐣 → 🐱 → 🦊 → 🐲</div><div class="evolve-time"><progress max="20" value="20"></progress><span></span></div><div class="evolve-grid"></div><p>Два одинаковых → новый зверь</p></div>';
    const grid = $(".evolve-grid", s.stage),
      meter = $("progress", s.stage),
      timeLabel = $(".evolve-time span", s.stage);

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
        M.pop(grid.children[i]);
        return;
      }
      const old = selected;
      cells[i] = Math.min(9, cells[i] + 1);
      s.add(2 ** (cells[i] + 1));
      cells[old] = Math.random() < .2 ? 1 : 0;
      selected = -1;
      turn++;
      config = s.progress(turn);
      left = config.pairSeconds;
      draw();
      M.pop(grid.children[i]);
      M.pop(grid.children[old]);
    });
    s.tick(dt => {
      left -= dt;
      meter.max = config.pairSeconds;
      meter.value = Math.max(0, left);
      timeLabel.textContent = `${Math.max(0,Math.ceil(left))} с на пару`;
      s.clock(`${turn} слияний`);
      if (left <= 0) s.end("Время на поиск пары вышло");
    });
    draw();
    s.hint("Каждые 8 слияний времени на пару становится меньше");
  }

  function bugs(s) {
    const {
      c,
      x,
      point
    } = canvas(s);
    let targets = [],
      spawn = 0,
      life = 3,
      config = s.progress(0);
    s.on(c, "pointerdown", e => {
      e.preventDefault();
      if (s.paused) return;
      const p = point(e),
        t = targets.slice().reverse().find(t => Math.hypot(t.x - p.x, t.y - p.y) < 30);
      if (!t) return;
      targets = targets.filter(a => a !== t);
      s.fx(t.x, t.y, t.good ? "#ff879b" : "#c3a2ff", 18);
      if (t.good) {
        life--;
        s.impact(4);
        if (!life) s.end("Роботы попросили перерыв");
      } else s.add(1);
    });
    s.tick(dt => {
      config = s.progress(s.score);
      spawn -= dt;
      if (spawn <= 0) {
        spawn = config.bugEvery * random(.85, 1.15);
        targets.push({
          x: random(35, 325),
          y: random(75, 365),
          vx: random(-1, 1) * config.bugSpeed,
          vy: random(-.6, .6) * config.bugSpeed,
          left: config.bugLife,
          total: config.bugLife,
          good: Math.random() < config.robotChance,
          phase: random(0, 6)
        });
      }
      for (const t of targets) {
        t.left -= dt;
        t.x += t.vx * dt;
        t.y += t.vy * dt;
        if (t.x < 32 || t.x > 328) t.vx *= -1;
        if (t.y < 68 || t.y > 375) t.vy *= -1;
      }
      for (const t of targets.filter(t => t.left <= 0))
        if (!t.good) {
          life--;
          s.impact(2);
        }
      targets = targets.filter(t => t.left > 0);
      s.clock(`${"♥".repeat(Math.max(0,life))} · ${Math.floor(s.time)} с`);
      if (life <= 0) s.end("Баги разбежались");
    });
    s.paint(() => {
      bg(x);
      for (const t of targets) {
        const age = t.total - t.left,
          scale = Math.min(1, age * 10) * (1 + Math.sin(age * 13) * Math.exp(-age * 6) * .18);
        x.save();
        x.translate(t.x, t.y);
        x.rotate(Math.sin(s.time * 5 + t.phase) * .15);
        x.scale(scale, scale);
        circle(x, 0, 0, 27, t.good ? "#3e6c5d" : "#65538a");
        x.strokeStyle = t.good ? "#bce98b" : "#c5afff";
        x.lineWidth = 3;
        x.beginPath();
        x.arc(0, 0, 29, -Math.PI / 2, -Math.PI / 2 + t.left / t.total * 2 * Math.PI);
        x.stroke();
        text(x, t.good ? "🤖" : "🐛", 0, 10, 29);
        x.restore();
      }
      text(x, "Баги — да. Роботы — нет.", 180, 35, 15, "#b5b1ca");
    });
    s.hint("Больше багов, выше скорость · три ошибки заканчивают партию");
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
      flashes = 0,
      debris = [],
      settle = 1,
      config = s.progress(0);
    action(s, c, () => {
      const prev = blocks.at(-1),
        a = Math.max(left, prev.left),
        b = Math.min(left + width, prev.left + prev.width);
      if (b - a < 5) {
        s.impact(5);
        s.end("Башня ушла в свободный полёт");
        return;
      }
      const perfect = Math.abs(left - prev.left) < config.perfectWindow,
        y = 390 - Math.min(11, blocks.length) * 25;
      if (!perfect) {
        const cuts = [
          [left, a],
          [b, left + width]
        ];
        for (const [from, to] of cuts)
          if (to - from > 1) debris.push({
            x: (from + to) / 2,
            y: y + 10,
            width: to - from,
            vx: from < prev.left ? -55 : 55,
            vy: -55,
            spin: from < prev.left ? -3 : 3,
            angle: 0,
            age: 0,
            color: "#b396ea"
          });
      }
      width = perfect ? prev.width : b - a;
      left = perfect ? prev.left : a;
      blocks.push({
        left,
        width
      });
      if (blocks.length > 12) blocks.shift();
      s.add(1);
      config = s.progress(s.score);
      flashes = perfect ? .5 : 0;
      settle = 0;
      if (perfect) s.fx(left + width / 2, y, "#d3f58b", 20);
      else s.impact(1.5);
      left = dir > 0 ? 360 - width : 0;
      dir *= -1;
    });
    s.tick(dt => {
      const wind = config.level >= 4 ? 1 + Math.sin(s.time * 1.9) * .2 : 1;
      left += dir * config.towerSpeed * wind * dt;
      if (left < 0) {
        left = 0;
        dir = 1;
      }
      if (left + width > 360) {
        left = 360 - width;
        dir = -1;
      }
      flashes = Math.max(0, flashes - dt);
      settle += dt;
      for (const p of debris) M.body(p, dt, 780);
      debris = debris.filter(p => p.age < 1.8 && p.y < 490);
      s.clock(`${s.score} этажей`);
    });
    s.paint(() => {
      bg(x);
      const visible = blocks.slice(-11),
        base = 390;
      visible.forEach((b, i) => {
        x.fillStyle = `hsl(${250+i*9+s.score*8} 65% 73%)`;
        const bounce = i === visible.length - 1 ? Math.sin(settle * 29) * Math.exp(-settle * 14) *
          5 : 0;
        x.fillRect(b.left, base - i * 25 + bounce, b.width, 21);
      });
      x.fillStyle = "#c9ed81";
      x.fillRect(left, base - visible.length * 25, width, 21);
      for (const p of debris) {
        x.save();
        x.globalAlpha = Math.min(1, (1.8 - p.age) * 2);
        x.translate(p.x, p.y);
        x.rotate(p.angle);
        x.fillStyle = p.color;
        x.fillRect(-p.width / 2, -10, p.width, 21);
        x.restore();
      }
      if (flashes) text(x, "ИДЕАЛЬНО", 180, 57, 19, "#c5ef78");
    });
    s.hint("Тап / пробел · блоки быстрее, точное попадание сложнее");
  }


  const typingTexts = [
    "Космический кот нашёл на орбите пиццу. Теперь его миссия стала гораздо интереснее. ",
    "Робот умеет считать звёзды, но всё ещё путает сахар и соль. Ошибки помогают ему учиться. ",
    "Самая высокая башня начинается с одного блока. Самая крутая программа начинается с идеи. "
  ];
  const typingLevels = [typingTexts,
    ["В команде 12 роботов: 7 считают звёзды, а 5 готовят пиццу. Вместе они справляются быстрее! ",
      "Новый рекорд: 128 очков за 60 секунд. Попробуешь улучшить результат ещё на 25 процентов? "
    ],
    ["Задание 3: (12 + 8) * 2 = 40. Проверь порядок действий, затем нажми Enter. ",
      'Робот сказал: "Старт!" Таймер: 00:45, точность: 98%, скорость: 240 знаков. '
    ],
    ['Пароль от шлюза: "Орбита-2048". Координаты: (17, 42), энергия: 75%, запас: 3/8. ',
      'Проверь: (144 / 12) + 7 = 19; 50% от 80 = 40. Ответ: "Всё верно!" '
    ]
  ];

  function typing(s) {
    let source = pick(typingTexts);
    let mistakes = 0,
      typed = 0,
      previous = "";
    s.stage.innerHTML =
      '<div class="typing-game"><div class="typing-stats"><span id="typingAccuracy">Точность 100%</span><span id="typingSpeed">0 зн/мин</span></div><div class="typing-passage" aria-label="Текст для печати"></div><label>Печатай здесь<textarea class="typing-input" rows="3" autocomplete="off" autocapitalize="off" spellcheck="false" inputmode="text" aria-label="Введи текст по образцу"></textarea></label><small>Русская раскладка · 60 секунд</small></div>';
    const input = $("textarea", s.stage),
      passage = $(".typing-passage", s.stage);
    let committed = 0;

    function draw() {
      while (source.length - committed < 160) {
        source += pick(typingLevels[E.difficulty("typing", source.length).level - 1]);
      }
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
      s.details({
        accuracy: typed ? Math.floor((typed - mistakes) / typed * 100) : 100
      });
      s.setScore(committed + correct);
      s.progress(s.score);
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
        `Точность ${typed?Math.floor((typed-mistakes)/typed*100):100}%`;
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
    const tasks = [
        [0, 1],
        [6, 2],
        [3, 5],
        [4, 7]
      ].flatMap(pair => Math.random() < .5 ? pair : pair.reverse())
      .map(i => E.tasks[i]);

    function draw() {
      s.progress(index);
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
      points = 0,
      config = s.progress(0),
      movingUntil = 0;
    s.stage.innerHTML =
      '<div class="number-game"><div class="number-points">Очки <b>0</b></div><div class="number-grid" role="grid" aria-label="Поле 2048"></div><div class="number-controls"><button data-dir="up" aria-label="Вверх">↑</button><div><button data-dir="left" aria-label="Влево">←</button><button data-dir="down" aria-label="Вниз">↓</button><button data-dir="right" aria-label="Вправо">→</button></div></div></div>';
    const grid = $(".number-grid", s.stage);

    function add() {
      const empty = board.map((v, i) => v ? null : i).filter(v => v !== null);
      if (empty.length) board[pick(empty)] = Math.random() < 1 - config.fourChance ? 2 : 4;
    }

    function draw() {
      grid.innerHTML = board.map(v =>
        `<div role="gridcell" class="number-cell n${Math.min(v,2048)}">${v||""}</div>`).join("");
      $(".number-points b", s.stage).textContent = points;
    }

    function move(dir) {
      if (s.paused || s.time < movingUntil) return;
      const r = E.slide(board, dir);
      if (!r.changed) return;
      const oldRects = [...grid.children].map(el => el.getBoundingClientRect());
      const oldStyles = [...grid.children].map(el => ({
        background: getComputedStyle(el).backgroundColor,
        color: getComputedStyle(el).color
      }));
      board = r.board;
      points += r.score;
      config = s.progress(Math.max(...board));
      add();
      s.setScore(Math.max(...board));
      s.rank(points);
      draw();
      if (!M.reduced()) {
        movingUntil = s.time + .17;
        const box = grid.getBoundingClientRect(),
          cells = [...grid.children],
          animations = [],
          hidden = new Set();
        for (const move of r.moves) {
          if (move.from === move.to && !move.merged) continue;
          const from = oldRects[move.from],
            to = cells[move.to].getBoundingClientRect(),
            ghost = document.createElement("div");
          ghost.className = `number-moving n${Math.min(move.value,2048)}`;
          ghost.textContent = move.value;
          ghost.setAttribute("aria-hidden", "true");
          Object.assign(ghost.style, {
            ...oldStyles[move.from],
            left: (to.left - box.left) + "px",
            top: (to.top - box.top) + "px",
            width: to.width + "px",
            height: to.height + "px"
          });
          grid.append(ghost);
          cells[move.to].style.opacity = "0";
          hidden.add(move.to);
          const animation = ghost.animate([{
            transform: `translate(${from.left-to.left}px,${from.top-to.top}px)`
          }, {
            transform: "translate(0,0)"
          }], {
            duration: 150,
            easing: "cubic-bezier(.2,.7,.3,1)"
          });
          animations.push(animation.finished.catch(() => {}).then(() => ghost.remove()));
        }
        Promise.allSettled(animations).then(() => {
          for (const i of hidden) {
            cells[i].style.opacity = "";
            if (r.moves.some(m => m.to === i && m.merged)) M.pop(cells[i]);
          }
        });
      }
      if (!E.canMove(board)) s.end("Ходов больше нет");
    }
    s.on(document, "keydown", e => {
      if (s.paused) return;
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
    s.rank(0);
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
      danger = 0,
      config = s.progress(0);
    const radii = [13, 18, 24, 31, 39, 48, 59, 72],
      colors = ["#b3b0ff", "#bbea7a", "#ffc27a", "#ff8a95", "#9ccfff", "#f2e48a", "#b9a0fc", "#fac27d"];

    function release() {
      if (s.paused || cool > 0) return;
      const r = radii[next];
      balls.push({
        x: Math.max(r + 12, Math.min(348 - r, aim)),
        y: 45,
        r,
        level: next,
        vx: 0,
        vy: 0,
        age: 0,
        angle: random(-.2, .2),
        spin: random(-.7, .7),
        squash: 0
      });
      next = Math.floor(random(0, config.dropKinds));
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
        M.body(b, dt, config.gravity);
        b.spin *= Math.exp(-.8 * dt);
        b.squash *= Math.exp(-10 * dt);
        if (b.x - b.r < 12) {
          b.x = 12 + b.r;
          b.vx = Math.abs(b.vx) * .28;
          b.spin += .15;
        }
        if (b.x + b.r > 348) {
          b.x = 348 - b.r;
          b.vx = -Math.abs(b.vx) * .28;
          b.spin -= .15;
        }
        if (b.y + b.r > 416) {
          const speed = Math.abs(b.vy);
          b.y = 416 - b.r;
          b.vy = -speed * .12;
          b.vx *= .98;
          if (speed > 50) b.squash = Math.min(.2, speed / 1300);
          if (Math.abs(b.vy) < 9) b.vy = 0;
        }
      }
      for (let pass = 0; pass < 5; pass++)
        for (let i = 0; i < balls.length; i++)
          for (let j = i + 1; j < balls.length; j++) {
            const a = balls[i],
              b = balls[j],
              dx = b.x - a.x,
              dy = b.y - a.y,
              d = Math.hypot(dx, dy),
              sum = a.r + b.r;
            if (d >= sum) continue;
            const ma = a.r * a.r,
              mb = b.r * b.r;
            if (a.level === b.level) {
              const level = Math.min(7, a.level + 1);
              balls[i] = {
                x: (a.x + b.x) / 2,
                y: (a.y + b.y) / 2,
                r: radii[level],
                level,
                vx: (a.vx * ma + b.vx * mb) / (ma + mb),
                vy: -45,
                age: 0,
                angle: 0,
                spin: (a.spin + b.spin) / 2 + .3,
                squash: .2
              };
              balls.splice(j, 1);
              s.add(2 ** (level + 1));
              s.fx(balls[i].x, balls[i].y, colors[level], 14);
              if (level >= 4) s.impact(2);
              break;
            }
            const nx = d > .001 ? dx / d : 1,
              ny = d > .001 ? dy / d : 0,
              overlap = sum - Math.max(d, .001),
              ia = 1 / ma,
              ib = 1 / mb;
            a.x -= nx * overlap * ia / (ia + ib);
            a.y -= ny * overlap * ia / (ia + ib);
            b.x += nx * overlap * ib / (ia + ib);
            b.y += ny * overlap * ib / (ia + ib);
            const rel = (b.vx - a.vx) * nx + (b.vy - a.vy) * ny;
            if (rel < 0) {
              const impulse = -rel * 1.12 / (ia + ib);
              a.vx -= impulse * nx * ia;
              a.vy -= impulse * ny * ia;
              b.vx += impulse * nx * ib;
              b.vy += impulse * ny * ib;
              const tangent = (b.vx - a.vx) * -ny + (b.vy - a.vy) * nx;
              a.spin += tangent / a.r * .01;
              b.spin -= tangent / b.r * .01;
              if (rel < -70) {
                a.squash = Math.min(.18, -rel / 1500);
                b.squash = a.squash;
              }
            }
          }
      for (const b of balls) {
        b.x = Math.max(12 + b.r, Math.min(348 - b.r, b.x));
        b.y = Math.min(416 - b.r, b.y);
      }
      const high = balls.some(b => b.age > 2 && b.y - b.r < config.dangerLine && Math.abs(b.vy) < 45);
      danger = high ? danger + dt : Math.max(0, danger - dt * 2);
      if (danger > 2.5) s.end("Космос закончился");
    }
    s.tick(dt => {
      config = s.progress(s.score);
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
      x.moveTo(12, config.dangerLine);
      x.lineTo(348, config.dangerLine);
      x.stroke();
      x.setLineDash([]);
      x.strokeStyle = "#4b4962";
      x.lineWidth = 3;
      x.strokeRect(11, 79, 338, 338);
      if (cool <= 0) {
        const a = Math.max(radii[next] + 12, Math.min(348 - radii[next], aim));
        x.globalAlpha = .7;
        circle(x, a, 38, radii[next], colors[next]);
        x.globalAlpha = 1;
        x.strokeStyle = "#6c658c";
        x.setLineDash([2, 5]);
        x.beginPath();
        x.moveTo(a, 60);
        x.lineTo(a, 390);
        x.stroke();
        x.setLineDash([]);
      }
      for (const b of balls) {
        const grow = 1 - Math.exp(-b.age * 12) * Math.cos(b.age * 20) * .2;
        x.save();
        x.translate(b.x, b.y);
        x.rotate(b.angle);
        x.scale(grow * (1 + b.squash), grow * (1 - b.squash));
        circle(x, 0, 0, b.r, colors[b.level]);
        const shine = x.createRadialGradient(-b.r * .35, -b.r * .4, 0, 0, 0, b.r);
        shine.addColorStop(0, "#ffffff50");
        shine.addColorStop(1, "#ffffff00");
        circle(x, 0, 0, b.r, shine);
        text(x, symbols[b.level], 0, b.r * .35, Math.max(16, b.r * 1.1));
        x.restore();
      }
      if (danger) text(x, "ОСТОРОЖНО", 180, config.dangerLine + 23, 14, "#ff8696");
    });
    s.hint("Выбирай место · выше уровень — сильнее гравитация и больше разных предметов");
  }

  function memory(s) {
    const values = ["🐱", "🪐", "🍕", "🐲", "🚀", "🍄", "⚡", "💎", "🦊", "🌵", "🍉", "🐙"];
    let cards = [],
      opened = [],
      matched = new Set(),
      moves = 0,
      wait = 0,
      total = 0,
      cleared = 0,
      left = 0,
      between = false,
      config = s.progress(0);
    s.stage.innerHTML =
      '<div class="memory-game"><div class="memory-top"><span id="memoryRound"></span><b id="memoryMoves">0 ходов</b></div><div class="memory-grid"></div><div class="memory-next"></div></div>';
    const grid = $(".memory-grid", s.stage),
      next = $(".memory-next", s.stage);

    function draw() {
      grid.style.gridTemplateColumns = `repeat(${config.pairs>=10?6:4},minmax(0,1fr))`;
      grid.innerHTML = cards.map((v, i) =>
        `<button data-card="${i}" class="${matched.has(i)?"matched":opened.includes(i)?"flipped":""}" ${matched.has(i)?"disabled":""} aria-label="${matched.has(i)||opened.includes(i)?v:`Карточка ${i+1}`}"><span>${matched.has(i)||opened.includes(i)?v:"✦"}</span></button>`
      ).join("");
      $("#memoryMoves", s.stage).textContent = `${moves} ходов`;
      $("#memoryRound", s.stage).textContent = `${config.pairs} пар · уровень ${config.level}`;
    }

    function round() {
      config = s.progress(cleared);
      cards = [...values.slice(0, config.pairs), ...values.slice(0, config.pairs)];
      for (let i = cards.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [cards[i], cards[j]] = [cards[j], cards[i]];
      }
      matched = new Set();
      opened = [];
      wait = 0;
      between = false;
      left = config.memorySeconds;
      next.innerHTML = "";
      draw();
    }
    s.on(grid, "click", e => {
      if (s.paused || wait > 0 || between) return;
      const b = e.target.closest("[data-card]");
      if (!b) return;
      const i = +b.dataset.card;
      if (matched.has(i) || opened.includes(i)) return;
      opened.push(i);
      let hit = [];
      if (opened.length === 2) {
        moves++;
        s.details({
          moves
        });
        if (cards[opened[0]] === cards[opened[1]]) {
          hit = opened.slice();
          opened.forEach(i => matched.add(i));
          opened = [];
          total++;
          s.setScore(total);
          if (matched.size === cards.length) {
            cleared = total;
            between = true;
            if (config.level === 5) {
              draw();
              s.end(`Все пять уровней! ${moves} ходов`);
              return;
            }
            next.innerHTML = '<button class="games-main" data-memory-next>Следующий уровень →</button>';
          }
        } else wait = Math.max(.4, .8 - config.level * .06);
      }
      draw();
      for (const j of hit) M.pop(grid.children[j]);
    });
    s.on(next, "click", e => {
      if (e.target.closest("[data-memory-next]") && !s.paused) round();
    });
    s.tick(dt => {
      if (between) {
        s.clock("Уровень пройден");
        return;
      }
      left -= dt;
      if (wait > 0) {
        wait -= dt;
        if (wait <= 0) {
          opened = [];
          draw();
        }
      }
      s.clock(`${Math.max(0,Math.ceil(left))} с`);
      if (left <= 0) s.end("Время вышло");
    });
    round();
    s.hint("Пять уровней · больше карточек, меньше времени на каждую пару");
  }

  function react(s) {
    let state = "wait",
      at = random(1.2, 3.5),
      since = 0,
      hits = [],
      misses = 0,
      feedback = "",
      config = s.progress(0);
    s.stage.innerHTML =
      '<button class="reaction-pad waiting"><span class="reaction-symbol">•••</span><b>Подожди зелёный</b><small>Не нажимай заранее</small></button><div class="reaction-attempts"></div>';
    const pad = $(".reaction-pad", s.stage),
      list = $(".reaction-attempts", s.stage);

    function draw() {
      pad.className = `reaction-pad ${state}`;
      $(".reaction-symbol", pad).textContent = state === "go" ? "⚡" : state === "feedback" ? (feedback ===
        "Рановато!" || feedback === "Не успел" ? "↻" : "✓") : "•••";
      $("b", pad).textContent = state === "go" ? "ЖМИ!" : state === "feedback" ? feedback :
        "Подожди зелёный";
      $("small", pad).textContent = state === "go" ?
        `${Math.round(config.reactionWindow*1000)} мс на ответ` : state === "feedback" ?
        "Готовься к следующей попытке" : `Ещё ${3-misses} ошибки до конца партии`;
      const start = Math.floor(Math.min(14, hits.length) / 5) * 5;
      list.innerHTML = Array.from({
          length: 5
        }, (_, i) =>
        `<span class="${hits[start+i]!==undefined?"done":""}">${hits[start+i]!==undefined?hits[start+i]+" мс":i+1}</span>`
      ).join("");
    }

    function miss(label) {
      misses++;
      s.details({
        mistakes: misses
      });
      feedback = label;
      M.shake(pad);
      if (misses >= 3) {
        s.end("Три ошибки — попробуем ещё?");
        return;
      }
      state = "feedback";
      at = s.time + .95;
      draw();
    }

    function hit() {
      if (s.paused || state === "feedback") return;
      if (state === "wait") {
        miss("Рановато!");
        return;
      }
      const ms = Math.round((s.time - since) * 1000);
      hits.push(ms);
      s.details({
        mistakes: misses,
        reactionMs: Math.round(hits.reduce((a, b) => a + b, 0) / hits.length)
      });
      s.setScore(hits.length);
      M.pop(pad);
      feedback = `${ms} мс`;
      config = s.progress(hits.length);
      if (hits.length >= 15) {
        s.end(`Средняя реакция ${Math.round(hits.reduce((a,b)=>a+b,0)/hits.length)} мс`);
        return;
      }
      state = "feedback";
      at = s.time + .95;
      draw();
    }
    s.on(pad, "click", hit);
    s.on(document, "keydown", e => {
      if (e.code === "Space" && !e.repeat && !s.paused) {
        e.preventDefault();
        hit();
      }
    });
    s.tick(() => {
      s.clock(`${hits.length} / 15 · ${"♥".repeat(Math.max(0,3-misses))}`);
      if (state === "go" && s.time - since > config.reactionWindow) {
        miss("Не успел");
        return;
      }
      if (s.time >= at) {
        if (state === "wait") {
          state = "go";
          since = s.time;
          at = Infinity;
        } else if (state === "feedback") {
          state = "wait";
          at = s.time + random(.8, 3.2);
        }
        draw();
      }
    });
    draw();
    s.hint("Три раунда · окно ответа сужается с 950 до 510 мс");
  }

  let visibleWeek = E.weekKey();
  setInterval(() => {
    if (visibleWeek !== E.weekKey() && !session) {
      visibleWeek = E.weekKey();
      if (state.view === "games") render();
    }
  }, 30000);
  window.algoGames = {
    render,
    close
  };
  window.addEventListener("pagehide", () => session?.destroy());
  window.addEventListener("storage", event => {
    if ((event.key === profile || event.key === boardKey) && !session) {
      refreshStored();
      render();
    }
  });
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", render, {
    once: true
  });
  else render();
})();
