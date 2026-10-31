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
    tag: "Открой нового",
    kind: "puzzle",
    icon: "evolve",
    color: "mint",
    goal: 128,
    unit: "очков",
    hint: "Выбери двух одинаковых зверей — они станут одним новым. На поиск пары даётся время. Собери 128 очков."
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
    name: "Башня из хлама",
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
    hint: "Найди ошибочную строку Python, затем выбери исправление. Реши 5 задач из 8."
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
    name: "Космо-дроп",
    tag: "Урони и объедини",
    kind: "fun",
    icon: "drop",
    color: "violet",
    goal: 100,
    unit: "очков",
    hint: "Выбирай место и роняй предмет. Одинаковые объединяются. Не заполняй поле выше линии."
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
    name: "Не жми на красное",
    tag: "Проверь реакцию",
    kind: "skill",
    icon: "react",
    color: "yellow",
    goal: 5,
    unit: "попаданий",
    hint: "Жди зелёный и нажимай. Три раунда: времени на ответ всё меньше. Пять попаданий — награда недели."
  }, ];
  const achievements = [{
    id: "first",
    title: "Поехали!",
    detail: "Заверши первую игру",
    reward: 15,
    target: 1,
    metric: s => s.runs
  }, {
    id: "explorer",
    title: "Везде свой",
    detail: "Сыграй в 5 разных игр",
    reward: 20,
    target: 5,
    metric: s => Object.keys(s.best).length
  }, {
    id: "all",
    title: "Вся коллекция",
    detail: "Сыграй во все 10 игр",
    reward: 40,
    target: 10,
    metric: s => Object.keys(s.best).length
  }, {
    id: "orbit",
    title: "Космокот",
    detail: "Сделай 15 прыжков за партию",
    reward: 20,
    target: 15,
    metric: s => s.best.orbit || 0
  }, {
    id: "tower",
    title: "Выше крыши",
    detail: "Построй башню из 15 этажей",
    reward: 20,
    target: 15,
    metric: s => s.best.tower || 0
  }, {
    id: "typing",
    title: "Быстрые пальцы",
    detail: "Напечатай 200 верных символов",
    reward: 25,
    target: 200,
    metric: s => s.best.typing || 0
  }, {
    id: "debug",
    title: "Шерлок Python",
    detail: "Реши все 8 задач за партию",
    reward: 25,
    target: 8,
    metric: s => s.best.debug || 0
  }, {
    id: "2048",
    title: "Число силы",
    detail: "Собери плитку 512",
    reward: 25,
    target: 512,
    metric: s => s.best["2048"] || 0
  }, {
    id: "drop",
    title: "Гравитация работает",
    detail: "Набери 300 очков в Космо-дропе",
    reward: 25,
    target: 300,
    metric: s => s.best.drop || 0
  }, {
    id: "week",
    title: "Неделя приключений",
    detail: "Выполни цели 5 игр за одну неделю",
    reward: 30,
    target: 5,
    metric: s => Math.max(0, ...Object.values(s.weeks).map(w => games.filter(g => (w.scores[g.id] ||
      0) >= g.goal).length))
  }, ];

  function weekKey(now = new Date()) {
    const m = new Date(now.getTime() + 3 * 3600000);
    const d = new Date(Date.UTC(m.getUTCFullYear(), m.getUTCMonth(), m.getUTCDate()));
    d.setUTCDate(d.getUTCDate() - (d.getUTCDay() + 6) % 7);
    return d.toISOString().slice(0, 10);
  }

  const ranked = ["orbit", "evolve", "bugs", "tower", "2048", "drop"];
  const rankUnit = id => id === "orbit" ? "прыжков" : id === "tower" ? "этажей" :
    id === "bugs" ? "багов" : "очков";

  // The same curve is used for the HUD, game rules and regression checks.
  function difficulty(id, progress = 0) {
    const p = Math.max(0, Number(progress) || 0);
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
      version: 1,
      all: {},
      weeks: {}
    };
  }

  function normalizeBoard(raw) {
    const board = blankBoard();
    if (!raw || raw.version !== 1) return board;

    function entries(rows) {
      if (!Array.isArray(rows)) return [];
      const valid = rows.filter(r => r && typeof r.player === "string" && r.player.length <= 100 &&
        typeof r.name === "string" && Number.isSafeInteger(r.score) && r.score > 0 &&
        Number.isFinite(Date.parse(r.at)));
      const unique = new Map();
      for (const r of valid) {
        const item = {
          player: r.player,
          name: r.name.slice(0, 80),
          group: String(r.group || "").slice(0, 140),
          score: r.score,
          level: Math.max(1, Math.min(10, Math.floor(Number(r.level) || 1))),
          at: r.at
        };
        if (!unique.has(r.player) || unique.get(r.player).score < r.score) unique.set(r.player, item);
      }
      return [...unique.values()].slice(0, 2000);
    }
    for (const id of ranked) board.all[id] = entries(raw.all?.[id]);
    for (const [key, scores] of Object.entries(raw.weeks || {})) {
      if (!/^\d{4}-\d{2}-\d{2}$/.test(key)) continue;
      board.weeks[key] = {};
      for (const id of ranked) board.weeks[key][id] = entries(scores?.[id]);
    }
    return board;
  }

  function recordBoard(board, id, player, score, level = 1, now = new Date()) {
    if (!ranked.includes(id) || !player?.id || !player.name ||
      !Number.isSafeInteger(score) || score <= 0) return false;
    const row = {
      player: String(player.id),
      name: String(player.name).slice(0, 80),
      group: String(player.group || "").slice(0, 140),
      score,
      level,
      at: now.toISOString()
    };
    const w = board.weeks[weekKey(now)] ||= {};
    let changed = false;
    for (const container of [board.all, w]) {
      const rows = container[id] ||= [],
        index = rows.findIndex(r => r.player === row.player);
      if (index < 0) {
        rows.push({
          ...row
        });
        changed = true;
      } else if (rows[index].score < score) {
        rows[index] = {
          ...row
        };
        changed = true;
      }
    }
    return changed;
  }

  function leaders(board, id, period = "week", now = new Date()) {
    if (!ranked.includes(id)) return [];
    const rows = (period === "all" ? board.all[id] : board.weeks[weekKey(now)]?.[id]) || [];
    let rank = 0,
      previous = -1;
    return rows.slice().sort((a, b) => b.score - a.score || a.at.localeCompare(b.at) ||
      a.player.localeCompare(b.player)).map((r, i) => {
      if (r.score !== previous) rank = i + 1;
      previous = r.score;
      return {
        ...r,
        rank
      };
    });
  }

  function blank() {
    return {
      version: 1,
      runs: 0,
      best: {},
      weeks: {},
      unlocked: {},
      claimed: {},
      transactions: []
    };
  }

  function normalize(raw) {
    const s = blank();
    if (!raw || raw.version !== 1) return s;
    s.runs = Math.max(0, Math.floor(Number(raw.runs) || 0));
    for (const g of games)
      if (Number.isFinite(raw.best?.[g.id])) s.best[g.id] = Math.max(0, raw.best[g.id]);
    for (const [key, w] of Object.entries(raw.weeks || {})) {
      if (!/^\d{4}-\d{2}-\d{2}$/.test(key) || !w || typeof w !== "object") continue;
      s.weeks[key] = {
        scores: {},
        claimed: {}
      };
      for (const g of games) {
        if (Number.isFinite(w.scores?.[g.id])) s.weeks[key].scores[g.id] = Math.max(0, w.scores[g.id]);
        if (w.claimed?.[g.id] === true) s.weeks[key].claimed[g.id] = true;
      }
    }
    for (const a of achievements) {
      if (raw.unlocked?.[a.id]) s.unlocked[a.id] = String(raw.unlocked[a.id]);
      if (raw.claimed?.[a.id] === true) s.claimed[a.id] = true;
    }
    s.transactions = Array.isArray(raw.transactions) ? raw.transactions.filter(t => typeof t.label ===
      "string" && Number.isFinite(t.amount) && t.amount > 0 && typeof t.at === "string").slice(0, 300) :
    [];
    return s;
  }

  function week(s, now) {
    return s.weeks[weekKey(now)] ||= {
      scores: {},
      claimed: {}
    };
  }

  function finish(s, id, score, now = new Date()) {
    if (!games.some(g => g.id === id) || !Number.isFinite(score) || score < 0) return [];
    s.runs++;
    s.best[id] = Math.max(s.best[id] || 0, Math.floor(score));
    const w = week(s, now);
    w.scores[id] = Math.max(w.scores[id] || 0, Math.floor(score));
    const unlocked = [];
    for (const a of achievements)
      if (!s.unlocked[a.id] && a.metric(s) >= a.target) {
        s.unlocked[a.id] = now.toISOString();
        unlocked.push(a.id);
      }
    return unlocked;
  }

  function claim(s, type, id, now = new Date()) {
    let amount, label;
    if (type === "week") {
      const g = games.find(g => g.id === id),
        w = week(s, now);
      if (!g || w.claimed[id] || (w.scores[id] || 0) < g.goal) return 0;
      w.claimed[id] = true;
      amount = 10;
      label = g.name + " · награда недели";
    } else if (type === "achievement") {
      const a = achievements.find(a => a.id === id);
      if (!a || !s.unlocked[id] || s.claimed[id]) return 0;
      s.claimed[id] = true;
      amount = a.reward;
      label = a.title + " · достижение";
    } else return 0;
    s.transactions.unshift({
      label,
      amount,
      at: now.toISOString()
    });
    return amount;
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
