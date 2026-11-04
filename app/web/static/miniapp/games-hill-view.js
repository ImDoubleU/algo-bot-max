/* Driving presentation. Rendering never changes the verified simulation. */
(() => {
    'use strict';
    const H = ArcadeHill;

    function carSvg(id = 'scout', color = H.getCar(id).color) {
        const roof = id === 'truck' ? 'M107 104V54h43l23 50' : id === 'buggy' ? 'M60 107 84 76h40l28 31' : id === 'rover' ? 'M54 104Q57 45 110 45t49 59Z' : 'M64 104l14-42h44l25 42';
        const body = id === 'buggy' ? 'M37 115 94 103l67 10 40 14-15 14H43Z' : id === 'rover' ? 'M39 105h138q30 5 18 31l-9 5H43q-14-16-4-36Z' : 'M48 103h129l17 18-8 20H43l-7-19Z';
        const dx = id === 'truck' ? 32 : 0,
            dy = id === 'buggy' ? 12 : 0;
        return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 176" fill="none" aria-hidden="true"><path d="M8 153q66-35 120-12t120-9" stroke="#9cb395" stroke-width="4"/><g transform="rotate(-8 128 100)" stroke="#344737" stroke-width="3" stroke-linejoin="round"><path d="${roof}" fill="${id==='buggy'?'none':'#d4e8e1'}"/><path d="${body}" fill="${color}"/>${id==='truck'?`<path d="M45 104V81h56v28" fill="${color}"/>`:id==='rover'?'<path d="M76 53V29l13-10" stroke="#6c8374"/><circle cx="90" cy="18" r="4" fill="#f2cf7c"/><path d="M57 119h93m-93 7h93" stroke="#e9e9d4"/>':'<path d="M124 66v36M42 120h151"/>'}<path d="M49 98h28v10H49Z" fill="#f0d08b"/><path d="M162 111h17v10h-17Z" fill="#fff1bf"/><path d="m54 140 11-26m83 26 11-26" stroke="#a1b2a2" stroke-width="5"/><g fill="#38423c"><circle cx="67" cy="141" r="23"/><circle cx="163" cy="141" r="23"/></g><g fill="#d8cfb4"><circle cx="67" cy="141" r="12"/><circle cx="163" cy="141" r="12"/></g><path d="m67 132 1 18m-9-9h18m86-9v18m-9-9h18" stroke="#677565" stroke-width="2"/><g transform="translate(${dx} ${dy})"><circle cx="105" cy="80" r="12" fill="#ecd4a4"/><path d="M92 77q13-23 26 0" fill="#587361"/><path d="M106 79h7" stroke-width="2"/></g></g></svg>`;
    }

    function mount(stage, send, options) {
        stage.dataset.game = 'hill';
        stage.innerHTML = `<div class="hill-drive"><div class="hill-instruments"><div><span>Скорость</span><b data-hill-speed>0 <small>км/ч</small></b></div><div class="hill-fuel"><span>Топливо <b data-hill-fuel>100</b></span><progress max="100" value="100" aria-label="Топливо"></progress></div><div><span>Монеты</span><b data-hill-coins>0</b></div></div><canvas class="hill-canvas" aria-label="Трасса. Вправо — газ, влево — тормоз." tabindex="0"></canvas><div class="hill-pedals"><button data-pedal="brake" aria-label="Тормоз"><span>↓</span>Тормоз <kbd>← / A</kbd></button><span class="hill-route-label"></span><button data-pedal="gas" aria-label="Газ"><span>↑</span>Газ <kbd>→ / D</kbd></button></div></div>`;
        stage.querySelector('.hill-route-label').setAttribute('data-hill-route', '');
        if (options.readOnly) {
            stage.querySelector('.hill-drive').classList.add('is-replay');
            stage.querySelector('.hill-instruments>div:first-child>span').textContent = 'Дистанция';
            const label = document.createElement('p');
            label.className = 'hill-replay-route';
            label.setAttribute('data-hill-route', '');
            stage.querySelector('.hill-pedals').replaceWith(label);
            stage.querySelector('canvas').setAttribute('aria-label', 'Запись заезда');
        }
        const canvas = stage.querySelector('canvas'),
            c = canvas.getContext('2d'),
            pressed = {
                gas: new Set(),
                brake: new Set()
            },
            state = {
                paused: true,
                reset: false
            },
            signal = options.signal;
        const on = (node, event, fn) => {
            if (!options.readOnly) node.addEventListener(event, fn, {
                signal
            });
        };
        const control = (pedal, key, down) => {
            const set = pressed[pedal],
                was = !!set.size;
            down ? set.add(key) : set.delete(key);
            const active = !!set.size;
            stage.querySelector(`[data-pedal="${pedal}"]`).classList.toggle('is-pressed', active);
            if (active !== was && !options.paused()) send({
                type: 'pedal',
                pedal,
                value: Number(active),
                source: options.device
            });
        };
        for (const button of stage.querySelectorAll('[data-pedal]')) {
            on(button, 'pointerdown', e => {
                e.preventDefault();
                if (options.paused()) return;
                button.setPointerCapture(e.pointerId);
                control(button.dataset.pedal, e.pointerId, true);
            });
            for (const event of ['pointerup', 'pointercancel', 'lostpointercapture']) on(button, event, e => control(button.dataset.pedal, e.pointerId, false));
        }
        const pedalFor = code => ['ArrowRight', 'KeyD', 'Space'].includes(code) ? 'gas' : ['ArrowLeft', 'KeyA'].includes(code) ? 'brake' : null;
        on(document, 'keydown', e => {
            if (e.code === 'Space' && e.target.closest?.('button')) return;
            const pedal = pedalFor(e.code);
            if (!pedal || e.repeat || options.phase?.() === 'paused') return;
            e.preventDefault();
            control(pedal, e.code, true);
        });
        on(document, 'keyup', e => {
            if (e.code === 'Space' && e.target.closest?.('button') && !pressed.gas.has('Space')) return;
            const pedal = pedalFor(e.code);
            if (pedal) {
                e.preventDefault();
                control(pedal, e.code, false);
            }
        });
        const releaseControls = () => {
            state.reset = true;
            for (const key of ['gas', 'brake']) {
                for (const held of [...pressed[key]]) control(key, held, false);
            }
        };
        on(window, 'blur', releaseControls);
        on(document, 'visibilitychange', () => {
            if (document.hidden) releaseControls();
        });

        function update(w) {
            const h = w.hill;
            if (!h) return;
            const paused = options.paused();
            if (options.phase?.() === 'paused') {
                state.reset = true;
                for (const p of ['gas', 'brake']) pressed[p].clear();
            }
            const synchronize = !paused && (state.reset || state.paused);
            state.paused = paused;
            if (synchronize) {
                state.reset = false;
                for (const p of ['gas', 'brake']) {
                    const desired = Number(!!pressed[p].size);
                    stage.querySelector(`[data-pedal="${p}"]`).classList.toggle('is-pressed', !!desired);
                    if (h[p] !== desired) send({
                        type: 'pedal',
                        pedal: p,
                        value: desired,
                        source: options.device
                    });
                }
            }
            const route = H.getRoute(h.route),
                width = canvas.clientWidth,
                height = canvas.clientHeight;
            if (!width || !height) return;
            const dpr = Math.min(2, devicePixelRatio || 1);
            if (canvas.width !== Math.round(width * dpr) || canvas.height !== Math.round(height * dpr)) {
                canvas.width = Math.round(width * dpr);
                canvas.height = Math.round(height * dpr);
            }
            c.setTransform(dpr, 0, 0, dpr, 0, 0);
            const scale = Math.min(width < 500 ? 21 : 29, Math.max(12, height / 5)),
                camera = h.x - width * .34 / scale,
                base = Math.max(H.terrain(w, h.x), h.y - 4),
                x = wx => (wx - camera) * scale,
                y = wy => height * .69 - (wy - base) * scale;
            const gradient = c.createLinearGradient(0, 0, 0, height);
            gradient.addColorStop(0, route.sky);
            gradient.addColorStop(1, h.route === 'moon' ? '#484b66' : '#f1edcf');
            c.fillStyle = gradient;
            c.fillRect(0, 0, width, height);
            c.fillStyle = h.route === 'moon' ? '#f5edc5' : '#fff0c0';
            c.beginPath();
            c.arc(width * .8, height * .19, 25, 0, Math.PI * 2);
            c.fill();
            if (h.route === 'moon') {
                c.fillStyle = '#eee8cf';
                for (let i = 0; i < 32; i++) c.fillRect((i * 79 + 17) % width, (i * 41 + 5) % (height * .6), 2, 2);
            }
            for (let layer = 0; layer < 2; layer++) {
                c.fillStyle = layer ? route.mountain : route.mountain + '77';
                c.beginPath();
                c.moveTo(0, height);
                for (let px = 0; px <= width + 8; px += 8) c.lineTo(px, height * (.5 + layer * .12) + Math.sin(px / 125 + camera * (.025 + layer * .018)) * 35 + Math.sin(px / 47 + layer) * 9);
                c.lineTo(width, height);
                c.closePath();
                c.fill();
            }
            c.beginPath();
            c.moveTo(-8, height + 8);
            for (let px = -8; px <= width + 8; px += 6) c.lineTo(px, y(H.terrain(w, camera + px / scale)));
            c.lineTo(width + 8, height + 8);
            c.closePath();
            c.fillStyle = route.soil;
            c.fill();
            c.beginPath();
            for (let px = -8; px <= width + 8; px += 6) {
                const py = y(H.terrain(w, camera + px / scale));
                px === -8 ? c.moveTo(px, py) : c.lineTo(px, py);
            }
            c.strokeStyle = route.grass;
            c.lineWidth = 8;
            c.lineJoin = 'round';
            c.stroke();
            // Trackside signs and supplies share coordinates with the simulation.
            for (let i = Math.max(1, Math.floor(camera / 18)); i < Math.ceil((camera + width / scale) / 18) + 1; i++) {
                if (h.collected[i]) continue;
                const wx = i * 18,
                    px = x(wx),
                    py = y(H.terrain(w, wx) + 1);
                if (i % 26 === 0) {
                    c.fillStyle = '#ba5040';
                    c.fillRect(px - 8, py - 12, 16, 20);
                    c.strokeStyle = '#fff3d0';
                    c.lineWidth = 2;
                    c.strokeRect(px - 3, py - 16, 8, 5);
                    c.beginPath();
                    c.moveTo(px - 5, py - 7);
                    c.lineTo(px + 5, py + 3);
                    c.moveTo(px + 5, py - 7);
                    c.lineTo(px - 5, py + 3);
                    c.stroke();
                } else {
                    c.fillStyle = '#f6cf65';
                    c.beginPath();
                    c.arc(px, py, 7, 0, 7);
                    c.fill();
                    c.strokeStyle = '#b9903e';
                    c.lineWidth = 2;
                    c.stroke();
                    c.fillStyle = '#9c7636';
                    c.font = 'bold 10px system-ui';
                    c.textAlign = 'center';
                    c.fillText('5', px, py + 3);
                }
            }
            for (let n = Math.max(1, Math.floor(camera / 100)); n <= Math.ceil((camera + width / scale) / 100); n++) {
                const px = x(n * 100),
                    py = y(H.terrain(w, n * 100));
                c.strokeStyle = '#806a4d';
                c.lineWidth = 3;
                c.beginPath();
                c.moveTo(px, py);
                c.lineTo(px, py - 36);
                c.stroke();
                c.fillStyle = '#f7ebc9';
                c.fillRect(px - 20, py - 43, 40, 19);
                c.fillStyle = '#475c43';
                c.textAlign = 'center';
                c.font = 'bold 11px system-ui';
                c.fillText(n * 100 + ' м', px, py - 30);
            }
            // Springs connect the moving body to independently compressed wheel centres.
            c.strokeStyle = '#bec7b8';
            c.lineWidth = 3;
            for (let i = 0; i < h.wheels.length; i++) {
                const wheel = h.wheels[i],
                    offset = i ? 1.22 : -1.22,
                    ax = h.x + offset * Math.cos(h.angle) + .18 * Math.sin(h.angle),
                    ay = h.y + offset * Math.sin(h.angle) - .18 * Math.cos(h.angle);
                c.beginPath();
                c.moveTo(x(ax), y(ay));
                for (let j = 1; j <= 6; j++) c.lineTo(x(ax) + (j % 2 ? 3 : -3), y(ay) + (y(wheel.y) - y(ay)) * j / 7);
                c.lineTo(x(wheel.x), y(wheel.y));
                c.stroke();
                c.save();
                c.translate(x(wheel.x), y(wheel.y));
                c.rotate(h.x / .46);
                c.fillStyle = '#344139';
                c.beginPath();
                c.arc(0, 0, .46 * scale, 0, 7);
                c.fill();
                c.strokeStyle = '#192b24';
                c.lineWidth = 3;
                c.stroke();
                c.fillStyle = '#c9c5b3';
                c.beginPath();
                c.arc(0, 0, .25 * scale, 0, 7);
                c.fill();
                c.strokeStyle = '#637164';
                c.lineWidth = 2;
                c.beginPath();
                c.moveTo(-.23 * scale, 0);
                c.lineTo(.23 * scale, 0);
                c.moveTo(0, -.23 * scale);
                c.lineTo(0, .23 * scale);
                c.stroke();
                c.restore();
            }
            c.save();
            c.translate(x(h.x), y(h.y));
            c.rotate(-h.angle);
            c.scale(scale, -scale);
            c.lineWidth = .09;
            c.strokeStyle = '#334539';
            c.lineJoin = 'round';
            c.fillStyle = '#d7ece5';
            c.beginPath();
            if (h.car === 'rover') {
                c.moveTo(-1, .3);
                c.bezierCurveTo(-1, 1.7, .8, 1.7, 1, .3);
            } else if (h.car === 'truck') {
                c.moveTo(.1, .3);
                c.lineTo(.1, 1.35);
                c.lineTo(.9, 1.35);
                c.lineTo(1.3, .3);
            } else {
                c.moveTo(-.85, .3);
                c.lineTo(-.6, h.car === 'buggy' ? .9 : 1.14);
                c.lineTo(.5, h.car === 'buggy' ? .9 : 1.14);
                c.lineTo(1, .3);
            }
            c.closePath();
            if (h.car !== 'buggy') c.fill();
            c.stroke();
            c.fillStyle = h.paint;
            c.beginPath();
            c.moveTo(-1.7, .35);
            c.lineTo(1.4, .35);
            c.lineTo(1.75, 0);
            c.lineTo(1.6, -.35);
            c.lineTo(-1.65, -.35);
            c.closePath();
            c.fill();
            c.stroke();
            if (h.car === 'truck') {
                c.fillStyle = h.paint;
                c.fillRect(-1.6, .3, 1.55, .55);
                c.strokeRect(-1.6, .3, 1.55, .55);
            }
            if (h.car === 'rover') {
                c.beginPath();
                c.moveTo(-.8, 1.2);
                c.lineTo(-.8, 1.8);
                c.stroke();
                c.fillStyle = '#e9cd80';
                c.beginPath();
                c.arc(-.8, 1.85, .09, 0, 7);
                c.fill();
            }
            const driver = h.car === 'truck' ? .65 : .05;
            c.fillStyle = '#f4dfaf';
            c.beginPath();
            c.arc(driver, .72, .25, 0, 7);
            c.fill();
            c.fillStyle = '#57775f';
            c.fillRect(driver - .25, .87, .5, .13);
            c.fillStyle = '#3d493a';
            c.beginPath();
            c.arc(driver + .1, .75, .035, 0, 7);
            c.fill();
            if (h.stats.power > H.getCar(h.car).power * 1.3) {
                c.fillStyle = '#687d66';
                c.fillRect(1, .35, .4, .25);
                c.strokeRect(1, .35, .4, .25);
            }
            c.fillStyle = '#fff2b7';
            c.fillRect(1.35, .05, .23, .15);
            c.fillStyle = '#bd5747';
            c.fillRect(-1.68, -.1, .12, .16);
            c.restore();
            if (h.contact && h.gas && !paused && options.quality() !== 'low') {
                c.fillStyle = route.soil + 'aa';
                for (let i = 0; i < 7; i++) {
                    const px = x(h.x - 1.6) - ((w.tick * 2 + i * 13) % 45),
                        py = y(H.terrain(w, h.x)) - 6 - Math.sin(i + w.time * 7) * 8;
                    c.beginPath();
                    c.arc(px, py, 2 + i % 3, 0, 7);
                    c.fill();
                }
            }
            if (h.airStart !== null && w.time - h.airStart > .6) {
                c.fillStyle = h.route === 'moon' ? '#fff0b5' : '#385943';
                c.font = 'bold 18px system-ui';
                c.textAlign = 'center';
                c.fillText('В воздухе ' + (w.time - h.airStart).toFixed(1) + ' с', width / 2, 32);
            }
            stage.querySelector('[data-hill-speed]').innerHTML = options.readOnly ? w.score + ' <small>м</small>' : Math.round(Math.abs(h.vx) * 3.6) + ' <small>км/ч</small>';
            stage.querySelector('[data-hill-coins]').textContent = h.coins;
            stage.querySelector('[data-hill-fuel]').textContent = Math.ceil(h.fuel);
            const fuel = stage.querySelector('progress');
            fuel.max = h.stats.tank;
            fuel.value = h.fuel;
            fuel.classList.toggle('is-low', h.fuel < 20);
            stage.querySelector('[data-hill-route]').textContent = route.name;
        }
        return {
            update,
            canvas
        };
    }
    window.ArcadeHillView = {
        mount,
        carSvg
    };
})();
