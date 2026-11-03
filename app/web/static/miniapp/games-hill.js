/* Fixed-step hill driving, shared verbatim with the server replay verifier. */
(() => {
    'use strict';
    const game = {
        id: 'hill',
        fresh: true,
        name: 'Холмы и моторы',
        tag: 'Дорога начинается в гараже',
        kind: 'fun',
        icon: 'hill',
        color: 'mint',
        goal: 500,
        unit: 'м',
        tutorial: 'Удерживай газ справа. Тормоз слева помогает опустить нос в полёте.',
        hint: 'Газ — стрелка вправо или D. Тормоз — влево или A. Балансируй в воздухе, собирай топливо и приземляйся на колёса.'
    };
    const routes = [{
        id: 'meadow',
        name: 'Зелёная долина',
        level: 1,
        gravity: 18,
        grip: 1,
        amplitude: 3.5,
        sky: '#c8e4dc',
        mountain: '#91b9a2',
        soil: '#ae8060',
        grass: '#57815a'
    }, {
        id: 'dunes',
        name: 'Песчаное море',
        level: 3,
        gravity: 18,
        grip: .83,
        amplitude: 5,
        sky: '#f7dba5',
        mountain: '#dbaf77',
        soil: '#cc945b',
        grass: '#e6bf7d'
    }, {
        id: 'snow',
        name: 'Северный перевал',
        level: 6,
        gravity: 18,
        grip: .55,
        amplitude: 4.8,
        sky: '#d6e7ef',
        mountain: '#a3bdcd',
        soil: '#8a9da8',
        grass: '#f4f4e9'
    }, {
        id: 'moon',
        name: 'Лунная станция',
        level: 10,
        gravity: 6,
        grip: .9,
        amplitude: 7,
        sky: '#252c46',
        mountain: '#586078',
        soil: '#797d8b',
        grass: '#a7afbc'
    }, {
        id: 'volcano',
        name: 'Огненный хребет',
        level: 15,
        gravity: 20,
        grip: .95,
        amplitude: 6.5,
        sky: '#e7b296',
        mountain: '#9c6960',
        soil: '#66504b',
        grass: '#d98455'
    }];
    const cars = [{
        id: 'scout',
        name: 'Скаут',
        level: 1,
        price: 0,
        power: 19,
        speed: 25,
        suspension: 68,
        air: 3,
        color: '#e7a64d',
        description: 'Лёгкий джип. Хорошо слушается в воздухе.'
    }, {
        id: 'buggy',
        name: 'Багги',
        level: 4,
        price: 1800,
        power: 23,
        speed: 30,
        suspension: 61,
        air: 4,
        color: '#66a99c',
        description: 'Быстрый и лёгкий. Для длинных прыжков.'
    }, {
        id: 'truck',
        name: 'Вездеход',
        level: 8,
        price: 5500,
        power: 28,
        speed: 23,
        suspension: 82,
        air: 2.1,
        color: '#b87758',
        description: 'Сильный двигатель и устойчивая подвеска.'
    }, {
        id: 'rover',
        name: 'Луноход',
        level: 13,
        price: 14000,
        power: 24,
        speed: 28,
        suspension: 57,
        air: 4.5,
        color: '#a0a8c0',
        description: 'Мягкая посадка и точный баланс на Луне.'
    }];
    const upgrades = [{
        id: 'engine',
        name: 'Двигатель',
        base: 130,
        effect: 'Тяга',
        unit: '',
        hint: 'Лучше забирается на крутые подъёмы.'
    }, {
        id: 'tires',
        name: 'Шины',
        base: 110,
        effect: 'Сцепление',
        unit: '%',
        hint: 'Меньше проскальзывания на песке и снегу.'
    }, {
        id: 'suspension',
        name: 'Подвеска',
        base: 100,
        effect: 'Ход подвески',
        unit: 'см',
        hint: 'Смягчает удары при приземлении.'
    }, {
        id: 'tank',
        name: 'Бак',
        base: 90,
        effect: 'Запас топлива',
        unit: 'л',
        hint: 'Дольше едет между канистрами.'
    }];
    const getRoute = id => routes.find(r => r.id === id) || routes[0];
    const getCar = id => cars.find(c => c.id === id) || cars[0];
    const clamp = (n, a, b) => Math.max(a, Math.min(b, n));

    function stats(carId = 'scout', levels = {}) {
        const c = getCar(carId),
            l = id => clamp(Number(levels[id]) || 0, 0, 10);
        return {
            power: c.power * (1 + l('engine') * .085),
            speed: c.speed * (1 + l('engine') * .025),
            grip: 1 + l('tires') * .08,
            travel: .68 + l('suspension') * .025,
            spring: c.suspension,
            damping: 5.8 + l('suspension') * .3,
            tank: 100 + l('tank') * 8,
            air: c.air
        };
    }

    function terrain(w, x) {
        const h = w.hill,
            r = getRoute(h.route),
            p = (w.seed % 997) / 157,
            start = clamp((x - 14) / 45, 0, 1),
            ramp = start * start * (3 - 2 * start);
        const k = 1 + Math.min(1.2, Math.max(0, x - 450) / 1800);
        const bumps = clamp((x - 80) / 650, 0, 1) * Math.sin(x * .32 + p) * Math.min(2.5, r.amplitude * .42);
        return ramp * (r.amplitude * k * (Math.sin(x * .058 + p) * .7 + Math.sin(x * .133 + p * .7) * .23 + Math.sin(x * .021 - p) * .5) + bumps);
    }
    const slope = (w, x) => (terrain(w, x + .15) - terrain(w, x - .15)) / .3;

    function create(w, setup) {
        const c = setup.hill || {},
            route = w.mode === 'ranked' ? 'meadow' : c.route || (w.journey ? routes[[0, 0, 1, 2, 3, 4][w.journey.chapter]].id : 'meadow');
        const car = w.mode === 'ranked' ? 'scout' : c.car || 'scout';
        w.hill = {
            route: getRoute(route).id,
            car: getCar(car).id,
            paint: c.paint || getCar(car).color,
            stats: stats(car, w.mode === 'ranked' ? {} : c.upgrades),
            x: 8,
            y: 1.5,
            vx: 0,
            vy: 0,
            angle: 0,
            omega: 0,
            gas: 0,
            brake: 0,
            fuel: 0,
            maxX: 8,
            coins: 0,
            flips: 0,
            jumps: 0,
            airTime: 0,
            bestAir: 0,
            airStart: null,
            airAngle: 0,
            contact: 0,
            roofTime: 0,
            stuck: 0,
            lastBest: 0,
            inputs: 0,
            collected: {},
            wheels: []
        };
        w.hill.fuel = w.hill.stats.tank;
        const h = w.hill,
            compression = getRoute(h.route).gravity / (2 * h.stats.spring);
        h.y = terrain(w, h.x) + .46 + h.stats.travel + .18 - compression;
        h.wheels = [-1.22, 1.22].map(offset => ({
            x: h.x + offset,
            y: terrain(w, h.x + offset) + .46,
            compression
        }));
        h.contact = 2;
        w.details.physics = 'hill1';
    }

    function input(w, a) {
        if (a.type !== 'pedal' || !['gas', 'brake'].includes(a.pedal) || ![0, 1].includes(a.value)) return false;
        if (w.hill[a.pedal] === a.value) return false;
        w.hill[a.pedal] = a.value;
        w.hill.inputs++;
        return true;
    }

    function physics(w, dt) {
        const h = w.hill,
            s = h.stats,
            r = getRoute(h.route),
            co = Math.cos(h.angle),
            si = Math.sin(h.angle);
        let fx = -h.vx * .22,
            fy = -r.gravity,
            torque = -h.omega * .7,
            contacts = 0;
        h.wheels = [];
        for (const offset of [-1.22, 1.22]) {
            const rx = offset * co + .18 * si,
                ry = offset * si - .18 * co;
            const x = h.x + rx,
                y = h.y + ry,
                g = terrain(w, x),
                m = slope(w, x),
                n = 1 / Math.sqrt(1 + m * m);
            const compression = g + .46 + s.travel - y,
                vy = h.vy + h.omega * rx,
                vx = h.vx - h.omega * ry;
            let force = compression > 0 ? clamp(compression * s.spring - (-vx * m + vy) * n * s.damping, 0, 100) : 0;
            if (force > 0) {
                contacts++;
                const nx = -m * n,
                    ny = n;
                const reverse = h.brake && !h.gas && h.vx <= .75;
                const drive = h.fuel > 0 ? (h.gas * s.power * .48 - (reverse ? s.power * .38 : 0)) : 0;
                const resistance = (h.brake && !reverse ? Math.min(38, Math.abs(h.vx) * 14) : Math.abs(h.vx) * .22) * Math.sign(h.vx);
                const traction = clamp(drive - resistance, -force * r.grip * s.grip * 1.1, force * r.grip * s.grip * 1.1);
                const ax = nx * force + ny * traction,
                    ay = ny * force - nx * traction;
                fx += ax;
                fy += ay;
                torque += rx * ay - ry * ax;
            }
            h.wheels.push({
                x,
                y: compression > 0 ? g + .46 : y - s.travel,
                compression: clamp(compression, 0, s.travel)
            });
        }
        if (!contacts) torque += (h.gas - h.brake) * s.air * 4;
        h.vx = clamp(h.vx + fx * dt, -8, s.speed);
        h.vy = clamp(h.vy + fy * dt, -40, 40);
        h.omega = clamp(h.omega + torque / 2.7 * dt, -6, 6);
        h.x = Math.max(2, h.x + h.vx * dt);
        h.y += h.vy * dt;
        h.angle += h.omega * dt;
        h.contact = contacts;
    }

    function step(w, H) {
        const h = w.hill;
        for (let i = 0; i < 4; i++) physics(w, H.DT / 4);
        h.fuel = Math.max(0, h.fuel - (.12 + Number(!!h.gas || h.brake && h.vx < -.5) * 1.65) * H.DT);
        h.maxX = Math.max(h.maxX, h.x);
        w.score = Math.max(0, Math.floor(h.maxX - 8));
        w.level = 1 + Math.floor(w.score / 350);
        if (h.contact === 0) {
            h.airTime += H.DT;
            if (h.airStart === null) {
                h.airStart = w.time;
                h.airAngle = h.angle;
            }
            h.bestAir = Math.max(h.bestAir, w.time - h.airStart);
        } else if (h.airStart !== null) {
            const air = w.time - h.airStart;
            if (air > .35) {
                h.jumps++;
                H.emit(w, 'land');
            }
            const flips = Math.floor((Math.abs(h.angle - h.airAngle) + .15) / (Math.PI * 2));
            if (flips && air > .5 && Math.cos(h.angle) > .65) {
                h.flips += flips;
                h.coins += flips * 50;
                H.emit(w, 'perfect');
            }
            h.airStart = null;
        }
        for (let i = Math.max(1, Math.floor((h.x - 3) / 18)); i <= Math.ceil((h.x + 3) / 18); i++) {
            const x = 18 * i,
                fuel = i % 26 === 0,
                y = terrain(w, x) + 1;
            if (!h.collected[i] && Math.abs(h.x - x) < 2.3 && Math.abs(h.y - y) < 2.8) {
                h.collected[i] = 1;
                if (fuel) {
                    h.fuel = Math.min(h.stats.tank, h.fuel + 45);
                    H.emit(w, 'gold');
                } else {
                    h.coins += 5;
                    H.emit(w, 'score');
                }
            }
        }
        const co = Math.cos(h.angle),
            si = Math.sin(h.angle);
        const roof = [-1, .9].some(rx => h.y + rx * si + .74 * co < terrain(w, h.x + rx * co - .74 * si) + .1);
        h.roofTime = roof ? h.roofTime + H.DT : 0;
        if (w.score > h.lastBest + 2) {
            h.lastBest = w.score;
            h.stuck = 0;
        } else h.stuck += H.DT;
        if (h.roofTime > .25) H.end(w, 'Перевернулся. Перед посадкой выровняй машину.');
        if (h.fuel <= 0 && Math.abs(h.vx) < .8) H.end(w, 'Топливо закончилось');
        if (h.stuck > 18 && w.time > 20) H.end(w, 'Машина застряла. Попробуй другой разгон.');
        if (w.time >= 600) H.end(w, 'Заезд завершён');
        Object.assign(w.details, {
            physics: 'hill1',
            route: h.route,
            car: h.car,
            coins: h.coins,
            flips: h.flips,
            jumps: h.jumps,
            airTimeMs: Math.round(h.airTime * 1000),
            bestAirMs: Math.round(h.bestAir * 1000),
            fuel: Math.round(h.fuel),
            inputs: h.inputs
        });
    }
    window.ArcadeHill = {
        game,
        routes,
        cars,
        upgrades,
        getRoute,
        getCar,
        stats,
        terrain,
        slope,
        create,
        input,
        step
    };
})();
