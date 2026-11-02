/* Active adventures. The same catalogue and rules run in the browser and verifier. */
(() => {
  'use strict';
  const specs = {
    orbit: {
      name: 'Звёздный курьер',
      chapters: ['Первая посылка', 'Лунные станции', 'Солнечный ветер', 'Обратная орбита', 'Дальний рейс', 'Край галактики'],
      goals: [4, 7, 10, 14, 18, 24],
      power: 'Коррекция',
      action: 'Увеличить окно следующего прыжка',
      rules: ['Посади кота на планеты', 'Движущаяся точка посадки', 'Встречный ветер', 'Узкие посадочные дуги'],
      reward: 'Марки космических станций'
    },
    evolve: {
      name: 'Атлас космозверей',
      chapters: ['Первая клетка', 'Тёплый океан', 'Папоротниковый лес', 'Ледяные пещеры', 'Летающие острова', 'Новый вид'],
      goals: [24, 64, 128, 256, 512, 1024],
      power: 'Катализатор',
      action: 'Поднять уровень одного младшего зверя',
      rules: ['Объединяй одинаковых', 'Охота за редким видом', 'Короткий поиск пары', 'Цепочка открытий'],
      reward: 'Страницы атласа'
    },
    bugs: {
      name: 'Мастерская роботов',
      chapters: ['Проверка платы', 'Ремонтный цех', 'Перегрев', 'Сбой конвейера', 'Главный сервер', 'Перезапуск'],
      goals: [8, 14, 20, 28, 36, 45],
      power: 'Импульс',
      action: 'Поймать багов на поле, не задев роботов',
      rules: ['Отличай багов от роботов', 'Быстрые беглецы', 'Больше роботов на поле', 'Короткие волны'],
      reward: 'Детали отремонтированного робота'
    },
    tower: {
      name: 'Город над облаками',
      chapters: ['Фундамент', 'Жилой квартал', 'Башня с часами', 'Ветровая станция', 'Облачный порт', 'Небоскрёб'],
      goals: [4, 7, 10, 14, 18, 24],
      power: 'Магнит',
      action: 'Следующий блок точно по центру',
      rules: ['Сохрани ширину башни', 'Точные серии расширяют площадку', 'Ветер меняет скорость', 'Узкий фундамент'],
      reward: 'Здания своего города'
    },
    typing: {
      name: 'Почта экспедиции',
      chapters: ['Короткие письма', 'Срочная доставка', 'Бортовой журнал', 'Шифры и координаты', 'Строки программы', 'Главный эфир'],
      goals: [35, 60, 90, 120, 160, 210],
      power: 'Подсветка',
      action: 'Показать следующие символы крупнее',
      rules: ['Набери сообщение', 'Сохрани точность', 'Без лишних исправлений', 'Срочная отправка'],
      reward: 'Открытки экспедиции'
    },
    debug: {
      name: 'Бюро ошибок',
      chapters: ['Арифметика', 'Имена и строки', 'Условия', 'Циклы', 'Списки и словари', 'Последнее дело'],
      goals: [2, 3, 4, 5, 6, 7],
      power: 'Улика',
      action: 'Исключить одно неверное исправление',
      rules: ['Найди ошибочную строку', 'Проверь результат программы', 'Выбери исправление', 'Разбери дело целиком'],
      reward: 'Раскрытые дела'
    },
    '2048': {
      name: 'Энергия города',
      chapters: ['Первый генератор', 'Первые улицы', 'Подстанция', 'Большой район', 'Мегаполис', 'Сердце города'],
      goals: [32, 64, 128, 256, 512, 1024],
      power: 'Обмен',
      action: 'Поменять местами две выбранные плитки',
      rules: ['Собери нужную плитку', 'Сохраняй свободный угол', 'Заранее спланированное поле', 'Ограниченное число ходов'],
      reward: 'Запущенные районы'
    },
    drop: {
      name: 'Планетарий',
      chapters: ['Каменные крошки', 'Первый спутник', 'Пояс астероидов', 'Газовые гиганты', 'Новые созвездия', 'Своя система'],
      goals: [40, 90, 160, 260, 400, 650],
      power: 'Смена',
      action: 'Поменять местами два следующих предмета',
      rules: ['Объединяй одинаковые тела', 'Заранее планируй очередь', 'Боковой ветер', 'Мало места над линией'],
      reward: 'Планеты личной системы'
    },
    memory: {
      name: 'Багаж путешественника',
      chapters: ['Собираем рюкзак', 'На вокзале', 'Ночной поезд', 'Музей находок', 'Большая пересадка', 'Возвращение'],
      goals: [4, 8, 12, 16, 24, 32],
      power: 'Взгляд',
      action: 'Открыть всё поле на одну секунду',
      rules: ['Запоминай расположение', 'Больше карточек', 'Короткое время на поиск', 'Без лишних открытий'],
      reward: 'Находки из путешествий'
    },
    react: {
      name: 'Школа пилотов',
      chapters: ['Первый сигнал', 'Полоса разгона', 'Туманная полоса', 'Ложные сигналы', 'Сложная посадка', 'Экзамен пилота'],
      goals: [3, 5, 7, 9, 11, 13],
      power: 'Фокус',
      action: 'На пять секунд увеличить время ответа',
      rules: ['Жми только на зелёный', 'Нерегулярные сигналы', 'Синий сигнал — приманка', 'Точность важнее спешки'],
      reward: 'Знаки пилота'
    },
    blocks: {
      name: 'Мозаичный парк',
      chapters: ['Первые дорожки', 'Клумбы', 'Площадь фонтанов', 'Заросший сад', 'Большая мозаика', 'Открытие парка'],
      goals: [70, 140, 240, 400, 650, 1000],
      power: 'Поворот',
      action: 'Повернуть выбранную фигуру',
      rules: ['Очищай линии', 'Начатая мозаика', 'Комбинации линий', 'Сложные фигуры'],
      reward: 'Участки мозаичного парка'
    },
    runner: {
      name: 'Пульс города',
      chapters: ['Учебная трасса', 'Крыши', 'Неоновый тоннель', 'Скоростная линия', 'Над пропастью', 'Финишный рывок'],
      goals: [5, 8, 12, 18, 25, 35],
      power: 'Рывок',
      action: 'На секунду проскочить сквозь препятствия',
      rules: ['Поймай ритм прыжков', 'Двойные препятствия', 'Переменный темп', 'Точный участок'],
      reward: 'Отметки пройденных трасс'
    },
    bubbles: {
      name: 'Подводная станция',
      chapters: ['Берег', 'Коралловый сад', 'Затонувший город', 'Тёмная вода', 'Глубинная станция', 'Сигнал со дна'],
      goals: [80, 140, 220, 320, 480, 700],
      power: 'Смена цвета',
      action: 'Поменять текущий и следующий шар',
      rules: ['Собирай цвета', 'Роняй оторванные группы', 'Меньше лишних выстрелов', 'Больше цветов'],
      reward: 'Снимки подводного мира'
    },
    sort: {
      name: 'Лаборатория цвета',
      chapters: ['Первый опыт', 'Чистые образцы', 'Новые реагенты', 'Сложная смесь', 'Большой эксперимент', 'Идеальный порядок'],
      goals: [1, 1, 2, 2, 3, 3],
      power: 'Запасная колба',
      action: 'Добавить пустую колбу на эту попытку',
      rules: ['Собери цвета отдельно', 'Спланируй переливания', 'Дополнительные цвета', 'Без лишних ходов'],
      reward: 'Коллекция чистых кристаллов'
    },
    words: {
      name: 'Библиотека слов',
      chapters: ['Первые страницы', 'Слова в дороге', 'Тайная полка', 'Длинные слова', 'Словарная экспедиция', 'Свой словарь'],
      goals: [4, 6, 8, 10, 14, 18],
      power: 'Закладка',
      action: 'Первая буква и длина ещё не найденного слова',
      rules: ['Ищи существительные', 'Используй запас букв', 'Слова от четырёх букв', 'Новая подборка'],
      reward: 'Полки собственной библиотеки'
    }
  };
  const limit = {
    orbit: 180,
    evolve: 240,
    bugs: 180,
    tower: 240,
    typing: 60,
    debug: 600,
    '2048': 900,
    drop: 600,
    memory: 360,
    react: 180,
    blocks: 600,
    runner: 180,
    bubbles: 600,
    sort: 900,
    words: 180
  };

  function speciesGoal(goal) {
    let level = 1;
    for (let n = 2; n <= 7; n++)
      if (n * 2 ** (n + 1) <= goal) level = n;
    return level;
  }

  function rotatable(w) {
    const piece = w.pieces?.[w.selectedPiece];
    if (!piece) return false;
    const rotated = piece.map(([x, y]) => [-y, x]),
      minX = Math.min(...rotated.map(p => p[0])),
      minY = Math.min(...rotated.map(p => p[1]));
    const key = p => p.map(([x, y]) => x + ',' + y).sort().join(';');
    return key(piece) !== key(rotated.map(([x, y]) => [x - minX, y - minY]));
  }

  function mission(game, stage) {
    const s = specs[game];
    if (!s || !Number.isInteger(stage) || stage < 1 || stage > 24) throw Error('Unknown adventure');
    const chapter = Math.floor((stage - 1) / 4),
      variant = (stage - 1) % 4;
    let goal = s.goals[chapter];
    if (game === 'evolve') goal = Math.round(goal * [1, 1.25, 1.5, 2][variant]);
    else if (game === '2048') goal *= variant >= 2 ? 2 : 1;
    else if (game === 'debug') goal = Math.min(8, goal + (variant % 2));
    else if (game === 'sort') goal += variant === 3 ? 1 : 0;
    else if (game === 'react') goal = Math.min(15, goal + variant % 3);
    else goal += variant * ({
      typing: 10,
      drop: 30,
      blocks: 60,
      bubbles: 30,
      runner: 2,
      words: 2,
      bugs: 2,
      memory: 2
    } [game] || 1);
    return {
      game,
      stage,
      chapter,
      variant,
      goal,
      title: s.chapters[chapter],
      rule: s.rules[variant],
      seconds: limit[game],
      power: s.power,
      action: s.action,
      corner: game === '2048' && variant === 1,
      moves: game === '2048' ? Math.ceil(Math.max(90, goal * 1.4) * (variant === 3 ? .8 : 1)) : game === 'sort' ? goal * 180 : game === 'bubbles' ? 70 + chapter * 12 : 0,
      species: speciesGoal(goal),
      minimumWord: game === 'words' && chapter >= 3 && variant === 2 ? 4 : 3
    };
  }

  function catalogue() {
    return Object.fromEntries(Object.keys(specs).map(id => [id, {
      ...specs[id],
      stages: Array.from({
        length: 24
      }, (_, i) => mission(id, i + 1))
    }]));
  }

  function config(setup) {
    const m = mission(setup.game, setup.journey?.stage);
    return {
      ...m,
      charges: Math.max(1, Math.min(3, Number(setup.journey.charges) || 1)),
      used: 0,
      movesUsed: 0,
      inputs: 0,
      mistakes: 0,
      perfect: 0,
      complete: false,
      stars: 0,
      powerUntil: 0,
      correction: false,
      revealUntil: 0,
      decoy: false,
      notes: ''
    };
  }

  function difficulty(w, c) {
    const j = w.journey;
    if (!j) return c;
    const r = {
        ...c
      },
      k = j.chapter,
      pressure = j.variant === 2;
    if (w.id === 'orbit') {
      r.orbitSpeed *= 1 + k * .06;
      r.orbitWindow *= j.correction ? 1.8 : 1 - k * .025;
      r.orbitDrift += j.variant === 1 ? .1 : j.variant === 2 ? .18 : 0;
    }
    if (w.id === 'tower') {
      r.towerSpeed *= (1 + k * .06 + (pressure ? .12 : 0)) * (pressure ? 1 + .15 * Math.sin(w.time * 1.5) : 1);
    }
    if (w.id === 'bugs') {
      r.bugEvery *= (1 - k * .025) * (j.variant === 3 ? .72 : 1);
      r.bugLife *= 1 - (pressure ? .12 : 0);
      r.robotChance = Math.min(.45, r.robotChance + (j.variant === 1 ? .13 : 0));
    }
    if (w.id === 'memory') {
      r.pairs = Math.min(12, r.pairs + Math.floor(k / 2) + (j.variant === 1 ? 2 : 0));
      r.memorySeconds *= pressure ? .85 : 1;
    }
    if (w.id === 'react') r.reactionWindow += j.powerUntil > w.time ? .25 : 0;
    if (w.id === 'evolve') r.pairSeconds *= pressure ? .7 : 1;
    if (w.id === 'drop' && j.variant === 3) r.dangerLine += 12;
    return r;
  }

  function debugTask(w, index, H) {
    const a = 2 + Math.floor(H.random(w) * 8),
      b = 2 + Math.floor(H.random(w) * 5),
      n = H.pick(w, ['points', 'coins', 'stars']);
    const lessons = [
      [`Нужна сумма ${a} и ${b}`, [`a = ${a}`, `b = ${b}`, 'print(a - b)'], 2, 'print(a + b)', ['print(a * b)', 'print(a // b)'], 'Сложение записывается через +.'],
      ['Выведи имя', ['name = "Соня"', 'print(Name)'], 1, 'print(name)', ['Print(name)', 'print(NAME)'], 'Имя переменной чувствительно к регистру.'],
      ['Получи число из строки', [`age = "${a}"`, `print(age + ${b})`], 1, `print(int(age) + ${b})`, [`print(age + "${b}")`, `print(str(age + ${b}))`], 'Перед арифметикой строку преобразуют в число.'],
      ['Выведи первое имя', ['names = ["Марк", "Даша"]', 'print(names[1])'], 1, 'print(names[0])', ['print(names[2])', 'print(names.first)'], 'Нумерация элементов начинается с нуля.'],
      ['Проверь равенство', [`${n} = ${a}`, `if ${n} = ${a}:`, '    print("Да")'], 1, `if ${n} == ${a}:`, [`if ${n} != ${a}:`, `if ${n} === ${a}:`], 'Одиночный = присваивает, двойной == сравнивает.'],
      ['Исправь условие', ['value = 8', 'if value > 5', '    print("Больше")'], 1, 'if value > 5:', ['if value > 5;', 'if value = 5:'], 'После условия нужно двоеточие.'],
      ['Выведи числа от 1 до 5', ['for i in range(1, 5):', '    print(i)'], 0, 'for i in range(1, 6):', ['for i in range(0, 5):', 'for i in range(2, 6):'], 'Правая граница range не включается.'],
      ['Заверши цикл', ['i = 0', 'while i < 3:', '    print(i)', '    i -= 1'], 3, '    i += 1', ['    i = 0', '    i *= 1'], 'Счётчик должен приближаться к границе.'],
      ['Добавь предмет', ['items = ["кот"]', 'items.add("мяч")'], 1, 'items.append("мяч")', ['items.push("мяч")', 'items.insert("мяч")'], 'В список добавляют элемент методом append.'],
      ['Получи цену', ['prices = {"мяч": 5}', 'print(prices[0])'], 1, 'print(prices["мяч"])', ['print(prices.mяч)', 'print(prices[1])'], 'У словаря обращаются по ключу, а не по номеру.'],
      ['Верни удвоенное число', ['def double(x):', '    print(x * 2)', 'value = double(4)'], 1, '    return x * 2', ['    return x + 1', '    x * 2'], 'return возвращает результат из функции.'],
      ['Не потеряй последний элемент', ['items = [2, 4, 6]', 'for i in range(len(items) - 1):', '    print(items[i])'], 1, 'for i in range(len(items)):', ['for i in range(1, len(items)):', 'for i in range(len(items) + 1):'], 'Для всех индексов нужен range(len(items)).']
    ];
    const first = Math.min(10, w.journey.chapter * 2);
    w.journey.lessonOrder ||= H.shuffled(w, lessons.map((_, i) => i));
    const t = lessons[w.journey.chapter === 5 ? w.journey.lessonOrder[index] : ((first + index % 4) % lessons.length)],
      options = H.shuffled(w, [t[3], ...t[4]]);
    return {
      intro: t[0],
      lines: t[1],
      line: t[2],
      options,
      answer: options.indexOf(t[3]),
      why: t[5]
    };
  }

  function create(w, H) {
    const j = w.journey;
    if (!j) return;
    if (w.id === 'typing') {
      const sets = [
        ['Лес шумит. Кот идёт домой. Мы строим новый город. '],
        ['Отряд 7: прибытие в 12:45. На борту 24 прибора. '],
        ['Координаты: (12, 48). Заряд: 85%; маршрут: A-17. '],
        ['for i in range(10): print(i * 2)\n', 'score = 12; name = "robot"; print(name, score)\n']
      ];
      const options = sets[Math.min(3, [0, 1, 1, 2, 3, 3][j.chapter] + (j.variant === 3 ? 1 : 0))];
      w.text = Array.from({
        length: 20
      }, () => H.pick(w, options)).join('');
    }
    if (w.id === 'debug') w.tasks = Array.from({
      length: 8
    }, (_, i) => debugTask(w, i, H));
    if (w.id === 'tower' && j.variant === 3) {
      w.width = 160;
      w.blocks[0] = {
        left: 100,
        width: 160
      };
    }
    if (w.id === 'blocks' && j.variant === 1)
      for (const i of [0, 7, 9, 14, 49, 54, 56, 63]) w.blockBoard[i] = 1 + (i % 6);
    if (w.id === '2048' && j.variant === 2) {
      w.board = Array(16).fill(0);
      w.board[0] = 8;
      w.board[5] = 4;
      w.board[10] = 4;
      w.board[15] = 2;
    }
    if (w.id === 'evolve') w.left = H.progress(w).pairSeconds;
  }

  function power(w, H) {
    const j = w.journey;
    if (!j || w.ended || (j.used >= j.charges && !j.swapSelecting)) return false;
    if (w.id === 'orbit') {
      if (j.correction) return false;
      j.correction = true;
    }
    if (w.id === 'tower') {
      if (j.magnet) return false;
      j.magnet = true;
    }
    if (w.id === 'bugs') {
      const targets = w.targets.filter(t => !t.good);
      if (!targets.length) return false;
      w.targets = w.targets.filter(t => t.good);
      w.score += targets.length;
      targets.forEach(t => H.emit(w, 'hit', {
        x: t.x,
        y: t.y
      }));
    }
    if (w.id === 'typing') {
      if (j.powerUntil > w.time) return false;
      j.powerUntil = w.time + 8;
    }
    if (w.id === 'debug') {
      if (w.answered || j.hintAt === w.index) return false;
      const t = w.tasks[w.index];
      j.hintAt = w.index;
      j.hintOption = [0, 1, 2].find(i => i !== t.answer);
    }
    if (w.id === '2048') {
      j.swapSelecting = !j.swapSelecting;
      j.swapFrom = null;
      j.notes = j.swapSelecting ? 'Выбери две клетки на поле' : '';
      j.inputs++;
      return true;
    }
    if (w.id === 'drop') {
      [w.queue[0], w.queue[1]] = [w.queue[1], w.queue[0]];
    }
    if (w.id === 'evolve') {
      const value = Math.min(...w.cells),
        i = w.cells.indexOf(value);
      w.cells[i] = Math.min(9, value + 1);
      w.selected = -1;
    }
    if (w.id === 'memory') {
      if (j.revealUntil > w.time) return false;
      j.revealUntil = w.time + 1;
    }
    if (w.id === 'react') {
      if (j.powerUntil > w.time) return false;
      j.powerUntil = w.time + 5;
    }
    if (w.id === 'blocks') {
      const piece = w.pieces[w.selectedPiece];
      if (!piece || !rotatable(w)) return false;
      const rotated = piece.map(([x, y]) => [-y, x]),
        minX = Math.min(...rotated.map(p => p[0])),
        minY = Math.min(...rotated.map(p => p[1]));
      w.pieces[w.selectedPiece] = rotated.map(([x, y]) => [x - minX, y - minY]);
    }
    if (w.id === 'runner') {
      if (j.powerUntil > w.time) return false;
      j.powerUntil = w.time + 1;
    }
    if (w.id === 'bubbles') {
      if (w.projectile) return false;
      [w.currentBubble, w.nextBubble] = [w.nextBubble, w.currentBubble];
    }
    if (w.id === 'sort') {
      if (w.sortWon) return false;
      w.tubes.push([]);
      w.sortStart.push([]);
    }
    if (w.id === 'words') {
      if (w.wordHint) return false;
      const word = w.wordPack.answers.find(a => !w.roundWords.includes(a) && a.length >= j.minimumWord);
      if (!word) return false;
      w.wordHint = word[0].toUpperCase() + ' · ' + word.length + ' букв';
    }
    j.used++;
    j.inputs++;
    H.emit(w, 'power');
    check(w, H);
    if (w.id === 'blocks' && !ArcadeExtras.blocksAvailable(w) && !w.ended) H.end(w, 'Для фигур не осталось места');
    return true;
  }

  function swap(w, i, H) {
    const j = w.journey;
    if (w.id !== '2048' || !j.swapSelecting || j.used >= j.charges || !Number.isInteger(i) || i < 0 || i >= 16) return false;
    if (j.swapFrom === i) {
      j.swapFrom = null;
      return true;
    }
    if (j.swapFrom === null) {
      j.swapFrom = i;
      return true;
    }
    if (w.board[j.swapFrom] === w.board[i]) return false;
    [w.board[i], w.board[j.swapFrom]] = [w.board[j.swapFrom], w.board[i]];
    j.swapSelecting = false;
    j.swapFrom = null;
    j.notes = '';
    j.used++;
    j.inputs++;
    H.emit(w, 'power');
    check(w, H);
    return true;
  }

  function measure(w) {
    return {
      score: w.score,
      lives: w.lives,
      misses: w.misses || 0,
      errors: w.errors || 0,
      answers: w.answers?.length || 0,
      moves: w.moves || 0,
      puzzleMoves: w.details.moves || 0,
      combo: w.combo || 0
    };
  }

  function after(w, a, before, accepted, H) {
    const j = w.journey;
    if (!j) return;
    if (!accepted) {
      if (a.type === 'word') j.mistakes++;
      return;
    }
    j.inputs++;
    if(w.id==='sort')j.movesUsed+=Math.max(0,w.details.moves-before.puzzleMoves);
    else if (a.type === 'move' || a.type === 'place' || a.type === 'shoot' || a.type === 'word' || w.id === 'drop' && a.type === 'tap') j.movesUsed++;
    if (w.id === 'tower' && a.type === 'tap' && w.score > before.score) {
      if (w.combo > before.combo) j.perfect++;
      if (w.combo > 0 && w.combo % 3 === 0) {
        w.width = Math.min(230, w.width + 12);
        w.blocks.at(-1).width = w.width;
        w.blocks.at(-1).left = Math.min(w.blocks.at(-1).left, 360 - w.width);
      }
    }
    if (w.id === 'orbit' && a.type === 'tap' && w.flight) {
      const c = H.progress(w),
        aim = w.target + Math.sin(w.time * .8) * c.orbitDrift,
        d = Math.abs(Math.atan2(Math.sin(w.angle - aim), Math.cos(w.angle - aim)));
      if (d <= c.orbitWindow * .5) j.perfect++;
      j.correction = false;
    }
    if (w.id === 'blocks') j.bestCombo = Math.max(j.bestCombo || 0, w.blockCombo || 0);
    j.mistakes += Math.max(0, (before.lives || 0) - (w.lives || 0)) + Math.max(0, (w.misses || 0) - before.misses) + Math.max(0, (w.errors || 0) - before.errors);
    if (w.id === 'debug' && w.answers.length > before.answers && !w.answers.at(-1).ok) j.mistakes++;
    if (w.id === 'memory' && w.moves > before.moves && w.wait > 0) j.mistakes++;
    check(w, H);
  }

  function step(w, H) {
    const j = w.journey;
    if (!j) return;
    j.decoy = w.id === 'react' && j.variant === 2 && w.signal === 'wait' && w.at - w.time < .65 && w.at - w.time > .3;
    if (w.id === 'drop' && j.variant === 2)
      for (const b of w.balls)
        if (b.age < 1.5) b.vx += Math.sin(w.time * 1.3) * H.DT * 8;
    check(w, H);
    if (!w.ended && w.time >= j.seconds) H.end(w, 'Время задания вышло');
  }

  function quality(w) {
    const j = w.journey;
    if (w.id === 'bugs') j.mistakes = 3 - w.lives;
    if (w.id === 'react') j.mistakes = w.misses;
    if (w.id === 'typing') j.mistakes = w.errors;
    if (w.id === 'debug') j.mistakes = w.answers.filter(a => !a.ok).length;
    if (w.id === 'memory') j.mistakes = Math.max(0, w.moves - w.score);
    if (w.id === 'orbit') return [j.perfect >= Math.ceil(j.goal * .5), j.perfect >= Math.ceil(j.goal * .8)];
    if (w.id === 'tower') return [j.perfect >= Math.ceil(j.goal / 4), j.perfect >= Math.ceil(j.goal / 2)];
    if (w.id === 'typing') return [w.details.accuracy >= 93, w.details.accuracy >= 98];
    if (w.id === 'react') return [w.misses <= 1, w.misses === 0 && (w.details.reactionMs || 999) <= 350];
    if (w.id === 'memory') return [w.moves <= w.score * 3, w.moves <= w.score * 2];
    if (w.id === '2048') return [j.movesUsed <= j.moves * .9, j.movesUsed <= j.moves * .7];
    if (w.id === 'evolve') return [w.merges <= Math.ceil(j.goal / 4), Math.max(...w.cells) >= j.species];
    if (w.id === 'drop') return [j.movesUsed <= Math.ceil(j.goal / 8) + 10, j.movesUsed <= Math.ceil(j.goal / 12) + 8];
    if (w.id === 'blocks') return [w.lines >= Math.ceil(j.goal / 200), (j.bestCombo || 0) >= 2];
    if (w.id === 'runner') return [w.jumps <= j.goal + 2, w.jumps <= j.goal];
    if (w.id === 'bubbles') return [j.movesUsed <= Math.ceil(j.goal / 18) + 10, j.movesUsed <= Math.ceil(j.goal / 30) + 5];
    if (w.id === 'sort') return [j.movesUsed <= j.goal * 110, j.movesUsed <= j.goal * 65];
    if (w.id === 'words') return [j.mistakes <= 2, j.mistakes === 0 && w.allWords.filter(a => a.length >= 5).length >= Math.ceil(j.goal / 3)];
    return [j.mistakes <= 2, j.mistakes === 0 && w.time <= j.seconds * .75];
  }

  function check(w, H) {
    const j = w.journey;
    if (!j || j.complete) return;
    const [clean, precision] = quality(w);
    if (w.score >= j.goal && j.inputs > 0 && (!j.corner || w.board[0] >= j.goal)) {
      j.complete = true;
      j.stars = 1 + Number(clean) + Number(clean && precision);
      w.ended = false;
      H.end(w, 'Задание пройдено');
    } else if (!w.ended && j.moves && j.movesUsed >= j.moves) H.end(w, 'Ходы закончились');
  }

  function summary(w) {
    const j = w.journey;
    return j ? {
      stage: j.stage,
      stars: j.stars,
      success: j.complete,
      goal: j.goal,
      inputs: j.inputs,
      used: j.used,
      moves: j.movesUsed,
      mistakes: j.mistakes,
      seconds: j.seconds
    } : null;
  }
  window.ArcadeJourney = {
    specs,
    rotatable,
    mission,
    catalogue,
    config,
    difficulty,
    create,
    power,
    swap,
    measure,
    after,
    step,
    summary,
    quality
  };
})();
