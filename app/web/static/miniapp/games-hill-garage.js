/* Persistent garage UI; balances and unlocks are owned by the server. */
(() => {
    'use strict';
    const H = ArcadeHill,
        art = (...args) => ArcadeHillView.carSvg(...args),
        fmt = n => Math.floor(n).toLocaleString('ru-RU');
    const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    } [c]));
    let current = null;

    function landscape(route) {
        const r = H.getRoute(route);
        return `<svg viewBox="0 0 520 150" preserveAspectRatio="xMidYMid slice" aria-hidden="true"><rect width="520" height="150" fill="${r.sky}"/><circle cx="430" cy="35" r="20" fill="#fff1c4"/><path d="M0 100 100 23l95 80 104-67 94 72 127-60v102H0Z" fill="${r.mountain}"/><path d="M0 112q91-57 180-7t160-9 180 7v47H0Z" fill="${r.soil}" stroke="${r.grass}" stroke-width="5"/></svg>`;
    }

    function routes(s, g) {
        const route = H.getRoute(g.route),
            saved = s.routes.find(r => r.id === route.id);
        return `<div class="hill-route-hero">${landscape(route.id)}<div><span>Свободный заезд</span><h3>${route.name}</h3><p>Рекорд: ${fmt(saved.best)} м</p></div></div><div class="hill-start-line"><span>${H.getCar(s.car).name} · твои улучшения</span><button class="hill-primary" data-drive>В путь →</button></div><div class="hill-route-grid">${s.routes.map(r=>`<button data-route="${r.id}" aria-pressed="${g.route===r.id}" ${r.unlocked?'':'disabled'}>${landscape(r.id)}<b>${H.getRoute(r.id).name}</b><span>${r.unlocked?fmt(r.best)+' м':'С уровня '+r.level}</span></button>`).join('')}</div>`;
    }

    function cars(s) {
        const stat = H.stats(s.car, s.upgrades[s.car]);
        return `<div class="hill-garage-car"><span class="hill-number-plate">${String(s.level).padStart(2,'0')} / ${H.getCar(s.car).name}</span>${art(s.car,s.paint)}<div class="hill-car-colors" aria-label="Цвет машины">${s.paints.map((p,i)=>`<button style="--paint:${p}" data-action="paint" data-item="${p}" aria-label="Цвет ${i+1}" aria-pressed="${p===s.paint}"></button>`).join('')}</div></div><div class="hill-car-stats"><span>Тяга <b>${stat.power.toFixed(1)}</b></span><span>Сцепление <b>${Math.round(stat.grip*100)}%</b></span><span>Бак <b>${stat.tank} л</b></span></div><div class="hill-car-list">${s.cars.map(c=>{const model=H.getCar(c.id);return `<article class="${s.car===c.id?'is-selected':''}">${art(c.id)}<div><h3>${model.name}</h3><p>${model.description}</p></div><button class="hill-secondary" data-action="${c.owned?'select':'buy'}" data-item="${c.id}" ${!c.unlocked||s.car===c.id||!c.owned&&s.balance<c.price?'disabled':''}>${s.car===c.id?'Выбрана':!c.unlocked?'Уровень '+c.level:c.owned?'Выбрать':fmt(c.price)+' монет'}</button></article>`;}).join('')}</div>`;
    }

    function upgrades(s) {
        const stat = H.stats(s.car, s.upgrades[s.car]),
            value = (id, stats) => id === 'engine' ? stats.power.toFixed(1) : id === 'tires' ? Math.round(stats.grip * 100) : id === 'suspension' ? Math.round(stats.travel * 100) : stats.tank;
        return `<div class="hill-section-title"><h3>Мастерская</h3><span>${H.getCar(s.car).name}</span></div><div class="hill-upgrades">${s.parts.map(p=>{const spec=H.upgrades.find(i=>i.id===p.id),next=H.stats(s.car,{...s.upgrades[s.car],[p.id]:p.tier+1});return `<article><div class="hill-upgrade-heading"><h3>${spec.name}</h3><span>${p.tier} / 10</span></div><div class="hill-upgrade-steps" aria-hidden="true">${Array.from({length:10},(_,i)=>`<i class="${i<p.tier?'is-filled':''}"></i>`).join('')}</div><p>${spec.hint}</p><div class="hill-upgrade-effect"><span>${spec.effect}</span><strong>${value(p.id,stat)}${spec.unit}${p.tier<10?` <span>→</span> ${value(p.id,next)}${spec.unit}`:''}</strong></div><button class="hill-primary" data-action="upgrade" data-item="${p.id}" ${p.tier>=10||s.balance<p.price?'disabled':''}>${p.tier===10?'Максимум':`Улучшить · ${fmt(p.price)} монет`}</button></article>`;}).join('')}</div>`;
    }

    function tasks(s, g) {
        const categories = [...new Set(s.tasks.map(t => t.category))],
            shown = s.tasks.filter(t => t.category === g.category);
        return `<div class="hill-task-categories">${categories.map(c=>`<button data-category="${c}" aria-pressed="${c===g.category}">${c}</button>`).join('')}</div><div class="hill-task-list">${shown.map(t=>`<article class="${t.claimed?'is-claimed':''}"><div><h3>${t.route?H.getRoute(t.route).name+' · ':''}${t.name}</h3><progress value="${t.value}" max="${t.target}" aria-label="Прогресс задания"></progress><span>${fmt(t.value)} / ${fmt(t.target)}</span></div><b>${t.claimed?'✓':t.ready?'Готово':`+${fmt(t.reward)}`}${!t.claimed?'<small>монет</small>':''}</b></article>`).join('')}</div>`;
    }

    function missions(g) {
        const saved = g.options.journey,
            stage = g.stage || saved.unlocked,
            m = ArcadeJourney.mission('hill', stage);
        return `<div class="hill-mission-current"><span>Экспедиция · ${saved.cleared} / 24</span><h3>${m.title}</h3><p>Проедь ${m.goal} м</p><button class="hill-primary" data-mission="${stage}">Заезд ${stage} →</button></div><div class="hill-missions">${Array.from({length:24},(_,i)=>{const n=i+1,r=saved.records.find(r=>r.stage===n);return `<button data-stage="${n}" aria-pressed="${stage===n}" ${n>saved.unlocked?'disabled':''}><b>${n}</b><span>${r?'★'.repeat(r.stars)+'☆'.repeat(3-r.stars):n>saved.unlocked?'—':'•'}</span></button>`;}).join('')}</div>`;
    }

    function render(g) {
        const s = g.snapshot,
            ready = s.tasks.filter(t => t.ready && !t.claimed);
        g.dialog.innerHTML = `<header class="hill-garage-header"><div><span>ХОЛМЫ И МОТОРЫ</span><h2>Мой гараж</h2></div><button data-close aria-label="Закрыть гараж">×</button></header><div class="hill-garage-wallet"><div><span>Уровень водителя</span><b>${s.level}</b></div><div><span>Монеты гаража</span><b>${fmt(s.balance)}</b></div><div><span>До уровня ${Math.min(25,s.level+1)}</span><b>${s.next_xp?fmt(s.next_xp-s.xp)+' XP':'Максимум'}</b></div></div><nav class="hill-garage-tabs" aria-label="Гараж">${[['routes','Трассы'],['cars','Машины'],['upgrades','Улучшения'],['tasks','Задания'],['missions','Экспедиция']].map(([id,label])=>`<button data-garage-tab="${id}" aria-pressed="${g.tab===id}">${label}${id==='tasks'&&ready.length?` <i>${ready.length}</i>`:''}</button>`).join('')}</nav><p class="hill-garage-error" role="status" ${g.error?'':'hidden'}>${esc(g.error)}</p>${ready.length?`<div class="hill-claim-line"><span>Готово заданий: ${ready.length}</span><button class="hill-primary" data-action="claim_all">Забрать всё · ${fmt(ready.reduce((n,t)=>n+t.reward,0))}</button></div>`:''}<main class="hill-garage-content">${g.tab==='routes'?routes(s,g):g.tab==='cars'?cars(s):g.tab==='upgrades'?upgrades(s):g.tab==='tasks'?tasks(s,g):missions(g)}</main>`;
    }
    async function open(api, options) {
        if (current) return;
        const dialog = document.createElement('dialog');
        dialog.className = 'hill-garage-dialog';
        dialog.innerHTML = '<p class="hill-garage-loading">Открываем гараж…</p>';
        document.body.append(dialog);
        dialog.showModal();
        const g = {
            api,
            options,
            dialog,
            tab: 'routes',
            route: 'meadow',
            category: 'Сегодня',
            snapshot: null,
            busy: false,
            error: ''
        };
        current = g;
        const close = () => {
            dialog.close();
            dialog.remove();
            current = null;
        };
        dialog.addEventListener('cancel', e => {
            e.preventDefault();
            if (!g.busy) close();
        });
        dialog.onclick = async e => {
            const b = e.target.closest('button');
            if (!b || b.disabled || g.busy) return;
            if (b.hasAttribute('data-close')) {
                close();
                return;
            }
            if (b.dataset.garageTab) {
                g.tab = b.dataset.garageTab;
                render(g);
                return;
            }
            if (b.dataset.route) {
                g.route = b.dataset.route;
                render(g);
                return;
            }
            if (b.dataset.category) {
                g.category = b.dataset.category;
                render(g);
                return;
            }
            if (b.dataset.stage) {
                g.stage = +b.dataset.stage;
                render(g);
                return;
            }
            if (b.hasAttribute('data-drive') || b.dataset.mission) {
                close();
                options.onDrive(g.route, b.dataset.mission ? +b.dataset.mission : null);
                return;
            }
            if (b.dataset.action) {
                g.busy = true;
                b.disabled = true;
                g.error = '';
                const body = {
                    id: crypto.randomUUID(),
                    action: b.dataset.action,
                    item: b.dataset.item || null
                };
                try {
                    try {
                        g.snapshot = await api('/garage/actions', {
                            method: 'POST',
                            body
                        });
                    } catch (error) {
                        g.snapshot = await api('/garage/actions', {
                            method: 'POST',
                            body
                        });
                    }
                } catch (error) {
                    g.error = error.message;
                    try {
                        g.snapshot = await api('/garage');
                    } catch {}
                } finally {
                    g.busy = false;
                    if (current === g) render(g);
                }
            }
        };
        try {
            g.snapshot = await api('/garage');
            if (current === g) render(g);
        } catch (error) {
            if (current === g) {
                dialog.innerHTML = `<p class="hill-garage-loading">${esc(error.message)}</p><button data-close>Закрыть</button>`;
            }
        }
    }
    window.ArcadeHillGarage = {
        open,
        get isOpen() {
            return !!current;
        }
    };
})();
