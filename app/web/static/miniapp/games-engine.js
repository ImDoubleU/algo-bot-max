/* Local prototype domain. No wallet, ledger, MAX or production API writes. */
(() => {
  "use strict";
  const games = [{
    id: "orbit",
    name: "Кот на орбите",
    tag: "Лови момент",
    kind: "fun",
    icon: "orbit",
    color: "violet",
    goal: 8,
    unit: "прыжков",
    hint: "Перепрыгни на 8 планет. Нажимай, когда кот пролетает рядом с лучом к следующей планете."
  }, {
    id: "evolve",
    name: "Космозвери",
    tag: "Экспедиция спасения",
    kind: "puzzle",
    icon: "evolve",
    color: "mint",
    goal: 128,
    unit: "очков",
    hint: "Объединяй одинаковых зверей, спасай тех, кого ждут на станции, и открывай способности видов. Собери 128 очков."
  }, {
    id: "bugs",
    name: "Поймай баг",
    tag: "Тапай быстрее",
    kind: "fun",
    icon: "bugs",
    color: "peach",
    goal: 20,
    unit: "багов",
    hint: "Лови фиолетовых багов, береги роботов. Три жизни, всё более быстрые волны и сколько угодно очков."
  }, {
    id: "tower",
    name: "Высотка",
    tag: "Ровно в центр",
    kind: "fun",
    icon: "tower",
    color: "blue",
    goal: 8,
    unit: "этажей",
    hint: "Нажимай, чтобы поставить блок. Выступающий край отрезается. Построй 8 этажей."
  }, {
    id: "typing",
    name: "Клавиатурный спринт",
    tag: "Пальцы на старт",
    kind: "skill",
    icon: "typing",
    color: "yellow",
    goal: 120,
    unit: "символов",
    hint: "Напечатай 120 верных символов за минуту. Ошибки можно исправлять. Вставка текста отключена."
  }, {
    id: "debug",
    name: "Детектив кода",
    tag: "Найди, что сломалось",
    kind: "skill",
    icon: "debug",
    color: "blue",
    goal: 5,
    unit: "задач",
    hint: "Найди ошибочную строку Python и исправь её. В сложных темах напиши исправление сам. Реши 5 задач из 8."
  }, {
    id: "2048",
    name: "2048",
    tag: "Ещё один ход",
    kind: "puzzle",
    icon: "2048",
    color: "peach",
    goal: 128,
    unit: "плитка",
    hint: "Свайпай или нажимай стрелки. Одинаковые числа складываются. Для награды получи плитку 128."
  }, {
    id: "drop",
    name: "Космодроп",
    tag: "Урони и объедини",
    kind: "fun",
    icon: "drop",
    color: "mint",
    goal: 100,
    unit: "очков",
    hint: "Веди пальцем и отпусти, чтобы бросить. Одинаковые существа сливаются в новое. Не заполняй капсулу выше линии."
  }, {
    id: "memory",
    name: "Перепутанные пары",
    tag: "Помнишь, где кот?",
    kind: "puzzle",
    icon: "memory",
    color: "mint",
    goal: 8,
    unit: "пар",
    hint: "Открывай пары и переходи дальше: от 4 до 12 пар на поле. Для награды найди 8 пар за игру."
  }, {
    id: "react",
    name: "Бенчмарки",
    tag: "Проверь реакцию",
    kind: "skill",
    icon: "react",
    color: "yellow",
    goal: 5,
    unit: "попаданий",
    hint: "Жди зелёный и нажимай. Три раунда: времени на ответ всё меньше. Пять попаданий — первая награда."
  }, ...(window.ArcadeExtras?.games || []).map(g=>g.id==='runner'?window.ArcadeHill.game:g)];
  const achievementRules = [
    ["orbit", "Космический ас", "25 прыжков за одну партию", 25, 35],
    ["evolve", "Создатель вселенных", "2048 очков за одну партию", 2048, 35],
    ["bugs", "Баги под контролем", "Поймай 50 багов за одну партию", 50, 35],
    ["tower", "Небоскрёб", "Построй 25 этажей за одну партию", 25, 35],
    ["typing", "Точно и быстро", "240 символов за минуту с точностью от 95%", 240, 40],
    ["debug", "Шерлок Python", "Реши все 8 задач без ошибок", 8, 35],
    ["2048", "Число силы", "Собери плитку 1024", 1024, 40],
    ["drop", "Космическая гравитация", "1000 очков за одну партию", 1000, 35],
    ["memory", "Фотографическая память", "Пройди все 5 уровней: 40 найденных пар", 40, 40],
    ["react", "Молниеносный", "15 попаданий без ошибок, средняя реакция до 350 мс", 15, 40],
  ];
  const achievements = achievementRules.map(([game, title, detail, target, reward]) => ({
    id: "master2_" + game,
    game,
    title,
    detail,
    target,
    reward,
    metric: state => state.mastery?.[game] || 0,
  }));

  function weekKey(now = new Date()) {
    const m = new Date(now.getTime() + 3 * 3600000);
    const d = new Date(Date.UTC(m.getUTCFullYear(), m.getUTCMonth(), m.getUTCDate()));
    d.setUTCDate(d.getUTCDate() - (d.getUTCDay() + 6) % 7);
    return d.toISOString().slice(0, 10);
  }

  const ranked = games.map(g => g.id);
  const prizes = [100, 75, 50];
  const placePoints = [100, 80, 65, 55, 45, 35, 25, 20, 15, 10];
  const rankUnit = id => id === "orbit" ? "прыжков" : id === "tower" ? "этажей" :
    id === "bugs" ? "багов" : id === "typing" ? "символов" :
    id === "debug" ? "задач" : id === "memory" ? "пар" :
    id === "react" ? "попаданий" : id === "2048" ? "очков" : (games.find(g=>g.id===id)?.unit || "очков");

  // The same curve is used for the HUD, game rules and regression checks.
  function difficulty(id, progress = 0) {
    const p = Math.max(0, Number(progress) || 0);
    const extra = window.ArcadeExtras?.difficulty(id, p);
    if (extra) return extra;
    let level = 1;
    if (id === "orbit") level += Math.floor(p / 5);
    if (id === "evolve") level += Math.floor(p / 8);
    if (id === "bugs") level += Math.floor(p / 10);
    if (id === "tower") level += Math.floor(p / 5);
    if (id === "typing") level += Math.floor(p / 80);
    if (id === "debug") level += Math.floor(p / 2);
    if (id === "2048") level = Math.max(1, Math.floor(Math.log2(Math.max(2, p))) - 2);
    if (id === "drop") level += Math.floor(p / 100);
    if (id === "memory") level = 1 + [4, 10, 18, 28].filter(n => p >= n).length;
    if (id === "react") level += Math.floor(p / 5);
    level = Math.min(id === "debug" || id === "typing" ? 4 : id === "memory" ? 5 :
      id === "react" ? 3 : 10, level);
    const step = level - 1;
    return {
      level,
      orbitSpeed: 1.4 + step * .24,
      orbitWindow: Math.max(.16, .38 - step * .025),
      orbitDrift: level >= 3 ? Math.min(.2, step * .025) : 0,
      pairSeconds: Math.max(7, 20 - step * 1.6),
      bugEvery: Math.max(.24, .8 - step * .055),
      bugLife: Math.max(.78, 2 - step * .13),
      robotChance: Math.min(.42, .15 + step * .03),
      bugSpeed: 12 + step * 7,
      towerSpeed: 100 + step * 29,
      perfectWindow: Math.max(2, 7 - step * .6),
      fourChance: Math.min(.3, .1 + step * .025),
      gravity: 520 + step * 36,
      dropKinds: Math.min(5, 3 + Math.floor(step / 3)),
      dangerLine: 78 + Math.min(32, step * 4),
      pairs: [4, 6, 8, 10, 12][Math.min(4, step)],
      memorySeconds: 50 + step * 5,
      reactionWindow: Math.max(.45, .95 - step * .22),
    };
  }

  function blankBoard() {
    return {
      version: 2,
      all: {},
      weeks: {},
      settled: {}
    };
  }

  function validWeek(key) {
    if (!/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(key)) return false;
    const d = new Date(key + "T00:00:00Z");
    return Number.isFinite(d.getTime()) && d.toISOString().slice(0, 10) === key && d.getUTCDay() === 1;
  }

  function safeInt(v, max = Number.MAX_SAFE_INTEGER) {
    return Number.isFinite(v) ? Math.max(0, Math.min(max, Math.floor(v))) : 0;
  }

  function detailsFor(id, score, input = {}) {
    const result = Number.isFinite(input.result) ? safeInt(input.result) : id === "2048" ? 0 : score;
    return {
      result,
      accuracy: safeInt(input.accuracy, 100),
      timeMs: safeInt(input.timeMs, 86400000),
      moves: safeInt(input.moves, 1000000),
      reactionMs: safeInt(input.reactionMs, 10000),
      mistakes: safeInt(input.mistakes, 1000000),
      qualified: result >= games.find(g => g.id === id).goal && (id !== "typing" || input.accuracy >= 90)
    };
  }

  function compareResult(id, a, b) {
    let n = b.score - a.score;
    if (n) return n;
    if (id === "typing") n = b.accuracy - a.accuracy;
    if (id === "react") n = (a.reactionMs || 10000) - (b.reactionMs || 10000) || a.mistakes - b.mistakes;
    if (id === "memory") n = (a.moves || 1000000) - (b.moves || 1000000);
    if (!n && ["debug", "memory"].includes(id)) n = (a.timeMs || 86400000) - (b.timeMs || 86400000);
    return n;
  }

  function normalizeBoard(raw) {
    const board = blankBoard();
    if (!raw || raw.version !== 2) return board;

    function entries(rows, id) {
      if (!Array.isArray(rows)) return [];
      const unique = new Map();
      for (const r of rows) {
        if (!r || typeof r.player !== "string" || !r.player || r.player.length > 100 || typeof r.name !==
          "string" ||
          !Number.isSafeInteger(r.score) || r.score <= 0 || !Number.isFinite(Date.parse(r.at))) continue;
        const item = {
          player: r.player,
          name: r.name.slice(0, 80),
          group: String(r.group || "").slice(0, 140),
          score: r.score,
          level: Math.max(1, Math.min(10, safeInt(r.level))),
          at: r.at,
          ...detailsFor(id, r.score, r)
        };
        if (!unique.has(r.player) || compareResult(id, item, unique.get(r.player)) < 0) unique.set(r.player,
          item);
      }
      return [...unique.values()].slice(0, 2000);
    }
    for (const id of ranked) board.all[id] = entries(raw.all?.[id], id);
    for (const [key, scores] of Object.entries(raw.weeks || {})) {
      if (!validWeek(key)) continue;
      board.weeks[key] = {};
      for (const id of ranked) board.weeks[key][id] = entries(scores?.[id], id);
    }
    for (const [key, closed] of Object.entries(raw.settled || {})) {
      if (!validWeek(key) || closed?.rule !== 1 || !Array.isArray(closed.winners) || !Number.isFinite(Date
          .parse(closed.at))) continue;
      const winners = closed.winners.filter(r => r && typeof r.player === "string" && typeof r.name ===
        "string" &&
        Number.isInteger(r.rank) && r.rank >= 1 && r.rank <= 3 && r.amount === prizes[r.rank - 1]);
      const seenPlayers = new Set(),
        seenRanks = new Set();
      board.settled[key] = {
        rule: 1,
        at: closed.at,
        winners: winners.filter(r => {
          if (seenPlayers.has(r.player) || seenRanks.has(r.rank)) return false;
          seenPlayers.add(r.player);
          seenRanks.add(r.rank);
          return true;
        }).slice(0, 3).map(r => ({
          ...r,
          id: `league:${key}:${r.player}`
        }))
      };
    }
    return board;
  }

  function recordBoard(board, id, player, score, level = 1, now = new Date(), details = {}) {
    if (!ranked.includes(id) || !player?.id || !player.name || !Number.isSafeInteger(score) || score <= 0 ||
      board.settled[weekKey(now)] || ({
        debug: 8,
        memory: 40,
        react: 15
      } [id] && score > {
        debug: 8,
        memory: 40,
        react: 15
      } [id])) return false;
    const row = {
      player: String(player.id).slice(0, 100),
      name: String(player.name).slice(0, 80),
      group: String(player.group || "").slice(0, 140),
      score,
      level,
      at: now.toISOString(),
      ...detailsFor(id, score, details)
    };
    const w = board.weeks[weekKey(now)] ||= ({});
    let changed = false;
    for (const container of [board.all, w]) {
      const rows = container[id] ||= [],
        i = rows.findIndex(r => r.player === row.player);
      if (i < 0) {
        rows.push({
          ...row
        });
        changed = true;
      } else if (compareResult(id, row, rows[i]) < 0) {
        rows[i] = {
          ...row
        };
        changed = true;
      }
    }
    return changed;
  }

  function rankRows(rows, comparator, equal) {
    let rank = 0,
      previous;
    return rows.slice().sort(comparator).map((r, i) => {
      if (!previous || !equal(r, previous)) rank = i + 1;
      previous = r;
      return {
        ...r,
        rank
      };
    });
  }

  function leaders(board, id, period = "week", now = new Date(), key = weekKey(now)) {
    if (!ranked.includes(id)) return [];
    const rows = (period === "all" ? board.all[id] : board.weeks[key]?.[id]) || [];
    return rankRows(rows, (a, b) => compareResult(id, a, b) || a.at.localeCompare(b.at) || a.player
      .localeCompare(b.player),
      (a, b) => compareResult(id, a, b) === 0);
  }

  function overall(board, period = "week", now = new Date(), key = weekKey(now)) {
    const people = new Map();
    for (const id of ranked) {
      // Only results meeting the weekly goal take part in the combined league.
      const qualified = leaders(board, id, period, now, key).filter(r => r.qualified);
      const table = rankRows(qualified, (a, b) => compareResult(id, a, b) || a.at.localeCompare(b.at),
        (a, b) => compareResult(id, a, b) === 0);
      for (const row of table) {
        const points = placePoints[row.rank - 1] || 5;
        if (!people.has(row.player)) people.set(row.player, {
          player: row.player,
          name: row.name,
          group: row.group,
          score: 0,
          games: 0,
          wins: 0,
          at: row.at,
          contributions: []
        });
        const person = people.get(row.player);
        person.score += points;
        person.games++;
        if (row.rank === 1) person.wins++;
        if (row.at > person.at) person.at = row.at;
        person.contributions.push({
          game: id,
          rank: row.rank,
          points,
          result: row.score,
          ...detailsFor(id, row.score, row)
        });
      }
    }
    return [...people.values()].sort((a, b) => b.score - a.score || b.games - a.games || b.wins - a.wins ||
      a.at.localeCompare(b.at) || a.player.localeCompare(b.player)).map((r, i) => ({
      ...r,
      rank: i + 1
    }));
  }

  function settleBoard(board, now = new Date()) {
    const current = weekKey(now),
      closed = [];
    for (const key of Object.keys(board.weeks).sort()) {
      if (!validWeek(key) || key >= current || board.settled[key]) continue;
      const rows = overall(board, "week", now, key);
      board.settled[key] = {
        rule: 1,
        at: now.toISOString(),
        winners: rows.slice(0, 3).map(r => ({
          player: r.player,
          name: r.name,
          rank: r.rank,
          points: r.score,
          amount: prizes[r.rank - 1],
          id: `league:${key}:${r.player}`
        }))
      };
      closed.push(key);
    }
    return closed;
  }

  function blank() {
    return {
      version: 2,
      runs: 0,
      best: {},
      mastery: {},
      weeks: {},
      unlocked: {},
      claimed: {},
      transactions: [],
      prizeClaims: {}
    };
  }

  function normalize(raw) {
    const state = blank();
    if (!raw || raw.version !== 2) return state;
    state.runs = safeInt(raw.runs);
    for (const game of games) {
      if (Number.isFinite(raw.best?.[game.id])) state.best[game.id] = safeInt(raw.best[game.id]);
      if (Number.isFinite(raw.mastery?.[game.id])) state.mastery[game.id] = safeInt(raw.mastery[game.id]);
      if (!["typing", "react"].includes(game.id)) state.mastery[game.id] = Math.max(state.mastery[game
        .id] || 0, state.best[game.id] || 0);
    }
    for (const [key, w] of Object.entries(raw.weeks || {})) {
      if (!validWeek(key) || !w || typeof w !== "object") continue;
      state.weeks[key] = {
        scores: {},
        claimed: {}
      };
      for (const game of games) {
        if (Number.isFinite(w.scores?.[game.id])) state.weeks[key].scores[game.id] = safeInt(w.scores[game
          .id]);
        if (w.claimed?.[game.id] === true) state.weeks[key].claimed[game.id] = true;
      }
    }
    for (const a of achievements) {
      if (raw.unlocked?.[a.id]) state.unlocked[a.id] = String(raw.unlocked[a.id]);
      if (raw.claimed?.[a.id] === true) state.claimed[a.id] = true;
    }
    for (const [key, prize] of Object.entries(raw.prizeClaims || {})) {
      if (!/^league:\d{4}-\d{2}-\d{2}:.+$/.test(key) || !prize ||
        !Number.isInteger(prize.rank) || prize.rank < 1 || prize.rank > 3 || prize.amount !== prizes[prize
          .rank - 1]) continue;
      state.prizeClaims[key] = {
        rank: prize.rank,
        amount: prize.amount,
        week: String(prize.week)
      };
    }
    state.transactions = Array.isArray(raw.transactions) ? raw.transactions.filter(t => t && typeof t
      .label ===
      "string" &&
      Number.isFinite(t.amount) && t.amount > 0 && typeof t.at === "string").slice(0, 300) : [];
    return state;
  }

  function week(state, now) {
    return state.weeks[weekKey(now)] ||= {
      scores: {},
      claimed: {}
    };
  }

  function unlockAchievements(state, now = new Date()) {
    const unlocked = [];
    for (const a of achievements)
      if (!state.unlocked[a.id] && a.metric(state) >= a.target) {
        state.unlocked[a.id] = now.toISOString();
        unlocked.push(a.id);
      }
    return unlocked;
  }

  function finish(state, id, score, now = new Date(), details = {}) {
    if (!games.some(g => g.id === id) || !Number.isSafeInteger(score) || score < 0) return [];
    state.runs++;
    state.best[id] = Math.max(state.best[id] || 0, score);
    const w = week(state, now);
    w.scores[id] = Math.max(w.scores[id] || 0, score);
    const qualifies = id === "typing" ? details.accuracy >= 95 : id === "react" ?
      details.mistakes === 0 && details.reactionMs > 0 && details.reactionMs <= 350 : true;
    if (qualifies) state.mastery[id] = Math.max(state.mastery[id] || 0, score);
    return unlockAchievements(state, now);
  }

  function claim(state, type, id, now = new Date()) {
    let amount, label;
    if (type === "week") {
      const game = games.find(g => g.id === id),
        w = week(state, now);
      if (!game || w.claimed[id] || (w.scores[id] || 0) < game.goal) return 0;
      w.claimed[id] = true;
      amount = 10;
      label = game.name + " · награда недели";
    } else if (type === "achievement") {
      const a = achievements.find(a => a.id === id);
      if (!a || !state.unlocked[id] || state.claimed[id]) return 0;
      state.claimed[id] = true;
      amount = a.reward;
      label = a.title + " · достижение";
    } else return 0;
    state.transactions.unshift({
      label,
      amount,
      at: now.toISOString()
    });
    return amount;
  }

  function collectPrizes(state, board, player, now = new Date()) {
    let received = 0;
    for (const [key, closed] of Object.entries(board.settled)) {
      if (key >= weekKey(now)) continue;
      for (const row of closed.winners) {
        if (row.player !== player || state.prizeClaims[row.id] || row.rank < 1 || row.rank > 3 ||
          row.amount !== prizes[row.rank - 1] || row.id !== `league:${key}:${row.player}`) continue;
        state.prizeClaims[row.id] = {
          week: key,
          rank: row.rank,
          amount: row.amount
        };
        received += row.amount;
        state.transactions.unshift({
          label: `Общий рейтинг · ${row.rank}-е место · неделя ${key}`,
          amount: row.amount,
          at: now.toISOString()
        });
      }
    }
    return received;
  }

  function balance(state) {
    return Object.values(state.weeks).reduce((n, w) => n + Object.keys(w.claimed).length * 10, 0) +
      achievements.reduce((n, a) => n + (state.claimed[a.id] ? a.reward : 0), 0) +
      Object.values(state.prizeClaims).reduce((n, r) => n + r.amount, 0);
  }

  function slide(board, direction) {
    const out = board.slice();
    const moves = [];
    let score = 0;
    for (let n = 0; n < 4; n++) {
      const indexes = Array.from({
          length: 4
        }, (_, i) => direction === "left" ? n * 4 + i : direction === "right" ? n * 4 + 3 - i :
        direction === "up" ? i * 4 + n : (3 - i) * 4 + n);
      const line = indexes.filter(i => board[i]).map(i => ({
          value: board[i],
          from: i
        })),
        merged = [];
      for (let i = 0; i < line.length; i++) {
        const to = indexes[merged.length];
        if (line[i].value === line[i + 1]?.value) {
          merged.push(line[i].value * 2);
          score += line[i].value * 2;
          moves.push({
            ...line[i],
            to,
            merged: true
          }, {
            ...line[i + 1],
            to,
            merged: true
          });
          i++;
        } else {
          merged.push(line[i].value);
          moves.push({
            ...line[i],
            to,
            merged: false
          });
        }
      }
      indexes.forEach((idx, i) => out[idx] = merged[i] || 0);
    }
    return {
      board: out,
      score,
      moves,
      changed: out.some((v, i) => v !== board[i])
    };
  }

  function canMove(board) {
    return ["left", "right", "up", "down"].some(d => slide(board, d).changed);
  }
  const tasks = [{
    intro: "Выведи приветствие",
    lines: ['name = "Миша"', 'print("Привет, " + Name)'],
    line: 1,
    options: ['print("Привет, " + name)', 'print("Привет, " - name)', 'Print("Привет, " + name)'],
    answer: 0,
    why: "Имена name и Name различаются: Python учитывает регистр."
  }, {
    intro: "Посчитай сумму двух чисел",
    lines: ['a = 7', 'b = 5', 'print(a - b)'],
    line: 2,
    options: ['print(a / b)', 'print(a + b)', 'print(a * b)'],
    answer: 1,
    why: "Для суммы нужен знак +."
  }, {
    intro: "Выведи «Победа», если счёт больше 10",
    lines: ['score = 15', 'if score > 10', '    print("Победа")'],
    line: 1,
    options: ['if score > 10;', 'if score > 10:', 'if score = 10:'],
    answer: 1,
    why: "В конце условия if ставится двоеточие."
  }, {
    intro: "Выведи первый цвет из списка",
    lines: ['colors = ["синий", "белый", "жёлтый"]', 'print(colors[1])'],
    line: 1,
    options: ['print(colors[3])', 'print(colors[0])', 'print(colors.first)'],
    answer: 1,
    why: "Нумерация элементов списка начинается с нуля."
  }, {
    intro: "Выведи числа от 1 до 5 включительно",
    lines: ['for i in range(1, 5):', '    print(i)'],
    line: 0,
    options: ['for i in range(1, 6):', 'for i in range(0, 5):', 'for i in range(5, 1):'],
    answer: 0,
    why: "Правая граница range не включается."
  }, {
    intro: "Сложи возраст из строки с числом",
    lines: ['age = "10"', 'print(age + 1)'],
    line: 1,
    options: ['print(age + "1")', 'print(int(age) + 1)', 'print(str(age + 1))'],
    answer: 1,
    why: "Сначала превращаем строку в число с помощью int()."
  }, {
    intro: "Проверь, равно ли число пяти",
    lines: ['x = 5', 'if x = 5:', '    print("Да")'],
    line: 1,
    options: ['if x == 5:', 'if x === 5:', 'if x != 5:'],
    answer: 0,
    why: "Сравнение — это ==, а одиночный = присваивает значение."
  }, {
    intro: "Верни удвоенное число",
    lines: ['def double(x):', '    result = x * 2', 'print(double(4))'],
    line: 1,
    options: ['    print(x * 2)', '    return x * 2', '    return x + 2'],
    answer: 1,
    why: "Чтобы функция вернула результат, нужен return."
  }, ];
  window.AlgoGameEngine = {
    prizes,
    placePoints,
    overall,
    settleBoard,
    collectPrizes,
    balance,
    unlockAchievements,
    ranked,
    rankUnit,
    difficulty,
    blankBoard,
    normalizeBoard,
    recordBoard,
    leaders,
    games,
    achievements,
    weekKey,
    blank,
    normalize,
    week,
    finish,
    claim,
    slide,
    canMove,
    tasks
  };
})();
