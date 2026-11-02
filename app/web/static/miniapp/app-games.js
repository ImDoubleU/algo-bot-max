/* Local arcade client. Ranked scores, achievements, caps and prizes belong to the server. */
(() => {
    "use strict";
    if (!window.ALGO_GAMES_PROTOTYPE || !localDemoHost || !apiContext.demoMode) return;
    const E = AlgoGameEngine,
        W = ArcadeWorld,
        V = ArcadeView,
        A = AlgoGameArt,
        M = AlgoGameMotion;
    const $ = (s, r = document) => r.querySelector(s),
        root = $("#gamesRoot"),
        apiRoot = window.ALGO_ARCADE_API;
    const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
    } [c]));
    const title = id => E.games.find(g => g.id === id)?.name || id,
        art = id => A.render(id),
        speed = new Set(["orbit", "bugs", "tower", "typing", "react", "kopatych", "runner", "words"]);
    const goal = id => {
        const g = E.games.find(g => g.id === id);
        return id === "2048" ? `плитка ${g.goal}` : `${g.goal} ${g.unit}`;
    };
    const actors = window.ALGO_GAME_PLAYERS || [];
    let selected = localStorage.getItem("arcade-player-v3") || actors[0]?.id,
        profile = null,
        tab = "games",
        filter = "all",
        period = "week",
        device = matchMedia("(pointer:coarse)").matches ? "touch" : "keyboard",
        mode = "ranked",
        play = null,
        profileLoad = null,
        boardCache = new Map(),
        loadingError = "",
        uiTimer = 0,
        scrollTimer = 0,
        scrollSaved = 0,
        restoring = false,
        statsGame = "orbit";
    const actor = () => actors.find(p => p.id === selected) || actors[0];
    async function api(path, {
        method = "GET",
        body,
        admin = false,
        keepalive = false
    } = {}) {
        if (!apiRoot || !actor()?.token) throw Error("Локальный сервер игр недоступен. Перезапусти демку.");
        const token = admin ? window.pizzaPreview?.token : actor().token;
        const response = await fetch(apiRoot + path, {
            method,
            keepalive,
            headers: {
                "X-Miniapp-Token": token,
                "Content-Type": "application/json"
            },
            body: body === undefined ? undefined : JSON.stringify(body)
        });
        let value;
        try {
            value = await response.json();
        } catch {
            throw Error("Не удалось получить ответ сервера. Попробуй ещё раз.");
        }
        if (!response.ok) throw Error(typeof value.detail === "string" ? value.detail : "Не удалось выполнить действие. Попробуй ещё раз.");
        return value;
    }

    function toast(message) {
        let t = $("#arcadeToast");
        if (!t) {
            t = document.createElement("div");
            t.id = "arcadeToast";
            t.className = "games-toast";
            t.setAttribute("role", "status");
            document.body.append(t);
        }
        t.textContent = message;
        t.classList.add("visible");
        setTimeout(() => t.classList.remove("visible"), 3000);
    }
    async function loadProfile({
        restore = false
    } = {}) {
        const who = actor()?.id;
        if (!who) throw Error("Нет аккаунта для локальной демки.");
        const value = await api("/profile");
        if (who !== actor()?.id) return;
        profile = value;
        loadingError = "";
        if (restore) {
            const ui = value.settings.ui || {};
            tab = ["games", "leaders", "achievements", "looks", "progress", "rewards"].includes(ui.tab) ? ui.tab : "games";
            filter = ["all", "fun", "skill", "puzzle"].includes(ui.filter) ? ui.filter : "all";
            scrollSaved = Number(ui.scroll) || 0;
            statsGame = E.games.some(g => g.id === ui.statsGame) ? ui.statsGame : "orbit";
            period = ui.period === "all" ? "all" : "week";
            if (["keyboard", "touch"].includes(ui.device)) device = ui.device;
        }
        return value;
    }

    const uiState = () => ({
        tab,
        filter,
        scroll: Math.max(0, Math.round(scrollSaved)),
        statsGame,
        period,
        device
    });

    function saveUi() {
        clearTimeout(uiTimer);
        uiTimer = setTimeout(() => {
            if (!profile || play) return;
            const ui = uiState();
            profile.settings.ui = ui;
            api("/settings", {
                method: "PATCH",
                body: {
                    values: {
                        ui
                    }
                }
            }).catch(() => {});
        }, 180);
    }
    async function render() {
        if (!root) return;
        if (!profile) {
            root.innerHTML = '<div class="arcade-loading" role="status">Загружаем игры…</div>';
            if (!profileLoad) profileLoad = loadProfile({
                restore: true
            }).catch(e => {
                loadingError = e.message;
            }).finally(() => {
                profileLoad = null;
                draw();
            });
            return profileLoad;
        }
        draw();
    }

    function nextDeadline() {
        const d = new Date(profile.week + "T00:00:00+03:00");
        d.setUTCDate(d.getUTCDate() + 7);
        return d.toLocaleDateString("ru-RU", {
            timeZone: "Europe/Moscow",
            day: "numeric",
            month: "long"
        });
    }

    function tabs() {
        return [
            ["games", "Игры"],
            ["leaders", "Общий рейтинг"],
            ["achievements", "Достижения"],
            ["looks", "Образы"],
            ["progress", "Мой прогресс"],
            ["rewards", "Награды"]
        ].map(([id, name]) => `<button data-tab="${id}" class="${tab===id?"active":""}" aria-pressed="${tab===id}">${name}</button>`).join("");
    }

    function draw() {
        if (!profile) {
            root.innerHTML = `<div class="games-warning" role="alert">${esc(loadingError||"Нет связи с сервером игр")}<button class="arcade-subtle" data-reload>Попробовать снова</button></div>`;
            $("[data-reload]", root).onclick = () => render();
            return;
        }
        const earned = Object.values(profile.goals).filter(g => g.claimed).length;
        root.innerHTML = `<div class="games-heading"><div><div class="games-wordmark">${art("arcade")}<span class="games-eyebrow">ALGO ARCADE</span></div><h1>Игры</h1></div><div class="arcade-account"><label class="games-player-picker">Игрок демки<select id="gamesPlayer">${actors.map(p=>`<option value="${esc(p.id)}" ${p.id===actor().id?"selected":""}>${esc(p.name)}</option>`).join("")}</select></label><button class="arcade-settings" aria-label="Настройки игр" data-settings>⚙</button></div></div>
      <section class="games-hero"><div class="games-hero-copy"><span class="games-season">ALGO ARCADE · НЕДЕЛЬНОЕ ИСПЫТАНИЕ</span><h2>Твой навык.<br><em>Твой рекорд.</em></h2><p>Тренируйся, соревнуйся и открывай новые образы.</p><button data-game="orbit" class="games-main">Полетели ↗</button></div><div class="games-hero-art">${art("orbit")}</div></section>
      <div class="games-weekbar"><div><span class="games-week-icon">✦</span><span><b>Награды недели</b><small>До ${nextDeadline()} · ${profile.cap.used} / ${profile.cap.limit} AC</small></span></div><b>${earned}<span> / ${E.games.length} целей</span></b><button data-tab="rewards">Награды →</button></div>
      <nav class="games-tabs" aria-label="Разделы игр">${tabs()}</nav><div id="arcadeTabContent"></div>`;
        const content = $("#arcadeTabContent", root);
        if (tab === "games") content.innerHTML = cards();
        if (tab === "achievements") content.innerHTML = achievements();
        if (tab === "rewards") content.innerHTML = rewards();
        if (tab === "looks") content.innerHTML = looks();
        if (tab === "progress") content.innerHTML = progress();
        if (tab === "leaders") {
            content.innerHTML = '<div class="arcade-loading">Загружаем рейтинг…</div>';
            void drawBoard(content, "overall");
        }
        root.onclick = handleRoot;
        $("#gamesPlayer", root).onchange = async e => {
            selected = e.target.value;
            localStorage.setItem("arcade-player-v3", selected);
            profile = null;
            boardCache.clear();
            restoring = true;
            await render();
        };
        $("#arcadeStatsGame", root)?.addEventListener("change", e => {
            statsGame = e.target.value;
            saveUi();
            draw();
        });
        if (restoring) {
            restoring = false;
            requestAnimationFrame(() => {
                if (state.view === "games") window.scrollTo({
                    top: scrollSaved,
                    behavior: "instant"
                });
            });
        }
    }

    function cards() {
        return `<div class="games-filters">${[["all","Все"],["fun","Залипательные"],["skill","С пользой"],["puzzle","Подумать"]].map(([id,name])=>`<button data-filter="${id}" aria-pressed="${filter===id}" class="${filter===id?"active":""}">${name}</button>`).join("")}</div><div class="games-grid">${E.games.slice().sort((a,b)=>Number(!!b.fresh)-Number(!!a.fresh)).filter(g=>filter==="all"||g.kind===filter).map(g=>{
    const q=profile.goals[g.id];return `<div class="game-card-shell"><button class="game-card ${g.color}" data-game="${g.id}"><div class="game-card-art">${art(g.id)}${g.fresh?'<span class="arcade-new">НОВОЕ</span>':""}<span class="game-reward">${q.claimed?"✓ Получено":q.eligible?"✦ Забрать награду":"✦ 10 AC"}</span></div><div class="game-card-body"><small>${g.tag}</small><h3>${g.name}</h3><div class="game-card-bottom"><span>${profile.best[g.id]?`Рекорд <b>${profile.best[g.id]}</b>`:`Цель: ${goal(g.id)}`}</span><span class="game-play">↗</span></div></div></button><button class="game-card-leader" data-leader="${g.id}">🏆 Лидеры</button></div>`;
  }).join("")}</div>`;
    }

    function achievementText(a) {
        const extra = a.game === "typing" ? ` · точность ${[90,93,95][a.tier]}%` : a.game === "react" ? ` · до ${[450,400,350][a.tier]} мс, ошибок ≤ ${[1,0,0][a.tier]}` : "";
        return `${a.target} ${E.games.find(g=>g.id===a.game).unit}${extra}`;
    }

    function achievements() {
        return `<div class="arcade-tier-key"><span>Бронза · уверенный старт</span><span>Серебро · сильный результат</span><span>Золото · мастерство</span></div><div class="games-achievement-grid">${profile.achievements.map(a=>`<article class="game-achievement ${a.unlocked?"unlocked":""}"><span class="achievement-medal ${E.games.find(g=>g.id===a.game).color}">${art(a.game)}<i>${["I","II","III"][a.tier]}</i></span><div><h3>${title(a.game)} · ${["бронза","серебро","золото"][a.tier]}</h3><p>${achievementText(a)}</p><progress max="${a.target}" value="${a.value}"></progress><small>${a.value} / ${a.target}</small></div><button data-claim="${esc(a.id)}" ${!a.unlocked||a.claimed?"disabled":""}>${a.credited?"✓ Получено":a.claimed?"Ждёт лимита":`+${a.reward} AC`}</button></article>`).join("")}</div>`;
    }

    function rewards() {
        const pending = profile.awards.filter(a => a.claimed && a.credited === null);
        return `<section class="games-reward-summary"><div><small>Тестовые астрокоины</small><strong>${profile.balance} <span>AC</span></strong><p>Отдельный игровой баланс демки</p></div><div><b>Лимит недели: ${profile.cap.limit} AC</b><p>Начислено ${profile.cap.used} AC. Заработанные награды сверх лимита ждут следующей недели.</p></div></section>
      ${pending.length?`<div class="games-warning"><b>Ожидают лимита: ${pending.reduce((n,a)=>n+a.amount,0)} AC</b><p>Награды сохранены. Начисление продолжится с новой недели.</p></div>`:""}
      <div class="games-reward-list">${E.games.map(g=>{const q=profile.goals[g.id];return `<div><span class="reward-dot ${g.color}">✦</span><span><b>${g.name}</b><small>${Math.min(q.score,q.target)} / ${q.target}${g.id==="typing"?" · точность от 90%":""}</small></span><button data-claim="${esc(q.id||"")}" ${!q.eligible||q.claimed?"disabled":""}>${q.claimed?"✓ Заявлено":"Забрать 10 AC"}</button></div>`;}).join("")}</div>
      <h3 class="games-history-title">История начислений</h3><div class="games-reward-list">${profile.credits.length?profile.credits.map(c=>`<div><span><b>${esc(c.label)}</b><small>${new Date(c.created*1000).toLocaleString("ru-RU",{timeZone:"Europe/Moscow"})}</small></span><strong>+${c.amount} AC</strong></div>`).join(""):'<div><span>Пока нет начислений</span></div>'}</div>`;
    }

    function looks() {
        const unlocked = Math.max(0, ...profile.achievements.filter(a => a.unlocked).map(a => a.tier + 1));
        return `<div class="arcade-looks-intro"><h3>Образы за мастерство</h3><p>Бронза открывает мятный набор, серебро — солнечный, золото — туманность. Характеристики персонажей одинаковые.</p></div><div class="arcade-looks">${[["base","space","Космос"],["mint","forest","Мятная орбита"],["sun","sunset","Солнечный рейс"],["nebula","nebula","Туманность"]].map(([skin,theme,name],i)=>`<button class="arcade-look ${skin===profile.settings.skin?"selected":""}" data-skin="${skin}" data-theme="${theme}" ${i>unlocked?"disabled":""}><div style="filter:hue-rotate(${i*52}deg)">${art("orbit")}</div><b>${name}</b><small>${i>unlocked?`${["","Бронза","Серебро","Золото"][i]} в любой игре`:skin===profile.settings.skin?"Выбрано":"Выбрать"}</small></button>`).join("")}</div>`;
    }

    function progress() {
        const rows = profile.runs.filter(r => r.game === statsGame).slice(0, 10).reverse(),
            max = Math.max(1, ...rows.map(r => r.score));
        const pts = rows.map((r, i) => `${20+i*260/Math.max(1,rows.length-1)},${110-r.score/max*85}`).join(" ");
        return `<div class="arcade-progress-heading"><h3>Последние 10 партий</h3><select id="arcadeStatsGame">${E.games.map(g=>`<option value="${g.id}" ${statsGame===g.id?"selected":""}>${g.name}</option>`).join("")}</select></div>
      ${rows.length?`<svg class="arcade-chart" viewBox="0 0 300 135" role="img" aria-label="Результаты от ${rows[0].score} до ${rows.at(-1).score}"><path d="M20 110H280" stroke="#dcd1e9"/><polyline points="${pts}" fill="none" stroke="#9673bc" stroke-width="3" stroke-linejoin="round"/>${rows.map((r,i)=>`<circle cx="${20+i*260/Math.max(1,rows.length-1)}" cy="${110-r.score/max*85}" r="4" fill="#b1cf87"/>`).join("")}<text x="20" y="130" fill="#9b85ac" font-size="9">${rows.length} партий</text></svg>`:'<div class="games-leaders-empty"><h4>Сыграй первую партию</h4><p>Здесь появится твой прогресс.</p></div>'}
      <div class="games-reward-list">${rows.slice().reverse().map(r=>`<div><span><b>${r.score} ${E.games.find(g=>g.id===r.game).unit}</b><small>${r.mode==="practice"?"Тренировка":r.accepted?"Соревнование":"Незавершённая попытка"} · ${new Date(r.created*1000).toLocaleDateString("ru-RU")} · ${detail(r)}</small></span><button data-replay="${r.id}">Разбор →</button></div>`).join("")}</div>`;
    }

    function detail(r) {
        const d = r.report?.details || r.details || {};
        return r.game === "typing" ? `точность ${d.accuracy}%` : r.game === "react" ? `${d.reactionMs||0} мс · ошибок ${d.mistakes||0}` : r.game === "memory" ? `${d.moves||0} ходов` : `${((r.report?.timeMs||d.timeMs||0)/1000).toFixed(1)} с`;
    }
    async function handleRoot(e) {
        const b = e.target.closest("button");
        if (!b || b.disabled) return;
        if (b.dataset.tab) {
            tab = b.dataset.tab;
            scrollSaved = window.scrollY;
            saveUi();
            draw();
        }
        if (b.dataset.filter) {
            filter = b.dataset.filter;
            saveUi();
            draw();
        }
        if (b.dataset.game) openGame(b.dataset.game);
        if (b.dataset.leader) openLeaders(b.dataset.leader);
        if (b.dataset.claim) {
            b.disabled = true;
            try {
                profile = await api("/claims", {
                    method: "POST",
                    body: {
                        id: b.dataset.claim
                    }
                });
                draw();
                toast("Награда сохранена");
            } catch (error) {
                toast(error.message);
                b.disabled = false;
            }
        }
        if (b.dataset.skin) {
            try {
                profile.settings = await api("/settings", {
                    method: "PATCH",
                    body: {
                        values: {
                            skin: b.dataset.skin,
                            theme: b.dataset.theme
                        }
                    }
                });
                draw();
            } catch (error) {
                toast(error.message);
            }
        }
        if (b.hasAttribute("data-settings")) openSettings();
        if (b.dataset.replay) void replayHistory(b.dataset.replay);
    }
    async function boardData(game, chosenPeriod = period, chosenDevice = device) {
        const key = [game, chosenPeriod, chosenDevice].join(":");
        if (!boardCache.has(key)) boardCache.set(key, await api(`/boards?game=${game}&period=${chosenPeriod}&device=${chosenDevice}`));
        return boardCache.get(key);
    }

    function boardMarkup(data, game) {
        const combined = game === "overall",
            rows = data.rows,
            mine = rows.find(r => r.player === actor().id),
            shown = rows.slice(0, 20),
            index = rows.findIndex(r => r.player === actor().id);
        for (const r of rows.slice(Math.max(0, index - 2), index + 3))
            if (index >= 0 && !shown.some(s => s.player === r.player)) shown.push(r);
        const before = index > 0 ? rows[index - 1] : null,
            gap = before && mine ? before.score - mine.score + 1 : 0;
        return `<section class="games-leaders ${combined?"games-overall":""}"><div class="games-leaders-top"><div><small>${combined?`ВСЕ ${E.games.length} ИГР`:"ТАБЛИЦА ЛИДЕРОВ"}</small><h3>${combined?"Общий рейтинг":title(game)}</h3></div><span>Сервер демки</span></div>
      ${combined?`<div class="league-prizes"><div class="league-prize-heading"><b>Награды недели</b><small>Итоги ${nextDeadline()} · 00:00 МСК</small></div><div class="league-prize-podium">${data.prizes.map((n,i)=>`<div><span>${["🥇","🥈","🥉"][i]}</span><small>${i+1}-е место</small><b>${n} <em>AC</em></b></div>`).join("")}</div><p>Призовой зачёт — от 3 игр с выполненной целью. Лимит ${profile.cap.limit} AC в неделю.</p></div>`:""}
      <div class="games-leader-controls"><div class="games-leader-period">${[["week","Неделя"],["all","Всё время"]].map(([id,name])=>`<button data-period="${id}" aria-pressed="${id===period}">${name}</button>`).join("")}</div>${speed.has(game)?`<div class="games-leader-period">${[["keyboard","Клавиатура / мышь"],["touch","Касания"]].map(([id,name])=>`<button data-board-device="${id}" aria-pressed="${id===device}">${name}</button>`).join("")}</div>`:""}</div>
      ${mine?`<div class="games-my-rank"><span>Твоё место <b>#${mine.rank}</b></span><span>${mine.score} ${combined?"очков рейтинга":E.rankUnit(game)}<small>${combined?`${mine.games}/3 игр для призов`:"Лучшая партия"}</small></span></div>${before?`<p class="arcade-neighbor">До #${before.rank}: ${Math.max(1,gap)} ${combined?"очков рейтинга":E.rankUnit(game)}</p>`:""}`:""}
      ${shown.length?`<div class="games-leader-scroll"><table><thead><tr><th>Место</th><th>Игрок</th><th>${combined?"Рейтинг":"Рекорд"}</th></tr></thead><tbody>${shown.map(r=>`<tr class="${r.player===actor().id?"is-me":""}"><td><span class="rank-medal rank-${r.rank}">${r.rank<=3?["🥇","🥈","🥉"][r.rank-1]:r.rank}</span></td><td><b>${esc(r.name)}${r.player===actor().id?" <em>Ты</em>":""}</b><small>${esc(r.group)}</small>${combined?`<details class="league-contributions"><summary>${r.games} игр${r.prizeEligible?" · в призовом зачёте":" · нужно 3"}</summary><ul>${r.contributions.map(c=>`<li><span>${title(c.game)} · #${c.rank}</span><strong>+${c.points}</strong></li>`).join("")}</ul></details>`:""}</td><td><strong>${r.score}</strong><small>${combined?`${r.wins} первых мест`:`Ур. ${r.level}${speed.has(game)?r.device==="touch"?" · сенсор":" · клавиатура":""}`}</small></td></tr>`).join("")}</tbody></table></div>`:'<div class="games-leaders-empty"><span>🏆</span><h4>Первый рекорд может быть твоим</h4><p>Заверши соревновательную партию.</p></div>'}
      ${combined?'<details class="league-rules"><summary>Как считаются очки</summary><p>За места в каждой игре: 100, 80, 65, 55, 45, 35, 25, 20, 15, 10 и дальше по 5. В зачёт идут только результаты с выполненной целью. Для печати нужна точность от 90%.</p><p>В скоростных играх клавиатура и касания сравниваются отдельно. В общий рейтинг идёт один лучший вклад за игру. Призы — за минимум три разные игры. При равенстве: больше игр, первых мест, затем раньше достигнутый результат.</p></details>':""}
      ${combined&&data.history.length?`<details class="league-last-week"><summary>Прошлые недели</summary>${data.history.map(w=>`<div><b>${w.week}</b><span>${w.winners.map(r=>`${esc(r.name)} +${r.prize} AC`).join(" · ")||"Нет призового зачёта"}</span></div>`).join("")}</details>`:""}</section>`;
    }
    async function drawBoard(host, game) {
        const key = game + ":" + period + ":" + device;
        host.dataset.request = key;
        try {
            const data = await boardData(game);
            if (!host.isConnected || host.dataset.request !== key) return;
            host.innerHTML = boardMarkup(data, game);
            host.onclick = e => {
                const b = e.target.closest("button");
                if (b?.dataset.period) {
                    period = b.dataset.period;
                    saveUi();
                    void drawBoard(host, game);
                }
                if (b?.dataset.boardDevice) {
                    device = b.dataset.boardDevice;
                    saveUi();
                    void drawBoard(host, game);
                }
            };
        } catch (error) {
            host.innerHTML = `<p class="games-warning">${esc(error.message)}</p>`;
        }
    }
    async function openLeaders(game) {
        if (play?.phase === "playing") await play.pause();
        $("#gamesLeaderDialog")?.remove();
        const d = document.createElement("dialog");
        d.id = "gamesLeaderDialog";
        d.className = "games-leader-dialog";
        d.innerHTML = '<button class="games-leader-close" aria-label="Закрыть таблицу">×</button><div class="arcade-board-slot"></div>';
        document.body.append(d);
        $(".games-leader-close", d).onclick = () => d.close();
        d.onclose = () => d.remove();
        d.showModal();
        void drawBoard($(".arcade-board-slot", d), game);
    }

    function openSettings() {
        const d = document.createElement("dialog");
        d.className = "games-leader-dialog arcade-preferences";
        const p = profile.settings,
            admin = window.pizzaPreview?.role === "partner_director";
        d.innerHTML = `<button class="games-leader-close" aria-label="Закрыть">×</button><h3>Настройки игр</h3><form><label>Качество эффектов<select name="quality"><option value="auto">Автоматически</option><option value="high">Высокое</option><option value="low">Экономное</option></select></label><label class="arcade-check"><input type="checkbox" name="sound" ${p.sound?"checked":""}> Звуки</label><label class="arcade-check"><input type="checkbox" name="vibration" ${p.vibration?"checked":""}> Вибрация</label><button class="games-main">Сохранить</button><p role="status"></p></form>${admin?`<form class="arcade-policy"><h4>Лимит наград</h4><label>AC за неделю<input type="number" min="50" max="1000" name="cap" value="${profile.nextCap}"></label><small>Изменение действует со следующей недели.</small><button class="arcade-subtle">Применить</button><p role="status"></p></form>`:""}`;
        document.body.append(d);
        d.showModal();
        $("[name=quality]", d).value = p.quality;
        $(".games-leader-close", d).onclick = () => d.close();
        d.onclose = () => d.remove();
        $("form", d).onsubmit = async e => {
            e.preventDefault();
            const form = e.target;
            try {
                profile.settings = await api("/settings", {
                    method: "PATCH",
                    body: {
                        values: {
                            quality: form.quality.value,
                            sound: form.sound.checked,
                            vibration: form.vibration.checked
                        }
                    }
                });
                d.close();
            } catch (error) {
                $("[role=status]", form).textContent = error.message;
            }
        };
        $(".arcade-policy", d)?.addEventListener("submit", async e => {
            e.preventDefault();
            try {
                const result = await api("/policy", {
                    method: "PATCH",
                    body: {
                        cap: Number(e.target.cap.value)
                    },
                    admin: true
                });
                $("[role=status]", e.target).textContent = `Сохранено: ${result.cap} AC с ${result.week}`;
            } catch (error) {
                $("[role=status]", e.target).textContent = error.message;
            }
        });
    }

    function openGame(id) {
        if (play) return;
        const g = E.games.find(g => g.id === id),
            d = document.createElement("dialog");
        d.id = "gameDialog";
        d.className = "game-dialog";
        d.innerHTML = `<header><div><small>ALGO ARCADE</small><h2>${g.name}</h2></div><button class="game-leaders-button" aria-label="Таблица лидеров">🏆</button><button class="game-close" aria-label="Закрыть игру">×</button></header><div class="game-hud"><span>Счёт <b id="gameScore">0</b></span><span id="gameClock"></span><span class="game-level" id="gameLevel">Ур. 1</span><button class="arcade-pause" aria-label="Пауза" hidden>Ⅱ</button></div><div class="arcade-live-goal"><span></span><progress value="0" max="${g.goal}"></progress></div><div class="game-stage"></div><footer><span id="gameHint"></span><button id="gameFinish" hidden>Завершить</button></footer>`;
        const run = {
            g,
            dialog: d,
            phase: "intro",
            abort: new AbortController(),
            world: null,
            session: null,
            events: [],
            frames: [],
            raf: 0,
            view: null,
            playedMs: 0,
            anchor: 0,
            clockPromise: Promise.resolve(),
            inputQueue: [],
            level: 1,
            lastCue: 0,
            averageFrame: 16,
            recorded: false
        };
        play = run;
        document.body.append(d);
        d.showModal();
        intro(run);
        $(".game-close", d).onclick = () => {
            if (["playing", "ready", "paused"].includes(run.phase)) run.pause(true);
            else close();
        };
        $(".game-leaders-button", d).onclick = () => openLeaders(id);
        $(".arcade-pause", d).onclick = () => run.pause();
        d.addEventListener("cancel", e => {
            e.preventDefault();
            if (run.phase === "playing" || run.phase === "ready") run.pause();
            else if (run.phase === "paused") run.resume();
            else close();
        });
        run.pause = async exit => {
            if (run.phase !== "playing" && run.phase !== "ready") return;
            const wasReady = run.phase === "ready";
            if (!wasReady) {
                catchUp(run);
                run.playedMs += performance.now() - run.anchor;
            }
            if (run.world?.ended) return;
            run.phase = "paused";
            const cover = document.createElement("div");
            cover.className = "game-pause";
            cover.innerHTML = `<span>Ⅱ</span><h3>${exit?"Закончить попытку?":"Пауза"}</h3><button class="games-main" data-resume>Продолжить →</button><button class="game-back" data-exit>Выйти из партии</button>`;
            $(".game-stage", d).append(cover);
            if (!wasReady) run.clockPromise = run.clockPromise.then(() => api(`/sessions/${run.session.id}/clock/pause`, {
                method: "POST"
            })).catch(e => toast(e.message));
            run.resume = async () => {
                const b = $("[data-resume]", cover);
                b.disabled = true;
                await run.clockPromise;
                if (play !== run) return;
                if (!wasReady) try {
                    await api(`/sessions/${run.session.id}/clock/resume`, {
                        method: "POST"
                    });
                } catch (error) {
                    toast(error.message);
                    b.disabled = false;
                    return;
                }
                cover.remove();
                run.anchor = performance.now();
                run.phase = wasReady ? "ready" : "playing";
            };
            $("[data-resume]", cover).onclick = run.resume;
            $("[data-exit]", cover).onclick = () => finish(run, true);
        };
        $("#gameFinish", d).onclick = () => finish(run, false);

        window.addEventListener("keydown", e => {
            if (e.code !== "Escape" || [...document.querySelectorAll("dialog[open]")].at(-1) !== d) return;
            e.preventDefault();
            e.stopImmediatePropagation();
            if (run.phase === "playing" || run.phase === "ready") run.pause();
            else if (run.phase === "paused") run.resume();
            else if (!["countdown", "starting", "loading", "finishing"].includes(run.phase)) close();
        }, {
            capture: true,
            signal: run.abort.signal
        });
        document.addEventListener("visibilitychange", () => {
            if (document.hidden) run.pause();
        }, {
            signal: run.abort.signal
        });
    }

    function intro(run) {
        const {
            g,
            dialog: d
        } = run, seen = profile.settings.tutorials.includes(g.id);
        $(".game-stage", d).innerHTML = `<div class="game-intro ${g.color}">${art(g.id)}<h3>${g.tag}</h3><p>${g.hint}</p><div class="arcade-mode">${[["ranked","Соревнование"],["practice","Тренировка"]].map(([id,t])=>`<button data-mode="${id}" aria-pressed="${mode===id}">${t}</button>`).join("")}</div><div class="arcade-input">${[["keyboard","Клавиатура / мышь"],["touch","Касания"]].map(([id,t])=>`<button data-input="${id}" aria-pressed="${device===id}">${t}</button>`).join("")}</div><button class="games-main" id="gameStart">${seen?"Начать игру →":"Пробный шаг →"}</button><button class="game-back" data-skip-guide>${seen?"Как играть":"Сразу играть"}</button><small>${mode==="ranked"?"Рейтинг и награды":"Подсказки и обучение · без рейтинга"}</small></div>`;
        $("#gameHint", d).textContent = `Цель недели: ${goal(g.id)}`;
        $(".game-stage", d).onclick = e => {
            const b = e.target.closest("button");
            if (b?.dataset.mode) {
                mode = b.dataset.mode;
                intro(run);
            }
            if (b?.dataset.input) {
                device = b.dataset.input;
                intro(run);
            }
        };
        $("#gameStart", d).onclick = () => seen ? begin(run) : tutorial(run);
        $("[data-skip-guide]", d).onclick = () => seen ? tutorial(run) : begin(run);
    }

    function mount(run) {
        run.viewAbort?.abort();
        run.viewAbort = new AbortController();
        run.abort.signal.addEventListener("abort", () => run.viewAbort?.abort(), {
            once: true
        });
        const stage = $(".game-stage", run.dialog);
        stage.innerHTML = "";
        stage.onclick = null;
        run.view = V.mount(run.g.id, stage, a => input(run, a), {
            signal: run.viewAbort.signal,
            device: run.world.device,
            mode: run.world.mode,
            skin: profile.settings.skin,
            theme: profile.settings.theme,
            quality: () => run.quality || "high",
            paused: () => !["playing", "ready", "tutorial"].includes(run.phase)
        });
        run.view.update(run.world, 0);
    }
    async function tutorial(run) {
        run.phase = "tutorial";
        run.world = W.create({
            game: run.g.id,
            seed: 41,
            mode: "practice",
            device
        });
        const w = run.world;
        if (w.id === "orbit") w.target = w.angle;
        if (w.id === "bugs") w.targets = [{
            id: 1,
            x: 180,
            y: 220,
            vx: 0,
            vy: 0,
            left: 100,
            total: 100,
            good: false,
            phase: 0
        }];
        if (w.id === "tower") w.left = 65;
        if (w.id === "evolve") w.cells[0] = w.cells[1] = 0;
        if (w.id === "typing") w.text = "кот на орбите ";
        if (w.id === "2048") w.board = [2, 2, ...Array(14).fill(0)];
        if (w.id === "memory") {
            w.cards = [0, 1, 0, 1];
            w.left = 100;
        }
        if (w.id === "react") {
            w.signal = "go";
            w.since = -.2;
        }
        if (w.id === "drop") {
            w.balls = [{
                id: 1,
                x: 180,
                y: 403,
                r: 13,
                level: 0,
                vx: 0,
                vy: 0,
                age: 3,
                angle: 0,
                spin: 0,
                squash: 0
            }];
            w.queue[0] = 0;
        }
        if (window.ArcadeExtras?.has(w.id)) ArcadeExtras.tutorial(w);
        mount(run);
        $("#gameHint", run.dialog).textContent = {
            orbit: "Нажми пробел или на поле — кот прыгнет",
            evolve: "Выбери две одинаковые фигурки",
            bugs: "Нажми на фиолетового бага",
            tower: "Нажми — блок встанет на башню",
            typing: "Напечатай слово «кот»",
            debug: "Выбери ошибочную строку, затем исправление",
            "2048": "Сдвинь плитки влево",
            drop: "Урони фигурку по центру",
            memory: "Найди одинаковую пару",
            react: "Нажми на зелёный"
        } [w.id] || run.g.tutorial;
        const frame = () => {
            if (play !== run || run.phase !== "tutorial") return;
            if (run.tutorialActed && ["orbit", "drop", "bubbles"].includes(w.id)) W.advance(w, 1);
            run.view.update(w, 1 / 60);
            if (window.ArcadeExtras?.tutorialDone(w) ?? (w.score >= (w.id === "typing" ? 3 : 1))) {
                run.phase = "intro";
                const cover = document.createElement("div");
                cover.className = "game-result";
                cover.innerHTML = '<span class="result-star">✓</span><h3>Получилось!</h3><p>Теперь можно начать настоящую попытку.</p><button class="games-main">Играть →</button>';
                $(".game-stage", run.dialog).append(cover);
                profile.settings.tutorials = [...new Set([...profile.settings.tutorials, w.id])];
                api("/settings", {
                    method: "PATCH",
                    body: {
                        values: {
                            tutorials: profile.settings.tutorials
                        }
                    }
                }).catch(() => {});
                $("button", cover).onclick = () => begin(run);
                return;
            }
            run.raf = requestAnimationFrame(frame);
        };
        frame();
    }
    async function begin(run) {
        if (profile.settings.sound) {
            try {
                run.audio ||= new(window.AudioContext || window.webkitAudioContext)();
                void run.audio.resume();
            } catch {}
        }
        cancelAnimationFrame(run.raf);
        run.viewAbort?.abort();
        run.phase = "loading";
        $(".game-stage", run.dialog).innerHTML = '<div class="arcade-loading">Готовим партию…</div>';
        try {
            run.session = await api("/sessions", {
                method: "POST",
                body: {
                    game: run.g.id,
                    mode,
                    device
                }
            });
        } catch (error) {
            toast(error.message);
            intro(run);
            return;
        }
        if (play !== run) return;
        run.world = W.create(run.session.setup);
        run.mode = mode;
        run.device = device;
        run.events = [];
        run.frames = [];
        run.playedMs = 0;
        run.lastCue = 0;
        mount(run);
        $(".arcade-pause", run.dialog).hidden = false;
        $("#gameFinish", run.dialog).hidden = false;
        run.oldBest = profile.best[run.g.id] || 0;
        run.knownAchievements = new Set(profile.achievements.filter(a => a.unlocked).map(a => a.id));
        try {
            const board = await boardData(run.g.id, "week", run.device);
            run.oldRank = board.rows.find(r => r.player === actor().id)?.rank;
        } catch {}
        if (run.g.id === "typing") {
            run.phase = "ready";
            $("#gameClock", run.dialog).textContent = "Первый символ → старт";
        } else {
            run.phase = "countdown";
            const cover = document.createElement("div");
            cover.className = "game-pause arcade-countdown";
            $(".game-stage", run.dialog).append(cover);
            for (const n of [3, 2, 1]) {
                cover.innerHTML = `<b>${n}</b>`;
                await new Promise(resolve => setTimeout(resolve, 650));
                if (play !== run) return;
            }
            cover.remove();
            await startClock(run);
        }
        if (play !== run) return;
        run.raf = requestAnimationFrame(now => frame(run, now));
    }
    async function startClock(run) {
        if (run.phase === "starting") return;
        run.phase = "starting";
        try {
            await api(`/sessions/${run.session.id}/clock/start`, {
                method: "POST"
            });
        } catch (error) {
            toast(error.message);
            close();
            return;
        }
        if (play !== run) return;
        run.phase = "playing";
        run.anchor = performance.now();
        run.lastFrame = run.anchor;
        for (const action of run.inputQueue.splice(0)) apply(run, action);
    }

    function catchUp(run) {
        if (run.phase !== "playing") return;
        const target = Math.floor((run.playedMs + performance.now() - run.anchor) / 1000 * 60);
        if (target > run.world.tick) W.advance(run.world, Math.min(216000, target - run.world.tick));
    }

    function apply(run, action) {
        const event = {
            ...action,
            t: run.world.tick
        };
        run.events.push(event);
        W.input(run.world, event);
        run.view.update(run.world, 0);
    }

    function input(run, action) {
        if (play !== run) return;
        if (run.phase === "tutorial") {
            W.input(run.world, action);
            run.tutorialActed = true;
            run.view.update(run.world, 0);
            return;
        }
        if (run.phase === "ready" && action.type === "text") {
            run.inputQueue.push(action);
            void startClock(run);
            return;
        }
        if (run.phase === "starting" && action.type === "text") {
            if (run.inputQueue.length < 10) run.inputQueue.push(action);
            return;
        }
        if (run.phase !== "playing") return;
        catchUp(run);
        if (run.world.ended) {
            void finish(run, false);
            return;
        }
        apply(run, action);
        if (run.world.ended) void finish(run, false);
    }

    function frame(run, now) {
        if (play !== run || ["done", "finishing", "intro"].includes(run.phase)) return;
        const delta = Math.max(1, now - (run.lastFrame || now));
        run.lastFrame = now;
        run.averageFrame = run.averageFrame * .96 + delta * .04;
        run.quality = profile.settings.quality === "auto" ? (run.averageFrame > 26 ? "low" : "high") : profile.settings.quality;
        M.quality = run.quality;
        if (run.phase === "playing") {
            catchUp(run);
            if (run.world.ended) {
                void finish(run, false);
                return;
            }
            if (now - (run.frameSaved || 0) > 200) {
                run.frameSaved = now;
                run.frames.push(JSON.parse(JSON.stringify(run.world)));
                if (run.frames.length > 26) run.frames.shift();
            }
            for (const cue of run.world.cues.filter(c => c.n > run.lastCue)) {
                run.lastCue = cue.n;
                if (cue.type === "level") {
                    M.pop($("#gameLevel", run.dialog));
                }
                if (cue.type === "miss") M.shake($(".game-stage", run.dialog), 3);
                if (["land", "perfect", "pair", "correct", "reaction", "merge"].includes(cue.type)) feedback(run, cue.type);
            }
        }
        run.view.update(run.world, delta / 1000);
        hud(run);
        run.raf = requestAnimationFrame(t => frame(run, t));
    }

    function feedback(run, type) {
        if (profile.settings.vibration && navigator.vibrate) navigator.vibrate(type === "perfect" ? [15, 20, 15] : 12);
        if (profile.settings.sound) {
            try {
                run.audio ||= new(window.AudioContext || window.webkitAudioContext)();
                const o = run.audio.createOscillator(),
                    g = run.audio.createGain();
                o.connect(g);
                g.connect(run.audio.destination);
                o.frequency.value = type === "merge" ? 520 : 660;
                g.gain.setValueAtTime(.035, run.audio.currentTime);
                g.gain.exponentialRampToValueAtTime(.001, run.audio.currentTime + .09);
                o.start();
                o.stop(run.audio.currentTime + .1);
            } catch {}
        }
    }

    function hud(run) {
        const w = run.world,
            d = run.dialog,
            g = run.g;
        $("#gameScore", d).textContent = w.score;
        $("#gameLevel", d).textContent = `Ур. ${w.level}`;
        if (run.phase !== "ready") $("#gameClock", d).textContent = (g.seconds || w.id === "typing") ? `${Math.max(0,Math.ceil((g.seconds||60)-w.time))} с` : w.id === "memory" && !w.between ? `${Math.max(0,Math.ceil(w.left))} с` : w.id === "debug" ? `${Math.min(8,w.index+1)} / 8` : `${Math.floor(w.time)} с`;
        const q = profile.goals[g.id],
            next = profile.achievements.filter(a => a.game === g.id && !a.unlocked).sort((a, b) => a.tier - b.tier)[0],
            target = q.claimed && next ? next.target : g.goal;
        $(".arcade-live-goal progress", d).max = target;
        $(".arcade-live-goal progress", d).value = Math.min(target, w.score);
        $(".arcade-live-goal span", d).textContent = w.id === "typing" && w.score >= target && w.details.accuracy < 90 ? `Точность ${w.details.accuracy}% · нужно 90%` : w.score >= target ? "Цель достигнута" : `До ${run.mode==="practice"?"цели":q.claimed?"достижения":"награды"}: ${target-w.score} ${g.unit}`;
    }
    async function finish(run, abandoned) {
        if (play !== run || ["finishing", "done"].includes(run.phase)) return;
        if (!run.session) {
            close();
            return;
        }
        if (run.phase === "ready") {
            close();
            return;
        }
        if (run.phase === "playing") {
            catchUp(run);
            run.playedMs += performance.now() - run.anchor;
        }
        run.frames.push(JSON.parse(JSON.stringify(run.world)));
        if (run.frames.length > 26) run.frames.shift();
        run.phase = "finishing";
        cancelAnimationFrame(run.raf);
        $(".arcade-pause", run.dialog).hidden = true;
        $("#gameFinish", run.dialog).hidden = true;
        $(".game-pause", run.dialog)?.remove();
        const stage = $(".game-stage", run.dialog),
            cover = document.createElement("div");
        cover.className = "game-result";
        cover.innerHTML = '<div class="arcade-loading">Проверяем результат партии…</div>';
        stage.append(cover);
        try {
            await run.clockPromise;
            const result = await api(`/sessions/${run.session.id}/finish`, {
                method: "POST",
                body: {
                    actions: run.events,
                    ticks: run.world.tick,
                    abandoned
                }
            });
            run.recorded = true;
            run.record = result.run;
            boardCache.clear();
            await loadProfile();
            if (play !== run) return;
            run.phase = "done";
            const report = result.run.report || W.report(run.world),
                q = profile.goals[run.g.id],
                newBadges = profile.achievements.filter(a => a.unlocked && !run.knownAchievements.has(a.id));
            const record = report.score > run.oldBest,
                board = await boardData(run.g.id, "week", run.device),
                rank = board.rows.find(r => r.player === actor().id)?.rank;
            cover.innerHTML = `<span class="result-star">${result.run.accepted?"✦":"↗"}</span><small>${abandoned?"Попытка завершена":report.reason||"Результат сохранён"}</small><h3>${report.score} <span>${run.g.unit}</span></h3><p>${run.mode==="practice"?"Тренировка сохранена":result.run.accepted?"Результат подтверждён сервером":"Попытка сохранена без рейтинга"}</p>${record&&result.run.accepted?`<div class="game-new-achievement">Новый рекорд · +${report.score-run.oldBest}</div>`:""}${rank&&result.run.accepted?`<div class="arcade-result-rank">Место #${rank}${run.oldRank&&run.oldRank!==rank?` · было #${run.oldRank}`:""}</div>`:""}${newBadges.length?`<div class="game-new-achievement">Открыто достижений: ${newBadges.length}</div>`:""}<button class="games-main" data-again>Ещё раз ↻</button>${q.eligible&&!q.claimed?'<button class="game-claim-result" data-claim-result>Забрать 10 AC</button>':""}<button class="game-result-leaders" data-result-board>🏆 Лидеры</button><button class="game-back" data-analysis>Разбор партии</button><button class="game-back" data-back>К играм</button>`;
            $("[data-again]", cover).onclick = () => {
                const g = run.g.id;
                close();
                openGame(g);
            };
            $("[data-back]", cover).onclick = () => {
                close();
                draw();
            };
            $("[data-result-board]", cover).onclick = () => openLeaders(run.g.id);
            $("[data-analysis]", cover).onclick = () => run.frames.length ? showReplay(run.g.id, run.frames, report) : replayHistory(result.run.id);
            $("[data-claim-result]", cover)?.addEventListener("click", async e => {
                e.currentTarget.disabled = true;
                try {
                    profile = await api("/claims", {
                        method: "POST",
                        body: {
                            id: q.id
                        }
                    });
                    e.target.textContent = "✓ Награда сохранена";
                } catch (error) {
                    toast(error.message);
                    e.target.disabled = false;
                }
            });
        } catch (error) {
            run.phase = "done";
            cover.innerHTML = `<h3>Не удалось сохранить</h3><p>${esc(error.message)}</p><button class="games-main" data-retry>Повторить отправку</button><button class="game-back" data-close>К играм</button>`;
            $("[data-retry]", cover).onclick = () => {
                cover.remove();
                run.phase = "paused";
                finish(run, abandoned);
            };
            $("[data-close]", cover).onclick = () => {
                close();
                draw();
            };
        }
    }
    async function replayHistory(id) {
        try {
            const saved = await api("/replay/" + id),
                w = W.create(saved.setup),
                frames = [];
            let cursor = 0;
            while (w.tick < saved.ticks && !w.ended) {
                while (cursor < saved.actions.length && saved.actions[cursor].t === w.tick) W.input(w, saved.actions[cursor++]);
                W.advance(w, 1);
                if (w.tick >= saved.ticks - 300 && w.tick % 12 === 0) frames.push(JSON.parse(JSON.stringify(w)));
            }
            while (cursor < saved.actions.length && saved.actions[cursor].t === w.tick && !w.ended) W.input(w, saved.actions[cursor++]);
            frames.push(JSON.parse(JSON.stringify(w)));
            showReplay(saved.setup.game, frames, W.report(w));
        } catch (error) {
            toast(error.message);
        }
    }

    function showReplay(game, frames, report) {
        const d = document.createElement("dialog");
        d.className = "game-dialog arcade-replay";
        d.innerHTML = `<header><div><small>РАЗБОР</small><h2>${title(game)}</h2></div><button class="game-close" aria-label="Закрыть разбор">×</button></header><div class="game-stage"></div><footer><span>${esc(report.reason||"Последние секунды партии")}</span></footer>`;
        document.body.append(d);
        d.showModal();
        const abort = new AbortController();
        const view = V.mount(game, $(".game-stage", d), () => {}, {
            signal: abort.signal,
            mode: "practice",
            device,
            readOnly: true,
            paused: () => true,
            theme: profile.settings.theme,
            skin: profile.settings.skin,
            quality: () => "high"
        });
        let index = 0,
            last = 0,
            raf = 0;
        const frame = now => {
            if (now - last >= 200) {
                last = now;
                view.update(frames[Math.min(index++, frames.length - 1)], .2);
            }
            if (index < frames.length) raf = requestAnimationFrame(frame);
        };
        if (frames.length) raf = requestAnimationFrame(frame);
        $(".game-close", d).onclick = () => d.close();
        d.onclose = () => {
            cancelAnimationFrame(raf);
            abort.abort();
            d.remove();
        };
    }

    function close() {
        if (play) {
            cancelAnimationFrame(play.raf);
            play.abort.abort();
            play.audio?.close();
            play.dialog.remove();
            play = null;
        }
        $("#gamesLeaderDialog")?.remove();
    }
    window.addEventListener("scroll", () => {
        if (state.view !== "games" || play) return;
        clearTimeout(scrollTimer);
        scrollTimer = setTimeout(() => {
            scrollSaved = window.scrollY;
            saveUi();
        }, 300);
    }, {
        passive: true
    });
    window.addEventListener("pagehide", () => {
        if (profile) {
            clearTimeout(uiTimer);
            api("/settings", {
                method: "PATCH",
                keepalive: true,
                body: {
                    values: {
                        ui: uiState()
                    }
                }
            }).catch(() => {});
        }
        if (play?.session && !play.recorded && ["playing", "paused"].includes(play.phase)) {
            if (play.phase === "playing") catchUp(play);
            api(`/sessions/${play.session.id}/finish`, {
                method: "POST",
                keepalive: true,
                body: {
                    actions: play.events,
                    ticks: play.world.tick,
                    abandoned: true
                }
            }).catch(() => {});
        }
        close();
    });
    setInterval(() => {
        if (state.view === "games" && !play && profile) loadProfile().then(() => {
            boardCache.clear();
            draw();
        }).catch(() => {});
    }, 60000);
    window.algoGames = {
        render,
        close
    };
    restoring = true;
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => render(), {
        once: true
    });
    else void render();
})();
