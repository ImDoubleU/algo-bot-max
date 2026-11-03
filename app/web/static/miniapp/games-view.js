/* Rendering and input only. Scores, random numbers and physics live in games-world. */
(() => {
    const S = window.ArcadeSprites,
        M = window.AlgoGameMotion,
        E = window.AlgoGameEngine;
    const $ = (s, r) => r.querySelector(s),
        esc = s => String(s).replace(/[&<>"']/g, c => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;"
        } [c]));
    const colors = ["#b6a0ec", "#c5e998", "#efb38e", "#eca3b4", "#9fc9e9", "#ecdc93", "#c498e6", "#efbf88"];

    function text(c, t, x, y, size = 17, color = "#d7c8e6") {
        c.fillStyle = color;
        c.font = `700 ${size}px system-ui`;
        c.textAlign = "center";
        c.fillText(t, x, y);
    }

    function circle(c, x, y, r, color) {
        c.fillStyle = color;
        c.beginPath();
        c.arc(x, y, r, 0, Math.PI * 2);
        c.fill();
    }

    function background(c, theme) {
        c.fillStyle = {
            space: "#17182c",
            forest: "#182c2b",
            sunset: "#352330",
            nebula: "#25203c"
        } [theme] || "#17182c";
        c.fillRect(0, 0, 360, 430);
        c.fillStyle = "#aaa0bf66";
        for (let i = 0; i < 30; i++) c.fillRect((i * 83 + 23) % 350, (i * 59 + 31) % 420, i % 3 ? 1 : 2, i % 3 ? 1 : 2);
    }

    function mount(game, stage, send, options) {
        if (window.ArcadeExtraView?.has(game)) return window.ArcadeExtraView.mount(game, stage, send, options);
        stage.dataset.game = game;
        const on = (el, type, fn, opts = {}) => el.addEventListener(type, fn, {
                ...opts,
                signal: options.signal
            }),
            active = () => !options.paused();
        const source = e => e?.pointerType ? (e.pointerType === "touch" ? "touch" : "keyboard") : e?.type === "keydown" ? "keyboard" : options.device;
        const input = (a, e) => {
            if (active()) send({
                ...a,
                source: source(e)
            });
        };
        let paint = () => {},
            update = () => {},
            aim = 180,
            lastCue = 0;
        if (["orbit", "bugs", "tower", "drop"].includes(game)) {
            const canvas = document.createElement("canvas");
            canvas.width = 720;
            canvas.height = 860;
            canvas.tabIndex = 0;
            canvas.setAttribute("aria-label", E.games.find(g => g.id === game).hint);
            stage.append(canvas);
            const c = canvas.getContext("2d");
            c.scale(2, 2);
            canvas.focus();
            const sparks = new M.Sparks();
            const point = e => {
                const r = canvas.getBoundingClientRect(),
                    s = Math.min(r.width / 360, r.height / 430);
                return {
                    x: (e.clientX - r.left - (r.width - 360 * s) / 2) / s,
                    y: (e.clientY - r.top - (r.height - 430 * s) / 2) / s
                };
            };
            on(canvas, "pointermove", e => {
                aim = point(e).x;
            });
            on(canvas, "pointerdown", e => {
                e.preventDefault();
                input({
                    type: "tap",
                    ...point(e)
                }, e);
            });
            on(document, "keydown", e => {
                if (!active()) return;
                if (game === "drop" && ["ArrowLeft", "ArrowRight"].includes(e.code)) {
                    e.preventDefault();
                    aim = Math.max(25, Math.min(335, aim + (e.code === "ArrowLeft" ? -12 : 12)));
                }
                if (["Space", "ArrowUp"].includes(e.code) && !e.repeat && game !== "bugs") {
                    e.preventDefault();
                    input({
                        type: "tap",
                        x: aim,
                        y: 0
                    }, e);
                }
            });
            paint = (w, dt = 0) => {
                background(c, options.theme);
                window.ArcadePersonality?.backdrop(c, game, w);
                const raw = E.difficulty(game, game === "2048" ? Math.max(...w.board) : w.score),
                    config = w.journey ? ArcadeJourney.difficulty(w, raw) : raw;
                for (const cue of w.cues.filter(q => q.n > lastCue)) {
                    if (["land", "hit", "merge", "perfect"].includes(cue.type)) sparks.burst(cue.x || 180, cue.y || 300, colors[cue.level || 1], options.quality() === "low" ? 5 : 16);
                    lastCue = cue.n;
                }
                sparks.tick(Math.min(dt, .05));
                if (game === "orbit") {
                    const a = w.flight ? w.flightTarget : w.target + Math.sin(w.time * .8) * config.orbitDrift,
                        target = {
                            x: 180 + Math.cos(a) * 105,
                            y: 281 + Math.sin(a) * 160
                        },
                        t = Math.min(1, w.flight || 0),
                        ease = t * t * (3 - 2 * t);
                    c.save();
                    c.translate((180 - target.x) * ease, (281 - target.y) * ease);
                    c.strokeStyle = "#c6ed9044";
                    c.lineWidth = 14;
                    c.beginPath();
                    c.arc(180, 281, 69, a - config.orbitWindow, a + config.orbitWindow);
                    c.stroke();
                    c.strokeStyle = "#8d79b744";
                    c.lineWidth = 1;
                    c.beginPath();
                    c.arc(180, 281, 69, 0, Math.PI * 2);
                    c.stroke();
                    S.draw(c, "planet", 180, 281, 95, {
                        ...options,
                        phase: w.time
                    });
                    circle(c, target.x, target.y, 28 + 15 * ease, "#bfe691");
                    circle(c, target.x - 7, target.y - 7, 8, "#def4b5");
                    const x = w.flight ? w.from.x + (target.x - w.from.x) * ease : 180 + Math.cos(w.angle) * 69,
                        y = w.flight ? w.from.y + (target.y + 69 - w.from.y) * ease - Math.sin(t * Math.PI) * 65 : 281 + Math.sin(w.angle) * 69;
                    S.draw(c, "cat", x, y, 38, {
                        ...options,
                        quality: options.quality(),
                        angle: w.flight ? Math.sin(t * Math.PI) * .65 : Math.sin(w.time * 3) * .06
                    });
                    c.restore();
                    text(c, w.flight ? "Есть контакт!" : "Поймай зелёную дугу", 180, 35, 15, "#c5ef96");
                }
                if (game === "bugs") {
                    for (const t of w.targets) {
                        const age = t.total - t.left;
                        c.strokeStyle = t.good ? "#b8e6aa" : "#c5aff2";
                        c.lineWidth = 2;
                        c.beginPath();
                        c.arc(t.x, t.y, 29, -Math.PI / 2, -Math.PI / 2 + t.left / t.total * 2 * Math.PI);
                        c.stroke();
                        S.draw(c, t.good ? "robot" : "bug", t.x, t.y, Math.min(1, age * 10) * 44, {
                            ...options,
                            quality: options.quality(),
                            phase: w.time,
                            angle: Math.sin(w.time * 5 + t.phase) * .13
                        });
                    }
                    text(c, `Жизни: ${Math.max(0,w.lives)}`, 180, 30, 14);
                }
                if (game === "tower") {
                    const visible = w.blocks.slice(-11);
                    visible.forEach((b, i) => {
                        c.fillStyle = `hsl(${250+i*9+w.score*8} 65% 73%)`;
                        const bounce = i === visible.length - 1 ? Math.sin(w.settle * 29) * Math.exp(-w.settle * 14) * 5 : 0;
                        c.fillRect(b.left, 390 - i * 25 + bounce, b.width, 21);
                    });
                    c.fillStyle = "#c9ed81";
                    c.fillRect(w.left, 390 - visible.length * 25, w.width, 21);
                    for (const p of w.debris) {
                        c.save();
                        c.globalAlpha = Math.min(1, (1.8 - p.age) * 2);
                        c.translate(p.x, p.y);
                        c.rotate(p.angle);
                        c.fillStyle = "#b498db";
                        c.fillRect(-p.width / 2, -10, p.width, 21);
                        c.restore();
                    }
                    if (w.combo >= 2) text(c, `Идеально ×${w.combo}`, 180, 42, 20, "#d6ef98");
                }
                if (game === "drop") {
                    const r = ArcadeWorld.rad[w.queue[0]],
                        x = Math.max(r + 12, Math.min(348 - r, aim));
                    let y = 416 - r;
                    for (const b of w.balls) {
                        const dx = b.x - x,
                            sum = b.r + r;
                        if (Math.abs(dx) < sum) y = Math.min(y, b.y - Math.sqrt(sum * sum - dx * dx));
                    }
                    if (w.dropPhysics === 3) y = ArcadeDrop.preview(w, x, r);
                    c.globalAlpha = .18;
                    circle(c, x, Math.max(45, y), r, colors[w.queue[0]]);
                    c.globalAlpha = 1;
                    c.strokeStyle = w.danger ? "#ee8c9b" : "#887997";
                    c.lineWidth = 1;
                    c.setLineDash([4, 5]);
                    c.beginPath();
                    c.moveTo(12, config.dangerLine);
                    c.lineTo(348, config.dangerLine);
                    c.stroke();
                    c.setLineDash([]);
                    c.strokeStyle = "#5c4e72";
                    c.lineWidth = 3;
                    c.strokeStyle = '#b8c9df88';
                    c.lineWidth = 4;
                    c.beginPath();
                    c.moveTo(11, 85);
                    c.lineTo(11, 401);
                    c.quadraticCurveTo(11, 417, 27, 417);
                    c.lineTo(333, 417);
                    c.quadraticCurveTo(349, 417, 349, 401);
                    c.lineTo(349, 85);
                    c.stroke();
                    c.strokeStyle = '#edf4ff22';
                    c.lineWidth = 2;
                    c.beginPath();
                    c.moveTo(17, 91);
                    c.lineTo(17, 394);
                    c.stroke();
                    if (w.dropPhysics === 3) ArcadeDrop.draw(c, w.arena);
                    S.draw(c, w.queue[0], x, 38, r * 1.7, {
                        ...options,
                        quality: options.quality()
                    });
                    S.draw(c, w.queue[1], 297, 32, 22, options);
                    S.draw(c, w.queue[2], 327, 32, 20, options);
                    for (const b of w.balls) {
                        c.save();
                        c.translate(b.x, b.y);
                        const grow = 1 - Math.exp(-b.age * 12) * Math.cos(b.age * 20) * .14;
                        if (w.softDrop) {
                            const q = Math.max(-.10, Math.min(.24, b.squash)),
                                axis = b.squashAxis ?? Math.PI / 2;
                            c.rotate(axis);
                            c.scale(grow * (1 - q), grow / (1 - q));
                            c.rotate(b.angle - axis);
                            const gradient = c.createRadialGradient(-b.r * .35, -b.r * .4, 1, 0, 0, b.r * 1.25);
                            gradient.addColorStop(0, '#fff7ed');
                            gradient.addColorStop(.32, colors[b.level]);
                            gradient.addColorStop(1, colors[b.level]);
                            c.beginPath();
                            const points = Array.from({
                                length: 12
                            }, (_, i) => {
                                const a = i * Math.PI / 6,
                                    wiggle = Math.min(.025, Math.abs(b.squashV || 0) * .012) * Math.sin(a * 3 + b.age * 13);
                                return {
                                    x: Math.cos(a) * b.r * (1 + wiggle),
                                    y: Math.sin(a) * b.r * (1 + wiggle)
                                };
                            });
                            c.moveTo((points[11].x + points[0].x) / 2, (points[11].y + points[0].y) / 2);
                            points.forEach((p, i) => {
                                const n = points[(i + 1) % 12];
                                c.quadraticCurveTo(p.x, p.y, (p.x + n.x) / 2, (p.y + n.y) / 2);
                            });
                            c.closePath();
                            c.fillStyle = gradient;
                            c.fill();
                            c.strokeStyle = '#ffffff77';
                            c.lineWidth = 1.4;
                            c.stroke();
                        } else {
                            c.rotate(b.angle);
                            c.scale(grow * (1 + b.squash), grow * (1 - b.squash));
                            circle(c, 0, 0, b.r, colors[b.level]);
                        }
                        S.draw(c, b.level, 0, 0, b.r * 1.4, {
                            ...options,
                            quality: options.quality()
                        });
                        c.restore();
                    }
                    if (w.danger) text(c, "Выше линии!", 180, config.dangerLine + 23, 14, "#ff9aab");
                }
                sparks.paint(c);
            };
            return {
                update: (w, dt) => paint(w, dt),
                canvas
            };
        }
        if (game === "evolve") {
            stage.innerHTML = '<div class="evolve-game"><div class="evolve-time"><progress></progress><span></span></div><div class="evolve-grid"></div></div>';
            const grid = $(".evolve-grid", stage);
            let signature = "";
            on(grid, "click", e => {
                const b = e.target.closest("[data-cell]");
                if (b) input({
                    type: "cell",
                    i: +b.dataset.cell
                }, e);
            });
            update = w => {
                const key = w.cells.join() + ":" + w.selected;
                if (key !== signature) {
                    signature = key;
                    grid.innerHTML = w.cells.map((v, i) => `<button data-cell="${i}" aria-label="Зверь уровня ${v+1}" class="${w.selected===i?"selected":""}"><small>${2**(v+1)}</small></button>`).join("");
                    [...grid.children].forEach((b, i) => S.buttonCanvas(b, w.cells[i], options));
                    const cue = w.cues.at(-1);
                    if (cue?.type === "evolve" && cue.n !== lastCue) {
                        M.pop(grid.children[cue.to]);
                        lastCue = cue.n;
                    }
                }
                const raw = E.difficulty(game, w.merges),
                    c = w.journey ? ArcadeJourney.difficulty(w, raw) : raw;
                $("progress", stage).max = c.pairSeconds;
                $("progress", stage).value = Math.max(0, w.left);
                $(".evolve-time span", stage).textContent = `${Math.max(0,Math.ceil(w.left))} с`;
            };
        }
        if (game === "typing") {
            stage.innerHTML = '<div class="typing-game"><div class="typing-stats"><span id="typingAccuracy"></span><span id="typingSpeed"></span></div><div class="typing-passage"></div><label>Печатай здесь<textarea class="typing-input" rows="3" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" aria-label="Текст по образцу"></textarea></label><small>Русская раскладка · минута после первого символа</small></div>';
            const field = $("textarea", stage);
            let current = "",
                committed = 0;
            on(field, "paste", e => e.preventDefault());
            on(field, "drop", e => e.preventDefault());
            on(field, "beforeinput", e => {
                if (!active() && e.inputType !== "insertText") {
                    e.preventDefault();
                    return;
                }
                if (e.inputType.startsWith("delete")) {
                    e.preventDefault();
                    input({
                        type: "text",
                        value: "",
                        delete: true
                    }, e);
                } else if (e.data && e.data.length === 1) {
                    e.preventDefault();
                    send({
                        type: "text",
                        value: e.data,
                        source: options.device
                    });
                } else if (!e.isComposing) e.preventDefault();
            });
            on(field, "compositionend", e => {
                if (e.data?.length === 1) send({
                    type: "text",
                    value: e.data,
                    source: options.device
                });
                field.value = current;
            });
            update = w => {
                const start = Math.max(0, w.typed.length - 35),
                    view = w.text.slice(start, start + 130);
                $(".typing-passage", stage).innerHTML = [...view].map((ch, i) => `<span class="${start+i<w.typed.length?(ch===w.typed[start+i]?"correct":"wrong"):start+i===w.typed.length?"cursor":""}">${esc(ch)}</span>`).join("");
                current = w.typed.slice(-60);
                if (field.value !== current) {
                    field.value = current;
                    field.setSelectionRange(current.length, current.length);
                }
                if (w.journey) $('.typing-game>small', stage).textContent = w.journey.chapter >= 4 ? 'Код · английская раскладка' : 'Сообщение · русская раскладка';
                $('.typing-game', stage).classList.toggle('journey-highlight', !!w.journey && w.journey.powerUntil > w.time);
                $("#typingAccuracy", stage).textContent = `Точность ${w.details.accuracy}%`;
                $("#typingSpeed", stage).textContent = `${Math.round(w.score/Math.max(1,w.time)*60)} зн/мин`;
            };
            if (!options.readOnly) field.focus();
        }
        if (game === "debug") {
            let signature = "";
            on(stage, "click", e => {
                const b = e.target.closest("button");
                if (!b) return;
                if (b.dataset.line !== undefined) input({
                    type: "line",
                    i: +b.dataset.line
                }, e);
                if (b.dataset.option !== undefined) input({
                    type: "answer",
                    i: +b.dataset.option
                }, e);
                if (b.hasAttribute("data-next")) input({
                    type: "next"
                }, e);
                if (b.hasAttribute("data-hint")) input({
                    type: "hint"
                }, e);
            });
            update = w => {
                if (w.index >= 8) return;
                const key = [w.index, w.line, w.answered, w.hints].join();
                if (key === signature) return;
                signature = key;
                const t = w.tasks[w.index],
                    last = w.answers.at(-1);
                stage.innerHTML = `<div class="debug-game"><div class="debug-progress">Задача ${w.index+1} / 8<span>PYTHON</span></div><h3>${esc(t.intro)}</h3><div class="debug-code">${t.lines.map((line,i)=>`<button data-line="${i}" class="${w.line===i?"selected":""} ${w.mode==="practice"&&w.hintAt===w.index&&i===t.line?"is-hint":""}" ${w.answered?"disabled":""}><span>${i+1}</span><code>${esc(line)}</code></button>`).join("")}</div><p class="debug-instruction">${w.line<0?"Нажми на строку с ошибкой":"Чем заменим строку?"}</p>${w.line>=0?`<div class="debug-options">${t.options.map((option,i)=>`<button data-option="${i}" ${w.answered||(w.journey?.hintAt===w.index&&w.journey?.hintOption===i)?"disabled":""}><code>${esc(option)}</code></button>`).join("")}</div>`:""}${w.mode==="practice"&&!w.answered?'<button class="arcade-subtle" data-hint>Подсказка</button>':""}<div class="debug-feedback" role="status">${w.answered?`<b>${last?.ok?"Верно!":"Разберём ошибку"}</b><p>${esc(t.why)}</p><code>${esc(t.options[t.answer])}</code><button class="games-main" data-next>${w.index===7?"Результат":"Дальше →"}</button>`:""}</div></div>`;
            };
        }
        if (game === "2048") {
            stage.innerHTML = '<div class="number-game"><div class="number-points">Очки <b>0</b></div><div class="number-grid" role="grid"></div><div class="number-controls"><button data-dir="up" aria-label="Вверх">↑</button><div><button data-dir="left" aria-label="Влево">←</button><button data-dir="down" aria-label="Вниз">↓</button><button data-dir="right" aria-label="Вправо">→</button></div></div>' + (options.mode === "practice" ? '<button class="arcade-subtle" data-undo>Отменить ход</button>' : "") + '</div>';
            const grid = $(".number-grid", stage);
            let start = null,
                signature = "";
            on(document, "keydown", e => {
                const dir = {
                    ArrowLeft: "left",
                    ArrowRight: "right",
                    ArrowUp: "up",
                    ArrowDown: "down"
                } [e.key];
                if (dir && active()) {
                    e.preventDefault();
                    input({
                        type: "move",
                        dir
                    }, e);
                }
            });
            on(grid, "pointerdown", e => {
                if (grid.querySelector('.can-swap')) {
                    start = null;
                    return;
                }
                start = {
                    x: e.clientX,
                    y: e.clientY
                };
                grid.setPointerCapture(e.pointerId);
            });
            on(grid, "pointerup", e => {
                if (!start) return;
                const dx = e.clientX - start.x,
                    dy = e.clientY - start.y;
                start = null;
                if (Math.max(Math.abs(dx), Math.abs(dy)) > 15) input({
                    type: "move",
                    dir: Math.abs(dx) > Math.abs(dy) ? dx > 0 ? "right" : "left" : dy > 0 ? "down" : "up"
                }, e);
            });
            on(stage, "click", e => {
                const b = e.target.closest("button");
                if (b?.dataset.numberCell !== undefined) input({
                    type: 'swap_cell',
                    i: +b.dataset.numberCell
                }, e);
                if (b?.dataset.dir) input({
                    type: "move",
                    dir: b.dataset.dir
                }, e);
                if (b?.hasAttribute("data-undo")) input({
                    type: "undo"
                }, e);
            });
            update = w => {
                const key = w.board.join() + ":" + !!w.journey?.swapSelecting + ":" + w.journey?.swapFrom;
                if (key === signature) return;
                const old = [...grid.children].slice(0, 16).map(c => ({
                    rect: c.getBoundingClientRect(),
                    background: getComputedStyle(c).backgroundColor,
                    color: getComputedStyle(c).color
                }));
                signature = key;
                grid.innerHTML = w.board.map((v, i) => w.journey ? `<button type="button" data-number-cell="${i}" aria-label="Клетка ${i+1}: ${v||'пусто'}" class="number-cell n${Math.min(v,2048)} ${w.journey.swapSelecting?'can-swap':''} ${w.journey.swapFrom===i?'swap-selected':''}">${v||""}</button>` : `<div role="gridcell" class="number-cell n${Math.min(v,2048)}">${v||""}</div>`).join("");
                $(".number-points b", stage).textContent = w.points || 0;
                const cue = w.cues.filter(c => c.type === "slide").at(-1);
                if (cue && cue.n !== lastCue) {
                    lastCue = cue.n;
                    const cells = [...grid.children],
                        box = grid.getBoundingClientRect();
                    if (!matchMedia("(prefers-reduced-motion: reduce)").matches && old.length === 16) {
                        for (const move of cue.moves) {
                            if (move.from === move.to && !move.merged) continue;
                            const source = old[move.from],
                                target = cells[move.to].getBoundingClientRect(),
                                ghost = document.createElement("div");
                            ghost.className = "number-moving";
                            ghost.textContent = move.value;
                            ghost.setAttribute("aria-hidden", "true");
                            Object.assign(ghost.style, {
                                left: (target.left - box.left) + "px",
                                top: (target.top - box.top) + "px",
                                width: target.width + "px",
                                height: target.height + "px",
                                background: source.background,
                                color: source.color
                            });
                            grid.append(ghost);
                            cells[move.to].style.opacity = "0";
                            ghost.animate([{
                                transform: `translate(${source.rect.left-target.left}px,${source.rect.top-target.top}px)`
                            }, {
                                transform: "translate(0,0)"
                            }], {
                                duration: 140,
                                easing: "cubic-bezier(.2,.8,.3,1)"
                            }).finished.then(() => {
                                ghost.remove();
                                cells[move.to].style.opacity = "";
                                if (move.merged) M.pop(cells[move.to]);
                            }).catch(() => ghost.remove());
                        }
                    } else
                        for (const to of new Set(cue.moves.filter(m => m.merged).map(m => m.to))) M.pop(cells[to]);
                }
            };
        }
        if (game === "memory") {
            let signature = "",
                wasBetween = null;
            stage.innerHTML = '<div class="memory-game"><div class="memory-top"><span></span><b></b></div><div class="memory-grid"></div><div class="memory-next"></div></div>';
            on(stage, "click", e => {
                const b = e.target.closest("button");
                if (b?.dataset.card !== undefined) input({
                    type: "cell",
                    i: +b.dataset.card
                }, e);
                if (b?.hasAttribute("data-memory-next")) input({
                    type: "next"
                }, e);
            });
            update = w => {
                const peek = !!w.journey && w.journey.revealUntil > w.time;
                const key = w.cards.join() + ":" + w.opened.join() + ":" + w.matched.join() + ":" + peek;
                if (key !== signature) {
                    signature = key;
                    const grid = $(".memory-grid", stage);
                    grid.style.gridTemplateColumns = `repeat(${w.cards.length>=20?6:4},minmax(0,1fr))`;
                    grid.innerHTML = w.cards.map((v, i) => `<button data-card="${i}" class="${w.matched.includes(i)?"matched":(w.opened.includes(i)||peek)?"flipped":""}" ${w.matched.includes(i)?"disabled":""} aria-label="Карточка ${i+1}">${w.matched.includes(i)||w.opened.includes(i)||peek?"":"✦"}</button>`).join("");
                    [...grid.children].forEach((b, i) => {
                        if (w.matched.includes(i) || w.opened.includes(i) || peek) S.buttonCanvas(b, S.memory[w.cards[i]], options);
                    });
                }
                $(".memory-top span", stage).textContent = `${w.cards.length/2} пар`;
                $(".memory-top b", stage).textContent = `${w.moves} ходов`;
                if (wasBetween !== w.between) {
                    wasBetween = w.between;
                    $(".memory-next", stage).innerHTML = w.between && !w.ended ? '<button class="games-main" data-memory-next>Следующий уровень →</button>' : "";
                }
            };
        }
        if (game === "react") {
            stage.innerHTML = '<button class="reaction-pad wait"><span class="reaction-symbol"></span><b></b><small></small></button><div class="reaction-attempts"></div>';
            const pad = $(".reaction-pad", stage);
            let signature = "";
            on(pad, "click", e => input({
                type: "tap"
            }, e));
            on(document, "keydown", e => {
                if (e.code === "Space" && !e.repeat && active()) {
                    e.preventDefault();
                    input({
                        type: "tap"
                    }, e);
                }
            });
            update = w => {
                const decoy = w.journey?.decoy;
                const key = w.signal + ":" + w.feedback + ":" + w.hits.length + ":" + decoy;
                if (key === signature) return;
                signature = key;
                pad.className = "reaction-pad " + (decoy ? 'decoy' : w.signal);
                $(".reaction-symbol", pad).textContent = w.signal === "go" ? "!" : w.signal === "feedback" ? "✓" : "•••";
                $("b", pad).textContent = w.signal === "go" ? "ЖМИ!" : w.signal === "feedback" ? w.feedback : decoy ? 'Пропусти синий' : "Подожди зелёный";
                $("small", pad).textContent = w.signal === "go" ? `${Math.round(E.difficulty(game,w.score).reactionWindow*1000)} мс на ответ` : `Осталось ошибок: ${3-w.misses}`;
                const from = Math.floor(Math.min(14, w.hits.length) / 5) * 5;
                $(".reaction-attempts", stage).innerHTML = Array.from({
                    length: 5
                }, (_, i) => `<span class="${w.hits[from+i]!==undefined?"done":""}">${w.hits[from+i]!==undefined?w.hits[from+i]+" мс":i+1}</span>`).join("");
            };
        }
        return {
            update
        };
    }
    window.ArcadeView = {
        mount
    };
})();
