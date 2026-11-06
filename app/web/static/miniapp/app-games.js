/* Local arcade client. Ranked scores, achievements and prizes belong to the server. */
(() => {
    "use strict";
    const pilot = !!window.ALGO_ARCADE_PILOT;
    if (!pilot && (!window.ALGO_GAMES_PROTOTYPE || !localDemoHost || !apiContext.demoMode)) return;
    const E = AlgoGameEngine,
        W = ArcadeWorld,
        V = ArcadeView,
        A = AlgoGameArt,
        M = AlgoGameMotion;
    const $ = (s, r = document) => r.querySelector(s),
        root = $("#gamesRoot"),
        apiRoot = pilot ? '/api/v1/miniapp/arcade' : window.ALGO_ARCADE_API;
    const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
    } [c]));
    const title = id => id === "kopatych" ? "Копатыч · турнир" : id === 'runner' ? 'Геометрический рывок · архив' : E.games.find(g => g.id === id)?.name || id,
        art = id => A.render(id),
        speed = new Set(["orbit", "bugs", "tower", "typing", "react", "kopatych", "runner", "words"]);
    const goal = id => {
        const g = E.games.find(g => g.id === id);
        return id === "2048" ? `плитка ${g.goal}` : `${g.goal} ${g.unit}`;
    };
    const actors = pilot ? [{
        id: 'pilot:' + Number(state.account?.max_user_id || apiContext.maxUserId),
        name: state.account?.display_name || 'Участник тестирования'
    }] : window.ALGO_GAME_PLAYERS || [];
    let savedPlayer = null;
    if (!pilot) {
        try { savedPlayer = window.localStorage.getItem("arcade-player-v3"); } catch {}
    }
    let selected = savedPlayer || actors[0]?.id,
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
        if (pilot && !window.AlgoArcadePilot?.canOpen()) throw Error('Нет доступа к тестированию игр.');
        if (!pilot && (!apiRoot || !actor()?.token)) throw Error("Локальный сервер игр недоступен. Перезапусти демку.");
        const token = pilot ? null : admin ? window.pizzaPreview?.token : actor().token;
        const controller = new AbortController(),
            timeout = keepalive ? null : setTimeout(() => controller.abort(), 15000);
        try {
            const response = await (pilot ? apiFetch : fetch)(apiRoot + path, {
                method,
                keepalive,
                signal: controller.signal,
                headers: {
                    ...(token ? {"X-Miniapp-Token": token} : {}),
                    "Content-Type": "application/json"
                },
                body: body === undefined ? undefined : JSON.stringify(body)
            });
            let value;
            try {
                value = await response.json();
            } catch (error) {
                if (error.name === 'AbortError') throw error;
                throw Error("Не удалось получить ответ сервера. Попробуй ещё раз.");
            }
            if (!response.ok) {
                const error = Error(typeof value.detail === "string" ? value.detail : "Не удалось выполнить действие. Попробуй ещё раз.");
                error.status = response.status;
                throw error;
            }
            return value;
        } catch (error) {
            if (error.name === 'AbortError') throw Error('Сервер долго не отвечает. Попробуй ещё раз.');
            if (error instanceof TypeError) throw Error('Не удалось связаться с сервером. Проверь подключение и попробуй ещё раз.');
            throw error;
        } finally {
            if (timeout !== null) clearTimeout(timeout);
        }
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
        if (pilot && !window.AlgoArcadePilot?.canOpen()) return;
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
        const remaining = tier.remainingGames,
            leagueName = remaining ? 'Без ранга' : esc(tier.name),
            leagueHint = remaining ? `Ещё ${remaining} ${remaining===1?'игра':'игры'} с выполненной целью` : tier.next ? `До следующего ранга — ${Math.max(0,tier.next-c.score)} очков` : 'Высшая лига открыта';
        return `${detailed?'':`<section class="arcade-passport" aria-label="Твой игровой прогресс"><div class="arcade-passport-skill"><span class="arcade-level-seal"><b>${m.level}</b><span>уровень</span></span><div><h2>${esc(m.title)}</h2><div class="arcade-xp-line"><progress aria-label="Опыт до следующего уровня" value="${progress}" max="${total}"></progress></div><p class="arcade-next-level">${m.next?`До уровня ${m.level+1} — <b>${m.next-m.xp} XP</b>`:'Все 50 уровней открыты'}</p></div></div><button class="arcade-passport-league" data-tab="leaders" aria-label="Открыть общий рейтинг"><span class="arcade-passport-label">Сезон до ${nextDeadline(profile.season.end)}</span><span class="arcade-season-result"><strong>${leagueName}</strong><span>${c.rank?'#'+c.rank+' · ':''}${c.score} очков</span></span><span class="arcade-season-hint">${leagueHint}</span></button></section>`}${detailed?`<section class="arcade-mastery-rules"><h3>Как растёт мастерство</h3><div><p><b>+100 XP</b> за первое прохождение задания</p><p><b>+25 XP</b> за каждую дополнительную звезду</p><p><b>+100 / 200 / 300 XP</b> за бронзовую, серебряную и золотую медали</p></div><p>${next?`Следующее звание: <b>${esc(next.name)}</b> — уровень ${next.level} и первая глава или медаль в ${next.games} играх. Сейчас освоено: ${m.breadth}.`:'Звание «Легенда» открыто.'}</p><small>Повторы без улучшения звёзд не добавляют опыт. Мастерство сохраняется, ранг пересчитывается каждые две недели. Уровень не даёт преимуществ в соревнованиях.</small></section>`:''}`;
    }

    function nextDeadline(end) {
        const d = new Date(end + "T00:00:00+03:00");
        return d.toLocaleDateString("ru-RU", {
            timeZone: "Europe/Moscow",
            day: "numeric",
            month: "long"
        });
    }

    function tabs() {
        return [
            ["games", "Игры"],
            ["leaders", "Рейтинг"],
            ["achievements", "Достижения"],
            ["looks", "Образы"],
            ["progress", "Прогресс"],
            ["rewards", "Награды"]
        ].map(([id, name]) => `<button data-tab="${id}" class="${tab===id?"active":""}" aria-pressed="${tab===id}">${name}</button>`).join("");
    }

    function draw() {
        if (!profile) {
            root.innerHTML = `<div class="games-warning" role="alert">${esc(loadingError||"Нет связи с сервером игр")}<button class="arcade-subtle" data-reload>Попробовать снова</button></div>`;
            $("[data-reload]", root).onclick = () => render();
            return;
        }
        root.innerHTML = `<div class="games-heading"><div class="games-lobby-title"><h1>Игры</h1></div><div class="arcade-account"><label class="games-player-picker"><span class="games-player-label">Игрок</span><select id="gamesPlayer" aria-label="Игрок">${actors.map(p=>`<option value="${esc(p.id)}" ${p.id===actor().id?"selected":""}>${esc(p.name)}</option>`).join("")}</select></label><button class="arcade-settings" aria-label="Настройки игр" data-settings>⚙</button></div></div>
      ${tab!=='leaders'?`<div class="arcade-lobby-status">${masteryMarkup()}<button class="arcade-reward-overview" data-tab="rewards"><span class="arcade-reward-balance"><span>Награды</span><strong>${profile.balance} <span>AC</span></strong></span></button></div>`:''}
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
        if(pilot) {
            $('.games-player-picker',root).remove();
            $('.games-heading',root).insertAdjacentHTML('afterend','<p class="arcade-pilot-note">Тестирование · награды не расходуются в магазине</p>');
        }
        const picker=$("#gamesPlayer", root);
        if(picker)picker.onchange = async e => {
            selected = e.target.value;
            try { window.localStorage.setItem("arcade-player-v3", selected); } catch {}
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

    function gardenFeature() {
        const bear = window.KopatychArt?.character(false, 1) || art('kopatych');
        return `<section class="arcade-garden-feature" aria-label="Копатыч"><div class="arcade-feature-copy"><p>Твой огород</p><h2>Копатыч</h2><div class="arcade-feature-actions"><button data-garden>Мой огород</button><button data-sprint>Соревнование</button></div></div><div class="arcade-feature-art" aria-hidden="true">${bear}</div></section>`;
    }

    function openGarden() {
        if (!window.KopatychFarm || KopatychFarm.isOpen) return;
        close();
        void KopatychFarm.open(api, {
            player: actor().id,
            settings: profile.settings,
            onSprint: () => openGame('kopatych')
        });
    }

    function openGarage(tab = 'routes', stage = null, route = null) {
        if (ArcadeHillGarage.isOpen) return;
        close();
        void ArcadeHillGarage.open(api, {
            tab,
            stage,
            route,
            journey: profile.journeys.hill,
            onDrive: (route, stage) => {
                openGame('hill');
                play.arena = route;
                play.fromGarage = true;
                mode = 'practice';
                void begin(play, stage);
            }
        });
    }

    function cards() {
        const trophy = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 4h8v6a4 4 0 0 1-8 0Z"/><path d="M8 6H4v2a4 4 0 0 0 4 4m8-6h4v2a4 4 0 0 1-4 4m-4 2v5m-4 1h8"/></svg>';
        return `${filter==='all'?gardenFeature():''}<div class="arcade-library-heading"><h2>Библиотека</h2><div class="games-filters" aria-label="Категории игр">${[["all","Все"],["fun","Аркады"],["skill","Навыки"],["puzzle","Логика"]].map(([id,name])=>`<button data-filter="${id}" aria-pressed="${filter===id}" class="${filter===id?"active":""}">${name}</button>`).join("")}</div></div><div class="games-grid">${E.games.slice().sort((a,b)=>Number(!!b.fresh)-Number(!!a.fresh)).filter(g=>filter==="all"||g.kind===filter).map(g=>{
            const q = profile.goals[g.id], journey = profile.journeys[g.id],
                cleared = journey?.cleared || 0, maximum=journey?.maximum||24,
                progressText = g.id==='react' ? '5 тестов · реакция и память' : g.persistent ? 'Огород и турнир' : journey ? cleared===maximum ? 'Все уровни пройдены' : cleared ? `${cleared} из ${maximum} пройдено` : maximum===24?'24 уровня':`${maximum} уровней` : `Цель: ${goal(g.id)}`;
            return `<div class="game-card-shell"><button class="game-card ${g.color}" data-game="${g.id}"><span class="game-card-art">${art(g.id)}</span><span class="game-card-body"><h3>${g.name}</h3><span class="game-card-bottom"><span>${progressText}</span>${!q.claimed||!q.credited?`<span class="game-reward">${q.claimed?'Начисляется':`+${q.reward} AC`}</span>`:''}</span>${journey&&cleared?`<progress class="game-card-progress" aria-label="Пройденные уровни: ${cleared} из ${maximum}" value="${cleared}" max="${maximum}"></progress>`:''}</span></button><button class="game-card-leader" data-leader="${g.id}" aria-label="Лидеры: ${g.name}" title="Лидеры">${trophy}</button></div>`;
        }).join("")}</div>`;
    }

    function achievementText(a) {
        return `${a.target} ${E.games.find(g=>g.id===a.game).unit} · ${esc(a.condition)}`;
    }

    function achievements() {
        return ArcadeJourneyView.collection(profile.journeys) + `<div class="arcade-tier-key"><span>Бронза · сильный результат</span><span>Серебро · эксперт</span><span>Золото · мастерство</span></div><div class="games-achievement-grid">${profile.achievements.map(a=>`<article class="game-achievement ${a.unlocked?"unlocked":""}"><span class="achievement-medal ${E.games.find(g=>g.id===a.game).color}">${art(a.game)}<i>${["I","II","III"][a.tier]}</i></span><div><h3>${title(a.game)} · ${["бронза","серебро","золото"][a.tier]}</h3><p>${achievementText(a)}</p><progress max="${a.target}" value="${a.value}"></progress><small>${a.value} / ${a.target}</small></div><button data-claim="${esc(a.id)}" ${!a.unlocked||a.claimed?"disabled":""}>${a.credited?"✓ Получено":a.claimed?"Начисляется":`+${a.reward} AC`}</button></article>`).join("")}</div>`;
    }

    function rewards() {
        return `<section class="games-reward-summary"><div><small>Тестовые астрокоины</small><strong>${profile.balance} <span>AC</span></strong><p>5 AC за первое выполнение цели каждой игры — один раз за всё время.</p></div></section>
      <div class="games-reward-list">${E.games.map(g=>{const q=profile.goals[g.id];return `<div><span class="reward-dot ${g.color}">✦</span><span><b>${g.name}</b><small>${Math.min(q.score,q.target)} / ${q.target}${g.id==="typing"?" · точность от 90%":""}</small></span><button data-claim="${esc(q.id||"")}" ${!q.eligible||q.claimed?"disabled":""}>${q.claimed?q.credited?"✓ Начислено":"Начисляется":`Забрать ${q.reward} AC`}</button></div>`;}).join("")}</div>
      <h3 class="games-history-title">История начислений</h3><div class="games-reward-list">${profile.credits.length?profile.credits.map(c=>`<div><span><b>${esc(c.label)}</b><small>${new Date(c.created*1000).toLocaleString("ru-RU",{timeZone:"Europe/Moscow"})}</small></span><strong>+${c.amount} AC</strong></div>`).join(""):'<div><span>Пока нет начислений</span></div>'}</div>`;
    }

    function looks() {
        const unlocked = Math.max(0, ...profile.achievements.filter(a => a.unlocked).map(a => a.tier + 1));
        return `<div class="arcade-looks-intro"><h3>Образы за мастерство</h3><p>Бронза открывает мятный набор, серебро — солнечный, золото — туманность. Характеристики персонажей одинаковые.</p></div><div class="arcade-looks">${[["base","space","Космос"],["mint","forest","Мятная орбита"],["sun","sunset","Солнечный рейс"],["nebula","nebula","Туманность"]].map(([skin,theme,name],i)=>`<button class="arcade-look ${skin===profile.settings.skin?"selected":""}" data-skin="${skin}" data-theme="${theme}" ${i>unlocked?"disabled":""}><div style="filter:hue-rotate(${i*52}deg)">${art("orbit")}</div><b>${name}</b><small>${i>unlocked?`${["","Бронза","Серебро","Золото"][i]} в любой игре`:skin===profile.settings.skin?"Выбрано":"Выбрать"}</small></button>`).join("")}</div>`;
    }

    function progress() {
        const rows = profile.runs.filter(r => r.game === statsGame && (r.accepted || r.report.complete)).slice(0, 10).reverse(),
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
        if (b.hasAttribute("data-garden")) openGarden();
        if (b.hasAttribute("data-sprint")) {
            mode = 'ranked';
            openGame('kopatych');
            if (play?.g.id === 'kopatych' && play.phase === 'intro') void begin(play);
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
            index = rows.indexOf(mine),
            minimum = data.min_games,
            shown = rows.slice(0, 20),
            eligible = combined && weekly ? rows.filter(r => r.prizeEligible).slice(0, data.prizes.length) : [],
            prizeFor = r => eligible.includes(r) ? data.prizes[eligible.indexOf(r)] : 0,
            word = n => n % 100 >= 11 && n % 100 <= 14 ? 'игр' : n % 10 === 1 ? 'игра' : n % 10 >= 2 && n % 10 <= 4 ? 'игры' : 'игр',
            missing = Math.max(0, minimum - (mine?.games || 0)),
            qualification = missing ? `${missing===1?'Осталась':'Осталось'} ${missing} ${word(missing)} до призового зачёта` : 'Ты в призовом зачёте',
            weekLabel = value => new Date(value + 'T00:00:00+03:00').toLocaleDateString('ru-RU', {
                timeZone: 'Europe/Moscow',
                day: 'numeric',
                month: 'long'
            }),
            periodControls = `<div class="games-leader-period" aria-label="Период рейтинга">${[['week','За сезон'],['all','За всё время']].map(([id,name])=>`<button data-period="${id}" aria-pressed="${id===period}">${name}</button>`).join('')}</div>`,
            winners = data.history.filter(w => w.winners.length);
        for (const r of rows.slice(Math.max(0, index - 2), index + 3))
            if (index >= 0 && !shown.includes(r)) shown.push(r);
        const subtitle = weekly ? `Сезон с ${weekLabel(data.season.start)} · итоги ${weekLabel(data.season.end)}` : 'Результаты за всё время';
        const gameMetric = r => {
            const d = r.details || {};
            if (game === 'typing' && d.accuracy) return `${d.accuracy}% точности`;
            if (game === 'react' && d.reactionMs) return `${d.reactionMs} мс`;
            if (game === 'memory' && d.moves) return `${d.moves} ходов`;
            if (game === 'debug' && d.timeMs) return `${Math.floor(d.timeMs/60000)}:${String(Math.floor(d.timeMs/1000)%60).padStart(2,'0')}`;
            if (game === '2048' && r.result) return `Плитка ${r.result}`;
            return E.rankUnit(game);
        };
        const playerMarkup = r => {
            const cells = `<span class="ranking-place place-${Math.min(4,r.rank)}" aria-label="Место ${r.rank}">${r.rank}</span><div class="ranking-person"><h4>${esc(r.name)}${r.player===actor().id?' <em>Ты</em>':''}</h4><p>${esc(r.group)}</p>${combined?`<span class="ranking-games-mobile">${r.games} ${word(r.games)} <span aria-hidden="true">⌄</span></span>`:''}</div>${combined?`<span class="ranking-games-column">${r.games} ${word(r.games)}${r.prizeEligible&&weekly?`<span>${esc(r.league?.name||'Бронза')}</span>`:''}</span>`:''}<span class="ranking-points"><strong>${r.score.toLocaleString('ru-RU')}</strong>${combined?prizeFor(r)?`<span class="ranking-row-prize" title="Предварительная награда по текущим результатам">${prizeFor(r)} AC</span>`:'':`<span>${esc(gameMetric(r))}</span>`}</span>${combined?'<span class="ranking-expand" aria-hidden="true">⌄</span>':''}`;
            return `<li value="${r.rank}" class="ranking-player ${r.player===actor().id?'is-me':''}">${combined?`<details class="ranking-breakdown"><summary class="ranking-player-line" title="Результаты по играм">${cells}</summary><ul>${r.contributions.map(c=>`<li><span class="ranking-game-mark">${art(c.game)}</span><div><b>${esc(title(c.game))}</b><span>${c.rank} место в игре</span></div><strong>+${c.points}</strong></li>`).join('')}</ul></details>`:`<div class="ranking-player-line">${cells}</div>`}</li>`;
        };
        let lastIndex = -1;
        const players = shown.map(r => {
            const current = rows.indexOf(r),
                gap = lastIndex >= 0 && current > lastIndex + 1;
            lastIndex = current;
            return `${gap?'<li class="ranking-gap" aria-label="Промежуточные участники не показаны">···</li>':''}${playerMarkup(r)}`;
        }).join('');
        return `<section class="arcade-ranking ${combined?'games-overall':'ranking-single-game'}" aria-label="${combined?'Общий рейтинг':esc(title(game))}">
          <header class="ranking-heading"><div><h3>${combined?'Общий рейтинг':esc(title(game))}</h3><p>${subtitle}</p></div>${periodControls}</header>
          ${speed.has(game)?`<div class="games-leader-period ranking-device" aria-label="Управление">${[['keyboard','Клавиатура / мышь'],['touch','Касания']].map(([id,name])=>`<button data-board-device="${id}" aria-pressed="${id===device}">${name}</button>`).join('')}</div>`:''}
          ${combined&&weekly?`<section class="ranking-prizes" aria-label="Призы сезона"><div class="ranking-prize-intro"><h4>Призы сезона</h4></div><div class="ranking-prize-strip">${data.prizes.map((amount,i)=>`<div class="ranking-prize"><span>${i+1} место</span><strong>${amount} <small>AC</small></strong></div>`).join('')}</div></section><div class="ranking-qualification ${missing?'':'is-qualified'}"><b>${qualification}</b><progress max="${minimum}" value="${Math.min(minimum,mine?.games||0)}" aria-label="Цели в ${Math.min(minimum,mine?.games||0)} из ${minimum} игр"></progress></div>`:''}
          <div class="ranking-list-heading"><span aria-label="Место">№</span><span>Игрок</span>${combined?'<span class="ranking-games-column">Игры</span>':''}<span>${combined?'Очки':'Результат'}</span></div>
          ${shown.length?`<ol class="ranking-list">${players}</ol>`:'<div class="ranking-empty"><h4>Пока нет результатов</h4><p>Заверши игру в режиме «Соревнование».</p></div>'}
          ${game==='drop'?'<p class="ranking-note">В рейтинге — Космопорт с новой физикой. Прежние партии остались в истории.</p>':''}
          ${combined?`<details class="ranking-rules"><summary>Как получить очки и призы</summary><div class="ranking-rules-content"><h4>Очки за место в каждой игре</h4><div class="ranking-point-key">${E.placePoints.map((points,i)=>`<div><span>${i+1} место</span><strong>${points}</strong></div>`).join('')}</div><p>Начиная с 11-го места — по 5 очков. В общий рейтинг идёт один лучший результат за каждую игру, если выполнена её цель. Для печати нужна точность от 90%.</p><p>Прохождение уровней, XP и достижения дают мастерство, а общий рейтинг считается по результатам «Соревнования».</p><h4>Ранги сезона</h4><ul class="ranking-league-key">${[[0,'Бронза'],[200,'Серебро'],[450,'Золото'],[800,'Алмаз'],[1200,'Космос']].map(([points,name])=>`<li><b>${name}</b><span>от ${points} очков</span></li>`).join('')}</ul><p>Для ранга нужны цели в ${minimum} разных играх в текущем сезоне. Сезон длится 14 дней. Итоги — по понедельникам раз в две недели в 00:00 МСК. При равных очках выше игрок с большим числом игр, затем первых мест, затем с более ранним результатом.</p><p>Клавиатура и касания сравниваются отдельно в скоростных играх; в общий рейтинг идёт один лучший вклад за игру.</p></div></details>`:''}
          ${combined&&winners.length?`<details class="ranking-history"><summary>Победители прошлых сезонов</summary>${winners.map(w=>`<section><h4>${w.days===7?'Неделя':'Сезон'} с ${weekLabel(w.week)}</h4>${w.winners.map(r=>`<div><span>${esc(r.name)}</span><strong>+${r.prize} AC</strong></div>`).join('')}</section>`).join('')}</details>`:''}
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
            if (!host.isConnected || host.dataset.request !== key) return;
            host.innerHTML = `<div class="games-warning" role="alert"><p>${esc(error.message)}</p><button class="arcade-subtle" data-board-retry>Попробовать снова</button></div>`;
            $('[data-board-retry]', host).onclick = () => {
                host.innerHTML = '<div class="arcade-loading" role="status">Загружаем рейтинг…</div>';
                void drawBoard(host, game);
            };
        }
    }
    async function openLeaders(game) {
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
        const p = profile.settings;
        d.innerHTML = `<button class="games-leader-close" aria-label="Закрыть">×</button><h3>Настройки игр</h3><form><label>Качество эффектов<select name="quality"><option value="auto">Автоматически</option><option value="high">Высокое</option><option value="low">Экономное</option></select></label><label class="arcade-check"><input type="checkbox" name="sound" ${p.sound?"checked":""}> Звуки</label><label class="arcade-check"><input type="checkbox" name="vibration" ${p.vibration?"checked":""}> Вибрация</label><button class="games-main">Сохранить</button><p role="status"></p></form>`;
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

    }

    function openGame(id) {
        if (play || window.KopatychFarm?.isOpen || window.ArcadeBenchmarkView?.isOpen()) return;
        device = matchMedia('(pointer:coarse)').matches ? 'touch' : 'keyboard';
        const g = E.games.find(g => g.id === id),
            d = document.createElement("dialog");
        d.id = "gameDialog";
        d.dataset.game = id;
        d.className = "game-dialog";
        d.innerHTML = `<header><button class="game-menu-back" aria-label="Меню игры" hidden>←</button><div><h2>${g.name}</h2></div><button class="game-leaders-button" aria-label="Таблица лидеров">${ArcadeResults.trophy}</button><button class="game-close" aria-label="Закрыть игру">×</button></header><div class="game-hud"><span>Счёт <b id="gameScore">0</b></span><span id="gameClock"></span><span class="game-level" id="gameLevel">Сложность 1</span></div><div class="arcade-live-goal"><span></span><progress value="0" max="${g.goal}"></progress></div><div class="arcade-learning-tip" role="status" hidden></div><div class="journey-tools" hidden><div><b></b><small></small></div><button></button></div><div class="game-stage"></div><footer><span id="gameHint"></span></footer>`;
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
            started: false,
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
        $(".game-close", d).onclick = () => leave(run);
        $(".game-leaders-button", d).onclick = () => openLeaders(id);
        d.addEventListener("cancel", e => {
            e.preventDefault();
            leave(run);
        });
        window.addEventListener("keydown", e => {
            if (e.code !== "Escape" || [...document.querySelectorAll("dialog[open]")].at(-1) !== d) return;
            e.preventDefault();
            e.stopImmediatePropagation();
            leave(run);
        }, {capture: true, signal: run.abort.signal});
    }

    function discard(run) {
        if (!run.started || run.recorded || !run.session) return;
        void api(`/sessions/${run.session.id}/finish`, {
            method: "POST", keepalive: true,
            body: {actions: run.events, ticks: run.world.tick, abandoned: true}
        }).catch(() => {});
    }

    function leave(run) {
        if (play !== run) return;
        if (run.phase === 'playing') catchUp(run);
        if (run.world?.ended && !run.recorded && run.phase !== 'finishing') {
            void finish(run, false);
            return;
        }
        if (run.phase !== 'finishing') discard(run);
        close();
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
        host.innerHTML = g.id==='react'&&screen==='menu'?ArcadeBenchmarkView.hub():screen === 'levels' ? ArcadeMenu.levels(g.id, profile.journeys[g.id], run.selectedJourney) :
            screen === 'arenas' ? ArcadeMenu.arenas(run.arena || 'classic') : ArcadeMenu.home(g);
        host.scrollTop = 0;
        host.onclick = e => {
            const button = e.target.closest('button');
            if (!button || button.disabled) return;
            if(button.dataset.benchmark) {
                const test=button.dataset.benchmark;close();
                void ArcadeBenchmarkView.open(api,test,()=>openGame('react'));return;
            }
            if(button.hasAttribute('data-benchmark-react')){run.menuScreen='reaction';intro(run);return;}
            if (button.hasAttribute('data-menu-levels')) {
                if (g.id === 'kopatych' && window.KopatychFarm) {
                    openGarden();
                } else if (g.id === 'hill') {
                    openGarage();
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
            expedition: !!run.world.expedition,
            skin: run.world.journey ? ['base', 'mint', 'sun', 'nebula', 'mint', 'nebula'][run.world.journey.chapter % 6] : profile.settings.skin,
            theme: run.world.journey ? ['space', 'forest', 'sunset', 'nebula', 'forest', 'nebula'][run.world.journey.chapter % 6] : profile.settings.theme === 'space' ? ({
                bugs: 'forest',
                tower: 'sunset',
                drop: 'nebula',
                runner: 'nebula',
                bubbles: 'forest'
            } [run.g.id] || 'space') : profile.settings.theme,
            quality: () => run.quality || "high",
            phase: () => run.phase,
            paused: () => !["playing", "ready", "tutorial"].includes(run.phase)
        });
        run.view.update(run.world, 0);
        ArcadePersonality.decorate(run);
        ArcadeJourneyView.tools(run);
    }
    async function tutorial(run) {
        cancelAnimationFrame(run.raf);
        run.tutorialActed = false;
        run.hillLesson = 0;
        run.phase = "tutorial";
        run.dialog.classList.remove('is-browsing');
        run.dialog.classList.add('is-learning');
        $('.game-menu-back', run.dialog).hidden = false;
        $('.game-leaders-button', run.dialog).hidden = true;
        run.world = W.create({
            game: run.g.id,
            seed: 41,
            sortRules: 2,
            wordDictionary: 2,
            lessonVersion: 2,
            evolveRules: 2,
            clockRules: 2,
            ...(run.g.id === 'drop' ? {
                dropPhysics: 5,
                arena: run.arena || 'classic'
            } : {}),
            ...(run.g.id === 'hill' ? {
                hill: {
                    route: 'meadow',
                    car: 'scout',
                    upgrades: {}
                }
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
            if (run.tutorialActed && ["orbit", "drop", "bubbles", "hill"].includes(w.id)) W.advance(w, 1);
            run.view.update(w, 1 / 60);
            if (w.id === 'hill' && !run.hillLesson && w.score >= 15) {
                run.hillLesson = 1;
                $('.arcade-learning-tip', run.dialog).textContent = 'Отпусти газ и удерживай тормоз до остановки. В воздухе он опускает нос машины.';
            }
            if (w.id === 'evolve' && w.merges > 0) {
                $('.arcade-learning-tip', run.dialog).textContent = 'Выбери росток на поле, затем нажми «Спасти» на станции';
            }
            if (w.id === 'evolve' ? w.merges > 0 && w.expedition.rescued > 0 : w.id === 'hill' ? run.hillLesson === 1 && w.hill.brake && Math.abs(w.hill.vx) < 2 : window.ArcadeExtras?.tutorialDone(w) ?? (w.score >= (w.id === "typing" ? 3 : 1))) {
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
        $('.game-leaders-button', run.dialog).hidden = true;
        $('footer', run.dialog).hidden = true;
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
                    ...(run.g.id === 'hill' && selectedMode === 'practice' ? {
                        arena: run.arena || 'meadow'
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
        run.finishResult = null;
        run.record = null;
        run.inputQueue = [];
        run.started = false;
        run.device = device;
        run.events = [];
        run.frames = [];
        run.playedMs = 0;
        run.lastCue = 0;
        delete $('#gameClock',run.dialog).dataset.clockText;
        $('#gameClock',run.dialog).classList.remove('is-intermission');
        mount(run);
        $('.game-hud', run.dialog).hidden = false;
        $('.arcade-live-goal', run.dialog).hidden = false;
        run.dialog.scrollTop = 0;
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
        run.started = true;
        if (play !== run) {
            discard(run);
            return;
        }
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
                if (["land", "perfect", "stack", "pair", "correct", "reaction", "merge", "hit", "evolve", "clearLines", "bubblePop", "pour", "sortWin", "wordFound"].includes(cue.type)
                    || cue.type === 'slide' && cue.moves.some(m => m.merged)) feedback(run, cue.type);
            }
        }
        run.view.update(run.world, delta / 1000);
        hud(run);
        run.raf = requestAnimationFrame(t => frame(run, t));
    }

    function feedback(run, type) {
        const now=performance.now();
        if(now-(run.feedbackAt||0)<85)return;
        run.feedbackAt=now;
        if (profile.settings.vibration && navigator.vibrate) navigator.vibrate(type === "perfect" ? [8, 15, 8] : 7);
        if (profile.settings.sound) {
            try {
                run.audio ||= new(window.AudioContext || window.webkitAudioContext)();
                const base={orbit:392,evolve:523,bugs:880,tower:196,debug:659,
                    '2048':330,drop:294,memory:523,react:880,blocks:262,bubbles:784,sort:587,words:659}[run.g.id]||440;
                const notes=['perfect','clearLines','sortWin','victory'].includes(type)?[1,1.25,1.5]:[1];
                notes.forEach((ratio,i)=>{
                    const o=run.audio.createOscillator(),g=run.audio.createGain(),start=run.audio.currentTime+i*.055;
                    o.type=['tower','blocks'].includes(run.g.id)?'triangle':'sine';
                    o.connect(g);g.connect(run.audio.destination);
                    o.frequency.setValueAtTime(base*ratio,start);
                    o.frequency.exponentialRampToValueAtTime(base*ratio*(type==='stack'?.65:1.05),start+.075);
                    g.gain.setValueAtTime(0,start);g.gain.linearRampToValueAtTime(.025,start+.006);
                    g.gain.exponentialRampToValueAtTime(.001,start+.13);
                    o.onended=()=>{o.disconnect();g.disconnect();};o.start(start);o.stop(start+.14);
                });
            } catch {}
        }
    }

    function hud(run) {
        const w = run.world,
            d = run.dialog,
            g = run.g;
        $("#gameScore", d).textContent = w.score;
        $("#gameLevel", d).textContent = `Сложность ${w.level}`;
        if (run.phase !== "ready") {
            const clock=ArcadeClock.view(w),node=$('#gameClock',d),
                value=ArcadeClock.format(clock.kind==='countdown'?Math.ceil(clock.value):clock.value),
                text=clock.label+' '+value;
            if(node.dataset.clockText!==text) {
                node.innerHTML=`<span class="game-clock-caption">${clock.label}</span><b>${value}</b>`;
                node.dataset.clockText=text;
            }
            node.classList.toggle('is-intermission',clock.paused);
            node.setAttribute('aria-label',text);
        }
        if (w.journey) {
            const j = w.journey;
            $('#gameLevel', d).textContent = 'Уровень ' + j.stage;
            $('.arcade-live-goal progress', d).max = j.goal;
            $('.arcade-live-goal progress', d).value = Math.min(j.goal, w.score);
            $('.arcade-live-goal span', d).textContent = ArcadeJourneyView.labels(j) + (j.moves ? ' · осталось ' + Math.max(0, Math.ceil(j.moves - j.movesUsed)) + ' ходов' : '');
            ArcadeJourneyView.tools(run);
            return;
        }
        const q = profile.goals[g.id],
            next = profile.achievements.filter(a => a.game === g.id && !a.unlocked).sort((a, b) => a.tier - b.tier)[0],
            live = ArcadeResults.liveGoal(w, g, q, next, run.mode === 'practice');
        $(".arcade-live-goal progress", d).max = live.target;
        $(".arcade-live-goal progress", d).value = Math.min(live.target, w.score);
        $(".arcade-live-goal span", d).textContent = live.text;
    }
    async function finish(run, abandoned) {
        if (play !== run || ["finishing", "done"].includes(run.phase)) return;
        if (!run.world?.ended) {
            leave(run);
            return;
        }
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
        if(run.view?.settled) {
            // The clock has already ended. Let the last balls land before replacing the board.
            run.view.update(run.world,0);
            let timer;
            await Promise.race([run.view.settled(),new Promise(resolve=>{timer=setTimeout(resolve,1000);})]);
            clearTimeout(timer);
            if(play!==run)return;
        }
        run.viewAbort?.abort();
        run.dialog.classList.add('is-finished');
        $('.game-leaders-button', run.dialog).hidden = false;
        $('.game-hud', run.dialog).hidden = true;
        $('.arcade-live-goal', run.dialog).hidden = true;
        $('.journey-tools', run.dialog).hidden = true;
        $('footer', run.dialog).hidden = true;
        $(".game-pause", run.dialog)?.remove();
        const stage = $(".game-stage", run.dialog),
            cover = document.createElement("div");
        cover.className = "game-result";
        cover.innerHTML = '<div class="arcade-loading">Проверяем результат партии…</div>';
        stage.replaceChildren(cover);
        try {
            const result = run.finishResult || await api(`/sessions/${run.session.id}/finish`, {
                method: "POST",
                body: {
                    actions: run.events,
                    ticks: run.world.tick,
                    abandoned
                }
            });
            run.finishResult = result;
            result.rewards = result.receipt || result.rewards;
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
                ArcadeFeedback.result(run, cover, report);
                if(report.journey.success)feedback(run,'victory');
                if (run.g.id === 'hill') {
                    if (result.garage_coins) $('.arcade-level-result', cover).insertAdjacentHTML('beforeend', `<p class="hill-run-coins">+${result.garage_coins} монет в гараж</p>`);
                    $('.arcade-result-actions', cover).insertAdjacentHTML('beforeend', '<button class="game-back" data-back-garage>В гараж</button>');
                    $('[data-back-garage]', cover).onclick = () => openGarage('missions', report.journey.stage);
                }
                masteryGain(run, cover);
                $('.journey-tools', run.dialog).hidden = true;
                const map = () => {
                    run.selectedJourney = report.journey.success ? Math.min(ArcadeJourney.stageCount(run.g.id), report.journey.stage + 1) : report.journey.stage;
                    if (run.g.id === 'hill') {
                        openGarage('missions', run.selectedJourney);
                        return;
                    }
                    run.phase = 'intro';
                    run.world = null;
                    run.menuScreen = 'levels';
                    intro(run);
                };
                $('[data-journey-next]', cover).onclick = () => !report.journey.success ? begin(run, report.journey.stage) : report.journey.stage < ArcadeJourney.stageCount(run.g.id) ? begin(run, report.journey.stage + 1) : map();
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
            ArcadeFeedback.result(run, cover, report);
            if(run.g.id==='react')cover.insertAdjacentHTML('beforeend','<details class="arcade-result-details"><summary>Сравнение с Human Benchmark</summary><p>На сайте Human Benchmark опубликованы среднее 284 мс и медиана 273 мс. Это ориентир: устройства, задержка экрана и условия теста влияют на результат.</p><a href="https://humanbenchmark.com/tests/reactiontime/statistics" target="_blank" rel="noopener noreferrer">Источник · 06.11.2026</a></details>');
            if(result.run.accepted&&report.score>run.oldBest)feedback(run,'victory');
            if (run.g.id === 'hill') {
                $('.arcade-score-result', cover).insertAdjacentHTML('beforeend', `${report.reason?`<p class="hill-run-reason">${esc(report.reason)}</p>`:''}${result.garage_coins?`<p class="hill-run-coins">+${result.garage_coins} монет в гараж</p>`:''}`);
                $('.arcade-result-actions', cover).insertAdjacentHTML('beforeend', '<button class="game-back" data-back-garage>В гараж</button>');
                $('[data-back-garage]', cover).onclick = () => openGarage('routes', null, run.world.hill.route);
            }
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
            cover.innerHTML = `<h3>${run.recorded?'Результат сохранён':'Не удалось сохранить'}</h3><p>${esc(run.recorded?'Не удалось обновить экран. Попробуй ещё раз.':error.message)}</p><button class="games-main" data-retry>${run.recorded?'Обновить результат':'Повторить отправку'}</button><button class="game-back" data-close>К играм</button>`;
            $("[data-retry]", cover).onclick = () => {
                cover.remove();
                run.phase = "retry";
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
            expedition: !!frames[0]?.expedition,
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
        if (play?.session && !play.recorded && play.started && ["playing", "starting"].includes(play.phase)) {
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
