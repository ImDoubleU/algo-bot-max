/* Driving presentation. Rendering never changes the verified simulation. */
(() => {
    'use strict';
    const H = ArcadeHill;

    function carSvg(id = 'scout', color) {
        return ArcadeHillArt.svg(id, color);
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
            const scale = Math.min(width < 500 ? 25 : 33, Math.max(12, height / 5)),
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
            // Suspension sits behind the shell; tires stay visible in front of the body.
            ArcadeHillArt.drawSuspension(c, h, x, y, scale);
            c.save();
            c.translate(x(h.x), y(h.y));
            c.rotate(-h.angle);
            c.scale(scale, -scale);
            ArcadeHillArt.drawBody(c, h);
            c.restore();
            ArcadeHillArt.drawWheels(c, h, x, y, scale);
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
