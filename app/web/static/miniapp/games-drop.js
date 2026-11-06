/* Shared arena geometry and contact mechanics. No DOM, clock or unseeded randomness. */
(() => {
    'use strict';
    const arenas = [{
        id: 'classic',
        name: 'Космопорт',
        hint: 'Открытое поле. Площадка соревнования.',
        lines: [],
        pins: []
    }, {
        id: 'bowl',
        name: 'Кратер',
        hint: 'Склоны собирают предметы в центре.',
        lines: [
            [12, 320, 96, 416],
            [264, 416, 348, 320]
        ],
        pins: []
    }, {
        id: 'slopes',
        name: 'Перевал',
        hint: 'Два уступа меняют направление падения.',
        lines: [
            [12, 245, 113, 282],
            [247, 337, 348, 300]
        ],
        pins: []
    }, {
        id: 'pins',
        name: 'Астероиды',
        hint: 'Облетай препятствия и используй отскоки.',
        lines: [],
        pins: [
            [116, 235, 13],
            [244, 235, 13],
            [180, 324, 16]
        ]
    }];
    const get = id => arenas.find(a => a.id === id) || arenas[0];

    function chapter(stage) {
        return ['classic', 'bowl', 'slopes', 'pins', 'bowl', 'pins'][Math.floor((stage - 1) / 4)] || 'classic';
    }

    function surfaces(arena, b, visit) {
        for (const [ax, ay, bx, by] of get(arena).lines) {
            const dx = bx - ax,
                dy = by - ay;
            const t = Math.max(0, Math.min(1, ((b.x - ax) * dx + (b.y - ay) * dy) / (dx * dx + dy * dy)));
            visit(ax + t * dx, ay + t * dy, 0);
        }
        for (const [x, y, r] of get(arena).pins) visit(x, y, r);
    }
    // A rough contact couples translation to rotation; friction cannot add energy.
    function friction(b, nx, ny, normalSpeed) {
        const tx = -ny,
            ty = nx,
            slip = b.vx * tx + b.vy * ty - b.spin * b.r;
        const change = Math.max(-normalSpeed * .28, Math.min(normalSpeed * .28, -slip / 3));
        b.vx += tx * change;
        b.vy += ty * change;
        b.spin -= 2 * change / b.r;
    }

    function collide(w, b, radius, press) {
        surfaces(w.arena, b, (x, y, r) => {
            let dx = b.x - x,
                dy = b.y - y,
                d = Math.hypot(dx, dy);
            const nx = d > .0001 ? dx / d : 0,
                ny = d > .0001 ? dy / d : -1;
            const reach = radius(b, nx, ny) + r;
            if (d >= reach) return;
            b.x += nx * (reach - d);
            b.y += ny * (reach - d);
            const speed = b.vx * nx + b.vy * ny;
            if (speed < 0) {
                b.vx -= nx * speed * 1.27;
                b.vy -= ny * speed * 1.27;
                friction(b, nx, ny, -speed * 1.27);
                b.squashV += Math.min(3, -speed / 210);
            }
            press(b, .04 + Math.max(0, -speed) / 1600, Math.atan2(ny, nx));
        });
    }

    function preview(w, x, r) {
        for (let y = 46; y <= 416 - r; y += 2) {
            let hit = w.balls.some(b => Math.hypot(b.x - x, b.y - y) <= b.r + r);
            surfaces(w.arena, {
                x,
                y
            }, (px, py, pr) => {
                if (Math.hypot(px - x, py - y) <= r + pr) hit = true;
            });
            if (hit) return y - 2;
        }
        return 416 - r;
    }

    function draw(c, id) {
        const arena = get(id);
        c.save();
        c.lineCap = 'round';
        c.lineWidth = 7;
        c.strokeStyle = '#a99bbb';
        for (const [ax, ay, bx, by] of arena.lines) {
            c.beginPath();
            c.moveTo(ax, ay);
            c.lineTo(bx, by);
            c.stroke();
        }
        for (const [x, y, r] of arena.pins) {
            c.beginPath();
            c.arc(x, y, r, 0, Math.PI * 2);
            c.fillStyle = '#53445f';
            c.fill();
            c.lineWidth = 2;
            c.strokeStyle = '#b9aacb';
            c.stroke();
            c.beginPath();
            c.arc(x - 3, y - 4, r * .25, 0, Math.PI * 2);
            c.fillStyle = '#9a87b1';
            c.fill();
        }
        c.font = '600 14px system-ui';
        c.textAlign = 'left';
        c.fillStyle = '#baaccd';
        c.fillText(arena.name, 20, 104);
        c.restore();
    }
    window.ArcadeDrop = {
        arenas,
        get,
        chapter,
        friction,
        surfaces,
        collide,
        preview,
        draw
    };
})();
