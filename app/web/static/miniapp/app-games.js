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
    const title = id => id === "kopatych" ? "Копатыч · турнир" : E.games.find(g => g.id === id)?.name || id,
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
        if (!response.ok) {
            const error = Error(typeof value.detail === "string" ? value.detail : "Не удалось выполнить действие. Попробуй ещё раз.");
            error.status = response.status;
            throw error;
        }
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

    function masteryMarkup(detailed = false) {
        const m = profile.mastery,
            c = profile.competition;
        if (!m || !c) return '';
        const progress = m.next ? m.xp - m.floor : 1,
            total = m.next ? m.next - m.floor : 1;
        const tier = c.league,
            next = m.nextTitle;
        return `${detailed?'':`<section class="arcade-passport"><div class="arcade-passport-skill"><span class="arcade-level-seal"><b>${m.level}</b><small>УРОВЕНЬ</small></span><div><small class="arcade-passport-label">ТВОЁ МАСТЕРСТВО</small><h2>${esc(m.title)}</h2><div class="arcade-xp-line"><progress aria-label="Опыт до следующего уровня" value="${progress}" max="${total}"></progress><span>${m.next?`${progress} / ${total} XP`:'Максимальный уровень'}</span></div><small>${m.next?`${m.next-m.xp} XP до уровня ${m.level+1}`:'Все 50 уровней открыты'}</small></div></div><div class="arcade-passport-league"><small class="arcade-passport-label">РАНГ НЕДЕЛИ</small><h3>${esc(tier.name)} <span>${c.rank?'#'+c.rank:''}</span></h3><p>${c.score} очков · ${c.games} игр</p><small>${tier.remainingGames?`Ещё ${tier.remainingGames} игры до ранга`:tier.next?`${Math.max(0,tier.next-c.score)} очков до следующего ранга`:'Высшая лига'}</small><button data-tab="leaders">К рейтингу →</button></div></section>`}${detailed?`<section class="arcade-mastery-rules"><h3>Как растёт мастерство</h3><div><p><b>+100 XP</b> за первое прохождение задания</p><p><b>+25 XP</b> за каждую дополнительную звезду</p><p><b>+100 / 200 / 300 XP</b> за бронзовую, серебряную и золотую медали</p></div><p>${next?`Следующее звание: <b>${esc(next.name)}</b> — уровень ${next.level} и первая глава или медаль в ${next.games} играх. Сейчас освоено: ${m.breadth}.`:'Звание «Легенда» открыто.'}</p><small>Повторы без улучшения звёзд не добавляют опыт. Мастерство сохраняется, ранг пересчитывается каждую неделю. Уровень не даёт преимуществ в соревнованиях.</small></section>`:''}`;
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
      ${masteryMarkup()}
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
    const q=profile.goals[g.id];return `<div class="game-card-shell"><button class="game-card ${g.color}" data-game="${g.id}"><div class="game-card-art">${art(g.id)}${g.fresh?'<span class="arcade-new">НОВОЕ</span>':""}<span class="game-reward">${q.claimed?q.credited?"✓ Получено":"В очереди":q.eligible?"✦ Забрать награду":"✦ 10 AC"}</span></div><div class="game-card-body"><small>${g.tag}</small><h3>${g.name}</h3><div class="game-card-bottom"><span>${g.persistent?"Ферма · свой прогресс":ArcadeJourney.specs[g.id]?`${profile.journeys[g.id].cleared}/24 заданий · ${profile.journeys[g.id].stars} ★`:profile.best[g.id]?`Рекорд <b>${profile.best[g.id]}</b>`:`Цель: ${goal(g.id)}`}</span><span class="game-play">↗</span></div></div></button><button class="game-card-leader" data-leader="${g.id}">🏆 ${g.persistent?"Лидеры турнира":"Лидеры"}</button></div>`;
  }).join("")}</div>`;
    }

    function achievementText(a) {
        const extra = a.game === "typing" ? ` · точность ${[90,93,95][a.tier]}%` : a.game === "react" ? ` · до ${[450,400,350][a.tier]} мс, ошибок ≤ ${[1,0,0][a.tier]}` : "";
        return `${a.target} ${E.games.find(g=>g.id===a.game).unit}${extra}`;
    }

    function achievements() {
        return ArcadeJourneyView.collection(profile.journeys) + `<div class="arcade-tier-key"><span>Бронза · уверенный старт</span><span>Серебро · сильный результат</span><span>Золото · мастерство</span></div><div class="games-achievement-grid">${profile.achievements.map(a=>`<article class="game-achievement ${a.unlocked?"unlocked":""}"><span class="achievement-medal ${E.games.find(g=>g.id===a.game).color}">${art(a.game)}<i>${["I","II","III"][a.tier]}</i></span><div><h3>${title(a.game)} · ${["бронза","серебро","золото"][a.tier]}</h3><p>${achievementText(a)}</p><progress max="${a.target}" value="${a.value}"></progress><small>${a.value} / ${a.target}</small></div><button data-claim="${esc(a.id)}" ${!a.unlocked||a.claimed?"disabled":""}>${a.credited?"✓ Получено":a.claimed?"Ждёт лимита":`+${a.reward} AC`}</button></article>`).join("")}</div>`;
    }

    function rewards() {
        const pending = profile.awards.filter(a => a.claimed && a.credited === null);
        return `<section class="games-reward-summary"><div><small>Тестовые астрокоины</small><strong>${profile.balance} <span>AC</span></strong><p>Отдельный игровой баланс демки</p></div><div><b>Лимит недели: ${profile.cap.limit} AC</b><p>Начислено ${profile.cap.used} AC. Заработанные награды сверх лимита ждут следующей недели.</p></div></section>
      ${pending.length?`<div class="games-warning"><b>Ожидают лимита: ${pending.reduce((n,a)=>n+a.amount,0)} AC</b><p>Награды сохранены. Начисление продолжится с новой недели.</p></div>`:""}
      <div class="games-reward-list">${E.games.map(g=>{const q=profile.goals[g.id];return `<div><span class="reward-dot ${g.color}">✦</span><span><b>${g.name}</b><small>${Math.min(q.score,q.target)} / ${q.target}${g.id==="typing"?" · точность от 90%":""}</small></span><button data-claim="${esc(q.id||"")}" ${!q.eligible||q.claimed?"disabled":""}>${q.claimed?q.credited?"✓ Начислено":"В очереди":"Забрать 10 AC"}</button></div>`;}).join("")}</div>
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
        return masteryMarkup(true) + `<div class="arcade-progress-heading"><h3>Последние 10 партий</h3><select id="arcadeStatsGame">${E.games.map(g=>`<option value="${g.id}" ${statsGame===g.id?"selected":""}>${g.name}</option>`).join("")}</select></div>
      ${rows.length?`<svg class="arcade-chart" viewBox="0 0 300 135" role="img" aria-label="Результаты от ${rows[0].score} до ${rows.at(-1).score}"><path d="M20 110H280" stroke="#dcd1e9"/><polyline points="${pts}" fill="none" stroke="#9673bc" stroke-width="3" stroke-linejoin="round"/>${rows.map((r,i)=>`<circle cx="${20+i*260/Math.max(1,rows.length-1)}" cy="${110-r.score/max*85}" r="4" fill="#b1cf87"/>`).join("")}<text x="20" y="130" fill="#9b85ac" font-size="9">${rows.length} партий</text></svg>`:'<div class="games-leaders-empty"><h4>Сыграй первую партию</h4><p>Здесь появится твой прогресс.</p></div>'}
      <div class="games-reward-list">${rows.slice().reverse().map(r=>`<div><span><b>${r.score} ${E.games.find(g=>g.id===r.game).unit}</b><small>${r.mode==="journey"?`Задание ${r.report.journey.stage} · ${r.report.journey.stars} ★`:r.mode==="practice"?"Тренировка":r.accepted?"Соревнование":"Незавершённая попытка"} · ${new Date(r.created*1000).toLocaleDateString("ru-RU")} · ${detail(r)}</small></span><button data-replay="${r.id}">Разбор →</button></div>`).join("")}</div>`;
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
        const combined = game === 'overall',
            weekly = period === 'week',
            rows = data.rows,
            mine = rows.find(r => r.player === actor().id),
            shown = rows.slice(0, 20),
            index = rows.findIndex(r => r.player === actor().id),
            minimum = data.min_games;
        for (const r of rows.slice(Math.max(0, index - 2), index + 3))
            if (index >= 0 && !shown.some(s => s.player === r.player)) shown.push(r);
        const before = index > 0 ? rows[index - 1] : null,
            gap = before && mine ? Math.max(1, before.score - mine.score + 1) : 0,
            word = n => n % 100 >= 11 && n % 100 <= 14 ? 'игр' : n % 10 === 1 ? 'игра' : n % 10 >= 2 && n % 10 <= 4 ? 'игры' : 'игр',
            remaining = r => Math.max(0, minimum - (r?.games || 0)),
            requirement = r => remaining(r) ? `Ещё ${remaining(r)} ${word(remaining(r))} до призов` : 'Ты участвуешь в борьбе за призы',
            weekLabel = value => new Date(value + 'T00:00:00+03:00').toLocaleDateString('ru-RU', {
                timeZone: 'Europe/Moscow',
                day: 'numeric',
                month: 'long'
            }),
            winners = data.history.filter(w => w.winners.length);
        return `<section class="games-leaders arcade-ranking ${combined?'games-overall':''}" aria-label="${combined?'Общий рейтинг':esc(title(game))}">
          <header class="ranking-heading"><h3>${combined?'Общий рейтинг':esc(title(game))}</h3><p>${weekly?'Лучшие результаты за неделю':'Лучшие результаты за всё время'} · режим «Соревнование»</p></header>
          <div class="games-leader-controls"><div class="games-leader-period" aria-label="Период рейтинга">${[['week','За неделю'],['all','За всё время']].map(([id,name])=>`<button data-period="${id}" aria-pressed="${id===period}">${name}</button>`).join('')}</div>${speed.has(game)?`<div class="games-leader-period" aria-label="Управление">${[['keyboard','Клавиатура / мышь'],['touch','Касания']].map(([id,name])=>`<button data-board-device="${id}" aria-pressed="${id===device}">${name}</button>`).join('')}</div>`:''}</div>
          ${combined&&weekly?`<section class="ranking-prizes" aria-label="Призы недели"><div class="ranking-section-heading"><h4>Призы недели</h4><p>Итоги ${nextDeadline()} · 00:00 МСК</p></div><div class="ranking-prize-strip">${data.prizes.map((amount,i)=>`<div class="ranking-prize prize-${i+1}"><span>${i+1} место</span><strong>${amount} <small>AC</small></strong></div>`).join('')}</div><p class="ranking-prize-condition">Чтобы получить приз, нужно попасть в первую тройку и выполнить цели в ${minimum} разных играх.</p></section>`:''}
          ${mine?`<section class="games-my-rank ranking-mine" aria-label="Твой результат"><div class="ranking-mine-numbers"><div><span>Твоё место</span><strong>#${mine.rank}</strong></div><div><span>${combined?'Твои очки':'Твой рекорд'}</span><strong>${mine.score}${!combined?` <small>${esc(E.rankUnit(game))}</small>`:''}</strong></div></div>${combined&&weekly?`<div class="ranking-qualification ${mine.prizeEligible?'is-qualified':''}"><div><b>${requirement(mine)}</b><span>${Math.min(minimum,mine.games)} из ${minimum} игр с выполненной целью</span></div><div class="ranking-game-steps" aria-label="${Math.min(minimum,mine.games)} из ${minimum} игр">${Array.from({length:minimum},(_,i)=>`<i class="${i<mine.games?'is-complete':''}" aria-hidden="true">${i<mine.games?'✓':i+1}</i>`).join('')}</div></div>`:''}${before?`<p class="ranking-next-place">Чтобы обойти игрока на #${before.rank}, нужно ещё <b>${gap}</b> ${combined?'очков':esc(E.rankUnit(game))}.</p>`:''}</section>`:combined&&weekly?`<section class="ranking-first-step"><b>Начни с одной игры</b><p>Выбери «Соревнование» и выполни цель. Для призов нужны ${minimum} разные игры.</p></section>`:''}
          <div class="ranking-list-heading"><h4>Участники</h4><span>${combined?'Очки':'Рекорд'}</span></div>
          ${shown.length?`<ol class="ranking-list">${shown.map(r=>`<li value="${r.rank}" class="ranking-player ${r.player===actor().id?'is-me':''}"><div class="ranking-player-line"><span class="ranking-place place-${Math.min(4,r.rank)}" aria-label="Место ${r.rank}">${r.rank}</span><div class="ranking-person"><h4>${esc(r.name)}${r.player===actor().id?' <em>Ты</em>':''}</h4><p>${esc(r.group)}</p>${combined?`<span class="ranking-player-status ${r.prizeEligible?'is-qualified':''}">${weekly?r.prizeEligible?esc(r.league?.name||'Бронза'):requirement(r):`${r.games} ${word(r.games)}`}</span>`:''}</div><div class="ranking-points"><strong>${r.score}</strong><span>${combined?'очков':esc(E.rankUnit(game))}</span></div></div>${combined?`<details class="league-contributions ranking-breakdown"><summary>Из чего сложились очки</summary><ul>${r.contributions.map(c=>`<li><div><b>${esc(title(c.game))}</b><span>Место ${c.rank} в игре</span></div><strong>+${c.points}</strong></li>`).join('')}</ul></details>`:''}</li>`).join('')}</ol>`:'<div class="games-leaders-empty ranking-empty"><h4>Здесь появятся первые результаты</h4><p>Открой любую игру и выбери «Соревнование».</p></div>'}
          ${game==='drop'?'<p class="ranking-note">В рейтинге — Космопорт с новой физикой. Прежние партии остались в истории.</p>':''}
          ${combined?`<details class="league-rules ranking-rules"><summary>Как получить очки и призы</summary><div class="ranking-rules-content"><h4>Очки за место в каждой игре</h4><div class="ranking-point-key">${E.placePoints.map((points,i)=>`<div><span>${i+1} место</span><strong>${points}</strong></div>`).join('')}</div><p>Начиная с 11-го места — по 5 очков. В общий рейтинг идёт один лучший результат за каждую игру, если выполнена её цель. Для печати нужна точность от 90%.</p><p>Прохождение уровней, XP и достижения дают мастерство, а общий рейтинг считается по результатам «Соревнования».</p><h4>Ранги недели</h4><ul class="ranking-league-key">${[[0,'Бронза'],[200,'Серебро'],[450,'Золото'],[800,'Алмаз'],[1200,'Космос']].map(([points,name])=>`<li><b>${name}</b><span>от ${points} очков</span></li>`).join('')}</ul><p>Для ранга нужны цели в ${minimum} разных играх. Итоги недели — по понедельникам в 00:00 МСК. При равных очках выше игрок с большим числом игр, затем первых мест, затем с более ранним результатом.</p><p>Клавиатура и касания сравниваются отдельно в скоростных играх; в общий рейтинг идёт один лучший вклад за игру. Общий лимит всех игровых наград — ${profile.cap.limit} AC за неделю. Награды сверх лимита сохраняются в очереди.</p></div></details>`:''}
          ${combined&&winners.length?`<details class="league-last-week ranking-history"><summary>Победители прошлых недель</summary>${winners.map(w=>`<section><h4>Неделя с ${weekLabel(w.week)}</h4>${w.winners.map(r=>`<div><span>${esc(r.name)}</span><strong>+${r.prize} AC</strong></div>`).join('')}</section>`).join('')}</details>`:''}
        </section>`;
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
        if (play || window.KopatychFarm?.isOpen) return;
        device = matchMedia('(pointer:coarse)').matches ? 'touch' : 'keyboard';
        const g = E.games.find(g => g.id === id),
            d = document.createElement("dialog");
        d.id = "gameDialog";
        d.dataset.game = id;
        d.className = "game-dialog";
        d.innerHTML = `<header><button class="game-menu-back" aria-label="Меню игры" hidden>←</button><div><h2>${g.name}</h2></div><button class="game-leaders-button" aria-label="Таблица лидеров">${ArcadeResults.trophy}</button><button class="game-close" aria-label="Закрыть игру">×</button></header><div class="game-hud"><span>Счёт <b id="gameScore">0</b></span><span id="gameClock"></span><span class="game-level" id="gameLevel">Сложность 1</span><button class="arcade-pause" aria-label="Пауза" hidden>Ⅱ</button></div><div class="arcade-live-goal"><span></span><progress value="0" max="${g.goal}"></progress></div><div class="arcade-learning-tip" role="status" hidden></div><div class="journey-tools" hidden><div><b></b><small></small></div><button></button></div><div class="game-stage"></div><footer><span id="gameHint"></span><button id="gameFinish" hidden>Завершить</button></footer>`;
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
            recorded: false,
            menuScreen: 'menu',
            selectedJourney: profile.journeys?.[id]?.unlocked || 1
        };
        play = run;
        document.body.append(d);
        d.showModal();
        intro(run);
        $('.game-menu-back', d).onclick = () => {
            run.menuScreen = 'menu';
            run.world = null;
            intro(run);
        };
        $('.journey-tools button', d).onclick = () => input(run, {
            type: 'power',
            source: run.device
        });
        $(".game-close", d).onclick = () => {
            if (["playing", "ready", "paused", "starting"].includes(run.phase)) run.pause(true);
            else close();
        };
        $(".game-leaders-button", d).onclick = async () => {
            if (["playing", "ready", "starting"].includes(run.phase)) await run.pause();
            openLeaders(id);
        };
        $(".arcade-pause", d).onclick = () => run.pause();
        d.addEventListener("cancel", e => {
            e.preventDefault();
            if (run.phase === "playing" || run.phase === "ready" || run.phase === "starting") run.pause();
            else if (run.phase === "paused") run.resume();
            else close();
        });
        run.pause = async exit => {
            if (run.phase === 'starting') {
                run.pauseQueued = true;
                run.pauseExit = !!exit;
                return;
            }
            if (run.phase !== "playing" && run.phase !== "ready") return;
            const wasReady = run.phase === "ready";
            const footerHidden = $('footer', d).hidden,
                goalHidden = $('.arcade-live-goal', d).hidden;
            if (!wasReady) {
                catchUp(run);
                run.playedMs += performance.now() - run.anchor;
            }
            if (run.world?.ended) return;
            run.phase = "paused";
            $('footer', d).hidden = true;
            $('.arcade-live-goal', d).hidden = true;
            const cover = document.createElement("div");
            cover.className = "game-pause";
            cover.innerHTML = `<span class="arcade-pause-symbol" aria-hidden="true">Ⅱ</span><h3>${exit?"Завершить игру?":"Пауза"}</h3><button class="games-main" data-resume>Продолжить</button><button class="game-back" data-exit>Завершить игру</button>`;
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
                $('footer', d).hidden = footerHidden;
                $('.arcade-live-goal', d).hidden = goalHidden;
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
            if (run.phase === "playing" || run.phase === "ready" || run.phase === "starting") run.pause();
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

    function masteryGain(run, cover) {
        const before = run.oldMastery,
            after = profile.mastery;
        if (!before || !after || after.xp <= before.xp) return;
        ($('.arcade-result-actions', cover) || cover).insertAdjacentHTML('afterend', `<div class="arcade-mastery-gain">+${after.xp-before.xp} XP${after.level>before.level?` · Уровень ${after.level}`:''}${after.title!==before.title?` · ${esc(after.title)}`:''}</div>`);
    }

    function intro(run) {
        cancelAnimationFrame(run.raf);
        run.viewAbort?.abort();
        run.phase = 'intro';
        const {
            g,
            dialog: d
        } = run, screen = run.menuScreen || 'menu';
        d.classList.add('is-browsing');
        d.classList.remove('is-learning', 'is-finished');
        $('.game-hud', d).hidden = true;
        $('.arcade-live-goal', d).hidden = true;
        $('.journey-tools', d).hidden = true;
        $('.arcade-learning-tip', d).hidden = true;
        $('footer', d).hidden = true;
        $('.game-leaders-button', d).hidden = true;
        $('.game-menu-back', d).hidden = screen === 'menu';
        const host = $('.game-stage', d);
        host.innerHTML = screen === 'levels' ? ArcadeMenu.levels(g.id, profile.journeys[g.id], run.selectedJourney) :
            screen === 'arenas' ? ArcadeMenu.arenas(run.arena || 'classic') : ArcadeMenu.home(g);
        host.scrollTop = 0;
        host.onclick = e => {
            const button = e.target.closest('button');
            if (!button || button.disabled) return;
            if (button.hasAttribute('data-menu-levels')) {
                if (g.id === 'kopatych' && window.KopatychFarm) {
                    close();
                    void KopatychFarm.open(api, {
                        player: actor().id,
                        settings: profile.settings,
                        onSprint: () => openGame(g.id)
                    });
                } else {
                    run.menuScreen = 'levels';
                    intro(run);
                }
            } else if (button.hasAttribute('data-menu-learning')) {
                void tutorial(run);
            } else if (button.dataset.mode) {
                mode = button.dataset.mode;
                if (g.id === 'drop' && mode === 'practice') {
                    run.menuScreen = 'arenas';
                    intro(run);
                } else void begin(run);
            } else if (button.dataset.journeyPlay) {
                void begin(run, +button.dataset.journeyPlay);
            } else if (button.dataset.journeyStage) {
                run.selectedJourney = +button.dataset.journeyStage;
                intro(run);
            } else if (button.dataset.arena) {
                run.arena = button.dataset.arena;
                intro(run);
            } else if (button.hasAttribute('data-practice-start')) {
                mode = 'practice';
                void begin(run);
            }
        };
    }

    function mount(run) {
        run.viewAbort?.abort();
        run.viewAbort = new AbortController();
        run.abort.signal.addEventListener("abort", () => run.viewAbort?.abort(), {
            once: true
        });
        const stage = $(".game-stage", run.dialog);
        run.dialog.dataset.playMode = run.world.mode;
        stage.innerHTML = "";
        stage.onclick = null;
        run.view = V.mount(run.g.id, stage, a => input(run, a), {
            signal: run.viewAbort.signal,
            device: run.world.device,
            mode: run.world.mode,
            skin: run.world.journey ? ['base', 'mint', 'sun', 'nebula', 'mint', 'nebula'][run.world.journey.chapter] : profile.settings.skin,
            theme: run.world.journey ? ['space', 'forest', 'sunset', 'nebula', 'forest', 'nebula'][run.world.journey.chapter] : profile.settings.theme === 'space' ? ({
                bugs: 'forest',
                tower: 'sunset',
                drop: 'nebula',
                runner: 'nebula',
                bubbles: 'forest'
            } [run.g.id] || 'space') : profile.settings.theme,
            quality: () => run.quality || "high",
            paused: () => !["playing", "ready", "tutorial"].includes(run.phase)
        });
        run.view.update(run.world, 0);
        ArcadePersonality.decorate(run);
        ArcadeJourneyView.tools(run);
    }
    async function tutorial(run) {
        cancelAnimationFrame(run.raf);
        run.tutorialActed = false;
        run.phase = "tutorial";
        run.dialog.classList.remove('is-browsing');
        run.dialog.classList.add('is-learning');
        $('.game-menu-back', run.dialog).hidden = false;
        $('.game-leaders-button', run.dialog).hidden = true;
        run.world = W.create({
            game: run.g.id,
            seed: 41,
            ...(run.g.id === 'drop' ? {
                dropPhysics: 3,
                arena: run.arena || 'classic'
            } : {}),
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
        const instruction = {
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
        $('.arcade-learning-tip', run.dialog).hidden = false;
        $('.arcade-learning-tip', run.dialog).textContent = instruction;
        const frame = () => {
            if (play !== run || run.phase !== "tutorial") return;
            if (run.tutorialActed && ["orbit", "drop", "bubbles"].includes(w.id)) W.advance(w, 1);
            run.view.update(w, 1 / 60);
            if (window.ArcadeExtras?.tutorialDone(w) ?? (w.score >= (w.id === "typing" ? 3 : 1))) {
                run.phase = "intro";
                const cover = document.createElement("div");
                cover.className = "game-result";
                cover.innerHTML = '<span class="result-star">✓</span><h3>Получилось!</h3><button class="games-main" data-learning-play>Соревнование</button><button class="game-back" data-learning-menu>В меню</button>';
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
                $('[data-learning-play]', cover).onclick = () => {
                    mode = 'ranked';
                    void begin(run);
                };
                $('[data-learning-menu]', cover).onclick = () => {
                    run.menuScreen = 'menu';
                    intro(run);
                };
                return;
            }
            run.raf = requestAnimationFrame(frame);
        };
        frame();
    }
    async function begin(run, journeyStage = null) {
        if (profile.settings.sound) {
            try {
                run.audio ||= new(window.AudioContext || window.webkitAudioContext)();
                void run.audio.resume();
            } catch {}
        }
        cancelAnimationFrame(run.raf);
        run.viewAbort?.abort();
        run.phase = "loading";
        run.dialog.classList.remove('is-browsing', 'is-learning', 'is-finished');
        $('.arcade-learning-tip', run.dialog).hidden = true;
        $('.game-menu-back', run.dialog).hidden = true;
        $('.game-leaders-button', run.dialog).hidden = false;
        $('footer', run.dialog).hidden = false;
        $("#gameHint", run.dialog).textContent = `Цель: ${goal(run.g.id)}`;
        $(".game-stage", run.dialog).innerHTML = '<div class="arcade-loading">Готовим партию…</div>';
        const selectedMode = journeyStage ? 'journey' : mode;
        run.oldMastery = profile.mastery;
        if (journeyStage) run.selectedJourney = journeyStage;
        try {
            run.session = await api("/sessions", {
                method: "POST",
                body: {
                    game: run.g.id,
                    mode: selectedMode,
                    device,
                    ...(run.g.id === 'drop' && selectedMode === 'practice' ? {
                        arena: run.arena || 'classic'
                    } : {}),
                    ...(journeyStage ? {
                        stage: journeyStage
                    } : {})
                }
            });
        } catch (error) {
            toast(error.message);
            intro(run);
            return;
        }
        if (play !== run) return;
        run.world = W.create(run.session.setup);
        run.mode = selectedMode;
        run.recorded = false;
        run.record = null;
        run.inputQueue = [];
        run.pauseQueued = false;
        run.pauseExit = false;
        run.clockPromise = Promise.resolve();
        run.device = device;
        run.events = [];
        run.frames = [];
        run.playedMs = 0;
        run.lastCue = 0;
        mount(run);
        $('.game-hud', run.dialog).hidden = false;
        $('.arcade-live-goal', run.dialog).hidden = false;
        run.dialog.scrollTop = 0;
        $(".arcade-pause", run.dialog).hidden = false;
        $("#gameFinish", run.dialog).hidden = false;
        run.oldBest = profile.best[run.g.id] || 0;
        if (run.g.id === "typing") {
            run.phase = "ready";
            $("#gameClock", run.dialog).textContent = "Начни печатать";
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
        if (run.pauseQueued) {
            run.pauseQueued = false;
            await run.pause(run.pauseExit);
        }
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
        hud(run);
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
        $("#gameLevel", d).textContent = `Сложность ${w.level}`;
        if (run.phase !== "ready") $("#gameClock", d).textContent = (g.seconds || w.id === "typing") ? `${Math.max(0,Math.ceil((g.seconds||60)-w.time))} с` : w.id === "memory" && !w.between ? `${Math.max(0,Math.ceil(w.left))} с` : w.id === "debug" ? `${Math.min(8,w.index+1)} / 8` : `${Math.floor(w.time)} с`;
        if (w.journey) {
            const j = w.journey;
            $('#gameLevel', d).textContent = 'Уровень ' + j.stage;
            if (run.phase !== 'ready') {
                const left = Math.max(0, Math.ceil(j.seconds - w.time));
                $('#gameClock', d).textContent = left >= 60 ? Math.floor(left / 60) + ':' + String(left % 60).padStart(2, '0') : left + ' с';
            }
            $('.arcade-live-goal progress', d).max = j.goal;
            $('.arcade-live-goal progress', d).value = Math.min(j.goal, w.score);
            $('.arcade-live-goal span', d).textContent = ArcadeJourneyView.labels(j) + (j.moves ? ' · осталось ' + Math.max(0, Math.ceil(j.moves - j.movesUsed)) + ' ходов' : '');
            ArcadeJourneyView.tools(run);
            return;
        }
        if (w.id === 'react') $('#gameClock', d).textContent = w.hits.length ? Math.round(w.hits.reduce((a, b) => a + b, 0) / w.hits.length) + ' мс' : '— мс';
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
        run.viewAbort?.abort();
        run.dialog.classList.add('is-finished');
        $('.game-hud', run.dialog).hidden = true;
        $('.arcade-live-goal', run.dialog).hidden = true;
        $('.journey-tools', run.dialog).hidden = true;
        $('footer', run.dialog).hidden = true;
        $(".arcade-pause", run.dialog).hidden = true;
        $("#gameFinish", run.dialog).hidden = true;
        $(".game-pause", run.dialog)?.remove();
        const stage = $(".game-stage", run.dialog),
            cover = document.createElement("div");
        cover.className = "game-result";
        cover.innerHTML = '<div class="arcade-loading">Проверяем результат партии…</div>';
        stage.replaceChildren(cover);
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
            const report = result.run.report || W.report(run.world);
            if (report.journey) {
                cover.classList.add('journey-result');
                cover.innerHTML = ArcadeResults.journey(run, report, result.rewards);
                masteryGain(run, cover);
                $('.journey-tools', run.dialog).hidden = true;
                const map = () => {
                    run.selectedJourney = report.journey.success ? Math.min(24, report.journey.stage + 1) : report.journey.stage;
                    run.phase = 'intro';
                    run.world = null;
                    run.menuScreen = 'levels';
                    intro(run);
                };
                $('[data-journey-next]', cover).onclick = () => !report.journey.success ? begin(run, report.journey.stage) : report.journey.stage < 24 ? begin(run, report.journey.stage + 1) : map();
                $('[data-journey-map]', cover)?.addEventListener('click', map);
                return;
            }
            let rank = null;
            if (result.run.accepted) {
                try {
                    const board = await boardData(run.g.id, 'week', run.device);
                    rank = board.rows.find(r => r.player === actor().id)?.rank;
                } catch {
                    /* The score and reward are already safe even if the board is unavailable. */
                }
            }
            if (play !== run) return;
            cover.innerHTML = ArcadeResults.normal(run, result, rank);
            masteryGain(run, cover);
            $("[data-again]", cover).onclick = () => {
                mode = run.mode;
                device = run.device;
                void begin(run);
            };
            $("[data-back]", cover).onclick = () => {
                close();
                draw();
            };
            $("[data-analysis]", cover).onclick = () => run.frames.length ? showReplay(run.g.id, run.frames, report) : replayHistory(result.run.id);
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
        d.dataset.game = game;
        d.dataset.playMode = 'replay';
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
        if (frames.length) view.update(frames[0], 0);
        ArcadePersonality.decorate({
            g: {
                id: game
            },
            dialog: d,
            view
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
        const refreshCards = !!play?.recorded;
        window.KopatychFarm?.close();
        if (play) {
            cancelAnimationFrame(play.raf);
            play.abort.abort();
            play.audio?.close();
            play.dialog.remove();
            play = null;
        }
        $("#gamesLeaderDialog")?.remove();
        if (refreshCards && profile && state.view === 'games' && !document.hidden) draw();
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
