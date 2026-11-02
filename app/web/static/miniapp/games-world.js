/* Deterministic, DOM-free gameplay shared by the browser and the result verifier. */
(() => {
    "use strict";
    const E = window.AlgoGameEngine,
        DT = 1 / 60,
        MAX_TICKS = 216000;
    const texts = [
        "Космический кот нашёл на орбите пиццу. Теперь его миссия стала гораздо интереснее. ",
        "Робот умеет считать звёзды, но всё ещё путает сахар и соль. Ошибки помогают ему учиться. ",
        "В команде 12 роботов: 7 считают звёзды, а 5 готовят пиццу. Вместе они справляются быстрее! ",
        'Задание 3: (12 + 8) * 2 = 40. Таймер: 00:45, точность: 98%, скорость: 240 знаков. ',
        'Пароль от шлюза: "Орбита-2048". Координаты: (17, 42), энергия: 75%, запас: 3/8. '
    ];

    function random(w) {
        let t = w.rng += 0x6D2B79F5;
        t = Math.imul(t ^ t >>> 15, t | 1);
        t ^= t + Math.imul(t ^ t >>> 7, t | 61);
        return ((t ^ t >>> 14) >>> 0) / 4294967296;
    }
    const range = (w, a, b) => a + random(w) * (b - a),
        pick = (w, a) => a[Math.floor(random(w) * a.length)];

    function shuffled(w, a) {
        a = a.slice();
        for (let i = a.length - 1; i > 0; i--) {
            const j = Math.floor(random(w) * (i + 1));
            [a[i], a[j]] = [a[j], a[i]];
        }
        return a;
    }

    function emit(w, type, values = {}) {
        w.cues.push({
            n: ++w.cueSeq,
            t: w.tick,
            type,
            ...values
        });
        if (w.cues.length > 30) w.cues.shift();
    }

    function end(w, reason) {
        if (!w.ended) {
            w.ended = true;
            w.reason = reason;
            emit(w, "end");
        }
    }

    function task(w, index) {
        const tier = Math.floor(index / 2),
            a = 2 + Math.floor(random(w) * 17),
            b = 2 + Math.floor(random(w) * 9),
            name = pick(w, ["score", "coins", "stars", "energy"]);
        const variants = [
            [{
                intro: `Нужно получить сумму ${a} и ${b}`,
                lines: [`a = ${a}`, `b = ${b}`, "print(a - b)"],
                line: 2,
                options: ["print(a + b)", "print(a * b)", "print(a / b)"],
                answer: 0,
                why: "Сумма вычисляется оператором +."
            }, {
                intro: "Выведи имя ученика",
                lines: [`name = "${pick(w,["Миша","Соня","Даша","Марк"])}"`, "print(Name)"],
                line: 1,
                options: ["print(name)", "Print(name)", "print(NAME)"],
                answer: 0,
                why: "Python различает строчные и заглавные буквы в имени переменной."
            }],
            [{
                intro: `Проверь, равно ли число ${a}`,
                lines: [`${name} = ${a}`, `if ${name} = ${a}:`, '    print("Да")'],
                line: 1,
                options: [`if ${name} == ${a}:`, `if ${name} != ${a}:`, `if ${name} === ${a}:`],
                answer: 0,
                why: "Для сравнения нужен ==; одиночный = присваивает значение."
            }, {
                intro: `Выведи сообщение при результате больше ${b}`,
                lines: [`${name} = ${a+b}`, `if ${name} > ${b}`, '    print("Ура!")'],
                line: 1,
                options: [`if ${name} > ${b}:`, `if ${name} > ${b};`, `if ${name} = ${b}:`],
                answer: 0,
                why: "После условия ставится двоеточие."
            }],
            [{
                intro: "Выведи первый предмет",
                lines: ['items = ["кот", "ракета", "пицца"]', "print(items[1])"],
                line: 1,
                options: ["print(items[0])", "print(items[3])", "print(items.first)"],
                answer: 0,
                why: "Первый элемент имеет индекс 0."
            }, {
                intro: `Прибавь ${b} к числу в строке`,
                lines: [`age = "${a}"`, `print(age + ${b})`],
                line: 1,
                options: [`print(int(age) + ${b})`, `print(age + "${b}")`, `print(str(age + ${b}))`],
                answer: 0,
                why: "Сначала строку нужно преобразовать в число через int()."
            }],
            [{
                intro: `Выведи числа от 1 до ${b} включительно`,
                lines: [`for i in range(1, ${b}):`, "    print(i)"],
                line: 0,
                options: [`for i in range(1, ${b+1}):`, `for i in range(0, ${b}):`, `for i in range(${b}, 1):`],
                answer: 0,
                why: "Правая граница range не включается."
            }, {
                intro: `Функция должна вернуть число, умноженное на ${b}`,
                lines: ["def multiply(x):", `    result = x * ${b}`, `print(multiply(${a}))`],
                line: 1,
                options: [`    return x * ${b}`, `    print(x * ${b})`, `    return x + ${b}`],
                answer: 0,
                why: "Для возвращения результата из функции нужен return."
            }]
        ];
        w.taskChoices ||= {};
        if (index % 2 === 0) w.taskChoices[tier] = Math.floor(random(w) * variants[tier].length);
        const result = variants[tier][(w.taskChoices[tier] + index % 2) % variants[tier].length],
            order = shuffled(w, [0, 1, 2]);
        return {
            ...result,
            options: order.map(i => result.options[i]),
            answer: order.indexOf(result.answer),
            tier: tier + 1
        };
    }

    function create(setup) {
        if (!E.games.some(g => g.id === setup.game)) throw Error("Unknown game");
        const w = {
            rule: 3,
            id: setup.game,
            rng: setup.seed >>> 0,
            seed: setup.seed >>> 0,
            mode: setup.mode || "ranked",
            device: setup.device || "keyboard",
            tick: 0,
            time: 0,
            score: 0,
            rankScore: 0,
            level: 1,
            ended: false,
            reason: "",
            cues: [],
            cueSeq: 0,
            details: {
                accuracy: 100,
                mistakes: 0,
                moves: 0
            },
            undo: [],
            weak: String(setup.weak || "").slice(0, 10),
            badKeys: {}
        };
        if (w.mode === "journey") w.journey = ArcadeJourney.config(setup);
        if (w.id === "orbit") Object.assign(w, {
            angle: -Math.PI / 2,
            flight: 0,
            target: range(w, -2.3, -.8),
            flightTarget: 0,
            from: {
                x: 0,
                y: 0
            },
            landed: 5
        });
        if (w.id === "evolve") Object.assign(w, {
            cells: Array.from({
                length: 16
            }, () => random(w) < .3 ? 1 : 0),
            selected: -1,
            merges: 0,
            left: 20
        });
        if (w.id === "bugs") Object.assign(w, {
            targets: [],
            spawn: 0,
            lives: 3,
            nextId: 0
        });
        if (w.id === "tower") Object.assign(w, {
            blocks: [{
                left: 65,
                width: 230
            }],
            left: 0,
            width: 230,
            dir: 1,
            debris: [],
            settle: 1,
            combo: 0,
            bestCombo: 0
        });
        if (w.id === "typing") Object.assign(w, {
            text: "",
            typed: "",
            started: false,
            keystrokes: 0,
            errors: 0
        });
        if (w.id === "debug") Object.assign(w, {
            tasks: Array.from({
                length: 8
            }, (_, i) => task(w, i)),
            index: 0,
            line: -1,
            answered: false,
            answers: [],
            hints: 0
        });
        if (w.id === "2048") {
            w.board = Array(16).fill(0);
            spawnNumber(w);
            spawnNumber(w);
        }
        if (w.id === "drop") Object.assign(w, {
            balls: [],
            softDrop: setup.dropPhysics === 2 || w.mode === 'journey',
            aim: 180,
            queue: [0, Math.floor(range(w, 0, 3)), Math.floor(range(w, 0, 3))],
            cool: 0,
            danger: 0,
            nextId: 0
        });
        if (w.id === "memory") {
            Object.assign(w, {
                cards: [],
                opened: [],
                matched: [],
                moves: 0,
                wait: 0,
                cleared: 0,
                between: false
            });
            memoryRound(w);
        }
        if (w.id === "react") Object.assign(w, {
            signal: "wait",
            at: range(w, 1.2, 3.5),
            since: 0,
            hits: [],
            misses: 0,
            feedback: ""
        });
        ensureText(w);
        if (window.ArcadeExtras?.has(w.id)) ArcadeExtras.create(w, helpers());
        if (w.journey) ArcadeJourney.create(w, helpers());
        return w;
    }

    function progress(w) {
        const p = w.id === "evolve" ? w.merges : w.id === "debug" ? w.index : w.id === "2048" ? Math.max(...w.board) : w.id === "memory" ? w.cleared : w.score;
        const base = E.difficulty(w.id, p),
            c = w.journey ? ArcadeJourney.difficulty(w, base) : base;
        if (c.level > w.level) {
            w.level = c.level;
            emit(w, "level", {
                level: w.level
            });
        }
        return c;
    }

    function ensureText(w) {
        if (w.id !== "typing") return;
        while (w.text.length - w.typed.length < 200) {
            const level = E.difficulty("typing", w.text.length).level;
            let sentence = level === 1 ? pick(w, texts.slice(0, 2)) : level === 2 ? texts[2] : texts[Math.min(4, level)];
            if (w.mode === "practice" && w.weak) sentence = w.weak.split("").join(" ") + " " + sentence;
            w.text += sentence;
        }
    }

    function spawnNumber(w) {
        const free = w.board.map((v, i) => v ? null : i).filter(v => v !== null);
        if (free.length) w.board[pick(w, free)] = random(w) < 1 - E.difficulty("2048", Math.max(...w.board)).fourChance ? 2 : 4;
    }

    function memoryRound(w) {
        const c = progress(w);
        w.cards = shuffled(w, [...Array(c.pairs).keys(), ...Array(c.pairs).keys()]);
        w.matched = [];
        w.opened = [];
        w.wait = 0;
        w.left = c.memorySeconds;
        w.between = false;
    }

    function reactMiss(w, label) {
        w.misses++;
        w.details.mistakes = w.misses;
        w.feedback = label;
        emit(w, "miss");
        if (w.misses >= 3) {
            end(w, "Три ошибки — попробуем ещё?");
            return;
        }
        w.signal = "feedback";
        w.at = w.time + .95;
    }
    const rad = [13, 18, 24, 31, 39, 48, 59, 72];

    function dropPhysics(w, dt, c) {
        if (w.softDrop) return softDropPhysics(w, dt, c);
        w.cool = Math.max(0, w.cool - dt);
        for (const b of w.balls) {
            b.age += dt;
            b.vy += c.gravity * dt;
            b.vx *= Math.exp(-.5 * dt);
            b.x += b.vx * dt;
            b.y += b.vy * dt;
            b.angle += b.spin * dt;
            b.spin *= Math.exp(-.8 * dt);
            b.squash *= Math.exp(-10 * dt);
            if (b.x - b.r < 12) {
                b.x = 12 + b.r;
                b.vx = Math.abs(b.vx) * .28;
            }
            if (b.x + b.r > 348) {
                b.x = 348 - b.r;
                b.vx = -Math.abs(b.vx) * .28;
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
            for (let i = 0; i < w.balls.length; i++)
                for (let j = i + 1; j < w.balls.length; j++) {
                    const a = w.balls[i],
                        b = w.balls[j],
                        dx = b.x - a.x,
                        dy = b.y - a.y,
                        d = Math.hypot(dx, dy),
                        sum = a.r + b.r;
                    if (d >= sum) continue;
                    if (a.level === b.level) {
                        const level = Math.min(7, a.level + 1);
                        w.balls[i] = {
                            id: ++w.nextId,
                            x: (a.x + b.x) / 2,
                            y: (a.y + b.y) / 2,
                            r: rad[level],
                            level,
                            vx: (a.vx + b.vx) / 2,
                            vy: -45,
                            age: 0,
                            angle: 0,
                            spin: (a.spin + b.spin) / 2 + .3,
                            squash: .2
                        };
                        w.balls.splice(j, 1);
                        w.score += 2 ** (level + 1);
                        emit(w, "merge", {
                            x: w.balls[i].x,
                            y: w.balls[i].y,
                            level
                        });
                        break;
                    }
                    const nx = d > .001 ? dx / d : 1,
                        ny = d > .001 ? dy / d : 0,
                        overlap = sum - Math.max(d, .001),
                        ia = 1 / (a.r * a.r),
                        ib = 1 / (b.r * b.r);
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
                        if (rel < -70) a.squash = b.squash = Math.min(.18, -rel / 1500);
                    }
                }
        for (const b of w.balls) {
            b.x = Math.max(12 + b.r, Math.min(348 - b.r, b.x));
            b.y = Math.min(416 - b.r, b.y);
        }
        const high = w.balls.some(b => b.age > 2 && b.y - b.r < c.dangerLine && Math.abs(b.vy) < 45);
        w.danger = high ? w.danger + dt : Math.max(0, w.danger - dt * 2);
        if (w.danger > 2.5) end(w, "Поле заполнено выше линии");
    }

    function softRadius(b, nx, ny) {
        const q = Math.max(-.10, Math.min(.24, b.squash || 0)),
            axis = b.squashAxis ?? Math.PI / 2,
            along = nx * Math.cos(axis) + ny * Math.sin(axis),
            cross = -nx * Math.sin(axis) + ny * Math.cos(axis),
            parallel = 1 - q,
            perpendicular = 1 / parallel;
        return b.r / Math.sqrt(along * along / (parallel * parallel) + cross * cross / (perpendicular * perpendicular));
    }

    function pressSoft(b, load, axis) {
        b.softLoad = Math.max(b.softLoad || 0, Math.min(.23, load));
        const old = b.squashAxis ?? axis,
            delta = Math.atan2(Math.sin(2 * (axis - old)), Math.cos(2 * (axis - old))) / 2;
        b.squashAxis = old + delta * .22;
    }

    function softDropPhysics(w, dt, c) {
        w.cool = Math.max(0, w.cool - dt);
        for (const b of w.balls) {
            b.age += dt;
            b.softLoad = 0;
            b.squashAxis ??= Math.PI / 2;
            b.squashV ??= 0;
            b.vy += c.gravity * dt;
            b.vx *= Math.exp(-.7 * dt);
            b.x += b.vx * dt;
            b.y += b.vy * dt;
            b.angle += b.spin * dt;
            b.spin *= Math.exp(-1.1 * dt);
            const rx = softRadius(b, 1, 0),
                ry = softRadius(b, 0, 1);
            if (b.x - rx < 12) {
                const speed = Math.abs(b.vx);
                b.x = 12 + rx;
                b.vx = speed * .22;
                pressSoft(b, .025 + speed / 1900, 0);
            }
            if (b.x + rx > 348) {
                const speed = Math.abs(b.vx);
                b.x = 348 - rx;
                b.vx = -speed * .22;
                pressSoft(b, .025 + speed / 1900, 0);
            }
            if (b.y + ry > 416) {
                const speed = Math.abs(b.vy);
                b.y = 416 - ry;
                b.vy = -speed * .19;
                b.vx *= .975;
                if (Math.abs(b.vy) < 11) b.vy = 0;
                pressSoft(b, .045 + speed / 1700, Math.PI / 2);
                if (speed > 80) b.squashV += Math.min(5, speed / 150);
            }
        }
        for (let pass = 0; pass < 5; pass++)
            for (let i = 0; i < w.balls.length; i++)
                for (let j = i + 1; j < w.balls.length; j++) {
                    const a = w.balls[i],
                        b = w.balls[j],
                        dx = b.x - a.x,
                        dy = b.y - a.y,
                        d = Math.hypot(dx, dy),
                        nx = d > .001 ? dx / d : 1,
                        ny = d > .001 ? dy / d : 0,
                        sum = softRadius(a, nx, ny) + softRadius(b, nx, ny);
                    if (d >= sum) continue;
                    if (a.level === b.level) {
                        const next = Math.min(7, a.level + 1);
                        w.balls[i] = {
                            id: ++w.nextId,
                            x: (a.x + b.x) / 2,
                            y: (a.y + b.y) / 2,
                            r: rad[next],
                            level: next,
                            vx: (a.vx + b.vx) / 2,
                            vy: -45,
                            age: 0,
                            angle: 0,
                            spin: (a.spin + b.spin) / 2 + .3,
                            squash: .16,
                            squashV: -.5,
                            squashAxis: Math.PI / 2,
                            softLoad: 0
                        };
                        w.balls.splice(j, 1);
                        w.score += 2 ** (next + 1);
                        emit(w, 'merge', {
                            x: w.balls[i].x,
                            y: w.balls[i].y,
                            level: next
                        });
                        break;
                    }
                    const overlap = sum - Math.max(d, .001),
                        ia = 1 / (a.r * a.r),
                        ib = 1 / (b.r * b.r),
                        inv = ia + ib,
                        correction = Math.max(0, overlap - sum * .025) * .68,
                        rel = (b.vx - a.vx) * nx + (b.vy - a.vy) * ny;
                    a.x -= nx * correction * ia / inv;
                    a.y -= ny * correction * ia / inv;
                    b.x += nx * correction * ib / inv;
                    b.y += ny * correction * ib / inv;
                    const axis = Math.atan2(ny, nx),
                        load = .025 + overlap / sum * .6 + Math.max(0, -rel) / 2300;
                    pressSoft(a, load * ib / inv * 1.6, axis);
                    pressSoft(b, load * ia / inv * 1.6, axis);
                    if (rel < 0) {
                        const impulse = -rel * 1.17 / inv;
                        a.vx -= impulse * nx * ia;
                        a.vy -= impulse * ny * ia;
                        b.vx += impulse * nx * ib;
                        b.vy += impulse * ny * ib;
                        const tangent = (b.vx - a.vx) * -ny + (b.vy - a.vy) * nx;
                        a.spin += tangent / a.r * .012;
                        b.spin -= tangent / b.r * .012;
                        if (rel < -60) {
                            a.squashV += Math.min(2.5, -rel / 280);
                            b.squashV += Math.min(2.5, -rel / 280);
                        }
                    }
                }
        for (const b of w.balls) {
            const target = Math.min(.22, b.softLoad || 0);
            b.squashV += ((target - b.squash) * 190 - b.squashV * 13) * dt;
            b.squash += b.squashV * dt;
            if (b.squash < -.10 || b.squash > .24) {
                b.squash = Math.max(-.10, Math.min(.24, b.squash));
                b.squashV *= .3;
            }
            const rx = softRadius(b, 1, 0),
                ry = softRadius(b, 0, 1);
            b.x = Math.max(12 + rx, Math.min(348 - rx, b.x));
            b.y = Math.min(416 - ry, b.y);
        }
        const high = w.balls.some(b => b.age > 2 && b.y - softRadius(b, 0, 1) < c.dangerLine && Math.abs(b.vy) < 45);
        w.danger = high ? w.danger + dt : Math.max(0, w.danger - dt * 2);
        if (w.danger > 2.5) end(w, 'Поле заполнено выше линии');
    }

    function step(w) {
        if (w.ended) return;
        w.tick++;
        if (w.id !== "typing" || w.started) w.time += DT;
        const c = progress(w);
        if (w.id === "orbit") {
            w.landed += DT;
            if (w.flight) {
                w.flight += DT * 2.3;
                if (w.flight >= 1) {
                    w.flight = 0;
                    w.score++;
                    w.angle = Math.PI / 2;
                    w.target = range(w, -2.5, -.65);
                    w.landed = 0;
                    emit(w, "land");
                }
            } else w.angle += DT * c.orbitSpeed * (c.level >= 5 && Math.floor(w.score / 5) % 2 ? -1 : 1);
        }
        if (w.id === "evolve") {
            w.left -= DT;
            if (w.left <= 0) end(w, "Время на поиск пары вышло");
        }
        if (w.id === "bugs") {
            w.spawn -= DT;
            if (w.spawn <= 0) {
                w.spawn = c.bugEvery * range(w, .85, 1.15);
                w.targets.push({
                    id: ++w.nextId,
                    x: range(w, 35, 325),
                    y: range(w, 75, 365),
                    vx: range(w, -1, 1) * c.bugSpeed,
                    vy: range(w, -.6, .6) * c.bugSpeed,
                    left: c.bugLife,
                    total: c.bugLife,
                    good: random(w) < c.robotChance,
                    phase: range(w, 0, 6)
                });
            }
            for (const t of w.targets) {
                t.left -= DT;
                t.x += t.vx * DT;
                t.y += t.vy * DT;
                if (t.x < 32 || t.x > 328) t.vx *= -1;
                if (t.y < 68 || t.y > 375) t.vy *= -1;
            }
            for (const t of w.targets.filter(t => t.left <= 0))
                if (!t.good) {
                    w.lives--;
                    emit(w, "miss", {
                        x: t.x,
                        y: t.y
                    });
                } w.targets = w.targets.filter(t => t.left > 0);
            if (w.lives <= 0) end(w, "Баги разбежались");
        }
        if (w.id === "tower") {
            w.left += w.dir * c.towerSpeed * (c.level >= 4 ? 1 + Math.sin(w.time * 1.9) * .2 : 1) * DT;
            if (w.left < 0) {
                w.left = 0;
                w.dir = 1;
            }
            if (w.left + w.width > 360) {
                w.left = 360 - w.width;
                w.dir = -1;
            }
            w.settle += DT;
            for (const p of w.debris) {
                p.age += DT;
                p.vy += 780 * DT;
                p.x += p.vx * DT;
                p.y += p.vy * DT;
                p.angle += p.spin * DT;
            }
            w.debris = w.debris.filter(p => p.age < 1.8 && p.y < 490);
        }
        if (w.id === "typing" && w.started && w.time >= 60) end(w, "Минута пролетела");
        if (w.id === "drop") {
            dropPhysics(w, DT / 3, c);
            dropPhysics(w, DT / 3, c);
            dropPhysics(w, DT / 3, c);
        }
        if (w.id === "memory" && !w.between) {
            w.left -= DT;
            if (w.wait > 0) {
                w.wait -= DT;
                if (w.wait <= 0) w.opened = [];
            }
            if (w.left <= 0) end(w, "Время на поиск пар вышло");
        }
        if (w.id === "react") {
            if (w.signal === "go" && w.time - w.since > c.reactionWindow) reactMiss(w, "Не успел");
            else if (w.time >= w.at) {
                if (w.signal === "wait") {
                    w.signal = "go";
                    w.since = w.time;
                    w.at = Infinity;
                    emit(w, "signal");
                } else if (w.signal === "feedback") {
                    w.signal = "wait";
                    w.at = w.time + range(w, .8, 3.2);
                }
            }
        }
        if (window.ArcadeExtras?.has(w.id)) ArcadeExtras.step(w, helpers());
        w.rankScore = w.id === "2048" ? w.points || 0 : w.score;
        if (w.journey) ArcadeJourney.step(w, helpers());
        if (w.tick >= MAX_TICKS) end(w, "Партия завершена");
    }

    function input(w, a) {
        if (w.ended) return false;
        if (!w.journey) return baseInput(w, a);
        if (a.type === "power") return ArcadeJourney.power(w, helpers());
        if (a.type === "swap_cell") return ArcadeJourney.swap(w, a.i, helpers());
        if (w.id === "2048" && w.journey.swapSelecting && a.type === "move") return false;
        if (w.id === "tower" && a.type === "tap" && w.journey.magnet) {
            w.left = w.blocks.at(-1).left;
            w.journey.magnet = false;
        }
        if (w.id === "words" && a.type === "word" && typeof a.value === "string" && a.value.trim().length < w.journey.minimumWord) {
            w.wordFeedback = "В этом задании нужны слова от " + w.journey.minimumWord + " букв";
            w.journey.mistakes++;
            return false;
        }
        const before = ArcadeJourney.measure(w),
            accepted = baseInput(w, a);
        ArcadeJourney.after(w, a, before, accepted, helpers());
        return accepted;
    }

    function baseInput(w, a) {
        if (w.ended) return false;
        const c = progress(w);
        if (window.ArcadeExtras?.has(w.id)) return ArcadeExtras.input(w, a, helpers());
        if (a.type === "undo") {
            if (w.id !== "2048" || w.mode !== "practice" || !w.undo.length) return false;
            const old = w.undo.pop();
            Object.assign(w, old);
            emit(w, "undo");
            return true;
        }
        if (w.id === "orbit" && a.type === "tap") {
            if (w.flight) return false;
            const aim = w.target + Math.sin(w.time * .8) * c.orbitDrift,
                delta = Math.atan2(Math.sin(w.angle - aim), Math.cos(w.angle - aim));
            if (Math.abs(delta) > c.orbitWindow) {
                emit(w, "miss", {
                    angle: w.angle,
                    target: aim
                });
                end(w, "Кот промахнулся мимо зелёной дуги");
                return true;
            }
            w.from = {
                x: 180 + Math.cos(w.angle) * 69,
                y: 281 + Math.sin(w.angle) * 69
            };
            w.flightTarget = aim;
            w.flight = .001;
            return true;
        }
        if (w.id === "evolve" && a.type === "cell") {
            const i = a.i;
            if (!Number.isInteger(i) || i < 0 || i >= 16) return false;
            if (w.selected === i) {
                w.selected = -1;
                return true;
            }
            if (w.selected < 0 || w.cells[w.selected] !== w.cells[i]) {
                w.selected = i;
                return true;
            }
            const from = w.selected;
            w.cells[i] = Math.min(9, w.cells[i] + 1);
            w.score += 2 ** (w.cells[i] + 1);
            w.cells[from] = random(w) < .2 ? 1 : 0;
            w.selected = -1;
            w.merges++;
            w.left = progress(w).pairSeconds;
            emit(w, "evolve", {
                from,
                to: i
            });
            return true;
        }
        if (w.id === "bugs" && a.type === "tap") {
            const t = w.targets.slice().reverse().find(t => Math.hypot(t.x - a.x, t.y - a.y) < 30);
            if (!t) return false;
            w.targets = w.targets.filter(b => b.id !== t.id);
            if (t.good) {
                w.lives--;
                emit(w, "miss", {
                    x: t.x,
                    y: t.y
                });
                if (w.lives <= 0) end(w, "Роботов трогать нельзя");
            } else {
                w.score++;
                emit(w, "hit", {
                    x: t.x,
                    y: t.y
                });
            }
            return true;
        }
        if (w.id === "tower" && a.type === "tap") {
            const prev = w.blocks.at(-1),
                left = Math.max(w.left, prev.left),
                right = Math.min(w.left + w.width, prev.left + prev.width),
                y = 390 - Math.min(11, w.blocks.length) * 25;
            if (right - left < 5) {
                emit(w, "miss", {
                    left: w.left,
                    width: w.width
                });
                end(w, "Блок не попал на башню");
                return true;
            }
            const perfect = Math.abs(w.left - prev.left) < c.perfectWindow;
            if (!perfect)
                for (const [from, to] of [
                        [w.left, left],
                        [right, w.left + w.width]
                    ])
                    if (to - from > 1) w.debris.push({
                        x: (from + to) / 2,
                        y: y + 10,
                        width: to - from,
                        vx: from < prev.left ? -55 : 55,
                        vy: -55,
                        spin: from < prev.left ? -3 : 3,
                        angle: 0,
                        age: 0
                    });
            w.width = perfect ? prev.width : right - left;
            w.left = perfect ? prev.left : left;
            w.blocks.push({
                left: w.left,
                width: w.width
            });
            if (w.blocks.length > 12) w.blocks.shift();
            w.score++;
            w.combo = perfect ? w.combo + 1 : 0;
            w.bestCombo = Math.max(w.bestCombo, w.combo);
            w.settle = 0;
            emit(w, perfect ? "perfect" : "stack", {
                x: w.left + w.width / 2,
                y,
                combo: w.combo
            });
            w.left = w.dir > 0 ? 360 - w.width : 0;
            w.dir *= -1;
            return true;
        }
        if (w.id === "typing" && a.type === "text") {
            if (typeof a.value !== "string" || a.value.length > 1) return false;
            w.started = true;
            if (a.delete) {
                w.typed = w.typed.slice(0, -1);
            } else if (a.value) {
                const i = w.typed.length;
                w.keystrokes++;
                if (a.value !== w.text[i]) {
                    w.errors++;
                    const ch = w.text[i];
                    w.badKeys[ch] = (w.badKeys[ch] || 0) + 1;
                }
                w.typed += a.value;
            }
            w.score = [...w.typed].reduce((n, ch, i) => n + (ch === w.text[i] ? 1 : 0), 0);
            w.details.accuracy = w.keystrokes ? Math.floor((w.keystrokes - w.errors) / w.keystrokes * 100) : 100;
            ensureText(w);
            return true;
        }
        if (w.id === "debug") {
            if (a.type === "hint" && w.mode === "practice") {
                w.hints++;
                w.hintAt = w.index;
                emit(w, "hint");
                return true;
            }
            if (a.type === "line" && !w.answered && Number.isInteger(a.i) && a.i >= 0 && a.i < w.tasks[w.index].lines.length) {
                w.line = a.i;
                return true;
            }
            if (a.type === "answer" && !w.answered && Number.isInteger(a.i) && a.i >= 0 && a.i < 3) {
                const t = w.tasks[w.index],
                    ok = w.line === t.line && a.i === t.answer;
                w.answered = true;
                if (ok) w.score++;
                w.answers.push({
                    line: w.line,
                    option: a.i,
                    ok
                });
                emit(w, ok ? "correct" : "wrong");
                return true;
            }
            if (a.type === "next" && w.answered) {
                w.index++;
                if (w.index >= 8) {
                    end(w, "Все задачи разобраны");
                    return true;
                }
                w.line = -1;
                w.answered = false;
                return true;
            }
        }
        if (w.id === "2048" && a.type === "move" && ["left", "right", "up", "down"].includes(a.dir)) {
            const result = E.slide(w.board, a.dir);
            if (!result.changed) return false;
            w.undo.push({
                board: w.board.slice(),
                points: w.points || 0,
                score: w.score,
                rng: w.rng,
                level: w.level
            });
            if (w.undo.length > 20) w.undo.shift();
            w.board = result.board;
            w.points = (w.points || 0) + result.score;
            spawnNumber(w);
            w.score = Math.max(...w.board);
            w.rankScore = w.points;
            emit(w, "slide", {
                moves: result.moves
            });
            if (!E.canMove(w.board)) end(w, "Ходов больше нет");
            return true;
        }
        if (w.id === "drop" && a.type === "tap") {
            if (w.cool > 0 || !Number.isFinite(a.x)) return false;
            const level = w.queue.shift(),
                r = rad[level];
            w.queue.push(Math.floor(range(w, 0, c.dropKinds)));
            w.balls.push({
                id: ++w.nextId,
                x: Math.max(r + 12, Math.min(348 - r, a.x)),
                y: 45,
                r,
                level,
                vx: 0,
                vy: 0,
                age: 0,
                angle: range(w, -.2, .2),
                spin: range(w, -.7, .7),
                squash: 0,
                ...(w.softDrop ? {
                    squashV: 0,
                    squashAxis: Math.PI / 2,
                    softLoad: 0
                } : {})
            });
            w.cool = .55;
            return true;
        }
        if (w.id === "memory") {
            if (a.type === "next" && w.between) {
                memoryRound(w);
                return true;
            }
            if (a.type !== "cell" || w.wait > 0 || w.between || !Number.isInteger(a.i) || a.i < 0 || a.i >= w.cards.length || w.matched.includes(a.i) || w.opened.includes(a.i)) return false;
            w.opened.push(a.i);
            if (w.opened.length === 2) {
                w.moves++;
                w.details.moves = w.moves;
                if (w.cards[w.opened[0]] === w.cards[w.opened[1]]) {
                    w.matched.push(...w.opened);
                    emit(w, "pair", {
                        cells: w.opened.slice()
                    });
                    w.opened = [];
                    w.score++;
                    if (w.matched.length === w.cards.length) {
                        w.cleared = w.score;
                        w.between = true;
                        if (w.level >= 5) end(w, "Все пять уровней пройдены");
                    }
                } else w.wait = Math.max(.4, .8 - w.level * .06);
            }
            return true;
        }
        if (w.id === "react" && a.type === "tap") {
            if (w.signal === "feedback") return false;
            if (w.signal === "wait") {
                reactMiss(w, "Рановато!");
                return true;
            }
            const ms = Math.max(1, Math.round((w.time - w.since) * 1000));
            w.hits.push(ms);
            w.score = w.hits.length;
            w.details.mistakes = w.misses;
            w.details.reactionMs = Math.round(w.hits.reduce((a, b) => a + b, 0) / w.hits.length);
            w.feedback = ms + " мс";
            emit(w, "reaction");
            if (w.hits.length >= 15) end(w, "Три раунда пройдены");
            else {
                w.signal = "feedback";
                w.at = w.time + .95;
            }
            return true;
        }
        return false;
    }

    function advance(w, count) {
        if (!Number.isInteger(count) || count < 0 || count > MAX_TICKS) throw Error("Invalid time");
        for (let i = 0; i < count && !w.ended; i++) step(w);
        return w;
    }

    function report(w) {
        return {
            score: w.score,
            rankScore: w.id === "2048" ? w.points || 0 : w.score,
            level: w.level,
            complete: w.ended,
            reason: w.reason,
            ticks: w.tick,
            timeMs: Math.round(w.time * 1000),
            details: {
                ...w.details,
                result: w.score,
                timeMs: Math.round(w.time * 1000),
                bestCombo: w.bestCombo || 0,
                ...(w.id === 'drop' && w.softDrop ? {
                    physics: 'soft2'
                } : {})
            },
            badKeys: w.badKeys,
            ...(w.journey ? {
                journey: ArcadeJourney.summary(w)
            } : {})
        };
    }

    function verify(setup, events, finalTick) {
        if (!Array.isArray(events) || events.length > 20000 || !Number.isInteger(finalTick) || finalTick < 0 || finalTick > MAX_TICKS) throw Error("Invalid replay");
        const w = create(setup);
        let previous = 0;
        for (const event of events) {
            if (!event || !Number.isInteger(event.t) || event.t < previous || event.t > finalTick) throw Error("Invalid event order");
            advance(w, event.t - w.tick);
            if (w.ended) throw Error("Action after completed run");
            input(w, event);
            previous = event.t;
        }
        advance(w, Math.max(0, finalTick - w.tick));
        return report(w);
    }

    function helpers() {
        return {
            random,
            range,
            pick,
            shuffled,
            emit,
            end,
            progress,
            DT
        };
    }
    window.ArcadeWorld = {
        create,
        input,
        advance,
        report,
        verify,
        rad,
        DT,
        MAX_TICKS
    };
})();
