/* Six deterministic arcade games. Every reward is still verified by arcade.py. */
(() => {
  "use strict";
  const games = [{
    id: "kopatych",
    persistent: true,
    name: "Кликер Копатыча",
    tag: "Морковки растут сами",
    kind: "fun",
    icon: "kopatych",
    color: "yellow",
    goal: 300,
    unit: "морковок",
    seconds: 90,
    tutorial: "Нажми на Копатыча — собери первую морковку",
    hint: "Собирай морковки за 90 секунд. Улучшай лопату и грядки, лови золотой урожай и держи серию нажатий."
  }, {
    id: "blocks",
    name: "Блоки в ряд",
    tag: "Уложи красиво",
    kind: "puzzle",
    icon: "blocks",
    color: "blue",
    goal: 300,
    unit: "очков",
    tutorial: "Выбери одиночный блок и закрой последнюю клетку нижнего ряда",
    hint: "Выбери фигуру снизу и поставь её на поле 8×8. Полные строки и столбцы исчезают. Расходуй все три фигуры, чтобы получить новые."
  }, {
    id: "runner",
    name: "Геометрический рывок",
    tag: "Прыжок в ритм",
    kind: "fun",
    icon: "runner",
    color: "violet",
    goal: 15,
    unit: "преград",
    tutorial: "Пробел или нажатие на поле — прыгни через шипы",
    hint: "Куб бежит сам. Нажимай или жми пробел, чтобы перепрыгивать шипы. Дальше — быстрее, шире препятствия и меньше времени на прыжок."
  }, {
    id: "bubbles",
    name: "Бабл-шутер",
    tag: "Один точный выстрел",
    kind: "fun",
    icon: "bubbles",
    color: "peach",
    goal: 200,
    unit: "очков",
    tutorial: "Выстрели рядом с двумя сиреневыми шарами наверху",
    hint: "Прицелься и выстрели. Три шара одного цвета лопаются, оторванные от потолка падают. Пять промахов опускают потолок."
  }, {
    id: "sort",
    name: "Шарики в колбах",
    tag: "Наведи порядок",
    kind: "puzzle",
    icon: "sort",
    color: "mint",
    goal: 3,
    unit: "уровня",
    tutorial: "Нажми на первую колбу, затем на вторую — одинаковые цвета собираются вместе",
    hint: "Выбери колбу, затем колбу назначения. Переносить можно верхние шарики в пустую колбу или на такой же цвет. Собери каждый цвет отдельно."
  }, {
    id: "words",
    name: "Слова из слова",
    tag: "Собери больше",
    kind: "skill",
    icon: "words",
    color: "yellow",
    goal: 10,
    unit: "слов",
    seconds: 180,
    tutorial: "Из букв «КОСМОС» собери «СОМ» и нажми «Проверить»",
    hint: "Составляй существительные от трёх букв. Каждая буква используется столько раз, сколько есть в исходном слове. Восемь слов открывают следующую подборку."
  }];
  games.forEach(game => { game.fresh = true; });
  const ids = new Set(games.map(g => g.id)),
    colors = ["#b8a1ed", "#cce994", "#f2b28e", "#91cbe6", "#ec9dbd", "#f1d17f", "#84d7bb", "#b5b9fb"];
  const shapes = [
    [
      [0, 0]
    ],
    [
      [0, 0],
      [1, 0]
    ],
    [
      [0, 0],
      [0, 1]
    ],
    [
      [0, 0],
      [1, 0],
      [2, 0]
    ],
    [
      [0, 0],
      [0, 1],
      [0, 2]
    ],
    [
      [0, 0],
      [1, 0],
      [0, 1],
      [1, 1]
    ],
    [
      [0, 0],
      [1, 0],
      [2, 0],
      [1, 1]
    ],
    [
      [0, 0],
      [0, 1],
      [1, 1]
    ],
    [
      [0, 0],
      [1, 0],
      [1, 1]
    ],
    [
      [0, 0],
      [1, 0],
      [2, 0],
      [3, 0]
    ],
    [
      [0, 0],
      [0, 1],
      [0, 2],
      [0, 3]
    ],
    [
      [0, 0],
      [1, 0],
      [2, 0],
      [0, 1],
      [1, 1],
      [2, 1]
    ],
    [
      [0, 0],
      [1, 0],
      [2, 0],
      [0, 1],
      [1, 1],
      [2, 1],
      [0, 2],
      [1, 2],
      [2, 2]
    ]
  ];
  const rawPacks = [
    ["КОСМОНАВТИКА", "космос коса космонавт кот том ток ком сом сок нос сон мост мот моток комок станок канат танк нота кино камин вино маска мотив атом сотка такси такса канва скат вокал тонна икона нитка тоска матка мина сомик канава"],
    ["ЭЛЕКТРОСТАНЦИЯ", "кот ток рот рост сорт трос торт трон кран крот трек слон лес сон нос сок лот лектор орел орёл река крем экран танец цена лицо цикл акция секция станция лекция концерт стрелка костер костёр клетка тост катер стена лето тело село сено скат сетка треск тонна"],
    ["ПРОГРАММИРОВАНИЕ", "мир пир мор рог маг миг гора игра рама нора мера мама грамм вагон ворон роман помарка манго пион пена вена мина вино право правило ремонт порог погром моргание ранение мнение вера орнамент равнина программа прогон регион"],
    ["ПУТЕШЕСТВЕННИК", "путь путник шут тень пень кит тип тик нут внук куст кустик теннис спутник шип шнур пунш винт век вес свет степь ступень пение утешение шест шесть вестник шептун птенец пение невеста"],
    ["МАТЕМАТИКА", "мат мак кит тик такт тема метка атака катет матка мим мина атом мама акт макака акме математика макет тамада тактика"],
    ["КОНСТРУКТОР", "кот ток тон нос сон сок рот рок крот трон торт трос сорт рост укор урок куст кнут ноктюрн курорт трус стук строка конструктор конус контур конкурс кокон сток корт торс крокус"],
    ["ПРОСТОКВАШИНО", "кот ток нос сон сок рот рок пот топ вор ров пир тир кит рис шок шип парк кран порт тропа вино кино окно каша нора пора торс тина икра квас покос носок остров покров крошка ковш кожа рост сорт трос спор спорт порошок"],
    ["ВЕЛОСИПЕДИСТ", "лес вес вид лед лёд лис лев вол велосипед след совет свет свод слепок тело село сито седло депо поле повод поезд диспетчер сет вето подвес липа полис плед пилот привет довесок повод велосипедист"]
  ];

  function bag(s) {
    const b = {};
    for (const ch of s.toLowerCase().replace(/ё/g, "е")) b[ch] = (b[ch] || 0) + 1;
    return b;
  }

  function fitsWord(word, root) {
    const b = bag(root);
    return [...word].every(ch => b[ch]-- > 0);
  }
  const packs = rawPacks.map(([root, text]) => ({
    root,
    answers: [...new Set(text.split(" ").map(w => w.replace(/ё/g, "е")))].filter(w => w.length >= 3 && w.length < root.length && fitsWord(w, root))
  }));

  function difficulty(id, p) {
    if (!ids.has(id)) return null;
    const unit = {
      kopatych: 200,
      blocks: 250,
      runner: 8,
      bubbles: 200,
      sort: 1,
      words: 8
    } [id];
    return {
      level: Math.min(10, 1 + Math.floor(p / unit))
    };
  }

  function dealBlocks(w, H) {
    const choices = shapes.slice(0, Math.min(shapes.length, 8 + w.level + (w.journey?.variant===3?3:0)));
    w.pieces = Array.from({
      length: 3
    }, () => H.pick(w, choices).map(a => a.slice()));
    w.pieceColors = Array.from({
      length: 3
    }, () => Math.floor(H.random(w) * 6) + 1);
    w.selectedPiece = 0;
  }

  function fitsBlock(w, p, x, y) {
    return p && p.every(([dx, dy]) => x + dx >= 0 && x + dx < 8 && y + dy >= 0 && y + dy < 8 && !w.blockBoard[(y + dy) * 8 + x + dx]);
  }

  function blocksAvailable(w) {
    return w.pieces.some(piece=>{
      if(!piece)return false;
      let p=piece;
      const turns=w.journey?Math.min(3,w.journey.charges-w.journey.used):0;
      for(let turn=0;turn<=turns;turn++){
        if(Array.from({length:64},(_,i)=>fitsBlock(w,p,i%8,Math.floor(i/8))).some(Boolean))return true;
        const rotated=p.map(([x,y])=>[-y,x]),minX=Math.min(...rotated.map(v=>v[0])),minY=Math.min(...rotated.map(v=>v[1]));
        p=rotated.map(([x,y])=>[x-minX,y-minY]);
      }
      return false;
    });
  }

  function tubeDone(t) {
    return t.length === 4 && t.every(c => c === t[0]);
  }

  function sortSolved(w) {
    return w.tubes.every(t => !t.length || tubeDone(t));
  }

  function sortMoves(w) {
    return w.tubes.flatMap((from, i) => w.tubes.map((to, j) => ({
      i,
      j,
      ok: i !== j && from.length && to.length < 4 && (!to.length || to.at(-1) === from.at(-1))
    }))).filter(m => m.ok);
  }

  function sortRound(w, H) {
    const count = Math.min(7, 3 + w.score + (w.journey ? Math.floor(w.journey.chapter/2)+(w.journey.variant===2?1:0) : 0));
    w.tubes = Array.from({
      length: count
    }, (_, i) => [i, i, i, i]).concat([
      [],
      []
    ]);
    w.sortSolution = [];
    let previous = null;
    for (let n = 0; n < 35 + count * 18; n++) {
      const candidates = [];
      w.tubes.forEach((from, i) => {
        if (!from.length || from.length > 1 && from.at(-2) !== from.at(-1)) return;
        w.tubes.forEach((to, j) => {
          if (i !== j && to.length < 4 && !(previous && previous.i === j && previous.j === i)) candidates.push({
            i,
            j
          });
        });
      });
      if (!candidates.length) break;
      const move = H.pick(w, candidates),
        color = w.tubes[move.i].pop();
      w.tubes[move.j].push(color);
      w.sortSolution.unshift({
        type: "pour",
        from: move.j,
        to: move.i,
        single: true
      });
      previous = move;
    }
    if (sortSolved(w)) {
      const c = w.tubes[0].pop();
      w.tubes[count].push(c);
      w.sortSolution.unshift({
        type: "pour",
        from: count,
        to: 0,
        single: true
      });
    }
    w.sortStart = w.tubes.map(t => t.slice());
    w.sortUndo = [];
    w.selectedTube = -1;
    w.roundMoves = 0;
    w.sortWon = false;
    w.sortMessage = "";
  }

  function wordRound(w) {
    w.wordPack = packs[w.packOrder[w.wordRound % w.packOrder.length]];
    w.roundWords = [];
    w.wordFeedback = "";
    w.wordHint = "";
  }
  const bubblePoint = i => ({
    x: 28 + (i % 8) * 39 + (Math.floor(i / 8) % 2) * 19.5,
    y: 46 + Math.floor(i / 8) * 34
  });

  function bubbleNear(i) {
    const r = Math.floor(i / 8),
      c = i % 8,
      shift = r % 2 ? 0 : -1;
    return [
      [r, c - 1],
      [r, c + 1],
      [r - 1, c + shift],
      [r - 1, c + shift + 1],
      [r + 1, c + shift],
      [r + 1, c + shift + 1]
    ].filter(([y, x]) => x >= 0 && x < 8 && y >= 0 && y < 11).map(([y, x]) => y * 8 + x);
  }

  function bubbleColor(w, H) {
    const found = [...new Set(w.bubbleBoard.filter(v => v >= 0))];
    return found.length ? H.pick(w, found) : 0;
  }

  function bubbleRound(w, H) {
    w.bubbleBoard = Array(88).fill(-1);
    const rows = Math.min(7, 4 + Math.floor(w.waves / 2) + (w.journey?Math.floor(w.journey.chapter/3):0));
    for (let r = 0; r < rows; r++)
      for (let c = 0; c < 8; c++) w.bubbleBoard[r * 8 + c] = Math.floor(H.random(w) * Math.min(6, 3 + Math.floor(w.waves / 2) + (w.journey?.variant===3?1:0)));
    w.currentBubble = bubbleColor(w, H);
    w.nextBubble = bubbleColor(w, H);
    w.bubbleMisses = 0;
    w.projectile = null;
  }

  function attachBubble(w, H, hit) {
    const s = w.projectile,
      candidates = hit === null ? Array.from({
        length: 8
      }, (_, i) => i) : bubbleNear(hit);
    let free = candidates.filter(i => w.bubbleBoard[i] < 0);
    if (!free.length) {
      H.end(w, "Шары заполнили поле");
      w.projectile = null;
      return;
    }
    free.sort((a, b) => {
      const A = bubblePoint(a),
        B = bubblePoint(b);
      return Math.hypot(A.x - s.x, A.y - s.y) - Math.hypot(B.x - s.x, B.y - s.y);
    });
    const index = free[0],
      color = w.currentBubble;
    w.bubbleBoard[index] = color;
    w.projectile = null;
    const group = new Set([index]),
      queue = [index];
    while (queue.length) {
      for (const n of bubbleNear(queue.pop()))
        if (w.bubbleBoard[n] === color && !group.has(n)) {
          group.add(n);
          queue.push(n);
        }
    }
    if (group.size >= 3) {
      for (const i of group) w.bubbleBoard[i] = -1;
      w.score += group.size * 10;
      const anchored = new Set(),
        q = [];
      for (let i = 0; i < 8; i++)
        if (w.bubbleBoard[i] >= 0) {
          anchored.add(i);
          q.push(i);
        } while (q.length)
        for (const n of bubbleNear(q.pop()))
          if (w.bubbleBoard[n] >= 0 && !anchored.has(n)) {
            anchored.add(n);
            q.push(n);
          }
      let fallen = 0;
      w.bubbleBoard.forEach((v, i) => {
        if (v >= 0 && !anchored.has(i)) {
          w.bubbleBoard[i] = -1;
          fallen++;
        }
      });
      w.score += fallen * 5;
      w.bubbleMisses = 0;
      H.emit(w, "bubblePop", {
        cells: [...group],
        fallen
      });
    } else {
      w.bubbleMisses++;
      H.emit(w, "bubbleStick", {
        index
      });
    }
    if (w.bubbleBoard.every(v => v < 0)) {
      w.score += 100;
      w.waves++;
      H.emit(w, "level");
      bubbleRound(w, H);
      return;
    }
    if (w.bubbleMisses >= 5) {
      if (w.bubbleBoard.slice(72).some(v => v >= 0)) {
        H.end(w, "Шары дошли до нижней линии");
        return;
      }
      w.bubbleBoard = Array.from({
        length: 8
      }, () => Math.floor(H.random(w) * Math.min(6, 3 + Math.floor(w.waves / 2) + (w.journey?.variant===3?1:0)))).concat(w.bubbleBoard.slice(0, 80));
      w.bubbleMisses = 0;
      H.emit(w, "ceiling");
    }
    if (w.bubbleBoard.slice(72).some(v => v >= 0)) H.end(w, "Шары дошли до нижней линии");
    w.currentBubble = w.nextBubble;
    w.nextBubble = bubbleColor(w, H);
    if (!w.bubbleBoard.includes(w.currentBubble)) w.currentBubble = bubbleColor(w, H);
  }

  function create(w, H) {
    if (w.id === "kopatych") Object.assign(w, {
      harvest: 0,
      spent: 0,
      upgrades: [0, 0, 0],
      combo: 0,
      lastTap: -100,
      goldUntil: 0,
      nextGold: 8,
      taps: 0
    });
    if (w.id === "blocks") {
      Object.assign(w, {
        blockBoard: Array(64).fill(0),
        lines: 0,
        blockCombo: 0
      });
      dealBlocks(w, H);
    }
    if (w.id === "runner") Object.assign(w, {
      runnerY: 352,
      runnerVy: 0,
      runnerGround: true,
      runnerAngle: 0,
      obstacles: [],
      spawnAt: 1.6,
      distance: 0,
      jumps: 0,
      runnerNextId: 0
    });
    if (w.id === "bubbles") {
      w.waves = 0;
      bubbleRound(w, H);
    }
    if (w.id === "sort") {
      w.details.moves = 0;
      sortRound(w, H);
    }
    if (w.id === "words") {
      Object.assign(w, {
        packOrder: H.shuffled(w, [0, 1, 2, 3, 4, 5, 6, 7]),
        wordRound: 0,
        allWords: []
      });
      wordRound(w);
    }
  }

  function step(w, H) {
    if (w.id === "kopatych") {
      if (w.time >= w.nextGold) {
        w.goldUntil = w.time + 3;
        w.nextGold = w.time + 12 + H.random(w) * 5;
        H.emit(w, "gold");
      }
      if (w.time - w.lastTap > .8) w.combo = 0;
      const auto = w.upgrades[1] * (1 + w.upgrades[2]) * .8 * H.DT;
      w.harvest += auto;
      w.score = Math.floor(w.harvest);
      if (w.time >= 90) H.end(w, "Урожай собран!");
    }
    if (w.id === "runner") {
      const speed = (155 + Math.min(160, w.score * 4.5)) * (w.journey && w.journey.variant===2 ? 1 + .1*Math.sin(w.time*1.4) : 1);
      w.distance += speed * H.DT;
      if (w.time >= w.spawnAt) {
        const wide = w.journey?.variant===1 || H.random(w) < Math.min(.45, w.score / 60);
        w.obstacles.push({
          id: ++w.runnerNextId,
          x: 390,
          width: wide ? 53 : 27,
          height: 30 + Math.min(12, w.score / 8),
          passed: false
        });
        w.spawnAt = w.time + (wide ? 1.5 : 1.15) + H.random(w) * .55;
      }
      w.runnerVy += 1120 * H.DT;
      w.runnerY += w.runnerVy * H.DT;
      if (w.runnerY >= 352) {
        w.runnerY = 352;
        w.runnerVy = 0;
        w.runnerGround = true;
        w.runnerAngle = Math.round(w.runnerAngle / (Math.PI / 2)) * Math.PI / 2;
      } else {
        w.runnerGround = false;
        w.runnerAngle += H.DT * 8;
      }
      for (const o of w.obstacles) {
        o.x -= speed * H.DT;
        if (!o.passed && o.x + o.width < 65) {
          o.passed = true;
          w.score++;
          H.emit(w, "land");
        }
        // Tight triangle hit boxes keep near misses fair.
        if ((!w.journey || w.journey.powerUntil<=w.time) && o.x + o.width - 5 > 69 && o.x + 5 < 91 && w.runnerY + 22 > 380 - o.height + 8) {
          H.emit(w, "miss", {
            x: o.x,
            y: 370
          });
          H.end(w, "Куб задел шип. Прыгай чуть раньше.");
        }
      }
      w.obstacles = w.obstacles.filter(o => o.x + o.width > -15);
      w.details.distance = Math.floor(w.distance);
      w.details.jumps = w.jumps;
    }
    if (w.id === "bubbles" && w.projectile) {
      const s = w.projectile;
      s.x += s.vx * H.DT;
      s.y += s.vy * H.DT;
      if (s.x < 18) {
        s.x = 36 - s.x;
        s.vx = Math.abs(s.vx);
      }
      if (s.x > 342) {
        s.x = 684 - s.x;
        s.vx = -Math.abs(s.vx);
      }
      const hit = w.bubbleBoard.findIndex((v, i) => {
        const p = bubblePoint(i);
        return v >= 0 && Math.hypot(p.x - s.x, p.y - s.y) < 34;
      });
      if (s.y <= 28 || hit >= 0) attachBubble(w, H, hit >= 0 ? hit : null);
    }
    if (w.id === "words" && w.time >= 180) H.end(w, "Время вышло — слова сохранены");
  }

  function cost(w, i) {
    return [25, 45, 80][i] * (w.upgrades[i] + 1) ** 2;
  }

  function input(w, a, H) {
    if (w.id === "kopatych") {
      if (a.type === "tap" && w.time - w.lastTap >= .075) {
        w.combo = w.time - w.lastTap <= .8 ? Math.min(40, w.combo + 1) : 1;
        w.lastTap = w.time;
        w.taps++;
        const gain = (1 + w.upgrades[0] * 2) * (1 + Math.floor(w.combo / 10)) * (w.time < w.goldUntil ? 3 : 1);
        w.harvest += gain;
        w.score = Math.floor(w.harvest);
        H.emit(w, "harvest", {
          gain
        });
        return true;
      }
      if (a.type === "buy" && Number.isInteger(a.i) && a.i >= 0 && a.i < 3 && w.upgrades[a.i] < 6 && w.harvest - w.spent >= cost(w, a.i)) {
        w.spent += cost(w, a.i);
        w.upgrades[a.i]++;
        H.emit(w, "upgrade", {
          i: a.i
        });
        return true;
      }
    }
    if (w.id === "blocks") {
      if (a.type === "piece" && Number.isInteger(a.i) && w.pieces[a.i]) {
        w.selectedPiece = a.i;
        return true;
      }
      if (a.type === "place" && Number.isInteger(a.x) && Number.isInteger(a.y) && Number.isInteger(a.piece) && a.piece >= 0 && a.piece < 3) {
        const p = w.pieces[a.piece];
        if (!fitsBlock(w, p, a.x, a.y)) return false;
        for (const [dx, dy] of p) w.blockBoard[(a.y + dy) * 8 + a.x + dx] = w.pieceColors[a.piece];
        w.score += p.length;
        w.pieces[a.piece] = null;
        const rows = [],
          cols = [];
        for (let i = 0; i < 8; i++) {
          if (w.blockBoard.slice(i * 8, i * 8 + 8).every(Boolean)) rows.push(i);
          if (Array.from({
              length: 8
            }, (_, y) => w.blockBoard[y * 8 + i]).every(Boolean)) cols.push(i);
        }
        if (rows.length + cols.length) {
          w.blockCombo++;
          w.lines += rows.length + cols.length;
          w.score += (rows.length + cols.length) * 40 * Math.min(5, w.blockCombo);
          w.blockBoard = w.blockBoard.map((v, i) => rows.includes(Math.floor(i / 8)) || cols.includes(i % 8) ? 0 : v);
          H.emit(w, "clearLines", {
            rows,
            cols,
            combo: w.blockCombo
          });
        } else w.blockCombo = 0;
        if (w.pieces.every(p => !p)) dealBlocks(w, H);
        else w.selectedPiece = w.pieces.findIndex(Boolean);
        w.details.lines = w.lines;
        w.details.moves++;
        if (!blocksAvailable(w)) H.end(w, "Для оставшихся фигур не осталось места");
        return true;
      }
    }
    if (w.id === "runner" && a.type === "tap" && w.runnerGround) {
      w.runnerVy = -460;
      w.runnerGround = false;
      w.jumps++;
      H.emit(w, "jump");
      return true;
    }
    if (w.id === "bubbles" && a.type === "shoot" && !w.projectile && Number.isFinite(a.x) && Number.isFinite(a.y)) {
      const angle = Math.max(-1.18, Math.min(1.18, Math.atan2(a.x - 180, 402 - Math.max(0, Math.min(370, a.y)))));
      w.projectile = {
        x: 180,
        y: 402,
        vx: Math.sin(angle) * 520,
        vy: -Math.cos(angle) * 520
      };
      w.details.moves++;
      H.emit(w, "shoot");
      return true;
    }
    if (w.id === "sort") {
      if (a.type === "undo" && w.mode === "practice" && w.sortUndo.length && !w.sortWon) {
        w.tubes = w.sortUndo.pop();
        w.selectedTube = -1;
        return true;
      }
      if (a.type === "restart" && !w.sortWon) {
        w.tubes = w.sortStart.map(t => t.slice());
        w.sortUndo = [];
        w.selectedTube = -1;
        w.roundMoves = 0;
        return true;
      }
      if (a.type === "next" && w.sortWon) {
        sortRound(w, H);
        return true;
      }
      if (a.type === "tube" && Number.isInteger(a.i) && a.i >= 0 && a.i < w.tubes.length) {
        if (w.selectedTube < 0) {
          w.selectedTube = w.tubes[a.i].length ? a.i : -1;
          return true;
        }
        const from = w.selectedTube;
        w.selectedTube = -1;
        if (from === a.i) return true;
        return pour(w, {
          from,
          to: a.i
        }, H);
      }
      if (a.type === "pour") return pour(w, a, H);
    }
    if (w.id === "words") {
      if (a.type === "hint" && w.mode === "practice") {
        w.wordHint = w.wordPack.answers.find(t => !w.roundWords.includes(t)) || "";
        return true;
      }
      if (a.type === "word" && typeof a.value === "string" && a.value.length <= 32) {
        const word = a.value.trim().toLowerCase().replace(/ё/g, "е");
        if (w.roundWords.includes(word)) {
          w.wordFeedback = "Это слово уже найдено";
          H.emit(w, "wordMiss");
          return false;
        }
        if (!w.wordPack.answers.includes(word)) {
          w.wordFeedback = "Этого слова пока нет в словаре игры";
          H.emit(w, "wordMiss");
          return false;
        }
        w.roundWords.push(word);
        w.allWords.push(word);
        w.score++;
        w.wordFeedback = "Есть такое слово!";
        w.wordHint = "";
        H.emit(w, "wordFound", {
          word
        });
        if (w.roundWords.length >= Math.min(8,w.wordPack.answers.filter(a=>a.length>=(w.journey?.minimumWord||3)).length)) {
          w.wordRound++;
          if (w.wordRound >= 5) H.end(w, "Пять подборок пройдены!");
          else {
            wordRound(w);
            H.emit(w, "level");
          }
        }
        return true;
      }
    }
    return false;
  }

  function pour(w, a, H) {
    if (w.sortWon || !Number.isInteger(a.from) || !Number.isInteger(a.to) || a.from === a.to || a.from < 0 || a.to < 0 || a.from >= w.tubes.length || a.to >= w.tubes.length) return false;
    const from = w.tubes[a.from],
      to = w.tubes[a.to];
    if (!from.length || to.length >= 4 || to.length && to.at(-1) !== from.at(-1)) {
      w.sortMessage = "Сверху должен быть тот же цвет или свободное место";
      return false;
    }
    // One ball per tap makes every scramble exactly reversible and exposes an undo in practice only.
    w.sortUndo.push(w.tubes.map(t => t.slice()));
    if (w.sortUndo.length > 40) w.sortUndo.shift();
    to.push(from.pop());
    w.roundMoves++;
    w.details.moves++;
    w.sortMessage = "";
    H.emit(w, "pour", {
      from: a.from,
      to: a.to
    });
    if (sortSolved(w)) {
      w.score++;
      w.sortWon = true;
      H.emit(w, "sortWin");
    }
    return true;
  }

  function tutorial(w) {
    w.extraTutorial = true;
    if (w.id === "blocks") {
      w.blockBoard = Array(64).fill(0);
      for (let i = 56; i < 63; i++) w.blockBoard[i] = 1;
      w.pieces = [
        [
          [0, 0]
        ], null, null
      ];
      w.selectedPiece = 0;
    }
    if (w.id === "bubbles") {
      w.bubbleBoard = Array(88).fill(-1);
      w.bubbleBoard[3] = w.bubbleBoard[4] = 0;
      w.currentBubble = w.nextBubble = 0;
    }
    if (w.id === "sort") {
      w.tubes = [
        [0, 1],
        [1, 1, 1],
        [0, 0, 0],
        []
      ];
      w.sortStart = w.tubes.map(t => t.slice());
    }
    if (w.id === "words") {
      w.wordPack = {
        root: "КОСМОС",
        answers: ["сом", "сок", "ком"]
      };
      w.roundWords = [];
    }
  }

  function tutorialDone(w) {
    if (!ids.has(w.id)) return undefined;
    return w.id === "runner" ? w.jumps > 0 : w.id === "sort" ? w.roundMoves > 0 : w.score > 0;
  }
  window.ArcadeExtras = {
    games,
    blocksAvailable,
    has: id => ids.has(id),
    difficulty,
    create,
    step,
    input,
    tutorial,
    tutorialDone,
    cost,
    colors,
    shapes,
    fitsBlock,
    blocksAvailable,
    sortSolved,
    sortMoves,
    bubblePoint,
    bubbleNear,
    packs
  };
})();
